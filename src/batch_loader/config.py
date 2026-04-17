"""Batch loader configuration and CLI argument parsing."""

import argparse
from dataclasses import dataclass, field


@dataclass
class BatchConfig:
    """Configuration for the incremental batch loader."""

    batch_size: int = 5000
    case_id: str = "ed0b6c27-3b6b-4255-b9d0-efe8f4383a99"
    sub_batch_size: int = 50
    dry_run: bool = False
    confirm: bool = False
    no_entity_resolution: bool = False
    max_batches: int = 1
    ocr_threshold: int = 50
    blank_threshold: int = 10
    source_prefixes: list[str] = field(default_factory=lambda: ["pdfs/", "bw-documents/"])
    source_bucket: str = "doj-cases-974220725866-us-east-1"
    data_lake_bucket: str = "research-analyst-data-lake-974220725866"
    api_url: str = "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1"
    sub_batch_delay: float = 2.0
    max_retries: int = 3
    failure_threshold: float = 0.10
    poll_initial_delay: int = 30
    poll_max_delay: int = 300


def parse_args() -> BatchConfig:
    """Parse CLI arguments and return a BatchConfig instance."""
    parser = argparse.ArgumentParser(
        description="Incremental Batch Loader — process raw PDFs through the DOJ pipeline"
    )
    parser.add_argument(
        "--batch-size", type=int, default=5000,
        help="Number of raw PDFs per batch (default: 5000)",
    )
    parser.add_argument(
        "--case-id", type=str, default="ed0b6c27-3b6b-4255-b9d0-efe8f4383a99",
        help="Target case ID (default: ed0b6c27-3b6b-4255-b9d0-efe8f4383a99)",
    )
    parser.add_argument(
        "--sub-batch-size", type=int, default=50,
        help="Documents per ingest API call (default: 50)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=False,
        help="Preview what would be processed without making changes",
    )
    parser.add_argument(
        "--confirm", action="store_true", default=False,
        help="Skip interactive confirmation prompt",
    )
    parser.add_argument(
        "--no-entity-resolution", action="store_true", default=False,
        help="Skip entity resolution after batch completes",
    )
    parser.add_argument(
        "--max-batches", type=int, default=1,
        help="Maximum number of consecutive batches to run (default: 1)",
    )
    parser.add_argument(
        "--ocr-threshold", type=int, default=50,
        help="Characters per page below which Textract OCR is used (default: 50)",
    )
    parser.add_argument(
        "--blank-threshold", type=int, default=10,
        help="Non-whitespace characters below which a document is blank (default: 10)",
    )
    parser.add_argument(
        "--source-prefixes", type=str, nargs="+", default=["pdfs/", "bw-documents/"],
        help="S3 prefixes to scan for raw documents (default: pdfs/ bw-documents/)",
    )
    parser.add_argument(
        "--source-bucket", type=str, default=None,
        help="S3 bucket to scan for raw documents (default: doj-cases-974220725866-us-east-1)",
    )

    args = parser.parse_args()

    return BatchConfig(
        batch_size=args.batch_size,
        case_id=args.case_id,
        sub_batch_size=args.sub_batch_size,
        dry_run=args.dry_run,
        confirm=args.confirm,
        no_entity_resolution=args.no_entity_resolution,
        max_batches=args.max_batches,
        ocr_threshold=args.ocr_threshold,
        blank_threshold=args.blank_threshold,
        source_prefixes=args.source_prefixes,
        source_bucket=args.source_bucket or "doj-cases-974220725866-us-east-1",
    )
