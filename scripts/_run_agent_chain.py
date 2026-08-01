"""Run the full agent investigation chain on a topic.

Usage:
    $env:BRAVE_SEARCH_API_KEY = "key"; python scripts/_run_agent_chain.py "ley_line_alignments"
"""
import json
import os
import sys
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from services.agent_orchestrator import create_default_orchestrator, AgentStatus

def main():
    topic = sys.argv[1] if len(sys.argv) > 1 else "ley_line_alignments"
    
    if not os.environ.get("TAVILY_API_KEY"):
        print("NOTE: TAVILY_API_KEY not set — running Bedrock-only (no web search)")
        print("      Set it for deeper Phase 2 research on specific findings")
        print()

    print("=" * 70)
    print(f"  AGENT CHAIN INVESTIGATION: {topic}")
    print("=" * 70)
    print()

    orchestrator = create_default_orchestrator()
    
    # Show registered agents
    agents = orchestrator.list_agents()
    print(f"Registered agents: {len(agents)}")
    for a in agents:
        has_handler = "(ready)" if a["id"] in ["broad_scanner", "taxonomy_scanner", "cross_pattern_agent"] else "(no handler)"
        print(f"  [{a['priority']}] {a['name']} {has_handler}")
    print()

    # Run the investigation chain
    print(f"Starting investigation: '{topic}'")
    print("-" * 70)
    t0 = time.time()
    
    results = orchestrator.investigate(topic, trigger="manual")
    
    elapsed = time.time() - t0
    print()
    print("-" * 70)
    print(f"Chain complete in {elapsed:.1f}s — {len(results)} agents ran")
    print()

    # Display results
    for i, result in enumerate(results):
        status_emoji = "✓" if result.status == AgentStatus.COMPLETE else "✗"
        print(f"  {status_emoji} Agent: {result.agent_id} ({result.execution_time_ms}ms)")
        
        if result.status == AgentStatus.COMPLETE:
            findings = result.findings
            if isinstance(findings, dict):
                summary = findings.get("summary", findings.get("key_facts", ""))
                if summary:
                    print(f"    Summary: {str(summary)[:150]}")
                
            sig_matches = result.signature_matches
            if sig_matches:
                print(f"    Signature matches: {len(sig_matches)}")
                for sig in sig_matches[:5]:
                    if isinstance(sig, dict):
                        print(f"      → {sig.get('signature_id','?')} ({sig.get('confidence','?')}): {str(sig.get('evidence',''))[:80]}")
                    else:
                        print(f"      → {sig}")

            follow_ups = result.suggested_follow_ups
            if follow_ups:
                print(f"    Suggested follow-ups: {follow_ups}")
        else:
            print(f"    Error: {result.error[:150] if result.error else 'Unknown'}")
        print()

    # Save full results
    output_path = os.path.join(os.path.dirname(__file__), "..", "src", "data", "agent-chain-results.json")
    output = {
        "topic": topic,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "elapsed_seconds": round(elapsed, 1),
        "agents_run": len(results),
        "results": []
    }
    for r in results:
        output["results"].append({
            "agent_id": r.agent_id,
            "status": r.status.value,
            "execution_time_ms": r.execution_time_ms,
            "findings": r.findings,
            "signature_matches": r.signature_matches,
            "suggested_follow_ups": r.suggested_follow_ups,
            "error": r.error,
        })
    
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"Full results saved: {output_path}")


if __name__ == "__main__":
    main()
