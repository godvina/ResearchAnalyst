"""
Archon Library — Ancient Text Processing Pipeline

Extracts text from mythology PDFs, runs Bedrock entity extraction,
builds cross-cultural pattern signatures, and outputs structured JSON
for the Archon frontend.

Usage:
    python scripts/archon_process_texts.py

Output:
    src/data/archon-library.json — entities, relationships, and cross-cultural patterns
    src/frontend/archon-data.js — frontend-ready data for the Archon dashboard
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

import pypdf
import boto3
from botocore.config import Config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
TEXTS_DIR = PROJECT_ROOT / "src" / "data" / "ancient-texts"
OUTPUT_JSON = PROJECT_ROOT / "src" / "data" / "archon-library.json"
OUTPUT_JS = PROJECT_ROOT / "src" / "frontend" / "archon-data.js"

HAIKU_MODEL = "anthropic.claude-3-haiku-20240307-v1:0"
AWS_REGION = "us-east-1"


# =============================================================================
# PDF TEXT EXTRACTION (Tier 1)
# =============================================================================

def extract_text(file_path: Path) -> str:
    """Extract text from a PDF or plain text file."""
    if file_path.suffix.lower() == ".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    elif file_path.suffix.lower() == ".pdf":
        reader = pypdf.PdfReader(str(file_path))
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text
    else:
        logger.warning(f"Unsupported file type: {file_path.suffix}")
        return ""


# =============================================================================
# BEDROCK ENTITY EXTRACTION (Tier 3)
# =============================================================================

EXTRACTION_PROMPT = """You are a mythology and ancient history scholar. Analyze this ancient text excerpt and extract:

1. ENTITIES: All divine beings, heroes, locations, and artifacts mentioned.
   For each entity: name, type (deity/hero/location/artifact/creature/concept), culture (Sumerian/Akkadian/Babylonian), description (1 sentence), aliases (other names for same entity)

2. RELATIONSHIPS: How entities relate to each other.
   For each: source_entity, target_entity, relationship_type (parent_of, child_of, sibling_of, spouse_of, created, destroyed, rules_over, serves, battles, travels_to, possesses)

3. CROSS-CULTURAL PATTERNS: Motifs that appear in multiple traditions.
   For each: pattern_name, description, appears_in (list of cultures/texts where similar motif exists)

4. KEY EVENTS: Major narrative events.
   For each: event_name, participants (entity names), description, significance

Return ONLY valid JSON:
{
  "source_text": "name of the text",
  "culture": "primary culture",
  "entities": [{"name":"...","type":"...","culture":"...","description":"...","aliases":["..."]}],
  "relationships": [{"source":"...","target":"...","type":"...","context":"..."}],
  "cross_cultural_patterns": [{"pattern":"...","description":"...","appears_in":["..."]}],
  "key_events": [{"event":"...","participants":["..."],"description":"...","significance":"..."}]
}"""


def invoke_bedrock(text_chunk: str, source_name: str) -> dict:
    """Call Bedrock Haiku to extract entities from a text chunk."""
    client = boto3.client("bedrock-runtime", region_name=AWS_REGION,
                          config=Config(read_timeout=60, connect_timeout=10, retries={"max_attempts": 2}))

    user_msg = f"Source text: {source_name}\n\n{text_chunk[:14000]}"

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "system": EXTRACTION_PROMPT,
        "messages": [{"role": "user", "content": user_msg}],
        "temperature": 0.2,
    }

    resp = client.invoke_model(
        modelId=HAIKU_MODEL,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body)
    )
    resp_body = json.loads(resp["body"].read().decode())
    text_out = ""
    for block in resp_body.get("content", []):
        if block.get("type") == "text":
            text_out = block.get("text", "")
            break

    # Parse JSON from response — try multiple strategies
    try:
        # Strategy 1: direct parse
        return json.loads(text_out)
    except (json.JSONDecodeError, ValueError):
        pass

    try:
        # Strategy 2: find outermost { }
        start = text_out.find("{")
        if start == -1:
            logger.warning(f"  No JSON object found in response. First 200 chars: {text_out[:200]}")
            return {}
        # Find matching closing brace
        depth = 0
        end = -1
        for i in range(start, len(text_out)):
            if text_out[i] == "{":
                depth += 1
            elif text_out[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end > start:
            return json.loads(text_out[start:end + 1])
    except json.JSONDecodeError as e:
        logger.warning(f"  JSON parse failed: {e}. Trying cleanup...")
        # Strategy 3: strip trailing commas and retry
        raw = text_out[start:end + 1]
        import re
        raw = re.sub(r',\s*([}\]])', r'\1', raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.error(f"  All JSON parse strategies failed.")
    return {}


# =============================================================================
# CROSS-CULTURAL PATTERN SIGNATURES
# =============================================================================

ARCHON_PATTERNS = [
    {
        "pattern_id": "arch-001",
        "name": "Divine Creation of Humans as Workers",
        "description": "Gods/divine beings create humans specifically to perform labor or serve the gods. Humans are fashioned from clay, blood, or divine substance.",
        "appears_in": ["Atra-Hasis (Sumerian)", "Enuma Elish (Babylonian)", "Genesis (Hebrew)", "Popol Vuh (Mayan)", "Prometheus myth (Greek)"],
        "indicators": ["humans created from clay", "gods tired of labor", "divine blood mixed with earth", "humans made to serve"],
        "significance": "Universal motif suggesting either shared cultural memory or independent convergence on the same metaphysical question"
    },
    {
        "pattern_id": "arch-002",
        "name": "Catastrophic Flood as Divine Reset",
        "description": "Divine council decides to destroy humanity via flood. One righteous human is warned and survives via a vessel. Post-flood, gods regret or grant immortality.",
        "appears_in": ["Gilgamesh Tablet XI", "Atra-Hasis", "Genesis 6-9", "Eridu Genesis", "Matsya Purana (Hindu)", "Popol Vuh", "Deucalion (Greek)", "Nu Wa (Chinese)"],
        "indicators": ["divine council", "flood warning to one person", "vessel/ark constructed", "animals preserved", "rainbow/covenant after"],
        "significance": "Appears in 200+ cultures globally. Either cultural diffusion from one event or independent flood memories from sea level rise (~12000 BCE)"
    },
    {
        "pattern_id": "arch-003",
        "name": "Divine/Human Interbreeding",
        "description": "Gods or divine beings mate with human women, producing semi-divine offspring with extraordinary powers. These offspring are often heroes or giants.",
        "appears_in": ["Genesis 6 (Nephilim)", "Gilgamesh (2/3 divine)", "Greek mythology (demigods)", "Book of Enoch (Watchers)", "Irish (Tuatha x humans)", "Mahabharata (Pandavas)"],
        "indicators": ["sons of gods", "daughters of men", "giant offspring", "semi-divine hero", "forbidden union"],
        "significance": "Recurring theme of divine genetics entering human bloodline — interpreted by AA as genetic engineering"
    },
    {
        "pattern_id": "arch-004",
        "name": "Underground Retreat of the Gods",
        "description": "Divine beings retreat underground or to another dimension, remaining present but hidden. They can be contacted at specific locations or times.",
        "appears_in": ["Tuatha Dé Danann → Sídhe (Irish)", "Anunnaki → Abzu (Sumerian)", "Greek gods → Underworld", "Hopi Ant People → underground", "Hindu Nagas → Patala"],
        "indicators": ["gods go underground", "hollow hills", "dimensional gateway", "still present but hidden", "accessible at sacred sites"],
        "significance": "Connected to Irish sacred site data — passage tombs as 'entrances to otherworld'"
    },
    {
        "pattern_id": "arch-005",
        "name": "Advanced Pre-Flood Civilization",
        "description": "Before the catastrophic flood, a highly advanced civilization existed. Post-flood survivors carried fragments of this knowledge. The civilization had technology beyond its era.",
        "appears_in": ["Sumerian King List (pre-flood kings)", "Plato's Atlantis", "Vedic Dwarka", "Irish Hy-Brasil", "Edgar Cayce readings", "Göbekli Tepe (archaeological)"],
        "indicators": ["impossibly long reigns", "lost continent", "advanced construction", "star knowledge", "sudden civilization emergence"],
        "significance": "Göbekli Tepe (9600 BCE) provides archaeological evidence of advanced construction pre-dating agriculture"
    },
    {
        "pattern_id": "arch-006",
        "name": "Solar/Astronomical Alignment Knowledge",
        "description": "Ancient structures demonstrate precise astronomical knowledge (solstice/equinox alignment, star mapping) that shouldn't have been possible without advanced instruments.",
        "appears_in": ["Newgrange (Irish)", "Giza (Egyptian)", "Göbekli Tepe (Turkish)", "Angkor Wat (Cambodian)", "Stonehenge (British)", "Chichen Itza (Mayan)"],
        "indicators": ["solstice alignment", "equinox light box", "star constellation mapping", "precession awareness", "global coordinate system"],
        "significance": "Direct connection to Irish Sacred Sites data — Newgrange winter solstice roofbox, Loughcrew equinox alignment"
    },
    {
        "pattern_id": "arch-007",
        "name": "Divine Kingship / Mandate of Heaven",
        "description": "Rulers claim direct descent from gods, with divine right to rule. Kingship 'descends from heaven' as a gift from the gods to humanity.",
        "appears_in": ["Sumerian King List", "Egyptian pharaohs (son of Ra)", "Chinese Mandate of Heaven", "Japanese emperor (Amaterasu descent)", "Irish High Kings (Tuatha lineage)"],
        "indicators": ["kingship from heaven", "divine blood", "god-king", "pharaoh as living god", "sacred coronation site"],
        "significance": "Connects political authority to divine origin across ALL major ancient civilizations"
    }
]


# =============================================================================
# MAIN PROCESSING PIPELINE
# =============================================================================

def process_all_texts():
    """Process all PDFs and text files in the ancient-texts directory."""
    pdf_files = list(TEXTS_DIR.glob("*.pdf"))
    txt_files = list(TEXTS_DIR.glob("*.txt"))
    all_files = pdf_files + txt_files

    if not all_files:
        logger.error(f"No PDFs or text files found in {TEXTS_DIR}")
        return

    logger.info(f"Found {len(all_files)} files to process ({len(pdf_files)} PDF, {len(txt_files)} TXT)")

    all_entities = []
    all_relationships = []
    all_events = []
    all_extractions = []

    for file_path in all_files:
        # Skip the large Chicago academic paper (10MB — analysis, not source text)
        if "Chicago" in file_path.name or "Parallels" in file_path.name:
            logger.info(f"Skipping academic analysis: {file_path.name}")
            continue

        logger.info(f"Processing: {file_path.name}")

        # Tier 1: Extract text
        text = extract_text(file_path)
        if not text.strip():
            logger.warning(f"  No text extracted from {file_path.name}")
            continue
        logger.info(f"  Extracted {len(text)} chars")

        # Tier 3: Bedrock entity extraction (take first 12K chars — most relevant content)
        source_name = file_path.stem.replace("_", " ")
        logger.info(f"  Invoking Bedrock for entity extraction...")
        try:
            extraction = invoke_bedrock(text, source_name)
            if extraction:
                extraction["source_file"] = file_path.name
                all_extractions.append(extraction)
                all_entities.extend(extraction.get("entities", []))
                all_relationships.extend(extraction.get("relationships", []))
                all_events.extend(extraction.get("key_events", []))
                logger.info(f"  Extracted: {len(extraction.get('entities', []))} entities, "
                          f"{len(extraction.get('relationships', []))} relationships, "
                          f"{len(extraction.get('key_events', []))} events")
            else:
                logger.warning(f"  Empty extraction result")
        except Exception as e:
            logger.error(f"  Bedrock error: {e}")

        time.sleep(1)  # Rate limit

    # Deduplicate entities by name
    unique_entities = {}
    for e in all_entities:
        name = e.get("name", "").strip()
        if name and name not in unique_entities:
            unique_entities[name] = e
        elif name in unique_entities:
            # Merge aliases
            existing = unique_entities[name]
            existing_aliases = set(existing.get("aliases", []))
            new_aliases = set(e.get("aliases", []))
            existing["aliases"] = list(existing_aliases | new_aliases)

    # Build output
    archon_library = {
        "name": "Archon Library",
        "version": "1.0.0",
        "description": "Cross-cultural mythology and ancient text analysis. Entities, relationships, and pattern signatures from Sumerian, Babylonian, Hebrew, and comparative traditions.",
        "last_updated": time.strftime("%Y-%m-%d"),
        "sources_processed": [p.name for p in all_files if "Chicago" not in p.name and "Parallels" not in p.name],
        "entities": list(unique_entities.values()),
        "relationships": all_relationships,
        "key_events": all_events,
        "cross_cultural_patterns": ARCHON_PATTERNS,
        "extractions": all_extractions,
        "stats": {
            "total_entities": len(unique_entities),
            "total_relationships": len(all_relationships),
            "total_events": len(all_events),
            "total_patterns": len(ARCHON_PATTERNS),
            "sources_processed": len(all_extractions),
        }
    }

    # Write JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(archon_library, f, indent=2, ensure_ascii=False)
    logger.info(f"Wrote: {OUTPUT_JSON} ({os.path.getsize(OUTPUT_JSON) // 1024}KB)")

    # Write frontend JS
    js_content = f"// Archon Library — Generated {time.strftime('%Y-%m-%d')}\n"
    js_content += f"// {len(unique_entities)} entities, {len(all_relationships)} relationships, {len(ARCHON_PATTERNS)} cross-cultural patterns\n\n"
    js_content += f"const ARCHON_DATA = {json.dumps(archon_library, indent=2, ensure_ascii=False)};\n"

    with open(OUTPUT_JS, "w", encoding="utf-8") as f:
        f.write(js_content)
    logger.info(f"Wrote: {OUTPUT_JS} ({os.path.getsize(OUTPUT_JS) // 1024}KB)")

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"ARCHON LIBRARY — Processing Complete")
    logger.info(f"{'='*60}")
    logger.info(f"  Entities: {len(unique_entities)}")
    logger.info(f"  Relationships: {len(all_relationships)}")
    logger.info(f"  Key Events: {len(all_events)}")
    logger.info(f"  Cross-Cultural Patterns: {len(ARCHON_PATTERNS)}")
    logger.info(f"  Sources: {len(all_extractions)}")
    logger.info(f"{'='*60}")

    return archon_library


if __name__ == "__main__":
    process_all_texts()
