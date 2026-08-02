"""Analysis of Competing Hypotheses (ACH) Scoring Service.

Implements the CIA's Structured Analytic Technique for evaluating findings
against multiple competing explanations. Prevents confirmation bias by
scoring every finding against 4 hypotheses simultaneously.

Based on Richards Heuer's "Psychology of Intelligence Analysis" (1999).
Heuer Scale: -2 (strongly contradicts) to +2 (highly consistent).
"""
import json
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ACHHypothesis:
    """One competing explanation for a finding."""
    hypothesis_id: str
    label: str          # conspiracy, official, coincidence, hybrid
    description: str


@dataclass
class ACHScore:
    """Score of one piece of evidence against one hypothesis."""
    finding_id: str
    hypothesis_id: str
    score: int          # -2 to +2 (Heuer scale)
    reasoning: str


@dataclass
class ACHMatrix:
    """Complete ACH evaluation for a single finding."""
    matrix_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    finding_id: str = ""
    document_id: str = ""
    signature_id: str = ""
    hypotheses: list = field(default_factory=list)
    scores: list = field(default_factory=list)
    dominant_hypothesis: str = ""
    confidence_delta: float = 0.0

    def compute_dominant(self):
        """Determine which hypothesis has the highest cumulative score."""
        totals = {}
        for score in self.scores:
            h_id = score.hypothesis_id if isinstance(score, ACHScore) else score['hypothesis_id']
            s = score.score if isinstance(score, ACHScore) else score['score']
            totals[h_id] = totals.get(h_id, 0) + s

        if not totals:
            self.dominant_hypothesis = "insufficient_data"
            self.confidence_delta = 0.0
            return

        sorted_hypotheses = sorted(totals.items(), key=lambda x: x[1], reverse=True)
        self.dominant_hypothesis = sorted_hypotheses[0][0]

        if len(sorted_hypotheses) >= 2:
            self.confidence_delta = sorted_hypotheses[0][1] - sorted_hypotheses[1][1]
        else:
            self.confidence_delta = abs(sorted_hypotheses[0][1])


# Default hypothesis set for conspiracy theory evaluation
DEFAULT_HYPOTHESES = [
    ACHHypothesis(
        "h_conspiracy", "conspiracy",
        "Deliberate concealment or coordination by powerful actors to hide truth"
    ),
    ACHHypothesis(
        "h_official", "official",
        "The official/institutional explanation is substantially accurate"
    ),
    ACHHypothesis(
        "h_coincidence", "coincidence",
        "Random coincidence, bureaucratic incompetence, or institutional inertia"
    ),
    ACHHypothesis(
        "h_hybrid", "hybrid",
        "Partial truth in multiple explanations; complex multi-causal reality"
    ),
]


class ACHScoringService:
    """Evaluates findings against competing hypotheses using Bedrock Claude.
    
    For each finding (a signature match from the taxonomy scanner), this service:
    1. Presents the finding + evidence to Claude
    2. Asks Claude to score each of 4 hypotheses on the Heuer scale (-2 to +2)
    3. Stores the ACH matrix in Aurora
    4. Computes the dominant hypothesis and confidence delta
    """

    SYSTEM_PROMPT = """You are an intelligence analyst applying the Analysis of Competing Hypotheses (ACH) methodology developed by Richards Heuer at the CIA. 

Your task: evaluate a single piece of evidence/finding against 4 competing hypotheses. For each hypothesis, assign a score from -2 to +2:
- +2: Evidence is highly consistent with this hypothesis (would be very likely if hypothesis were true)
- +1: Evidence is somewhat consistent with this hypothesis
-  0: Evidence is neutral/irrelevant to this hypothesis
- -1: Evidence is somewhat inconsistent with this hypothesis
- -2: Evidence strongly contradicts this hypothesis

Be rigorous. Do not favor any hypothesis. Consider each independently.
The most powerful evidence is DIAGNOSTIC — it strongly supports one hypothesis while contradicting others.

Respond in JSON format:
{
  "scores": [
    {"hypothesis_id": "h_conspiracy", "score": <int>, "reasoning": "<one sentence>"},
    {"hypothesis_id": "h_official", "score": <int>, "reasoning": "<one sentence>"},
    {"hypothesis_id": "h_coincidence", "score": <int>, "reasoning": "<one sentence>"},
    {"hypothesis_id": "h_hybrid", "score": <int>, "reasoning": "<one sentence>"}
  ]
}"""

    def __init__(self, bedrock_client=None, connection_manager=None):
        self.bedrock = bedrock_client
        self.db = connection_manager

    def score_finding(self, finding: dict, signature_match: dict,
                      document_context: str) -> ACHMatrix:
        """Score a single finding against all competing hypotheses.
        
        Args:
            finding: The detected pattern/anomaly
            signature_match: Which taxonomy signature was matched
            document_context: Relevant text from the source document
            
        Returns:
            ACHMatrix with scores for all 4 hypotheses
        """
        matrix = ACHMatrix(
            finding_id=finding.get('finding_id', str(uuid.uuid4())),
            document_id=finding.get('document_id', ''),
            signature_id=signature_match.get('signature_id', ''),
            hypotheses=[h.__dict__ for h in DEFAULT_HYPOTHESES],
        )

        if not self.bedrock:
            # Without Bedrock, return neutral scores
            matrix.scores = [
                ACHScore(matrix.finding_id, h.hypothesis_id, 0, "No AI evaluation available")
                for h in DEFAULT_HYPOTHESES
            ]
            matrix.compute_dominant()
            return matrix

        # Build the evaluation prompt
        user_prompt = self._build_evaluation_prompt(finding, signature_match, document_context)

        try:
            response = self.bedrock.invoke_model(
                modelId="anthropic.claude-sonnet-4-20250514-v1:0",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 500,
                    "system": self.SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": user_prompt}]
                }),
                contentType="application/json",
                accept="application/json"
            )

            result = json.loads(response['body'].read())
            content = result['content'][0]['text']

            # Parse JSON response
            scores_data = json.loads(content)
            matrix.scores = [
                ACHScore(
                    finding_id=matrix.finding_id,
                    hypothesis_id=s['hypothesis_id'],
                    score=max(-2, min(2, int(s['score']))),  # Clamp to [-2, +2]
                    reasoning=s.get('reasoning', '')[:500]
                )
                for s in scores_data.get('scores', [])
            ]

        except Exception as e:
            # On failure, assign neutral scores with error note
            matrix.scores = [
                ACHScore(matrix.finding_id, h.hypothesis_id, 0, f"Evaluation failed: {str(e)[:100]}")
                for h in DEFAULT_HYPOTHESES
            ]

        matrix.compute_dominant()

        # Store in Aurora if available
        if self.db:
            self._store_matrix(matrix)

        return matrix

    def _build_evaluation_prompt(self, finding: dict, signature_match: dict,
                                  document_context: str) -> str:
        """Build the user prompt for ACH evaluation."""
        sig_desc = signature_match.get('description', 'Unknown signature')
        sim_score = signature_match.get('similarity_score', 0)
        theory = finding.get('theory_name', 'unknown')

        # Truncate context to avoid token limits
        context = document_context[:3000] if document_context else "No additional context available."

        return f"""FINDING: A document from the "{theory}" dataset matched the taxonomy signature:
"{sig_desc}"
(Similarity score: {sim_score:.2f})

EVIDENCE CONTEXT:
{context}

HYPOTHESES TO EVALUATE:
H1 (Conspiracy): Deliberate concealment or coordination by powerful actors
H2 (Official): The official/institutional explanation is substantially accurate  
H3 (Coincidence): Random coincidence, bureaucratic incompetence, or institutional inertia
H4 (Hybrid): Partial truth in multiple explanations; complex multi-causal reality

Score each hypothesis -2 to +2 based on how well this evidence supports or contradicts it."""

    def _store_matrix(self, matrix: ACHMatrix):
        """Store ACH scores in Aurora."""
        try:
            for score in matrix.scores:
                s = score if isinstance(score, ACHScore) else ACHScore(**score)
                self.db.execute(
                    """INSERT INTO conspiracy.ach_scores 
                       (match_id, document_id, hypothesis_id, score, reasoning)
                       VALUES (%s, %s, %s, %s, %s)
                       ON CONFLICT (match_id, hypothesis_id) DO UPDATE SET
                       score = EXCLUDED.score, reasoning = EXCLUDED.reasoning""",
                    (matrix.matrix_id, matrix.document_id,
                     s.hypothesis_id, s.score, s.reasoning)
                )

            # Update document summary
            totals = {}
            for score in matrix.scores:
                s = score if isinstance(score, ACHScore) else ACHScore(**score)
                totals[s.hypothesis_id] = totals.get(s.hypothesis_id, 0) + s.score

            self.db.execute(
                """INSERT INTO conspiracy.ach_document_summary
                   (document_id, dominant_hypothesis, conspiracy_total, official_total,
                    coincidence_total, hybrid_total, confidence_delta)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (document_id) DO UPDATE SET
                   dominant_hypothesis = EXCLUDED.dominant_hypothesis,
                   conspiracy_total = EXCLUDED.conspiracy_total,
                   official_total = EXCLUDED.official_total,
                   coincidence_total = EXCLUDED.coincidence_total,
                   hybrid_total = EXCLUDED.hybrid_total,
                   confidence_delta = EXCLUDED.confidence_delta,
                   computed_at = NOW()""",
                (matrix.document_id, matrix.dominant_hypothesis,
                 totals.get('h_conspiracy', 0), totals.get('h_official', 0),
                 totals.get('h_coincidence', 0), totals.get('h_hybrid', 0),
                 matrix.confidence_delta)
            )
        except Exception as e:
            print(f"Warning: Failed to store ACH matrix: {e}")

    def aggregate_theory_scores(self, theory_name: str) -> dict:
        """Aggregate ACH scores across all findings for a theory.
        
        Returns per-hypothesis totals and identifies dominant explanation.
        """
        if not self.db:
            return {"error": "No database connection"}

        rows = self.db.fetch_all("""
            SELECT hypothesis_id, SUM(score) as total, COUNT(*) as count, AVG(score) as avg
            FROM conspiracy.ach_scores a
            JOIN conspiracy.documents d ON a.document_id = d.document_id
            WHERE d.theory_name = %s
            GROUP BY hypothesis_id
            ORDER BY total DESC
        """, (theory_name,))

        result = {
            "theory_name": theory_name,
            "hypothesis_totals": {},
            "dominant_hypothesis": None,
            "finding_count": 0,
        }

        max_total = float('-inf')
        for row in rows:
            result["hypothesis_totals"][row['hypothesis_id']] = {
                "total": row['total'],
                "count": row['count'],
                "average": round(row['avg'], 2)
            }
            result["finding_count"] = max(result["finding_count"], row['count'])
            if row['total'] > max_total:
                max_total = row['total']
                result["dominant_hypothesis"] = row['hypothesis_id']

        return result

    def get_key_assumptions(self, theory_name: str) -> list:
        """CIA Key Assumptions Check: identify assumptions that, if wrong,
        would change the dominant hypothesis.
        
        Returns list of critical assumptions underlying the current assessment.
        """
        aggregated = self.aggregate_theory_scores(theory_name)
        dominant = aggregated.get("dominant_hypothesis")

        if not dominant or not self.bedrock:
            return ["Insufficient data for key assumptions check"]

        # Use Bedrock to identify critical assumptions
        try:
            prompt = f"""Given that the dominant hypothesis for the "{theory_name}" investigation is "{dominant}" 
(meaning: {next((h.description for h in DEFAULT_HYPOTHESES if h.hypothesis_id == dominant), 'unknown')}),
identify the 3-5 KEY ASSUMPTIONS that, if proven wrong, would change the dominant hypothesis.

Format as a JSON array of strings, each being one assumption."""

            response = self.bedrock.invoke_model(
                modelId="anthropic.claude-sonnet-4-20250514-v1:0",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 300,
                    "messages": [{"role": "user", "content": prompt}]
                }),
                contentType="application/json",
                accept="application/json"
            )

            result = json.loads(response['body'].read())
            content = result['content'][0]['text']
            assumptions = json.loads(content)
            return assumptions if isinstance(assumptions, list) else [content]

        except Exception as e:
            return [f"Key assumptions check failed: {str(e)[:200]}"]
