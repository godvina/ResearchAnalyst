"""Command Center Engine — computes intelligence indicators and generates strategic assessments.

Computes five Intelligence Indicator scores (0-100 each) from Neptune graph data
and Aurora entity/document data, derives a composite Viability Score, generates
a structured Strategic Assessment via Bedrock, and identifies Threat Threads
from existing lead data.

Uses Neptune HTTP API (POST /gremlin) for graph queries, same pattern as
trawler_engine.py and pattern_discovery_service.py.
"""

import json
import logging
import re
import ssl
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, List, Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
CACHE_TTL_SECONDS = 900  # 15 minutes


def _escape(s: str) -> str:
    """Escape a string for Gremlin query embedding."""
    return s.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')


def _clamp(value: int, lo: int = 0, hi: int = 100) -> int:
    """Clamp an integer to [lo, hi]."""
    return max(lo, min(hi, value))


# ---------------------------------------------------------------------------
# IndicatorResult dataclass
# ---------------------------------------------------------------------------

@dataclass
class IndicatorResult:
    """Result of a single intelligence indicator computation."""
    name: str
    key: str
    score: int          # 0-100
    insight: str        # one-line summary
    gap_note: str       # what's missing
    emoji: str          # display icon
    raw_data: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Color classification helper
# ---------------------------------------------------------------------------

def classify_indicator_color(score: int) -> str:
    """Classify indicator card color based on score.

    Green for >60, yellow/amber for 30-60, red for <30.
    """
    if score > 60:
        return "green"
    if score >= 30:
        return "yellow"
    return "red"


# ---------------------------------------------------------------------------
# CommandCenterEngine
# ---------------------------------------------------------------------------

class CommandCenterEngine:
    """Computes intelligence indicators and generates strategic assessments."""

    SENIOR_ANALYST_PERSONA = (
        "You are a senior federal investigative analyst with 20+ years of experience "
        "in complex multi-jurisdictional investigations. You brief supervising attorneys "
        "with precision and clarity. Every statement must be grounded in the evidence data "
        "provided. Use proper investigative methodology and legal terminology."
    )

    def __init__(
        self,
        aurora_cm: Any,
        bedrock_client: Optional[Any],
        neptune_endpoint: str,
        neptune_port: str,
        case_assessment_svc: Any,
        case_weakness_svc: Any,
        investigator_engine: Any,
    ) -> None:
        self._db = aurora_cm
        self._bedrock = bedrock_client
        self._neptune_ep = neptune_endpoint
        self._neptune_port = neptune_port
        self._case_assessment_svc = case_assessment_svc
        self._case_weakness_svc = case_weakness_svc
        self._investigator_engine = investigator_engine

    # ------------------------------------------------------------------
    # GraphSON deserialization helper
    # ------------------------------------------------------------------

    @staticmethod
    def _deserialize_graphson(obj: Any) -> Any:
        """Recursively deserialize Neptune GraphSON typed values.

        Handles g:Map, g:List, g:Int32, g:Int64, g:Double, g:Float, g:Date.
        Converts g:Map from flat [k,v,k,v,...] arrays to Python dicts.
        """
        if not isinstance(obj, dict):
            return obj
        t = obj.get("@type")
        v = obj.get("@value")
        if t is None or v is None:
            # Regular dict — recurse into values
            return {k: CommandCenterEngine._deserialize_graphson(val) for k, val in obj.items()}
        if t == "g:Map":
            # @value is a flat list: [key, value, key, value, ...]
            result = {}
            if isinstance(v, list):
                for i in range(0, len(v) - 1, 2):
                    key = CommandCenterEngine._deserialize_graphson(v[i])
                    val = CommandCenterEngine._deserialize_graphson(v[i + 1])
                    result[key] = val
            return result
        if t == "g:List":
            return [CommandCenterEngine._deserialize_graphson(item) for item in v] if isinstance(v, list) else v
        if t in ("g:Int32", "g:Int64"):
            return int(v)
        if t in ("g:Double", "g:Float"):
            return float(v)
        # For other types (g:Date, g:UUID, etc.), return the raw value
        return v

    # ------------------------------------------------------------------
    # Neptune helper (same pattern as trawler_engine.py)
    # ------------------------------------------------------------------

    def _gremlin(self, query: str, timeout: int = 12) -> list:
        """Execute a Gremlin query via Neptune HTTPS endpoint."""
        if not self._neptune_ep:
            logger.warning("_gremlin: Neptune endpoint not configured, returning empty")
            return []
        url = f"https://{self._neptune_ep}:{self._neptune_port}/gremlin"
        data = json.dumps({"gremlin": query}).encode()
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
                body = json.loads(resp.read().decode())
        except Exception as exc:
            logger.error("_gremlin query failed (timeout=%ds): %s\nQuery: %s", timeout, str(exc)[:200], query[:200])
            raise
        raw = body.get("result", {}).get("data", {})
        if isinstance(raw, dict) and "@value" in raw:
            raw = raw["@value"]
        if not isinstance(raw, list):
            return []
        # Deserialize GraphSON typed values (g:Map, g:Int32, etc.)
        return [self._deserialize_graphson(item) for item in raw]

    # ------------------------------------------------------------------
    # Viability score and verdict
    # ------------------------------------------------------------------

    @staticmethod
    def compute_viability_score(indicators: List[IndicatorResult]) -> int:
        """Equal-weighted average of indicator scores, clamped to int 0-100."""
        if not indicators:
            return 0
        total = sum(ind.score for ind in indicators)
        avg = total / len(indicators)
        return _clamp(round(avg))

    @staticmethod
    def classify_verdict(score: int) -> str:
        """Classify verdict from viability score.

        PURSUE (67-100), INVESTIGATE FURTHER (34-66), CLOSE (0-33).
        """
        if score >= 67:
            return "PURSUE"
        if score >= 34:
            return "INVESTIGATE FURTHER"
        return "CLOSE"

    # ------------------------------------------------------------------
    # Indicator 1: Signal Strength (Neptune)
    # ------------------------------------------------------------------

    def compute_signal_strength(self, case_id: str) -> IndicatorResult:
        """Query Neptune for meaningful vs noise entity connections.

        Meaningful = relationship_type in (causal, temporal, geographic,
        co-occurrence, thematic).  Only truly noise edges are excluded.
        Score = clamp(int((meaningful / max(total, 1)) * 100), 0, 100).
        """
        try:
            label = f"Entity_{_escape(case_id)}"

            # Total edge count first (simpler query, less likely to fail)
            total_query = (
                f"g.V().hasLabel('{label}')"
                f".bothE('RELATED_TO').limit(10000)"
                f".count()"
            )
            logger.info("Signal Strength: querying total edges for label %s", label)
            total_result = self._gremlin(total_query, timeout=10)
            total = self._extract_count(total_result)
            logger.info("Signal Strength: total edges = %d", total)

            if total == 0:
                return IndicatorResult(
                    name="Signal Strength", key="signal_strength", score=0,
                    insight="No entity connections found in graph",
                    gap_note="Ingest more documents to build entity connections",
                    emoji="📡", raw_data={"meaningful": 0, "total": 0, "ratio": 0},
                )

            # Count meaningful connections — all substantive relationship types
            # co-occurrence = entities appear together in documents (signal)
            # causal/temporal/geographic/thematic = extracted relationships (strong signal)
            meaningful_query = (
                f"g.V().hasLabel('{label}')"
                f".bothE('RELATED_TO').limit(10000)"
                f".has('relationship_type', within("
                f"'causal','temporal','geographic','co-occurrence','thematic'))"
                f".count()"
            )
            meaningful_result = self._gremlin(meaningful_query, timeout=10)
            meaningful = self._extract_count(meaningful_result)
            logger.info("Signal Strength: meaningful edges = %d", meaningful)

            ratio = meaningful / max(total, 1)
            score = _clamp(int(ratio * 100))

            insight = f"{int(ratio * 100)}% of connections are substantive ({meaningful} of {total})"
            gap_note = "Financial link data would improve signal clarity" if ratio < 0.6 else "Signal strength is healthy"

            return IndicatorResult(
                name="Signal Strength",
                key="signal_strength",
                score=score,
                insight=insight,
                gap_note=gap_note,
                emoji="📡",
                raw_data={"meaningful": meaningful, "total": total, "ratio": ratio},
            )
        except Exception as exc:
            logger.error("compute_signal_strength failed for %s: %s", case_id, str(exc)[:300])
            return IndicatorResult(
                name="Signal Strength", key="signal_strength", score=0,
                insight="Unable to compute signal strength",
                gap_note="Neptune unavailable", emoji="📡",
                raw_data={"error": str(exc)[:300]},
            )

    # ------------------------------------------------------------------
    # Indicator 2: Corroboration Depth (Aurora)
    # ------------------------------------------------------------------

    def compute_corroboration_depth(self, case_id: str) -> IndicatorResult:
        """Query Neptune for multi-source vs single-source entities.

        Uses occurrence_count as a corroboration proxy — entities appearing
        in multiple document extractions (occurrence_count >= 2) are considered
        corroborated.  Also counts entities with 2+ graph connections as
        cross-referenced.

        Score = clamp(int((corroborated / max(total_entities, 1)) * 100), 0, 100).
        """
        try:
            label = f"Entity_{_escape(case_id)}"

            # Get entities with their occurrence count and connection degree
            q = (
                f"g.V().hasLabel('{label}').limit(500)"
                f".project('name','occurrences','degree')"
                f".by('canonical_name')"
                f".by(coalesce(values('occurrence_count'), constant(1)))"
                f".by(bothE('RELATED_TO').count())"
            )
            logger.info("Corroboration Depth: querying entities for label %s", label)
            results = self._gremlin(q, timeout=10)
            logger.info("Corroboration Depth: got %d entity results, sample: %s",
                        len(results), json.dumps(results[:2], default=str)[:500])

            multi = 0
            single = 0
            uncorroborated = []
            for r in results:
                if not isinstance(r, dict):
                    continue
                occ = r.get("occurrences", 1)
                if isinstance(occ, dict):
                    occ = occ.get("@value", 1)
                degree = r.get("degree", 0)
                if isinstance(degree, dict):
                    degree = degree.get("@value", 0)

                # Corroborated = appears multiple times OR has 2+ connections
                if int(occ) >= 2 or int(degree) >= 2:
                    multi += 1
                else:
                    single += 1
                    name = r.get("name", "")
                    if name and len(uncorroborated) < 5:
                        uncorroborated.append(name)

            total_entities = multi + single
            ratio = multi / max(total_entities, 1)
            score = _clamp(int(ratio * 100))

            insight = f"{multi} entities corroborated across sources vs {single} single-source"
            gap_note = (
                f"Uncorroborated: {', '.join(uncorroborated[:3])}"
                if uncorroborated
                else "Corroboration depth is solid"
            )

            return IndicatorResult(
                name="Corroboration Depth",
                key="corroboration_depth",
                score=score,
                insight=insight,
                gap_note=gap_note,
                emoji="🔗",
                raw_data={"multi_source": multi, "single_source": single, "ratio": ratio, "total_entities": total_entities},
            )
        except Exception as exc:
            logger.error("compute_corroboration_depth failed for %s: %s", case_id, str(exc)[:300])
            return IndicatorResult(
                name="Corroboration Depth", key="corroboration_depth", score=0,
                insight="Unable to compute corroboration depth",
                gap_note="Neptune graph query failed", emoji="🔗",
                raw_data={"error": str(exc)[:300]},
            )

    # ------------------------------------------------------------------
    # Indicator 3: Network Density (Neptune)
    # ------------------------------------------------------------------

    def compute_network_density(self, case_id: str) -> IndicatorResult:
        """Query Neptune for clustering coefficient and hub detection.

        Score = clamp(int(clustering_coeff * 50 + min(hub_count / 3, 1.0) * 50), 0, 100).
        Hub = entity with > 10 connections.

        Uses a two-step approach: first get node count + degree stats via
        simple queries, then attempt clustering coefficient if time allows.
        """
        try:
            label = f"Entity_{_escape(case_id)}"

            # Step 1: Get total node count (fast query)
            count_query = f"g.V().hasLabel('{label}').count()"
            logger.info("Network Density: counting nodes for label %s", label)
            count_result = self._gremlin(count_query, timeout=8)
            node_count = self._extract_count(count_result)
            logger.info("Network Density: %d nodes found", node_count)

            if node_count == 0:
                return IndicatorResult(
                    name="Network Density", key="network_density", score=0,
                    insight="No entities found in graph",
                    gap_note="Ingest documents to build entity network",
                    emoji="🕸️", raw_data={"node_count": 0},
                )

            # Step 2: Get top entities by degree (simpler query — no neighbor list)
            degree_query = (
                f"g.V().hasLabel('{label}').limit(100)"
                f".project('id','degree')"
                f".by(id())"
                f".by(bothE('RELATED_TO').count())"
                f".order().by('degree', desc).limit(20)"
            )
            degree_nodes = self._gremlin(degree_query, timeout=10)
            logger.info("Network Density: got %d degree results, sample: %s",
                        len(degree_nodes), json.dumps(degree_nodes[:2], default=str)[:500])

            # Count hub entities (degree > 10) and compute avg degree
            hub_count = 0
            total_degree = 0
            for node in degree_nodes:
                if not isinstance(node, dict):
                    continue
                degree = node.get("degree", 0)
                if isinstance(degree, dict):
                    degree = degree.get("@value", 0)
                d = int(degree)
                total_degree += d
                if d > 10:
                    hub_count += 1

            avg_degree = total_degree / max(len(degree_nodes), 1)

            # Step 3: Attempt clustering coefficient with neighbor data
            clustering_coeff = 0.0
            try:
                neighbor_query = (
                    f"g.V().hasLabel('{label}').limit(50)"
                    f".project('id','degree','neighbors')"
                    f".by(id())"
                    f".by(bothE('RELATED_TO').count())"
                    f".by(both('RELATED_TO').hasLabel('{label}').id().dedup().fold())"
                    f".order().by('degree', desc).limit(15)"
                )
                nodes_with_neighbors = self._gremlin(neighbor_query, timeout=10)
                if nodes_with_neighbors:
                    clustering_coeff = self._compute_clustering_coefficient(nodes_with_neighbors)
            except Exception as cc_exc:
                # Clustering coefficient is optional — estimate from degree stats
                logger.warning("Clustering coefficient query failed, estimating: %s", str(cc_exc)[:200])
                # Estimate: higher avg degree relative to node count = denser
                if node_count > 1:
                    clustering_coeff = min(avg_degree / max(node_count, 1) * 5, 1.0)

            hub_bonus = min(hub_count / 3.0, 1.0)
            score = _clamp(int(clustering_coeff * 50 + hub_bonus * 50))

            # Classify topology
            if clustering_coeff > 0.5 and hub_count >= 2:
                topology = "tight cluster"
            elif hub_count >= 1:
                topology = "hub-and-spoke"
            else:
                topology = "scattered"

            insight = f"Network topology: {topology} (clustering: {clustering_coeff:.2f}, {hub_count} hub(s), avg degree: {avg_degree:.1f})"
            gap_note = (
                "Disconnected entity clusters may represent unexplored connections"
                if clustering_coeff < 0.3
                else "Network structure is well-connected"
            )

            return IndicatorResult(
                name="Network Density",
                key="network_density",
                score=score,
                insight=insight,
                gap_note=gap_note,
                emoji="🕸️",
                raw_data={
                    "clustering_coeff": clustering_coeff,
                    "hub_count": hub_count,
                    "hub_bonus": hub_bonus,
                    "topology": topology,
                    "node_count": node_count,
                    "avg_degree": avg_degree,
                },
            )
        except Exception as exc:
            logger.error("compute_network_density failed for %s: %s", case_id, str(exc)[:300])
            return IndicatorResult(
                name="Network Density", key="network_density", score=0,
                insight="Unable to compute network density",
                gap_note="Neptune unavailable", emoji="🕸️",
                raw_data={"error": str(exc)[:200]},
            )

    def _compute_clustering_coefficient(self, nodes: list) -> float:
        """Approximate clustering coefficient from node neighbor lists."""
        if not nodes:
            return 0.0

        total_coeff = 0.0
        valid_nodes = 0

        for node in nodes:
            if not isinstance(node, dict):
                continue
            neighbors = node.get("neighbors", [])
            if isinstance(neighbors, dict) and "@value" in neighbors:
                neighbors = neighbors["@value"]
            if not isinstance(neighbors, list):
                continue
            k = len(neighbors)
            if k < 2:
                continue

            # Count edges between neighbors (triangles)
            neighbor_set = set(str(n.get("@value", n) if isinstance(n, dict) else n) for n in neighbors)
            triangles = 0
            for other_node in nodes:
                if not isinstance(other_node, dict):
                    continue
                other_id = other_node.get("id", "")
                if isinstance(other_id, dict):
                    other_id = other_id.get("@value", other_id)
                if str(other_id) not in neighbor_set:
                    continue
                other_neighbors = other_node.get("neighbors", [])
                if isinstance(other_neighbors, dict) and "@value" in other_neighbors:
                    other_neighbors = other_neighbors["@value"]
                if not isinstance(other_neighbors, list):
                    continue
                other_neighbor_set = set(
                    str(n.get("@value", n) if isinstance(n, dict) else n) for n in other_neighbors
                )
                triangles += len(neighbor_set & other_neighbor_set)

            possible = k * (k - 1)
            if possible > 0:
                total_coeff += triangles / possible
                valid_nodes += 1

        return total_coeff / max(valid_nodes, 1)

    # ------------------------------------------------------------------
    # Indicator 4: Temporal Coherence (Aurora)
    # ------------------------------------------------------------------

    def compute_temporal_coherence(self, case_id: str) -> IndicatorResult:
        """Query Aurora for date entities and analyze temporal patterns.

        Detects gaps > 90 days, clusters of 3+ events within 7-day windows.
        Score = sequence_score + cluster_score - gap_penalty, clamped 0-100.
        """
        try:
            # Query Neptune for date entities instead of Aurora
            label = f"Entity_{_escape(case_id)}"
            q = (
                f"g.V().hasLabel('{label}')"
                f".has('entity_type', 'date')"
                f".values('canonical_name')"
                f".limit(200)"
            )
            logger.info("Temporal Coherence: querying date entities for label %s", label)
            date_strings = [str(d) for d in self._gremlin(q, timeout=10) if d]
            logger.info("Temporal Coherence: found %d date strings", len(date_strings))
            dates = self._parse_dates(date_strings)

            if not dates:
                return IndicatorResult(
                    name="Temporal Coherence", key="temporal_coherence", score=0,
                    insight="No date entities found in case data",
                    gap_note="Ingest documents with date references to enable temporal analysis",
                    emoji="⏱️", raw_data={"date_count": 0},
                )

            dates.sort()

            # Sequence score: dates are parseable and form a sequence
            sequence_score = min(len(dates) * 5, 40)  # up to 40 points

            # Cluster detection: 3+ events within 7-day windows
            clusters = self._detect_temporal_clusters(dates, window_days=7, min_events=3)
            cluster_score = min(len(clusters) * 15, 40)  # up to 40 points

            # Gap penalty: gaps > 90 days
            gaps = self._detect_temporal_gaps(dates, gap_days=90)
            gap_penalty = min(len(gaps) * 10, 30)  # up to 30 points penalty

            raw_score = sequence_score + cluster_score - gap_penalty
            score = _clamp(int(raw_score))

            # Describe pattern
            if clusters and not gaps:
                pattern = "sequential with temporal clusters"
            elif gaps and not clusters:
                pattern = "anomalous gaps detected"
            elif clusters and gaps:
                pattern = "clustered activity with suspicious gaps"
            else:
                pattern = "sparse temporal data"

            insight = f"Temporal pattern: {pattern} ({len(dates)} dates, {len(clusters)} cluster(s), {len(gaps)} gap(s))"
            gap_note = (
                f"Time periods with no documented activity: {', '.join(g['description'] for g in gaps[:3])}"
                if gaps
                else "No suspicious temporal gaps detected"
            )

            return IndicatorResult(
                name="Temporal Coherence",
                key="temporal_coherence",
                score=score,
                insight=insight,
                gap_note=gap_note,
                emoji="⏱️",
                raw_data={
                    "date_count": len(dates),
                    "cluster_count": len(clusters),
                    "gap_count": len(gaps),
                    "sequence_score": sequence_score,
                    "cluster_score": cluster_score,
                    "gap_penalty": gap_penalty,
                },
            )
        except Exception as exc:
            logger.error("compute_temporal_coherence failed for %s: %s", case_id, str(exc)[:300])
            return IndicatorResult(
                name="Temporal Coherence", key="temporal_coherence", score=0,
                insight="Unable to compute temporal coherence",
                gap_note="Neptune graph query failed", emoji="⏱️",
                raw_data={"error": str(exc)[:300]},
            )

    @staticmethod
    def _parse_dates(date_strings: list) -> list:
        """Parse date strings into datetime objects. Skips unparseable strings."""
        from datetime import date as date_type
        parsed = []
        for s in date_strings:
            if not s:
                continue
            # Try ISO format: 2017-09-06
            m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
            if m:
                try:
                    parsed.append(date_type(int(m.group(1)), int(m.group(2)), int(m.group(3))))
                    continue
                except ValueError:
                    pass
            # Try US format: 4/28/2017 or Fri 4/28/2017
            m = re.match(r"(?:\w+\s+)?(\d{1,2})/(\d{1,2})/(\d{4})", s)
            if m:
                try:
                    parsed.append(date_type(int(m.group(3)), int(m.group(1)), int(m.group(2))))
                    continue
                except ValueError:
                    pass
        return parsed

    @staticmethod
    def _detect_temporal_clusters(dates: list, window_days: int = 7, min_events: int = 3) -> list:
        """Detect clusters of min_events+ events within window_days."""
        from datetime import timedelta
        if len(dates) < min_events:
            return []
        clusters = []
        window = timedelta(days=window_days)
        i = 0
        while i < len(dates):
            j = i
            while j < len(dates) and (dates[j] - dates[i]) <= window:
                j += 1
            if j - i >= min_events:
                clusters.append({
                    "start": dates[i].isoformat(),
                    "end": dates[j - 1].isoformat(),
                    "count": j - i,
                })
                i = j  # skip past this cluster
            else:
                i += 1
        return clusters

    @staticmethod
    def _detect_temporal_gaps(dates: list, gap_days: int = 90) -> list:
        """Detect gaps > gap_days between sequential dates."""
        from datetime import timedelta
        if len(dates) < 2:
            return []
        gaps = []
        threshold = timedelta(days=gap_days)
        for i in range(1, len(dates)):
            delta = dates[i] - dates[i - 1]
            if delta > threshold:
                gaps.append({
                    "from": dates[i - 1].isoformat(),
                    "to": dates[i].isoformat(),
                    "days": delta.days,
                    "description": f"{dates[i - 1].isoformat()} to {dates[i].isoformat()} ({delta.days} days)",
                })
        return gaps

    # ------------------------------------------------------------------
    # Indicator 5: Prosecution Readiness (existing services)
    # ------------------------------------------------------------------

    def compute_prosecution_readiness(self, case_id: str) -> IndicatorResult:
        """Leverage CaseAssessmentService + CaseWeaknessService.

        Score = clamp(int((covered / 7) * 80 + (20 if zero_critical else 0)), 0, 100).
        """
        try:
            assessment = self._case_assessment_svc.get_assessment(case_id)
            coverage = assessment.get("evidence_coverage", {})

            covered = sum(
                1 for v in coverage.values()
                if isinstance(v, dict) and v.get("status") == "covered"
            )

            weaknesses = self._case_weakness_svc.analyze_weaknesses(case_id)
            critical_count = sum(
                1 for w in weaknesses
                if hasattr(w, "severity") and str(w.severity.value) == "critical"
            )

            zero_critical = critical_count == 0
            score = _clamp(int((covered / 7) * 80 + (20 if zero_critical else 0)))

            # Find highest-priority missing category
            missing_categories = [
                k.replace("_", " ").title()
                for k, v in coverage.items()
                if isinstance(v, dict) and v.get("status") == "gap"
            ]

            insight = f"{covered}/7 evidence categories covered, {critical_count} critical weakness(es)"
            gap_note = (
                f"Missing: {', '.join(missing_categories[:3])}"
                if missing_categories
                else "All evidence categories covered"
            )

            return IndicatorResult(
                name="Prosecution Readiness",
                key="prosecution_readiness",
                score=score,
                insight=insight,
                gap_note=gap_note,
                emoji="⚖️",
                raw_data={
                    "covered_categories": covered,
                    "total_categories": 7,
                    "critical_weakness_count": critical_count,
                    "missing_categories": missing_categories,
                    "category_details": {
                        k: {"count": v.get("count", 0), "status": v.get("status", "gap")}
                        for k, v in coverage.items()
                        if isinstance(v, dict)
                    },
                },
            )
        except Exception as exc:
            logger.error("compute_prosecution_readiness failed for %s: %s", case_id, str(exc)[:200])
            return IndicatorResult(
                name="Prosecution Readiness", key="prosecution_readiness", score=0,
                insight="Unable to compute prosecution readiness",
                gap_note="Assessment services unavailable", emoji="⚖️",
                raw_data={"error": str(exc)[:200]},
            )

    # ------------------------------------------------------------------
    # Helper: extract count from Gremlin result
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_count(result: list) -> int:
        """Extract a count value from a Gremlin query result."""
        if not result:
            return 0
        val = result[0]
        if isinstance(val, dict):
            val = val.get("@value", 0)
        return int(val)

    # ------------------------------------------------------------------
    # Strategic Assessment (Bedrock) — Task 4.1
    # ------------------------------------------------------------------

    def generate_strategic_assessment(
        self,
        case_id: str,
        indicators: List[IndicatorResult],
        viability_score: int,
        leads: list,
    ) -> dict:
        """Generate structured strategic assessment via Bedrock.

        Returns dict with keys: bluf, key_finding, critical_gap, next_action.
        Falls back to deterministic template when Bedrock is unavailable.
        """
        if not self._bedrock:
            return self._fallback_strategic_assessment(indicators, viability_score)

        indicator_summary = "\n".join(
            f"- {ind.name} ({ind.emoji}): {ind.score}/100 — {ind.insight}. Gap: {ind.gap_note}"
            for ind in indicators
        )
        lead_summary = "\n".join(
            f"- {l.entity_name} ({l.entity_type}): priority {l.lead_priority_score}"
            for l in leads[:10]
        ) if leads else "No leads available."

        # Gather top hub entities from the graph for richer context
        hub_entities = ""
        try:
            label = f"Entity_{case_id}"
            hub_query = (
                f"g.V().hasLabel('{_escape(label)}').limit(500)"
                f".project('name','type','degree')"
                f".by('canonical_name').by('entity_type')"
                f".by(bothE('RELATED_TO').count())"
            )
            hub_results = self._gremlin(hub_query, timeout=5)
            hubs = []
            for r in hub_results:
                if isinstance(r, dict):
                    name = r.get("name", "")
                    etype = r.get("type", "")
                    degree = r.get("degree", 0)
                    if isinstance(degree, dict):
                        degree = degree.get("@value", 0)
                    if name and int(degree) > 5:
                        hubs.append({"name": name, "type": etype, "degree": int(degree)})
            hubs.sort(key=lambda x: x["degree"], reverse=True)
            if hubs:
                hub_entities = "Top connected entities in the intelligence graph:\n" + "\n".join(
                    f"- {h['name']} ({h['type']}): {h['degree']} connections"
                    for h in hubs[:15]
                )
        except Exception:
            hub_entities = "Entity graph data unavailable."

        verdict = self.classify_verdict(viability_score)

        prompt = (
            "You are a senior investigative intelligence analyst writing a case status briefing "
            "for a supervising attorney or CIO. Write like a real analyst — specific names, "
            "specific connections, specific gaps. Do not restate scores or metrics.\n\n"
            f"Case Viability: {viability_score}/100 ({verdict})\n\n"
            f"Intelligence Indicators:\n{indicator_summary}\n\n"
            f"{hub_entities}\n\n"
            f"Top Investigative Leads:\n{lead_summary}\n\n"
            "Provide a structured assessment in JSON with these keys:\n"
            '- "bluf": 3-4 sentences. Name the key subjects, describe the network structure, '
            "state the investigation's current posture. Write as if briefing someone who has never seen the case.\n"
            '- "key_finding": The single most important discovery from the evidence. '
            "Name specific entities and their relationships.\n"
            '- "critical_gap": What evidence is missing that would make or break the case. '
            "Be specific about what types of records are needed and for which entities.\n"
            '- "next_action": Object with "text" (specific actionable step naming entities), '
            '"action_type" (investigative_search, hypothesis_test, or entity_drilldown), '
            'and "action_target" (entity name)\n\n'
            "Return ONLY the JSON object. No markdown."
        )

        try:
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1500,
                "system": self.SENIOR_ANALYST_PERSONA,
                "messages": [{"role": "user", "content": prompt}],
            })
            resp = self._bedrock.invoke_model(modelId=BEDROCK_MODEL_ID, body=body)
            text = json.loads(resp["body"].read()).get("content", [{}])[0].get("text", "")

            # Parse JSON from response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                parsed = json.loads(text[start:end])
                # Validate required keys
                result = {
                    "bluf": str(parsed.get("bluf", ""))[:500],
                    "key_finding": str(parsed.get("key_finding", ""))[:500],
                    "critical_gap": str(parsed.get("critical_gap", ""))[:500],
                    "next_action": parsed.get("next_action", {
                        "text": "Review top investigative leads",
                        "action_type": "investigative_search",
                        "action_target": leads[0].entity_name if leads else case_id,
                    }),
                }
                # Ensure next_action has required keys
                if not isinstance(result["next_action"], dict):
                    result["next_action"] = {
                        "text": str(result["next_action"]),
                        "action_type": "investigative_search",
                        "action_target": leads[0].entity_name if leads else case_id,
                    }
                return result
        except Exception as exc:
            logger.error("Bedrock strategic assessment failed for %s: %s", case_id, str(exc)[:200])

        return self._fallback_strategic_assessment(indicators, viability_score)

    @staticmethod
    def _fallback_strategic_assessment(
        indicators: List[IndicatorResult], viability_score: int,
    ) -> dict:
        """Deterministic fallback when Bedrock is unavailable."""
        verdict = CommandCenterEngine.classify_verdict(viability_score)

        # Find weakest and strongest indicators
        sorted_inds = sorted(indicators, key=lambda i: i.score) if indicators else []
        weakest = sorted_inds[0] if sorted_inds else None
        strongest = sorted_inds[-1] if sorted_inds else None

        bluf = f"Case viability score is {viability_score}/100 ({verdict})."
        if strongest:
            bluf += f" Strongest signal: {strongest.name} at {strongest.score}/100."

        key_finding = (
            f"{strongest.name} indicates {strongest.insight}"
            if strongest
            else "Insufficient data for key finding determination."
        )
        critical_gap = (
            f"{weakest.name}: {weakest.gap_note}"
            if weakest
            else "Unable to determine critical gaps."
        )
        next_action = {
            "text": f"Investigate {weakest.name.lower()} gap: {weakest.gap_note}" if weakest else "Review case data",
            "action_type": "investigative_search",
            "action_target": weakest.key if weakest else "case_overview",
        }

        return {
            "bluf": bluf,
            "key_finding": key_finding,
            "critical_gap": critical_gap,
            "next_action": next_action,
        }

    # ------------------------------------------------------------------
    # Threat Threads (Bedrock) — Task 4.2
    # ------------------------------------------------------------------

    def generate_threat_threads(
        self,
        case_id: str,
        leads: list,
        indicators: List[IndicatorResult],
    ) -> list:
        """Generate 2-3 investigation thread narratives via Bedrock.

        Falls back to deterministic threads from top leads when Bedrock unavailable.
        """
        if not self._bedrock or not leads:
            return self._fallback_threat_threads(leads)

        lead_summary = "\n".join(
            f"- {l.entity_name} ({l.entity_type}): priority {l.lead_priority_score}, "
            f"justification: {l.ai_justification[:200]}"
            for l in leads[:10]
        )
        indicator_summary = "\n".join(
            f"- {ind.name}: {ind.score}/100"
            for ind in indicators
        )

        prompt = (
            f"Based on these investigative leads for case {case_id}:\n{lead_summary}\n\n"
            f"Intelligence indicators:\n{indicator_summary}\n\n"
            "Generate 2-3 investigation thread narratives. Each thread should group "
            "connected entities into a coherent investigation narrative.\n\n"
            "Return a JSON array where each element has:\n"
            '- "title": Thread title\n'
            '- "narrative": Mini-narrative description (2-3 sentences)\n'
            '- "confidence": 0-100 confidence score\n'
            '- "primary_entity": Main entity name for drill-down\n'
            '- "evidence_chain": Array of {entity, connection, target} objects\n\n'
            "Return ONLY the JSON array."
        )

        try:
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "system": self.SENIOR_ANALYST_PERSONA,
                "messages": [{"role": "user", "content": prompt}],
            })
            resp = self._bedrock.invoke_model(modelId=BEDROCK_MODEL_ID, body=body)
            text = json.loads(resp["body"].read()).get("content", [{}])[0].get("text", "")

            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                parsed = json.loads(text[start:end])
                threads = []
                for item in parsed[:3]:
                    if not isinstance(item, dict):
                        continue
                    threads.append({
                        "title": str(item.get("title", "Investigation Thread")),
                        "narrative": str(item.get("narrative", "")),
                        "confidence": _clamp(int(item.get("confidence", 50))),
                        "primary_entity": str(item.get("primary_entity", "")),
                        "evidence_chain": item.get("evidence_chain", []),
                    })
                if threads:
                    return threads
        except Exception as exc:
            logger.error("Bedrock threat threads failed for %s: %s", case_id, str(exc)[:200])

        return self._fallback_threat_threads(leads)

    @staticmethod
    def _fallback_threat_threads(leads: list) -> list:
        """Deterministic fallback threads from top leads."""
        threads = []
        for lead in leads[:2]:
            threads.append({
                "title": f"{lead.entity_name} Investigation Thread",
                "narrative": (
                    f"{lead.entity_name} ({lead.entity_type}) has a priority score of "
                    f"{lead.lead_priority_score}. {lead.ai_justification[:200]}"
                ),
                "confidence": lead.lead_priority_score,
                "primary_entity": lead.entity_name,
                "evidence_chain": [
                    {
                        "entity": lead.entity_name,
                        "connection": "high_priority_lead",
                        "target": "case_network",
                    }
                ],
            })
        return threads

    # ------------------------------------------------------------------
    # Main orchestration — Task 4.3
    # ------------------------------------------------------------------

    def compute(self, case_id: str, bypass_cache: bool = False, graph_case_id: str = "") -> dict:
        """Main entry point. Returns full Command Center payload.

        1. Check cache (15 min TTL)
        2. Compute all 5 indicators (each wrapped in try/except)
        3. Compute viability score and verdict
        4. Get leads from InvestigatorAIEngine
        5. Generate strategic assessment and threat threads
        6. Cache result

        Args:
            case_id: Case ID for Aurora/OpenSearch queries.
            bypass_cache: Skip cache check if True.
            graph_case_id: Optional separate case ID for Neptune graph queries.
                           Falls back to case_id if not provided.
        """
        g_case_id = graph_case_id or case_id  # Neptune may use a different case ID
        logger.info("CommandCenter.compute: case_id=%s, graph_case_id=%s, g_case_id=%s", case_id, graph_case_id, g_case_id)
        # --- Cache check ---
        if not bypass_cache:
            cached = self._check_cache(case_id)
            if cached is not None:
                cached["cache_hit"] = True
                return cached

        # --- Compute indicators ---
        # Neptune-based indicators use g_case_id, Aurora-based use case_id
        indicator_calls = [
            ("compute_signal_strength", g_case_id),      # Neptune
            ("compute_corroboration_depth", g_case_id),   # Neptune (entity source_document_refs)
            ("compute_network_density", g_case_id),       # Neptune
            ("compute_temporal_coherence", g_case_id),    # Neptune (date entities)
            ("compute_prosecution_readiness", case_id),   # Existing services
        ]

        indicators: List[IndicatorResult] = []
        for method_name, cid in indicator_calls:
            method = getattr(self, method_name)
            try:
                result = method(cid)
                indicators.append(result)
            except Exception as exc:
                logger.error("Indicator %s failed: %s", method_name, str(exc)[:200])
                name = method_name.replace("compute_", "").replace("_", " ").title()
                key = method_name.replace("compute_", "")
                indicators.append(IndicatorResult(
                    name=name, key=key, score=0,
                    insight=f"Computation failed: {str(exc)[:100]}",
                    gap_note="Data source unavailable",
                    emoji="❓", raw_data={"error": str(exc)[:200]},
                ))

        # --- Viability score and verdict ---
        viability_score = self.compute_viability_score(indicators)
        verdict = self.classify_verdict(viability_score)

        # --- Get leads ---
        leads = []
        try:
            leads = self._investigator_engine.get_investigative_leads(case_id)
        except Exception as exc:
            logger.error("Failed to get leads for %s: %s", case_id, str(exc)[:200])

        # --- Generate verdict reasoning ---
        verdict_reasoning = self._generate_verdict_reasoning(indicators, viability_score, verdict)

        # --- Strategic assessment ---
        strategic_assessment = self.generate_strategic_assessment(
            case_id, indicators, viability_score, leads
        )

        # --- Threat threads ---
        threat_threads = self.generate_threat_threads(case_id, leads, indicators)

        # --- Build payload ---
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "viability_score": viability_score,
            "verdict": verdict,
            "verdict_reasoning": verdict_reasoning,
            "indicators": [
                {
                    "name": ind.name,
                    "key": ind.key,
                    "score": ind.score,
                    "insight": ind.insight,
                    "gap_note": ind.gap_note,
                    "emoji": ind.emoji,
                }
                for ind in indicators
            ],
            "strategic_assessment": strategic_assessment,
            "threat_threads": threat_threads,
            "computed_at": now,
            "cache_hit": False,
        }

        # --- Cache write ---
        self._write_cache(case_id, payload)

        return payload

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _check_cache(self, case_id: str) -> Optional[dict]:
        """Check command_center_cache for a fresh result (< 15 min)."""
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT command_center_data, cached_at FROM command_center_cache WHERE case_file_id = %s",
                    (case_id,),
                )
                row = cur.fetchone()
                if row:
                    data, cached_at = row
                    age = (datetime.now(timezone.utc) - cached_at).total_seconds()
                    if age < CACHE_TTL_SECONDS:
                        logger.info("Cache hit for case %s (age %.0fs)", case_id, age)
                        if isinstance(data, str):
                            return json.loads(data)
                        return data
                    logger.info("Cache stale for case %s (age %.0fs)", case_id, age)
        except Exception as exc:
            logger.warning("Cache check failed for %s: %s", case_id, str(exc)[:200])
        return None

    def _write_cache(self, case_id: str, payload: dict) -> None:
        """Write result to command_center_cache table."""
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "INSERT INTO command_center_cache (case_file_id, cached_at, command_center_data) "
                    "VALUES (%s, now(), %s) "
                    "ON CONFLICT (case_file_id) DO UPDATE "
                    "SET cached_at = now(), command_center_data = EXCLUDED.command_center_data",
                    (case_id, json.dumps(payload, default=str)),
                )
            logger.info("Cached command center result for case %s", case_id)
        except Exception as exc:
            logger.error("Cache write failed for %s: %s", case_id, str(exc)[:200])

    # ------------------------------------------------------------------
    # Verdict reasoning
    # ------------------------------------------------------------------

    def _generate_verdict_reasoning(
        self, indicators: List[IndicatorResult], viability_score: int, verdict: str,
    ) -> str:
        """Generate a brief reasoning string for the verdict."""
        sorted_inds = sorted(indicators, key=lambda i: i.score, reverse=True)
        top = sorted_inds[0] if sorted_inds else None
        bottom = sorted_inds[-1] if sorted_inds else None

        parts = [f"Viability score {viability_score}/100 ({verdict})."]
        if top:
            parts.append(f"Strongest: {top.name} ({top.score}/100).")
        if bottom and bottom != top:
            parts.append(f"Weakest: {bottom.name} ({bottom.score}/100).")
        return " ".join(parts)
