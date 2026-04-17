"""Discovery Engine Service — AI-generated "Did You Know" investigative discoveries.

Generates batches of 5 narrative discoveries by gathering case context from
Aurora (documents, entities, temporal data), Neptune (graph neighborhoods),
and existing services (PatternDiscoveryService, InvestigatorAIEngine), then
synthesizing via Bedrock Claude with an investigator persona.

Supports feedback learning (thumbs-up/down) and iterative batch generation
with exclusion of previously seen discoveries via content_hash dedup.
"""

import hashlib
import json
import logging
import os
import ssl
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Load model registry from config
# ---------------------------------------------------------------------------

def _load_model_registry() -> dict:
    """Load the Bedrock model registry from config/bedrock_models.json."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "config",
        "bedrock_models.json",
    )
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error("Failed to load model registry from %s: %s", config_path, str(e)[:200])
        return {"models": [], "excluded_providers": [], "defaults": {}}


# ---------------------------------------------------------------------------
# Valid discovery types
# ---------------------------------------------------------------------------

VALID_DISCOVERY_TYPES = {
    "temporal_insight",
    "entity_cluster",
    "document_pattern",
    "relationship_anomaly",
    "geographic_convergence",
    "financial_pattern",
    "cross_reference",
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Discovery:
    """A narrative 'Did you know...?' investigative discovery."""

    discovery_id: str       # UUID
    narrative: str          # "Did you know...?" narrative text
    discovery_type: str     # One of VALID_DISCOVERY_TYPES
    entities: List[str]     # Entity names referenced in the discovery
    confidence: float       # 0.0–1.0
    content_hash: str       # SHA-256 of narrative for dedup

    def to_dict(self) -> dict:
        return {
            "discovery_id": self.discovery_id,
            "narrative": self.narrative,
            "discovery_type": self.discovery_type,
            "entities": list(self.entities),
            "confidence": self.confidence,
            "content_hash": self.content_hash,
        }


@dataclass
class DiscoveryBatch:
    """A batch of discoveries generated for a case."""

    case_id: str
    batch_number: int
    discoveries: List[Discovery]
    generated_at: str       # ISO timestamp
    model_id: str = ""

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "batch_number": self.batch_number,
            "discoveries": [d.to_dict() for d in self.discoveries],
            "generated_at": self.generated_at,
            "model_id": self.model_id,
        }


# ---------------------------------------------------------------------------
# Discovery Engine Service
# ---------------------------------------------------------------------------

class DiscoveryEngineService:
    """Generates batches of 5 narrative 'Did You Know' discoveries.

    Gathers context from Aurora (documents, entities, temporal distribution),
    Neptune (graph neighborhoods via PatternDiscoveryService / InvestigatorAIEngine),
    builds a Bedrock Claude prompt with investigator persona, incorporates
    feedback preferences, excludes previously seen discoveries, and returns
    a DiscoveryBatch of exactly 5 items (padded with fallback if needed).
    """

    INVESTIGATOR_PERSONA = (
        "You are a senior federal investigative analyst with 20+ years of experience "
        "in complex multi-jurisdictional investigations. Generate narrative investigative "
        "discoveries framed as 'Did you know...?' statements that explain WHY a finding "
        "matters investigatively. Each discovery must be surprise-based, non-obvious, and "
        "actionable. Cite specific evidence documents and entity connections by name. "
        "Do NOT restate raw statistics or graph metrics — frame everything as narrative insight."
    )

    def __init__(
        self,
        aurora_cm: Any,
        bedrock_client: Any,
        neptune_endpoint: str = "",
        neptune_port: str = "8182",
        pattern_svc: Any = None,
        ai_engine: Any = None,
        default_model_id: str = "anthropic.claude-3-haiku-20240307-v1:0",
    ) -> None:
        self._aurora = aurora_cm
        self._bedrock = bedrock_client
        self._neptune_endpoint = neptune_endpoint
        self._neptune_port = neptune_port
        self._pattern_svc = pattern_svc
        self._ai_engine = ai_engine
        self._default_model_id = default_model_id

        # Load model registry and build SUPPORTED_MODELS set
        self._registry = _load_model_registry()
        self.SUPPORTED_MODELS: Set[str] = {
            m["model_id"]
            for m in self._registry.get("models", [])
            if m.get("type") == "text"
        }
        self._excluded_providers: List[str] = self._registry.get("excluded_providers", [])

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_discoveries(
        self,
        case_id: str,
        user_id: str = "investigator",
        model_id: Optional[str] = None,
    ) -> DiscoveryBatch:
        """Generate a batch of 5 'Did You Know' discoveries for a case.

        Steps:
        1. Validate model_id against SUPPORTED_MODELS and excluded_providers
        2. Query discovery_history for previously generated content_hashes
        3. Query discovery_feedback for thumbs-up/down records
        4. Gather case context via _gather_case_context
        5. Build prompt via _build_prompt with feedback and exclusions
        6. Invoke Bedrock with selected model_id
        7. Parse JSON response into Discovery objects
        8. Pad with fallback discoveries if fewer than 5
        9. Store batch in discovery_history
        10. Return DiscoveryBatch
        """
        # 1. Validate model_id
        effective_model_id = self._resolve_model_id(model_id)

        # 2. Get previous discovery hashes for exclusion
        previous_hashes = self._get_previous_discovery_hashes(case_id)

        # 3. Get feedback records
        feedback = self._get_feedback(case_id)

        # 4. Gather case context
        context = self._gather_case_context(case_id)

        # 5. Build prompt
        prompt = self._build_prompt(case_id, context, feedback, previous_hashes)

        # 6–7. Invoke Bedrock and parse response
        discoveries = self._invoke_bedrock_and_parse(
            prompt, effective_model_id, case_id, context, previous_hashes,
        )

        # 8. Pad with fallback if fewer than 5
        if len(discoveries) < 5:
            fallbacks = self._generate_fallback_discoveries(case_id, context)
            for fb in fallbacks:
                if len(discoveries) >= 5:
                    break
                if fb.content_hash not in previous_hashes:
                    discoveries.append(fb)
        # Final trim/pad to exactly 5
        discoveries = discoveries[:5]
        while len(discoveries) < 5:
            discoveries.append(self._make_padding_discovery(case_id, context, len(discoveries)))

        # 9. Determine batch number and store
        batch_number = self._get_next_batch_number(case_id)
        self._store_batch(case_id, batch_number, discoveries)

        # 10. Return batch
        return DiscoveryBatch(
            case_id=case_id,
            batch_number=batch_number,
            discoveries=discoveries,
            generated_at=datetime.now(timezone.utc).isoformat(),
            model_id=effective_model_id,
        )

    def submit_feedback(
        self,
        case_id: str,
        user_id: str,
        discovery_id: str,
        rating: int,
        discovery_type: str,
        content_hash: str,
    ) -> dict:
        """Store feedback record in discovery_feedback table."""
        try:
            with self._aurora.cursor() as cur:
                cur.execute(
                    "INSERT INTO discovery_feedback "
                    "(feedback_id, discovery_id, case_id, user_id, rating, discovery_type, content_hash) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (
                        str(uuid.uuid4()),
                        discovery_id,
                        case_id,
                        user_id,
                        rating,
                        discovery_type,
                        content_hash,
                    ),
                )
        except Exception as e:
            logger.error("Failed to store feedback: %s", str(e)[:200])
            raise
        return {"status": "ok"}

    # ------------------------------------------------------------------
    # Model validation
    # ------------------------------------------------------------------

    def _resolve_model_id(self, model_id: Optional[str]) -> str:
        """Validate model_id against SUPPORTED_MODELS and excluded_providers.

        Falls back to default_model_id if invalid or excluded. If the default
        is also excluded, picks the first non-excluded model.
        """
        if model_id and model_id in self.SUPPORTED_MODELS:
            # Check if provider is excluded
            if not self._is_provider_excluded(model_id):
                return model_id

        # Fall back to default
        if self._default_model_id in self.SUPPORTED_MODELS and not self._is_provider_excluded(self._default_model_id):
            return self._default_model_id

        # Default is also excluded — pick first non-excluded text model
        for m in self._registry.get("models", []):
            if m.get("type") == "text" and m["model_id"] in self.SUPPORTED_MODELS:
                if not self._is_provider_excluded(m["model_id"]):
                    return m["model_id"]

        # Last resort
        return self._default_model_id

    def _is_provider_excluded(self, model_id: str) -> bool:
        """Check if the provider of a model_id is in the excluded list."""
        if not self._excluded_providers:
            return False
        for m in self._registry.get("models", []):
            if m["model_id"] == model_id:
                return m.get("provider", "").lower() in [
                    p.lower() for p in self._excluded_providers
                ]
        return False

    # ------------------------------------------------------------------
    # Context gathering
    # ------------------------------------------------------------------

    def _gather_case_context(self, case_id: str) -> dict:
        """Gather documents, entities, temporal distribution, graph data.

        Returns a context dict with keys:
        - doc_count, documents (list of {doc_id, filename, excerpt})
        - entity_count, entities (list of {name, type, count})
        - temporal (list of {period, count})
        - patterns (list of pattern dicts from PatternDiscoveryService)
        - neighborhoods (dict of entity_name -> neighborhood data)
        """
        context: Dict[str, Any] = {
            "doc_count": 0,
            "documents": [],
            "entity_count": 0,
            "entities": [],
            "temporal": [],
            "patterns": [],
            "neighborhoods": {},
        }

        # --- Aurora: documents ---
        try:
            with self._aurora.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM documents WHERE case_file_id = %s",
                    (case_id,),
                )
                row = cur.fetchone()
                context["doc_count"] = row[0] if row else 0

                cur.execute(
                    "SELECT document_id, source_filename, LEFT(raw_text, 300) "
                    "FROM documents WHERE case_file_id = %s "
                    "ORDER BY indexed_at DESC LIMIT 20",
                    (case_id,),
                )
                for r in cur.fetchall():
                    context["documents"].append({
                        "doc_id": r[0],
                        "filename": r[1],
                        "excerpt": r[2] or "",
                    })
        except Exception as e:
            logger.error("Aurora document query failed: %s", str(e)[:200])

        # --- Aurora: entities ---
        try:
            with self._aurora.cursor() as cur:
                cur.execute(
                    "SELECT canonical_name, entity_type, occurrence_count "
                    "FROM entities WHERE case_file_id = %s "
                    "ORDER BY occurrence_count DESC LIMIT 50",
                    (case_id,),
                )
                rows = cur.fetchall()
                context["entity_count"] = len(rows)
                for r in rows:
                    context["entities"].append({
                        "name": r[0],
                        "type": r[1],
                        "count": r[2],
                    })
        except Exception as e:
            logger.error("Aurora entity query failed: %s", str(e)[:200])

        # --- Aurora: temporal distribution ---
        try:
            with self._aurora.cursor() as cur:
                cur.execute(
                    "SELECT TO_CHAR(indexed_at, 'YYYY-MM') AS period, COUNT(*) "
                    "FROM documents WHERE case_file_id = %s "
                    "GROUP BY period ORDER BY period",
                    (case_id,),
                )
                for r in cur.fetchall():
                    context["temporal"].append({
                        "period": r[0],
                        "count": r[1],
                    })
        except Exception as e:
            logger.error("Aurora temporal query failed: %s", str(e)[:200])

        # --- PatternDiscoveryService: co-occurrence patterns ---
        if self._pattern_svc:
            try:
                report = self._pattern_svc.discover_top_patterns(case_id)
                context["patterns"] = report.get("patterns", [])
            except Exception as e:
                logger.error("Pattern query failed: %s", str(e)[:200])

        # --- InvestigatorAIEngine: entity neighborhoods for top 5 ---
        if self._ai_engine and hasattr(self._ai_engine, "_query_neptune_neighborhood"):
            top_entities = context["entities"][:5]
            for ent in top_entities:
                try:
                    neighborhood = self._ai_engine._query_neptune_neighborhood(
                        case_id, ent["name"],
                    )
                    context["neighborhoods"][ent["name"]] = neighborhood
                except Exception as e:
                    logger.error(
                        "Neighborhood query failed for '%s': %s",
                        ent["name"], str(e)[:200],
                    )

        return context

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        case_id: str,
        context: dict,
        feedback: List[dict],
        exclusions: Set[str],
    ) -> str:
        """Build Bedrock prompt with context, feedback preferences, and exclusions.

        Returns the full user message string. The system prompt (INVESTIGATOR_PERSONA)
        is set separately in the Messages API call.
        """
        parts: List[str] = []

        parts.append(
            f"Analyze the following investigative context for case {case_id} "
            f"and generate exactly 5 'Did you know...?' discoveries.\n"
        )

        # --- Document context ---
        parts.append(f"\nDOCUMENT CONTEXT ({context.get('doc_count', 0)} documents):")
        for doc in context.get("documents", [])[:10]:
            parts.append(f"- {doc['filename']}: {doc['excerpt'][:200]}")

        # --- Entity context ---
        parts.append(f"\nENTITY CONTEXT ({context.get('entity_count', 0)} entities):")
        for ent in context.get("entities", [])[:20]:
            parts.append(f"- {ent['name']} ({ent['type']}): {ent['count']} occurrences")

        # --- Temporal data ---
        temporal = context.get("temporal", [])
        if temporal:
            parts.append("\nTEMPORAL DISTRIBUTION:")
            for t in temporal:
                parts.append(f"- {t['period']}: {t['count']} documents")

        # --- Graph connections ---
        neighborhoods = context.get("neighborhoods", {})
        if neighborhoods:
            parts.append("\nGRAPH CONNECTIONS:")
            for entity_name, hood in neighborhoods.items():
                neighbors = hood.get("neighbors", [])
                if neighbors:
                    neighbor_names = [
                        n.get("name", "") if isinstance(n, dict) else str(n)
                        for n in neighbors[:10]
                    ]
                    parts.append(
                        f"- {entity_name}: connected to {', '.join(neighbor_names)}"
                    )

        # --- Patterns ---
        patterns = context.get("patterns", [])
        if patterns:
            parts.append("\nDISCOVERED PATTERNS:")
            for p in patterns[:5]:
                q = p.get("question", p.get("description", ""))
                if q:
                    parts.append(f"- {q}")

        # --- Feedback preferences ---
        if feedback:
            thumbs_up_types = list({
                f["discovery_type"] for f in feedback if f.get("rating", 0) > 0
            })
            thumbs_down_types = list({
                f["discovery_type"] for f in feedback if f.get("rating", 0) < 0
            })
            if thumbs_up_types or thumbs_down_types:
                parts.append("\nINVESTIGATOR FEEDBACK:")
                if thumbs_up_types:
                    parts.append(
                        f"The investigator found these types useful: {', '.join(thumbs_up_types)}."
                    )
                if thumbs_down_types:
                    parts.append(
                        f"Not useful: {', '.join(thumbs_down_types)}."
                    )

        # --- Exclusions ---
        if exclusions:
            parts.append(
                f"\nDo NOT generate discoveries similar to these already-seen findings "
                f"(content hashes): {', '.join(list(exclusions)[:20])}"
            )

        # --- Output format ---
        parts.append(
            "\nReturn ONLY a JSON array of exactly 5 objects. Each object must have:\n"
            '- "discovery_type": one of [temporal_insight, entity_cluster, document_pattern, '
            "relationship_anomaly, geographic_convergence, financial_pattern, cross_reference]\n"
            '- "narrative": a sentence starting with "Did you know..." explaining the investigative significance\n'
            '- "entities": array of entity names referenced\n'
            '- "confidence": float 0.0-1.0 based on evidence strength\n\n'
            "Return ONLY the JSON array, no other text."
        )

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Bedrock invocation and parsing
    # ------------------------------------------------------------------

    def _invoke_bedrock_and_parse(
        self,
        prompt: str,
        model_id: str,
        case_id: str,
        context: dict,
        previous_hashes: Set[str],
    ) -> List[Discovery]:
        """Invoke Bedrock with the Messages API and parse JSON response."""
        try:
            response = self._bedrock.invoke_model(
                modelId=model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 2000,
                    "system": self.INVESTIGATOR_PERSONA,
                    "messages": [{"role": "user", "content": prompt}],
                }),
            )
            body = json.loads(response["body"].read())
            text = body.get("content", [{}])[0].get("text", "")
        except Exception as e:
            logger.error("Bedrock invocation failed: %s", str(e)[:200])
            return []

        if not text:
            return []

        return self._parse_discoveries_response(text, previous_hashes)

    def _parse_discoveries_response(
        self, text: str, previous_hashes: Set[str],
    ) -> List[Discovery]:
        """Parse Bedrock JSON response into Discovery objects."""
        # Extract JSON array from response (may have surrounding text)
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1 or end <= start:
            logger.error("Could not find JSON array in Bedrock response")
            return []

        try:
            items = json.loads(text[start : end + 1])
        except json.JSONDecodeError as e:
            logger.error("Failed to parse Bedrock JSON: %s", str(e)[:200])
            return []

        if not isinstance(items, list):
            return []

        discoveries: List[Discovery] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            narrative = str(item.get("narrative", ""))
            if not narrative:
                continue

            content_hash = hashlib.sha256(narrative.encode("utf-8")).hexdigest()

            # Skip if this hash was already seen
            if content_hash in previous_hashes:
                continue

            entities = item.get("entities", [])
            if not isinstance(entities, list):
                entities = []
            entities = [str(e) for e in entities if e]

            discovery_type = str(item.get("discovery_type", "document_pattern"))
            if discovery_type not in VALID_DISCOVERY_TYPES:
                discovery_type = "document_pattern"

            confidence = float(item.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))

            discoveries.append(Discovery(
                discovery_id=str(uuid.uuid4()),
                narrative=narrative,
                discovery_type=discovery_type,
                entities=entities,
                confidence=confidence,
                content_hash=content_hash,
            ))

        return discoveries

    # ------------------------------------------------------------------
    # Fallback discoveries
    # ------------------------------------------------------------------

    def _generate_fallback_discoveries(
        self, case_id: str, context: dict,
    ) -> List[Discovery]:
        """Generate 2+ discoveries from available context without Bedrock.

        Uses entity counts, temporal patterns, and relationship data to
        frame narrative discoveries.
        """
        discoveries: List[Discovery] = []
        entities = context.get("entities", [])
        temporal = context.get("temporal", [])
        doc_count = context.get("doc_count", 0)
        neighborhoods = context.get("neighborhoods", {})

        # --- Fallback 1: Entity cluster discovery ---
        if len(entities) >= 2:
            top = entities[:3]
            names = [e["name"] for e in top]
            counts = [str(e["count"]) for e in top]
            narrative = (
                f"Did you know that {names[0]} appears {counts[0]} times across the case evidence, "
                f"making it the most frequently referenced entity? "
                f"Together with {' and '.join(names[1:])}, these entities form the core cluster "
                f"of this investigation and warrant deeper cross-referencing."
            )
            content_hash = hashlib.sha256(narrative.encode("utf-8")).hexdigest()
            discoveries.append(Discovery(
                discovery_id=str(uuid.uuid4()),
                narrative=narrative,
                discovery_type="entity_cluster",
                entities=names,
                confidence=min(0.7, 0.3 + len(entities) * 0.02),
                content_hash=content_hash,
            ))

        # --- Fallback 2: Temporal pattern discovery ---
        if len(temporal) >= 2:
            periods = temporal
            max_period = max(periods, key=lambda t: t["count"])
            min_period = min(periods, key=lambda t: t["count"])
            if max_period["count"] > 0 and min_period["count"] != max_period["count"]:
                narrative = (
                    f"Did you know that document activity peaked in {max_period['period']} "
                    f"with {max_period['count']} documents, while {min_period['period']} had only "
                    f"{min_period['count']}? This temporal variation may indicate periods of "
                    f"heightened or suppressed activity worth investigating."
                )
                content_hash = hashlib.sha256(narrative.encode("utf-8")).hexdigest()
                discoveries.append(Discovery(
                    discovery_id=str(uuid.uuid4()),
                    narrative=narrative,
                    discovery_type="temporal_insight",
                    entities=[],
                    confidence=0.5,
                    content_hash=content_hash,
                ))

        # --- Fallback 3: Relationship discovery from neighborhoods ---
        if neighborhoods:
            for entity_name, hood in list(neighborhoods.items())[:1]:
                neighbors = hood.get("neighbors", [])
                if neighbors:
                    neighbor_names = [
                        n.get("name", "") if isinstance(n, dict) else str(n)
                        for n in neighbors[:5]
                    ]
                    neighbor_names = [n for n in neighbor_names if n]
                    if neighbor_names:
                        narrative = (
                            f"Did you know that {entity_name} is connected to "
                            f"{', '.join(neighbor_names)} in the knowledge graph? "
                            f"These connections span {len(neighbor_names)} entities and may "
                            f"reveal undisclosed relationships or coordinated activity."
                        )
                        content_hash = hashlib.sha256(narrative.encode("utf-8")).hexdigest()
                        discoveries.append(Discovery(
                            discovery_id=str(uuid.uuid4()),
                            narrative=narrative,
                            discovery_type="relationship_anomaly",
                            entities=[entity_name] + neighbor_names,
                            confidence=0.5,
                            content_hash=content_hash,
                        ))

        # --- Fallback 4: Document volume discovery ---
        if doc_count > 0:
            narrative = (
                f"Did you know that this case contains {doc_count} documents? "
                f"A comprehensive review of the full document corpus may surface "
                f"patterns not visible in individual document analysis."
            )
            content_hash = hashlib.sha256(narrative.encode("utf-8")).hexdigest()
            discoveries.append(Discovery(
                discovery_id=str(uuid.uuid4()),
                narrative=narrative,
                discovery_type="document_pattern",
                entities=[],
                confidence=0.3,
                content_hash=content_hash,
            ))

        # Ensure at least 2 discoveries
        if len(discoveries) < 2:
            narrative = (
                f"Did you know that the evidence in case {case_id} may contain "
                f"hidden connections? Further analysis of entity relationships and "
                f"document timelines is recommended to uncover investigative leads."
            )
            content_hash = hashlib.sha256(narrative.encode("utf-8")).hexdigest()
            discoveries.append(Discovery(
                discovery_id=str(uuid.uuid4()),
                narrative=narrative,
                discovery_type="cross_reference",
                entities=[],
                confidence=0.3,
                content_hash=content_hash,
            ))

        return discoveries

    def _make_padding_discovery(
        self, case_id: str, context: dict, index: int,
    ) -> Discovery:
        """Create a single padding discovery to reach the 5-item target."""
        types = list(VALID_DISCOVERY_TYPES)
        discovery_type = types[index % len(types)]
        entities = context.get("entities", [])
        entity_names = [e["name"] for e in entities[:3]] if entities else []

        narrative = (
            f"Did you know that further analysis of case {case_id} may reveal "
            f"additional {discovery_type.replace('_', ' ')} findings? "
            f"Continued investigation is recommended."
        )
        content_hash = hashlib.sha256(narrative.encode("utf-8")).hexdigest()
        return Discovery(
            discovery_id=str(uuid.uuid4()),
            narrative=narrative,
            discovery_type=discovery_type,
            entities=entity_names,
            confidence=0.3,
            content_hash=content_hash,
        )

    # ------------------------------------------------------------------
    # Helper methods: history and feedback queries
    # ------------------------------------------------------------------

    def _get_previous_discovery_hashes(self, case_id: str) -> Set[str]:
        """Query discovery_history for all content_hashes of previously generated discoveries."""
        hashes: Set[str] = set()
        try:
            with self._aurora.cursor() as cur:
                cur.execute(
                    "SELECT discoveries FROM discovery_history WHERE case_id = %s",
                    (case_id,),
                )
                for row in cur.fetchall():
                    discoveries_json = row[0]
                    if isinstance(discoveries_json, str):
                        discoveries_json = json.loads(discoveries_json)
                    if isinstance(discoveries_json, list):
                        for d in discoveries_json:
                            if isinstance(d, dict) and d.get("content_hash"):
                                hashes.add(d["content_hash"])
        except Exception as e:
            logger.error("Failed to query discovery history: %s", str(e)[:200])
        return hashes

    def _get_feedback(self, case_id: str) -> List[dict]:
        """Query discovery_feedback for all feedback records for this case."""
        feedback: List[dict] = []
        try:
            with self._aurora.cursor() as cur:
                cur.execute(
                    "SELECT discovery_id, rating, discovery_type, content_hash "
                    "FROM discovery_feedback WHERE case_id = %s "
                    "ORDER BY created_at DESC",
                    (case_id,),
                )
                for row in cur.fetchall():
                    feedback.append({
                        "discovery_id": str(row[0]),
                        "rating": row[1],
                        "discovery_type": row[2],
                        "content_hash": row[3],
                    })
        except Exception as e:
            logger.error("Failed to query feedback: %s", str(e)[:200])
        return feedback

    # ------------------------------------------------------------------
    # Batch storage helpers
    # ------------------------------------------------------------------

    def _get_next_batch_number(self, case_id: str) -> int:
        """Get the next batch number for a case."""
        try:
            with self._aurora.cursor() as cur:
                cur.execute(
                    "SELECT COALESCE(MAX(batch_number), 0) + 1 "
                    "FROM discovery_history WHERE case_id = %s",
                    (case_id,),
                )
                row = cur.fetchone()
                return row[0] if row else 1
        except Exception as e:
            logger.error("Failed to get batch number: %s", str(e)[:200])
            return 1

    def _store_batch(
        self, case_id: str, batch_number: int, discoveries: List[Discovery],
    ) -> None:
        """Store a discovery batch in discovery_history."""
        try:
            with self._aurora.cursor() as cur:
                cur.execute(
                    "INSERT INTO discovery_history "
                    "(discovery_id, case_id, batch_number, discoveries) "
                    "VALUES (%s, %s, %s, %s)",
                    (
                        str(uuid.uuid4()),
                        case_id,
                        batch_number,
                        json.dumps([d.to_dict() for d in discoveries]),
                    ),
                )
        except Exception as e:
            logger.error("Failed to store discovery batch: %s", str(e)[:200])
