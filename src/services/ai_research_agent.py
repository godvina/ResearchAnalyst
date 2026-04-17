"""AI Research Agent — generates synthetic research documents per subject.

Uses Bedrock Claude Haiku to produce structured research text for each
subject in a lead, incorporating OSINT directives and evidence hints.
Results are formatted for ingestion through the existing Step Functions pipeline.
"""

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MODEL_ID = os.environ.get("BEDROCK_LLM_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")


def _slug(name: str) -> str:
    """Convert a name to a filesystem-safe slug."""
    s = name.lower().strip().replace(" ", "_")
    return re.sub(r"[^a-z0-9_]", "", s) or "unknown"


class AIResearchAgent:
    """Generates research documents for lead subjects via Bedrock Haiku."""

    def __init__(self, bedrock_client=None):
        self._bedrock = bedrock_client

    def _get_bedrock(self):
        if self._bedrock is None:
            import boto3
            from botocore.config import Config
            cfg = Config(read_timeout=120, connect_timeout=10,
                         retries={"max_attempts": 2, "mode": "adaptive"})
            self._bedrock = boto3.client("bedrock-runtime", config=cfg)
        return self._bedrock

    def _call_bedrock(self, prompt: str) -> str:
        """Call Bedrock Haiku with retry logic."""
        bedrock = self._get_bedrock()
        resp = bedrock.invoke_model(
            modelId=MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            }),
        )
        body = json.loads(resp["body"].read().decode("utf-8"))
        return body.get("content", [{}])[0].get("text", "")

    def _build_research_prompt(self, subject: dict, osint_directives: list[str],
                                evidence_hints: list[dict]) -> str:
        """Build the Bedrock prompt for subject research."""
        name = subject.get("name", "Unknown")
        stype = subject.get("type", "unknown")
        role = subject.get("role", "")
        aliases = subject.get("aliases", [])
        identifiers = subject.get("identifiers", {})

        alias_text = f"Aliases: {', '.join(aliases)}" if aliases else ""
        id_text = "\n".join(f"  {k}: {v}" for k, v in identifiers.items()) if identifiers else ""

        # Filter evidence hints relevant to this subject
        relevant_hints = []
        for h in evidence_hints:
            relevant = h.get("relevant_subjects", [])
            if not relevant or name in relevant:
                relevant_hints.append(h)

        hints_text = ""
        if relevant_hints:
            hints_text = "EVIDENCE HINTS:\n" + "\n".join(
                f"- {h.get('description', '')} (URL: {h.get('url', 'N/A')})"
                for h in relevant_hints
            )

        directives_text = ""
        if osint_directives:
            directives_text = "OSINT DIRECTIVES:\n" + "\n".join(f"- {d}" for d in osint_directives)

        return f"""You are a senior DOJ investigative research analyst. Generate a comprehensive
research report on the following subject using publicly available information.

SUBJECT: {name}
TYPE: {stype}
ROLE: {role}
{alias_text}
{f"IDENTIFIERS:{chr(10)}{id_text}" if id_text else ""}

{hints_text}

{directives_text}

Produce a structured research report with these sections:
== PUBLIC RECORDS ==
(SEC filings, corporate registrations, property records, bankruptcy filings)

== NEWS AND MEDIA ==
(News articles, press releases, investigative journalism)

== REGULATORY ==
(OFAC/SDN matches, sanctions, enforcement actions, regulatory filings)

== EVIDENCE HINTS ==
(Analysis of the evidence hints provided above)

== OSINT FINDINGS ==
(Results from the OSINT directives above)

== CONNECTIONS ==
(Known relationships, business associations, co-directors, shared addresses)

Be specific and factual. If you don't have information for a section, state "No public records found."
Include dates, amounts, and specific references where possible."""

    def research_subject(self, subject: dict, osint_directives: list[str],
                          evidence_hints: list[dict]) -> str:
        """Generate a research document for a single subject."""
        prompt = self._build_research_prompt(subject, osint_directives, evidence_hints)
        text = self._call_bedrock(prompt)

        name = subject.get("name", "Unknown")
        stype = subject.get("type", "unknown")
        now = datetime.now(timezone.utc).isoformat()

        header = f"RESEARCH REPORT: {name}\nGenerated: {now}\nSubject Type: {stype}\n\n"
        return header + text

    def research_all_subjects(self, subjects: list[dict], osint_directives: list[str],
                               evidence_hints: list[dict]) -> list[dict]:
        """Research all subjects sequentially. Continues on individual failure."""
        results = []
        for subj in subjects:
            name = subj.get("name", "Unknown")
            slug = _slug(name)
            try:
                text = self.research_subject(subj, osint_directives, evidence_hints)
                results.append({
                    "subject_name": name,
                    "slug": slug,
                    "research_text": text,
                    "success": True,
                    "error": None,
                })
                logger.info("Research complete for subject: %s", name)
            except Exception as exc:
                logger.error("Research failed for subject '%s': %s", name, str(exc)[:200])
                results.append({
                    "subject_name": name,
                    "slug": slug,
                    "research_text": "",
                    "success": False,
                    "error": str(exc)[:500],
                })
        return results
