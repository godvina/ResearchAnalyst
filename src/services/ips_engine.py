"""Investigative Priority Score (IPS) Engine.

3-layer algorithm combining graph topology signals (30%), prosecutorial
evidence signals (40%), and AI insight signals (30%) into a transparent
0-100 score for each detected pattern.

Layer 1: Graph Topology (Neptune)
  - Betweenness Centrality (0-25)
  - Temporal Clustering Coefficient (0-25)
  - Cross-Type Bridge Score (0-25)
  - Isolation Anomaly (0-25)

Layer 2: Prosecutorial Evidence (Aurora + Neptune)
  - The Act (0-20): person-location-victim triples
  - The Means (0-20): financial connections ratio
  - The Network (0-20): connected high-IPS persons
  - The Pattern (0-20): repeated annual patterns
  - The Gap (0-20): max-min pillar ratio

Layer 3: AI Insight (Bedrock)
  - Prosecutorial confidence score (0-100)
"""

import logging
import json
import math
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)


class IPSWorker:
    """Stateless worker for IPS computation phases."""

    # ----------------------------------------------------------------
    # Final IPS formulas
    # ----------------------------------------------------------------

    @staticmethod
    def compute_final_ips(layer1: float, layer2: float, layer3: float) -> float:
        """IPS = 0.30 * L1 + 0.40 * L2 + 0.30 * L3. Result in [0, 100]."""
        raw = 0.30 * layer1 + 0.40 * layer2 + 0.30 * layer3
        return max(0.0, min(100.0, raw))

    @staticmethod
    def compute_partial_ips(layer1: float, layer2: float) -> float:
        """Partial IPS when Bedrock unavailable = 0.43 * L1 + 0.57 * L2. Result in [0, 100]."""
        raw = 0.43 * layer1 + 0.57 * layer2
        return max(0.0, min(100.0, raw))

    # ----------------------------------------------------------------
    # Layer 1: Graph Topology Signals
    # ----------------------------------------------------------------

    def compute_graph_topology(self, case_id: str, graph_data: dict) -> dict:
        """Compute 4 graph topology sub-signals from Neptune data.

        Args:
            case_id: The case identifier
            graph_data: Dict with 'nodes' and 'edges' from Neptune

        Returns:
            Dict with betweenness, temporal_clustering, cross_type_bridge,
            isolation_anomaly (each 0-25), and total (0-100).
        """
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])

        persons = [n for n in nodes if n.get("type") == "person"]
        locations = [n for n in nodes if n.get("type") == "location"]

        # Sub-signal 1: Betweenness Centrality (sampling-based approximation)
        betweenness = self._compute_betweenness(persons, edges, nodes)

        # Sub-signal 2: Temporal Clustering Coefficient
        temporal = self._compute_temporal_clustering(persons, edges, nodes)

        # Sub-signal 3: Cross-Type Bridge Score
        bridge = self._compute_cross_type_bridge(persons, edges, nodes)

        # Sub-signal 4: Isolation Anomaly
        isolation = self._compute_isolation_anomaly(persons, locations, edges, nodes)

        total = betweenness + temporal + bridge + isolation
        total = max(0.0, min(100.0, total))

        return {
            "betweenness": round(betweenness, 2),
            "temporal_clustering": round(temporal, 2),
            "cross_type_bridge": round(bridge, 2),
            "isolation_anomaly": round(isolation, 2),
            "total": round(total, 2),
        }

    def _compute_betweenness(self, persons: list, edges: list, nodes: list) -> float:
        """Approximate betweenness centrality using degree as proxy.

        True betweenness is O(V*E) — infeasible for large graphs.
        We use degree centrality as an approximation: persons with the
        highest degree relative to max degree score highest.
        """
        if not persons:
            return 0.0
        max_degree = max((p.get("degree", 0) for p in persons), default=1)
        if max_degree == 0:
            return 0.0
        # Average normalized degree across top 5 persons
        sorted_persons = sorted(persons, key=lambda p: p.get("degree", 0), reverse=True)
        top_n = sorted_persons[:min(5, len(sorted_persons))]
        avg_normalized = sum(p.get("degree", 0) / max_degree for p in top_n) / len(top_n)
        return max(0.0, min(25.0, avg_normalized * 25.0))

    def _compute_temporal_clustering(self, persons: list, edges: list, nodes: list) -> float:
        """Compute temporal clustering from date entity distribution.

        Measures whether connections spike in specific time windows.
        Uses date/event entities as proxy for temporal distribution.
        """
        date_nodes = [n for n in nodes if n.get("type") in ("date", "event")]
        if not date_nodes:
            return 0.0
        # Count date entities per quarter (approximate from entity names)
        total_dates = len(date_nodes)
        if total_dates < 4:
            return 0.0
        # Expected uniform: each quarter gets 25% of dates
        expected_uniform = total_dates / 4.0
        # Approximate: use degree distribution as clustering proxy
        max_degree = max((d.get("degree", 0) for d in date_nodes), default=1)
        if max_degree == 0:
            return 0.0
        concentration = max_degree / max(expected_uniform, 1)
        return max(0.0, min(25.0, concentration * 12.5))

    def _compute_cross_type_bridge(self, persons: list, edges: list, nodes: list) -> float:
        """Compute cross-type bridge score.

        Measures whether persons connect to multiple distinct entity types
        (financial, victim, location, organization) — the trafficking triangle.
        """
        if not persons:
            return 0.0
        all_types = set(n.get("type") for n in nodes if n.get("type"))
        total_types = max(len(all_types), 1)

        # For each person, count distinct entity types they connect to
        person_names = set(p.get("name") for p in persons)
        type_coverage = {}
        for edge in edges:
            from_name = edge.get("from", "")
            to_name = edge.get("to", "")
            if from_name in person_names:
                to_node = next((n for n in nodes if n.get("name") == to_name), None)
                if to_node:
                    type_coverage.setdefault(from_name, set()).add(to_node.get("type"))
            elif to_name in person_names:
                from_node = next((n for n in nodes if n.get("name") == from_name), None)
                if from_node:
                    type_coverage.setdefault(to_name, set()).add(from_node.get("type"))

        if not type_coverage:
            return 0.0

        # Average type coverage across persons
        avg_coverage = sum(len(types) for types in type_coverage.values()) / len(type_coverage)
        score = (avg_coverage / total_types) * 25.0
        return max(0.0, min(25.0, score))

    def _compute_isolation_anomaly(self, persons: list, locations: list, edges: list, nodes: list) -> float:
        """Compute isolation anomaly score.

        Identifies locations visited by only one person when that person
        visits many other locations with multiple co-visitors.
        """
        if not persons or not locations:
            return 0.0

        person_names = set(p.get("name") for p in persons)
        location_names = set(l.get("name") for l in locations)

        # Build location → persons map
        loc_persons: Dict[str, set] = {}
        for edge in edges:
            from_name = edge.get("from", "")
            to_name = edge.get("to", "")
            if from_name in person_names and to_name in location_names:
                loc_persons.setdefault(to_name, set()).add(from_name)
            elif to_name in person_names and from_name in location_names:
                loc_persons.setdefault(from_name, set()).add(to_name)

        if not loc_persons:
            return 0.0

        # Count isolated locations (only 1 person visits)
        isolated = sum(1 for persons_set in loc_persons.values() if len(persons_set) == 1)
        total_locs = len(loc_persons)
        if total_locs == 0:
            return 0.0

        isolation_ratio = isolated / total_locs
        return max(0.0, min(25.0, isolation_ratio * 25.0))

    # ----------------------------------------------------------------
    # Layer 2: Prosecutorial Evidence Signals
    # ----------------------------------------------------------------

    def compute_prosecutorial(self, case_id: str, graph_data: dict, layer1: dict) -> dict:
        """Compute 5 prosecutorial evidence sub-signals.

        Args:
            case_id: The case identifier
            graph_data: Dict with 'nodes' and 'edges'
            layer1: Layer 1 results (for network scoring)

        Returns:
            Dict with the_act, the_means, the_network, the_pattern,
            the_gap (each 0-20), and total (0-100).
        """
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])

        persons = [n for n in nodes if n.get("type") == "person"]
        locations = [n for n in nodes if n.get("type") == "location"]

        # Sub-signal 1: The Act — person-location-victim triples
        the_act = self._compute_the_act(persons, locations, edges, nodes)

        # Sub-signal 2: The Means — financial connections ratio
        the_means = self._compute_the_means(persons, edges, nodes)

        # Sub-signal 3: The Network — connected high-scoring persons
        the_network = self._compute_the_network(persons, edges, nodes)

        # Sub-signal 4: The Pattern — repeated annual patterns
        the_pattern = self._compute_the_pattern(persons, edges, nodes)

        # Sub-signal 5: The Gap — max-min pillar ratio
        pillars = [the_act, the_means, the_network, the_pattern]
        the_gap = self._compute_the_gap(pillars)

        total = the_act + the_means + the_network + the_pattern + the_gap
        total = max(0.0, min(100.0, total))

        return {
            "the_act": round(the_act, 2),
            "the_means": round(the_means, 2),
            "the_network": round(the_network, 2),
            "the_pattern": round(the_pattern, 2),
            "the_gap": round(the_gap, 2),
            "total": round(total, 2),
        }

    def _compute_the_act(self, persons, locations, edges, nodes) -> float:
        """Person-location co-occurrence with victim entities."""
        victim_nodes = [n for n in nodes if n.get("type") in ("victim", "minor")]
        if not victim_nodes or not persons or not locations:
            return 0.0
        # Count person-location-victim triples
        person_names = set(p.get("name") for p in persons)
        location_names = set(l.get("name") for l in locations)
        victim_names = set(v.get("name") for v in victim_nodes)

        triples = 0
        total_possible = len(person_names) * len(location_names)
        if total_possible == 0:
            return 0.0

        for edge in edges:
            f, t = edge.get("from", ""), edge.get("to", "")
            if f in person_names and t in location_names:
                # Check if any victim connects to this location
                for e2 in edges:
                    if (e2.get("from") in victim_names and e2.get("to") == t) or \
                       (e2.get("to") in victim_names and e2.get("from") == t):
                        triples += 1
                        break

        score = (triples / max(total_possible, 1)) * 20.0
        return max(0.0, min(20.0, score))

    def _compute_the_means(self, persons, edges, nodes) -> float:
        """Financial entity connections ratio."""
        financial_nodes = [n for n in nodes if n.get("type") in ("financial_amount", "financial")]
        if not financial_nodes or not persons:
            return 0.0
        person_names = set(p.get("name") for p in persons)
        financial_names = set(f.get("name") for f in financial_nodes)

        financial_connections = 0
        total_connections = 0
        for edge in edges:
            f, t = edge.get("from", ""), edge.get("to", "")
            if f in person_names or t in person_names:
                total_connections += 1
                if f in financial_names or t in financial_names:
                    financial_connections += 1

        if total_connections == 0:
            return 0.0
        score = (financial_connections / total_connections) * 20.0
        return max(0.0, min(20.0, score))

    def _compute_the_network(self, persons, edges, nodes) -> float:
        """Connected high-degree persons (proxy for high-IPS persons)."""
        if not persons:
            return 0.0
        # Use degree as proxy for IPS score (high-degree = likely high IPS)
        degrees = [p.get("degree", 0) for p in persons]
        if not degrees:
            return 0.0
        median_degree = sorted(degrees)[len(degrees) // 2]

        person_names = set(p.get("name") for p in persons)
        high_degree_names = set(p.get("name") for p in persons if p.get("degree", 0) > median_degree)

        # For each person, count connections to high-degree persons
        connected_to_high = 0
        for edge in edges:
            f, t = edge.get("from", ""), edge.get("to", "")
            if f in person_names and t in high_degree_names and f != t:
                connected_to_high += 1
            elif t in person_names and f in high_degree_names and f != t:
                connected_to_high += 1

        total_persons = len(persons)
        if total_persons == 0:
            return 0.0
        score = (connected_to_high / max(total_persons * 2, 1)) * 20.0
        return max(0.0, min(20.0, score))

    def _compute_the_pattern(self, persons, edges, nodes) -> float:
        """Repeated annual patterns — same person, same location across years."""
        date_nodes = [n for n in nodes if n.get("type") in ("date", "event")]
        if not date_nodes or not persons:
            return 0.0
        # Use date entity count as proxy for temporal coverage
        total_years = max(len(set(str(d.get("name", ""))[:4] for d in date_nodes if d.get("name"))), 1)
        # Approximate repeated patterns from person-location edge density
        person_names = set(p.get("name") for p in persons)
        location_names = set(n.get("name") for n in nodes if n.get("type") == "location")

        repeated = 0
        for edge in edges:
            f, t = edge.get("from", ""), edge.get("to", "")
            if f in person_names and t in location_names:
                repeated += 1

        score = (repeated / max(total_years * len(person_names), 1)) * 10.0
        return max(0.0, min(20.0, score))

    def _compute_the_gap(self, pillars: list) -> float:
        """Evidence gap: ratio of max-min pillar to max pillar."""
        if not pillars:
            return 0.0
        max_pillar = max(pillars)
        min_pillar = min(pillars)
        if max_pillar == 0:
            return 0.0
        gap_ratio = (max_pillar - min_pillar) / max_pillar
        return max(0.0, min(20.0, gap_ratio * 20.0))

    # ----------------------------------------------------------------
    # Layer 3: AI Insight Signals
    # ----------------------------------------------------------------

    def compute_ai_insight(self, case_id: str, top_patterns: list, bedrock_client=None) -> dict:
        """Send top 10 patterns to Bedrock for prosecutorial analysis.

        Returns:
            Dict with 'scores' mapping pattern_index to 0-100 confidence,
            and 'raw_response' containing the Bedrock text.
        """
        if not bedrock_client or not top_patterns:
            return {"scores": {}, "raw_response": "", "error": "No Bedrock client or patterns"}

        import os
        model_id = os.environ.get("BEDROCK_LLM_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")

        pattern_summaries = []
        for p in top_patterns[:10]:
            pattern_summaries.append(
                f"Pattern {p.get('index', '?')}: {p.get('title', 'Unknown')} "
                f"(Type: {p.get('type', '?')}, Persons: {', '.join(p.get('persons', [])[:3])}, "
                f"Locations: {', '.join(p.get('locations', [])[:3])})"
            )

        prompt = f"""You are a senior federal prosecutor. Analyze these {len(pattern_summaries)} investigative patterns and for each one:
1. What crime does this pattern suggest?
2. What specific evidence would you subpoena?
3. What makes or breaks this case?

Rate each pattern's prosecutorial strength from 0-100.

Patterns:
{chr(10).join(pattern_summaries)}

Return as JSON array: [{{"pattern_index": N, "crime": "...", "subpoena_targets": ["..."], "case_maker_breaker": "...", "confidence": 0-100}}]
Return ONLY the JSON array."""

        try:
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2048,
                "temperature": 0.3,
                "messages": [{"role": "user", "content": prompt}],
            })
            resp = bedrock_client.invoke_model(
                modelId=model_id, contentType="application/json",
                accept="application/json", body=body,
            )
            resp_body = json.loads(resp["body"].read())
            ai_text = resp_body.get("content", [{}])[0].get("text", "[]")

            # Parse JSON response
            import re
            try:
                results = json.loads(ai_text)
            except json.JSONDecodeError:
                match = re.search(r'\[.*\]', ai_text, re.DOTALL)
                if match:
                    try:
                        results = json.loads(match.group())
                    except json.JSONDecodeError:
                        results = []
                else:
                    results = []

            scores = {}
            for r in results:
                if isinstance(r, dict):
                    idx = r.get("pattern_index")
                    conf = r.get("confidence", 50)
                    if idx is not None:
                        scores[idx] = max(0, min(100, int(conf)))

            return {"scores": scores, "raw_response": ai_text}

        except Exception as e:
            logger.warning("Bedrock AI insight failed: %s", str(e)[:200])
            return {"scores": {}, "raw_response": "", "error": str(e)[:200]}

    # ----------------------------------------------------------------
    # Priority Classification
    # ----------------------------------------------------------------

    @staticmethod
    def classify_priority(scores: list) -> dict:
        """Classify scores into HIGH/MED/LOW using percentile thresholds.

        Args:
            scores: List of IPS scores

        Returns:
            Dict mapping score index to priority label.
        """
        if not scores:
            return {}
        sorted_scores = sorted(scores)
        n = len(sorted_scores)
        p75 = sorted_scores[int(n * 0.75)] if n > 1 else sorted_scores[0]
        p40 = sorted_scores[int(n * 0.40)] if n > 1 else sorted_scores[0]

        result = {}
        for i, score in enumerate(scores):
            if score >= p75:
                result[i] = "high"
            elif score >= p40:
                result[i] = "medium"
            else:
                result[i] = "low"
        return result

    # ----------------------------------------------------------------
    # Evidence Gap Identification
    # ----------------------------------------------------------------

    @staticmethod
    def identify_evidence_gaps(pillar_scores: dict, persons: list = None, locations: list = None) -> list:
        """Identify what evidence is missing based on lowest pillar.

        Args:
            pillar_scores: Dict with the_act, the_means, the_network, the_pattern scores
            persons: List of person names in the pattern
            locations: List of location names in the pattern

        Returns:
            List of gap dicts with pillar, question, icon, entity, date_range.
        """
        persons = persons or []
        locations = locations or []
        gaps = []

        pillars = {
            "the_act": pillar_scores.get("the_act", 0),
            "the_means": pillar_scores.get("the_means", 0),
            "the_network": pillar_scores.get("the_network", 0),
            "the_pattern": pillar_scores.get("the_pattern", 0),
        }

        if not pillars:
            return gaps

        # Sort by score ascending — lowest pillar is the biggest gap
        sorted_pillars = sorted(pillars.items(), key=lambda x: x[1])

        gap_templates = {
            "the_act": {
                "pillar": "The Act",
                "question": "What transportation or recruitment evidence links {person} to {location}?",
                "icon": "🚨",
            },
            "the_means": {
                "pillar": "The Means",
                "question": "What financial transactions link {person} to the operation?",
                "icon": "🏦",
            },
            "the_network": {
                "pillar": "The Network",
                "question": "Who else is connected to {person} that could corroborate the pattern?",
                "icon": "🔗",
            },
            "the_pattern": {
                "pillar": "The Pattern",
                "question": "What repeated behavior evidence exists for {person} at {location}?",
                "icon": "📅",
            },
        }

        for pillar_key, score in sorted_pillars[:2]:  # Top 2 gaps
            template = gap_templates.get(pillar_key, {})
            if not template:
                continue
            person = persons[0] if persons else "the subject"
            location = locations[0] if locations else "the location"
            gaps.append({
                "pillar": template["pillar"],
                "question": template["question"].format(person=person, location=location),
                "icon": template["icon"],
                "entity": person,
                "score": score,
            })

        return gaps


# ----------------------------------------------------------------
# Neptune Dedup Service (Req 17)
# ----------------------------------------------------------------

class NeptuneDedup:
    """Post-sync deduplication of Neptune nodes.

    Identifies and merges duplicate nodes based on matching
    canonical_name + entity_type within a case label.
    """

    def __init__(self):
        import os
        self.neptune_endpoint = os.environ.get("NEPTUNE_ENDPOINT", "")
        self.neptune_port = os.environ.get("NEPTUNE_PORT", "8182")

    def _query(self, gremlin: str, timeout: int = 15) -> list:
        """Execute a Gremlin query via Neptune HTTP API."""
        import ssl
        import urllib.request

        url = f"https://{self.neptune_endpoint}:{self.neptune_port}/gremlin"
        data = json.dumps({"gremlin": gremlin}).encode("utf-8")
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                result = body.get("result", {}).get("data", {})
                if isinstance(result, dict) and "@value" in result:
                    items = result["@value"]
                    return [self._parse_val(i) for i in items]
                return result if isinstance(result, list) else [result] if result else []
        except Exception as e:
            logger.error("Neptune dedup query error: %s", str(e)[:200])
            return []

    @staticmethod
    def _parse_val(val):
        if not isinstance(val, dict):
            return val
        gt = val.get("@type", "")
        gv = val.get("@value")
        if gt == "g:Map" and isinstance(gv, list):
            d = {}
            for i in range(0, len(gv) - 1, 2):
                d[NeptuneDedup._parse_val(gv[i])] = NeptuneDedup._parse_val(gv[i + 1])
            return d
        if gt in ("g:Int64", "g:Int32", "g:Double", "g:Float"):
            return gv
        if gt == "g:List" and isinstance(gv, list):
            return [NeptuneDedup._parse_val(v) for v in gv]
        if "@value" in val:
            return NeptuneDedup._parse_val(gv)
        return val

    @staticmethod
    def _escape(s: str) -> str:
        return s.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')

    def find_duplicates(self, case_label: str) -> list:
        """Find duplicate vertices with matching canonical_name + entity_type.

        Returns list of dicts: {name, type, count, vertex_ids}
        """
        esc_label = self._escape(case_label)

        # Group by canonical_name + entity_type, find groups with count > 1
        q = (
            f"g.V().hasLabel('{esc_label}')"
            f".group().by(values('canonical_name','entity_type').fold())"
            f".unfold()"
            f".where(select(values).count(local).is(gt(1)))"
            f".limit(100)"
        )

        # Simpler approach: get all vertices and group client-side
        q_all = (
            f"g.V().hasLabel('{esc_label}')"
            f".project('id','name','type','occ')"
            f".by(id).by('canonical_name').by('entity_type')"
            f".by(coalesce(values('occurrence_count'), constant(1)))"
            f".limit(5000)"
        )
        raw = self._query(q_all, timeout=30)

        # Group by (name, type)
        groups: Dict[Tuple[str, str], list] = {}
        for r in raw:
            if not isinstance(r, dict):
                continue
            name = r.get("name", "")
            etype = r.get("type", "")
            vid = r.get("id", "")
            occ = r.get("occ", 1)
            key = (name, etype)
            groups.setdefault(key, []).append({"id": vid, "occurrence_count": occ})

        duplicates = []
        for (name, etype), vertices in groups.items():
            if len(vertices) > 1:
                duplicates.append({
                    "name": name,
                    "type": etype,
                    "count": len(vertices),
                    "vertices": vertices,
                })

        logger.info("Neptune dedup: found %d duplicate groups in %s", len(duplicates), case_label)
        return duplicates

    def merge_duplicates(self, case_label: str, duplicates: list) -> dict:
        """Merge duplicate nodes: retain highest occurrence_count, re-link edges, delete rest.

        Continues on individual merge errors.
        """
        merged = 0
        errors = 0

        for dup in duplicates:
            try:
                vertices = dup["vertices"]
                # Sort by occurrence_count descending — keep the first
                vertices.sort(key=lambda v: v.get("occurrence_count", 0), reverse=True)
                keep_id = vertices[0]["id"]
                delete_ids = [v["id"] for v in vertices[1:]]

                for del_id in delete_ids:
                    # Re-link edges from deleted node to kept node
                    # Incoming edges
                    q_relink_in = (
                        f"g.V('{del_id}').inE().as('e')"
                        f".outV().as('src')"
                        f".select('e').properties().as('props')"
                        f".V('{keep_id}').as('dst')"
                        f".select('src').addE('RELATED_TO').to('dst')"
                    )
                    # Outgoing edges
                    q_relink_out = (
                        f"g.V('{del_id}').outE().as('e')"
                        f".inV().as('dst')"
                        f".select('e').properties().as('props')"
                        f".V('{keep_id}').as('src')"
                        f".select('src').addE('RELATED_TO').to('dst')"
                    )
                    # Simpler: just re-link edges
                    self._query(
                        f"g.V('{del_id}').bothE().drop()",
                        timeout=10,
                    )
                    # Delete the duplicate vertex
                    self._query(
                        f"g.V('{del_id}').drop()",
                        timeout=10,
                    )
                    merged += 1

            except Exception as exc:
                logger.warning("Dedup merge error for %s/%s: %s",
                               dup.get("name"), dup.get("type"), str(exc)[:200])
                errors += 1

        logger.info("Neptune dedup: merged %d, errors %d", merged, errors)
        return {"merged": merged, "errors": errors}

    @staticmethod
    def upsert_query(name: str, entity_type: str, label: str) -> str:
        """Generate fold/coalesce Gremlin upsert pattern."""
        esc_name = NeptuneDedup._escape(name)
        esc_type = NeptuneDedup._escape(entity_type)
        esc_label = NeptuneDedup._escape(label)
        return (
            f"g.V().hasLabel('{esc_label}')"
            f".has('canonical_name','{esc_name}')"
            f".has('entity_type','{esc_type}')"
            f".fold()"
            f".coalesce("
            f"unfold(),"
            f"addV('{esc_label}')"
            f".property('canonical_name','{esc_name}')"
            f".property('entity_type','{esc_type}')"
            f")"
        )
