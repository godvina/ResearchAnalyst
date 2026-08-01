"""Summary Prompt Builder — Constructs Bedrock prompts for AI level summaries.

Builds level-specific prompts from the Pattern Library taxonomy data for
each of the 5 drill-down levels (Domain, Typology, Method, Signature,
Precedent Case). Handles context gathering, token estimation, and
truncation to stay within the 4000-token context budget.
"""

import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a senior investigative intelligence analyst producing structured intelligence briefs. "
    "Your output must follow this format:\n\n"
    "ASSESSMENT: [One sentence overall assessment with confidence level (HIGH/MEDIUM/LOW)]\n\n"
    "KEY INDICATORS:\n"
    "• [Bullet 1 — most significant finding]\n"
    "• [Bullet 2 — supporting evidence]\n"
    "• [Bullet 3 — pattern connection or anomaly]\n\n"
    "GAPS: [One sentence on what's missing or unverified]\n\n"
    "RECOMMENDED ACTION: [One concrete next step for the investigator]\n\n"
    "Be specific, cite numbers from the data, and include confidence qualifiers. "
    "Do not use generic language. Every statement should be grounded in the taxonomy data provided."
)


class SummaryPromptBuilder:
    """Builds Bedrock messages payloads for AI level summaries.

    Gathers taxonomy context for the requested level (current + one level
    below), estimates token usage, and truncates when exceeding the 4000-token
    budget by removing low-severity signatures first, then oldest cases.
    """

    MAX_CONTEXT_TOKENS = 4000
    SEVERITY_ORDER = ["low", "medium", "high", "critical"]

    def build_prompt(self, level: str, context_key: str, taxonomy_data: dict) -> dict:
        """Build Bedrock messages payload for the given taxonomy level.

        Args:
            level: One of 'domain', 'typology', 'method', 'signature', 'precedent_case'.
            context_key: Hierarchical path identifying the taxonomy node.
            taxonomy_data: Full taxonomy dictionary (from pattern-library-taxonomy.json).

        Returns:
            Dict with 'system' (str), 'messages' (list of message dicts), 'max_tokens' (int).
        """
        context = self._gather_context(level, context_key, taxonomy_data)

        user_message = (
            f"Produce a structured intelligence brief for the {level.replace('_', ' ')} level "
            f"taxonomy node below. Follow the ASSESSMENT → KEY INDICATORS → GAPS → RECOMMENDED ACTION format.\n\n"
            f"{context}"
        )

        return {
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_message}],
            "max_tokens": 300,
        }

    def _gather_context(self, level: str, context_key: str, taxonomy_data: dict) -> str:
        """Extract level-specific context (current level + one level below).

        Navigates the taxonomy hierarchy using the context_key path segments,
        then extracts relevant data for the target level and its immediate
        children only (no grandchildren).

        Args:
            level: Taxonomy level identifier.
            context_key: Slash-separated path (e.g., 'antitrust/procurement_collusion').
            taxonomy_data: Full taxonomy dictionary.

        Returns:
            Formatted context string, truncated to fit within token budget.
        """
        parts = context_key.split("/")
        domains = taxonomy_data.get("domains", [])

        if level == "domain":
            return self._gather_domain_context(parts, domains)
        elif level == "typology":
            return self._gather_typology_context(parts, domains)
        elif level == "method":
            return self._gather_method_context(parts, domains)
        elif level == "signature":
            return self._gather_signature_context(parts, domains)
        elif level == "precedent_case":
            return self._gather_precedent_case_context(parts, domains)
        else:
            return ""

    def _gather_domain_context(self, parts: list, domains: list) -> str:
        """Gather context for domain level: typology count, signature count, cross-typology highlights."""
        domain_id = parts[0] if parts else ""
        domain = self._find_domain(domains, domain_id)
        if not domain:
            return ""

        typologies = domain.get("typologies", [])
        typology_count = len(typologies)
        total_signatures = 0
        cross_typology_highlights = []

        for typology in typologies:
            methods = typology.get("methods", [])
            for method in methods:
                signatures = method.get("signatures", [])
                total_signatures += len(signatures)

            # Collect typology-level info (one level below = typologies)
            cross_typology_highlights.append(
                f"- {typology.get('name', 'Unknown')}: {typology.get('needle_count', 0)} patterns, "
                f"primary statute: {typology.get('primary_statute', 'N/A')}"
            )

        context_lines = [
            f"Domain: {domain.get('name', domain_id)}",
            f"Agency: {domain.get('agency', 'N/A')}",
            f"Statutes: {', '.join(domain.get('statutes', []))}",
            f"Number of typologies: {typology_count}",
            f"Total signature count: {total_signatures}",
            "",
            "Cross-typology highlights:",
        ]
        context_lines.extend(cross_typology_highlights)

        context = "\n".join(context_lines)
        signatures_for_truncation = self._collect_signatures_from_domain(domain)
        cases_for_truncation = self._collect_cases_from_domain(domain)
        return self._truncate_context(context, signatures_for_truncation, cases_for_truncation)

    def _gather_typology_context(self, parts: list, domains: list) -> str:
        """Gather context for typology level: method names, signature counts, severity, precedent cases."""
        if len(parts) < 2:
            return ""

        domain = self._find_domain(domains, parts[0])
        if not domain:
            return ""

        typology = self._find_typology(domain, parts[1])
        if not typology:
            return ""

        methods = typology.get("methods", [])
        method_details = []
        severity_counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        precedent_cases = []
        all_signatures = []

        for method in methods:
            signatures = method.get("signatures", [])
            all_signatures.extend(signatures)
            method_details.append(
                f"- {method.get('name', 'Unknown')}: {len(signatures)} signatures — "
                f"{method.get('description', 'N/A')}"
            )
            for sig in signatures:
                severity = sig.get("severity", "medium").lower()
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
                case = sig.get("precedent_case", "")
                if case:
                    precedent_cases.append(case)

        severity_str = ", ".join(f"{k}: {v}" for k, v in severity_counts.items() if v > 0)

        context_lines = [
            f"Typology: {typology.get('name', parts[1])}",
            f"Primary statute: {typology.get('primary_statute', 'N/A')}",
            f"Total methods: {len(methods)}",
            f"Severity distribution: {severity_str}",
            "",
            "Methods:",
        ]
        context_lines.extend(method_details)

        if precedent_cases:
            context_lines.append("")
            context_lines.append("Key precedent cases:")
            for case in precedent_cases[:10]:
                context_lines.append(f"- {case}")

        context = "\n".join(context_lines)
        cases_for_truncation = [{"name": c, "date": ""} for c in precedent_cases]
        return self._truncate_context(context, all_signatures, cases_for_truncation)

    def _gather_method_context(self, parts: list, domains: list) -> str:
        """Gather context for method level: all signature descriptions, indicators, precedent cases."""
        if len(parts) < 3:
            return ""

        domain = self._find_domain(domains, parts[0])
        if not domain:
            return ""

        typology = self._find_typology(domain, parts[1])
        if not typology:
            return ""

        method = self._find_method(typology, parts[2])
        if not method:
            return ""

        signatures = method.get("signatures", [])
        sig_details = []
        precedent_cases = []

        for sig in signatures:
            indicators = sig.get("indicators", [])
            indicators_str = ", ".join(indicators)
            sig_details.append(
                f"- [{sig.get('severity', 'medium').upper()}] {sig.get('signature_id', 'N/A')}: "
                f"{sig.get('description', 'N/A')}"
            )
            sig_details.append(f"  Indicators: {indicators_str}")
            case = sig.get("precedent_case", "")
            if case:
                sig_details.append(f"  Precedent: {case}")
                precedent_cases.append(case)

        context_lines = [
            f"Method: {method.get('name', parts[2])}",
            f"Description: {method.get('description', 'N/A')}",
            f"Total signatures: {len(signatures)}",
            "",
            "Signatures:",
        ]
        context_lines.extend(sig_details)

        context = "\n".join(context_lines)
        cases_for_truncation = [{"name": c, "date": ""} for c in precedent_cases]
        return self._truncate_context(context, signatures, cases_for_truncation)

    def _gather_signature_context(self, parts: list, domains: list) -> str:
        """Gather context for signature level: vector text, indicators, precedent case details, severity."""
        if len(parts) < 4:
            return ""

        domain = self._find_domain(domains, parts[0])
        if not domain:
            return ""

        typology = self._find_typology(domain, parts[1])
        if not typology:
            return ""

        method = self._find_method(typology, parts[2])
        if not method:
            return ""

        signature = self._find_signature(method, parts[3])
        if not signature:
            return ""

        indicators = signature.get("indicators", [])
        indicators_str = "\n".join(f"- {ind}" for ind in indicators)

        context_lines = [
            f"Signature: {signature.get('signature_id', parts[3])}",
            f"Description: {signature.get('description', 'N/A')}",
            f"Severity: {signature.get('severity', 'N/A')}",
            f"Vector text: {signature.get('vector_text', 'N/A')}",
            "",
            "Indicators:",
            indicators_str,
            "",
            f"Precedent case: {signature.get('precedent_case', 'N/A')}",
        ]

        context = "\n".join(context_lines)
        # Signature level has no children to truncate meaningfully, but apply limits anyway
        return self._truncate_context(context, [signature], [])

    def _gather_precedent_case_context(self, parts: list, domains: list) -> str:
        """Gather context for precedent case level: case name, referencing signatures, evidentiary pattern."""
        if len(parts) < 5:
            # Try to find by case reference across the taxonomy
            return self._find_case_by_key(parts, domains)

        domain = self._find_domain(domains, parts[0])
        if not domain:
            return ""

        typology = self._find_typology(domain, parts[1])
        if not typology:
            return ""

        method = self._find_method(typology, parts[2])
        if not method:
            return ""

        signature = self._find_signature(method, parts[3])
        if not signature:
            return ""

        case_name = signature.get("precedent_case", "")
        referencing_signatures = self._find_signatures_referencing_case(case_name, domains)

        context_lines = [
            f"Precedent Case: {case_name}",
            f"Referenced by signature: {signature.get('signature_id', 'N/A')}",
            f"Signature description: {signature.get('description', 'N/A')}",
            f"Evidentiary pattern: {signature.get('vector_text', 'N/A')}",
            "",
            "All referencing signatures:",
        ]
        for ref_sig in referencing_signatures:
            context_lines.append(
                f"- {ref_sig.get('signature_id', 'N/A')} [{ref_sig.get('severity', 'N/A')}]: "
                f"{ref_sig.get('description', 'N/A')}"
            )

        context = "\n".join(context_lines)
        return self._truncate_context(context, referencing_signatures, [])

    def _find_case_by_key(self, parts: list, domains: list) -> str:
        """Fallback: find a precedent case by traversing available path segments."""
        if len(parts) < 4:
            return ""

        domain = self._find_domain(domains, parts[0])
        if not domain:
            return ""

        typology = self._find_typology(domain, parts[1])
        if not typology:
            return ""

        method = self._find_method(typology, parts[2])
        if not method:
            return ""

        signature = self._find_signature(method, parts[3])
        if not signature:
            return ""

        case_name = signature.get("precedent_case", "")
        referencing_signatures = self._find_signatures_referencing_case(case_name, domains)

        context_lines = [
            f"Precedent Case: {case_name}",
            f"Referenced by signature: {signature.get('signature_id', 'N/A')}",
            f"Evidentiary pattern: {signature.get('vector_text', 'N/A')}",
            "",
            "All referencing signatures:",
        ]
        for ref_sig in referencing_signatures:
            context_lines.append(
                f"- {ref_sig.get('signature_id', 'N/A')} [{ref_sig.get('severity', 'N/A')}]: "
                f"{ref_sig.get('description', 'N/A')}"
            )

        return "\n".join(context_lines)

    # --- Truncation Logic ---

    def _estimate_tokens(self, text: str) -> int:
        """Approximate token count using word-based estimation.

        Uses len(text.split()) * 1.3 as a conservative approximation
        to avoid adding a tiktoken dependency.

        Args:
            text: Input text to estimate.

        Returns:
            Estimated token count (rounded up to nearest integer).
        """
        return math.ceil(len(text.split()) * 1.3)

    def _truncate_context(self, context: str, signatures: list, cases: list) -> str:
        """Truncate context to fit within MAX_CONTEXT_TOKENS budget.

        Removal order:
        1. Remove signatures by ascending severity (Low → Medium → High → Critical)
        2. If still over budget, remove precedent cases oldest-first

        Args:
            context: The assembled context string.
            signatures: List of signature dicts (with 'severity' field).
            cases: List of case dicts or strings for potential removal.

        Returns:
            Context string that fits within the token budget.
        """
        if self._estimate_tokens(context) <= self.MAX_CONTEXT_TOKENS:
            return context

        # Phase 1: Remove signatures by ascending severity
        sorted_sigs = sorted(
            signatures,
            key=lambda s: self.SEVERITY_ORDER.index(
                s.get("severity", "medium").lower()
                if s.get("severity", "medium").lower() in self.SEVERITY_ORDER
                else "medium"
            ),
        )

        for sig in sorted_sigs:
            sig_id = sig.get("signature_id", "")
            sig_desc = sig.get("description", "")
            # Remove lines referencing this signature from context
            lines = context.split("\n")
            filtered_lines = []
            skip_next = False
            for line in lines:
                if skip_next and line.startswith("  "):
                    continue
                skip_next = False
                if sig_id and sig_id in line:
                    skip_next = True
                    continue
                if sig_desc and len(sig_desc) > 20 and sig_desc[:30] in line:
                    skip_next = True
                    continue
                filtered_lines.append(line)
            context = "\n".join(filtered_lines)

            if self._estimate_tokens(context) <= self.MAX_CONTEXT_TOKENS:
                return context

        # Phase 2: Remove cases (oldest first — cases list assumed in chronological order)
        for case in cases:
            case_name = case.get("name", case) if isinstance(case, dict) else str(case)
            if not case_name:
                continue
            lines = context.split("\n")
            filtered_lines = [line for line in lines if case_name not in line]
            context = "\n".join(filtered_lines)

            if self._estimate_tokens(context) <= self.MAX_CONTEXT_TOKENS:
                return context

        return context

    # --- Taxonomy Navigation Helpers ---

    def _find_domain(self, domains: list, domain_id: str) -> Optional[dict]:
        """Find a domain by its domain_id."""
        for domain in domains:
            if domain.get("domain_id") == domain_id:
                return domain
        return None

    def _find_typology(self, domain: dict, typology_id: str) -> Optional[dict]:
        """Find a typology within a domain by its typology_id."""
        for typology in domain.get("typologies", []):
            if typology.get("typology_id") == typology_id:
                return typology
        return None

    def _find_method(self, typology: dict, method_id: str) -> Optional[dict]:
        """Find a method within a typology by its method_id."""
        for method in typology.get("methods", []):
            if method.get("method_id") == method_id:
                return method
        return None

    def _find_signature(self, method: dict, signature_id: str) -> Optional[dict]:
        """Find a signature within a method by its signature_id."""
        for sig in method.get("signatures", []):
            if sig.get("signature_id") == signature_id:
                return sig
        return None

    def _find_signatures_referencing_case(self, case_name: str, domains: list) -> list:
        """Find all signatures across the taxonomy that reference a given precedent case."""
        results = []
        if not case_name:
            return results
        for domain in domains:
            for typology in domain.get("typologies", []):
                for method in typology.get("methods", []):
                    for sig in method.get("signatures", []):
                        if sig.get("precedent_case", "") == case_name:
                            results.append(sig)
        return results

    def _collect_signatures_from_domain(self, domain: dict) -> list:
        """Collect all signatures within a domain for truncation purposes."""
        signatures = []
        for typology in domain.get("typologies", []):
            for method in typology.get("methods", []):
                signatures.extend(method.get("signatures", []))
        return signatures

    def _collect_cases_from_domain(self, domain: dict) -> list:
        """Collect all precedent case references from a domain."""
        cases = []
        for typology in domain.get("typologies", []):
            for method in typology.get("methods", []):
                for sig in method.get("signatures", []):
                    case = sig.get("precedent_case", "")
                    if case:
                        cases.append({"name": case, "date": ""})
        return cases
