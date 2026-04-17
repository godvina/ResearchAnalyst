"""Automated investigative report generation service (Req 26).

Generates formal reports from case data using Bedrock:
- Case Summary Brief
- Prosecution Memo
- Entity Profile Dossier
- Evidence Inventory
- Subpoena Recommendation List
"""
import json
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

REPORT_TYPES = {
    "case_summary": {
        "title": "Case Summary Brief",
        "prompt_template": """You are a senior investigative analyst preparing a formal case summary brief.

Based on the following case data, generate a comprehensive case summary suitable for presenting to a supervising attorney or case review meeting.

CASE: {case_name}
DOCUMENTS: {doc_count} documents analyzed
ENTITIES: {entity_count} entities extracted
KEY SUBJECTS: {key_subjects}
ENTITY TYPES: {entity_types}
DOCUMENT EXCERPTS: {doc_excerpts}

Generate the following sections:
1. CASE OVERVIEW - Brief description of the case and its scope
2. KEY SUBJECTS - Top persons of interest with connection counts and significance
3. EVIDENCE SUMMARY - Summary of evidence by type (documents, financial records, communications, etc.)
4. TIMELINE OF KEY EVENTS - Chronological sequence of significant events
5. CASE STRENGTH ASSESSMENT - Overall assessment of evidence strength (strong/moderate/weak) with reasoning
6. RECOMMENDED NEXT STEPS - Specific actionable recommendations for the investigation

For every factual claim, cite the specific document or entity that supports it using [Doc: filename] or [Entity: name] format.""",
    },
    "prosecution_memo": {
        "title": "Prosecution Memorandum",
        "prompt_template": """You are a federal prosecutor preparing a prosecution memorandum.

Based on the following case evidence, generate a formal prosecution memo suitable for filing with the court or presenting to a grand jury.

CASE: {case_name}
KEY SUBJECTS: {key_subjects}
ENTITIES: {entity_types}
DOCUMENT EXCERPTS: {doc_excerpts}
CONNECTIONS: {connections}

Generate the following sections:
1. STATEMENT OF FACTS - Chronological narrative of events based on evidence
2. ELEMENTS OF THE OFFENSE - Map each element to specific evidence that proves it
3. WITNESS AND DOCUMENT LIST - Key witnesses and documents with relevance
4. ANTICIPATED DEFENSES - Likely defense arguments with counter-evidence
5. SENTENCING CONSIDERATIONS - Aggravating and mitigating factors

Cite every factual claim using [Doc: filename] or [Entity: name] format.""",
    },
    "entity_dossier": {
        "title": "Entity Profile Dossier",
        "prompt_template": """You are an intelligence analyst preparing a comprehensive entity dossier.

Generate a detailed profile for the entity "{entity_name}" based on the following data:

ENTITY: {entity_name} (Type: {entity_type})
CONNECTIONS: {connections}
DOCUMENTS: {doc_excerpts}

Generate:
1. ENTITY OVERVIEW - Who/what is this entity and their role in the case
2. CONNECTION ANALYSIS - All known connections with significance assessment
3. DOCUMENT REFERENCES - Every document mentioning this entity with context
4. TIMELINE OF APPEARANCES - When this entity appears in the evidence
5. RISK ASSESSMENT - Assessment of this entity's significance to the investigation
6. RECOMMENDED ACTIONS - Specific investigative steps for this entity

Cite sources using [Doc: filename] or [Entity: name] format.""",
    },
    "evidence_inventory": {
        "title": "Evidence Inventory",
        "prompt_template": """Generate a structured evidence inventory for case "{case_name}".

DOCUMENTS: {doc_list}
ENTITIES: {entity_count} entities across {entity_type_count} types
ENTITY TYPES: {entity_types}

Generate:
1. DOCUMENT INVENTORY - List all documents with type, date, and key content
2. ENTITY INVENTORY - All entities grouped by type with connection counts
3. EVIDENCE GAPS - What evidence types are missing or underrepresented
4. CHAIN OF CUSTODY NOTES - Any issues with evidence provenance""",
    },
    "subpoena_list": {
        "title": "Subpoena Recommendation List",
        "prompt_template": """Based on the case evidence, generate a prioritized subpoena recommendation list.

CASE: {case_name}
KEY SUBJECTS: {key_subjects}
EVIDENCE GAPS: Entities with connections but limited document support
ENTITIES: {entity_types}
CONNECTIONS: {connections}

Generate:
1. HIGH PRIORITY SUBPOENAS - Records that would significantly strengthen the case
2. MEDIUM PRIORITY - Records that would fill evidence gaps
3. LOW PRIORITY - Records for completeness
For each, specify: target entity, record type requested, and justification.""",
    },
}


class ReportGenerationService:
    """Generates investigative reports using Bedrock."""

    def __init__(self, aurora_cm=None, bedrock_client=None, search_client=None, graph_client=None):
        self._db = aurora_cm
        self._bedrock = bedrock_client
        self._search = search_client
        self._graph = graph_client

    async def generate_report(self, case_id: str, report_type: str,
                               entity_name: Optional[str] = None,
                               created_by: str = "system") -> dict:
        """Generate a report for a case."""
        if report_type not in REPORT_TYPES:
            raise ValueError(f"Unknown report type: {report_type}. Valid: {list(REPORT_TYPES.keys())}")

        template = REPORT_TYPES[report_type]
        case_data = self._gather_case_data(case_id, entity_name)
        prompt = template["prompt_template"].format(**case_data)
        content = self._invoke_bedrock(prompt)

        report = {
            "report_id": str(datetime.utcnow().timestamp()),
            "case_id": case_id,
            "report_type": report_type,
            "title": template["title"],
            "content": content,
            "created_at": datetime.utcnow().isoformat(),
            "created_by": created_by,
        }

        self._store_report(report)
        return report

    def _gather_case_data(self, case_id: str, entity_name: Optional[str] = None) -> dict:
        """Gather case data for report generation."""
        data = {"case_name": "Case " + case_id[:8], "doc_count": 0, "entity_count": 0,
                "key_subjects": "N/A", "entity_types": "N/A", "doc_excerpts": "N/A",
                "connections": "N/A", "doc_list": "N/A", "entity_type_count": 0,
                "entity_name": entity_name or "", "entity_type": "unknown"}
        try:
            if self._db:
                # Query case info
                with self._db.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT topic_name, document_count, entity_count FROM case_files WHERE case_id = %s", (case_id,))
                        row = cur.fetchone()
                        if row:
                            data["case_name"] = row[0] or data["case_name"]
                            data["doc_count"] = row[1] or 0
                            data["entity_count"] = row[2] or 0
        except Exception as e:
            logger.warning("Failed to gather case data: %s", e)
        return data

    def _invoke_bedrock(self, prompt: str) -> str:
        """Call Bedrock to generate report content."""
        if not self._bedrock:
            return "[Report generation requires Bedrock access. Deploy with bedrock-runtime permissions.]"
        try:
            body = json.dumps({"anthropic_version": "bedrock-2023-05-31", "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}]})
            resp = self._bedrock.invoke_model(modelId="anthropic.claude-3-sonnet-20240229-v1:0", body=body)
            result = json.loads(resp["body"].read())
            return result.get("content", [{}])[0].get("text", "")
        except Exception as e:
            logger.error("Bedrock invocation failed: %s", e)
            return f"[Report generation failed: {e}]"

    def _store_report(self, report: dict) -> None:
        """Store generated report in Aurora."""
        if not self._db:
            return
        try:
            with self._db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO case_reports (case_id, report_type, title, content_html, created_by) VALUES (%s,%s,%s,%s,%s)",
                        (report["case_id"], report["report_type"], report["title"], report["content"], report["created_by"]))
                conn.commit()
        except Exception as e:
            logger.warning("Failed to store report: %s", e)
