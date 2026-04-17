"""Pipeline Configuration Wizard Service.

Maps customer intake questionnaire answers to an optimized Pipeline_Config,
generates cost estimates, produces shareable summaries, and supports
save/load of partial wizard progress.

Provides:
- generate_config: map wizard answers to Pipeline_Config JSON
- estimate_cost: delegate to CostEstimationService
- generate_summary: produce shareable HTML summary
- save_progress: persist partial wizard state to Aurora
- load_progress: reload saved wizard state
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

# Investigation type → base template mapping
_TYPE_TO_TEMPLATE = {
    "antitrust": "antitrust",
    "criminal": "criminal",
    "financial": "financial_fraud",
    "financial_fraud": "financial_fraud",
    "drug_trafficking": "criminal",
    "public_corruption": "criminal",
    "cybercrime": "criminal",
    "national_security": "criminal",
    "environmental": "antitrust",
    "civil_rights": "criminal",
    "immigration": "criminal",
}

# Entity types recommended per investigation type
_TYPE_ENTITY_MAP = {
    "antitrust": [
        "person", "organization", "financial_amount", "date",
        "event", "email", "address",
    ],
    "criminal": [
        "person", "location", "date", "event", "phone_number",
        "vehicle", "address", "organization",
    ],
    "financial_fraud": [
        "person", "organization", "account_number", "financial_amount",
        "date", "email", "address",
    ],
}


class WizardService:
    """Guided wizard that generates pipeline configs from intake answers."""

    def __init__(self, aurora_cm, bedrock_client=None, cost_service=None) -> None:
        self._db = aurora_cm
        self._bedrock = bedrock_client
        self._cost_service = cost_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_config(self, answers: dict) -> dict:
        """Map wizard answers to an optimized Pipeline_Config JSON.

        Steps:
        1. Start with template based on investigation_type
        2. Adjust entity_types based on goals
        3. Set pdf_method based on file formats
        4. Enable rekognition if images/video present
        5. Set search_tier based on volume and concurrent users
        6. Set graph_load strategy based on document count
        7. Optionally use AI to suggest custom extraction prompt
        """
        inv_type = answers.get("investigation_type", "criminal")
        quick_mode = answers.get("quick_mode", False)

        # 1. Base template
        template_key = _TYPE_TO_TEMPLATE.get(inv_type, "criminal")
        entity_types = list(
            _TYPE_ENTITY_MAP.get(template_key, _TYPE_ENTITY_MAP["criminal"])
        )

        # 2. Adjust entity types for specific goals
        goals = answers.get("investigation_goals", [])
        if "financial_tracking" in goals and "account_number" not in entity_types:
            entity_types.append("account_number")
        if "financial_tracking" in goals and "financial_amount" not in entity_types:
            entity_types.append("financial_amount")

        # 3. PDF method from file formats
        formats = answers.get("file_formats", [])
        scanned_pct = answers.get("scanned_percentage", 0)
        if scanned_pct > 80:
            pdf_method = "ocr"
        elif scanned_pct > 20 or "PDF scanned" in formats:
            pdf_method = "hybrid"
        else:
            pdf_method = "text"

        # 4. Rekognition
        image_count = answers.get("image_count", 0)
        video_hours = answers.get("video_hours", 0)
        rek_enabled = image_count > 0 or video_hours > 0

        # 5. Search tier based on volume
        doc_count = answers.get("document_count", 0)
        concurrent_users = answers.get("concurrent_users", 10)
        if doc_count > 1_000_000 or concurrent_users > 100:
            search_tier = "enterprise"
        else:
            search_tier = "standard"

        # 6. Graph load strategy
        if doc_count > 50_000:
            load_strategy = "bulk_csv"
            batch_size = 1000
        else:
            load_strategy = "bulk_csv"
            batch_size = 500

        # 7. Model selection
        if quick_mode:
            llm_model = "anthropic.claude-3-haiku-20240307-v1:0"
            confidence = 0.4
        else:
            llm_model = "anthropic.claude-3-sonnet-20240229-v1:0"
            confidence = 0.5

        config = {
            "parse": {
                "pdf_method": pdf_method,
                "ocr_enabled": scanned_pct > 0,
                "table_extraction_enabled": "Excel" in formats,
            },
            "extract": {
                "prompt_template": "default_investigative_v1",
                "entity_types": entity_types,
                "llm_model_id": llm_model,
                "chunk_size_chars": 8000,
                "confidence_threshold": confidence,
                "relationship_inference_enabled": True,
            },
            "embed": {
                "embedding_model_id": "amazon.titan-embed-text-v1",
                "search_tier": search_tier,
            },
            "graph_load": {
                "load_strategy": load_strategy,
                "batch_size": batch_size,
                "normalization_rules": {
                    "case_folding": True,
                    "trim_whitespace": True,
                    "alias_merging": inv_type in ("antitrust", "financial_fraud", "financial"),
                    "abbreviation_expansion": inv_type in ("antitrust", "financial_fraud", "financial"),
                },
            },
            "store_artifact": {
                "artifact_format": "json",
                "include_raw_text": False,
            },
        }

        # 8. Document Organization → classification config
        doc_org = answers.get("document_organization", "pre_organized")
        if doc_org == "pre_organized":
            config["classification"] = {"routing_mode": "folder_based"}
        elif doc_org == "has_case_numbers":
            pattern = answers.get("case_number_pattern", r"\d{4}-[A-Z]{2}-\d{5}")
            config["classification"] = {
                "routing_mode": "metadata_routing",
                "case_number_pattern": pattern,
            }
        elif doc_org == "mixed_unorganized":
            config["classification"] = {"routing_mode": "ai_classification"}
        elif doc_org == "unknown":
            config["classification"] = {
                "routing_mode": "ai_classification",
                "classify_sample_size": 100,
            }

        if rek_enabled:
            # Map video processing priority from wizard answers
            video_priority = answers.get("video_processing_priority", "after_docs")
            if video_priority == "with_initial_load":
                video_mode = "full"
            elif video_priority == "on_demand":
                video_mode = "targeted"
            else:
                video_mode = "skip"  # Default: process after document analysis

            config["rekognition"] = {
                "enabled": True,
                "video_processing_mode": video_mode,
                "min_face_confidence": 0.8,
                "min_object_confidence": 0.7,
                "detect_text": True,
                "detect_moderation_labels": False,
                "video_segment_length_seconds": 60,
            }

        return config

    def estimate_cost(self, answers: dict, config: dict) -> dict:
        """Delegate to CostEstimationService."""
        if self._cost_service is None:
            from services.cost_estimation_service import CostEstimationService
            self._cost_service = CostEstimationService()
        return self._cost_service.estimate(answers, config)

    def generate_summary(self, answers: dict, config: dict, cost: dict) -> str:
        """Generate a shareable HTML summary document."""
        inv_type = answers.get("investigation_type", "Unknown")
        doc_count = answers.get("document_count", 0)
        volume = answers.get("total_volume_tb", 0)

        one_time_total = cost.get("one_time", {}).get("total", 0)
        monthly_total = cost.get("monthly", {}).get("total", 0)

        html = f"""<!DOCTYPE html>
<html><head><title>Pipeline Configuration Summary</title>
<style>
body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
h1 {{ color: #1a365d; }} h2 {{ color: #2d3748; border-bottom: 1px solid #e2e8f0; }}
table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
th, td {{ border: 1px solid #e2e8f0; padding: 8px; text-align: left; }}
th {{ background: #f7fafc; }}
.cost {{ font-weight: bold; color: #2b6cb0; }}
</style></head><body>
<h1>Pipeline Configuration Summary</h1>
<h2>Investigation Profile</h2>
<table>
<tr><th>Type</th><td>{inv_type}</td></tr>
<tr><th>Documents</th><td>{doc_count:,}</td></tr>
<tr><th>Volume</th><td>{volume} TB</td></tr>
</table>
<h2>Cost Estimate</h2>
<table>
<tr><th>One-Time Processing</th><td class="cost">${one_time_total:,.2f}</td></tr>
<tr><th>Monthly Running</th><td class="cost">${monthly_total:,.2f}</td></tr>
</table>
<h2>Generated Configuration</h2>
<pre>{json.dumps(config, indent=2)}</pre>
<h2>Optimizations</h2>
<ul>"""
        for opt in cost.get("optimizations", []):
            html += f"\n<li>{opt}</li>"
        html += "\n</ul></body></html>"
        return html

    def save_progress(self, progress_id: Optional[str], answers: dict) -> str:
        """Save partial wizard state to Aurora. Returns progress_id."""
        if not progress_id:
            progress_id = str(uuid4())
        with self._db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO wizard_progress (progress_id, answers_json, updated_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (progress_id) DO UPDATE
                    SET answers_json = EXCLUDED.answers_json,
                        updated_at = EXCLUDED.updated_at
                """,
                (progress_id, json.dumps(answers), datetime.now(timezone.utc)),
            )
        return progress_id

    def load_progress(self, progress_id: str) -> dict:
        """Load saved wizard state from Aurora."""
        with self._db.cursor() as cur:
            cur.execute(
                "SELECT answers_json FROM wizard_progress WHERE progress_id = %s",
                (progress_id,),
            )
            row = cur.fetchone()
        if row is None:
            raise ValueError(f"No saved wizard progress found for id: {progress_id}")
        return row[0] if isinstance(row[0], dict) else json.loads(row[0])
