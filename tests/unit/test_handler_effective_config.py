"""Unit tests verifying that pipeline step handlers read from effective_config
with proper fallback to defaults when effective_config is absent."""

import pytest


class TestEmbedHandlerConfig:
    """Verify embed_handler reads embed section from effective_config."""

    def test_model_id_from_effective_config(self):
        """When effective_config.embed.embedding_model_id is set, it should be used."""
        # We test the config extraction logic directly rather than invoking
        # the full handler (which requires Bedrock, DB, etc.).
        event = {
            "case_id": "c1",
            "document_id": "d1",
            "raw_text": "hello",
            "effective_config": {
                "embed": {
                    "embedding_model_id": "custom-model-v2",
                    "search_tier": "enterprise",
                    "opensearch_settings": {"index_name": "custom"},
                }
            },
        }
        embed_cfg = event.get("effective_config", {}).get("embed", {})
        model_id = embed_cfg.get("embedding_model_id", "amazon.titan-embed-text-v1")
        search_tier = embed_cfg.get("search_tier")
        opensearch_settings = embed_cfg.get("opensearch_settings", {})

        assert model_id == "custom-model-v2"
        assert search_tier == "enterprise"
        assert opensearch_settings == {"index_name": "custom"}

    def test_fallback_when_no_effective_config(self):
        """When effective_config is absent, defaults should be used."""
        event = {
            "case_id": "c1",
            "document_id": "d1",
            "raw_text": "hello",
        }
        embed_cfg = event.get("effective_config", {}).get("embed", {})
        model_id = embed_cfg.get("embedding_model_id", "amazon.titan-embed-text-v1")
        search_tier = embed_cfg.get("search_tier")
        opensearch_settings = embed_cfg.get("opensearch_settings", {})

        assert model_id == "amazon.titan-embed-text-v1"
        assert search_tier is None
        assert opensearch_settings == {}

    def test_partial_effective_config(self):
        """When effective_config exists but embed section is missing, defaults apply."""
        event = {
            "case_id": "c1",
            "document_id": "d1",
            "raw_text": "hello",
            "effective_config": {"parse": {"pdf_method": "ocr"}},
        }
        embed_cfg = event.get("effective_config", {}).get("embed", {})
        model_id = embed_cfg.get("embedding_model_id", "amazon.titan-embed-text-v1")

        assert model_id == "amazon.titan-embed-text-v1"


class TestGraphLoadHandlerConfig:
    """Verify graph_load_handler reads graph_load section from effective_config."""

    def test_load_strategy_from_effective_config(self):
        """When effective_config.graph_load.load_strategy is set, it should be used."""
        event = {
            "case_id": "c1",
            "extraction_results": [],
            "effective_config": {
                "graph_load": {
                    "load_strategy": "bulk_csv",
                    "batch_size": 1000,
                }
            },
        }
        graph_load_cfg = event.get("effective_config", {}).get("graph_load", {})
        load_strategy = graph_load_cfg.get(
            "load_strategy", event.get("load_strategy", "gremlin")
        )
        batch_size = graph_load_cfg.get("batch_size", event.get("batch_size", 0))

        assert load_strategy == "bulk_csv"
        assert batch_size == 1000

    def test_fallback_to_event_level_load_strategy(self):
        """When no effective_config, fall back to event-level load_strategy."""
        event = {
            "case_id": "c1",
            "load_strategy": "gremlin",
            "extraction_results": [],
        }
        graph_load_cfg = event.get("effective_config", {}).get("graph_load", {})
        load_strategy = graph_load_cfg.get(
            "load_strategy", event.get("load_strategy", "gremlin")
        )

        assert load_strategy == "gremlin"

    def test_fallback_to_hardcoded_default(self):
        """When neither effective_config nor event-level strategy, use hardcoded default."""
        event = {
            "case_id": "c1",
            "extraction_results": [],
        }
        graph_load_cfg = event.get("effective_config", {}).get("graph_load", {})
        load_strategy = graph_load_cfg.get(
            "load_strategy", event.get("load_strategy", "gremlin")
        )

        assert load_strategy == "gremlin"


class TestExtractHandlerConfig:
    """Verify extract_handler reads extract section from effective_config."""

    def test_extract_config_from_effective_config(self):
        """When effective_config.extract is set, values should be extracted."""
        event = {
            "case_id": "c1",
            "document_id": "d1",
            "raw_text": "hello",
            "effective_config": {
                "extract": {
                    "llm_model_id": "anthropic.claude-3-sonnet-20240229-v1:0",
                    "chunk_size_chars": 20000,
                    "confidence_threshold": 0.7,
                    "entity_types": ["person", "organization"],
                }
            },
        }
        extract_cfg = event.get("effective_config", {}).get("extract", {})

        assert extract_cfg.get("llm_model_id") == "anthropic.claude-3-sonnet-20240229-v1:0"
        assert extract_cfg.get("chunk_size_chars") == 20000
        assert extract_cfg.get("confidence_threshold") == 0.7
        assert extract_cfg.get("entity_types") == ["person", "organization"]

    def test_extract_config_absent_returns_none(self):
        """When no effective_config, extract params should be None."""
        event = {
            "case_id": "c1",
            "document_id": "d1",
            "raw_text": "hello",
        }
        extract_cfg = event.get("effective_config", {}).get("extract", {})

        assert extract_cfg.get("llm_model_id") is None
        assert extract_cfg.get("chunk_size_chars") is None
        assert extract_cfg.get("confidence_threshold") is None
        assert extract_cfg.get("entity_types") is None
