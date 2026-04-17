"""Tests for entity resolution service — fuzzy matching and cluster building."""

import pytest
from services.entity_resolution_service import (
    AUTO_MERGE_THRESHOLD,
    LLM_REVIEW_THRESHOLD,
    EntityResolutionService,
    MergeCandidate,
    compute_similarity,
    jaro_winkler,
    normalize_name,
)


class TestNormalizeName:
    def test_lowercase_and_strip(self):
        assert normalize_name("  Jeffrey Epstein  ") == "jeffrey epstein"

    def test_remove_prefix(self):
        assert normalize_name("Mr. Jeffrey Epstein") == "jeffrey epstein"
        assert normalize_name("Dr. John Smith") == "john smith"

    def test_collapse_whitespace(self):
        assert normalize_name("Jeffrey   E.   Epstein") == "jeffrey e. epstein"

    def test_strip_trailing_punctuation(self):
        assert normalize_name("Epstein, Jeffrey.") == "epstein, jeffrey"


class TestJaroWinkler:
    def test_identical(self):
        assert jaro_winkler("hello", "hello") == 1.0

    def test_empty(self):
        assert jaro_winkler("", "hello") == 0.0
        assert jaro_winkler("hello", "") == 0.0

    def test_similar(self):
        sim = jaro_winkler("jeffrey", "jeffery")
        assert sim > 0.95  # very similar

    def test_different(self):
        sim = jaro_winkler("apple", "zebra")
        assert sim < 0.5


class TestComputeSimilarity:
    def test_exact_after_normalize(self):
        assert compute_similarity("Jeffrey Epstein", "  jeffrey epstein  ", "person") == 1.0

    def test_initial_match(self):
        sim = compute_similarity("J. Epstein", "Jeffrey Epstein", "person")
        assert sim == 0.95

    def test_middle_initial(self):
        sim = compute_similarity("J. E. Epstein", "Jeffrey Edward Epstein", "person")
        assert sim == 0.95

    def test_reversed_name(self):
        sim = compute_similarity("Epstein, Jeffrey", "Jeffrey Epstein", "person")
        assert sim == 0.97

    def test_phone_exact_digits(self):
        sim = compute_similarity("(212) 555-0142", "212-555-0142", "phone_number")
        assert sim == 1.0

    def test_phone_different(self):
        sim = compute_similarity("212-555-0142", "212-555-9999", "phone_number")
        assert sim == 0.0

    def test_similar_person_names(self):
        sim = compute_similarity("Jeffrey Epstein", "Jeffrey E. Epstein", "person")
        assert sim >= LLM_REVIEW_THRESHOLD

    def test_different_people(self):
        sim = compute_similarity("Jeffrey Epstein", "John Smith", "person")
        assert sim < LLM_REVIEW_THRESHOLD

    def test_mr_prefix_stripped(self):
        sim = compute_similarity("Mr. Jeffrey Epstein", "Jeffrey Epstein", "person")
        assert sim == 1.0

    def test_organization_similar(self):
        sim = compute_similarity("JP Morgan Chase", "JPMorgan Chase", "organization")
        assert sim >= LLM_REVIEW_THRESHOLD


class TestFindCandidates:
    def test_finds_similar_pairs(self):
        svc = EntityResolutionService(neptune_endpoint="fake", neptune_port="8182")
        entities = [
            {"name": "Jeffrey Epstein", "type": "person", "occurrence_count": 100, "confidence": 0.95},
            {"name": "Jeffrey E. Epstein", "type": "person", "occurrence_count": 50, "confidence": 0.90},
            {"name": "John Smith", "type": "person", "occurrence_count": 10, "confidence": 0.80},
        ]
        candidates = svc.find_candidates(entities)
        # Should find Jeffrey Epstein / Jeffrey E. Epstein as a candidate
        epstein_pairs = [c for c in candidates if "Epstein" in c.name_a and "Epstein" in c.name_b]
        assert len(epstein_pairs) >= 1
        assert epstein_pairs[0].similarity >= LLM_REVIEW_THRESHOLD

    def test_no_cross_type_matches(self):
        svc = EntityResolutionService(neptune_endpoint="fake", neptune_port="8182")
        entities = [
            {"name": "New York", "type": "location", "occurrence_count": 50, "confidence": 0.9},
            {"name": "New York", "type": "organization", "occurrence_count": 5, "confidence": 0.6},
        ]
        candidates = svc.find_candidates(entities)
        # Same name but different types — should NOT be matched
        assert len(candidates) == 0


class TestBuildClusters:
    def test_simple_cluster(self):
        svc = EntityResolutionService(neptune_endpoint="fake", neptune_port="8182")
        entities = [
            {"name": "Jeffrey Epstein", "type": "person", "occurrence_count": 100, "confidence": 0.95},
            {"name": "Jeffrey E. Epstein", "type": "person", "occurrence_count": 50, "confidence": 0.90},
            {"name": "J. Epstein", "type": "person", "occurrence_count": 10, "confidence": 0.80},
        ]
        candidates = [
            MergeCandidate("Jeffrey Epstein", "Jeffrey E. Epstein", "person", 0.95, "auto"),
            MergeCandidate("Jeffrey Epstein", "J. Epstein", "person", 0.95, "auto"),
        ]
        clusters = svc.build_clusters(candidates, entities)
        assert len(clusters) == 1
        assert clusters[0].canonical_name == "Jeffrey Epstein"  # highest occ
        assert set(clusters[0].aliases) == {"Jeffrey E. Epstein", "J. Epstein"}
        assert clusters[0].total_occurrences == 160

    def test_rejected_not_clustered(self):
        svc = EntityResolutionService(neptune_endpoint="fake", neptune_port="8182")
        entities = [
            {"name": "A", "type": "person", "occurrence_count": 10, "confidence": 0.9},
            {"name": "B", "type": "person", "occurrence_count": 5, "confidence": 0.8},
        ]
        candidates = [
            MergeCandidate("A", "B", "person", 0.85, "llm_rejected"),
        ]
        clusters = svc.build_clusters(candidates, entities)
        assert len(clusters) == 0

    def test_transitive_merge(self):
        """A~B and B~C should produce one cluster {A, B, C}."""
        svc = EntityResolutionService(neptune_endpoint="fake", neptune_port="8182")
        entities = [
            {"name": "A", "type": "person", "occurrence_count": 100, "confidence": 0.9},
            {"name": "B", "type": "person", "occurrence_count": 50, "confidence": 0.9},
            {"name": "C", "type": "person", "occurrence_count": 10, "confidence": 0.9},
        ]
        candidates = [
            MergeCandidate("A", "B", "person", 0.95, "auto"),
            MergeCandidate("B", "C", "person", 0.93, "auto"),
        ]
        clusters = svc.build_clusters(candidates, entities)
        assert len(clusters) == 1
        assert clusters[0].canonical_name == "A"
        assert set(clusters[0].aliases) == {"B", "C"}


class TestReferenceIdDetection:
    def test_efta_codes_not_merged(self):
        """EFTA00001515 and EFTA00002165 are different doc IDs, not duplicates."""
        sim = compute_similarity("EFTA00001515", "EFTA00002165", "artifact")
        assert sim == 0.0

    def test_efta_exact_match(self):
        sim = compute_similarity("EFTA00001515", "EFTA00001515", "artifact")
        assert sim == 1.0

    def test_bates_numbers_not_merged(self):
        sim = compute_similarity("EFTA000", "EFTA0000", "artifact")
        assert sim == 0.0

    def test_normal_artifacts_still_fuzzy(self):
        """Non-reference-ID artifacts should still use fuzzy matching."""
        sim = compute_similarity("Ark of the Covenant", "Ark of Covenant", "artifact")
        assert sim > 0.8
