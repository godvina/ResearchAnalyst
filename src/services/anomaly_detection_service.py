"""Anomaly Detection Service — statistical anomaly detection across five dimensions.

Computes anomalies across temporal, network, frequency, co-absence, and volume
dimensions using z-scores, structural hole detection, frequency distribution
outliers, co-absence analysis, and entity type ratio comparisons.

No LLM dependency — pure algorithmic. Uses Neptune HTTP API (POST /gremlin)
for graph queries and Aurora PostgreSQL for relational queries.
"""

import json
import logging
import math
import os
import ssl
import urllib.request
import urllib.error
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Feature flag: when "false", Neptune-dependent detectors are skipped
_NEPTUNE_ENABLED = os.environ.get("NEPTUNE_ENABLED", "true") == "true"

ALL_DIMENSIONS = ["temporal", "network", "frequency", "co_absence", "volume"]

# Expected entity type distribution ratios (baseline)
EXPECTED_TYPE_RATIOS: Dict[str, float] = {
    "PERSON": 0.35,
    "ORGANIZATION": 0.25,
    "LOCATION": 0.20,
    "EVENT": 0.10,
    "OTHER": 0.10,
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Anomaly:
    """A statistical anomaly detected by one of the five dimension detectors."""

    anomaly_id: str          # UUID
    anomaly_type: str        # One of: temporal, network, frequency, co_absence, volume
    description: str         # Concise factual statement (no narrative)
    data_points: List[float] # Values for sparkline rendering
    severity: float          # 0.0–1.0 (based on z-score magnitude)
    entities: List[str]      # Affected entity names
    metadata: dict           # Type-specific details

    def to_dict(self) -> dict:
        return {
            "anomaly_id": self.anomaly_id,
            "anomaly_type": self.anomaly_type,
            "description": self.description,
            "data_points": list(self.data_points),
            "severity": self.severity,
            "entities": list(self.entities),
            "metadata": dict(self.metadata),
        }


@dataclass
class AnomalyReport:
    """Report containing all detected anomalies and dimension status."""

    case_id: str
    anomalies: List[Anomaly]
    computed_dimensions: List[str]   # Which dimensions succeeded
    failed_dimensions: List[str]     # Which dimensions failed
    computed_at: str                  # ISO timestamp

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "anomalies": [a.to_dict() for a in self.anomalies],
            "computed_dimensions": list(self.computed_dimensions),
            "failed_dimensions": list(self.failed_dimensions),
            "computed_at": self.computed_at,
        }


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------

def _mean(values: List[float]) -> float:
    """Compute arithmetic mean. Returns 0.0 for empty list."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def _std_dev(values: List[float], mean_val: float) -> float:
    """Compute population standard deviation. Returns 0.0 for fewer than 2 values."""
    if len(values) < 2:
        return 0.0
    variance = sum((v - mean_val) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


def _z_score(value: float, mean_val: float, std_val: float) -> float:
    """Compute z-score. Returns 0.0 if std_dev is 0."""
    if std_val == 0.0:
        return 0.0
    return (value - mean_val) / std_val


# ---------------------------------------------------------------------------
# Neptune HTTP API helper
# ---------------------------------------------------------------------------

def _gremlin_query(query: str, neptune_endpoint: str, neptune_port: str) -> list:
    """Execute a Gremlin query via Neptune HTTP API and return results."""
    if not neptune_endpoint:
        return []
    url = f"https://{neptune_endpoint}:{neptune_port}/gremlin"
    data = json.dumps({"gremlin": query}).encode("utf-8")
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            result = body.get("result", {}).get("data", {})
            if isinstance(result, dict) and "@value" in result:
                return _parse_graphson(result["@value"])
            if isinstance(result, list):
                return _parse_graphson(result)
            return [result] if result else []
    except Exception as e:
        logger.error("Neptune query error: %s | query: %s", str(e)[:200], query[:200])
        return []


def _parse_graphson(items: list) -> list:
    """Parse GraphSON typed values into plain Python objects."""
    return [_parse_graphson_value(item) for item in items]


def _parse_graphson_value(val):
    """Recursively parse a single GraphSON value."""
    if not isinstance(val, dict):
        return val
    gtype = val.get("@type", "")
    gval = val.get("@value")
    if gtype == "g:Map" and isinstance(gval, list):
        d = {}
        for i in range(0, len(gval) - 1, 2):
            k = _parse_graphson_value(gval[i])
            v = _parse_graphson_value(gval[i + 1])
            d[k] = v
        return d
    if gtype in ("g:Int64", "g:Int32", "g:Double", "g:Float"):
        return gval
    if gtype == "g:List" and isinstance(gval, list):
        return [_parse_graphson_value(v) for v in gval]
    if "@value" in val:
        return _parse_graphson_value(gval)
    return val


def _escape(s: str) -> str:
    """Escape a string for Gremlin query embedding."""
    return s.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')


def _entity_label(case_id: str) -> str:
    return f"Entity_{case_id}"


# ---------------------------------------------------------------------------
# Anomaly Detection Service
# ---------------------------------------------------------------------------

class AnomalyDetectionService:
    """Detects statistical anomalies across five dimensions.

    Dimensions: temporal, network, frequency, co_absence, volume.
    Each detector runs independently; failures in one do not block others.
    """

    def __init__(
        self,
        aurora_cm: Any,
        neptune_endpoint: str = "",
        neptune_port: str = "8182",
    ) -> None:
        self._aurora = aurora_cm
        self._neptune_endpoint = neptune_endpoint
        self._neptune_port = neptune_port

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_anomalies(self, case_id: str, time_budget: float = 20.0) -> AnomalyReport:
        """Run all five anomaly detectors and return an AnomalyReport.

        Each detector runs independently with its own try/except.
        Failures are recorded in failed_dimensions; successes in computed_dimensions.
        Stops processing if time_budget (seconds) is exceeded.
        """
        import time as _time
        start = _time.time()
        all_anomalies: List[Anomaly] = []
        computed: List[str] = []
        failed: List[str] = []
        skipped: List[str] = []

        detectors = [
            ("temporal", self._detect_temporal_anomalies),
            ("frequency", self._detect_frequency_anomalies),
            ("volume", self._detect_volume_anomalies),
            ("network", self._detect_network_anomalies),
            ("co_absence", self._detect_coabsence_anomalies),
        ]

        # Skip Neptune-dependent detectors when Neptune is disabled
        if not _NEPTUNE_ENABLED:
            detectors = [
                (dim, det) for dim, det in detectors
                if dim not in ("network", "co_absence")
            ]

        for dimension, detector in detectors:
            elapsed = _time.time() - start
            if elapsed > time_budget:
                skipped.append(dimension)
                logger.warning(
                    "Anomaly detector '%s' skipped for case %s — time budget %.1fs exceeded (%.1fs elapsed)",
                    dimension, case_id, time_budget, elapsed,
                )
                continue
            try:
                anomalies = detector(case_id)
                all_anomalies.extend(anomalies)
                computed.append(dimension)
            except Exception as exc:
                logger.error(
                    "Anomaly detector '%s' failed for case %s: %s",
                    dimension, case_id, str(exc)[:200],
                )
                failed.append(dimension)

        return AnomalyReport(
            case_id=case_id,
            anomalies=all_anomalies,
            computed_dimensions=computed,
            failed_dimensions=failed + skipped,
            computed_at=datetime.now(timezone.utc).isoformat(),
        )

    # ------------------------------------------------------------------
    # Temporal anomaly detector
    # ------------------------------------------------------------------

    def _detect_temporal_anomalies(self, case_id: str) -> List[Anomaly]:
        """Query Aurora for document counts by month. Compute z-scores.
        Flag periods where |z| > 2.0. Return data_points for sparkline.
        """
        rows: List[tuple] = []
        with self._aurora.cursor() as cur:
            cur.execute(
                "SELECT TO_CHAR(indexed_at, 'YYYY-MM') AS period, COUNT(*) "
                "FROM documents WHERE case_file_id = %s "
                "GROUP BY period ORDER BY period",
                (case_id,),
            )
            rows = cur.fetchall()

        if len(rows) < 3:
            return []

        periods = [r[0] for r in rows]
        counts = [float(r[1]) for r in rows]

        mean_val = _mean(counts)
        std_val = _std_dev(counts, mean_val)

        if std_val == 0.0:
            return []

        anomalies: List[Anomaly] = []
        for i, (period, count) in enumerate(zip(periods, counts)):
            z = _z_score(count, mean_val, std_val)
            if abs(z) > 2.0:
                direction = "increased" if z > 0 else "decreased"
                # Find adjacent period for comparison
                if i > 0:
                    prev_period = periods[i - 1]
                    prev_count = counts[i - 1]
                    if prev_count > 0:
                        pct_change = abs((count - prev_count) / prev_count) * 100
                    else:
                        pct_change = 100.0
                    desc = (
                        f"Unusual {'spike' if z > 0 else 'drop'} in activity between "
                        f"{prev_period} and {period} — {pct_change:.0f}% "
                        f"{'increase' if z > 0 else 'decrease'} may indicate a triggering event"
                    )
                else:
                    desc = (
                        f"Unusual activity in {period}: {int(count)} documents "
                        f"vs average of {mean_val:.0f} — may indicate a triggering event"
                    )

                anomalies.append(Anomaly(
                    anomaly_id=str(uuid.uuid4()),
                    anomaly_type="temporal",
                    description=desc,
                    data_points=counts,
                    severity=min(1.0, abs(z) / 5.0),
                    entities=[],
                    metadata={
                        "period": period,
                        "count": int(count),
                        "z_score": round(z, 2),
                        "baseline_mean": round(mean_val, 2),
                        "baseline_std": round(std_val, 2),
                    },
                ))

        return anomalies

    # ------------------------------------------------------------------
    # Network anomaly detector
    # ------------------------------------------------------------------

    def _detect_network_anomalies(self, case_id: str) -> List[Anomaly]:
        """Query Neptune for entities bridging disconnected clusters (structural holes).

        An entity is a structural hole if it connects to 2+ groups of entities
        that have no direct connections to each other.
        """
        label = _entity_label(case_id)

        # Get entities with their neighbors
        query = (
            f"g.V().hasLabel('{_escape(label)}').limit(200)"
            f".project('name','neighbors')"
            f".by('canonical_name')"
            f".by(both('RELATED_TO').hasLabel('{_escape(label)}')"
            f".values('canonical_name').dedup().fold())"
        )
        results = _gremlin_query(query, self._neptune_endpoint, self._neptune_port)
        if not results:
            return []

        # Build adjacency map: entity -> set of neighbors
        adjacency: Dict[str, set] = {}
        for r in results:
            if not isinstance(r, dict):
                continue
            name = r.get("name", "")
            neighbors = r.get("neighbors", [])
            if isinstance(neighbors, dict) and "@value" in neighbors:
                neighbors = neighbors["@value"]
            if not isinstance(neighbors, list):
                neighbors = []
            adjacency[name] = {str(n) for n in neighbors}

        anomalies: List[Anomaly] = []

        for entity, neighbors in adjacency.items():
            if len(neighbors) < 2:
                continue

            # Check if neighbors form disconnected clusters
            neighbor_list = list(neighbors)
            clusters = self._find_disconnected_clusters(neighbor_list, adjacency)

            if len(clusters) >= 2:
                cluster_sizes = [len(c) for c in clusters]
                anomalies.append(Anomaly(
                    anomaly_id=str(uuid.uuid4()),
                    anomaly_type="network",
                    description=(
                        f"{entity} connects {len(clusters)} separate groups who have no other links — "
                        f"potential intermediary or cutout"
                    ),
                    data_points=[float(s) for s in cluster_sizes],
                    severity=min(1.0, len(clusters) / 5.0),
                    entities=[entity],
                    metadata={
                        "cluster_count": len(clusters),
                        "cluster_sizes": cluster_sizes,
                        "clusters": [list(c) for c in clusters],
                    },
                ))

        return anomalies

    @staticmethod
    def _find_disconnected_clusters(
        neighbors: List[str], adjacency: Dict[str, set]
    ) -> List[set]:
        """Find disconnected clusters among a set of neighbor entities.

        Two neighbors are in the same cluster if they are directly connected
        (i.e., one appears in the other's adjacency set). Returns a list of
        sets, each set being a connected component among the neighbors.
        """
        if not neighbors:
            return []

        # Build local adjacency among neighbors only
        neighbor_set = set(neighbors)
        visited: set = set()
        clusters: List[set] = []

        for node in neighbors:
            if node in visited:
                continue
            # BFS to find connected component
            cluster: set = set()
            queue = [node]
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                cluster.add(current)
                # Check which other neighbors are connected to current
                current_neighbors = adjacency.get(current, set())
                for other in neighbor_set:
                    if other not in visited and other in current_neighbors:
                        queue.append(other)
            clusters.append(cluster)

        return clusters

    # ------------------------------------------------------------------
    # Frequency anomaly detector
    # ------------------------------------------------------------------

    def _detect_frequency_anomalies(self, case_id: str) -> List[Anomaly]:
        """Query Aurora for entity occurrence counts.
        Flag entities where count > mean + 2*std_dev.
        """
        rows: List[tuple] = []
        with self._aurora.cursor() as cur:
            cur.execute(
                "SELECT canonical_name, entity_type, occurrence_count "
                "FROM entities WHERE case_file_id = %s "
                "ORDER BY occurrence_count DESC",
                (case_id,),
            )
            rows = cur.fetchall()

        if len(rows) < 2:
            return []

        names = [r[0] for r in rows]
        types = [r[1] for r in rows]
        counts = [float(r[2]) for r in rows]

        mean_val = _mean(counts)
        std_val = _std_dev(counts, mean_val)

        if std_val == 0.0:
            return []

        threshold = mean_val + 2.0 * std_val
        anomalies: List[Anomaly] = []

        for name, etype, count in zip(names, types, counts):
            if count > threshold:
                z = _z_score(count, mean_val, std_val)
                anomalies.append(Anomaly(
                    anomaly_id=str(uuid.uuid4()),
                    anomaly_type="frequency",
                    description=(
                        f"{name} ({etype}) is mentioned {int(count)} times — far more than typical "
                        f"(average: {mean_val:.0f}) — possible central figure or key subject"
                    ),
                    data_points=counts,
                    severity=min(1.0, z / 5.0),
                    entities=[name],
                    metadata={
                        "entity_name": name,
                        "entity_type": etype,
                        "count": int(count),
                        "mean": round(mean_val, 2),
                        "std_dev": round(std_val, 2),
                        "z_score": round(z, 2),
                        "threshold": round(threshold, 2),
                    },
                ))

        return anomalies

    # ------------------------------------------------------------------
    # Co-absence anomaly detector
    # ------------------------------------------------------------------

    def _detect_coabsence_anomalies(self, case_id: str) -> List[Anomaly]:
        """Query Neptune for entity pairs that co-occur in most documents
        but are absent from specific sources.

        Identifies entity sets that appear together in documents from all
        sources except one, flagging the missing source.
        """
        label = _entity_label(case_id)

        # Get entity co-occurrence with source documents
        query = (
            f"g.V().hasLabel('{_escape(label)}').limit(100)"
            f".project('name','docs')"
            f".by('canonical_name')"
            f".by(both('MENTIONED_IN').hasLabel('Document_{_escape(case_id)}')"
            f".project('doc_id','source')"
            f".by(id())"
            f".by(coalesce(values('source'), constant('unknown')))"
            f".fold())"
        )
        results = _gremlin_query(query, self._neptune_endpoint, self._neptune_port)
        if not results:
            return []

        # Build entity -> set of sources mapping
        entity_sources: Dict[str, set] = {}
        for r in results:
            if not isinstance(r, dict):
                continue
            name = r.get("name", "")
            docs = r.get("docs", [])
            if isinstance(docs, dict) and "@value" in docs:
                docs = docs["@value"]
            if not isinstance(docs, list):
                docs = []
            sources = set()
            for doc in docs:
                if isinstance(doc, dict):
                    src = doc.get("source", "unknown")
                    sources.add(str(src))
            if sources:
                entity_sources[name] = sources

        if not entity_sources:
            return []

        # Collect all sources across the case
        all_sources = set()
        for sources in entity_sources.values():
            all_sources.update(sources)

        if len(all_sources) < 2:
            return []

        anomalies: List[Anomaly] = []
        checked_pairs: set = set()

        # Check entity pairs for co-absence patterns
        entity_names = list(entity_sources.keys())
        for i in range(len(entity_names)):
            for j in range(i + 1, min(len(entity_names), i + 50)):
                e1, e2 = entity_names[i], entity_names[j]
                pair_key = frozenset([e1, e2])
                if pair_key in checked_pairs:
                    continue
                checked_pairs.add(pair_key)

                sources_e1 = entity_sources[e1]
                sources_e2 = entity_sources[e2]

                # Both entities present in most sources
                shared_sources = sources_e1 & sources_e2
                missing_sources = all_sources - shared_sources

                # Flag if they co-occur in most sources but are absent from 1-2
                if (
                    len(shared_sources) >= 2
                    and 0 < len(missing_sources) <= 2
                    and len(shared_sources) > len(missing_sources)
                ):
                    missing_list = sorted(missing_sources)
                    anomalies.append(Anomaly(
                        anomaly_id=str(uuid.uuid4()),
                        anomaly_type="co_absence",
                        description=(
                            f"{e1} and {e2} appear together in {len(shared_sources)} sources "
                            f"but are missing from {', '.join(missing_list)} — "
                            f"possible deliberate omission or gap in evidence"
                        ),
                        data_points=[
                            float(len(shared_sources)),
                            float(len(missing_sources)),
                        ],
                        severity=min(
                            1.0,
                            len(shared_sources) / max(len(all_sources), 1),
                        ),
                        entities=[e1, e2],
                        metadata={
                            "shared_sources": sorted(shared_sources),
                            "missing_sources": missing_list,
                            "total_sources": len(all_sources),
                        },
                    ))

        return anomalies

    # ------------------------------------------------------------------
    # Volume anomaly detector
    # ------------------------------------------------------------------

    def _detect_volume_anomalies(self, case_id: str) -> List[Anomaly]:
        """Query Aurora for entity type ratios (person/org/location/event).
        Flag significant deviations from expected distribution.
        """
        rows: List[tuple] = []
        with self._aurora.cursor() as cur:
            cur.execute(
                "SELECT entity_type, COUNT(*) "
                "FROM entities WHERE case_file_id = %s "
                "GROUP BY entity_type",
                (case_id,),
            )
            rows = cur.fetchall()

        if not rows:
            return []

        # Build actual type counts
        type_counts: Dict[str, int] = {}
        total = 0
        for etype, count in rows:
            normalized = str(etype).upper()
            type_counts[normalized] = int(count)
            total += int(count)

        if total == 0:
            return []

        # Compute actual ratios
        actual_ratios: Dict[str, float] = {
            t: c / total for t, c in type_counts.items()
        }

        # Compare against expected ratios
        # Collect all deviations to compute std_dev of deviations
        deviations: List[float] = []
        type_deviations: Dict[str, float] = {}

        for etype, expected_ratio in EXPECTED_TYPE_RATIOS.items():
            actual_ratio = actual_ratios.get(etype, 0.0)
            deviation = actual_ratio - expected_ratio
            deviations.append(deviation)
            type_deviations[etype] = deviation

        # Also check for types not in expected distribution
        for etype in actual_ratios:
            if etype not in EXPECTED_TYPE_RATIOS:
                type_deviations[etype] = actual_ratios[etype]
                deviations.append(actual_ratios[etype])

        if not deviations:
            return []

        mean_dev = _mean(deviations)
        std_dev = _std_dev(deviations, mean_dev)

        if std_dev == 0.0:
            return []

        anomalies: List[Anomaly] = []
        data_points = [float(type_counts.get(t, 0)) for t in EXPECTED_TYPE_RATIOS]

        for etype, deviation in type_deviations.items():
            z = _z_score(deviation, mean_dev, std_dev)
            if abs(z) > 2.0:
                expected = EXPECTED_TYPE_RATIOS.get(etype, 0.0)
                actual = actual_ratios.get(etype, 0.0)
                anomalies.append(Anomaly(
                    anomaly_id=str(uuid.uuid4()),
                    anomaly_type="volume",
                    description=(
                        f"Unusually high proportion of {etype} entities — "
                        f"{actual:.0%} vs expected {expected:.0%} — "
                        f"may indicate focus area or data collection bias"
                    ),
                    data_points=data_points,
                    severity=min(1.0, abs(z) / 5.0),
                    entities=[],
                    metadata={
                        "entity_type": etype,
                        "actual_ratio": round(actual, 4),
                        "expected_ratio": round(expected, 4),
                        "actual_count": type_counts.get(etype, 0),
                        "total_entities": total,
                        "z_score": round(z, 2),
                    },
                ))

        return anomalies
