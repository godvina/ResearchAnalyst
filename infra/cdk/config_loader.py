"""Deployment configuration loader and validator."""
import json
import os
from typing import Any


class ConfigValidationError(Exception):
    """Raised when deployment config validation fails."""
    def __init__(self, errors: list):
        self.errors = errors
        super().__init__("Config validation failed:\n" + "\n".join(f"  - {e}" for e in errors))


class ConfigLoader:
    """Load and validate a deployment configuration file."""

    REQUIRED_TOP_LEVEL = ["environment_name", "account", "region", "partition", "vpc", "aurora", "neptune", "opensearch", "encryption", "bedrock", "features", "logging"]
    VALID_PARTITIONS = {"aws", "aws-us-gov"}
    VALID_SUBNET_TYPES = {"PUBLIC", "PRIVATE_WITH_EGRESS"}
    VALID_OPENSEARCH_MODES = {"serverless", "disabled"}

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = {}

    def load(self) -> dict:
        """Read JSON, resolve env var placeholders, validate, return config dict."""
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)
        self._resolve_env_vars(self.config)
        self._validate(self.config)
        return self.config

    def _resolve_env_vars(self, config: dict) -> None:
        """Replace CDK_DEFAULT_ACCOUNT and CDK_DEFAULT_REGION placeholders."""
        if config.get("account") == "CDK_DEFAULT_ACCOUNT":
            val = os.environ.get("CDK_DEFAULT_ACCOUNT", "")
            if not val:
                raise ConfigValidationError(["CDK_DEFAULT_ACCOUNT environment variable is not set"])
            config["account"] = val
        if config.get("region") == "CDK_DEFAULT_REGION":
            val = os.environ.get("CDK_DEFAULT_REGION", "")
            if not val:
                raise ConfigValidationError(["CDK_DEFAULT_REGION environment variable is not set"])
            config["region"] = val

    def _validate(self, config: dict) -> None:
        """Validate required fields, types, cross-field constraints."""
        errors = []

        # Top-level required fields
        for field in self.REQUIRED_TOP_LEVEL:
            if field not in config:
                errors.append(f"Missing required field: {field}")

        if errors:
            raise ConfigValidationError(errors)

        # Type checks
        if not isinstance(config.get("environment_name"), str):
            errors.append("environment_name must be a string")
        if not isinstance(config.get("account"), str):
            errors.append("account must be a string")
        if not isinstance(config.get("region"), str):
            errors.append("region must be a string")

        # Partition
        partition = config.get("partition", "")
        if partition not in self.VALID_PARTITIONS:
            errors.append(f"partition must be one of {self.VALID_PARTITIONS}, got '{partition}'")

        # VPC
        vpc = config.get("vpc", {})
        if not isinstance(vpc, dict):
            errors.append("vpc must be an object")
        else:
            if "create_new" not in vpc:
                errors.append("Missing required field: vpc.create_new")
            elif vpc["create_new"] is True:
                if not vpc.get("cidr"):
                    errors.append("vpc.cidr is required when vpc.create_new is true")
            elif vpc["create_new"] is False:
                if not vpc.get("existing_vpc_id"):
                    errors.append("vpc.existing_vpc_id is required when vpc.create_new is false")

        # Aurora
        aurora = config.get("aurora", {})
        if not isinstance(aurora, dict):
            errors.append("aurora must be an object")
        else:
            for f in ("min_capacity", "max_capacity", "subnet_type"):
                if f not in aurora:
                    errors.append(f"Missing required field: aurora.{f}")
            if aurora.get("subnet_type") and aurora["subnet_type"] not in self.VALID_SUBNET_TYPES:
                errors.append(f"aurora.subnet_type must be one of {self.VALID_SUBNET_TYPES}")

        # Neptune
        neptune = config.get("neptune", {})
        if not isinstance(neptune, dict):
            errors.append("neptune must be an object")
        else:
            if "enabled" not in neptune:
                errors.append("Missing required field: neptune.enabled")
            elif neptune["enabled"] is True:
                for f in ("min_capacity", "max_capacity", "subnet_type"):
                    if f not in neptune:
                        errors.append(f"neptune.{f} is required when neptune.enabled is true")
                if neptune.get("subnet_type") and neptune["subnet_type"] not in self.VALID_SUBNET_TYPES:
                    errors.append(f"neptune.subnet_type must be one of {self.VALID_SUBNET_TYPES}")

        # OpenSearch
        opensearch = config.get("opensearch", {})
        if not isinstance(opensearch, dict):
            errors.append("opensearch must be an object")
        else:
            mode = opensearch.get("mode", "")
            if mode not in self.VALID_OPENSEARCH_MODES:
                errors.append(f"opensearch.mode must be one of {self.VALID_OPENSEARCH_MODES}")

        # Encryption
        encryption = config.get("encryption", {})
        if not isinstance(encryption, dict):
            errors.append("encryption must be an object")
        else:
            if "enforce_tls" not in encryption:
                errors.append("Missing required field: encryption.enforce_tls")

        # Bedrock
        bedrock = config.get("bedrock", {})
        if not isinstance(bedrock, dict):
            errors.append("bedrock must be an object")
        else:
            for f in ("llm_model_id", "embedding_model_id"):
                if f not in bedrock:
                    errors.append(f"Missing required field: bedrock.{f}")

        # Features
        features = config.get("features", {})
        if not isinstance(features, dict):
            errors.append("features must be an object")
        else:
            for f in ("pipeline_only", "rekognition"):
                if f not in features:
                    errors.append(f"Missing required field: features.{f}")

        # Logging
        logging_cfg = config.get("logging", {})
        if not isinstance(logging_cfg, dict):
            errors.append("logging must be an object")
        else:
            if "vpc_flow_logs" not in logging_cfg:
                errors.append("Missing required field: logging.vpc_flow_logs")

        if errors:
            raise ConfigValidationError(errors)

        # Cross-field: Bedrock excluded providers
        self._validate_bedrock_models(config)

    def _validate_bedrock_models(self, config: dict) -> None:
        """Check that configured model IDs are not from excluded providers."""
        bedrock = config.get("bedrock", {})
        excluded = bedrock.get("excluded_providers", [])
        if not excluded:
            pass  # Still need to check GovCloud FedRAMP below

        errors = []
        for field in ("llm_model_id", "embedding_model_id"):
            model_id = bedrock.get(field, "")
            for provider in excluded:
                if model_id.lower().startswith(provider.lower()):
                    errors.append(f"Model {model_id} (bedrock.{field}) belongs to excluded provider '{provider}'")

        # GovCloud FedRAMP check
        if config.get("partition") == "aws-us-gov":
            registry_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "bedrock_models.json")
            if os.path.exists(registry_path):
                with open(registry_path, "r") as f:
                    registry = json.load(f)
                fedramp_high_models = []

                # Check for explicit govcloud_fedramp_high key
                govcloud_list = registry.get("govcloud_fedramp_high", [])
                if govcloud_list:
                    for entry in govcloud_list:
                        if isinstance(entry, dict):
                            fedramp_high_models.append(entry.get("model_id", ""))
                        elif isinstance(entry, str):
                            fedramp_high_models.append(entry)

                # Fall back to models list filtered by fedramp_levels
                if not fedramp_high_models:
                    models_list = registry.get("models", [])
                    if isinstance(models_list, list):
                        for entry in models_list:
                            if isinstance(entry, dict):
                                levels = entry.get("fedramp_levels", [])
                                if "fedramp_high" in levels:
                                    fedramp_high_models.append(entry.get("model_id", ""))

                if fedramp_high_models:
                    for field in ("llm_model_id", "embedding_model_id"):
                        model_id = bedrock.get(field, "")
                        if model_id and model_id not in fedramp_high_models:
                            # Check prefix match (e.g., "anthropic.claude-3-haiku" matches "anthropic.claude-3-haiku-20240307-v1:0")
                            prefix_match = any(model_id.startswith(m.split(":")[0]) or m.startswith(model_id.split(":")[0]) for m in fedramp_high_models)
                            if not prefix_match:
                                errors.append(f"Model {model_id} (bedrock.{field}) is not in the FedRAMP High approved list for GovCloud")

        if errors:
            raise ConfigValidationError(errors)
