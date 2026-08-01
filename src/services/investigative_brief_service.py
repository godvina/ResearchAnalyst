"""Investigative Brief Service — AI-generated intelligence briefs for antitrust leads.

Uses Amazon Bedrock (Nova Pro) to synthesize OSINT data, classification results,
and prosecution assessments into actionable investigative intelligence briefs.

This is a single-lead analysis service (not bulk). Each call generates one brief
for one lead, suitable for investigator review.
"""

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class InvestigativeBriefService:
    """Generates AI investigative intelligence briefs from pre-case lead data."""

    MODEL_ID = "amazon.nova-pro-v1:0"

    def __init__(self, bedrock_client: Any) -> None:
        self.bedrock_client = bedrock_client

    def generate_brief(
        self,
        lead_data: dict,
        osint_data: list,
        classification: Optional[dict] = None,
        assessment: Optional[dict] = None,
    ) -> dict:
        """Generate an investigative intelligence brief for a single lead.

        Args:
            lead_data: Dict with title, summary, source_content (subjects, industry,
                       alleged_conduct, geographic_scope, etc.)
            osint_data: List of OSINT source results with extracted_entities.
            classification: Classification result dict (case_type, confidence, reasoning).
            assessment: Prosecution readiness assessment dict (score, evidence_matrix, gaps).

        Returns:
            Dict with sections: executive_summary, key_findings, red_flags,
            evidence_gaps, recommended_next_steps. On error, returns brief_unavailable message.
        """
        try:
            prompt = self._build_prompt(lead_data, osint_data, classification, assessment)
            response = self._invoke_bedrock(prompt)
            brief = self._parse_response(response)
            return brief
        except Exception as exc:
            logger.exception("Failed to generate investigative brief")
            return {
                "brief_unavailable": True,
                "error_message": f"Brief generation failed: {str(exc)}",
                "executive_summary": "The AI investigative brief is temporarily unavailable. Please review the raw OSINT data and assessment scores manually.",
                "key_findings": [],
                "red_flags": [],
                "evidence_gaps": [],
                "recommended_next_steps": [],
            }

    def _build_prompt(
        self,
        lead_data: dict,
        osint_data: list,
        classification: Optional[dict],
        assessment: Optional[dict],
    ) -> str:
        """Construct the Bedrock prompt for brief generation."""
        # Extract source_content fields
        source_content = lead_data.get("source_content", {})
        if isinstance(source_content, str):
            try:
                source_content = json.loads(source_content)
            except (json.JSONDecodeError, TypeError):
                source_content = {}

        subjects = source_content.get("subjects", [])
        industry = source_content.get("industry", "Unknown")
        alleged_conduct = source_content.get("alleged_conduct", "Not specified")
        geographic_scope = source_content.get("geographic_scope", "Not specified")
        estimated_harm = source_content.get("estimated_harm", "Not quantified")
        mechanism = source_content.get("mechanism", "")
        affected_parties = source_content.get("affected_parties", "")

        # Format OSINT sources summary
        osint_summary = self._format_osint_for_prompt(osint_data)

        # Format classification
        classification_text = "Not yet classified"
        if classification:
            classification_text = (
                f"Case Type: {classification.get('case_type', 'Unknown')}\n"
                f"Confidence: {classification.get('confidence', 0)}%\n"
                f"Reasoning: {classification.get('reasoning', '')}"
            )

        # Format assessment
        assessment_text = "No assessment completed"
        if assessment:
            score = assessment.get("overall_score", assessment.get("pre_assessment_score", 0))
            assessment_text = f"Prosecution Readiness Score: {score}/100\n"
            if assessment.get("scoring_components"):
                comps = assessment["scoring_components"]
                assessment_text += (
                    f"  - Elements Satisfied: {comps.get('elements_satisfied', 0)}/100\n"
                    f"  - Evidence Quality: {comps.get('evidence_quality', 0)}/100\n"
                    f"  - Corroboration: {comps.get('corroboration', 0)}/100\n"
                    f"  - Pattern Strength: {comps.get('pattern_strength', 0)}/100\n"
                )
            if assessment.get("evidence_gaps"):
                assessment_text += "Evidence Gaps Identified:\n"
                for gap in assessment["evidence_gaps"]:
                    gap_desc = gap.get("element", gap.get("description", ""))
                    gap_action = gap.get("recommended_action", gap.get("action", ""))
                    assessment_text += f"  - {gap_desc}: {gap_action}\n"
            if assessment.get("legal_reasoning"):
                assessment_text += f"Legal Reasoning: {assessment['legal_reasoning']}\n"

        subjects_str = ", ".join(subjects) if subjects else "Unknown subjects"

        prompt = f"""You are a senior DOJ Antitrust Division investigator preparing an intelligence brief for a pre-case lead. Your analysis must be precise, actionable, and grounded in the evidence gathered through OSINT sources.

LEAD INFORMATION:
Title: {lead_data.get('title', 'Untitled Lead')}
Summary: {lead_data.get('summary', '')}
Subjects Under Investigation: {subjects_str}
Industry: {industry}
Alleged Conduct: {alleged_conduct}
Geographic Scope: {geographic_scope}
Estimated Economic Harm: {estimated_harm}
Mechanism: {mechanism}
Affected Parties: {affected_parties}

CLASSIFICATION:
{classification_text}

OSINT INTELLIGENCE GATHERED:
{osint_summary}

PROSECUTION READINESS ASSESSMENT:
{assessment_text}

Based on the above intelligence, produce a structured investigative brief with the following sections. Be specific — reference the actual subjects ({subjects_str}), the industry ({industry}), and the alleged conduct ({alleged_conduct}).

1. EXECUTIVE SUMMARY (2-3 paragraphs synthesizing what the investigation has uncovered so far, the strength of the case, and the most critical next steps)

2. KEY FINDINGS (5-8 bullet points of specific investigative findings derived from the OSINT data — what was actually discovered about the subjects, their relationships, financial patterns, or market behavior)

3. RED FLAGS (3-6 indicators of anticompetitive behavior identified in the data — be specific about which subjects and what behavior patterns suggest violations of Sherman Act section 1 or section 2, Clayton Act, or FTC Act)

4. EVIDENCE GAPS (3-5 items identifying what critical evidence is missing and what investigative steps would fill those gaps — reference specific document types, witness categories, or data sources)

5. RECOMMENDED NEXT STEPS (4-6 specific actionable items: identify subpoena targets by name, CID (Civil Investigative Demand) recipients, potential cooperating witnesses, market studies needed, or economic analyses required)

Format your response as JSON with these exact keys:
{{
  "executive_summary": "paragraph text...",
  "key_findings": ["finding 1", "finding 2", ...],
  "red_flags": [{{"indicator": "...", "severity": "high|medium|low", "subjects_involved": ["..."], "evidence_basis": "..."}}],
  "evidence_gaps": [{{"gap": "...", "criticality": "high|medium|low", "recommended_action": "..."}}],
  "recommended_next_steps": [{{"action": "...", "target": "...", "priority": "immediate|short_term|medium_term", "rationale": "..."}}]
}}"""

        return prompt

    def _format_osint_for_prompt(self, osint_data: list) -> str:
        """Format OSINT data into a readable summary for the prompt."""
        if not osint_data:
            return "No OSINT data gathered yet."

        lines = []
        for src in osint_data:
            source_name = (src.get("source_name", "unknown")).replace("_", " ").upper()
            reliability = src.get("reliability_rating", "unknown")
            entities = src.get("extracted_entities", [])
            if isinstance(entities, str):
                try:
                    entities = json.loads(entities)
                except (json.JSONDecodeError, TypeError):
                    entities = []

            lines.append(f"Source: {source_name} (Reliability: {reliability})")
            if entities:
                for ent in entities[:10]:  # Cap at 10 entities per source
                    name = ent.get("name", ent.get("entity_name", ""))
                    query_type = ent.get("query_type", "")
                    findings = ent.get("findings_summary", ent.get("result_summary", ""))
                    if name:
                        line = f"  - Entity: {name}"
                        if query_type:
                            line += f" | Query: {query_type}"
                        if findings:
                            line += f" | Findings: {findings}"
                        lines.append(line)
            lines.append("")

        return "\n".join(lines) if lines else "No OSINT data gathered yet."

    def _invoke_bedrock(self, prompt: str) -> str:
        """Call Bedrock Nova Pro with the constructed prompt."""
        response = self.bedrock_client.converse(
            modelId=self.MODEL_ID,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                }
            ],
            inferenceConfig={
                "maxTokens": 4096,
                "temperature": 0.3,
                "topP": 0.9,
            },
        )

        # Extract text from response
        output = response.get("output", {})
        message = output.get("message", {})
        content_blocks = message.get("content", [])

        text_parts = []
        for block in content_blocks:
            if "text" in block:
                text_parts.append(block["text"])

        return "\n".join(text_parts)

    def _parse_response(self, response_text: str) -> dict:
        """Parse the Bedrock response into structured brief sections."""
        # Try to extract JSON from the response
        try:
            # Look for JSON block in the response
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                parsed = json.loads(json_str)

                # Validate expected keys exist
                return {
                    "executive_summary": parsed.get("executive_summary", ""),
                    "key_findings": parsed.get("key_findings", []),
                    "red_flags": parsed.get("red_flags", []),
                    "evidence_gaps": parsed.get("evidence_gaps", []),
                    "recommended_next_steps": parsed.get("recommended_next_steps", []),
                    "brief_unavailable": False,
                }
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback: parse as plain text sections
        return self._parse_plain_text_response(response_text)

    def _parse_plain_text_response(self, text: str) -> dict:
        """Fallback parser for non-JSON responses."""
        sections = {
            "executive_summary": "",
            "key_findings": [],
            "red_flags": [],
            "evidence_gaps": [],
            "recommended_next_steps": [],
            "brief_unavailable": False,
        }

        # Simple section extraction by headers
        current_section = "executive_summary"
        current_content = []

        for line in text.split("\n"):
            line_lower = line.lower().strip()
            if "executive summary" in line_lower:
                current_section = "executive_summary"
                current_content = []
            elif "key findings" in line_lower:
                if current_content:
                    sections["executive_summary"] = "\n".join(current_content).strip()
                current_section = "key_findings"
                current_content = []
            elif "red flag" in line_lower:
                if current_section == "key_findings":
                    sections["key_findings"] = [l.strip().lstrip("•-* ") for l in current_content if l.strip()]
                current_section = "red_flags"
                current_content = []
            elif "evidence gap" in line_lower:
                if current_section == "red_flags":
                    sections["red_flags"] = [{"indicator": l.strip().lstrip("•-* "), "severity": "medium", "subjects_involved": [], "evidence_basis": ""} for l in current_content if l.strip()]
                current_section = "evidence_gaps"
                current_content = []
            elif "next step" in line_lower or "recommended" in line_lower:
                if current_section == "evidence_gaps":
                    sections["evidence_gaps"] = [{"gap": l.strip().lstrip("•-* "), "criticality": "medium", "recommended_action": ""} for l in current_content if l.strip()]
                current_section = "recommended_next_steps"
                current_content = []
            else:
                if line.strip():
                    current_content.append(line)

        # Capture last section
        if current_section == "recommended_next_steps" and current_content:
            sections["recommended_next_steps"] = [{"action": l.strip().lstrip("•-* "), "target": "", "priority": "short_term", "rationale": ""} for l in current_content if l.strip()]
        elif current_section == "executive_summary" and current_content:
            sections["executive_summary"] = "\n".join(current_content).strip()

        return sections
