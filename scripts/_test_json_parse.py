"""Test the JSON parsing with a simulated Sonnet response."""
import sys
sys.path.insert(0, "src")
from services.concept_research_agent import ConceptResearchAgent

# Simulate the response that starts with ```json and may be truncated
test_text = '```json\n{\n  "codename": "PROJECT PALIMPSEST",\n  "executive_summary": "Test summary.",\n  "field_status": "CONTESTED THEORY",\n  "key_researchers": [{"name": "Dr. Test", "affiliation": "Uni", "contribution": "stuff", "credibility": "high"}],\n  "priority_targets": [{"rank": 1, "location": "Gobekli Tepe", "rationale": "test", "difficulty": "moderate"}]\n}\n```'

agent = ConceptResearchAgent()
result = agent._parse_json_response(test_text)
print("Test 1 (complete with fences):")
print("  Parsed keys:", list(result.keys()))
print("  Targets:", len(result.get("priority_targets", [])))

# Test with truncated response (no closing ```)
test_truncated = '```json\n{\n  "codename": "PROJECT X",\n  "priority_targets": [{"rank": 1, "location": "Place"}]\n}'
result2 = agent._parse_json_response(test_truncated)
print("\nTest 2 (truncated, no closing ```):")
print("  Parsed keys:", list(result2.keys()))
print("  Targets:", len(result2.get("priority_targets", [])))

# Test with a really long response where JSON is incomplete
test_incomplete = '```json\n{\n  "codename": "PROJECT Y",\n  "priority_targets": [{"rank": 1, "location": "Place"'
result3 = agent._parse_json_response(test_incomplete)
print("\nTest 3 (incomplete JSON):")
print("  Parsed keys:", list(result3.keys()))
