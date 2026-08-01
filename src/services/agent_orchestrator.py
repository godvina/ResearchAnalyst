"""Agent Orchestrator — Runs investigative intelligence agents in sequence.

The orchestrator manages a library of specialized research agents and
triggers them based on findings. When one agent completes, the orchestrator
evaluates what was found and decides which agent(s) to run next.

This is the "threat hunter auto-query" system — it generates the next
investigation step automatically based on what the current step revealed.

Architecture:
    AgentOrchestrator
    ├── AgentRegistry (library of available agents)
    ├── TriggerEngine (decides which agent to run next)
    ├── ContextManager (passes findings between agents)
    └── ResultStore (persists all findings)
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

import boto3
import requests

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class AgentStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class TriggerType(Enum):
    MANUAL = "manual"              # Human explicitly triggers
    ON_FINDINGS = "on_findings"    # Triggered by specific findings from another agent
    ON_SIGNATURE = "on_signature"  # Triggered when a specific signature matches
    ON_COUNT = "on_count"          # Triggered when N+ nodes match a condition
    SCHEDULED = "scheduled"        # Triggered periodically


@dataclass
class AgentDefinition:
    """Defines an investigative agent's configuration."""
    id: str
    name: str
    description: str
    trigger_type: TriggerType
    trigger_condition: dict  # Varies by trigger_type
    research_strategy: str   # Description of what queries to run
    taxonomy_scope: list     # Which signature IDs this agent checks
    follow_up_agents: list   # Agent IDs to potentially trigger after completion
    handler: Optional[Callable] = None  # The function that executes this agent
    priority: int = 5        # 1=highest, 10=lowest


@dataclass
class AgentResult:
    """Output from an agent execution."""
    agent_id: str
    status: AgentStatus
    findings: dict = field(default_factory=dict)
    signature_matches: list = field(default_factory=list)
    suggested_follow_ups: list = field(default_factory=list)
    execution_time_ms: int = 0
    error: Optional[str] = None


@dataclass
class InvestigationContext:
    """Shared context passed between agents in a chain."""
    investigation_id: str
    domain: str
    initial_trigger: str
    accumulated_findings: list = field(default_factory=list)
    signature_matches: dict = field(default_factory=dict)  # sig_id → count
    agents_run: list = field(default_factory=list)
    current_depth: int = 0
    max_depth: int = 5  # Safety: don't recurse forever


class AgentOrchestrator:
    """Manages and executes investigative intelligence agents.

    Usage:
        orchestrator = AgentOrchestrator()
        orchestrator.register_agent(broad_scanner)
        orchestrator.register_agent(taxonomy_scanner)
        
        # Run a full investigation chain
        results = orchestrator.investigate("ley_line_alignments", trigger="human")
    """

    def __init__(self, max_chain_depth: int = 5):
        self._agents: dict[str, AgentDefinition] = {}
        self._max_depth = max_chain_depth
        self._results_history: list[AgentResult] = []

    def register_agent(self, agent: AgentDefinition) -> None:
        """Register an agent in the library."""
        self._agents[agent.id] = agent
        logger.info("Registered agent: %s (%s)", agent.id, agent.name)

    def list_agents(self) -> list[dict]:
        """List all registered agents."""
        return [
            {
                "id": a.id,
                "name": a.name,
                "description": a.description,
                "trigger_type": a.trigger_type.value,
                "priority": a.priority,
                "taxonomy_scope": a.taxonomy_scope,
            }
            for a in sorted(self._agents.values(), key=lambda x: x.priority)
        ]

    def investigate(self, topic: str, trigger: str = "manual", context: Optional[InvestigationContext] = None) -> list[AgentResult]:
        """Run a full investigation chain starting from a topic.

        The orchestrator:
        1. Starts with the Broad Scanner agent
        2. Evaluates findings
        3. Triggers follow-up agents based on what was found
        4. Repeats until no more follow-ups or max depth reached

        Args:
            topic: What to investigate (e.g., "ley_line_alignments")
            trigger: What triggered this investigation
            context: Optional existing context to continue from

        Returns:
            List of all AgentResults from the chain
        """
        if context is None:
            context = InvestigationContext(
                investigation_id=f"inv_{int(time.time())}",
                domain=topic,
                initial_trigger=trigger,
                max_depth=self._max_depth,
            )

        all_results = []
        agents_to_run = self._get_initial_agents(trigger)

        while agents_to_run and context.current_depth < context.max_depth:
            context.current_depth += 1
            next_round = []

            for agent_id in agents_to_run:
                agent = self._agents.get(agent_id)
                if not agent:
                    continue

                logger.info(
                    "Running agent '%s' (depth %d/%d)",
                    agent.name, context.current_depth, context.max_depth,
                )

                # Execute agent
                result = self._execute_agent(agent, context)
                all_results.append(result)
                self._results_history.append(result)
                context.agents_run.append(agent_id)

                if result.status == AgentStatus.COMPLETE:
                    # Accumulate findings
                    context.accumulated_findings.append(result.findings)
                    for sig in result.signature_matches:
                        sig_id = sig if isinstance(sig, str) else sig.get("signature_id", "")
                        context.signature_matches[sig_id] = context.signature_matches.get(sig_id, 0) + 1

                    # Determine follow-up agents
                    follow_ups = self._evaluate_follow_ups(agent, result, context)
                    next_round.extend(follow_ups)

            # Deduplicate and filter already-run agents
            agents_to_run = [a for a in set(next_round) if a not in context.agents_run]

        return all_results

    def _get_initial_agents(self, trigger: str) -> list[str]:
        """Determine which agents to run first based on trigger type."""
        if trigger == "manual":
            # Start with broad scanner
            return [a.id for a in self._agents.values() if a.trigger_type == TriggerType.MANUAL]
        
        # For automatic triggers, find matching agents
        return [
            a.id for a in self._agents.values()
            if a.trigger_type == TriggerType.MANUAL and a.priority <= 3
        ]

    def _execute_agent(self, agent: AgentDefinition, context: InvestigationContext) -> AgentResult:
        """Execute a single agent."""
        t0 = time.time()

        if agent.handler is None:
            # No handler registered — return stub result
            return AgentResult(
                agent_id=agent.id,
                status=AgentStatus.FAILED,
                error="No handler registered for this agent",
                execution_time_ms=0,
            )

        try:
            findings = agent.handler(context)
            elapsed = int((time.time() - t0) * 1000)

            return AgentResult(
                agent_id=agent.id,
                status=AgentStatus.COMPLETE,
                findings=findings.get("findings", {}),
                signature_matches=findings.get("signature_matches", []),
                suggested_follow_ups=findings.get("suggested_follow_ups", []),
                execution_time_ms=elapsed,
            )
        except Exception as e:
            elapsed = int((time.time() - t0) * 1000)
            logger.error("Agent '%s' failed: %s", agent.id, str(e)[:200])
            return AgentResult(
                agent_id=agent.id,
                status=AgentStatus.FAILED,
                error=str(e)[:500],
                execution_time_ms=elapsed,
            )

    def _evaluate_follow_ups(self, agent: AgentDefinition, result: AgentResult, context: InvestigationContext) -> list[str]:
        """Determine which follow-up agents should run based on results.

        This is the AUTO-QUERY GENERATION logic — it decides what to investigate
        next based on what was just found.
        """
        follow_ups = []

        # Check each registered agent's trigger condition
        for candidate in self._agents.values():
            if candidate.id in context.agents_run:
                continue  # Already ran this one

            if candidate.trigger_type == TriggerType.ON_SIGNATURE:
                # Trigger if a specific signature was matched
                required_sig = candidate.trigger_condition.get("signature_id")
                min_count = candidate.trigger_condition.get("min_count", 1)
                if required_sig and context.signature_matches.get(required_sig, 0) >= min_count:
                    follow_ups.append(candidate.id)

            elif candidate.trigger_type == TriggerType.ON_COUNT:
                # Trigger if enough nodes match a condition
                required_count = candidate.trigger_condition.get("min_matches", 3)
                total_matches = sum(context.signature_matches.values())
                if total_matches >= required_count:
                    follow_ups.append(candidate.id)

            elif candidate.trigger_type == TriggerType.ON_FINDINGS:
                # Trigger if specific keywords appear in findings
                keywords = candidate.trigger_condition.get("keywords", [])
                findings_text = json.dumps(result.findings).lower()
                if any(kw.lower() in findings_text for kw in keywords):
                    follow_ups.append(candidate.id)

        # Also include explicitly suggested follow-ups from the agent itself
        for suggested in result.suggested_follow_ups:
            if suggested in self._agents and suggested not in context.agents_run:
                follow_ups.append(suggested)

        # Sort by priority
        follow_ups.sort(key=lambda aid: self._agents[aid].priority if aid in self._agents else 99)

        return follow_ups


# =========================================================================
# Pre-built Agent Definitions (the library)
# =========================================================================

BROAD_SCANNER = AgentDefinition(
    id="broad_scanner",
    name="Broad Scanner",
    description="Initial sweep of a topic — finds anything interesting with diverse queries",
    trigger_type=TriggerType.MANUAL,
    trigger_condition={},
    research_strategy="3-5 diverse queries: academic, geographic, cultural, skeptic, recent",
    taxonomy_scope=["*"],  # All signatures
    follow_up_agents=["taxonomy_scanner", "cross_pattern_agent"],
    priority=1,
)

TAXONOMY_SCANNER = AgentDefinition(
    id="taxonomy_scanner",
    name="Taxonomy-Guided Scanner",
    description="Second pass with targeted signature-specific queries",
    trigger_type=TriggerType.ON_FINDINGS,
    trigger_condition={"keywords": ["ancient", "site", "ruins", "sacred", "anomaly"]},
    research_strategy="One query per signature indicator from taxonomy",
    taxonomy_scope=["am-gge-san-*", "am-gge-ga-*", "am-gge-se-*", "am-gge-cm-*"],
    follow_up_agents=["cross_pattern_agent", "cultural_memory_agent"],
    priority=2,
)

CROSS_PATTERN_AGENT = AgentDefinition(
    id="cross_pattern_agent",
    name="Cross-Pattern Correlation",
    description="Finds connections between distant sites sharing the same signatures",
    trigger_type=TriggerType.ON_SIGNATURE,
    trigger_condition={"signature_id": "am-gge-cnp-004", "min_count": 3},
    research_strategy="Compare sites at matched nodes — what do they share?",
    taxonomy_scope=["am-gge-cnp-001", "am-gge-cnp-002", "am-gge-cnp-003", "am-gge-cnp-004"],
    follow_up_agents=["production_agent"],
    priority=3,
)

CULTURAL_MEMORY_AGENT = AgentDefinition(
    id="cultural_memory_agent",
    name="Cultural Memory Deep-Dive",
    description="Investigates WHY indigenous peoples consider grid nodes sacred",
    trigger_type=TriggerType.ON_SIGNATURE,
    trigger_condition={"signature_id": "am-gge-cm-001", "min_count": 3},
    research_strategy="What traditions, rituals, stories mark these locations?",
    taxonomy_scope=["am-gge-cm-001", "am-gge-cm-002", "am-gge-cm-003"],
    follow_up_agents=["geological_agent"],
    priority=4,
)

GEOLOGICAL_AGENT = AgentDefinition(
    id="geological_agent",
    name="Geological Correlation",
    description="Gets hard measurement data — geomagnetic surveys, seismic data",
    trigger_type=TriggerType.ON_COUNT,
    trigger_condition={"min_matches": 3},
    research_strategy="Find published measurement data, USGS surveys, satellite magnetometer",
    taxonomy_scope=["am-gge-ga-001", "am-gge-ga-002", "am-gge-ga-003"],
    follow_up_agents=["lidar_agent"],
    priority=4,
)

LIDAR_AGENT = AgentDefinition(
    id="lidar_agent",
    name="LiDAR Opportunity Finder",
    description="Identifies where LiDAR hasn't been used but should be",
    trigger_type=TriggerType.ON_FINDINGS,
    trigger_condition={"keywords": ["unexplored", "vegetation", "unexcavated", "dense forest", "jungle", "canopy"]},
    research_strategy="Has LiDAR been used here? What would it reveal?",
    taxonomy_scope=["am-gge-lidar-001"],
    follow_up_agents=["production_agent"],
    priority=5,
)

AUTO_QUERY_AGENT = AgentDefinition(
    id="auto_query_agent",
    name="Auto-Query Generator",
    description="Generates the next best research queries based on gaps in findings",
    trigger_type=TriggerType.ON_COUNT,
    trigger_condition={"min_matches": 5},
    research_strategy="Analyze unfired signatures as gaps — generate queries to fill them",
    taxonomy_scope=["*"],
    follow_up_agents=["broad_scanner"],  # Loops back
    priority=6,
)

PRODUCTION_AGENT = AgentDefinition(
    id="production_agent",
    name="Documentary Production Brief",
    description="Prepares field production briefs for confirmed high-priority findings",
    trigger_type=TriggerType.ON_FINDINGS,
    trigger_condition={"keywords": ["CONFIRMED", "PROBABLE", "production_value"]},
    research_strategy="Visual appeal, access logistics, narrative arc, expert contacts",
    taxonomy_scope=[],  # Meta-agent
    follow_up_agents=[],  # Terminal
    priority=8,
)

# All pre-defined agents
AGENT_LIBRARY = [
    BROAD_SCANNER,
    TAXONOMY_SCANNER,
    CROSS_PATTERN_AGENT,
    CULTURAL_MEMORY_AGENT,
    GEOLOGICAL_AGENT,
    LIDAR_AGENT,
    AUTO_QUERY_AGENT,
    PRODUCTION_AGENT,
]


# =========================================================================
# Agent Handler Functions
# =========================================================================

BEDROCK_MODEL_ID = "us.anthropic.claude-sonnet-4-6"
TAVILY_API_URL = "https://api.tavily.com/search"
_tavily_call_count = 0  # Track usage within session
TAVILY_MAX_CALLS_PER_RUN = 20  # Safety cap per agent chain run


def _tavily_search(query: str, max_results: int = 3) -> list[dict]:
    """Execute a Tavily search query and return results. Tracks usage."""
    global _tavily_call_count
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return []
    
    if _tavily_call_count >= TAVILY_MAX_CALLS_PER_RUN:
        logger.warning("Tavily call cap reached (%d). Skipping.", TAVILY_MAX_CALLS_PER_RUN)
        return []

    try:
        resp = requests.post(TAVILY_API_URL, json={
            "api_key": api_key,
            "query": query[:400],
            "max_results": max_results,
            "search_depth": "basic",
        }, timeout=15)
        resp.raise_for_status()
        _tavily_call_count += 1
        data = resp.json()
        return [
            {"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("content", "")}
            for r in data.get("results", [])
        ]
    except Exception as e:
        logger.warning("Tavily search failed for '%s': %s", query[:50], str(e)[:100])
        return []


def _bedrock_synthesize(prompt: str) -> str:
    """Call Bedrock Claude to synthesize research findings."""
    from botocore.config import Config
    config = Config(read_timeout=120, connect_timeout=10, retries={"max_attempts": 2})
    client = boto3.client("bedrock-runtime", region_name="us-east-1", config=config)

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    })

    response = client.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        body=body,
        contentType="application/json",
        accept="application/json",
    )

    result = json.loads(response["body"].read())
    # Handle multiple content blocks (thinking + text)
    for block in result.get("content", []):
        if block.get("type") == "text":
            return block["text"]
    return result["content"][0]["text"] if result.get("content") else ""


def _parse_llm_json(raw: str) -> dict:
    """Robustly parse JSON from LLM output, handling fences and truncation."""
    text = raw.strip()
    # Strip markdown fences
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0].strip()
    
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Truncation repair
    for trim_to in [text.rfind('},'), text.rfind('}'), text.rfind('"]')]:
        if trim_to <= 0:
            continue
        candidate = text[:trim_to + 1]
        candidate += "]" * max(0, candidate.count("[") - candidate.count("]"))
        candidate += "}" * max(0, candidate.count("{") - candidate.count("}"))
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    
    # Last resort: return raw in a dict
    return {"_raw": text[:2000], "_parse_failed": True}


def broad_scanner_handler(context: InvestigationContext) -> dict:
    """Execute broad scanner research.

    Uses Bedrock Claude's knowledge directly (no web search needed).
    Generates a comprehensive research brief on the investigation topic
    covering multiple angles: academic, geographic, cultural, skeptic.
    """
    topic = context.domain.replace("_", " ")

    prompt = (
        f"You are an investigative intelligence analyst conducting a BROAD SCAN on: {topic}\n\n"
        "Research this topic thoroughly from 5 angles:\n"
        "1. Academic/archaeological — peer-reviewed findings, measurements, dates\n"
        "2. Geographic/geological — coordinates, alignments, geological features\n"
        "3. Cultural/indigenous — traditions, ceremonies, oral histories\n"
        "4. Skeptical/debunking — counter-arguments, conventional explanations\n"
        "5. Connections — links to other ancient sites, shared patterns\n\n"
        "For EACH finding, provide: specific measurements, researcher names, publication years.\n"
        "Be concrete — cite J.H. Cole 1925, Petrie 1883, Jim Alison 2001, etc.\n\n"
        "Return ONLY valid JSON (no markdown fences):\n"
        "{\n"
        '  "findings": {\n'
        '    "summary": "3-4 sentence overview",\n'
        '    "key_facts": ["fact 1 with measurement/source", "fact 2", ...],\n'
        '    "anomalies": ["unexplained finding 1", ...],\n'
        '    "counter_arguments": ["skeptic point 1", ...],\n'
        '    "sites_identified": ["site name 1", "site name 2", ...]\n'
        "  },\n"
        '  "signature_matches": [\n'
        '    {"signature_id": "am-gge-lla-001", "confidence": "strong|moderate|weak", "evidence": "specific finding"}\n'
        "  ],\n"
        '  "suggested_follow_ups": ["taxonomy_scanner", "cross_pattern_agent"]\n'
        "}"
    )

    raw = _bedrock_synthesize(prompt)
    result = _parse_llm_json(raw)
    
    # Ensure expected structure
    if "findings" not in result:
        result = {"findings": result, "signature_matches": [], "suggested_follow_ups": ["taxonomy_scanner"]}
    if "signature_matches" not in result:
        result["signature_matches"] = []
    if "suggested_follow_ups" not in result:
        result["suggested_follow_ups"] = ["taxonomy_scanner"]

    return result


def taxonomy_scanner_handler(context: InvestigationContext) -> dict:
    """Execute taxonomy-guided scanner research.

    Uses Bedrock Claude directly to check each unmatched signature
    against the investigation topic with deep domain knowledge.
    """
    topic = context.domain.replace("_", " ")
    
    # Determine which signatures haven't been matched yet
    all_signatures = [
        ("am-gge-san-001", "megalithic construction — stone blocks >10 tons, precision fitting, distant quarry"),
        ("am-gge-cnp-002", "astronomical encoding — same star alignment at multiple ancient sites"),
        ("am-gge-lla-001", "great circle alignment — 3+ ancient sites on same great circle within 0.5°"),
        ("am-gge-cnp-001", "shared construction technique — identical method at sites >5000km apart"),
        ("am-gge-cm-001", "indigenous sacred — traditional designation as power place for 500+ years"),
        ("am-gge-ga-002", "geometric precision — mathematical constants encoded in dimensions"),
        ("am-gge-cnp-004", "site cluster — 5+ ancient sites within 300km of single point"),
    ]

    matched_sigs = set(context.signature_matches.keys())
    unmatched = [(sig_id, desc) for sig_id, desc in all_signatures if sig_id not in matched_sigs]
    if not unmatched:
        unmatched = all_signatures  # Re-check all if everything matched

    # Get previous findings for context
    prev_summary = ""
    if context.accumulated_findings:
        last = context.accumulated_findings[-1]
        if isinstance(last, dict):
            prev_summary = json.dumps(last.get("findings", last))[:2000]

    prompt = (
        f"You are an investigative analyst doing a TARGETED TAXONOMY SCAN for: {topic}\n\n"
        f"Previous broad scan findings:\n{prev_summary}\n\n"
        f"Now check EACH of these specific signatures against your knowledge of {topic}.\n"
        "For each, determine if there is concrete evidence (MATCH), suggestive evidence (POSSIBLE), or nothing (NO_MATCH).\n\n"
        "SIGNATURES TO CHECK:\n"
    )
    for sig_id, desc in unmatched:
        prompt += f"- {sig_id}: {desc}\n"
    
    prompt += (
        "\n\nFor MATCH or POSSIBLE, cite specific measurements, sites, researchers, dates.\n"
        "Return ONLY valid JSON (no markdown fences):\n"
        "{\n"
        '  "findings": {\n'
        '    "new_evidence": "summary of what was found",\n'
        '    "gaps_remaining": ["what we still don\'t know"],\n'
        '    "strongest_signal": "the single most compelling new finding"\n'
        "  },\n"
        '  "signature_matches": [\n'
        '    {"signature_id": "am-gge-xxx-000", "confidence": "strong|moderate|weak", "evidence": "specific cite"}\n'
        "  ],\n"
        '  "suggested_follow_ups": ["cross_pattern_agent"]\n'
        "}"
    )

    raw = _bedrock_synthesize(prompt)
    result = _parse_llm_json(raw)

    # Ensure expected structure
    if "findings" not in result:
        result = {"findings": result, "signature_matches": [], "suggested_follow_ups": ["cross_pattern_agent"]}
    if "signature_matches" not in result:
        result["signature_matches"] = []
    if "suggested_follow_ups" not in result:
        result["suggested_follow_ups"] = ["cross_pattern_agent"]

    # Phase 2: If we found strong matches, do targeted Tavily searches for specifics
    strong_sigs = [s for s in result.get("signature_matches", []) if s.get("confidence") == "strong"]
    if strong_sigs and os.environ.get("TAVILY_API_KEY"):
        for sig in strong_sigs[:3]:
            evidence = sig.get("evidence", "")
            query = f"{topic} {evidence[:80]} measurement source research"
            web_results = _tavily_search(query, max_results=3)
            if web_results:
                sig["web_sources"] = [{"title": r["title"], "url": r["url"]} for r in web_results]

    return result


def cross_pattern_agent_handler(context: InvestigationContext) -> dict:
    """Execute cross-pattern correlation research.

    Uses Bedrock Claude to analyze connections between sites that share
    signatures, finding the documentary gold: same technique 5000km apart.
    """
    topic = context.domain.replace("_", " ")
    
    # Build context from previous findings
    all_findings_text = ""
    sites_found = []
    for findings in context.accumulated_findings:
        if isinstance(findings, dict):
            f = findings.get("findings", findings)
            if isinstance(f, dict):
                all_findings_text += json.dumps(f)[:1500] + "\n"
                sites_found.extend(f.get("sites_identified", []))
    
    sig_summary = json.dumps(context.signature_matches)

    prompt = (
        f"You are an investigative analyst looking for CROSS-PATTERN CORRELATIONS in: {topic}\n\n"
        f"Signatures matched so far: {sig_summary}\n"
        f"Sites identified: {list(set(sites_found))[:15]}\n"
        f"Previous findings summary:\n{all_findings_text[:3000]}\n\n"
        "Your task: Find SPECIFIC connections between DISTANT sites (>3000km apart) that share:\n"
        "1. Same construction technique (stone cutting, fitting, material)\n"
        "2. Same astronomical alignment (same star, same precision)\n"
        "3. Same mathematical encoding (phi, pi, Earth dimensions)\n"
        "4. Same cultural tradition (without known contact)\n"
        "5. Same anomalous feature (unexplained by local context alone)\n\n"
        "For each connection, cite: which sites, what they share, distance apart, "
        "why this rules out coincidence, and which researcher documented it.\n\n"
        "This is DOCUMENTARY GOLD — the 'how is this possible?' moments.\n\n"
        "Return ONLY valid JSON (no markdown fences):\n"
        "{\n"
        '  "findings": {\n'
        '    "connections_found": [\n'
        '      {"sites": ["Site A", "Site B"], "shared_trait": "what they share", "distance_km": 5000, "researcher": "who documented", "significance": "why it matters"}\n'
        "    ],\n"
        '    "strongest_correlation": "the single most compelling cross-site connection",\n'
        '    "documentary_hook": "one sentence that makes a producer greenlight this episode"\n'
        "  },\n"
        '  "signature_matches": [\n'
        '    {"signature_id": "am-gge-cnp-001", "confidence": "strong", "evidence": "specific cross-site finding", "sites_involved": ["A","B"]}\n'
        "  ],\n"
        '  "suggested_follow_ups": ["production_agent"]\n'
        "}"
    )

    raw = _bedrock_synthesize(prompt)
    result = _parse_llm_json(raw)

    # Ensure expected structure
    if "findings" not in result:
        result = {"findings": result, "signature_matches": [], "suggested_follow_ups": ["production_agent"]}
    if "signature_matches" not in result:
        result["signature_matches"] = []
    if "suggested_follow_ups" not in result:
        result["suggested_follow_ups"] = ["production_agent"]

    # Phase 2: Deep search on the strongest connections via Tavily
    connections = result.get("findings", {}).get("connections_found", [])
    if connections and os.environ.get("TAVILY_API_KEY"):
        for conn in connections[:3]:
            sites = conn.get("sites", [])
            trait = conn.get("shared_trait", "")
            if len(sites) >= 2:
                query = f"{sites[0]} {sites[1]} connection shared {trait[:50]}"
                web_results = _tavily_search(query, max_results=3)
                if web_results:
                    conn["web_sources"] = [{"title": r["title"], "url": r["url"], "snippet": r["content"][:150]} for r in web_results]

    return result


def geological_agent_handler(context: InvestigationContext) -> dict:
    """Execute geological correlation research.

    Uses Bedrock Claude to analyze tectonic, volcanic, geomagnetic, and
    bathymetric data at UVG grid nodes. Finds correlations between grid
    geometry and Earth's geological structure.
    """
    topic = context.domain.replace("_", " ")

    # Gather sites from previous findings
    all_findings_text = ""
    sites_found = []
    for findings in context.accumulated_findings:
        if isinstance(findings, dict):
            f = findings.get("findings", findings)
            if isinstance(f, dict):
                all_findings_text += json.dumps(f)[:1500] + "\n"
                sites_found.extend(f.get("sites_identified", []))

    sig_summary = json.dumps(dict(list(context.signature_matches.items())[:10]))

    prompt = (
        f"You are a geophysicist analyzing the geological properties of UVG grid node locations.\n\n"
        f"Topic: {topic}\n"
        f"Sites identified so far: {list(set(sites_found))[:20]}\n"
        f"Previous findings: {all_findings_text[:2000]}\n\n"
        "For each UVG grid node with known coordinates, research:\n"
        "1. PLATE BOUNDARY PROXIMITY: Distance to nearest plate boundary (transform, convergent, divergent)\n"
        "2. VOLCANIC ACTIVITY: Active/dormant volcanoes within 200km, hotspot proximity\n"
        "3. SEISMIC ACTIVITY: Historical earthquake magnitude/frequency within 300km\n"
        "4. GEOMAGNETIC ANOMALY: Any documented magnetic declination anomaly, magnetic intensity variation\n"
        "5. BATHYMETRIC FEATURES: Submarine ridges, seamounts, abyssal fracture zones at oceanic nodes\n"
        "6. MINERAL/CRYSTAL DEPOSITS: Quartz, magnetite, piezoelectric mineral concentrations\n"
        "7. FAULT LINE INTERSECTION: Where multiple fault lines cross at or near a node\n\n"
        "Focus on MEASURABLE data with sources (USGS, BGS, NOAA, peer-reviewed geology papers).\n"
        "Identify which nodes show UNUSUAL geological properties that could explain why ancient peoples\n"
        "selected these locations — geomagnetic anomalies that could be 'felt', tectonic features visible\n"
        "in the landscape, mineral deposits used in construction.\n\n"
        "Return ONLY valid JSON (no markdown fences):\n"
        "{\n"
        '  "findings": {\n'
        '    "geological_correlations": [\n'
        '      {"node_id_or_site": "name/id", "feature": "what geological feature", '
        '"measurement": "specific value with units", "source": "who measured it", '
        '"significance": "why this matters for the grid theory"}\n'
        "    ],\n"
        '    "plate_boundary_stats": "X of 62 nodes within 200km of a plate boundary",\n'
        '    "volcanic_correlation": "X nodes near active/dormant volcanic systems",\n'
        '    "strongest_geological_signal": "the single most compelling geological finding",\n'
        '    "documentary_hook": "one sentence for a documentary producer"\n'
        "  },\n"
        '  "signature_matches": [\n'
        '    {"signature_id": "am-gge-ga-003", "confidence": "strong|moderate|weak", '
        '"evidence": "specific geological finding with measurement", '
        '"sites_involved": ["site names"]}\n'
        "  ],\n"
        '  "suggested_follow_ups": ["lidar_agent"]\n'
        "}"
    )

    raw = _bedrock_synthesize(prompt)
    result = _parse_llm_json(raw)

    # Ensure expected structure
    if "findings" not in result:
        result = {"findings": result, "signature_matches": [], "suggested_follow_ups": ["lidar_agent"]}
    if "signature_matches" not in result:
        result["signature_matches"] = []
    if "suggested_follow_ups" not in result:
        result["suggested_follow_ups"] = ["lidar_agent"]

    # Phase 2: Web search on strongest geological findings via Tavily
    correlations = result.get("findings", {}).get("geological_correlations", [])
    if correlations and os.environ.get("TAVILY_API_KEY"):
        for corr in correlations[:3]:
            site = corr.get("node_id_or_site", "")
            feature = corr.get("feature", "")
            if site and feature:
                query = f"{site} geological {feature} USGS measurement"
                web_results = _tavily_search(query, max_results=2)
                if web_results:
                    corr["web_sources"] = [
                        {"title": r["title"], "url": r["url"], "snippet": r["content"][:150]}
                        for r in web_results
                    ]

    return result


# Register handlers on agent definitions
BROAD_SCANNER.handler = broad_scanner_handler
TAXONOMY_SCANNER.handler = taxonomy_scanner_handler
CROSS_PATTERN_AGENT.handler = cross_pattern_agent_handler
GEOLOGICAL_AGENT.handler = geological_agent_handler


def lidar_agent_handler(context: InvestigationContext) -> dict:
    """Execute LiDAR opportunity analysis.

    Identifies UVG grid nodes where:
    1. Dense vegetation/jungle covers potential structures
    2. LiDAR has NOT yet been deployed (opportunity)
    3. LiDAR HAS been deployed and revealed hidden structures (evidence)
    4. Analogous sites suggest what might be found

    This is the "what's still hidden?" agent — finds the next Angkor.
    """
    topic = context.domain.replace("_", " ")

    # Gather sites from previous findings
    all_findings_text = ""
    sites_found = []
    for findings in context.accumulated_findings:
        if isinstance(findings, dict):
            f = findings.get("findings", findings)
            if isinstance(f, dict):
                all_findings_text += json.dumps(f)[:2000] + "\n"
                sites_found.extend(f.get("sites_identified", []))

    sig_summary = json.dumps(dict(list(context.signature_matches.items())[:10]))

    prompt = (
        f"You are a remote sensing archaeologist specializing in LiDAR (Light Detection and Ranging) surveys.\n\n"
        f"Topic: {topic}\n"
        f"Sites identified: {list(set(sites_found))[:20]}\n"
        f"Signatures matched: {sig_summary}\n\n"
        "Analyze UVG grid nodes for LiDAR opportunity:\n\n"
        "1. WHERE LIDAR HAS BEEN USED SUCCESSFULLY:\n"
        "   - Angkor (2015 CALI survey revealed 1000+ previously unknown structures)\n"
        "   - Guatemala (2018 Pacunam survey: 60,000 Maya structures under canopy)\n"
        "   - Amazon (2022 Iriarte: pre-Columbian earthworks beneath forest)\n"
        "   List OTHER UVG-proximate sites where LiDAR has revealed hidden structures.\n\n"
        "2. WHERE LIDAR SHOULD BE DEPLOYED (highest opportunity):\n"
        "   Criteria: dense vegetation + archaeological indicators + near UVG node + no LiDAR survey yet\n"
        "   For each candidate: what specifically might be found, based on analogous nearby sites?\n\n"
        "3. PREDICTION:\n"
        "   Based on what LiDAR revealed at surveyed sites, what would we expect to find at\n"
        "   unsurveyed UVG nodes in similar environments (tropical forest, dense scrub)?\n\n"
        "Cite: survey name, institution, year, key finding, publication.\n\n"
        "Return ONLY valid JSON (no markdown fences):\n"
        "{\n"
        '  "findings": {\n'
        '    "lidar_confirmed": [{"site": "name", "year": 2018, "institution": "who", '
        '"discovery": "what was found", "node_proximity_km": 50}],\n'
        '    "lidar_opportunities": [{"site": "name", "lat": 0, "lng": 0, '
        '"vegetation_type": "tropical forest", "why_promising": "reason", '
        '"predicted_discovery": "what LiDAR might reveal", "priority": "high|medium|low"}],\n'
        '    "strongest_opportunity": "single best candidate for next LiDAR survey",\n'
        '    "documentary_hook": "one sentence for a producer"\n'
        "  },\n"
        '  "signature_matches": [\n'
        '    {"signature_id": "am-gge-lidar-001", "confidence": "strong|moderate", '
        '"evidence": "specific LiDAR finding or opportunity", "sites_involved": ["names"]}\n'
        "  ],\n"
        '  "suggested_follow_ups": ["production_agent"]\n'
        "}"
    )

    raw = _bedrock_synthesize(prompt)
    result = _parse_llm_json(raw)

    # Ensure expected structure
    if "findings" not in result:
        result = {"findings": result, "signature_matches": [], "suggested_follow_ups": ["production_agent"]}
    if "signature_matches" not in result:
        result["signature_matches"] = []
    if "suggested_follow_ups" not in result:
        result["suggested_follow_ups"] = ["production_agent"]

    # Phase 2: Web search on top opportunities via Tavily
    opportunities = result.get("findings", {}).get("lidar_opportunities", [])
    if opportunities and os.environ.get("TAVILY_API_KEY"):
        for opp in opportunities[:2]:
            site = opp.get("site", "")
            if site:
                query = f"{site} LiDAR archaeological survey hidden structures"
                web_results = _tavily_search(query, max_results=2)
                if web_results:
                    opp["web_sources"] = [
                        {"title": r["title"], "url": r["url"], "snippet": r["content"][:150]}
                        for r in web_results
                    ]

    return result


LIDAR_AGENT.handler = lidar_agent_handler


def create_default_orchestrator() -> AgentOrchestrator:
    """Create an orchestrator pre-loaded with the standard agent library."""
    orchestrator = AgentOrchestrator(max_chain_depth=5)
    for agent in AGENT_LIBRARY:
        orchestrator.register_agent(agent)
    return orchestrator
