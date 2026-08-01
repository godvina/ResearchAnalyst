"""Drill-Down Engine — Recursive AI-driven follow-up OSINT queries for high-signal findings.

Uses Amazon Bedrock (Nova Pro) to generate targeted follow-up queries based on
high-signal findings, executes them via OsintDataGatherer, scores results,
and returns structured DrillDownResult with sub-findings.

Individual finding processing only — no bulk/batch operations.
Max recursion depth: 3 levels.
"""

import json
import logging
import uuid
from typing import Any

from models.signal_mining import (
    DrillDownResult,
    Finding,
    FlatIndicator,
    FollowUpQuery,
    IovHierarchy,
)
from services.iov_taxonomy_service import IovTaxonomyService
from services.signal_scorer import SignalScorer

logger = logging.getLogger(__name__)

# Valid OSINT target sources for follow-up queries
VALID_TARGET_SOURCES = [
    "sam_gov",
    "fpds_gov",
    "usaspending_gov",
    "sec_edgar",
    "pacer",
    "news_press",
    "state_corporate_registry",
]


class DrillDownEngine:
    """Recursive AI drill-down engine for investigative findings.

    Generates follow-up OSINT queries for high-signal findings via Bedrock,
    executes them, scores results, and returns sub-findings. Processes
    findings individually (not batch). Max depth: 3 levels.
    """

    MAX_DEPTH = 3
    MODEL_ID = "amazon.nova-pro-v1:0"

    def __init__(
        self,
        bedrock_client: Any,
        osint_gatherer: Any,
        signal_scorer: SignalScorer,
        iov_taxonomy_service: IovTaxonomyService,
    ) -> None:
        """Initialize with required service dependencies.

        Args:
            bedrock_client: boto3 Bedrock Runtime client for AI query generation.
            osint_gatherer: OsintDataGatherer instance for executing OSINT queries.
            signal_scorer: SignalScorer for scoring sub-findings against IoV indicators.
            iov_taxonomy_service: IovTaxonomyService for loading indicator hierarchies.
        """
        self.bedrock_client = bedrock_client
        self.osint_gatherer = osint_gatherer
        self.signal_scorer = signal_scorer
        self.iov_taxonomy_service = iov_taxonomy_service

    def execute_drill_down(
        self,
        finding: Finding,
        case_type: str,
        current_depth: int = 0,
    ) -> DrillDownResult:
        """Execute a drill-down cycle on a single finding.

        Generates follow-up queries via Bedrock, executes them against OSINT
        sources, scores results, and returns sub-findings.

        Args:
            finding: The parent Finding to drill into.
            case_type: Antitrust case type for IoV taxonomy lookup.
            current_depth: Current recursion depth (0-based). Must be < MAX_DEPTH.

        Returns:
            DrillDownResult with sub-findings, query counts, and status.
        """
        # Depth limit check
        if current_depth >= self.MAX_DEPTH:
            logger.info(
                "Depth limit reached for finding %s at depth %d",
                finding.finding_id,
                current_depth,
            )
            return DrillDownResult(
                parent_finding_id=finding.finding_id,
                depth_reached=current_depth,
                status="depth_limit_reached",
            )

        # Generate follow-up queries via Bedrock
        queries = self._generate_follow_up_queries(finding, case_type, current_depth)

        if not queries:
            return DrillDownResult(
                parent_finding_id=finding.finding_id,
                queries_generated=0,
                queries_executed=0,
                depth_reached=current_depth + 1,
                status="uncorroborated",
            )

        # Load IoV taxonomy for scoring
        try:
            hierarchy = self.iov_taxonomy_service.load_taxonomy(case_type)
            flat_indicators = self.iov_taxonomy_service.flatten_indicators(hierarchy)
        except Exception as e:
            logger.error("Failed to load IoV taxonomy for case_type=%s: %s", case_type, e)
            flat_indicators = []

        # Execute each query and collect sub-findings
        sub_findings: list[Finding] = []
        queries_executed = 0

        for query in queries:
            try:
                # Build subjects from finding context
                subjects = self._extract_subjects(finding)

                # Execute OSINT query
                gather_result = self.osint_gatherer.gather(
                    lead_id=finding.lead_id,
                    case_type=case_type,
                    subjects=subjects,
                    sources=[query.target_source],
                )
                queries_executed += 1

                # Create sub-finding from result
                sub_finding = self._create_sub_finding(
                    gather_result=gather_result,
                    parent_finding=finding,
                    query=query,
                    current_depth=current_depth,
                    flat_indicators=flat_indicators,
                )
                if sub_finding:
                    sub_findings.append(sub_finding)

            except Exception as e:
                logger.error(
                    "Failed to execute drill-down query target_source=%s for finding %s: %s",
                    query.target_source,
                    finding.finding_id,
                    e,
                )

        status = "completed" if sub_findings else "uncorroborated"

        return DrillDownResult(
            parent_finding_id=finding.finding_id,
            sub_findings=sub_findings,
            queries_generated=len(queries),
            queries_executed=queries_executed,
            depth_reached=current_depth + 1,
            status=status,
        )

    def _generate_follow_up_queries(
        self,
        finding: Finding,
        case_type: str,
        depth: int,
    ) -> list[FollowUpQuery]:
        """Generate follow-up OSINT queries using Bedrock AI.

        Builds a prompt with finding context and asks Bedrock to produce
        2-5 structured follow-up queries targeting specific OSINT sources.

        Args:
            finding: The parent finding to generate queries for.
            case_type: Antitrust case type for context.
            depth: Current drill-down depth (included in prompt for specificity).

        Returns:
            List of validated FollowUpQuery objects (2-5 items), or empty on failure.
        """
        prompt = self._build_query_generation_prompt(finding, case_type, depth)

        try:
            response = self.bedrock_client.converse(
                modelId=self.MODEL_ID,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={"maxTokens": 2048, "temperature": 0.3, "topP": 0.9},
            )

            output = response.get("output", {})
            message = output.get("message", {})
            content_blocks = message.get("content", [])
            text = "".join(
                block["text"] for block in content_blocks if "text" in block
            )

            return self._parse_queries_from_response(text)

        except Exception as e:
            logger.error(
                "Bedrock query generation failed for finding %s: %s",
                finding.finding_id,
                e,
            )
            return []

    def _build_query_generation_prompt(
        self,
        finding: Finding,
        case_type: str,
        depth: int,
    ) -> str:
        """Build the prompt for Bedrock to generate follow-up queries.

        Args:
            finding: Parent finding with summary and matched indicators.
            case_type: Antitrust case type.
            depth: Current depth level (deeper = more specific queries).

        Returns:
            Formatted prompt string.
        """
        # Extract subject names from finding context
        subjects = self._extract_subjects(finding)
        subjects_text = ", ".join(subjects) if subjects else "Unknown subjects"

        # Format matched indicators
        indicators_text = ""
        if finding.matched_indicators:
            indicator_lines = []
            for ind in finding.matched_indicators[:10]:  # Cap at 10 for prompt size
                if isinstance(ind, dict):
                    indicator_lines.append(f"  - {ind.get('indicator_text', str(ind))}")
                else:
                    indicator_lines.append(f"  - {ind}")
            indicators_text = "\n".join(indicator_lines)
        else:
            indicators_text = "  (none matched)"

        specificity_guidance = ""
        if depth == 0:
            specificity_guidance = "Generate broad exploratory queries across multiple source types."
        elif depth == 1:
            specificity_guidance = "Generate more targeted queries focusing on specific entities and transactions."
        else:
            specificity_guidance = "Generate highly specific queries targeting exact documents, filings, or records."

        valid_sources = ", ".join(VALID_TARGET_SOURCES)

        return f"""You are an investigative intelligence analyst conducting a recursive drill-down
on a finding from an antitrust investigation.

FINDING SUMMARY:
{finding.summary}

MATCHED INDICATORS OF VIOLATION:
{indicators_text}

CASE TYPE: {case_type}
SUBJECT NAMES: {subjects_text}
DRILL-DOWN DEPTH: {depth} (of max {self.MAX_DEPTH})

SPECIFICITY GUIDANCE: {specificity_guidance}

Generate 2-5 follow-up OSINT queries to corroborate or expand on this finding.
Each query should target a specific public data source and include precise search terms.

VALID TARGET SOURCES: {valid_sources}

Return ONLY a JSON array with this exact structure (no other text):
[
  {{"target_source": "sec_edgar", "search_terms": "company name 10-K filing 2023", "rationale": "Why this query helps"}},
  {{"target_source": "news_press", "search_terms": "specific search terms", "rationale": "Why this query helps"}}
]

Rules:
- Return 2-5 queries only
- Each query must have target_source, search_terms, and rationale
- target_source must be one of: {valid_sources}
- search_terms should be specific and actionable
- rationale should explain investigative value
"""

    def _parse_queries_from_response(self, text: str) -> list[FollowUpQuery]:
        """Parse Bedrock response text into validated FollowUpQuery objects.

        Handles malformed JSON gracefully — logs errors and returns empty list.

        Args:
            text: Raw text response from Bedrock.

        Returns:
            List of validated FollowUpQuery objects (0-5 items).
        """
        if not text or not text.strip():
            logger.warning("Empty response from Bedrock for query generation")
            return []

        # Try to extract JSON array from response (may have surrounding text)
        json_text = text.strip()

        # Find JSON array boundaries if wrapped in other text
        start_idx = json_text.find("[")
        end_idx = json_text.rfind("]")

        if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
            logger.warning("No JSON array found in Bedrock response: %s", text[:200])
            return []

        json_text = json_text[start_idx:end_idx + 1]

        try:
            parsed = json.loads(json_text)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON from Bedrock response: %s", e)
            return []

        if not isinstance(parsed, list):
            logger.warning("Bedrock response is not a JSON array")
            return []

        # Validate and convert each query (cap at 5)
        queries: list[FollowUpQuery] = []
        for item in parsed[:5]:
            if not isinstance(item, dict):
                continue

            if not self._validate_query(item):
                continue

            queries.append(FollowUpQuery(
                target_source=item["target_source"].strip(),
                search_terms=item["search_terms"].strip(),
                rationale=item["rationale"].strip(),
            ))

        if len(queries) < 2:
            logger.warning(
                "Only %d valid queries parsed from Bedrock (expected 2-5)",
                len(queries),
            )

        return queries

    def _validate_query(self, query_data: dict) -> bool:
        """Validate that a query dict has all required non-empty string fields.

        Args:
            query_data: Dict with expected keys target_source, search_terms, rationale.

        Returns:
            True if all fields are present and non-empty strings.
        """
        required_fields = ["target_source", "search_terms", "rationale"]

        for field_name in required_fields:
            value = query_data.get(field_name)
            if not value or not isinstance(value, str) or not value.strip():
                return False

        # Validate target_source is in allowed list
        if query_data["target_source"].strip() not in VALID_TARGET_SOURCES:
            logger.warning(
                "Invalid target_source '%s' — not in allowed list",
                query_data["target_source"],
            )
            return False

        return True

    def _extract_subjects(self, finding: Finding) -> list[str]:
        """Extract subject names from a finding's raw data or summary.

        Args:
            finding: Finding to extract subjects from.

        Returns:
            List of subject name strings.
        """
        subjects = []

        # Try raw_data first (may contain structured subject info)
        if finding.raw_data:
            raw_subjects = finding.raw_data.get("subjects", [])
            if isinstance(raw_subjects, list):
                subjects.extend(
                    s for s in raw_subjects if isinstance(s, str) and s.strip()
                )

            # Also check for entity names
            entities = finding.raw_data.get("entities", [])
            if isinstance(entities, list):
                for entity in entities:
                    if isinstance(entity, dict):
                        name = entity.get("name", "")
                        if name and name not in subjects:
                            subjects.append(name)

        # Fallback: use first few words of summary as search subject
        if not subjects and finding.summary:
            subjects = [finding.summary[:100]]

        return subjects

    def _create_sub_finding(
        self,
        gather_result: Any,
        parent_finding: Finding,
        query: FollowUpQuery,
        current_depth: int,
        flat_indicators: list[FlatIndicator],
    ) -> Finding | None:
        """Create a scored sub-Finding from an OSINT gather result.

        Args:
            gather_result: Result from OsintDataGatherer.gather().
            parent_finding: The parent finding being drilled into.
            query: The FollowUpQuery that produced this result.
            current_depth: Current drill-down depth.
            flat_indicators: Flattened IoV indicators for scoring.

        Returns:
            A new Finding with signal_strength scored, or None if no useful data.
        """
        # Build summary from gather result
        summary = self._build_sub_finding_summary(gather_result, query)

        if not summary:
            return None

        # Score the sub-finding against IoV indicators
        scoring_result = self.signal_scorer.score_finding(summary, flat_indicators)

        sub_finding = Finding(
            finding_id=str(uuid.uuid4()),
            lead_id=parent_finding.lead_id,
            parent_finding_id=parent_finding.finding_id,
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
            drill_down_depth=current_depth + 1,
            raw_data={
                "source": query.target_source,
                "search_terms": query.search_terms,
                "rationale": query.rationale,
                "sources_queried": getattr(gather_result, "sources_queried", []),
                "total_records": getattr(gather_result, "total_records", 0),
            },
        )

        return sub_finding

    def _build_sub_finding_summary(self, gather_result: Any, query: FollowUpQuery) -> str:
        """Build a summary string from an OSINT gather result.

        Args:
            gather_result: Result from OsintDataGatherer.
            query: The query that produced this result.

        Returns:
            Summary string, or empty string if no useful data.
        """
        total_records = getattr(gather_result, "total_records", 0)
        sources_queried = getattr(gather_result, "sources_queried", [])

        if total_records == 0:
            return ""

        # Build summary from available result data
        summary_parts = [
            f"Drill-down query to {query.target_source}",
            f"({query.search_terms})",
            f"returned {total_records} record(s)",
        ]

        # Include extracted data if available
        extracted = getattr(gather_result, "extracted_entities", None)
        if extracted and isinstance(extracted, list):
            entity_names = [
                e.get("name", "") for e in extracted[:5]
                if isinstance(e, dict) and e.get("name")
            ]
            if entity_names:
                summary_parts.append(f"involving: {', '.join(entity_names)}")

        return " ".join(summary_parts)
