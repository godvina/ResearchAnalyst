"""Create Neptune graph schema for Conspiracy Theory Taxonomy.

Creates vertex and edge labels for cross-theory relationship tracking.
Uses the existing Neptune cluster: neptunedbcluster-qoxzlhiau0ao

Vertex Labels: Theory, ConspiracyDocument, ConspiracyDomain, ConspiracyTypology,
               ConspiracyMethod, ConspiracySignature, PrecedentCase
Edge Labels: belongs_to, matches, contains, cross_connects, geo_correlates

Usage:
    python scripts/_create_conspiracy_neptune_schema.py
"""
import json
import requests
from requests_aws4auth import AWS4Auth
import boto3

NEPTUNE_ENDPOINT = "neptunedbcluster-qoxzlhiau0ao.cluster-cgaj5jxtrulh.us-east-1.neptune.amazonaws.com"
NEPTUNE_PORT = 8182
REGION = "us-east-1"


def get_neptune_url(path="/gremlin"):
    return f"https://{NEPTUNE_ENDPOINT}:{NEPTUNE_PORT}{path}"


def execute_gremlin(query: str):
    """Execute a Gremlin query against Neptune."""
    url = get_neptune_url("/gremlin")
    payload = {"gremlin": query}

    session = boto3.Session()
    credentials = session.get_credentials().get_frozen_credentials()
    auth = AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        REGION,
        "neptune-db",
        session_token=credentials.token
    )

    response = requests.post(url, json=payload, auth=auth, timeout=30)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error {response.status_code}: {response.text[:500]}")
        return None


def seed_theory_vertices():
    """Create Theory vertices for all 10 conspiracy theories."""
    theories = [
        {"name": "bermuda_triangle", "size": "small", "formats": "xml,html"},
        {"name": "princess_diana", "size": "small", "formats": "pdf"},
        {"name": "flat_earth", "size": "large", "formats": "json"},
        {"name": "ufos_uaps", "size": "large", "formats": "pdf,csv,mp4"},
        {"name": "jfk_assassination", "size": "massive", "formats": "pdf"},
        {"name": "nine_eleven", "size": "large", "formats": "pdf,jpeg,video"},
        {"name": "covid_lab_leak", "size": "massive", "formats": "fasta,pdf"},
        {"name": "moon_landing", "size": "medium", "formats": "tiff,jpeg"},
        {"name": "vaccine_conspiracies", "size": "medium", "formats": "csv,json"},
        {"name": "new_world_order", "size": "small", "formats": "pdf,html"},
    ]

    for theory in theories:
        query = (
            f"g.V().has('Theory', 'theory_name', '{theory['name']}').fold()"
            f".coalesce(unfold(), "
            f"addV('Theory')"
            f".property('theory_name', '{theory['name']}')"
            f".property('dataset_size', '{theory['size']}')"
            f".property('primary_formats', '{theory['formats']}')"
            f".property('tenant', 'conspiracy_theories')"
            f")"
        )
        result = execute_gremlin(query)
        if result:
            print(f"  ✓ Theory vertex: {theory['name']}")
        else:
            print(f"  ✗ Failed: {theory['name']}")


def seed_domain_vertices():
    """Create ConspiracyDomain vertices for the 10 universal domains."""
    domains = [
        ("evidence_suppression", "Documents hidden, destroyed, classified, or made inaccessible"),
        ("institutional_behavior", "Inter-agency coordination, contradictory official statements"),
        ("witness_reliability", "Credibility indicators, corroboration patterns, recantation"),
        ("timeline_anomalies", "Events out of sequence, impossible timing, retroactive dating"),
        ("geographic_clustering", "Statistically unlikely spatial concentration"),
        ("information_asymmetry", "What was known vs disclosed, delayed revelations"),
        ("counter_narrative_emergence", "How alternative explanations develop and propagate"),
        ("narrative_coherence", "Does official story survive logical scrutiny"),
        ("expert_divergence", "Credentialed experts contradicting institutional position"),
        ("methodological_red_flags", "Investigation flawed: scope narrowed, evidence mishandled"),
    ]

    for name, desc in domains:
        query = (
            f"g.V().has('ConspiracyDomain', 'name', '{name}').fold()"
            f".coalesce(unfold(), "
            f"addV('ConspiracyDomain')"
            f".property('name', '{name}')"
            f".property('description', '{desc}')"
            f".property('tenant', 'conspiracy_theories')"
            f")"
        )
        result = execute_gremlin(query)
        if result:
            print(f"  ✓ Domain vertex: {name}")
        else:
            print(f"  ✗ Failed: {name}")


def main():
    print("Seeding Neptune graph schema for Conspiracy Theory Taxonomy...")
    print("\nNote: Neptune doesn't require explicit schema creation.")
    print("Vertices and edges are created on first use.")
    print("This script seeds the initial Theory and Domain vertices.\n")

    print("Creating Theory vertices (10 conspiracy theories):")
    seed_theory_vertices()

    print("\nCreating ConspiracyDomain vertices (10 universal domains):")
    seed_domain_vertices()

    print("\nNeptune schema seeded.")
    print("\nVertex labels that will be used:")
    print("  - Theory (10 theories)")
    print("  - ConspiracyDocument (created during ingestion)")
    print("  - ConspiracyDomain (10 domains)")
    print("  - ConspiracyTypology (created during seeding)")
    print("  - ConspiracyMethod (created during seeding)")
    print("  - ConspiracySignature (created during seeding)")
    print("  - PrecedentCase (created during seeding)")
    print("\nEdge labels that will be used:")
    print("  - belongs_to (Document → Theory)")
    print("  - matches (Document → Signature, with similarity_score)")
    print("  - contains (Domain → Typology → Method → Signature → Case)")
    print("  - cross_connects (Document → Document, with justification)")
    print("  - geo_correlates (Document → Ancient Mystery Entity, with distance_km)")


if __name__ == "__main__":
    main()
