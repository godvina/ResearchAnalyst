"""Normalize the GEIPAN (French CNES) cases into the global UAP pipeline record shape,
so France registers as a real government source in the corpus, signal, map and the
convergence / ley-line analyses.

Input:  docs/geipan/geipan_reports.json   (3,381 official French cases; from _geipan_calibrate.py)
Output: docs/geipan/geipan_pipeline_records.json  (records: id, source=GEIPAN, date,
        description, city, district, country=FR, lat, lng)

Why a dedicated normalizer (mirrors fetch_spanish_ufo_files.py):
  - GEIPAN fields are French and differently named (details/departement/year/lat/lng).
  - GEIPAN already carries REAL lat/lng per case — far better than country-centroid
    geocoding. We preserve those so French placement on the map + vertex analysis is
    accurate. The pipeline honors a pre-existing lat/lng when present.
  - We fold the official identification + A/B/C/D classification into the description
    text so the (English + French) signature matcher and the KNOWN case view keep the
    ground-truth GEIPAN disposition visible.

Provenance: GEIPAN / CNES official UAP investigations (export_cas.xlsx). Public.
"""
import json
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(PROJECT_ROOT, "docs", "geipan", "geipan_reports.json")
OUT = os.path.join(PROJECT_ROOT, "docs", "geipan", "geipan_pipeline_records.json")

# GEIPAN A/B/C/D -> plain-language disposition (already in the file as `disposition`)
DISP_LABEL = {
    "explained": "GEIPAN official: EXPLAINED (identified)",
    "insufficient": "GEIPAN official: INSUFFICIENT DATA",
    "unexplained": "GEIPAN official: UNEXPLAINED (class D)",
}


def city_from_title(title, departement):
    """GEIPAN titles look like 'MARIGOT (LE) (972) --.--.1937'. The leading token is
    the commune name. Fall back to departement. We keep it only as a label; placement
    uses the real lat/lng."""
    if title:
        # take text before the first '(' — that's the commune
        head = title.split("(")[0].strip()
        if head:
            return head.title()
    return (departement or "").strip()


def main():
    d = json.load(open(IN, encoding="utf-8"))
    reports = d["reports"] if isinstance(d, dict) and "reports" in d else d
    out = []
    kept = dropped = 0
    for r in reports:
        lat = r.get("lat")
        lng = r.get("lng")
        details = (r.get("details") or "").strip()
        if not details:
            dropped += 1
            continue
        # Compose a description that keeps the official GEIPAN judgment visible.
        disp = r.get("disposition", "")
        official = (r.get("official_identification") or "").strip()
        phenom = (r.get("phenomene") or "").strip()
        tag = DISP_LABEL.get(disp, "")
        desc = details
        extras = []
        if official:
            extras.append(f"Official identification: {official}")
        if phenom:
            extras.append(f"Phenomenon category: {phenom}")
        if tag:
            extras.append(tag)
        if extras:
            desc = desc + "  [" + " | ".join(extras) + "]"
        yr = r.get("year")
        date = f"{yr}-01-01" if yr else ""
        out.append({
            "id": f"GEIPAN-{r.get('id','')}",
            "source": "GEIPAN",
            "date": date,
            "description": desc,
            "city": city_from_title(r.get("title", ""), r.get("departement", "")),
            "district": r.get("departement", ""),
            "country": "FR",
            # Preserve the REAL GEIPAN coordinates (pipeline honors these).
            "lat": lat,
            "lng": lng,
            # ground-truth metadata carried through for the KNOWN case view
            "geipan_classification": r.get("classification", ""),
            "geipan_disposition": disp,
        })
        kept += 1

    doc = {
        "source": "GEIPAN / CNES (official French UAP investigations), export_cas.xlsx",
        "licence": "Public (French government open data)",
        "count": len(out),
        "note": "Normalized to the global UAP pipeline record shape. Real per-case lat/lng preserved.",
        "reports": out,
    }
    json.dump(doc, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    from collections import Counter
    disp_counts = Counter(r["geipan_disposition"] for r in out)
    with_coords = sum(1 for r in out if r["lat"] is not None and r["lng"] is not None)
    print(f"Built {kept} GEIPAN pipeline records ({dropped} dropped, no details) -> {os.path.relpath(OUT, PROJECT_ROOT)}")
    print(f"  with real coordinates: {with_coords}/{kept}")
    print(f"  dispositions: {dict(disp_counts)}")


if __name__ == "__main__":
    main()
