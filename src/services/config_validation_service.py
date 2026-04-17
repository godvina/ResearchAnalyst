"""Config Validation Service — validates pipeline configuration JSON
before it is saved.

Collects all validation errors (non-fail-fast) and returns a list of
ValidationError instances with field_path and reason for each violation.
"""

import re

from models.entity import EntityType
from models.pipeline_config import ValidationError


# Valid top-level section keys in a pipeline config
_VALID_SECTIONS = {"parse", "extract", "embed", "graph_load", "store_artifact", "rekognition", "classification", "face_crop", "image_description"}

# Known sub-keys per section
_PARSE_KEYS = {"pdf_method", "ocr_enabled", "table_extraction_enabled", "extract_images", "min_image_dimension"}
_EXTRACT_KEYS = {
    "prompt_template", "entity_types", "llm_model_id", "chunk_size_chars",
    "confidence_threshold", "relationship_inference_enabled",
}
_EMBED_KEYS = {"embedding_model_id", "search_tier", "opensearch_settings"}
_GRAPH_LOAD_KEYS = {"load_strategy", "batch_size", "normalization_rules"}
_STORE_ARTIFACT_KEYS = {"artifact_format", "include_raw_text"}
_REKOGNITION_KEYS = {
    "enabled", "watchlist_collection_id", "min_face_confidence",
    "min_object_confidence", "detect_text", "detect_moderation_labels",
    "video_segment_length_seconds", "video_processing_mode",
}
_CLASSIFICATION_KEYS = {
    "routing_mode", "case_number_pattern", "ai_model_id",
    "confidence_threshold", "max_preview_chars", "classify_sample_size",
}
_FACE_CROP_KEYS = {
    "enabled", "min_face_confidence", "thumbnail_size", "thumbnail_format",
}

_IMAGE_DESCRIPTION_KEYS = {
    "enabled", "model_id", "describe_all_images", "max_images_per_run",
    "max_tokens_per_image", "min_rekognition_confidence", "custom_prompt",
    "use_batch_inference",
}

VALID_ROUTING_MODES = {"folder_based", "metadata_routing", "ai_classification"}

# Mapping of section name → known sub-keys
_SECTION_KEYS: dict[str, set[str]] = {
    "parse": _PARSE_KEYS,
    "extract": _EXTRACT_KEYS,
    "embed": _EMBED_KEYS,
    "graph_load": _GRAPH_LOAD_KEYS,
    "store_artifact": _STORE_ARTIFACT_KEYS,
    "rekognition": _REKOGNITION_KEYS,
    "classification": _CLASSIFICATION_KEYS,
    "face_crop": _FACE_CROP_KEYS,
    "image_description": _IMAGE_DESCRIPTION_KEYS,
}


# ---------------------------------------------------------------------------
# Config Templates — preset configs for common case types
# ---------------------------------------------------------------------------

CONFIG_TEMPLATES: dict[str, dict] = {
    "antitrust": {
        "extract": {
            "entity_types": [
                "person", "organization", "financial_amount", "date",
                "event", "email", "address",
            ],
            "confidence_threshold": 0.6,
            "chunk_size_chars": 10000,
            "relationship_inference_enabled": True,
        },
        "graph_load": {
            "normalization_rules": {
                "case_folding": True,
                "alias_merging": True,
                "abbreviation_expansion": True,
            },
        },
    },
    "criminal": {
        "extract": {
            "entity_types": [
                "person", "location", "date", "event", "phone_number",
                "vehicle", "address", "organization",
            ],
            "confidence_threshold": 0.4,
            "chunk_size_chars": 6000,
        },
        "graph_load": {
            "normalization_rules": {
                "case_folding": True,
                "alias_merging": True,
            },
        },
    },
    "financial_fraud": {
        "extract": {
            "entity_types": [
                "person", "organization", "account_number", "financial_amount",
                "date", "email", "address",
            ],
            "confidence_threshold": 0.55,
            "chunk_size_chars": 8000,
            "relationship_inference_enabled": True,
        },
        "embed": {
            "search_tier": "enterprise",
        },
        "graph_load": {
            "normalization_rules": {
                "case_folding": True,
                "alias_merging": True,
                "abbreviation_expansion": True,
            },
        },
    },
}


class ConfigValidationService:
    """Validates pipeline configuration JSON documents."""

    SUPPORTED_ENTITY_TYPES: set[str] = {et.value for et in EntityType}
    VALID_LOAD_STRATEGIES = {"bulk_csv", "gremlin"}
    VALID_PDF_METHODS = {"text", "ocr", "hybrid"}
    VALID_ARTIFACT_FORMATS = {"json", "jsonl"}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(self, config_json: dict) -> list[ValidationError]:
        """Validate all fields in *config_json*.

        Returns an empty list when the config is valid.  Otherwise returns
        one ``ValidationError`` per problem found (collects all errors,
        does **not** fail-fast).
        """
        errors: list[ValidationError] = []

        errors.extend(self._check_unknown_keys(config_json))

        if "parse" in config_json:
            errors.extend(self._validate_parse(config_json["parse"]))

        if "extract" in config_json:
            errors.extend(self._validate_extract(config_json["extract"]))

        if "embed" in config_json:
            errors.extend(self._validate_embed(config_json["embed"]))

        if "graph_load" in config_json:
            errors.extend(self._validate_graph_load(config_json["graph_load"]))

        if "store_artifact" in config_json:
            errors.extend(self._validate_store_artifact(config_json["store_artifact"]))

        if "rekognition" in config_json:
            errors.extend(self._validate_rekognition(config_json["rekognition"]))

        if "classification" in config_json:
            errors.extend(self._validate_classification(config_json["classification"]))

        if "face_crop" in config_json:
            errors.extend(self._validate_face_crop(config_json["face_crop"]))

        if "image_description" in config_json:
            errors.extend(self._validate_image_description(config_json["image_description"]))

        return errors

    # ------------------------------------------------------------------
    # Per-section validators
    # ------------------------------------------------------------------

    def _validate_parse(self, section: dict) -> list[ValidationError]:
        errors: list[ValidationError] = []
        unknown = set(section.keys()) - _PARSE_KEYS
        for key in sorted(unknown):
            errors.append(ValidationError(
                field_path=f"parse.{key}",
                reason=f"Unknown key '{key}' in parse section",
            ))

        if "pdf_method" in section:
            if section["pdf_method"] not in self.VALID_PDF_METHODS:
                errors.append(ValidationError(
                    field_path="parse.pdf_method",
                    reason=f"Must be one of {sorted(self.VALID_PDF_METHODS)}",
                ))

        if "min_image_dimension" in section:
            val = section["min_image_dimension"]
            if not isinstance(val, int) or val < 1 or val > 10000:
                errors.append(ValidationError(
                    field_path="parse.min_image_dimension",
                    reason="Must be an integer between 1 and 10000",
                ))

        return errors

    def _validate_extract(self, section: dict) -> list[ValidationError]:
        errors: list[ValidationError] = []
        unknown = set(section.keys()) - _EXTRACT_KEYS
        for key in sorted(unknown):
            errors.append(ValidationError(
                field_path=f"extract.{key}",
                reason=f"Unknown key '{key}' in extract section",
            ))

        if "confidence_threshold" in section:
            val = section["confidence_threshold"]
            if not isinstance(val, (int, float)) or val < 0.0 or val > 1.0:
                errors.append(ValidationError(
                    field_path="extract.confidence_threshold",
                    reason="Must be a number between 0.0 and 1.0",
                ))

        if "chunk_size_chars" in section:
            val = section["chunk_size_chars"]
            if not isinstance(val, int) or val < 500 or val > 100000:
                errors.append(ValidationError(
                    field_path="extract.chunk_size_chars",
                    reason="Must be an integer between 500 and 100000",
                ))

        if "entity_types" in section:
            val = section["entity_types"]
            if not isinstance(val, list):
                errors.append(ValidationError(
                    field_path="extract.entity_types",
                    reason="Must be a list of strings",
                ))
            else:
                invalid = [t for t in val if t not in self.SUPPORTED_ENTITY_TYPES]
                if invalid:
                    errors.append(ValidationError(
                        field_path="extract.entity_types",
                        reason=f"Unsupported entity types: {invalid}. "
                               f"Allowed: {sorted(self.SUPPORTED_ENTITY_TYPES)}",
                    ))

        return errors

    def _validate_embed(self, section: dict) -> list[ValidationError]:
        errors: list[ValidationError] = []
        unknown = set(section.keys()) - _EMBED_KEYS
        for key in sorted(unknown):
            errors.append(ValidationError(
                field_path=f"embed.{key}",
                reason=f"Unknown key '{key}' in embed section",
            ))
        return errors

    def _validate_graph_load(self, section: dict) -> list[ValidationError]:
        errors: list[ValidationError] = []
        unknown = set(section.keys()) - _GRAPH_LOAD_KEYS
        for key in sorted(unknown):
            errors.append(ValidationError(
                field_path=f"graph_load.{key}",
                reason=f"Unknown key '{key}' in graph_load section",
            ))

        if "load_strategy" in section:
            if section["load_strategy"] not in self.VALID_LOAD_STRATEGIES:
                errors.append(ValidationError(
                    field_path="graph_load.load_strategy",
                    reason=f"Must be one of {sorted(self.VALID_LOAD_STRATEGIES)}",
                ))
        return errors

    def _validate_store_artifact(self, section: dict) -> list[ValidationError]:
        errors: list[ValidationError] = []
        unknown = set(section.keys()) - _STORE_ARTIFACT_KEYS
        for key in sorted(unknown):
            errors.append(ValidationError(
                field_path=f"store_artifact.{key}",
                reason=f"Unknown key '{key}' in store_artifact section",
            ))

        if "artifact_format" in section:
            if section["artifact_format"] not in self.VALID_ARTIFACT_FORMATS:
                errors.append(ValidationError(
                    field_path="store_artifact.artifact_format",
                    reason=f"Must be one of {sorted(self.VALID_ARTIFACT_FORMATS)}",
                ))
        return errors

    def _validate_rekognition(self, section: dict) -> list[ValidationError]:
        errors: list[ValidationError] = []
        unknown = set(section.keys()) - _REKOGNITION_KEYS
        for key in sorted(unknown):
            errors.append(ValidationError(
                field_path=f"rekognition.{key}",
                reason=f"Unknown key '{key}' in rekognition section",
            ))

        if "min_face_confidence" in section:
            val = section["min_face_confidence"]
            if not isinstance(val, (int, float)) or val < 0.0 or val > 1.0:
                errors.append(ValidationError(
                    field_path="rekognition.min_face_confidence",
                    reason="Must be a number between 0.0 and 1.0",
                ))

        if "min_object_confidence" in section:
            val = section["min_object_confidence"]
            if not isinstance(val, (int, float)) or val < 0.0 or val > 1.0:
                errors.append(ValidationError(
                    field_path="rekognition.min_object_confidence",
                    reason="Must be a number between 0.0 and 1.0",
                ))

        if "video_segment_length_seconds" in section:
            val = section["video_segment_length_seconds"]
            if not isinstance(val, (int, float)) or val <= 0:
                errors.append(ValidationError(
                    field_path="rekognition.video_segment_length_seconds",
                    reason="Must be a positive number greater than 0",
                ))

        if "video_processing_mode" in section:
            val = section["video_processing_mode"]
            valid_modes = {"skip", "faces_only", "targeted", "full"}
            if val not in valid_modes:
                errors.append(ValidationError(
                    field_path="rekognition.video_processing_mode",
                    reason=f"Must be one of {sorted(valid_modes)}, got '{val}'",
                ))

        return errors

    def _validate_classification(self, section: dict) -> list[ValidationError]:
        errors: list[ValidationError] = []
        unknown = set(section.keys()) - _CLASSIFICATION_KEYS
        for key in sorted(unknown):
            errors.append(ValidationError(
                field_path=f"classification.{key}",
                reason=f"Unknown key '{key}' in classification section",
            ))

        if "routing_mode" in section:
            if section["routing_mode"] not in VALID_ROUTING_MODES:
                errors.append(ValidationError(
                    field_path="classification.routing_mode",
                    reason=f"Must be one of {sorted(VALID_ROUTING_MODES)}",
                ))

        if "confidence_threshold" in section:
            val = section["confidence_threshold"]
            if not isinstance(val, (int, float)) or val < 0.0 or val > 1.0:
                errors.append(ValidationError(
                    field_path="classification.confidence_threshold",
                    reason="Must be a number between 0.0 and 1.0",
                ))

        if "case_number_pattern" in section:
            val = section["case_number_pattern"]
            if not isinstance(val, str):
                errors.append(ValidationError(
                    field_path="classification.case_number_pattern",
                    reason="Must be a string containing a valid regex pattern",
                ))
            else:
                try:
                    re.compile(val)
                except re.error as exc:
                    errors.append(ValidationError(
                        field_path="classification.case_number_pattern",
                        reason=f"Invalid regex pattern: {exc}",
                    ))

        if "max_preview_chars" in section:
            val = section["max_preview_chars"]
            if not isinstance(val, int) or val < 100 or val > 50000:
                errors.append(ValidationError(
                    field_path="classification.max_preview_chars",
                    reason="Must be an integer between 100 and 50000",
                ))

        if "classify_sample_size" in section:
            val = section["classify_sample_size"]
            if not isinstance(val, int) or val < 1 or val > 10000:
                errors.append(ValidationError(
                    field_path="classification.classify_sample_size",
                    reason="Must be an integer between 1 and 10000",
                ))

        return errors

    def _validate_face_crop(self, section: dict) -> list[ValidationError]:
        errors: list[ValidationError] = []
        unknown = set(section.keys()) - _FACE_CROP_KEYS
        for key in sorted(unknown):
            errors.append(ValidationError(
                field_path=f"face_crop.{key}",
                reason=f"Unknown key '{key}' in face_crop section",
            ))

        if "min_face_confidence" in section:
            val = section["min_face_confidence"]
            if not isinstance(val, (int, float)) or val < 0.0 or val > 1.0:
                errors.append(ValidationError(
                    field_path="face_crop.min_face_confidence",
                    reason="Must be a number between 0.0 and 1.0",
                ))

        if "thumbnail_size" in section:
            val = section["thumbnail_size"]
            if not isinstance(val, int) or val < 16 or val > 1024:
                errors.append(ValidationError(
                    field_path="face_crop.thumbnail_size",
                    reason="Must be an integer between 16 and 1024",
                ))

        if "thumbnail_format" in section:
            val = section["thumbnail_format"]
            valid_formats = {"jpeg", "png"}
            if val not in valid_formats:
                errors.append(ValidationError(
                    field_path="face_crop.thumbnail_format",
                    reason=f"Must be one of {sorted(valid_formats)}",
                ))

        return errors

    def _validate_image_description(self, section: dict) -> list[ValidationError]:
        errors: list[ValidationError] = []
        unknown = set(section.keys()) - _IMAGE_DESCRIPTION_KEYS
        for key in sorted(unknown):
            errors.append(ValidationError(
                field_path=f"image_description.{key}",
                reason=f"Unknown key '{key}' in image_description section",
            ))

        if "model_id" in section:
            val = section["model_id"]
            if not isinstance(val, str) or not val or not re.match(r"^anthropic\.claude-3-", val):
                errors.append(ValidationError(
                    field_path="image_description.model_id",
                    reason="Must be a non-empty string matching 'anthropic.claude-3-*' pattern",
                ))

        if "max_images_per_run" in section:
            val = section["max_images_per_run"]
            if not isinstance(val, int) or val < 1 or val > 500:
                errors.append(ValidationError(
                    field_path="image_description.max_images_per_run",
                    reason="Must be an integer between 1 and 500",
                ))

        if "max_tokens_per_image" in section:
            val = section["max_tokens_per_image"]
            if not isinstance(val, int) or val < 256 or val > 4096:
                errors.append(ValidationError(
                    field_path="image_description.max_tokens_per_image",
                    reason="Must be an integer between 256 and 4096",
                ))

        if "min_rekognition_confidence" in section:
            val = section["min_rekognition_confidence"]
            if not isinstance(val, (int, float)) or val < 0.0 or val > 1.0:
                errors.append(ValidationError(
                    field_path="image_description.min_rekognition_confidence",
                    reason="Must be a number between 0.0 and 1.0",
                ))

        return errors

    # ------------------------------------------------------------------
    # Unknown top-level key detection
    # ------------------------------------------------------------------

    def _check_unknown_keys(self, config_json: dict) -> list[ValidationError]:
        errors: list[ValidationError] = []
        unknown = set(config_json.keys()) - _VALID_SECTIONS
        for key in sorted(unknown):
            errors.append(ValidationError(
                field_path=key,
                reason=f"Unknown top-level key '{key}'. "
                       f"Allowed: {sorted(_VALID_SECTIONS)}",
            ))
        return errors

