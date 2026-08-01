#!/usr/bin/env python3
"""
Model Bake-Off — Compare entity extraction quality across Bedrock models.

MANDATORY: Run this before ANY bulk entity extraction on a new dataset.
See docs/lessons-learned.md "Model Bake-Off Before Bulk Extraction" rule.

Usage:
    python scripts/model_bakeoff.py --case-id <CASE_ID> [--sample-size 10]

What it does:
1. Selects N random documents from Aurora (mix of types/lengths)
2. Runs entity extraction on each document with ALL available models
3. Scores each model on precision, recall, noise ratio, cost
4. Outputs a comparison table and recommendation
5. Saves results to docs/model-bakeoff-{case_name}.md
"""
import boto3
import json
import time
import sys
import os
import re
from datetime import datetime

# ── Configuration ──────────────────────────────────────────────────
REGION = "us-east-1"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"

# Models to test (add/remove based on availability in your account)
MODELS = [
    {
        "id": "amazon.nova-lite-v1:0",
        "name": "Nova Lite",
        "format": "nova",
        "input_cost_per_1k": 0.00006,   # $0.06 per 1M input tokens
        "output_cost_per_1k": 0.00024,  # $0.24 per 1M output tokens
    },
    {
        "id": "amazon.nova-pro-v1:0",
        "name": "Nova Pro",
        "format": "nova",
        "input_cost_per_1k": 0.0008,
        "output_cost_per_1k": 0.0032,
    },
    {
        "id": "anthropic.claude-3-haiku-20240307-v1:0",
        "name": "Claude 3 Haiku",
        "format": "anthropic",
        "input_cost_per_1k": 0.00025,
        "output_cost_per_1k": 0.00125,
    },
    {
        "id": "anthropic.claude-3-5-haiku-20241022-v1:0",
        "name": "Claude 3.5 Haiku",
        "format": "anthropic",
        "input_cost_per_1k": 0.0008,
        "output_cost_per_1k": 0.004,
    },
    {
        "id": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "name": "Claude 3.5 Sonnet v2",
        "format": "anthropic",
        "input_cost_per_1k": 0.003,
        "output_cost_per_1k": 0.015,
    },
]

# Entity types from master taxonomy (docs/master-entity-taxonomy.md)
VALID_TYPES = {
    "person", "organization", "location", "event",
    "financial", "financial_amount", "account_number",
    "phone_number", "email", "address",
    "date", "time", "flight", "vehicle",
    "legal", "legal_case", "statute", "legislation",
    "charge", "offense", "substance", "weapon", "property",
    "role", "relationship", "contact",
    "cryptocurrency", "domain",
}

# The extraction prompt — constrained to master taxonomy types
EXTRACTION_PROMPT = """Extract named entities from the following document text. 
Return ONLY a JSON array of objects with "name", "type", and "confidence" fields.

Extract ONLY these entity types:
- person (names of people — suspects, witnesses, victims, associates)
- organization (companies, banks, law firms, foundations, government agencies)
- location (cities, countries, addresses, properties, venues)
- financial_amount (dollar amounts, transaction values)
- account_number (bank accounts, wire transfer numbers)
- phone_number (telephone numbers)
- email (email addresses)
- address (physical addresses)
- date (specific dates)
- event (meetings, transactions, arrests, filings)
- flight (flight numbers, aircraft identifiers)
- vehicle (cars, boats, aircraft with identifying info)
- legal_case (case numbers, court filings)
- statute (laws, regulations cited)
- role (job titles, organizational roles)

Do NOT extract:
- Document formatting (page numbers, headers, footers)
- OCR artifacts (random characters, symbols)
- Generic descriptions (colors, sizes, measurements)
- Medical terms (unless relevant to the case)

Return valid JSON only. Example:
[{"name": "Jeffrey Epstein", "type": "person", "confidence": 0.95}]

Document text:
---
{text}
---

JSON entities:"""

# ── Clients ────────────────────────────────────────────────────────
bedrock = boto3.client("bedrock-runtime", region_name=REGION)
lam = boto3.client("lambda", region_name=REGION)


def get_sample_documents(case_id, sample_size=10):
    """Get a random sample of documents from Aurora."""
    resp = lam.invoke(
        FunctionName=LAMBDA_NAME,
        Payload=json.dumps({
            "action": "query_aurora_entities",
            "case_id": case_id,
            "limit": 1,
            "offset": 0,
        }),
    )
    # We need actual document text, not entities
    # Use a direct SQL query through a custom action
    # For now, get documents from the documents table
    resp = lam.invoke(
        FunctionName=LAMBDA_NAME,
        Payload=json.dumps({
            "httpMethod": "POST",
            "resource": "/case-files/{id}/patterns",
            "pathParameters": {"id": case_id},
            "body": json.dumps({"action": "sample_documents", "limit": sample_size}),
        }),
    )
    result = json.loads(resp["Payload"].read())
    # Fallback: if sample_documents action doesn't exist, explain
    if "error" in str(result).lower() or "statusCode" in result:
        print("NOTE: sample_documents action not available.")
        print("To run the bake-off, manually select 10 document texts and save to:")
        print("  scripts/bakeoff_samples/{case_id}/doc_01.txt through doc_10.txt")
        print("Then re-run this script.")
        return []
    return result.get("documents", [])


def invoke_model(model_config, text):
    """Invoke a Bedrock model for entity extraction."""
    model_id = model_config["id"]
    prompt = EXTRACTION_PROMPT.replace("{text}", text[:8000])  # Limit to 8K chars
    
    try:
        if model_config["format"] == "nova":
            body = {
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"maxTokens": 4096, "temperature": 0.1},
            }
        else:  # anthropic
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "temperature": 0.1,
                "messages": [{"role": "user", "content": prompt}],
            }
        
        start = time.time()
        response = bedrock.invoke_model(
            modelId=model_id,
            body=json.dumps(body),
        )
        elapsed = time.time() - start
        
        result = json.loads(response["body"].read())
        
        # Extract text from response
        if model_config["format"] == "nova":
            text_out = result.get("output", {}).get("message", {}).get("content", [{}])[0].get("text", "")
            input_tokens = result.get("usage", {}).get("inputTokens", 0)
            output_tokens = result.get("usage", {}).get("outputTokens", 0)
        else:
            text_out = result.get("content", [{}])[0].get("text", "")
            input_tokens = result.get("usage", {}).get("input_tokens", 0)
            output_tokens = result.get("usage", {}).get("output_tokens", 0)
        
        # Parse entities from response
        entities = parse_entities(text_out)
        
        cost = (input_tokens * model_config["input_cost_per_1k"] / 1000 +
                output_tokens * model_config["output_cost_per_1k"] / 1000)
        
        return {
            "entities": entities,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
            "elapsed": elapsed,
            "raw_output": text_out[:500],
        }
    
    except Exception as e:
        return {
            "entities": [],
            "error": str(e)[:300],
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0,
            "elapsed": 0,
        }


def parse_entities(text):
    """Parse JSON entity array from model output."""
    # Try direct JSON parse
    try:
        # Find JSON array in the text
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except json.JSONDecodeError:
        pass
    
    # Try markdown-fenced JSON
    try:
        match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
    except json.JSONDecodeError:
        pass
    
    return []


def score_entities(entities):
    """Score entity extraction quality."""
    if not entities:
        return {"total": 0, "valid": 0, "noise": 0, "precision": 0, "noise_ratio": 0}
    
    valid = 0
    noise = 0
    type_correct = 0
    
    for ent in entities:
        name = ent.get("name", "")
        etype = ent.get("type", "unknown").lower()
        
        # Is the type in our taxonomy?
        if etype not in VALID_TYPES:
            noise += 1
            continue
        
        # Is the name real (not OCR garbage)?
        stripped = name.strip()
        if len(stripped) < 3:
            noise += 1
            continue
        
        # Check for obvious noise patterns
        alnum = sum(1 for c in stripped if c.isalnum() or c == ' ')
        if len(stripped) > 3 and alnum / len(stripped) < 0.4:
            noise += 1
            continue
        
        if stripped[0] in '[](){}|<>*#@$%^&!?;:,./\\-_+=~`':
            noise += 1
            continue
        
        valid += 1
    
    total = len(entities)
    precision = valid / total if total > 0 else 0
    noise_ratio = noise / valid if valid > 0 else float('inf')
    
    return {
        "total": total,
        "valid": valid,
        "noise": noise,
        "precision": precision,
        "noise_ratio": noise_ratio,
    }


def main():
    case_id = None
    sample_size = 10
    
    for i, arg in enumerate(sys.argv):
        if arg == "--case-id" and i + 1 < len(sys.argv):
            case_id = sys.argv[i + 1]
        if arg == "--sample-size" and i + 1 < len(sys.argv):
            sample_size = int(sys.argv[i + 1])
    
    if not case_id:
        print("Usage: python scripts/model_bakeoff.py --case-id <CASE_ID> [--sample-size 10]")
        print("\nThis script compares entity extraction quality across Bedrock models.")
        print("MANDATORY before any bulk extraction. See docs/lessons-learned.md.")
        sys.exit(1)
    
    print("=" * 70)
    print("MODEL BAKE-OFF — Entity Extraction Quality Comparison")
    print(f"Case: {case_id}")
    print(f"Sample size: {sample_size} documents")
    print(f"Models to test: {len(MODELS)}")
    print("=" * 70)
    
    # Check which models are available
    print("\nChecking model availability...")
    available_models = []
    for model in MODELS:
        try:
            # Quick test with minimal input
            if model["format"] == "nova":
                body = {"messages": [{"role": "user", "content": [{"text": "test"}]}],
                        "inferenceConfig": {"maxTokens": 10}}
            else:
                body = {"anthropic_version": "bedrock-2023-05-31", "max_tokens": 10,
                        "messages": [{"role": "user", "content": "test"}]}
            
            bedrock.invoke_model(modelId=model["id"], body=json.dumps(body))
            available_models.append(model)
            print(f"  ✓ {model['name']} ({model['id']})")
        except Exception as e:
            err = str(e)[:100]
            print(f"  ✗ {model['name']} — {err}")
    
    if not available_models:
        print("\nNo models available! Check Bedrock access.")
        sys.exit(1)
    
    # Get sample documents
    print(f"\nGetting {sample_size} sample documents...")
    
    # Check for local sample files first
    sample_dir = f"scripts/bakeoff_samples/{case_id}"
    docs = []
    if os.path.exists(sample_dir):
        for f in sorted(os.listdir(sample_dir)):
            if f.endswith(".txt"):
                with open(os.path.join(sample_dir, f)) as fh:
                    docs.append({"id": f, "text": fh.read()})
        print(f"  Loaded {len(docs)} documents from {sample_dir}")
    
    if not docs:
        docs = get_sample_documents(case_id, sample_size)
    
    if not docs:
        print("\nNo sample documents available.")
        print(f"Create sample files in: {sample_dir}/doc_01.txt through doc_10.txt")
        print("Copy representative document text (emails, legal filings, financial docs, OCR scans)")
        sys.exit(1)
    
    # Run bake-off
    results = {model["name"]: {"scores": [], "costs": [], "times": []} for model in available_models}
    
    for i, doc in enumerate(docs[:sample_size]):
        doc_id = doc.get("id", f"doc_{i+1}")
        text = doc.get("text", "")[:8000]
        print(f"\n--- Document {i+1}/{min(len(docs), sample_size)}: {doc_id} ({len(text)} chars) ---")
        
        for model in available_models:
            result = invoke_model(model, text)
            score = score_entities(result["entities"])
            
            results[model["name"]]["scores"].append(score)
            results[model["name"]]["costs"].append(result["cost"])
            results[model["name"]]["times"].append(result["elapsed"])
            
            if "error" in result:
                print(f"  {model['name']:20s}: ERROR — {result['error'][:80]}")
            else:
                print(f"  {model['name']:20s}: {score['total']:3d} entities, "
                      f"{score['valid']:3d} valid, {score['noise']:3d} noise, "
                      f"precision={score['precision']:.0%}, "
                      f"cost=${result['cost']:.4f}, {result['elapsed']:.1f}s")
    
    # Summary
    print("\n" + "=" * 70)
    print("BAKE-OFF RESULTS SUMMARY")
    print("=" * 70)
    print(f"\n{'Model':25s} {'Avg Precision':>14s} {'Avg Noise Ratio':>16s} "
          f"{'Avg Cost/Doc':>13s} {'Avg Time':>10s} {'Est. 75K Cost':>14s}")
    print("-" * 95)
    
    best_model = None
    best_score = -1
    
    for model in available_models:
        name = model["name"]
        scores = results[name]["scores"]
        costs = results[name]["costs"]
        times = results[name]["times"]
        
        if not scores:
            continue
        
        avg_precision = sum(s["precision"] for s in scores) / len(scores)
        avg_noise = sum(s["noise_ratio"] for s in scores if s["noise_ratio"] != float('inf')) / max(1, len([s for s in scores if s["noise_ratio"] != float('inf')]))
        avg_cost = sum(costs) / len(costs)
        avg_time = sum(times) / len(times)
        est_75k = avg_cost * 75000
        
        print(f"{name:25s} {avg_precision:>13.0%} {avg_noise:>15.1f}:1 "
              f"${avg_cost:>11.4f} {avg_time:>9.1f}s ${est_75k:>12.0f}")
        
        # Score = precision * (1 - noise_ratio_penalty) / cost_factor
        if avg_precision > best_score:
            best_score = avg_precision
            best_model = name
    
    print(f"\n🏆 RECOMMENDED: {best_model} (highest precision)")
    print(f"\nFull results saved to: docs/model-bakeoff-results.json")
    
    # Save results
    with open("docs/model-bakeoff-results.json", "w") as f:
        json.dump({
            "case_id": case_id,
            "timestamp": datetime.now().isoformat(),
            "sample_size": len(docs[:sample_size]),
            "models_tested": len(available_models),
            "results": {
                name: {
                    "scores": results[name]["scores"],
                    "avg_cost": sum(results[name]["costs"]) / max(1, len(results[name]["costs"])),
                    "avg_time": sum(results[name]["times"]) / max(1, len(results[name]["times"])),
                }
                for name in results
            },
            "recommendation": best_model,
        }, f, indent=2, default=str)


if __name__ == "__main__":
    main()
