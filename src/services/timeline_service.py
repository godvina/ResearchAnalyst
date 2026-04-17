"""Timeline reconstruction service — chronological event extraction, clustering, and gap analysis.

Reconstructs investigative timelines from Neptune graph date entities,
Aurora entity metadata, and OpenSearch document snippets. Provides
activity clustering, temporal gap detection, and AI-powered analysis
via Bedrock Claude.

Uses Neptune HTTP API (POST /gremlin) instead of WebSocket-based gremlinpython
to avoid VPC Lambda cold start timeouts.
"""

import json
import logging
import os
import re
import ssl
import urllib.request
import urllib.error
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from db.connection import ConnectionManager

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

NEPTUNE_ENDPOINT = os.environ.get("NEPTUNE_ENDPOINT", "")
NEPTUNE_PORT = os.environ.get("NEPTUNE_PORT", "8182")
BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"

# Allowed event types
ALLOWED_EVENT_TYPES = frozenset([
    "communication", "meeting", "financial_transaction", "travel",
    "legal_proceeding", "document_creation", "other",
])


def _parse_graphson(items: list) -> list:
    """Parse GraphSON typed values into plain Python objects."""
    result = []
    for item in items:
        result.append(_parse_graphson_value(item))
    return result


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
    if gtype == "g:Path" and isinstance(gval, dict):
        objects = gval.get("objects", gval.get("labels", []))
        if isinstance(objects, dict) and "@value" in objects:
            objects = objects["@value"]
        return {"objects": [_parse_graphson_value(o) for o in objects] if isinstance(objects, list) else objects}
    if "@value" in val:
        return _parse_graphson_value(gval)
    return val


def _escape(s: str) -> str:
    """Escape a string for Gremlin query embedding."""
    return s.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')


class TimelineService:
    """Reconstructs investigative timelines from graph, relational, and search data."""

    def __init__(self, neptune_conn: Any, aurora_conn: ConnectionManager, bedrock_client: Any) -> None:
        self._aurora = aurora_conn
        self._bedrock = bedrock_client

    # ------------------------------------------------------------------
    # Neptune HTTP API helper
    # ------------------------------------------------------------------

    def _neptune_query(self, query: str) -> list:
        """Execute a Gremlin query via Neptune HTTP API."""
        url = f"https://{NEPTUNE_ENDPOINT}:{NEPTUNE_PORT}/gremlin"
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

    # ------------------------------------------------------------------
    # Date normalization
    # ------------------------------------------------------------------

    # Common date patterns
    _DATE_PATTERNS = [
        # ISO 8601 full datetime
        (r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", "%Y-%m-%dT%H:%M:%S"),
        # ISO 8601 date only
        (r"^\d{4}-\d{2}-\d{2}$", "%Y-%m-%d"),
        # MM/DD/YYYY
        (r"^\d{1,2}/\d{1,2}/\d{4}$", "%m/%d/%Y"),
        # DD-MM-YYYY
        (r"^\d{1,2}-\d{1,2}-\d{4}$", "%d-%m-%Y"),
        # Mon DD, YYYY or Month DD, YYYY
        (r"^[A-Za-z]+ \d{1,2},? \d{4}$", None),
        # Weekday MM/DD/YYYY (e.g., "Fri 4/28/2017")
        (r"^[A-Za-z]{3}\s+\d{1,2}/\d{1,2}/\d{4}$", None),
        # YYYY
        (r"^\d{4}$", "%Y"),
    ]

    def _normalize_date(self, date_str: str) -> str | None:
        """Parse various date formats into ISO 8601. Return None for unparseable."""
        if not date_str or not isinstance(date_str, str):
            return None

        text = date_str.strip()

        # Skip obvious noise: all zeros, too short, mostly non-alphanumeric
        if len(text) < 4:
            return None
        alpha_count = sum(1 for c in text if c.isalnum())
        if alpha_count < 3:
            return None
        if re.match(r'^0+$', text.replace('/', '').replace('-', '').replace(' ', '')):
            return None

        # Strip parenthetical suffixes: "1958-01-16 (January 16, 1958)"
        text = re.sub(r'\s*\(.*\)\s*$', '', text).strip()

        # Try standard ISO and common formats
        for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d",
                     "%m/%d/%Y", "%d/%m/%Y", "%d-%m-%Y", "%m-%d-%Y",
                     "%d.%m.%Y", "%m.%d.%Y", "%Y"):
            try:
                dt = datetime.strptime(text.rstrip("Z"), fmt)
                if dt.year < 1900 or dt.year > 2030:
                    continue
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                continue

        # "DD MMM YYYY" or "DD MMM, YYYY": "02 JUN 2013", "17 JUN 2020"
        dd_mmm_match = re.match(r'^(\d{1,2})\s+([A-Za-z]{3,9}),?\s+(\d{4})$', text)
        if dd_mmm_match:
            for fmt in ("%d %B %Y", "%d %b %Y"):
                try:
                    clean = f"{dd_mmm_match.group(1)} {dd_mmm_match.group(2)} {dd_mmm_match.group(3)}"
                    dt = datetime.strptime(clean, fmt)
                    if 1900 <= dt.year <= 2030:
                        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                except ValueError:
                    continue

        # "DD Month YYYY": "17 March 2011"
        dd_month_match = re.match(r'^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$', text)
        if dd_month_match:
            for fmt in ("%d %B %Y", "%d %b %Y"):
                try:
                    clean = f"{dd_month_match.group(1)} {dd_month_match.group(2)} {dd_month_match.group(3)}"
                    dt = datetime.strptime(clean, fmt)
                    if 1900 <= dt.year <= 2030:
                        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                except ValueError:
                    continue

        # Weekday prefix: "Fri 4/28/2017"
        wkday_match = re.match(r"^[A-Za-z]{3}\s+(\d{1,2}/\d{1,2}/\d{4})$", text)
        if wkday_match:
            try:
                dt = datetime.strptime(wkday_match.group(1), "%m/%d/%Y")
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                pass

        # "Month DD, YYYY" or "Month DD YYYY"
        month_match = re.match(r"^([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})$", text)
        if month_match:
            for fmt in ("%B %d %Y", "%b %d %Y"):
                try:
                    dt = datetime.strptime(f"{month_match.group(1)} {month_match.group(2)} {month_match.group(3)}", fmt)
                    if 1900 <= dt.year <= 2030:
                        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                except ValueError:
                    continue

        # "MMM YYYY": "JUN 2013" → first of month
        mmm_yyyy = re.match(r'^([A-Za-z]{3,9})\s+(\d{4})$', text)
        if mmm_yyyy:
            for fmt in ("%B %Y", "%b %Y"):
                try:
                    dt = datetime.strptime(f"{mmm_yyyy.group(1)} {mmm_yyyy.group(2)}", fmt)
                    if 1900 <= dt.year <= 2030:
                        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                except ValueError:
                    continue

        return None

    # ------------------------------------------------------------------
    # Event type inference
    # ------------------------------------------------------------------

    def _infer_event_type(self, connected_entity_types: list[str]) -> str:
        """Deterministic event type inference from connected entity types."""
        types_set = set(t.lower() for t in connected_entity_types if t)

        has_person = "person" in types_set
        has_location = "location" in types_set
        has_financial = "financial_amount" in types_set
        has_phone = "phone_number" in types_set
        has_email = "email" in types_set
        has_org = "organization" in types_set
        has_legal = "legal" in types_set
        has_metadata = "metadata" in types_set

        if has_person and has_location:
            return "travel"
        if has_person and has_financial:
            return "financial_transaction"
        if has_person and sum(1 for t in connected_entity_types if t.lower() == "person") >= 2:
            return "meeting"
        if has_person and (has_phone or has_email):
            return "communication"
        if has_org and has_legal:
            return "legal_proceeding"
        if has_metadata:
            return "document_creation"
        return "other"

    # ------------------------------------------------------------------
    # Source snippet retrieval (OpenSearch)
    # ------------------------------------------------------------------

    def _get_source_snippets(self, case_id: str, date_str: str,
                              document_ids: list[str]) -> list[dict]:
        """Query OpenSearch for text surrounding date mentions, truncate to 200 chars."""
        os_endpoint = os.environ.get("OPENSEARCH_ENDPOINT", "")
        if not os_endpoint or not document_ids:
            return [{"document_id": did, "filename": None, "snippet": None,
                      "status": "source_unavailable"} for did in document_ids]

        snippets = []
        for doc_id in document_ids:
            try:
                url = f"https://{os_endpoint}/{case_id}/_search"
                body = json.dumps({
                    "query": {
                        "bool": {
                            "must": [
                                {"match": {"content": date_str}},
                                {"term": {"document_id": doc_id}},
                            ]
                        }
                    },
                    "size": 1,
                    "highlight": {
                        "fields": {"content": {"fragment_size": 200, "number_of_fragments": 1}},
                    },
                })
                ctx = ssl.create_default_context()
                req = urllib.request.Request(
                    url, data=body.encode(), headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                    hits = data.get("hits", {}).get("hits", [])
                    if hits:
                        hit = hits[0]
                        source = hit.get("_source", {})
                        highlight = hit.get("highlight", {}).get("content", [])
                        snippet_text = highlight[0] if highlight else None
                        if snippet_text and len(snippet_text) > 200:
                            snippet_text = snippet_text[:200]
                        snippets.append({
                            "document_id": doc_id,
                            "filename": source.get("source_filename", source.get("filename")),
                            "snippet": snippet_text,
                        })
                    else:
                        snippets.append({
                            "document_id": doc_id,
                            "filename": None,
                            "snippet": None,
                            "status": "source_unavailable",
                        })
            except Exception as e:
                logger.warning("OpenSearch snippet retrieval failed for doc %s: %s", doc_id, str(e)[:200])
                snippets.append({
                    "document_id": doc_id,
                    "filename": None,
                    "snippet": None,
                    "status": "source_unavailable",
                })
        return snippets

    # ------------------------------------------------------------------
    # Event extraction
    # ------------------------------------------------------------------

    def _extract_events(self, case_id: str, skip_snippets: bool = True) -> list[dict]:
        """Build timeline events from Aurora entities table (fast)."""
        aurora_dates: list[dict] = []
        aurora_other_entities: list[dict] = []
        try:
            with self._aurora.cursor() as cur:
                # Get date/event entities (simple query, no JOIN)
                cur.execute(
                    "SELECT canonical_name, entity_type, source_document_ids "
                    "FROM entities "
                    "WHERE case_file_id = %s AND LOWER(entity_type) IN ('date', 'event') "
                    "LIMIT 500",
                    (case_id,),
                )
                for row in cur.fetchall():
                    aurora_dates.append({
                        "name": row[0], "type": row[1],
                        "doc_refs": row[2] if row[2] else "[]",
                    })

                # Get non-date entities for co-occurrence (simple, no JOIN)
                cur.execute(
                    "SELECT canonical_name, entity_type, source_document_ids "
                    "FROM entities "
                    "WHERE case_file_id = %s AND LOWER(entity_type) NOT IN ('date', 'event') "
                    "LIMIT 2000",
                    (case_id,),
                )
                for row in cur.fetchall():
                    aurora_other_entities.append({
                        "name": row[0], "type": row[1],
                        "doc_refs": row[2] if row[2] else "[]",
                    })
        except Exception as e:
            logger.error("Aurora entity query failed for case %s: %s", case_id, str(e)[:500])

        # Build doc_id -> entities lookup for co-occurrence
        import json as _json
        doc_entities: dict[str, list[dict]] = {}
        for ent in aurora_other_entities:
            try:
                refs = _json.loads(ent["doc_refs"]) if isinstance(ent["doc_refs"], str) else ent["doc_refs"]
            except Exception:
                refs = []
            if isinstance(refs, list):
                for ref in refs[:5]:  # limit per entity
                    doc_id = str(ref)
                    if doc_id not in doc_entities:
                        doc_entities[doc_id] = []
                    doc_entities[doc_id].append({"name": ent["name"], "type": ent["type"]})

        # Build events
        events = []
        for date_ent in aurora_dates:
            timestamp = self._normalize_date(date_ent["name"])
            if timestamp is None:
                continue

            # Parse doc refs
            try:
                refs = _json.loads(date_ent["doc_refs"]) if isinstance(date_ent["doc_refs"], str) else date_ent["doc_refs"]
            except Exception:
                refs = []
            if not isinstance(refs, list):
                refs = []

            # Co-occurring entities from same documents
            co_entities: dict[str, dict] = {}
            entity_types = []
            for ref in refs[:5]:
                for ent in doc_entities.get(str(ref), [])[:10]:
                    key = ent["name"]
                    if key not in co_entities:
                        co_entities[key] = ent
                        entity_types.append(ent["type"] or "other")

            event_type = self._infer_event_type(entity_types)
            entities = list(co_entities.values())[:10]

            source_documents = [
                {"document_id": str(r), "filename": None, "snippet": None}
                for r in refs[:5]
            ]

            events.append({
                "event_id": str(uuid.uuid4()),
                "timestamp": timestamp,
                "event_type": event_type,
                "entities": entities,
                "source_documents": source_documents,
            })

        return events

    # ------------------------------------------------------------------
    # Clustering
    # ------------------------------------------------------------------

    def _cluster_events(self, events: list[dict], window_hours: int) -> list[dict]:
        """Group events within temporal proximity — relaxed overlap rules.

        window_hours=0 disables clustering.
        """
        if window_hours <= 0 or not events:
            return []

        window = timedelta(hours=window_hours)
        tight_window = timedelta(hours=window_hours / 2)
        used = set()
        clusters = []

        # Sort events by timestamp for clustering
        sorted_events = sorted(events, key=lambda e: e.get("timestamp", ""))

        def _get_doc_ids(evt):
            """Extract source document IDs from an event."""
            ids = set()
            for doc in evt.get("source_documents", []):
                if isinstance(doc, dict):
                    did = doc.get("document_id", "")
                    if did:
                        ids.add(str(did))
            return ids

        for i, evt in enumerate(sorted_events):
            if i in used:
                continue
            evt_ts = self._parse_iso(evt["timestamp"])
            if evt_ts is None:
                continue

            evt_entity_names = {e["name"] for e in evt.get("entities", []) if isinstance(e, dict)}
            evt_doc_ids = _get_doc_ids(evt)
            cluster_indices = [i]
            cluster_entity_names = set(evt_entity_names)
            cluster_doc_ids = set(evt_doc_ids)

            # Find all events within window sharing entities, documents, or tight temporal proximity
            for j in range(i + 1, len(sorted_events)):
                if j in used:
                    continue
                other = sorted_events[j]
                other_ts = self._parse_iso(other["timestamp"])
                if other_ts is None:
                    continue

                # Check temporal proximity to any event already in cluster
                in_window = False
                in_tight_window = False
                for ci in cluster_indices:
                    ci_ts = self._parse_iso(sorted_events[ci]["timestamp"])
                    if ci_ts:
                        delta = abs((other_ts - ci_ts).total_seconds())
                        if delta <= window.total_seconds():
                            in_window = True
                        if delta <= tight_window.total_seconds():
                            in_tight_window = True
                        if in_window:
                            break

                if not in_window:
                    continue

                # Check shared entities
                other_entity_names = {e["name"] for e in other.get("entities", []) if isinstance(e, dict)}
                has_entity_overlap = bool(cluster_entity_names & other_entity_names)

                # Check document co-occurrence
                other_doc_ids = _get_doc_ids(other)
                has_doc_overlap = bool(cluster_doc_ids & other_doc_ids)

                # Relaxed clustering: entity overlap OR document overlap OR tight temporal proximity
                if has_entity_overlap or has_doc_overlap or in_tight_window:
                    cluster_indices.append(j)
                    cluster_entity_names |= other_entity_names
                    cluster_doc_ids |= other_doc_ids

            if len(cluster_indices) >= 2:
                for ci in cluster_indices:
                    used.add(ci)

                cluster_events = [sorted_events[ci] for ci in cluster_indices]
                timestamps = [e["timestamp"] for e in cluster_events]

                # Shared entities = entities present in ALL cluster events
                all_entity_sets = [
                    {e["name"] for e in ce.get("entities", []) if isinstance(e, dict)}
                    for ce in cluster_events
                ]
                shared = set.intersection(*all_entity_sets) if all_entity_sets else set()
                # If no entity is in ALL events, use entities in at least 2 events
                if not shared:
                    from collections import Counter
                    name_counts = Counter()
                    for es in all_entity_sets:
                        for n in es:
                            name_counts[n] += 1
                    shared = {n for n, c in name_counts.items() if c >= 2}

                clusters.append({
                    "cluster_id": str(uuid.uuid4()),
                    "event_count": len(cluster_events),
                    "start_timestamp": min(timestamps),
                    "end_timestamp": max(timestamps),
                    "shared_entities": sorted(shared),
                    "event_ids": [e["event_id"] for e in cluster_events],
                })

        # Log cluster results
        logger.info("Clustering: %d events with %dh window → %d clusters",
                     len(events), window_hours, len(clusters))
        if len(clusters) == 0 and len(events) >= 10:
            logger.warning(
                "0 clusters for %d events (window=%dh). Check entity/document overlap.",
                len(events), window_hours,
            )

        return clusters

    @staticmethod
    def _compute_display_label(event: dict) -> str:
        """Build a human-readable label for a timeline event marker."""
        # Format date
        ts = event.get("timestamp", "")
        try:
            dt = datetime.strptime(ts.rstrip("Z"), "%Y-%m-%dT%H:%M:%S")
            formatted_date = dt.strftime("%b %d, %Y")  # e.g. "Mar 15, 2019"
        except (ValueError, AttributeError):
            formatted_date = ts[:10] if len(ts) >= 10 else ts

        entities = event.get("entities", [])
        if not entities:
            # Fall back to event type label + date
            event_type = event.get("event_type", "other")
            type_labels = {
                "communication": "Communication",
                "meeting": "Meeting",
                "financial_transaction": "Financial",
                "travel": "Travel",
                "legal_proceeding": "Legal",
                "document_creation": "Document",
                "other": "Other",
            }
            label = type_labels.get(event_type, "Event")
            return f"{label} — {formatted_date}"

        # Get top 2 entity names
        def _truncate_name(name: str) -> str:
            if len(name) > 25:
                return name[:22] + "..."
            return name

        names = []
        for ent in entities[:2]:
            name = ent.get("name", "") if isinstance(ent, dict) else str(ent)
            if name:
                names.append(_truncate_name(name))

        if not names:
            event_type = event.get("event_type", "other")
            type_labels = {
                "communication": "Communication",
                "meeting": "Meeting",
                "financial_transaction": "Financial",
                "travel": "Travel",
                "legal_proceeding": "Legal",
                "document_creation": "Document",
                "other": "Other",
            }
            label = type_labels.get(event_type, "Event")
            return f"{label} — {formatted_date}"

        entity_part = ", ".join(names)
        return f"{entity_part} — {formatted_date}"

    @staticmethod
    def _parse_iso(ts: str) -> datetime | None:
        """Parse an ISO 8601 timestamp string into a datetime."""
        try:
            return datetime.strptime(ts.rstrip("Z"), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        except (ValueError, AttributeError):
            return None

    # ------------------------------------------------------------------
    # Relevant range computation
    # ------------------------------------------------------------------

    def _compute_relevant_range(self, events: list[dict]) -> dict | None:
        """Find the smallest time window containing >= 80% of events."""
        if len(events) < 3:
            return None

        # Parse and sort timestamps
        timestamps = []
        for evt in events:
            ts = self._parse_iso(evt.get("timestamp", ""))
            if ts is not None:
                timestamps.append(ts)

        if len(timestamps) < 3:
            return None

        timestamps.sort()
        import math
        target_count = math.ceil(len(timestamps) * 0.8)

        if target_count >= len(timestamps):
            return {
                "start": timestamps[0].strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end": timestamps[-1].strftime("%Y-%m-%dT%H:%M:%SZ"),
            }

        best_span = None
        best_start = 0
        for i in range(len(timestamps) - target_count + 1):
            span = (timestamps[i + target_count - 1] - timestamps[i]).total_seconds()
            if best_span is None or span < best_span:
                best_span = span
                best_start = i

        return {
            "start": timestamps[best_start].strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": timestamps[best_start + target_count - 1].strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    # ------------------------------------------------------------------
    # Noise date filtering
    # ------------------------------------------------------------------

    def _filter_noise_dates(self, events: list[dict], noise_cutoff_year: int | None = None) -> tuple[list[dict], list[dict]]:
        """Split events into relevant and noise based on density analysis."""
        if not events:
            return ([], [])

        # Extract years from event timestamps
        event_years = []
        for evt in events:
            ts = evt.get("timestamp", "")
            try:
                dt = datetime.strptime(ts.rstrip("Z"), "%Y-%m-%dT%H:%M:%S")
                event_years.append(dt.year)
            except (ValueError, AttributeError):
                event_years.append(None)

        valid_years = [y for y in event_years if y is not None]
        if not valid_years:
            return (list(events), [])

        # If manual cutoff provided, use it directly
        if noise_cutoff_year is not None:
            relevant = []
            noise = []
            for evt, year in zip(events, event_years):
                if year is not None and year < noise_cutoff_year:
                    noise.append(evt)
                else:
                    relevant.append(evt)
            return (relevant, noise)

        # Check if all events fall within a 20-year window — no filtering needed
        min_year = min(valid_years)
        max_year = max(valid_years)
        if max_year - min_year <= 20:
            return (list(events), [])

        # Build year histogram
        year_counts: dict[int, int] = {}
        for y in valid_years:
            year_counts[y] = year_counts.get(y, 0) + 1

        # Find the largest contiguous block of active years (Density_Cluster)
        # where no gap between consecutive active years exceeds 5 years
        active_years = sorted(year_counts.keys())
        if len(active_years) <= 1:
            return (list(events), [])

        # Split into contiguous blocks
        blocks: list[list[int]] = []
        current_block = [active_years[0]]
        for i in range(1, len(active_years)):
            if active_years[i] - active_years[i - 1] <= 5:
                current_block.append(active_years[i])
            else:
                blocks.append(current_block)
                current_block = [active_years[i]]
        blocks.append(current_block)

        # Find the largest block (by event count)
        best_block = max(blocks, key=lambda b: sum(year_counts[y] for y in b))

        # Set auto cutoff to Density_Cluster start year minus 20
        auto_cutoff = best_block[0] - 20

        # Filter events
        relevant = []
        noise = []
        for evt, year in zip(events, event_years):
            if year is not None and year < auto_cutoff:
                noise.append(evt)
            else:
                relevant.append(evt)

        # If all events are noise (unlikely), return all as relevant
        if not relevant:
            return (list(events), [])

        return (relevant, noise)

    # ------------------------------------------------------------------
    # Phase detection
    # ------------------------------------------------------------------

    def _detect_phases(self, events: list[dict]) -> list[dict]:
        """Detect investigative phases from event type distribution."""
        if len(events) < 5:
            return []

        # Sort events by timestamp
        sorted_events = sorted(events, key=lambda e: e.get("timestamp", ""))

        # Divide into temporal thirds
        n = len(sorted_events)
        third = n // 3
        if third == 0:
            return []

        first_third = sorted_events[:third]
        middle_third = sorted_events[third:2 * third]
        last_third = sorted_events[2 * third:]

        def _type_counts(evts):
            counts: dict[str, int] = {}
            for e in evts:
                t = e.get("event_type", "other")
                counts[t] = counts.get(t, 0) + 1
            return counts

        first_types = _type_counts(first_third)
        middle_types = _type_counts(middle_third)
        last_types = _type_counts(last_third)

        phases = []

        # Analyze first third
        first_doc_other = first_types.get("document_creation", 0) + first_types.get("other", 0)
        first_total = sum(first_types.values())
        if first_total > 0:
            first_ts_start = first_third[0].get("timestamp", "")
            first_ts_end = first_third[-1].get("timestamp", "")
            if first_doc_other > first_total * 0.5:
                label = "Early Activity"
                desc = f"Initial period with {first_total} events, primarily document creation and background activity"
            else:
                # Check for financial/meeting activity
                first_active = first_types.get("financial_transaction", 0) + first_types.get("meeting", 0) + first_types.get("travel", 0)
                if first_active > first_total * 0.3:
                    label = "Escalation"
                    desc = f"Early escalation period with {first_total} events including financial transactions and meetings"
                else:
                    label = "Pre-Criminal Activity"
                    desc = f"Pre-criminal period with {first_total} events of mixed activity types"
            phases.append({
                "phase_id": str(uuid.uuid4()),
                "label": label,
                "start": first_ts_start,
                "end": first_ts_end,
                "description": desc,
                "event_count": first_total,
            })

        # Analyze middle third
        middle_total = sum(middle_types.values())
        if middle_total > 0:
            middle_ts_start = middle_third[0].get("timestamp", "")
            middle_ts_end = middle_third[-1].get("timestamp", "")
            middle_active = middle_types.get("financial_transaction", 0) + middle_types.get("meeting", 0) + middle_types.get("travel", 0)
            if middle_active > middle_total * 0.3:
                # Count unique persons in middle third
                persons = set()
                for e in middle_third:
                    for ent in e.get("entities", []):
                        if isinstance(ent, dict) and ent.get("type", "").lower() == "person":
                            persons.add(ent.get("name", ""))
                label = "Active Criminal Period"
                desc = f"Peak period of financial transactions and meetings involving {len(persons)} key persons"
            else:
                label = "Peak Activity"
                desc = f"Peak activity period with {middle_total} events across multiple categories"
            phases.append({
                "phase_id": str(uuid.uuid4()),
                "label": label,
                "start": middle_ts_start,
                "end": middle_ts_end,
                "description": desc,
                "event_count": middle_total,
            })

        # Analyze last third
        last_total = sum(last_types.values())
        if last_total > 0:
            last_ts_start = last_third[0].get("timestamp", "")
            last_ts_end = last_third[-1].get("timestamp", "")
            last_legal = last_types.get("legal_proceeding", 0)
            if last_legal > 0:
                label = "Legal Proceedings"
                desc = f"Legal proceedings phase with {last_legal} legal events out of {last_total} total"
            else:
                # Check if types shift from active to quieter
                last_active = last_types.get("financial_transaction", 0) + last_types.get("meeting", 0) + last_types.get("travel", 0)
                if last_active > last_total * 0.3:
                    label = "Peak Activity"
                    desc = f"Continued peak activity with {last_total} events"
                else:
                    label = "Post-Resolution"
                    desc = f"Post-resolution period with {last_total} events of reduced activity"
            phases.append({
                "phase_id": str(uuid.uuid4()),
                "label": label,
                "start": last_ts_start,
                "end": last_ts_end,
                "description": desc,
                "event_count": last_total,
            })

        # Detect investigation phase transition: if event types shift from non-legal to legal
        all_types = _type_counts(sorted_events)
        if all_types.get("legal_proceeding", 0) > 0:
            # Find first legal event
            for i, evt in enumerate(sorted_events):
                if evt.get("event_type") == "legal_proceeding":
                    # Check if there are non-legal events before it
                    if i > 0:
                        inv_start = sorted_events[max(0, i - 1)].get("timestamp", "")
                        inv_end = evt.get("timestamp", "")
                        phases.append({
                            "phase_id": str(uuid.uuid4()),
                            "label": "Investigation Phase",
                            "start": inv_start,
                            "end": inv_end,
                            "description": "Transition point where investigation activity begins, marked by first legal proceeding",
                            "event_count": 1,
                        })
                    break

        # If no phases were generated (all same type), return empty
        if not phases:
            return []

        # Sort phases by start timestamp
        phases.sort(key=lambda p: p.get("start", ""))
        return phases

    # ------------------------------------------------------------------
    # Gap detection
    # ------------------------------------------------------------------

    def _detect_gaps(self, events: list[dict], entity_names: list[str],
                     threshold_days: int) -> list[dict]:
        """Find per-entity temporal gaps exceeding threshold_days."""
        if not events or threshold_days <= 0:
            return []

        gaps = []
        threshold = timedelta(days=threshold_days)

        for entity_name in entity_names:
            # Collect events for this entity, sorted by timestamp
            entity_events = [
                e for e in events
                if any(ent["name"] == entity_name for ent in e.get("entities", []))
            ]
            entity_events.sort(key=lambda e: e.get("timestamp", ""))

            for i in range(len(entity_events) - 1):
                ts_before = self._parse_iso(entity_events[i]["timestamp"])
                ts_after = self._parse_iso(entity_events[i + 1]["timestamp"])
                if ts_before is None or ts_after is None:
                    continue

                gap_duration = ts_after - ts_before
                if gap_duration >= threshold:
                    gaps.append({
                        "entity_name": entity_name,
                        "gap_start": entity_events[i]["timestamp"],
                        "gap_end": entity_events[i + 1]["timestamp"],
                        "gap_days": gap_duration.days,
                        "event_before_id": entity_events[i]["event_id"],
                        "event_after_id": entity_events[i + 1]["event_id"],
                    })

        return gaps

    # ------------------------------------------------------------------
    # Narrative header generation
    # ------------------------------------------------------------------

    def _generate_narrative_header(self, events: list[dict], relevant_range: dict | None, phases: list[dict]) -> str:
        """Generate a one-sentence AI narrative header for the timeline."""
        if not events:
            return "No timeline events available."

        # Compute stats for prompt and fallback
        event_count = len(events)

        # Entity counts by type
        entity_type_counts: dict[str, int] = {}
        unique_entities: dict[str, set] = {}
        for evt in events:
            for ent in evt.get("entities", []):
                if isinstance(ent, dict):
                    etype = ent.get("type", "other")
                    ename = ent.get("name", "")
                else:
                    etype = "other"
                    ename = str(ent)
                if etype not in unique_entities:
                    unique_entities[etype] = set()
                unique_entities[etype].add(ename)
        for etype, names in unique_entities.items():
            entity_type_counts[etype] = len(names)

        # Event type counts
        event_type_counts: dict[str, int] = {}
        for evt in events:
            t = evt.get("event_type", "other")
            event_type_counts[t] = event_type_counts.get(t, 0) + 1

        # Time span
        if relevant_range:
            time_span = f"{relevant_range['start'][:4]}–{relevant_range['end'][:4]}"
        else:
            timestamps = sorted(e.get("timestamp", "") for e in events if e.get("timestamp"))
            if timestamps:
                time_span = f"{timestamps[0][:4]}–{timestamps[-1][:4]}"
            else:
                time_span = "unknown period"

        # Phase labels
        phase_labels = [p.get("label", "") for p in phases if p.get("label")]

        # Build fallback string
        parts = [f"{event_count} events"]
        if time_span:
            parts.append(f"from {time_span}")
        if entity_type_counts.get("person"):
            parts.append(f"involving {entity_type_counts['person']} persons")
        if entity_type_counts.get("location"):
            parts.append(f"across {entity_type_counts['location']} locations")
        top_types = sorted(event_type_counts.items(), key=lambda x: -x[1])[:3]
        type_parts = []
        for t, c in top_types:
            type_labels = {
                "communication": "communications", "meeting": "meetings",
                "financial_transaction": "financial transactions", "travel": "travel events",
                "legal_proceeding": "legal proceedings", "document_creation": "documents",
                "other": "other events",
            }
            type_parts.append(f"{c} {type_labels.get(t, t)}")
        if type_parts:
            parts.append(f"with {', '.join(type_parts)}")
        fallback = " ".join(parts)

        # Try Bedrock for AI narrative
        try:
            prompt = (
                f"Write a single sentence investigative summary for a timeline with:\n"
                f"- {event_count} events spanning {time_span}\n"
                f"- Entity counts: {json.dumps(entity_type_counts)}\n"
                f"- Top event types: {json.dumps(event_type_counts)}\n"
                f"- Phases detected: {', '.join(phase_labels) if phase_labels else 'none'}\n\n"
                f"Write ONE sentence in investigative language. Example style: "
                f"'Criminal activity spanning 1999–2019 involving 12 key persons across 4 locations "
                f"with 8 financial transactions and 15 communications'\n"
                f"Respond with ONLY the sentence, no quotes or extra text."
            )

            resp = self._bedrock.invoke_model(
                modelId=BEDROCK_MODEL_ID,
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
            if text:
                return text
        except Exception as exc:
            logger.warning("Narrative header Bedrock call failed, using fallback: %s", str(exc)[:200])

        return fallback

    # ------------------------------------------------------------------
    # Main orchestrator
    # ------------------------------------------------------------------

    def reconstruct_timeline(self, case_id: str, clustering_window_hours: int = 48,
                              gap_threshold_days: int = 30, skip_snippets: bool = True,
                              noise_cutoff_year: int | None = None) -> dict:
        """Orchestrate event extraction, clustering, and gap detection.

        Returns dict with events, clusters, gaps, summary, and new intelligence fields.
        """
        # Extract events
        events = self._extract_events(case_id, skip_snippets=skip_snippets)

        # Compute display_label for each event
        for evt in events:
            evt["display_label"] = self._compute_display_label(evt)

        # Filter noise dates
        relevant_events, noise_events = self._filter_noise_dates(events, noise_cutoff_year)

        # Sort relevant events ascending by timestamp
        relevant_events.sort(key=lambda e: e.get("timestamp", ""))

        # Compute relevant range from relevant events
        relevant_range = self._compute_relevant_range(relevant_events)

        # Build noise filter summary
        noise_filter_summary = {}
        if noise_events:
            noise_years = []
            for ne in noise_events:
                try:
                    dt = datetime.strptime(ne.get("timestamp", "").rstrip("Z"), "%Y-%m-%dT%H:%M:%S")
                    noise_years.append(dt.year)
                except (ValueError, AttributeError):
                    pass
            auto_cutoff = noise_cutoff_year if noise_cutoff_year is not None else (min(noise_years) if noise_years else 0)
            # Compute actual auto cutoff from density analysis
            if noise_cutoff_year is None and relevant_events:
                try:
                    rel_years = []
                    for re_evt in relevant_events:
                        dt = datetime.strptime(re_evt.get("timestamp", "").rstrip("Z"), "%Y-%m-%dT%H:%M:%S")
                        rel_years.append(dt.year)
                    if rel_years:
                        auto_cutoff = min(rel_years)
                except (ValueError, AttributeError):
                    pass
            noise_filter_summary = {
                "auto_cutoff_year": auto_cutoff,
                "events_filtered": len(noise_events),
                "relevant_range_start": relevant_range["start"] if relevant_range else (relevant_events[0]["timestamp"] if relevant_events else ""),
                "relevant_range_end": relevant_range["end"] if relevant_range else (relevant_events[-1]["timestamp"] if relevant_events else ""),
            }
        else:
            # No noise filtered
            noise_filter_summary = {
                "auto_cutoff_year": 0,
                "events_filtered": 0,
                "relevant_range_start": relevant_range["start"] if relevant_range else "",
                "relevant_range_end": relevant_range["end"] if relevant_range else "",
            }

        # Collect all entity names for gap detection (from relevant events only)
        all_entity_names = set()
        for evt in relevant_events:
            for ent in evt.get("entities", []):
                if isinstance(ent, dict):
                    all_entity_names.add(ent["name"])

        # Cluster relevant events only
        clusters = self._cluster_events(relevant_events, clustering_window_hours)

        # Detect gaps on relevant events only
        gaps = self._detect_gaps(relevant_events, sorted(all_entity_names), gap_threshold_days)

        # Detect phases on relevant events
        phases = self._detect_phases(relevant_events)

        # Generate narrative header
        narrative_header = self._generate_narrative_header(relevant_events, relevant_range, phases)

        return {
            "events": relevant_events,
            "clusters": clusters,
            "gaps": gaps,
            "summary": {
                "total_events": len(relevant_events),
                "total_entities": len(all_entity_names),
                "total_clusters": len(clusters),
                "total_gaps": len(gaps),
            },
            "filtered_noise_events": noise_events,
            "noise_filter_summary": noise_filter_summary,
            "relevant_range": relevant_range,
            "phases": phases,
            "narrative_header": narrative_header,
        }

    # ------------------------------------------------------------------
    # AI analysis via Bedrock Claude
    # ------------------------------------------------------------------

    def generate_ai_analysis(self, case_id: str, events: list[dict],
                              gaps: list[dict]) -> dict:
        """Send timeline data to Bedrock Claude for temporal pattern analysis."""
        # Build a concise summary for the prompt
        event_summary = []
        for evt in events[:100]:  # Limit to avoid token overflow
            ents = evt.get("entities", [])
            if isinstance(ents, str):
                entities_str = ents
            elif isinstance(ents, list):
                entities_str = ", ".join(
                    (f"{e['name']} ({e['type']})" if isinstance(e, dict) else str(e))
                    for e in ents
                )
            else:
                entities_str = str(ents)
            event_summary.append(
                f"- {evt.get('timestamp', 'unknown')}: {evt.get('event_type', 'other')} "
                f"involving {entities_str or 'unknown entities'}"
            )

        gap_summary = []
        for gap in gaps:
            gap_summary.append(
                f"- {gap.get('entity_name', 'unknown')}: {gap.get('gap_days', '?')}-day gap "
                f"from {gap.get('gap_start', '?')} to {gap.get('gap_end', '?')}"
            )

        prompt = (
            f"You are an expert investigative analyst. Analyze the following timeline "
            f"of {len(events)} events for case {case_id}.\n\n"
            f"EVENTS:\n" + "\n".join(event_summary) + "\n\n"
            f"TEMPORAL GAPS:\n" + ("\n".join(gap_summary) if gap_summary else "None detected") + "\n\n"
            f"Provide a structured analysis as JSON with these exact keys:\n"
            f'- "chronological_patterns": string describing key chronological patterns\n'
            f'- "escalation_trends": string describing any escalation or de-escalation trends\n'
            f'- "clustering_significance": string explaining what event clusters reveal\n'
            f'- "gap_interpretation": string interpreting the temporal gaps\n'
            f'- "cross_entity_coordination": string describing coordination between entities\n'
            f'- "recommended_followups": array of strings with recommended investigative follow-ups\n\n'
            f"Respond ONLY with the JSON object, no other text."
        )

        try:
            resp = self._bedrock.invoke_model(
                modelId=BEDROCK_MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 2000,
                    "messages": [{"role": "user", "content": prompt}],
                }),
            )
            body = json.loads(resp["body"].read())
            text = body.get("content", [{}])[0].get("text", "")

            analysis = json.loads(text)
            if not isinstance(analysis, dict):
                raise ValueError("Expected JSON object from Bedrock")

            # Ensure all required keys are present
            required_keys = [
                "chronological_patterns", "escalation_trends",
                "clustering_significance", "gap_interpretation",
                "cross_entity_coordination", "recommended_followups",
            ]
            for key in required_keys:
                if key not in analysis:
                    analysis[key] = "" if key != "recommended_followups" else []

            return {"analysis": analysis}

        except Exception as exc:
            logger.error("Bedrock AI analysis failed for case %s: %s", case_id, str(exc)[:200])
            raise
