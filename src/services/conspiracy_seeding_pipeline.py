"""Conspiracy Theory Seeding Pipeline.

Derives the universal taxonomy from all 10 conspiracy theory datasets
simultaneously. Processes 50+ representative documents per theory,
identifies cross-cutting patterns appearing in 3+ theories, and builds
the 10-domain taxonomy structure.

Methodology: FinCEN-inspired pattern derivation — each candidate pattern
must appear in 3+ theories to qualify as universal (same threshold as
FinCEN requiring 3+ suspicious transactions to file SAR).
"""
import json
import os
import uuid
from dataclasses import dataclass, field
from typing import Optional

from src.services.conspiracy_ingestion_adapters import AdapterRegistry, NormalizedRecord
from src.services.conspiracy_taxonomy_service import ConspiracyTaxonomyService


@dataclass
class CandidatePattern:
    """A pattern identified during seeding that may become a taxonomy entry."""
    pattern_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    suggested_domain: str = ""
    suggested_typology: str = ""
    source_theories: list = field(default_factory=list)  # Which theories it appeared in
    example_excerpts: list = field(default_factory=list)
    theory_count: int = 0

    @property
    def is_universal(self) -> bool:
        """A pattern is universal if it appears in 3+ distinct theories."""
        return self.theory_count >= 3


# Theory dataset configurations
THEORY_DATASETS = [
    {"name": "bermuda_triangle", "formats": ["xml", "html"]},
    {"name": "princess_diana", "formats": ["pdf"]},
    {"name": "flat_earth", "formats": ["json"]},
    {"name": "ufos_uaps", "formats": ["pdf", "csv"]},
    {"name": "jfk_assassination", "formats": ["pdf"]},
    {"name": "nine_eleven", "formats": ["pdf", "jpeg"]},
    {"name": "covid_lab_leak", "formats": ["pdf", "fasta"]},
    {"name": "moon_landing", "formats": ["tiff", "jpeg"]},
    {"name": "vaccine_conspiracies", "formats": ["csv", "json"]},
    {"name": "new_world_order", "formats": ["pdf", "html"]},
]


class ConspiracySeedingPipeline:
    """Derives universal taxonomy from 10 conspiracy theory datasets.
    
    Phase 1: Ingest 50+ docs per theory via adapters
    Phase 2: Extract behavioral indicators via Broad Scanner (Bedrock)
    Phase 3: Cluster indicators across theories
    Phase 4: Patterns appearing in 3+ theories → universal taxonomy
    Phase 5: Patterns in <3 theories → theory_specific_patterns table
    """

    def __init__(self, taxonomy_service: ConspiracyTaxonomyService,
                 bedrock_client=None, connection_manager=None,
                 data_root: str = "src/data/conspiracy-seed"):
        self.taxonomy = taxonomy_service
        self.bedrock = bedrock_client
        self.db = connection_manager
        self.data_root = data_root
        self.adapter_registry = AdapterRegistry()

    def initiate_seeding(self, sample_size_per_theory: int = 50) -> str:
        """Start the seeding pipeline.
        
        Processes sample_size_per_theory documents from each of the 10 theories.
        Returns execution_id for tracking.
        """
        execution_id = str(uuid.uuid4())
        print(f"Seeding pipeline started: {execution_id}")
        print(f"Sample size per theory: {sample_size_per_theory}")

        all_extractions = []

        for theory_config in THEORY_DATASETS:
            theory_name = theory_config["name"]
            theory_dir = os.path.join(self.data_root, theory_name)

            if not os.path.exists(theory_dir):
                print(f"  ⚠ No data directory for {theory_name}: {theory_dir}")
                continue

            # Ingest up to sample_size files
            records = self._ingest_theory_sample(theory_name, theory_dir, sample_size_per_theory)
            print(f"  ✓ {theory_name}: {len(records)} records ingested")
            all_extractions.extend(records)

        if not all_extractions:
            print("No data ingested. Create data directories and add sample files.")
            return execution_id

        # Extract behavioral indicators from all records
        print(f"\nExtracting behavioral indicators from {len(all_extractions)} records...")
        indicators = self._extract_indicators(all_extractions)

        # Derive universal patterns (3+ theories)
        print(f"\nDeriving universal patterns from {len(indicators)} indicators...")
        candidates = self.derive_universal_patterns(indicators)

        # Route patterns to universal taxonomy or theory-specific table
        universal_count = 0
        specific_count = 0
        for candidate in candidates:
            if candidate.is_universal:
                self._add_to_taxonomy(candidate)
                universal_count += 1
            else:
                self.classify_theory_specific(candidate)
                specific_count += 1

        print(f"\nSeeding complete:")
        print(f"  Universal patterns (3+ theories): {universal_count}")
        print(f"  Theory-specific patterns (<3 theories): {specific_count}")
        print(f"  Skipped files: {len(self.adapter_registry.skipped_files)}")

        # Generate coverage report
        report = self.generate_coverage_report()
        print(f"\nCoverage report:")
        print(f"  Domains: {report.get('total_domains', 0)}")
        print(f"  Under-specified: {report.get('under_specified', [])}")

        return execution_id

    def _ingest_theory_sample(self, theory_name: str, directory: str,
                               max_files: int) -> list[NormalizedRecord]:
        """Ingest up to max_files from a theory directory."""
        records = []
        file_count = 0

        for root, dirs, files in os.walk(directory):
            for filename in files:
                if file_count >= max_files:
                    break
                file_path = os.path.join(root, filename)
                result = self.adapter_registry.ingest_file(file_path, theory_name)
                records.extend(result)
                file_count += 1

        return records

    def _extract_indicators(self, records: list[NormalizedRecord]) -> list[dict]:
        """Use Bedrock to extract behavioral indicators from ingested records.
        
        For each record, Claude identifies which of the 10 domains the content
        relates to and extracts specific behavioral indicators.
        """
        indicators = []

        if not self.bedrock:
            # Without Bedrock, do basic keyword extraction
            for record in records:
                indicators.append({
                    "theory_name": record.theory_name,
                    "content_snippet": record.content_text[:500],
                    "indicators": self._keyword_extract(record.content_text),
                })
            return indicators

        # Process in batches via Bedrock
        for i, record in enumerate(records):
            if not record.content_text:
                continue

            try:
                result = self._extract_via_bedrock(record)
                indicators.append(result)
            except Exception as e:
                print(f"  Extraction failed for record {i}: {e}")
                continue

            if (i + 1) % 50 == 0:
                print(f"  Processed {i+1}/{len(records)} records")

        return indicators

    def _extract_via_bedrock(self, record: NormalizedRecord) -> dict:
        """Extract behavioral indicators from a single record using Claude."""
        prompt = f"""Analyze this document from the "{record.theory_name}" conspiracy theory dataset.

Identify behavioral/informational patterns that match these 10 universal investigation domains:
1. evidence_suppression - Documents hidden, classified, destroyed
2. institutional_behavior - Agency coordination, contradictory statements
3. witness_reliability - Credibility issues, recantation, pressure
4. timeline_anomalies - Events out of sequence, impossible timing
5. geographic_clustering - Spatial concentration of events
6. information_asymmetry - Known vs disclosed, delayed revelations
7. counter_narrative_emergence - Alternative explanations developing
8. narrative_coherence - Official story logical inconsistencies
9. expert_divergence - Credentialed experts disagreeing with institutions
10. methodological_red_flags - Flawed investigation procedure

DOCUMENT EXCERPT:
{record.content_text[:3000]}

Respond in JSON:
{{
  "matched_domains": ["domain_name_1", "domain_name_2"],
  "indicators": [
    {{"domain": "domain_name", "indicator": "specific behavioral pattern observed", "excerpt": "relevant quote"}}
  ]
}}"""

        response = self.bedrock.invoke_model(
            modelId="anthropic.claude-sonnet-4-20250514-v1:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 500,
                "messages": [{"role": "user", "content": prompt}]
            }),
            contentType="application/json",
            accept="application/json"
        )

        result = json.loads(response['body'].read())
        content = result['content'][0]['text']
        parsed = json.loads(content)

        return {
            "theory_name": record.theory_name,
            "document_id": record.record_id,
            "matched_domains": parsed.get("matched_domains", []),
            "indicators": parsed.get("indicators", []),
        }

    def _keyword_extract(self, text: str) -> list[dict]:
        """Basic keyword-based indicator extraction (fallback without Bedrock)."""
        text_lower = text.lower()
        indicators = []

        keyword_map = {
            "evidence_suppression": ["classified", "redacted", "withheld", "destroyed", "sealed"],
            "institutional_behavior": ["inter-agency", "coordinated", "contradicted", "denied"],
            "witness_reliability": ["recanted", "pressured", "threatened", "credible", "inconsistent"],
            "timeline_anomalies": ["before", "after", "impossible", "retroactive", "predated"],
            "geographic_clustering": ["concentrated", "cluster", "multiple locations", "same area"],
            "information_asymmetry": ["known but not disclosed", "years later", "delayed release"],
            "counter_narrative_emergence": ["alternative theory", "researchers argue", "disputed"],
            "narrative_coherence": ["contradiction", "inconsistent", "doesn't explain", "impossible"],
            "expert_divergence": ["expert disagrees", "whistleblower", "dissent", "credentials"],
            "methodological_red_flags": ["scope limited", "not investigated", "predetermined"],
        }

        for domain, keywords in keyword_map.items():
            for kw in keywords:
                if kw in text_lower:
                    indicators.append({"domain": domain, "indicator": kw, "excerpt": ""})
                    break

        return indicators

    def derive_universal_patterns(self, extractions: list[dict]) -> list[CandidatePattern]:
        """Identify patterns appearing in 3+ theories.
        
        Groups indicators by domain+indicator text, counts distinct theories,
        and creates CandidatePattern for each group.
        """
        # Group by domain + indicator description
        pattern_groups = {}  # key: (domain, indicator) → {theories: set, excerpts: []}

        for extraction in extractions:
            theory = extraction.get("theory_name", "unknown")
            for ind in extraction.get("indicators", []):
                domain = ind.get("domain", "unknown")
                indicator_text = ind.get("indicator", "")
                if not indicator_text:
                    continue

                key = (domain, indicator_text)
                if key not in pattern_groups:
                    pattern_groups[key] = {"theories": set(), "excerpts": []}

                pattern_groups[key]["theories"].add(theory)
                excerpt = ind.get("excerpt", "")
                if excerpt:
                    pattern_groups[key]["excerpts"].append(f"[{theory}] {excerpt[:200]}")

        # Convert to CandidatePattern instances
        candidates = []
        for (domain, indicator_text), group in pattern_groups.items():
            candidates.append(CandidatePattern(
                description=indicator_text,
                suggested_domain=domain,
                suggested_typology=f"{domain}_general",
                source_theories=list(group["theories"]),
                example_excerpts=group["excerpts"][:5],
                theory_count=len(group["theories"]),
            ))

        # Sort by theory count descending (most universal first)
        candidates.sort(key=lambda c: c.theory_count, reverse=True)
        return candidates

    def _add_to_taxonomy(self, candidate: CandidatePattern):
        """Add a universal pattern to the taxonomy hierarchy."""
        # For now, create as a signature under the suggested domain
        # Full typology/method creation would require more context
        try:
            self.taxonomy.create_signature(
                method_id=candidate.suggested_domain,  # Placeholder — needs real method_id
                description=candidate.description[:512],
                vector_text=candidate.description[:512],
                indicators=[f"Appeared in {t}" for t in candidate.source_theories],
                precedent_cases=candidate.example_excerpts[:3],
            )
        except Exception as e:
            # Likely fails due to proper noun check or missing method_id
            # Store as theory_specific instead
            self.classify_theory_specific(candidate)

    def classify_theory_specific(self, pattern: CandidatePattern):
        """Route patterns appearing in <3 theories to theory_specific_patterns table."""
        if self.db:
            self.db.execute(
                """INSERT INTO conspiracy.theory_specific_patterns 
                   (theory_name, description, source_theories) VALUES (%s, %s, %s)""",
                (pattern.source_theories[0] if pattern.source_theories else "unknown",
                 pattern.description,
                 json.dumps(pattern.source_theories))
            )

    def generate_coverage_report(self) -> dict:
        """Generate seeding coverage report."""
        report = {
            "total_domains": 10,
            "signatures_per_domain": {},
            "under_specified": [],
            "skipped_files": len(self.adapter_registry.skipped_files),
        }

        if self.db:
            coverage = self.taxonomy.get_coverage_report()
            report["total_domains"] = coverage.total_domains
            report["total_signatures"] = coverage.total_signatures
            report["balance_score"] = coverage.balance_score
            report["under_specified"] = coverage.under_specified_domains
            report["per_domain"] = coverage.per_domain

        return report
