"""Image Description Service — pure functions for AI image description pipeline.

Provides trigger filtering, prompt building, entity extraction, artifact
construction, and Bedrock response parsing for the image description handler.
"""

import logging
import re

logger = logging.getLogger(__name__)

# Default Bedrock model for image description
DEFAULT_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"

# Haiku pricing per 1K tokens (approximate)
_HAIKU_INPUT_PRICE_PER_1K = 0.00025
_HAIKU_OUTPUT_PRICE_PER_1K = 0.00125


def apply_trigger_filter(image_rek_map: dict, config: dict) -> list[dict]:
    """Select and prioritize images for description based on Rekognition results.

    Args:
        image_rek_map: Dict mapping image S3 keys to dicts with:
            - face_count (int): number of faces detected
            - labels_with_confidence (list[dict]): each has 'name' (str) and 'confidence' (float)
        config: The image_description config dict with keys:
            - describe_all_images (bool, default False)
            - min_rekognition_confidence (float, default 0.7)
            - max_images_per_run (int, default 50)

    Returns:
        List of dicts: {s3_key, face_count, labels, reason}
        Sorted by face_count desc, then investigative label count desc.
        Truncated to max_images_per_run.
    """
    describe_all = config.get("describe_all_images", False)
    min_confidence = config.get("min_rekognition_confidence", 0.7)
    max_images = config.get("max_images_per_run", 50)

    selected = []

    for s3_key, rek_data in image_rek_map.items():
        face_count = rek_data.get("face_count", 0)
        labels_with_conf = rek_data.get("labels_with_confidence", [])

        # Filter labels above confidence threshold
        qualifying_labels = [
            lbl["name"] for lbl in labels_with_conf
            if lbl.get("confidence", 0) >= min_confidence
        ]

        if describe_all:
            reason = "describe_all_images"
            selected.append({
                "s3_key": s3_key,
                "face_count": face_count,
                "labels": qualifying_labels,
                "reason": reason,
            })
        elif face_count >= 1:
            selected.append({
                "s3_key": s3_key,
                "face_count": face_count,
                "labels": qualifying_labels,
                "reason": "faces_detected",
            })
        elif len(qualifying_labels) >= 1:
            selected.append({
                "s3_key": s3_key,
                "face_count": face_count,
                "labels": qualifying_labels,
                "reason": "investigative_labels",
            })

    # Sort: face_count desc, then label count desc
    selected.sort(key=lambda x: (-x["face_count"], -len(x["labels"])))

    # Truncate to max_images_per_run
    if max_images and max_images > 0:
        selected = selected[:max_images]

    return selected


# ---------------------------------------------------------------------------
# Investigative Prompt
# ---------------------------------------------------------------------------

_DEFAULT_SYSTEM_PROMPT = (
    "You are an expert forensic image analyst assisting a criminal investigation. "
    "Your task is to provide a detailed, factual description of the image. "
    "Report only observable facts. Do not make speculative conclusions or legal judgments."
)

_DEFAULT_INVESTIGATIVE_PROMPT_TEMPLATE = """Analyze this image and describe the following in order:

(a) PEOPLE: Count of individuals visible, apparent age ranges, gender, physical descriptions, and interactions between individuals. Note when any individual appears to be a minor based on physical appearance.

(b) SETTING: Indoor or outdoor, type of location, identifiable landmarks or signage.

(c) OBJECTS OF INTEREST: Weapons, drugs, currency, documents, electronics, vehicles, luxury items, or any other objects of investigative relevance.

(d) ACTIVITIES: What people are doing, body language, and interactions.

(e) INVESTIGATIVE OBSERVATIONS: Anything unusual, potentially illegal, or relevant to trafficking, financial crime, or organized crime investigations.

Report only observable facts. Avoid speculative conclusions or legal judgments. Note when individuals appear to be minors based on physical appearance.

Rekognition context for this image:
- Faces detected: {face_count}
- Labels detected: {labels}

Use the Rekognition context above to confirm or refine your observations."""


def build_investigative_prompt(rek_context: dict, custom_prompt: str | None = None) -> str:
    """Build the prompt to send alongside the image to Claude.

    Args:
        rek_context: Dict with 'face_count' (int) and 'labels' (list[str]).
        custom_prompt: Optional custom prompt override. When provided, the
            custom prompt is used with Rekognition context appended.

    Returns:
        The formatted prompt string.
    """
    face_count = rek_context.get("face_count", 0)
    labels = rek_context.get("labels", [])
    labels_str = ", ".join(labels) if labels else "none"

    if custom_prompt is not None:
        # Use custom prompt with Rekognition context appended
        rek_suffix = (
            f"\n\nRekognition context for this image:\n"
            f"- Faces detected: {face_count}\n"
            f"- Labels detected: {labels_str}"
        )
        return custom_prompt + rek_suffix

    return _DEFAULT_INVESTIGATIVE_PROMPT_TEMPLATE.format(
        face_count=face_count,
        labels=labels_str,
    )


def get_system_prompt() -> str:
    """Return the system prompt for investigative image analysis."""
    return _DEFAULT_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Entity Mention Extraction
# ---------------------------------------------------------------------------


def extract_mentioned_entities(description: str, entity_names: list[str]) -> list[str]:
    """Find entity names mentioned in a description via case-insensitive substring match.

    For each entity name in *entity_names*, checks if it appears as a
    case-insensitive substring in *description*.

    Args:
        description: The image description text.
        entity_names: List of known entity names (original casing preserved).

    Returns:
        List of matched entity names in their original casing.
    """
    if not description or not entity_names:
        return []

    description_lower = description.lower()
    matched = []
    for name in entity_names:
        if name and name.lower() in description_lower:
            matched.append(name)
    return matched


# ---------------------------------------------------------------------------
# Description Artifact
# ---------------------------------------------------------------------------


def build_description_artifact(
    case_id: str,
    run_id: str,
    model_id: str,
    descriptions: list[dict],
    images_evaluated: int,
    images_skipped: int,
) -> dict:
    """Build the description artifact dict for S3 storage.

    Args:
        case_id: The case file ID.
        run_id: Unique run identifier (hex string).
        model_id: Bedrock model ID used.
        descriptions: List of description dicts, each with:
            image_s3_key, source_document_id, description,
            rekognition_context, mentioned_entities, model_id,
            input_tokens, output_tokens, duration_ms.
        images_evaluated: Total images evaluated by trigger filter.
        images_skipped: Images skipped by trigger filter.

    Returns:
        The artifact dict ready for JSON serialization.
    """
    total_input_tokens = sum(d.get("input_tokens", 0) for d in descriptions)
    total_output_tokens = sum(d.get("output_tokens", 0) for d in descriptions)
    total_duration_ms = sum(d.get("duration_ms", 0) for d in descriptions)

    # Estimate cost based on Haiku pricing
    estimated_cost = (
        (total_input_tokens / 1000) * _HAIKU_INPUT_PRICE_PER_1K
        + (total_output_tokens / 1000) * _HAIKU_OUTPUT_PRICE_PER_1K
    )

    return {
        "case_id": case_id,
        "run_id": run_id,
        "model_id": model_id,
        "descriptions": descriptions,
        "summary": {
            "images_evaluated": images_evaluated,
            "images_described": len(descriptions),
            "images_skipped": images_skipped,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "estimated_cost_usd": round(estimated_cost, 6),
            "total_duration_ms": total_duration_ms,
        },
    }


def get_artifact_s3_key(case_id: str, run_id: str) -> str:
    """Return the S3 key for a description artifact.

    Pattern: cases/{case_id}/image-description-artifacts/{run_id}_descriptions.json
    """
    return f"cases/{case_id}/image-description-artifacts/{run_id}_descriptions.json"


# ---------------------------------------------------------------------------
# Bedrock Response Parsing
# ---------------------------------------------------------------------------


def parse_bedrock_response(response_body: dict) -> str:
    """Extract description text from a Claude vision API response.

    Claude's response format:
        {"content": [{"type": "text", "text": "..."}], "usage": {...}}

    Args:
        response_body: Parsed JSON response from Bedrock invoke_model.

    Returns:
        The description text, or empty string if content block is missing.
    """
    try:
        content = response_body.get("content", [])
        if content and isinstance(content, list) and len(content) > 0:
            first_block = content[0]
            if isinstance(first_block, dict):
                return first_block.get("text", "")
        return ""
    except Exception:
        return ""
