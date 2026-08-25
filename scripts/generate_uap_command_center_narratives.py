"""
Generate AI narratives for the UAP Command Center module.
Run once to build the static narrative JS file. Re-run when uap-command-data.js changes.
Estimated cost: ~$0.10-0.20 for ~20 Bedrock calls (Nova Pro).

ANALYTICAL INTEGRITY (no embellishment):
  Narratives are grounded ONLY in uap-command-data.js. The prompts forbid inventing
  cases, names, dates, or places. A post-generation validator (validate_grounding)
  rejects any output containing proper nouns / 4-digit years / place-like tokens that
  do not appear in the source data. Rejected output is retried once at temperature 0,
  then blanked so the UI falls back to data-derived content rather than showing
  fabricated claims.

Follows the AI Investigation UI Standard: static generation, no live Bedrock calls
in the browser. Produces src/frontend/uap-command-center-narratives.js with:
    UAP_BRIEFS      — AI Intelligence Brief (hook -> evidence -> implication)
    UAP_MISSIONS    — Research missions for non-proven typologies
    UAP_CHAPTERS    — Documentary chapters per tier
    UAP_CONNECTIONS — Narrated network-edge explanations

Usage:
    python scripts/generate_uap_command_center_narratives.py
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

import boto3

MODEL_ID = "us.amazon.nova-pro-v1:0"
REGION = "us-east-1"
MAX_TOKENS = 600
TEMPERATURE = 0.0  # factual consistency — no creative drift

PROJECT_ROOT = Path(__file__).parent.parent
DATA_FILE = PROJECT_ROOT / "src" / "frontend" / "uap-command-data.js"
OUTPUT_FILE = PROJECT_ROOT / "src" / "frontend" / "uap-command-center-narratives.js"

# Shared grounding clause prepended to every prompt.
GROUNDING_RULES = (
    "STRICT ANALYTICAL INTEGRITY RULES — follow exactly:\n"
    "- Use ONLY the data provided in this prompt. Do not add outside knowledge.\n"
    "- Do NOT invent or reference specific real-world cases, incidents, operations, "
    "locations, dates, years, agencies, or named people. If it is not in the data, it does not exist.\n"
    "- Do NOT name individuals (no 'Dr. X', no witnesses by name).\n"
    "- Describe patterns generically using the signature descriptions and counts given.\n"
    "- If the data is thin, say so plainly rather than filling gaps with speculation.\n"
    "- Every quantitative claim must match a number present in the data.\n\n"
)

_bedrock = None
_call_count = 0
_rejections = 0

# Tokens allowed even though they look like proper nouns (domain vocabulary, not fabricated entities).
ALLOWLIST = {
    "UAP", "UAPs", "UFO", "UFOs", "USO", "USOs", "AI", "GEIPAN", "FAA", "ATC", "FLIR",
    "Tier", "Craft", "Morphology", "Flight", "Kinematics", "Sensor", "Electromagnetic",
    "Signatures", "Encounter", "Typology", "Witness", "Reliability", "Corroboration",
    "Institutional", "Response", "Information", "Control", "Hook", "Evidence",
    "Implication", "Anomaly", "Pattern", "The", "This", "These", "Their", "It", "If",
    "What", "One", "Are", "Whether", "While", "With", "As", "To", "For", "In", "Both",
    "Highest", "Waves", "Cross", "Explained", "Priority",
}


def bedrock():
    global _bedrock
    if _bedrock is None:
        _bedrock = boto3.client("bedrock-runtime", region_name=REGION)
    return _bedrock


def load_data():
    """Parse the window.UAP_DATA = {...}; assignment out of the data JS file."""
    if not DATA_FILE.exists():
        print(f"  ERROR: data file not found: {DATA_FILE}")
        sys.exit(1)
    text = DATA_FILE.read_text(encoding="utf-8")
    m = re.search(r"window\.UAP_DATA\s*=\s*(\{.*\})\s*;?\s*$", text, re.DOTALL | re.MULTILINE)
    if not m:
        m = re.search(r"window\.UAP_DATA\s*=\s*(\{.*\})", text, re.DOTALL)
    if not m:
        print("  ERROR: could not locate window.UAP_DATA object in data file.")
        sys.exit(1)
    return json.loads(m.group(1))


def build_source_vocabulary(data):
    """Build the set of word tokens that legitimately appear in the source data.
    Any capitalized token or 4-digit year in generated text that is NOT in this set
    (and not in ALLOWLIST) is treated as fabricated."""
    blob = json.dumps(data)
    tokens = set(re.findall(r"[A-Za-z][A-Za-z'\-]+", blob))
    years = set(re.findall(r"\b(1[89]\d{2}|20\d{2})\b", blob))
    # Case-insensitive vocabulary for matching
    vocab = {t.lower() for t in tokens}
    return vocab, years


def validate_grounding(text, vocab, source_years):
    """Return list of suspected fabricated tokens. Empty list == clean.
    Flags: capitalized mid-sentence proper nouns and 4-digit years absent from source."""
    problems = []
    # 4-digit years not present in the source data
    for y in re.findall(r"\b(1[89]\d{2}|20\d{2})\b", text):
        if y not in source_years:
            problems.append(y)
    # Proper-noun-like tokens: capitalized word not at sentence start
    # Split into sentences, skip the first word of each sentence.
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for sent in sentences:
        words = re.findall(r"[A-Za-z][A-Za-z'\-]+", sent)
        for i, w in enumerate(words):
            if i == 0:
                continue  # sentence-initial capitalization is expected
            if w[0].isupper():
                if w in ALLOWLIST:
                    continue
                if w.lower() in vocab:
                    continue
                problems.append(w)
    # De-dupe, preserve order
    seen = set()
    out = []
    for p in problems:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def invoke(prompt, temperature=TEMPERATURE):
    global _call_count
    _call_count += 1
    resp = bedrock().converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": MAX_TOKENS, "temperature": temperature},
    )
    return resp["output"]["message"]["content"][0]["text"].strip()


def invoke_grounded(prompt, vocab, source_years, label=""):
    """Invoke, validate grounding, retry once, then blank if still fabricating."""
    global _rejections
    text = invoke(prompt)
    problems = validate_grounding(text, vocab, source_years)
    if problems:
        _rejections += 1
        print(f"  [reject] {label}: ungrounded tokens {problems[:8]} — retrying")
        retry_prompt = (
            prompt
            + "\n\nYOUR PREVIOUS ANSWER INTRODUCED TERMS NOT IN THE DATA: "
            + ", ".join(problems[:12])
            + ". Rewrite using ONLY the provided data. Remove every invented name, place, case, and year."
        )
        text = invoke(retry_prompt)
        problems = validate_grounding(text, vocab, source_years)
        if problems:
            _rejections += 1
            print(f"  [blank]  {label}: still ungrounded {problems[:8]} — dropping to data fallback")
            return None
    return text


def _paras(text):
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def build_brief(data, vocab, years):
    summary = {
        "corpus_total": data.get("corpus_total"),
        "reports_firing": data.get("reports_firing"),
        "signatures_total": data.get("signatures_total"),
        "top_tier1": (data.get("tiers", {}).get("tier1_bring_me_these", {}).get("top_signatures", []))[:5],
    }
    prompt = (
        GROUNDING_RULES
        + "You are an intelligence analyst writing a brief for a field researcher, using ONLY this data:\n"
        + f"{json.dumps(summary)}\n\n"
        "Write exactly 3 short paragraphs, separated by a blank line, no headers:\n"
        "1. HOOK: the most significant pattern in the data (reference the signature description and its count).\n"
        "2. EVIDENCE: cite the specific counts and signature IDs present in the data.\n"
        "3. IMPLICATION: what these counts do and do not establish. State what is unproven.\n"
        "Max 180 words. No invented cases, names, places, or years."
    )
    text = invoke_grounded(prompt, vocab, years, "brief")
    if not text:
        return None
    paras = _paras(text)
    if len(paras) >= 3:
        return {"hook": paras[0], "evidence": paras[1], "implication": " ".join(paras[2:])}
    return {"hook": text, "evidence": "", "implication": ""}


def typology_score(t):
    sigs = t.get("signatures", [])
    strong = [s for s in sigs if s.get("severity") in ("critical", "high")]
    strong_fired = sum(s.get("fired", 0) for s in strong)
    total_fired = sum(s.get("fired", 0) for s in sigs) or 1
    return min(strong_fired / total_fired, 1.0)


def build_missions(data, vocab, years):
    tasks = []
    for tid, t in (data.get("typology_rollup") or {}).items():
        score = typology_score(t)
        if score >= 0.80:
            continue
        zero = [s for s in t.get("signatures", []) if s.get("fired", 0) == 0 and s.get("severity") in ("critical", "high")]
        if not zero:
            continue
        prompt = (
            GROUNDING_RULES
            + f"A UAP pattern named '{t['name']}' has these unconfirmed high-priority signatures (0 reports fired), "
            + f"described exactly as: {json.dumps([s['description'] for s in zero][:4])}\n"
            "Write ONE specific, measurable research mission that would surface cases matching these signature "
            "descriptions. Reference a generic evidence type (e.g. radar logs, sensor data, corroborated multi-witness "
            "reports) — do NOT name any real system, place, agency, or case. One sentence, max 30 words."
        )
        task_text = invoke_grounded(prompt, vocab, years, f"mission:{tid}")
        if not task_text:
            # Deterministic, fully-grounded fallback built from the signature text itself.
            task_text = (
                f"Source corroborated cases matching {len(zero)} unfired high-priority "
                f"signature(s), starting with: \"{zero[0]['description'][:80]}\"."
            )
        tasks.append({
            "id": f"{tid}-corr",
            "theory": t["name"],
            "current": f"{score:.2f}",
            "target": "0.80",
            "task": task_text,
        })
    return {"tasks": tasks}


def build_chapters(data, vocab, years):
    chapters = {}
    for key, t in (data.get("tiers") or {}).items():
        # Provide the concrete signatures/typologies for this tier so the model has real material.
        material = {"label": t.get("label"), "desc": t.get("desc")}
        if t.get("top_signatures"):
            material["signatures"] = [{"desc": s["desc"], "fired": s.get("fired"), "sev": s.get("sev")} for s in t["top_signatures"]]
        if t.get("typologies"):
            material["typologies"] = [
                {"name": (data["typology_rollup"].get(tid) or {}).get("name", tid),
                 "reports": (data["typology_rollup"].get(tid) or {}).get("reports")}
                for tid in t["typologies"]
            ]
        if t.get("mass_sightings"):
            material["mass_sighting_count"] = len(t["mass_sightings"])
        prompt = (
            GROUNDING_RULES
            + "Write a short documentary-style chapter using ONLY this tier data:\n"
            + f"{json.dumps(material)}\n\n"
            "Structure as plain paragraphs (blank-line separated): an opening framing of what this tier contains, "
            "what the signatures/counts show, what is anomalous about them, and what a researcher should examine next. "
            "Describe patterns generically from the provided signature descriptions and counts. "
            "Do NOT invent cases, named incidents, places, agencies, people, or years. 200-350 words."
        )
        text = invoke_grounded(prompt, vocab, years, f"chapter:{key}")
        if not text:
            # Fallback: strictly the label + desc, no model text.
            chapters[key] = {
                "title": t.get("label", key),
                "body": [t.get("desc", "")],
            }
            continue
        chapters[key] = {"title": t.get("label", key), "body": _paras(text)}
    return chapters


def build_connections(data, vocab, years):
    connections = {}
    rollup = data.get("typology_rollup") or {}
    seen = set()
    for t in (data.get("tiers") or {}).values():
        tids = t.get("typologies") or []
        for i in range(len(tids)):
            for j in range(i + 1, len(tids)):
                a, b = tids[i], tids[j]
                if a not in rollup or b not in rollup:
                    continue
                key = f"{a}|{b}"
                if key in seen:
                    continue
                seen.add(key)
                prompt = (
                    GROUNDING_RULES
                    + f"Two UAP patterns co-occur in the same priority tier: '{rollup[a]['name']}' "
                    + f"({rollup[a].get('reports')} reports) and '{rollup[b]['name']}' ({rollup[b].get('reports')} reports).\n"
                    "In 1-2 sentences, explain generically why cases firing one pattern would also tend to fire the other. "
                    "Do NOT invent cases, places, or names. Max 35 words."
                )
                text = invoke_grounded(prompt, vocab, years, f"conn:{key}")
                if not text:
                    text = (
                        f"Both patterns appear in the same priority tier; cases firing "
                        f"'{rollup[a]['name']}' signatures frequently also fire '{rollup[b]['name']}' signatures."
                    )
                connections[key] = text
    return connections


def js_const(name, obj):
    return f"const {name} = {json.dumps(obj, indent=2)};\n"


def main():
    data = load_data()
    vocab, years = build_source_vocabulary(data)
    print(f"Source vocabulary: {len(vocab)} tokens, {len(years)} distinct years.")

    print("Generating AI Intelligence Brief...")
    brief = build_brief(data, vocab, years)
    briefs = {"overview": brief} if brief else {}

    print("Generating Research Missions...")
    missions = build_missions(data, vocab, years)

    print("Generating Documentary Chapters...")
    chapters = build_chapters(data, vocab, years)

    print("Generating Connection Narratives...")
    connections = build_connections(data, vocab, years)

    header = (
        "// Auto-generated by scripts/generate_uap_command_center_narratives.py\n"
        f"// Calls: {_call_count} | Rejections (ungrounded, retried/blanked): {_rejections}\n"
        f"// Grounded against src/frontend/uap-command-data.js | Generated: {datetime.now().isoformat()}\n\n"
    )
    body = (
        js_const("UAP_BRIEFS", briefs)
        + js_const("UAP_MISSIONS", missions)
        + js_const("UAP_CHAPTERS", chapters)
        + js_const("UAP_CONNECTIONS", connections)
    )
    footer = (
        "\nwindow.UAP_BRIEFS = UAP_BRIEFS;\n"
        "window.UAP_MISSIONS = UAP_MISSIONS;\n"
        "window.UAP_CHAPTERS = UAP_CHAPTERS;\n"
        "window.UAP_CONNECTIONS = UAP_CONNECTIONS;\n"
    )
    OUTPUT_FILE.write_text(header + body + footer, encoding="utf-8")
    print(f"Wrote {OUTPUT_FILE} ({_call_count} calls, {_rejections} ungrounded rejections).")


if __name__ == "__main__":
    main()
