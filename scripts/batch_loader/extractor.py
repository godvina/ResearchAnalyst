"""Text extraction from PDFs using PyPDF2 with Textract OCR fallback.

Extracts text from raw PDF files stored in S3. Tries PyPDF2 direct text
extraction first (free), then falls back to AWS Textract OCR for scanned
or image-based PDFs where chars/page falls below the configured threshold.
Results are cached to S3 so re-runs skip already-extracted files.
"""

from __future__ import annotations

import io
import json
import logging
import os
import time
from dataclasses import dataclass

from scripts.batch_loader.config import BatchConfig

logger = logging.getLogger(__name__)

# Sync Textract limit is 5 MB
_TEXTRACT_SYNC_LIMIT = 5 * 1024 * 1024


@dataclass
class ExtractionResult:
    """Result of extracting text from a single PDF."""

    s3_key: str
    text: str
    method: str  # "pypdf2" | "textract" | "cached" | "failed"
    char_count: int
    error: str | None = None


class TextExtractor:
    """Extracts text from PDFs using PyPDF2 with Textract OCR fallback."""

    def __init__(self, config: BatchConfig, s3_client, textract_client):
        self.config = config
        self.s3 = s3_client
        self.textract = textract_client

    def extract(self, s3_key: str, batch_id: str = "") -> ExtractionResult:
        """Extract text from a single PDF. Checks cache first.

        Wraps the core extraction logic in a retry loop (up to config.max_retries
        with exponential backoff). On each retry, logs the attempt number and error.
        After all retries exhausted, returns ExtractionResult with method="failed".

        Flow:
        1. Check extraction cache — return cached text if found
        2. Download PDF from S3
        3. Try PyPDF2 direct extraction
        4. If chars/page < ocr_threshold, fall back to Textract
        5. Save result to cache
        """
        # 1. Check cache (no retry needed for cache check)
        cached_text = self._check_cache(s3_key, batch_id)
        if cached_text is not None:
            return ExtractionResult(
                s3_key=s3_key,
                text=cached_text,
                method="cached",
                char_count=len(cached_text),
            )

        last_error: str | None = None
        for attempt in range(self.config.max_retries):
            result = self._try_extract(s3_key, batch_id)
            if result.method != "failed":
                return result

            last_error = result.error
            if attempt < self.config.max_retries - 1:
                backoff = 2 ** attempt
                logger.warning(
                    "Extraction attempt %d/%d failed for %s: %s — retrying in %ds",
                    attempt + 1,
                    self.config.max_retries,
                    s3_key,
                    last_error,
                    backoff,
                )
                time.sleep(backoff)

        logger.error(
            "Extraction failed after %d attempts for %s: %s",
            self.config.max_retries,
            s3_key,
            last_error,
        )
        return ExtractionResult(
            s3_key=s3_key, text="", method="failed", char_count=0, error=last_error
        )

    def _try_extract(self, s3_key: str, batch_id: str) -> ExtractionResult:
        """Single extraction attempt (download → PyPDF2 → optional Textract → cache)."""
        # Download PDF from S3
        try:
            obj = self.s3.get_object(
                Bucket=self.config.source_bucket, Key=s3_key
            )
            pdf_bytes = obj["Body"].read()
        except Exception as exc:
            msg = f"S3 download failed: {exc}"
            logger.error("Failed to download %s: %s", s3_key, msg)
            return ExtractionResult(
                s3_key=s3_key, text="", method="failed", char_count=0, error=msg
            )

        # Try PyPDF2
        try:
            text, page_count = self._extract_pypdf2(pdf_bytes)
        except Exception as exc:
            msg = f"PyPDF2 failed: {exc}"
            logger.error("PyPDF2 extraction failed for %s: %s", s3_key, msg)
            return ExtractionResult(
                s3_key=s3_key, text="", method="failed", char_count=0, error=msg
            )

        # Decide if OCR fallback is needed
        chars_per_page = len(text) / max(page_count, 1)
        if chars_per_page < self.config.ocr_threshold:
            try:
                ocr_text = self._extract_textract(s3_key)
                self._save_to_cache(s3_key, batch_id, ocr_text, "textract")
                return ExtractionResult(
                    s3_key=s3_key,
                    text=ocr_text,
                    method="textract",
                    char_count=len(ocr_text),
                )
            except Exception as exc:
                logger.warning(
                    "Textract fallback failed for %s: %s — using PyPDF2 text",
                    s3_key,
                    exc,
                )
                # Fall through to return PyPDF2 result

        # Return PyPDF2 result and cache it
        self._save_to_cache(s3_key, batch_id, text, "pypdf2")
        return ExtractionResult(
            s3_key=s3_key,
            text=text,
            method="pypdf2",
            char_count=len(text),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _check_cache(self, s3_key: str, batch_id: str) -> str | None:
        """Check if extracted text exists in S3 extraction cache.

        Cache key format: textract-output/batch_{batch_id}/{basename}.json
        """
        if not batch_id:
            return None

        basename = os.path.basename(s3_key)
        cache_key = f"textract-output/batch_{batch_id}/{basename}.json"

        try:
            obj = self.s3.get_object(
                Bucket=self.config.data_lake_bucket, Key=cache_key
            )
            data = json.loads(obj["Body"].read().decode("utf-8"))
            return data.get("extractedText")
        except Exception:
            return None

    def _extract_pypdf2(self, pdf_bytes: bytes) -> tuple[str, int]:
        """Extract text via PyPDF2. Returns (text, page_count).

        Raises PyPDF2.errors.PdfReadError for corrupted/encrypted PDFs.
        """
        import PyPDF2

        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        pages: list[str] = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            pages.append(page_text.strip())

        full_text = "\n\n".join(p for p in pages if p)
        return full_text, len(reader.pages)

    def _extract_textract(self, s3_key: str) -> str:
        """Submit to Textract OCR and return combined text.

        Uses synchronous detect_document_text for PDFs under 5 MB.
        Falls back to async start/get_document_text_detection for larger files.
        """
        # Check file size to decide sync vs async
        head = self.s3.head_object(
            Bucket=self.config.source_bucket, Key=s3_key
        )
        file_size = head["ContentLength"]

        if file_size <= _TEXTRACT_SYNC_LIMIT:
            return self._extract_textract_sync(s3_key)
        return self._extract_textract_async(s3_key)

    def _extract_textract_sync(self, s3_key: str) -> str:
        """Synchronous Textract for files <= 5 MB."""
        # Download bytes for sync API
        obj = self.s3.get_object(
            Bucket=self.config.source_bucket, Key=s3_key
        )
        pdf_bytes = obj["Body"].read()

        resp = self.textract.detect_document_text(
            Document={"Bytes": pdf_bytes}
        )
        lines: list[str] = []
        for block in resp.get("Blocks", []):
            if block["BlockType"] == "LINE":
                lines.append(block.get("Text", ""))
        return "\n".join(lines)

    def _extract_textract_async(self, s3_key: str) -> str:
        """Async Textract for files > 5 MB."""
        resp = self.textract.start_document_text_detection(
            DocumentLocation={
                "S3Object": {
                    "Bucket": self.config.source_bucket,
                    "Name": s3_key,
                }
            }
        )
        job_id = resp["JobId"]

        # Poll until complete
        while True:
            result = self.textract.get_document_text_detection(JobId=job_id)
            status = result["JobStatus"]
            if status == "SUCCEEDED":
                break
            if status == "FAILED":
                raise RuntimeError(
                    f"Textract async job failed for {s3_key}: "
                    f"{result.get('StatusMessage', 'unknown')}"
                )
            time.sleep(5)

        # Collect all pages of results
        lines: list[str] = []
        next_token = None
        while True:
            kwargs: dict = {"JobId": job_id}
            if next_token:
                kwargs["NextToken"] = next_token
            result = self.textract.get_document_text_detection(**kwargs)
            for block in result.get("Blocks", []):
                if block["BlockType"] == "LINE":
                    lines.append(block.get("Text", ""))
            next_token = result.get("NextToken")
            if not next_token:
                break

        return "\n".join(lines)

    def _save_to_cache(self, s3_key: str, batch_id: str, text: str, method: str) -> None:
        """Save extracted text JSON to S3 extraction cache.

        Cache key: textract-output/batch_{batch_id}/{basename}.json
        """
        if not batch_id:
            return

        basename = os.path.basename(s3_key)
        cache_key = f"textract-output/batch_{batch_id}/{basename}.json"

        cache_data = {
            "extractedText": text,
            "sourceFile": s3_key,
            "method": method,
        }

        try:
            self.s3.put_object(
                Bucket=self.config.data_lake_bucket,
                Key=cache_key,
                Body=json.dumps(cache_data, ensure_ascii=False).encode("utf-8"),
                ContentType="application/json",
            )
        except Exception as exc:
            logger.warning("Failed to save cache for %s: %s", s3_key, exc)
