"""Proof Engine — Standards of Proof Evaluation.

Evaluates whether findings meet configurable evidentiary standards.
Supports 6 standards: scientific, criminal_legal, civil_legal,
intelligence, financial_audit, journalistic.

Produces structured verdicts: PROVEN, UNPROVEN, INSUFFICIENT_EVIDENCE
with checklist items, scores, reasoning, and research directions.
"""
import json
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ChecklistItem:
    """A single evidence requirement within a proof standard."""
    description: str
    weight: float
    is_critical: bool
    score: float = 0.0          # 0.0 (unsatisfied), 0.5 (partial), 1.0 (satisfied)
    justification: str = ""


@dataclass
class ProofVerdict:
    """The complete proof evaluation result for a finding."""
    verdict_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    finding_id: str = ""
    standard_used: str = ""
    tenant_id: str = ""
    checklist_items: list = field(default_factory=list)
    overall_score: float = 0.0
    verdict: str = "INSUFFICIENT_EVIDENCE"  # PROVEN | UNPROVEN | INSUFFICIENT_EVIDENCE
    reasoning: dict = field(default_factory=dict)
    research_directions: list = field(default_factory=list)
    evaluated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "verdict_id": self.verdict_id,
            "finding_id": self.finding_id,
            "standard_used": self.standard_used,
            "tenant_id": self.tenant_id,
            "checklist_items": [
                {"description": i.description, "weight": i.weight,
                 "is_critical": i.is_critical, "score": i.score,
                 "justification": i.justification}
                for i in self.checklist_items
            ],
            "overall_score": self.overall_score,
            "verdict": self.verdict,
            "reasoning": self.reasoning,
            "research_directions": self.research_directions,
            "evaluated_at": self.evaluated_at,
        }


class ProofEngine:
    """Evaluates findings against configurable standards of proof.
    
    After the taxonomy detects a pattern and ACH scoring evaluates competing
    hypotheses, the Proof Engine determines whether the finding meets the
    required evidentiary standard for the tenant/investigation type.
    """

    SYSTEM_PROMPT = """You are an expert evidence evaluator applying formal standards of proof.
You will be given:
1. A finding (pattern match or analytical conclusion)
2. Available evidence supporting or contradicting the finding
3. A specific evidence checklist item to evaluate

Score the checklist item:
- 1.0 = SATISFIED: The available evidence clearly meets this criterion
- 0.5 = PARTIAL: Some evidence exists but is incomplete or ambiguous
- 0.0 = UNSATISFIED: No evidence meets this criterion, or evidence contradicts it

Also provide:
- A one-sentence justification (max 100 words)
- Whether the evidence ACTIVELY CONTRADICTS the finding (for UNPROVEN verdicts)

Respond in JSON:
{"score": <float>, "justification": "<string>", "contradicts": <bool>}"""

    def __init__(self, bedrock_client=None, connection_manager=None):
        self.bedrock = bedrock_client
        self.db = connection_manager
        self._standards_cache = {}

    def get_standard(self, standard_name: str) -> Optional[dict]:
        """Load a proof standard from Aurora or cache."""
        if standard_name in self._standards_cache:
            return self._standards_cache[standard_name]

        if self.db:
            row = self.db.fetch_one(
                "SELECT * FROM conspiracy.proof_standards WHERE standard_name = %s",
                (standard_name,)
            )
            if row:
                standard = {
                    "name": row['standard_name'],
                    "description": row['description'],
                    "checklist_items": json.loads(row['checklist_items']) if isinstance(row['checklist_items'], str) else row['checklist_items'],
                    "item_weights": json.loads(row['item_weights']) if isinstance(row['item_weights'], str) else row['item_weights'],
                    "critical_items": json.loads(row['critical_items']) if isinstance(row['critical_items'], str) else row['critical_items'],
                    "proof_threshold": row['proof_threshold'],
                }
                self._standards_cache[standard_name] = standard
                return standard

        # Fallback: hardcoded defaults
        return self._get_default_standard(standard_name)

    def evaluate(self, finding_id: str, finding_data: dict, evidence: str,
                 standard_name: str, tenant_id: str = "conspiracy_theories") -> ProofVerdict:
        """Evaluate a finding against a specified standard of proof.
        
        Args:
            finding_id: UUID of the finding to evaluate
            finding_data: Dict with finding details (description, signature, theory, etc.)
            evidence: Available evidence text supporting/contradicting the finding
            standard_name: Which proof standard to apply
            tenant_id: Tenant requesting the evaluation
            
        Returns:
            ProofVerdict with checklist scores, verdict, and research directions
        """
        standard = self.get_standard(standard_name)
        if not standard:
            return ProofVerdict(
                finding_id=finding_id,
                standard_used=standard_name,
                verdict="INSUFFICIENT_EVIDENCE",
                reasoning={"error": f"Unknown standard: {standard_name}"}
            )

        # Generate checklist items from the standard
        items = []
        contradicts_finding = False

        for i, item_desc in enumerate(standard['checklist_items']):
            weight = standard['item_weights'][i] if i < len(standard['item_weights']) else 0.1
            is_critical = item_desc in standard['critical_items']

            # Score each item via Bedrock
            score, justification, contradicts = self._score_item(
                item_desc, finding_data, evidence
            )

            items.append(ChecklistItem(
                description=item_desc,
                weight=weight,
                is_critical=is_critical,
                score=score,
                justification=justification
            ))

            if contradicts:
                contradicts_finding = True

        # Calculate overall score (weighted sum)
        total_weight = sum(item.weight for item in items)
        if total_weight > 0:
            overall_score = sum(item.score * item.weight for item in items) / total_weight
        else:
            overall_score = 0.0

        # Determine verdict
        all_critical_satisfied = all(
            item.score >= 1.0 for item in items if item.is_critical
        )
        threshold = standard['proof_threshold']

        if contradicts_finding:
            verdict = "UNPROVEN"
        elif overall_score >= threshold and all_critical_satisfied:
            verdict = "PROVEN"
        else:
            verdict = "INSUFFICIENT_EVIDENCE"

        # Generate reasoning
        satisfied = [i for i in items if i.score >= 1.0]
        unsatisfied = [i for i in items if i.score < 1.0]
        critical_failed = [i for i in items if i.is_critical and i.score < 1.0]

        reasoning = {
            "verdict": verdict,
            "overall_score": round(overall_score, 3),
            "threshold": threshold,
            "satisfied_items": [{"item": i.description, "justification": i.justification} for i in satisfied],
            "unsatisfied_items": [{"item": i.description, "justification": i.justification} for i in unsatisfied],
            "critical_items_failed": [i.description for i in critical_failed],
            "contradicts_finding": contradicts_finding,
        }

        # Generate research directions (what would change the verdict)
        research_directions = self._generate_research_directions(unsatisfied, verdict, finding_data)

        proof_verdict = ProofVerdict(
            finding_id=finding_id,
            standard_used=standard_name,
            tenant_id=tenant_id,
            checklist_items=items,
            overall_score=round(overall_score, 3),
            verdict=verdict,
            reasoning=reasoning,
            research_directions=research_directions,
        )

        # Store in Aurora
        if self.db:
            self._store_verdict(proof_verdict)

        return proof_verdict

    def _score_item(self, item_description: str, finding_data: dict,
                    evidence: str) -> tuple:
        """Score a single checklist item against available evidence.
        
        Returns: (score: float, justification: str, contradicts: bool)
        """
        if not self.bedrock:
            return (0.0, "No AI evaluation available", False)

        finding_desc = finding_data.get('description', 'Unknown finding')
        theory = finding_data.get('theory_name', 'unknown')

        prompt = f"""FINDING: "{finding_desc}" (from {theory} dataset)

AVAILABLE EVIDENCE:
{evidence[:2000]}

CHECKLIST ITEM TO EVALUATE:
"{item_description}"

Does the available evidence satisfy this checklist item? Score 0.0, 0.5, or 1.0.
Does the evidence ACTIVELY CONTRADICT the finding (not just fail to support it)?"""

        try:
            response = self.bedrock.invoke_model(
                modelId="us.anthropic.claude-3-haiku-20240307-v1:0",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 200,
                    "system": self.SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": prompt}]
                }),
                contentType="application/json",
                accept="application/json"
            )

            result = json.loads(response['body'].read())
            content = result['content'][0]['text']
            parsed = json.loads(content)

            score = float(parsed.get('score', 0.0))
            score = max(0.0, min(1.0, score))  # Clamp to [0, 1]
            justification = parsed.get('justification', '')[:500]
            contradicts = bool(parsed.get('contradicts', False))

            return (score, justification, contradicts)

        except Exception as e:
            return (0.0, f"Evaluation failed: {str(e)[:100]}", False)

    def _generate_research_directions(self, unsatisfied: list, verdict: str,
                                       finding_data: dict) -> list:
        """Generate specific research directions that would move the finding toward PROVEN.
        
        For UNPROVEN findings: explain why it's disproven.
        For INSUFFICIENT_EVIDENCE: identify what specific investigations would help.
        """
        if verdict == "PROVEN":
            return ["Finding meets all evidentiary requirements."]

        if verdict == "UNPROVEN":
            return [
                "Evidence actively contradicts this finding.",
                "To rehabilitate: provide evidence addressing the contradiction directly.",
            ]

        # INSUFFICIENT_EVIDENCE — generate actionable research directions
        directions = []
        for item in unsatisfied[:5]:
            directions.append(
                f"To satisfy '{item.description}': {item.justification or 'Obtain relevant evidence'}"
            )

        return directions

    def _store_verdict(self, verdict: ProofVerdict):
        """Store the proof verdict in Aurora."""
        try:
            from datetime import datetime, timezone
            verdict.evaluated_at = datetime.now(timezone.utc).isoformat()

            self.db.execute(
                """INSERT INTO conspiracy.proof_verdicts
                   (verdict_id, finding_id, tenant_id, standard_used, checklist_items,
                    scores, overall_score, verdict, reasoning, evaluated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (verdict.verdict_id, verdict.finding_id, verdict.tenant_id,
                 verdict.standard_used,
                 json.dumps([{"desc": i.description, "weight": i.weight, "critical": i.is_critical}
                             for i in verdict.checklist_items]),
                 json.dumps([{"desc": i.description, "score": i.score, "justification": i.justification}
                             for i in verdict.checklist_items]),
                 verdict.overall_score, verdict.verdict,
                 json.dumps(verdict.reasoning), verdict.evaluated_at)
            )
        except Exception as e:
            print(f"Warning: Failed to store proof verdict: {e}")

    def _get_default_standard(self, name: str) -> Optional[dict]:
        """Hardcoded fallback standards when DB is unavailable."""
        defaults = {
            "scientific": {
                "name": "scientific",
                "description": "Scientific method standard",
                "checklist_items": [
                    "Falsifiable hypothesis stated",
                    "Statistical significance demonstrated (p<0.05)",
                    "Independent replication achieved or achievable",
                    "Peer critique addressed",
                    "Alternative explanations systematically eliminated"
                ],
                "item_weights": [0.15, 0.25, 0.25, 0.15, 0.20],
                "critical_items": [
                    "Statistical significance demonstrated (p<0.05)",
                    "Alternative explanations systematically eliminated"
                ],
                "proof_threshold": 0.70,
            },
            "intelligence": {
                "name": "intelligence",
                "description": "IC analytic confidence standard",
                "checklist_items": [
                    "Minimum source count met (2+)",
                    "Source independence verified",
                    "Diagnostic evidence identified",
                    "Alternative hypotheses eliminated via ACH",
                    "Confidence level assigned (Low/Mod/High)"
                ],
                "item_weights": [0.20, 0.20, 0.25, 0.20, 0.15],
                "critical_items": ["Diagnostic evidence identified"],
                "proof_threshold": 0.65,
            },
            "criminal_legal": {
                "name": "criminal_legal",
                "description": "Beyond reasonable doubt standard",
                "checklist_items": [
                    "Chain of custody documented",
                    "Independent corroboration obtained",
                    "No credible alternative explanation remaining",
                    "Witness statements consistent and uncoerced",
                    "Evidence authenticated"
                ],
                "item_weights": [0.20, 0.25, 0.25, 0.15, 0.15],
                "critical_items": [
                    "Chain of custody documented",
                    "No credible alternative explanation remaining"
                ],
                "proof_threshold": 0.85,
            },
            "journalistic": {
                "name": "journalistic",
                "description": "Documentary/investigative journalism standard (Hook→Facts→Anomaly→Pattern→Implication)",
                "checklist_items": [
                    "Hook identified (provocative anomaly that challenges assumptions)",
                    "Established facts documented (peer-reviewed or institutional sources)",
                    "Anomaly is measurable, reproducible, and not yet debunked",
                    "Pattern demonstrated across geography, time, or culture",
                    "Implication stated as testable question (not conclusion)",
                    "Three-source rule satisfied (measurement + researcher + control)",
                    "Strongest counter-argument addressed (skeptic paragraph)",
                    "Expert sources identified on both sides"
                ],
                "item_weights": [0.10, 0.15, 0.20, 0.20, 0.10, 0.10, 0.10, 0.05],
                "critical_items": [
                    "Anomaly is measurable, reproducible, and not yet debunked",
                    "Pattern demonstrated across geography, time, or culture"
                ],
                "proof_threshold": 0.60,
            },
            "civil_legal": {
                "name": "civil_legal",
                "description": "Balance of probabilities standard",
                "checklist_items": [
                    "Positive evidence presented (not just absence of disproof)",
                    "More likely than not (>50% probability)",
                    "Evidence is credible and internally consistent",
                    "Reasonable inference drawn from established facts"
                ],
                "item_weights": [0.30, 0.30, 0.20, 0.20],
                "critical_items": [
                    "More likely than not (>50% probability)"
                ],
                "proof_threshold": 0.55,
            },
            "financial_audit": {
                "name": "financial_audit",
                "description": "Material accuracy and substantive testing standard",
                "checklist_items": [
                    "Materiality threshold defined and tested",
                    "Substantive testing performed on sample",
                    "Sampling methodology is adequate for population",
                    "Management representations are consistent with evidence",
                    "Analytical procedures confirm reasonableness"
                ],
                "item_weights": [0.20, 0.25, 0.20, 0.20, 0.15],
                "critical_items": [
                    "Substantive testing performed on sample"
                ],
                "proof_threshold": 0.70,
            },
        }
        return defaults.get(name)
