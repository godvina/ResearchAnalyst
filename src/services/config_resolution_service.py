"""Config Resolution Service — computes Effective_Config by deep-merging
system defaults with per-case overrides.

Responsible for:
- Fetching the active system default config from Aurora
- Fetching the active case-level pipeline config override from Aurora
- Deep-merging system defaults with case overrides (override wins at leaf level)
- Annotating each leaf key with its origin ("system_default" or "case_override")
"""

import json
from typing import Optional
from uuid import UUID

from db.connection import ConnectionManager
from models.pipeline_config import EffectiveConfig


class ConfigResolutionService:
    """Resolves the effective pipeline configuration for a case."""

    def __init__(self, aurora_cm: ConnectionManager) -> None:
        self.aurora_cm = aurora_cm

    def resolve_effective_config(self, case_id: str) -> EffectiveConfig:
        """Single Aurora query: deep merge system default + case override.

        Returns EffectiveConfig with origin annotations (inherited vs overridden).
        """
        with self.aurora_cm.cursor() as cur:
            cur.execute(
                """
                SELECT sd.config_json AS system_default,
                       pc.config_json AS case_override,
                       pc.version     AS config_version
                FROM system_default_config sd
                LEFT JOIN pipeline_configs pc
                       ON pc.case_id = %s AND pc.is_active = TRUE
                WHERE sd.is_active = TRUE
                """,
                (case_id,),
            )
            row = cur.fetchone()

        if row is None:
            raise RuntimeError("No active system default config found")

        system_default = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        case_override = None
        config_version = None

        if row[1] is not None:
            case_override = row[1] if isinstance(row[1], dict) else json.loads(row[1])
            config_version = row[2]

        if case_override:
            effective_json = self.deep_merge(system_default, case_override)
        else:
            effective_json = dict(system_default)

        origins = self._compute_origins(system_default, case_override or {})

        return EffectiveConfig(
            case_id=UUID(case_id) if isinstance(case_id, str) else case_id,
            config_version=config_version,
            effective_json=effective_json,
            origins=origins,
        )

    def get_system_default(self) -> dict:
        """Return the active system default config_json."""
        with self.aurora_cm.cursor() as cur:
            cur.execute(
                "SELECT config_json FROM system_default_config WHERE is_active = TRUE"
            )
            row = cur.fetchone()

        if row is None:
            raise RuntimeError("No active system default config found")

        return row[0] if isinstance(row[0], dict) else json.loads(row[0])

    def get_case_override(self, case_id: str) -> Optional[dict]:
        """Return the active case-level Pipeline_Config config_json, or None."""
        with self.aurora_cm.cursor() as cur:
            cur.execute(
                "SELECT config_json FROM pipeline_configs WHERE case_id = %s AND is_active = TRUE",
                (case_id,),
            )
            row = cur.fetchone()

        if row is None:
            return None

        return row[0] if isinstance(row[0], dict) else json.loads(row[0])

    @staticmethod
    def deep_merge(base: dict, override: dict) -> dict:
        """Recursive deep merge. Override values replace base at leaf level.

        Rules:
        - For each key in override, if both base[key] and override[key] are dicts, recurse.
        - Otherwise, override[key] replaces base[key].
        - Keys in base not present in override are preserved.
        - Lists are replaced wholesale (not appended).
        """
        result = dict(base)
        for key, override_val in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(override_val, dict)
            ):
                result[key] = ConfigResolutionService.deep_merge(result[key], override_val)
            else:
                result[key] = override_val
        return result

    @staticmethod
    def _compute_origins(
        system_default: dict, case_override: dict, prefix: str = ""
    ) -> dict:
        """Build a flat dict mapping each leaf key path to its origin.

        Origin is "case_override" if the leaf value came from the case override,
        otherwise "system_default".
        """
        origins: dict[str, str] = {}
        all_keys = set(system_default.keys()) | set(case_override.keys())

        for key in all_keys:
            path = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
            sd_val = system_default.get(key)
            co_val = case_override.get(key)

            if isinstance(sd_val, dict) and isinstance(co_val, dict):
                # Both are dicts — recurse
                origins.update(
                    ConfigResolutionService._compute_origins(sd_val, co_val, path)
                )
            elif isinstance(sd_val, dict) and co_val is None:
                # Only in system default and it's a dict — recurse with no override
                origins.update(
                    ConfigResolutionService._compute_origins(sd_val, {}, path)
                )
            elif key in case_override:
                # Leaf present in override — mark as case_override
                if isinstance(co_val, dict):
                    # Override introduces a new dict not in base — mark all leaves
                    origins.update(
                        ConfigResolutionService._compute_origins({}, co_val, path)
                    )
                else:
                    origins[path] = "case_override"
            else:
                # Leaf only in system default
                origins[path] = "system_default"

        return origins

