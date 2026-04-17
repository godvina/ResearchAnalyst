"""AI-Powered Cost Estimation Service.

Computes detailed cost estimates from customer intake answers and generated
Pipeline_Config, using externalized AWS pricing data from config/aws_pricing.json.

Provides:
- estimate: full cost breakdown (one-time + monthly + optimizations + tiers)
- _compute_one_time: Textract, Bedrock extraction/embeddings, Rekognition, Lambda, S3
- _compute_monthly: OpenSearch OCUs, Neptune NCUs, Aurora ACUs, S3, API Gateway
- _suggest_optimizations: cost reduction recommendations
- _compute_tiers: economy, recommended, premium tier configs
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Default pricing file path (relative to project root)
_DEFAULT_PRICING_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "config", "aws_pricing.json"
)


class CostEstimationService:
    """Computes cost estimates from customer profile and pipeline config."""

    def __init__(self, pricing_file: str | None = None) -> None:
        path = pricing_file or _DEFAULT_PRICING_PATH
        self.pricing = self._load_pricing(path)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_pricing(path: str) -> dict:
        resolved = Path(path).resolve()
        with open(resolved) as f:
            return json.load(f)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def estimate(self, answers: dict, config: dict) -> dict:
        """Return a full CostEstimate dict."""
        one_time = self._compute_one_time(answers, config)
        monthly = self._compute_monthly(answers, config)
        optimizations = self._suggest_optimizations(one_time, monthly, answers, config)
        tiers = self._compute_tiers(answers, config)
        return {
            "one_time": one_time,
            "monthly": monthly,
            "optimizations": optimizations,
            "tiers": tiers,
        }

    # ------------------------------------------------------------------
    # One-time costs
    # ------------------------------------------------------------------

    def _compute_one_time(self, answers: dict, config: dict) -> dict:
        """Compute one-time processing costs."""
        costs: dict[str, float] = {}
        doc_count = answers.get("document_count", 0)
        avg_pages = answers.get("avg_page_count", 10)
        scanned_pct = answers.get("scanned_percentage", 0) / 100.0
        volume_tb = answers.get("total_volume_tb", 0)
        image_count = answers.get("image_count", 0)
        video_hours = answers.get("video_hours", 0)

        # Textract — only for scanned docs
        if scanned_pct > 0:
            scanned_pages = doc_count * avg_pages * scanned_pct
            rate = self.pricing["textract"]["per_1000_pages"]
            costs["textract"] = round(scanned_pages / 1000 * rate, 2)

        # Bedrock entity extraction
        extract_cfg = config.get("extract", {})
        model_id = extract_cfg.get(
            "llm_model_id", "anthropic.claude-3-sonnet-20240229-v1:0"
        )
        chunk_size = extract_cfg.get("chunk_size_chars", 8000)
        avg_chars_per_doc = avg_pages * 2000  # rough estimate
        chunks_per_doc = max(1, avg_chars_per_doc // chunk_size)
        avg_input_tokens = chunk_size // 4  # ~4 chars per token
        avg_output_tokens = 500
        model_pricing = self.pricing["bedrock"].get(model_id, {})
        input_rate = model_pricing.get("input_per_1m", 3.0)
        output_rate = model_pricing.get("output_per_1m", 15.0)
        total_input = doc_count * chunks_per_doc * avg_input_tokens
        total_output = doc_count * chunks_per_doc * avg_output_tokens
        costs["bedrock_extraction"] = round(
            total_input / 1_000_000 * input_rate
            + total_output / 1_000_000 * output_rate,
            2,
        )

        # Bedrock embeddings
        embed_model = config.get("embed", {}).get(
            "embedding_model_id", "amazon.titan-embed-text-v1"
        )
        embed_pricing = self.pricing["bedrock"].get(embed_model, {})
        embed_tokens = doc_count * chunks_per_doc * avg_input_tokens
        costs["bedrock_embeddings"] = round(
            embed_tokens / 1_000_000 * embed_pricing.get("input_per_1m", 0.10), 2
        )

        # Rekognition
        rek_cfg = config.get("rekognition", {})
        if rek_cfg.get("enabled") and image_count > 0:
            rek_p = self.pricing["rekognition"]
            costs["rekognition_images"] = round(
                image_count / 1000 * rek_p["image_per_1000"], 2
            )
            if rek_cfg.get("watchlist_collection_id"):
                costs["rekognition_face_compare"] = round(
                    image_count * rek_p["face_compare_each"], 2
                )
        if rek_cfg.get("enabled") and video_hours > 0:
            rek_p = self.pricing["rekognition"]
            video_mins = video_hours * 60
            video_mode = rek_cfg.get("video_processing_mode", "skip")
            if video_mode == "skip":
                costs["rekognition_video"] = 0.0
                costs["rekognition_video_note"] = "Video processing skipped (process after document analysis)"
            elif video_mode == "faces_only":
                costs["rekognition_video"] = round(video_mins * rek_p["video_face_per_min"], 2)
                costs["rekognition_video_note"] = "Faces only — no label detection"
            elif video_mode == "targeted":
                # Estimate 20% of videos flagged
                flagged_pct = 0.2
                costs["rekognition_video"] = round(
                    video_mins * flagged_pct * (rek_p["video_label_per_min"] + rek_p["video_face_per_min"]), 2
                )
                costs["rekognition_video_note"] = f"Targeted — estimated {int(flagged_pct*100)}% of videos flagged"
            elif video_mode == "full":
                costs["rekognition_video"] = round(
                    video_mins * (rek_p["video_label_per_min"] + rek_p["video_face_per_min"]), 2
                )
                costs["rekognition_video_note"] = "Full processing — all detections on all videos"

        # Lambda compute
        total_invocations = doc_count * (chunks_per_doc + 3)  # extract + embed + graph + store
        lam = self.pricing["lambda"]
        costs["lambda"] = round(
            total_invocations / 1_000_000 * lam["per_1m_requests"]
            + total_invocations
            * (lam["avg_duration_ms"] / 1000)
            * (lam["avg_memory_mb"] / 1024)
            * lam["per_gb_second"],
            2,
        )

        # S3 storage
        volume_gb = volume_tb * 1024
        costs["s3_storage"] = round(volume_gb * self.pricing["s3"]["gb_per_month"], 2)

        # Classification cost — only for ai_classification routing mode
        classification_cfg = config.get("classification", {})
        if classification_cfg.get("routing_mode") == "ai_classification":
            haiku_pricing = self.pricing.get("bedrock", {}).get(
                "anthropic.claude-3-haiku-20240307-v1:0", {}
            )
            haiku_input_rate = haiku_pricing.get("input_per_1m", 0.25)
            haiku_output_rate = haiku_pricing.get("output_per_1m", 1.25)
            classification_input_tokens = doc_count * 2500
            classification_output_tokens = doc_count * 100
            classification_cost = (
                classification_input_tokens / 1_000_000 * haiku_input_rate
                + classification_output_tokens / 1_000_000 * haiku_output_rate
            )
            costs["classification"] = round(classification_cost, 2)

        costs["total"] = round(sum(costs.values()), 2)
        return costs

    # ------------------------------------------------------------------
    # Monthly costs
    # ------------------------------------------------------------------

    def _compute_monthly(self, answers: dict, config: dict) -> dict:
        """Compute monthly running costs."""
        costs: dict[str, float] = {}
        doc_count = answers.get("document_count", 0)
        volume_tb = answers.get("total_volume_tb", 0)
        hours = self.pricing["hours_per_month"]

        # OpenSearch Serverless OCUs
        search_tier = config.get("embed", {}).get("search_tier", "standard")
        min_ocu = self.pricing["opensearch_serverless"]["min_ocu"].get(search_tier, 2)
        # Scale OCUs with volume: +1 OCU per 500K docs
        extra_ocu = max(0, doc_count // 500_000)
        ocu_count = min_ocu + extra_ocu
        costs["opensearch"] = round(
            ocu_count * self.pricing["opensearch_serverless"]["ocu_per_hour"] * hours, 2
        )

        # Neptune Serverless NCUs
        # Estimate: 1 NCU base + 1 per 100K entities (rough: 5 entities/doc)
        est_entities = doc_count * 5
        ncu_count = max(
            self.pricing["neptune_serverless"]["min_ncu"],
            1.0 + est_entities / 100_000,
        )
        ncu_count = min(ncu_count, self.pricing["neptune_serverless"]["max_ncu"])
        costs["neptune"] = round(
            ncu_count * self.pricing["neptune_serverless"]["ncu_per_hour"] * hours, 2
        )

        # Aurora Serverless ACUs
        acu_count = max(self.pricing["aurora_serverless"]["min_acu"], 0.5)
        if doc_count > 100_000:
            acu_count = 2.0
        if doc_count > 1_000_000:
            acu_count = 4.0
        costs["aurora"] = round(
            acu_count * self.pricing["aurora_serverless"]["acu_per_hour"] * hours, 2
        )

        # S3 ongoing storage
        volume_gb = volume_tb * 1024
        costs["s3"] = round(volume_gb * self.pricing["s3"]["gb_per_month"], 2)

        # API Gateway + Lambda (monthly API calls)
        concurrent_users = answers.get("concurrent_users", 10)
        monthly_api_calls = concurrent_users * 1000 * 22  # ~22 working days
        costs["api_gateway_lambda"] = round(
            monthly_api_calls / 1_000_000 * self.pricing["api_gateway"]["per_1m_requests"]
            + monthly_api_calls / 1_000_000 * self.pricing["lambda"]["per_1m_requests"],
            2,
        )

        costs["total"] = round(sum(costs.values()), 2)
        return costs

    # ------------------------------------------------------------------
    # Optimizations
    # ------------------------------------------------------------------

    def _suggest_optimizations(
        self, one_time: dict, monthly: dict, answers: dict, config: dict
    ) -> list[str]:
        """Generate cost reduction recommendations."""
        suggestions: list[str] = []
        model_id = config.get("extract", {}).get(
            "llm_model_id", "anthropic.claude-3-sonnet-20240229-v1:0"
        )

        # Suggest batch inference
        if one_time.get("bedrock_extraction", 0) > 100:
            savings = round(one_time["bedrock_extraction"] * 0.5, 2)
            suggestions.append(
                f"Use Bedrock Batch Inference for entity extraction to save ~50% (${savings} savings)"
            )

        # Suggest PyPDF2 over Textract for searchable PDFs
        scanned_pct = answers.get("scanned_percentage", 0)
        if scanned_pct < 50 and one_time.get("textract", 0) > 0:
            suggestions.append(
                "Use PyPDF2 instead of Textract for searchable PDFs to reduce Textract costs"
            )

        # Suggest Haiku over Sonnet
        if "sonnet" in model_id.lower():
            haiku_cost = one_time.get("bedrock_extraction", 0) * 0.083  # Haiku ~12x cheaper
            savings = round(one_time.get("bedrock_extraction", 0) - haiku_cost, 2)
            suggestions.append(
                f"Use Haiku instead of Sonnet for entity extraction to save ${savings} with minimal quality impact"
            )

        # Suggest lower OpenSearch tier
        doc_count = answers.get("document_count", 0)
        if doc_count < 1_000_000 and config.get("embed", {}).get("search_tier") == "enterprise":
            suggestions.append(
                "Reduce OpenSearch to standard tier for cases under 1M documents"
            )

        return suggestions

    # ------------------------------------------------------------------
    # Tiers
    # ------------------------------------------------------------------

    def _compute_tiers(self, answers: dict, config: dict) -> dict:
        """Compute economy, recommended, and premium tier estimates."""
        tiers: dict[str, dict] = {}

        # Economy: Haiku, standard tier, lower concurrency
        economy_config = {
            **config,
            "extract": {
                **config.get("extract", {}),
                "llm_model_id": "anthropic.claude-3-haiku-20240307-v1:0",
                "confidence_threshold": 0.4,
            },
            "embed": {
                **config.get("embed", {}),
                "search_tier": "standard",
            },
        }
        eco_one = self._compute_one_time(answers, economy_config)
        eco_mon = self._compute_monthly(answers, economy_config)
        tiers["economy"] = {
            "label": "Economy",
            "description": "Lowest cost — Haiku model, standard search tier",
            "one_time_total": eco_one["total"],
            "monthly_total": eco_mon["total"],
        }

        # Recommended: Sonnet, standard tier
        rec_one = self._compute_one_time(answers, config)
        rec_mon = self._compute_monthly(answers, config)
        tiers["recommended"] = {
            "label": "Recommended",
            "description": "Balanced quality and cost — Sonnet model",
            "one_time_total": rec_one["total"],
            "monthly_total": rec_mon["total"],
        }

        # Premium: Sonnet, enterprise tier, higher thresholds
        premium_config = {
            **config,
            "extract": {
                **config.get("extract", {}),
                "confidence_threshold": 0.7,
                "relationship_inference_enabled": True,
            },
            "embed": {
                **config.get("embed", {}),
                "search_tier": "enterprise",
            },
        }
        prem_one = self._compute_one_time(answers, premium_config)
        prem_mon = self._compute_monthly(answers, premium_config)
        tiers["premium"] = {
            "label": "Premium",
            "description": "Maximum quality — enterprise search, high confidence",
            "one_time_total": prem_one["total"],
            "monthly_total": prem_mon["total"],
        }

        return tiers
