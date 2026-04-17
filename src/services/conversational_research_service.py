"""Conversational Research Service — multi-turn external research with AIResearchAgent.

Wraps AIResearchAgent with conversation state stored in Aurora PostgreSQL.
Supports:
- start_conversation: initial OSINT report + conversation record creation
- continue_conversation: follow-up with intent detection (refine/drill/general)

Uses Bedrock Haiku for speed-critical synthesis within the 29s API Gateway budget.
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from services.ai_research_agent import AIResearchAgent

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

HAIKU_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"

# Intent detection patterns for follow-up messages
REFINE_PATTERN = re.compile(r"\b(refine|search\s+for|look\s+up)\b", re.I)
DRILL_PATTERN = re.compile(r"\b(drill\s+deeper|more\s+about|expand\s+on)\b", re.I)

# Maximum messages to include as context in Bedrock invocations
MAX_CONTEXT_MESSAGES = 10


class ConversationalResearchService:
    """Multi-turn conversational research backed by AIResearchAgent and Bedrock Haiku."""

    def __init__(self, aurora_cm, bedrock_client, research_agent: AIResearchAgent):
        self._aurora = aurora_cm
        self._bedrock = bedrock_client
        self._agent = research_agent

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_conversation(self, case_id: str, subject: dict) -> dict:
        """Generate initial OSINT report and create conversation record.

        Args:
            case_id: UUID of the case.
            subject: dict with 'name' and 'type' keys.

        Returns:
            dict with response, conversation_id, sources, suggested_followups.
        """
        subject_name = subject.get("name", "Unknown")
        subject_type = subject.get("type", "person")

        # 1. Call AIResearchAgent for initial OSINT report
        try:
            research_text = self._agent.research_subject(
                {"name": subject_name, "type": subject_type},
                osint_directives=[],
                evidence_hints=[],
            )
        except Exception:
            logger.exception("AIResearchAgent failed for subject %s", subject_name)
            raise

        # 2. Extract sources from the research text (URLs if present)
        sources = self._extract_sources(research_text)

        # 3. Create conversation record in Aurora
        conversation_id = str(uuid4())
        now = datetime.now(timezone.utc)
        initial_messages = [
            {
                "role": "user",
                "content": f"Research {subject_name} ({subject_type})",
                "timestamp": now.isoformat(),
                "sources": [],
            },
            {
                "role": "assistant",
                "content": research_text,
                "timestamp": now.isoformat(),
                "sources": sources,
            },
        ]

        with self._aurora.cursor() as cur:
            cur.execute(
                """
                INSERT INTO research_conversations
                    (conversation_id, case_id, subject_name, subject_type,
                     messages, research_context, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s)
                """,
                (
                    conversation_id, case_id, subject_name, subject_type,
                    json.dumps(initial_messages),
                    json.dumps({"subject": subject, "initial_report": research_text[:2000]}),
                    now, now,
                ),
            )

        # 4. Generate suggested follow-ups
        suggested_followups = self._generate_followups(research_text, subject_name)

        return {
            "response": research_text,
            "conversation_id": conversation_id,
            "sources": sources,
            "suggested_followups": suggested_followups,
        }

    def continue_conversation(self, case_id: str, conversation_id: str,
                               message: str) -> dict:
        """Process a follow-up message with prior context.

        Args:
            case_id: UUID of the case.
            conversation_id: UUID of the existing conversation.
            message: The follow-up message from the investigator.

        Returns:
            dict with response, conversation_id, sources, suggested_followups.

        Raises:
            ValueError: If conversation_id is not found.
        """
        # 1. Load conversation history from Aurora
        conv_record = self._load_conversation(conversation_id)
        if conv_record is None:
            raise ValueError(f"Conversation not found: {conversation_id}")

        messages = conv_record["messages"]
        subject_name = conv_record["subject_name"]

        # 2. Detect intent
        intent = self._detect_intent(message)

        # 3. Generate response based on intent
        if intent == "refine":
            response_text, sources = self._handle_refine(message, subject_name, messages)
        elif intent == "drill_deeper":
            response_text, sources = self._handle_drill_deeper(message, messages)
        else:
            response_text, sources = self._handle_general(message, messages)

        # 4. Append new messages to Aurora
        now = datetime.now(timezone.utc)
        new_messages = [
            {
                "role": "user",
                "content": message,
                "timestamp": now.isoformat(),
                "sources": [],
            },
            {
                "role": "assistant",
                "content": response_text,
                "timestamp": now.isoformat(),
                "sources": sources,
            },
        ]

        with self._aurora.cursor() as cur:
            cur.execute(
                """
                UPDATE research_conversations
                SET messages = messages || %s::jsonb,
                    updated_at = %s
                WHERE conversation_id = %s
                """,
                (json.dumps(new_messages), now, conversation_id),
            )

        # 5. Generate suggested follow-ups
        suggested_followups = self._generate_followups(response_text, subject_name)

        return {
            "response": response_text,
            "conversation_id": conversation_id,
            "sources": sources,
            "suggested_followups": suggested_followups,
        }

    # ------------------------------------------------------------------
    # Intent detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_intent(message: str) -> str:
        """Classify follow-up message intent.

        Returns:
            'refine' — new external search via AIResearchAgent
            'drill_deeper' — focused deep-dive on a referenced finding
            'general' — contextual Bedrock response
        """
        if REFINE_PATTERN.search(message):
            return "refine"
        if DRILL_PATTERN.search(message):
            return "drill_deeper"
        return "general"

    # ------------------------------------------------------------------
    # Intent handlers
    # ------------------------------------------------------------------

    def _handle_refine(self, message: str, subject_name: str,
                       messages: list[dict]) -> tuple[str, list[dict]]:
        """Handle refine intent — new Brave query via AIResearchAgent."""
        try:
            research_text = self._agent.research_subject(
                {"name": subject_name, "type": "person"},
                osint_directives=[message],
                evidence_hints=[],
            )
            sources = self._extract_sources(research_text)
            return research_text, sources
        except Exception:
            logger.exception("Refine search failed for %s", subject_name)
            # Fall back to contextual Bedrock response
            return self._handle_general(message, messages)

    def _handle_drill_deeper(self, message: str,
                              messages: list[dict]) -> tuple[str, list[dict]]:
        """Handle drill-deeper intent — focused deep-dive using Bedrock Haiku."""
        # Extract the initial research report (first assistant message)
        initial_report = ""
        for msg in messages:
            if msg.get("role") == "assistant":
                initial_report = msg.get("content", "")
                break

        context_messages = messages[-MAX_CONTEXT_MESSAGES:]
        context_text = self._format_context(context_messages)

        prompt = (
            "You are a senior DOJ investigative research analyst. "
            "The investigator wants to drill deeper into a specific finding.\n\n"
            f"INITIAL RESEARCH REPORT:\n{initial_report[:3000]}\n\n"
            f"CONVERSATION CONTEXT:\n{context_text}\n\n"
            f"INVESTIGATOR REQUEST: {message}\n\n"
            "Provide a focused, detailed deep-dive analysis on the specific topic "
            "the investigator is asking about. Reference specific details from the "
            "initial report. Be thorough and cite any relevant information."
        )

        response_text = self._invoke_haiku(prompt)
        sources = self._extract_sources(response_text)
        return response_text, sources

    def _handle_general(self, message: str,
                        messages: list[dict]) -> tuple[str, list[dict]]:
        """Handle general follow-up — contextual Bedrock response."""
        # Include initial report for context
        initial_report = ""
        for msg in messages:
            if msg.get("role") == "assistant":
                initial_report = msg.get("content", "")
                break

        context_messages = messages[-MAX_CONTEXT_MESSAGES:]
        context_text = self._format_context(context_messages)

        prompt = (
            "You are a senior DOJ investigative research analyst. "
            "Continue the research conversation based on the context below.\n\n"
            f"INITIAL RESEARCH REPORT:\n{initial_report[:3000]}\n\n"
            f"CONVERSATION CONTEXT:\n{context_text}\n\n"
            f"INVESTIGATOR QUESTION: {message}\n\n"
            "Provide a helpful, detailed response based on the research context. "
            "If you can reference specific findings from the initial report, do so."
        )

        response_text = self._invoke_haiku(prompt)
        sources = self._extract_sources(response_text)
        return response_text, sources

    # ------------------------------------------------------------------
    # Bedrock Haiku invocation
    # ------------------------------------------------------------------

    def _invoke_haiku(self, prompt: str) -> str:
        """Invoke Bedrock Haiku for speed-critical synthesis."""
        try:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            }

            response = self._bedrock.invoke_model(
                modelId=HAIKU_MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body),
            )

            response_body = json.loads(response["body"].read())
            content_blocks = response_body.get("content", [])
            return "".join(
                block.get("text", "") for block in content_blocks
                if block.get("type") == "text"
            )
        except Exception:
            logger.exception("Bedrock Haiku invocation failed")
            return "I encountered an error generating a response. Please try again."

    # ------------------------------------------------------------------
    # Aurora helpers
    # ------------------------------------------------------------------

    def _load_conversation(self, conversation_id: str) -> Optional[dict]:
        """Load a conversation record from Aurora."""
        with self._aurora.cursor() as cur:
            cur.execute(
                """
                SELECT conversation_id, case_id, subject_name, subject_type,
                       messages, research_context, created_at, updated_at
                FROM research_conversations
                WHERE conversation_id = %s
                """,
                (conversation_id,),
            )
            row = cur.fetchone()

        if row is None:
            return None

        messages = row[4] if isinstance(row[4], list) else json.loads(row[4])
        research_context = row[5] if isinstance(row[5], dict) else json.loads(row[5])

        return {
            "conversation_id": str(row[0]),
            "case_id": str(row[1]),
            "subject_name": row[2],
            "subject_type": row[3],
            "messages": messages,
            "research_context": research_context,
            "created_at": row[6],
            "updated_at": row[7],
        }

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_context(messages: list[dict]) -> str:
        """Format conversation messages into a text block for the prompt."""
        lines = []
        for msg in messages:
            role = msg.get("role", "user").upper()
            content = msg.get("content", "")
            # Truncate long messages to keep prompt within limits
            if len(content) > 1500:
                content = content[:1500] + "..."
            lines.append(f"{role}: {content}")
        return "\n\n".join(lines)

    @staticmethod
    def _extract_sources(text: str) -> list[dict]:
        """Extract URL references from research text."""
        sources = []
        seen = set()
        for match in re.finditer(r"https?://[^\s\)\"'>]+", text):
            url = match.group(0).rstrip(".,;:")
            if url not in seen:
                seen.add(url)
                sources.append({
                    "title": url.split("/")[-1][:80] or url[:80],
                    "url": url,
                    "snippet": "",
                })
        return sources

    @staticmethod
    def _generate_followups(response_text: str, subject_name: str) -> list[str]:
        """Generate suggested follow-up questions based on response content."""
        followups = []

        if "SEC" in response_text or "filing" in response_text.lower():
            followups.append(f"Drill deeper into SEC filings for {subject_name}")
        if "corporate" in response_text.lower() or "company" in response_text.lower():
            followups.append(f"Search for related corporate entities of {subject_name}")
        if "connection" in response_text.lower() or "associate" in response_text.lower():
            followups.append(f"Expand on known connections of {subject_name}")
        if "property" in response_text.lower() or "real estate" in response_text.lower():
            followups.append(f"Look up property records for {subject_name}")

        # Always include a compare suggestion
        followups.append("Compare with internal evidence")

        # Cap at 4 suggestions
        return followups[:4]
