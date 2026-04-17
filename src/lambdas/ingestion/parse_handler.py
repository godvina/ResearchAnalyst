"""Lambda handler for document parsing step of the ingestion pipeline.

Receives a document ID and delegates to DocumentParser.parse().
"""

import logging
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _try_extract_pdf_images(raw_bytes, case_id, document_id, effective_config):
    """Attempt PDF image extraction. Returns image metadata or empty result.

    Called only for .pdf files. Falls back gracefully on any error.

    Args:
        raw_bytes: Raw PDF file bytes.
        case_id: The case file identifier.
        document_id: The document identifier.
        effective_config: The resolved pipeline configuration dict.

    Returns:
        Dict with ``extracted_images`` list and ``image_extraction_summary`` dict.
    """
    empty_result = {
        "extracted_images": [],
        "image_extraction_summary": {},
    }

    # Check if image extraction is enabled (default: true)
    extract_images = (
        effective_config
        .get("parse", {})
        .get("extract_images", True)
    )
    if not extract_images:
        logger.info("PDF image extraction disabled via config for document %s", document_id)
        return empty_result

    try:
        from services.pdf_image_extractor import PdfImageExtractor

        s3_bucket = os.environ.get("S3_BUCKET_NAME", "")
        extractor = PdfImageExtractor(s3_bucket=s3_bucket)
        result = extractor.extract_images(
            pdf_bytes=raw_bytes,
            case_id=case_id,
            document_id=document_id,
        )
        logger.info(
            "PDF image extraction for document %s: %d images saved",
            document_id,
            result.get("image_extraction_summary", {}).get("images_saved", 0),
        )
        return result
    except Exception as exc:
        logger.warning(
            "PDF image extraction failed for document %s, falling back to text-only: %s",
            document_id,
            exc,
        )
        return empty_result


def handler(event, context):
    """Parse a raw document into structured representation.

    Expected event:
        {
            "case_id": "...",
            "document_id": "...",
            "effective_config": {...}   # optional
        }

    Returns:
        {
            "case_id": "...",
            "document_id": "...",
            "raw_text": "...",
            "sections": [...],
            "source_metadata": {...},
            "extracted_images": [...],
            "image_extraction_summary": {...}
        }
    """
    from services.document_parser import DocumentParser
    from storage.s3_helper import PrefixType, download_file, list_files

    case_id = event["case_id"]
    document_id = event["document_id"]
    effective_config = event.get("effective_config", {})
    s3_bucket = os.environ.get("S3_BUCKET_NAME")

    logger.info("Parsing document %s for case %s", document_id, case_id)

    # Find and download the raw file
    raw_files = list_files(case_id, PrefixType.RAW, bucket=s3_bucket)
    raw_content = None
    raw_bytes = None
    matched_filename = None
    for filename in raw_files:
        if filename.startswith(document_id):
            raw_bytes = download_file(case_id, PrefixType.RAW, filename, bucket=s3_bucket)
            matched_filename = filename
            try:
                raw_content = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                # Binary file (e.g. PDF) — raw_content stays None for text parsing
                raw_content = None
            break

    if raw_bytes is None:
        raise FileNotFoundError(
            f"Raw file not found for document {document_id} in case {case_id}"
        )

    # --- PDF image extraction (separate step, runs before text parsing) ---
    extracted_images = []
    image_extraction_summary = {}

    if matched_filename and matched_filename.lower().endswith(".pdf"):
        image_result = _try_extract_pdf_images(
            raw_bytes, case_id, document_id, effective_config
        )
        extracted_images = image_result.get("extracted_images", [])
        image_extraction_summary = image_result.get("image_extraction_summary", {})

    # --- Text extraction (existing logic, untouched) ---
    if raw_content is None:
        # Binary file that couldn't be decoded as UTF-8 — use empty text
        raw_content = ""

    parser = DocumentParser()
    try:
        parsed = parser.parse(
            raw_content=raw_content,
            document_id=document_id,
            case_file_id=case_id,
        )
    except Exception as exc:
        logger.warning(
            "Text parsing failed for document %s: %s — returning empty text",
            document_id,
            exc,
        )
        # Return what we have — images may still have been extracted
        return {
            "case_id": case_id,
            "document_id": document_id,
            "raw_text": "",
            "sections": [],
            "source_metadata": {},
            "extracted_images": extracted_images,
            "image_extraction_summary": image_extraction_summary,
        }

    logger.info("Parsed document %s: %d sections", document_id, len(parsed.sections))

    return {
        "case_id": case_id,
        "document_id": document_id,
        "raw_text": parsed.raw_text,
        "sections": parsed.sections,
        "source_metadata": parsed.source_metadata,
        "extracted_images": extracted_images,
        "image_extraction_summary": image_extraction_summary,
    }
