"""Score typology Lambda — k-NN similarity scoring with Bedrock synthesis.

Receives extracted subgraph from extract_subgraph, embeds evidence summaries
via Titan Embed v2, queries OpenSearch for matching prosecution patterns,
classifies match strength, and optionally synthesizes narratives via Claude Haiku.
Results are stored to Aurora precomputed tables.

Input: output of extract_subgraph (case_id, typology_module_id, sub_categories)
Output: overall_score, match_strength, sub_category_scores, key_entities
"""

import hashlib
import json
import logging
import os
import time
import urllib.error
from typing import Optional

import boto3
import botocore.auth
import botocore.awsrequest
import botocore.credentials
from botocore.session import Session as BotocoreSession

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT", "")
INDEX_NAME = "typology-patterns"
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
EMBED_MODEL = "amazon.titan-embed-text-v2:0"
SYNTH_MODEL = "anthropic.claude-3-haiku-20240307-v1:0"
SYNTH_TIMEOUT = 30

bedrock_runtime = boto3.client("bedrock-runtime", region_name=AWS_REGION)


def _build_evidence_text(sub_cat: dict) -> str:
    """Build a concise evidence summary from entities and edges."""
    entities = sub_cat.get("entities", [])
    edges = sub_cat.get("edges", [])
    parts = []
    # Summarize top entities by type
    type_groups: dict[str, list[str]] = {}
    for e in entities[:50]:
        type_groups.setdefault(e.get("type", "unknown"), []).append(e.get("name", ""))
    for etype, names in type_groups.items():
        parts.append(f"{etype}: {', '.join(names[:10])}")
    # Summarize key relationships
    for edge in edges[:30]:
        parts.append(f"{edge.get('src','')} -[{edge.get('type','')}]-> {edge.get('tgt','')}")
    return "; ".join(parts)[:4000]


def _embed_text(text: str) -> list[float]:
    """Embed text using Amazon Titan Embed Text v2."""
    resp = bedrock_runtime.invoke_model(
        modelId=EMBED_MODEL,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({"inputText": text}),
    )
    body = json.loads(resp["body"].read())
    return body["embedding"]


def _opensearch_knn(vector: list[float], k: int = 5) -> list[dict]:
    """Query OpenSearch typology-patterns index with k-NN."""
    if not OPENSEARCH_ENDPOINT:
        logger.warning("OPENSEARCH_ENDPOINT not set, skipping k-NN")
        return []

    endpoint = OPENSEARCH_ENDPOINT.rstrip("/")
    if not endpoint.startswith("https://"):
        endpoint = f"https://{endpoint}"

    path = f"/{INDEX_NAME}/_search"
    query = {
        "size": k,
        "query": {"knn": {"embedding": {"vector": vector, "k": k}}},
        "_source": ["pattern_id", "description", "severity", "typology"],
    }
    body_bytes = json.dumps(query).encode("utf-8")

    session = BotocoreSession()
    credentials = session.get_credentials().get_frozen_credentials()
    headers = {
        "Content-Type": "application/json",
        "X-Amz-Content-Sha256": hashlib.sha256(body_bytes).hexdigest(),
    }
    url = f"{endpoint}{path}"
    aws_req = botocore.awsrequest.AWSRequest(
        method="POST", url=url, headers=headers, data=body_bytes
    )
    signer = botocore.auth.SigV4Auth(credentials, "aoss", AWS_REGION)
    signer.add_auth(aws_req)
    prepared = aws_req.prepare()

    try:
        from botocore.httpsession import URLLib3Session
        http_session = URLLib3Session()
        response = http_session.send(prepared)
        if response.status_code >= 400:
            logger.error("OpenSearch k-NN error: %d %s", response.status_code, response.content[:200])
            return []
        result = json.loads(response.content.decode("utf-8"))
        hits = result.get("hits", {}).get("hits", [])
        return [{"score": h["_score"], **h.get("_source", {})} for h in hits]
    except Exception as e:
        logger.error("OpenSearch k-NN request failed: %s", str(e)[:200])
        return []


def _classify_strength(score: float) -> str:
    """Classify match strength from cosine similarity score."""
    if score >= 0.80:
        return "strong"
    elif score >= 0.60:
        return "moderate"
    return "weak"


def _synthesize_narrative(sub_cat_id: str, evidence: str, patterns: list[dict]) -> Optional[str]:
    """Invoke Claude Haiku to synthesize a prosecution-relevant narrative."""
    pattern_desc = "; ".join(p.get("description", "")[:200] for p in patterns[:3])
    prompt = (
        f"Given the following financial evidence for sub-category '{sub_cat_id}' "
        f"and matching prosecution patterns, write a 2-3 sentence analyst summary "
        f"explaining how the evidence aligns with known typologies.\n\n"
        f"Evidence: {evidence[:2000]}\n\nPatterns: {pattern_desc[:1000]}"
    )
    try:
        resp = bedrock_runtime.invoke_model(
            modelId=SYNTH_MODEL,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}],
            }),
        )
        body = json.loads(resp["body"].read())
        return body.get("content", [{}])[0].get("text", "")
    except Exception as e:
        logger.warning("Bedrock synthesis failed for %s: %s", sub_cat_id, str(e)[:150])
        return None


def _score_sub_category(sub_cat: dict) -> dict:
    """Score a single sub-category using graph density + k-NN similarity.

    Blended scoring:
    - Graph density (40%): min(1.0, entity_count/20) * 0.6 + min(1.0, edge_count/100) * 0.4
    - k-NN cosine similarity (60%): average top-k match score from OpenSearch

    Falls back to graph-density-only scoring if k-NN is unavailable.
    """
    sub_id = sub_cat["id"]
    entity_count = sub_cat.get("entity_count", 0)
    edge_count = sub_cat.get("edge_count", 0)

    if entity_count == 0:
        return {"id": sub_id, "score": 0.0, "match_strength": "weak",
                "cosine_similarity": 0.0, "synthesis_status": "skipped"}

    # Graph density score: entities contribute 60%, edges 40%
    entity_score = min(1.0, entity_count / 20.0)
    edge_score = min(1.0, edge_count / 100.0)
    density_score = entity_score * 0.6 + edge_score * 0.4

    # k-NN similarity scoring
    knn_score = 0.0
    pattern_matches = 0
    try:
        evidence_text = _build_evidence_text(sub_cat)
        if evidence_text:
            embedding = _embed_text(evidence_text)
            hits = _opensearch_knn(embedding, k=5)
            if hits:
                pattern_matches = len(hits)
                knn_score = sum(h.get("score", 0.0) for h in hits) / len(hits)
    except Exception as e:
        logger.warning("k-NN scoring failed for %s: %s", sub_id, str(e)[:150])

    # Blend: 60% k-NN + 40% density (fallback to density-only if no k-NN)
    if knn_score > 0:
        composite = knn_score * 0.6 + density_score * 0.4
    else:
        composite = density_score

    strength = _classify_strength(composite)

    return {
        "id": sub_id, "score": round(composite, 4), "match_strength": strength,
        "cosine_similarity": round(knn_score, 4),
        "synthesis_status": "skipped",
        "pattern_matches": pattern_matches,
    }


def _store_results(case_id: str, typology_module_id: str, scores: list[dict],
                   overall_score: float, overall_strength: str, execution_id: str):
    """UPSERT results into Aurora precomputed tables."""
    from db.connection import ConnectionManager
    cm = ConnectionManager()

    with cm.cursor() as cur:
        # Upsert each sub-category result
        for s in scores:
            cur.execute("""
                INSERT INTO typology_precomputed_results
                    (case_id, typology_module_id, sub_category_id, overall_score,
                     match_strength, cosine_similarity, narrative, synthesis_status,
                     is_stale, computed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, FALSE, NOW())
                ON CONFLICT (case_id, typology_module_id, sub_category_id) DO UPDATE SET
                    overall_score = EXCLUDED.overall_score,
                    match_strength = EXCLUDED.match_strength,
                    cosine_similarity = EXCLUDED.cosine_similarity,
                    narrative = EXCLUDED.narrative,
                    synthesis_status = EXCLUDED.synthesis_status,
                    is_stale = FALSE,
                    computed_at = NOW()
            """, (case_id, typology_module_id, s["id"], s["score"],
                  s["match_strength"], s["cosine_similarity"],
                  s.get("narrative"), s["synthesis_status"]))

        # Upsert aggregate summary
        key_entities = []
        for s in sorted(scores, key=lambda x: x["score"], reverse=True)[:3]:
            key_entities.append(s["id"])

        cur.execute("""
            INSERT INTO typology_precomputed_summary
                (case_id, typology_module_id, overall_typology_score, match_strength,
                 key_entities, is_stale, computed_at)
            VALUES (%s, %s, %s, %s, %s, FALSE, NOW())
            ON CONFLICT (case_id, typology_module_id) DO UPDATE SET
                overall_typology_score = EXCLUDED.overall_typology_score,
                match_strength = EXCLUDED.match_strength,
                key_entities = EXCLUDED.key_entities,
                is_stale = FALSE,
                computed_at = NOW()
        """, (case_id, typology_module_id, overall_score, overall_strength,
              json.dumps(key_entities)))


def handler(event, context):
    """Lambda entry point for typology scoring."""
    # Special action: seed the OpenSearch typology-patterns index
    if event.get("action") == "seed_typology_patterns_index":
        from db.seeds.typology_patterns_index import seed_typology_patterns
        seed_typology_patterns()
        return {"status": "seeded", "message": "typology-patterns index created and populated"}

    case_id = event.get("case_id", "")
    typology_module_id = event.get("typology_module_id", "")
    execution_id = event.get("execution_id", "")

    if not case_id or not typology_module_id:
        return {"error": "Missing case_id or typology_module_id"}

    # Read extraction results from Aurora (written by extract_subgraph Lambda)
    from db.connection import ConnectionManager
    cm = ConnectionManager()
    sub_categories = []
    try:
        with cm.cursor() as cur:
            cur.execute("""
                SELECT sub_category_id, key_entities, subgraph_summary
                FROM typology_precomputed_results
                WHERE case_id = %s AND typology_module_id = %s
            """, (case_id, typology_module_id))
            rows = cur.fetchall()
            for row in rows:
                import json as _json
                key_ents = row[1] if isinstance(row[1], list) else _json.loads(row[1] or "[]")
                summary = row[2] if isinstance(row[2], dict) else _json.loads(row[2] or "{}")
                sub_categories.append({
                    "id": row[0],
                    "entities": [{"name": n, "type": "unknown"} for n in key_ents],
                    "edges": [],
                    "entity_count": summary.get("entity_count", 0),
                    "edge_count": summary.get("edge_count", 0),
                })
    except Exception as db_exc:
        logger.error("Failed to read extraction data from Aurora: %s", str(db_exc)[:200])

    logger.info("Scoring: case=%s typology=%s sub_cats=%d",
                case_id, typology_module_id, len(sub_categories))
    start = time.monotonic()

    scores = []
    for sub_cat in sub_categories:
        try:
            result = _score_sub_category(sub_cat)
            scores.append(result)
        except Exception as e:
            logger.error("Scoring failed for %s: %s", sub_cat.get("id"), str(e)[:200])
            scores.append({"id": sub_cat.get("id", "unknown"), "score": 0.0,
                           "match_strength": "weak", "cosine_similarity": 0.0,
                           "synthesis_status": "pending", "pattern_matches": 0})

    # Compute aggregate score (weighted average by non-zero scores)
    valid_scores = [s["score"] for s in scores if s["score"] > 0]
    overall_score = round(sum(valid_scores) / len(valid_scores), 4) if valid_scores else 0.0
    overall_strength = _classify_strength(overall_score)

    # Extract top key entities from highest-scoring sub-categories
    key_entities = [s["id"] for s in sorted(scores, key=lambda x: x["score"], reverse=True)[:5]]

    # Store to Aurora
    try:
        _store_results(case_id, typology_module_id, scores, overall_score,
                       overall_strength, execution_id)
    except Exception as e:
        logger.error("Aurora store failed: %s", str(e)[:300])

    duration_ms = int((time.monotonic() - start) * 1000)
    logger.info("Scoring complete: case=%s overall=%.4f (%s) %dms",
                case_id, overall_score, overall_strength, duration_ms)

    return {
        "case_id": case_id,
        "typology_module_id": typology_module_id,
        "overall_score": overall_score,
        "match_strength": overall_strength,
        "sub_category_scores": [
            {"id": s["id"], "score": s["score"], "match_strength": s["match_strength"],
             "cosine_similarity": s["cosine_similarity"]} for s in scores
        ],
        "key_entities": key_entities,
        "scoring_duration_ms": duration_ms,
        "execution_id": execution_id,
    }
