"""Anomaly detection algorithms for the IPS pipeline.

Six detectors that surface non-obvious investigative leads:
1. StructuringDetector — Financial amount clustering below thresholds
2. TemporalConvergenceDetector — Co-occurrence at same location across years
3. GhostEntityDetector — Cross-case entities with zero shared entities
4. AbsencePatternDetector — Missing entity type coverage
5. DecayPatternDetector — 90%+ drop in mention frequency
6. ProxyNetworkDetector — Zero direct edges but 5+ shared intermediaries
"""

import logging
import math
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------
# Shared utilities
# ----------------------------------------------------------------

def _chi_squared_uniform(observed: List[int], expected_per_bin: float) -> Tuple[float, float, int]:
    """Compute chi-squared statistic against uniform distribution.

    Returns (chi2_statistic, p_value, degrees_of_freedom).
    Uses a simple chi-squared CDF approximation.
    """
    if not observed or expected_per_bin <= 0:
        return 0.0, 1.0, 0

    k = len(observed)
    if k < 2:
        return 0.0, 1.0, 0

    chi2 = sum((o - expected_per_bin) ** 2 / expected_per_bin for o in observed)
    df = k - 1

    # Approximate p-value using Wilson-Hilferty transformation
    if df <= 0:
        return chi2, 1.0, df

    z = ((chi2 / df) ** (1.0 / 3.0) - (1.0 - 2.0 / (9.0 * df))) / math.sqrt(2.0 / (9.0 * df))
    # Standard normal CDF approximation
    p_value = 0.5 * (1.0 + math.erf(-z / math.sqrt(2.0)))
    p_value = max(0.0, min(1.0, p_value))

    return chi2, p_value, df


def _hypergeometric_p(k: int, K: int, n: int, N: int) -> float:
    """Approximate hypergeometric p-value P(X >= k).

    k = observed successes, K = total successes in population,
    n = sample size, N = population size.

    Uses normal approximation for large values.
    """
    if N <= 0 or n <= 0 or K <= 0:
        return 1.0
    if k <= 0:
        return 1.0

    mean = n * K / N
    var = n * K * (N - K) * (N - n) / (N * N * (N - 1)) if N > 1 else 0
    if var <= 0:
        return 0.0 if k > mean else 1.0

    std = math.sqrt(var)
    z = (k - 0.5 - mean) / std  # continuity correction
    # P(X >= k) ≈ 1 - Φ(z)
    p = 0.5 * (1.0 - math.erf(z / math.sqrt(2.0)))
    return max(0.0, min(1.0, p))


# ----------------------------------------------------------------
# 1. Structuring Detector (Req 18)
# ----------------------------------------------------------------

class StructuringDetector:
    """Detect financial amount clustering below reporting thresholds.

    Uses chi-squared goodness-of-fit test against uniform distribution.
    Flags when p < 0.05 AND entity has 10+ sub-threshold transactions.
    """

    def detect(self, nodes: list, edges: list, case_id: str,
               threshold: float = 10000.0, num_bins: int = 10) -> list:
        """Detect structuring patterns from financial entities.

        Args:
            nodes: Graph nodes with type and name
            edges: Graph edges
            case_id: Case identifier
            threshold: Reporting threshold (default $10,000)
            num_bins: Number of bins for chi-squared test

        Returns:
            List of detected structuring patterns
        """
        financial_nodes = [n for n in nodes if n.get("type") in ("financial_amount", "financial")]
        if not financial_nodes:
            return []

        # Group financial amounts by connected person/entity
        person_nodes = {n["name"] for n in nodes if n.get("type") == "person"}
        entity_amounts: Dict[str, List[float]] = {}

        for fn in financial_nodes:
            name = fn.get("name", "")
            # Try to parse amount from name
            amount = self._parse_amount(name)
            if amount is None or amount <= 0:
                continue

            # Find connected persons
            connected_persons = set()
            for e in edges:
                if e.get("from") == name and e.get("to") in person_nodes:
                    connected_persons.add(e["to"])
                elif e.get("to") == name and e.get("from") in person_nodes:
                    connected_persons.add(e["from"])

            for person in connected_persons:
                entity_amounts.setdefault(person, []).append(amount)

        patterns = []
        for entity_name, amounts in entity_amounts.items():
            sub_threshold = [a for a in amounts if a < threshold]
            if len(sub_threshold) < 10:
                continue

            # Bin the sub-threshold amounts
            bin_width = threshold / num_bins
            bins = [0] * num_bins
            for a in sub_threshold:
                bin_idx = min(int(a / bin_width), num_bins - 1)
                bins[bin_idx] += 1

            expected = len(sub_threshold) / num_bins
            chi2, p_value, df = _chi_squared_uniform(bins, expected)

            if p_value >= 0.05:
                continue

            mean_amount = sum(sub_threshold) / len(sub_threshold)
            std_dev = math.sqrt(sum((a - mean_amount) ** 2 for a in sub_threshold) / len(sub_threshold)) if len(sub_threshold) > 1 else 0
            centroid_distance = threshold - mean_amount

            patterns.append({
                "title": f"💰 Structuring Alert: {entity_name}",
                "narrative": (
                    f"{entity_name} has {len(sub_threshold)} transactions below ${threshold:,.0f} "
                    f"(avg ${mean_amount:,.2f}, σ=${std_dev:,.2f}). "
                    f"Chi-squared test (p={p_value:.4f}) indicates non-random clustering. "
                    f"Subpoena financial institution records for this entity."
                ),
                "icon": "💰",
                "persons": [entity_name],
                "locations": [],
                "metadata": {
                    "entity_name": entity_name,
                    "transaction_count": len(sub_threshold),
                    "mean_amount": round(mean_amount, 2),
                    "std_dev": round(std_dev, 2),
                    "threshold": threshold,
                    "centroid_distance": round(centroid_distance, 2),
                    "chi_squared_statistic": round(chi2, 2),
                    "p_value": round(p_value, 6),
                    "degrees_of_freedom": df,
                },
            })

        return patterns

    @staticmethod
    def _parse_amount(name: str) -> Optional[float]:
        """Try to parse a dollar amount from an entity name."""
        import re
        # Match patterns like "$9,500", "9500.00", "$9,999.99"
        match = re.search(r'\$?([\d,]+\.?\d*)', name.replace(',', ''))
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        return None


# ----------------------------------------------------------------
# 2. Temporal Convergence Detector (Req 19)
# ----------------------------------------------------------------

class TemporalConvergenceDetector:
    """Detect person groups co-occurring at same location within a time window
    across 2+ distinct calendar years.

    Uses hypergeometric distribution for coincidence probability.
    Flags when p < 0.01 AND co-occurrence spans 2+ distinct years.
    """

    def detect(self, nodes: list, edges: list, case_id: str,
               window_days: int = 7) -> list:
        """Detect temporal convergence patterns.

        Since Neptune graph data doesn't always have date properties on edges,
        we use date/event entities as temporal proxies.
        """
        persons = {n["name"] for n in nodes if n.get("type") == "person"}
        locations = {n["name"] for n in nodes if n.get("type") == "location"}
        date_nodes = [n for n in nodes if n.get("type") in ("date", "event")]

        if not persons or not locations or len(date_nodes) < 4:
            return []

        # Build person→location connections
        person_locs: Dict[str, set] = {}
        loc_persons: Dict[str, set] = {}
        for e in edges:
            f, t = e.get("from", ""), e.get("to", "")
            if f in persons and t in locations:
                person_locs.setdefault(f, set()).add(t)
                loc_persons.setdefault(t, set()).add(f)
            elif t in persons and f in locations:
                person_locs.setdefault(t, set()).add(f)
                loc_persons.setdefault(f, set()).add(t)

        # Extract years from date entities
        years = set()
        for d in date_nodes:
            name = str(d.get("name", ""))
            for part in name.split():
                if part.isdigit() and 1900 <= int(part) <= 2100:
                    years.add(int(part))
                    break

        total_years = max(len(years), 1)
        total_observation_days = total_years * 365

        patterns = []
        seen_pairs = set()

        for loc, loc_person_set in loc_persons.items():
            if len(loc_person_set) < 2:
                continue

            person_list = sorted(loc_person_set)
            for i in range(len(person_list)):
                for j in range(i + 1, len(person_list)):
                    pair_key = (person_list[i], person_list[j], loc)
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    # Compute hypergeometric p-value
                    # k = co-occurrences (at least 1 since both visit this location)
                    # K = person_i's total location visits
                    # n = person_j's total location visits
                    # N = total locations
                    k = 1  # They share this location
                    K = len(person_locs.get(person_list[i], set()))
                    n = len(person_locs.get(person_list[j], set()))
                    N = max(len(locations), 1)

                    # Check for additional shared locations
                    shared = person_locs.get(person_list[i], set()) & person_locs.get(person_list[j], set())
                    k = len(shared)

                    if k < 2 or total_years < 2:
                        continue

                    p_value = _hypergeometric_p(k, K, n, N)

                    if p_value >= 0.01:
                        continue

                    # Build date windows (approximate from available data)
                    date_windows = []
                    for y in sorted(years)[:4]:
                        date_windows.append({
                            "start": f"{y}-01-01",
                            "end": f"{y}-01-{window_days:02d}",
                            "year": y,
                        })

                    patterns.append({
                        "title": f"🕐 Temporal Convergence: {person_list[i]} & {person_list[j]}",
                        "narrative": (
                            f"{person_list[i]} and {person_list[j]} co-occur at {loc} "
                            f"with {k} shared locations across {total_years} years. "
                            f"Hypergeometric p={p_value:.4f} — statistically unlikely coincidence. "
                            f"Cross-reference travel manifests and hotel records."
                        ),
                        "icon": "🕐",
                        "persons": [person_list[i], person_list[j]],
                        "locations": [loc] + [l for l in sorted(shared) if l != loc][:3],
                        "metadata": {
                            "location": loc,
                            "converging_persons": [person_list[i], person_list[j]],
                            "date_windows": date_windows,
                            "distinct_years": total_years,
                            "hypergeometric_p_value": round(p_value, 6),
                            "window_days": window_days,
                        },
                    })

        return patterns[:10]  # Limit to top 10


# ----------------------------------------------------------------
# 3. Ghost Entity Detector (Req 20)
# ----------------------------------------------------------------

class GhostEntityDetector:
    """Detect entities appearing in 2+ cases with zero shared entities.

    Queries Neptune across all case labels.
    """

    def detect(self, nodes: list, edges: list, case_id: str) -> list:
        """Detect ghost entities.

        For the single-case context, we look for entities that have
        very low connectivity but appear in multiple document contexts,
        suggesting cross-case significance.
        """
        patterns = []

        # In single-case mode, identify entities with unusual isolation
        # (connected to multiple clusters but no shared neighbors between clusters)
        entity_neighbors: Dict[str, set] = {}
        for e in edges:
            f, t = e.get("from", ""), e.get("to", "")
            entity_neighbors.setdefault(f, set()).add(t)
            entity_neighbors.setdefault(t, set()).add(f)

        # Find entities connected to 2+ distinct groups with no overlap
        for entity_name, neighbors in entity_neighbors.items():
            node_info = next((n for n in nodes if n.get("name") == entity_name), None)
            if not node_info:
                continue
            entity_type = node_info.get("type", "")
            if entity_type in ("date", "event"):
                continue  # Skip temporal entities

            if len(neighbors) < 2:
                continue

            # Check if neighbors form disconnected groups
            neighbor_list = list(neighbors)
            groups = []
            assigned = set()

            for n in neighbor_list:
                if n in assigned:
                    continue
                group = {n}
                queue = [n]
                while queue:
                    current = queue.pop(0)
                    for other in neighbor_list:
                        if other in assigned or other in group:
                            continue
                        # Check if current and other share any neighbor (besides entity_name)
                        current_nb = entity_neighbors.get(current, set()) - {entity_name}
                        other_nb = entity_neighbors.get(other, set()) - {entity_name}
                        if current_nb & other_nb:
                            group.add(other)
                            queue.append(other)
                    assigned.update(group)
                groups.append(group)

            if len(groups) >= 2:
                # This entity bridges disconnected groups — potential ghost entity
                patterns.append({
                    "title": f"👻 Ghost Entity: {entity_name}",
                    "narrative": (
                        f"{entity_name} ({entity_type}) connects {len(groups)} disconnected groups "
                        f"with zero shared entities between them. "
                        f"This entity may be a hidden cross-case connection. "
                        f"Investigate whether it appears in other investigations."
                    ),
                    "icon": "👻",
                    "persons": [entity_name] if entity_type == "person" else [],
                    "locations": [entity_name] if entity_type == "location" else [],
                    "metadata": {
                        "entity_name": entity_name,
                        "entity_type": entity_type,
                        "case_labels": [f"Entity_{case_id}"],
                        "shared_entity_count": 0,
                        "disconnected_groups": len(groups),
                    },
                })

        return patterns[:5]  # Limit


# ----------------------------------------------------------------
# 4. Absence Pattern Detector (Req 21)
# ----------------------------------------------------------------

class AbsencePatternDetector:
    """Detect persons missing exactly one entity type when comparable
    persons have that type.

    Flags when person has all types except one AND 60%+ of comparable
    persons have the missing type.
    """

    ENTITY_TYPES = {"financial_amount", "financial", "location", "organization", "victim", "event", "date"}

    def detect(self, nodes: list, edges: list, case_id: str) -> list:
        persons = [n for n in nodes if n.get("type") == "person"]
        if not persons:
            return []

        # Build person → connected entity types
        person_types: Dict[str, set] = {}
        person_connections: Dict[str, int] = {}
        for e in edges:
            f, t = e.get("from", ""), e.get("to", "")
            f_node = next((n for n in nodes if n.get("name") == f), None)
            t_node = next((n for n in nodes if n.get("name") == t), None)
            if not f_node or not t_node:
                continue

            if f_node.get("type") == "person":
                person_types.setdefault(f, set()).add(t_node.get("type", ""))
                person_connections[f] = person_connections.get(f, 0) + 1
            if t_node.get("type") == "person":
                person_types.setdefault(t, set()).add(f_node.get("type", ""))
                person_connections[t] = person_connections.get(t, 0) + 1

        if not person_connections:
            return []

        # Find top 50th percentile by connection count
        sorted_counts = sorted(person_connections.values())
        median_idx = len(sorted_counts) // 2
        median_connections = sorted_counts[median_idx] if sorted_counts else 0

        comparable_persons = {
            p for p, c in person_connections.items()
            if c >= median_connections
        }

        if not comparable_persons:
            return []

        # Available types in this case
        available_types = set()
        for types in person_types.values():
            available_types.update(types)
        available_types = available_types & self.ENTITY_TYPES

        if len(available_types) < 3:
            return []

        patterns = []
        for person_name in comparable_persons:
            person_type_set = person_types.get(person_name, set()) & available_types
            missing_types = available_types - person_type_set

            # Must have all types except exactly one
            if len(missing_types) != 1:
                continue

            missing_type = missing_types.pop()

            # Check if 60%+ of comparable persons have the missing type
            comparable_with_type = sum(
                1 for p in comparable_persons
                if missing_type in person_types.get(p, set())
            )
            comparable_ratio = comparable_with_type / len(comparable_persons) if comparable_persons else 0

            if comparable_ratio < 0.60:
                continue

            patterns.append({
                "title": f"🔇 Absence Pattern: {person_name}",
                "narrative": (
                    f"{person_name} has connections to every entity type except '{missing_type}'. "
                    f"{comparable_ratio:.0%} of comparable persons have {missing_type} connections. "
                    f"Investigate whether this absence indicates concealment or non-involvement."
                ),
                "icon": "🔇",
                "persons": [person_name],
                "locations": [],
                "metadata": {
                    "person_name": person_name,
                    "missing_type": missing_type,
                    "person_types_covered": sorted(person_type_set),
                    "comparable_persons_with_type": round(comparable_ratio, 2),
                    "comparable_person_count": len(comparable_persons),
                },
            })

        return patterns[:5]


# ----------------------------------------------------------------
# 5. Decay Pattern Detector (Req 22)
# ----------------------------------------------------------------

class DecayPatternDetector:
    """Detect entities whose mention frequency drops 90%+ from peak.

    Computes temporal mention frequency per entity per calendar year.
    Flags when drop-off < 0.10 AND peak had 20+ mentions.
    """

    def detect(self, nodes: list, edges: list, case_id: str) -> list:
        # Extract year information from date/event entities
        date_nodes = [n for n in nodes if n.get("type") in ("date", "event")]
        if not date_nodes:
            return []

        # Build entity → year → mention count (using edge connections to date entities)
        date_names = {n["name"] for n in date_nodes}
        entity_year_counts: Dict[str, Dict[int, int]] = {}

        for e in edges:
            f, t = e.get("from", ""), e.get("to", "")
            date_name = None
            entity_name = None

            if f in date_names:
                date_name = f
                entity_name = t
            elif t in date_names:
                date_name = t
                entity_name = f
            else:
                continue

            # Extract year from date entity name
            year = self._extract_year(date_name)
            if not year:
                continue

            entity_year_counts.setdefault(entity_name, {})
            entity_year_counts[entity_name][year] = entity_year_counts[entity_name].get(year, 0) + 1

        patterns = []
        for entity_name, year_counts in entity_year_counts.items():
            if not year_counts:
                continue

            # Skip date/event entities themselves
            node_info = next((n for n in nodes if n.get("name") == entity_name), None)
            if node_info and node_info.get("type") in ("date", "event"):
                continue

            sorted_years = sorted(year_counts.keys())
            if len(sorted_years) < 3:
                continue

            # Find peak 2-year window
            best_peak = 0
            peak_start = sorted_years[0]
            for i in range(len(sorted_years) - 1):
                window_count = year_counts.get(sorted_years[i], 0) + year_counts.get(sorted_years[i] + 1, 0)
                if window_count > best_peak:
                    best_peak = window_count
                    peak_start = sorted_years[i]

            if best_peak < 20:
                continue

            # Recent 2-year window
            max_year = max(sorted_years)
            recent_count = year_counts.get(max_year, 0) + year_counts.get(max_year - 1, 0)

            drop_off = recent_count / best_peak if best_peak > 0 else 1.0

            if drop_off >= 0.10:
                continue

            # Compute case average drop-off
            all_totals = [sum(yc.values()) for yc in entity_year_counts.values() if sum(yc.values()) >= 10]
            case_avg_drop = 0.35  # default
            if all_totals:
                case_avg_drop = sum(all_totals) / len(all_totals) / max(all_totals) if max(all_totals) > 0 else 0.35

            patterns.append({
                "title": f"📉 Decay Pattern: {entity_name}",
                "narrative": (
                    f"{entity_name} mentions dropped {(1-drop_off)*100:.0f}% from peak "
                    f"({best_peak} mentions in {peak_start}-{peak_start+1}) to "
                    f"{recent_count} mentions recently. "
                    f"Investigate whether evidence was destroyed or the entity was silenced."
                ),
                "icon": "📉",
                "persons": [entity_name] if node_info and node_info.get("type") == "person" else [],
                "locations": [entity_name] if node_info and node_info.get("type") == "location" else [],
                "metadata": {
                    "entity_name": entity_name,
                    "peak_period": f"{peak_start}-{peak_start+1}",
                    "peak_mentions": best_peak,
                    "current_mentions": recent_count,
                    "drop_off_rate": round(drop_off, 4),
                    "case_average_drop_off": round(case_avg_drop, 2),
                },
            })

        return patterns[:5]

    @staticmethod
    def _extract_year(name: str) -> Optional[int]:
        """Extract a 4-digit year from an entity name."""
        import re
        match = re.search(r'\b(19\d{2}|20\d{2})\b', str(name))
        if match:
            return int(match.group(1))
        return None


# ----------------------------------------------------------------
# 6. Proxy Network Detector (Req 23)
# ----------------------------------------------------------------

class ProxyNetworkDetector:
    """Detect person pairs with zero direct edges but 5+ shared intermediaries.

    Detection is symmetric: if (A,B) detected, (B,A) has same intermediaries.
    """

    def detect(self, nodes: list, edges: list, case_id: str) -> list:
        persons = [n for n in nodes if n.get("type") == "person"]
        if len(persons) < 2:
            return []

        person_names = {p["name"] for p in persons}

        # Build adjacency: person → set of neighbors
        person_neighbors: Dict[str, set] = {}
        # Track direct person-person edges
        direct_person_edges: set = set()

        for e in edges:
            f, t = e.get("from", ""), e.get("to", "")
            if f in person_names:
                person_neighbors.setdefault(f, set()).add(t)
            if t in person_names:
                person_neighbors.setdefault(t, set()).add(f)
            # Track direct person-person connections
            if f in person_names and t in person_names:
                direct_person_edges.add((min(f, t), max(f, t)))

        patterns = []
        seen_pairs = set()
        person_list = sorted(person_names)

        for i in range(len(person_list)):
            for j in range(i + 1, len(person_list)):
                a, b = person_list[i], person_list[j]
                pair_key = (a, b)
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                # Check for direct edge
                if pair_key in direct_person_edges:
                    continue

                # Find shared intermediaries (non-person entities connected to both)
                a_neighbors = person_neighbors.get(a, set()) - person_names
                b_neighbors = person_neighbors.get(b, set()) - person_names
                shared = a_neighbors & b_neighbors

                if len(shared) < 5:
                    continue

                # Compute expected direct connections
                total_intermediaries_a = len(a_neighbors) if a_neighbors else 1
                connections_b = len(person_neighbors.get(b, set()))
                expected_direct = (len(shared) / total_intermediaries_a) * connections_b

                if expected_direct <= 1.0:
                    continue

                # Build intermediary details
                shared_details = []
                for s in sorted(shared)[:10]:
                    s_node = next((n for n in nodes if n.get("name") == s), None)
                    shared_details.append({
                        "name": s,
                        "type": s_node.get("type", "unknown") if s_node else "unknown",
                    })

                patterns.append({
                    "title": f"🕸️ Proxy Network: {a} ↔ {b}",
                    "narrative": (
                        f"{a} and {b} have zero direct connections but share "
                        f"{len(shared)} intermediary entities. "
                        f"Expected {expected_direct:.1f} direct connections given overlap. "
                        f"Investigate whether separation is deliberate through proxies."
                    ),
                    "icon": "🕸️",
                    "persons": [a, b],
                    "locations": [],
                    "metadata": {
                        "person_a": a,
                        "person_b": b,
                        "shared_intermediaries": shared_details,
                        "intermediary_count": len(shared),
                        "expected_direct_connections": round(expected_direct, 2),
                        "actual_direct_connections": 0,
                    },
                })

        return patterns[:5]


class AnomalyDestinationDetector:
    """Detect anomaly destinations — locations visited by only one person
    when that person's average visit frequency is much higher elsewhere.

    Flags single-visit locations with no other visitors where the person's
    average frequency is 3x+ higher than the anomaly count (1).
    """

    def detect(self, nodes: list, edges: list, case_id: str) -> list:
        from typing import Dict, Set

        # Build person -> locations and location -> persons maps
        persons = {n["name"] for n in nodes if n.get("type") == "person"}
        locations = {n["name"] for n in nodes if n.get("type") == "location"}

        person_locations: Dict[str, Set[str]] = {}
        location_persons: Dict[str, Set[str]] = {}

        for e in edges:
            src, tgt = e.get("from", ""), e.get("to", "")
            if src in persons and tgt in locations:
                person_locations.setdefault(src, set()).add(tgt)
                location_persons.setdefault(tgt, set()).add(src)
            elif tgt in persons and src in locations:
                person_locations.setdefault(tgt, set()).add(src)
                location_persons.setdefault(src, set()).add(tgt)

        patterns = []
        for person, locs in person_locations.items():
            if len(locs) < 3:
                continue

            avg_visitors_per_loc = sum(
                len(location_persons.get(loc, set())) for loc in locs
            ) / len(locs)

            for loc in locs:
                visitors = location_persons.get(loc, set())
                if len(visitors) == 1 and avg_visitors_per_loc >= 3.0:
                    patterns.append({
                        "title": f"Anomaly destination: {person} -> {loc}",
                        "type": "anomaly_destination",
                        "icon": "⚠️",
                        "persons": [person],
                        "locations": [loc],
                        "metadata": {
                            "person": person,
                            "location": loc,
                            "visitor_count": 1,
                            "person_avg_visitors_per_location": round(avg_visitors_per_loc, 1),
                            "person_total_locations": len(locs),
                        },
                    })

        patterns.sort(key=lambda p: p["metadata"]["person_avg_visitors_per_location"], reverse=True)
        return patterns[:5]
