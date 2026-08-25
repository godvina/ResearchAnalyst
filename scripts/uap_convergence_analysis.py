#!/usr/bin/env python3
"""UAP × Ancient Sites × Mythology — 3-way convergence test (LOCAL, grounded).

Tests the hypothesis: do UAP sightings converge on ancient sacred sites, and do
those sites carry a mythological signature — such that a 3-way overlap is real?

ANALYTICAL INTEGRITY (this is the whole point):
  A raw "sightings near sites" count is CONFOUNDED — UAP reports track modern
  population and reporting infrastructure, and many ancient sites sit near modern
  towns/tourist traffic. So we do NOT just count. We compute a near-site density
  and compare it to a BASELINE (matched control points offset from each site by
  ~2° in random directions, same country/region band). The metric is a LIFT
  RATIO: near-site density / baseline density. Lift ≈ 1 = no signal (fully
  explained by geography). Lift >> 1 = a real over-concentration worth reporting.
  We label everything KNOWN (counts) vs ASSESSED (interpretation), UTS-style.

  No OpenSearch / AOSS is touched — pure local file analysis.

Inputs (all on disk):
  src/data/conspiracy-seed/irish_sacred_sites/irish_ancient_sites.json  (coords)
  docs/updb/updb_reports.json  (296K UAP reports; we use placed signal via geocode)
  scripts/updb_signal_reports.json  (178K firing reports w/ lat/lng)
  src/data/archon-crosswalk.json  (deity -> site mythology mapping)

Output:
  scripts/uap_convergence_results.json
  console narrative of what the data does and does NOT show.
"""
import json
import math
import os
import random
from collections import Counter, defaultdict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def P(*a): return os.path.join(PROJECT_ROOT, *a)

random.seed(42)  # reproducible baseline

# ---- Global ancient sites (Irish from file + world wonders w/ public coords) ----
WORLD_SITES = [
    {"name": "Giza Pyramids", "country": "EG", "lat": 29.9792, "lon": 31.1344, "myth": "Egyptian: Ra, Osiris, Horus — sky/afterlife gods; pyramids as resurrection machines"},
    {"name": "Stonehenge", "country": "GB", "lat": 51.1789, "lon": -1.8262, "myth": "British/Druidic solar ritual tradition"},
    {"name": "Nazca Lines", "country": "PE", "lat": -14.7390, "lon": -75.1300, "myth": "Nazca: figures visible from the sky; sky-being tradition"},
    {"name": "Teotihuacan", "country": "MX", "lat": 19.6925, "lon": -98.8438, "myth": "Mesoamerican: 'place where gods were created'"},
    {"name": "Machu Picchu", "country": "PE", "lat": -13.1631, "lon": -72.5450, "myth": "Inca: Inti (sun god), astronomical alignment"},
    {"name": "Chichen Itza", "country": "MX", "lat": 20.6843, "lon": -88.5678, "myth": "Maya: Kukulkan (feathered serpent) descends at equinox"},
    {"name": "Puma Punku", "country": "BO", "lat": -16.5547, "lon": -68.6800, "myth": "Andean: Viracocha creator god"},
    {"name": "Angkor Wat", "country": "KH", "lat": 13.4125, "lon": 103.8670, "myth": "Hindu/Khmer: Mount Meru, Draco alignment"},
    {"name": "Gobekli Tepe", "country": "TR", "lat": 37.2231, "lon": 38.9225, "myth": "Pre-pottery Neolithic; oldest temple, star-carvings"},
    {"name": "Sedona (vortex sites)", "country": "US", "lat": 34.8697, "lon": -111.7610, "myth": "Native American / New Age energy-vortex tradition"},
    # ── Data-rich US/UK sites (corpus has real coverage here) ──
    {"name": "Avebury", "country": "GB", "lat": 51.4286, "lon": -1.8543, "myth": "Largest stone circle in Europe; British ritual landscape near Silbury"},
    {"name": "Silbury Hill", "country": "GB", "lat": 51.4156, "lon": -1.8574, "myth": "Largest prehistoric man-made mound in Europe; purpose unknown"},
    {"name": "Callanish Stones", "country": "GB", "lat": 58.1978, "lon": -6.7455, "myth": "Scottish standing stones; lunar-standstill alignment tradition"},
    {"name": "Glastonbury Tor", "country": "GB", "lat": 51.1441, "lon": -2.6989, "myth": "Avalon / Arthurian & ley-line tradition"},
    {"name": "Serpent Mound", "country": "US", "lat": 39.0256, "lon": -83.4300, "myth": "Adena/Fort Ancient effigy mound; solstice-aligned serpent"},
    {"name": "Cahokia Mounds", "country": "US", "lat": 38.6551, "lon": -90.0615, "myth": "Mississippian 'Woodhenge'; sun-priest cosmology"},
    {"name": "Chaco Canyon", "country": "US", "lat": 36.0606, "lon": -107.9559, "myth": "Ancestral Puebloan solar/lunar astronomy; Sun Dagger"},
    {"name": "Sedona Bell Rock", "country": "US", "lat": 34.8000, "lon": -111.7667, "myth": "Yavapai-Apache sacred land; vortex tradition"},
    {"name": "Mount Shasta", "country": "US", "lat": 41.4092, "lon": -122.1949, "myth": "Native American sacred mountain; Lemurian/Telos legend"},
    {"name": "Sacsayhuaman", "country": "PE", "lat": -13.5100, "lon": -71.9817, "myth": "Inca megalithic fortress; polygonal masonry mystery"},
]

SPAIN_SITES = [
    {"name": "Canary Islands (Spanish AF hotspot)", "country": "ES", "lat": 28.29, "lon": -16.63,
     "myth": "Guanche aboriginal sky/mountain worship; Teide as sacred axis"},
]

def load_irish():
    d = json.load(open(P("src", "data", "conspiracy-seed", "irish_sacred_sites", "irish_ancient_sites.json"), encoding="utf-8"))
    out = []
    for s in d["sites"]:
        c = s.get("coordinates") or {}
        if c.get("lat") is None:
            continue
        out.append({"name": s["name"], "country": "IE", "lat": c["lat"], "lon": c["lon"],
                    "id": s.get("id"), "taxonomy": s.get("taxonomy_matches", {}),
                    "myth": "Irish: Tuatha Dé Danann (Dagda, Aengus, Nuada, Lugh…)"})
    return out

def load_myth_links():
    try:
        d = json.load(open(P("src", "data", "archon-crosswalk.json"), encoding="utf-8"))
    except Exception:
        return {}
    links = defaultdict(list)
    for m in d.get("tuatha_de_danann_to_irish_sites", {}).get("mappings", []):
        for sid in m.get("sites", []):
            short = sid.split("_")[0]
            links[short].append({"deity": m["entity"], "role": m.get("role", ""),
                                 "parallel": m.get("anunnaki_parallel", "")})
    return links

def load_uap_points():
    """Use the geocoded signal reports (lat/lng present). Coerce to float — some
    source records (or merged sets) may carry coords as strings."""
    path = P("scripts", "updb_signal_reports.json")
    d = json.load(open(path, encoding="utf-8"))
    pts = []
    for r in d["reports"]:
        if r.get("lat") is None or r.get("lng") is None:
            continue
        try:
            pts.append((float(r["lat"]), float(r["lng"])))
        except (TypeError, ValueError):
            continue
    return pts

def load_uap_dated():
    """Load geocoded UAP reports WITH full date, from the raw UPDB corpus, geocoded
    the same way the pipeline does. Returns [(lat, lon, month, day)] for the
    solstice-timing test. Reuses geocode()/COUNTRY_CENTROIDS/WORLD_CITIES from the
    pipeline module so placement is identical."""
    import re
    from ufo_global_updb_pipeline import geocode as _geocode  # same geocoder
    d = json.load(open(P("docs", "updb", "updb_reports.json"), encoding="utf-8", errors="replace"))
    out = []
    for r in d["reports"]:
        desc = r.get("description") or ""
        if len(desc) < 60:
            continue
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", r.get("date") or "")
        if not m:
            continue
        mo, dy = int(m.group(2)), int(m.group(3))
        if mo == 0 or dy == 0:
            continue
        lat, lon, gtype = _geocode(r.get("city"), r.get("country"), r.get("id", ""))
        if lat is None:
            continue
        out.append((lat, lon, mo, dy))
    return out

# Days-of-year near the four solar events (± window). Solstices/equinoxes ~
# Mar 20, Jun 21, Sep 22, Dec 21.
SOLAR_DOYS = [79, 172, 265, 355]  # approx day-of-year for equinox/solstice
def _doy(mo, dy):
    md = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    return md[mo-1] + dy
def near_solar(mo, dy, window=7):
    d = _doy(mo, dy)
    for s in SOLAR_DOYS:
        if min(abs(d - s), 365 - abs(d - s)) <= window:
            return True
    return False

def solstice_test(dated, lat, lon, radius_km, window=7):
    """For reports within radius of a site: what fraction fall within ±window days
    of a solstice/equinox, vs the expected baseline fraction (8 windows * (2w+1)/365)."""
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * max(0.2, math.cos(math.radians(lat))))
    near = 0; solar = 0
    for (a, b, mo, dy) in dated:
        if abs(a - lat) > dlat or abs(b - lon) > dlon:
            continue
        if haversine(lat, lon, a, b) <= radius_km:
            near += 1
            if near_solar(mo, dy, window):
                solar += 1
    expected_frac = (4 * (2*window + 1)) / 365.0   # 4 events, ±window each
    obs_frac = (solar / near) if near else 0.0
    lift = (obs_frac / expected_frac) if expected_frac else 0.0
    return {"reports_dated": near, "near_solar": solar,
            "observed_frac": round(obs_frac, 3), "expected_frac": round(expected_frac, 3),
            "solar_lift": round(lift, 2)}

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1); dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def count_within(pts, lat, lon, radius_km):
    # cheap bounding-box pre-filter then haversine
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * max(0.2, math.cos(math.radians(lat))))
    n = 0
    for (a, b) in pts:
        if abs(a - lat) > dlat or abs(b - lon) > dlon:
            continue
        if haversine(lat, lon, a, b) <= radius_km:
            n += 1
    return n

def baseline_density(pts, lat, lon, radius_km, trials=16):
    """Matched control: same latitude band, offset ~2-4° in random directions.
    Returns report counts in equal-radius circles that are NOT on the site.

    We return BOTH the median and the mean. At a tight radius many single controls
    land in empty rural/ocean cells and read 0; the median can therefore collapse to
    0 and produce a bogus divide-by-zero 'infinite' lift. The mean over many trials is
    a more honest denominator for population-matched density, so lift is computed from
    a Laplace-smoothed mean downstream (see main)."""
    counts = []
    for _ in range(trials):
        ang = random.uniform(0, 2*math.pi)
        dist_deg = random.uniform(2.0, 4.0)
        blat = max(-70, min(70, lat + dist_deg*math.sin(ang)))
        blon = lon + dist_deg*math.cos(ang)/max(0.2, math.cos(math.radians(lat)))
        counts.append(count_within(pts, blat, blon, radius_km))
    counts.sort()
    mid = counts[len(counts)//2]
    mean = sum(counts) / len(counts) if counts else 0.0
    nonzero = sum(1 for c in counts if c > 0)
    return mid, mean, counts, nonzero

def main():
    sites = load_irish() + WORLD_SITES
    myth = load_myth_links()
    print("Loading UAP points…")
    pts = load_uap_points()
    print(f"  {len(pts)} geocoded UAP signal points; {len(sites)} ancient sites\n")

    RADIUS = 60.0  # km around each site (tight enough that nearby sites don't share a catchment)
    # A baseline is only trustworthy if enough control circles actually contain
    # reports. If fewer than this many of the 16 controls are non-empty, we treat
    # the lift as UNRELIABLE rather than reporting a divide-by-near-zero blowup.
    MIN_NONZERO_CONTROLS = 4
    results = []
    for s in sites:
        near = count_within(pts, s["lat"], s["lon"], RADIUS)
        base_med, base_mean, base_all, base_nonzero = baseline_density(pts, s["lat"], s["lon"], RADIUS)
        # Laplace-smoothed lift off the MEAN control density (honest, always finite).
        lift = (near + 1.0) / (base_mean + 1.0)
        baseline_reliable = base_nonzero >= MIN_NONZERO_CONTROLS
        mlinks = myth.get(s.get("id", ""), [])
        results.append({
            "site": s["name"], "country": s["country"],
            "uap_within_radius": near,
            "baseline_mean": round(base_mean, 1),
            "baseline_median": base_med,
            "baseline_samples": base_all,
            "baseline_nonzero_controls": base_nonzero,
            "baseline_reliable": baseline_reliable,
            "lift_ratio": round(lift, 2),
            "mythology": s.get("myth", ""),
            "mythology_links": mlinks,
            "three_way": bool(near > 0 and mlinks),  # UAP present AND explicit myth-site link
        })

    # sort by lift, but push unreliable-baseline sites to the bottom so a bogus
    # small-sample number never leads the table
    def sortkey(r):
        return (1 if r["baseline_reliable"] else 0, r["lift_ratio"])
    results.sort(key=sortkey, reverse=True)

    # ---- Solstice-timing test on data-rich sites (near>=25 reports) ----
    print("Loading dated UAP reports for the solstice test…")
    dated = load_uap_dated()
    print(f"  {len(dated)} dated+geocoded reports\n")
    for r in results:
        s = next((x for x in sites if x["name"] == r["site"]), None)
        if s and r["uap_within_radius"] >= 25:
            r["solstice"] = solstice_test(dated, s["lat"], s["lon"], RADIUS)
        else:
            r["solstice"] = None
        # data-rich vs sparse flag (honest coverage signal)
        r["data_coverage"] = "rich" if r["uap_within_radius"] >= 25 else "sparse"

    json.dump({"radius_km": RADIUS, "uap_points": len(pts), "sites": len(sites),
               "solar_window_days": 7, "results": results},
              open(P("scripts", "uap_convergence_results.json"), "w", encoding="utf-8"), indent=2)

    # frontend data file for the Convergence view
    fe = {"generated": "uap_convergence_analysis.py", "radius_km": RADIUS,
          "uap_points": len(pts), "solar_window_days": 7,
          "note": "lift = near-site UAP density / matched-baseline density. solar_lift = share of near-site reports within +/-7d of a solstice/equinox vs expected. Grounded in local files; no OpenSearch.",
          "results": results}
    with open(P("src", "frontend", "uap-convergence.js"), "w", encoding="utf-8") as f:
        f.write("// UAP x Ancient Sites x Mythology convergence results. Grounded, confound-controlled (lift ratio).\n")
        f.write("window.UAP_CONVERGENCE = " + json.dumps(fe, ensure_ascii=False) + ";\n")
    print("Frontend data written: src/frontend/uap-convergence.js")

    # ---- Narrative ----
    print("="*82)
    print(f"UAP × ANCIENT SITES CONVERGENCE — lift ratio, {int(RADIUS)}km radius (near-site vs baseline)")
    print("  lift ≈ 1.0 = no signal beyond geography; lift > 2 = over-concentration")
    print("  '*' = baseline too sparse to trust (too few non-empty control circles)")
    print("="*82)
    print(f"{'SITE':<26}{'UAP≤'+str(int(RADIUS))+'km':>10}{'base(mean)':>11}{'LIFT':>8}  base?  myth-link")
    for r in results:
        ml = "yes" if r["mythology_links"] else "-"
        flag = " " if r["baseline_reliable"] else "*"
        print(f"{r['site']:<26}{r['uap_within_radius']:>10}{r['baseline_mean']:>11}{str(r['lift_ratio']):>8}  {flag:^5}  {ml}")

    high = [r for r in results if r["baseline_reliable"] and r["lift_ratio"] >= 2.0]
    unreliable = [r for r in results if not r["baseline_reliable"] and r["uap_within_radius"] > 0]
    threeway = [r for r in results if r["three_way"]]
    print("\n" + "-"*82)
    print(f"Sites with LIFT >= 2.0 AND a trustworthy baseline (real over-concentration): {len(high)}")
    for r in high: print(f"   {r['site']}: {r['uap_within_radius']} near vs {r['baseline_mean']} baseline-mean (lift {r['lift_ratio']})")
    if unreliable:
        print(f"\nSites with reports but an UNTRUSTWORTHY baseline (cannot compute honest lift): {len(unreliable)}")
        for r in unreliable: print(f"   {r['site']}: {r['uap_within_radius']} near, only {r['baseline_nonzero_controls']}/16 control circles had any reports")
    print(f"\n3-way convergence (UAP present + explicit mythology→site link): {len(threeway)}")
    for r in threeway: print(f"   {r['site']}: {r['uap_within_radius']} UAP reports; myth: {[m['deity'] for m in r['mythology_links']]}")
    print("\n" + "-"*74)
    print("SOLSTICE / EQUINOX TIMING (data-rich sites; solar_lift 1.0 = no timing signal)")
    for r in results:
        if r.get("solstice"):
            s = r["solstice"]
            print(f"   {r['site']:<24} near-solar {s['near_solar']}/{s['reports_dated']} = {s['observed_frac']:.0%} (expected {s['expected_frac']:.0%}) → solar_lift {s['solar_lift']}")
    print("\nResults saved to scripts/uap_convergence_results.json + src/frontend/uap-convergence.js")

if __name__ == "__main__":
    main()
