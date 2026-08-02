"""Conspiracy Theory Universal Taxonomy Service.

Manages the 10-domain taxonomy CRUD operations, proper noun validation,
coverage reporting, and OpenSearch embedding integration.

Domains: evidence_suppression, institutional_behavior, witness_reliability,
timeline_anomalies, geographic_clustering, information_asymmetry,
counter_narrative_emergence, narrative_coherence, expert_divergence,
methodological_red_flags
"""
import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Optional


# Theory-specific proper nouns that must NOT appear in universal taxonomy definitions
PROPER_NOUN_BLOCKLIST = [
    "jfk", "kennedy", "oswald", "dealey", "warren commission",
    "roswell", "area 51", "bob lazar", "tic tac",
    "9/11", "twin towers", "wtc", "pentagon attack",
    "covid", "wuhan", "fauci", "gain of function", "sars-cov",
    "apollo", "moon landing", "nasa fake",
    "vaers", "mrna", "pfizer", "moderna",
    "diana", "dodi", "henri paul", "alma tunnel",
    "illuminati", "bilderberg", "rothschild", "freemason",
    "bermuda triangle", "flight 19",
    "flat earth", "firmament", "ice wall", "reptilian", "david icke",
]


@dataclass
class CoverageReport:
    """Taxonomy coverage metrics."""
    total_domains: int = 0
    total_typologies: int = 0
    total_methods: int = 0
    total_signatures: int = 0
    total_precedent_cases: int = 0
    per_domain: list = field(default_factory=list)
    balance_score: float = 0.0
    under_specified_domains: list = field(default_factory=list)


class ConspiracyTaxonomyService:
    """Manages the conspiracy theory universal taxonomy.
    
    Provides CRUD operations for the 5-level hierarchy, enforces
    universality (no theory-specific proper nouns), and integrates
    with OpenSearch for signature embeddings.
    """

    def __init__(self, connection_manager=None, opensearch_client=None, bedrock_client=None):
        """Initialize with database and search connections.
        
        Args:
            connection_manager: Aurora PostgreSQL connection manager
            opensearch_client: OpenSearch client for embedding storage
            bedrock_client: Bedrock client for embedding generation
        """
        self.db = connection_manager
        self.os_client = opensearch_client
        self.bedrock = bedrock_client

    # ============================================================
    # VALIDATION
    # ============================================================

    def validate_no_proper_nouns(self, text: str) -> bool:
        """Reject definitions containing theory-specific proper nouns.
        
        Ensures taxonomy nodes are domain-agnostic and universal.
        Returns True if text is clean, False if it contains blocklisted terms.
        """
        text_lower = text.lower()
        for noun in PROPER_NOUN_BLOCKLIST:
            if noun in text_lower:
                return False
        return True

    def validate_context_key(self, context_key: str) -> bool:
        """Validate context_key format: conspiracy/{domain}/{typology}/{method}/{sig}."""
        if len(context_key) > 512:
            return False
        pattern = r'^conspiracy/[a-z_]+/[a-z_]+/[a-z_]+/[a-z0-9_]+$'
        return bool(re.match(pattern, context_key))

    # ============================================================
    # CRUD OPERATIONS
    # ============================================================

    def create_domain(self, name: str, description: str) -> str:
        """Create a new taxonomy domain. Returns domain_id."""
        if not self.validate_no_proper_nouns(description):
            raise ValueError(f"Description contains theory-specific proper nouns: {description[:50]}...")

        domain_id = str(uuid.uuid4())

        if self.db:
            self.db.execute(
                "INSERT INTO conspiracy.domains (domain_id, name, description) VALUES (%s, %s, %s)",
                (domain_id, name, description)
            )
            self._audit("add", "domain", f"conspiracy/{name}", None, description, "Domain created")

        return domain_id

    def create_typology(self, domain_id: str, name: str, description: str) -> str:
        """Create a new typology under a domain. Returns typology_id."""
        if not self.validate_no_proper_nouns(description):
            raise ValueError(f"Description contains theory-specific proper nouns")

        typology_id = str(uuid.uuid4())

        if self.db:
            self.db.execute(
                "INSERT INTO conspiracy.typologies (typology_id, domain_id, name, description) VALUES (%s, %s, %s, %s)",
                (typology_id, domain_id, name, description)
            )

        return typology_id

    def create_method(self, typology_id: str, name: str, description: str) -> str:
        """Create a new method under a typology. Returns method_id."""
        if not self.validate_no_proper_nouns(description):
            raise ValueError(f"Description contains theory-specific proper nouns")

        method_id = str(uuid.uuid4())

        if self.db:
            self.db.execute(
                "INSERT INTO conspiracy.methods (method_id, typology_id, name, description) VALUES (%s, %s, %s, %s)",
                (method_id, typology_id, name, description)
            )

        return method_id

    def create_signature(self, method_id: str, description: str, vector_text: str,
                         indicators: list, precedent_cases: list) -> str:
        """Create a new signature under a method. Returns signature_id.
        
        Also generates embedding and stores in OpenSearch.
        """
        if not self.validate_no_proper_nouns(description):
            raise ValueError(f"Description contains theory-specific proper nouns")

        if len(vector_text) > 512:
            raise ValueError(f"vector_text exceeds 512 characters ({len(vector_text)})")

        signature_id = str(uuid.uuid4())
        context_key = self._generate_context_key(method_id, signature_id)

        if self.db:
            self.db.execute(
                """INSERT INTO conspiracy.signatures 
                   (signature_id, method_id, context_key, description, vector_text, indicators, precedent_cases)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (signature_id, method_id, context_key, description, vector_text,
                 json.dumps(indicators), json.dumps(precedent_cases))
            )
            self._audit("add", "signature", context_key, None, description, "Signature created")

        # Generate and store embedding
        if self.bedrock and self.os_client:
            self._store_signature_embedding(signature_id, context_key, vector_text, description, indicators)

        return signature_id

    # ============================================================
    # EMBEDDING INTEGRATION
    # ============================================================

    def _store_signature_embedding(self, signature_id: str, context_key: str,
                                    vector_text: str, description: str, indicators: list):
        """Generate Titan embedding and store in OpenSearch typology-patterns index."""
        try:
            # Generate embedding via Bedrock Titan
            embedding = self._generate_embedding(vector_text)
            if not embedding:
                return

            # Store in OpenSearch
            doc = {
                "signature_id": signature_id,
                "context_key": context_key,
                "description": description,
                "vector_text": vector_text,
                "embedding": embedding,
                "indicators": indicators,
                "status": "active",
                "taxonomy_domain": "conspiracy_theory",
            }
            self.os_client.index(
                index="typology-patterns",
                id=signature_id,
                body=doc
            )
        except Exception as e:
            # Log but don't fail — embedding is supplementary
            print(f"Warning: Failed to store embedding for {signature_id}: {e}")

    def _generate_embedding(self, text: str) -> Optional[list]:
        """Generate a 1024-dim embedding using Titan Embed Text v2."""
        if not self.bedrock:
            return None

        try:
            response = self.bedrock.invoke_model(
                modelId="amazon.titan-embed-text-v2:0",
                body=json.dumps({"inputText": text}),
                contentType="application/json",
                accept="application/json"
            )
            result = json.loads(response['body'].read())
            return result.get('embedding')
        except Exception as e:
            print(f"Embedding generation failed: {e}")
            return None

    # ============================================================
    # CONTEXT KEY GENERATION
    # ============================================================

    def _generate_context_key(self, method_id: str, signature_id: str) -> str:
        """Generate hierarchical context_key for a signature.
        
        Format: conspiracy/{domain}/{typology}/{method}/{sig_short_id}
        """
        if self.db:
            # Look up hierarchy from database
            row = self.db.fetch_one("""
                SELECT d.name as domain_name, t.name as typology_name, m.name as method_name
                FROM conspiracy.methods m
                JOIN conspiracy.typologies t ON m.typology_id = t.typology_id
                JOIN conspiracy.domains d ON t.domain_id = d.domain_id
                WHERE m.method_id = %s
            """, (method_id,))
            if row:
                domain_slug = self._slugify(row['domain_name'])
                typology_slug = self._slugify(row['typology_name'])
                method_slug = self._slugify(row['method_name'])
                sig_slug = f"sig_{signature_id[:8]}"
                return f"conspiracy/{domain_slug}/{typology_slug}/{method_slug}/{sig_slug}"

        # Fallback if no DB
        return f"conspiracy/unknown/unknown/unknown/sig_{signature_id[:8]}"

    def _slugify(self, text: str) -> str:
        """Convert text to a URL-safe slug."""
        slug = text.lower().strip()
        slug = re.sub(r'[^a-z0-9]+', '_', slug)
        slug = slug.strip('_')
        return slug[:64]

    # ============================================================
    # COVERAGE REPORTING
    # ============================================================

    def get_coverage_report(self) -> CoverageReport:
        """Generate taxonomy coverage metrics."""
        report = CoverageReport()

        if not self.db:
            return report

        # Total counts
        report.total_domains = self.db.fetch_one(
            "SELECT COUNT(*) as c FROM conspiracy.domains")['c']
        report.total_typologies = self.db.fetch_one(
            "SELECT COUNT(*) as c FROM conspiracy.typologies")['c']
        report.total_methods = self.db.fetch_one(
            "SELECT COUNT(*) as c FROM conspiracy.methods")['c']
        report.total_signatures = self.db.fetch_one(
            "SELECT COUNT(*) as c FROM conspiracy.signatures")['c']
        report.total_precedent_cases = self.db.fetch_one(
            "SELECT COUNT(*) as c FROM conspiracy.precedent_cases")['c']

        # Per-domain breakdown
        rows = self.db.fetch_all("""
            SELECT d.name,
                   COUNT(DISTINCT t.typology_id) as typologies,
                   COUNT(DISTINCT m.method_id) as methods,
                   COUNT(DISTINCT s.signature_id) as signatures
            FROM conspiracy.domains d
            LEFT JOIN conspiracy.typologies t ON d.domain_id = t.domain_id
            LEFT JOIN conspiracy.methods m ON t.typology_id = m.typology_id
            LEFT JOIN conspiracy.signatures s ON m.method_id = s.method_id
            GROUP BY d.name
            ORDER BY d.name
        """)

        sig_counts = []
        for row in rows:
            report.per_domain.append({
                "domain": row['name'],
                "typologies": row['typologies'],
                "methods": row['methods'],
                "signatures": row['signatures']
            })
            sig_counts.append(row['signatures'])
            if row['signatures'] < 5:
                report.under_specified_domains.append(row['name'])

        # Balance score: min/max signature ratio
        if sig_counts and max(sig_counts) > 0:
            report.balance_score = min(sig_counts) / max(sig_counts)
        else:
            report.balance_score = 0.0

        return report

    def get_balance_score(self) -> float:
        """Quick balance score: ratio of smallest to largest domain signature count."""
        report = self.get_coverage_report()
        return report.balance_score

    # ============================================================
    # AUDIT LOGGING
    # ============================================================

    def _audit(self, action: str, level: str, context_key: str,
               old_value: Optional[str], new_value: Optional[str], reason: str):
        """Log taxonomy modification to audit table."""
        if self.db:
            self.db.execute(
                """INSERT INTO conspiracy.taxonomy_audit 
                   (action, level, context_key, old_value, new_value, reason)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (action, level, context_key, old_value, new_value, reason)
            )

    # ============================================================
    # SIGNATURE STATUS MANAGEMENT
    # ============================================================

    def promote_to_universal(self, signature_id: str, theory_count: int):
        """Promote a signature to 'universal_confirmed' when matched by 5+ theories."""
        if theory_count >= 5 and self.db:
            old_status = self.db.fetch_one(
                "SELECT status FROM conspiracy.signatures WHERE signature_id = %s",
                (signature_id,)
            )
            if old_status and old_status['status'] != 'universal_confirmed':
                self.db.execute(
                    "UPDATE conspiracy.signatures SET status = 'universal_confirmed' WHERE signature_id = %s",
                    (signature_id,)
                )
                self._audit("update", "signature", None,
                            old_status['status'], "universal_confirmed",
                            f"Promoted: matched by {theory_count} theories")
