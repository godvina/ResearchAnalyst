"""Semantic Search Service — Bedrock Knowledge Base retrieval and AI analysis.

Provides semantic search across case file documents via Bedrock Knowledge
Bases and AI-assisted entity/pattern analysis via Bedrock Agents.

Dependencies are injected via the constructor for testability:
    - A boto3 Bedrock Agent Runtime client for retrieve and agent invocations
    - A Knowledge Base ID identifying the Bedrock Knowledge Base resource
    - A BackendFactory for multi-backend search routing
    - A CaseFileService for resolving case file metadata
    - A boto3 Bedrock Runtime client for embedding generation
"""

import json
import logging
import os
import uuid
from typing import Any, Optional, Protocol

from models.case_file import SearchTier
from models.search import AnalysisSummary, FacetedFilter, SearchResult


logger = logging.getLogger(__name__)

# Feature flag: when "false", OpenSearch is bypassed and pgvector is used
_OPENSEARCH_ENABLED = os.environ.get("OPENSEARCH_ENABLED", "true") == "true"

# ---------------------------------------------------------------------------
# Bedrock Agent Runtime client protocol (for testability)
# ---------------------------------------------------------------------------


class BedrockAgentRuntimeClient(Protocol):
    """Minimal boto3 bedrock-agent-runtime client interface."""

    def retrieve(self, **kwargs: Any) -> Any: ...

    def invoke_agent(self, **kwargs: Any) -> Any: ...


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TOP_K = 10
AGENT_ALIAS_ID = "TSTALIASID"
DEFAULT_EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v2:0"


# ---------------------------------------------------------------------------
# SemanticSearchService
# ---------------------------------------------------------------------------


class SemanticSearchService:
    """Interfaces with Bedrock Knowledge Base for semantic retrieval.

    Extended to support multi-backend search routing via BackendFactory.
    """

    def __init__(
        self,
        bedrock_agent_runtime_client: Any,
        knowledge_base_id: str,
        agent_id: str = "",
        agent_alias_id: str = AGENT_ALIAS_ID,
        backend_factory: Any = None,
        case_file_service: Any = None,
        bedrock_client: Any = None,
        embedding_model_id: str = DEFAULT_EMBEDDING_MODEL_ID,
        enterprise_knowledge_base_id: str = "",
    ) -> None:
        self._client = bedrock_agent_runtime_client
        self._knowledge_base_id = knowledge_base_id
        self._agent_id = agent_id
        self._agent_alias_id = agent_alias_id
        self._backend_factory = backend_factory
        self._case_service = case_file_service
        self._bedrock_client = bedrock_client
        self._embedding_model_id = embedding_model_id
        self._enterprise_kb_id = enterprise_knowledge_base_id

    # ------------------------------------------------------------------
    # Semantic search (multi-backend)
    # ------------------------------------------------------------------

    def search(
        self,
        case_id: str,
        query: str,
        *,
        mode: str = "semantic",
        filters: Optional[FacetedFilter] = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> list[SearchResult]:
        """Route search to the correct backend based on case file tier.

        If BackendFactory is configured, resolves the backend from the case
        file's search_tier, validates the mode, generates an embedding for
        semantic/hybrid modes, and delegates to the backend.

        When OpenSearch is disabled, falls back to the pgvector backend
        (STANDARD tier) regardless of the case file's configured tier.

        Falls back to the legacy Bedrock Knowledge Base path when no
        BackendFactory is configured (backward compatibility).
        """
        if self._backend_factory is not None and self._case_service is not None:
            # When OpenSearch is disabled, force STANDARD tier (pgvector)
            if not _OPENSEARCH_ENABLED:
                return self._search_via_backend(
                    case_id, query, mode=mode, filters=filters, top_k=top_k,
                    force_tier=SearchTier.STANDARD,
                )
            return self._search_via_backend(case_id, query, mode=mode, filters=filters, top_k=top_k)

        # Legacy path — Bedrock Knowledge Base only (semantic mode)
        return self._search_via_knowledge_base(case_id, query, top_k=top_k)

    def _search_via_backend(
        self,
        case_id: str,
        query: str,
        *,
        mode: str = "semantic",
        filters: Optional[FacetedFilter] = None,
        top_k: int = DEFAULT_TOP_K,
        force_tier: Optional[SearchTier] = None,
    ) -> list[SearchResult]:
        """Search using the multi-backend architecture."""
        if force_tier is not None:
            tier = force_tier
        else:
            case_file = self._case_service.get_case_file(case_id)
            tier = case_file.search_tier

        # Validate mode is supported for this tier
        self._backend_factory.validate_search_mode(tier, mode)

        # Standard tier rejects faceted filters
        if filters is not None and tier == SearchTier.STANDARD:
            raise ValueError(
                "Faceted filtering is not available for the standard tier. "
                "Upgrade to enterprise tier for filter support."
            )

        # Generate embedding for semantic/hybrid modes
        embedding = None
        if mode in ("semantic", "hybrid"):
            embedding = self._generate_embedding(query)

        backend = self._backend_factory.get_backend(tier)
        return backend.search(
            case_id, query, mode=mode, embedding=embedding,
            filters=filters, top_k=top_k,
        )

    def _search_via_knowledge_base(
        self,
        case_id: str,
        query: str,
        top_k: int = DEFAULT_TOP_K,
    ) -> list[SearchResult]:
        """Legacy search path using Bedrock Knowledge Base directly."""
        response = self._client.retrieve(
            knowledgeBaseId=self._knowledge_base_id,
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {
                    "numberOfResults": top_k,
                    "filter": {
                        "equals": {
                            "key": "case_file_id",
                            "value": case_id,
                        }
                    },
                }
            },
        )

        results: list[SearchResult] = []
        for item in response.get("retrievalResults", []):
            content = item.get("content", {})
            location = item.get("location", {})
            metadata = item.get("metadata", {})

            passage = content.get("text", "")
            score = item.get("score", 0.0)

            # Clamp score to [0, 1]
            score = max(0.0, min(1.0, score))

            s3_uri = location.get("s3Location", {}).get("uri", "")
            document_id = metadata.get("document_id", "")
            surrounding_context = metadata.get("surrounding_context", "")

            results.append(
                SearchResult(
                    document_id=document_id,
                    passage=passage,
                    relevance_score=score,
                    source_document_ref=s3_uri,
                    surrounding_context=surrounding_context,
                )
            )

        # Sort by relevance score descending
        results.sort(key=lambda r: r.relevance_score, reverse=True)
        return results

    # ------------------------------------------------------------------
    # Embedding generation
    # ------------------------------------------------------------------

    def _generate_embedding(self, query: str) -> list[float]:
        """Generate an embedding vector for the given query using Bedrock.

        Uses Titan v1 (1536 dims) if the OpenSearch index was built with 1536-dim
        vectors, otherwise uses the configured model.
        """
        if self._bedrock_client is None:
            raise RuntimeError(
                "Bedrock client is not configured. Cannot generate embeddings."
            )
        try:
            # Use Titan v1 for 1536-dim compatibility with existing OpenSearch index
            # Titan v2 only supports 256/512/1024 dims, not 1536
            model_id = self._embedding_model_id
            body: dict = {"inputText": query}
            if "v2" in model_id:
                model_id = "amazon.titan-embed-text-v1"
                logger.info("Using Titan v1 for 1536-dim OpenSearch compatibility")
            response = self._bedrock_client.invoke_model(
                modelId=model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body),
            )
            response_body = json.loads(response["body"].read())
            return response_body["embedding"]
        except Exception as exc:
            logger.exception("Failed to generate embedding")
            raise RuntimeError(f"Embedding generation failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Knowledge Base ID resolution
    # ------------------------------------------------------------------

    def _resolve_kb_id(self, tier: str | SearchTier) -> str:
        """Return the correct Bedrock Knowledge Base ID for the tier."""
        if isinstance(tier, str):
            tier = SearchTier(tier)
        if tier == SearchTier.ENTERPRISE and self._enterprise_kb_id:
            return self._enterprise_kb_id
        return self._knowledge_base_id

    # ------------------------------------------------------------------
    # Entity analysis
    # ------------------------------------------------------------------

    def analyze_entity(
        self,
        case_id: str,
        entity_name: str,
    ) -> AnalysisSummary:
        """AI-assisted analysis of an entity using Bedrock Agent.

        Invokes a Bedrock Agent that has access to the Knowledge Base to
        generate a structured analytical summary for the given entity.
        """
        prompt = (
            f"Provide a structured analytical summary of the entity "
            f"'{entity_name}' based on documents in case file '{case_id}'. "
            f"Include key facts, relationships, significance, and any "
            f"patterns involving this entity."
        )

        agent_response = self._invoke_agent(prompt, case_id)
        supporting = self._get_supporting_passages(case_id, entity_name)

        return AnalysisSummary(
            subject=entity_name,
            summary=agent_response["summary"],
            supporting_passages=supporting,
            confidence=agent_response["confidence"],
        )

    # ------------------------------------------------------------------
    # Pattern analysis
    # ------------------------------------------------------------------

    def analyze_pattern(
        self,
        case_id: str,
        pattern_id: str,
    ) -> AnalysisSummary:
        """AI-assisted analysis of a pattern using Bedrock Agent.

        Invokes a Bedrock Agent that has access to the Knowledge Base to
        generate a structured analytical summary for the given pattern.
        """
        prompt = (
            f"Provide a structured analytical summary of pattern "
            f"'{pattern_id}' based on documents in case file '{case_id}'. "
            f"Include the entities involved, the nature of the connections, "
            f"supporting evidence, and confidence assessment."
        )

        agent_response = self._invoke_agent(prompt, case_id)
        supporting = self._get_supporting_passages(case_id, pattern_id)

        return AnalysisSummary(
            subject=pattern_id,
            summary=agent_response["summary"],
            supporting_passages=supporting,
            confidence=agent_response["confidence"],
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _invoke_agent(self, prompt: str, case_id: str) -> dict:
        """Invoke the Bedrock Agent and parse the response.

        Returns a dict with ``summary`` (str) and ``confidence`` (float).
        """
        session_id = str(uuid.uuid4())

        response = self._client.invoke_agent(
            agentId=self._agent_id,
            agentAliasId=self._agent_alias_id,
            sessionId=session_id,
            inputText=prompt,
        )

        # The response contains an EventStream; collect completion chunks.
        completion_text = self._collect_agent_completion(response)

        # Attempt to parse structured JSON from the agent response.
        try:
            parsed = json.loads(completion_text)
            summary = parsed.get("summary", completion_text)
            confidence = float(parsed.get("confidence", 0.5))
        except (json.JSONDecodeError, ValueError):
            summary = completion_text
            confidence = 0.5

        confidence = max(0.0, min(1.0, confidence))

        return {"summary": summary, "confidence": confidence}

    @staticmethod
    def _collect_agent_completion(response: dict) -> str:
        """Collect text chunks from the Bedrock Agent EventStream."""
        chunks: list[str] = []
        event_stream = response.get("completion", [])
        for event in event_stream:
            chunk = event.get("chunk", {})
            if "bytes" in chunk:
                chunks.append(chunk["bytes"].decode("utf-8"))
        return "".join(chunks)

    def _get_supporting_passages(
        self,
        case_id: str,
        subject: str,
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Retrieve supporting passages for an entity or pattern.

        Always uses the legacy Knowledge Base path for AI analysis support,
        since analysis is driven by Bedrock Agent + KB, not the search backend.
        """
        return self._search_via_knowledge_base(case_id=case_id, query=subject, top_k=top_k)
