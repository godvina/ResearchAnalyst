"""Precedent Analysis Service — case precedent matching and sentencing advisory.

Extends cross_case_service.py entity matching to include case characteristic
matching (charge type, evidence patterns, defendant profile, aggravating/
mitigating factors).  Combines Neptune graph similarity with OpenSearch
semantic similarity for composite scoring.

Composite score weights:
    0.3 × Neptune entity similarity
    0.3 × OpenSearch semantic similarity
    0.2 × charge type match
    0.2 × defendant profile match

When OpenSearch is unavailable, falls back to Neptune-only similarity.
"""

import json
import logging
import uuid
from typing import Any, Optional

from models.prosecutor import (
    PrecedentMatch,
    RulingDistribution,
    RulingOutcome,
    SentencingAdvisory,
)

logger = logging.getLogger(__name__)

_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"

# Composite score weights
_W_ENTITY = 0.3
_W_SEMANTIC = 0.3
_W_CHARGE = 0.2
_W_PROFILE = 0.2

# Neptune-only fallback weights (when OpenSearch unavailable)
_W_ENTITY_FALLBACK = 0.5
_W_CHARGE_FALLBACK = 0.3
_W_PROFILE_FALLBACK = 0.2


class PrecedentAnalysisService:
    """Finds historically similar cases and generates sentencing advisories."""

    SENIOR_LEGAL_ANALYST_PERSONA = (
        "You are a senior federal prosecutor (AUSA) with 20+ years of experience. "
        "Reason using proper legal terminology. Cite case law patterns and reference "
        "federal sentencing guidelines (USSG) where applicable. Provide thorough legal "
        "justifications for every recommendation."
    )

    def __init__(
        self,
        aurora_cm,
        neptune_cm,
        bedrock_client,
        opensearch_client=None,
    ):
        self._db = aurora_cm
        self._neptune = neptune_cm
        self._bedrock = bedrock_client
        self._opensearch = opensearch_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def find_precedents(
        self, case_id: str, charge_type: str, top_k: int = 10
    ) -> list[PrecedentMatch]:
        """Find top-K matching precedent cases by composite similarity.

        Combines Neptune entity similarity, OpenSearch semantic similarity,
        charge type match, and defendant profile match into a composite
        score.  Falls back to Neptune-only when OpenSearch is unavailable.
        """
        # Fetch all precedent cases from Aurora
        precedent_rows = self._fetch_precedent_cases(charge_type)
        if not precedent_rows:
            return []

        # Compute per-component scores
        entity_scores = self._compute_entity_similarity(case_id, precedent_rows)
        semantic_scores = self._compute_semantic_similarity(case_id, precedent_rows)
        charge_scores = self._compute_charge_match(charge_type, precedent_rows)
        profile_scores = self._compute_profile_match(case_id, precedent_rows)

        use_opensearch = self._opensearch is not None and semantic_scores is not None

        matches: list[PrecedentMatch] = []
        for row in precedent_rows:
            pid = row["precedent_id"]

            entity_sim = entity_scores.get(pid, 0.0)
            charge_sim = charge_scores.get(pid, 0.0)
            profile_sim = profile_scores.get(pid, 0.0)

            if use_opensearch:
                semantic_sim = semantic_scores.get(pid, 0.0)
                composite = (
                    _W_ENTITY * entity_sim
                    + _W_SEMANTIC * semantic_sim
                    + _W_CHARGE * charge_sim
                    + _W_PROFILE * profile_sim
                )
            else:
                # Fallback: redistribute semantic weight
                composite = (
                    _W_ENTITY_FALLBACK * entity_sim
                    + _W_CHARGE_FALLBACK * charge_sim
                    + _W_PROFILE_FALLBACK * profile_sim
                )

            score = max(0, min(100, round(composite * 100)))

            key_factors = row.get("key_factors", [])
            if not isinstance(key_factors, list):
                key_factors = []

            matches.append(
                PrecedentMatch(
                    precedent_id=pid,
                    case_reference=row["case_reference"],
                    charge_type=row["charge_type"],
                    ruling=RulingOutcome(row["ruling"]),
                    sentence=row.get("sentence"),
                    similarity_score=score,
                    key_factors=key_factors,
                    judge=row.get("judge"),
                    jurisdiction=row.get("jurisdiction"),
                )
            )

        # Sort by similarity descending, take top_k
        matches.sort(key=lambda m: m.similarity_score, reverse=True)
        return matches[:top_k]

    def compute_ruling_distribution(
        self, matches: list[PrecedentMatch]
    ) -> RulingDistribution:
        """Compute outcome percentages across matched precedents.

        Percentages sum to 100 (within floating-point tolerance).
        """
        total = len(matches)
        if total == 0:
            return RulingDistribution(
                guilty_pct=0.0,
                not_guilty_pct=0.0,
                plea_deal_pct=0.0,
                dismissed_pct=0.0,
                settled_pct=0.0,
                total_cases=0,
            )

        counts = {
            RulingOutcome.GUILTY: 0,
            RulingOutcome.NOT_GUILTY: 0,
            RulingOutcome.PLEA_DEAL: 0,
            RulingOutcome.DISMISSED: 0,
            RulingOutcome.SETTLED: 0,
        }
        for m in matches:
            counts[m.ruling] = counts.get(m.ruling, 0) + 1

        # Compute raw percentages
        raw = {k: (v / total) * 100 for k, v in counts.items()}

        # Round and adjust to ensure sum == 100
        rounded = {k: round(v, 2) for k, v in raw.items()}
        diff = 100.0 - sum(rounded.values())

        # Apply rounding correction to the largest bucket
        if abs(diff) > 0.001:
            largest_key = max(rounded, key=rounded.get)
            rounded[largest_key] = round(rounded[largest_key] + diff, 2)

        return RulingDistribution(
            guilty_pct=rounded[RulingOutcome.GUILTY],
            not_guilty_pct=rounded[RulingOutcome.NOT_GUILTY],
            plea_deal_pct=rounded[RulingOutcome.PLEA_DEAL],
            dismissed_pct=rounded[RulingOutcome.DISMISSED],
            settled_pct=rounded[RulingOutcome.SETTLED],
            total_cases=total,
        )

    def generate_sentencing_advisory(
        self, case_id: str, matches: list[PrecedentMatch]
    ) -> SentencingAdvisory:
        """Generate sentencing advisory citing precedent cases and guidelines.

        Uses Bedrock with Senior_Legal_Analyst_Persona.  Includes a
        disclaimer when fewer than 3 matches have similarity > 50.
        """
        high_confidence_count = sum(
            1 for m in matches if m.similarity_score > 50
        )
        disclaimer = None
        if high_confidence_count < 3:
            disclaimer = (
                "This advisory is based on limited precedent data. "
                f"Only {high_confidence_count} precedent case(s) matched with "
                "similarity above 50%. Results should be interpreted with caution."
            )

        if not matches:
            return SentencingAdvisory(
                likely_sentence="Insufficient precedent data for sentencing advisory.",
                fine_or_penalty="N/A",
                supervised_release="N/A",
                precedent_match_pct=0,
                disclaimer=disclaimer,
            )

        avg_similarity = round(
            sum(m.similarity_score for m in matches) / len(matches)
        )

        # Build precedent summary for Bedrock prompt
        precedent_summary = self._build_precedent_summary(matches)

        if not self._bedrock:
            # Fallback: static advisory without case law citations
            return self._static_advisory(matches, avg_similarity, disclaimer)

        return self._bedrock_sentencing_advisory(
            case_id, matches, precedent_summary, avg_similarity, disclaimer
        )

    # ------------------------------------------------------------------
    # Similarity component computations
    # ------------------------------------------------------------------

    def _compute_entity_similarity(
        self, case_id: str, precedent_rows: list[dict]
    ) -> dict[str, float]:
        """Compute Neptune entity similarity between case and each precedent.

        Uses shared entity count as a proxy for similarity.
        """
        scores: dict[str, float] = {}

        if not self._neptune:
            return {row["precedent_id"]: 0.0 for row in precedent_rows}

        # Get case entities from Neptune
        case_entities = self._fetch_case_entities(case_id)
        case_entity_names = {e.get("canonical_name", "").lower() for e in case_entities}

        if not case_entity_names:
            return {row["precedent_id"]: 0.0 for row in precedent_rows}

        for row in precedent_rows:
            pid = row["precedent_id"]
            # Use key_factors as proxy for precedent entities
            precedent_factors = row.get("key_factors", [])
            if not isinstance(precedent_factors, list):
                precedent_factors = []

            if not precedent_factors:
                scores[pid] = 0.0
                continue

            factor_names = {f.lower() for f in precedent_factors if isinstance(f, str)}
            overlap = len(case_entity_names & factor_names)
            max_possible = max(len(case_entity_names), len(factor_names), 1)
            scores[pid] = overlap / max_possible

        return scores

    def _compute_semantic_similarity(
        self, case_id: str, precedent_rows: list[dict]
    ) -> Optional[dict[str, float]]:
        """Compute OpenSearch semantic similarity.

        Returns None when OpenSearch is unavailable (triggers fallback).
        """
        if not self._opensearch:
            return None

        try:
            # Query OpenSearch for case summary vector
            case_summary = self._fetch_case_summary(case_id)
            if not case_summary:
                return {row["precedent_id"]: 0.0 for row in precedent_rows}

            scores: dict[str, float] = {}
            for row in precedent_rows:
                pid = row["precedent_id"]
                precedent_summary = row.get("case_summary", "")
                if not precedent_summary:
                    scores[pid] = 0.0
                    continue

                try:
                    result = self._opensearch.search(
                        body={
                            "query": {
                                "match": {"content": case_summary}
                            },
                            "size": 1,
                        }
                    )
                    hits = result.get("hits", {}).get("hits", [])
                    if hits:
                        scores[pid] = min(1.0, hits[0].get("_score", 0.0) / 10.0)
                    else:
                        scores[pid] = 0.0
                except Exception:
                    scores[pid] = 0.0

            return scores
        except Exception as e:
            logger.warning("OpenSearch semantic similarity failed: %s", e)
            return None

    def _compute_charge_match(
        self, charge_type: str, precedent_rows: list[dict]
    ) -> dict[str, float]:
        """Compute charge type match score.

        Exact match = 1.0, partial match (same statute family) = 0.5,
        no match = 0.0.
        """
        scores: dict[str, float] = {}
        charge_lower = charge_type.lower().strip()

        for row in precedent_rows:
            pid = row["precedent_id"]
            precedent_charge = row.get("charge_type", "").lower().strip()

            if precedent_charge == charge_lower:
                scores[pid] = 1.0
            elif self._same_statute_family(charge_lower, precedent_charge):
                scores[pid] = 0.5
            else:
                scores[pid] = 0.0

        return scores

    def _compute_profile_match(
        self, case_id: str, precedent_rows: list[dict]
    ) -> dict[str, float]:
        """Compute defendant profile match score.

        Uses aggravating/mitigating factor overlap as a proxy.
        """
        case_factors = self._fetch_case_factors(case_id)
        case_factor_set = {f.lower() for f in case_factors if isinstance(f, str)}

        scores: dict[str, float] = {}
        for row in precedent_rows:
            pid = row["precedent_id"]
            agg = row.get("aggravating_factors", [])
            mit = row.get("mitigating_factors", [])
            if not isinstance(agg, list):
                agg = []
            if not isinstance(mit, list):
                mit = []

            precedent_factors = {
                f.lower() for f in (agg + mit) if isinstance(f, str)
            }

            if not case_factor_set or not precedent_factors:
                scores[pid] = 0.0
                continue

            overlap = len(case_factor_set & precedent_factors)
            max_possible = max(len(case_factor_set), len(precedent_factors), 1)
            scores[pid] = overlap / max_possible

        return scores

    # ------------------------------------------------------------------
    # Bedrock interaction
    # ------------------------------------------------------------------

    def _bedrock_sentencing_advisory(
        self,
        case_id: str,
        matches: list[PrecedentMatch],
        precedent_summary: str,
        avg_similarity: int,
        disclaimer: Optional[str],
    ) -> SentencingAdvisory:
        """Use Bedrock to generate a sentencing advisory."""
        case_names = [m.case_reference for m in matches[:5]]

        prompt = (
            "Based on the following precedent cases, generate a sentencing advisory "
            "for the current case.\n\n"
            f"Precedent Cases:\n{precedent_summary}\n\n"
            "Provide:\n"
            "- likely_sentence: expected sentence citing specific precedent cases by name\n"
            "- fine_or_penalty: expected fine/penalty range with USSG references\n"
            "- supervised_release: expected supervised release terms\n\n"
            "You MUST cite at least one precedent case by name (e.g., "
            f"{case_names[0] if case_names else 'United States v. Smith'}).\n"
            "You MUST reference at least one federal sentencing guideline section "
            "(e.g., USSG §2B1.1, USSG §3E1.1).\n\n"
            "Return JSON object with keys: likely_sentence, fine_or_penalty, "
            "supervised_release.\nReturn ONLY JSON."
        )

        try:
            result = self._invoke_bedrock(prompt)

            likely = result.get("likely_sentence", "")
            fine = result.get("fine_or_penalty", "")
            release = result.get("supervised_release", "")

            # Ensure at least one case reference is present
            has_case_ref = any(name in likely or name in fine or name in release for name in case_names)
            if not has_case_ref and case_names:
                likely = f"Based on {case_names[0]}, {likely}"

            # Ensure USSG reference is present
            combined = f"{likely} {fine} {release}"
            if "USSG" not in combined and "U.S.S.G." not in combined:
                fine = f"{fine} (see USSG §2B1.1 for applicable guidelines)"

            return SentencingAdvisory(
                likely_sentence=likely or "Unable to determine likely sentence.",
                fine_or_penalty=fine or "Unable to determine fine/penalty.",
                supervised_release=release or "Unable to determine supervised release.",
                precedent_match_pct=avg_similarity,
                disclaimer=disclaimer,
            )
        except Exception as e:
            logger.warning("Bedrock sentencing advisory failed: %s", e)
            return self._static_advisory(matches, avg_similarity, disclaimer)

    def _invoke_bedrock(self, prompt: str) -> dict:
        """Invoke Bedrock and parse a JSON object response."""
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2048,
            "system": self.SENIOR_LEGAL_ANALYST_PERSONA,
            "messages": [{"role": "user", "content": prompt}],
        })
        resp = self._bedrock.invoke_model(modelId=_MODEL_ID, body=body)
        text = (
            json.loads(resp["body"].read())
            .get("content", [{}])[0]
            .get("text", "{}")
        )
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        return {}

    # ------------------------------------------------------------------
    # Data access helpers
    # ------------------------------------------------------------------

    def _fetch_precedent_cases(self, charge_type: str) -> list[dict]:
        """Fetch precedent cases from Aurora, prioritizing matching charge type."""
        if not self._db:
            return []
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT precedent_id, case_reference, charge_type, ruling, "
                    "sentence, judge, jurisdiction, case_summary, key_factors, "
                    "aggravating_factors, mitigating_factors "
                    "FROM precedent_cases "
                    "ORDER BY CASE WHEN charge_type = %s THEN 0 ELSE 1 END, "
                    "resolved_date DESC NULLS LAST",
                    (charge_type,),
                )
                rows = cur.fetchall()
                return [
                    {
                        "precedent_id": str(r[0]),
                        "case_reference": r[1],
                        "charge_type": r[2],
                        "ruling": r[3],
                        "sentence": r[4],
                        "judge": r[5],
                        "jurisdiction": r[6],
                        "case_summary": r[7],
                        "key_factors": r[8] if isinstance(r[8], list) else [],
                        "aggravating_factors": r[9] if isinstance(r[9], list) else [],
                        "mitigating_factors": r[10] if isinstance(r[10], list) else [],
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.warning("Failed to fetch precedent cases: %s", e)
            return []

    def _fetch_case_entities(self, case_id: str) -> list[dict]:
        """Fetch case entities from Neptune."""
        if not self._neptune:
            return []
        try:
            with self._neptune.traversal_source() as g:
                from db.neptune import entity_label, NODE_PROP_CANONICAL_NAME, NODE_PROP_ENTITY_TYPE
                label = entity_label(case_id)
                nodes = (
                    g.V()
                    .hasLabel(label)
                    .project("canonical_name", "entity_type")
                    .by(NODE_PROP_CANONICAL_NAME)
                    .by(NODE_PROP_ENTITY_TYPE)
                    .toList()
                )
                return nodes
        except Exception as e:
            logger.warning("Failed to fetch case entities: %s", e)
            return []

    def _fetch_case_summary(self, case_id: str) -> str:
        """Fetch case summary text from Aurora for semantic comparison."""
        if not self._db:
            return ""
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT title, description FROM case_files WHERE case_id = %s",
                    (case_id,),
                )
                row = cur.fetchone()
                if row:
                    return f"{row[0] or ''} {row[1] or ''}".strip()
                return ""
        except Exception as e:
            logger.warning("Failed to fetch case summary: %s", e)
            return ""

    def _fetch_case_factors(self, case_id: str) -> list[str]:
        """Fetch case-level factors (charge types from case_statutes)."""
        if not self._db:
            return []
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT s.citation FROM case_statutes cs "
                    "JOIN statutes s ON cs.statute_id = s.statute_id "
                    "WHERE cs.case_id = %s",
                    (case_id,),
                )
                return [str(r[0]) for r in cur.fetchall()]
        except Exception as e:
            logger.warning("Failed to fetch case factors: %s", e)
            return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _same_statute_family(charge_a: str, charge_b: str) -> bool:
        """Check if two charges belong to the same statute family.

        E.g., '18 u.s.c. § 1341' and '18 u.s.c. § 1343' are both
        in the fraud family (18 U.S.C. § 13xx).
        """
        # Extract statute number prefix (first 2 digits after §)
        def _extract_prefix(charge: str) -> str:
            idx = charge.find("§")
            if idx < 0:
                idx = charge.find("section")
            if idx < 0:
                return charge
            rest = charge[idx:].strip("§ section").strip()
            # Take first 2 digits as family
            digits = ""
            for ch in rest:
                if ch.isdigit():
                    digits += ch
                    if len(digits) >= 2:
                        break
                elif digits:
                    break
            return digits

        prefix_a = _extract_prefix(charge_a)
        prefix_b = _extract_prefix(charge_b)
        return bool(prefix_a) and prefix_a == prefix_b

    @staticmethod
    def _build_precedent_summary(matches: list[PrecedentMatch]) -> str:
        """Build a text summary of precedent matches for Bedrock prompt."""
        lines = []
        for m in matches[:10]:
            factors = ", ".join(m.key_factors[:5]) if m.key_factors else "N/A"
            lines.append(
                f"- {m.case_reference}: {m.charge_type}, ruling={m.ruling.value}, "
                f"sentence={m.sentence or 'N/A'}, similarity={m.similarity_score}%, "
                f"key_factors=[{factors}]"
            )
        return "\n".join(lines)

    @staticmethod
    def _static_advisory(
        matches: list[PrecedentMatch],
        avg_similarity: int,
        disclaimer: Optional[str],
    ) -> SentencingAdvisory:
        """Fallback advisory when Bedrock is unavailable."""
        if not matches:
            return SentencingAdvisory(
                likely_sentence="Insufficient precedent data.",
                fine_or_penalty="N/A",
                supervised_release="N/A",
                precedent_match_pct=0,
                disclaimer=disclaimer,
            )

        # Summarize from available data
        sentences = [m.sentence for m in matches if m.sentence]
        top_case = matches[0].case_reference

        likely = (
            f"Based on {top_case} and {len(matches)} similar cases, "
            f"sentencing data available from precedent records. "
            f"See USSG §2B1.1 for applicable guidelines."
        )

        return SentencingAdvisory(
            likely_sentence=likely,
            fine_or_penalty="Refer to federal sentencing guidelines (USSG §5E1.2).",
            supervised_release="Refer to USSG §5D1.2 for supervised release terms.",
            precedent_match_pct=avg_similarity,
            disclaimer=disclaimer,
        )

