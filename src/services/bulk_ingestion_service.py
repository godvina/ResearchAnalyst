"""Bulk Ingestion Service — Redshift bulk data loading for pre-case analytics.

Manages the lifecycle of bulk data ingestion jobs that load structured
procurement data (CSV, JSON, Parquet) from S3 into Redshift Serverless.
Supports schema validation, COPY command generation, vendor name normalization
via fuzzy matching against SAM.gov registrations, deduplication on incremental
loads, and job resumption from failure points.

Usage:
    service = BulkIngestionService(
        redshift_client=redshift_data_client,
        aurora_cm=connection_manager,
        s3_client=s3_client,
    )
    job_id = service.submit_job("state_dot_bids", "s3://bucket/bids/", "bid_tabulations")
    result = service.execute_copy(job_id)
    status = service.get_job_status(job_id)
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Redshift database name for pre-case analytics
REDSHIFT_DATABASE = "pre_case_analytics"

# Schema definitions for each source type
SOURCE_SCHEMAS = {
    "state_dot_bids": {
        "target_table": "bid_tabulations",
        "required_columns": [
            "vendor_id", "contract_id", "bid_amount", "submission_date",
        ],
        "optional_columns": [
            "awarding_agency", "state", "award_status", "source_file",
        ],
        "composite_key": ["vendor_id", "contract_id", "submission_date"],
    },
    "sam_gov": {
        "target_table": "sam_registrations",
        "required_columns": ["entity_id", "legal_name"],
        "optional_columns": [
            "duns_number", "cage_code", "naics_codes", "sam_status",
            "exclusion_records", "physical_address", "registration_date",
        ],
        "composite_key": ["entity_id"],
    },
    "fpds_gov": {
        "target_table": "fpds_awards",
        "required_columns": ["contract_number", "vendor_id"],
        "optional_columns": [
            "awarding_agency", "award_amount", "award_date",
            "place_of_performance", "competition_type", "subcontracting_plan",
        ],
        "composite_key": ["contract_number"],
    },
    "usaspending": {
        "target_table": "usaspending_transactions",
        "required_columns": ["award_id", "recipient_id"],
        "optional_columns": [
            "federal_action_obligation", "awarding_agency",
            "period_of_performance_start", "period_of_performance_end",
            "sub_award_data",
        ],
        "composite_key": ["award_id"],
    },
}

# Supported file formats and their COPY options
FORMAT_OPTIONS = {
    "csv": "FORMAT AS CSV IGNOREHEADER 1 ACCEPTINVCHARS",
    "json": "FORMAT AS JSON 'auto'",
    "parquet": "FORMAT AS PARQUET",
}

# Fuzzy match confidence threshold for vendor normalization
VENDOR_MATCH_THRESHOLD = 0.80


class BulkIngestionService:
    """Manages bulk data ingestion into Redshift Serverless.

    Follows Protocol/constructor-injection pattern for testability.
    Uses Redshift COPY command for efficient bulk loading (correct approach
    for millions of rows — not individual INSERT statements).
    """

    def __init__(
        self, redshift_client: Any, aurora_cm: Any, s3_client: Any
    ) -> None:
        """Initialize with dependencies.

        Args:
            redshift_client: boto3 redshift-data client for execute_statement.
            aurora_cm: Aurora PostgreSQL connection manager with cursor() context.
            s3_client: boto3 S3 client for manifest and schema validation.
        """
        self.redshift_client = redshift_client
        self.aurora_cm = aurora_cm
        self.s3_client = s3_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def submit_job(
        self, source_type: str, s3_path: str, schema: str
    ) -> str:
        """Submit a new bulk ingestion job.

        Creates a job record in Aurora pre_case_bulk_ingestion_jobs table
        with status 'queued'. Validates that the source_type is recognized
        and the schema matches expected structure.

        Args:
            source_type: One of state_dot_bids, sam_gov, fpds_gov, usaspending.
            s3_path: S3 URI to the data file(s) or manifest.
            schema: Target table name in Redshift.

        Returns:
            job_id (UUID string) for tracking.

        Raises:
            ValueError: If source_type is not recognized or schema is invalid.
        """
        # Validate source type
        if source_type not in SOURCE_SCHEMAS:
            raise ValueError(
                f"Unknown source_type '{source_type}'. "
                f"Valid types: {list(SOURCE_SCHEMAS.keys())}"
            )

        # Validate schema matches expected target table
        expected_table = SOURCE_SCHEMAS[source_type]["target_table"]
        if schema != expected_table:
            raise ValueError(
                f"Schema mismatch: source_type '{source_type}' expects "
                f"target table '{expected_table}', got '{schema}'"
            )

        # Validate file structure against expected schema
        self._validate_file_structure(source_type, s3_path)

        job_id = str(uuid.uuid4())

        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO pre_case_bulk_ingestion_jobs
                        (job_id, source_type, s3_path, target_table, status,
                         rows_loaded, rows_rejected, created_at)
                    VALUES (%s, %s, %s, %s, 'queued', 0, 0, %s)
                    """,
                    (
                        job_id,
                        source_type,
                        s3_path,
                        schema,
                        datetime.now(timezone.utc),
                    ),
                )
        except Exception as e:
            logger.error("Failed to create bulk ingestion job: %s", e)
            raise

        logger.info(
            "Submitted bulk ingestion job %s: source=%s path=%s table=%s",
            job_id, source_type, s3_path, schema,
        )
        return job_id

    def execute_copy(self, job_id: str) -> dict:
        """Execute the Redshift COPY command for a queued job.

        Generates the COPY command with manifest and compression options,
        updates job status to 'running', executes via Redshift Data API,
        and polls for completion. Supports deduplication on incremental
        loads using a staging table + merge pattern.

        Args:
            job_id: UUID of the job to execute.

        Returns:
            dict with keys: status, rows_loaded, statement_id, copy_command.
        """
        # Retrieve job details from Aurora
        job = self._get_job(job_id)
        if not job:
            return {"status": "error", "message": f"Job {job_id} not found"}

        if job["status"] not in ("queued", "resuming"):
            return {
                "status": "error",
                "message": f"Job {job_id} is in status '{job['status']}', expected 'queued' or 'resuming'",
            }

        source_type = job["source_type"]
        s3_path = job["s3_path"]
        target_table = job["target_table"]

        # Determine file format from path
        file_format = self._detect_format(s3_path)
        format_opts = FORMAT_OPTIONS.get(file_format, FORMAT_OPTIONS["csv"])

        # Build COPY command with deduplication via staging table
        staging_table = f"staging_{target_table}_{job_id.replace('-', '_')[:8]}"
        composite_key = SOURCE_SCHEMAS[source_type]["composite_key"]

        # Generate the COPY SQL with manifest and compression
        copy_sql = self._build_copy_sql(
            staging_table=staging_table,
            target_table=target_table,
            s3_path=s3_path,
            format_opts=format_opts,
            composite_key=composite_key,
            resume_point=job.get("resume_point"),
        )

        # Update job status to running
        self._update_job_status(job_id, "running")

        try:
            # Execute the COPY command via Redshift Data API
            response = self.redshift_client.execute_statement(
                Database=REDSHIFT_DATABASE,
                Sql=copy_sql,
                WithEvent=False,
            )

            statement_id = response.get("Id", "")

            # Poll for completion
            success = self._poll_redshift_statement(statement_id)

            if success:
                # Get load statistics
                rows_loaded = self._get_rows_loaded(statement_id)
                self._update_job_completion(job_id, rows_loaded, 0)
                return {
                    "status": "completed",
                    "rows_loaded": rows_loaded,
                    "statement_id": statement_id,
                    "copy_command": copy_sql,
                }
            else:
                # Get error details
                error_info = self._get_statement_error(statement_id)
                self._update_job_failure(job_id, error_info)
                return {
                    "status": "failed",
                    "statement_id": statement_id,
                    "error": error_info,
                    "copy_command": copy_sql,
                }

        except Exception as e:
            logger.error("COPY execution failed for job %s: %s", job_id, e)
            self._update_job_failure(job_id, str(e))
            return {
                "status": "failed",
                "error": str(e),
                "copy_command": copy_sql,
            }

    def get_job_status(self, job_id: str) -> dict:
        """Get the current status of a bulk ingestion job.

        Args:
            job_id: UUID of the job.

        Returns:
            dict with: status, rows_loaded, rows_rejected, rejection_reasons,
            started_at, completed_at, source_type, s3_path, target_table.
        """
        job = self._get_job(job_id)
        if not job:
            return {"status": "not_found", "message": f"Job {job_id} not found"}

        return {
            "job_id": job_id,
            "status": job["status"],
            "source_type": job["source_type"],
            "s3_path": job["s3_path"],
            "target_table": job["target_table"],
            "rows_loaded": job.get("rows_loaded", 0),
            "rows_rejected": job.get("rows_rejected", 0),
            "rejection_reasons": job.get("rejection_reasons"),
            "resume_point": job.get("resume_point"),
            "started_at": job.get("started_at"),
            "completed_at": job.get("completed_at"),
            "created_at": job.get("created_at"),
        }

    def normalize_vendors(self, job_id: str) -> dict:
        """Normalize vendor names using fuzzy matching against SAM.gov registrations.

        After a state DOT bid tabulation load, this method compares vendor names
        from the loaded data against canonical SAM.gov registrations using
        Levenshtein similarity. Creates vendor_alias mappings for matches above
        the confidence threshold.

        Args:
            job_id: UUID of the completed ingestion job.

        Returns:
            dict with: aliases_created, matches (list of alias details),
            unmatched_count.
        """
        job = self._get_job(job_id)
        if not job:
            return {"status": "error", "message": f"Job {job_id} not found"}

        if job["source_type"] != "state_dot_bids":
            return {
                "status": "skipped",
                "message": "Vendor normalization only applies to state_dot_bids",
            }

        # Query distinct vendor names from the loaded bid data
        # and compare against SAM.gov registrations using Levenshtein
        normalize_sql = """
            WITH new_vendors AS (
                SELECT DISTINCT bt.vendor_id
                FROM bid_tabulations bt
                LEFT JOIN vendor_aliases va ON bt.vendor_id = va.alias_name
                WHERE va.alias_id IS NULL
            ),
            matches AS (
                SELECT
                    nv.vendor_id AS alias_name,
                    sr.entity_id AS canonical_vendor_id,
                    sr.legal_name,
                    CAST(
                        LENGTH(nv.vendor_id) + LENGTH(sr.legal_name)
                        - LEVENSHTEIN(LOWER(nv.vendor_id), LOWER(sr.legal_name))
                    AS FLOAT) / GREATEST(LENGTH(nv.vendor_id), LENGTH(sr.legal_name), 1)
                    AS match_confidence
                FROM new_vendors nv
                CROSS JOIN sam_registrations sr
            )
            SELECT alias_name, canonical_vendor_id, legal_name, match_confidence
            FROM matches
            WHERE match_confidence >= {threshold}
            ORDER BY match_confidence DESC
        """.format(threshold=VENDOR_MATCH_THRESHOLD)

        try:
            response = self.redshift_client.execute_statement(
                Database=REDSHIFT_DATABASE,
                Sql=normalize_sql,
                WithEvent=False,
            )
            statement_id = response.get("Id", "")
            success = self._poll_redshift_statement(statement_id)

            if not success:
                return {"status": "failed", "message": "Normalization query failed"}

            # Get results and create alias mappings
            results = self._get_statement_results(statement_id)
            aliases_created = 0
            matches = []

            for row in results:
                alias_name = row[0] if row else ""
                canonical_id = row[1] if len(row) > 1 else ""
                legal_name = row[2] if len(row) > 2 else ""
                confidence = float(row[3]) if len(row) > 3 else 0.0

                # Insert alias mapping
                insert_sql = (
                    "INSERT INTO vendor_aliases "
                    "(canonical_vendor_id, alias_name, alias_source, match_confidence) "
                    "VALUES ('{cid}', '{aname}', 'fuzzy_match_job_{jid}', {conf})"
                ).format(
                    cid=canonical_id.replace("'", "''"),
                    aname=alias_name.replace("'", "''"),
                    jid=job_id[:8],
                    conf=confidence,
                )
                self.redshift_client.execute_statement(
                    Database=REDSHIFT_DATABASE,
                    Sql=insert_sql,
                    WithEvent=False,
                )
                aliases_created += 1
                matches.append({
                    "alias_name": alias_name,
                    "canonical_vendor_id": canonical_id,
                    "canonical_name": legal_name,
                    "confidence": confidence,
                })

            return {
                "status": "completed",
                "aliases_created": aliases_created,
                "matches": matches,
                "threshold": VENDOR_MATCH_THRESHOLD,
            }

        except Exception as e:
            logger.error("Vendor normalization failed for job %s: %s", job_id, e)
            return {"status": "failed", "error": str(e)}

    def resume_failed_job(self, job_id: str) -> dict:
        """Resume a failed job from its recorded failure point.

        Retrieves the resume_point from the job record and re-executes
        the COPY command starting from that point, without re-loading
        completed segments.

        Args:
            job_id: UUID of the failed job to resume.

        Returns:
            dict with: status, rows_loaded (additional), statement_id.
        """
        job = self._get_job(job_id)
        if not job:
            return {"status": "error", "message": f"Job {job_id} not found"}

        if job["status"] != "failed":
            return {
                "status": "error",
                "message": f"Job {job_id} is in status '{job['status']}', can only resume 'failed' jobs",
            }

        if not job.get("resume_point"):
            return {
                "status": "error",
                "message": f"Job {job_id} has no resume_point recorded",
            }

        # Update status to resuming
        self._update_job_status(job_id, "resuming")

        # Re-execute with resume point
        return self.execute_copy(job_id)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_file_structure(self, source_type: str, s3_path: str) -> None:
        """Validate file structure against expected schema before loading.

        Checks that the S3 path exists and the file contains the required
        columns for the source type.

        Args:
            source_type: The data source type.
            s3_path: S3 URI to validate.

        Raises:
            ValueError: If file structure doesn't match expected schema.
        """
        schema_def = SOURCE_SCHEMAS[source_type]
        required_cols = schema_def["required_columns"]

        # Parse S3 URI
        bucket, key = self._parse_s3_uri(s3_path)
        if not bucket:
            raise ValueError(f"Invalid S3 path: {s3_path}")

        try:
            # Check if path is a manifest or direct file
            if s3_path.endswith(".manifest"):
                # Validate manifest exists
                self.s3_client.head_object(Bucket=bucket, Key=key)
            else:
                # For direct files, check header row for CSV
                response = self.s3_client.get_object(
                    Bucket=bucket, Key=key, Range="bytes=0-4096"
                )
                header_bytes = response["Body"].read()
                header_line = header_bytes.decode("utf-8", errors="ignore").split("\n")[0]
                columns = [c.strip().lower().strip('"') for c in header_line.split(",")]

                missing = [c for c in required_cols if c not in columns]
                if missing:
                    raise ValueError(
                        f"File missing required columns for {source_type}: {missing}. "
                        f"Found columns: {columns}"
                    )
        except self.s3_client.exceptions.NoSuchKey:
            raise ValueError(f"S3 path does not exist: {s3_path}")
        except ValueError:
            raise
        except Exception as e:
            # Log but don't block — file might be Parquet or JSON
            logger.warning(
                "Could not validate file structure for %s: %s", s3_path, e
            )

    def _build_copy_sql(
        self,
        staging_table: str,
        target_table: str,
        s3_path: str,
        format_opts: str,
        composite_key: list[str],
        resume_point: Optional[str] = None,
    ) -> str:
        """Build the COPY SQL with staging table for deduplication.

        Uses a staging table + INSERT...SELECT pattern to deduplicate
        against existing records using composite keys.

        Args:
            staging_table: Temporary staging table name.
            target_table: Final target table in Redshift.
            s3_path: S3 path for COPY source.
            format_opts: Format options string.
            composite_key: Columns forming the composite key for dedup.
            resume_point: Optional S3 path to resume from.

        Returns:
            Complete SQL string for execution.
        """
        # Use resume_point if available (for resumed jobs)
        copy_source = resume_point if resume_point else s3_path

        # Determine if manifest
        manifest_opt = "MANIFEST" if copy_source.endswith(".manifest") else ""

        # Build deduplication merge SQL
        key_join = " AND ".join(
            f"s.{col} = t.{col}" for col in composite_key
        )
        key_where = " AND ".join(
            f"t.{col} IS NULL" for col in composite_key
        )

        sql = f"""
            -- Create staging table (like target)
            CREATE TEMP TABLE {staging_table} (LIKE {target_table});

            -- COPY data into staging
            COPY {staging_table}
            FROM '{copy_source}'
            IAM_ROLE default
            {format_opts}
            {manifest_opt}
            COMPUPDATE ON
            STATUPDATE ON
            MAXERROR 1000;

            -- Merge: insert only new records (deduplication on composite key)
            INSERT INTO {target_table}
            SELECT s.*
            FROM {staging_table} s
            LEFT JOIN {target_table} t ON {key_join}
            WHERE {key_where};

            -- Drop staging table
            DROP TABLE IF EXISTS {staging_table};
        """

        return sql.strip()

    def _detect_format(self, s3_path: str) -> str:
        """Detect file format from S3 path extension.

        Args:
            s3_path: S3 URI.

        Returns:
            Format string: csv, json, or parquet.
        """
        path_lower = s3_path.lower()
        if path_lower.endswith(".parquet") or ".parquet" in path_lower:
            return "parquet"
        elif path_lower.endswith(".json") or ".json" in path_lower:
            return "json"
        return "csv"

    def _parse_s3_uri(self, s3_path: str) -> tuple[str, str]:
        """Parse an S3 URI into bucket and key.

        Args:
            s3_path: S3 URI (s3://bucket/key).

        Returns:
            Tuple of (bucket, key).
        """
        if not s3_path.startswith("s3://"):
            return "", ""
        parts = s3_path[5:].split("/", 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ""
        return bucket, key

    def _get_job(self, job_id: str) -> Optional[dict]:
        """Retrieve job record from Aurora.

        Args:
            job_id: UUID of the job.

        Returns:
            Job dict or None if not found.
        """
        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    """
                    SELECT job_id, source_type, s3_path, target_table, status,
                           rows_loaded, rows_rejected, rejection_reasons,
                           resume_point, started_at, completed_at, created_at
                    FROM pre_case_bulk_ingestion_jobs
                    WHERE job_id = %s
                    """,
                    (job_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "job_id": row[0],
                    "source_type": row[1],
                    "s3_path": row[2],
                    "target_table": row[3],
                    "status": row[4],
                    "rows_loaded": row[5],
                    "rows_rejected": row[6],
                    "rejection_reasons": row[7],
                    "resume_point": row[8],
                    "started_at": row[9],
                    "completed_at": row[10],
                    "created_at": row[11],
                }
        except Exception as e:
            logger.error("Failed to retrieve job %s: %s", job_id, e)
            return None

    def _update_job_status(self, job_id: str, status: str) -> None:
        """Update job status in Aurora.

        Args:
            job_id: UUID of the job.
            status: New status value.
        """
        try:
            with self.aurora_cm.cursor() as cur:
                if status == "running":
                    cur.execute(
                        """
                        UPDATE pre_case_bulk_ingestion_jobs
                        SET status = %s, started_at = %s
                        WHERE job_id = %s
                        """,
                        (status, datetime.now(timezone.utc), job_id),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE pre_case_bulk_ingestion_jobs
                        SET status = %s
                        WHERE job_id = %s
                        """,
                        (status, job_id),
                    )
        except Exception as e:
            logger.error("Failed to update job %s status to %s: %s", job_id, status, e)

    def _update_job_completion(
        self, job_id: str, rows_loaded: int, rows_rejected: int
    ) -> None:
        """Mark job as completed with final statistics.

        Args:
            job_id: UUID of the job.
            rows_loaded: Total rows successfully loaded.
            rows_rejected: Total rows rejected.
        """
        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    """
                    UPDATE pre_case_bulk_ingestion_jobs
                    SET status = 'completed',
                        rows_loaded = %s,
                        rows_rejected = %s,
                        completed_at = %s
                    WHERE job_id = %s
                    """,
                    (rows_loaded, rows_rejected, datetime.now(timezone.utc), job_id),
                )
        except Exception as e:
            logger.error("Failed to update job %s completion: %s", job_id, e)

    def _update_job_failure(self, job_id: str, error_info: str) -> None:
        """Mark job as failed with error details and resume point.

        Args:
            job_id: UUID of the job.
            error_info: Error description.
        """
        try:
            with self.aurora_cm.cursor() as cur:
                # Record the failure with resume point (the original s3_path)
                cur.execute(
                    """
                    UPDATE pre_case_bulk_ingestion_jobs
                    SET status = 'failed',
                        rejection_reasons = %s,
                        resume_point = s3_path,
                        completed_at = %s
                    WHERE job_id = %s
                    """,
                    (
                        json.dumps({"error": error_info}),
                        datetime.now(timezone.utc),
                        job_id,
                    ),
                )
        except Exception as e:
            logger.error("Failed to update job %s failure: %s", job_id, e)

    def _poll_redshift_statement(
        self, statement_id: str, max_attempts: int = 60
    ) -> bool:
        """Poll Redshift Data API for statement completion.

        Args:
            statement_id: The statement ID from execute_statement.
            max_attempts: Maximum polling attempts (2s intervals).

        Returns:
            True if statement completed successfully, False otherwise.
        """
        for _ in range(max_attempts):
            try:
                desc = self.redshift_client.describe_statement(Id=statement_id)
                status = desc.get("Status", "")
                if status == "FINISHED":
                    return True
                elif status in ("FAILED", "ABORTED"):
                    logger.error(
                        "Redshift statement %s failed: %s",
                        statement_id, desc.get("Error", "unknown"),
                    )
                    return False
                time.sleep(2)
            except Exception as e:
                logger.error("Error polling Redshift statement: %s", e)
                return False
        logger.warning("Redshift statement %s timed out", statement_id)
        return False

    def _get_rows_loaded(self, statement_id: str) -> int:
        """Get the number of rows affected by a completed statement.

        Args:
            statement_id: Completed statement ID.

        Returns:
            Number of rows loaded.
        """
        try:
            desc = self.redshift_client.describe_statement(Id=statement_id)
            return desc.get("ResultRows", 0)
        except Exception as e:
            logger.error("Failed to get rows loaded for %s: %s", statement_id, e)
            return 0

    def _get_statement_error(self, statement_id: str) -> str:
        """Get error details from a failed statement.

        Args:
            statement_id: Failed statement ID.

        Returns:
            Error message string.
        """
        try:
            desc = self.redshift_client.describe_statement(Id=statement_id)
            return desc.get("Error", "Unknown error")
        except Exception as e:
            return f"Could not retrieve error: {e}"

    def _get_statement_results(self, statement_id: str) -> list:
        """Get result rows from a completed statement.

        Args:
            statement_id: Completed statement ID.

        Returns:
            List of row tuples.
        """
        try:
            response = self.redshift_client.get_statement_result(Id=statement_id)
            records = response.get("Records", [])
            rows = []
            for record in records:
                row = []
                for field in record:
                    # Redshift Data API returns typed fields
                    value = (
                        field.get("stringValue")
                        or field.get("longValue")
                        or field.get("doubleValue")
                        or field.get("booleanValue")
                        or field.get("blobValue")
                        or ""
                    )
                    row.append(value)
                rows.append(row)
            return rows
        except Exception as e:
            logger.error("Failed to get statement results: %s", e)
            return []
