#!/usr/bin/env python3
"""
Quick Model Bake-Off — Test entity extraction on 3 real documents from Aurora.
Compares all available Bedrock models side by side.
"""
import boto3
import json
import time
import re
from datetime import datetime

REGION = "us-east-1"
LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"

bedrock = boto3.client("bedrock-runtime", region_name=REGION)
lam = boto3.client("lambda", region_name=REGION)

# Constrained extraction prompt using master taxonomy
PROMPT_TEMPLATE = """Extract named entities from this document text. Return ONLY a valid JSON array.

Extract ONLY these entity types:
- person (full names of people)
- organization (companies, banks, law firms, foundations, agencies)
- location (cities, countries, addresses, properties)
- financial_amount (dollar amounts, transaction values)
- account_number (bank account numbers, wire transfer IDs)
- phone_number (telephone numbers including area code)
- email (email addresses)
- address (physical street addresses)
- date (specific dates like "January 15, 2005")
- event (meetings, transactions, arrests, court hearings)
- flight (flight numbers, aircraft tail numbers)
- vehicle (cars, boats, aircraft with make/model/plate)
- legal_case (case numbers like "Case 1:20-cr-00330")
- statute (laws cited like "18 U.S.C. § 1591")
- role (job titles, organizational roles like "pilot", "assistant")

Do NOT extract: page numbers, formatting, OCR artifacts, measurements, colors, generic words.
Return valid JSON array only. Example: [{{"name":"Jeffrey Epstein","type":"person","confidence":0.95}}]

Document:
---
{text}
---

JSON:"""


def get_sample_docs():
    """Get 3 diverse documents from Aurora via Lambda."""
    docs = []
    # Get documents with different characteristics
    for offset in [0, 1000, 5000]:
        resp = lam.invoke(
            FunctionName=LAMBDA_NAME,
            Payload=json.dumps({
                "httpMethod": "GET",
                "resource": "/case-files/{id}/documents",
                "pathParameters": {"id": CASE_ID},
                "queryStringParameters": {"limit": "1", "offset": str(offset)},
            }),
        )
        result = json.loads(resp["Payload"].read())
        body = json.loads(result.get("body", "{}")) if isinstance(result.get("body"), str) else result
        doc_list = body.get("documents", [])
        if doc_list:
            d = doc_list[0]
            text = d.get("raw_text", d.get("text", ""))
            if text and len(text) > 100:
                docs.append({
                    "id": d.get("document_id", f"doc_{offset}"),
                    "filename": d.get("filename", f"doc_{offset}"),
                    "text": text[:6000],
                    "length": len(text),
                })
    return docs


def invoke_model(model_id, model_format, text):
    """Invoke a single Bedrock model."""
    prompt = PROMPT_TEMPLATE.format(text=text[:6000])
    
    try:
        if model_format == "nova":
            body = {
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"maxTokens": 4096, "temperature": 0.1},
            }
        else:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "temperature": 0.1,
                "messages": [{"role": "user", "content": prompt}],
            }
        
        start = time.time()
        response = bedrock.invoke_model(modelId=model_id, body=json.dumps(body))
        elapsed = time.time() - start
        
        result = json.loads(response["body"].read())
        
        if model_format == "nova":
            text_out = result.get("output", {}).get("message", {}).get("content", [{}])[0].get("text", "")
            in_tok = result.get("usage", {}).get("inputTokens", 0)
            out_tok = result.get("usage", {}).get("outputTokens", 0)
        else:
            text_out = result.get("content", [{}])[0].get("text", "")
            in_tok = result.get("usage", {}).get("input_tokens", 0)
            out_tok = result.get("usage", {}).get("output_tokens", 0)
        
        # Parse entities
        entities = []
        try:
            match = re.search(r'\[.*\]', text_out, re.DOTALL)
            if match:
                entities = json.loads(match.group())
        except:
            try:
                match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', text_out, re.DOTALL)
                if match:
                    entities = json.loads(match.group(1))
            except:
                pass
        
        return {
            "entities": entities,
            "in_tokens": in_tok,
            "out_tokens": out_tok,
            "elapsed": elapsed,
            "raw": text_out[:300],
        }
    except Exception as e:
        return {"entities": [], "error": str(e)[:200], "in_tokens": 0, "out_tokens": 0, "elapsed": 0}


VALID_TYPES = {
    "person", "organization", "location", "event", "financial_amount",
    "account_number", "phone_number", "email", "address", "date",
    "flight", "vehicle", "legal_case", "statute", "role",
    "financial", "time", "legal", "charge", "substance", "weapon", "property",
}

def score(entities):
    """Score entity quality."""
    valid = 0
    noise = 0
    for e in entities:
        name = e.get("name", "").strip()
        etype = e.get("type", "").lower()
        
        if etype not in VALID_TYPES:
            noise += 1
            continue
        if len(name) < 3:
            noise += 1
            continue
        alnum = sum(1 for c in name if c.isalnum() or c == ' ')
        if len(name) > 3 and alnum / len(name) < 0.4:
            noise += 1
            continue
        if name[0] in '[](){}|<>*#@$%^&!?;:,./\\-_+=~`':
            noise += 1
            continue
        valid += 1
    
    total = len(entities)
    precision = valid / total if total > 0 else 0
    return {"total": total, "valid": valid, "noise": noise, "precision": precision}


# Models to test
MODELS = [
    ("amazon.nova-lite-v1:0", "Nova Lite", "nova", 0.00006, 0.00024),
    ("amazon.nova-pro-v1:0", "Nova Pro", "nova", 0.0008, 0.0032),
    ("anthropic.claude-3-haiku-20240307-v1:0", "Claude 3 Haiku", "anthropic", 0.00025, 0.00125),
    ("anthropic.claude-3-5-haiku-20241022-v1:0", "Claude 3.5 Haiku", "anthropic", 0.0008, 0.004),
    ("anthropic.claude-3-5-sonnet-20241022-v2:0", "Claude 3.5 Sonnet v2", "anthropic", 0.003, 0.015),
]


def main():
    print("=" * 80)
    print("MODEL BAKE-OFF — Entity Extraction Quality Test")
    print(f"Case: Epstein Main ({CASE_ID})")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 80)
    
    # Step 1: Check which models are available
    print("\nChecking model availability...")
    available = []
    for model_id, name, fmt, in_cost, out_cost in MODELS:
        try:
            if fmt == "nova":
                body = {"messages": [{"role": "user", "content": [{"text": "hi"}]}],
                        "inferenceConfig": {"maxTokens": 5}}
            else:
                body = {"anthropic_version": "bedrock-2023-05-31", "max_tokens": 5,
                        "messages": [{"role": "user", "content": "hi"}]}
            bedrock.invoke_model(modelId=model_id, body=json.dumps(body))
            available.append((model_id, name, fmt, in_cost, out_cost))
            print(f"  ✓ {name}")
        except Exception as e:
            print(f"  ✗ {name} — {str(e)[:80]}")
    
    if not available:
        print("No models available!")
        return
    
    # Step 2: Get sample documents
    print(f"\nFetching sample documents from Aurora...")
    docs = get_sample_docs()
    
    if not docs:
        print("Could not fetch documents from Aurora. Using a hardcoded sample.")
        # Use a known Epstein document excerpt as fallback
        docs = [{
            "id": "sample_1",
            "filename": "flight_log_sample.txt",
            "text": """LOLITA EXPRESS FLIGHT LOG
Date: January 22, 2002
Aircraft: N908JE (Boeing 727-31)
Pilot: Larry Visoski
Co-pilot: Larry Morrison

Passengers:
- Jeffrey Epstein
- Ghislaine Maxwell  
- Emmy Tayler
- Sarah Kellen

Route: Teterboro (TEB) → Palm Beach International (PBI)
Departure: 10:30 AM EST
Arrival: 1:45 PM EST

Note: Mr. Epstein requested catering from American Express Travel.
Contact: jeevacation@gmail.com
Phone: (212) 350-0099

Previous flight on January 20, 2002 carried passengers from 
Little St. James, U.S. Virgin Islands to New York.
Account: JP Morgan Chase #4578-2291-0034""",
            "length": 600,
        }]
    
    print(f"  Got {len(docs)} documents")
    for d in docs:
        print(f"    {d['filename']}: {d['length']} chars")
    
    # Step 3: Run each model on each document
    results = {}
    for model_id, name, fmt, in_cost, out_cost in available:
        results[name] = {"scores": [], "costs": [], "times": [], "entities_samples": []}
    
    for i, doc in enumerate(docs):
        print(f"\n{'─'*80}")
        print(f"Document {i+1}: {doc['filename']} ({len(doc['text'])} chars)")
        print(f"{'─'*80}")
        
        for model_id, name, fmt, in_cost, out_cost in available:
            r = invoke_model(model_id, fmt, doc["text"])
            
            if "error" in r:
                print(f"  {name:22s}: ERROR — {r['error'][:60]}")
                results[name]["scores"].append({"total": 0, "valid": 0, "noise": 0, "precision": 0})
                results[name]["costs"].append(0)
                results[name]["times"].append(0)
                continue
            
            s = score(r["entities"])
            cost = r["in_tokens"] * in_cost / 1000 + r["out_tokens"] * out_cost / 1000
            
            results[name]["scores"].append(s)
            results[name]["costs"].append(cost)
            results[name]["times"].append(r["elapsed"])
            
            # Show sample entities
            valid_ents = [e for e in r["entities"] 
                         if e.get("type", "").lower() in VALID_TYPES 
                         and len(e.get("name", "").strip()) >= 3]
            noise_ents = [e for e in r["entities"] if e not in valid_ents]
            
            print(f"  {name:22s}: {s['total']:3d} total, {s['valid']:3d} valid, "
                  f"{s['noise']:3d} noise, precision={s['precision']:.0%}, "
                  f"${cost:.4f}, {r['elapsed']:.1f}s")
            
            # Show top 5 valid entities
            for e in valid_ents[:5]:
                print(f"    ✓ {e['type']:18s} {e['name'][:50]}")
            # Show top 3 noise entities
            for e in noise_ents[:3]:
                print(f"    ✗ {e.get('type','?'):18s} {e.get('name','?')[:50]}")
            
            results[name]["entities_samples"].append(valid_ents[:10])
    
    # Step 4: Summary
    print(f"\n{'='*80}")
    print("BAKE-OFF SUMMARY")
    print(f"{'='*80}")
    print(f"\n{'Model':24s} {'Precision':>10s} {'Valid/Doc':>10s} {'Noise/Doc':>10s} "
          f"{'Cost/Doc':>10s} {'Time/Doc':>10s} {'75K Cost':>10s}")
    print("─" * 90)
    
    best_model = None
    best_precision = -1
    
    for model_id, name, fmt, in_cost, out_cost in available:
        r = results[name]
        n = len(r["scores"])
        if n == 0:
            continue
        
        avg_prec = sum(s["precision"] for s in r["scores"]) / n
        avg_valid = sum(s["valid"] for s in r["scores"]) / n
        avg_noise = sum(s["noise"] for s in r["scores"]) / n
        avg_cost = sum(r["costs"]) / n
        avg_time = sum(r["times"]) / n
        est_75k = avg_cost * 75000
        
        print(f"{name:24s} {avg_prec:>9.0%} {avg_valid:>9.1f} {avg_noise:>9.1f} "
              f"${avg_cost:>8.4f} {avg_time:>9.1f}s ${est_75k:>8.0f}")
        
        if avg_prec > best_precision:
            best_precision = avg_prec
            best_model = name
    
    print(f"\n🏆 RECOMMENDED: {best_model} (precision: {best_precision:.0%})")
    
    # Re-extraction time estimate
    print(f"\n{'='*80}")
    print("RE-EXTRACTION TIME ESTIMATE")
    print(f"{'='*80}")
    print(f"Documents to re-extract: 75,069")
    print(f"Method: Bedrock Batch Inference API (same as before)")
    print(f"")
    print(f"Steps:")
    print(f"  1. Generate JSONL with new prompt + best model: ~5 min (local)")
    print(f"  2. Submit batch job: ~1 min")
    print(f"  3. Bedrock processes 75K docs: ~30-60 min (same as Nova Lite)")
    print(f"  4. Load results into Aurora: ~30 min (EC2 direct, not Lambda)")
    print(f"  5. Neptune re-sync with taxonomy filter: ~4 hours (EC2)")
    print(f"")
    print(f"Total: ~5-6 hours (mostly unattended on EC2)")
    print(f"")
    print(f"NOTE: Document text is already in Aurora — no re-extraction of PDF text needed.")
    print(f"We only re-run the entity extraction (Bedrock) with the better model + constrained prompt.")
    
    # Save results
    output = {
        "timestamp": datetime.now().isoformat(),
        "case_id": CASE_ID,
        "documents_tested": len(docs),
        "models_tested": len(available),
        "recommendation": best_model,
        "results": {name: {
            "avg_precision": sum(s["precision"] for s in results[name]["scores"]) / max(1, len(results[name]["scores"])),
            "avg_cost": sum(results[name]["costs"]) / max(1, len(results[name]["costs"])),
            "avg_time": sum(results[name]["times"]) / max(1, len(results[name]["times"])),
            "est_75k_cost": sum(results[name]["costs"]) / max(1, len(results[name]["costs"])) * 75000,
        } for name in results},
    }
    
    with open("docs/model-bakeoff-epstein-main.json", "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to docs/model-bakeoff-epstein-main.json")


if __name__ == "__main__":
    main()
