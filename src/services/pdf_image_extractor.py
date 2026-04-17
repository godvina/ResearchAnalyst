"""PDF Image Extractor — extracts embedded images from PDF files using PyMuPDF (fitz).

Iterates over each page of a PDF, extracts embedded images, filters out small
decorative elements (< 50x50), and uploads qualifying images to S3 under the
``cases/{case_id}/extracted-images/`` prefix. Returns image metadata and an
extraction summary with counts for pipeline observability.
"""

import logging

import boto3

logger = logging.getLogger(__name__)

# Minimum pixel dimension — images smaller than this on either axis are skipped
MIN_DIMENSION = 50


class PdfImageExtractor:
    """Extracts embedded images from PDF files using PyMuPDF (fitz)."""

    def __init__(self, s3_bucket: str):
        self.s3_bucket = s3_bucket
        self.s3 = boto3.client("s3")

    def extract_images(
        self, pdf_bytes: bytes, case_id: str, document_id: str
    ) -> dict:
        """Extract all embedded images from a PDF and upload to S3.

        Args:
            pdf_bytes: Raw PDF file bytes.
            case_id: The case file identifier.
            document_id: The document identifier.

        Returns:
            Dict with ``extracted_images`` list and ``image_extraction_summary``.
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.warning(
                "PyMuPDF (fitz) not installed — skipping image extraction for document_id=%s",
                document_id,
            )
            return {
                "extracted_images": [],
                "image_extraction_summary": {
                    "total_pages_scanned": 0,
                    "total_images_found": 0,
                    "images_saved": 0,
                    "images_skipped_too_small": 0,
                    "extraction_errors": 0,
                },
            }

        extracted_images: list[dict] = []
        total_images_found = 0
        images_skipped_too_small = 0
        extraction_errors = 0

        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as exc:
            logger.warning(
                "Failed to open PDF for image extraction: document_id=%s, error=%s",
                document_id,
                exc,
            )
            return {
                "extracted_images": [],
                "image_extraction_summary": {
                    "total_pages_scanned": 0,
                    "total_images_found": 0,
                    "images_saved": 0,
                    "images_skipped_too_small": 0,
                    "extraction_errors": 0,
                },
            }

        total_pages = len(doc)

        for page_num in range(total_pages):
            try:
                page_images, page_skipped, page_errors = self._extract_page_images(
                    doc, page_num, case_id, document_id
                )
                extracted_images.extend(page_images)
                total_images_found += len(page_images) + page_skipped + page_errors
                images_skipped_too_small += page_skipped
                extraction_errors += page_errors
            except Exception as exc:
                logger.error(
                    "Failed to extract images from page: document_id=%s, page=%d, error=%s",
                    document_id,
                    page_num,
                    exc,
                )
                extraction_errors += 1

        doc.close()

        return {
            "extracted_images": extracted_images,
            "image_extraction_summary": {
                "total_pages_scanned": total_pages,
                "total_images_found": total_images_found,
                "images_saved": len(extracted_images),
                "images_skipped_too_small": images_skipped_too_small,
                "extraction_errors": extraction_errors,
            },
        }

    def _extract_page_images(
        self,
        doc,
        page_num: int,
        case_id: str,
        document_id: str,
    ) -> tuple[list[dict], int, int]:
        """Extract images from a single PDF page.

        Returns:
            Tuple of (image_metadata_list, skipped_count, error_count).
        """
        import fitz  # PyMuPDF

        page = doc[page_num]
        image_list = page.get_images(full=True)

        page_images: list[dict] = []
        skipped = 0
        errors = 0

        for img_index, img_info in enumerate(image_list):
            try:
                xref = img_info[0]
                base_image = doc.extract_image(xref)

                if not base_image or not base_image.get("image"):
                    errors += 1
                    continue

                width = base_image.get("width", 0)
                height = base_image.get("height", 0)

                # Check for SMASK (soft mask / alpha channel)
                smask_xref = img_info[1] if len(img_info) > 1 else 0
                has_alpha = smask_xref and smask_xref != 0

                # Determine format: PNG for alpha/transparency, JPEG otherwise
                if has_alpha:
                    ext = "png"
                    content_type = "image/png"
                else:
                    ext = "jpg"
                    content_type = "image/jpeg"

                # Skip small images (decorative elements, icons)
                if width < MIN_DIMENSION or height < MIN_DIMENSION:
                    skipped += 1
                    continue

                # Build image bytes — handle SMASK compositing
                image_bytes = self._build_image_bytes(
                    doc, xref, smask_xref, base_image, ext
                )

                if not image_bytes:
                    errors += 1
                    continue

                # Build S3 key
                filename = f"{document_id}_page{page_num}_img{img_index}.{ext}"
                s3_key = f"cases/{case_id}/extracted-images/{filename}"

                # Upload to S3
                file_size = self._save_image_to_s3(image_bytes, s3_key, content_type)

                page_images.append({
                    "s3_key": s3_key,
                    "page_num": page_num,
                    "width": width,
                    "height": height,
                    "file_size_bytes": file_size,
                    "source_document_id": document_id,
                })

            except Exception as exc:
                logger.error(
                    "Error extracting image %d from page %d: document_id=%s, error=%s",
                    img_index,
                    page_num,
                    document_id,
                    exc,
                )
                errors += 1

        return page_images, skipped, errors

    def _build_image_bytes(
        self, doc, xref: int, smask_xref: int, base_image: dict, ext: str
    ) -> bytes | None:
        """Build final image bytes, handling SMASK compositing.

        For images with an SMASK (alpha mask), composites the image onto a
        white background before saving. Returns JPEG or PNG bytes depending
        on ``ext``.
        """
        import fitz  # PyMuPDF

        try:
            pix = fitz.Pixmap(doc, xref)

            # Handle SMASK compositing onto white background
            if smask_xref and smask_xref != 0:
                try:
                    mask_pix = fitz.Pixmap(doc, smask_xref)
                    # Create pixmap with alpha from mask
                    if pix.n - pix.alpha < 4:  # not CMYK
                        pix_with_alpha = fitz.Pixmap(pix, mask_pix)
                    else:
                        # Convert CMYK to RGB first
                        pix_rgb = fitz.Pixmap(fitz.csRGB, pix)
                        pix_with_alpha = fitz.Pixmap(pix_rgb, mask_pix)
                        pix_rgb = None  # noqa: F841

                    # Composite onto white background for JPEG output
                    if ext == "jpg":
                        white_bg = fitz.Pixmap(fitz.csRGB, pix_with_alpha)
                        image_bytes = white_bg.tobytes("jpeg")
                        white_bg = None  # noqa: F841
                    else:
                        image_bytes = pix_with_alpha.tobytes("png")

                    mask_pix = None  # noqa: F841
                    pix_with_alpha = None  # noqa: F841
                    pix = None  # noqa: F841
                    return image_bytes
                except Exception as exc:
                    logger.warning(
                        "SMASK compositing failed for xref=%d, falling back: %s",
                        xref,
                        exc,
                    )
                    # Fall through to simple extraction below

            # Handle CMYK conversion
            if pix.n - pix.alpha >= 4:
                pix = fitz.Pixmap(fitz.csRGB, pix)

            # Simple extraction without SMASK
            if ext == "png":
                image_bytes = pix.tobytes("png")
            else:
                # For JPEG, strip alpha if present
                if pix.alpha:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                image_bytes = pix.tobytes("jpeg")

            pix = None  # noqa: F841
            return image_bytes

        except Exception as exc:
            logger.error("Failed to build image bytes for xref=%d: %s", xref, exc)
            return None

    def _save_image_to_s3(
        self, image_bytes: bytes, s3_key: str, content_type: str
    ) -> int:
        """Upload image bytes to S3 with correct Content-Type.

        Args:
            image_bytes: The image file bytes.
            s3_key: Full S3 object key.
            content_type: MIME type (``image/jpeg`` or ``image/png``).

        Returns:
            File size in bytes.
        """
        self.s3.put_object(
            Bucket=self.s3_bucket,
            Key=s3_key,
            Body=image_bytes,
            ContentType=content_type,
        )
        return len(image_bytes)
