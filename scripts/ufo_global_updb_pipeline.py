#!/usr/bin/env python3
"""UPDB Global UAP Pipeline — Tiered scan + signature firing + UI data build.

Processes the global UPDB corpus (docs/updb/updb_reports.json, ~296,600 reports
across 221 countries) using the SAME Tier-1 keyword logic and signature-firing
logic as the US NUFORC pipeline (ufo_tiered_scan.py + ufo_full_corpus_signature_scan.py),
adapted to the UPDB schema (no shape column, no coordinates — geocoded here).

Per .kiro steering (tiered-data-processing): NEVER bulk-process raw data. We run
Tier 1 keyword/regex filtering first, then only signature-scan the reports that
pass. Geocoding uses public-domain country centroids + a curated world-city table
(reference geodata, NOT fabricated sightings). Reports we cannot place are counted
but excluded from map points rather than given invented coordinates.

Outputs (all grounded in the source data):
  scripts/updb_tier1_filtered.json      — reports passing the Tier-1 anomaly filter
  scripts/updb_signal_reports.json      — reports that fired >=1 signature (+ geo)
  src/frontend/uap-command-data.js       — REBUILT global UI data (window.UAP_DATA)

Usage:
    python scripts/ufo_global_updb_pipeline.py
    python scripts/ufo_global_updb_pipeline.py --max-records 20000   # quick test
"""
import argparse
import json
import os
import re
from collections import defaultdict, Counter
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPDB = os.path.join(PROJECT_ROOT, "docs", "updb", "updb_reports.json")
TAX = os.path.join(PROJECT_ROOT, "src", "data", "ufo-uap-taxonomy.json")
TIER1_OUT = os.path.join(PROJECT_ROOT, "scripts", "updb_tier1_filtered.json")
SIGNAL_OUT = os.path.join(PROJECT_ROOT, "scripts", "updb_signal_reports.json")
UI_OUT = os.path.join(PROJECT_ROOT, "src", "frontend", "uap-command-data.js")

# ============================================================
# Tier 1 keyword patterns — copied verbatim from ufo_tiered_scan.py
# so global filtering is identical to the US pipeline.
# ============================================================
KEYWORD_PATTERNS = {
    "impossible_kinematics": [
        "instant", "instantly", "instantaneous", "shot off", "shot up", "sped off",
        "right angle", "90 degree", "sharp turn", "zig zag", "zigzag", "no sound",
        "silent", "accelerat", "disappeared instantly", "vanished", "hovering",
        "hovered", "stationary", "motionless", "against the wind", "changed direction",
        # Spanish (ES-AIRFORCE)
        "silencioso", "sin ruido", "instant\u00e1neo", "gran velocidad", "inm\u00f3vil",
        "estacionario", "desapareci\u00f3", "\u00e1ngulo recto", "aceler",
        # French (GEIPAN)
        "silencieux", "sans bruit", "grande vitesse", "immobile", "stationnaire",
        "disparu", "disparait", "dispara\u00eet", "angle droit", "acc\u00e9l\u00e9r",
        "brusquement", "stoppant", "changement de direction", "trajectoire",
        # Russian (RU-SAMIZDAT / Soviet), transliteration + Cyrillic
        "beshumno", "besshumno", "zavis", "nepodvizhn", "ischez", "isчез",
        "\u0431\u0435\u0441\u0448\u0443\u043c\u043d", "\u0437\u0430\u0432\u0438\u0441", "\u043d\u0435\u043f\u043e\u0434\u0432\u0438\u0436\u043d",
        "\u0438\u0441\u0447\u0435\u0437", "\u043c\u0433\u043d\u043e\u0432\u0435\u043d\u043d",
        # Japanese (JP): silent, hovered, vanished, high-speed, motionless
        "\u9759\u304b", "\u7121\u97f3", "\u9759\u6b62", "\u9ad8\u901f", "\u6d88\u3048",
        "\u30db\u30d0\u30ea\u30f3\u30b0", "\u98db\u884c",
    ],
    "em_physical_effects": [
        "engine died", "engine stalled", "car stalled", "electrical", "power went out",
        "radio static", "compass", "interference", "burn", "sunburn", "radiation",
        "paralyz", "could not move", "scorched", "landing marks", "trace", "melted",
    ],
    "radar_visual": [
        "radar", "air traffic", "atc", "flir", "tracked", "confirmed by", "scrambled",
        "tower", "picked up on",
        # French (GEIPAN)
        "contr\u00f4le a\u00e9rien", "tour de contr\u00f4le", "contr\u00f4leur",
        "d\u00e9tect\u00e9 au radar", "confirm\u00e9 par",
    ],
    "structured_craft": [
        "triangle", "triangular", "delta", "disc", "disk", "saucer", "dome", "domed",
        "metallic", "cylinder", "cigar", "sphere", "spherical", "orb", "craft",
        "structured", "solid object", "windows", "portholes",
        # Spanish
        "tri\u00e1ngulo", "disco", "platillo", "met\u00e1lico", "cilindro", "esfera",
        "esf\u00e9rico", "c\u00fapula", "objeto s\u00f3lido", "luces", "luz",
        # French (GEIPAN)
        "disque", "soucoupe", "sph\u00e8re", "sph\u00e9rique", "m\u00e9tallique",
        "cylindre", "cylindrique", "coupole", "objet", "lumi\u00e8re", "lumineux",
        "boule", "globe", "engin", "forme",
        # Amorphous/plasma morphology (Petrozavodsk-type) — EN + RU
        "jellyfish", "amorphous", "plasma", "glowing mass", "beam of light", "rays of light",
        "meduza", "\u043c\u0435\u0434\u0443\u0437", "\u0448\u0430\u0440", "\u0441\u0432\u0435\u0447\u0435\u043d\u0438",
        # Russian craft/object terms (Cyrillic)
        "\u0434\u0438\u0441\u043a", "\u0448\u0430\u0440\u043e\u043e\u0431\u0440\u0430\u0437", "\u043e\u0431\u044a\u0435\u043a\u0442", "\u0441\u0432\u0435\u0442\u044f\u0449",
        # Japanese (JP): UFO, unidentified, disc, sphere, triangle, glowing, lights
        "\u672a\u78ba\u8a8d\u98db\u884c\u7269\u4f53", "\u5186\u76e4", "\u7403\u4f53", "\u4e09\u89d2\u5f62", "\u767a\u5149", "\u5149\u3063\u3066", "\u98db\u884c\u7269\u4f53",
    ],
    "encounter_quality": [
        "close range", "landed", "landing", "occupant", "figure", "being", "entity",
        "abduct", "multiple witnesses", "several people", "everyone saw", "crowd",
        "many people", "family", "we all saw",
        # French (GEIPAN)
        "atterri", "atterrissage", "t\u00e9moin", "t\u00e9moins", "plusieurs personnes",
        "occupant", "silhouette", "\u00e0 faible distance", "de pr\u00e8s",
    ],
    "credible_witness": [
        "pilot", "police", "officer", "sheriff", "military", "air force", "navy",
        "controller", "scientist", "engineer", "retired", "trained observer",
        # French (GEIPAN)
        "pilote", "gendarme", "gendarmerie", "militaire", "arm\u00e9e de l'air",
        "officier", "ing\u00e9nieur", "policier",
    ],
    "institutional": [
        "government", "military", "classified", "cover up", "cover-up", "told not to",
        "confiscated", "officials", "investigation", "base", "restricted airspace",
        "men in black", "denied",
        # strategic-weapons / nuclear-facility interference + military engagement (Soviet seed)
        "missile", "nuclear", "silo", "launch", "warhead", "command", "reactor",
        "shot down", "fired on", "downed", "engaged", "retaliat", "kgb", "setka",
        # French (GEIPAN)
        "gouvernement", "enqu\u00eate", "arm\u00e9e", "base a\u00e9rienne",
        "espace a\u00e9rien", "confisqu\u00e9",
        # Russian (Cyrillic)
        "\u0432\u043e\u0435\u043d\u043d", "\u0440\u0430\u043a\u0435\u0442", "\u044f\u0434\u0435\u0440\u043d", "\u043a\u0433\u0431",
        "\u0441\u0435\u043a\u0440\u0435\u0442\u043d", "\u0440\u0430\u0441\u0441\u043b\u0435\u0434\u043e\u0432\u0430\u043d",
        # Japanese (JP): Self-Defense Force, military, nuclear power, investigation
        "\u81ea\u885b\u968a", "\u8ecd", "\u539f\u767a", "\u539f\u5b50\u529b", "\u8abf\u67fb",
    ],
}
NEGATIVE_PATTERNS = {
    "likely_misid": [
        "probably a plane", "was a plane", "must have been", "satellite", "starlink",
        "chinese lantern", "sky lantern", "weather balloon", "was venus", "was the moon",
        "shooting star", "meteor", "firework", "drone", "helicopter", "flare",
        "hoax", "probably", "explanation: meteor", "explanation:",
        # French (GEIPAN official identifications of prosaic causes)
        "ballon", "lanterne", "montgolfi\u00e8re", "satellite", "rentr\u00e9e atmosph\u00e9rique",
        "avion", "h\u00e9licopt\u00e8re", "plan\u00e8te", "v\u00e9nus", "\u00e9toile",
        "m\u00e9t\u00e9ore", "feu d'artifice", "cerf-volant", "ph\u00e9nom\u00e8ne astronomique",
        "confusion", "m\u00e9prise",
    ],
}
REGEX_PATTERNS = {
    "duration_reference": r'\b\d+\s?(second|minute|hour|min|sec)s?\b',
    "altitude_reference": r'\b\d{2,5}\s?(feet|ft|meters|m)\b',
    "count_of_objects": r'\b(\d{1,3})\s?(objects|lights|craft|orbs|discs|triangles)\b',
    "speed_reference": r'\b(mph|knots|km/h)\b',
}
COMPILED_REGEX = {n: re.compile(p, re.IGNORECASE) for n, p in REGEX_PATTERNS.items()}
MIN_KEYWORD_HITS = 2
HIGH_VALUE_CATEGORIES = ["impossible_kinematics", "em_physical_effects", "radar_visual"]

# Map Tier-1 category proxies -> taxonomy typologies (for rollup coloring)
CATEGORY_TO_TYPOLOGY = {
    "impossible_kinematics": "flight_kinematics",
    "em_physical_effects": "sensor_em_signatures",
    "radar_visual": "sensor_em_signatures",
    "structured_craft": "craft_morphology",
    "encounter_quality": "encounter_typology",
    "credible_witness": "witness_reliability",
    "institutional": "institutional_response",
}


def score_report_tier1(text):
    blob = text.lower()
    hits, total, high_value = {}, 0, False
    for category, keywords in KEYWORD_PATTERNS.items():
        cat_hits = [kw for kw in keywords if kw in blob]
        if cat_hits:
            hits[category] = cat_hits
            total += len(cat_hits)
            if category in HIGH_VALUE_CATEGORIES:
                high_value = True
    regex_hits = {}
    for name, pat in COMPILED_REGEX.items():
        m = pat.findall(text)
        if m:
            regex_hits[name] = len(m)
            total += len(m)
    neg_hits = []
    for kws in NEGATIVE_PATTERNS.values():
        neg_hits.extend([kw for kw in kws if kw in blob])
    penalty = len(neg_hits)
    priority = total - penalty
    keep = (total >= MIN_KEYWORD_HITS) or high_value
    return {"keyword_hits": hits, "regex_hits": regex_hits, "negative_hits": neg_hits,
            "raw_score": total, "penalty": penalty, "priority_score": priority, "keep": keep}


# ============================================================
# Signature firing — same token logic as ufo_full_corpus_signature_scan.py
# ============================================================
STOP = set("a an the of to in on at and or is are was were with no not this that "
           "it its as for by from up down over under out into within near above "
           "below than then so if would could should may might per each any all "
           "which who whom whose when where how".split())
MIN_NEEDLES = 2


def needle_tokens(indicator):
    words = re.findall(r"[a-z0-9']+", indicator.lower())
    return [w for w in words if w not in STOP and len(w) > 3]


def load_signatures():
    tax = json.load(open(TAX, encoding="utf-8"))
    sigs = []
    meta = {}
    for typ in tax["typologies"]:
        for method in typ["methods"]:
            for s in method["signatures"]:
                entry = {
                    "signature_id": s["signature_id"],
                    "typology": typ["typology_id"],
                    "typology_name": typ["name"],
                    "method": method["method_id"],
                    "severity": s["severity"],
                    "description": s["description"],
                    "indicators": s["indicators"],
                    "precedent_case": s.get("precedent_case", ""),
                    "needle_tokens": [needle_tokens(i) for i in s["indicators"]],
                }
                sigs.append(entry)
                meta[s["signature_id"]] = entry
    return tax, sigs, meta


def fire_signatures(blob, sigs):
    fired = []
    for sig in sigs:
        hit = 0
        for toks in sig["needle_tokens"]:
            if not toks:
                continue
            present = sum(1 for t in toks if t in blob)
            if present >= max(1, len(toks) // 2):
                hit += 1
        if hit >= MIN_NEEDLES:
            fired.append(sig["signature_id"])
    return fired


# ============================================================
# Geocoding — public-domain country centroids + curated world cities.
# Reference geodata only. Reports we cannot place are excluded from the
# map (counted as unplaced) rather than given invented coordinates.
# ============================================================
COUNTRY_CENTROIDS = {
    "US": (39.8, -98.6), "CA": (56.1, -106.3), "GB": (54.0, -2.0), "AU": (-25.3, 133.8),
    "FR": (46.2, 2.2), "BR": (-14.2, -51.9), "DE": (51.2, 10.5), "MX": (23.6, -102.6),
    "IN": (22.4, 78.7), "ES": (40.5, -3.7), "IT": (41.9, 12.6), "AR": (-38.4, -63.6),
    "SE": (60.1, 18.6), "NZ": (-40.9, 174.9), "ZA": (-30.6, 22.9), "JP": (36.2, 138.3),
    "DK": (56.3, 9.5), "CN": (35.9, 104.2), "RU": (61.5, 105.3), "CH": (46.8, 8.2),
    "IE": (53.4, -8.2), "CL": (-35.7, -71.5), "PT": (39.4, -8.2), "BE": (50.5, 4.5),
    "NL": (52.1, 5.3), "NO": (60.5, 8.5), "FI": (61.9, 25.7), "AT": (47.5, 14.6),
    "PL": (51.9, 19.1), "GR": (39.1, 21.8), "TR": (39.0, 35.2), "PH": (12.9, 121.8),
    "MY": (4.2, 101.9), "ID": (-0.8, 113.9), "TH": (15.9, 100.9), "KR": (35.9, 127.8),
    "CO": (4.6, -74.3), "PE": (-9.2, -75.0), "VE": (6.4, -66.6), "EG": (26.8, 30.8),
    "IL": (31.0, 34.9), "AE": (23.4, 53.8), "SA": (23.9, 45.1), "PK": (30.4, 69.3),
    "UA": (48.4, 31.2), "RO": (45.9, 24.9), "HU": (47.2, 19.5), "CZ": (49.8, 15.5),
    "HR": (45.1, 15.2), "RS": (44.0, 21.0), "BG": (42.7, 25.5), "SK": (48.7, 19.7),
    "SI": (46.2, 14.8), "IS": (65.0, -18.6), "LT": (55.2, 23.9), "LV": (56.9, 24.6),
    "EE": (58.6, 25.0), "HK": (22.3, 114.2), "SG": (1.35, 103.8), "TW": (23.7, 121.0),
    "VN": (14.1, 108.3), "NG": (9.1, 8.7), "KE": (-0.0, 37.9), "MA": (31.8, -7.1),
    "PR": (18.2, -66.6), "CR": (9.7, -83.8), "PA": (8.5, -80.8), "GT": (15.8, -90.2),
    "EC": (-1.8, -78.2), "UY": (-32.5, -55.8), "PY": (-23.4, -58.4), "BO": (-16.3, -63.6),
    "DO": (18.7, -70.2), "JM": (18.1, -77.3), "TT": (10.7, -61.2), "CU": (21.5, -77.8),
}
WORLD_CITIES = {
    ("london", "GB"): (51.5074, -0.1278), ("manchester", "GB"): (53.4808, -2.2426),
    ("birmingham", "GB"): (52.4862, -1.8904), ("glasgow", "GB"): (55.8642, -4.2518),
    ("liverpool", "GB"): (53.4084, -2.9916), ("edinburgh", "GB"): (55.9533, -3.1883),
    ("bristol", "GB"): (51.4545, -2.5879), ("leeds", "GB"): (53.8008, -1.5491),
    ("toronto", "CA"): (43.6532, -79.3832), ("vancouver", "CA"): (49.2827, -123.1207),
    ("montreal", "CA"): (45.5017, -73.5673), ("calgary", "CA"): (51.0447, -114.0719),
    ("ottawa", "CA"): (45.4215, -75.6972), ("edmonton", "CA"): (53.5461, -113.4938),
    ("winnipeg", "CA"): (49.8951, -97.1384), ("halifax", "CA"): (44.6488, -63.5752),
    ("sydney", "AU"): (-33.8688, 151.2093), ("melbourne", "AU"): (-37.8136, 144.9631),
    ("brisbane", "AU"): (-27.4698, 153.0251), ("perth", "AU"): (-31.9505, 115.8605),
    ("adelaide", "AU"): (-34.9285, 138.6007), ("canberra", "AU"): (-35.2809, 149.1300),
    ("paris", "FR"): (48.8566, 2.3522), ("marseille", "FR"): (43.2965, 5.3698),
    ("lyon", "FR"): (45.7640, 4.8357), ("toulouse", "FR"): (43.6047, 1.4442),
    ("berlin", "DE"): (52.5200, 13.4050), ("munich", "DE"): (48.1351, 11.5820),
    ("hamburg", "DE"): (53.5511, 9.9937), ("frankfurt", "DE"): (50.1109, 8.6821),
    ("cologne", "DE"): (50.9375, 6.9603),
    ("madrid", "ES"): (40.4168, -3.7038), ("barcelona", "ES"): (41.3851, 2.1734),
  ("sevilla", "ES"): (37.3891, -5.9845), ("valencia", "ES"): (39.4699, -0.3763),
  ("zaragoza", "ES"): (41.6488, -0.8891), ("canarias", "ES"): (28.2916, -16.6291),
  ("tenerife", "ES"): (28.4636, -16.2518), ("las palmas", "ES"): (28.1235, -15.4363),
  ("gerona", "ES"): (41.9794, 2.8214), ("burgos", "ES"): (42.3439, -3.6969),
  ("murcia", "ES"): (37.9922, -1.1307), ("mallorca", "ES"): (39.6953, 3.0176),
  ("menorca", "ES"): (39.9496, 4.1100), ("alicante", "ES"): (38.3452, -0.4810),
  ("navarra", "ES"): (42.6954, -1.6761), ("lerida", "ES"): (41.6176, 0.6200),
  ("reus", "ES"): (41.1550, 1.1075), ("san javier", "ES"): (37.8060, -0.8377),
  ("el ferrol", "ES"): (43.4890, -8.2225), ("gijon", "ES"): (43.5322, -5.6611),
    ("rome", "IT"): (41.9028, 12.4964), ("milan", "IT"): (45.4642, 9.1900),
    ("naples", "IT"): (40.8518, 14.2681),
    ("tokyo", "JP"): (35.6762, 139.6503), ("osaka", "JP"): (34.6937, 135.5023),
    ("mexico city", "MX"): (19.4326, -99.1332), ("guadalajara", "MX"): (20.6597, -103.3496),
    ("sao paulo", "BR"): (-23.5505, -46.6333), ("rio de janeiro", "BR"): (-22.9068, -43.1729),
    ("buenos aires", "AR"): (-34.6037, -58.3816),
    ("santiago", "CL"): (-33.4489, -70.6693), ("lima", "PE"): (-12.0464, -77.0428),
    ("bogota", "CO"): (4.7110, -74.0721), ("caracas", "VE"): (10.4806, -66.9036),
    ("mumbai", "IN"): (19.0760, 72.8777), ("delhi", "IN"): (28.7041, 77.1025),
    ("new delhi", "IN"): (28.6139, 77.2090), ("bangalore", "IN"): (12.9716, 77.5946),
    ("moscow", "RU"): (55.7558, 37.6173), ("saint petersburg", "RU"): (59.9311, 30.3609),
    ("beijing", "CN"): (39.9042, 116.4074), ("shanghai", "CN"): (31.2304, 121.4737),
    ("hong kong", "HK"): (22.3193, 114.1694), ("singapore", "SG"): (1.3521, 103.8198),
    ("auckland", "NZ"): (-36.8485, 174.7633), ("wellington", "NZ"): (-41.2865, 174.7762),
    ("dublin", "IE"): (53.3498, -6.2603), ("amsterdam", "NL"): (52.3676, 4.9041),
    ("brussels", "BE"): (50.8503, 4.3517), ("zurich", "CH"): (47.3769, 8.5417),
    ("stockholm", "SE"): (59.3293, 18.0686), ("oslo", "NO"): (59.9139, 10.7522),
    ("copenhagen", "DK"): (55.6761, 12.5683), ("helsinki", "FI"): (60.1699, 24.9384),
    ("vienna", "AT"): (48.2082, 16.3738), ("warsaw", "PL"): (52.2297, 21.0122),
    ("athens", "GR"): (37.9838, 23.7275), ("istanbul", "TR"): (41.0082, 28.9784),
    ("cape town", "ZA"): (-33.9249, 18.4241), ("johannesburg", "ZA"): (-26.2041, 28.0473),
    ("lisbon", "PT"): (38.7223, -9.1393), ("cairo", "EG"): (30.0444, 31.2357),
    ("tel aviv", "IL"): (32.0853, 34.7818), ("dubai", "AE"): (25.2048, 55.2708),
}

# small deterministic jitter so many reports in one country don't stack on one pixel
def _jitter(lat, lng, key):
    h = abs(hash(key))
    dlat = ((h % 1000) / 1000.0 - 0.5) * 1.6      # +-0.8 deg
    dlng = (((h // 1000) % 1000) / 1000.0 - 0.5) * 1.6
    return round(lat + dlat, 4), round(lng + dlng, 4)


def geocode(city, country, rid):
    city_l = (city or "").strip().lower()
    country = (country or "").strip().upper()
    if city_l and country and (city_l, country) in WORLD_CITIES:
        lat, lng = WORLD_CITIES[(city_l, country)]
        return lat, lng, "city"
    if country in COUNTRY_CENTROIDS:
        lat, lng = COUNTRY_CENTROIDS[country]
        lat, lng = _jitter(lat, lng, rid)
        return lat, lng, "country"
    return None, None, "unplaced"


COUNTRY_NAMES = {
    "US": "United States", "CA": "Canada", "GB": "United Kingdom", "AU": "Australia",
    "FR": "France", "BR": "Brazil", "DE": "Germany", "MX": "Mexico", "IN": "India",
    "ES": "Spain", "IT": "Italy", "AR": "Argentina", "SE": "Sweden", "NZ": "New Zealand",
    "ZA": "South Africa", "JP": "Japan", "DK": "Denmark", "CN": "China", "RU": "Russia",
    "CH": "Switzerland", "IE": "Ireland", "CL": "Chile", "PT": "Portugal", "BE": "Belgium",
}


def year_of(date_str):
    m = re.match(r"(\d{4})", date_str or "")
    return m.group(1) if m else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-records", type=int, default=None)
    args = ap.parse_args()

    print("Loading taxonomy + UPDB...")
    tax, sigs, sig_meta = load_signatures()
    data = json.load(open(UPDB, encoding="utf-8", errors="replace"))
    reports = data["reports"]
    if args.max_records:
        reports = reports[: args.max_records]
    # Merge additional public-domain sources (Spanish Air Force OVNI files).
    es_path = os.path.join(PROJECT_ROOT, "docs", "spanish-ufo", "spain_airforce_ufo.json")
    if os.path.exists(es_path):
        es = json.load(open(es_path, encoding="utf-8"))
        reports = reports + es["reports"]
        print(f"  + merged {es['count']} Spanish Air Force (ES-AIRFORCE) records")
    # Merge GEIPAN (French CNES official cases) — real per-case lat/lng preserved.
    fr_path = os.path.join(PROJECT_ROOT, "docs", "geipan", "geipan_pipeline_records.json")
    if os.path.exists(fr_path):
        fr = json.load(open(fr_path, encoding="utf-8"))
        reports = reports + fr["reports"]
        print(f"  + merged {fr['count']} GEIPAN (FR / CNES official) records")
    # Merge Russian/Soviet corpus (RU-SAMIZDAT) — UFO Chronicles of the Soviet Union.
    ru_path = os.path.join(PROJECT_ROOT, "docs", "russia-ufo", "russia_ufo.json")
    if os.path.exists(ru_path):
        ru = json.load(open(ru_path, encoding="utf-8"))
        reports = reports + ru["reports"]
        print(f"  + merged {ru['count']} RU-SAMIZDAT (Soviet UFO Chronicles) records")
    # Merge Ukraine Kyiv Observatory instrument-measured UAP events (UA-KYIV-OBS).
    ua_path = os.path.join(PROJECT_ROOT, "docs", "ukraine-uap", "ukraine_uap.json")
    if os.path.exists(ua_path):
        ua = json.load(open(ua_path, encoding="utf-8"))
        reports = reports + ua["reports"]
        print(f"  + merged {ua['count']} UA-KYIV-OBS (Kyiv Observatory scientific) records")
    # Merge Japan documented-precedent cases (JP-SEED).
    jp_path = os.path.join(PROJECT_ROOT, "docs", "japan-ufo", "japan_uap.json")
    if os.path.exists(jp_path):
        jp = json.load(open(jp_path, encoding="utf-8"))
        reports = reports + jp["reports"]
        print(f"  + merged {jp['count']} JP-SEED (Japan documented cases) records")
    # Merge Galileo Project instrument-census records (GALILEO, NGO scientific).
    gal_path = os.path.join(PROJECT_ROOT, "docs", "galileo", "galileo_uap.json")
    if os.path.exists(gal_path):
        gal = json.load(open(gal_path, encoding="utf-8"))
        reports = reports + gal["reports"]
        print(f"  + merged {gal['count']} GALILEO (Harvard IR array, NGO) records")
    # Merge government UAP committees (Belgium/Chile/Brazil/Argentina/Peru/Uruguay).
    gc_path = os.path.join(PROJECT_ROOT, "docs", "govt-committees", "govt_committees.json")
    if os.path.exists(gc_path):
        gc = json.load(open(gc_path, encoding="utf-8"))
        reports = reports + gc["reports"]
        print(f"  + merged {gc['count']} government-committee (BE/CL/BR/AR/PE/UY) records")
    # Merge Project Hessdalen (Norway) instrumented recurring-hotspot field station.
    no_path = os.path.join(PROJECT_ROOT, "docs", "hessdalen", "hessdalen_uap.json")
    if os.path.exists(no_path):
        no = json.load(open(no_path, encoding="utf-8"))
        reports = reports + no["reports"]
        print(f"  + merged {no['count']} NO-HESSDALEN (Norway field station) records")
    # Merge roadmap-tail documented cases (Mexico SEDENA, Italy CUN).
    rt_path = os.path.join(PROJECT_ROOT, "docs", "roadmap-tail", "roadmap_tail_uap.json")
    if os.path.exists(rt_path):
        rt = json.load(open(rt_path, encoding="utf-8"))
        reports = reports + rt["reports"]
        print(f"  + merged {rt['count']} roadmap-tail (MX/IT) records")
    # Merge US nuclear-UAP documented anchor cases (Nuclear Sentinel dossier landmarks).
    un_path = os.path.join(PROJECT_ROOT, "docs", "us-nuclear", "us_nuclear_uap.json")
    if os.path.exists(un_path):
        un = json.load(open(un_path, encoding="utf-8"))
        reports = reports + un["reports"]
        print(f"  + merged {un['count']} US-NUKE-DOCUMENTED (Malmstrom/SAC/Rendlesham) records")
    total = len(reports)
    print(f"  {total} reports, {len(sigs)} signatures")

    # ---- Tier 1 filter ----
    tier1 = []
    cat_stats = Counter()
    for r in reports:
        desc = r.get("description") or ""
        if not desc:
            continue
        sc = score_report_tier1(desc)
        if sc["keep"]:
            tier1.append((r, sc))
            for c in sc["keyword_hits"]:
                cat_stats[c] += 1
    kept = len(tier1)
    print(f"  Tier 1: kept {kept}/{total} ({100.0*kept/total:.1f}%), discarded {total-kept}")

    json.dump({
        "tier": 1, "source": "docs/updb/updb_reports.json",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_scanned": total, "total_kept": kept,
        "filter_rate_pct": round(100.0*kept/total, 2),
        "category_stats": dict(cat_stats),
    }, open(TIER1_OUT, "w", encoding="utf-8"), indent=2)

    # ---- Signature firing on Tier-1 survivors + geocode ----
    signal = []
    per_sig_fire = Counter()
    typ_report = Counter()
    cooccur = Counter()               # (sigA, sigB) undirected
    sig_country = defaultdict(Counter)
    sig_shape = defaultdict(Counter)  # UPDB has no shape; leave for parity/empty
    country_counter = Counter()
    placed = unplaced = 0

    for r, sc in tier1:
        desc = r["description"]
        blob = desc.lower()
        fired = fire_signatures(blob, sigs)
        if not fired:
            continue
        country = (r.get("country") or "").strip().upper()
        city = r.get("city") or ""
        # Honor a source-supplied real lat/lng (e.g. GEIPAN carries exact coords)
        # before falling back to city/country geocoding.
        if r.get("lat") is not None and r.get("lng") is not None:
            lat, lng, gtype = r["lat"], r["lng"], "source"
        else:
            lat, lng, gtype = geocode(city, country, r.get("id", ""))
        if gtype == "unplaced":
            unplaced += 1
        else:
            placed += 1
        country_counter[country or "??"] += 1
        typs = sorted({sig_meta[s]["typology"] for s in fired})
        for s in fired:
            per_sig_fire[s] += 1
            if country:
                sig_country[s][country] += 1
        for t in typs:
            typ_report[t] += 1
        for i in range(len(fired)):
            for j in range(i+1, len(fired)):
                a, b = sorted((fired[i], fired[j]))
                cooccur[(a, b)] += 1
        signal.append({
            "id": r.get("id", ""),
            "city": city, "country": country,
            "district": r.get("district", ""),
            "lat": lat, "lng": lng, "geo": gtype,
            "year": year_of(r.get("date", "")),
            "source": r.get("source", ""),
            "description": desc[:600],
            "fired_signatures": fired,
            "typologies": typs,
            "signature_count": len(fired),
        })

    signal.sort(key=lambda x: x["signature_count"], reverse=True)
    json.dump({"count": len(signal), "placed": placed, "unplaced": unplaced,
               "reports": signal}, open(SIGNAL_OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"  Signal reports: {len(signal)} (placed {placed}, unplaced {unplaced})")

    # ---- Build UI data (window.UAP_DATA) ----
    # typology rollup with per-signature fired counts + needles
    typ_rollup = {}
    for typ in tax["typologies"]:
        tid = typ["typology_id"]
        sig_rows = []
        crit = 0
        for method in typ["methods"]:
            for s in method["signatures"]:
                sid = s["signature_id"]
                if s["severity"] == "critical":
                    crit += 1
                sig_rows.append({
                    "id": sid, "severity": s["severity"],
                    "fired": per_sig_fire.get(sid, 0),
                    "description": s["description"],
                    "needles": s["indicators"],
                    "precedent_case": s.get("precedent_case", ""),
                })
        typ_rollup[tid] = {
            "name": typ["name"], "icon": typ.get("icon", ""),
            "reports": typ_report.get(tid, 0),
            "critical": crit,
            "signatures": sig_rows,
        }

    # sig_meta lookup for the drill-down / insight panel
    sig_meta_out = {}
    for sid, m in sig_meta.items():
        sig_meta_out[sid] = {
            "typology": m["typology"], "typology_name": m["typology_name"],
            "method": m["method"], "severity": m["severity"],
            "description": m["description"], "needles": m["indicators"],
            "precedent_case": m["precedent_case"],
            "fired": per_sig_fire.get(sid, 0),
            "top_countries": dict(sig_country[sid].most_common(8)),
        }

    # per-signature -> the geolocated reports that fired it (capped for payload size)
    sig_points = defaultdict(list)
    for rep in signal:
        if rep["lat"] is None:
            continue
        for sid in rep["fired_signatures"]:
            if len(sig_points[sid]) < 400:
                sig_points[sid].append({
                    "lat": rep["lat"], "lng": rep["lng"], "city": rep["city"],
                    "country": rep["country"], "year": rep["year"],
                    "n": rep["signature_count"], "geo": rep["geo"],
                })

    # global map points (all placed signal reports, capped)
    map_points = []
    for rep in signal:
        if rep["lat"] is None:
            continue
        map_points.append({
            "lat": rep["lat"], "lng": rep["lng"], "city": rep["city"],
            "country": rep["country"], "year": rep["year"],
            "sigs": rep["signature_count"],
            "top_sig": rep["fired_signatures"][0] if rep["fired_signatures"] else "",
            "geo": rep["geo"],
        })
    map_points = map_points[:5000]

    # co-occurrence edges for the knowledge graph (signature<->signature)
    edges = [{"a": a, "b": b, "w": w} for (a, b), w in cooccur.most_common(200)]

    # country rollup for the choropleth / sidebar
    country_rollup = [{"country": c, "name": COUNTRY_NAMES.get(c, c), "reports": n}
                      for c, n in country_counter.most_common() if c != "??"]

    # tiers (same 4-tier structure, now global)
    def top_sigs_for(typ_ids, n=8):
        rows = []
        for tid in typ_ids:
            for s in typ_rollup.get(tid, {}).get("signatures", []):
                rows.append({"id": s["id"], "fired": s["fired"], "sev": s["severity"],
                             "typ": tid, "desc": s["description"]})
        rows.sort(key=lambda x: (x["sev"] != "critical", -x["fired"]))
        return rows[:n]

    tiers = {
        "tier1_bring_me_these": {
            "label": "Tier 1 - Highest priority (critical + corroborated)",
            "desc": "Cases firing critical signatures (impossible kinematics, radar-visual, trans-medium/USO, military).",
            "typologies": ["flight_kinematics", "sensor_em_signatures"],
            "top_signatures": top_sigs_for(["flight_kinematics", "sensor_em_signatures"]),
        },
        "tier2_waves_clusters": {
            "label": "Tier 2 - Global hotspots (by country)",
            "desc": f"{len([c for c in country_counter if c!='??'])} countries with signature-firing reports.",
            "country_rollup": country_rollup[:40],
        },
        "tier3_cross_cutting": {
            "label": "Tier 3 - Cross-cutting anomalies (institutional/suppression)",
            "desc": "Cases bridging to conspiracy/crime domains (official involvement, suppression).",
            "typologies": ["institutional_response", "witness_reliability", "encounter_typology"],
        },
        "tier4_explained": {
            "label": "Tier 4 - Explained / low-signal (down-ranked)",
            "desc": "Prosaic/misID down-ranked via negative signals.",
        },
    }

    out = {
        "generated_from": "updb_global (296k) tiered scan + taxonomy",
        "source_file": "docs/updb/updb_reports.json",
        "corpus_total": total,
        "tier1_kept": kept,
        "reports_firing": len(signal),
        "signatures_total": len(sigs),
        "countries_total": len([c for c in country_counter if c != "??"]),
        "geo_placed": placed, "geo_unplaced": unplaced,
        "typology_rollup": typ_rollup,
        "sig_meta": sig_meta_out,
        "per_signature_fire": dict(per_sig_fire),
        "sig_points": {k: v for k, v in sig_points.items()},
        "cooccurrence_edges": edges,
        "country_rollup": country_rollup,
        "map_points": map_points,
        "tiers": tiers,
    }

    with open(UI_OUT, "w", encoding="utf-8") as f:
        f.write("// UAP Command Center data - GLOBAL (UPDB) - generated by scripts/ufo_global_updb_pipeline.py\n")
        f.write("// Grounded in docs/updb/updb_reports.json. Coordinates are reference geodata (country centroid / curated city), not source-provided.\n")
        f.write("window.UAP_DATA = " + json.dumps(out, ensure_ascii=False) + ";\n")

    # ---- Case store: curated rich reports for the static Case File view ----
    # 178K full-text records are too large for the browser. Emit the richest
    # ~1400 (verbatim description, source, geo, fired signatures) as inspectable
    # case files. Selection favors longer narratives + more signatures, and keeps
    # source diversity so BLUEBOOK / UKGOV / PILOTS etc. are represented.
    SOURCE_URLS = {
        "NUFORC": "https://nuforc.org/databank/",
        "MUFON": "https://mufon.com/",
        "UFODNA": "http://www.ufodna.com/",
        "BLUEBOOK": "https://www.archives.gov/research/military/air-force/ufos",
        "NICAP": "https://www.nicap.org/",
        "UKGOV": "https://www.nationalarchives.gov.uk/ufos/",
        "CANADAGOV": "https://www.bac-lac.gc.ca/eng/discover/unusual/ufo/Pages/ufo.aspx",
        "NIDS": "https://en.wikipedia.org/wiki/National_Institute_for_Discovery_Science",
        "SKINWALKER": "https://en.wikipedia.org/wiki/Skinwalker_Ranch",
        "PILOTS": "https://nuforc.org/databank/",
        "GEIPAN": "https://www.cnes-geipan.fr/",
        "ES-AIRFORCE": "https://archive.org/details/SpanishUFOFiles",
        "RU-SAMIZDAT": "https://archive.org/details/B-001-002-573",
        "UA-KYIV-OBS": "https://arxiv.org/abs/2211.17085",
        "JP-SEED": "https://thediplomat.com/2021/07/a-brief-history-of-ufos-in-japan/",
        "GALILEO": "https://arxiv.org/abs/2411.07956",
        "BE-SOBEPS": "https://en.wikipedia.org/wiki/Belgian_UFO_wave",
        "CL-CEFAA": "https://www.cefaa.gob.cl/",
        "BR-CENIMAR": "https://en.wikipedia.org/wiki/Operation_Saucer",
        "AR-CEFAe": "https://en.wikipedia.org/wiki/CEFAe",
        "PE-DIFAA": "https://en.wikipedia.org/wiki/Peruvian_Air_Force",
        "UY-CRIDOVNI": "https://en.wikipedia.org/wiki/CRIDOVNI",
        "NO-HESSDALEN": "https://www.hessdalen.org/",
        "MX-SEDENA": "https://en.wikipedia.org/wiki/2004_Mexican_UFO_incident",
        "IT-CUN": "https://en.wikipedia.org/wiki/Centro_Ufologico_Nazionale",
        "US-NUKE-DOCUMENTED": "https://www.archives.gov/research/military/air-force/ufos",
    }
    # Sources we always want represented in the Case Files view even if their
    # descriptions are shorter than the dominant English corpora — the newly added
    # national/scientific sources are the whole point of the enrichment loop.
    PRIORITY_SOURCES = {"RU-SAMIZDAT", "UA-KYIV-OBS", "GEIPAN", "ES-AIRFORCE", "JP-SEED", "GALILEO",
                        "BE-SOBEPS", "CL-CEFAA", "BR-CENIMAR", "AR-CEFAe", "PE-DIFAA", "UY-CRIDOVNI",
                        "NO-HESSDALEN", "MX-SEDENA", "IT-CUN", "US-NUKE-DOCUMENTED"}
    # rank: rich description + multi-signature; drop junk/no-detail
    def _rich(r):
        d = r.get("description", "")
        if len(d) < 120:
            return False
        if any(k in d.lower() for k in ("no details", "explanation:")):
            return False
        return True
    ranked = [r for r in signal if _rich(r)]
    ranked.sort(key=lambda r: (len(r["description"]) >= 300, r["signature_count"], len(r["description"])), reverse=True)
    by_src = defaultdict(int)
    case_store = []
    seen_ids = set()

    def _emit(r):
        case_store.append({
            "id": r["id"], "source": r["source"], "source_url": SOURCE_URLS.get(r["source"], ""),
            "city": r["city"], "country": r["country"], "district": r["district"],
            "lat": r["lat"], "lng": r["lng"], "geo": r["geo"], "year": r["year"],
            "description": r["description"],
            "fired_signatures": r["fired_signatures"],
            "typologies": r["typologies"],
            "signature_count": r["signature_count"],
        })
        seen_ids.add(r["id"])
        by_src[r.get("source", "?")] += 1

    # Pass A: guarantee the priority (newly added) sources are represented, up to a
    # per-source cap, so RU-SAMIZDAT / UA-KYIV-OBS / GEIPAN / Spain are inspectable.
    prio_cap = {"RU-SAMIZDAT": 40, "UA-KYIV-OBS": 8, "GEIPAN": 40, "ES-AIRFORCE": 10, "JP-SEED": 5, "GALILEO": 3,
                "BE-SOBEPS": 2, "CL-CEFAA": 2, "BR-CENIMAR": 1, "AR-CEFAe": 1, "PE-DIFAA": 1, "UY-CRIDOVNI": 1,
                "NO-HESSDALEN": 3, "MX-SEDENA": 1, "IT-CUN": 1, "US-NUKE-DOCUMENTED": 3}
    for r in ranked:
        s = r.get("source", "?")
        if s in PRIORITY_SOURCES and by_src[s] < prio_cap.get(s, 20) and r["id"] not in seen_ids:
            _emit(r)

    # Pass B: general fill with source-diversity caps.
    caps = {"NUFORC": 500, "MUFON": 400, "UFODNA": 150}
    for r in ranked:
        if r["id"] in seen_ids:
            continue
        s = r.get("source", "?")
        if by_src[s] >= caps.get(s, 120):
            continue
        _emit(r)
        if len(case_store) >= 1400:
            break
    CASE_OUT = os.path.join(PROJECT_ROOT, "src", "frontend", "uap-case-store.js")
    with open(CASE_OUT, "w", encoding="utf-8") as f:
        f.write("// UAP Case Store - curated rich reports for the static Case File view.\n")
        f.write("// Verbatim descriptions from docs/updb/updb_reports.json (KNOWN, unaltered). source_url links to the issuing body's public archive.\n")
        f.write("window.UAP_CASES = " + json.dumps({"count": len(case_store), "by_source": dict(by_src), "cases": case_store}, ensure_ascii=False) + ";\n")
    print(f"  Case store written: {len(case_store)} cases -> {os.path.relpath(CASE_OUT, PROJECT_ROOT)} (by source: {dict(by_src)})")

    # ---- Geo aggregates: per-country + per-city stats for map drill briefings ----
    # Computed over ALL signal reports (not the curated store) so hotspot/location
    # briefings reflect true density. Grounded; no invented figures.
    TRAINED_KW = ("pilot", "police", "officer", "military", "air force", "navy",
                  "controller", "sheriff", "scientist", "engineer")
    def _country_agg():
        by_c = {}
        for r in signal:
            c = r.get("country") or "??"
            e = by_c.setdefault(c, {"country": c, "name": COUNTRY_NAMES.get(c, c),
                                    "reports": 0, "years": {}, "sigs": {}, "cities": {}, "trained": 0})
            e["reports"] += 1
            y = r.get("year")
            if y:
                e["years"][y] = e["years"].get(y, 0) + 1
            for s in r.get("fired_signatures", []):
                e["sigs"][s] = e["sigs"].get(s, 0) + 1
            city = (r.get("city") or "").strip()
            if city:
                e["cities"][city] = e["cities"].get(city, 0) + 1
            if any(k in (r.get("description") or "").lower() for k in TRAINED_KW):
                e["trained"] += 1
        out = {}
        for c, e in by_c.items():
            if c == "??":
                continue
            peak = max(e["years"].items(), key=lambda kv: kv[1]) if e["years"] else (None, 0)
            yrs = [int(y) for y in e["years"] if str(y).isdigit()]
            out[c] = {
                "country": c, "name": e["name"], "reports": e["reports"],
                "year_min": min(yrs) if yrs else None, "year_max": max(yrs) if yrs else None,
                "peak_year": peak[0], "peak_count": peak[1],
                "top_signatures": sorted(e["sigs"].items(), key=lambda kv: -kv[1])[:6],
                "top_cities": sorted(e["cities"].items(), key=lambda kv: -kv[1])[:8],
                "trained_observer_reports": e["trained"],
                "distinct_cities": len(e["cities"]),
            }
        return out

    def _city_agg():
        by_city = {}
        for r in signal:
            city = (r.get("city") or "").strip()
            country = r.get("country") or "??"
            if not city:
                continue
            k = country + "|" + city.lower()
            e = by_city.setdefault(k, {"city": city.title(), "country": country,
                                       "reports": 0, "years": {}, "sigs": {}, "shapes": {}, "trained": 0,
                                       "lat": r.get("lat"), "lng": r.get("lng")})
            e["reports"] += 1
            y = r.get("year")
            if y:
                e["years"][y] = e["years"].get(y, 0) + 1
            for s in r.get("fired_signatures", []):
                e["sigs"][s] = e["sigs"].get(s, 0) + 1
            if any(k2 in (r.get("description") or "").lower() for k2 in TRAINED_KW):
                e["trained"] += 1
        out = {}
        for k, e in by_city.items():
            if e["reports"] < 3:      # only cities with enough for a briefing
                continue
            peak = max(e["years"].items(), key=lambda kv: kv[1]) if e["years"] else (None, 0)
            yrs = [int(y) for y in e["years"] if str(y).isdigit()]
            out[k] = {
                "city": e["city"], "country": e["country"], "reports": e["reports"],
                "lat": e["lat"], "lng": e["lng"],
                "year_min": min(yrs) if yrs else None, "year_max": max(yrs) if yrs else None,
                "peak_year": peak[0], "peak_count": peak[1],
                "top_signatures": sorted(e["sigs"].items(), key=lambda kv: -kv[1])[:6],
                "trained_observer_reports": e["trained"],
            }
        # cap to the busiest ~1500 cities to keep payload sane
        top = dict(sorted(out.items(), key=lambda kv: -kv[1]["reports"])[:1500])
        return top

    geo = {"countries": _country_agg(), "cities": _city_agg()}
    GEO_OUT = os.path.join(PROJECT_ROOT, "src", "frontend", "uap-geo.js")
    with open(GEO_OUT, "w", encoding="utf-8") as f:
        f.write("// UAP geo aggregates for map drill-down briefings (per-country + per-city).\n")
        f.write("// Computed over all signature-firing reports. Grounded counts; no invented figures.\n")
        f.write("window.UAP_GEO = " + json.dumps(geo, ensure_ascii=False) + ";\n")
    print(f"  Geo aggregates: {len(geo['countries'])} countries, {len(geo['cities'])} cities -> {os.path.relpath(GEO_OUT, PROJECT_ROOT)}")

    print(f"  UI data written: {os.path.relpath(UI_OUT, PROJECT_ROOT)}")
    print(f"  countries={out['countries_total']}  firing={len(signal)}  map_points={len(map_points)}  edges={len(edges)}")


if __name__ == "__main__":
    main()
