"""Tier-1 keyword filter: extract MUFON-attributed records from the NUFORC UFO corpus.

MUFON (Mutual UFO Network) reports appear as text attributions embedded inside
NUFORC sighting descriptions (e.g. "MUFON/COLORADO REPORT: ..."). This script
performs a FREE ($0) keyword/regex scan over the description field and pulls the
matching rows into their own filtered set for downstream processing.

Inputs (uses whichever exists):
    docs/ufo_sightings.csv
    src/data/conspiracy-seed/ufo_sightings/ufo_sightings.csv

Outputs:
    src/data/conspiracy-seed/ufo_sightings/mufon_records.csv   (filtered rows + provenance)
    src/data/conspiracy-seed/ufo_sightings/mufon_analysis.json (summary + provenance)
"""

import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

INPUT_CANDIDATES = [
    PROJECT_ROOT / "docs" / "ufo_sightings.csv",
    PROJECT_ROOT / "src" / "data" / "conspiracy-seed" / "ufo_sightings" / "ufo_sightings.csv",
]

OUT_DIR = PROJECT_ROOT / "src" / "data" / "conspiracy-seed" / "ufo_sightings"
OUT_CSV = OUT_DIR / "mufon_records.csv"
OUT_JSON = OUT_DIR / "mufon_analysis.json"

DESC_FIELD = "Data.Description excerpt"
CITY_FIELD = "Location.City"
STATE_FIELD = "Location.State"
COUNTRY_FIELD = "Location.Country"
SHAPE_FIELD = "Data.Shape"
YEAR_FIELD = "Dates.Sighted.Year"

# Tier-1 keyword pattern: MUFON as a whole word (case-insensitive).
# Catches "MUFON", "MUFON/COLORADO REPORT", "COMUFON", "MUFON Investigator", etc.
MUFON_RE = re.compile(r"MUFON", re.IGNORECASE)


def find_input() -> Path:
    for p in INPUT_CANDIDATES:
        if p.exists():
            return p
    print("ERROR: no ufo_sightings.csv found in known locations", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    src = find_input()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    total = 0
    matched_rows = []
    by_state: dict[str, int] = {}
    by_shape: dict[str, int] = {}
    by_year: dict[str, int] = {}

    with src.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        for row in reader:
            total += 1
            desc = (row.get(DESC_FIELD) or "")
            if MUFON_RE.search(desc):
                matched_rows.append(row)
                st = (row.get(STATE_FIELD) or "?").strip()
                sh = (row.get(SHAPE_FIELD) or "?").strip()
                yr = (row.get(YEAR_FIELD) or "?").strip()
                by_state[st] = by_state.get(st, 0) + 1
                by_shape[sh] = by_shape.get(sh, 0) + 1
                by_year[yr] = by_year.get(yr, 0) + 1

    # Write filtered CSV (adds a source tag column for provenance)
    out_fields = list(fieldnames) + ["_source"]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields)
        writer.writeheader()
        for row in matched_rows:
            row = dict(row)
            row["_source"] = "NUFORC/CORGIS (MUFON-attributed)"
            writer.writerow(row)

    def top(d: dict[str, int], n: int = 15):
        return sorted(d.items(), key=lambda kv: kv[1], reverse=True)[:n]

    summary = {
        "source": "NUFORC UFO Sightings via CORGIS (MUFON-attributed subset)",
        "source_file": str(src.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "extraction_method": "Tier-1 keyword/regex scan ($0) on description field",
        "keyword": "MUFON (case-insensitive, substring)",
        "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
        "total_records_scanned": total,
        "mufon_matched": len(matched_rows),
        "match_rate_pct": round(100.0 * len(matched_rows) / total, 4) if total else 0.0,
        "top_states": top(by_state),
        "top_shapes": top(by_shape),
        "top_years": top(by_year),
        "output_csv": str(OUT_CSV.relative_to(PROJECT_ROOT)).replace("\\", "/"),
    }

    with OUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Scanned : {total} records from {src.name}")
    print(f"MUFON   : {len(matched_rows)} matched ({summary['match_rate_pct']}%)")
    print(f"CSV out : {OUT_CSV}")
    print(f"JSON out: {OUT_JSON}")
    print("\nTop states:")
    for st, c in summary["top_states"]:
        print(f"  {st:>4}  {c}")


if __name__ == "__main__":
    main()
