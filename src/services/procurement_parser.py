"""Procurement data parser for bid tabulations.

Extracts structured ProcurementRecords from CSV, Excel, PDF (via Textract),
and JSON input formats. Normalizes vendor names using fuzzy matching.
Provides a pretty-printer for round-trip CSV serialization.

Usage:
    parser = ProcurementParser()
    records = parser.parse_csv(csv_content)
    csv_output = parser.pretty_print_csv(records)
"""

from __future__ import annotations

import csv
import io
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from typing import Optional

logger = logging.getLogger(__name__)

# Standard CSV column headers for pretty-printing
STANDARD_HEADERS = [
    "record_id",
    "vendor_id",
    "vendor_name",
    "contract_id",
    "bid_amount",
    "submission_timestamp",
    "specifications_met",
    "award_status",
    "government_estimate",
    "geographic_region",
]

# Common column name mappings from various procurement formats
COLUMN_ALIASES = {
    "vendor_id": ["vendor_id", "vendorid", "vendor_code", "bidder_id", "bidder_code", "supplier_id"],
    "vendor_name": ["vendor_name", "vendorname", "bidder_name", "bidder", "company", "company_name", "supplier", "supplier_name", "firm"],
    "contract_id": ["contract_id", "contractid", "contract_number", "contract_no", "solicitation", "solicitation_number", "rfp", "rfp_number", "ifb", "project_id"],
    "bid_amount": ["bid_amount", "bidamount", "bid_price", "price", "amount", "total_bid", "total_price", "bid_value", "offer_amount"],
    "submission_timestamp": ["submission_timestamp", "submission_date", "bid_date", "date_submitted", "submit_date", "date", "bid_submission_date"],
    "specifications_met": ["specifications_met", "specs_met", "responsive", "compliant", "meets_specs", "technically_acceptable"],
    "award_status": ["award_status", "status", "award", "result", "outcome", "winner", "awarded"],
    "government_estimate": ["government_estimate", "govt_estimate", "estimate", "ige", "independent_estimate", "cost_estimate"],
    "geographic_region": ["geographic_region", "region", "state", "location", "area", "district", "zone"],
}

# Award status normalization mapping
AWARD_STATUS_MAP = {
    "won": "won", "win": "won", "winner": "won", "awarded": "won", "yes": "won", "1": "won", "true": "won", "w": "won",
    "lost": "lost", "lose": "lost", "loser": "lost", "not awarded": "lost", "no": "lost", "0": "lost", "false": "lost", "l": "lost",
    "withdrawn": "withdrawn", "withdraw": "withdrawn", "wd": "withdrawn", "cancelled": "withdrawn", "retracted": "withdrawn",
}


@dataclass
class ParsedRecord:
    """Internal representation of a parsed procurement record."""

    record_id: str = ""
    vendor_id: str = ""
    vendor_name: str = ""
    contract_id: str = ""
    bid_amount: float = 0.0
    submission_timestamp: Optional[str] = None
    specifications_met: bool = True
    award_status: str = ""
    government_estimate: Optional[float] = None
    naics_codes: list[str] = field(default_factory=list)
    geographic_region: Optional[str] = None
    raw_data: dict = field(default_factory=dict)


class ProcurementParser:
    """Parser for procurement bid tabulation data.

    Supports CSV, Excel, PDF (via Textract), and JSON formats.
    Normalizes vendor names using fuzzy matching against known vendors.
    """

    def __init__(self, textract_client=None, fuzzy_threshold: float = 0.85) -> None:
        """Initialize parser.

        Args:
            textract_client: boto3 Textract client for PDF parsing (optional).
            fuzzy_threshold: Levenshtein similarity threshold for vendor name
                normalization. Names with similarity >= threshold are matched.
        """
        self.textract_client = textract_client
        self.fuzzy_threshold = fuzzy_threshold

    # =========================================================================
    # Validation
    # =========================================================================

    def validate_record(self, record: dict) -> tuple[bool, Optional[str]]:
        """Validate a raw record dict has required fields with valid values.

        Args:
            record: Dict with procurement record fields.

        Returns:
            Tuple of (is_valid, error_message). error_message is None if valid.
        """
        # Required fields
        if not record.get("vendor_name") and not record.get("vendor_id"):
            return False, "Missing required field: vendor_name or vendor_id"
        if not record.get("contract_id"):
            return False, "Missing required field: contract_id"

        # Bid amount validation
        bid_amount = record.get("bid_amount")
        if bid_amount is None:
            return False, "Missing required field: bid_amount"
        try:
            amount = float(str(bid_amount).replace(",", "").replace("$", "").strip())
            if amount <= 0:
                return False, f"bid_amount must be positive, got: {bid_amount}"
        except (ValueError, TypeError):
            return False, f"bid_amount is not a valid number: {bid_amount}"

        # Award status validation
        award_status = record.get("award_status", "").strip().lower()
        if award_status and award_status not in AWARD_STATUS_MAP:
            return False, f"Invalid award_status: {record.get('award_status')}. Expected one of: won, lost, withdrawn"

        return True, None

    # =========================================================================
    # CSV Parsing
    # =========================================================================

    def parse_csv(self, file_content: str | bytes) -> list[ParsedRecord]:
        """Parse CSV bid tabulation data into structured records.

        Handles common government procurement CSV formats with flexible
        column name matching.

        Args:
            file_content: CSV file content as string or bytes.

        Returns:
            List of parsed ProcurementRecords.
        """
        if isinstance(file_content, bytes):
            file_content = file_content.decode("utf-8-sig")  # Handle BOM

        reader = csv.DictReader(io.StringIO(file_content))
        if not reader.fieldnames:
            return []

        # Map actual column names to standard names
        column_map = self._build_column_map(reader.fieldnames)

        records = []
        for row in reader:
            raw_data = dict(row)
            record_dict = self._extract_fields(row, column_map)
            record_dict["raw_data"] = raw_data

            is_valid, error = self.validate_record(record_dict)
            if is_valid:
                records.append(self._dict_to_record(record_dict))
            else:
                logger.warning(f"Skipping invalid CSV row: {error}")

        return records

    # =========================================================================
    # JSON Parsing
    # =========================================================================

    def parse_json(self, file_content: str | bytes) -> list[ParsedRecord]:
        """Parse JSON array of bid records.

        Args:
            file_content: JSON content as string or bytes.

        Returns:
            List of parsed ProcurementRecords.
        """
        if isinstance(file_content, bytes):
            file_content = file_content.decode("utf-8")

        data = json.loads(file_content)
        if isinstance(data, dict):
            # Handle wrapped format: {"records": [...]} or {"bids": [...]}
            data = data.get("records") or data.get("bids") or data.get("data") or [data]
        if not isinstance(data, list):
            data = [data]

        records = []
        for item in data:
            if not isinstance(item, dict):
                continue
            raw_data = dict(item)
            # JSON fields may already use standard names
            record_dict = {}
            for std_name, aliases in COLUMN_ALIASES.items():
                for alias in aliases:
                    if alias in item:
                        record_dict[std_name] = item[alias]
                        break
                    # Case-insensitive fallback
                    lower_keys = {k.lower(): k for k in item}
                    if alias.lower() in lower_keys:
                        record_dict[std_name] = item[lower_keys[alias.lower()]]
                        break
            record_dict["raw_data"] = raw_data

            is_valid, error = self.validate_record(record_dict)
            if is_valid:
                records.append(self._dict_to_record(record_dict))
            else:
                logger.warning(f"Skipping invalid JSON record: {error}")

        return records

    # =========================================================================
    # Excel Parsing
    # =========================================================================

    def parse_excel(self, file_content: bytes) -> list[ParsedRecord]:
        """Parse Excel spreadsheet containing procurement data.

        Handles multi-sheet workbooks, processing all sheets.
        Requires openpyxl to be available.

        Args:
            file_content: Excel file content as bytes.

        Returns:
            List of parsed ProcurementRecords.
        """
        try:
            import openpyxl
        except ImportError:
            logger.error("openpyxl not available for Excel parsing")
            return []

        wb = openpyxl.load_workbook(io.BytesIO(file_content), read_only=True, data_only=True)
        records = []

        for sheet in wb.worksheets:
            rows = list(sheet.iter_rows(values_only=True))
            if len(rows) < 2:
                continue

            # First row is headers
            headers = [str(h).strip() if h else "" for h in rows[0]]
            column_map = self._build_column_map(headers)

            for row_values in rows[1:]:
                row_dict = {}
                for i, header in enumerate(headers):
                    if i < len(row_values) and row_values[i] is not None:
                        row_dict[header] = str(row_values[i])
                    else:
                        row_dict[header] = ""

                raw_data = dict(row_dict)
                record_dict = self._extract_fields(row_dict, column_map)
                record_dict["raw_data"] = raw_data

                is_valid, error = self.validate_record(record_dict)
                if is_valid:
                    records.append(self._dict_to_record(record_dict))

        wb.close()
        return records

    # =========================================================================
    # PDF Parsing (via Textract)
    # =========================================================================

    def parse_pdf(self, s3_bucket: str, s3_key: str) -> list[ParsedRecord]:
        """Parse PDF bid abstract using Amazon Textract table extraction.

        Args:
            s3_bucket: S3 bucket containing the PDF.
            s3_key: S3 key of the PDF file.

        Returns:
            List of parsed ProcurementRecords.
        """
        if not self.textract_client:
            logger.error("Textract client not configured for PDF parsing")
            return []

        try:
            response = self.textract_client.analyze_document(
                Document={"S3Object": {"Bucket": s3_bucket, "Name": s3_key}},
                FeatureTypes=["TABLES"],
            )
        except Exception as e:
            logger.error(f"Textract failed for s3://{s3_bucket}/{s3_key}: {e}")
            return []

        # Extract tables from Textract response
        tables = self._extract_textract_tables(response)
        records = []

        for table in tables:
            if len(table) < 2:
                continue
            headers = [str(h).strip() for h in table[0]]
            column_map = self._build_column_map(headers)

            for row in table[1:]:
                row_dict = {}
                for i, header in enumerate(headers):
                    if i < len(row):
                        row_dict[header] = str(row[i]).strip()
                    else:
                        row_dict[header] = ""

                raw_data = dict(row_dict)
                record_dict = self._extract_fields(row_dict, column_map)
                record_dict["raw_data"] = raw_data

                is_valid, error = self.validate_record(record_dict)
                if is_valid:
                    records.append(self._dict_to_record(record_dict))

        return records

    # =========================================================================
    # Vendor Name Normalization
    # =========================================================================

    def normalize_vendor_name(self, name: str, known_vendors: list[str]) -> str:
        """Normalize a vendor name using fuzzy matching against known vendors.

        Uses SequenceMatcher (Levenshtein-like) similarity ratio.
        Returns the best match if ratio >= fuzzy_threshold, otherwise
        returns the original name unchanged.

        Args:
            name: Vendor name to normalize.
            known_vendors: List of canonical vendor names.

        Returns:
            Normalized vendor name (matched or original).
        """
        if not name or not known_vendors:
            return name

        name_lower = name.lower().strip()
        best_match = None
        best_ratio = 0.0

        for vendor in known_vendors:
            ratio = SequenceMatcher(None, name_lower, vendor.lower().strip()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = vendor

        if best_ratio >= self.fuzzy_threshold and best_match:
            return best_match

        return name

    # =========================================================================
    # Pretty Printer (CSV round-trip)
    # =========================================================================

    def pretty_print_csv(self, records: list[ParsedRecord]) -> str:
        """Format ProcurementRecords as standardized CSV.

        Produces CSV with STANDARD_HEADERS columns for round-trip
        serialization (parse -> print -> parse produces equivalent records).

        Args:
            records: List of ParsedRecords to serialize.

        Returns:
            CSV string with standardized headers.
        """
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=STANDARD_HEADERS)
        writer.writeheader()

        for record in records:
            writer.writerow({
                "record_id": record.record_id,
                "vendor_id": record.vendor_id,
                "vendor_name": record.vendor_name,
                "contract_id": record.contract_id,
                "bid_amount": f"{record.bid_amount:.2f}",
                "submission_timestamp": record.submission_timestamp or "",
                "specifications_met": str(record.specifications_met),
                "award_status": record.award_status,
                "government_estimate": f"{record.government_estimate:.2f}" if record.government_estimate else "",
                "geographic_region": record.geographic_region or "",
            })

        return output.getvalue()

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _build_column_map(self, actual_headers: list[str]) -> dict[str, str]:
        """Map actual column headers to standard field names."""
        column_map = {}
        headers_lower = {h.lower().strip().replace(" ", "_"): h for h in actual_headers if h}

        for std_name, aliases in COLUMN_ALIASES.items():
            for alias in aliases:
                if alias in headers_lower:
                    column_map[std_name] = headers_lower[alias]
                    break

        return column_map

    def _extract_fields(self, row: dict, column_map: dict[str, str]) -> dict:
        """Extract standard fields from a row using the column map."""
        result = {}
        for std_name, actual_col in column_map.items():
            value = row.get(actual_col, "").strip() if row.get(actual_col) else ""
            result[std_name] = value
        return result

    def _dict_to_record(self, d: dict) -> ParsedRecord:
        """Convert a validated dict to a ParsedRecord."""
        # Clean bid amount
        bid_str = str(d.get("bid_amount", "0")).replace(",", "").replace("$", "").strip()
        try:
            bid_amount = float(bid_str)
        except (ValueError, TypeError):
            bid_amount = 0.0

        # Clean government estimate
        est_str = str(d.get("government_estimate", "")).replace(",", "").replace("$", "").strip()
        try:
            govt_estimate = float(est_str) if est_str else None
        except (ValueError, TypeError):
            govt_estimate = None

        # Normalize award status
        raw_status = str(d.get("award_status", "lost")).strip().lower()
        award_status = AWARD_STATUS_MAP.get(raw_status, "lost")

        # Parse specifications_met
        specs_raw = str(d.get("specifications_met", "true")).strip().lower()
        specs_met = specs_raw in ("true", "1", "yes", "y", "")

        # Generate record_id if not present
        record_id = d.get("record_id", "") or str(uuid.uuid4())

        # Vendor ID fallback to name-based ID
        vendor_id = d.get("vendor_id", "") or d.get("vendor_name", "unknown").lower().replace(" ", "_")[:50]

        return ParsedRecord(
            record_id=record_id,
            vendor_id=vendor_id,
            vendor_name=d.get("vendor_name", "") or d.get("vendor_id", ""),
            contract_id=d.get("contract_id", ""),
            bid_amount=bid_amount,
            submission_timestamp=d.get("submission_timestamp") or None,
            specifications_met=specs_met,
            award_status=award_status,
            government_estimate=govt_estimate,
            geographic_region=d.get("geographic_region") or None,
            raw_data=d.get("raw_data", {}),
        )

    def _extract_textract_tables(self, response: dict) -> list[list[list[str]]]:
        """Extract table data from Textract AnalyzeDocument response."""
        blocks = response.get("Blocks", [])
        block_map = {b["Id"]: b for b in blocks}

        tables = []
        for block in blocks:
            if block["BlockType"] == "TABLE":
                table = self._parse_textract_table(block, block_map)
                if table:
                    tables.append(table)

        return tables

    def _parse_textract_table(self, table_block: dict, block_map: dict) -> list[list[str]]:
        """Parse a single Textract TABLE block into rows and cells."""
        rows: dict[int, dict[int, str]] = {}

        for rel in table_block.get("Relationships", []):
            if rel["Type"] == "CHILD":
                for child_id in rel["Ids"]:
                    cell = block_map.get(child_id, {})
                    if cell.get("BlockType") == "CELL":
                        row_idx = cell.get("RowIndex", 0)
                        col_idx = cell.get("ColumnIndex", 0)
                        text = self._get_cell_text(cell, block_map)
                        if row_idx not in rows:
                            rows[row_idx] = {}
                        rows[row_idx][col_idx] = text

        if not rows:
            return []
        max_row = max(rows.keys())
        max_col = max(max(cols.keys()) for cols in rows.values()) if rows else 0

        result = []
        for r in range(1, max_row + 1):
            row_data = []
            for c in range(1, max_col + 1):
                row_data.append(rows.get(r, {}).get(c, ""))
            result.append(row_data)

        return result

    def _get_cell_text(self, cell_block: dict, block_map: dict) -> str:
        """Extract text content from a Textract CELL block."""
        words = []
        for rel in cell_block.get("Relationships", []):
            if rel["Type"] == "CHILD":
                for word_id in rel["Ids"]:
                    word_block = block_map.get(word_id, {})
                    if word_block.get("BlockType") in ("WORD", "SELECTION_ELEMENT"):
                        text = word_block.get("Text", "")
                        if text:
                            words.append(text)
        return " ".join(words)
