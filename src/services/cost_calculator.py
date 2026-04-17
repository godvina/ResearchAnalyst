"""Cost Calculator for customer deployment sizing and estimation."""

import json
import os
from typing import Any

PRICING_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'aws_pricing.json')

TIER_SIZING = {
    "Small": {"neptune": {"type": "serverless", "min_ncu": 1, "max_ncu": 4},
              "aurora": {"min_acu": 0.5, "max_acu": 4}, "opensearch": {"ocu": 2}},
    "Medium": {"neptune": {"type": "r6g.xlarge", "monthly": 730 * 0.88},
               "aurora": {"min_acu": 1, "max_acu": 8}, "opensearch": {"ocu": 4}},
    "Large": {"neptune": {"type": "r6g.2xlarge", "monthly": 730 * 1.76},
              "aurora": {"min_acu": 2, "max_acu": 16}, "opensearch": {"ocu": 8}},
    "Enterprise": {"neptune": {"type": "r6g.4xlarge", "monthly": 730 * 3.52},
                   "aurora": {"min_acu": 4, "max_acu": 32}, "opensearch": {"ocu": 16}},
}


class CostCalculator:
    def __init__(self, pricing_path: str = None):
        path = pricing_path or PRICING_PATH
        try:
            with open(path) as f:
                self._pricing = json.load(f)
        except Exception:
            self._pricing = {}
        self._hours = self._pricing.get("hours_per_month", 730)

    def determine_tier(self, document_count: int) -> str:
        if document_count < 100_000:
            return "Small"
        if document_count < 1_000_000:
            return "Medium"
        if document_count < 10_000_000:
            return "Large"
        return "Enterprise"

    def get_tier_sizing(self, tier: str) -> dict:
        return TIER_SIZING.get(tier, TIER_SIZING["Small"])

    def calculate(self, tier: str, modules: list[str], document_count: int,
                  avg_doc_size_mb: float = 1.0, entity_count: int = 0) -> dict:
        sizing = self.get_tier_sizing(tier)
        total_gb = document_count * avg_doc_size_mb / 1024

        monthly = {
            "aurora": self._aurora_cost(sizing),
            "neptune": self._neptune_cost(sizing, tier),
            "opensearch": self._opensearch_cost(sizing),
            "s3": self._s3_cost(total_gb),
            "lambda": self._lambda_cost(document_count),
            "api_gateway": self._api_gateway_cost(document_count),
            "bedrock": self._bedrock_cost(document_count),
            "cloudfront": max(1.0, total_gb * 0.085),
        }
        monthly["total"] = round(sum(monthly.values()), 2)

        # One-time ingestion costs
        one_time = {
            "ingestion_processing": self._ingestion_cost(document_count),
            "total": 0.0,
        }
        one_time["total"] = round(sum(v for k, v in one_time.items() if k != "total"), 2)

        return {
            "monthly": {k: round(v, 2) for k, v in monthly.items()},
            "annual": round(monthly["total"] * 12, 2),
            "one_time": {k: round(v, 2) for k, v in one_time.items()},
            "tier": tier,
            "total_data_volume_gb": round(total_gb, 2),
        }

    def _aurora_cost(self, sizing: dict) -> float:
        acu = sizing.get("aurora", {})
        avg_acu = (acu.get("min_acu", 0.5) + acu.get("max_acu", 4)) / 2
        rate = self._pricing.get("aurora_serverless", {}).get("acu_per_hour", 0.12)
        return avg_acu * rate * self._hours

    def _neptune_cost(self, sizing: dict, tier: str) -> float:
        nep = sizing.get("neptune", {})
        if nep.get("type") == "serverless":
            avg_ncu = (nep.get("min_ncu", 1) + nep.get("max_ncu", 4)) / 2
            rate = self._pricing.get("neptune_serverless", {}).get("ncu_per_hour", 0.22)
            return avg_ncu * rate * self._hours
        return nep.get("monthly", 500.0)

    def _opensearch_cost(self, sizing: dict) -> float:
        ocu = sizing.get("opensearch", {}).get("ocu", 2)
        rate = self._pricing.get("opensearch_serverless", {}).get("ocu_per_hour", 0.24)
        return ocu * rate * self._hours

    def _s3_cost(self, total_gb: float) -> float:
        rate = self._pricing.get("s3", {}).get("gb_per_month", 0.023)
        return max(0.01, total_gb * rate)

    def _lambda_cost(self, doc_count: int) -> float:
        p = self._pricing.get("lambda", {})
        requests = doc_count * 5  # ~5 Lambda invocations per doc
        req_cost = (requests / 1_000_000) * p.get("per_1m_requests", 0.20)
        duration_s = p.get("avg_duration_ms", 3000) / 1000
        memory_gb = p.get("avg_memory_mb", 512) / 1024
        compute_cost = requests * duration_s * memory_gb * p.get("per_gb_second", 0.0000166667)
        return req_cost + compute_cost

    def _api_gateway_cost(self, doc_count: int) -> float:
        requests = doc_count * 3
        rate = self._pricing.get("api_gateway", {}).get("per_1m_requests", 3.50)
        return (requests / 1_000_000) * rate

    def _bedrock_cost(self, doc_count: int) -> float:
        # Estimate: ~500 input tokens + ~200 output tokens per doc for entity extraction
        p = self._pricing.get("bedrock", {}).get("anthropic.claude-3-haiku-20240307-v1:0", {})
        input_cost = (doc_count * 500 / 1_000_000) * p.get("input_per_1m", 0.25)
        output_cost = (doc_count * 200 / 1_000_000) * p.get("output_per_1m", 1.25)
        return input_cost + output_cost

    def _ingestion_cost(self, doc_count: int) -> float:
        # Textract + Bedrock extraction + Lambda compute for initial processing
        textract = self._pricing.get("textract", {}).get("per_1000_pages", 1.50)
        textract_cost = (doc_count / 1000) * textract
        bedrock_cost = self._bedrock_cost(doc_count)
        lambda_cost = self._lambda_cost(doc_count)
        return textract_cost + bedrock_cost + lambda_cost
