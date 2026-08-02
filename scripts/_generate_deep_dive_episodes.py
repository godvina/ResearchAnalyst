"""Generate 30-minute deep-dive episodes from existing research data.

Each deep dive expands a 60-second overview chapter into a full 30-min episode
with 5-7 sub-chapters of ~5 minutes each (~600 words per sub-chapter).
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

DEEP_DIVES = [
    {
        "id": "deep-4.1",
        "parent_chapter": "4.1",
        "title": "Orion's Belt and the Pyramids — Deep Dive",
        "subtitle": "The full story of the Orion Correlation Theory",
        "chapters": [
            {"id": "4.1.1", "title": "The Discovery",
             "prompt": "Tell the story of Robert Bauval's discovery in 1983 in the Saudi Arabian desert, looking up at Orion's Belt and noticing the offset of the third star matches the offset of the third pyramid at Giza. His background as a construction engineer. His partnership with Adrian Gilbert. Publication of 'The Orion Mystery' in 1994. The immediate controversy and media attention. Include: the specific moment of insight, the reaction from Egyptology establishment, the book's key claims."},
            {"id": "4.1.2", "title": "The Measurements",
             "prompt": "Detail the precision measurements that support (and challenge) the Orion correlation. J.H. Cole's 1925 Survey of Egypt measurements: base sides 230.253m, 230.454m, 230.391m, 230.357m. W.M. Flinders Petrie 1883: 9068.8 ± 0.5 inches. The pyramid's alignment to true north within 0.067° (3 arcminutes 54 seconds). Kate Spence's Nature paper (2000): alignment achieved via simultaneous transit of Kochab and Mizar. Glen Dash 2012 confirmation. The scale of precision these numbers represent — and what it implies about the builders' capabilities."},
            {"id": "4.1.3", "title": "The Offset — Why the Third Pyramid Matters",
             "prompt": "Explain why the offset of Menkaure's pyramid from the Khufu-Khafre line is the KEY to Bauval's argument. Orion's Belt: Alnitak and Alnilam are nearly aligned, but Mintaka is offset to the north. The three Giza pyramids: Khufu and Khafre are nearly aligned, but Menkaure is offset to the south-west. This SPECIFIC offset pattern — not just 'three in a row' — is what Bauval claims is encoded. The angular match: Orion's Belt spans 2.73° with Mintaka offset by 0.28° from the Alnitak-Alnilam line. Giza spans 1.1km with Menkaure offset proportionally. Critics say this is cherry-picking; Bauval says the offset PROVES intent because random placement would be a straight line."},
            {"id": "4.1.4", "title": "The Counter-Arguments",
             "prompt": "Present the strongest skeptical arguments against the Orion Correlation Theory. Ed Krupp (Griffith Observatory) and Anthony Fabian in Sky & Telescope (1997): the correlation requires MIRRORING the constellation (flipping north-south), a manipulation Bauval doesn't adequately justify. The 10,500 BCE date is selectively chosen to maximize alignment — other epochs also produce rough matches. Mainstream Egyptologist Mark Lehner: pyramids were built over 80 years by different pharaohs with different architects — no master plan. Ian Lawton's analysis: the angular match is approximate (within 10%) not exact. The 'Texas Sharpshooter' fallacy: drawing the target around the bullet holes after the fact."},
            {"id": "4.1.5", "title": "The Precession Mathematics",
             "prompt": "Explain the precession mathematics that dates the alignment to exactly 10,500 BCE. Earth's axial precession: 25,920 year cycle, 1° per 72 years, 50.3 arcseconds per year. At J2000, Orion's Belt declination is approximately -1° to 0°. Working backward: at 10,500 BCE (12,500 years ago), the Belt's declination would have been approximately at its minimum (crossing the meridian at lowest point in the precessional cycle). This means Orion would have been at its lowest transit altitude as seen from Giza — 'touching the horizon' as Bauval describes. The mathematical verification: anyone with a planetarium program (Stellarium) can confirm this date independently. The Nile as the Milky Way: Bauval's additional claim that the Nile mirrors the Milky Way at this epoch."},
            {"id": "4.1.6", "title": "What Would Prove It — Or Disprove It",
             "prompt": "What specific investigations could settle the Orion Correlation debate once and for all? (1) Independent GPS survey of all three pyramid apex coordinates to sub-meter precision, compared to Orion's Belt star positions at multiple precessional epochs — finding the EXACT best-fit date with error bars. (2) Similar analysis at Teotihuacan (Harleston 1974 claimed Orion match) and Angkor (Hancock 1998 claimed Draco match) — if three sites independently point to the same epoch, coincidence becomes far less likely. (3) Monte Carlo simulation: generate 10,000 random 3-point configurations and measure how often they match ANY 3-star pattern within the observed precision — establishing a null hypothesis. (4) Archaeological dating: if material under the Sphinx or at Giza bedrock dates to 10,500 BCE (like Schoch's geological weathering argument), it corroborates the astronomical date. The investigation remains open."},
        ]
    },
    {
        "id": "deep-3.1",
        "parent_chapter": "3.1",
        "title": "The Great Circle — Deep Dive",
        "subtitle": "Five ancient civilizations on a single mathematical line",
        "chapters": [
            {"id": "3.1.1", "title": "Jim Alison and the Great Circle",
             "prompt": "Tell the story of researcher Jim Alison's 2001 discovery. He plotted ancient sites on a globe and noticed that a great circle (the shortest path between two points on a sphere) connecting Giza and Easter Island passes through Petra, Persepolis, Mohenjo-daro, Khajuraho, and Angkor Wat with less than 1 degree of arc deviation over 40,000km. The methodology: great circles are unique between any two points on a sphere, so choosing Giza-Easter Island as endpoints and finding multiple sites along the path is the striking observation. Previous researchers (Hapgood, Hancock) had noted individual alignments but Alison was first to measure the PRECISION across all sites simultaneously."},
            {"id": "3.1.2", "title": "Giza — The Anchor Point",
             "prompt": "Giza as the starting point of the great circle. 29.9792°N, 31.1342°E. Why Giza: it's the most precisely measured ancient site on Earth (Cole 1925, Petrie 1883, Lehner 1997). The Great Pyramid sits remarkably close to the geographic center of Earth's landmass (centroid calculation). Its cardinal alignment to true north (0.067° error). The pyramid's position as the proposed 'prime meridian' of the ancient world (Stecchini in Tompkins 1971). From Giza, the great circle heads east through the Arabian Peninsula toward Persia."},
            {"id": "3.1.3", "title": "Persepolis and Mohenjo-daro",
             "prompt": "The great circle passes through two of the ancient world's most sophisticated cities. Persepolis (29.93°N, 52.89°E): ceremonial capital of the Achaemenid Empire, built 515 BCE by Darius I, with precise astronomical alignments in its apadana hall — equinox sunrise strikes the central stairway. Mohenjo-daro (27.33°N, 68.14°E): Indus Valley metropolis of 40,000 people, 2500 BCE, grid-planned streets oriented to cardinal directions, Great Bath, advanced sanitation predating Rome by 2000 years. Both cities demonstrate geodetic awareness (grid planning, cardinal orientation) consistent with the knowledge needed to place sites on a great circle. The distance: Giza to Mohenjo-daro is 3,800km. Deviation from the great circle: less than 0.5°."},
            {"id": "3.1.4", "title": "Angkor Wat and Easter Island",
             "prompt": "The line continues to two of Earth's most mysterious sites. Angkor Wat (13.41°N, 103.87°E): largest religious monument ever built, 162 hectares, precise west-facing orientation (equinox sunrise hits the central tower), Khmer civilization 12th century CE. Easter Island (27.12°S, 109.35°W): 887 moai stone heads, average 13.8 tons, most remote inhabited island on Earth, Polynesian civilization from ~400 CE. These two sites are separated by 14,000km of Pacific Ocean. No known contact between Khmer and Polynesian civilizations. Yet both fall on the same great circle as Giza. The full line spans 40,000km — essentially Earth's circumference — with 8 major ancient sites along it within 1° deviation."},
            {"id": "3.1.5", "title": "The Mathematical Precision",
             "prompt": "Break down the mathematics of what '1 degree of arc over 40,000km' means in practical terms. 1° of arc on Earth's surface = 111km. So the sites deviate by at most 111km from a perfect mathematical line spanning the entire planet. For comparison: GPS accuracy is ~5m, ancient surveying with gnomon and stars achieves ~1km accuracy over short distances. But maintaining <111km accuracy over 40,000km implies either: (a) extraordinary geodetic knowledge spanning multiple civilizations, (b) a common geographical/geological feature that attracted settlement, or (c) selection bias in which sites are included. The probability calculation: if you randomly place 8 points on Earth's surface, the chance of all 8 falling within 1° of ANY great circle is astronomically small — but quantifying this precisely requires the Monte Carlo test that has never been peer-reviewed."},
            {"id": "3.1.6", "title": "What the Skeptics Say",
             "prompt": "The strongest counter-arguments to the Great Circle alignment. Clive Ruggles (Leicester): post-hoc site selection — Alison chose sites that fit and ignored thousands that don't. The combinatorial argument: with hundreds of great circles possible through Giza, and thousands of ancient sites globally, SOME line will hit multiple sites by chance. The 'proximity' problem: 111km is a wide corridor — many things fall within it. Lippard (Skeptical Inquirer 1994): virtually any point on Earth is within 50km of a significant archaeological site. BUT: the counter-counter-argument is that these aren't random sites — they're among the MOST famous, MOST precisely engineered ancient structures on Earth. The specific combination of Giza + Mohenjo-daro + Angkor + Easter Island is not cherry-picked from obscure locations."},
        ]
    },
    {
        "id": "deep-2.2",
        "parent_chapter": "2.2",
        "title": "Sedona — Nine Sacred Traditions — Deep Dive",
        "subtitle": "What the Yavapai-Apache know about the red rocks",
        "chapters": [
            {"id": "2.2.1", "title": "The Land Before the Vortexes",
             "prompt": "Before New Age tourism, Sedona was Yavapai-Apache territory for thousands of years. The Yavapai people (Yavapé) and Dilzhe'e Apache have oral traditions placing creation events in the Verde Valley region. Komwidapokuwia (First Woman) emerged from floodwaters in this landscape. The forced removal to San Carlos reservation in 1875 (the March of Tears) — and the ongoing return pilgrimages as acts of cultural reclamation. Sedona as sacred land LONG before it became a tourist destination. Document the pre-contact traditions independent of modern vortex claims."},
            {"id": "2.2.2", "title": "Nine Confirmed Traits",
             "prompt": "Walk through each of the 9 confirmed cultural traits found by the AI Cultural Memory agent: (1) ENERGY_SENSATION — Yavapai recognized specific landscape features as spiritually potent, power spots near Cathedral Rock and Bell Rock. (2) HEALING_TRADITION — shamans conducted healing ceremonies, medicinal plant gathering in Oak Creek Canyon (ethnographer Edward Spicer). (3) FORBIDDEN_ZONE — cliff dwelling areas considered off-limits to non-initiates, Honanki and Palatki restricted pictograph chambers. (4) CREATION_MYTH — Komwidapokuwia/First Woman emerged here. (5) PILGRIMAGE — tribal members continue ceremonial visits after 1875 removal. (6) SPIRIT_DWELLING — Thunder Mountain formations associated with spiritual beings. (7) WATER_SACRED — Oak Creek as sacred waterway, springs for purification rites. (8) BURIAL_GROUND — prehistoric burials throughout area, NAGPRA protections pursued. (9) POWER_TRANSFER — shamanic initiation at designated red rock locations."},
            {"id": "2.2.3", "title": "The Vortex Science Question",
             "prompt": "The modern vortex claims: are they new-age invention or do they connect to something the Yavapai always knew? The four main vortex sites (Airport Mesa, Cathedral Rock, Bell Rock, Boynton Canyon) were identified by Page Bryant in 1980. BUT: Cathedral Rock and Bell Rock were already documented as Yavapai ceremonial sites. Magnetic declination measurements at Sedona show documented anomalies in the red rock iron oxide deposits. Pete Sanders' 'Scientific Vortex Information' studies (1981). The overlap between indigenous 'power spots' and modern 'vortex sites' is either coincidence, cultural absorption, or both groups detecting the same geophysical phenomenon through different frameworks."},
            {"id": "2.2.4", "title": "The Geological Anomaly",
             "prompt": "Why Sedona is geologically unusual. The red rocks are Permian-age sandstone (270-290 million years old) with extremely high iron oxide content, giving them their distinctive color. Iron oxide is paramagnetic — it interacts with Earth's magnetic field. The Sedona region sits at the edge of the Colorado Plateau, a tectonically uplifted block. Multiple fault lines intersect beneath the red rock formations. Documented magnetic field variations between vortex sites and surrounding areas (though no peer-reviewed study confirms 'vortex energy'). The question: did ancient peoples SENSE geomagnetic anomalies (like birds navigate by magnetism), and is that why they designated these specific locations as 'power places'?"},
            {"id": "2.2.5", "title": "The Pattern — Sedona and the Grid",
             "prompt": "Sedona's position on the UVG grid: Node 17 at 31.72°N, 112.8°W — within 350km of the site. What the scored findings show: the node has signatures for indigenous sacred site (am-gge-cm-001 STRONG) with 9 specific traits — the richest cultural memory data of any node in the entire 62-vertex grid. The pattern connection: SPIRIT_DWELLING trait shared with 5 other sites on different continents (Sichuan, Nile, Gulf Savanna, Orinoco, Flinders). None of these cultures had contact with each other. All independently identified grid-proximate locations as places where spirits dwell. Either this is a universal human psychological pattern, or these locations share a physical characteristic that humans detect and interpret as 'spiritual presence.'"},
        ]
    },
]


def generate_deep_chapter(chapter, episode_title):
    """Generate ~5 minutes of narration (~600 words) for a deep-dive sub-chapter."""
    prompt = (
        "You are a narrator for a premium documentary series. "
        "Tone: measured, intelligent, evocative — David Attenborough meets Carl Sagan. "
        "You present evidence precisely, build narrative tension, and respect the viewer's intelligence.\n\n"
        f"SERIES: 'The Grid' — Deep Dive\n"
        f"EPISODE: '{episode_title}'\n"
        f"CHAPTER: '{chapter['title']}'\n\n"
        f"CONTENT TO COVER:\n{chapter['prompt']}\n\n"
        "Write EXACTLY 500-650 words of narration. "
        "Structure: provocative opening → evidence with specifics → building tension → cliffhanger ending.\n"
        "Include: researcher names, dates, measurements, place names. "
        "Address counter-arguments where relevant. "
        "End each chapter with a line that connects to the next chapter.\n\n"
        "Return ONLY the narration text. No JSON, no markdown, no stage directions."
    )

    try:
        resp = bedrock.invoke_model(
            modelId=MODEL,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
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
    print("  DEEP DIVE EPISODE GENERATION")
    print(f"  {len(DEEP_DIVES)} deep dives, {sum(len(d['chapters']) for d in DEEP_DIVES)} chapters")
    print("=" * 60)

    output = {"deep_dives": []}

    for dd in DEEP_DIVES:
        print(f"\n  DEEP DIVE: {dd['title']} ({len(dd['chapters'])} chapters)")
        episode_data = {
            "id": dd["id"],
            "parent_chapter": dd["parent_chapter"],
            "title": dd["title"],
            "subtitle": dd["subtitle"],
            "chapters": []
        }

        for ch in dd["chapters"]:
            print(f"    [{ch['id']}] {ch['title']}...", end=" ")
            narration = generate_deep_chapter(ch, dd["title"])
            if narration:
                word_count = len(narration.split())
                est_seconds = int(word_count / 2.5)
                print(f"OK ({word_count} words, ~{est_seconds//60}:{est_seconds%60:02d})")
                episode_data["chapters"].append({
                    "id": ch["id"],
                    "title": ch["title"],
                    "narration": narration,
                    "word_count": word_count,
                    "estimated_seconds": est_seconds,
                })
            else:
                print("FAILED")
            time.sleep(2)

        output["deep_dives"].append(episode_data)

    # Save
    output_path = os.path.join(DATA_DIR, "deep-dive-episodes.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    # Summary
    total_words = sum(ch["word_count"] for dd in output["deep_dives"] for ch in dd["chapters"])
    total_seconds = sum(ch["estimated_seconds"] for dd in output["deep_dives"] for ch in dd["chapters"])
    print(f"\n{'=' * 60}")
    print(f"  COMPLETE: {len(output['deep_dives'])} deep dives")
    print(f"  Total: {sum(len(dd['chapters']) for dd in output['deep_dives'])} chapters")
    print(f"  Total narration: {total_words} words (~{total_seconds//60} min {total_seconds%60}s)")
    print(f"  Saved: {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
