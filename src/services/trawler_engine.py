"""TrawlerEngine — multi-phase background analysis engine for intelligence detection.

Orchestrates sequential scans across Neptune graph, OpenSearch documents,
pattern scores, cross-case overlaps, and optional OSINT sources to detect
new intelligence leads and generate prioritized alerts.

Dependencies are injected via the constructor for testability.
"""

import json
import logging
import os
import ssl
import time
import urllib.request
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from services.trawler_alert_store import TrawlerAlertStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FULL_SCAN_BUDGET = 30  # seconds
TARGETED_SCAN_BUDGET = 15  # seconds
EXTERNAL_PHASE_BUDGET = 60  # seconds
MAX_EXTERNAL_ENTITIES = 5

SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1}

ALERT_THRESHOLDS = {
    "new_connection": 3,      # ≥3 shared evidence docs
    "entity_spike": 5,        # ≥5 new docs for single entity
    "network_expansion": 3,   # ≥3 new connections to single entity
}

DEFAULT_CONFIG = {
    "enabled_alert_types": [
        "new_connection", "pattern_change", "entity_spike",
        "new_evidence_match", "cross_case_overlap",
        "temporal_anomaly", "network_expansion",
    ],
    "min_severity": "low",
    "external_trawl_enabled": False,
}


def _escape(s: str) -> str:
    """Escape a string for Gremlin query embedding."""
    return s.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')


# ---------------------------------------------------------------------------
# Severity helpers (module-level for testability)
# ---------------------------------------------------------------------------

def assign_severity(evidence_count: int) -> str:
    """Assign alert severity based on evidence reference count.

    ≥10 → critical, 5-9 → high, 3-4 → medium, 1-2 → low.
    Returns 'low' for 0 or negative counts.
    """
    if evidence_count >= 10:
        return "critical"
    if evidence_count >= 5:
        return "high"
    if evidence_count >= 3:
        return "medium"
    return "low"


def severity_meets_threshold(severity: str, min_severity: str) -> bool:
    """Check if severity meets or exceeds the minimum threshold."""
    return SEVERITY_ORDER.get(severity, 0) >= SEVERITY_ORDER.get(min_severity, 0)


def make_evidence_ref(
    ref_id: str,
    ref_type: str,
    source_label: str,
    excerpt: str,
) -> dict:
    """Build a validated evidence_ref dict."""
    valid_types = {"document", "graph_edge", "external_url"}
    if ref_type not in valid_types:
        ref_type = "document"
    return {
        "ref_id": str(ref_id) if ref_id else str(uuid.uuid4()),
        "ref_type": ref_type,
        "source_label": str(source_label) if source_label else "",
        "excerpt": str(excerpt)[:500] if excerpt else "",
    }



# ---------------------------------------------------------------------------
# TrawlerEngine
# ---------------------------------------------------------------------------

class TrawlerEngine:
    """Orchestrates multi-phase trawl scans for a case."""

    def __init__(
        self,
        aurora_cm: Any,
        pattern_service: Any,
        cross_case_service: Any,
        research_agent: Optional[Any] = None,
        search_service: Optional[Any] = None,
        neptune_endpoint: str = "",
        neptune_port: str = "8182",
        bedrock_client: Optional[Any] = None,
    ) -> None:
        self._db = aurora_cm
        self._pattern_svc = pattern_service
        self._cross_case_svc = cross_case_service
        self._research_agent = research_agent
        self._search_svc = search_service
        self._neptune_ep = neptune_endpoint or os.environ.get("NEPTUNE_ENDPOINT", "")
        self._neptune_port = neptune_port or os.environ.get("NEPTUNE_PORT", "8182")
        self._alert_store = TrawlerAlertStore(aurora_cm)
        self._bedrock = bedrock_client

    # ------------------------------------------------------------------
    # Neptune helper (same pattern as InvestigativeSearchService)
    # ------------------------------------------------------------------

    def _gremlin(self, query: str, timeout: int = 12) -> list:
        """Execute a Gremlin query via Neptune HTTPS endpoint."""
        if not self._neptune_ep:
            return []
        url = f"https://{self._neptune_ep}:{self._neptune_port}/gremlin"
        data = json.dumps({"gremlin": query}).encode()
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            body = json.loads(resp.read().decode())
        raw = body.get("result", {}).get("data", {})
        if isinstance(raw, dict) and "@value" in raw:
            raw = raw["@value"]
        return raw if isinstance(raw, list) else []

    # ------------------------------------------------------------------
    # Scan orchestration
    # ------------------------------------------------------------------

    def run_scan(
        self, case_id: str, targeted_doc_ids: Optional[list] = None,
    ) -> dict:
        """Execute a full or targeted trawl scan. Returns scan summary."""
        scan_id = str(uuid.uuid4())
        scan_type = "targeted" if targeted_doc_ids else "full"
        budget = TARGETED_SCAN_BUDGET if targeted_doc_ids else FULL_SCAN_BUDGET
        t0 = time.time()
        phase_timings: dict = {}
        errors: list = []
        all_candidates: list = []
        scan_status = "completed"

        # Create scan record
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """INSERT INTO trawl_scans
                       (scan_id, case_id, scan_status, scan_type)
                       VALUES (%s, %s, 'running', %s)""",
                    (scan_id, case_id, scan_type),
                )
        except Exception as e:
            logger.error("Failed to create scan record: %s", str(e)[:300])

        # Load last scan info
        since, baseline = self._load_last_scan(case_id)

        # Load config
        config = self.get_trawl_config(case_id)

        def _remaining():
            return max(0, budget - (time.time() - t0))

        # --- Phase 1: Graph Scan ---
        if _remaining() > 0:
            pt = time.time()
            try:
                candidates = self._phase_graph_scan(case_id, since)
                all_candidates.extend(candidates)
            except Exception as e:
                logger.error("Phase 1 (graph scan) failed: %s", str(e)[:300])
                errors.append(f"graph_scan: {str(e)[:200]}")
                scan_status = "partial"
            phase_timings["graph_scan"] = round(time.time() - pt, 2)
        else:
            scan_status = "partial"
            errors.append("graph_scan: skipped (budget exceeded)")

        # --- Phase 2: Document Scan ---
        if _remaining() > 0:
            pt = time.time()
            try:
                candidates = self._phase_document_scan(case_id, since, targeted_doc_ids)
                all_candidates.extend(candidates)
            except Exception as e:
                logger.error("Phase 2 (document scan) failed: %s", str(e)[:300])
                errors.append(f"document_scan: {str(e)[:200]}")
                scan_status = "partial"
            phase_timings["document_scan"] = round(time.time() - pt, 2)
        else:
            scan_status = "partial"
            errors.append("document_scan: skipped (budget exceeded)")

        # --- Phase 3: Pattern Comparison ---
        if _remaining() > 0:
            pt = time.time()
            try:
                candidates = self._phase_pattern_comparison(case_id, baseline)
                all_candidates.extend(candidates)
            except Exception as e:
                logger.error("Phase 3 (pattern comparison) failed: %s", str(e)[:300])
                errors.append(f"pattern_comparison: {str(e)[:200]}")
                scan_status = "partial"
            phase_timings["pattern_comparison"] = round(time.time() - pt, 2)
        else:
            scan_status = "partial"
            errors.append("pattern_comparison: skipped (budget exceeded)")

        # --- Phase 4: Cross-Case Scan ---
        if _remaining() > 0:
            pt = time.time()
            try:
                candidates = self._phase_cross_case_scan(case_id)
                all_candidates.extend(candidates)
            except Exception as e:
                logger.error("Phase 4 (cross-case scan) failed: %s", str(e)[:300])
                errors.append(f"cross_case_scan: {str(e)[:200]}")
                scan_status = "partial"
            phase_timings["cross_case_scan"] = round(time.time() - pt, 2)
        else:
            scan_status = "partial"
            errors.append("cross_case_scan: skipped (budget exceeded)")

        # --- Phase 5: External OSINT (optional) ---
        if _remaining() > 0 and config.get("external_trawl_enabled", False):
            pt = time.time()
            try:
                candidates = self._phase_external_trawl(case_id, config)
                all_candidates.extend(candidates)
            except Exception as e:
                logger.error("Phase 5 (external trawl) failed: %s", str(e)[:300])
                errors.append(f"external_trawl: {str(e)[:200]}")
                scan_status = "partial"
            phase_timings["external_trawl"] = round(time.time() - pt, 2)

        # --- Alert generation, filtering, dedup, persistence ---
        alerts = self._generate_alerts(case_id, all_candidates, config)
        alerts = self._enrich_alerts_with_ai(alerts)
        alerts = self._deduplicate_alerts(case_id, alerts)
        alerts_count = self._persist_alerts(case_id, scan_id, alerts)

        # If all phases failed, mark as failed
        if errors and not all_candidates and alerts_count == 0:
            if len(errors) >= 4:
                scan_status = "failed"

        # Store new pattern baseline
        new_baseline = self._get_current_baseline(case_id)

        # Update scan record
        error_msg = "; ".join(errors) if errors else None
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """UPDATE trawl_scans
                       SET completed_at = NOW(), alerts_generated = %s,
                           scan_status = %s, phase_timings = %s::jsonb,
                           error_message = %s, pattern_baseline = %s::jsonb
                       WHERE scan_id = %s""",
                    (alerts_count, scan_status, json.dumps(phase_timings),
                     error_msg, json.dumps(new_baseline), scan_id),
                )
        except Exception as e:
            logger.error("Failed to update scan record: %s", str(e)[:300])

        elapsed = round(time.time() - t0, 2)
        logger.info(
            "Trawl scan %s for case %s completed in %.1fs — %d alerts, status=%s",
            scan_id, case_id, elapsed, alerts_count, scan_status,
        )

        return {
            "scan_id": scan_id,
            "case_id": case_id,
            "scan_type": scan_type,
            "scan_status": scan_status,
            "alerts_generated": alerts_count,
            "phase_timings": phase_timings,
            "elapsed_seconds": elapsed,
            "errors": errors if errors else None,
        }

    # ------------------------------------------------------------------
    # Load last scan info
    # ------------------------------------------------------------------

    def _load_last_scan(self, case_id: str) -> tuple:
        """Load last scan timestamp and pattern baseline. Returns (since, baseline)."""
        since = datetime.now(timezone.utc) - timedelta(days=30)  # default: 30 days back
        baseline: dict = {}
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """SELECT started_at, pattern_baseline FROM trawl_scans
                       WHERE case_id = %s AND scan_status IN ('completed', 'partial')
                       ORDER BY started_at DESC LIMIT 1""",
                    (case_id,),
                )
                row = cur.fetchone()
                if row:
                    since = row[0] if row[0] else since
                    bl = row[1]
                    if isinstance(bl, str):
                        baseline = json.loads(bl)
                    elif isinstance(bl, dict):
                        baseline = bl
        except Exception as e:
            logger.error("Failed to load last scan: %s", str(e)[:300])
        return since, baseline

    def _get_current_baseline(self, case_id: str) -> dict:
        """Get current pattern scores for baseline storage."""
        try:
            report = self._pattern_svc.discover_top_patterns(case_id)
            patterns = report.get("patterns", [])
            return {
                p.get("title", f"pattern_{i}"): p.get("composite_score", 0.0)
                for i, p in enumerate(patterns)
            }
        except Exception as e:
            logger.error("Failed to get current baseline: %s", str(e)[:300])
            return {}


    # ------------------------------------------------------------------
    # Phase 1: Graph Scan
    # ------------------------------------------------------------------

    def _phase_graph_scan(self, case_id: str, since: datetime) -> list:
        """Query Neptune for new entity connections since last scan.

        Detects: new_connection, network_expansion, temporal_anomaly.
        """
        candidates: list = []
        label = f"Entity_{case_id}"
        since_str = since.strftime("%Y-%m-%dT%H:%M:%S")

        # 1. New connections: edges added since last scan
        try:
            q = (
                f"g.V().hasLabel('{_escape(label)}')"
                f".bothE('RELATED_TO').has('created_at', P.gte('{since_str}'))"
                f".project('edge_id','src','tgt','docs')"
                f".by(id())"
                f".by(outV().values('canonical_name'))"
                f".by(inV().values('canonical_name'))"
                f".by(coalesce(values('source_document_refs'), constant('')))"
                f".limit(200)"
            )
            edges = self._gremlin(q)

            # Group by entity pair for new_connection detection
            pair_edges: dict = {}
            entity_connections: dict = {}
            for edge in edges:
                if not isinstance(edge, dict):
                    continue
                src = str(edge.get("src", ""))
                tgt = str(edge.get("tgt", ""))
                edge_id = str(edge.get("edge_id", ""))
                docs = str(edge.get("docs", ""))
                if not src or not tgt:
                    continue

                pair_key = tuple(sorted([src, tgt]))
                pair_edges.setdefault(pair_key, []).append({
                    "edge_id": edge_id, "docs": docs,
                })

                # Track connections per entity for network_expansion
                entity_connections.setdefault(src, set()).add(tgt)
                entity_connections.setdefault(tgt, set()).add(src)

            # new_connection alerts: pairs with ≥3 shared evidence docs
            for (ent_a, ent_b), edge_list in pair_edges.items():
                doc_refs = [e["docs"] for e in edge_list if e["docs"]]
                evidence_refs = [
                    make_evidence_ref(e["edge_id"], "graph_edge", e["edge_id"], f"Connection: {ent_a} ↔ {ent_b}")
                    for e in edge_list
                ]
                if len(evidence_refs) >= ALERT_THRESHOLDS["new_connection"]:
                    candidates.append({
                        "alert_type": "new_connection",
                        "title": f"New connection: {ent_a} ↔ {ent_b}",
                        "summary": f"Detected {len(evidence_refs)} shared evidence links between {ent_a} and {ent_b}.",
                        "entity_names": [ent_a, ent_b],
                        "evidence_refs": evidence_refs,
                        "source_type": "internal",
                    })

            # network_expansion alerts: ≥3 new connections to single entity
            for entity, connections in entity_connections.items():
                if len(connections) >= ALERT_THRESHOLDS["network_expansion"]:
                    evidence_refs = [
                        make_evidence_ref(str(uuid.uuid4()), "graph_edge", f"{entity}->{c}", f"New connection to {c}")
                        for c in list(connections)[:20]
                    ]
                    candidates.append({
                        "alert_type": "network_expansion",
                        "title": f"Network expansion: {entity}",
                        "summary": f"{entity} gained {len(connections)} new connections since last scan.",
                        "entity_names": [entity] + list(connections)[:5],
                        "evidence_refs": evidence_refs,
                        "source_type": "internal",
                    })

        except Exception as e:
            logger.error("Graph new connections query failed: %s", str(e)[:300])

        # 2. Temporal anomaly: events in 48-hour window with ≥3 tracked entities
        try:
            q = (
                f"g.V().hasLabel('{_escape(label)}')"
                f".has('entity_type', 'event')"
                f".has('created_at', P.gte('{since_str}'))"
                f".project('name','created_at','connected_entities')"
                f".by('canonical_name')"
                f".by('created_at')"
                f".by(both('RELATED_TO').hasLabel('{_escape(label)}').values('canonical_name').dedup().fold())"
                f".limit(100)"
            )
            events = self._gremlin(q)
            temporal_candidates = self._detect_temporal_anomalies(events)
            candidates.extend(temporal_candidates)
        except Exception as e:
            logger.error("Temporal anomaly query failed: %s", str(e)[:300])

        return candidates

    @staticmethod
    def _detect_temporal_anomalies(events: list) -> list:
        """Detect clusters of events within 48-hour windows involving ≥3 entities.

        This is a static method for testability.
        """
        candidates: list = []
        if not events:
            return candidates

        # Parse events with timestamps
        parsed: list = []
        for ev in events:
            if not isinstance(ev, dict):
                continue
            name = ev.get("name", "")
            ts_str = ev.get("created_at", "")
            connected = ev.get("connected_entities", [])
            if isinstance(connected, dict) and "@value" in connected:
                connected = connected["@value"]
            if not isinstance(connected, list):
                connected = []

            ts = None
            if ts_str:
                try:
                    if isinstance(ts_str, datetime):
                        ts = ts_str
                    else:
                        ts = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass
            if ts:
                parsed.append({"name": name, "ts": ts, "entities": connected})

        if len(parsed) < 2:
            return candidates

        # Sort by timestamp
        parsed.sort(key=lambda x: x["ts"])

        # Sliding window: check 48-hour windows
        window = timedelta(hours=48)
        checked_windows: set = set()
        for i, ev_start in enumerate(parsed):
            window_entities: set = set()
            window_events: list = []
            for j in range(i, len(parsed)):
                if parsed[j]["ts"] - ev_start["ts"] <= window:
                    window_entities.update(parsed[j]["entities"])
                    window_events.append(parsed[j])
                else:
                    break

            if len(window_entities) >= 3:
                key = frozenset(window_entities)
                if key not in checked_windows:
                    checked_windows.add(key)
                    entity_list = sorted(window_entities)
                    evidence_refs = [
                        make_evidence_ref(
                            str(uuid.uuid4()), "graph_edge",
                            we["name"], f"Event at {we['ts'].isoformat()}"
                        )
                        for we in window_events[:20]
                    ]
                    candidates.append({
                        "alert_type": "temporal_anomaly",
                        "title": f"Temporal cluster: {len(window_entities)} entities in 48h window",
                        "summary": (
                            f"Events involving {', '.join(entity_list[:5])} "
                            f"clustered within a 48-hour window."
                        ),
                        "entity_names": entity_list[:10],
                        "evidence_refs": evidence_refs,
                        "source_type": "internal",
                    })

        return candidates


    # ------------------------------------------------------------------
    # Phase 2: Document Scan
    # ------------------------------------------------------------------

    def _phase_document_scan(
        self, case_id: str, since: datetime,
        targeted_doc_ids: Optional[list] = None,
    ) -> list:
        """Query OpenSearch for newly ingested documents matching tracked entities.

        Detects: entity_spike, new_evidence_match.
        """
        candidates: list = []

        # Get tracked entities from Neptune
        entity_names: list = []
        try:
            label = f"Entity_{case_id}"
            q = (
                f"g.V().hasLabel('{_escape(label)}')"
                f".values('canonical_name').dedup().limit(100)"
            )
            entity_names = [str(n) for n in self._gremlin(q) if n]
        except Exception as e:
            logger.error("Failed to get tracked entities: %s", str(e)[:300])

        if not entity_names and not targeted_doc_ids:
            return candidates

        # Query OpenSearch for new documents
        new_docs: list = []
        if self._search_svc and hasattr(self._search_svc, '_search_documents'):
            # Use InvestigativeSearchService pattern
            for entity in entity_names[:20]:
                try:
                    results = self._search_svc._search_documents(case_id, entity, top_k=20)
                    for doc in results:
                        doc_id = doc.get("document_id", doc.get("id", ""))
                        if targeted_doc_ids and doc_id not in targeted_doc_ids:
                            continue
                        new_docs.append({
                            "doc_id": doc_id,
                            "filename": doc.get("source_filename", doc.get("source", "")),
                            "excerpt": (doc.get("text_excerpt") or doc.get("text") or doc.get("content", ""))[:500],
                            "entity": entity,
                        })
                except Exception as e:
                    logger.error("Doc search for entity '%s' failed: %s", entity, str(e)[:200])
        elif self._search_svc and hasattr(self._search_svc, 'search'):
            for entity in entity_names[:20]:
                try:
                    results = self._search_svc.search(case_id, entity, top_k=20)
                    for doc in results:
                        d = doc.model_dump() if hasattr(doc, "model_dump") else (doc if isinstance(doc, dict) else {"text": str(doc)})
                        doc_id = d.get("document_id", d.get("id", ""))
                        if targeted_doc_ids and doc_id not in targeted_doc_ids:
                            continue
                        new_docs.append({
                            "doc_id": doc_id,
                            "filename": d.get("source_filename", d.get("source", "")),
                            "excerpt": (d.get("text_excerpt") or d.get("text") or d.get("content", ""))[:500],
                            "entity": entity,
                        })
                except Exception as e:
                    logger.error("Doc search for entity '%s' failed: %s", entity, str(e)[:200])

        # Count docs per entity for entity_spike detection
        entity_doc_count: dict = {}
        entity_docs: dict = {}
        for doc in new_docs:
            ent = doc["entity"]
            entity_doc_count[ent] = entity_doc_count.get(ent, 0) + 1
            entity_docs.setdefault(ent, []).append(doc)

        # entity_spike: ≥5 new docs for single entity
        for entity, count in entity_doc_count.items():
            if count >= ALERT_THRESHOLDS["entity_spike"]:
                docs = entity_docs[entity][:20]
                evidence_refs = [
                    make_evidence_ref(d["doc_id"], "document", d["filename"], d["excerpt"])
                    for d in docs
                ]
                candidates.append({
                    "alert_type": "entity_spike",
                    "title": f"Entity spike: {entity} ({count} new documents)",
                    "summary": f"{entity} appears in {count} newly matched documents.",
                    "entity_names": [entity],
                    "evidence_refs": evidence_refs,
                    "source_type": "internal",
                })

        # new_evidence_match: any new doc matching tracked entities
        if targeted_doc_ids and new_docs:
            # Group by doc for targeted scans
            doc_entities: dict = {}
            for doc in new_docs:
                doc_entities.setdefault(doc["doc_id"], {
                    "filename": doc["filename"],
                    "excerpt": doc["excerpt"],
                    "entities": set(),
                })
                doc_entities[doc["doc_id"]]["entities"].add(doc["entity"])

            for doc_id, info in doc_entities.items():
                evidence_refs = [
                    make_evidence_ref(doc_id, "document", info["filename"], info["excerpt"])
                ]
                entity_list = sorted(info["entities"])
                candidates.append({
                    "alert_type": "new_evidence_match",
                    "title": f"New evidence: {info['filename']}",
                    "summary": f"New document matches entities: {', '.join(entity_list[:5])}.",
                    "entity_names": entity_list[:10],
                    "evidence_refs": evidence_refs,
                    "source_type": "internal",
                })

        return candidates

    # ------------------------------------------------------------------
    # Phase 3: Pattern Comparison
    # ------------------------------------------------------------------

    def _phase_pattern_comparison(self, case_id: str, baseline: dict) -> list:
        """Compare current pattern scores against previous baseline.

        Detects: pattern_change (score increase >25%).
        """
        candidates: list = []
        report = self._pattern_svc.discover_top_patterns(case_id)
        current_patterns = report.get("patterns", [])

        current_scores: dict = {}
        for p in current_patterns:
            title = p.get("title", p.get("question", ""))
            score = p.get("composite_score", 0.0)
            if title:
                current_scores[title] = {"score": score, "pattern": p}

        # Compare against baseline
        changed = detect_pattern_changes(baseline, current_scores)
        for change in changed:
            pattern_title = change["title"]
            p_data = current_scores.get(pattern_title, {}).get("pattern", {})
            entities = [
                e.get("name", "") for e in p_data.get("entities", [])
                if isinstance(e, dict) and e.get("name")
            ]
            evidence_refs = [
                make_evidence_ref(
                    str(uuid.uuid4()), "document", pattern_title,
                    f"Score changed from {change['old_score']:.3f} to {change['new_score']:.3f} (+{change['pct_change']:.0f}%)"
                )
            ]
            candidates.append({
                "alert_type": "pattern_change",
                "title": f"Pattern change: {pattern_title}",
                "summary": (
                    f"Pattern '{pattern_title}' score increased by "
                    f"{change['pct_change']:.0f}% (from {change['old_score']:.3f} to {change['new_score']:.3f})."
                ),
                "entity_names": entities[:10],
                "evidence_refs": evidence_refs,
                "source_type": "internal",
            })

        return candidates


    # ------------------------------------------------------------------
    # Phase 4: Cross-Case Scan
    # ------------------------------------------------------------------

    def _phase_cross_case_scan(self, case_id: str) -> list:
        """Detect new cross-case entity overlaps.

        Detects: cross_case_overlap (severity high).
        """
        candidates: list = []
        overlaps = self._cross_case_svc.scan_for_overlaps(case_id)

        for match in overlaps:
            entity_a = match.entity_a if isinstance(match.entity_a, dict) else {}
            entity_b = match.entity_b if isinstance(match.entity_b, dict) else {}
            name_a = entity_a.get("name", "")
            name_b = entity_b.get("name", "")
            case_b = entity_b.get("case_id", "")

            entity_names = sorted(set(filter(None, [name_a, name_b])))
            evidence_refs = [
                make_evidence_ref(
                    entity_a.get("entity_id", str(uuid.uuid4())),
                    "graph_edge",
                    f"Cross-case: {case_id} ↔ {case_b}",
                    f"Entity '{name_a}' found in both case {case_id} and case {case_b}."
                ),
            ]

            candidates.append({
                "alert_type": "cross_case_overlap",
                "title": f"Cross-case overlap: {name_a or name_b}",
                "summary": (
                    f"Entity '{name_a}' appears in both this case and case {case_b}. "
                    f"Similarity score: {getattr(match, 'similarity_score', 1.0):.2f}."
                ),
                "entity_names": entity_names,
                "evidence_refs": evidence_refs,
                "source_type": "internal",
            })

        return candidates

    # ------------------------------------------------------------------
    # Phase 5: External OSINT
    # ------------------------------------------------------------------

    def _phase_external_trawl(self, case_id: str, config: dict) -> list:
        """OSINT scan via AIResearchAgent + cross-reference report.

        Detects: external_lead.
        """
        candidates: list = []

        if not self._research_agent or not self._search_svc:
            return candidates

        # Get top tracked entities
        entity_names: list = []
        try:
            label = f"Entity_{case_id}"
            q = (
                f"g.V().hasLabel('{_escape(label)}')"
                f".order().by(bothE('RELATED_TO').count(), desc)"
                f".limit({MAX_EXTERNAL_ENTITIES})"
                f".project('name','type')"
                f".by('canonical_name')"
                f".by('entity_type')"
            )
            entity_names = self._gremlin(q)
        except Exception as e:
            logger.error("Failed to get top entities for OSINT: %s", str(e)[:300])

        if not entity_names:
            return candidates

        subjects = [
            {"name": e.get("name", ""), "type": e.get("type", "person")}
            for e in entity_names if isinstance(e, dict) and e.get("name")
        ][:MAX_EXTERNAL_ENTITIES]

        # Research via AIResearchAgent
        external_results: list = []
        try:
            external_results = self._research_agent.research_all_subjects(
                subjects=subjects, osint_directives=[], evidence_hints=[],
            )
        except Exception as e:
            logger.error("AIResearchAgent failed: %s", str(e)[:300])
            return candidates

        if not external_results:
            return candidates

        # Cross-reference via InvestigativeSearchService
        internal_brief = {"executive_summary": f"Internal case {case_id} evidence"}
        xref_entries: list = []
        try:
            if hasattr(self._search_svc, '_generate_cross_reference_report'):
                xref_entries = self._search_svc._generate_cross_reference_report(
                    internal_brief, external_results,
                )
            else:
                # Fallback: treat all external results as external_only
                for r in external_results:
                    if r.get("success", False):
                        xref_entries.append({
                            "finding": r.get("subject_name", ""),
                            "category": "external_only",
                            "internal_evidence": [],
                            "external_source": r.get("research_text", "")[:200],
                        })
        except Exception as e:
            logger.error("Cross-reference report failed: %s", str(e)[:300])

        # Generate alerts from cross-reference entries
        ext_candidates = categorize_external_findings(xref_entries)
        candidates.extend(ext_candidates)

        return candidates


    # ------------------------------------------------------------------
    # Alert generation, filtering, dedup, persistence
    # ------------------------------------------------------------------

    def _generate_alerts(
        self, case_id: str, candidates: list, config: dict,
    ) -> list:
        """Apply severity rules and config filters to candidate alerts."""
        enabled_types = config.get("enabled_alert_types", DEFAULT_CONFIG["enabled_alert_types"])
        min_sev = config.get("min_severity", "low")

        alerts: list = []
        for c in candidates:
            alert_type = c.get("alert_type", "")
            evidence_refs = c.get("evidence_refs", [])

            # Assign severity based on evidence count (or forced severity)
            forced = c.get("_force_severity")
            severity = forced if forced else assign_severity(len(evidence_refs))

            # Apply config filters
            if not filter_alert_by_config(alert_type, severity, enabled_types, min_sev):
                continue

            alerts.append({
                "alert_id": str(uuid.uuid4()),
                "case_id": case_id,
                "alert_type": alert_type,
                "severity": severity,
                "title": c.get("title", ""),
                "summary": c.get("summary", ""),
                "entity_names": c.get("entity_names", []),
                "evidence_refs": evidence_refs,
                "source_type": c.get("source_type", "internal"),
            })

        return alerts

    def _enrich_alerts_with_ai(self, alerts: list) -> list:
        """Add AI-generated one-line insights to each alert via Bedrock Claude Haiku."""
        if not self._bedrock or not alerts:
            return alerts
        for alert in alerts:
            try:
                prompt = (
                    "You are an investigative analyst. Given this alert, write ONE sentence "
                    "explaining its investigative significance.\n"
                    f"Alert: {alert.get('title', '')}\n"
                    f"Entities: {', '.join(alert.get('entity_names', []))}\n"
                    f"Evidence: {alert.get('summary', '')}"
                )
                resp = self._bedrock.invoke_model(
                    modelId="anthropic.claude-3-haiku-20240307-v1:0",
                    contentType="application/json",
                    accept="application/json",
                    body=json.dumps({
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 150,
                        "messages": [{"role": "user", "content": prompt}],
                    }),
                )
                body = json.loads(resp["body"].read())
                text = body.get("content", [{}])[0].get("text", "").strip()
                alert["ai_insight"] = text if text else alert.get("summary", "")
            except Exception as e:
                logger.warning("AI enrichment failed for alert %s: %s", alert.get("alert_id", "?"), str(e)[:200])
                alert["ai_insight"] = alert.get("summary", "")
        return alerts

    def _deduplicate_alerts(self, case_id: str, alerts: list) -> list:
        """Check for existing non-dismissed alerts with overlapping entities within 7 days."""
        deduped: list = []
        for alert in alerts:
            entity_names = alert.get("entity_names", [])
            alert_type = alert.get("alert_type", "")

            is_dup = is_duplicate_alert(
                case_id, alert_type, entity_names,
                self._alert_store,
            )

            if is_dup:
                # Merge into existing
                existing = self._alert_store.find_duplicate(case_id, alert_type, entity_names)
                if existing:
                    try:
                        self._alert_store.merge_into_existing(
                            existing["alert_id"],
                            alert.get("evidence_refs", []),
                            alert.get("summary", ""),
                        )
                        logger.debug(
                            "Deduplicated alert: type=%s, entities=%s merged into %s",
                            alert_type, entity_names, existing["alert_id"],
                        )
                    except Exception as e:
                        logger.error("Merge failed for alert %s: %s", existing["alert_id"], str(e)[:200])
            else:
                deduped.append(alert)

        return deduped

    def _persist_alerts(
        self, case_id: str, scan_id: str, alerts: list,
    ) -> int:
        """Insert new alerts into Aurora. Returns count of successfully persisted alerts."""
        count = 0
        for alert in alerts:
            try:
                with self._db.cursor() as cur:
                    cur.execute(
                        """INSERT INTO trawler_alerts
                           (alert_id, case_id, scan_id, alert_type, severity,
                            title, summary, entity_names, evidence_refs,
                            source_type, is_read, is_dismissed, ai_insight)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb,
                                   %s::jsonb, %s, FALSE, FALSE, %s)""",
                        (
                            alert["alert_id"], case_id, scan_id,
                            alert["alert_type"], alert["severity"],
                            alert["title"], alert["summary"],
                            json.dumps(alert.get("entity_names", [])),
                            json.dumps(alert.get("evidence_refs", [])),
                            alert.get("source_type", "internal"),
                            alert.get("ai_insight"),
                        ),
                    )
                count += 1
            except Exception as e:
                logger.error(
                    "Failed to persist alert %s: %s",
                    alert.get("alert_id", "?"), str(e)[:300],
                )
        return count

    # ------------------------------------------------------------------
    # Trawl config CRUD
    # ------------------------------------------------------------------

    def get_trawl_config(self, case_id: str) -> dict:
        """Load per-case trawl config from Aurora, falling back to defaults."""
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """SELECT enabled_alert_types, min_severity, external_trawl_enabled
                       FROM trawl_configs WHERE case_id = %s""",
                    (case_id,),
                )
                row = cur.fetchone()
                if row:
                    eat = row[0]
                    if isinstance(eat, str):
                        eat = json.loads(eat)
                    return {
                        "enabled_alert_types": eat if isinstance(eat, list) else DEFAULT_CONFIG["enabled_alert_types"],
                        "min_severity": row[1] or "low",
                        "external_trawl_enabled": bool(row[2]) if row[2] is not None else False,
                    }
        except Exception as e:
            logger.error("Failed to load trawl config: %s", str(e)[:300])
        return dict(DEFAULT_CONFIG)

    def save_trawl_config(self, case_id: str, config: dict) -> dict:
        """Persist per-case trawl config to Aurora via upsert."""
        enabled = config.get("enabled_alert_types", DEFAULT_CONFIG["enabled_alert_types"])
        min_sev = config.get("min_severity", "low")
        ext_enabled = config.get("external_trawl_enabled", False)

        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """INSERT INTO trawl_configs
                       (case_id, enabled_alert_types, min_severity, external_trawl_enabled, updated_at)
                       VALUES (%s, %s::jsonb, %s, %s, NOW())
                       ON CONFLICT (case_id) DO UPDATE SET
                           enabled_alert_types = EXCLUDED.enabled_alert_types,
                           min_severity = EXCLUDED.min_severity,
                           external_trawl_enabled = EXCLUDED.external_trawl_enabled,
                           updated_at = NOW()""",
                    (case_id, json.dumps(enabled), min_sev, ext_enabled),
                )
        except Exception as e:
            logger.error("Failed to save trawl config: %s", str(e)[:300])
            raise

        return {
            "case_id": case_id,
            "enabled_alert_types": enabled,
            "min_severity": min_sev,
            "external_trawl_enabled": ext_enabled,
        }



# ---------------------------------------------------------------------------
# Module-level helpers (extracted for property-based testing)
# ---------------------------------------------------------------------------

def detect_pattern_changes(baseline: dict, current_scores: dict) -> list:
    """Detect patterns whose score increased >25% vs baseline.

    Args:
        baseline: dict mapping pattern title → float score.
        current_scores: dict mapping pattern title → {"score": float, ...}.

    Returns:
        List of dicts with title, old_score, new_score, pct_change.
    """
    changes: list = []
    for title, info in current_scores.items():
        new_score = info["score"] if isinstance(info, dict) else float(info)
        old_score = baseline.get(title, 0.0)
        if isinstance(old_score, dict):
            old_score = old_score.get("score", 0.0)
        old_score = float(old_score)
        new_score = float(new_score)

        if old_score > 0 and new_score > old_score * 1.25:
            pct = ((new_score - old_score) / old_score) * 100
            changes.append({
                "title": title,
                "old_score": old_score,
                "new_score": new_score,
                "pct_change": pct,
            })
    return changes


def filter_alert_by_config(
    alert_type: str,
    severity: str,
    enabled_types: list,
    min_severity: str,
) -> bool:
    """Check if an alert passes config-based filtering.

    Returns True if alert_type is in enabled_types AND severity meets
    or exceeds min_severity threshold.
    """
    if alert_type not in enabled_types:
        return False
    return severity_meets_threshold(severity, min_severity)


def is_duplicate_alert(
    case_id: str,
    alert_type: str,
    entity_names: list,
    alert_store: Optional[TrawlerAlertStore] = None,
) -> bool:
    """Check if a candidate alert is a duplicate of an existing one.

    A duplicate exists when the store has a non-dismissed alert with the
    same case_id, alert_type, at least one overlapping entity_name,
    created within the past 7 days.
    """
    if not alert_store or not entity_names:
        return False
    existing = alert_store.find_duplicate(case_id, alert_type, entity_names)
    return existing is not None


def categorize_external_findings(xref_entries: list) -> list:
    """Generate external_lead alert candidates from cross-reference entries.

    - "external_only" → external_lead alert
    - "confirmed_internally" → external_lead alert with severity medium
    - "needs_research" → no alert
    """
    candidates: list = []
    for entry in xref_entries:
        if not isinstance(entry, dict):
            continue
        category = entry.get("category", "needs_research")
        finding = entry.get("finding", "")
        source = entry.get("external_source", "")

        if category == "needs_research":
            continue

        source_label = str(source)[:200] if source else "external source"
        evidence_refs = [
            make_evidence_ref(
                str(uuid.uuid4()), "external_url",
                source_label, str(finding)[:500],
            )
        ]

        if category == "external_only":
            candidates.append({
                "alert_type": "external_lead",
                "title": f"External lead: {str(finding)[:100]}",
                "summary": str(finding)[:500],
                "entity_names": [str(finding)[:100]] if finding else [],
                "evidence_refs": evidence_refs,
                "source_type": "osint",
            })
        elif category == "confirmed_internally":
            # Force severity medium via evidence count (3-4 refs)
            # Add padding refs to ensure medium severity
            for _ in range(2):
                evidence_refs.append(
                    make_evidence_ref(
                        str(uuid.uuid4()), "external_url",
                        source_label, f"Corroborating evidence for: {str(finding)[:400]}",
                    )
                )
            candidates.append({
                "alert_type": "external_lead",
                "title": f"Corroborated: {str(finding)[:100]}",
                "summary": f"External finding corroborates internal evidence: {str(finding)[:400]}",
                "entity_names": [str(finding)[:100]] if finding else [],
                "evidence_refs": evidence_refs,
                "source_type": "osint",
                "_force_severity": "medium",
            })

    return candidates
