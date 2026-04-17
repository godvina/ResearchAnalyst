"""Case Weakness Service — automated case weakness detection engine.

Analyzes case evidence for credibility issues, missing corroboration,
suppression risks, and Brady material.  Each weakness flag includes
legal reasoning citing relevant case law (e.g., Brady v. Maryland,
Mapp v. Ohio, Crawford v. Washington).

Bedrock-dependent checks (suppression_risk, brady_material) are skipped
when Bedrock is unavailable, returning only deterministic weaknesses.
"""

import json
import logging
import uuid

from models.prosecutor import (
    CaseWeakness,
    WeaknessSeverity,
    WeaknessType,
)

logger = logging.getLogger(__name__)

_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"


class CaseWeaknessService:
    """Automated case weakness detection with legal reasoning citations."""

    SENIOR_LEGAL_ANALYST_PERSONA = (
        "You are a senior federal prosecutor (AUSA) with 20+ years of experience. "
        "Reason using proper legal terminology. Cite case law patterns and reference "
        "federal sentencing guidelines (USSG) where applicable. Provide thorough legal "
        "justifications for every recommendation."
    )

    def __init__(self, aurora_cm, neptune_cm, bedrock_client):
        self._db = aurora_cm
        self._neptune = neptune_cm
        self._bedrock = bedrock_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_weaknesses(
        self, case_id: str, statute_id: str = None
    ) -> list[CaseWeakness]:
        """Run full weakness analysis for a case.

        Orchestrates all four detection methods.  When Bedrock is
        unavailable, only deterministic checks (conflicting_statements,
        missing_corroboration) are executed.
        """
        weaknesses: list[CaseWeakness] = []

        weaknesses.extend(self.detect_conflicting_statements(case_id))

        if statute_id:
            weaknesses.extend(
                self.detect_missing_corroboration(case_id, statute_id)
            )

        # Bedrock-dependent checks — skip when unavailable
        if self._bedrock:
            weaknesses.extend(self.detect_suppression_risks(case_id))
            weaknesses.extend(self.detect_brady_material(case_id))

        return weaknesses

    def detect_conflicting_statements(
        self, case_id: str
    ) -> list[CaseWeakness]:
        """Find conflicting statements across documents for the same witness.

        Queries Aurora documents and Neptune entity relationships to
        identify same-witness contradictions.  Cites Crawford v. Washington
        for confrontation clause implications.
        """
        weaknesses: list[CaseWeakness] = []

        # Fetch documents attributed to witnesses from Aurora
        witness_docs = self._fetch_witness_documents(case_id)

        # Fetch witness entity relationships from Neptune
        neptune_witness_docs = self._fetch_neptune_witness_relationships(case_id)

        # Merge both sources
        for witness_id, docs in neptune_witness_docs.items():
            existing = witness_docs.get(witness_id, [])
            for d in docs:
                if d not in existing:
                    existing.append(d)
            witness_docs[witness_id] = existing

        # Detect contradictions: witnesses with 2+ documents
        for witness_id, docs in witness_docs.items():
            if len(docs) < 2:
                continue

            contradictions = self._find_contradictions(docs)
            if not contradictions:
                continue

            doc_ids = [d["document_id"] for d in docs]
            severity = WeaknessSeverity.WARNING
            remediation = None

            # If contradictions are significant, escalate to critical
            if len(contradictions) >= 2:
                severity = WeaknessSeverity.CRITICAL
                remediation = (
                    f"Re-interview witness {witness_id} to resolve "
                    f"contradictory statements across {len(docs)} documents. "
                    f"Consider impeachment preparation under FRE 613."
                )

            weakness = CaseWeakness(
                weakness_id=str(uuid.uuid4()),
                case_id=case_id,
                weakness_type=WeaknessType.CONFLICTING_STATEMENTS,
                severity=severity,
                description=(
                    f"Witness {witness_id} has conflicting statements "
                    f"across {len(docs)} documents: {'; '.join(contradictions)}"
                ),
                legal_reasoning=(
                    "Under Crawford v. Washington, 541 U.S. 36 (2004), "
                    "testimonial statements by witnesses are subject to the "
                    "Confrontation Clause. Conflicting statements from the same "
                    "witness undermine credibility and may be exploited on "
                    "cross-examination, weakening the prosecution's case."
                ),
                affected_elements=[],
                affected_evidence=doc_ids,
                remediation=remediation,
            )
            weaknesses.append(weakness)

        return weaknesses

    def detect_missing_corroboration(
        self, case_id: str, statute_id: str
    ) -> list[CaseWeakness]:
        """Find elements supported by only one evidence source.

        Queries element_assessments for elements with only one green/yellow
        evidence source.
        """
        weaknesses: list[CaseWeakness] = []

        element_evidence = self._fetch_element_assessments(case_id, statute_id)

        for element_id, info in element_evidence.items():
            sources = info["sources"]
            display_name = info["display_name"]

            if len(sources) == 1:
                severity = WeaknessSeverity.WARNING
                remediation = None

                # Single-source critical elements get escalated
                if info.get("is_critical", False):
                    severity = WeaknessSeverity.CRITICAL
                    remediation = (
                        f"Obtain additional corroborating evidence for element "
                        f"'{display_name}'. Currently supported by only one source: "
                        f"{sources[0]}. Consider documentary evidence, additional "
                        f"witness testimony, or forensic analysis."
                    )

                weakness = CaseWeakness(
                    weakness_id=str(uuid.uuid4()),
                    case_id=case_id,
                    weakness_type=WeaknessType.MISSING_CORROBORATION,
                    severity=severity,
                    description=(
                        f"Element '{display_name}' is supported by only one "
                        f"evidence source ({sources[0]}). Single-source elements "
                        f"are vulnerable to challenge."
                    ),
                    legal_reasoning=(
                        "Corroboration strengthens the evidentiary foundation "
                        "for each statutory element. A single-source element is "
                        "vulnerable to exclusion or impeachment, potentially "
                        "creating reasonable doubt on an essential element of "
                        "the offense."
                    ),
                    affected_elements=[element_id],
                    affected_evidence=sources,
                    remediation=remediation,
                )
                weaknesses.append(weakness)

        return weaknesses

    def detect_suppression_risks(
        self, case_id: str
    ) -> list[CaseWeakness]:
        """Use Bedrock to flag potential Fourth Amendment issues.

        Cites Mapp v. Ohio and relevant exclusionary rule precedent.
        Returns empty list when Bedrock is unavailable.
        """
        if not self._bedrock:
            return []

        documents = self._fetch_case_documents(case_id)
        if not documents:
            return []

        doc_summaries = "\n".join(
            f"- {d['document_id']}: {d['title']} ({d.get('type', 'document')})"
            for d in documents[:20]
        )

        prompt = (
            "Analyze the following case documents for potential Fourth Amendment "
            "suppression risks. Identify any evidence that may have been obtained "
            "through warrantless searches, improper seizures, or other constitutional "
            "violations that could lead to exclusion under the exclusionary rule.\n\n"
            f"Documents:\n{doc_summaries}\n\n"
            "For each risk found, provide:\n"
            "- document_id: the affected document\n"
            "- description: what the suppression risk is\n"
            "- severity: critical, warning, or info\n"
            "- affected_elements: list of element IDs affected (can be empty)\n\n"
            "Return a JSON array. If no risks found, return [].\n"
            "Return ONLY the JSON array."
        )

        try:
            results = self._invoke_bedrock_list(prompt)
            weaknesses: list[CaseWeakness] = []

            for item in results:
                severity_val = item.get("severity", "warning")
                if severity_val not in ("critical", "warning", "info"):
                    severity_val = "warning"
                severity = WeaknessSeverity(severity_val)

                doc_id = item.get("document_id", "unknown")
                affected_elements = item.get("affected_elements", [])
                if not isinstance(affected_elements, list):
                    affected_elements = []

                remediation = None
                if severity == WeaknessSeverity.CRITICAL:
                    remediation = (
                        f"Review the collection method for document '{doc_id}'. "
                        "Verify warrant validity and chain of custody. Consider "
                        "filing a motion in limine to address suppression risk "
                        "before trial."
                    )

                weakness = CaseWeakness(
                    weakness_id=str(uuid.uuid4()),
                    case_id=case_id,
                    weakness_type=WeaknessType.SUPPRESSION_RISK,
                    severity=severity,
                    description=item.get(
                        "description",
                        f"Potential suppression risk identified in document {doc_id}",
                    ),
                    legal_reasoning=(
                        "Under Mapp v. Ohio, 367 U.S. 643 (1961), evidence "
                        "obtained in violation of the Fourth Amendment is "
                        "inadmissible in state and federal court under the "
                        "exclusionary rule. The prosecution must establish that "
                        "all evidence was lawfully obtained to prevent suppression "
                        "motions from the defense."
                    ),
                    affected_elements=affected_elements,
                    affected_evidence=[doc_id],
                    remediation=remediation,
                )
                weaknesses.append(weakness)

            return weaknesses
        except Exception as e:
            logger.warning("Bedrock suppression risk analysis failed: %s", e)
            return []

    def detect_brady_material(
        self, case_id: str
    ) -> list[CaseWeakness]:
        """Use Bedrock to identify exculpatory evidence.

        Cites Brady v. Maryland and Giglio v. United States.
        Returns empty list when Bedrock is unavailable.
        """
        if not self._bedrock:
            return []

        documents = self._fetch_case_documents(case_id)
        if not documents:
            return []

        doc_summaries = "\n".join(
            f"- {d['document_id']}: {d['title']} ({d.get('type', 'document')})"
            for d in documents[:20]
        )

        prompt = (
            "Analyze the following case documents for potential Brady material — "
            "exculpatory or impeaching evidence that the prosecution is "
            "constitutionally required to disclose to the defense.\n\n"
            f"Documents:\n{doc_summaries}\n\n"
            "For each piece of potential Brady material found, provide:\n"
            "- document_id: the affected document\n"
            "- description: what the exculpatory/impeaching content is\n"
            "- severity: critical, warning, or info\n"
            "- affected_elements: list of element IDs affected (can be empty)\n\n"
            "Return a JSON array. If no Brady material found, return [].\n"
            "Return ONLY the JSON array."
        )

        try:
            results = self._invoke_bedrock_list(prompt)
            weaknesses: list[CaseWeakness] = []

            for item in results:
                severity_val = item.get("severity", "critical")
                if severity_val not in ("critical", "warning", "info"):
                    severity_val = "critical"
                severity = WeaknessSeverity(severity_val)

                doc_id = item.get("document_id", "unknown")
                affected_elements = item.get("affected_elements", [])
                if not isinstance(affected_elements, list):
                    affected_elements = []

                remediation = None
                if severity == WeaknessSeverity.CRITICAL:
                    remediation = (
                        f"Immediately disclose document '{doc_id}' to the defense "
                        "as required under Brady v. Maryland. Failure to disclose "
                        "exculpatory evidence may result in reversal of conviction "
                        "and potential sanctions. Document the disclosure in the "
                        "case file."
                    )

                weakness = CaseWeakness(
                    weakness_id=str(uuid.uuid4()),
                    case_id=case_id,
                    weakness_type=WeaknessType.BRADY_MATERIAL,
                    severity=severity,
                    description=item.get(
                        "description",
                        f"Potential Brady material identified in document {doc_id}",
                    ),
                    legal_reasoning=(
                        "Under Brady v. Maryland, 373 U.S. 83 (1963), the "
                        "prosecution must disclose all material exculpatory "
                        "evidence to the defense. This obligation extends to "
                        "impeachment evidence under Giglio v. United States, "
                        "405 U.S. 150 (1972). Failure to comply constitutes a "
                        "due process violation and may result in reversal of "
                        "any conviction obtained."
                    ),
                    affected_elements=affected_elements,
                    affected_evidence=[doc_id],
                    remediation=remediation,
                )
                weaknesses.append(weakness)

            return weaknesses
        except Exception as e:
            logger.warning("Bedrock Brady material analysis failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # Bedrock invocation
    # ------------------------------------------------------------------

    def _invoke_bedrock_list(self, prompt: str) -> list[dict]:
        """Invoke Bedrock and parse a JSON array response."""
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "system": self.SENIOR_LEGAL_ANALYST_PERSONA,
            "messages": [{"role": "user", "content": prompt}],
        })
        resp = self._bedrock.invoke_model(modelId=_MODEL_ID, body=body)
        text = (
            json.loads(resp["body"].read())
            .get("content", [{}])[0]
            .get("text", "[]")
        )
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        return []

    # ------------------------------------------------------------------
    # Data access helpers
    # ------------------------------------------------------------------

    def _fetch_witness_documents(self, case_id: str) -> dict[str, list[dict]]:
        """Fetch documents grouped by witness from Aurora.

        Returns {witness_id: [{document_id, title, content_snippet}]}.
        """
        if not self._db:
            return {}
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT cd.document_id, cd.filename, cd.doc_type, cd.content_snippet, "
                    "cd.attributed_entity_id "
                    "FROM case_documents cd "
                    "WHERE cd.case_id = %s AND cd.attributed_entity_id IS NOT NULL",
                    (case_id,),
                )
                rows = cur.fetchall()
                witness_docs: dict[str, list[dict]] = {}
                for r in rows:
                    witness_id = str(r[4])
                    doc = {
                        "document_id": str(r[0]),
                        "title": r[1],
                        "type": r[2] or "document",
                        "content_snippet": r[3] or "",
                    }
                    witness_docs.setdefault(witness_id, []).append(doc)
                return witness_docs
        except Exception as e:
            logger.warning("Failed to fetch witness documents: %s", e)
            return {}

    def _fetch_neptune_witness_relationships(
        self, case_id: str
    ) -> dict[str, list[dict]]:
        """Fetch witness-document relationships from Neptune graph.

        Returns {witness_id: [{document_id, title}]}.
        """
        if not self._neptune:
            return {}
        try:
            with self._neptune.cursor() as cur:
                cur.execute(
                    "g.V().has('case_id', case_id).hasLabel('person')"
                    ".as('witness')"
                    ".outE('mentioned_in', 'authored', 'statement_in')"
                    ".inV().hasLabel('document')"
                    ".as('doc')"
                    ".select('witness', 'doc').by(valueMap(true))",
                    {"case_id": case_id},
                )
                rows = cur.fetchall()
                witness_docs: dict[str, list[dict]] = {}
                for r in rows:
                    witness = r.get("witness", {})
                    doc = r.get("doc", {})
                    witness_id = str(
                        witness.get("id", witness.get("entity_id", "unknown"))
                    )
                    doc_info = {
                        "document_id": str(
                            doc.get("id", doc.get("document_id", "unknown"))
                        ),
                        "title": (
                            doc.get("name", ["unknown"])[0]
                            if isinstance(doc.get("name"), list)
                            else doc.get("name", "unknown")
                        ),
                    }
                    witness_docs.setdefault(witness_id, []).append(doc_info)
                return witness_docs
        except Exception as e:
            logger.warning("Failed to fetch Neptune witness relationships: %s", e)
            return {}

    def _fetch_element_assessments(
        self, case_id: str, statute_id: str
    ) -> dict[str, dict]:
        """Fetch element assessments grouped by element.

        Returns {element_id: {display_name, sources: [evidence_id], is_critical}}.
        Only includes green/yellow rated sources.
        """
        if not self._db:
            return {}
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT ea.element_id, se.display_name, ea.evidence_id, "
                    "ea.rating, se.element_order "
                    "FROM element_assessments ea "
                    "JOIN statutory_elements se ON ea.element_id = se.element_id "
                    "WHERE ea.case_id = %s AND se.statute_id = %s "
                    "AND ea.rating IN ('green', 'yellow') "
                    "ORDER BY se.element_order",
                    (case_id, statute_id),
                )
                rows = cur.fetchall()
                elements: dict[str, dict] = {}
                for r in rows:
                    eid = str(r[0])
                    if eid not in elements:
                        elements[eid] = {
                            "display_name": r[1],
                            "sources": [],
                            "is_critical": r[4] <= 2,  # first 2 elements are critical
                        }
                    evidence_id = str(r[2])
                    if evidence_id not in elements[eid]["sources"]:
                        elements[eid]["sources"].append(evidence_id)
                return elements
        except Exception as e:
            logger.warning("Failed to fetch element assessments: %s", e)
            return {}

    def _fetch_case_documents(self, case_id: str) -> list[dict]:
        """Fetch all case documents from Aurora."""
        if not self._db:
            return []
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT document_id, filename, doc_type "
                    "FROM case_documents WHERE case_id = %s",
                    (case_id,),
                )
                return [
                    {
                        "document_id": str(r[0]),
                        "title": r[1],
                        "type": r[2] or "document",
                    }
                    for r in cur.fetchall()
                ]
        except Exception as e:
            logger.warning("Failed to fetch case documents: %s", e)
            return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_contradictions(docs: list[dict]) -> list[str]:
        """Identify contradictions between documents.

        Uses simple heuristic: if two documents from the same witness
        exist, they are flagged as potentially contradictory.
        In production, Bedrock would perform deeper semantic analysis.
        """
        contradictions: list[str] = []
        for i, d1 in enumerate(docs):
            for d2 in docs[i + 1:]:
                contradictions.append(
                    f"{d1.get('title', d1['document_id'])} vs "
                    f"{d2.get('title', d2['document_id'])}"
                )
        return contradictions

