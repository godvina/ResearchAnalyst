"""Generate Amazon Polly voiceover for each Pattern Dossier chapter.

Reads the narration straight from src/frontend/uap-dossiers.js (so audio always matches
the text), synthesizes one MP3 per chapter with a neural documentary voice, writes them to
src/frontend/audio/dossiers/, and updates each chapter with an `audio` path in-place +
a manifest. Mirrors scripts/archon_generate_audio_briefs.py (proven Polly pattern here).

Requires AWS credentials + network. If Polly can't be reached, prints exactly what failed
and leaves the text dossier intact (no fabricated audio).

Usage: python scripts/generate_dossier_audio.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_JS = os.path.join(ROOT, "src", "frontend", "uap-dossiers.js")
AUDIO_DIR = os.path.join(ROOT, "src", "frontend", "audio", "dossiers")
VOICE = "Matthew"   # neural, authoritative documentary narrator (matches archon briefs)


def load_dossiers():
    """Parse window.UAP_DOSSIERS = {...}; out of the JS file."""
    txt = open(DOSSIER_JS, encoding="utf-8").read()
    m = re.search(r"window\.UAP_DOSSIERS\s*=\s*(\{.*\});\s*$", txt, re.S)
    if not m:
        raise SystemExit("Could not find window.UAP_DOSSIERS in uap-dossiers.js")
    return json.loads(m.group(1))


def write_dossiers(obj):
    with open(DOSSIER_JS, "w", encoding="utf-8") as f:
        f.write("// UAP Pattern Dossiers - documentary + play + AI investigator, grounded in the live signal.\n")
        f.write("window.UAP_DOSSIERS = " + json.dumps(obj, ensure_ascii=False) + ";\n")


def main():
    obj = load_dossiers()
    try:
        import boto3
        polly = boto3.client("polly", region_name="us-east-1")
    except Exception as e:
        print(f"AWS/Polly not available: {e}\nText dossier untouched. Run this where AWS creds + boto3 exist.")
        return

    os.makedirs(AUDIO_DIR, exist_ok=True)
    manifest = {}
    made = 0
    def synth(text, fn, tag):
        """Synthesize one clip -> returns relative path or None."""
        nonlocal made
        if len(text) < 40:
            return None
        fp = os.path.join(AUDIO_DIR, fn)
        rel = f"audio/dossiers/{fn}"
        try:
            resp = polly.synthesize_speech(Text=text, OutputFormat="mp3",
                                           VoiceId=VOICE, Engine="neural")
            with open(fp, "wb") as f:
                f.write(resp["AudioStream"].read())
            manifest[fn] = rel
            made += 1
            print(f"  {tag}: {fn} ({os.path.getsize(fp)//1024} KB)")
            return rel
        except Exception as e:
            print(f"  FAILED {fn}: {e}")
            return None

    for dos in obj.get("dossiers", []):
        for ch in dos.get("chapters", []):
            rel = synth(ch.get("narration") or "", f"{dos['id']}_{ch['id']}.mp3", f"{dos['id']}/{ch['id']}")
            if rel:
                ch["audio"] = rel
            # deep-dive sub-chapters carry their own narration + audio
            for d in ((ch.get("visualData") or {}).get("deep") or []):
                drel = synth(d.get("narration") or "",
                             f"{dos['id']}_{ch['id']}_{d['id']}.mp3",
                             f"{dos['id']}/{ch['id']}/deep/{d['id']}")
                if drel:
                    d["audio"] = drel

    if made:
        write_dossiers(obj)   # persist the `audio` paths back into the dossier data
        json.dump({"voice": VOICE, "files": manifest},
                  open(os.path.join(AUDIO_DIR, "manifest.json"), "w", encoding="utf-8"), indent=2)
        print(f"\nGenerated {made} clips (voice={VOICE}). Dossier updated with audio paths + manifest.")
    else:
        print("\nNo clips generated.")


if __name__ == "__main__":
    main()
