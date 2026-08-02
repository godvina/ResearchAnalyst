"""Generate expanded documentary episodes with sub-chapters.

Structure: Series → Episodes → Sub-Chapters
Each sub-chapter is 60-90 seconds of narration (~150-200 words).
Uses Bedrock to generate narration in documentary voice.
Output: expanded-documentary-script.json (for Polly synthesis later).

Chapters are scored by content richness — skip if insufficient data.
"""
import boto3
import json
import os
import time
from botocore.config import Config

REGION = "us-east-1"
MODEL = "us.anthropic.claude-sonnet-4-6"
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "data")

bedrock = boto3.client("bedrock-runtime", region_name=REGION,
                       config=Config(read_timeout=120, retries={"max_attempts": 2}))

# Episode structure with sub-chapters
EPISODES = [
    {
        "id": "ep2",
        "title": "Sacred Sites",
        "subtitle": "What indigenous peoples know that archaeology doesn't",
        "duration_target": "5-7 min",
        "chapters": [
            {"id": "2.1", "title": "Giza — The Confirmed Node",
             "prompt_context": "Node 1, Great Pyramid, CONFIRMED status, aligned to true north within 0.067°, Cole 1925 measurements, center of Earth's landmass claim, UVG grid vertex",
             "min_richness": 3},
            {"id": "2.2", "title": "Sedona — Nine Sacred Traditions",
             "prompt_context": "Node 17, Sedona Vortexes, 9 confirmed cultural traits: ENERGY_SENSATION, HEALING_TRADITION, FORBIDDEN_ZONE, CREATION_MYTH, PILGRIMAGE, SPIRIT_DWELLING, WATER_SACRED, BURIAL_GROUND, POWER_TRANSFER. Yavapai-Apache territory, Cathedral Rock, Bell Rock, Oak Creek Canyon",
             "min_richness": 5},
            {"id": "2.3", "title": "The Cultural Memory Pattern",
             "prompt_context": "6 sites across 5 continents independently share SPIRIT_DWELLING and WATER_SACRED traits: Sichuan Highland, Sedona, Nile Savanna, Gulf Savanna Australia, Orinoco Amazon, Flinders Australia. No known cultural contact between them.",
             "min_richness": 3},
            {"id": "2.4", "title": "Why Six Cultures Say the Same Thing",
             "prompt_context": "FORBIDDEN_ZONE shared by Pripyat, Sichuan, Sedona. CREATION_MYTH shared by Sichuan, Sedona, Nile, Gulf Savanna, Flinders. Statistical improbability of 6 independent cultures identifying the same geographic points as spiritually significant.",
             "min_richness": 2},
        ]
    },
    {
        "id": "ep3",
        "title": "The Great Circle",
        "subtitle": "Five ancient sites on a single line across 40,000 kilometers",
        "duration_target": "5-7 min",
        "chapters": [
            {"id": "3.1", "title": "Five Sites, One Line, 40,000km",
             "prompt_context": "Jim Alison (2001) great circle: Giza, Persepolis, Mohenjo-daro, Angkor Wat, Easter Island. Less than 1 degree of arc deviation across 40,000km. Either shared geodetic knowledge or extraordinary coincidence.",
             "min_richness": 3},
            {"id": "3.2", "title": "Mohenjo-daro to Easter Island",
             "prompt_context": "Mohenjo-daro: 40,000-person city, 2500 BCE, grid streets, advanced sanitation. Easter Island: 887 moai, volcanic isolation, 27°S. Separated by 15,000km, no known contact, yet on the same mathematical line.",
             "min_richness": 2},
            {"id": "3.3", "title": "The Skeptic's Challenge",
             "prompt_context": "Counter-argument: with enough sites and lines, coincidences are inevitable. Atkinson's combinatorial argument. Lippard (1994): random point within 50km of ancient site. BUT: the precision is <0.1° and includes MAJOR sites, not random ones. No peer-reviewed statistical null test performed.",
             "min_richness": 2},
        ]
    },
    {
        "id": "ep4",
        "title": "Written in the Stars",
        "subtitle": "When three civilizations encode the same sky-date",
        "duration_target": "5-7 min",
        "chapters": [
            {"id": "4.1", "title": "Orion's Belt and the Pyramids",
             "prompt_context": "Robert Bauval (1994, The Orion Mystery): three Giza pyramids mirror Orion's Belt at 10,500 BCE. Declination match within 0.5°. The offset of Mintaka matches the offset of Menkaure. Precession means this alignment only works at ONE specific epoch.",
             "min_richness": 3},
            {"id": "4.2", "title": "Angkor and Draco — Same Epoch",
             "prompt_context": "Graham Hancock & Santha Faiia (1998, Heaven's Mirror): Angkor Wat ground plan mirrors Draco constellation at the SAME precessional epoch as Giza mirrors Orion — 10,500 BCE. Two civilizations, 8000km apart, no contact, encoding same sky-date.",
             "min_richness": 3},
            {"id": "4.3", "title": "The 10,500 BCE Problem",
             "prompt_context": "Giza built ~2560 BCE. Angkor built ~1100 CE. Teotihuacan built ~200 CE. All encode 10,500 BCE sky. Either: (a) builders encoded an ancient date from oral tradition, (b) sites are far older than accepted, (c) coincidence. No option is comfortable for mainstream archaeology.",
             "min_richness": 3},
            {"id": "4.4", "title": "Precession as a Clock",
             "prompt_context": "Earth's axis precesses at 1° per 72 years. Full cycle: 25,920 years. Star positions shift predictably. If a building encodes a specific star position, you can calculate WHEN that position was visible. This makes precession a cosmic clock — and three independent civilizations set their clocks to the same time.",
             "min_richness": 2},
        ]
    },
    {
        "id": "ep5",
        "title": "Fire and Stone",
        "subtitle": "Why ancient builders chose the most geologically active locations on Earth",
        "duration_target": "5-7 min",
        "chapters": [
            {"id": "5.1", "title": "The Volcanic Correlation",
             "prompt_context": "80% of analyzed UVG nodes show active volcanism within 200km. Hawaii, Easter Island, Iceland — all hotspot volcanoes at grid nodes. Ritsema et al (1999, Science): antipodal LLSVPs at core-mantle boundary correspond to UVG supernode clusters. The grid may reflect GEOLOGICAL structure, not human design.",
             "min_richness": 3},
            {"id": "5.2", "title": "Did They Feel the Earth?",
             "prompt_context": "Geomagnetic anomalies are measurable at Giza (electromagnetic survey 2003). Sedona vortex sites correspond to documented magnetic declination anomalies. Ancient peoples may have SENSED geomagnetic features and built there. Documented 'energy sensation' tradition at 6 sites independently.",
             "min_richness": 2},
            {"id": "5.3", "title": "What LiDAR Could Reveal",
             "prompt_context": "2015 CALI survey: 1000+ structures found under Angkor canopy. 2018 Guatemala Pacunam: 60,000 Maya structures under jungle. 2022 Amazon: pre-Columbian earthworks. Multiple UVG nodes in tropical forest zones have NEVER been LiDAR surveyed. The next Angkor may be waiting.",
             "min_richness": 3},
        ]
    },
    {
        "id": "ep6",
        "title": "What Comes Next",
        "subtitle": "The questions this investigation cannot yet answer",
        "duration_target": "3-5 min",
        "chapters": [
            {"id": "6.1", "title": "The 70 Unexplained Connections",
             "prompt_context": "OpenSearch k-NN similarity analysis found 70 unexpected similarity pairs between nodes that share NO taxonomy signature. These are connections the AI found that human researchers never looked for. The Southern Ocean cluster is the most anomalous — deep-ocean nodes with shared bathymetric geometry.",
             "min_richness": 2},
            {"id": "6.2", "title": "The Statistical Question",
             "prompt_context": "The fundamental challenge: with 62 nodes and thousands of ancient sites, what is EXPECTED by chance? No peer-reviewed Monte Carlo null test has been performed. The AI research system suggests this as the single highest-priority next investigation. Until it's done, all correlations remain 'notable' rather than 'proven'.",
             "min_richness": 2},
            {"id": "6.3", "title": "The Questions We Haven't Asked",
             "prompt_context": "Auto-Query agent generated: (1) isotopic stone-sourcing across UVG nodes, (2) precessional encoding test at 3 sites with identical methodology, (3) underwater survey compilation for marine nodes, (4) systematic 'navel of world' linguistic convergence test. Each could confirm or deny the grid theory. The investigation continues.",
             "min_richness": 1},
        ]
    },
]


def generate_narration(chapter, episode_title):
    """Generate 60-90 second narration for a sub-chapter."""
    prompt = (
        "You are a narrator for a premium documentary series about ancient mysteries and scientific investigation. "
        "Your tone is: measured, intelligent, evocative — like David Attenborough meets Carl Sagan. "
        "You state facts precisely with citations, but create emotional resonance through pacing and word choice.\n\n"
        f"SERIES: 'The Grid' — AI-powered investigation of the UVG World Grid theory\n"
        f"EPISODE: '{episode_title}'\n"
        f"CHAPTER: '{chapter['title']}'\n\n"
        f"CONTEXT (use this data in the narration):\n{chapter['prompt_context']}\n\n"
        "Write EXACTLY 150-200 words of narration for this chapter. "
        "The narration should:\n"
        "1. Open with a provocative statement or image\n"
        "2. Present specific facts with measurements and researcher names\n"
        "3. Build toward a moment of revelation or unanswered question\n"
        "4. End on a line that makes the listener want to hear the next chapter\n\n"
        "Return ONLY the narration text. No JSON, no markdown, no stage directions. Just the words the narrator speaks."
    )

    try:
        resp = bedrock.invoke_model(
            modelId=MODEL,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 400,
                "messages": [{"role": "user", "content": prompt}]
            })
        )
        body = json.loads(resp["body"].read())
        for block in body.get("content", []):
            if block.get("type") == "text":
                return block["text"].strip()
        return ""
    except Exception as e:
        print(f"    Error: {e}")
        return None


def main():
    print("=" * 60)
    print("  EXPANDED DOCUMENTARY GENERATION")
    print(f"  {len(EPISODES)} episodes, {sum(len(e['chapters']) for e in EPISODES)} sub-chapters")
    print("=" * 60)

    output = {
        "series_title": "The Grid",
        "series_subtitle": "An AI-Powered Investigation of Earth's Hidden Geometry",
        "total_episodes": len(EPISODES) + 1,  # +1 for existing Episode 1
        "episodes": []
    }

    for ep in EPISODES:
        print(f"\n  EPISODE: {ep['title']} ({len(ep['chapters'])} chapters)")
        episode_data = {
            "id": ep["id"],
            "title": ep["title"],
            "subtitle": ep["subtitle"],
            "duration_target": ep["duration_target"],
            "chapters": []
        }

        for ch in ep["chapters"]:
            print(f"    [{ch['id']}] {ch['title']}...", end=" ")
            narration = generate_narration(ch, ep["title"])
            if narration:
                word_count = len(narration.split())
                print(f"OK ({word_count} words)")
                episode_data["chapters"].append({
                    "id": ch["id"],
                    "title": ch["title"],
                    "narration": narration,
                    "word_count": word_count,
                    "estimated_seconds": int(word_count / 2.5),  # ~2.5 words/sec for Polly
                })
            else:
                print("FAILED — skipping")
            time.sleep(1)

        output["episodes"].append(episode_data)

    # Save
    output_path = os.path.join(DATA_DIR, "expanded-documentary-script.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    # Summary
    total_words = sum(
        ch["word_count"] for ep in output["episodes"] for ch in ep["chapters"]
    )
    total_seconds = sum(
        ch["estimated_seconds"] for ep in output["episodes"] for ch in ep["chapters"]
    )
    print(f"\n{'=' * 60}")
    print(f"  COMPLETE: {len(output['episodes'])} episodes, "
          f"{sum(len(e['chapters']) for e in output['episodes'])} chapters")
    print(f"  Total narration: {total_words} words (~{total_seconds//60} min {total_seconds%60}s)")
    print(f"  Saved: {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
