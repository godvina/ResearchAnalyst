"""
Archon Library — Phase 3: Embed Patterns & Score Entities

Embeds the 7 cross-cultural patterns using Titan Embed v2,
then scores each entity against all patterns via cosine similarity.
Outputs scored results for the frontend and saves embeddings for future k-NN.

Usage:
    python scripts/archon_embed_and_score.py

Output:
    src/data/archon-pattern-scores.json — entity-to-pattern scores
    src/data/archon-embeddings.json — raw embeddings for Aurora pgvector upload
"""

import json
import math
import time
import sys
from pathlib import Path

import boto3
from botocore.config import Config

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from archon_process_texts import ARCHON_PATTERNS

ARCHON_JSON = PROJECT_ROOT / "src" / "data" / "archon-library.json"
OUTPUT_SCORES = PROJECT_ROOT / "src" / "data" / "archon-pattern-scores.json"
OUTPUT_EMBEDDINGS = PROJECT_ROOT / "src" / "data" / "archon-embeddings.json"
OUTPUT_JS = PROJECT_ROOT / "src" / "frontend" / "archon-scores.js"

TITAN_MODEL = "amazon.titan-embed-text-v2:0"
AWS_REGION = "us-east-1"

client = boto3.client("bedrock-runtime", region_name=AWS_REGION,
                      config=Config(read_timeout=30, connect_timeout=10, retries={"max_attempts": 3}))


def embed_text(text: str) -> list:
    """Generate embedding using Titan Embed Text v2 (1024 dimensions)."""
    response = client.invoke_model(
        modelId=TITAN_MODEL,
        body=json.dumps({"inputText": text[:8000]}),  # Titan v2 max ~8K chars
        contentType="application/json",
        accept="application/json"
    )
    result = json.loads(response["body"].read())
    return result.get("embedding", [])


def cosine_similarity(a: list, b: list) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def main():
    print("=" * 60)
    print("ARCHON LIBRARY — Phase 3: Embed Patterns & Score Entities")
    print("=" * 60)

    # Load library
    lib = json.load(open(ARCHON_JSON, encoding="utf-8"))
    entities = lib["entities"]
    print(f"Loaded {len(entities)} entities from archon-library.json")

    # =========================================================================
    # STEP 1: Embed the 7 cross-cultural patterns
    # =========================================================================
    print(f"\nStep 1: Embedding {len(ARCHON_PATTERNS)} patterns...")

    pattern_embeddings = []
    for i, pattern in enumerate(ARCHON_PATTERNS):
        # Build rich text for embedding: name + description + indicators + cultures
        embed_text_str = (
            f"{pattern['name']}. {pattern['description']}. "
            f"Indicators: {', '.join(pattern.get('indicators', []))}. "
            f"Appears in: {', '.join(pattern.get('appears_in', []))}"
        )
        print(f"  [{i+1}/{len(ARCHON_PATTERNS)}] {pattern['name']}...")
        embedding = embed_text(embed_text_str)
        pattern_embeddings.append({
            "pattern_id": pattern["pattern_id"],
            "name": pattern["name"],
            "embedding": embedding,
            "embed_text": embed_text_str[:200],  # Store truncated for reference
        })
        time.sleep(0.2)  # Light rate limiting

    print(f"  Done. {len(pattern_embeddings)} patterns embedded ({len(pattern_embeddings[0]['embedding'])} dimensions)")

    # =========================================================================
    # STEP 2: Embed entities (batch — take description + culture + type)
    # =========================================================================
    print(f"\nStep 2: Embedding {len(entities)} entities...")

    entity_embeddings = []
    batch_size = 10
    for i, entity in enumerate(entities):
        # Build entity text for embedding
        embed_text_str = (
            f"{entity['name']}. {entity.get('description', '')}. "
            f"Culture: {entity.get('culture', 'unknown')}. "
            f"Type: {entity.get('type', 'unknown')}. "
            f"Aliases: {', '.join(entity.get('aliases', []))}"
        )
        embedding = embed_text(embed_text_str)
        entity_embeddings.append({
            "name": entity["name"],
            "culture": entity.get("culture", "unknown"),
            "type": entity.get("type", "unknown"),
            "embedding": embedding,
        })

        if (i + 1) % batch_size == 0:
            print(f"  [{i+1}/{len(entities)}] embedded...")
            time.sleep(0.3)  # Rate limit every 10

    print(f"  Done. {len(entity_embeddings)} entities embedded.")

    # =========================================================================
    # STEP 3: Score each entity against each pattern (cosine similarity)
    # =========================================================================
    print(f"\nStep 3: Scoring {len(entities)} entities against {len(ARCHON_PATTERNS)} patterns...")

    scored_entities = []
    for ent_emb in entity_embeddings:
        scores = {}
        for pat_emb in pattern_embeddings:
            sim = cosine_similarity(ent_emb["embedding"], pat_emb["embedding"])
            scores[pat_emb["pattern_id"]] = round(sim, 4)

        # Find top matching patterns
        sorted_scores = sorted(scores.items(), key=lambda x: -x[1])
        top_pattern = sorted_scores[0] if sorted_scores else ("none", 0)

        scored_entities.append({
            "name": ent_emb["name"],
            "culture": ent_emb["culture"],
            "type": ent_emb["type"],
            "pattern_scores": scores,
            "top_pattern": top_pattern[0],
            "top_score": top_pattern[1],
            "cross_cutting": sum(1 for _, s in sorted_scores if s > 0.2),  # patterns with >0.2 match
        })

    # =========================================================================
    # STEP 4: Aggregate pattern-level statistics
    # =========================================================================
    print("\nStep 4: Aggregating pattern statistics...")

    pattern_stats = {}
    for pattern in ARCHON_PATTERNS:
        pid = pattern["pattern_id"]
        matching = [e for e in scored_entities if e["pattern_scores"].get(pid, 0) > 0.15]
        cultures = set(e["culture"] for e in matching)
        pattern_stats[pid] = {
            "pattern_id": pid,
            "name": pattern["name"],
            "matching_entities": len(matching),
            "cultures_represented": len(cultures),
            "culture_list": sorted(cultures),
            "top_5_entities": sorted(matching, key=lambda x: -x["pattern_scores"][pid])[:5],
            "avg_score": round(sum(e["pattern_scores"][pid] for e in scored_entities) / len(scored_entities), 4) if scored_entities else 0,
            "verdict": "UNIVERSAL" if len(cultures) >= 8 else "WIDESPREAD" if len(cultures) >= 5 else "REGIONAL" if len(cultures) >= 2 else "ISOLATED",
        }

    # =========================================================================
    # STEP 5: Output results
    # =========================================================================
    print("\nStep 5: Writing output files...")

    # Full scores JSON
    output = {
        "version": "1.0.0",
        "generated": time.strftime("%Y-%m-%d %H:%M"),
        "total_entities": len(scored_entities),
        "total_patterns": len(ARCHON_PATTERNS),
        "embedding_model": TITAN_MODEL,
        "embedding_dimensions": len(pattern_embeddings[0]["embedding"]) if pattern_embeddings else 0,
        "pattern_stats": pattern_stats,
        "scored_entities": scored_entities,
    }
    json.dump(output, open(OUTPUT_SCORES, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"  Wrote: {OUTPUT_SCORES}")

    # Embeddings JSON (for Aurora pgvector upload later)
    embeddings_output = {
        "version": "1.0.0",
        "model": TITAN_MODEL,
        "dimensions": len(pattern_embeddings[0]["embedding"]) if pattern_embeddings else 0,
        "patterns": pattern_embeddings,
        "entities": entity_embeddings,
    }
    json.dump(embeddings_output, open(OUTPUT_EMBEDDINGS, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"  Wrote: {OUTPUT_EMBEDDINGS}")

    # Frontend JS (scores only, no embeddings — too large)
    frontend_data = {
        "pattern_stats": pattern_stats,
        "top_cross_cutting": sorted(scored_entities, key=lambda x: -x["cross_cutting"])[:20],
        "by_culture": {},
    }
    # Group by culture
    for e in scored_entities:
        c = e["culture"]
        if c not in frontend_data["by_culture"]:
            frontend_data["by_culture"][c] = []
        frontend_data["by_culture"][c].append({
            "name": e["name"],
            "top_pattern": e["top_pattern"],
            "top_score": e["top_score"],
            "cross_cutting": e["cross_cutting"],
        })

    js = f"// Archon Pattern Scores - Generated {time.strftime('%Y-%m-%d')}\n"
    js += f"// {len(scored_entities)} entities scored against {len(ARCHON_PATTERNS)} patterns\n\n"
    js += f"const ARCHON_SCORES = {json.dumps(frontend_data, indent=2, ensure_ascii=False)};\n"
    open(OUTPUT_JS, "w", encoding="utf-8").write(js)
    print(f"  Wrote: {OUTPUT_JS}")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print(f"\n{'='*60}")
    print(f"PHASE 3 COMPLETE — Pattern Scoring Results")
    print(f"{'='*60}")
    print(f"  Entities scored: {len(scored_entities)}")
    print(f"  Patterns: {len(ARCHON_PATTERNS)}")
    print(f"  Embedding dimensions: {len(pattern_embeddings[0]['embedding']) if pattern_embeddings else 0}")
    print(f"\n  PATTERN VERDICTS:")
    for pid, stats in pattern_stats.items():
        print(f"    {stats['name']}: {stats['verdict']} ({stats['matching_entities']} entities, {stats['cultures_represented']} cultures)")
    print(f"\n  TOP CROSS-CUTTING ENTITIES (match 3+ patterns):")
    for e in sorted(scored_entities, key=lambda x: -x["cross_cutting"])[:10]:
        print(f"    {e['name']} ({e['culture']}): {e['cross_cutting']} patterns, top={e['top_pattern']} ({e['top_score']:.3f})")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
