"""Store investigation rationales in Aurora via the existing SummaryCacheManager.

Uses the ai_level_summaries table with key prefix 'rationale:node_{id}'
so that the API can serve them on second request without calling Bedrock.

The frontend can also call GET /pattern-library/summary/rationale/{node_id}
to retrieve cached rationales via the existing API endpoint.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "data")

def main():
    try:
        from db.connection import ConnectionManager
        from services.summary_cache_manager import SummaryCacheManager
    except ImportError:
        print("NOTE: Cannot import Aurora modules (likely running outside Lambda/VPC)")
        print("Rationales are saved in investigation-rationales.json for local use.")
        print("To store in Aurora, run this script from within the Lambda environment")
        print("or with VPC access to the Aurora cluster.")
        return

    # Load rationales
    rationale_path = os.path.join(DATA_DIR, "investigation-rationales.json")
    with open(rationale_path) as f:
        rationales = json.load(f)

    print(f"Storing {len(rationales)} rationales in Aurora...")

    cm = ConnectionManager()
    cache = SummaryCacheManager(cm, ttl_seconds=2592000)  # 30-day TTL

    stored = 0
    for node_id, rationale in rationales.items():
        context_key = f"rationale:node_{node_id}"
        summary_text = json.dumps(rationale)
        
        try:
            cache.store_summary(
                context_key=context_key,
                level="rationale",
                summary_text=summary_text,
                model_id="us.anthropic.claude-sonnet-4-6",
                prompt_tokens=0,
                completion_tokens=0,
            )
            stored += 1
        except Exception as e:
            print(f"  Failed node {node_id}: {e}")

    print(f"Stored {stored}/{len(rationales)} rationales in Aurora")
    print("Retrieval: GET /pattern-library/summary/rationale/node_{id}")


if __name__ == "__main__":
    main()
