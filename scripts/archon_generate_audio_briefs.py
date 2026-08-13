"""
Generate audio intelligence briefs for Archon crosswalk entities using Amazon Polly.
Each brief is a 30-60 second narration explaining the entity and its cross-cultural parallel.
"""
import json
import os
from pathlib import Path
import boto3

PROJECT_ROOT = Path(__file__).parent.parent
CROSSWALK_JSON = PROJECT_ROOT / "src" / "data" / "archon-crosswalk.json"
AUDIO_DIR = PROJECT_ROOT / "src" / "frontend" / "audio"
AUDIO_DIR.mkdir(exist_ok=True)

polly = boto3.client("polly", region_name="us-east-1")

# Intelligence briefs for each crosswalk entry
BRIEFS = {
    "Dagda": "The Dagda. Chief of the Tuatha Dé Danann. His dwelling is Brú na Bóinne, known today as Newgrange. A father god and trickster, wielder of a magic cauldron that never empties, and a club that both kills and resurrects. His Sumerian parallel is Enki, also a father of wisdom, also a trickster, also associated with life-giving waters. Both operate outside the rules of the other gods. Both save humanity through cunning rather than force. The convergence is structural, not superficial. Two cultures, five thousand kilometers apart, independently conceived of the same divine archetype.",

    "Aengus Óg": "Aengus Óg. God of youth, love, and poetry. Son of the Dagda and Boann. He tricked his father out of Newgrange by asking for it 'for a day and a night,' which in Irish cosmology means forever, since all time is composed of days and nights. He is the eternal youth. His closest parallel is the Sumerian Dumuzi, also associated with fertility and seasonal renewal. Both represent the cycle of life that persists even after death. Aengus still dwells at Newgrange.",

    "Nuada": "Nuada Airgetlám. Nuada of the Silver Hand. First king of the Tuatha Dé Danann. He lost his arm in the First Battle of Mag Tuired against the Fir Bolg. The physician Dian Cécht replaced it with a fully functional silver prosthetic. This disqualified him from kingship, as a king must be physically perfect. His son Miach later regrew the real hand. Nuada's Sumerian parallel is Anu, the supreme sky deity, king of the gods. Both represent legitimate divine authority, both are eventually succeeded by a younger, more dynamic god: Lugh replaces Nuada, just as Marduk supersedes Anu.",

    "Lugh": "Lugh Lámhfhada. Lugh of the Long Arm. Also called Samildánach, master of all arts. He arrived at the gates of Tara and when asked his skill, named every art: smith, champion, harper, poet, sorcerer, physician. The doorkeeper said 'we have one of each.' Lugh replied: 'but do you have one who masters all?' He was admitted. He killed his own grandfather Balor of the Evil Eye with a sling stone through the eye. His parallel is Marduk of Babylon, a young god who rises to supremacy through demonstrated superiority in combat and skill, overthrowing the old order.",

    "Brigid": "Brigid. Daughter of the Dagda. Triple goddess of healing, poetry, and smithcraft. Her festival is Imbolc, February first, marking the return of spring. At Loughcrew, the equinox alignment illuminates the chamber on her sacred days. She bridges pagan and Christian Ireland. Her parallel is Ninhursag, the Sumerian mother goddess associated with healing and creation. Both represent the feminine creative force that sustains life. Brigid's fire at Kildare burned for a thousand years without ash.",

    "Morrigan": "The Morrigan. Daughter of Ernmas. Triple goddess of war, fate, and sovereignty. She appears as crow, as beautiful woman, as hag. Before the Second Battle of Mag Tuired, she mated with the Dagda at the river ford, a ritual joining of war and fertility. After the battle, she prophesied both eternal peace and the end of the world. Her parallel is Inanna of Sumer, also a goddess of war and sexuality who descends to the underworld. Both exercise sovereignty: they choose who lives, who dies, who rules.",

    "Manannán mac Lir": "Manannán mac Lir. God of the sea and the Otherworld. His domain is the western ocean, the boundary between the living world and Tír na nÓg, the Land of the Young. Skellig Michael sits in his waters, an island monastery at the very edge of the known world. His parallel is Enki of Eridu, also god of the cosmic waters, also guardian of the boundary between worlds. The Abzu, Enki's underground ocean, is structurally identical to the sea beneath the sídhe mounds.",

    "Dian Cécht": "Dian Cécht. God of healing and chief physician of the Tuatha Dé Danann. He made Nuada's silver hand. He maintained the Well of Slaine during the battle, into which mortally wounded warriors were thrown and emerged whole the next day. His son Miach surpassed him by regrowing Nuada's real hand. In jealousy, Dian Cécht killed his own son with four blows to the head. Three hundred and sixty-five herbs grew from Miach's grave, one for each joint. His daughter Airmed catalogued them, but Dian Cécht scattered them. Medical knowledge, given and taken by the gods.",

    "Boann": "Boann. Goddess of the River Boyne. Mother of Aengus Óg by the Dagda. She created the River Boyne by approaching Nechtan's forbidden well. The waters rose and pursued her, tearing off her arm, her leg, and her eye. The river that formed flows past Newgrange, Knowth, and Dowth. The entire Brú na Bóinne complex, five thousand years old, sits in the bend of her river. Her parallel is Tiamat, the Babylonian primeval water goddess. Both are feminine water that shapes the landscape itself.",

    "Medb": "Medb. Queen Maeve of Connacht. Warrior queen of the Táin Bó Cúailnge. Tradition holds she is buried standing upright inside the unopened cairn atop Knocknarea mountain in Sligo, facing north toward her enemies in Ulster. Forty thousand tons of stone piled on a mountain summit, never excavated. Every passage tomb at Carrowmore below is oriented toward her cairn. She is likely a euhemerized sovereignty goddess. Her parallel is Inanna, the Sumerian warrior queen archetype. Both demand tribute. Both command armies. Both embody the land itself.",

    "Tuatha Dé Danann": "The Tuatha Dé Danann. The People of the Goddess Danu. They arrived in Ireland from the Northern Islands bearing four treasures: the Stone of Fal, the Spear of Lugh, the Sword of Nuada, and the Cauldron of the Dagda. After defeating the Fir Bolg and then the Fomorians, they were themselves defeated by the Sons of Míl, the Gaels. Rather than leave, they retreated underground into the sídhe, the fairy mounds, which are the passage tombs. They are still there. Their parallel is the Anunnaki, the gods who came from elsewhere and retreated underground. Two pantheons, same structural narrative: arrival, rule, retreat beneath the earth.",

    "Balor": "Balor of the Evil Eye. King of the Fomorians. Grandson of Net. His eye was so destructive it required four men to raise the lid, and all who looked upon it perished. He acquired this power as a youth when druid's potion fumes entered his eye. A prophecy foretold his grandson would kill him. He imprisoned his daughter Ethne on Tory Island. Despite this, she bore Lugh by Cian, son of Dian Cécht. At the Second Battle of Mag Tuired, Lugh fulfilled the prophecy, casting a sling stone through the eye, driving it out the back of Balor's head onto his own army. His parallel is Kronos of Greece, who also tried to prevent his prophesied overthrow by his offspring, and also failed.",
}


def generate_audio(entity_name: str, text: str) -> str:
    """Generate MP3 audio using Polly neural voice."""
    filename = f"brief_{entity_name.lower().replace(' ', '_').replace('á','a').replace('é','e').replace('í','i').replace('ó','o').replace('ú','u')}.mp3"
    filepath = AUDIO_DIR / filename

    response = polly.synthesize_speech(
        Text=text,
        OutputFormat="mp3",
        VoiceId="Matthew",  # Neural male voice - authoritative narrator
        Engine="neural",
    )

    with open(filepath, "wb") as f:
        f.write(response["AudioStream"].read())

    size_kb = os.path.getsize(filepath) // 1024
    print(f"  {entity_name}: {filename} ({size_kb} KB)")
    return filename


def main():
    print("=" * 60)
    print("ARCHON — Generating Audio Intelligence Briefs")
    print("=" * 60)

    audio_manifest = {}

    for entity_name, brief_text in BRIEFS.items():
        try:
            filename = generate_audio(entity_name, brief_text)
            audio_manifest[entity_name] = f"audio/{filename}"
        except Exception as e:
            print(f"  ERROR {entity_name}: {e}")

    # Save manifest
    manifest_path = AUDIO_DIR / "manifest.json"
    json.dump(audio_manifest, open(manifest_path, "w"), indent=2)
    print(f"\nWrote manifest: {manifest_path}")
    print(f"Generated {len(audio_manifest)} audio briefs")

    # Also write as JS for frontend
    js = f"// Archon Audio Briefs Manifest\nconst ARCHON_AUDIO = {json.dumps(audio_manifest, indent=2)};\n"
    js_path = PROJECT_ROOT / "src" / "frontend" / "archon-audio.js"
    open(js_path, "w").write(js)
    print(f"Wrote: {js_path}")


if __name__ == "__main__":
    main()
