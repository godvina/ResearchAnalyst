"""Case Type Classifier — AI-powered antitrust case type classification.

Classifies incoming pre-case leads into one of six antitrust case types using
Amazon Nova Pro with the Antitrust_Legal_Persona. Produces a ClassificationResult
with confidence scoring, legal reasoning, and alternative classifications.

Each classification is stored as an AI_Proposed decision in Aurora for the
Decision_Workflow (human-in-the-loop confirmation before downstream actions).

Usage:
    classifier = CaseTypeClassifier(
        bedrock_client=bedrock_runtime,
        aurora_cm=connection_manager,
    )
    result = classifier.classify("Tip: multiple vendors submitting identical bids...")
    result = classifier.reclassify("lead-uuid", "New evidence: subcontracting flows...")
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Amazon Nova Pro — GovCloud-available, platform standard
MODEL_ID = "amazon.nova-pro-v1:0"

# Valid antitrust case types
CASE_TYPES = [
    "procurement_collusion",
    "price_fixing",
    "market_allocation",
    "merger_review",
    "monopolization",
    "criminal_cartel",
]


@dataclass
class ClassificationResult:
    """Output of the CaseTypeClassifier.

    Attributes:
        case_type: Exactly one primary case type from CASE_TYPES.
        confidence: Score in [0, 100].
        reasoning: Non-empty explanation citing elements from the lead.
        alternatives: Present iff confidence < 80; up to two alternative types with scores.
        manual_review: True iff confidence < 60.
        classification_id: UUID for this classification record.
    """

    case_type: str
    confidence: int
    reasoning: str
    alternatives: Optional[list[dict]] = None
    manual_review: bool = False
    classification_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class CaseTypeClassifier:
    """Classifies pre-case leads into antitrust case types via Amazon Nova Pro.

    Follows Protocol/constructor-injection pattern for testability.
    """

    CASE_TYPES = CASE_TYPES

    def __init__(self, bedrock_client: Any, aurora_cm: Any) -> None:
        """Initialize classifier with dependencies.

        Args:
            bedrock_client: boto3 Bedrock Runtime client for invoke_model.
            aurora_cm: Aurora PostgreSQL connection manager with cursor() context manager.
        """
        self.bedrock_client = bedrock_client
        self.aurora_cm = aurora_cm
        self.model_id = MODEL_ID

    def classify(
        self, lead_content: str, lead_format: str = "free_text"
    ) -> ClassificationResult:
        """Classify a lead into an antitrust case type.

        Args:
            lead_content: The lead text (tip, JSON, news extract, anomaly report).
            lead_format: One of free_text, json, news_url, anomaly_report.

        Returns:
            ClassificationResult with case_type, confidence, reasoning, etc.
        """
        prompt = self._build_classification_prompt(lead_content, lead_format)
        raw_response = self._invoke_bedrock(prompt)
        result = self._parse_classification_response(raw_response)

        # Store classification in Aurora as AI_Proposed decision
        self._store_classification(result, lead_content)

        return result

    def reclassify(
        self, lead_id: str, additional_evidence: str
    ) -> ClassificationResult:
        """Reclassify a lead with additional evidence appended.

        Retrieves the original lead content from Aurora, appends the new
        evidence, and re-runs classification.

        Args:
            lead_id: UUID of the existing lead.
            additional_evidence: New evidence text to incorporate.

        Returns:
            Updated ClassificationResult (may change the primary case_type).
        """
        # Retrieve original lead content
        original_content = self._get_lead_content(lead_id)

        combined_content = (
            f"{original_content}\n\n"
            f"--- ADDITIONAL EVIDENCE ---\n{additional_evidence}"
        )

        prompt = self._build_classification_prompt(combined_content, "free_text")
        raw_response = self._invoke_bedrock(prompt)
        result = self._parse_classification_response(raw_response)

        # Store updated classification linked to the lead
        self._store_classification(result, combined_content, lead_id=lead_id)

        return result

    def _build_classification_prompt(self, content: str, format_type: str) -> str:
        """Build the classification prompt with Antitrust_Legal_Persona.

        Args:
            content: Lead content to classify.
            format_type: Input format descriptor.

        Returns:
            Complete prompt string for Bedrock invocation.
        """
        format_instructions = {
            "free_text": "The following is a free-text tip or whistleblower narrative.",
            "json": "The following is structured JSON from automated anomaly detection.",
            "news_url": "The following is extracted text from a news article.",
            "anomaly_report": "The following is a statistical anomaly report from Redshift queries.",
        }

        format_desc = format_instructions.get(
            format_type, format_instructions["free_text"]
        )

        prompt = f"""{format_desc}

Analyze this lead and classify it into exactly ONE primary antitrust case type.

VALID CASE TYPES:
1. procurement_collusion — Bid-rigging, complementary bidding, bid rotation, bid suppression in government procurement
2. price_fixing — Horizontal agreements to fix, raise, or stabilize prices among competitors
3. market_allocation — Agreements to divide markets by geography, customer, or product line
4. merger_review — Potentially anticompetitive mergers or acquisitions under Clayton Act Section 7
5. monopolization — Exclusionary conduct by a dominant firm under Sherman Act Section 2
6. criminal_cartel — Criminal conspiracy involving hardcore cartel conduct (often international)

LEAD CONTENT:
{content}

Respond with a JSON object containing:
- "case_type": exactly one value from the valid case types list above
- "confidence": integer 0-100 representing your confidence in this classification
- "reasoning": detailed explanation citing specific elements from the lead that support this classification
- "alternatives": if confidence < 80, include up to 2 alternative case types with their confidence scores as [{{"case_type": "...", "confidence": N}}]; if confidence >= 80, set to null

Respond ONLY with the JSON object, no additional text."""

        return prompt

    def _parse_classification_response(self, response: dict) -> ClassificationResult:
        """Parse and validate the Bedrock response into a ClassificationResult.

        Enforces:
        - Exactly one case_type from CASE_TYPES
        - Confidence in [0, 100]
        - Non-empty reasoning
        - Alternatives present iff confidence < 80
        - manual_review flag iff confidence < 60

        Args:
            response: Parsed response dict from Bedrock.

        Returns:
            Validated ClassificationResult.
        """
        # Extract case_type
        case_type = response.get("case_type", "")
        if case_type not in CASE_TYPES:
            logger.warning(
                f"Invalid case_type '{case_type}' from model, defaulting to procurement_collusion"
            )
            case_type = "procurement_collusion"

        # Extract and clamp confidence
        confidence = response.get("confidence", 50)
        if not isinstance(confidence, (int, float)):
            confidence = 50
        confidence = int(max(0, min(100, confidence)))

        # Extract reasoning — must be non-empty
        reasoning = response.get("reasoning", "")
        if not reasoning or not reasoning.strip():
            reasoning = "Classification based on lead content analysis."

        # Handle alternatives based on confidence threshold
        alternatives = response.get("alternatives")
        if confidence < 80:
            # Alternatives MUST be present when confidence < 80
            if not alternatives or not isinstance(alternatives, list):
                alternatives = []
            # Validate each alternative
            valid_alternatives = []
            for alt in alternatives[:2]:
                if isinstance(alt, dict) and alt.get("case_type") in CASE_TYPES:
                    alt_conf = int(max(0, min(100, alt.get("confidence", 0))))
                    valid_alternatives.append(
                        {"case_type": alt["case_type"], "confidence": alt_conf}
                    )
            alternatives = valid_alternatives if valid_alternatives else [
                {"case_type": t, "confidence": 0}
                for t in CASE_TYPES if t != case_type
            ][:2]
        else:
            # Alternatives MUST NOT be present when confidence >= 80
            alternatives = None

        # Set manual_review flag iff confidence < 60
        manual_review = confidence < 60

        return ClassificationResult(
            case_type=case_type,
            confidence=confidence,
            reasoning=reasoning,
            alternatives=alternatives,
            manual_review=manual_review,
        )

    def _invoke_bedrock(self, user_prompt: str) -> dict:
        """Invoke Amazon Nova Pro via Bedrock and return parsed JSON response.

        Args:
            user_prompt: The classification prompt.

        Returns:
            Parsed dict from model response.
        """
        system_prompt = (
            "You are a senior DOJ Antitrust Division prosecutor with 20+ years of "
            "experience across all antitrust case types. You have deep expertise in "
            "Sherman Act sections 1 and 2, Clayton Act section 7, FTC Act section 5, "
            "and federal sentencing guidelines for antitrust offenses. You classify "
            "incoming leads into the appropriate antitrust case type with precision, "
            "citing specific legal elements and factual indicators that support your "
            "classification. You reason conservatively and flag uncertainty."
        )

        if not self.bedrock_client:
            logger.warning("Bedrock client not configured — returning default classification")
            return {
                "case_type": "procurement_collusion",
                "confidence": 50,
                "reasoning": "Bedrock client not configured — default classification applied.",
                "alternatives": [
                    {"case_type": "price_fixing", "confidence": 30},
                    {"case_type": "criminal_cartel", "confidence": 20},
                ],
            }

        try:
            # Nova format request body
            request_body = {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"text": f"{system_prompt}\n\n{user_prompt}"}
                        ],
                    }
                ],
                "inferenceConfig": {"maxTokens": 4096, "temperature": 0.2},
            }

            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(request_body),
            )

            response_body = json.loads(response["body"].read())

            # Parse Nova format response
            message = response_body.get("output", {}).get("message", {})
            content = message.get("content", [])
            if content and isinstance(content, list):
                text = content[0].get("text", "")
            else:
                text = str(response_body)

            # Extract JSON from response text
            return self._extract_json(text)

        except Exception as e:
            logger.error(f"Bedrock invocation failed: {e}")
            return {
                "case_type": "procurement_collusion",
                "confidence": 50,
                "reasoning": f"Classification failed ({str(e)}), default applied.",
                "alternatives": [
                    {"case_type": "price_fixing", "confidence": 30},
                ],
            }

    def _extract_json(self, text: str) -> dict:
        """Extract JSON object from model response text.

        Handles responses wrapped in markdown code blocks.

        Args:
            text: Raw model response text.

        Returns:
            Parsed dict.
        """
        try:
            if "```json" in text:
                json_str = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                json_str = text.split("```")[1].split("```")[0].strip()
            else:
                json_str = text.strip()
            return json.loads(json_str)
        except (json.JSONDecodeError, IndexError) as e:
            logger.warning(f"Failed to parse classification JSON: {e}")
            return {
                "case_type": "procurement_collusion",
                "confidence": 50,
                "reasoning": "Failed to parse model response, default applied.",
                "alternatives": [
                    {"case_type": "price_fixing", "confidence": 30},
                ],
            }

    def _store_classification(
        self,
        result: ClassificationResult,
        content: str,
        lead_id: Optional[str] = None,
    ) -> None:
        """Store classification result in Aurora pre_case_classifications table.

        Creates an AI_Proposed decision record.

        Args:
            result: The ClassificationResult to store.
            content: Original content used for input_hash.
            lead_id: Optional lead_id to associate with.
        """
        input_hash = hashlib.sha256(content.encode()).hexdigest()[:32]

        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO pre_case_classifications
                        (classification_id, lead_id, case_type, confidence,
                         reasoning, alternatives, model_version, input_hash,
                         decision_status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        result.classification_id,
                        lead_id,
                        result.case_type,
                        result.confidence,
                        result.reasoning,
                        json.dumps(result.alternatives) if result.alternatives else None,
                        self.model_id,
                        input_hash,
                        "ai_proposed",
                    ),
                )
        except Exception as e:
            logger.error(f"Failed to store classification: {e}")

    def _get_lead_content(self, lead_id: str) -> str:
        """Retrieve original lead content from Aurora.

        Args:
            lead_id: UUID of the lead.

        Returns:
            Lead source_content as string.
        """
        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    "SELECT source_content FROM pre_case_leads WHERE lead_id = %s",
                    (lead_id,),
                )
                row = cur.fetchone()
                if row:
                    content = row[0]
                    if isinstance(content, dict):
                        return json.dumps(content)
                    return str(content)
        except Exception as e:
            logger.error(f"Failed to retrieve lead content for {lead_id}: {e}")

        return ""
