"""Cost estimation for batch processing of raw PDFs."""

import json
import os
from dataclasses import dataclass

from batch_loader.config import BatchConfig


@dataclass
class CostEstimate:
    """Estimated AWS costs for a batch."""

    textract_ocr_cost: float
    bedrock_entity_cost: float
    bedrock_embedding_cost: float
    neptune_write_cost: float
    total_estimated: float
    estimated_ocr_pages: int
    estimated_non_blank_docs: int


@dataclass
class DualCostEstimate:
    """Gross and net cost estimates with per-component breakdown."""

    gross: CostEstimate
    net: CostEstimate
    blank_page_rate: float
    component_breakdown: dict  # {component: {gross: float, net: float}}

    @dataclass
    class DualCostEstimate:
        """Gross and net cost estimates with per-component breakdown."""

        gross: CostEstimate
        net: CostEstimate
        blank_page_rate: float
        component_breakdown: dict  # {component: {gross: float, net: float}}


class CostEstimator:
    """Estimates AWS costs for a batch before processing."""

    def __init__(self, config: BatchConfig, historical_blank_rate: float = 0.45):
        self.config = config
        self.historical_blank_rate = historical_blank_rate
        self.pricing = self._load_pricing()

    def _load_pricing(self) -> dict:
        """Load pricing data from config/aws_pricing.json."""
        # Try multiple paths: Lambda (/var/task/config/), relative to file, project root
        candidates = [
            os.path.join(os.environ.get("LAMBDA_TASK_ROOT", ""), "config", "aws_pricing.json"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "aws_pricing.json"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config", "aws_pricing.json"),
        ]
        for pricing_path in candidates:
            if os.path.exists(pricing_path):
                with open(pricing_path) as f:
                    return json.load(f)
        # Fallback: return default pricing
        return {"textract_per_page": 0.001, "bedrock_embed_per_1k_tokens": 0.0001, "bedrock_extract_per_1k_tokens": 0.003, "s3_put_per_1k": 0.005, "s3_get_per_1k": 0.0004, "step_functions_per_transition": 0.000025}

    def estimate(self, file_count: int, avg_pages: float = 3.0) -> CostEstimate:
        """Calculate estimated costs for a batch.

        Args:
            file_count: Number of raw PDF files in the batch.
            avg_pages: Average pages per document (default 3.0).

        Returns:
            CostEstimate with per-component and total costs.
        """
        non_blank_docs = int(file_count * (1 - self.historical_blank_rate))

        # ~15% of non-blank docs need OCR
        estimated_ocr_docs = int(non_blank_docs * 0.15)
        estimated_ocr_pages = int(estimated_ocr_docs * avg_pages)

        # Textract OCR: $1.50 per 1000 pages = $0.0015/page
        textract_per_page = self.pricing["textract"]["per_1000_pages"] / 1000.0
        textract_ocr_cost = estimated_ocr_pages * textract_per_page

        # Bedrock entity extraction: Nova Pro pricing ~$0.004/doc
        # Using input pricing: $0.80 per 1M tokens. Assume ~5000 tokens/doc input.
        # 5000 / 1_000_000 * 0.80 = $0.004/doc
        bedrock_entity_cost = non_blank_docs * 0.004

        # Bedrock embedding: Titan Embed $0.10 per 1M tokens. Assume ~1000 tokens/doc.
        # 1000 / 1_000_000 * 0.10 = $0.0001/doc
        bedrock_embedding_cost = non_blank_docs * 0.0001

        # Neptune write: estimated ~$0.001/doc from NCU usage
        neptune_write_cost = non_blank_docs * 0.001

        total_estimated = (
            textract_ocr_cost
            + bedrock_entity_cost
            + bedrock_embedding_cost
            + neptune_write_cost
        )

        return CostEstimate(
            textract_ocr_cost=round(textract_ocr_cost, 4),
            bedrock_entity_cost=round(bedrock_entity_cost, 4),
            bedrock_embedding_cost=round(bedrock_embedding_cost, 4),
            neptune_write_cost=round(neptune_write_cost, 4),
            total_estimated=round(total_estimated, 4),
            estimated_ocr_pages=estimated_ocr_pages,
            estimated_non_blank_docs=non_blank_docs,
        )

    def estimate_dual(
        self, file_count: int, blank_page_rate: float = 0.40, avg_pages: float = 3.0
    ) -> DualCostEstimate:
        """Calculate both gross (all files) and net (blank-adjusted) estimates.

        Args:
            file_count: Number of raw PDF files.
            blank_page_rate: Expected proportion of blank docs (0.0–1.0, default 0.40).
            avg_pages: Average pages per document.

        Returns:
            DualCostEstimate with gross, net, and per-component breakdown.
        """
        import logging as _log

        # Clamp blank_page_rate
        if blank_page_rate < 0.0 or blank_page_rate > 1.0:
            _log.getLogger(__name__).warning(
                "blank_page_rate %.2f out of range, clamping to [0, 1]", blank_page_rate
            )
            blank_page_rate = max(0.0, min(1.0, blank_page_rate))

        if file_count <= 0:
            zero = CostEstimate(0, 0, 0, 0, 0, 0, 0)
            return DualCostEstimate(
                gross=zero, net=zero, blank_page_rate=blank_page_rate,
                component_breakdown={
                    "textract": {"gross": 0, "net": 0},
                    "bedrock_entity": {"gross": 0, "net": 0},
                    "bedrock_embedding": {"gross": 0, "net": 0},
                    "neptune": {"gross": 0, "net": 0},
                },
            )

        # Gross: treat all files as non-blank
        old_rate = self.historical_blank_rate
        self.historical_blank_rate = 0.0
        gross = self.estimate(file_count, avg_pages)
        self.historical_blank_rate = old_rate

        # Net: apply the user-specified blank_page_rate
        self.historical_blank_rate = blank_page_rate
        net = self.estimate(file_count, avg_pages)
        self.historical_blank_rate = old_rate

        breakdown = {
            "textract": {"gross": gross.textract_ocr_cost, "net": net.textract_ocr_cost},
            "bedrock_entity": {"gross": gross.bedrock_entity_cost, "net": net.bedrock_entity_cost},
            "bedrock_embedding": {"gross": gross.bedrock_embedding_cost, "net": net.bedrock_embedding_cost},
            "neptune": {"gross": gross.neptune_write_cost, "net": net.neptune_write_cost},
        }

        return DualCostEstimate(
            gross=gross,
            net=net,
            blank_page_rate=blank_page_rate,
            component_breakdown=breakdown,
        )

    def display(self, estimate: CostEstimate):
        """Print formatted cost breakdown to stdout."""
        print("=" * 60)
        print("  Cost Estimate")
        print("=" * 60)
        print(f"  Estimated non-blank docs:  {estimate.estimated_non_blank_docs:,}")
        print(f"  Estimated OCR pages:       {estimate.estimated_ocr_pages:,}")
        print("-" * 60)
        print(f"  Textract OCR:              ${estimate.textract_ocr_cost:,.4f}")
        print(f"  Bedrock entity extraction: ${estimate.bedrock_entity_cost:,.4f}")
        print(f"  Bedrock embedding:         ${estimate.bedrock_embedding_cost:,.4f}")
        print(f"  Neptune writes:            ${estimate.neptune_write_cost:,.4f}")
        print("-" * 60)
        print(f"  TOTAL ESTIMATED:           ${estimate.total_estimated:,.4f}")
        print("=" * 60)
