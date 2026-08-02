"""File format adapters for conspiracy theory data ingestion.

Normalizes diverse file formats (PDF, XML, CSV, JSON, HTML tables, TIFF, FASTA)
into a unified NormalizedRecord structure for downstream processing by the
agent chain (Broad Scanner → Taxonomy Scanner → Cross-Pattern Agent).

Each adapter follows the BaseAdapter interface and produces NormalizedRecord
instances that get stored to S3 as JSON.
"""
import hashlib
import json
import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


@dataclass
class NormalizedRecord:
    """Universal output format from any file format adapter.
    
    Every document, regardless of original format, gets normalized into this
    structure before being passed to the agent chain.
    """
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    theory_name: str = ""
    source_file: str = ""
    source_type: str = ""                    # pdf, xml, csv, json, html, tiff, jpeg, fasta
    content_text: str = ""                   # Extracted text (max 50K chars)
    metadata: dict = field(default_factory=dict)
    extracted_entities: list = field(default_factory=list)
    extracted_dates: list = field(default_factory=list)
    extracted_locations: list = field(default_factory=list)  # [{name, lat, lon}]
    ingested_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    content_hash: str = ""                   # SHA-256 for dedup

    def compute_hash(self):
        """Compute SHA-256 of content for deduplication."""
        self.content_hash = hashlib.sha256(self.content_text.encode('utf-8')).hexdigest()
        return self.content_hash

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage."""
        return asdict(self)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @property
    def s3_key(self) -> str:
        """Generate the S3 storage path for this record.
        
        Format: data-lake/conspiracy-theories/{theory_name}/{source_type}/{filename}.json
        """
        filename = os.path.splitext(os.path.basename(self.source_file))[0]
        safe_filename = filename[:100].replace(' ', '_').replace('/', '_')
        return f"data-lake/conspiracy-theories/{self.theory_name}/{self.source_type}/{safe_filename}_{self.record_id[:8]}.json"


class BaseAdapter(ABC):
    """Abstract base for all file format adapters.
    
    Each adapter handles one or more file types, extracting content
    into NormalizedRecord instances.
    """

    @abstractmethod
    def can_handle(self, file_path: str, mime_type: str = "") -> bool:
        """Return True if this adapter can process the given file."""
        ...

    @abstractmethod
    def extract(self, file_path: str, theory_name: str) -> list[NormalizedRecord]:
        """Extract content from the file into one or more NormalizedRecords.
        
        Args:
            file_path: Path to the source file
            theory_name: Which theory dataset this belongs to (e.g., "bermuda_triangle")
            
        Returns:
            List of NormalizedRecord instances (one per logical document/record)
        """
        ...

    def _truncate_content(self, text: str, max_chars: int = 50000) -> str:
        """Truncate content to max length to stay within embedding limits."""
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "\n[TRUNCATED]"


class PDFAdapter(BaseAdapter):
    """Extract text, tables, and structural elements from PDF documents."""

    EXTENSIONS = {'.pdf'}

    def can_handle(self, file_path: str, mime_type: str = "") -> bool:
        ext = os.path.splitext(file_path)[1].lower()
        return ext in self.EXTENSIONS or mime_type == 'application/pdf'

    def extract(self, file_path: str, theory_name: str) -> list[NormalizedRecord]:
        try:
            import pdfplumber
        except ImportError:
            # Fallback to PyPDF2 if pdfplumber not available
            return self._extract_pypdf2(file_path, theory_name)

        records = []
        try:
            with pdfplumber.open(file_path) as pdf:
                full_text = []
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    full_text.append(text)

                content = "\n\n".join(full_text)
                record = NormalizedRecord(
                    theory_name=theory_name,
                    source_file=file_path,
                    source_type="pdf",
                    content_text=self._truncate_content(content),
                    metadata={
                        "page_count": len(pdf.pages),
                        "file_size_bytes": os.path.getsize(file_path),
                    }
                )
                record.compute_hash()
                records.append(record)
        except Exception as e:
            # Return partial record on error
            record = NormalizedRecord(
                theory_name=theory_name,
                source_file=file_path,
                source_type="pdf",
                content_text="",
                metadata={"error": str(e), "status": "extraction_failed"}
            )
            records.append(record)

        return records

    def _extract_pypdf2(self, file_path: str, theory_name: str) -> list[NormalizedRecord]:
        """Fallback extraction using PyPDF2."""
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(file_path)
            full_text = []
            for page in reader.pages:
                text = page.extract_text() or ""
                full_text.append(text)

            content = "\n\n".join(full_text)
            record = NormalizedRecord(
                theory_name=theory_name,
                source_file=file_path,
                source_type="pdf",
                content_text=self._truncate_content(content),
                metadata={"page_count": len(reader.pages)}
            )
            record.compute_hash()
            return [record]
        except Exception as e:
            return [NormalizedRecord(
                theory_name=theory_name,
                source_file=file_path,
                source_type="pdf",
                metadata={"error": str(e)}
            )]


class XMLAdapter(BaseAdapter):
    """Extract structured content from XML documents (e.g., NTSB accident reports)."""

    EXTENSIONS = {'.xml'}

    def can_handle(self, file_path: str, mime_type: str = "") -> bool:
        ext = os.path.splitext(file_path)[1].lower()
        return ext in self.EXTENSIONS or mime_type in ('application/xml', 'text/xml')

    def extract(self, file_path: str, theory_name: str) -> list[NormalizedRecord]:
        import xml.etree.ElementTree as ET

        records = []
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            # Extract all text content recursively
            def get_all_text(elem, depth=0):
                texts = []
                tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                if elem.text and elem.text.strip():
                    texts.append(f"{'  '*depth}{tag}: {elem.text.strip()}")
                for child in elem:
                    texts.extend(get_all_text(child, depth + 1))
                return texts

            content_lines = get_all_text(root)
            content = "\n".join(content_lines)

            # Extract attributes as metadata
            metadata = dict(root.attrib)
            metadata["root_tag"] = root.tag
            metadata["child_count"] = len(list(root))

            record = NormalizedRecord(
                theory_name=theory_name,
                source_file=file_path,
                source_type="xml",
                content_text=self._truncate_content(content),
                metadata=metadata
            )
            record.compute_hash()
            records.append(record)
        except Exception as e:
            records.append(NormalizedRecord(
                theory_name=theory_name,
                source_file=file_path,
                source_type="xml",
                metadata={"error": str(e)}
            ))

        return records


class CSVJSONAdapter(BaseAdapter):
    """Extract records from CSV and JSON tabular data."""

    EXTENSIONS = {'.csv', '.json', '.jsonl'}

    def can_handle(self, file_path: str, mime_type: str = "") -> bool:
        ext = os.path.splitext(file_path)[1].lower()
        return ext in self.EXTENSIONS

    def extract(self, file_path: str, theory_name: str) -> list[NormalizedRecord]:
        ext = os.path.splitext(file_path)[1].lower()

        if ext == '.csv':
            return self._extract_csv(file_path, theory_name)
        else:
            return self._extract_json(file_path, theory_name)

    def _extract_csv(self, file_path: str, theory_name: str) -> list[NormalizedRecord]:
        """Extract CSV rows as individual records (up to 10K rows per batch)."""
        import csv

        records = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []
                rows = []
                for i, row in enumerate(reader):
                    if i >= 10000:  # Cap at 10K rows per file for memory safety
                        break
                    rows.append(row)

                # Create one NormalizedRecord per batch of rows
                content = json.dumps(rows[:100], ensure_ascii=False)  # First 100 for content preview
                record = NormalizedRecord(
                    theory_name=theory_name,
                    source_file=file_path,
                    source_type="csv",
                    content_text=self._truncate_content(content),
                    metadata={
                        "headers": headers,
                        "row_count": len(rows),
                        "sample_rows": rows[:5]
                    }
                )
                record.compute_hash()
                records.append(record)
        except Exception as e:
            records.append(NormalizedRecord(
                theory_name=theory_name,
                source_file=file_path,
                source_type="csv",
                metadata={"error": str(e)}
            ))

        return records

    def _extract_json(self, file_path: str, theory_name: str) -> list[NormalizedRecord]:
        """Extract JSON content (array or object)."""
        records = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                data = json.load(f)

            if isinstance(data, list):
                content = json.dumps(data[:100], ensure_ascii=False)
                metadata = {"record_count": len(data), "type": "array"}
            elif isinstance(data, dict):
                content = json.dumps(data, ensure_ascii=False)
                metadata = {"keys": list(data.keys())[:20], "type": "object"}
            else:
                content = str(data)
                metadata = {"type": type(data).__name__}

            record = NormalizedRecord(
                theory_name=theory_name,
                source_file=file_path,
                source_type="json",
                content_text=self._truncate_content(content),
                metadata=metadata
            )
            record.compute_hash()
            records.append(record)
        except Exception as e:
            records.append(NormalizedRecord(
                theory_name=theory_name,
                source_file=file_path,
                source_type="json",
                metadata={"error": str(e)}
            ))

        return records


class HTMLTableAdapter(BaseAdapter):
    """Extract structured data from HTML tables (Wikipedia, etc.)."""

    EXTENSIONS = {'.html', '.htm'}

    def can_handle(self, file_path: str, mime_type: str = "") -> bool:
        ext = os.path.splitext(file_path)[1].lower()
        return ext in self.EXTENSIONS or mime_type == 'text/html'

    def extract(self, file_path: str, theory_name: str) -> list[NormalizedRecord]:
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return [NormalizedRecord(
                theory_name=theory_name,
                source_file=file_path,
                source_type="html",
                metadata={"error": "beautifulsoup4 not installed"}
            )]

        records = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')

            tables = soup.find_all('table')
            for table_idx, table in enumerate(tables):
                rows = table.find_all('tr')
                if not rows:
                    continue

                # Extract headers
                header_row = rows[0]
                headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]

                # Extract data rows
                data_rows = []
                for row in rows[1:]:
                    cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                    if cells:
                        data_rows.append(dict(zip(headers, cells)))

                content = json.dumps(data_rows[:100], ensure_ascii=False)
                record = NormalizedRecord(
                    theory_name=theory_name,
                    source_file=file_path,
                    source_type="html",
                    content_text=self._truncate_content(content),
                    metadata={
                        "table_index": table_idx,
                        "headers": headers,
                        "row_count": len(data_rows)
                    }
                )
                record.compute_hash()
                records.append(record)

            if not records:
                # No tables found — extract body text
                text = soup.get_text(separator='\n', strip=True)
                record = NormalizedRecord(
                    theory_name=theory_name,
                    source_file=file_path,
                    source_type="html",
                    content_text=self._truncate_content(text),
                    metadata={"type": "body_text", "tables_found": 0}
                )
                record.compute_hash()
                records.append(record)

        except Exception as e:
            records.append(NormalizedRecord(
                theory_name=theory_name,
                source_file=file_path,
                source_type="html",
                metadata={"error": str(e)}
            ))

        return records


class ImageMetadataAdapter(BaseAdapter):
    """Extract EXIF metadata from TIFF/JPEG images without analyzing content."""

    EXTENSIONS = {'.tiff', '.tif', '.jpg', '.jpeg'}

    def can_handle(self, file_path: str, mime_type: str = "") -> bool:
        ext = os.path.splitext(file_path)[1].lower()
        return ext in self.EXTENSIONS

    def extract(self, file_path: str, theory_name: str) -> list[NormalizedRecord]:
        source_type = "tiff" if os.path.splitext(file_path)[1].lower() in {'.tiff', '.tif'} else "jpeg"

        try:
            from PIL import Image
            from PIL.ExifTags import TAGS

            img = Image.open(file_path)
            exif_data = {}

            if hasattr(img, '_getexif') and img._getexif():
                for tag_id, value in img._getexif().items():
                    tag_name = TAGS.get(tag_id, str(tag_id))
                    # Convert non-serializable types
                    if isinstance(value, bytes):
                        value = value.hex()[:100]
                    elif not isinstance(value, (str, int, float, bool, type(None))):
                        value = str(value)[:200]
                    exif_data[tag_name] = value

            # Extract GPS if available
            locations = []
            if 'GPSInfo' in exif_data:
                locations.append({"name": "EXIF GPS", "raw": str(exif_data['GPSInfo'])[:200]})

            content = f"Image file: {os.path.basename(file_path)}\nFormat: {img.format}\nSize: {img.size}\nMode: {img.mode}"
            if exif_data:
                content += f"\nEXIF fields: {', '.join(list(exif_data.keys())[:20])}"

            record = NormalizedRecord(
                theory_name=theory_name,
                source_file=file_path,
                source_type=source_type,
                content_text=content,
                metadata={
                    "format": img.format,
                    "size": img.size,
                    "mode": img.mode,
                    "exif": {k: v for k, v in list(exif_data.items())[:30]}
                },
                extracted_locations=locations
            )
            record.compute_hash()
            return [record]

        except Exception as e:
            return [NormalizedRecord(
                theory_name=theory_name,
                source_file=file_path,
                source_type=source_type,
                metadata={"error": str(e)}
            )]


class FASTAAdapter(BaseAdapter):
    """Extract sequence headers and metadata from FASTA genomic files."""

    EXTENSIONS = {'.fasta', '.fa', '.fna', '.faa'}

    def can_handle(self, file_path: str, mime_type: str = "") -> bool:
        ext = os.path.splitext(file_path)[1].lower()
        return ext in self.EXTENSIONS

    def extract(self, file_path: str, theory_name: str) -> list[NormalizedRecord]:
        records = []
        try:
            headers = []
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    if line.startswith('>'):
                        headers.append(line[1:].strip())
                        if len(headers) >= 1000:  # Cap at 1000 sequences
                            break

            content = "\n".join(headers)
            record = NormalizedRecord(
                theory_name=theory_name,
                source_file=file_path,
                source_type="fasta",
                content_text=self._truncate_content(content),
                metadata={
                    "sequence_count": len(headers),
                    "sample_headers": headers[:10]
                }
            )
            record.compute_hash()
            records.append(record)

        except Exception as e:
            records.append(NormalizedRecord(
                theory_name=theory_name,
                source_file=file_path,
                source_type="fasta",
                metadata={"error": str(e)}
            ))

        return records


# ============================================================
# ADAPTER REGISTRY
# ============================================================

class AdapterRegistry:
    """Routes files to the correct adapter based on extension/MIME type.
    
    Handles unrecognized formats gracefully by logging to skipped_files.
    """

    def __init__(self):
        self.adapters: list[BaseAdapter] = [
            PDFAdapter(),
            XMLAdapter(),
            CSVJSONAdapter(),
            HTMLTableAdapter(),
            ImageMetadataAdapter(),
            FASTAAdapter(),
        ]
        self.skipped_files: list[dict] = []

    def get_adapter(self, file_path: str, mime_type: str = "") -> Optional[BaseAdapter]:
        """Find the appropriate adapter for a file."""
        for adapter in self.adapters:
            if adapter.can_handle(file_path, mime_type):
                return adapter
        return None

    def ingest_file(self, file_path: str, theory_name: str, mime_type: str = "") -> list[NormalizedRecord]:
        """Ingest a single file, routing to the correct adapter.
        
        Returns NormalizedRecords on success, logs to skipped_files on failure.
        """
        adapter = self.get_adapter(file_path, mime_type)

        if adapter is None:
            ext = os.path.splitext(file_path)[1].lower()
            self.skipped_files.append({
                "file_path": file_path,
                "detected_format": ext or "unknown",
                "theory_name": theory_name,
                "reason": "no_adapter_registered"
            })
            return []

        return adapter.extract(file_path, theory_name)

    def ingest_directory(self, directory: str, theory_name: str) -> list[NormalizedRecord]:
        """Ingest all files in a directory recursively."""
        all_records = []
        for root, dirs, files in os.walk(directory):
            for filename in files:
                file_path = os.path.join(root, filename)
                records = self.ingest_file(file_path, theory_name)
                all_records.extend(records)
        return all_records
