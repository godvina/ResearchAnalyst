"""UAP × Ley-Line Vertices — convergence test (LOCAL, grounded).

Tests the user's hypothesis: do UAP sightings converge on the VERTICES of the
Becker-Hagens "UVG" world grid (where two great-circle ley lines cross)?

THE REPORTING CONFOUND (the user's own insight, made rigorous):
  A ley-line vertex in the middle of an ocean or a Siberian tundra will show zero
  UAP reports — but that tells us nothing, because there is nobody there to see or
  report anything. So a raw "reports at vertices" count is doubly confounded: by
  population AND by whether anyone can even file a report. We therefore:

    1. Use the SAME confound-controlled LIFT RATIO as the ancient-sites analysis:
       near-vertex report density / matched-baseline density (16 control circles
       offset ~2-4deg). Laplace-smoothed so it is always finite; a baseline is
       flagged UNRELIABLE if < 4/16 controls contain any reports.

    2. CLASSIFY each vertex by local reporting infrastructure, using a wide 300km
       "can anyone even report here?" probe:
         - ocean     : intersection is at sea (on_land = null)
         - remote    : on land but < REMOTE_REPORTS reports within 300km
                       -> a zero here is a COVERAGE GAP, not evidence of absence
         - populated : reports exist nearby -> a clean test is possible

  Reading rule (ASSESSED):
    populated + lift >= 2   -> interesting over-concentration worth a look
    populated + lift ~ 1    -> clean NULL (reporters exist, no concentration)
    remote/ocean + 0        -> INCONCLUSIVE (no reporter), NOT a null

No OpenSearch / AOSS. Pure local file analysis. Reuses helpers from
uap_convergence_analysis.py so the method is identical to the sites test.

Inputs:
  src/data/uvg-grid-intersections.json         (20 vertices; 11 on land)
  scripts/updb_signal_reports.json             (firing UAP signal w/ lat/lng)
  docs/updb/updb_reports.json                  (dated corpus, for solstice test)

Outputs:
  scripts/uap_leyline_results.json
  src/frontend/uap-leyline-convergence.js       (window.UAP_LEYLINE)
"""
import json
import os

# reuse the exact same method as the ancient-sites convergence
from uap_convergence_analysis import (
    P, count_within, baseline_density, load_uap_points, load_uap_dated, solstice_test,
)

RADIUS = 60.0             # km around each vertex (matches the sites analysis)
WIDE_PROBE_KM = 300.0     # "can anyone even report here?" reporting-infrastructure probe
REMOTE_REPORTS = 15       # < this many reports within 300km => treat as remote/low-coverage
MIN_NONZERO_CONTROLS = 4  # baseline reliability gate (of 16 controls)


def load_intersections():
    d = json.load(open(P("src", "data", "uvg-grid-intersections.json"), encoding="utf-8"))
    return d["intersections"]


def load_grid_nodes():
    """The 62 Becker-Hagens grid NODES (vertices of the polyhedron). Unlike the 20
    line-crossing intersections (all pinned to +/-43.56 deg), the nodes land on far
    more populated territory: Japan (10), Russia (2/3/52/53), Egypt (7), Bermuda (14),
    Uluru (40), Sedona (13), Ireland/UK (56), Nazca (44). Skip the two poles."""
    d = json.load(open(P("src", "data", "uvg-grid-62-points.json"), encoding="utf-8"))
    return [n for n in d["vertices"] if n.get("type") != "polar"]


# ---- British St Michael / Apollo ley line (a REAL, populated alignment) ----
# The famous "St Michael's Line" runs SW->NE across southern England, threading a
# string of St-Michael/St-George dedications and prehistoric sites. Coordinates are
# public/geographic. This is the populated ley line the global grid could not provide.
BRITISH_LEY = [
    {"id": "LEY-STM-01", "name": "St Michael's Mount (Cornwall)", "lat": 50.1170, "lon": -5.4776},
    {"id": "LEY-STM-02", "name": "The Hurlers stone circles (Bodmin Moor)", "lat": 50.5165, "lon": -4.4568},
    {"id": "LEY-STM-03", "name": "Brentor / St Michael de Rupe", "lat": 50.5807, "lon": -4.1560},
    {"id": "LEY-STM-04", "name": "Burrow Mump (Somerset)", "lat": 51.0631, "lon": -2.9110},
    {"id": "LEY-STM-05", "name": "Glastonbury Tor (Somerset)", "lat": 51.1441, "lon": -2.6989},
    {"id": "LEY-STM-06", "name": "Avebury stone circle (Wiltshire)", "lat": 51.4286, "lon": -1.8543},
    {"id": "LEY-STM-07", "name": "Ogbourne St George (Wiltshire)", "lat": 51.4700, "lon": -1.7200},
    {"id": "LEY-STM-08", "name": "Bury St Edmunds (Suffolk)", "lat": 52.2450, "lon": 0.7130},
    {"id": "LEY-STM-09", "name": "Hopton-on-Sea (Norfolk, NE terminus)", "lat": 52.5390, "lon": 1.7360},
]


def classify(on_land, wide_count):
    """on_land: truthy region string or None. A point on land but with almost no
    reports within 300km is 'remote' (a zero there is a coverage gap, not a null)."""
    if not on_land:
        return "ocean"
    if wide_count < REMOTE_REPORTS:
        return "remote"
    return "populated"


def score_point(pts, lat, lon, on_land, extra):
    near = count_within(pts, lat, lon, RADIUS)
    wide = count_within(pts, lat, lon, WIDE_PROBE_KM)
    _med, base_mean, _all, base_nonzero = baseline_density(pts, lat, lon, RADIUS)
    lift = (near + 1.0) / (base_mean + 1.0)
    rec = {
        "lat": lat, "lng": lon,
        "on_land": on_land,
        "class": classify(on_land, wide),
        "uap_within_radius": near,
        "reports_within_300km": wide,
        "baseline_mean": round(base_mean, 1),
        "baseline_nonzero_controls": base_nonzero,
        "baseline_reliable": base_nonzero >= MIN_NONZERO_CONTROLS,
        "lift_ratio": round(lift, 2),
    }
    rec.update(extra)
    return rec


def sort_results(rows):
    def k(r):
        cls_rank = {"populated": 2, "remote": 1, "ocean": 0}[r["class"]]
        return (cls_rank, 1 if r["baseline_reliable"] else 0, r["lift_ratio"])
    rows.sort(key=k, reverse=True)
    return rows


def region_for_node(node):
    """Infer a coarse on-land/region label from the node name (it embeds the place)."""
    name = node.get("name", "")
    ocean_words = ("Ocean", "Pacific", "Atlantic", "Sea of", "Drake Passage",
                   "Gulf of Alaska", "Southern Ocean", "Mid-Atlantic", "Kerguelen",
                   "Devil's Sea", "Bermuda Triangle", "Celebes", "Tristan")
    if any(w in name for w in ocean_words):
        return None
    return name


def print_table(title, rows):
    print("=" * 92)
    print(title)
    print("  lift ~ 1 = no signal; lift >= 2 = over-concentration; '*' = baseline unreliable")
    print("=" * 92)
    print(f"{'ID':<11}{'CLASS':<11}{'UAP<=60':>8}{'<=300km':>9}{'base(mean)':>11}{'LIFT':>7}  base?  where")
    for r in rows:
        flag = " " if r["baseline_reliable"] else "*"
        where = (r.get("on_land") or "ocean")
        wtxt = (str(where)[:26])
        print(f"{r['id']:<11}{r['class']:<11}{r['uap_within_radius']:>8}{r['reports_within_300km']:>9}"
              f"{r['baseline_mean']:>11}{r['lift_ratio']:>7}  {flag:^5}  {wtxt}")


def summarize(label, rows):
    pop = [r for r in rows if r["class"] == "populated"]
    pop_sig = [r for r in pop if r["baseline_reliable"] and r["lift_ratio"] >= 2.0]
    remote = [r for r in rows if r["class"] == "remote"]
    ocean = [r for r in rows if r["class"] == "ocean"]
    print(f"\n{label}: populated {len(pop)} (over-concentration {len(pop_sig)}), "
          f"remote {len(remote)}, ocean {len(ocean)}")
    for r in pop_sig:
        print(f"   OVER-CONCENTRATION  {r['id']} ({r.get('name') or r.get('on_land')}): "
              f"{r['uap_within_radius']} near, lift {r['lift_ratio']}")


def main():
    print("Loading UAP points…")
    pts = load_uap_points()
    ix = load_intersections()
    nodes = load_grid_nodes()
    print(f"  {len(pts)} geocoded UAP signal points; {len(ix)} vertices; "
          f"{len(nodes)} grid nodes; {len(BRITISH_LEY)} British ley waypoints\n")

    vertices = sort_results([
        score_point(pts, v["lat"], v["lng"], v.get("on_land"),
                    {"id": v["id"], "priority": v.get("priority", ""),
                     "lines": (v.get("edge1_names", []) + v.get("edge2_names", []))})
        for v in ix
    ])

    grid_nodes = sort_results([
        score_point(pts, n["lat"], n["lng"], region_for_node(n),
                    {"id": f"NODE-{n['id']}", "name": n.get("name", ""),
                     "node_type": n.get("type", "")})
        for n in nodes
    ])

    british = sort_results([
        score_point(pts, s["lat"], s["lon"], "United Kingdom",
                    {"id": s["id"], "name": s["name"]})
        for s in BRITISH_LEY
    ])

    dated = load_uap_dated()
    for row in vertices + grid_nodes + british:
        if row["uap_within_radius"] >= 25:
            row["solstice"] = solstice_test(dated, row["lat"], row["lng"], RADIUS)
        else:
            row["solstice"] = None

    fe = {
        "generated": "uap_leyline_convergence.py",
        "radius_km": RADIUS, "wide_probe_km": WIDE_PROBE_KM,
        "remote_threshold": REMOTE_REPORTS,
        "note": ("lift = near-point UAP density / matched-baseline mean (Laplace-smoothed). "
                 "Points classified by a 300km reporting-infrastructure probe: ocean / remote "
                 "(coverage gap) / populated (testable). A zero at a remote/ocean point is "
                 "inconclusive, not a null. Grounded in local files; no OpenSearch."),
        "results": vertices,          # back-compat: vertices under `results`
        "vertices": vertices,
        "grid_nodes": grid_nodes,
        "british_ley": british,
    }
    with open(P("src", "frontend", "uap-leyline-convergence.js"), "w", encoding="utf-8") as f:
        f.write("// UAP x Ley-Line convergence (grid vertices + 62 grid nodes + British St Michael line).\n")
        f.write("window.UAP_LEYLINE = " + json.dumps(fe, ensure_ascii=False) + ";\n")
    json.dump(fe, open(P("scripts", "uap_leyline_results.json"), "w", encoding="utf-8"), indent=2)

    print_table(f"UAP × GRID VERTICES — {int(RADIUS)}km (line crossings)", vertices)
    summarize("VERTICES", vertices)
    print()
    print_table(f"UAP × 62 GRID NODES — {int(RADIUS)}km (Japan/Russia/Egypt/Bermuda/…)", grid_nodes)
    summarize("GRID NODES", grid_nodes)
    print()
    print_table(f"UAP × BRITISH ST MICHAEL LEY LINE — {int(RADIUS)}km (populated, testable)", british)
    summarize("BRITISH LEY", british)
    print("\nSaved: scripts/uap_leyline_results.json + src/frontend/uap-leyline-convergence.js")


if __name__ == "__main__":
    main()
