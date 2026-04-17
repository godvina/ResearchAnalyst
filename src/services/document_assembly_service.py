"""Court Document Assembly Service — AI-powered legal document generation.

Generates court-ready documents (indictments, evidence summaries, witness lists,
exhibit lists, sentencing memoranda, case briefs, template filings) from case
evidence. Each section flows through the three-state Decision Workflow
(AI_Proposed → Human_Confirmed → Human_Overridden).

Dependencies injected via constructor for testability.
"""

import json
import logging
import ssl
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from models.document_assembly import (
    DiscoveryDocument,
    DiscoveryStatus,
    DocumentDraft,
    DocumentSection,
    DocumentStatus,
    DocumentType,
    DocumentVersion,
    ExhibitEntry,
    ExhibitType,
    GuidelineCalculation,
    PrivilegeCategory,
    PrivilegeLogEntry,
    ProductionSet,
    ProductionStatus,
    VersionDiff,
    WitnessEntry,
    WitnessRole,
)

logger = logging.getLogger(__name__)

BEDROCK_MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"


class DocumentAssemblyService:
    """Orchestrates AI-powered court document generation."""

    SENIOR_LEGAL_ANALYST_PERSONA = (
        "You are a senior federal prosecutor (AUSA) with 20+ years of experience. "
        "Reason using proper legal terminology. Cite case law patterns and reference "
        "federal sentencing guidelines (USSG) where applicable. Provide thorough legal "
        "justifications for every recommendation. Format all output for federal court "
        "filing standards."
    )

    DOCUMENT_TYPES = [t.value for t in DocumentType]

    PAGE_SIZE = 1000
    MAX_BEDROCK_TOKENS = 100_000
    ASYNC_THRESHOLD = 10_000

    def __init__(
        self,
        aurora_cm: Any,
        neptune_endpoint: str,
        neptune_port: str,
        bedrock_client: Any,
        decision_workflow_svc: Any,
        element_assessment_svc: Any = None,
        case_weakness_svc: Any = None,
        precedent_analysis_svc: Any = None,
    ) -> None:
        self._aurora = aurora_cm
        self._neptune_endpoint = neptune_endpoint
        self._neptune_port = neptune_port
        self._bedrock = bedrock_client
        self._decision_svc = decision_workflow_svc
        self._element_svc = element_assessment_svc
        self._weakness_svc = case_weakness_svc
        self._precedent_svc = precedent_analysis_svc

    # ------------------------------------------------------------------
    # Internal: Helpers
    # ------------------------------------------------------------------

    def _gremlin_query(self, query: str) -> list:
        url = f"https://{self._neptune_endpoint}:{self._neptune_port}/gremlin"
        data = json.dumps({"gremlin": query}).encode("utf-8")
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                result = body.get("result", {}).get("data", {})
                if isinstance(result, dict) and "@value" in result:
                    return result["@value"]
                return result if isinstance(result, list) else ([result] if result else [])
        except Exception as e:
            logger.error("Neptune query error: %s", str(e)[:200])
            return []

    @staticmethod
    def _escape(s: str) -> str:
        return s.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')

    def _invoke_bedrock_section(self, section_type: str, context_data: str) -> str:
        prompt = (
            f"Generate the '{section_type}' section of a federal court document.\n\n"
            f"Context:\n{context_data}\n\n"
            f"Format the output as professional legal prose suitable for federal court filing."
        )
        try:
            response = self._bedrock.invoke_model(
                modelId=BEDROCK_MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 2000,
                    "system": self.SENIOR_LEGAL_ANALYST_PERSONA,
                    "messages": [{"role": "user", "content": prompt}],
                }),
            )
            body = json.loads(response["body"].read())
            return body.get("content", [{}])[0].get("text", "")
        except Exception as e:
            logger.error("Bedrock section generation failed: %s", str(e)[:200])
            return f"[AI generation unavailable for {section_type}. Manual drafting required.]"

    def _gather_evidence_data(self, case_id: str, statute_id: str = None) -> dict:
        data = {"assessments": [], "weaknesses": [], "precedents": [], "evidence_count": 0}
        try:
            with self._aurora.cursor() as cur:
                # Count evidence items
                cur.execute("SELECT COUNT(*) FROM documents WHERE case_file_id = %s", (case_id,))
                row = cur.fetchone()
                data["evidence_count"] = row[0] if row else 0

                # Get element assessments if available
                cur.execute(
                    "SELECT element_id, statute_id, element_description, evidence_rating, confidence "
                    "FROM element_assessments WHERE case_id = %s LIMIT %s",
                    (case_id, self.PAGE_SIZE),
                )
                data["assessments"] = [
                    {"element_id": str(r[0]), "statute_id": str(r[1]), "description": r[2],
                     "rating": r[3], "confidence": r[4]}
                    for r in cur.fetchall()
                ]

                # Get case weaknesses
                cur.execute(
                    "SELECT weakness_id, weakness_type, description, severity, affected_elements "
                    "FROM case_weaknesses WHERE case_id = %s LIMIT %s",
                    (case_id, self.PAGE_SIZE),
                )
                data["weaknesses"] = [
                    {"weakness_id": str(r[0]), "type": r[1], "description": r[2],
                     "severity": r[3], "affected": r[4]}
                    for r in cur.fetchall()
                ]
        except Exception as e:
            logger.error("Evidence data gathering failed: %s", str(e)[:200])
        return data

    def _summarize_for_bedrock(self, data: dict) -> str:
        parts = []
        if data.get("assessments"):
            parts.append(f"Evidence Assessments ({len(data['assessments'])} elements):")
            for a in data["assessments"][:20]:
                parts.append(f"  - {a.get('description','')}: {a.get('rating','unknown')}")
        if data.get("weaknesses"):
            parts.append(f"\nCase Weaknesses ({len(data['weaknesses'])}):")
            for w in data["weaknesses"][:10]:
                parts.append(f"  - [{w.get('severity','')}] {w.get('description','')}")
        if data.get("precedents"):
            parts.append(f"\nPrecedent Cases ({len(data['precedents'])}):")
            for p in data["precedents"][:5]:
                parts.append(f"  - {p.get('case_name','')}: {p.get('ruling','')}")
        summary = "\n".join(parts)
        # Truncate to fit Bedrock context
        if len(summary) > self.MAX_BEDROCK_TOKENS * 3:
            summary = summary[:self.MAX_BEDROCK_TOKENS * 3] + "\n[... truncated for context window]"
        return summary

    # ------------------------------------------------------------------
    # Public: Document Generation (Task 3.2)
    # ------------------------------------------------------------------

    def generate_document(
        self, case_id: str, document_type: str,
        statute_id: str = None, defendant_id: str = None,
    ) -> DocumentDraft:
        if document_type not in self.DOCUMENT_TYPES:
            raise ValueError(f"Invalid document_type: {document_type}. Must be one of {self.DOCUMENT_TYPES}")

        draft_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Gather evidence data
        evidence_data = self._gather_evidence_data(case_id, statute_id)

        # Check async threshold
        if evidence_data.get("evidence_count", 0) > self.ASYNC_THRESHOLD:
            draft = DocumentDraft(
                draft_id=draft_id, case_id=case_id,
                document_type=DocumentType(document_type),
                title=f"{document_type.replace('_', ' ').title()} — Processing",
                status=DocumentStatus.PROCESSING,
                statute_id=statute_id, defendant_id=defendant_id,
                created_at=now,
            )
            self._store_draft(draft)
            return draft

        # Dispatch to type-specific generator
        generators = {
            "indictment": self._generate_indictment,
            "evidence_summary": self._generate_evidence_summary,
            "witness_list": self._generate_witness_list,
            "exhibit_list": self._generate_exhibit_list,
            "sentencing_memorandum": self._generate_sentencing_memo,
            "case_brief": self._generate_case_brief,
        }
        generator = generators.get(document_type, self._generate_template_filing)
        sections = generator(case_id, evidence_data, statute_id, defendant_id)

        # Create AI_Proposed decision for each section
        for section in sections:
            try:
                decision = self._decision_svc.create_decision(
                    case_id=case_id,
                    decision_type=f"document_section_{document_type}",
                    recommendation_text=f"Section: {section.section_type}",
                    legal_reasoning=section.content[:500] if section.content else "",
                    confidence="high",
                    source_service="document_assembly",
                )
                section.decision_id = decision.decision_id
                section.decision_state = decision.state.value
            except Exception as e:
                logger.error("Decision creation failed for section %s: %s", section.section_type, str(e)[:200])

        is_wp = document_type == "case_brief"
        draft = DocumentDraft(
            draft_id=draft_id, case_id=case_id,
            document_type=DocumentType(document_type),
            title=f"{document_type.replace('_', ' ').title()} — {case_id[:8]}",
            status=DocumentStatus.DRAFT,
            statute_id=statute_id, defendant_id=defendant_id,
            is_work_product=is_wp,
            sections=sections,
            created_at=now,
        )
        self._store_draft(draft)
        return draft

    # ------------------------------------------------------------------
    # Indictment Generator (Task 3.3)
    # ------------------------------------------------------------------

    def _generate_indictment(self, case_id, evidence_data, statute_id, defendant_id) -> list[DocumentSection]:
        sections = []
        draft_id = ""  # Will be set by caller
        context = self._summarize_for_bedrock(evidence_data)

        # 1. Caption
        caption_content = self._invoke_bedrock_section("caption", (
            f"Case ID: {case_id}\nDefendant: {defendant_id or 'Unknown'}\n"
            f"Generate a federal indictment caption with case number, district court, "
            f"defendant names, and statute citations.\n{context}"
        ))
        sections.append(DocumentSection(
            section_id=str(uuid.uuid4()), draft_id=draft_id,
            section_type="caption", section_order=1, content=caption_content,
        ))

        # 2. Counts (one per charge from evidence assessments)
        charges = evidence_data.get("assessments", [])
        for i, charge in enumerate(charges[:10], start=2):
            count_content = self._invoke_bedrock_section("count", (
                f"Count {i-1}: {charge.get('description', '')}\n"
                f"Evidence Rating: {charge.get('rating', 'unknown')}\n"
                f"Generate a formal count section for this charge.\n{context}"
            ))
            sections.append(DocumentSection(
                section_id=str(uuid.uuid4()), draft_id=draft_id,
                section_type=f"count_{i-1}", section_order=i, content=count_content,
            ))

        # 3. Factual Basis
        next_order = len(sections) + 1
        factual_content = self._invoke_bedrock_section("factual_basis", (
            f"Generate the factual basis section with evidence citations.\n{context}"
        ))
        sections.append(DocumentSection(
            section_id=str(uuid.uuid4()), draft_id=draft_id,
            section_type="factual_basis", section_order=next_order, content=factual_content,
        ))

        # 4. Overt Acts
        next_order += 1
        overt_content = self._invoke_bedrock_section("overt_acts", (
            f"Generate chronologically ordered overt acts from case events.\n{context}"
        ))
        sections.append(DocumentSection(
            section_id=str(uuid.uuid4()), draft_id=draft_id,
            section_type="overt_acts", section_order=next_order, content=overt_content,
        ))

        # 5. Forfeiture Allegations
        next_order += 1
        forfeiture_content = self._invoke_bedrock_section("forfeiture_allegations", (
            f"Generate forfeiture allegations from financial/asset entities.\n{context}"
        ))
        sections.append(DocumentSection(
            section_id=str(uuid.uuid4()), draft_id=draft_id,
            section_type="forfeiture_allegations", section_order=next_order, content=forfeiture_content,
        ))

        return sections

    # ------------------------------------------------------------------
    # Evidence Summary Generator (Task 5.1)
    # ------------------------------------------------------------------

    def _generate_evidence_summary(self, case_id, evidence_data, statute_id, defendant_id) -> list[DocumentSection]:
        sections = []
        context = self._summarize_for_bedrock(evidence_data)
        assessments = evidence_data.get("assessments", [])

        for i, assessment in enumerate(assessments[:20], start=1):
            content = self._invoke_bedrock_section("evidence_element", (
                f"Element: {assessment.get('description', '')}\n"
                f"Rating: {assessment.get('rating', 'unknown')}\n"
                f"Generate evidence summary for this statutory element.\n{context}"
            ))
            sections.append(DocumentSection(
                section_id=str(uuid.uuid4()), draft_id="",
                section_type=f"element_{i}", section_order=i, content=content,
            ))

        if not sections:
            sections.append(DocumentSection(
                section_id=str(uuid.uuid4()), draft_id="",
                section_type="overview", section_order=1,
                content=self._invoke_bedrock_section("evidence_overview", context),
            ))
        return sections

    # ------------------------------------------------------------------
    # Witness List Generator (Task 5.2)
    # ------------------------------------------------------------------

    def _generate_witness_list(self, case_id, evidence_data, statute_id, defendant_id) -> list[DocumentSection]:
        sections = []
        context = self._summarize_for_bedrock(evidence_data)

        content = self._invoke_bedrock_section("witness_list", (
            f"Generate a comprehensive witness list with roles, testimony summaries, "
            f"and credibility assessments.\n{context}"
        ))
        sections.append(DocumentSection(
            section_id=str(uuid.uuid4()), draft_id="",
            section_type="witness_roster", section_order=1, content=content,
        ))
        return sections

    # ------------------------------------------------------------------
    # Exhibit List Generator (Task 5.3)
    # ------------------------------------------------------------------

    def _generate_exhibit_list(self, case_id, evidence_data, statute_id, defendant_id) -> list[DocumentSection]:
        sections = []
        context = self._summarize_for_bedrock(evidence_data)

        content = self._invoke_bedrock_section("exhibit_list", (
            f"Generate a numbered exhibit index with descriptions, types, "
            f"and authentication notes.\n{context}"
        ))
        sections.append(DocumentSection(
            section_id=str(uuid.uuid4()), draft_id="",
            section_type="exhibit_index", section_order=1, content=content,
        ))
        return sections

    # ------------------------------------------------------------------
    # Sentencing Memorandum Generator (Task 7.2)
    # ------------------------------------------------------------------

    def _generate_sentencing_memo(self, case_id, evidence_data, statute_id, defendant_id) -> list[DocumentSection]:
        sections = []
        context = self._summarize_for_bedrock(evidence_data)
        memo_sections = [
            ("introduction", "Generate the introduction section of a sentencing memorandum."),
            ("offense_conduct", "Generate the offense conduct narrative with evidence citations."),
            ("criminal_history", "Generate the criminal history section."),
            ("ussg_calculations", "Generate USSG guideline calculations with base offense level and adjustments."),
            ("aggravating_factors", "Generate aggravating factors (leadership role, vulnerable victims, obstruction)."),
            ("mitigating_factors", "Generate mitigating factors (cooperation, acceptance of responsibility)."),
            ("victim_impact", "Generate victim impact summary."),
            ("recommendation", "Generate sentencing recommendation with guideline range and justification."),
        ]
        for i, (stype, prompt) in enumerate(memo_sections, start=1):
            content = self._invoke_bedrock_section(stype, f"{prompt}\n{context}")
            sections.append(DocumentSection(
                section_id=str(uuid.uuid4()), draft_id="",
                section_type=stype, section_order=i, content=content,
            ))
        return sections

    # ------------------------------------------------------------------
    # Case Brief Generator (Task 7.3)
    # ------------------------------------------------------------------

    def _generate_case_brief(self, case_id, evidence_data, statute_id, defendant_id) -> list[DocumentSection]:
        sections = []
        context = self._summarize_for_bedrock(evidence_data)
        brief_sections = [
            ("case_overview", "Generate case overview with key facts and legal theory."),
            ("investigation_summary", "Generate investigation summary with timeline and methods."),
            ("evidence_analysis", "Generate evidence analysis with strength assessment."),
            ("legal_theory", "Generate legal theory section with statutory basis."),
            ("anticipated_defenses", "Generate anticipated defenses from case weaknesses."),
            ("trial_strategy", "Generate trial strategy with risk assessment."),
        ]
        for i, (stype, prompt) in enumerate(brief_sections, start=1):
            content = self._invoke_bedrock_section(stype, f"{prompt}\n{context}")
            sections.append(DocumentSection(
                section_id=str(uuid.uuid4()), draft_id="",
                section_type=stype, section_order=i, content=content,
            ))
        return sections

    # ------------------------------------------------------------------
    # Template Filing Generator (Task 7.4)
    # ------------------------------------------------------------------

    def _generate_template_filing(self, case_id, evidence_data, statute_id, defendant_id) -> list[DocumentSection]:
        sections = []
        context = self._summarize_for_bedrock(evidence_data)
        content = self._invoke_bedrock_section("legal_filing", (
            f"Generate a legal filing document with proper formatting.\n{context}"
        ))
        sections.append(DocumentSection(
            section_id=str(uuid.uuid4()), draft_id="",
            section_type="filing_body", section_order=1, content=content,
        ))
        return sections

    # ------------------------------------------------------------------
    # USSG Calculator (Task 7.1)
    # ------------------------------------------------------------------

    def compute_sentencing_guidelines(
        self, statute_citation: str, offense_characteristics: dict,
        criminal_history_category: int,
    ) -> GuidelineCalculation:
        base_level = offense_characteristics.get("base_offense_level", 20)
        adjustments = offense_characteristics.get("adjustments", [])
        total = base_level
        for adj in adjustments:
            total += adj.get("level_change", 0)
        total = max(1, min(43, total))

        # USSG sentencing table (simplified)
        ranges = self._ussg_range(total, criminal_history_category)
        return GuidelineCalculation(
            statute_citation=statute_citation,
            base_offense_level=base_level,
            adjustments=adjustments,
            total_offense_level=total,
            criminal_history_category=criminal_history_category,
            guideline_range_months_low=ranges[0],
            guideline_range_months_high=ranges[1],
        )

    @staticmethod
    def _ussg_range(offense_level: int, history_cat: int) -> tuple[int, int]:
        """Simplified USSG sentencing table lookup."""
        base = max(0, (offense_level - 1) * 3)
        spread = max(6, offense_level)
        cat_mult = 1.0 + (history_cat - 1) * 0.15
        low = int(base * cat_mult)
        high = int((base + spread) * cat_mult)
        if offense_level >= 43:
            return (360, 360)  # Life
        return (low, max(low, high))

    # ------------------------------------------------------------------
    # Attorney Sign-Off (Task 6.1)
    # ------------------------------------------------------------------

    def sign_off_document(self, doc_id: str, attorney_id: str, attorney_name: str) -> DocumentDraft:
        draft = self.get_document(doc_id)
        if draft.status == DocumentStatus.FINAL:
            raise ValueError("Document already finalized")
        # Verify all sections reviewed
        for s in draft.sections:
            if s.decision_state == "ai_proposed":
                raise ValueError(f"Section '{s.section_type}' has not been reviewed")
        now = datetime.now(timezone.utc).isoformat()
        draft.status = DocumentStatus.FINAL
        draft.attorney_id = attorney_id
        draft.attorney_name = attorney_name
        draft.sign_off_at = now
        try:
            with self._aurora.cursor() as cur:
                cur.execute(
                    "UPDATE document_drafts SET status='final', attorney_id=%s, "
                    "attorney_name=%s, sign_off_at=%s, updated_at=NOW() WHERE draft_id=%s",
                    (attorney_id, attorney_name, now, doc_id),
                )
        except Exception as e:
            logger.error("Sign-off failed: %s", str(e)[:200])
        return draft

    # ------------------------------------------------------------------
    # Version Control (Task 6.2)
    # ------------------------------------------------------------------

    def create_version(self, doc_id: str, changed_sections: list[str], author_id: str) -> DocumentVersion:
        draft = self.get_document(doc_id)
        snapshot = {s.section_type: s.content for s in draft.sections}
        # Get next version number
        try:
            with self._aurora.cursor() as cur:
                cur.execute("SELECT COALESCE(MAX(version_number),0) FROM document_versions WHERE draft_id=%s", (doc_id,))
                next_ver = cur.fetchone()[0] + 1
        except Exception:
            next_ver = 1
        version = DocumentVersion(
            version_id=str(uuid.uuid4()), draft_id=doc_id,
            version_number=next_ver, content_snapshot=snapshot,
            changed_sections=changed_sections, author_id=author_id,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        try:
            with self._aurora.cursor() as cur:
                cur.execute(
                    "INSERT INTO document_versions (version_id,draft_id,version_number,content_snapshot,changed_sections,author_id,created_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (version.version_id, doc_id, next_ver, json.dumps(snapshot),
                     json.dumps(changed_sections), author_id, version.created_at),
                )
        except Exception as e:
            logger.error("Version creation failed: %s", str(e)[:200])
        return version

    def get_version_history(self, doc_id: str) -> list[DocumentVersion]:
        try:
            with self._aurora.cursor() as cur:
                cur.execute(
                    "SELECT version_id,draft_id,version_number,content_snapshot,changed_sections,author_id,created_at "
                    "FROM document_versions WHERE draft_id=%s ORDER BY version_number ASC", (doc_id,))
                return [DocumentVersion(
                    version_id=str(r[0]), draft_id=str(r[1]), version_number=r[2],
                    content_snapshot=r[3] if isinstance(r[3], dict) else json.loads(r[3] or "{}"),
                    changed_sections=r[4] if isinstance(r[4], list) else json.loads(r[4] or "[]"),
                    author_id=r[5], created_at=str(r[6]) if r[6] else "",
                ) for r in cur.fetchall()]
        except Exception:
            return []

    def get_version(self, doc_id: str, version_number: int) -> DocumentVersion:
        versions = self.get_version_history(doc_id)
        for v in versions:
            if v.version_number == version_number:
                return v
        raise KeyError(f"Version {version_number} not found")

    def compare_versions(self, doc_id: str, version_a: int, version_b: int) -> VersionDiff:
        va = self.get_version(doc_id, version_a)
        vb = self.get_version(doc_id, version_b)
        keys_a = set(va.content_snapshot.keys())
        keys_b = set(vb.content_snapshot.keys())
        modified = []
        for k in keys_a & keys_b:
            if va.content_snapshot[k] != vb.content_snapshot[k]:
                modified.append({"section": k, "old": va.content_snapshot[k][:100], "new": vb.content_snapshot[k][:100]})
        return VersionDiff(
            version_a=version_a, version_b=version_b,
            added_sections=list(keys_b - keys_a),
            removed_sections=list(keys_a - keys_b),
            modified_sections=modified,
        )

    # ------------------------------------------------------------------
    # Export (Task 9.1)
    # ------------------------------------------------------------------

    def export_document(self, doc_id: str, fmt: str) -> bytes:
        if fmt not in ("html", "pdf", "docx"):
            raise ValueError(f"Invalid format: {fmt}. Must be html, pdf, or docx")
        draft = self.get_document(doc_id)
        if fmt == "html":
            return self._render_html(draft)
        elif fmt == "pdf":
            return self._render_pdf(draft)
        return self._render_docx(draft)

    def _render_html(self, draft: DocumentDraft) -> bytes:
        parts = [f"<html><head><title>{draft.title}</title></head><body>"]
        parts.append(f"<h1>{draft.title}</h1>")
        parts.append(f"<p>Type: {draft.document_type.value} | Status: {draft.status.value}</p>")
        for s in draft.sections:
            badge = s.decision_state or "ai_proposed"
            parts.append(f'<div class="section"><h2>{s.section_type} <span class="badge">[{badge}]</span></h2>')
            parts.append(f"<div>{s.content}</div></div>")
        if draft.attorney_name:
            parts.append(f"<p>Signed off by: {draft.attorney_name} at {draft.sign_off_at}</p>")
        parts.append("</body></html>")
        return "\n".join(parts).encode("utf-8")

    def _render_pdf(self, draft: DocumentDraft) -> bytes:
        # Simplified PDF: return HTML with court filing format note
        html = self._render_html(draft).decode("utf-8")
        header = "<!-- Court Filing Format: Times New Roman 12pt, double-spaced, 1-inch margins -->\n"
        return (header + html).encode("utf-8")

    def _render_docx(self, draft: DocumentDraft) -> bytes:
        # Simplified DOCX: return plain text representation
        parts = [draft.title, "=" * len(draft.title), ""]
        for s in draft.sections:
            parts.append(f"## {s.section_type}")
            parts.append(s.content)
            parts.append("")
        return "\n".join(parts).encode("utf-8")

    # ------------------------------------------------------------------
    # Discovery Tracking (Task 10.1)
    # ------------------------------------------------------------------

    def categorize_document_privilege(self, case_id: str, document_id: str) -> DiscoveryDocument:
        prompt = f"Categorize this document for discovery privilege: case {case_id}, doc {document_id}"
        category = "pending"
        try:
            resp = self._invoke_bedrock_section("privilege_categorization", prompt)
            resp_lower = resp.lower()
            if "brady" in resp_lower:
                category = "brady_material"
            elif "jencks" in resp_lower:
                category = "jencks_material"
            elif "attorney-client" in resp_lower or "attorney client" in resp_lower:
                category = "attorney_client"
            elif "work product" in resp_lower:
                category = "work_product"
            else:
                category = "non_privileged"
        except Exception:
            pass

        doc = DiscoveryDocument(
            id=str(uuid.uuid4()), case_id=case_id, document_id=document_id,
            privilege_category=PrivilegeCategory(category),
        )
        # Brady auto-alert
        if category == "brady_material":
            doc.disclosure_alert = True
            doc.disclosure_alert_at = datetime.now(timezone.utc).isoformat()

        # Create AI_Proposed decision
        try:
            decision = self._decision_svc.create_decision(
                case_id=case_id, decision_type="privilege_categorization",
                recommendation_text=f"Document {document_id}: {category}",
                legal_reasoning=f"AI categorized as {category}",
                confidence="medium", source_service="document_assembly",
            )
            doc.decision_id = decision.decision_id
        except Exception:
            pass

        self._store_discovery_document(doc)
        return doc

    def get_discovery_status(self, case_id: str) -> DiscoveryStatus:
        try:
            with self._aurora.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM discovery_documents WHERE case_id=%s", (case_id,))
                total = cur.fetchone()[0]
                cur.execute(
                    "SELECT privilege_category, COUNT(*) FROM discovery_documents "
                    "WHERE case_id=%s GROUP BY privilege_category", (case_id,))
                by_priv = {r[0]: r[1] for r in cur.fetchall()}
                cur.execute(
                    "SELECT production_status, COUNT(*) FROM discovery_documents "
                    "WHERE case_id=%s GROUP BY production_status", (case_id,))
                by_prod = {r[0]: r[1] for r in cur.fetchall()}
                cur.execute(
                    "SELECT COUNT(*) FROM discovery_documents WHERE case_id=%s AND disclosure_alert=TRUE", (case_id,))
                brady = cur.fetchone()[0]
                cur.execute(
                    "SELECT COUNT(*) FROM discovery_documents WHERE case_id=%s AND waiver_flag=TRUE", (case_id,))
                waivers = cur.fetchone()[0]
                return DiscoveryStatus(
                    total_documents=total, by_privilege=by_priv,
                    by_production_status=by_prod, brady_alerts=brady, waiver_flags=waivers,
                )
        except Exception:
            return DiscoveryStatus()

    def create_production_set(self, case_id: str, recipient: str, document_ids: list[str]) -> ProductionSet:
        prod_id = str(uuid.uuid4())
        try:
            with self._aurora.cursor() as cur:
                cur.execute("SELECT COALESCE(MAX(production_number),0) FROM production_sets WHERE case_id=%s", (case_id,))
                next_num = cur.fetchone()[0] + 1
        except Exception:
            next_num = 1
        ps = ProductionSet(
            production_id=prod_id, case_id=case_id, production_number=next_num,
            recipient=recipient, document_ids=document_ids,
            document_count=len(document_ids),
            production_date=datetime.now(timezone.utc).isoformat(),
        )
        try:
            with self._aurora.cursor() as cur:
                cur.execute(
                    "INSERT INTO production_sets (production_id,case_id,production_number,recipient,document_ids,document_count) "
                    "VALUES (%s,%s,%s,%s,%s,%s)",
                    (prod_id, case_id, next_num, recipient, json.dumps(document_ids), len(document_ids)),
                )
                # Mark documents as produced
                for did in document_ids:
                    cur.execute(
                        "UPDATE discovery_documents SET production_status='produced', updated_at=NOW() "
                        "WHERE case_id=%s AND document_id=%s", (case_id, did))
        except Exception as e:
            logger.error("Production set creation failed: %s", str(e)[:200])
        return ps

    def generate_privilege_log(self, case_id: str) -> list[PrivilegeLogEntry]:
        try:
            with self._aurora.cursor() as cur:
                cur.execute(
                    "SELECT document_id, privilege_category, privilege_description, privilege_doctrine, created_at "
                    "FROM discovery_documents WHERE case_id=%s AND production_status='withheld'", (case_id,))
                return [PrivilegeLogEntry(
                    document_id=str(r[0]), privilege_category=r[1],
                    privilege_description=r[2] or "", privilege_doctrine=r[3] or "",
                    date_withheld=str(r[4]) if r[4] else "",
                ) for r in cur.fetchall()]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Query Methods (Task 15.2)
    # ------------------------------------------------------------------

    def get_document(self, doc_id: str) -> DocumentDraft:
        try:
            with self._aurora.cursor() as cur:
                cur.execute(
                    "SELECT draft_id,case_id,document_type,title,status,statute_id,defendant_id,"
                    "is_work_product,attorney_id,attorney_name,sign_off_at,created_at,updated_at "
                    "FROM document_drafts WHERE draft_id=%s", (doc_id,))
                r = cur.fetchone()
                if not r:
                    raise KeyError(f"Document {doc_id} not found")
                cur.execute(
                    "SELECT section_id,draft_id,section_type,section_order,content,decision_id "
                    "FROM document_sections WHERE draft_id=%s ORDER BY section_order", (doc_id,))
                sections = [DocumentSection(
                    section_id=str(s[0]), draft_id=str(s[1]), section_type=s[2],
                    section_order=s[3], content=s[4] or "", decision_id=str(s[5]) if s[5] else None,
                ) for s in cur.fetchall()]
                return DocumentDraft(
                    draft_id=str(r[0]), case_id=str(r[1]),
                    document_type=DocumentType(r[2]), title=r[3],
                    status=DocumentStatus(r[4]),
                    statute_id=str(r[5]) if r[5] else None,
                    defendant_id=r[6],
                    is_work_product=bool(r[7]),
                    sections=sections,
                    attorney_id=r[8], attorney_name=r[9],
                    sign_off_at=str(r[10]) if r[10] else None,
                    created_at=str(r[11]) if r[11] else "",
                    updated_at=str(r[12]) if r[12] else None,
                )
        except KeyError:
            raise
        except Exception as e:
            raise KeyError(f"Document {doc_id} not found: {e}")

    def list_documents(self, case_id: str, document_type: str = None, status: str = None) -> list[DocumentDraft]:
        try:
            with self._aurora.cursor() as cur:
                q = "SELECT draft_id FROM document_drafts WHERE case_id=%s"
                params: list = [case_id]
                if document_type:
                    q += " AND document_type=%s"
                    params.append(document_type)
                if status:
                    q += " AND status=%s"
                    params.append(status)
                q += " ORDER BY created_at DESC"
                cur.execute(q, tuple(params))
                return [self.get_document(str(r[0])) for r in cur.fetchall()]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    def _store_draft(self, draft: DocumentDraft) -> None:
        try:
            with self._aurora.cursor() as cur:
                cur.execute(
                    "INSERT INTO document_drafts (draft_id,case_id,document_type,title,status,"
                    "statute_id,defendant_id,is_work_product,created_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (draft_id) DO UPDATE SET status=EXCLUDED.status, updated_at=NOW()",
                    (draft.draft_id, draft.case_id, draft.document_type.value,
                     draft.title, draft.status.value, draft.statute_id,
                     draft.defendant_id, draft.is_work_product, draft.created_at),
                )
                for s in draft.sections:
                    cur.execute(
                        "INSERT INTO document_sections (section_id,draft_id,section_type,section_order,content,decision_id) "
                        "VALUES (%s,%s,%s,%s,%s,%s) "
                        "ON CONFLICT (draft_id,section_order) DO UPDATE SET content=EXCLUDED.content",
                        (s.section_id, draft.draft_id, s.section_type,
                         s.section_order, s.content, s.decision_id),
                    )
        except Exception as e:
            logger.error("Draft storage failed: %s", str(e)[:200])

    def _store_discovery_document(self, doc: DiscoveryDocument) -> None:
        try:
            with self._aurora.cursor() as cur:
                cur.execute(
                    "INSERT INTO discovery_documents (id,case_id,document_id,privilege_category,"
                    "production_status,disclosure_alert,disclosure_alert_at,decision_id) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (case_id,document_id) DO UPDATE SET "
                    "privilege_category=EXCLUDED.privilege_category, updated_at=NOW()",
                    (doc.id, doc.case_id, doc.document_id, doc.privilege_category.value,
                     doc.production_status.value, doc.disclosure_alert,
                     doc.disclosure_alert_at, doc.decision_id),
                )
        except Exception as e:
            logger.error("Discovery doc storage failed: %s", str(e)[:200])

    def update_section_content(self, doc_id: str, section_id: str, new_content: str, author_id: str) -> DocumentSection:
        try:
            with self._aurora.cursor() as cur:
                cur.execute(
                    "UPDATE document_sections SET content=%s, updated_at=NOW() WHERE section_id=%s AND draft_id=%s",
                    (new_content, section_id, doc_id))
                cur.execute(
                    "SELECT section_id,draft_id,section_type,section_order,content,decision_id "
                    "FROM document_sections WHERE section_id=%s", (section_id,))
                r = cur.fetchone()
                if not r:
                    raise KeyError(f"Section {section_id} not found")
            self.create_version(doc_id, [str(r[2])], author_id)
            return DocumentSection(
                section_id=str(r[0]), draft_id=str(r[1]), section_type=r[2],
                section_order=r[3], content=r[4] or "", decision_id=str(r[5]) if r[5] else None,
            )
        except KeyError:
            raise
        except Exception as e:
            raise KeyError(f"Section update failed: {e}")

    def get_section(self, doc_id: str, section_id: str) -> DocumentSection:
        try:
            with self._aurora.cursor() as cur:
                cur.execute(
                    "SELECT section_id,draft_id,section_type,section_order,content,decision_id "
                    "FROM document_sections WHERE section_id=%s AND draft_id=%s", (section_id, doc_id))
                r = cur.fetchone()
                if not r:
                    raise KeyError(f"Section {section_id} not found")
                return DocumentSection(
                    section_id=str(r[0]), draft_id=str(r[1]), section_type=r[2],
                    section_order=r[3], content=r[4] or "", decision_id=str(r[5]) if r[5] else None,
                )
        except KeyError:
            raise
        except Exception as e:
            raise KeyError(f"Section not found: {e}")
