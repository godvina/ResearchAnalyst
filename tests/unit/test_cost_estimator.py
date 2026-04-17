"""Unit tests for the cost estimator module."""

import pytest

from scripts.batch_loader.config import BatchConfig
from scripts.batch_loader.cost_estimator import CostEstimate, CostEstimator


class TestCostEstimate:
    """Tests for the CostEstimate dataclass."""

    def test_dataclass_fields(self):
        est = CostEstimate(
            textract_ocr_cost=1.0,
            bedrock_entity_cost=2.0,
            bedrock_embedding_cost=0.5,
            neptune_write_cost=0.3,
            total_estimated=3.8,
            estimated_ocr_pages=100,
            estimated_non_blank_docs=500,
        )
        assert est.textract_ocr_cost == 1.0
        assert est.bedrock_entity_cost == 2.0
        assert est.bedrock_embedding_cost == 0.5
        assert est.neptune_write_cost == 0.3
        assert est.total_estimated == 3.8
        assert est.estimated_ocr_pages == 100
        assert est.estimated_non_blank_docs == 500


class TestCostEstimator:
    """Tests for the CostEstimator class."""

    def test_init_loads_pricing(self):
        config = BatchConfig()
        estimator = CostEstimator(config)
        assert estimator.pricing is not None
        assert "textract" in estimator.pricing
        assert "bedrock" in estimator.pricing

    def test_default_blank_rate(self):
        config = BatchConfig()
        estimator = CostEstimator(config)
        assert estimator.historical_blank_rate == 0.45

    def test_custom_blank_rate(self):
        config = BatchConfig()
        estimator = CostEstimator(config, historical_blank_rate=0.30)
        assert estimator.historical_blank_rate == 0.30

    def test_estimate_returns_cost_estimate(self):
        config = BatchConfig()
        estimator = CostEstimator(config)
        result = estimator.estimate(file_count=5000)
        assert isinstance(result, CostEstimate)

    def test_estimate_non_blank_docs(self):
        config = BatchConfig()
        estimator = CostEstimator(config, historical_blank_rate=0.45)
        result = estimator.estimate(file_count=1000)
        assert result.estimated_non_blank_docs == 550  # 1000 * (1 - 0.45)

    def test_estimate_ocr_pages(self):
        config = BatchConfig()
        estimator = CostEstimator(config, historical_blank_rate=0.45)
        result = estimator.estimate(file_count=1000, avg_pages=3.0)
        non_blank = 550
        ocr_docs = int(non_blank * 0.15)  # 82
        expected_pages = int(ocr_docs * 3.0)  # 246
        assert result.estimated_ocr_pages == expected_pages

    def test_estimate_total_equals_sum_of_components(self):
        config = BatchConfig()
        estimator = CostEstimator(config)
        result = estimator.estimate(file_count=5000, avg_pages=3.0)
        component_sum = (
            result.textract_ocr_cost
            + result.bedrock_entity_cost
            + result.bedrock_embedding_cost
            + result.neptune_write_cost
        )
        assert abs(result.total_estimated - component_sum) < 0.001

    def test_estimate_all_components_non_negative(self):
        config = BatchConfig()
        estimator = CostEstimator(config)
        result = estimator.estimate(file_count=5000)
        assert result.textract_ocr_cost >= 0
        assert result.bedrock_entity_cost >= 0
        assert result.bedrock_embedding_cost >= 0
        assert result.neptune_write_cost >= 0
        assert result.total_estimated >= 0

    def test_estimate_zero_files(self):
        config = BatchConfig()
        estimator = CostEstimator(config)
        result = estimator.estimate(file_count=0)
        assert result.total_estimated == 0
        assert result.estimated_non_blank_docs == 0
        assert result.estimated_ocr_pages == 0

    def test_estimate_textract_cost_uses_pricing_file(self):
        """Verify Textract cost uses $1.50/1000 pages from aws_pricing.json."""
        config = BatchConfig()
        estimator = CostEstimator(config, historical_blank_rate=0.0)
        result = estimator.estimate(file_count=1000, avg_pages=1.0)
        # non_blank = 1000, ocr_docs = 150, ocr_pages = 150
        # cost = 150 * 1.50/1000 = 150 * 0.0015 = 0.225
        assert result.textract_ocr_cost == 0.225

    def test_display_prints_output(self, capsys):
        config = BatchConfig()
        estimator = CostEstimator(config)
        est = estimator.estimate(file_count=5000)
        estimator.display(est)
        captured = capsys.readouterr()
        assert "Cost Estimate" in captured.out
        assert "TOTAL ESTIMATED" in captured.out
        assert "Textract OCR" in captured.out
        assert "Bedrock entity extraction" in captured.out
        assert "Bedrock embedding" in captured.out
        assert "Neptune writes" in captured.out
