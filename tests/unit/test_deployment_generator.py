"""Unit tests for DeploymentGenerator service.

Requirements: 22.1, 22.2, 22.3, 22.4, 22.5, 22.7, 22.10
"""

import json
import pytest
from unittest.mock import patch

from services.deployment_generator import DeploymentGenerator


@pytest.fixture
def generator():
    return DeploymentGenerator()


@pytest.fixture
def sample_answers():
    return {
        "investigation_type": "financial_fraud",
        "document_count": 50000,
        "total_volume_tb": 2,
        "concurrent_users": 25,
        "aws_region": "us-east-1",
        "image_count": 500,
        "video_hours": 10,
        "scanned_percentage": 30,
    }


@pytest.fixture
def sample_config():
    return {
        "parse": {"pdf_method": "hybrid", "ocr_enabled": True},
        "extract": {
            "llm_model_id": "anthropic.claude-3-sonnet-20240229-v1:0",
            "entity_types": ["person", "organization", "financial_amount"],
            "confidence_threshold": 0.5,
        },
        "embed": {"search_tier": "standard"},
        "graph_load": {"load_strategy": "bulk_csv", "batch_size": 500},
        "rekognition": {"enabled": True},
    }


@pytest.fixture
def sample_cost():
    return {
        "one_time": {"total": 1250.00, "textract": 200, "bedrock_extraction": 800},
        "monthly": {"total": 650.00, "opensearch": 350, "neptune": 160},
        "optimizations": ["Use Haiku to save $500"],
    }


class TestGenerateBundle:
    """Tests for the generate_bundle orchestrator."""

    def test_returns_all_required_keys(self, generator, sample_answers, sample_config, sample_cost):
        result = generator.generate_bundle(sample_answers, sample_config, sample_cost)
        assert "cfn_template" in result
        assert "deployment_guide" in result
        assert "pipeline_config" in result
        assert "cost_estimate" in result
        assert "bundle_contents" in result

    def test_bundle_contents_list(self, generator, sample_answers, sample_config, sample_cost):
        result = generator.generate_bundle(sample_answers, sample_config, sample_cost)
        expected_files = [
            "template.yaml",
            "lambda-code.zip",
            "DEPLOYMENT_GUIDE.md",
            "pipeline-config.json",
            "cost-estimate.json",
        ]
        assert result["bundle_contents"] == expected_files

    def test_pipeline_config_is_valid_json(self, generator, sample_answers, sample_config, sample_cost):
        result = generator.generate_bundle(sample_answers, sample_config, sample_cost)
        parsed = json.loads(result["pipeline_config"])
        assert parsed == sample_config

    def test_cost_estimate_is_valid_json(self, generator, sample_answers, sample_config, sample_cost):
        result = generator.generate_bundle(sample_answers, sample_config, sample_cost)
        parsed = json.loads(result["cost_estimate"])
        assert parsed == sample_cost


class TestRenderCfnTemplate:
    """Tests for CloudFormation template rendering."""

    def test_template_contains_parameters(self, generator, sample_answers, sample_config):
        template = generator._render_cfn_template(sample_answers, sample_config)
        assert "EnvironmentName" in template
        assert "AdminEmail" in template
        assert "VpcCidr" in template
        assert "DeploymentBucketName" in template
        assert "LambdaCodeKey" in template

    def test_template_contains_outputs(self, generator, sample_answers, sample_config):
        template = generator._render_cfn_template(sample_answers, sample_config)
        assert "InvestigatorURL" in template
        assert "ApiGatewayURL" in template
        assert "S3DataBucket" in template
        assert "AuroraEndpoint" in template
        assert "NeptuneEndpoint" in template

    def test_template_substitutes_acu_sizing(self, generator, sample_answers, sample_config):
        template = generator._render_cfn_template(sample_answers, sample_config)
        # 50K docs → min 0.5, max 4.0 ACU
        assert "0.5" in template
        assert "{{MIN_ACU}}" not in template
        assert "{{MAX_ACU}}" not in template

    def test_template_substitutes_ncu_sizing(self, generator, sample_answers, sample_config):
        template = generator._render_cfn_template(sample_answers, sample_config)
        assert "{{MIN_NCU}}" not in template
        assert "{{MAX_NCU}}" not in template

    def test_template_no_unresolved_placeholders(self, generator, sample_answers, sample_config):
        template = generator._render_cfn_template(sample_answers, sample_config)
        # No double-brace placeholders should remain
        assert "{{" not in template
        assert "}}" not in template

    def test_large_volume_increases_sizing(self, generator, sample_config):
        large_answers = {
            "document_count": 2_000_000,
            "total_volume_tb": 100,
            "concurrent_users": 200,
            "aws_region": "us-east-1",
        }
        template = generator._render_cfn_template(large_answers, sample_config)
        # 2M docs → min 2.0 NCU, max 16.0 NCU
        assert "MinCapacity: 2.0" in template  # NCU
        assert "MaxCapacity: 16.0" in template  # ACU or NCU

    def test_govcloud_uses_correct_partition(self, generator, sample_config):
        gov_answers = {"aws_region": "us-gov-west-1", "document_count": 1000}
        template = generator._render_cfn_template(gov_answers, sample_config)
        assert "aws-us-gov" in template

    def test_commercial_uses_aws_partition(self, generator, sample_answers, sample_config):
        template = generator._render_cfn_template(sample_answers, sample_config)
        # Should use 'aws' partition, not 'aws-us-gov'
        assert "arn:aws:" in template


class TestGenerateDeploymentGuide:
    """Tests for deployment guide generation."""

    def test_guide_contains_steps(self, generator, sample_answers, sample_cost):
        guide = generator._generate_deployment_guide(sample_answers, sample_cost)
        assert "Step 1" in guide
        assert "Step 2" in guide
        assert "Step 3" in guide
        assert "Step 4" in guide

    def test_guide_contains_cost_info(self, generator, sample_answers, sample_cost):
        guide = generator._generate_deployment_guide(sample_answers, sample_cost)
        assert "$1,250.00" in guide
        assert "$650.00" in guide

    def test_guide_contains_region(self, generator, sample_answers, sample_cost):
        guide = generator._generate_deployment_guide(sample_answers, sample_cost)
        assert "us-east-1" in guide

    def test_guide_contains_investigation_type(self, generator, sample_answers, sample_cost):
        guide = generator._generate_deployment_guide(sample_answers, sample_cost)
        assert "financial_fraud" in guide

    def test_govcloud_guide_uses_gov_console(self, generator, sample_cost):
        gov_answers = {
            "aws_region": "us-gov-west-1",
            "investigation_type": "criminal",
            "document_count": 1000,
            "total_volume_tb": 1,
        }
        guide = generator._generate_deployment_guide(gov_answers, sample_cost)
        assert "console.amazonaws-us-gov.com" in guide
        assert "GovCloud" in guide

    def test_guide_is_valid_markdown(self, generator, sample_answers, sample_cost):
        guide = generator._generate_deployment_guide(sample_answers, sample_cost)
        assert guide.startswith("# Deployment Guide")
        assert "```bash" in guide


class TestPackageLambdaCode:
    """Tests for Lambda code packaging."""

    def test_package_returns_bytes(self, generator):
        result = generator._package_lambda_code()
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_package_is_valid_zip(self, generator):
        import io
        import zipfile
        result = generator._package_lambda_code()
        buf = io.BytesIO(result)
        assert zipfile.is_zipfile(buf)

    def test_package_contains_python_files(self, generator):
        import io
        import zipfile
        result = generator._package_lambda_code()
        buf = io.BytesIO(result)
        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
            py_files = [n for n in names if n.endswith(".py")]
            assert len(py_files) > 0
