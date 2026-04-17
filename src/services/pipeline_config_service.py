"""Pipeline Config Service — CRUD operations on pipeline configs with versioning.

Handles create/update, version listing, rollback, export/import, and
template application for per-case pipeline configurations.
"""

import json
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from db.connection import ConnectionManager
from models.pipeline_config import ConfigVersion, PipelineConfig
from services.config_validation_service import CONFIG_TEMPLATES, ConfigValidationService
from services.config_resolution_service import ConfigResolutionService


class PipelineConfigService:
    """CRUD operations on pipeline configs with versioning."""

    def __init__(
        self,
        aurora_cm: ConnectionManager,
        validator: ConfigValidationService,
        resolution: ConfigResolutionService,
    ) -> None:
        self.aurora_cm = aurora_cm
        self.validator = validator
        self.resolution = resolution

    def create_or_update_config(
        self, case_id: str, config_json: dict, created_by: str
    ) -> ConfigVersion:
        """Validate, deactivate previous active version, insert new version.

        Returns the newly created ConfigVersion.
        Raises ValueError if validation fails.
        """
        errors = self.validator.validate(config_json)
        if errors:
            raise ValueError(
                f"Config validation failed: "
                f"{[{'field': e.field_path, 'reason': e.reason} for e in errors]}"
            )

        with self.aurora_cm.cursor() as cur:
            # Get current max version for this case
            cur.execute(
                "SELECT COALESCE(MAX(version), 0) FROM pipeline_configs WHERE case_id = %s",
                (case_id,),
            )
            max_version = cur.fetchone()[0]
            new_version = max_version + 1

            # Deactivate previous active version
            cur.execute(
                "UPDATE pipeline_configs SET is_active = FALSE WHERE case_id = %s AND is_active = TRUE",
                (case_id,),
            )

            # Insert new version
            cur.execute(
                """
                INSERT INTO pipeline_configs (case_id, version, config_json, created_by, is_active)
                VALUES (%s, %s, %s, %s, TRUE)
                RETURNING config_id, created_at
                """,
                (case_id, new_version, json.dumps(config_json), created_by),
            )
            row = cur.fetchone()

        return ConfigVersion(
            config_id=row[0] if isinstance(row[0], UUID) else UUID(str(row[0])),
            case_id=UUID(case_id) if isinstance(case_id, str) else case_id,
            version=new_version,
            config_json=config_json,
            created_at=row[1],
            created_by=created_by,
        )

    def get_active_config(self, case_id: str) -> Optional[PipelineConfig]:
        """Return the active PipelineConfig for a case, or None."""
        with self.aurora_cm.cursor() as cur:
            cur.execute(
                """
                SELECT config_id, case_id, version, config_json, created_at, created_by, is_active
                FROM pipeline_configs
                WHERE case_id = %s AND is_active = TRUE
                """,
                (case_id,),
            )
            row = cur.fetchone()

        if row is None:
            return None

        config_json = row[3] if isinstance(row[3], dict) else json.loads(row[3])
        return PipelineConfig(
            config_id=row[0] if isinstance(row[0], UUID) else UUID(str(row[0])),
            case_id=row[1] if isinstance(row[1], UUID) else UUID(str(row[1])),
            version=row[2],
            config_json=config_json,
            created_at=row[4],
            created_by=row[5],
            is_active=row[6],
        )

    def list_versions(self, case_id: str) -> list[ConfigVersion]:
        """List all config versions for a case, ordered by version desc."""
        with self.aurora_cm.cursor() as cur:
            cur.execute(
                """
                SELECT config_id, case_id, version, config_json, created_at, created_by
                FROM pipeline_configs
                WHERE case_id = %s
                ORDER BY version DESC
                """,
                (case_id,),
            )
            rows = cur.fetchall()

        versions: list[ConfigVersion] = []
        for row in rows:
            config_json = row[3] if isinstance(row[3], dict) else json.loads(row[3])
            versions.append(ConfigVersion(
                config_id=row[0] if isinstance(row[0], UUID) else UUID(str(row[0])),
                case_id=row[1] if isinstance(row[1], UUID) else UUID(str(row[1])),
                version=row[2],
                config_json=config_json,
                created_at=row[4],
                created_by=row[5],
            ))
        return versions

    def get_version(self, case_id: str, version: int) -> ConfigVersion:
        """Return a specific config version. Raises ValueError if not found."""
        with self.aurora_cm.cursor() as cur:
            cur.execute(
                """
                SELECT config_id, case_id, version, config_json, created_at, created_by
                FROM pipeline_configs
                WHERE case_id = %s AND version = %s
                """,
                (case_id, version),
            )
            row = cur.fetchone()

        if row is None:
            raise ValueError(f"Config version {version} not found for case {case_id}")

        config_json = row[3] if isinstance(row[3], dict) else json.loads(row[3])
        return ConfigVersion(
            config_id=row[0] if isinstance(row[0], UUID) else UUID(str(row[0])),
            case_id=row[1] if isinstance(row[1], UUID) else UUID(str(row[1])),
            version=row[2],
            config_json=config_json,
            created_at=row[4],
            created_by=row[5],
        )

    def rollback_to_version(
        self, case_id: str, target_version: int, created_by: str
    ) -> ConfigVersion:
        """Create a new version with the content of target_version."""
        target = self.get_version(case_id, target_version)
        return self.create_or_update_config(case_id, target.config_json, created_by)

    def export_config(self, case_id: str) -> dict:
        """Export active config with metadata header.

        Returns a dict with 'metadata' and 'config_json' keys.
        Raises ValueError if no active config exists.
        """
        active = self.get_active_config(case_id)
        if active is None:
            raise ValueError(f"No active config found for case {case_id}")

        return {
            "metadata": {
                "source_case_id": str(active.case_id),
                "config_version": active.version,
                "exported_at": datetime.now(timezone.utc).isoformat(),
            },
            "config_json": active.config_json,
        }

    def import_config(
        self, case_id: str, export_doc: dict, created_by: str
    ) -> ConfigVersion:
        """Validate and import an exported config, creating a new version.

        Expects export_doc to have a 'config_json' key.
        Raises ValueError if validation fails or config_json is missing.
        """
        config_json = export_doc.get("config_json")
        if config_json is None:
            raise ValueError("Export document must contain a 'config_json' key")

        return self.create_or_update_config(case_id, config_json, created_by)

    def apply_template(
        self, case_id: str, template_name: str, created_by: str
    ) -> ConfigVersion:
        """Apply a named Config_Template as the case's PipelineConfig.

        Raises ValueError if template_name is not found.
        """
        template = CONFIG_TEMPLATES.get(template_name)
        if template is None:
            raise ValueError(
                f"Unknown template '{template_name}'. "
                f"Available: {sorted(CONFIG_TEMPLATES.keys())}"
            )

        return self.create_or_update_config(case_id, template, created_by)

