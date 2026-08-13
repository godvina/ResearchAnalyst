#!/usr/bin/env python3
"""Upload Tier 3 Epstein entities to Aurora + Run Irish sites through taxonomy.

Part 1: Load Tier 3 extraction results (1,329 entities, 445 relationships)
        into Aurora via Lambda.
Part 2: Process 13 Irish sacred sites through taxonomy pipeline with
        cross-domain scoring against ALL existing datasets.
"""
import boto3
import json
import os
import re
import time
from collections import defaultdict

REGION = "us-east-1"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
EMBED_MODEL = "amazon.titan-embed-text-v2:0"

lam = boto3.client("lambda", region_name=REGION)
bedrock = boto3.client("bedrock-runtime", region_name=REGION)


def invoke_lambda(payload):
    r = lam.invoke(FunctionName=LAMBDA_NAME, InvocationType="RequestResponse",
        Payload=json.dumps(payload))
    return json.loads(r["Payload"].read().decode())


def embed_text(text):
    resp = bedrock.invoke_model(
        modelId=EMBED_MODEL, contentType="application/json",
        accept="application/json", body=json.dumps({"inputText": text[:8000]}))
    return json.loads(resp["body"].read())["embedding"]


# ================================================================
# PART 1: Upload Tier 3 Epstein entities to Aurora
# ================================================================
print("=" * 70)
print("PART 1: Upload Tier 3 Epstein Entities → Aurora")
print("=" * 70)

tier3_path = "scripts/epstein_tier3_entities.json"
if not os.path.exists(tier3_path):
    print("  ERROR: Tier 3 results not found!")
else:
    data = json.load(open(tier3_path, "r", encoding="utf-8"))
    results = data.get("results", [])
    print(f"  Documents with extractions: {len(results)}")
    print(f"  Total entities in file: {data.get('total_entities', 0)}")
    print(f"  Total relationships: {data.get('total_relationships', 0)}")

    # Collect all entities from all documents
    all_entities = []
    for doc in results:
        extraction = doc.get("extraction", {})
        for ent in extraction.get("entities", []):
            if isinstance(ent, dict):
                name = ent.get("name", "")
                etype = ent.get("type", "unknown")
                conf = ent.get("confidence", 0.8)
                if name and len(name) >= 2:
                    all_entities.append({
                        "case_id": CASE_ID,
                        "document_id": "",
                        "name": name[:255],
                        "type": etype,
                        "confidence": float(conf) if isinstance(conf, (int, float)) else 0.8,
                    })

    print(f"  Valid entities to upload: {len(all_entities)}")

    # Batch insert
    batch_size = 200
    total_inserted = 0
    for i in range(0, len(all_entities), batch_size):
        batch = all_entities[i:i + batch_size]
        result = invoke_lambda({
            "action": "insert_entities_from_batch",
            "entities": batch,
        })
        total_inserted += result.get("inserted", 0)

    print(f"  Inserted into Aurora: {total_inserted}")
    print(f"  ✓ Tier 3 Epstein entities now in Aurora")

# ================================================================
# PART 2: Irish Sites Through Taxonomy Pipeline
# ================================================================
print("\n" + "=" * 70)
print("PART 2: Irish Sacred Sites — Taxonomy Pipeline")
print("=" * 70)

# Load Irish sites
sites = []
for filename in ["irish_ancient_sites.json", "irish_ancient_sites_continued.json"]:
    path = f"src/data/conspiracy-seed/irish_sacred_sites/{filename}"
    if os.path.exists(path):
        data = json.load(open(path, "r", encoding="utf-8"))
        sites.extend(data.get("sites", data.get("sites_continued", [])))

print(f"  Irish sites loaded: {len(sites)}")

# Cross-domain taxonomy signatures (ALL domains — per steering rules)
TAXONOMY_SIGNATURES = {
    "ancient_mysteries": {
        "advanced_technology": "Ancient construction requiring knowledge and engineering capabilities that challenge conventional explanations for the time period, including precision stone cutting, massive material transport, and waterproofing.",
        "geographic_alignment": "Deliberate alignment of ancient structures along geographic lines, intervisibility networks, and coordinate relationships suggesting large-scale planning and communication.",
        "astronomical_correlation": "Precise alignment of ancient structures with solar, lunar, or stellar events including solstices, equinoxes, precession cycles, and specific star positions.",
        "lost_knowledge": "Evidence of knowledge systems, technologies, or cultural practices that were lost, suppressed, or forgotten, only rediscovered through archaeology or independent study.",
        "anomalous_artifacts": "Objects, carvings, or constructions that are out of place for their time period or location, suggesting contact, trade, or shared knowledge across distant cultures.",
    },
    "conspiracy_theory": {
        "evidence_suppression": "Patterns of institutional behavior that suppress, classify, or limit access to evidence that could challenge official narratives about history or events.",
        "institutional_behavior": "Actions by government agencies, academic institutions, or religious organizations that control the narrative around discoveries or historical interpretations.",
        "information_asymmetry": "Situations where certain groups had access to knowledge about sites, artifacts, or technologies that was not shared with the broader public.",
    },
    "crime": {
        "document_concealment": "Destruction, theft, or concealment of archaeological records, site documentation, or research findings.",
        "organizational_hierarchy": "Networks of researchers, institutions, or organizations that coordinate to control access to sites or suppress alternative interpretations.",
    },
}

# Embed all taxonomy signatures
print("\n  Embedding taxonomy signatures...")
taxonomy_embeddings = {}
for domain, sigs in TAXONOMY_SIGNATURES.items():
    for sig_name, sig_text in sigs.items():
        key = f"{domain}/{sig_name}"
        taxonomy_embeddings[key] = embed_text(sig_text)
        print(f"    ✓ {key}")

print(f"  Total signatures: {len(taxonomy_embeddings)}")

# Process each Irish site
print("\n  Processing sites through taxonomy...")

def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

site_results = []
for site in sites:
    name = site.get("name", "?")
    print(f"\n  [{site.get('id')}] {name}")

    # Build rich text description for embedding
    text_parts = [
        f"Ancient site: {name}",
        f"Location: County {site.get('county', '?')}, Ireland",
        f"Age: {site.get('age_years', '?')} years old ({site.get('date_built', '?')})",
        f"Category: {site.get('category', '?')}",
        f"Description: {site.get('description', '')}",
    ]
    for mystery in site.get("mysteries", []):
        text_parts.append(f"Mystery: {mystery}")
    for conn in site.get("cross_domain_connections", []):
        text_parts.append(f"Cross-domain: {conn}")

    site_text = "\n".join(text_parts)

    # Embed the site
    site_embedding = embed_text(site_text)

    # Score against ALL taxonomy signatures
    scores = {}
    for sig_key, sig_embedding in taxonomy_embeddings.items():
        sim = cosine_similarity(site_embedding, sig_embedding)
        scores[sig_key] = round(sim, 4)

    # Sort by score
    sorted_scores = sorted(scores.items(), key=lambda x: -x[1])

    # Identify cross-domain matches
    domains_hit = set()
    for key, score in sorted_scores[:10]:
        domain = key.split("/")[0]
        domains_hit.add(domain)

    is_cross_cutting = len(domains_hit) >= 2

    result = {
        "id": site.get("id"),
        "name": name,
        "category": site.get("category"),
        "county": site.get("county"),
        "coordinates": site.get("coordinates"),
        "taxonomy_scores": dict(sorted_scores[:10]),
        "top_match": sorted_scores[0] if sorted_scores else None,
        "is_cross_cutting": is_cross_cutting,
        "domains_matched": list(domains_hit),
        "text_used": site_text[:200],
    }
    site_results.append(result)

    # Print top scores
    print(f"    Top matches:")
    for key, score in sorted_scores[:5]:
        print(f"      {key}: {score:.4f}")
    if is_cross_cutting:
        print(f"    ⚡ CROSS-CUTTING: matches {len(domains_hit)} domains ({', '.join(domains_hit)})")

    time.sleep(0.5)  # Rate limit

# ================================================================
# Summary and save results
# ================================================================
print("\n" + "=" * 70)
print("IRISH SITES TAXONOMY RESULTS")
print("=" * 70)

cross_cutting_sites = [s for s in site_results if s["is_cross_cutting"]]
print(f"\n  Sites processed: {len(site_results)}")
print(f"  Cross-cutting (2+ domains): {len(cross_cutting_sites)}")

print(f"\n  Site rankings by taxonomy relevance:")
ranked = sorted(site_results, key=lambda x: x["top_match"][1] if x["top_match"] else 0, reverse=True)
for i, site in enumerate(ranked, 1):
    top = site["top_match"]
    cross = " ⚡CROSS-DOMAIN" if site["is_cross_cutting"] else ""
    print(f"    {i:2d}. {site['name'][:35]:35s} | {top[0]:30s} | {top[1]:.4f}{cross}")

# Save results
output = {
    "pipeline_run": "irish_sacred_sites_taxonomy",
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "sites_processed": len(site_results),
    "cross_cutting": len(cross_cutting_sites),
    "taxonomy_domains_used": list(TAXONOMY_SIGNATURES.keys()),
    "signatures_used": len(taxonomy_embeddings),
    "results": site_results,
}

output_path = "src/data/proof-engine-results-irish-sacred-sites.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
print(f"\n  Results saved: {output_path}")

# Also upload site entities to Aurora for cross-case search
print(f"\n  Uploading Irish site entities to Aurora...")
site_entities = []
for site in sites:
    # Each site becomes an entity
    site_entities.append({
        "case_id": CASE_ID,
        "document_id": "",
        "name": site.get("name", "")[:255],
        "type": "location",
        "confidence": 0.99,
    })
    # Key mysteries as theme entities
    for mystery in site.get("mysteries", [])[:3]:
        site_entities.append({
            "case_id": CASE_ID,
            "document_id": "",
            "name": mystery[:255],
            "type": "theme",
            "confidence": 0.85,
        })

result = invoke_lambda({
    "action": "insert_entities_from_batch",
    "entities": site_entities,
})
print(f"  Inserted: {result.get('inserted', 0)} site entities")

# ================================================================
# TODO LOG: Full corpus processing
# ================================================================
todo = {
    "task": "Process full HuggingFace Epstein corpus (1.38M docs) via tiered pipeline",
    "estimated_cost": "$50-70",
    "approach": "Download parquet → Tier 1 keyword filter → Tier 2 embed filtered → Tier 3 Haiku on top matches",
    "source": "huggingface.co/datasets/ishumilin/epstein-files-ocr-complete",
    "status": "PARKED — awaiting user decision",
    "notes": "Would give complete coverage of all 12 DOJ datasets vs current 3,804 file subset",
}
with open("scripts/TODO_full_corpus_processing.json", "w") as f:
    json.dump(todo, f, indent=2)
print(f"\n  TODO logged: scripts/TODO_full_corpus_processing.json")

print("\n" + "=" * 70)
print("ALL DONE")
print("=" * 70)
