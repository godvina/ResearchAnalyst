"""IoV Taxonomy Service — loads and flattens Indicators of Violation hierarchies from S3.

Reads per-case-type taxonomy JSON from S3, validates structure, and
produces flat indicator lists with depth-based weights for scoring.
No caching — fresh load on each request. No bulk processing, no Bedrock, no EC2.
"""

import json
import logging
from typing import Any

from models.signal_mining import FlatIndicator, IovConfigError, IovHierarchy

logger = logging.getLogger(__name__)

# Weight mapping by hierarchy depth
_DEPTH_WEIGHTS: dict[int, float] = {
    0: 1.0,
    1: 0.7,
    2: 0.5,
}


class IovTaxonomyService:
    """Loads IoV taxonomy hierarchies from S3 and flattens them for scoring.

    Uses constructor-injection for testability — accepts an S3 client
    and bucket name, no global state.
    """

    def __init__(self, s3_client: Any, s3_bucket: str) -> None:
        """Initialize with S3 dependencies.

        Args:
            s3_client: boto3 S3 client for reading taxonomy JSON files.
            s3_bucket: S3 bucket name containing taxonomy configs.
        """
        self._s3 = s3_client
        self._bucket = s3_bucket

    def load_taxonomy(self, case_type: str) -> IovHierarchy:
        """Load an IoV taxonomy hierarchy from S3 for the given case type.

        Reads from s3://{bucket}/config/iov_taxonomies/{case_type}.json,
        validates the structure, and returns a parsed IovHierarchy.

        Args:
            case_type: The antitrust case type (e.g. "monopolization").

        Returns:
            Parsed IovHierarchy dataclass.

        Raises:
            IovConfigError: If the file is missing, unreadable, or malformed.
        """
        s3_key = f"config/iov_taxonomies/{case_type}.json"
        logger.info("Loading IoV taxonomy from s3://%s/%s", self._bucket, s3_key)

        try:
            response = self._s3.get_object(Bucket=self._bucket, Key=s3_key)
            body = response["Body"].read().decode("utf-8")
        except self._s3.exceptions.NoSuchKey:
            raise IovConfigError(
                case_type, f"Taxonomy file not found: s3://{self._bucket}/{s3_key}"
            )
        except Exception as e:
            raise IovConfigError(
                case_type, f"Failed to read taxonomy from S3: {e}"
            )

        try:
            hierarchy_data = json.loads(body)
        except json.JSONDecodeError as e:
            raise IovConfigError(
                case_type, f"Malformed JSON in taxonomy file: {e}"
            )

        is_valid, error_message = self.validate_hierarchy(hierarchy_data)
        if not is_valid:
            raise IovConfigError(case_type, error_message)

        return IovHierarchy(
            case_type=hierarchy_data["case_type"],
            version=hierarchy_data["version"],
            categories=hierarchy_data["categories"],
        )

    def flatten_indicators(self, hierarchy: IovHierarchy) -> list[FlatIndicator]:
        """Recursively walk the hierarchy and produce a flat list of indicators.

        Each indicator gets a category_path (list of ancestor category names),
        a depth (0 for top-level, 1 for sub_category, 2 for sub_sub_category),
        and a weight based on depth (1.0, 0.7, 0.5).

        Args:
            hierarchy: Parsed IovHierarchy to flatten.

        Returns:
            List of FlatIndicator dataclasses with correct paths and weights.
        """
        flat: list[FlatIndicator] = []

        for category in hierarchy.categories:
            category_name = category["name"]
            self._walk_category(category, [category_name], 0, flat)

        logger.debug(
            "Flattened %d indicators from %d categories for case_type=%s",
            len(flat),
            len(hierarchy.categories),
            hierarchy.case_type,
        )
        return flat

    def validate_hierarchy(self, hierarchy_data: dict) -> tuple[bool, str]:
        """Validate the structure of a raw hierarchy dict.

        Checks:
        - case_type field is present and non-empty
        - version field is present and non-empty
        - At least one category exists
        - Each category has a name and at least one indicator

        Args:
            hierarchy_data: Raw dict parsed from the taxonomy JSON.

        Returns:
            Tuple of (is_valid, error_message). error_message is empty on success.
        """
        if not hierarchy_data.get("case_type"):
            return False, "Missing or empty 'case_type' field"

        if not hierarchy_data.get("version"):
            return False, "Missing or empty 'version' field"

        categories = hierarchy_data.get("categories")
        if not categories or not isinstance(categories, list):
            return False, "Must have at least one category"

        for i, category in enumerate(categories):
            if not category.get("name"):
                return False, f"Category at index {i} is missing 'name'"

            indicators = category.get("indicators")
            if not indicators or not isinstance(indicators, list):
                return (
                    False,
                    f"Category '{category.get('name', i)}' must have at least one indicator",
                )

        return True, ""

    def _walk_category(
        self,
        category: dict,
        path: list[str],
        depth: int,
        flat: list[FlatIndicator],
    ) -> None:
        """Recursively walk a category node and collect indicators.

        Args:
            category: Category dict with 'name', 'indicators', optional 'sub_categories'.
            path: Current category path from root.
            depth: Current depth (0 = top-level).
            flat: Accumulator list to append FlatIndicator instances to.
        """
        weight = _DEPTH_WEIGHTS.get(depth, 0.5)

        for indicator_text in category.get("indicators", []):
            flat.append(FlatIndicator(
                indicator_text=indicator_text,
                category_path=list(path),
                depth=depth,
                weight=weight,
            ))

        for sub_category in category.get("sub_categories", []):
            sub_name = sub_category.get("name", "Unknown")
            self._walk_category(
                sub_category,
                path + [sub_name],
                depth + 1,
                flat,
            )
