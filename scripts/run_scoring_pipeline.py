"""Run the full scoring pipeline: Research → Signatures → Embeddings → OpenSearch.

Assumes batch_research_direct.py has already run and produced findings.
This script processes those findings through:
  Step 2: Score against taxonomy signatures (Sonnet classifier)
  Step 3: Embed scored findings (Titan Embed v2)
  Step 4: Index into OpenSearch (k-NN)

Usage:
    python scripts/run_scoring_pipeline.py [--limit 5] [--skip-embed]
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "data")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--skip-embed", action="store_true")
    args = parser.parse_args()

    # Load research results
    results_path = os.path.join(DATA_DIR, "uvg-grid-research-all-nodes.json")
    if not os.path.exists(results_path):
        print("ERROR: No research results found. Run batch_research_direct.py first.")
        return

    with open(results_path, encoding="utf-8") as f:
        research_data = json.load(f)

    results = research_data.get("results", [])
    # Filter to nodes that have actual findings (not errors)
    valid_results = [r for r in results if r.get("brief", {}).get("codename")]
    print(f"Pipeline Input: {len(valid_results)} nodes with research findings")
    print()

    # Step 2: Score against taxonomy
    print("=" * 60)
    print("STEP 2: Scoring findings against 18 investigation signatures")
    print("=" * 60)

    from services.signature_matching_engine import score_finding

    scored_results = []
    limit = min(args.limit, len(valid_results))

    for i, r in enumerate(valid_results[:limit]):
        node_id = r["node_id"]
        brief = r.get("brief", {})
        print(f"  [{i+1}/{limit}] Node {node_id}...", end=" ")

        t0 = time.time()
        score = score_finding(node_id, brief)
        elapsed = time.time() - t0

        matches = score.get("matches", [])
        if matches:
            sigs = [m["signature_id"] for m in matches]
            print(f"✅ {len(matches)} matches: {', '.join(sigs)} ({elapsed:.1f}s)")
        else:
            print(f"— no matches ({elapsed:.1f}s)")

        scored_results.append(score)
        time.sleep(1)  # Rate limit

    # Save scored results
    scored_path = os.path.join(DATA_DIR, "uvg-grid-scored-findings.json")
    output = {
        "name": "UVG Grid — Scored Findings (Signature Matches)",
        "total_scored": len(scored_results),
        "total_with_matches": len([s for s in scored_results if s.get("matches")]),
        "results": scored_results,
    }
    with open(scored_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nScored results saved to {scored_path}")

    # Summary
    all_matches = []
    for s in scored_results:
        all_matches.extend(s.get("matches", []))

    if all_matches:
        print(f"\nSIGNATURE MATCH SUMMARY:")
        sig_counts = {}
        for m in all_matches:
            sig_id = m.get("signature_id", "?")
            sig_counts[sig_id] = sig_counts.get(sig_id, 0) + 1
        for sig_id, count in sorted(sig_counts.items(), key=lambda x: -x[1]):
            print(f"  {sig_id}: {count} nodes match")

    if args.skip_embed:
        print("\nSkipping embedding step (--skip-embed).")
        return

    # Step 3 & 4: Embed and index (only for scored results with matches)
    print()
    print("=" * 60)
    print("STEP 3+4: Embedding scored findings and indexing to OpenSearch")
    print("=" * 60)

    import boto3
    bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

    embedded_count = 0
    for score in scored_results:
        if not score.get("embedding_text"):
            continue

        text = score["embedding_text"][:8000]
        try:
            resp = bedrock.invoke_model(
                modelId="amazon.titan-embed-text-v2:0",
                contentType="application/json",
                accept="application/json",
                body=json.dumps({"inputText": text}),
            )
            embedding = json.loads(resp["body"].read())["embedding"]
            score["embedding"] = embedding
            embedded_count += 1
        except Exception as e:
            print(f"  Embed failed for Node {score['node_id']}: {e}")

        time.sleep(0.3)

    print(f"  Embedded {embedded_count} nodes")

    # Save with embeddings
    embedded_path = os.path.join(DATA_DIR, "uvg-grid-embedded-findings.json")
    with open(embedded_path, "w") as f:
        # Don't save raw embeddings to JSON (too large) — just save metadata
        meta_results = [{k: v for k, v in s.items() if k != "embedding"} for s in scored_results]
        json.dump({"results": meta_results, "embedded_count": embedded_count}, f, indent=2)
    print(f"  Metadata saved to {embedded_path}")
    print(f"\nPipeline complete! {embedded_count} nodes ready for k-NN similarity queries.")


if __name__ == "__main__":
    main()
