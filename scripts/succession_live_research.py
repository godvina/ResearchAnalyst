"""
Executive Succession Planning — Live Research Agent

Real-time web research + Bedrock analysis for any company/role.
Called by the succession dashboard via a local HTTP endpoint.

Flow:
1. User submits transaction (company, division, role)
2. Agent constructs targeted search queries
3. Brave Search returns public profiles, press releases, bios
4. Bedrock (Haiku) extracts structured candidate data
5. Scoring engine computes composite scores
6. Returns JSON for dashboard rendering

Usage:
    # Set env vars first:
    # $env:BRAVE_SEARCH_API_KEY = "your-key"
    
    # Run as HTTP server (called by dashboard):
    python scripts/succession_live_research.py --serve
    
    # Run as CLI (one-shot):
    python scripts/succession_live_research.py --company "AWS" --division "Public Sector"

Endpoint: POST http://localhost:8089/research
Body: {"company":"AWS","division":"Worldwide Public Sector","role":"VP","sector":"PRIVATE","country":"US"}
"""

import json
import logging
import os
import sys
import time
import urllib.parse
import urllib.request
import ssl
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    import boto3
    from botocore.config import Config
    BEDROCK_AVAILABLE = True
except ImportError:
    BEDROCK_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Config
BRAVE_API_KEY = os.environ.get("BRAVE_SEARCH_API_KEY", os.environ.get("BRAVE_API_KEY", ""))
HAIKU_MODEL = "anthropic.claude-3-haiku-20240307-v1:0"
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")


# =============================================================================
# BRAVE SEARCH
# =============================================================================

def brave_search(query: str, count: int = 10) -> list[dict]:
    """Execute a web search via Brave Search API."""
    if not BRAVE_API_KEY:
        logger.warning("No BRAVE_SEARCH_API_KEY set — returning empty results")
        return []

    params = urllib.parse.urlencode({"q": query[:400], "count": min(count, 20)})
    url = f"https://api.search.brave.com/res/v1/web/search?{params}"
    req = urllib.request.Request(url)
    req.add_header("X-Subscription-Token", BRAVE_API_KEY)
    req.add_header("Accept", "application/json")

    try:
        ctx = ssl.create_default_context()
        resp = urllib.request.urlopen(req, context=ctx, timeout=12)
        data = json.loads(resp.read().decode())
        results = []
        for r in data.get("web", {}).get("results", [])[:count]:
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("description", "")[:500],
            })
        return results
    except Exception as e:
        logger.error(f"Brave search error for '{query[:60]}': {e}")
        return []


# =============================================================================
# BEDROCK (HAIKU) — Candidate Extraction & Scoring
# =============================================================================

def get_bedrock_client():
    """Get Bedrock runtime client."""
    if not BEDROCK_AVAILABLE:
        return None
    return boto3.client(
        "bedrock-runtime",
        region_name=AWS_REGION,
        config=Config(read_timeout=60, connect_timeout=10, retries={"max_attempts": 2})
    )


def invoke_haiku(system_prompt: str, user_message: str, max_tokens: int = 2000) -> str:
    """Call Claude Haiku via Bedrock for extraction."""
    client = get_bedrock_client()
    if not client:
        logger.warning("Bedrock not available — returning empty")
        return ""

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}],
        "temperature": 0.2,
    }

    try:
        resp = client.invoke_model(
            modelId=HAIKU_MODEL,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body)
        )
        resp_body = json.loads(resp["body"].read().decode())
        for block in resp_body.get("content", []):
            if block.get("type") == "text":
                return block.get("text", "")
        return ""
    except Exception as e:
        logger.error(f"Bedrock invocation error: {e}")
        return ""


def parse_json_from_llm(text: str) -> dict:
    """Extract JSON from LLM response (handles markdown fences)."""
    if not text:
        return {}
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]

    # Find first { and matching }
    start = text.find("{")
    if start == -1:
        start = text.find("[")
        if start == -1:
            return {}

    bracket_char = text[start]
    close_char = "}" if bracket_char == "{" else "]"
    depth = 0
    end = -1
    for i in range(start, len(text)):
        if text[i] == bracket_char:
            depth += 1
        elif text[i] == close_char:
            depth -= 1
            if depth == 0:
                end = i
                break

    if end == -1:
        # Try parsing what we have
        try:
            return json.loads(text[start:])
        except:
            return {}

    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {}


# =============================================================================
# RESEARCH PIPELINE
# =============================================================================

EXTRACTION_SYSTEM_PROMPT = """You are an executive research analyst specializing in succession planning.
Given search results about leadership at a company, extract structured candidate profiles.

For EACH person you identify as a potential succession candidate, extract:
- name: Full name
- current_title: Current job title
- current_org: Current organization
- country: ISO 2-letter country code
- source_type: "internal" (currently at target company) or "external_competitor" or "external_adjacent"
- prior_roles: List of previous roles (strings)
- awards: List of notable awards/recognition
- key_signals: List of notable achievements/evidence mapped to leadership criteria
- ai_brief: 2-3 sentence executive assessment

Then SCORE each candidate on these criteria (1-10 integer scale based on available evidence):
strategic_vision, integrity, cognitive_ability, resilience, results_orientation,
emotional_intelligence, adaptability, self_awareness, learning_agility, executive_presence,
decisiveness, energy_drive, industry_expertise, functional_excellence, financial_acumen,
digital_fluency, global_perspective, talent_development, stakeholder_management,
board_governance, crisis_leadership, innovation_leadership, change_management,
customer_centricity, operational_excellence

Use 5 as default when no evidence is available. Use 7-10 only when there's clear public evidence.

IMPORTANT: When scoring, consider the CULTURAL CONTEXT provided. Different regions value different
leadership attributes. For example, in Middle East contexts, relationship_networks and
hierarchical_respect are critical; in Germanic Europe, technical_depth matters more than charisma.

Return JSON format:
{
  "candidates": [
    {
      "name": "...",
      "current_title": "...",
      "current_org": "...",
      "country": "US",
      "source_type": "internal",
      "prior_roles": ["..."],
      "awards": ["..."],
      "key_signals": ["..."],
      "ai_brief": "...",
      "scores": {
        "strategic_vision": 8,
        ...all 25 criteria...
      }
    }
  ]
}"""


# Cultural context descriptions for the LLM
CULTURAL_CONTEXTS = {
    "IR": "MIDDLE EAST (Iran): High power distance, collective decision-making. Islamic business principles (halal, no riba). Relationships precede transactions. Sanctions navigation critical. Farsi language capability important. Hierarchical authority respected. Wasta (influence through connections) is primary business mechanism.",
    "AE": "MIDDLE EAST (UAE): Very high power distance, group collectivism. Sovereign wealth fund relationships critical. Emiratisation policies. Arabic essential. Vision 2030 transformation. Royal family/government relationships paramount.",
    "SA": "MIDDLE EAST (Saudi Arabia): Very high power distance. Vision 2030 transformation. Islamic business principles. Tribal/family networks. Arabic essential. Government relationships dominate.",
    "SG": "CONFUCIAN ASIA (Singapore): High power distance with meritocratic overlay. Face-saving dynamics. Government-linked company ecosystem. Long-term orientation. English + Mandarin.",
    "CN": "CONFUCIAN ASIA (China): Very high power distance. Guanxi (relationship networks) essential. CCP relationship navigation. Long-term planning. Mandarin essential.",
    "DE": "GERMANIC EUROPE (Germany): Low power distance. Technical/engineering depth valued. Mitbestimmung (co-determination). Process-oriented. Long-term planning. German language important.",
    "BR": "LATIN AMERICA (Brazil): High power distance, group-oriented. Personalismo (personal relationships drive business). Jeitinho (creative problem-solving). Emotional intelligence critical.",
    "US": "ANGLO (United States): Low power distance, high individualism. Results-driven meritocracy. Direct communication. Innovation celebrated. Standard Western executive criteria apply.",
    "GB": "ANGLO (United Kingdom): Low power distance, individualistic. Class-aware but meritocratic. Understated leadership style. Board governance experience valued.",
}


def build_search_queries(company: str, division: str, role: str, sector: str) -> list[str]:
    """Generate targeted search queries for succession research."""
    queries = [
        # Internal leadership
        f'"{company}" "{division}" VP OR "Vice President" OR Director leadership',
        f'"{company}" "{division}" executive team leaders',
        f'"{company}" "{division}" keynote speaker conference',
        f'"{company}" "{division}" award OR recognition OR "Wash100" OR "Top Exec"',
        # Role-specific
        f'"{company}" "{role}" successor OR appointed OR promoted',
        # External competitors
        f'"{division}" VP OR "Vice President" -"{company}" competitor cloud',
        # Industry news
        f'"{company}" "{division}" strategy AI OR innovation 2025 OR 2026',
    ]
    return queries


def research_candidates(company: str, division: str, role: str,
                        sector: str = "PRIVATE", country: str = "US") -> dict:
    """Full live research pipeline.
    
    1. Search web for leadership information
    2. Collect search results
    3. Send to Bedrock for structured extraction
    4. Score candidates
    5. Return dashboard-ready JSON
    """
    start_time = time.time()
    logger.info(f"Starting live research: {company} / {division} / {role}")

    # Step 1: Generate and execute search queries
    queries = build_search_queries(company, division, role, sector)
    all_results = []

    for q in queries:
        results = brave_search(q, count=5)
        all_results.extend(results)
        logger.info(f"  Query '{q[:50]}...' → {len(results)} results")
        time.sleep(0.3)  # Rate limiting

    # Deduplicate by URL
    seen_urls = set()
    unique_results = []
    for r in all_results:
        if r["url"] not in seen_urls:
            seen_urls.add(r["url"])
            unique_results.append(r)

    logger.info(f"Total unique search results: {len(unique_results)}")

    # Step 2: Build context for LLM
    search_context = "\n\n".join([
        f"[{r['title']}]\nURL: {r['url']}\n{r['snippet']}"
        for r in unique_results[:30]  # Cap at 30 most relevant
    ])

    # Step 3: Extract candidates via Bedrock
    cultural_context = CULTURAL_CONTEXTS.get(country.upper(), CULTURAL_CONTEXTS.get("US", ""))
    user_message = f"""Research context for succession planning:

Company: {company}
Division: {division}
Target Role: {role}
Sector: {sector}
Country: {country}

CULTURAL CONTEXT FOR SCORING:
{cultural_context}

Here are the search results about leadership at this company and division:

{search_context}

Based on this information, identify ALL potential succession candidates for the {role} role.
Include both internal candidates (currently at {company}) and external candidates (at competitors).
Score each candidate on all 25 criteria based on the available evidence.
Apply cultural context when scoring — weight relationship_networks, hierarchical_respect, and region-specific factors appropriately.
Return valid JSON only."""

    logger.info("Invoking Bedrock Haiku for candidate extraction...")
    raw_response = invoke_haiku(EXTRACTION_SYSTEM_PROMPT, user_message, max_tokens=4000)

    # Step 4: Parse response
    extracted = parse_json_from_llm(raw_response)
    candidates_raw = extracted.get("candidates", [])

    if not candidates_raw and raw_response:
        # Try parsing as array
        if raw_response.strip().startswith("["):
            try:
                candidates_raw = json.loads(raw_response.strip())
            except:
                pass

    logger.info(f"Extracted {len(candidates_raw)} candidates from LLM")

    # Step 5: Compute composite scores
    candidates_output = []
    for c in candidates_raw:
        scores = c.get("scores", {})
        # Fill missing scores with 5
        all_criteria = [
            "strategic_vision", "integrity", "cognitive_ability", "resilience",
            "results_orientation", "emotional_intelligence", "adaptability",
            "self_awareness", "learning_agility", "executive_presence",
            "decisiveness", "energy_drive", "industry_expertise",
            "functional_excellence", "financial_acumen", "digital_fluency",
            "global_perspective", "talent_development", "stakeholder_management",
            "board_governance", "crisis_leadership", "innovation_leadership",
            "change_management", "customer_centricity", "operational_excellence"
        ]
        for criterion in all_criteria:
            if criterion not in scores:
                scores[criterion] = 5

        # Compute composite using default VP/Private/US weights
        weights = {
            "strategic_vision": 9, "integrity": 10, "cognitive_ability": 8,
            "resilience": 8, "results_orientation": 8,
            "emotional_intelligence": 7, "adaptability": 7,
            "self_awareness": 6, "learning_agility": 7, "executive_presence": 8,
            "decisiveness": 7, "energy_drive": 6,
            "industry_expertise": 7, "functional_excellence": 6, "financial_acumen": 7,
            "digital_fluency": 6, "global_perspective": 7, "talent_development": 6,
            "stakeholder_management": 8, "board_governance": 7,
            "crisis_leadership": 7, "innovation_leadership": 6, "change_management": 6,
            "customer_centricity": 6, "operational_excellence": 6
        }
        total_w = sum(weights.values())
        weighted_sum = sum((weights[k] / total_w) * scores.get(k, 5) for k in weights)
        composite = round(weighted_sum / 10 * 100, 1)

        candidates_output.append({
            "name": c.get("name", "Unknown"),
            "current_title": c.get("current_title", ""),
            "current_org": c.get("current_org", company),
            "division": division,
            "country": c.get("country", country),
            "sector": sector,
            "source_type": c.get("source_type", "internal"),
            "signals": [{"source_type": "web_search", "source_url": "", "source_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "signal_text": s, "criteria_mapped": [], "confidence": "medium", "raw_snippet": ""} for s in c.get("key_signals", [])],
            "inferred_scores": scores,
            "score_confidence": {k: "medium" for k in scores},
            "composite_estimate": composite,
            "ai_brief": c.get("ai_brief", ""),
            "linkedin_public_url": "",
            "years_in_role": 0,
            "prior_roles": c.get("prior_roles", []),
            "education": [],
            "board_seats": [],
            "awards": c.get("awards", []),
            "speaking_engagements": [],
            "research_timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # Sort by composite score
    candidates_output.sort(key=lambda x: x["composite_estimate"], reverse=True)

    # Step 6: Build output
    internal_count = len([c for c in candidates_output if c["source_type"] == "internal"])
    external_count = len([c for c in candidates_output if "external" in c["source_type"]])
    incumbent_count = len([c for c in candidates_output if c["source_type"] == "internal_incumbent"])

    elapsed = round(time.time() - start_time, 1)
    logger.info(f"Research complete in {elapsed}s — {len(candidates_output)} candidates")

    output = {
        "transaction": {
            "transaction_id": f"TXN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "company": company,
            "division": division,
            "target_role": role,
            "scope": "single_role",
            "sector": sector,
            "country": country,
            "incumbent_name": "",
            "urgency": "planned",
            "constraints": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "complete"
        },
        "research_date": datetime.now(timezone.utc).isoformat(),
        "candidates_found": len(candidates_output),
        "search_results_analyzed": len(unique_results),
        "elapsed_seconds": elapsed,
        "candidates": candidates_output,
        "pipeline_summary": {
            "internal": internal_count,
            "internal_incumbent": incumbent_count,
            "external_competitor": external_count,
            "external_adjacent": 0,
            "avg_composite": round(sum(c["composite_estimate"] for c in candidates_output) / len(candidates_output), 1) if candidates_output else 0,
            "top_internal": next((c["name"] for c in candidates_output if c["source_type"] == "internal"), None),
            "top_external": next((c["name"] for c in candidates_output if "external" in c["source_type"]), None),
        },
        "search_queries_used": queries,
    }

    return output


# =============================================================================
# HTTP SERVER (called by dashboard)
# =============================================================================

class ResearchHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler for the research API."""

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        """Handle research request."""
        if self.path != "/research":
            self.send_response(404)
            self.end_headers()
            return

        # Read body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")

        try:
            params = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode())
            return

        company = params.get("company", "")
        division = params.get("division", "")
        role = params.get("role", "VP")
        sector = params.get("sector", "PRIVATE")
        country = params.get("country", "US")

        if not company or not division:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "company and division required"}).encode())
            return

        # Run research
        try:
            results = research_candidates(company, division, role, sector, country)
            response_json = json.dumps(results, ensure_ascii=False)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(response_json.encode("utf-8"))

        except Exception as e:
            logger.error(f"Research failed: {e}")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def log_message(self, format, *args):
        """Suppress default HTTP access log."""
        pass


def run_server(port: int = 8089):
    """Start the research API server."""
    server = HTTPServer(("0.0.0.0", port), ResearchHandler)
    logger.info(f"Succession Research Agent API running on http://localhost:{port}/research")
    logger.info(f"Brave API key: {'SET' if BRAVE_API_KEY else 'MISSING'}")
    logger.info(f"Bedrock model: {HAIKU_MODEL}")
    logger.info(f"AWS Region: {AWS_REGION}")
    server.serve_forever()


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Executive Succession Live Research Agent")
    parser.add_argument("--serve", action="store_true", help="Run as HTTP server on port 8089")
    parser.add_argument("--port", type=int, default=8089, help="Server port")
    parser.add_argument("--company", default="", help="Company name")
    parser.add_argument("--division", default="", help="Division/BU")
    parser.add_argument("--role", default="VP", help="Target role")
    parser.add_argument("--sector", default="PRIVATE")
    parser.add_argument("--country", default="US")
    parser.add_argument("--output", default="", help="Output JSON file")

    args = parser.parse_args()

    if args.serve:
        run_server(args.port)
    elif args.company and args.division:
        results = research_candidates(
            args.company, args.division, args.role, args.sector, args.country
        )
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            logger.info(f"Results written to {args.output}")
        else:
            print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        parser.print_help()
        print("\nExamples:")
        print("  # Run as API server (for dashboard):")
        print("  $env:BRAVE_SEARCH_API_KEY = 'your-key'")
        print("  python scripts/succession_live_research.py --serve")
        print("")
        print("  # One-shot CLI research:")
        print("  python scripts/succession_live_research.py --company 'Microsoft' --division 'Azure Government' --role 'CVP'")


if __name__ == "__main__":
    main()
