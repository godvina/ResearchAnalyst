"""Pattern discovery service — graph traversal and vector similarity.

Discovers patterns using Neptune graph traversal algorithms (centrality,
community detection, shortest path) and Aurora pgvector semantic clustering,
then combines results into a unified PatternReport.

Uses Neptune HTTP API (POST /gremlin) instead of WebSocket-based gremlinpython
to avoid VPC Lambda cold start timeouts.
"""

import json
import logging
import os
import ssl
import time
import urllib.request
import urllib.error
import uuid
from datetime import datetime, timezone
from typing import Any, Protocol

from db.connection import ConnectionManager
from models.pattern import Pattern, PatternReport
from models.pattern import EvidenceModality, PatternQuestion, RawPattern, TopPatternReport

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

NEPTUNE_ENDPOINT = os.environ.get("NEPTUNE_ENDPOINT", "")
NEPTUNE_PORT = os.environ.get("NEPTUNE_PORT", "8182")
SIMILARITY_THRESHOLD = 0.75
TOP_CENTRALITY_NODES = 5
BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
BEDROCK_SYNTHESIS_MODEL_ID = "us.anthropic.claude-3-haiku-20240307-v1:0"
NEPTUNE_TIMEOUT_THRESHOLD = 15.0  # seconds — skip Bedrock if Neptune queries exceed this


def _looks_like_date(text: str) -> bool:
    """Check if a string looks like a date (e.g., '2017-09-06', 'Fri 4/28/2017')."""
    import re
    if re.match(r"\d{4}-\d{2}-\d{2}", text):
        return True
    if re.match(r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+\d{1,2}/\d{1,2}/\d{4}", text):
        return True
    if re.match(r"\d{1,2}/\d{1,2}/\d{4}", text):
        return True
    return False


class BedrockClient(Protocol):
    def invoke_model(self, **kwargs: Any) -> Any: ...


def _gremlin_query(query: str) -> list:
    """Execute a Gremlin query via Neptune HTTP API and return results."""
    url = f"https://{NEPTUNE_ENDPOINT}:{NEPTUNE_PORT}/gremlin"
    data = json.dumps({"gremlin": query}).encode("utf-8")
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            result = body.get("result", {}).get("data", {})
            logger.info("Raw result type: %s, keys: %s", type(result).__name__, list(result.keys()) if isinstance(result, dict) else "N/A")
            if isinstance(result, dict) and "@value" in result:
                parsed = _parse_graphson(result["@value"])
                logger.info("Parsed %d items, sample: %s", len(parsed), str(parsed[:2])[:300])
                return parsed
            if isinstance(result, list):
                return _parse_graphson(result)
            return [result] if result else []
    except Exception as e:
        logger.error("Neptune query error: %s | query: %s", str(e)[:200], query[:200])
        return []


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
        # Flat list of alternating key-value pairs
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


def _entity_label(case_id: str) -> str:
    return f"Entity_{case_id}"


class PatternDiscoveryService:
    """Discovers patterns using graph traversal and vector similarity."""

    def __init__(self, neptune_conn: Any, aurora_conn: ConnectionManager, bedrock_client: Any) -> None:
        self._aurora = aurora_conn
        self._bedrock = bedrock_client

    # ------------------------------------------------------------------
    # Top 5 Investigative Patterns — scoring helpers
    # ------------------------------------------------------------------

    # Cross-modal bonus lookup: number of distinct modalities → bonus multiplier
    _CROSS_MODAL_BONUS = {1: 0.5, 2: 0.75, 3: 0.9, 4: 1.0}

    def _score_pattern(self, pattern: dict) -> float:
        """Compute composite score for a pattern.

        Formula: evidence_strength × cross_modal_bonus × novelty_score

        ``pattern`` must contain keys ``evidence_strength``, ``novelty_score``,
        and ``modalities`` (a list of :class:`EvidenceModality` values or
        equivalent strings).  The cross-modal bonus is derived from the number
        of distinct modalities.
        """
        evidence_strength = float(pattern.get("evidence_strength", 0.0))
        novelty_score = float(pattern.get("novelty_score", 0.0))
        modalities = pattern.get("modalities", [])

        num_modalities = len(set(modalities))
        cross_modal_bonus = self._CROSS_MODAL_BONUS.get(
            num_modalities, 1.0 if num_modalities >= 4 else 0.5
        )

        return evidence_strength * cross_modal_bonus * novelty_score

    @staticmethod
    def _classify_corroboration(modalities: list) -> str:
        """Classify corroboration level based on the number of distinct modalities.

        Returns:
            ``"strong"`` for 3+ modalities, ``"moderate"`` for 2, or
            ``"single_source"`` for 1 (or 0).
        """
        count = len(set(modalities))
        if count >= 3:
            return "strong"
        if count == 2:
            return "moderate"
        return "single_source"

    @staticmethod
    def _filter_low_quality_patterns(patterns: list[dict]) -> list[dict]:
        """Remove patterns that are noise rather than signal.

        Filters:
        - Patterns where all entities have 0 connections (no network)
        - Patterns with unreasonably high connection counts (>5000, data quality issue)
        - Patterns with composite_score of 0
        - Patterns with only 1 entity and no cross-modal evidence
        """
        MIN_COMPOSITE_SCORE = 0.01
        MAX_REASONABLE_DEGREE = 5000

        filtered = []
        for p in patterns:
            # Skip zero-score patterns
            if p.get("composite_score", 0) < MIN_COMPOSITE_SCORE:
                continue

            entities = p.get("entities", [])

            # Skip patterns with unreasonably high degree (data quality noise)
            has_absurd_degree = False
            for e in entities:
                degree = e.get("degree", 0)
                if isinstance(degree, dict):
                    degree = degree.get("@value", 0)
                if int(degree) > MAX_REASONABLE_DEGREE:
                    has_absurd_degree = True
                    break
            if has_absurd_degree:
                logger.debug("Filtered pattern with degree > %d: %s", MAX_REASONABLE_DEGREE,
                             [e.get("name") for e in entities[:3]])
                continue

            # Skip single-entity patterns with no cross-modal evidence
            modalities = p.get("modalities", [])
            if len(entities) <= 1 and len(set(
                m.value if hasattr(m, "value") else str(m) for m in modalities
            )) <= 1:
                continue

            filtered.append(p)

        logger.info("Pattern quality filter: %d → %d patterns", len(patterns), len(filtered))
        return filtered

    # ------------------------------------------------------------------
    # Multi-modal Neptune query methods (Top 5 Investigative Patterns)
    # ------------------------------------------------------------------

    def _query_text_entity_patterns(self, case_id: str) -> list:
        """Query RELATED_TO edges for text entity centrality and clusters.

        Returns a list of dicts with keys matching RawPattern fields,
        modality="text".
        """
        label = _entity_label(case_id)
        try:
            # Get top entities by degree centrality via RELATED_TO edges
            query = (
                f"g.V().hasLabel('{_escape(label)}').limit(200)"
                f".project('name','type','degree','neighbors')"
                f".by('canonical_name')"
                f".by('entity_type')"
                f".by(bothE('RELATED_TO').count())"
                f".by(both('RELATED_TO').hasLabel('{_escape(label)}').values('canonical_name').dedup().fold())"
            )
            results = _gremlin_query(query)
            if not results:
                return []

            # Parse nodes and sort by degree
            nodes = []
            for r in results:
                if not isinstance(r, dict):
                    continue
                degree = r.get("degree", 0)
                if isinstance(degree, dict):
                    degree = degree.get("@value", 0)
                neighbors = r.get("neighbors", [])
                if isinstance(neighbors, dict) and "@value" in neighbors:
                    neighbors = neighbors["@value"]
                if not isinstance(neighbors, list):
                    neighbors = []
                nodes.append({
                    "name": r.get("name", ""),
                    "type": r.get("type", ""),
                    "degree": int(degree),
                    "neighbors": [str(n) for n in neighbors],
                })
            nodes.sort(key=lambda x: x["degree"], reverse=True)

            # Build patterns from high-centrality clusters
            patterns = []
            seen_entities: set[str] = set()
            for node in nodes:
                if node["degree"] == 0 or node["name"] in seen_entities:
                    continue
                # Cluster: the node plus its neighbors
                cluster_names = [node["name"]] + [
                    n for n in node["neighbors"] if n not in seen_entities
                ]
                if len(cluster_names) < 2:
                    continue
                seen_entities.update(cluster_names)

                source_count = node["degree"]
                unexpected_connections = len(cluster_names) - 1
                patterns.append({
                    "entities": [
                        {"name": name, "type": node["type"] if name == node["name"] else "unknown", "role": "hub" if name == node["name"] else "connected"}
                        for name in cluster_names[:10]
                    ],
                    "modalities": [EvidenceModality.TEXT],
                    "source_documents": [],
                    "source_images": [],
                    "face_crops": [],
                    "evidence_strength": min(1.0, source_count / 10),
                    "cross_modal_score": 0.5,
                    "novelty_score": min(1.0, unexpected_connections / 5),
                })
            return patterns

        except Exception as exc:
            logger.error("_query_text_entity_patterns failed for case %s: %s", case_id, str(exc)[:200])
            return []

    def _query_visual_entity_patterns(self, case_id: str) -> list:
        """Query DETECTED_IN edges for visual label co-occurrence patterns.

        Returns a list of dicts with keys matching RawPattern fields,
        modality="visual".
        """
        visual_label = f"VisualEntity_{case_id}"
        try:
            # Find visual entities that co-occur in the same images
            query = (
                f"g.V().hasLabel('{_escape(visual_label)}').limit(200)"
                f".project('name','type','images','degree')"
                f".by('canonical_name')"
                f".by('entity_type')"
                f".by(out('DETECTED_IN').id().fold())"
                f".by(outE('DETECTED_IN').count())"
            )
            results = _gremlin_query(query)
            if not results:
                return []

            # Build image → labels mapping for co-occurrence
            image_labels: dict[str, list[dict]] = {}
            for r in results:
                if not isinstance(r, dict):
                    continue
                images = r.get("images", [])
                if isinstance(images, dict) and "@value" in images:
                    images = images["@value"]
                if not isinstance(images, list):
                    images = []
                entity_info = {
                    "name": r.get("name", ""),
                    "type": r.get("type", ""),
                }
                for img_id in images:
                    img_key = str(img_id)
                    image_labels.setdefault(img_key, []).append(entity_info)

            # Find co-occurring label groups (2+ labels in same image)
            patterns = []
            seen_groups: set[frozenset[str]] = set()
            for img_key, labels in image_labels.items():
                if len(labels) < 2:
                    continue
                group_key = frozenset(l["name"] for l in labels)
                if group_key in seen_groups:
                    continue
                seen_groups.add(group_key)

                source_count = len([
                    k for k, v in image_labels.items()
                    if frozenset(l["name"] for l in v) == group_key
                ])
                unexpected_connections = len(labels) - 1
                patterns.append({
                    "entities": [
                        {"name": l["name"], "type": l["type"], "role": "visual_label"}
                        for l in labels[:10]
                    ],
                    "modalities": [EvidenceModality.VISUAL],
                    "source_documents": [],
                    "source_images": [img_key],
                    "face_crops": [],
                    "evidence_strength": min(1.0, source_count / 10),
                    "cross_modal_score": 0.5,
                    "novelty_score": min(1.0, unexpected_connections / 5),
                })
            return patterns

        except Exception as exc:
            logger.error("_query_visual_entity_patterns failed for case %s: %s", case_id, str(exc)[:200])
            return []

    def _query_face_match_patterns(self, case_id: str) -> list:
        """Query HAS_FACE_MATCH edges for person-face connections.

        Returns a list of dicts with keys matching RawPattern fields,
        modality="face".
        """
        face_label = f"FaceCrop_{case_id}"
        entity_label_str = _entity_label(case_id)
        try:
            # Find face crops matched to entities
            query = (
                f"g.V().hasLabel('{_escape(face_label)}').limit(200)"
                f".project('crop_id','crop_s3_key','matched_entity','similarity')"
                f".by(id())"
                f".by('s3_key')"
                f".by(out('HAS_FACE_MATCH').hasLabel('{_escape(entity_label_str)}').values('canonical_name').fold())"
                f".by(outE('HAS_FACE_MATCH').values('similarity').fold())"
            )
            results = _gremlin_query(query)
            if not results:
                return []

            # Group by matched entity to build patterns
            entity_faces: dict[str, list[dict]] = {}
            for r in results:
                if not isinstance(r, dict):
                    continue
                matched = r.get("matched_entity", [])
                if isinstance(matched, dict) and "@value" in matched:
                    matched = matched["@value"]
                if not isinstance(matched, list) or not matched:
                    continue
                similarities = r.get("similarity", [])
                if isinstance(similarities, dict) and "@value" in similarities:
                    similarities = similarities["@value"]
                if not isinstance(similarities, list):
                    similarities = []

                crop_s3_key = r.get("crop_s3_key", "")
                for i, entity_name in enumerate(matched):
                    entity_name = str(entity_name)
                    sim = float(similarities[i]) if i < len(similarities) else 0.0
                    entity_faces.setdefault(entity_name, []).append({
                        "crop_s3_key": str(crop_s3_key),
                        "entity_name": entity_name,
                        "similarity": sim,
                    })

            patterns = []
            for entity_name, faces in entity_faces.items():
                source_count = len(faces)
                unexpected_connections = len(faces)
                patterns.append({
                    "entities": [
                        {"name": entity_name, "type": "PERSON", "role": "matched_identity"},
                    ],
                    "modalities": [EvidenceModality.FACE],
                    "source_documents": [],
                    "source_images": [],
                    "face_crops": faces,
                    "evidence_strength": min(1.0, source_count / 10),
                    "cross_modal_score": 0.5,
                    "novelty_score": min(1.0, unexpected_connections / 5),
                })
            return patterns

        except Exception as exc:
            logger.error("_query_face_match_patterns failed for case %s: %s", case_id, str(exc)[:200])
            return []

    def _query_cooccurrence_patterns(self, case_id: str) -> list:
        """Query CO_OCCURS_WITH edges for cross-document entity co-occurrence.

        Returns a list of dicts with keys matching RawPattern fields,
        modality="cooccurrence".
        """
        label = _entity_label(case_id)
        try:
            # Find entity pairs connected by CO_OCCURS_WITH edges
            query = (
                f"g.V().hasLabel('{_escape(label)}').limit(200)"
                f".outE('CO_OCCURS_WITH').limit(500)"
                f".project('src_name','src_type','tgt_name','tgt_type','weight')"
                f".by(outV().values('canonical_name'))"
                f".by(outV().values('entity_type'))"
                f".by(inV().values('canonical_name'))"
                f".by(inV().values('entity_type'))"
                f".by(coalesce(values('weight'), constant(1)))"
            )
            results = _gremlin_query(query)
            if not results:
                return []

            # Group co-occurring pairs and build patterns
            patterns = []
            seen_pairs: set[frozenset[str]] = set()
            for r in results:
                if not isinstance(r, dict):
                    continue
                src_name = r.get("src_name", "")
                tgt_name = r.get("tgt_name", "")
                if not src_name or not tgt_name:
                    continue
                pair_key = frozenset([src_name, tgt_name])
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                weight = r.get("weight", 1)
                if isinstance(weight, dict):
                    weight = weight.get("@value", 1)
                weight = int(weight)

                source_count = weight
                unexpected_connections = 1  # each co-occurrence pair is one connection
                patterns.append({
                    "entities": [
                        {"name": src_name, "type": r.get("src_type", ""), "role": "co_occurring"},
                        {"name": tgt_name, "type": r.get("tgt_type", ""), "role": "co_occurring"},
                    ],
                    "modalities": [EvidenceModality.COOCCURRENCE],
                    "source_documents": [],
                    "source_images": [],
                    "face_crops": [],
                    "evidence_strength": min(1.0, source_count / 10),
                    "cross_modal_score": 0.5,
                    "novelty_score": min(1.0, unexpected_connections / 5),
                })
            return patterns

        except Exception as exc:
            logger.error("_query_cooccurrence_patterns failed for case %s: %s", case_id, str(exc)[:200])
            return []

    # ------------------------------------------------------------------
    # Top 5 Investigative Patterns — orchestrator + AI synthesis
    # ------------------------------------------------------------------

    def discover_top_patterns(self, case_id: str) -> dict:
        """Query all four modalities, score, rank, and synthesize top 5 questions.

        Returns a dict matching :class:`TopPatternReport` structure with
        patterns indexed 1-5.  Tracks total Neptune query time; if it
        exceeds ``NEPTUNE_TIMEOUT_THRESHOLD`` (15 s), Bedrock synthesis is
        skipped and fallback templates are used instead.

        Results are cached in Aurora ``top_pattern_cache`` for 15 minutes.
        """
        # --- Cache check ---
        try:
            with self._aurora.cursor() as cur:
                cur.execute(
                    "SELECT top_patterns, cached_at FROM top_pattern_cache WHERE case_file_id = %s",
                    (case_id,),
                )
                row = cur.fetchone()
                if row:
                    cached_patterns, cached_at = row
                    age_seconds = (datetime.now(timezone.utc) - cached_at).total_seconds()
                    if age_seconds < 900:  # 15 minutes
                        logger.info("Cache hit for case %s (age %.0fs)", case_id, age_seconds)
                        if isinstance(cached_patterns, str):
                            return json.loads(cached_patterns)
                        return cached_patterns
                    logger.info("Cache stale for case %s (age %.0fs)", case_id, age_seconds)
        except Exception as exc:
            logger.warning("Cache check failed for case %s: %s", case_id, str(exc)[:200])

        neptune_start = time.monotonic()

        # 1. Query all four modalities
        text_patterns = self._query_text_entity_patterns(case_id)
        visual_patterns = self._query_visual_entity_patterns(case_id)
        face_patterns = self._query_face_match_patterns(case_id)
        cooccurrence_patterns = self._query_cooccurrence_patterns(case_id)

        neptune_elapsed = time.monotonic() - neptune_start
        logger.info(
            "Neptune queries for case %s completed in %.2fs (text=%d, visual=%d, face=%d, cooccur=%d)",
            case_id, neptune_elapsed,
            len(text_patterns), len(visual_patterns),
            len(face_patterns), len(cooccurrence_patterns),
        )

        # 2. Merge all raw patterns into one list
        all_patterns: list[dict] = (
            text_patterns + visual_patterns + face_patterns + cooccurrence_patterns
        )

        # 3. Merge patterns that share entities across modalities
        all_patterns = self._merge_cross_modal_patterns(all_patterns)

        # 4. Score each pattern and sort descending by composite_score
        for p in all_patterns:
            p["composite_score"] = self._score_pattern(p)
        all_patterns.sort(key=lambda p: p.get("composite_score", 0.0), reverse=True)

        # 4b. Filter out low-quality patterns (noise reduction)
        all_patterns = self._filter_low_quality_patterns(all_patterns)

        # 5. Take top 5 (or fewer)
        top = all_patterns[:5]
        fewer_explanation = ""
        if len(top) < 5:
            available = len(top)
            fewer_explanation = (
                f"Only {available} distinct pattern(s) discovered. "
                f"Text: {len(text_patterns)}, Visual: {len(visual_patterns)}, "
                f"Face: {len(face_patterns)}, Co-occurrence: {len(cooccurrence_patterns)}."
            )

        # 6. Synthesize investigative questions
        skip_bedrock = neptune_elapsed > NEPTUNE_TIMEOUT_THRESHOLD
        if skip_bedrock:
            logger.warning(
                "Neptune queries took %.2fs (>%.0fs threshold) — using fallback templates",
                neptune_elapsed, NEPTUNE_TIMEOUT_THRESHOLD,
            )
            questions = self._generate_fallback_questions(top)
        else:
            questions = self._synthesize_questions(case_id, top)

        # 7. Assign 1-based indices
        for i, q in enumerate(questions):
            q["index"] = i + 1

        # 8. Build the report dict matching TopPatternReport structure
        report = {
            "case_file_id": case_id,
            "patterns": questions,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "fewer_patterns_explanation": fewer_explanation,
        }

        # --- Cache write ---
        try:
            with self._aurora.cursor() as cur:
                cur.execute(
                    "INSERT INTO top_pattern_cache (case_file_id, cached_at, top_patterns) "
                    "VALUES (%s, now(), %s) "
                    "ON CONFLICT (case_file_id) DO UPDATE "
                    "SET cached_at = now(), top_patterns = EXCLUDED.top_patterns",
                    (case_id, json.dumps(report, default=str)),
                )
            logger.info("Cached top patterns for case %s", case_id)
        except Exception as exc:
            logger.error("Cache write failed for case %s: %s", case_id, str(exc)[:200])

        return report

    @staticmethod
    def _merge_cross_modal_patterns(patterns: list[dict]) -> list[dict]:
        """Merge patterns that share entities across different modalities.

        Two patterns are considered mergeable when they share at least one
        entity name *and* come from different modalities.  Merged patterns
        combine their modality lists, source documents, source images, and
        face crops, and take the maximum evidence_strength and novelty_score.
        """
        if not patterns:
            return []

        merged: list[dict] = []
        used: set[int] = set()

        for i, pa in enumerate(patterns):
            if i in used:
                continue
            current = dict(pa)
            # Ensure modalities is a mutable list
            current["modalities"] = list(current.get("modalities", []))
            current["source_documents"] = list(current.get("source_documents", []))
            current["source_images"] = list(current.get("source_images", []))
            current["face_crops"] = list(current.get("face_crops", []))

            names_a = {e.get("name", "") for e in current.get("entities", []) if e.get("name")}

            for j in range(i + 1, len(patterns)):
                if j in used:
                    continue
                pb = patterns[j]
                names_b = {e.get("name", "") for e in pb.get("entities", []) if e.get("name")}
                shared = names_a & names_b
                mods_a = set(current["modalities"])
                mods_b = set(pb.get("modalities", []))

                if shared and mods_a != mods_b:
                    # Merge pb into current
                    used.add(j)
                    # Combine modalities (deduplicated)
                    for m in pb.get("modalities", []):
                        if m not in current["modalities"]:
                            current["modalities"].append(m)
                    # Combine supporting evidence
                    current["source_documents"].extend(pb.get("source_documents", []))
                    current["source_images"].extend(pb.get("source_images", []))
                    current["face_crops"].extend(pb.get("face_crops", []))
                    # Add new entities not already present
                    existing_names = {e.get("name", "") for e in current.get("entities", [])}
                    for e in pb.get("entities", []):
                        if e.get("name") and e["name"] not in existing_names:
                            current["entities"].append(e)
                            existing_names.add(e["name"])
                    # Take max strengths
                    current["evidence_strength"] = max(
                        current.get("evidence_strength", 0.0),
                        pb.get("evidence_strength", 0.0),
                    )
                    current["novelty_score"] = max(
                        current.get("novelty_score", 0.0),
                        pb.get("novelty_score", 0.0),
                    )

            merged.append(current)
        return merged

    # Investigator persona for narrative synthesis (modeled after LeadGeneratorService.INVESTIGATOR_PERSONA)
    NARRATIVE_SYNTHESIS_PERSONA = (
        "You are a senior federal investigative analyst with 20+ years of experience "
        "in complex multi-jurisdictional investigations. Generate narrative investigation "
        "leads that explain WHY a finding matters investigatively. Cite specific evidence "
        "documents and entity connections by name. Each narrative must be actionable — "
        "describe relationship context, gaps, anomalies, and what an investigator should do next."
    )

    def _synthesize_questions(self, case_id: str, patterns: list) -> list:
        """Call Bedrock Claude to convert top patterns into investigative questions
        with narrative explanations.

        Builds a prompt with entity names, types, visual labels, face match
        identities, and co-occurring documents for each pattern.  Uses the
        investigator persona to generate both an investigative question and a
        3-5 sentence narrative explanation for each pattern.

        On Bedrock failure, generates fallback questions using a template.
        Returns a list of dicts matching :class:`PatternQuestion` structure
        with an additional ``narrative`` field.
        """
        if not patterns:
            return []

        # Build the prompt with multi-modal evidence context
        pattern_descriptions = []
        for idx, p in enumerate(patterns, 1):
            entities = p.get("entities", [])
            entity_desc = ", ".join(
                f"{e.get('name', '?')} ({e.get('type', '?')})" for e in entities[:10]
            )
            modalities = [str(m.value) if hasattr(m, "value") else str(m) for m in p.get("modalities", [])]
            face_crops = p.get("face_crops", [])
            face_desc = ", ".join(
                f"{fc.get('entity_name', '?')} (similarity: {fc.get('similarity', 0):.2f})"
                for fc in face_crops[:5]
            ) if face_crops else "none"
            source_docs = p.get("source_documents", [])
            source_images = p.get("source_images", [])
            composite_score = p.get("composite_score", 0)

            low_evidence_note = ""
            if composite_score < 0.3:
                low_evidence_note = (
                    "  *** LOW EVIDENCE STRENGTH (composite_score < 0.3) — "
                    "include a caveat about low evidence strength and recommend further corroboration.\n"
                )

            pattern_descriptions.append(
                f"Pattern {idx}:\n"
                f"  Entities: {entity_desc}\n"
                f"  Evidence modalities: {', '.join(modalities)}\n"
                f"  Face matches: {face_desc}\n"
                f"  Supporting documents: {len(source_docs)}\n"
                f"  Supporting images: {len(source_images)}\n"
                f"  Evidence strength: {p.get('evidence_strength', 0):.2f}\n"
                f"  Novelty score: {p.get('novelty_score', 0):.2f}\n"
                f"  Composite score: {composite_score:.3f}\n"
                f"{low_evidence_note}"
            )

        prompt = (
            "Given the following multi-modal evidence patterns discovered from case "
            "documents, images, face matches, and entity co-occurrence analysis, "
            "generate an investigative question AND a narrative explanation for each pattern.\n\n"
            f"Case ID: {case_id}\n\n"
            + "\n\n".join(pattern_descriptions)
            + "\n\nFor each pattern, respond with a JSON array where each element has:\n"
            '- "question": an investigative question (1 sentence)\n'
            '- "narrative": a narrative explanation (3-5 sentences) that explains WHY this '
            "pattern matters investigatively — not graph statistics. Describe relationship "
            "context, gaps, anomalies, and what an investigator should do next. "
            "Cite specific entity names, document counts, and relationship types. "
            "Reference all evidence modalities present in the pattern. "
            "If the pattern has LOW EVIDENCE STRENGTH (composite_score < 0.3), include a "
            "caveat about low evidence strength and recommend further corroboration.\n"
            '- "confidence": an integer 0-100 representing how likely this leads to actionable evidence\n'
            '- "summary": a 2-3 sentence explanation of why this pattern is significant\n\n'
            "Respond ONLY with the JSON array, no other text."
        )

        try:
            resp = self._bedrock.invoke_model(
                modelId=BEDROCK_SYNTHESIS_MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4000,
                    "system": self.NARRATIVE_SYNTHESIS_PERSONA,
                    "messages": [{"role": "user", "content": prompt}],
                }),
            )
            body = json.loads(resp["body"].read())
            text = body.get("content", [{}])[0].get("text", "")

            # Parse JSON from Claude's response
            ai_results = json.loads(text)
            if not isinstance(ai_results, list):
                raise ValueError("Expected JSON array from Bedrock")

            questions = []
            for idx, (ai, p) in enumerate(zip(ai_results, patterns)):
                modalities = p.get("modalities", [])
                entities = p.get("entities", [])
                questions.append({
                    "index": idx + 1,
                    "question": str(ai.get("question", "")),
                    "narrative": str(ai.get("narrative", "")),
                    "confidence": max(0, min(100, int(ai.get("confidence", 50)))),
                    "modalities": modalities,
                    "summary": str(ai.get("summary", "")),
                    "entities": entities,
                    "composite_score": p.get("composite_score", 0),
                    "document_count": len(p.get("source_documents", [])),
                    "image_count": len(p.get("source_images", [])),
                    "raw_pattern": p,
                })
            return questions

        except Exception as exc:
            logger.error("Bedrock synthesis failed for case %s: %s", case_id, str(exc)[:200])
            return self._generate_fallback_questions(patterns)

    def _generate_fallback_questions(self, patterns: list) -> list:
        """Generate fallback questions when Bedrock is unavailable.

        Uses template: "Investigate the connection between [Entity A] and
        [Entity B] found in [N] documents with [modalities] evidence."
        Sets fallback confidence to 50.
        """
        questions = []
        for idx, p in enumerate(patterns):
            entities = p.get("entities", [])
            entity_a = entities[0].get("name", "Unknown") if len(entities) > 0 else "Unknown"
            entity_b = entities[1].get("name", "Unknown") if len(entities) > 1 else "Unknown"
            modalities = p.get("modalities", [])
            modality_names = ", ".join(
                m.value if hasattr(m, "value") else str(m) for m in modalities
            )
            doc_count = len(p.get("source_documents", []))
            img_count = len(p.get("source_images", []))

            question = (
                f"Investigate the connection between {entity_a} and {entity_b} "
                f"found in {doc_count} documents with {modality_names} evidence."
            )
            summary = (
                f"This pattern connects {entity_a} and {entity_b} across "
                f"{modality_names} evidence sources. "
                f"Further investigation may reveal additional connections."
            )
            questions.append({
                "index": idx + 1,
                "question": question,
                "confidence": 50,
                "modalities": modalities,
                "summary": summary,
                "document_count": doc_count,
                "image_count": img_count,
                "raw_pattern": p,
            })
        return questions

    # ------------------------------------------------------------------
    # Existing pattern discovery methods
    # ------------------------------------------------------------------

    def discover_graph_patterns(self, case_id: str) -> list[Pattern]:
        label = _entity_label(case_id)
        patterns: list[Pattern] = []

        # Quick connectivity test
        test = _gremlin_query(f"g.V().hasLabel('{_escape(label)}').count()")
        logger.info("Neptune node count for %s: %s", label, test)

        # Centrality only — community detection and path finding are too slow for API Gateway's 29s limit
        patterns.extend(self._discover_centrality_patterns(label))
        return patterns

    def _discover_centrality_patterns(self, label: str) -> list[Pattern]:
        # Get top 20 nodes with edge counts (limit to avoid timeout)
        query = (
            f"g.V().hasLabel('{_escape(label)}').limit(100)"
            f".project('n','t','d').by('canonical_name').by('entity_type').by(bothE().count())"
        )
        results = _gremlin_query(query)
        logger.info("Centrality raw count: %d, sample: %s", len(results), str(results[:2])[:500])

        # Parse and sort in Python
        nodes = []
        for r in results:
            if not isinstance(r, dict):
                continue
            name = r.get("n", "")
            etype = r.get("t", "")
            degree = r.get("d", 0)
            if isinstance(degree, dict):
                degree = degree.get("@value", 0)
            nodes.append({"name": name, "type": etype, "degree": int(degree)})

        nodes.sort(key=lambda x: x["degree"], reverse=True)
        top = nodes[:TOP_CENTRALITY_NODES]
        logger.info("Top centrality: %s", [(n["name"], n["degree"]) for n in top])

        patterns = []
        for node in top:
            if node["degree"] == 0:
                continue
            novelty = min(1.0, node["degree"] / 10.0)
            patterns.append(Pattern(
                pattern_id=str(uuid.uuid4()),
                entities_involved=[{"entity_id": "", "name": node["name"], "type": node["type"]}],
                connection_type="graph-based",
                explanation="",
                confidence_score=0.8,
                novelty_score=novelty,
                source_documents=[],
            ))
        return patterns

    def _get_high_centrality_nodes(self, label: str) -> list[dict]:
        query = (
            f"g.V().hasLabel('{_escape(label)}')"
            f".project('n','t','d').by('canonical_name').by('entity_type').by(bothE().count())"
        )
        results = _gremlin_query(query)
        nodes = []
        for r in results:
            if isinstance(r, dict):
                d = r.get("d", 0)
                if isinstance(d, dict):
                    d = d.get("@value", 0)
                nodes.append({"name": r.get("n", ""), "type": r.get("t", ""), "degree": int(d)})
        nodes.sort(key=lambda x: x["degree"], reverse=True)
        return nodes[:TOP_CENTRALITY_NODES]

    def _discover_community_patterns(self, label: str) -> list[Pattern]:
        # Get all nodes
        query = f"g.V().hasLabel('{_escape(label)}').project('name','type','confidence').by('canonical_name').by('entity_type').by('confidence')"
        all_nodes = _gremlin_query(query)
        if not all_nodes or not isinstance(all_nodes[0], dict):
            return []

        # Get all edges to build adjacency
        edge_query = (
            f"g.V().hasLabel('{_escape(label)}').outE('RELATED_TO')"
            f".project('src','tgt').by(outV().values('canonical_name')).by(inV().values('canonical_name'))"
        )
        edges = _gremlin_query(edge_query)

        # Build adjacency list
        adj: dict[str, set[str]] = {}
        for e in edges:
            if isinstance(e, dict):
                src, tgt = e.get("src", ""), e.get("tgt", "")
                if src and tgt:
                    adj.setdefault(src, set()).add(tgt)
                    adj.setdefault(tgt, set()).add(src)

        # Find connected components via BFS
        node_map = {n.get("name", ""): n for n in all_nodes if isinstance(n, dict)}
        visited: set[str] = set()
        components: list[list[dict]] = []

        for name in node_map:
            if name in visited:
                continue
            component = []
            queue = [name]
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                if current in node_map:
                    component.append(node_map[current])
                for neighbor in adj.get(current, set()):
                    if neighbor not in visited:
                        queue.append(neighbor)
            if len(component) >= 2:
                components.append(component)

        patterns = []
        for comp in components:
            avg_conf = sum(float(n.get("confidence", 0.5)) for n in comp) / len(comp)
            novelty = min(1.0, len(comp) / 5.0)
            patterns.append(Pattern(
                pattern_id=str(uuid.uuid4()),
                entities_involved=[{"entity_id": "", "name": n.get("name", ""), "type": n.get("type", "")} for n in comp],
                connection_type="graph-based",
                explanation="",
                confidence_score=round(avg_conf, 4),
                novelty_score=round(novelty, 4),
                source_documents=[],
            ))
        return patterns

    def _discover_path_patterns(self, label: str, high_nodes: list[dict]) -> list[Pattern]:
        patterns = []
        seen: set[tuple[str, str]] = set()
        for i, a in enumerate(high_nodes):
            for b in high_nodes[i + 1:]:
                a_name, b_name = a.get("name", ""), b.get("name", "")
                pair = tuple(sorted((a_name, b_name)))
                if pair in seen or not a_name or not b_name:
                    continue
                seen.add(pair)
                query = (
                    f"g.V().hasLabel('{_escape(label)}').has('canonical_name','{_escape(a_name)}')"
                    f".repeat(both('RELATED_TO').hasLabel('{_escape(label)}').simplePath())"
                    f".until(has('canonical_name','{_escape(b_name)}')).limit(1)"
                    f".path().by('canonical_name')"
                )
                result = _gremlin_query(query)
                if not result:
                    continue
                path = result[0] if result else []
                if isinstance(path, dict) and "objects" in path:
                    path = path["objects"]
                if isinstance(path, dict) and "@value" in path:
                    path = path["@value"]
                if not isinstance(path, list) or len(path) < 2:
                    continue
                entities = [{"entity_id": "", "name": str(n), "type": ""} for n in path]
                novelty = min(1.0, len(entities) / 4.0)
                patterns.append(Pattern(
                    pattern_id=str(uuid.uuid4()),
                    entities_involved=entities,
                    connection_type="graph-based",
                    explanation="",
                    confidence_score=0.5,
                    novelty_score=round(novelty, 4),
                    source_documents=[],
                ))
        return patterns

    def discover_vector_patterns(self, case_id: str) -> list[Pattern]:
        with self._aurora.cursor() as cur:
            cur.execute(
                """
                SELECT a.document_id::text, b.document_id::text,
                       1 - (a.embedding <=> b.embedding) AS similarity
                FROM documents a JOIN documents b
                    ON a.case_file_id = b.case_file_id AND a.document_id < b.document_id
                WHERE a.case_file_id = %s AND a.embedding IS NOT NULL AND b.embedding IS NOT NULL
                    AND 1 - (a.embedding <=> b.embedding) >= %s
                ORDER BY similarity DESC
                """,
                (case_id, SIMILARITY_THRESHOLD),
            )
            rows = cur.fetchall()

        clusters = self._cluster_documents(rows)
        patterns = []
        for cluster_docs, avg_sim in clusters:
            if len(cluster_docs) < 2:
                continue
            novelty = min(1.0, len(cluster_docs) / 5.0)
            patterns.append(Pattern(
                pattern_id=str(uuid.uuid4()),
                entities_involved=[{"entity_id": d, "name": d, "type": "document"} for d in sorted(cluster_docs)],
                connection_type="vector-based",
                explanation="",
                confidence_score=round(avg_sim, 4),
                novelty_score=round(novelty, 4),
                source_documents=sorted(cluster_docs),
            ))
        return patterns

    @staticmethod
    def _cluster_documents(rows: list[tuple]) -> list[tuple[set[str], float]]:
        parent: dict[str, str] = {}
        def find(x):
            while parent.get(x, x) != x:
                parent[x] = parent.get(parent[x], parent[x])
                x = parent[x]
            return x
        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        sims: dict[str, list[float]] = {}
        for a, b, s in rows:
            union(a, b)
            sims.setdefault(find(a), []).append(float(s))

        groups: dict[str, set[str]] = {}
        for a, b, _ in rows:
            for d in (a, b):
                groups.setdefault(find(d), set()).add(d)

        return [(members, sum(sims.get(r, sims.get(find(r), [0.8]))) / len(sims.get(r, sims.get(find(r), [0.8])))) for r, members in groups.items()]

    def generate_pattern_report(self, case_id: str) -> PatternReport:
        graph_patterns = self.discover_graph_patterns(case_id)
        vector_patterns = self.discover_vector_patterns(case_id)
        all_p = graph_patterns + vector_patterns
        deduped = self._deduplicate_patterns(all_p)
        deduped.sort(key=lambda p: p.confidence_score * p.novelty_score, reverse=True)
        # Skip Bedrock explanations for speed — API Gateway has 29s timeout
        for p in deduped:
            entities_desc = ", ".join(f"{e.get('name','?')} ({e.get('type','?')})" for e in p.entities_involved[:5])
            p.explanation = f"Pattern involving {entities_desc} ({p.connection_type}, confidence: {p.confidence_score})"
        report = PatternReport(
            report_id=str(uuid.uuid4()),
            case_file_id=case_id,
            patterns=deduped,
            graph_patterns_count=len(graph_patterns),
            vector_patterns_count=len(vector_patterns),
            combined_count=len(deduped),
        )
        self._store_report(report)
        return report

    @staticmethod
    def _deduplicate_patterns(patterns: list[Pattern]) -> list[Pattern]:
        seen: set[tuple[frozenset[str], str]] = set()
        unique = []
        for p in patterns:
            names = frozenset(e.get("name", "") for e in p.entities_involved)
            key = (names, p.connection_type)
            if key not in seen:
                seen.add(key)
                unique.append(p)
        return unique

    def _generate_explanation(self, pattern: Pattern) -> str:
        entities_desc = ", ".join(f"{e.get('name','?')} ({e.get('type','?')})" for e in pattern.entities_involved[:10])
        prompt = (
            f"Explain the significance of this pattern in a research investigation.\n\n"
            f"Entities: {entities_desc}\nConnection type: {pattern.connection_type}\n"
            f"Confidence: {pattern.confidence_score}\n\n"
            f"Provide a concise 2-3 sentence explanation."
        )
        try:
            resp = self._bedrock.invoke_model(
                modelId=BEDROCK_MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({"anthropic_version": "bedrock-2023-05-31", "max_tokens": 300, "messages": [{"role": "user", "content": prompt}]}),
            )
            body = json.loads(resp["body"].read())
            return body.get("content", [{}])[0].get("text", "")
        except Exception:
            return f"Pattern involving {entities_desc} ({pattern.connection_type}, confidence: {pattern.confidence_score})"

    # ------------------------------------------------------------------
    # Network-specific pattern detection (conspiracy-network-discovery)
    # ------------------------------------------------------------------

    def discover_financial_patterns(self, case_id: str) -> list[Pattern]:
        """Detect unusual financial transaction patterns, shell companies, and money laundering indicators."""
        label = _entity_label(case_id)
        patterns: list[Pattern] = []

        # Find entities with financial relationships
        query = (
            f"g.V().hasLabel('{_escape(label)}')"
            f".has('entity_type', within('FINANCIAL_AMOUNT','ACCOUNT_NUMBER','ORGANIZATION'))"
            f".project('name','type','degree')"
            f".by('canonical_name').by('entity_type').by(bothE().has('relationship_type','financial').count())"
            f".order().by('degree', desc).limit(50)"
        )
        results = _gremlin_query(query)

        # Group by connected components to find financial clusters
        financial_entities = []
        for r in results:
            if not isinstance(r, dict):
                continue
            deg = r.get("degree", 0)
            if isinstance(deg, dict):
                deg = deg.get("@value", 0)
            if int(deg) > 0:
                financial_entities.append({
                    "name": r.get("name", ""),
                    "type": r.get("type", ""),
                    "degree": int(deg),
                })

        if len(financial_entities) >= 2:
            # Cluster financial entities by shared connections
            confidence = min(1.0, len(financial_entities) / 10.0)
            patterns.append(Pattern(
                pattern_id=str(uuid.uuid4()),
                entities_involved=[
                    {"entity_id": "", "name": e["name"], "type": e["type"], "role": "financial_actor"}
                    for e in financial_entities[:20]
                ],
                connection_type="financial",
                explanation=(
                    f"Financial network cluster: {len(financial_entities)} entities with "
                    f"financial relationships detected. Potential indicators of coordinated "
                    f"financial activity requiring further investigation."
                ),
                confidence_score=round(confidence, 4),
                novelty_score=round(min(1.0, len(financial_entities) / 5.0), 4),
                source_documents=[],
            ))

        # Detect shell company patterns (organizations with many financial links but few other types)
        org_query = (
            f"g.V().hasLabel('{_escape(label)}')"
            f".has('entity_type','ORGANIZATION')"
            f".project('name','fin','total')"
            f".by('canonical_name')"
            f".by(bothE().has('relationship_type','financial').count())"
            f".by(bothE().count())"
            f".limit(30)"
        )
        org_results = _gremlin_query(org_query)
        shell_candidates = []
        for r in org_results:
            if not isinstance(r, dict):
                continue
            fin = r.get("fin", 0)
            total = r.get("total", 0)
            if isinstance(fin, dict):
                fin = fin.get("@value", 0)
            if isinstance(total, dict):
                total = total.get("@value", 0)
            fin, total = int(fin), int(total)
            if total > 0 and fin / total > 0.7 and fin >= 2:
                shell_candidates.append({"name": r.get("name", ""), "type": "ORGANIZATION", "role": "shell_company_candidate"})

        if shell_candidates:
            patterns.append(Pattern(
                pattern_id=str(uuid.uuid4()),
                entities_involved=[{"entity_id": "", **sc} for sc in shell_candidates],
                connection_type="financial",
                explanation=(
                    f"Potential shell company indicators: {len(shell_candidates)} organizations "
                    f"with disproportionately high financial relationship ratios."
                ),
                confidence_score=round(min(0.9, 0.5 + len(shell_candidates) * 0.1), 4),
                novelty_score=0.9,
                source_documents=[],
            ))

        return patterns

    def discover_communication_patterns(self, case_id: str) -> list[Pattern]:
        """Detect communication frequency anomalies, timing patterns, and encrypted indicators."""
        label = _entity_label(case_id)
        patterns: list[Pattern] = []

        # Find communication entities (phone, email) with high connection counts
        query = (
            f"g.V().hasLabel('{_escape(label)}')"
            f".has('entity_type', within('PHONE_NUMBER','EMAIL'))"
            f".project('name','type','degree')"
            f".by('canonical_name').by('entity_type').by(bothE().count())"
            f".order().by('degree', desc).limit(50)"
        )
        results = _gremlin_query(query)

        comm_entities = []
        for r in results:
            if not isinstance(r, dict):
                continue
            deg = r.get("degree", 0)
            if isinstance(deg, dict):
                deg = deg.get("@value", 0)
            if int(deg) > 0:
                comm_entities.append({
                    "name": r.get("name", ""),
                    "type": r.get("type", ""),
                    "degree": int(deg),
                })

        if not comm_entities:
            return patterns

        # Detect frequency anomalies (entities with unusually high communication links)
        if len(comm_entities) >= 3:
            import statistics
            degrees = [e["degree"] for e in comm_entities]
            mean_deg = statistics.mean(degrees)
            std_deg = statistics.stdev(degrees) if len(degrees) > 1 else 0
            threshold = mean_deg + 1.5 * std_deg

            anomalous = [e for e in comm_entities if e["degree"] > threshold]
            if anomalous:
                patterns.append(Pattern(
                    pattern_id=str(uuid.uuid4()),
                    entities_involved=[
                        {"entity_id": "", "name": e["name"], "type": e["type"], "role": "high_frequency_communicator"}
                        for e in anomalous
                    ],
                    connection_type="communication",
                    explanation=(
                        f"Communication frequency anomaly: {len(anomalous)} contact points "
                        f"with significantly above-average connection counts (threshold: {threshold:.0f})."
                    ),
                    confidence_score=round(min(0.95, 0.6 + len(anomalous) * 0.1), 4),
                    novelty_score=0.85,
                    source_documents=[],
                ))

        # General communication cluster
        confidence = min(0.9, len(comm_entities) / 15.0)
        patterns.append(Pattern(
            pattern_id=str(uuid.uuid4()),
            entities_involved=[
                {"entity_id": "", "name": e["name"], "type": e["type"], "role": "communicator"}
                for e in comm_entities[:15]
            ],
            connection_type="communication",
            explanation=(
                f"Communication network: {len(comm_entities)} phone/email entities "
                f"forming a communication cluster within the case evidence."
            ),
            confidence_score=round(confidence, 4),
            novelty_score=round(min(1.0, len(comm_entities) / 5.0), 4),
            source_documents=[],
        ))

        return patterns

    def discover_geographic_patterns(self, case_id: str) -> list[Pattern]:
        """Detect travel patterns, co-location events, and venue clustering."""
        label = _entity_label(case_id)
        patterns: list[Pattern] = []

        # Find location entities and their connections to persons
        query = (
            f"g.V().hasLabel('{_escape(label)}')"
            f".has('entity_type','LOCATION')"
            f".project('name','persons')"
            f".by('canonical_name')"
            f".by(both().has('entity_type','PERSON').values('canonical_name').fold())"
            f".limit(50)"
        )
        results = _gremlin_query(query)

        location_persons: dict[str, list[str]] = {}
        for r in results:
            if not isinstance(r, dict):
                continue
            loc = r.get("name", "")
            persons = r.get("persons", [])
            if isinstance(persons, dict) and "@value" in persons:
                persons = persons["@value"]
            if not isinstance(persons, list):
                persons = []
            if loc and len(persons) >= 2:
                location_persons[loc] = [str(p) for p in persons]

        # Detect co-location events (2+ persons at same location)
        for loc, persons in location_persons.items():
            if len(persons) >= 2:
                confidence = min(0.95, 0.5 + len(persons) * 0.1)
                entities = [{"entity_id": "", "name": loc, "type": "LOCATION", "role": "venue"}]
                entities.extend([
                    {"entity_id": "", "name": p, "type": "PERSON", "role": "co_located"}
                    for p in persons[:10]
                ])
                patterns.append(Pattern(
                    pattern_id=str(uuid.uuid4()),
                    entities_involved=entities,
                    connection_type="geographic",
                    explanation=(
                        f"Co-location event at {loc}: {len(persons)} persons connected "
                        f"to this location in case evidence."
                    ),
                    confidence_score=round(confidence, 4),
                    novelty_score=round(min(1.0, len(persons) / 4.0), 4),
                    source_documents=[],
                ))

        # Detect venue clustering (locations sharing many of the same persons)
        if len(location_persons) >= 2:
            locs = list(location_persons.keys())
            for i, loc_a in enumerate(locs):
                for loc_b in locs[i + 1:]:
                    shared = set(location_persons[loc_a]) & set(location_persons[loc_b])
                    if len(shared) >= 2:
                        patterns.append(Pattern(
                            pattern_id=str(uuid.uuid4()),
                            entities_involved=[
                                {"entity_id": "", "name": loc_a, "type": "LOCATION", "role": "venue"},
                                {"entity_id": "", "name": loc_b, "type": "LOCATION", "role": "venue"},
                            ] + [
                                {"entity_id": "", "name": p, "type": "PERSON", "role": "shared_visitor"}
                                for p in list(shared)[:5]
                            ],
                            connection_type="geographic",
                            explanation=(
                                f"Venue clustering: {loc_a} and {loc_b} share "
                                f"{len(shared)} persons in common."
                            ),
                            confidence_score=round(min(0.9, 0.4 + len(shared) * 0.15), 4),
                            novelty_score=0.8,
                            source_documents=[],
                        ))

        return patterns

    def discover_temporal_patterns(self, case_id: str) -> list[Pattern]:
        """Detect event clustering, timeline anomalies, and timing correlations."""
        label = _entity_label(case_id)
        patterns: list[Pattern] = []

        # Find date/event entities and their connections
        query = (
            f"g.V().hasLabel('{_escape(label)}')"
            f".has('entity_type', within('DATE','EVENT'))"
            f".project('name','type','degree','connected')"
            f".by('canonical_name').by('entity_type').by(bothE().count())"
            f".by(both().values('canonical_name').fold())"
            f".order().by('degree', desc).limit(50)"
        )
        results = _gremlin_query(query)

        temporal_entities = []
        for r in results:
            if not isinstance(r, dict):
                continue
            deg = r.get("degree", 0)
            if isinstance(deg, dict):
                deg = deg.get("@value", 0)
            connected = r.get("connected", [])
            if isinstance(connected, dict) and "@value" in connected:
                connected = connected["@value"]
            if not isinstance(connected, list):
                connected = []
            temporal_entities.append({
                "name": r.get("name", ""),
                "type": r.get("type", ""),
                "degree": int(deg),
                "connected": [str(c) for c in connected],
            })

        if not temporal_entities:
            return patterns

        # Detect event clustering (dates/events with many shared entities)
        if len(temporal_entities) >= 2:
            for i, te_a in enumerate(temporal_entities):
                for te_b in temporal_entities[i + 1:]:
                    shared = set(te_a["connected"]) & set(te_b["connected"])
                    if len(shared) >= 2:
                        patterns.append(Pattern(
                            pattern_id=str(uuid.uuid4()),
                            entities_involved=[
                                {"entity_id": "", "name": te_a["name"], "type": te_a["type"], "role": "temporal_anchor"},
                                {"entity_id": "", "name": te_b["name"], "type": te_b["type"], "role": "temporal_anchor"},
                            ] + [
                                {"entity_id": "", "name": p, "type": "ENTITY", "role": "correlated"}
                                for p in list(shared)[:5]
                            ],
                            connection_type="temporal",
                            explanation=(
                                f"Temporal correlation: {te_a['name']} and {te_b['name']} "
                                f"share {len(shared)} connected entities, suggesting "
                                f"coordinated activity."
                            ),
                            confidence_score=round(min(0.9, 0.4 + len(shared) * 0.15), 4),
                            novelty_score=0.85,
                            source_documents=[],
                        ))
                        if len(patterns) >= 10:
                            break
                if len(patterns) >= 10:
                    break

        # High-activity temporal nodes
        high_activity = [te for te in temporal_entities if te["degree"] > 5]
        if high_activity:
            patterns.append(Pattern(
                pattern_id=str(uuid.uuid4()),
                entities_involved=[
                    {"entity_id": "", "name": te["name"], "type": te["type"], "role": "high_activity_period"}
                    for te in high_activity[:10]
                ],
                connection_type="temporal",
                explanation=(
                    f"High-activity temporal nodes: {len(high_activity)} dates/events "
                    f"with above-average entity connections, indicating periods of "
                    f"concentrated activity."
                ),
                confidence_score=round(min(0.85, 0.5 + len(high_activity) * 0.1), 4),
                novelty_score=0.75,
                source_documents=[],
            ))

        return patterns

    def _store_report(self, report: PatternReport) -> None:
        patterns_json = json.dumps([p.model_dump() for p in report.patterns])
        with self._aurora.cursor() as cur:
            cur.execute(
                "INSERT INTO pattern_reports (report_id, case_file_id, patterns, graph_patterns_count, vector_patterns_count, combined_count) VALUES (%s, %s, %s, %s, %s, %s)",
                (report.report_id, report.case_file_id, patterns_json, report.graph_patterns_count, report.vector_patterns_count, report.combined_count),
            )

    # ------------------------------------------------------------------
    # Evidence Bundle retrieval (Top 5 detail view)
    # ------------------------------------------------------------------

    def get_evidence_bundle(self, case_id: str, pattern: dict) -> dict:
        """Fetch detailed evidence for a single pattern.

        Retrieves document excerpts from Aurora, generates presigned S3 URLs
        for supporting images and face crop thumbnails, and queries Neptune
        for entity connection paths.

        Returns a dict matching :class:`EvidenceBundle` structure.
        """
        import boto3

        bucket = os.environ.get("S3_DATA_BUCKET", os.environ.get("S3_BUCKET_NAME", ""))
        s3 = boto3.client("s3")

        # --- Document excerpts from Aurora ---
        documents = []
        doc_ids = pattern.get("source_documents", [])
        if doc_ids:
            try:
                with self._aurora.cursor() as cur:
                    placeholders = ",".join(["%s"] * len(doc_ids))
                    cur.execute(
                        f"SELECT document_id, source_filename, raw_text "
                        f"FROM documents "
                        f"WHERE document_id IN ({placeholders}) AND case_file_id = %s",
                        (*doc_ids, case_id),
                    )
                    for row in cur.fetchall():
                        doc_id_val = str(row[0])
                        filename = row[1] or doc_id_val
                        content = row[2] or ""
                        excerpt = content[:200]
                        documents.append({
                            "document_id": doc_id_val,
                            "filename": filename,
                            "excerpt": excerpt,
                            "download_url": "",
                        })
            except Exception as exc:
                logger.error("Failed to fetch document excerpts for case %s: %s", case_id, str(exc)[:200])

        # --- Presigned S3 URLs for supporting images ---
        images = []
        for img_key in pattern.get("source_images", []):
            try:
                url = s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": bucket, "Key": str(img_key)},
                    ExpiresIn=3600,
                )
                images.append({
                    "s3_key": str(img_key),
                    "presigned_url": url,
                    "visual_labels": [],
                })
            except Exception as exc:
                logger.error("Failed to generate presigned URL for image %s: %s", img_key, str(exc)[:200])

        # --- Presigned S3 URLs for face crop thumbnails ---
        face_crops = []
        for fc in pattern.get("face_crops", []):
            crop_key = fc.get("crop_s3_key", "")
            if not crop_key:
                continue
            try:
                url = s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": bucket, "Key": crop_key},
                    ExpiresIn=3600,
                )
                face_crops.append({
                    "presigned_url": url,
                    "entity_name": fc.get("entity_name", ""),
                    "similarity": fc.get("similarity", 0.0),
                })
            except Exception as exc:
                logger.error("Failed to generate presigned URL for face crop %s: %s", crop_key, str(exc)[:200])

        # --- Entity connection paths from Neptune ---
        entity_paths = []
        entities = pattern.get("entities", [])
        if len(entities) >= 2:
            label = _entity_label(case_id)
            for i in range(len(entities)):
                for j in range(i + 1, min(len(entities), i + 3)):
                    name_a = entities[i].get("name", "")
                    name_b = entities[j].get("name", "")
                    if not name_a or not name_b:
                        continue
                    try:
                        query = (
                            f"g.V().hasLabel('{_escape(label)}')"
                            f".has('canonical_name','{_escape(name_a)}')"
                            f".repeat(both('RELATED_TO').hasLabel('{_escape(label)}').simplePath())"
                            f".until(has('canonical_name','{_escape(name_b)}')).limit(1)"
                            f".path().by('canonical_name')"
                        )
                        result = _gremlin_query(query)
                        if result:
                            path_data = result[0]
                            if isinstance(path_data, dict) and "objects" in path_data:
                                path_data = path_data["objects"]
                            if isinstance(path_data, list):
                                entity_paths.append({
                                    "from_entity": name_a,
                                    "to_entity": name_b,
                                    "path_nodes": [str(n) for n in path_data],
                                })
                    except Exception as exc:
                        logger.error("Failed to query path %s->%s: %s", name_a, name_b, str(exc)[:200])

        # --- Co-occurring labels ---
        cooccurring_labels = []
        for entity in entities:
            if entity.get("role") == "visual_label":
                cooccurring_labels.append(entity.get("name", ""))

        # --- Enhancement 1: Document snippets via semantic search ---
        # If no documents from source_documents, search Aurora for docs mentioning pattern entities
        if not documents and entities:
            try:
                entity_names = [e.get("name", "") for e in entities[:3] if e.get("name")]
                search_query = " ".join(entity_names)
                with self._aurora.cursor() as cur:
                    cur.execute(
                        "SELECT document_id, source_filename, raw_text "
                        "FROM documents WHERE case_file_id = %s AND raw_text ILIKE %s "
                        "LIMIT 5",
                        (case_id, f"%{entity_names[0]}%"),
                    )
                    for row in cur.fetchall():
                        content = row[2] or ""
                        # Find the snippet around the entity mention
                        idx = content.lower().find(entity_names[0].lower())
                        start = max(0, idx - 100) if idx >= 0 else 0
                        excerpt = content[start:start + 300]
                        if idx > 100:
                            excerpt = "..." + excerpt
                        documents.append({
                            "document_id": str(row[0]),
                            "filename": row[1] or str(row[0]),
                            "excerpt": excerpt[:300],
                            "download_url": "",
                        })
            except Exception as exc:
                logger.error("Document snippet search failed: %s", str(exc)[:200])

        # --- Enhancement 2: Timeline from date entities ---
        timeline = []
        for entity in entities:
            etype = entity.get("type", "").lower()
            name = entity.get("name", "")
            if etype in ("date", "temporal", "event") or _looks_like_date(name):
                timeline.append({"date": name, "entities": [
                    e.get("name", "") for e in entities if e.get("name") != name
                ][:3]})
        timeline.sort(key=lambda t: t["date"])

        # --- Enhancement 3: Face crop photos for matched entities ---
        if not face_crops and entities:
            try:
                face_label = f"FaceCrop_{case_id}"
                entity_label_str = _entity_label(case_id)
                person_names = [e.get("name", "") for e in entities
                                if e.get("type", "").upper() in ("PERSON", "UNKNOWN", "")]
                for pname in person_names[:3]:
                    if not pname:
                        continue
                    query = (
                        f"g.V().hasLabel('{_escape(entity_label_str)}')"
                        f".has('canonical_name','{_escape(pname)}')"
                        f".in('HAS_FACE_MATCH').hasLabel('{_escape(face_label)}')"
                        f".values('s3_key').limit(2)"
                    )
                    result = _gremlin_query(query)
                    for crop_key in (result or []):
                        if crop_key and bucket:
                            try:
                                url = s3.generate_presigned_url(
                                    "get_object",
                                    Params={"Bucket": bucket, "Key": str(crop_key)},
                                    ExpiresIn=3600,
                                )
                                face_crops.append({
                                    "presigned_url": url,
                                    "entity_name": pname,
                                    "similarity": 0.0,
                                })
                            except Exception:
                                pass
            except Exception as exc:
                logger.error("Face crop lookup failed: %s", str(exc)[:200])

        # --- Enhancement 4: Related images from extracted images ---
        if not images and documents:
            try:
                for doc in documents[:3]:
                    doc_id = doc.get("document_id", "")
                    if not doc_id:
                        continue
                    prefix = f"cases/{case_id}/extracted-images/{doc_id}_"
                    resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=3)
                    for obj in resp.get("Contents", []):
                        try:
                            url = s3.generate_presigned_url(
                                "get_object",
                                Params={"Bucket": bucket, "Key": obj["Key"]},
                                ExpiresIn=3600,
                            )
                            images.append({
                                "s3_key": obj["Key"],
                                "presigned_url": url,
                                "visual_labels": [],
                            })
                        except Exception:
                            pass
            except Exception as exc:
                logger.error("Related images lookup failed: %s", str(exc)[:200])

        # --- Enhancement 5: "Why this matters" deep AI analysis ---
        why_this_matters = ""
        try:
            entity_desc = ", ".join(
                f"{e.get('name', '?')} ({e.get('type', '?')})" for e in entities[:8]
            )
            doc_context = ""
            if documents:
                doc_context = "\n".join(
                    f"- {d.get('filename', '?')}: {d.get('excerpt', '')[:150]}"
                    for d in documents[:3]
                )
            prompt = (
                "You are an investigative intelligence analyst. Based on the following "
                "entity connections and document evidence, provide a 3-4 sentence analysis "
                "of WHY this pattern matters for the investigation. Be specific about what "
                "an investigator should look for next.\n\n"
                f"Entities: {entity_desc}\n"
                f"Connection paths: {len(entity_paths)} paths found\n"
                f"Documents: {len(documents)} supporting documents\n"
                f"Face matches: {len(face_crops)} identified faces\n"
            )
            if doc_context:
                prompt += f"\nDocument excerpts:\n{doc_context}\n"
            prompt += "\nProvide ONLY the analysis text, no headers or formatting."

            resp = self._bedrock.invoke_model(
                modelId=BEDROCK_SYNTHESIS_MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 500,
                    "messages": [{"role": "user", "content": prompt}],
                }),
            )
            body = json.loads(resp["body"].read())
            why_this_matters = body.get("content", [{}])[0].get("text", "")
        except Exception as exc:
            logger.error("Why-this-matters analysis failed: %s", str(exc)[:200])
            why_this_matters = ""

        return {
            "documents": documents,
            "images": images,
            "face_crops": face_crops,
            "entity_paths": entity_paths,
            "cooccurring_labels": cooccurring_labels,
            "timeline": timeline,
            "why_this_matters": why_this_matters,
        }
