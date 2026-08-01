"""Grid Investigation API — Serves the UVG 62-node classified grid + intersections.

Endpoints:
    GET  /pattern-library/grid/nodes          — all 62 classified nodes
    GET  /pattern-library/grid/intersections   — all computed intersection points
    GET  /pattern-library/grid/targets         — high-priority investigation targets only
"""

import json
import logging
import os

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

S3_BUCKET = os.environ.get("S3_BUCKET", "research-analyst-data-lake-974220725866")

_grid_cache = {}


def _load_from_s3(key):
    """Load and cache a JSON file from S3."""
    if key in _grid_cache:
        return _grid_cache[key]
    
    try:
        s3 = boto3.client("s3")
        resp = s3.get_object(Bucket=S3_BUCKET, Key=key)
        data = json.loads(resp["Body"].read().decode("utf-8"))
        _grid_cache[key] = data
        return data
    except Exception as e:
        logger.error("Failed to load %s from S3: %s", key, str(e)[:200])
        return None


def get_grid_nodes_handler(event, context):
    """Return all 62 classified UVG grid nodes (official Hagens coordinates)."""
    from lambdas.api.response_helper import CORS_HEADERS, error_response, success_response

    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    data = _load_from_s3("pattern-library/uvg-grid-investigation-database.json")
    if not data:
        return error_response(503, "DATA_UNAVAILABLE", "Grid data not available", event)

    return success_response(data, 200, event)


def get_grid_intersections_handler(event, context):
    """Return all computed grid intersection points."""
    from lambdas.api.response_helper import CORS_HEADERS, error_response, success_response

    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    data = _load_from_s3("pattern-library/uvg-grid-intersections.json")
    if not data:
        return error_response(503, "DATA_UNAVAILABLE", "Intersection data not available", event)

    return success_response(data, 200, event)


def get_grid_targets_handler(event, context):
    """Return only high-priority investigation targets (unexplored land nodes + intersections)."""
    from lambdas.api.response_helper import CORS_HEADERS, error_response, success_response

    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    grid = _load_from_s3("pattern-library/uvg-grid-classified.json")
    intersections = _load_from_s3("pattern-library/uvg-grid-intersections.json")

    if not grid:
        return error_response(503, "DATA_UNAVAILABLE", "Grid data not available", event)

    nodes = grid.get("nodes", [])
    
    # High priority = confirmed sites + unexplored land nodes
    confirmed = [n for n in nodes if n.get("research_status") == "confirmed"]
    unexplored = [n for n in nodes if n.get("research_status") == "unexplored"]
    anomalies = [n for n in nodes if n.get("research_status") == "anomaly"]
    probable = [n for n in nodes if n.get("research_status") == "probable"]

    # Land intersections from edge crossings
    land_intersections = []
    if intersections:
        land_intersections = [p for p in intersections.get("intersections", []) if p.get("on_land")]

    targets = {
        "confirmed_sites": confirmed,
        "unexplored_targets": unexplored,
        "anomaly_zones": anomalies,
        "probable_sites": probable,
        "edge_intersections_on_land": land_intersections,
        "summary": {
            "total_grid_nodes": len(nodes),
            "confirmed": len(confirmed),
            "unexplored_land": len(unexplored),
            "anomalies": len(anomalies),
            "probable": len(probable),
            "edge_intersections": len(land_intersections),
        }
    }

    return success_response(targets, 200, event)


def get_grid_research_handler(event, context):
    """Return all AI research briefs for grid nodes."""
    from lambdas.api.response_helper import CORS_HEADERS, error_response, success_response

    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    data = _load_from_s3("pattern-library/uvg-grid-research-all-nodes.json")
    if not data:
        return error_response(503, "DATA_UNAVAILABLE", "Research data not available", event)

    return success_response(data, 200, event)


def get_grid_scored_handler(event, context):
    """Return scored findings (signature matches) for all grid nodes."""
    from lambdas.api.response_helper import CORS_HEADERS, error_response, success_response

    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    data = _load_from_s3("pattern-library/uvg-grid-scored-findings.json")
    if not data:
        return error_response(503, "DATA_UNAVAILABLE", "Scored findings not available", event)

    return success_response(data, 200, event)


def get_grid_emergent_handler(event, context):
    """Return emergent patterns detected by OpenSearch k-NN similarity."""
    from lambdas.api.response_helper import CORS_HEADERS, error_response, success_response

    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    data = _load_from_s3("pattern-library/emergent-patterns.json")
    if not data:
        return error_response(503, "DATA_UNAVAILABLE", "Emergent patterns not available", event)

    return success_response(data, 200, event)


def get_grid_audio_handler(event, context):
    """Return presigned URLs for audio briefing chapters."""
    from lambdas.api.response_helper import CORS_HEADERS, error_response, success_response

    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    # Load manifest
    manifest = _load_from_s3("pattern-library/audio-briefing-manifest.json")
    if not manifest:
        return error_response(503, "DATA_UNAVAILABLE", "Audio briefing not available", event)

    # Generate presigned URLs for each chapter
    s3 = boto3.client("s3")
    chapters = []
    for ch in manifest.get("chapters", []):
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": ch["s3_key"]},
            ExpiresIn=3600
        )
        chapters.append({
            "chapter": ch["chapter"],
            "title": ch["title"],
            "url": url,
            "size_kb": ch.get("size_kb", 0)
        })

    # Full briefing URL
    full_url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": "audio/briefing-full.mp3"},
        ExpiresIn=3600
    )

    result = {
        "title": manifest.get("title", "Research Briefing"),
        "voice": manifest.get("voice", "Matthew"),
        "total_chapters": len(chapters),
        "full_url": full_url,
        "chapters": chapters
    }

    return success_response(result, 200, event)
