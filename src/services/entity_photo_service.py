"""Entity Photo Service — generates base64 data URI mappings for entity face thumbnails.

Lists S3 face-crops (pipeline-generated and demo) for a case, applies priority
(pipeline > demo > omit), downloads images and returns base64 data URIs for
direct embedding in vis.js graph nodes.
"""

import base64
import logging
import os

import boto3

logger = logging.getLogger(__name__)

S3_BUCKET = os.environ.get("S3_BUCKET", "research-analyst-data-lake-974220725866")


class EntityPhotoService:
    """Generate entity name → base64 data URI mappings for face thumbnails."""

    def __init__(self, s3_bucket: str | None = None):
        self.bucket = s3_bucket or S3_BUCKET
        self.s3 = boto3.client("s3")

    def get_entity_photos(self, case_id: str, expiration: int = 3600) -> dict:
        """Return entity name → base64 data URI mapping.

        Priority: pipeline primary_thumbnail.jpg > demo photo > omit.
        Images are downloaded from S3 and returned as data:image/jpeg;base64,... URIs.
        Also returns entity_metadata with source and face_crop_count per entity.
        """
        pipeline_photos = self._list_pipeline_photos(case_id)
        demo_photos = self._list_demo_photos(case_id)

        entity_photos = {}
        source_breakdown = {"pipeline": 0, "demo": 0}
        entity_metadata = {}

        # Merge: pipeline wins over demo
        all_entities = set(list(pipeline_photos.keys()) + list(demo_photos.keys()))
        for name in all_entities:
            if name in pipeline_photos:
                s3_key = pipeline_photos[name]
                source = "pipeline"
            elif name in demo_photos:
                s3_key = demo_photos[name]
                source = "demo"
            else:
                continue

            data_uri = self._download_as_data_uri(s3_key, name)
            if data_uri:
                entity_photos[name] = data_uri
                source_breakdown[source] += 1
                face_crop_count = self._count_entity_crops(case_id, name)
                entity_metadata[name] = {
                    "source": source,
                    "face_crop_count": face_crop_count,
                }

        logger.info(
            "Entity photos for case %s: %d total (%d pipeline, %d demo)",
            case_id, len(entity_photos),
            source_breakdown["pipeline"], source_breakdown["demo"],
        )

        return {
            "entity_photos": entity_photos,
            "photo_count": len(entity_photos),
            "source_breakdown": source_breakdown,
            "entity_metadata": entity_metadata,
        }

    def _list_pipeline_photos(self, case_id: str) -> dict[str, str]:
        """List pipeline-generated primary thumbnails.

        Looks for: cases/{case_id}/face-crops/{entity_name}/primary_thumbnail.jpg
        """
        prefix = f"cases/{case_id}/face-crops/"
        photos = {}
        try:
            paginator = self.s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    # Match pattern: .../face-crops/{name}/primary_thumbnail.jpg
                    rel = key[len(prefix):]
                    parts = rel.split("/")
                    if (
                        len(parts) == 2
                        and parts[1] == "primary_thumbnail.jpg"
                        and parts[0] != "demo"
                    ):
                        entity_name = parts[0]
                        photos[entity_name] = key
        except Exception as e:
            logger.warning("Failed to list pipeline photos for case %s: %s", case_id, e)
        return photos

    def _list_demo_photos(self, case_id: str) -> dict[str, str]:
        """List demo photos uploaded by setup_demo_photos.py.

        Looks for: cases/{case_id}/face-crops/demo/{person_name}.jpg
        """
        prefix = f"cases/{case_id}/face-crops/demo/"
        photos = {}
        try:
            paginator = self.s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    rel = key[len(prefix):]
                    if rel.endswith(".jpg"):
                        entity_name = rel[:-4]  # strip .jpg
                        photos[entity_name] = key
        except Exception as e:
            logger.warning("Failed to list demo photos for case %s: %s", case_id, e)
        return photos

    def _count_entity_crops(self, case_id: str, entity_name: str) -> int:
        """Count individual face crop files for an entity, excluding primary_thumbnail.jpg."""
        prefix = f"cases/{case_id}/face-crops/{entity_name}/"
        count = 0
        try:
            paginator = self.s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    filename = key[len(prefix):]
                    if filename and filename != "primary_thumbnail.jpg":
                        count += 1
        except Exception as e:
            logger.warning("Failed to count crops for entity %s: %s", entity_name, e)
        return count

    def _download_as_data_uri(self, s3_key: str, entity_name: str) -> str | None:
        """Download image from S3 and return as base64 data URI."""
        try:
            resp = self.s3.get_object(Bucket=self.bucket, Key=s3_key)
            image_bytes = resp["Body"].read()
            b64 = base64.b64encode(image_bytes).decode("ascii")
            data_uri = f"data:image/jpeg;base64,{b64}"
            logger.info(
                "Photo loaded: entity=%s, key=%s, size=%d bytes",
                entity_name, s3_key, len(image_bytes),
            )
            return data_uri
        except Exception as e:
            logger.warning(
                "Failed to download photo: entity=%s, key=%s, error=%s",
                entity_name, s3_key, e,
            )
            return None
