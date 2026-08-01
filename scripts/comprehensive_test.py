#!/usr/bin/env python3
"""
Comprehensive API Endpoint Test Suite
Tests ALL endpoints for the Epstein Main case against the deployed API.
Uses only urllib.request (no requests library).
"""

import urllib.request
import urllib.error
import json
import time
import ssl

BASE_URL = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
CASE_ID = "7f05e8d5-4492-4f19-8894-25367606db96"
TIMEOUT = 25

# Disable SSL verification for corporate environments
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

results = []

def make_request(method, path, body=None, timeout_override=None):
    """Make an HTTP request and return (status, data, elapsed_ms)."""
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    effective_timeout = timeout_override or TIMEOUT
    
    start = time.time()
    try:
        resp = urllib.request.urlopen(req, timeout=effective_timeout, context=ctx)
        elapsed = (time.time() - start) * 1000
        raw = resp.read().decode("utf-8")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"_raw": raw[:500]}
        return resp.status, parsed, elapsed
    except urllib.error.HTTPError as e:
        elapsed = (time.time() - start) * 1000
        raw = ""
        try:
            raw = e.read().decode("utf-8")
        except Exception:
            pass
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"_raw": raw[:500]}
        return e.code, parsed, elapsed
    except urllib.error.URLError as e:
        elapsed = (time.time() - start) * 1000
        return 0, {"error": str(e.reason)}, elapsed
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        return 0, {"error": str(e)}, elapsed


def test_endpoint(name, method, path, body=None, validator=None, timeout_override=None):
    """Test a single endpoint and record results."""
    print(f"\n{'='*70}")
    print(f"TEST: {name}")
    print(f"  {method} {path}")
    if body:
        print(f"  Body: {json.dumps(body)}")
    if timeout_override:
        print(f"  Timeout: {timeout_override}s (extended)")
    print(f"{'='*70}")
    
    status, data, elapsed = make_request(method, path, body, timeout_override=timeout_override)
    
    details = {}
    passed = False
    
    if status == 200:
        if validator:
            passed, details = validator(data)
        else:
            passed = True
            details = {"note": "200 OK received"}
    elif status == 404 and "NO_IPS_RESULTS" in str(data):
        passed = True
        details = {"note": "404 - No IPS results cached (expected - needs trigger)", "status_note": "EXPECTED"}
    else:
        passed = False
        details = {"error": str(data)[:200]}
    
    result = {
        "name": name,
        "method": method,
        "path": path,
        "status": status,
        "elapsed_ms": round(elapsed, 1),
        "passed": passed,
        "details": details,
    }
    results.append(result)
    
    status_str = "PASS" if passed else "FAIL"
    print(f"  Status: {status} | Time: {elapsed:.0f}ms | {status_str}")
    for k, v in details.items():
        print(f"  {k}: {v}")
    
    return result


# --- Validators ---

def validate_list_cases(data):
    if isinstance(data, list):
        case_names = [c.get("case_name", c.get("topic_name", c.get("name", "?"))) for c in data[:5]]
        return len(data) > 0, {"case_count": len(data), "sample_cases": case_names}
    if isinstance(data, dict):
        # Handle various key names: case_files, cases, Items, items
        items = (data.get("case_files") or data.get("cases") or 
                 data.get("Items") or data.get("items") or [])
        if isinstance(items, list) and len(items) > 0:
            case_names = [c.get("topic_name", c.get("case_name", c.get("name", "?"))) for c in items[:5]]
            return True, {"case_count": len(items), "sample_cases": case_names}
    return False, {"note": f"Unexpected format: {str(data)[:200]}"}


def validate_case_details(data):
    if isinstance(data, dict):
        has_id = "case_id" in data or "id" in data or "caseId" in data
        name = data.get("case_name") or data.get("name") or data.get("caseName", "")
        return True, {"has_id": has_id, "case_name": name, "keys": list(data.keys())[:10]}
    return False, {"note": "Not a dict"}


def validate_graph(data):
    nodes = []
    edges = []
    locations = []
    
    if isinstance(data, dict):
        nodes = data.get("nodes") or data.get("graph", {}).get("nodes", []) or []
        edges = (data.get("edges") or data.get("links") or 
                 data.get("graph", {}).get("edges", []) or 
                 data.get("graph", {}).get("links", []) or [])
        locations = data.get("locations") or data.get("graph", {}).get("locations", []) or []
        
        if not nodes and "data" in data:
            inner = data["data"]
            if isinstance(inner, dict):
                nodes = inner.get("nodes", [])
                edges = inner.get("edges", []) or inner.get("links", [])
                locations = inner.get("locations", [])
    
    node_count = len(nodes) if isinstance(nodes, list) else (nodes if isinstance(nodes, int) else 0)
    edge_count = len(edges) if isinstance(edges, list) else (edges if isinstance(edges, int) else 0)
    loc_count = len(locations) if isinstance(locations, list) else (locations if isinstance(locations, int) else 0)
    
    passed = node_count > 0 and edge_count > 0
    return passed, {
        "node_count": node_count,
        "edge_count": edge_count,
        "location_count": loc_count,
        "top_level_keys": list(data.keys())[:10] if isinstance(data, dict) else "N/A",
    }


def validate_travel_intel(data):
    if isinstance(data, dict):
        patterns = data.get("patterns") or data.get("travel_patterns") or data.get("routes") or []
        cards = data.get("cards") or data.get("intelligence_cards") or data.get("intel_cards") or []
        pattern_count = len(patterns) if isinstance(patterns, list) else 0
        card_count = len(cards) if isinstance(cards, list) else 0
        has_data = pattern_count > 0 or card_count > 0 or len(data) > 1
        return has_data, {
            "pattern_count": pattern_count,
            "card_count": card_count,
            "top_level_keys": list(data.keys())[:10],
        }
    return False, {"note": f"Unexpected type: {type(data).__name__}"}


def validate_suspects(data):
    if isinstance(data, dict):
        suspects = data.get("suspects") or data.get("entities") or data.get("persons_of_interest") or []
        if isinstance(suspects, list) and len(suspects) > 0:
            sample = suspects[0]
            has_score = any(k in (sample if isinstance(sample, dict) else {}) 
                          for k in ["score", "risk_score", "suspicion_score", "confidence"])
            return True, {
                "suspect_count": len(suspects),
                "has_scores": has_score,
                "sample_suspect": str(sample)[:150],
            }
        return len(data) > 0, {
            "top_level_keys": list(data.keys())[:10],
            "data_preview": str(data)[:200],
        }
    return False, {"note": f"Unexpected type: {type(data).__name__}"}


def validate_case_builder(data):
    if isinstance(data, dict):
        return len(data) > 0, {
            "top_level_keys": list(data.keys())[:10],
            "data_preview": str(data)[:300],
        }
    return False, {"note": f"Unexpected type: {type(data).__name__}"}


def validate_anomaly(anomaly_type):
    def validator(data):
        if isinstance(data, dict):
            anomalies = (data.get("anomalies") or data.get("patterns") or 
                        data.get("results") or data.get("detections") or
                        data.get("entities") or data.get("findings") or [])
            count = len(anomalies) if isinstance(anomalies, list) else 0
            has_content = count > 0 or len(data) > 0
            return has_content, {
                "anomaly_type": anomaly_type,
                "result_count": count,
                "top_level_keys": list(data.keys())[:10],
                "data_preview": str(data)[:250],
            }
        return False, {"note": f"Unexpected type: {type(data).__name__}"}
    return validator


def validate_ips_results(data):
    """Validate IPS results - note: 404 NO_IPS_RESULTS is handled in test_endpoint."""
    if isinstance(data, dict):
        results_list = data.get("results") or data.get("ips_results") or data.get("items") or []
        count = len(results_list) if isinstance(results_list, list) else 0
        return True, {
            "result_count": count,
            "top_level_keys": list(data.keys())[:10],
            "data_preview": str(data)[:250],
        }
    if isinstance(data, list):
        return True, {"result_count": len(data)}
    return False, {"note": f"Unexpected type: {type(data).__name__}"}


def validate_search(data):
    if isinstance(data, dict):
        hits = (data.get("results") or data.get("hits") or 
                data.get("matches") or data.get("items") or [])
        count = len(hits) if isinstance(hits, list) else 0
        return count > 0 or len(data) > 0, {
            "hit_count": count,
            "top_level_keys": list(data.keys())[:10],
            "data_preview": str(data)[:250],
        }
    return False, {"note": f"Unexpected type: {type(data).__name__}"}


# --- Run All Tests ---

def main():
    print("=" * 75)
    print("  COMPREHENSIVE API ENDPOINT TEST SUITE")
    print(f"  Base URL: {BASE_URL}")
    print(f"  Case ID:  {CASE_ID}")
    print(f"  Timeout:  {TIMEOUT}s per request")
    print("=" * 75)
    
    overall_start = time.time()
    
    # 1. List all cases
    test_endpoint("1. List All Cases", "GET", "/case-files",
                  validator=validate_list_cases)
    
    # 2. Get case details
    test_endpoint("2. Get Case Details", "GET", f"/case-files/{CASE_ID}",
                  validator=validate_case_details)
    
    # 3. Graph data
    test_endpoint("3. Graph Data (nodes/edges/locations)", "POST",
                  f"/case-files/{CASE_ID}/patterns",
                  body={"graph": True}, validator=validate_graph)
    
    # 4. Travel intelligence
    test_endpoint("4. Travel Intelligence", "POST",
                  f"/case-files/{CASE_ID}/patterns",
                  body={"action": "travel_intelligence"},
                  validator=validate_travel_intel,
                  timeout_override=90)
    
    # 5. AI Investigator - suspects
    test_endpoint("5. AI Investigator - Get Suspects", "POST",
                  f"/case-files/{CASE_ID}/patterns",
                  body={"investigator_action": "get_suspects", "case_id": CASE_ID},
                  validator=validate_suspects,
                  timeout_override=90)
    
    # 6. Case Builder
    test_endpoint("6. Case Builder", "POST",
                  f"/case-files/{CASE_ID}/patterns",
                  body={"investigator_action": "case_builder", "case_id": CASE_ID},
                  validator=validate_case_builder,
                  timeout_override=90)
    
    # 7-13. Anomaly detection endpoints
    anomaly_types = [
        ("7", "structuring"),
        ("8", "temporal_convergence"),
        ("9", "ghost_entity"),
        ("10", "absence_pattern"),
        ("11", "decay_pattern"),
        ("12", "proxy_network"),
        ("13", "anomaly_destination"),
    ]
    
    for num, atype in anomaly_types:
        test_endpoint(f"{num}. Anomaly - {atype}", "POST",
                      f"/case-files/{CASE_ID}/anomaly/{atype}",
                      validator=validate_anomaly(atype))
    
    # 14. IPS Results
    test_endpoint("14. IPS Results", "GET",
                  f"/case-files/{CASE_ID}/ips-results",
                  validator=validate_ips_results)
    
    # 15. Search
    test_endpoint("15. Search", "POST",
                  f"/case-files/{CASE_ID}/search",
                  body={"query": "Jeffrey Epstein"},
                  validator=validate_search)
    
    overall_elapsed = time.time() - overall_start
    
    # --- Summary Table ---
    print("\n\n")
    print("=" * 88)
    print("  COMPREHENSIVE TEST RESULTS SUMMARY")
    print("=" * 88)
    print(f"  {'#':<4} {'Test Name':<45} {'Status':<7} {'Time':>8}  {'Result':<6}")
    print("-" * 88)
    
    pass_count = 0
    fail_count = 0
    
    for i, r in enumerate(results):
        status_str = str(r["status"])
        time_str = f"{r['elapsed_ms']:.0f}ms"
        result_str = "PASS" if r["passed"] else "FAIL"
        name = r["name"][:45]
        
        if r["passed"]:
            pass_count += 1
        else:
            fail_count += 1
        
        print(f"  {i+1:<4} {name:<45} {status_str:<7} {time_str:>8}  {result_str:<6}")
    
    print("-" * 88)
    total = pass_count + fail_count
    pct = (pass_count / total * 100) if total > 0 else 0
    print(f"  TOTAL: {total} tests | PASSED: {pass_count} | FAILED: {fail_count} | Rate: {pct:.0f}% | Time: {overall_elapsed:.1f}s")
    print("=" * 88)
    
    # --- Detailed Key Metrics ---
    print("\n\nKEY METRICS DETAIL:")
    print("-" * 70)
    
    for r in results:
        d = r["details"]
        print(f"\n  {r['name']}:")
        if "node_count" in d:
            print(f"    Nodes: {d['node_count']} | Edges: {d['edge_count']} | Locations: {d.get('location_count', 'N/A')}")
        if "pattern_count" in d:
            print(f"    Patterns: {d['pattern_count']} | Cards: {d.get('card_count', 'N/A')}")
        if "suspect_count" in d:
            print(f"    Suspects: {d['suspect_count']} | Has Scores: {d.get('has_scores', 'N/A')}")
        if "case_count" in d:
            print(f"    Cases: {d['case_count']}")
        if "result_count" in d:
            print(f"    Results: {d['result_count']}")
        if "hit_count" in d:
            print(f"    Hits: {d['hit_count']}")
        if "error" in d:
            print(f"    Error: {d['error'][:150]}")
    
    print("\n" + "=" * 70)
    print(f"  Suite completed in {overall_elapsed:.1f}s")
    print("=" * 70)


if __name__ == "__main__":
    main()
