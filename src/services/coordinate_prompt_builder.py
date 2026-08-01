"""Coordinate Prompt Builder — Constructs Bedrock prompts for geographic coordinate generation.

Builds level-specific prompts from the Pattern Library taxonomy data for
each of the 5 drill-down levels (Domain, Typology, Method, Signature,
Precedent Case). Returns instructions for Bedrock to produce 3-8 geographic
locations as a JSON array with name, lat, lng, and description fields.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

COORDINATE_SYSTEM_PROMPT = (
    "You are a geographic research assistant with expertise in geospatial visualization. "
    "Given a taxonomy node from an investigative intelligence system, identify 3-8 real-world "
    "geographic locations relevant to the described pattern, and suggest the best geospatial "
    "visualization to reveal the pattern's geographic significance.\n\n"
    "Return ONLY a JSON object with these keys:\n"
    "- coordinates: array of {name, lat, lng, description} objects (3-8 sites)\n"
    "- visualization: object with keys:\n"
    "  - type: one of 'great_circle_lines', 'cluster_regions', 'sequential_connections', "
    "'heat_zones', 'constellation_overlay', 'none'\n"
    "  - lines: (for great_circle_lines) array of {from: site_name, to: site_name, label: string}\n"
    "  - clusters: (for cluster_regions) array of {center_site: site_name, radius_km: number, "
    "label: string, color: string}\n"
    "  - connections: (for sequential_connections) array of {from: site_name, to: site_name, "
    "order: number, label: string}\n"
    "  - zones: (for heat_zones) array of {center_site: site_name, radius_km: number, intensity: 0-1}\n"
    "  - pattern: (for constellation_overlay) array of {from: site_name, to: site_name}\n"
    "  - description: string explaining why this visualization was chosen\n"
    "  - reasoning: one sentence on the geographic significance\n\n"
    "No markdown, no preamble — just the JSON object."
)

CRIME_INSTRUCTION = (
    "Identify cities or regions where precedent cases, criminal operations, "
    "or pattern instances of this type have been documented."
)

ANCIENT_MYSTERIES_INSTRUCTION = (
    "Identify actual archaeological sites, historical monuments, temples, "
    "ley line endpoints, or geological formations associated with this topic."
)


class CoordinatePromptBuilder:
    """Builds Bedrock messages payloads for geographic coordinate generation.

    Gathers taxonomy context for the requested level, determines the domain
    (Crime vs Ancient Mysteries), and constructs a prompt instructing Bedrock
    to return 3-8 geographic locations as a JSON array.
    """

    def build_prompt(self, level: str, context_key: str, taxonomy_data: dict) -> dict:
        """Build Bedrock messages payload for coordinate generation.

        Args:
            level: One of 'domain', 'typology', 'method', 'signature', 'precedent_case'.
            context_key: Hierarchical path identifying the taxonomy node.
            taxonomy_data: Full taxonomy dictionary (merged domains under 'domains' key).

        Returns:
            Dict with 'system' (str), 'messages' (list of message dicts), 'max_tokens' (int).
        """
        context = self._gather_context(level, context_key, taxonomy_data)

        # Check if this is an alignment/global pattern and adjust instructions
        if "alignment" in context.lower() or "ley line" in context.lower() or "grid" in context.lower() or "equidistant" in context.lower():
            user_message = (
                f"Based on the following taxonomy context for the {level.replace('_', ' ')} level, "
                f"identify 6-8 real-world geographic locations spanning ALL continents where this pattern is observed. "
                f"This is a GLOBAL pattern — provide maximum geographic coverage.\n\n"
                f"{context}"
            )
        else:
            user_message = (
                f"Based on the following taxonomy context for the {level.replace('_', ' ')} level, "
                f"identify 3-8 real-world geographic locations relevant to this node.\n\n"
                f"{context}"
            )

        return {
            "system": COORDINATE_SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_message}],
            "max_tokens": 800,
        }

    def _gather_context(self, level: str, context_key: str, taxonomy_data: dict) -> str:
        """Extract node name, description, and domain-specific instructions.

        Navigates the taxonomy hierarchy using the context_key path segments,
        then builds a context string with the node's identity and domain-appropriate
        geographic instructions.

        Args:
            level: Taxonomy level identifier.
            context_key: Slash-separated path (e.g., 'ancient_mysteries/global_grid_earth_energy').
            taxonomy_data: Full taxonomy dictionary.

        Returns:
            Formatted context string with node info and domain instructions.
        """
        parts = context_key.split("/")
        domains = taxonomy_data.get("domains", [])

        # Find the domain
        domain_id = parts[0] if parts else ""
        domain = self._find_domain(domains, domain_id)

        if not domain:
            return ""

        # Determine domain-specific instruction
        domain_instruction = self._get_domain_instruction(domain)

        # Gather node-specific context based on level
        node_context = self._gather_node_context(level, parts, domain)

        if not node_context:
            return ""

        context_lines = [
            node_context,
            "",
            "Geographic search instructions:",
            domain_instruction,
            "",
            "Output format: Return a JSON array of 3-8 objects, each with keys: "
            'name (string), lat (decimal degrees), lng (decimal degrees), description (one sentence, ≤200 chars).',
            "",
            'Example: [{"name": "Ancient Giza Complex", "lat": 29.9792, "lng": 31.1342, '
            '"description": "Primary pyramid complex with Great Pyramid of Khufu."}]',
        ]

        return "\n".join(context_lines)

    def _gather_node_context(self, level: str, parts: list, domain: dict) -> str:
        """Extract node name and description based on level."""
        if level == "domain":
            return self._node_context_domain(domain)
        elif level == "typology":
            return self._node_context_typology(parts, domain)
        elif level == "method":
            return self._node_context_method(parts, domain)
        elif level == "signature":
            return self._node_context_signature(parts, domain)
        elif level == "precedent_case":
            return self._node_context_precedent_case(parts, domain)
        return ""

    def _node_context_domain(self, domain: dict) -> str:
        """Context for domain level."""
        name = domain.get("name", domain.get("domain_id", "Unknown"))
        description = domain.get("description", "")
        typologies = domain.get("typologies", [])
        typology_names = [t.get("name", t.get("typology_id", "")) for t in typologies]

        lines = [
            f"Domain: {name}",
            f"Description: {description}" if description else "",
            f"Agency: {domain.get('agency', 'N/A')}",
            f"Contains {len(typologies)} typologies: {', '.join(typology_names[:5])}",
        ]
        return "\n".join(line for line in lines if line)

    def _node_context_typology(self, parts: list, domain: dict) -> str:
        """Context for typology level."""
        if len(parts) < 2:
            return ""
        typology = self._find_typology(domain, parts[1])
        if not typology:
            return ""

        name = typology.get("name", typology.get("typology_id", "Unknown"))
        description = typology.get("description", "")
        methods = typology.get("methods", [])
        method_names = [m.get("name", m.get("method_id", "")) for m in methods]

        lines = [
            f"Domain: {domain.get('name', domain.get('domain_id', ''))}",
            f"Typology: {name}",
            f"Description: {description}" if description else "",
            f"Primary statute: {typology.get('primary_statute', 'N/A')}",
            f"Contains {len(methods)} methods: {', '.join(method_names[:5])}",
        ]
        return "\n".join(line for line in lines if line)

    def _node_context_method(self, parts: list, domain: dict) -> str:
        """Context for method level."""
        if len(parts) < 3:
            return ""
        typology = self._find_typology(domain, parts[1])
        if not typology:
            return ""
        method = self._find_method(typology, parts[2])
        if not method:
            return ""

        name = method.get("name", method.get("method_id", "Unknown"))
        description = method.get("description", "")
        signatures = method.get("signatures", [])

        lines = [
            f"Domain: {domain.get('name', domain.get('domain_id', ''))}",
            f"Typology: {typology.get('name', typology.get('typology_id', ''))}",
            f"Method: {name}",
            f"Description: {description}" if description else "",
            f"Contains {len(signatures)} signatures",
        ]

        # For alignment/grid patterns, instruct Bedrock to think globally
        method_name = method.get("name", "").lower()
        method_id = method.get("method_id", "").lower()
        if any(kw in method_name or kw in method_id for kw in ["alignment", "ley_line", "grid", "equidistant", "great_circle"]):
            lines.append("")
            lines.append("IMPORTANT: This is a GLOBAL alignment pattern. Provide sites spanning ALL continents where this pattern is observed. Include at least one site from each major region (Americas, Europe, Africa, Asia, Oceania) if evidence exists.")

        return "\n".join(line for line in lines if line)

    def _node_context_signature(self, parts: list, domain: dict) -> str:
        """Context for signature level."""
        if len(parts) < 4:
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

        name = signature.get("signature_id", parts[3])
        description = signature.get("description", "")
        vector_text = signature.get("vector_text", "")

        lines = [
            f"Domain: {domain.get('name', domain.get('domain_id', ''))}",
            f"Typology: {typology.get('name', typology.get('typology_id', ''))}",
            f"Method: {method.get('name', method.get('method_id', ''))}",
            f"Signature: {name}",
            f"Description: {description}" if description else "",
            f"Vector text: {vector_text}" if vector_text else "",
            f"Severity: {signature.get('severity', 'N/A')}",
            f"Precedent case: {signature.get('precedent_case', 'N/A')}",
        ]
        return "\n".join(line for line in lines if line)

    def _node_context_precedent_case(self, parts: list, domain: dict) -> str:
        """Context for precedent case level."""
        if len(parts) < 4:
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
        description = signature.get("description", "")

        lines = [
            f"Domain: {domain.get('name', domain.get('domain_id', ''))}",
            f"Typology: {typology.get('name', typology.get('typology_id', ''))}",
            f"Method: {method.get('name', method.get('method_id', ''))}",
            f"Precedent Case: {case_name}",
            f"Related signature: {signature.get('signature_id', 'N/A')}",
            f"Description: {description}" if description else "",
        ]
        return "\n".join(line for line in lines if line)

    def _get_domain_instruction(self, domain: dict) -> str:
        """Select domain-appropriate geographic instructions.

        Crime-related domains get city/region instructions.
        Ancient Mysteries domains get archaeological site instructions.
        """
        domain_id = domain.get("domain_id", "").lower()
        domain_name = domain.get("name", "").lower()

        # Ancient Mysteries domain detection
        if "ancient" in domain_id or "ancient" in domain_name or "mysteries" in domain_id or "mysteries" in domain_name:
            return ANCIENT_MYSTERIES_INSTRUCTION

        # Default to crime-oriented instructions
        return CRIME_INSTRUCTION

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
