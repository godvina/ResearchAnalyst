#!/usr/bin/env python3
"""Parse the UPDB pg_dump (docs/updb/phenomenon.sql.gz) into normalized records.

Extracts the api.report table joined with api.location (city/district/country/water)
and api.source (source name). Output is a normalized JSON list of global UFO
sightings ready for Tier-1 filtering + ingest.

pg_dump COPY format: tab-separated, '\\N' = NULL, backslash escapes (\\t \\n \\\\).

Output: docs/updb/updb_reports.json
        (also prints country distribution to prove GLOBAL coverage)
"""
import gzip
import json
import os
from collections import Counter, defaultdict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DUMP = os.path.join(PROJECT_ROOT, "docs", "updb", "phenomenon.sql.gz")
OUT = os.path.join(PROJECT_ROOT, "docs", "updb", "updb_reports.json")

# COPY headers we care about (col order from the dump)
REPORT_COLS = ["id", "source", "source_id", "date", "description", "location", "date_detail"]
LOCATION_COLS = ["id", "city", "district", "country", "water", "other"]
SOURCE_COLS = ["id", "name"]


def _unescape(v):
    if v == r"\N":
        return None
    return (v.replace(r"\t", "\t").replace(r"\n", "\n").replace(r"\r", "\r").replace(r"\\", "\\"))


def parse_copy_block(f, cols):
    """Read lines of a COPY block (until a lone '\\.') into dicts keyed by cols."""
    rows = {}
    for line in f:
        if line.startswith("\\."):
            break
        line = line.rstrip("\n")
        parts = line.split("\t")
        if len(parts) != len(cols):
            continue
        rec = {c: _unescape(p) for c, p in zip(cols, parts)}
        rows[rec["id"]] = rec
    return rows


def main():
    locations, sources = {}, {}
    reports = []

    with gzip.open(DUMP, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("COPY api.location "):
                locations = parse_copy_block(f, LOCATION_COLS)
            elif line.startswith("COPY api.source "):
                sources = parse_copy_block(f, SOURCE_COLS)
            elif line.startswith("COPY api.report "):
                # stream report rows, joining as we go
                for rline in f:
                    if rline.startswith("\\."):
                        break
                    rline = rline.rstrip("\n")
                    parts = rline.split("\t")
                    if len(parts) != len(REPORT_COLS):
                        continue
                    rec = {c: _unescape(p) for c, p in zip(REPORT_COLS, parts)}
                    reports.append(rec)

    # Join
    joined = []
    for r in reports:
        loc = locations.get(r.get("location") or "", {})
        src = sources.get(r.get("source") or "", {})
        joined.append({
            "id": r["id"],
            "source": (src.get("name") if src else r.get("source")) or "UPDB",
            "date": r.get("date") or (r.get("date_detail") or ""),
            "description": r.get("description") or "",
            "city": (loc.get("city") if loc else "") or "",
            "district": (loc.get("district") if loc else "") or "",
            "country": (loc.get("country") if loc else "") or "",
            "water": (loc.get("water") if loc else "") or "",
        })

    json.dump({"count": len(joined), "reports": joined},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False)

    countries = Counter(j["country"] for j in joined if j["country"])
    src_counts = Counter(j["source"] for j in joined)
    print(f"Parsed UPDB reports: {len(joined)}")
    print(f"Locations: {len(locations)}  Sources: {len(sources)}")
    print(f"Output: {os.path.relpath(OUT, PROJECT_ROOT)}")
    print("\nTop 15 countries (proves GLOBAL coverage):")
    for c, n in countries.most_common(15):
        print(f"  {c:<22} {n}")
    print(f"\nDistinct countries: {len(countries)}")
    print("\nTop sources:")
    for s, n in src_counts.most_common(10):
        print(f"  {s:<22} {n}")


if __name__ == "__main__":
    main()
