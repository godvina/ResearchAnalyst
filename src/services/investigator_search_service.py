"""Investigator Search Service — Natural language directive parsing and OSINT execution.

Accepts natural language directives from investigators, uses Amazon Bedrock (Nova Pro)
to interpret them into structured search parameters, executes OSINT queries via
OsintDataGatherer, and returns scored findings with directive_text preserved.

No EC2, no bulk processing (100+ items). Uses Bedrock for directive parsing only.
Individual finding processing — each OSINT result scored and returned separately.
Target: complete within 3 seconds (Bedrock parsing + OSINT execution).
"""

import json
import logging
import uuid
from typing import Any

from models.signal_mining import (
    DirectiveResult,
    Finding,
    FlatIndicator,
    ParsedDirective,
)
from services.iov_taxonomy_service import IovTaxonomyService
from services.signal_scorer import SignalScorer

logger = logging.getLogger(__name__)


class InvestigatorSearchService:
    """Parses investigator directives via Bedrock and executes OSINT searches.

    Converts natural language search directives into structured queries,
    validates source availability, executes against OSINT backends, and
    returns scored findings with the original directive_text preserved
    on every finding (Requirement 5.5).

    Individual finding processing only — no bulk/batch operations.
    """

    MODEL_ID = "amazon.nova-pro-v1:0"

    SUPPORTED_SOURCES = [
        "sam_gov",
        "fpds_gov",
        "usaspending_gov",
        "sec_edgar",
        "pacer",
        "news_press",
        "state_corporate_registry",
    ]

    DOCUMENT_TYPE_MAP = {
        "PACER filings": "pacer",
        "Form 990s": "sec_edgar",
        "SEC filings": "sec_edgar",
        "news": "news_press",
        "government contracts": "fpds_gov",
        "spending": "usaspending_gov",
        "SAM registrations": "sam_gov",
        "corporate registry": "state_corporate_registry",
    }

    def __init__(
        self,
        bedrock_client: Any,
        osint_gatherer: Any,
        signal_scorer: SignalScorer,
        iov_taxonomy_service: IovTaxonomyService,
    ) -> None:
        """Initialize with required service dependencies.

        Args:
            bedrock_client: boto3 Bedrock Runtime client for directive parsing.
            osint_gatherer: OsintDataGatherer instance for executing OSINT queries.
            signal_scorer: SignalScorer for scoring findings against IoV indicators.
            iov_taxonomy_service: IovTaxonomyService for loading indicator hierarchies.
        """
        self.bedrock_client = bedrock_client
        self.osint_gatherer = osint_gatherer
        self.signal_scorer = signal_scorer
        self.iov_taxonomy_service = iov_taxonomy_service

    def execute_directive(
        self,
        directive: str,
        lead_id: str,
        case_type: str,
        subjects: list[str],
    ) -> DirectiveResult:
        """Parse a natural language directive and execute OSINT searches.

        Workflow:
        1. Parse directive via Bedrock into structured search parameters
        2. Validate referenced sources are supported
        3. Execute OSINT queries via OsintDataGatherer
        4. Score results against IoV hierarchy
        5. Associate directive_text with ALL resulting findings (Req 5.5)

        Args:
            directive: Natural language search directive from investigator.
            lead_id: UUID of the parent pre-case lead.
            case_type: Antitrust case type for IoV taxonomy lookup.
            subjects: List of subject names for OSINT queries.

        Returns:
            DirectiveResult with findings, directive_text, and unsupported_sources.
        """
        # Step 1: Parse directive via Bedrock
        parsed = self._parse_directive(directive, case_type)

        # Step 2: Resolve target sources from document types and explicit sources
        resolved_sources = self._resolve_sources(parsed)
        unsupported_sources = self._identify_unsupported(parsed)

        # If no valid sources resolved, return empty result with unsupported info
        if not resolved_sources:
            logger.warning(
                "No supported sources resolved from directive: %s", directive[:100]
            )
            return DirectiveResult(
                findings=[],
                directive_text=directive,
                unsupported_sources=unsupported_sources,
            )

        # Step 3: Load IoV taxonomy for scoring
        flat_indicators: list[FlatIndicator] = []
        try:
            hierarchy = self.iov_taxonomy_service.load_taxonomy(case_type)
            flat_indicators = self.iov_taxonomy_service.flatten_indicators(hierarchy)
        except Exception as e:
            logger.error(
                "Failed to load IoV taxonomy for case_type=%s: %s", case_type, e
            )

        # Step 4: Execute OSINT queries
        # Merge subjects from directive parsing with provided subjects
        all_subjects = list(subjects)
        for person in parsed.persons:
            if person not in all_subjects:
                all_subjects.append(person)
        for org in parsed.organizations:
            if org not in all_subjects:
                all_subjects.append(org)

        findings: list[Finding] = []

        try:
            gather_result = self.osint_gatherer.gather(
                lead_id=lead_id,
                case_type=case_type,
                subjects=all_subjects,
                sources=resolved_sources,
            )

            # Step 5: Create scored findings from OSINT results
            findings = self._create_findings_from_result(
                gather_result=gather_result,
                lead_id=lead_id,
                directive=directive,
                flat_indicators=flat_indicators,
            )
        except Exception as e:
            logger.error(
                "OSINT gather failed for directive on lead %s: %s", lead_id, e
            )

        return DirectiveResult(
            findings=findings,
            directive_text=directive,
            unsupported_sources=unsupported_sources,
        )

    def _parse_directive(self, directive: str, case_type: str) -> ParsedDirective:
        """Parse a natural language directive into structured search parameters via Bedrock.

        Builds a prompt asking Bedrock to extract persons, organizations,
        document_types, geographic_regions, and target_sources from the directive.

        Args:
            directive: Natural language search directive from investigator.
            case_type: Antitrust case type for context.

        Returns:
            ParsedDirective with extracted parameters, or empty ParsedDirective on failure.
        """
        prompt = self._build_parse_prompt(directive, case_type)

        try:
            response = self.bedrock_client.converse(
                modelId=self.MODEL_ID,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={"maxTokens": 1024, "temperature": 0.2, "topP": 0.9},
            )

            output = response.get("output", {})
            message = output.get("message", {})
            content_blocks = message.get("content", [])
            text = "".join(
                block["text"] for block in content_blocks if "text" in block
            )

            return self._parse_bedrock_response(text, directive)

        except Exception as e:
            logger.error(
                "Bedrock directive parsing failed for directive '%s': %s",
                directive[:100],
                e,
            )
            # Don't raise to caller — return empty parsed directive
            return ParsedDirective(raw_directive=directive)

    def _build_parse_prompt(self, directive: str, case_type: str) -> str:
        """Build the Bedrock prompt for directive parsing.

        Args:
            directive: The investigator's natural language directive.
            case_type: Antitrust case type for context.

        Returns:
            Formatted prompt string.
        """
        supported_sources_str = ", ".join(self.SUPPORTED_SOURCES)
        document_types_str = ", ".join(self.DOCUMENT_TYPE_MAP.keys())

        return f"""You are an investigative intelligence analyst parsing a search directive
from an investigator working on an antitrust {case_type} case.

INVESTIGATOR DIRECTIVE:
"{directive}"

Extract the following structured information from the directive:
- persons: Names of individuals mentioned
- organizations: Names of companies or organizations mentioned
- document_types: Types of documents referenced (e.g. {document_types_str})
- geographic_regions: Geographic areas mentioned
- target_sources: OSINT data sources to query

SUPPORTED SOURCES: {supported_sources_str}

Return ONLY a JSON object with this exact structure (no other text):
{{
  "persons": ["person name"],
  "organizations": ["org name"],
  "document_types": ["document type"],
  "geographic_regions": ["region"],
  "target_sources": ["source_id"]
}}

Rules:
- Only include items explicitly mentioned or clearly implied by the directive
- target_sources must be from the supported list above
- If a document type implies a source, include that source in target_sources
- Return empty arrays for categories with no matches
"""

    def _parse_bedrock_response(self, text: str, directive: str) -> ParsedDirective:
        """Parse Bedrock response text into a ParsedDirective.

        Handles malformed JSON gracefully — logs errors and returns empty directive.

        Args:
            text: Raw text response from Bedrock.
            directive: Original directive text for the raw_directive field.

        Returns:
            ParsedDirective with extracted parameters.
        """
        if not text or not text.strip():
            logger.warning("Empty response from Bedrock for directive parsing")
            return ParsedDirective(raw_directive=directive)

        # Find JSON object boundaries (may have surrounding text)
        json_text = text.strip()
        start_idx = json_text.find("{")
        end_idx = json_text.rfind("}")

        if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
            logger.warning(
                "No JSON object found in Bedrock response: %s", text[:200]
            )
            return ParsedDirective(raw_directive=directive)

        json_text = json_text[start_idx:end_idx + 1]

        try:
            parsed = json.loads(json_text)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON from Bedrock directive response: %s", e)
            return ParsedDirective(raw_directive=directive)

        if not isinstance(parsed, dict):
            logger.warning("Bedrock response is not a JSON object")
            return ParsedDirective(raw_directive=directive)

        return ParsedDirective(
            persons=self._safe_list(parsed.get("persons")),
            organizations=self._safe_list(parsed.get("organizations")),
            document_types=self._safe_list(parsed.get("document_types")),
            geographic_regions=self._safe_list(parsed.get("geographic_regions")),
            target_sources=self._safe_list(parsed.get("target_sources")),
            raw_directive=directive,
        )

    def _resolve_sources(self, parsed: ParsedDirective) -> list[str]:
        """Resolve target sources from parsed directive.

        Combines explicitly listed target_sources with sources implied by
        document_types via DOCUMENT_TYPE_MAP. Filters to supported sources only.

        Args:
            parsed: ParsedDirective with target_sources and document_types.

        Returns:
            Deduplicated list of supported source identifiers.
        """
        sources: set[str] = set()

        # Add explicitly listed target sources (if supported)
        for source in parsed.target_sources:
            if source in self.SUPPORTED_SOURCES:
                sources.add(source)

        # Map document types to sources
        for doc_type in parsed.document_types:
            mapped_source = self.DOCUMENT_TYPE_MAP.get(doc_type)
            if mapped_source:
                sources.add(mapped_source)

        return list(sources)

    def _identify_unsupported(self, parsed: ParsedDirective) -> list[str]:
        """Identify any unsupported sources referenced in the directive.

        Args:
            parsed: ParsedDirective with target_sources.

        Returns:
            List of unsupported source identifiers with suggested alternatives.
        """
        unsupported: list[str] = []

        for source in parsed.target_sources:
            if source not in self.SUPPORTED_SOURCES:
                unsupported.append(
                    f"{source} (not supported — available: {', '.join(self.SUPPORTED_SOURCES)})"
                )

        return unsupported

    def _create_findings_from_result(
        self,
        gather_result: Any,
        lead_id: str,
        directive: str,
        flat_indicators: list[FlatIndicator],
    ) -> list[Finding]:
        """Create scored Finding objects from an OSINT gather result.

        Processes results individually (not bulk). Preserves directive_text
        on every finding per Requirement 5.5.

        Args:
            gather_result: Result from OsintDataGatherer.gather().
            lead_id: UUID of the parent lead.
            directive: Original directive text to preserve on findings.
            flat_indicators: Flattened IoV indicators for scoring.

        Returns:
            List of Finding objects with signal_strength scored.
        """
        findings: list[Finding] = []

        # Extract individual records from gather result
        records = getattr(gather_result, "records", None)
        if records is None:
            # Fallback: treat entire result as a single finding
            records = [gather_result]

        for record in records:
            summary = self._build_finding_summary(record, gather_result)

            if not summary:
                continue

            # Score the finding against IoV indicators
            scoring_result = self.signal_scorer.score_finding(summary, flat_indicators)

            finding = Finding(
                finding_id=str(uuid.uuid4()),
                lead_id=lead_id,
                summary=summary,
                signal_strength=scoring_result.score,
                tier=scoring_result.tier,
                matched_indicators=[
                    {
                        "indicator_text": ind.indicator_text,
                        "category_path": ind.category_path,
                        "weight": ind.weight,
                    }
                    for ind in scoring_result.matched_indicators
                ],
                drill_down_depth=0,
                directive_text=directive,  # MUST preserve on every finding (Req 5.5)
                raw_data=self._extract_raw_data(record),
            )

            findings.append(finding)

        return findings

    def _build_finding_summary(self, record: Any, gather_result: Any) -> str:
        """Build a summary string from an individual OSINT record.

        Args:
            record: Individual record from OSINT results.
            gather_result: Full gather result for context.

        Returns:
            Summary string, or empty string if no useful data.
        """
        # Handle dict-style records
        if isinstance(record, dict):
            parts = []
            title = record.get("title") or record.get("name") or record.get("summary")
            if title:
                parts.append(str(title))
            source = record.get("source") or record.get("source_type")
            if source:
                parts.append(f"[{source}]")
            description = record.get("description") or record.get("details")
            if description:
                parts.append(str(description)[:200])
            return " ".join(parts) if parts else ""

        # Handle object-style records with attributes
        summary_parts = []
        for attr in ("summary", "title", "name", "description"):
            value = getattr(record, attr, None)
            if value:
                summary_parts.append(str(value))
                break

        source = getattr(record, "source", None) or getattr(record, "source_type", None)
        if source:
            summary_parts.append(f"[{source}]")

        # Fallback to gather_result context
        if not summary_parts:
            total_records = getattr(gather_result, "total_records", 0)
            sources_queried = getattr(gather_result, "sources_queried", [])
            if total_records > 0:
                summary_parts.append(
                    f"OSINT result from {', '.join(sources_queried)} "
                    f"({total_records} records)"
                )

        return " ".join(summary_parts)

    def _extract_raw_data(self, record: Any) -> dict:
        """Extract raw data dict from a record for storage.

        Args:
            record: Individual record from OSINT results.

        Returns:
            Dict representation of the record.
        """
        if isinstance(record, dict):
            return record

        if hasattr(record, "__dict__"):
            return {
                k: v for k, v in record.__dict__.items()
                if not k.startswith("_")
            }

        return {"raw": str(record)}

    @staticmethod
    def _safe_list(value: Any) -> list[str]:
        """Safely convert a value to a list of strings.

        Args:
            value: Value from parsed JSON (may be None, list, or other).

        Returns:
            List of non-empty strings.
        """
        if not value or not isinstance(value, list):
            return []
        return [str(item) for item in value if item and str(item).strip()]
