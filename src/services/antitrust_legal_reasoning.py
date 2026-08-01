"""Antitrust legal reasoning service — Bedrock prompt management.

Provides the Antitrust_Legal_Persona and structured prompts for:
- Sherman Act section 1 per se violation analysis
- PCSF case precedent citation
- Prosecution assessment generation
- Sentencing guideline estimation
- Financial relationship assessment

Shared across all antitrust case types. Each module provides case-type-specific
context (evidence, patterns) and this service handles the Bedrock interaction.

Usage:
    legal = AntitrustLegalReasoning(bedrock_client)
    reasoning = legal.analyze_pattern(pattern, CaseType.PROCUREMENT_COLLUSION, evidence)
    assessment = legal.generate_prosecution_assessment(case_id, score, rings, red_flags)
"""

from __future__ import annotations

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Default model for legal reasoning (Amazon Nova Pro — no government restrictions)
DEFAULT_MODEL_ID = "amazon.nova-pro-v1:0"

# Persona prompts by case type
PERSONA_PROMPTS = {
    "procurement_collusion": """You are a senior DOJ Antitrust Division prosecutor with 20+ years of experience in procurement fraud and bid-rigging cases. You have deep expertise in:

- Sherman Act section 1 per se violations (horizontal price-fixing, bid-rigging, market allocation)
- Procurement Collusion Strike Force (PCSF) framework and red flag taxonomy
- Federal sentencing guidelines for antitrust offenses (USSG section 2R1.1)
- Key precedents: United States v. Socony-Vacuum, United States v. Topco Associates, Leegin Creative Leather Products v. PSKS

When analyzing evidence, you:
1. Identify which elements of a Sherman Act section 1 violation are satisfied
2. Cite specific bid data and statistical patterns as evidence
3. Reference applicable PCSF red flag categories
4. Assess the strength of circumstantial vs. direct evidence
5. Identify evidence gaps that need to be filled for prosecution
6. Recommend investigative steps to strengthen the case

Always reason conservatively — flag uncertainty and distinguish between strong evidence and mere suspicion.""",

    "merger_review": """You are a senior DOJ Antitrust Division attorney specializing in merger review under Clayton Act section 7 and the 2023 Merger Guidelines. You have expertise in market definition, HHI analysis, unilateral and coordinated effects, and divestiture remedies.""",

    "price_fixing": """You are a senior DOJ Antitrust Division prosecutor specializing in horizontal price-fixing conspiracies under Sherman Act section 1. You have expertise in parallel pricing analysis, plus factors, econometric damage modeling, and the Twombly plausibility standard.""",

    "market_allocation": """You are a senior DOJ Antitrust Division prosecutor specializing in market allocation agreements under Sherman Act section 1. You have expertise in geographic and customer division schemes, per se analysis, and territorial restriction cases.""",

    "monopolization": """You are a senior DOJ Antitrust Division attorney specializing in Section 2 monopolization cases. You have expertise in market definition (SSNIP test), market power assessment, exclusionary conduct analysis, and the distinction between competitive harm and competitor harm.""",

    "criminal_cartel": """You are a senior DOJ Antitrust Division criminal prosecutor. You have expertise in Sherman Act section 1 criminal cases, Title III wiretap evidence, leniency program administration, grand jury proceedings, and federal sentencing guidelines for antitrust offenses (USSG section 2R1.1).""",
}


class AntitrustLegalReasoning:
    """Bedrock prompt management for antitrust legal analysis.

    Provides structured prompts and invokes Amazon Bedrock to generate
    legal reasoning for detected antitrust patterns.
    """

    def __init__(
        self,
        bedrock_client=None,
        model_id: str = DEFAULT_MODEL_ID,
    ) -> None:
        """Initialize legal reasoning service.

        Args:
            bedrock_client: boto3 Bedrock Runtime client.
            model_id: Bedrock model ID for inference.
        """
        self.bedrock_client = bedrock_client
        self.model_id = model_id

    def get_persona_prompt(self, case_type: str) -> str:
        """Return the system prompt for the antitrust legal persona.

        Args:
            case_type: One of the CaseType enum values.

        Returns:
            System prompt string for the legal persona.
        """
        return PERSONA_PROMPTS.get(case_type, PERSONA_PROMPTS["procurement_collusion"])

    def analyze_pattern(
        self,
        pattern: dict,
        case_type: str,
        evidence: list[dict],
    ) -> str:
        """Generate legal reasoning for a detected pattern.

        Args:
            pattern: Dict describing the detected pattern (type, confidence,
                involved vendors/contracts, statistical details).
            case_type: The antitrust case type for persona selection.
            evidence: List of supporting evidence items.

        Returns:
            Legal reasoning text explaining how the pattern constitutes
            evidence of an antitrust violation.
        """
        system_prompt = self.get_persona_prompt(case_type)

        user_prompt = f"""Analyze the following detected pattern and provide legal reasoning explaining how it constitutes evidence of an antitrust violation.

DETECTED PATTERN:
- Type: {pattern.get('pattern_type', 'unknown')}
- Confidence: {pattern.get('confidence', 0)}%
- Involved Vendors: {json.dumps(pattern.get('involved_vendors', []))}
- Involved Contracts: {json.dumps(pattern.get('involved_contracts', []))}
- Statistical Details: {json.dumps(pattern.get('details', {}))}

SUPPORTING EVIDENCE ({len(evidence)} items):
{json.dumps(evidence[:10], indent=2)}

Provide your analysis in the following structure:
1. LEGAL FRAMEWORK: Which statute and legal standard applies
2. ELEMENTS SATISFIED: Which elements of the offense this evidence supports
3. EVIDENCE STRENGTH: Assessment of the evidence quality (direct vs. circumstantial)
4. PCSF RED FLAGS: Which PCSF taxonomy categories are triggered
5. GAPS: What additional evidence would strengthen the case
6. RECOMMENDATION: Recommended next investigative steps"""

        return self._invoke_bedrock(system_prompt, user_prompt)

    def generate_prosecution_assessment(
        self,
        case_id: str,
        score: dict,
        rings: list[dict],
        red_flags: list[dict],
    ) -> dict:
        """Generate full prosecution assessment.

        Args:
            case_id: Investigation identifier.
            score: ScoringResult as dict (overall_score, factors, severity).
            rings: List of identified collusion rings.
            red_flags: List of detected red flags.

        Returns:
            Dict with keys: elements_satisfied, evidence_gaps, recommended_steps,
            case_strength, sentencing_estimate, prosecution_timeline.
        """
        system_prompt = self.get_persona_prompt("procurement_collusion")

        user_prompt = f"""Generate a comprehensive prosecution assessment for this antitrust investigation.

INVESTIGATION: {case_id}
PCSF SCORE: {score.get('overall_score', 0)}/100 (Severity: {score.get('severity', 'Unknown')})

SCORE BREAKDOWN:
{json.dumps(score.get('factors', []), indent=2)}

IDENTIFIED COLLUSION RINGS ({len(rings)}):
{json.dumps(rings[:5], indent=2)}

RED FLAGS ({len(red_flags)} total, showing Critical/High):
{json.dumps([rf for rf in red_flags if rf.get('severity') in ('Critical', 'High')][:10], indent=2)}

Provide your assessment as a JSON object with these keys:
- "elements_satisfied": list of Sherman Act section 1 elements with evidence citations
- "evidence_gaps": list of missing evidence needed for prosecution
- "recommended_steps": list of investigative actions to fill gaps
- "case_strength": "strong" or "moderate" or "weak" with explanation
- "sentencing_estimate": estimated penalties based on USSG section 2R1.1
- "prosecution_timeline": estimated timeline to indictment-ready

Respond ONLY with the JSON object."""

        response_text = self._invoke_bedrock(system_prompt, user_prompt)

        # Parse JSON response
        try:
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = response_text.strip()
            return json.loads(json_str)
        except (json.JSONDecodeError, IndexError):
            logger.warning("Failed to parse prosecution assessment JSON, returning raw text")
            return {
                "elements_satisfied": [],
                "evidence_gaps": [],
                "recommended_steps": [],
                "case_strength": "unknown",
                "sentencing_estimate": "",
                "prosecution_timeline": "",
                "raw_reasoning": response_text,
            }

    def assess_financial_relationship(
        self,
        vendor_pair: dict,
        flows: list[dict],
    ) -> str:
        """Assess whether financial flows constitute Sherman Act section 1 evidence.

        Args:
            vendor_pair: Dict with vendor_a and vendor_b info.
            flows: List of financial flow records between the vendors.

        Returns:
            Legal assessment text.
        """
        system_prompt = self.get_persona_prompt("procurement_collusion")

        user_prompt = f"""Assess whether the following financial relationship between competing vendors constitutes evidence of an agreement in restraint of trade under Sherman Act section 1.

VENDOR A: {json.dumps(vendor_pair.get('vendor_a', {}))}
VENDOR B: {json.dumps(vendor_pair.get('vendor_b', {}))}

FINANCIAL FLOWS ({len(flows)} transactions):
{json.dumps(flows[:20], indent=2)}

Consider:
1. Are these vendors competitors (bidding on same contracts)?
2. Is the financial relationship consistent with legitimate business (genuine subcontracting) or suspicious (kickbacks, profit-sharing)?
3. Is there reciprocity (A pays B on A's wins, B pays A on B's wins)?
4. Does the timing correlate with contract awards?
5. What is the legal significance under Sherman Act section 1?

Provide a concise assessment (3-5 paragraphs) with your conclusion on whether this constitutes evidence of collusion."""

        return self._invoke_bedrock(system_prompt, user_prompt)

    def _invoke_bedrock(self, system_prompt: str, user_prompt: str) -> str:
        """Invoke Bedrock with the given prompts.

        Args:
            system_prompt: System/persona prompt.
            user_prompt: User message with analysis request.

        Returns:
            Model response text. Returns placeholder if client unavailable.
        """
        if not self.bedrock_client:
            logger.warning("Bedrock client not configured — returning placeholder")
            return "[Legal reasoning unavailable — Bedrock client not configured]"

        try:
            # Build request body — supports both Nova and Anthropic formats
            if "nova" in self.model_id.lower():
                request_body = {
                    "messages": [
                        {"role": "user", "content": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}
                    ],
                    "inferenceConfig": {"maxTokens": 4096, "temperature": 0.2},
                }
            else:
                request_body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4096,
                    "system": system_prompt,
                    "messages": [
                        {"role": "user", "content": user_prompt}
                    ],
                }

            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(request_body),
            )

            response_body = json.loads(response["body"].read())

            # Parse response — handle both Nova and Anthropic formats
            if "output" in response_body:
                # Nova format
                message = response_body.get("output", {}).get("message", {})
                content = message.get("content", [])
                if content and isinstance(content, list):
                    return content[0].get("text", "")
            else:
                # Anthropic format
                content = response_body.get("content", [])
                if content and isinstance(content, list):
                    return content[0].get("text", "")
            return str(response_body)

        except Exception as e:
            logger.error(f"Bedrock invocation failed: {e}")
            return f"[Legal reasoning generation failed: {str(e)}]"
