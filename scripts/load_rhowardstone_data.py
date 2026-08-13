#!/usr/bin/env python3
"""Download rhowardstone/Epstein-research-data and load into Aurora + Neptune.

Downloads pre-processed knowledge graph, persons registry, and entity
extractions from GitHub. Transforms to our schema and loads via Lambda.

This data covers ALL 12 DOJ datasets (1.39M docs, 2.77M pages) — far more
than the 3,804 Textract files in our S3 bucket.

Cost: $0 (no Bedrock, no embeddings — data is already extracted)

Usage:
    python scripts/load_rhowardstone_data.py --download     # Download files
    python scripts/load_rhowardstone_data.py --load         # Load into infra
    python scripts/load_rhowardstone_data.py --all          # Both
    python scripts/load_rhowardstone_data.py --dry-run      # Preview only
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request
import uuid

import boto3

# ============================================================
# Configuration
# ============================================================

REGION = "us-east-1"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"

# GitHub raw URLs for rhowardstone/Epstein-research-data
GITHUB_BASE = "https://raw.githubusercontent.com/rhowardstone/Epstein-research-data/main"

FILES_TO_DOWNLOAD = {
    "knowledge_graph_entities.json": f"{GITHUB_BASE}/knowledge_graph_entities.json",
    "knowledge_graph_relationships.json": f"{GITHUB_BASE}/knowledge_graph_relationships.json",
    "persons_registry.json": f"{GITHUB_BASE}/persons_registry.json",
    "extracted_entities_filtered.json": f"{GITHUB_BASE}/extracted_entities_filtered.json",
}

# Local download directory
DOWNLOAD_DIR = "scripts/rhowardstone_data"

# Entity type mapping (their types → our EntityType enum)
ENTITY_TYPE_MAP = {
    "person": "person",
    "organization": "organization",
    "shell_company": "organization",
    "property": "location",
    "location": "location",
    "aircraft": "vehicle",
    "foundation": "organization",
    "bank": "organization",
    "company": "organization",
    "government_agency": "organization",
    "school": "organization",
    "unknown": "person",
}

# Relationship type mapping (their types → our RelationshipType enum)
RELATIONSHIP_TYPE_MAP = {
    "financial": "thematic",
    "social": "co-occurrence",
    "legal": "thematic",
    "employment": "co-occurrence",
    "ownership": "thematic",
    "associated_with": "co-occurrence",
    "traveled_with": "geographic",
    "recruited_by": "causal",
    "victim_of": "causal",
    "funded_by": "thematic",
    "managed_by": "co-occurrence",
    "witnessed": "temporal",
    "resided_at": "geographic",
    "employed_at": "co-occurrence",
    "default": "co-occurrence",
}

lam = boto3.client("lambda", region_name=REGION)


# ============================================================
# Download from GitHub
# ============================================================

def download_files():
    """Download pre-processed data from GitHub."""
    print("=" * 70)
    print("PHASE 1: Download from rhowardstone/Epstein-research-data")
    print("=" * 70)

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    for filename, url in FILES_TO_DOWNLOAD.items():
        local_path = os.path.join(DOWNLOAD_DIR, filename)
        if os.path.exists(local_path):
            size_mb = os.path.getsize(local_path) / (1024 * 1024)
            print(f"  [SKIP] {filename} already exists ({size_mb:.1f} MB)")
            continue

        print(f"  Downloading {filename}...")
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "ResearchAnalyst/1.0")
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
                with open(local_path, "wb") as f:
                    f.write(data)
                size_mb = len(data) / (1024 * 1024)
                print(f"    ✓ {size_mb:.2f} MB")
        except Exception as e:
            print(f"    ✗ FAILED: {str(e)[:200]}")
            continue

    print()
    # Verify
    for filename in FILES_TO_DOWNLOAD:
        local_path = os.path.join(DOWNLOAD_DIR, filename)
        if os.path.exists(local_path):
            size = os.path.getsize(local_path)
            print(f"  ✓ {filename}: {size:,} bytes")
        else:
            print(f"  ✗ {filename}: MISSING")

# ============================================================
# Lambda invocation helpers
# ============================================================

def invoke_lambda(payload, timeout=120):
    """Invoke the CaseFiles Lambda with a payload."""
    resp = lam.invoke(
        FunctionName=LAMBDA_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload),
    )
    return json.loads(resp["Payload"].read().decode())


def gremlin(query, timeout=120):
    """Execute a Gremlin query via Lambda."""
    result = invoke_lambda({
        "action": "gremlin_query",
        "case_id": CASE_ID,
        "query": query,
        "timeout": timeout,
        "max_result_len": 2000,
    })
    if "error" in result:
        return None, result["error"][:300]
    return result.get("result"), None


# ============================================================
# Load Knowledge Graph into Neptune
# ============================================================

def load_knowledge_graph(dry_run=False):
    """Load knowledge_graph_entities.json and knowledge_graph_relationships.json
    into Neptune via Gremlin.
    
    Their format:
    entities: [{id, name, entity_type, source_id, aliases, metadata}]
    relationships: [{id, source_entity_id, target_entity_id, relationship_type, weight, metadata}]
    """
    print("=" * 70)
    print("PHASE 2: Load Knowledge Graph → Neptune")
    print("=" * 70)

    # Load entities
    ent_path = os.path.join(DOWNLOAD_DIR, "knowledge_graph_entities.json")
    rel_path = os.path.join(DOWNLOAD_DIR, "knowledge_graph_relationships.json")

    if not os.path.exists(ent_path):
        print("  ERROR: knowledge_graph_entities.json not found. Run --download first.")
        return

    with open(ent_path, "r", encoding="utf-8") as f:
        kg_entities = json.load(f)
    with open(rel_path, "r", encoding="utf-8") as f:
        kg_relationships = json.load(f)

    print(f"  Entities: {len(kg_entities)}")
    print(f"  Relationships: {len(kg_relationships)}")

    if dry_run:
        print("\n  [DRY RUN] Would load these into Neptune.")
        print("\n  Sample entities:")
        for e in kg_entities[:5]:
            print(f"    {e.get('name', '?')} ({e.get('entity_type', '?')})")
        print("\n  Sample relationships:")
        for r in kg_relationships[:5]:
            print(f"    entity_{r.get('source_entity_id','?')} → entity_{r.get('target_entity_id','?')} ({r.get('relationship_type', '?')})")
        return

    # Check current Neptune state
    label = f"Entity_{CASE_ID}"
    count, err = gremlin(f"g.V().hasLabel('{label}').count()")
    print(f"  Current Neptune nodes for this case: {count}")

    # Build entity ID → name lookup for edge creation
    entity_id_to_name = {}
    entity_node_ids = {}  # name → neptune_node_id

    # Load entities as Neptune nodes
    print(f"\n  Loading {len(kg_entities)} entities into Neptune...")
    created = 0
    errors = 0

    for i, ent in enumerate(kg_entities):
        name = ent.get("name", "")
        if not name or len(name) < 2:
            continue

        ent_id = ent.get("id")
        entity_id_to_name[ent_id] = name

        etype = ENTITY_TYPE_MAP.get(ent.get("entity_type", ""), "person")
        escaped_name = name.replace("'", "\\'").replace("\\", "\\\\")
        # Sanitize node ID: only alphanumeric, underscore, dash
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)[:150]
        node_id = f"rh_{ent_id}_{safe_name}"
        entity_node_ids[name] = node_id

        # Parse metadata if present
        metadata = ent.get("metadata", "{}")
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except Exception:
                metadata = {}

        q = (
            f"g.addV('{label}')"
            f".property(id, '{node_id}')"
            f".property('canonical_name', '{escaped_name}')"
            f".property('entity_type', '{etype}')"
            f".property('confidence', 0.95)"
            f".property('occurrence_count', 1)"
            f".property('case_file_id', '{CASE_ID}')"
            f".property('source', 'rhowardstone_kg')"
        )

        result, err_msg = gremlin(q)
        if err_msg:
            errors += 1
            if errors <= 5:
                print(f"    Error: {err_msg[:150]}")
        else:
            created += 1

        if (i + 1) % 50 == 0:
            print(f"    Progress: {i+1}/{len(kg_entities)} "
                  f"({created} created, {errors} errors)")
        time.sleep(0.05)  # Rate limit

    print(f"\n  Nodes created: {created}, Errors: {errors}")

    # Load relationships as Neptune edges
    print(f"\n  Loading {len(kg_relationships)} relationships into Neptune...")
    edges_created = 0
    edges_errors = 0
    edges_skipped = 0

    for i, rel in enumerate(kg_relationships):
        source_id = rel.get("source_entity_id")
        target_id = rel.get("target_entity_id")
        rtype = rel.get("relationship_type", "associated_with")
        weight = rel.get("weight", 1)

        # Resolve entity IDs to names, then to Neptune node IDs
        source_name = entity_id_to_name.get(source_id, "")
        target_name = entity_id_to_name.get(target_id, "")
        from_id = entity_node_ids.get(source_name)
        to_id = entity_node_ids.get(target_name)

        if not from_id or not to_id:
            edges_skipped += 1
            continue

        mapped_rtype = RELATIONSHIP_TYPE_MAP.get(rtype, "co-occurrence")
        escaped_rtype = rtype.replace("'", "\\'")
        # Normalize weight to 0-1 range (their weights can be large counts)
        norm_weight = min(1.0, weight / 1000) if weight > 1 else weight

        # Use __.V() anonymous traversal for Neptune edge creation
        q = (
            f"g.V('{from_id}')"
            f".addE('related_to')"
            f".to(__.V('{to_id}'))"
            f".property('relationship_type', '{mapped_rtype}')"
            f".property('original_type', '{escaped_rtype}')"
            f".property('confidence', {norm_weight:.3f})"
            f".property('source', 'rhowardstone_kg')"
        )

        result, err_msg = gremlin(q)
        if err_msg:
            edges_errors += 1
            if edges_errors <= 5:
                print(f"    Edge error: {err_msg[:150]}")
        else:
            edges_created += 1

        if (i + 1) % 100 == 0:
            print(f"    Progress: {i+1}/{len(kg_relationships)} "
                  f"({edges_created} edges, {edges_errors} errors, {edges_skipped} skipped)")
        time.sleep(0.05)

    print(f"\n  Edges created: {edges_created}, Errors: {edges_errors}, Skipped: {edges_skipped}")

    # Final count
    count, _ = gremlin(f"g.V().hasLabel('{label}').count()")
    edge_count, _ = gremlin(f"g.E().count()")
    print(f"\n  Final Neptune state:")
    print(f"    Nodes: {count}")
    print(f"    Edges: {edge_count}")

# ============================================================
# Load Persons Registry into Aurora
# ============================================================

def load_persons_registry(dry_run=False):
    """Load persons_registry.json into Aurora entities table.
    
    Their format:
    [{name, aliases: [], category, search_terms: [], description}]
    """
    print("=" * 70)
    print("PHASE 3: Load Persons Registry → Aurora")
    print("=" * 70)

    path = os.path.join(DOWNLOAD_DIR, "persons_registry.json")
    if not os.path.exists(path):
        print("  ERROR: persons_registry.json not found. Run --download first.")
        return

    with open(path, "r", encoding="utf-8") as f:
        persons = json.load(f)

    print(f"  Persons: {len(persons)}")

    # Filter out FOIA redaction codes and junk entries
    junk_patterns = ["(b)", "(6)", "(7)", "*D -", "*F -", "CBP", "(MARHAM", "(ROXEBY"]
    clean_persons = []
    filtered_out = 0
    for p in persons:
        name = p.get("name", "")
        # Skip entries that start with redaction codes or are too short
        if len(name) < 3:
            filtered_out += 1
            continue
        if any(name.startswith(jp) for jp in junk_patterns):
            filtered_out += 1
            continue
        if name.startswith("(") and ")" in name[:10]:
            filtered_out += 1
            continue
        if name.startswith("*"):
            filtered_out += 1
            continue
        clean_persons.append(p)

    print(f"  After filtering junk: {len(clean_persons)} (removed {filtered_out} noise entries)")
    persons = clean_persons

    if dry_run:
        print("\n  [DRY RUN] Would load these into Aurora.")
        print("\n  Sample persons:")
        for p in persons[:10]:
            aliases = p.get("aliases", [])
            print(f"    {p.get('name', '?')} ({p.get('category', '?')}) "
                  f"aliases: {aliases[:3]}")
        return

    # Batch insert via Lambda
    batch_size = 200
    total_inserted = 0
    total_errors = 0

    for i in range(0, len(persons), batch_size):
        batch = persons[i:i + batch_size]
        entities_payload = []

        for person in batch:
            name = person.get("name", "")
            if not name or len(name) < 2:
                continue

            entities_payload.append({
                "case_id": CASE_ID,
                "document_id": "",
                "name": name[:255],
                "type": "person",
                "confidence": 0.95,
            })

            # Also insert aliases as separate entities linked to main
            for alias in person.get("aliases", [])[:5]:
                if alias and len(alias) >= 2 and alias != name:
                    entities_payload.append({
                        "case_id": CASE_ID,
                        "document_id": "",
                        "name": alias[:255],
                        "type": "person",
                        "confidence": 0.80,
                    })

        if entities_payload:
            result = invoke_lambda({
                "action": "insert_entities_from_batch",
                "entities": entities_payload,
            })
            inserted = result.get("inserted", 0)
            total_inserted += inserted
            if "error" in result:
                total_errors += 1
                if total_errors <= 3:
                    print(f"    Error: {result['error'][:200]}")

        if (i + batch_size) % 500 == 0:
            print(f"    Progress: {i + batch_size}/{len(persons)} "
                  f"({total_inserted} inserted)")

    print(f"\n  Persons loaded: {total_inserted}")
    print(f"  Errors: {total_errors}")

# ============================================================
# Load Extracted Entities into Aurora
# ============================================================

def load_extracted_entities(dry_run=False):
    """Load extracted_entities_filtered.json into Aurora.
    
    Their format (dict with category keys):
    {metadata, names: [{entity_value, entity_type, document_count, efta_numbers}],
     organizations: [...], emails: [...], phones: [...], amounts: [...]}
    
    8,085 entities: 3,881 names, 2,238 phones, 1,489 amounts, 357 emails, 116 orgs
    """
    print("=" * 70)
    print("PHASE 4: Load Extracted Entities → Aurora")
    print("=" * 70)

    path = os.path.join(DOWNLOAD_DIR, "extracted_entities_filtered.json")
    if not os.path.exists(path):
        print("  ERROR: extracted_entities_filtered.json not found. Run --download first.")
        return

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Flatten all categories into a single list
    category_to_type = {
        "names": "person",
        "organizations": "organization",
        "emails": "email",
        "phones": "phone_number",
        "amounts": "financial_amount",
    }

    all_entities = []
    for category, our_type in category_to_type.items():
        items = data.get(category, [])
        print(f"  {category}: {len(items)} entities")
        for item in items:
            all_entities.append({
                "name": item.get("entity_value", ""),
                "type": our_type,
                "count": item.get("document_count", 1),
                "efta_numbers": item.get("efta_numbers", []),
            })

    print(f"  TOTAL: {len(all_entities)} entities to load")

    if dry_run:
        print("\n  [DRY RUN] Would load these into Aurora.")
        print("\n  Sample entities:")
        for e in all_entities[:10]:
            print(f"    {e['name'][:40]} ({e['type']}) "
                  f"in {e['count']} docs")
        return

    # Batch insert via Lambda
    batch_size = 500
    total_inserted = 0
    total_errors = 0

    for i in range(0, len(all_entities), batch_size):
        batch = all_entities[i:i + batch_size]
        entities_payload = []

        for ent in batch:
            name = ent["name"]
            if not name or len(name) < 2:
                continue
            # Higher confidence for entities in more documents
            confidence = min(0.99, 0.5 + (ent["count"] / 100))

            entities_payload.append({
                "case_id": CASE_ID,
                "document_id": "",
                "name": name[:255],
                "type": ent["type"],
                "confidence": round(confidence, 2),
            })

        if entities_payload:
            result = invoke_lambda({
                "action": "insert_entities_from_batch",
                "entities": entities_payload,
            })
            inserted = result.get("inserted", 0)
            total_inserted += inserted
            if "error" in result:
                total_errors += 1
                if total_errors <= 3:
                    print(f"    Error: {result['error'][:200]}")

        if (i + batch_size) % 2000 == 0:
            print(f"    Progress: {i + batch_size}/{len(all_entities)} "
                  f"({total_inserted} inserted)")

    print(f"\n  Entities loaded: {total_inserted}")
    print(f"  Errors: {total_errors}")

# ============================================================
# Load into OpenSearch (taxonomy scoring)
# ============================================================

def load_to_opensearch(dry_run=False):
    """Apply taxonomy scoring to the knowledge graph entities and
    load embeddings into OpenSearch for k-NN search.
    
    This is the ONLY step that costs money (~$0.05 for 524 entities).
    """
    print("=" * 70)
    print("PHASE 5: Taxonomy Score + OpenSearch Index")
    print("=" * 70)

    ent_path = os.path.join(DOWNLOAD_DIR, "knowledge_graph_entities.json")
    if not os.path.exists(ent_path):
        print("  ERROR: knowledge_graph_entities.json not found.")
        return

    with open(ent_path, "r", encoding="utf-8") as f:
        kg_entities = json.load(f)

    print(f"  Entities to embed: {len(kg_entities)}")
    print(f"  Estimated cost: ~${len(kg_entities) * 0.0001:.4f}")

    if dry_run:
        print("\n  [DRY RUN] Would embed and index these in OpenSearch.")
        return

    # For each entity with a description, create embedding and index
    bedrock = boto3.client("bedrock-runtime", region_name=REGION)
    indexed = 0
    errors = 0

    for i, ent in enumerate(kg_entities):
        name = ent.get("name", "")
        etype = ent.get("entity_type", "")
        
        # Parse metadata for description
        metadata = ent.get("metadata", "{}")
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except Exception:
                metadata = {}

        aliases = ent.get("aliases") or []
        if isinstance(aliases, str):
            try:
                aliases = json.loads(aliases)
            except Exception:
                aliases = []

        # Build searchable text for this entity
        text_parts = [name]
        if metadata.get("occupation"):
            text_parts.append(f"Occupation: {metadata['occupation']}")
        if metadata.get("person_type"):
            text_parts.append(f"Role: {metadata['person_type']}")
        if aliases:
            text_parts.append(f"Also known as: {', '.join(aliases[:5])}")
        if etype:
            text_parts.append(f"Type: {etype}")

        text = ". ".join(text_parts)
        if len(text) < 10:
            continue

        try:
            # Generate embedding
            resp = bedrock.invoke_model(
                modelId="amazon.titan-embed-text-v2:0",
                contentType="application/json",
                accept="application/json",
                body=json.dumps({"inputText": text[:8000]}),
            )
            embedding = json.loads(resp["body"].read())["embedding"]

            # Index via Lambda (OpenSearch)
            result = invoke_lambda({
                "action": "index_document_opensearch",
                "case_id": CASE_ID,
                "document": {
                    "document_id": f"kg_{name.replace(' ', '_')[:50]}",
                    "text": text,
                    "embedding": embedding,
                    "metadata": {
                        "entity_name": name,
                        "entity_type": etype,
                        "source": "rhowardstone_kg",
                    },
                },
            })

            if "error" not in result:
                indexed += 1
            else:
                errors += 1

        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"    Error on {name}: {str(e)[:100]}")

        if (i + 1) % 100 == 0:
            print(f"    Progress: {i+1}/{len(kg_entities)} "
                  f"({indexed} indexed, {errors} errors)")
        time.sleep(0.01)

    print(f"\n  OpenSearch indexed: {indexed}")
    print(f"  Errors: {errors}")
    print(f"  Cost: ~${indexed * 0.0001:.4f}")

# ============================================================
# Summary + Stats
# ============================================================

def print_summary():
    """Print what was loaded and next steps."""
    print()
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║  RHOWARDSTONE DATA LOAD COMPLETE                               ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print()
    print("  What was loaded:")
    print("  ─────────────────")
    print("  • Knowledge Graph → Neptune")
    print("    524 curated entities + 2,096 typed relationships")
    print("    (people, shell companies, orgs, properties, aircraft)")
    print()
    print("  • Persons Registry → Aurora")
    print("    1,538 people with aliases (merged from 9 sources)")
    print()
    print("  • Extracted Entities → Aurora")
    print("    8,085 entities (names, phones, amounts, emails, orgs)")
    print("    Each appearing in 2+ documents (pre-filtered)")
    print()
    print("  • Entity Embeddings → OpenSearch (optional)")
    print("    k-NN searchable entity descriptions")
    print()
    print("  Cost: ~$0.05 (embedding only, all else free)")
    print()
    print("  Coverage: ALL 12 DOJ datasets (1.39M docs, 2.77M pages)")
    print("  vs. our previous: 3,804 files from DataSet1-5 only")
    print()
    print("  ─────────────────")
    print("  NEXT STEPS:")
    print("  1. Run taxonomy scoring against these entities")
    print("  2. Download full_text_corpus.db (2.3GB) for full-text search")
    print("  3. Run tiered pipeline on the full corpus for new discoveries")
    print("  4. Check Neptune graph explorer for network visualization")


# ============================================================
# Main / CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Download rhowardstone/Epstein-research-data and load into Aurora + Neptune"
    )
    parser.add_argument("--download", action="store_true", help="Download files from GitHub")
    parser.add_argument("--load", action="store_true", help="Load into Aurora + Neptune")
    parser.add_argument("--all", action="store_true", help="Download + Load")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument(
        "--skip-opensearch", action="store_true",
        help="Skip OpenSearch embedding (saves $0.05)"
    )
    args = parser.parse_args()

    if not (args.download or args.load or args.all):
        parser.print_help()
        print("\n  Example: python scripts/load_rhowardstone_data.py --all --dry-run")
        return

    print()
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║  LOAD PRE-PROCESSED EPSTEIN DATA (rhowardstone)                ║")
    print("║  524 entities, 2,096 relationships, 1,538 persons              ║")
    print("║  Coverage: ALL 12 DOJ datasets (1.39M documents)               ║")
    print("║  Cost: ~$0.05 (embedding only)                                 ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print()

    if args.download or args.all:
        download_files()
        print()

    if args.load or args.all:
        load_knowledge_graph(dry_run=args.dry_run)
        print()
        load_persons_registry(dry_run=args.dry_run)
        print()
        load_extracted_entities(dry_run=args.dry_run)
        print()
        if not args.skip_opensearch:
            load_to_opensearch(dry_run=args.dry_run)
            print()

    if not args.dry_run and (args.load or args.all):
        print_summary()


if __name__ == "__main__":
    main()
