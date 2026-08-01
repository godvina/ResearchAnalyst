"""Signature Matching Engine — Scores research findings against taxonomy patterns.

This is Step 2 in the pipeline: takes raw research findings from each grid node
and classifies them against the 18 investigation signatures. Uses Sonnet to
determine which signatures match each finding and at what confidence level.

The output feeds into Titan Embed (Step 3) — we embed the MATCHED SIGNATURE
vector_text alongside the finding, so similar findings cluster in vector space.
"""

import json
import logging
import os
from typing import Optional

import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)

SONNET_MODEL = os.environ.get("RESEARCH_MODEL_ID", "us.anthropic.claude-sonnet-4-6")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

# Load taxonomy signatures
_taxonomy_cache = None


def _load_taxonomy():
    global _taxonomy_cache
    if _taxonomy_cache is None:
        taxonomy_path = os.path.join(DATA_DIR, "grid-investigation-taxonomy.json")
        with open(taxonomy_path, encoding="utf-8") as f:
            _taxonomy_cache = json.load(f)
    return _taxonomy_cache


def _get_bedrock():
    return boto3.client(
        "bedrock-runtime", region_name="us-east-1",
        config=Config(read_timeout=60, connect_timeout=10, retries={"max_attempts": 2})
    )


def _build_signature_descriptions():
    """Build a compact description of all signatures for the classifier prompt."""
    taxonomy = _load_taxonomy()
    descriptions = []
    for method in taxonomy["methods"]:
        for sig in method["signatures"]:
            descriptions.append(
                f"  {sig['signature_id']}: {sig['description']} "
                f"[Indicators: {', '.join(sig['indicators'][:3])}]"
            )
    return "\n".join(descriptions)


CLASSIFIER_PROMPT = """You are a pattern recognition classifier for an archaeological investigation system.

Given a research finding about a specific location, determine which investigation signatures (if any) it matches.

AVAILABLE SIGNATURES:
{signatures}

RULES:
- A finding can match ZERO or MULTIPLE signatures
- Only mark a match if the finding provides SPECIFIC evidence matching the signature's indicators
- Confidence levels: "strong" (3+ indicators match), "moderate" (2 indicators), "weak" (1 indicator)
- If nothing matches, return empty matches array

Return ONLY valid JSON (no markdown):
{{"matches": [{{"signature_id": "am-gge-xxx-nnn", "confidence": "strong|moderate|weak", "matched_indicators": ["which specific indicators match"], "evidence_excerpt": "the specific text from the finding that supports this match"}}]}}"""


def score_finding(node_id: int, finding: dict) -> dict:
    """Score a single node's research finding against all taxonomy signatures.

    Args:
        node_id: The grid node ID
        finding: The research brief dict (from batch research)

    Returns:
        Dict with node_id, matched signatures, and embedding-ready text
    """
    if not finding or finding.get("error"):
        return {"node_id": node_id, "matches": [], "embedding_text": ""}

    # Build the finding text to classify
    finding_text = _extract_finding_text(finding)
    if not finding_text:
        return {"node_id": node_id, "matches": [], "embedding_text": ""}

    # Call Sonnet to classify
    sig_descriptions = _build_signature_descriptions()
    prompt = CLASSIFIER_PROMPT.format(signatures=sig_descriptions)

    user_msg = f"Node {node_id} research finding:\n{finding_text}"

    try:
        bedrock = _get_bedrock()
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 500,
            "system": prompt,
            "messages": [{"role": "user", "content": user_msg}],
            "temperature": 0.2,
        }
        resp = bedrock.invoke_model(
            modelId=SONNET_MODEL, contentType="application/json",
            accept="application/json", body=json.dumps(body)
        )
        resp_body = json.loads(resp["body"].read().decode())

        # Extract text from response
        text = ""
        for block in resp_body.get("content", []):
            if block.get("type") == "text":
                text = block.get("text", "")
                break
        if not text:
            text = resp_body.get("content", [{}])[0].get("text", "")

        # Parse JSON response
        result = _parse_json(text)
        matches = result.get("matches", [])

    except Exception as e:
        logger.error("Signature matching failed for node %d: %s", node_id, str(e)[:200])
        matches = []

    # Build embedding text from matched signatures
    embedding_text = _build_embedding_text(node_id, finding, matches)

    return {
        "node_id": node_id,
        "matches": matches,
        "match_count": len(matches),
        "strongest_match": matches[0]["signature_id"] if matches else None,
        "embedding_text": embedding_text,
        "finding_summary": finding_text[:300],
    }


def _extract_finding_text(finding: dict) -> str:
    """Extract the meaningful text from a research finding for classification."""
    parts = []
    if finding.get("situation"):
        parts.append(finding["situation"])
    elif finding.get("summary"):
        parts.append(finding["summary"])
    if finding.get("smoking_gun") and "No definitive" not in finding.get("smoking_gun", ""):
        parts.append(f"Key finding: {finding['smoking_gun']}")
    if finding.get("evidence_found"):
        for e in finding["evidence_found"][:3]:
            parts.append(f"Evidence ({e.get('source_type','')}): {e.get('finding','')}")
    if finding.get("undiscovered_sites"):
        for s in finding["undiscovered_sites"][:2]:
            parts.append(f"Undiscovered: {s.get('location','')} — {s.get('rationale','')}")
    return " | ".join(parts)


def _build_embedding_text(node_id: int, finding: dict, matches: list) -> str:
    """Build the text to embed — combines finding summary with matched signature vector_texts.

    This is critical: by embedding the SIGNATURE'S vector_text alongside the finding,
    nodes that match the same signature will naturally cluster in vector space.
    """
    taxonomy = _load_taxonomy()
    sig_vectors = {}
    for method in taxonomy["methods"]:
        for sig in method["signatures"]:
            sig_vectors[sig["signature_id"]] = sig["vector_text"]

    parts = [f"UVG Grid Node {node_id}"]

    # Add finding summary
    if finding.get("situation"):
        parts.append(finding["situation"][:200])
    elif finding.get("summary"):
        parts.append(finding["summary"][:200])

    # Add matched signature vector texts (this is what makes similar nodes cluster!)
    for match in matches:
        sig_id = match.get("signature_id", "")
        if sig_id in sig_vectors:
            parts.append(sig_vectors[sig_id])

    return " | ".join(parts)


def _parse_json(raw: str) -> dict:
    """Parse JSON from model response."""
    if not raw:
        return {}
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].strip()
    idx = text.find("{")
    if idx == -1:
        return {}
    text = text[idx:]
    brace_count = 0
    end_idx = -1
    for i, ch in enumerate(text):
        if ch == "{": brace_count += 1
        elif ch == "}":
            brace_count -= 1
            if brace_count == 0:
                end_idx = i
                break
    if end_idx >= 0:
        try:
            return json.loads(text[:end_idx + 1])
        except (json.JSONDecodeError, TypeError):
            pass
    return {}


def batch_score_findings(research_results: dict) -> list:
    """Score all research findings in a batch.

    Args:
        research_results: The full research results dict (from batch_research_direct.py)

    Returns:
        List of scored results, one per node
    """
    results = research_results.get("results", [])
    scored = []

    for r in results:
        node_id = r["node_id"]
        brief = r.get("brief", {})
        if brief.get("error"):
            scored.append({"node_id": node_id, "matches": [], "embedding_text": ""})
            continue

        score = score_finding(node_id, brief)
        scored.append(score)
        logger.info(
            "Node %d: %d signature matches (strongest: %s)",
            node_id, score["match_count"], score.get("strongest_match", "none")
        )

    return scored
