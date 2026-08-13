"""
Archon Library — Cross-Cultural Deity Dialogue Generator

Generates in-character conversations between entities from different traditions
who fill the same structural role. Uses Bedrock to create investigative dialogues
that surface cross-cultural pattern questions.

Usage:
    python scripts/archon_generate_dialogue.py "Thor" "Indra"
    python scripts/archon_generate_dialogue.py "Osiris" "Baldur"
    python scripts/archon_generate_dialogue.py --auto  (picks best matches from scores)
"""

import json
import sys
import time
from pathlib import Path

import boto3
from botocore.config import Config

PROJECT_ROOT = Path(__file__).parent.parent
ARCHON_JSON = PROJECT_ROOT / "src" / "data" / "archon-library.json"
CROSSWALK_JSON = PROJECT_ROOT / "src" / "data" / "archon-crosswalk.json"
OUTPUT_DIR = PROJECT_ROOT / "src" / "data"
OUTPUT_JS = PROJECT_ROOT / "src" / "frontend" / "archon-dialogues.js"

HAIKU_MODEL = "anthropic.claude-3-haiku-20240307-v1:0"
AWS_REGION = "us-east-1"

client = boto3.client("bedrock-runtime", region_name=AWS_REGION,
                      config=Config(read_timeout=60, connect_timeout=10, retries={"max_attempts": 2}))


def find_entity(name, entities):
    """Find entity by name (case-insensitive, alias-aware)."""
    name_lower = name.lower()
    for e in entities:
        if e["name"].lower() == name_lower:
            return e
        if name_lower in [a.lower() for a in e.get("aliases", [])]:
            return e
    return None


def generate_dialogue(entity_a, entity_b, shared_pattern=None):
    """Generate an in-character dialogue between two entities from different traditions."""

    prompt = f"""You are a creative writer and comparative mythology scholar. Generate a short, engaging dialogue between two mythological figures who discover they share remarkable parallels despite coming from completely different cultures with no historical contact.

ENTITY A:
- Name: {entity_a['name']}
- Culture: {entity_a.get('culture', 'unknown')}
- Type: {entity_a.get('type', 'unknown')}
- Description: {entity_a.get('description', 'A mythological figure')}
- Aliases: {', '.join(entity_a.get('aliases', []))}

ENTITY B:
- Name: {entity_b['name']}
- Culture: {entity_b.get('culture', 'unknown')}
- Type: {entity_b.get('type', 'unknown')}
- Description: {entity_b.get('description', 'A mythological figure')}
- Aliases: {', '.join(entity_b.get('aliases', []))}

{f'SHARED PATTERN: {shared_pattern}' if shared_pattern else ''}

RULES:
1. Write 8-12 exchanges of dialogue (not too long)
2. Each entity speaks IN CHARACTER — using references to their own mythology
3. They should DISCOVER their parallels through conversation (not state them upfront)
4. The tone should be curious, respectful, slightly amazed at the similarities
5. End with an unanswered question that an investigator would want to pursue
6. After the dialogue, provide:
   - "insight": A 2-sentence investigative insight about what this convergence means
   - "questions": 3 specific research questions this dialogue raises

Return JSON:
{{"dialogue": [{{"speaker": "Name", "text": "What they say"}}], "insight": "...", "questions": ["...", "...", "..."]}}"""

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,  # Higher creativity for dialogue
    }

    resp = client.invoke_model(modelId=HAIKU_MODEL, contentType="application/json",
                               accept="application/json", body=json.dumps(body))
    text_out = json.loads(resp["body"].read().decode())["content"][0]["text"]

    # Parse JSON
    start = text_out.find("{")
    if start < 0:
        return None
    depth = 0
    end = -1
    for i in range(start, len(text_out)):
        if text_out[i] == "{": depth += 1
        elif text_out[i] == "}":
            depth -= 1
            if depth == 0: end = i; break
    if end <= start:
        return None

    import re
    raw = text_out[start:end+1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raw = re.sub(r',\s*([}\]])', r'\1', raw)
        try:
            return json.loads(raw)
        except:
            return None


def generate_top_questions(pattern_stats):
    """Generate the top 3 investigative questions from pattern scoring results."""

    prompt = f"""You are an investigative journalist specializing in comparative mythology and ancient civilizations. Based on the following pattern detection results from analyzing 266 entities across 13 independent cultural traditions, identify the 3 MOST IMPORTANT unanswered questions.

PATTERN SCORING RESULTS:
{json.dumps({k: {'name': v['name'], 'verdict': v['verdict'], 'cultures': v['cultures_represented'], 'matching': v['matching_entities']} for k, v in pattern_stats.items()}, indent=2)}

KEY FINDING: 6 of 7 patterns scored UNIVERSAL (8+ independent cultures confirm them). These cultures include Sumerian, Hebrew, Irish, Mayan, Hindu, Norse, Greek, Egyptian, Persian, and Chinese — many with ZERO historical contact.

Generate exactly 3 questions. Each should be:
- Specific and investigatable (not vague)
- Based on the statistical significance of the findings
- The kind of question that would drive a documentary or research paper

Return JSON:
{{"questions": [{{"question": "...", "why_it_matters": "...", "evidence_basis": "..."}}]}}"""

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1500,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
    }

    resp = client.invoke_model(modelId=HAIKU_MODEL, contentType="application/json",
                               accept="application/json", body=json.dumps(body))
    text_out = json.loads(resp["body"].read().decode())["content"][0]["text"]

    start = text_out.find("{")
    if start < 0: return None
    depth = 0; end = -1
    for i in range(start, len(text_out)):
        if text_out[i] == "{": depth += 1
        elif text_out[i] == "}":
            depth -= 1
            if depth == 0: end = i; break
    if end <= start: return None
    import re
    raw = text_out[start:end+1]
    try:
        return json.loads(raw)
    except:
        raw = re.sub(r',\s*([}\]])', r'\1', raw)
        return json.loads(raw)


def main():
    print("=" * 60)
    print("ARCHON — Cross-Cultural Dialogue Generator")
    print("=" * 60)

    lib = json.load(open(ARCHON_JSON, encoding="utf-8"))
    entities = lib["entities"]

    # Define compelling dialogue pairs from the crosswalk
    dialogue_pairs = [
        ("Lug", "Zeus", "Both master-of-all-arts / supreme young gods who overthrow older order"),
        ("Dagda", "Odin", "Both father-gods with magical artifacts, wisdom, and shape-shifting"),
        ("Morrigan", "Inanna", "Both war/sovereignty goddesses who descend to the underworld"),
        ("Balor", "Kronos", "Both old-generation tyrants with a prophesied death by their grandson/son"),
        ("Enoch", "Huangdi", "Both taken to heaven — one by God, one on a dragon"),
    ]

    results = {"dialogues": [], "top_questions": None, "generated": time.strftime("%Y-%m-%d %H:%M")}

    # Generate dialogues
    for name_a, name_b, pattern in dialogue_pairs:
        ent_a = find_entity(name_a, entities)
        ent_b = find_entity(name_b, entities)

        if not ent_a or not ent_b:
            print(f"  Skipping {name_a} vs {name_b} — entity not found")
            continue

        print(f"\nGenerating: {name_a} ({ent_a.get('culture','?')}) meets {name_b} ({ent_b.get('culture','?')})")
        dialogue = generate_dialogue(ent_a, ent_b, pattern)

        if dialogue:
            dialogue["entity_a"] = {"name": ent_a["name"], "culture": ent_a.get("culture", ""), "type": ent_a.get("type", "")}
            dialogue["entity_b"] = {"name": ent_b["name"], "culture": ent_b.get("culture", ""), "type": ent_b.get("type", "")}
            dialogue["shared_pattern"] = pattern
            results["dialogues"].append(dialogue)
            exchanges = len(dialogue.get("dialogue", []))
            print(f"  OK: {exchanges} exchanges, {len(dialogue.get('questions', []))} questions")
        else:
            print(f"  FAILED — no valid response")

        time.sleep(1)

    # Generate top 3 questions from pattern scores
    print("\nGenerating top 3 investigative questions...")
    scores_file = PROJECT_ROOT / "src" / "data" / "archon-pattern-scores.json"
    if scores_file.exists():
        scores = json.load(open(scores_file, encoding="utf-8"))
        questions = generate_top_questions(scores.get("pattern_stats", {}))
        if questions:
            results["top_questions"] = questions
            print(f"  OK: {len(questions.get('questions', []))} questions generated")

    # Save
    output_path = OUTPUT_DIR / "archon-dialogues.json"
    json.dump(results, open(output_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"\nWrote: {output_path}")

    # Frontend JS
    js = f"// Archon Dialogues - Generated {time.strftime('%Y-%m-%d')}\n"
    js += f"const ARCHON_DIALOGUES = {json.dumps(results, indent=2, ensure_ascii=False)};\n"
    open(OUTPUT_JS, "w", encoding="utf-8").write(js)
    print(f"Wrote: {OUTPUT_JS}")

    # Print summary
    print(f"\n{'='*60}")
    print(f"Generated {len(results['dialogues'])} dialogues")
    if results["top_questions"]:
        print(f"\nTOP 3 INVESTIGATIVE QUESTIONS:")
        for i, q in enumerate(results["top_questions"].get("questions", []), 1):
            print(f"  {i}. {q['question']}")
            print(f"     Why: {q['why_it_matters']}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
