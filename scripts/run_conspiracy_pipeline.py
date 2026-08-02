"""Run the Conspiracy Theory Taxonomy Pipeline end-to-end.

This is the main orchestration script that wires together:
1. File format adapters (PDF, XML, CSV, JSON, HTML, TIFF, FASTA)
2. Taxonomy Service (10-domain universal taxonomy)
3. ACH Scoring Service (competing hypotheses)
4. Proof Engine (standards of proof)
5. Seeding Pipeline (derive universal patterns from 10 theories)
6. Validation Pipeline (sequential: Bermuda → Diana → Flat → UFO → JFK)

Usage:
    # Seed the taxonomy from sample data
    python scripts/run_conspiracy_pipeline.py seed

    # Validate against Bermuda Triangle
    python scripts/run_conspiracy_pipeline.py validate bermuda_triangle

    # Run proof engine on a finding (uses Flat Earth as demo)
    python scripts/run_conspiracy_pipeline.py prove flat_earth

    # Show coverage report
    python scripts/run_conspiracy_pipeline.py coverage

    # Show processing status
    python scripts/run_conspiracy_pipeline.py status
"""
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.conspiracy_taxonomy_service import ConspiracyTaxonomyService
from src.services.conspiracy_ingestion_adapters import AdapterRegistry
from src.services.conspiracy_seeding_pipeline import ConspiracySeedingPipeline
from src.services.conspiracy_validation_pipeline import ConspiracyValidationPipeline
from src.services.ach_scoring_service import ACHScoringService
from src.services.proof_engine import ProofEngine


def cmd_seed(args):
    """Seed the universal taxonomy from 10 conspiracy theory datasets."""
    print("=" * 60)
    print("CONSPIRACY THEORY TAXONOMY — SEEDING PIPELINE")
    print("=" * 60)

    sample_size = int(args[0]) if args else 50
    data_root = "src/data/conspiracy-seed"

    # Check if seed data directory exists
    if not os.path.exists(data_root):
        print(f"\nNo seed data found at: {data_root}")
        print("Create this directory structure:")
        print(f"  {data_root}/")
        for theory in ["bermuda_triangle", "princess_diana", "flat_earth",
                       "ufos_uaps", "jfk_assassination", "nine_eleven",
                       "covid_lab_leak", "moon_landing", "vaccine_conspiracies",
                       "new_world_order"]:
            print(f"    {theory}/  (add sample files here)")
        print(f"\nThen re-run: python scripts/run_conspiracy_pipeline.py seed")
        return

    # Initialize services (without DB/Bedrock for local testing)
    taxonomy = ConspiracyTaxonomyService()
    pipeline = ConspiracySeedingPipeline(
        taxonomy_service=taxonomy,
        data_root=data_root,
    )

    execution_id = pipeline.initiate_seeding(sample_size_per_theory=sample_size)
    print(f"\nExecution ID: {execution_id}")


def cmd_validate(args):
    """Validate taxonomy against a specific theory dataset."""
    if not args:
        print("Usage: python scripts/run_conspiracy_pipeline.py validate <theory_name>")
        print("Available: bermuda_triangle, princess_diana, flat_earth, ufos_uaps, jfk_assassination")
        return

    theory_name = args[0]
    print(f"=" * 60)
    print(f"VALIDATION PIPELINE — {theory_name.upper()}")
    print(f"=" * 60)

    pipeline = ConspiracyValidationPipeline()
    result = pipeline.start_validation(theory_name)

    print(f"\nResult:")
    print(f"  Status: {result.status}")
    print(f"  Documents processed: {result.documents_processed}")
    print(f"  Signatures matched: {result.signatures_matched}")
    print(f"  Match rate: {result.match_rate:.1%}")
    print(f"  Cross-connections: {result.cross_connections_found}")
    print(f"  Verdict: {'PASSED ✓' if result.passed else 'FAILED ✗'}")

    if result.gap_analysis:
        print(f"\nGap Analysis:")
        print(f"  {json.dumps(result.gap_analysis, indent=2)}")


def cmd_prove(args):
    """Run the Proof Engine on a theory to demonstrate proving/disproving.
    
    Demo: Flat Earth against scientific standard → should produce UNPROVEN.
    """
    theory = args[0] if args else "flat_earth"
    standard = args[1] if len(args) > 1 else "scientific"

    print(f"=" * 60)
    print(f"PROOF ENGINE — {theory.upper()} vs {standard.upper()} STANDARD")
    print(f"=" * 60)

    engine = ProofEngine()

    # Simulate a finding from the flat earth dataset
    finding_data = {
        "description": f"Core claim from {theory} dataset",
        "theory_name": theory,
        "signature_matched": "narrative_coherence/logical_impossibility",
    }

    # Simulated evidence (what we'd extract from the dataset)
    evidence_map = {
        "flat_earth": (
            "The flat earth hypothesis claims the Earth is a flat disc rather than an oblate spheroid. "
            "Available evidence: Every satellite image shows a sphere. Ships disappear hull-first over "
            "the horizon. Different stars are visible at different latitudes. Time zones exist because "
            "the Earth rotates. GPS satellites orbit a sphere. Lunar eclipses show Earth's circular shadow. "
            "No flat earth model explains seasons, day/night cycles across hemispheres, or flight paths "
            "in the southern hemisphere. Zero peer-reviewed papers support the claim. "
            "All measurements from every scientific discipline confirm spherical geometry."
        ),
        "bermuda_triangle": (
            "The Bermuda Triangle hypothesis claims an anomalous region of ocean causes unexplained "
            "disappearances. Available evidence: Lloyd's of London insurance data shows the region is "
            "statistically no more dangerous than any comparable area of ocean. The Coast Guard found "
            "no unusual pattern of losses. Many 'mysterious' disappearances have documented explanations "
            "(storms, mechanical failure, human error). The region has heavy shipping traffic, so "
            "absolute numbers of incidents are expected to be higher. No physical mechanism has been "
            "identified. The original 1964 article by Vincent Gaddis cherry-picked incidents."
        ),
    }

    evidence = evidence_map.get(theory, f"No pre-loaded evidence for {theory}. Would be extracted from dataset.")

    verdict = engine.evaluate(
        finding_id=f"demo_{theory}",
        finding_data=finding_data,
        evidence=evidence,
        standard_name=standard,
        tenant_id="conspiracy_theories"
    )

    print(f"\nFinding: {finding_data['description']}")
    print(f"Standard: {standard}")
    print(f"\nChecklist Items:")
    for item in verdict.checklist_items:
        status = "✓" if item.score >= 1.0 else ("◐" if item.score >= 0.5 else "✗")
        critical = " [CRITICAL]" if item.is_critical else ""
        print(f"  {status} {item.description}{critical}")
        if item.justification:
            print(f"      → {item.justification}")

    print(f"\nOverall Score: {verdict.overall_score:.2f}")
    print(f"Verdict: {verdict.verdict}")

    if verdict.research_directions:
        print(f"\nResearch Directions:")
        for rd in verdict.research_directions:
            print(f"  • {rd}")


def cmd_coverage(args):
    """Display taxonomy coverage report."""
    print("=" * 60)
    print("TAXONOMY COVERAGE REPORT")
    print("=" * 60)

    taxonomy = ConspiracyTaxonomyService()
    report = taxonomy.get_coverage_report()

    print(f"\nTotal Domains: {report.total_domains}")
    print(f"Total Typologies: {report.total_typologies}")
    print(f"Total Methods: {report.total_methods}")
    print(f"Total Signatures: {report.total_signatures}")
    print(f"Total Precedent Cases: {report.total_precedent_cases}")
    print(f"Balance Score: {report.balance_score:.2f}")

    if report.under_specified_domains:
        print(f"\n⚠ Under-specified domains (<5 signatures):")
        for d in report.under_specified_domains:
            print(f"    {d}")

    if report.per_domain:
        print(f"\nPer-Domain Breakdown:")
        for d in report.per_domain:
            print(f"  {d['domain']}: {d['typologies']} typologies, {d['methods']} methods, {d['signatures']} signatures")


def cmd_status(args):
    """Display processing status for all theories."""
    print("=" * 60)
    print("PROCESSING STATUS — ALL THEORIES")
    print("=" * 60)

    pipeline = ConspiracyValidationPipeline()

    print(f"\nOrdered Validation Sequence:")
    for i, theory in enumerate(pipeline.PROCESSING_ORDER, 1):
        print(f"  {i}. {theory} → pending")

    print(f"\nUngated (process after first 5):")
    for theory in pipeline.UNGATED_THEORIES:
        print(f"  • {theory} → pending")

    print(f"\nTo start: python scripts/run_conspiracy_pipeline.py validate bermuda_triangle")


def main():
    if len(sys.argv) < 2:
        print("Conspiracy Theory Taxonomy Pipeline")
        print("=" * 40)
        print("\nCommands:")
        print("  seed [sample_size]     — Seed taxonomy from 10 theories")
        print("  validate <theory>      — Validate taxonomy against a theory")
        print("  prove <theory> [std]   — Run proof engine (default: scientific)")
        print("  coverage               — Show taxonomy coverage report")
        print("  status                 — Show processing status")
        print("\nExamples:")
        print("  python scripts/run_conspiracy_pipeline.py seed 50")
        print("  python scripts/run_conspiracy_pipeline.py validate bermuda_triangle")
        print("  python scripts/run_conspiracy_pipeline.py prove flat_earth scientific")
        print("  python scripts/run_conspiracy_pipeline.py prove bermuda_triangle scientific")
        return

    command = sys.argv[1]
    args = sys.argv[2:]

    commands = {
        "seed": cmd_seed,
        "validate": cmd_validate,
        "prove": cmd_prove,
        "coverage": cmd_coverage,
        "status": cmd_status,
    }

    if command in commands:
        commands[command](args)
    else:
        print(f"Unknown command: {command}")
        print(f"Available: {', '.join(commands.keys())}")


if __name__ == "__main__":
    main()
