"""Face Crop Service — crops face bounding box regions from source images.

Downloads source images from S3, crops face regions using Rekognition bounding
box coordinates, resizes to 100×100 JPEG thumbnails, and uploads to
``cases/{case_id}/face-crops/{entity_name}/{hash}.jpg``. Selects the highest-
confidence crop per entity as ``primary_thumbnail.jpg``.
"""

import hashlib
import io
import logging
import os
from collections import defaultdict

import boto3
from PIL import Image

logger = logging.getLogger(__name__)

# Feature flag: when "false", face cropping is skipped
_REKOGNITION_ENABLED = os.environ.get("REKOGNITION_ENABLED", "true") == "true"

# Minimum Rekognition confidence (normalised 0–1) to process a face crop
MIN_FACE_CONFIDENCE = 0.90


class FaceCropService:
    """Crops face bounding box regions from source images."""

    def __init__(self, s3_bucket: str):
        self.s3_bucket = s3_bucket
        self.s3 = boto3.client("s3")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def crop_faces(self, case_id: str, rekognition_results: list[dict]) -> dict:
        """Process all face detections from Rekognition output.

        For each face with confidence >= 0.90:
        1. Download source image from S3
        2. Crop bounding box region
        3. Resize to 100×100 JPEG
        4. Upload to cases/{case_id}/face-crops/{entity_name}/{hash}.jpg
        5. Select highest-confidence crop per entity as primary_thumbnail.jpg

        Args:
            case_id: The case file identifier.
            rekognition_results: List of per-image Rekognition result dicts,
                each containing ``s3_key``, ``faces`` (list of face dicts with
                ``confidence`` and ``bounding_box``), and optionally
                ``watchlist_matches`` (list with ``external_image_id``).

        Returns:
            Dict with ``crops_created``, ``crops_from_extracted_images``,
            ``entities_with_thumbnails``, ``primary_thumbnails``, and ``errors``.
        """
        if not _REKOGNITION_ENABLED:
            return {
                "crops_created": 0,
                "crops_from_extracted_images": 0,
                "entities_with_thumbnails": [],
                "primary_thumbnails": {},
                "errors": [],
                "labels": [],
                "faces": [],
                "source": "disabled",
            }

        crops_created = 0
        crops_from_extracted = 0
        errors: list[str] = []
        # entity_name -> list of (confidence, s3_crop_key)
        entity_crops: dict[str, list[tuple[float, str]]] = defaultdict(list)

        # Build a mapping of s3_key -> list of entity names from watchlist matches
        # so we can associate face crops with named entities.
        key_entity_map: dict[str, list[str]] = defaultdict(list)
        for result in rekognition_results:
            s3_key = result.get("s3_key", "")
            for match in result.get("watchlist_matches", []):
                name = match.get("external_image_id", "")
                if name:
                    key_entity_map[s3_key].append(name)

        # Cache downloaded images to avoid re-downloading for multiple faces
        image_cache: dict[str, bytes | None] = {}

        for result in rekognition_results:
            s3_key = result.get("s3_key", "")
            is_extracted = "/extracted-images/" in s3_key
            faces = result.get("faces", [])

            for face in faces:
                confidence = face.get("confidence", 0)
                if confidence < MIN_FACE_CONFIDENCE:
                    continue

                bounding_box = face.get("bounding_box", {})
                if not bounding_box:
                    continue

                # Download source image (cached)
                if s3_key not in image_cache:
                    image_cache[s3_key] = self._download_image(s3_key)

                image_bytes = image_cache[s3_key]
                if image_bytes is None:
                    continue

                # Crop the face
                try:
                    crop_bytes = self._crop_single_face(image_bytes, bounding_box)
                except Exception as exc:
                    msg = f"Failed to crop face from {s3_key}: {exc}"
                    logger.warning(msg)
                    errors.append(msg)
                    continue

                # Determine entity name(s) for this face
                entity_names = key_entity_map.get(s3_key, [])
                if not entity_names:
                    # Use a generic label for unmatched faces
                    entity_names = ["unidentified"]

                # Compute deterministic hash for dedup
                crop_hash = self._compute_crop_hash(s3_key, bounding_box)

                for entity_name in entity_names:
                    crop_key = (
                        f"cases/{case_id}/face-crops/{entity_name}/{crop_hash}.jpg"
                    )
                    try:
                        self.s3.put_object(
                            Bucket=self.s3_bucket,
                            Key=crop_key,
                            Body=crop_bytes,
                            ContentType="image/jpeg",
                        )
                        crops_created += 1
                        if is_extracted:
                            crops_from_extracted += 1
                        entity_crops[entity_name].append((confidence, crop_key))
                    except Exception as exc:
                        msg = f"Failed to upload crop {crop_key}: {exc}"
                        logger.error(msg)
                        errors.append(msg)

        # Select primary thumbnail per entity (highest confidence)
        primary_thumbnails: dict[str, str] = {}
        entities_with_thumbnails: list[str] = []

        for entity_name, crops in entity_crops.items():
            if not crops:
                continue
            # Sort by confidence descending, pick the best
            best_confidence, best_key = max(crops, key=lambda x: x[0])
            primary_key = (
                f"cases/{case_id}/face-crops/{entity_name}/primary_thumbnail.jpg"
            )
            try:
                # Copy the best crop as primary_thumbnail.jpg
                self.s3.copy_object(
                    Bucket=self.s3_bucket,
                    CopySource={"Bucket": self.s3_bucket, "Key": best_key},
                    Key=primary_key,
                    ContentType="image/jpeg",
                )
                primary_thumbnails[entity_name] = primary_key
                entities_with_thumbnails.append(entity_name)
            except Exception as exc:
                msg = f"Failed to set primary thumbnail for {entity_name}: {exc}"
                logger.error(msg)
                errors.append(msg)

        return {
            "crops_created": crops_created,
            "crops_from_extracted_images": crops_from_extracted,
            "entities_with_thumbnails": sorted(entities_with_thumbnails),
            "primary_thumbnails": primary_thumbnails,
            "errors": errors,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _download_image(self, s3_key: str) -> bytes | None:
        """Download an image from S3. Returns None on failure."""
        try:
            resp = self.s3.get_object(Bucket=self.s3_bucket, Key=s3_key)
            return resp["Body"].read()
        except Exception as exc:
            logger.warning("Failed to download source image %s: %s", s3_key, exc)
            return None

    def _crop_single_face(
        self,
        image_bytes: bytes,
        bounding_box: dict,
        target_size: tuple = (100, 100),
    ) -> bytes:
        """Crop a face region from image bytes using bounding box coordinates.

        Bounding box values are normalised 0.0–1.0. Coordinates that exceed
        image boundaries are clamped to the edge.

        Args:
            image_bytes: Raw source image bytes (JPEG, PNG, or TIFF).
            bounding_box: Dict with ``Left``, ``Top``, ``Width``, ``Height``
                as normalised floats.
            target_size: Output dimensions (width, height) in pixels.

        Returns:
            JPEG bytes of the cropped and resized face.
        """
        img = Image.open(io.BytesIO(image_bytes))
        img_width, img_height = img.size

        # Extract normalised coordinates
        left = bounding_box.get("Left", 0.0)
        top = bounding_box.get("Top", 0.0)
        bb_width = bounding_box.get("Width", 0.0)
        bb_height = bounding_box.get("Height", 0.0)

        # Convert to pixel coordinates and clamp to image boundaries
        x1 = max(0, int(left * img_width))
        y1 = max(0, int(top * img_height))
        x2 = min(img_width, int((left + bb_width) * img_width))
        y2 = min(img_height, int((top + bb_height) * img_height))

        # Ensure we have a non-zero crop area
        if x2 <= x1:
            x2 = min(x1 + 1, img_width)
        if y2 <= y1:
            y2 = min(y1 + 1, img_height)

        cropped = img.crop((x1, y1, x2, y2))
        resized = cropped.resize(target_size, Image.LANCZOS)

        # Convert to RGB if necessary (e.g. RGBA, palette, CMYK)
        if resized.mode not in ("RGB",):
            resized = resized.convert("RGB")

        buf = io.BytesIO()
        resized.save(buf, format="JPEG", quality=90)
        return buf.getvalue()

    @staticmethod
    def _compute_crop_hash(s3_key: str, bounding_box: dict) -> str:
        """Deterministic hash from source key + bounding box for dedup.

        Uses SHA-256 on ``"{s3_key}:{Left}:{Top}:{Width}:{Height}"``.
        Returns first 12 hex chars.
        """
        left = bounding_box.get("Left", 0.0)
        top = bounding_box.get("Top", 0.0)
        width = bounding_box.get("Width", 0.0)
        height = bounding_box.get("Height", 0.0)
        raw = f"{s3_key}:{left}:{top}:{width}:{height}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
