"""Investigative Case Assistant ChatService with RAG and graph integration.

Provides:
- send_message: classify intent, retrieve context via RAG (OpenSearch + Neptune),
  build prompt, invoke Bedrock, extract citations, log to Aurora
- get_history: get conversation history from Aurora
- share_finding: save chat exchange as investigator finding

Intent classification for commands:
  summarize, who is, connections between, documents mention, flag,
  timeline, what's missing, subpoena list
"""

import json
import logging
import re
import ssl
import urllib.request
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Intent patterns — ordered so more specific patterns match first
# ---------------------------------------------------------------------------

INTENT_PATTERNS = [
    ("summarize", re.compile(r"\bsummariz(e|ing)\b.*\bcase\b|\bcase\s+brief\b", re.I)),
    ("who_is", re.compile(r"\bwho\s+is\b", re.I)),
    ("connections", re.compile(r"\b(connections?|links?|paths?)\s+between\b", re.I)),
    ("documents_mention", re.compile(
        r"\b(documents?|docs?|files?)\s+(mention|about|reference|containing)\b", re.I,
    )),
    ("flag", re.compile(r"\bflag\b.*\b(suspicious|this)\b|\bmark\b.*\bsuspicious\b", re.I)),
    ("timeline", re.compile(r"\b(generate|build|create|show)?\s*timeline\b", re.I)),
    ("whats_missing", re.compile(r"\bwhat('?s| is)\s+missing\b|\bgap\s+analysis\b", re.I)),
    ("subpoena_list", re.compile(
        r"\bsubpoena\s+list\b|\bdraft\s+subpoena\b|\bsubpoena\b", re.I,
    )),
    # Network discovery intents
    ("network_who_list", re.compile(
        r"\bwho\s+is\s+on\b.*\b(list|network|circle)\b", re.I)),
    ("network_travel", re.compile(
        r"\bwho\s+traveled\s+with\b|\btravel.*\bpattern\b", re.I)),
    ("network_financial", re.compile(
        r"\bfinancial\s+(connections?|links?|transactions?)\s+between\b", re.I)),
    ("network_flag", re.compile(
        r"\bflag\b.*\bfor\s+investigation\b", re.I)),
    ("network_sub_case", re.compile(
        r"\bcreate\s+sub[- ]?case\s+for\b", re.I)),
    # Investigator AI-first intents
    ("flag_entity", re.compile(
        r"\bflag\b.*\b(entity|person|organization)\b.*\b(suspicious|investigate)\b", re.I)),
    ("create_lead", re.compile(
        r"\bcreate\s+(a\s+)?lead\s+for\b|\badd\s+(a\s+)?lead\b", re.I)),
    ("generate_subpoena", re.compile(
        r"\bgenerate\s+subpoena\b|\brecommend\s+subpoena\b", re.I)),
    ("co_location", re.compile(
        r"\bco[- ]?locat(ion|ed)\b|\bsame\s+(place|location)\b", re.I)),
    ("shared_documents", re.compile(
        r"\bshared\s+documents?\b|\bdocuments?\s+(?:containing|mentioning)\s+both\b", re.I)),
]


class ChatService:
    """Investigative chatbot service backed by Bedrock, OpenSearch, and Neptune."""

    def __init__(
        self,
        aurora_cm,
        bedrock_client,
        opensearch_endpoint: str,
        neptune_endpoint: str,
        neptune_port: str = "8182",
        default_model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0",
    ) -> None:
        self._db = aurora_cm
        self._bedrock = bedrock_client
        self._os_endpoint = opensearch_endpoint
        self._neptune_endpoint = neptune_endpoint
        self._neptune_port = neptune_port
        self._default_model_id = default_model_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send_message(
        self,
        case_id: str,
        message: str,
        conversation_id: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> dict:
        """Process an investigator message and return an AI response.

        Steps:
        1. Classify intent (question vs command)
        2. Retrieve context via RAG (OpenSearch + Neptune)
        3. Build prompt with case context + retrieved context + history
        4. Invoke Bedrock
        5. Extract citations
        6. Log conversation to Aurora

        Returns dict with response, citations, conversation_id, suggested_actions.
        """
        context = context or {}
        intent = self.classify_intent(message)
        model_id = context.get("llm_model_id", self._default_model_id)

        # Load existing conversation history for multi-turn memory
        history = []
        if conversation_id:
            history = self._load_conversation_messages(conversation_id)

        # RAG retrieval
        doc_context = self._search_documents(case_id, message)
        graph_context = self._query_graph(case_id, message, intent)

        # Route to specialised command handler or general Q&A
        handler = self._COMMAND_HANDLERS.get(intent)
        if handler:
            prompt = handler(self, case_id, message, doc_context, graph_context, context)
        else:
            prompt = self._build_prompt(message, doc_context, graph_context, context, history)

        # Invoke Bedrock
        raw_response = self._invoke_bedrock(prompt, model_id, history)

        # Extract citations from the response
        citations = self._extract_citations(raw_response, doc_context)

        # Persist conversation
        if not conversation_id:
            conversation_id = str(uuid4())
        user_id = context.get("user_id", "investigator")
        self._log_conversation(case_id, conversation_id, user_id, message, raw_response)

        suggested_actions = self._suggest_actions(intent, raw_response)

        return {
            "response": raw_response,
            "citations": citations,
            "conversation_id": conversation_id,
            "intent": intent,
            "suggested_actions": suggested_actions,
        }

    def get_history(self, case_id: str, limit: int = 50) -> list[dict]:
        """Return conversation history for a case from Aurora."""
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT conversation_id, user_id, messages, created_at, updated_at
                FROM chat_conversations
                WHERE case_id = %s
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (case_id, limit),
            )
            rows = cur.fetchall()

        return [
            {
                "conversation_id": str(row[0]),
                "user_id": row[1],
                "messages": row[2] if isinstance(row[2], list) else json.loads(row[2]),
                "created_at": row[3].isoformat() if row[3] else None,
                "updated_at": row[4].isoformat() if row[4] else None,
            }
            for row in rows
        ]

    def share_finding(self, case_id: str, message_content: str, user_id: str) -> dict:
        """Save a chat exchange as an investigator finding attached to the case."""
        finding_id = str(uuid4())
        now = datetime.now(timezone.utc)

        with self._db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO investigator_findings
                    (finding_id, case_id, user_id, finding_type, title, content, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    finding_id,
                    case_id,
                    user_id,
                    "chat_finding",
                    f"Chat finding — {now.strftime('%Y-%m-%d %H:%M')}",
                    message_content,
                    now,
                ),
            )

        return {
            "finding_id": finding_id,
            "case_id": case_id,
            "user_id": user_id,
            "finding_type": "chat_finding",
            "content": message_content,
            "created_at": now.isoformat(),
        }

    # ------------------------------------------------------------------
    # Intent classification
    # ------------------------------------------------------------------

    @staticmethod
    def classify_intent(message: str) -> str:
        """Classify the investigator's message into an intent.

        Returns one of the command intents or 'question' for general Q&A.
        """
        for intent_name, pattern in INTENT_PATTERNS:
            if pattern.search(message):
                return intent_name
        return "question"

    # ------------------------------------------------------------------
    # RAG retrieval — OpenSearch
    # ------------------------------------------------------------------

    def _search_documents(self, case_id: str, query: str, top_k: int = 5) -> list[dict]:
        """Search case documents in OpenSearch for relevant passages."""
        if not self._os_endpoint:
            return []

        try:
            search_body = {
                "size": top_k,
                "query": {
                    "bool": {
                        "must": [
                            {"match": {"content": query}},
                        ],
                        "filter": [
                            {"term": {"case_id": case_id}},
                        ],
                    }
                },
                "_source": ["content", "document_id", "document_name", "chunk_index", "page_number"],
            }

            url = f"https://{self._os_endpoint}/case-documents-{case_id}/_search"
            data = json.dumps(search_body).encode("utf-8")
            ctx = ssl.create_default_context()
            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                body = json.loads(resp.read().decode("utf-8"))

            hits = body.get("hits", {}).get("hits", [])
            return [
                {
                    "content": h["_source"].get("content", ""),
                    "document_id": h["_source"].get("document_id", ""),
                    "document_name": h["_source"].get("document_name", ""),
                    "chunk_index": h["_source"].get("chunk_index"),
                    "page_number": h["_source"].get("page_number"),
                    "score": h.get("_score", 0),
                }
                for h in hits
            ]
        except Exception:
            logger.exception("OpenSearch document search failed for case %s", case_id)
            return []

    # ------------------------------------------------------------------
    # RAG retrieval — Neptune graph
    # ------------------------------------------------------------------

    def _query_graph(self, case_id: str, message: str, intent: str) -> list[dict]:
        """Query Neptune knowledge graph for entity/relationship context."""
        if not self._neptune_endpoint:
            return []

        try:
            if intent == "who_is":
                return self._graph_entity_profile(case_id, message)
            elif intent == "connections":
                return self._graph_connections(case_id, message)
            else:
                return self._graph_related_entities(case_id, message)
        except Exception:
            logger.exception("Neptune graph query failed for case %s", case_id)
            return []

    def _neptune_gremlin(self, query: str) -> list:
        """Execute a Gremlin query via Neptune HTTP API."""
        url = f"https://{self._neptune_endpoint}:{self._neptune_port}/gremlin"
        data = json.dumps({"gremlin": query}).encode("utf-8")
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body.get("result", {}).get("data", {}).get("@value", [])

    def _graph_entity_profile(self, case_id: str, message: str) -> list[dict]:
        """Retrieve entity profile for 'who is' queries."""
        # Extract entity name from "who is <name>" pattern
        match = re.search(r"who\s+is\s+(.+?)[\?\.]?\s*$", message, re.I)
        if not match:
            return []
        entity_name = match.group(1).strip()
        label = f"Entity_{case_id}"
        query = (
            f"g.V().hasLabel('{label}')"
            f".has('canonical_name', TextP.containing('{_escape(entity_name)}'))"
            f".project('name','type','confidence','connections')"
            f".by('canonical_name').by('entity_type').by('confidence')"
            f".by(bothE().count())"
        )
        results = self._neptune_gremlin(query)
        return [{"type": "entity_profile", "data": results}]

    def _graph_connections(self, case_id: str, message: str) -> list[dict]:
        """Find connections between two entities."""
        match = re.search(
            r"(?:connections?|links?|paths?)\s+between\s+(.+?)\s+and\s+(.+?)[\?\.]?\s*$",
            message, re.I,
        )
        if not match:
            return []
        entity_a = match.group(1).strip()
        entity_b = match.group(2).strip()
        label = f"Entity_{case_id}"
        query = (
            f"g.V().hasLabel('{label}')"
            f".has('canonical_name', TextP.containing('{_escape(entity_a)}'))"
            f".repeat(both().simplePath()).until("
            f"has('canonical_name', TextP.containing('{_escape(entity_b)}'))"
            f".or().loops().is(3)).hasLabel('{label}')"
            f".has('canonical_name', TextP.containing('{_escape(entity_b)}'))"
            f".path().by('canonical_name')"
            f".limit(5)"
        )
        results = self._neptune_gremlin(query)
        return [{"type": "connection_paths", "entity_a": entity_a, "entity_b": entity_b, "data": results}]

    def _graph_related_entities(self, case_id: str, message: str, limit: int = 10) -> list[dict]:
        """Get entities related to terms in the message."""
        # Extract key terms (simple heuristic: words > 3 chars, not stop words)
        stop_words = {"what", "where", "when", "which", "that", "this", "from", "with", "about", "have", "does"}
        terms = [w for w in re.findall(r"\b\w{4,}\b", message.lower()) if w not in stop_words]
        if not terms:
            return []

        label = f"Entity_{case_id}"
        conditions = " | ".join(
            f"TextP.containing('{_escape(t)}')" for t in terms[:3]
        )
        # Use first term for simplicity in Gremlin
        first_term = _escape(terms[0])
        query = (
            f"g.V().hasLabel('{label}')"
            f".has('canonical_name', TextP.containing('{first_term}'))"
            f".project('name','type','confidence')"
            f".by('canonical_name').by('entity_type').by('confidence')"
            f".limit({limit})"
        )
        results = self._neptune_gremlin(query)
        return [{"type": "related_entities", "data": results}]

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        message: str,
        doc_context: list[dict],
        graph_context: list[dict],
        case_context: dict,
        history: list[dict] | None = None,
    ) -> str:
        """Assemble system prompt + case context + retrieved context + user message."""
        parts = [self._system_prompt()]

        # Case context (current entity, graph filter, etc.)
        if case_context.get("current_entity"):
            parts.append(f"\n[Current Entity Focus: {case_context['current_entity']}]")
        if case_context.get("graph_filter"):
            parts.append(f"\n[Active Graph Filter: {case_context['graph_filter']}]")

        # Document context from OpenSearch RAG
        if doc_context:
            parts.append("\n--- Retrieved Document Context ---")
            for i, doc in enumerate(doc_context, 1):
                ref = doc.get("document_name", doc.get("document_id", "unknown"))
                page = doc.get("page_number", "")
                page_str = f" (page {page})" if page else ""
                parts.append(f"\n[Source {i}: {ref}{page_str}]\n{doc.get('content', '')}")

        # Graph context from Neptune
        if graph_context:
            parts.append("\n--- Knowledge Graph Context ---")
            for item in graph_context:
                parts.append(f"\n[{item.get('type', 'graph')}]: {json.dumps(item.get('data', []), default=str)}")

        # Conversation history for multi-turn memory
        if history:
            parts.append("\n--- Conversation History ---")
            for msg in history[-10:]:  # last 10 messages
                role = msg.get("role", "user")
                parts.append(f"\n{role}: {msg.get('content', '')}")

        parts.append(f"\n\nInvestigator: {message}")
        return "\n".join(parts)

    @staticmethod
    def _system_prompt() -> str:
        """Return the system prompt for the investigative assistant."""
        return (
            "You are an AI investigative case assistant for the DOJ. "
            "You help investigators analyze case evidence, explore entity connections, "
            "identify patterns, and generate investigative insights. "
            "Always cite specific documents and sources for factual claims using "
            "[Source N] notation. Be precise, factual, and thorough. "
            "If you are uncertain, say so. Never fabricate evidence or connections."
        )

    # ------------------------------------------------------------------
    # Command-specific prompt builders
    # ------------------------------------------------------------------

    def _handle_summarize(self, case_id, message, doc_ctx, graph_ctx, ctx):
        return self._build_prompt(
            "Generate a comprehensive case brief summarizing all evidence, "
            "key entities, relationships, and investigative findings. "
            "Structure the brief with sections: Overview, Key Subjects, "
            "Evidence Summary, Connections, and Recommended Next Steps.",
            doc_ctx, graph_ctx, ctx,
        )

    def _handle_who_is(self, case_id, message, doc_ctx, graph_ctx, ctx):
        return self._build_prompt(
            f"{message}\n\nProvide a complete entity profile including all known "
            "connections, document references, timeline of appearances, and "
            "any suspicious patterns. Cite every source.",
            doc_ctx, graph_ctx, ctx,
        )

    def _handle_connections(self, case_id, message, doc_ctx, graph_ctx, ctx):
        return self._build_prompt(
            f"{message}\n\nAnalyze the paths between these entities. Explain each "
            "connection, the strength of evidence, and any indirect links. "
            "Highlight the most significant connections.",
            doc_ctx, graph_ctx, ctx,
        )

    def _handle_documents_mention(self, case_id, message, doc_ctx, graph_ctx, ctx):
        return self._build_prompt(
            f"{message}\n\nList all documents that mention this topic with relevant "
            "excerpts. Group by document and include page references.",
            doc_ctx, graph_ctx, ctx,
        )

    def _handle_flag(self, case_id, message, doc_ctx, graph_ctx, ctx):
        return self._build_prompt(
            f"{message}\n\nAcknowledge the flag and explain what evidence supports "
            "marking this as suspicious. Suggest related items to investigate.",
            doc_ctx, graph_ctx, ctx,
        )

    def _handle_timeline(self, case_id, message, doc_ctx, graph_ctx, ctx):
        return self._build_prompt(
            "Generate a chronological timeline of events from case evidence. "
            "Include dates, involved entities, and source documents for each event. "
            "Highlight gaps in the timeline.",
            doc_ctx, graph_ctx, ctx,
        )

    def _handle_whats_missing(self, case_id, message, doc_ctx, graph_ctx, ctx):
        return self._build_prompt(
            "Analyze the case evidence for gaps. Compare entity types present "
            "against what would be expected for this type of investigation. "
            "Identify missing connections, unexplored leads, and evidence gaps. "
            "Prioritize the most critical gaps.",
            doc_ctx, graph_ctx, ctx,
        )

    def _handle_subpoena_list(self, case_id, message, doc_ctx, graph_ctx, ctx):
        return self._build_prompt(
            "Based on evidence gaps and investigative leads, draft a suggested "
            "subpoena list. For each item, specify: the entity or document target, "
            "the custodian, the justification based on existing evidence, and "
            "the expected evidentiary value. Prioritize by investigative impact.",
            doc_ctx, graph_ctx, ctx,
        )

    # ------------------------------------------------------------------
    # Network discovery command handlers
    # ------------------------------------------------------------------

    def _handle_network_who_list(self, case_id, message, doc_ctx, graph_ctx, ctx):
        """Query network analysis for persons of interest matching criteria."""
        return self._build_prompt(
            f"{message}\n\nUsing the network analysis results, list all persons of "
            "interest with their Connection Strength, Involvement Score, Risk Level, "
            "and the number of evidence documents. Sort by Involvement Score descending. "
            "For each person, briefly explain why they are flagged.",
            doc_ctx, graph_ctx, ctx,
        )

    def _handle_network_travel(self, case_id, message, doc_ctx, graph_ctx, ctx):
        """Query Neptune for co-location relationships filtered by person and location."""
        return self._build_prompt(
            f"{message}\n\nAnalyze geographic co-location patterns from the knowledge graph. "
            "List all locations where the specified person appears alongside other persons "
            "of interest. Include document references and dates where available.",
            doc_ctx, graph_ctx, ctx,
        )

    def _handle_network_financial(self, case_id, message, doc_ctx, graph_ctx, ctx):
        """Query Neptune for financial relationship paths between entities."""
        return self._build_prompt(
            f"{message}\n\nTrace all financial relationship paths between the specified "
            "entities in the knowledge graph. Include transaction details, intermediary "
            "entities (shell companies, accounts), and supporting document references.",
            doc_ctx, graph_ctx, ctx,
        )

    def _handle_network_flag(self, case_id, message, doc_ctx, graph_ctx, ctx):
        """Flag a person for investigation via the decision workflow."""
        return self._build_prompt(
            f"{message}\n\nAcknowledge the investigation flag request. Summarize the "
            "evidence supporting this person's flagging, their current risk level and "
            "involvement score, and recommend immediate investigative steps.",
            doc_ctx, graph_ctx, ctx,
        )

    def _handle_network_sub_case(self, case_id, message, doc_ctx, graph_ctx, ctx):
        """Trigger sub-case spawning workflow for specified person."""
        return self._build_prompt(
            f"{message}\n\nInitiate a sub-case proposal for the specified person. "
            "Summarize the evidence justifying a separate investigation, list proposed "
            "charges with statute citations, and outline recommended investigative steps.",
            doc_ctx, graph_ctx, ctx,
        )

    # ------------------------------------------------------------------
    # Investigator AI-first command handlers
    # ------------------------------------------------------------------

    def _handle_flag_entity(self, case_id, message, doc_ctx, graph_ctx, ctx):
        return self._build_prompt(
            f"{message}\n\nFlag this entity for investigation. Summarize the evidence "
            "supporting the flag, assess risk level, and recommend immediate actions.",
            doc_ctx, graph_ctx, ctx,
        )

    def _handle_create_lead(self, case_id, message, doc_ctx, graph_ctx, ctx):
        return self._build_prompt(
            f"{message}\n\nCreate an investigative lead. Provide the entity name, "
            "priority justification, evidence strength assessment, and recommended actions.",
            doc_ctx, graph_ctx, ctx,
        )

    def _handle_generate_subpoena(self, case_id, message, doc_ctx, graph_ctx, ctx):
        return self._build_prompt(
            f"{message}\n\nGenerate subpoena recommendations based on current evidence gaps "
            "and active leads. For each, specify target, custodian, legal basis, and expected value.",
            doc_ctx, graph_ctx, ctx,
        )

    def _handle_co_location(self, case_id, message, doc_ctx, graph_ctx, ctx):
        return self._build_prompt(
            f"{message}\n\nQuery co-location relationships from the knowledge graph. "
            "List all persons found at the same location with dates and document references.",
            doc_ctx, graph_ctx, ctx,
        )

    def _handle_shared_documents(self, case_id, message, doc_ctx, graph_ctx, ctx):
        return self._build_prompt(
            f"{message}\n\nFind documents containing both specified entities. "
            "Return a structured table with document names, relevance scores, and key excerpts.",
            doc_ctx, graph_ctx, ctx,
        )

    # Map intent names to handler methods
    _COMMAND_HANDLERS = {
        "summarize": _handle_summarize,
        "who_is": _handle_who_is,
        "connections": _handle_connections,
        "documents_mention": _handle_documents_mention,
        "flag": _handle_flag,
        "timeline": _handle_timeline,
        "whats_missing": _handle_whats_missing,
        "subpoena_list": _handle_subpoena_list,
        "network_who_list": _handle_network_who_list,
        "network_travel": _handle_network_travel,
        "network_financial": _handle_network_financial,
        "network_flag": _handle_network_flag,
        "network_sub_case": _handle_network_sub_case,
        "flag_entity": _handle_flag_entity,
        "create_lead": _handle_create_lead,
        "generate_subpoena": _handle_generate_subpoena,
        "co_location": _handle_co_location,
        "shared_documents": _handle_shared_documents,
    }

    # ------------------------------------------------------------------
    # Bedrock invocation
    # ------------------------------------------------------------------

    def _invoke_bedrock(self, prompt: str, model_id: str, history: list[dict] | None = None) -> str:
        """Call Bedrock with the assembled prompt using the case-configured LLM model."""
        try:
            messages = []

            # Include conversation history for multi-turn
            if history:
                for msg in history[-10:]:
                    messages.append({
                        "role": msg.get("role", "user"),
                        "content": [{"type": "text", "text": msg.get("content", "")}],
                    })

            messages.append({
                "role": "user",
                "content": [{"type": "text", "text": prompt}],
            })

            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "system": self._system_prompt(),
                "messages": messages,
            }

            response = self._bedrock.invoke_model(
                modelId=model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body),
            )

            response_body = json.loads(response["body"].read())
            content_blocks = response_body.get("content", [])
            return "".join(
                block.get("text", "") for block in content_blocks if block.get("type") == "text"
            )
        except Exception:
            logger.exception("Bedrock invocation failed with model %s", model_id)
            return "I'm sorry, I encountered an error generating a response. Please try again."

    # ------------------------------------------------------------------
    # Citation extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_citations(response: str, doc_context: list[dict]) -> list[dict]:
        """Link [Source N] references in the response to actual documents."""
        citations = []
        seen = set()
        for match in re.finditer(r"\[Source\s+(\d+)\]", response):
            idx = int(match.group(1)) - 1  # 1-based in text
            if 0 <= idx < len(doc_context) and idx not in seen:
                seen.add(idx)
                doc = doc_context[idx]
                citations.append({
                    "source_index": idx + 1,
                    "document_id": doc.get("document_id", ""),
                    "document_name": doc.get("document_name", ""),
                    "page_number": doc.get("page_number"),
                    "excerpt": doc.get("content", "")[:200],
                })
        return citations

    # ------------------------------------------------------------------
    # Conversation persistence
    # ------------------------------------------------------------------

    def _load_conversation_messages(self, conversation_id: str) -> list[dict]:
        """Load messages from an existing conversation."""
        with self._db.cursor() as cur:
            cur.execute(
                "SELECT messages FROM chat_conversations WHERE conversation_id = %s",
                (conversation_id,),
            )
            row = cur.fetchone()

        if row is None:
            return []
        messages = row[0] if isinstance(row[0], list) else json.loads(row[0])
        return messages

    def _log_conversation(
        self,
        case_id: str,
        conversation_id: str,
        user_id: str,
        user_message: str,
        assistant_response: str,
    ) -> None:
        """Persist conversation turn to Aurora for audit trail."""
        now = datetime.now(timezone.utc)
        new_messages = [
            {"role": "user", "content": user_message, "timestamp": now.isoformat()},
            {"role": "assistant", "content": assistant_response, "timestamp": now.isoformat()},
        ]

        with self._db.cursor() as cur:
            # Upsert: insert new conversation or append to existing
            cur.execute(
                """
                INSERT INTO chat_conversations (conversation_id, case_id, user_id, messages, created_at, updated_at)
                VALUES (%s, %s, %s, %s::jsonb, %s, %s)
                ON CONFLICT (conversation_id) DO UPDATE
                SET messages = chat_conversations.messages || %s::jsonb,
                    updated_at = %s
                """,
                (
                    conversation_id, case_id, user_id,
                    json.dumps(new_messages), now, now,
                    json.dumps(new_messages), now,
                ),
            )

    # ------------------------------------------------------------------
    # Suggested actions
    # ------------------------------------------------------------------

    @staticmethod
    def _suggest_actions(intent: str, response: str) -> list[str]:
        """Suggest follow-up actions based on the intent and response."""
        suggestions = {
            "question": ["Ask a follow-up question", "Search for related documents", "View entity graph"],
            "summarize": ["Generate timeline", "Identify gaps", "Draft subpoena list"],
            "who_is": ["Find connections", "Search related documents", "Flag as suspicious"],
            "connections": ["View in graph explorer", "Search for more evidence", "Generate timeline"],
            "documents_mention": ["Summarize findings", "Find connections", "Flag documents"],
            "flag": ["Share finding", "Search for corroborating evidence", "View entity profile"],
            "timeline": ["Identify gaps", "Find connections", "Draft subpoena list"],
            "whats_missing": ["Draft subpoena list", "Search for evidence", "Generate case brief"],
            "subpoena_list": ["Share finding", "Generate case brief", "Review timeline"],
        }
        return suggestions.get(intent, suggestions["question"])


def _escape(s: str) -> str:
    """Escape single quotes for Gremlin query strings."""
    return s.replace("'", "\\'").replace("\\", "\\\\")
