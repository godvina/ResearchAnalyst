"""AI Hypothesis Testing Service (Req 27).

Allows investigators to state a hypothesis in natural language,
decomposes it into testable claims, evaluates each against evidence,
and produces a structured evaluation with confidence scores.
"""
import json
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class HypothesisTestingService:
    """Evaluates investigative hypotheses against case evidence."""

    def __init__(self, aurora_cm=None, bedrock_client=None, search_fn=None, graph_fn=None):
        self._db = aurora_cm
        self._bedrock = bedrock_client
        self._search = search_fn  # async fn(case_id, query) -> results
        self._graph = graph_fn    # async fn(case_id, entity) -> neighbors

    def evaluate(self, case_id: str, hypothesis: str, created_by: str = "investigator") -> dict:
        """Evaluate a hypothesis against case evidence."""
        # Step 1: Decompose hypothesis into testable claims
        claims = self._decompose(hypothesis)

        # Step 2: For each claim, search for supporting and contradicting evidence
        evaluated_claims = []
        for claim in claims:
            evidence = self._search_evidence(case_id, claim["text"])
            status = self._classify_evidence(claim["text"], evidence)
            evaluated_claims.append({
                "claim": claim["text"],
                "status": status["status"],  # SUPPORTED, CONTRADICTED, UNVERIFIED, PARTIALLY_SUPPORTED
                "confidence": status["confidence"],
                "supporting_docs": status.get("supporting", []),
                "contradicting_docs": status.get("contradicting", []),
                "evidence_gaps": status.get("gaps", []),
            })

        # Step 3: Compute overall confidence
        statuses = [c["status"] for c in evaluated_claims]
        supported = statuses.count("SUPPORTED")
        contradicted = statuses.count("CONTRADICTED")
        total = len(statuses) or 1
        overall_confidence = int((supported / total) * 100)
        if contradicted > 0:
            overall_confidence = max(0, overall_confidence - (contradicted / total) * 50)

        result = {
            "hypothesis_id": str(datetime.utcnow().timestamp()),
            "case_id": case_id,
            "hypothesis": hypothesis,
            "claims": evaluated_claims,
            "overall_confidence": overall_confidence,
            "summary": self._generate_summary(hypothesis, evaluated_claims, overall_confidence),
            "created_at": datetime.utcnow().isoformat(),
            "created_by": created_by,
        }
        self._store(result)
        return result

    def _decompose(self, hypothesis: str) -> list[dict]:
        """Use Bedrock to decompose hypothesis into testable claims."""
        if not self._bedrock:
            return [{"text": hypothesis}]
        try:
            prompt = f"""Decompose this investigative hypothesis into 3-5 specific, testable claims.
Each claim should be a single factual assertion that can be verified against evidence.

Hypothesis: "{hypothesis}"

Return a JSON array of objects with "text" field for each claim. Example:
[{{"text": "Person A is connected to Organization B"}}, {{"text": "Financial transactions occurred between 2005-2008"}}]

Return ONLY the JSON array, no other text."""
            body = json.dumps({"anthropic_version": "bedrock-2023-05-31", "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}]})
            resp = self._bedrock.invoke_model(modelId="anthropic.claude-3-haiku-20240307-v1:0", body=body)
            text = json.loads(resp["body"].read()).get("content", [{}])[0].get("text", "[]")
            # Extract JSON from response
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except Exception as e:
            logger.warning("Hypothesis decomposition failed: %s", e)
        return [{"text": hypothesis}]

    def _search_evidence(self, case_id: str, claim: str) -> list[dict]:
        """Search for evidence related to a claim."""
        if not self._search:
            return []
        try:
            return self._search(case_id, claim) or []
        except Exception as e:
            logger.warning("Evidence search failed: %s", e)
            return []

    def _classify_evidence(self, claim: str, evidence: list[dict]) -> dict:
        """Classify evidence as supporting, contradicting, or unverified."""
        if not evidence:
            return {"status": "UNVERIFIED", "confidence": 0, "gaps": [f"No evidence found for: {claim}"]}
        if not self._bedrock:
            return {"status": "PARTIALLY_SUPPORTED", "confidence": 50, "supporting": evidence[:3]}
        try:
            excerpts = "\n".join([f"- {e.get('filename','doc')}: {e.get('text','')[:200]}" for e in evidence[:5]])
            prompt = f"""Evaluate whether this evidence supports or contradicts the claim.

Claim: "{claim}"
Evidence:
{excerpts}

Return JSON: {{"status": "SUPPORTED"|"CONTRADICTED"|"PARTIALLY_SUPPORTED", "confidence": 0-100, "reasoning": "..."}}
Return ONLY JSON."""
            body = json.dumps({"anthropic_version": "bedrock-2023-05-31", "max_tokens": 512,
                "messages": [{"role": "user", "content": prompt}]})
            resp = self._bedrock.invoke_model(modelId="anthropic.claude-3-haiku-20240307-v1:0", body=body)
            text = json.loads(resp["body"].read()).get("content", [{}])[0].get("text", "{}")
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                result = json.loads(text[start:end])
                result["supporting"] = evidence[:3]
                return result
        except Exception as e:
            logger.warning("Evidence classification failed: %s", e)
        return {"status": "PARTIALLY_SUPPORTED", "confidence": 50, "supporting": evidence[:3]}

    def _generate_summary(self, hypothesis: str, claims: list, confidence: int) -> str:
        """Generate a human-readable summary of the evaluation."""
        supported = sum(1 for c in claims if c["status"] == "SUPPORTED")
        contradicted = sum(1 for c in claims if c["status"] == "CONTRADICTED")
        unverified = sum(1 for c in claims if c["status"] == "UNVERIFIED")
        total = len(claims)
        summary = f"Hypothesis evaluated against {total} claims. "
        summary += f"{supported} supported, {contradicted} contradicted, {unverified} unverified. "
        summary += f"Overall confidence: {confidence}%. "
        if contradicted > 0:
            summary += "WARNING: Contradicting evidence found — review before proceeding. "
        if unverified > 0:
            summary += f"{unverified} claim(s) lack evidence — additional investigation needed."
        return summary

    # ------------------------------------------------------------------
    # Generate hypotheses from patterns (investigator-ai-first)
    # ------------------------------------------------------------------

    def generate_hypotheses(self, case_id: str, patterns: list) -> list[dict]:
        """Generate investigative hypotheses from detected patterns using Bedrock."""
        if not patterns:
            return []
        pattern_summary = "\n".join(
            f"- {getattr(p, 'connection_type', 'unknown')}: {getattr(p, 'explanation', str(p))[:150]}"
            for p in patterns[:10]
        )
        prompt = (
            f"Based on these patterns detected in case {case_id}:\n{pattern_summary}\n\n"
            f"Generate 3-5 investigative hypotheses. For each, provide:\n"
            f"1. hypothesis_text: a clear statement\n"
            f"2. confidence: High, Medium, or Low\n"
            f"3. supporting_evidence: list of evidence citations\n"
            f"4. recommended_actions: list of investigative steps\n"
            f"Return as JSON array."
        )
        if not self._bedrock:
            return [{"hypothesis_text": f"Pattern-based hypothesis for case {case_id}",
                     "confidence": "Medium", "supporting_evidence": [], "recommended_actions": ["Review patterns"]}]
        try:
            body = json.dumps({"anthropic_version": "bedrock-2023-05-31", "max_tokens": 2000,
                "messages": [{"role": "user", "content": prompt}]})
            resp = self._bedrock.invoke_model(modelId="anthropic.claude-3-haiku-20240307-v1:0", body=body)
            text = json.loads(resp["body"].read()).get("content", [{}])[0].get("text", "[]")
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except Exception as e:
            logger.warning("Hypothesis generation failed: %s", e)
        return [{"hypothesis_text": f"Investigate patterns in case {case_id}",
                 "confidence": "Medium", "supporting_evidence": [], "recommended_actions": ["Review detected patterns"]}]

    def _store(self, result: dict) -> None:
        """Store hypothesis evaluation in Aurora."""
        if not self._db:
            return
        try:
            with self._db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO case_hypotheses (case_id, hypothesis_text, evaluation_json, confidence_score, created_by) VALUES (%s,%s,%s,%s,%s)",
                        (result["case_id"], result["hypothesis"], json.dumps(result["claims"]),
                         result["overall_confidence"], result["created_by"]))
                conn.commit()
        except Exception as e:
            logger.warning("Failed to store hypothesis: %s", e)
