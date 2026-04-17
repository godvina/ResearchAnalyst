"""Pipeline ingestion — sends documents through the existing ingest API and polls Step Functions."""

import base64
import json
import logging
import math
import time
import urllib.request
import urllib.error

import boto3

from scripts.batch_loader.config import BatchConfig

logger = logging.getLogger(__name__)

TERMINAL_STATES = {"SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"}


class PipelineIngestion:
    """Sends non-blank documents through the existing ingest API in sub-batches."""

    def __init__(self, config: BatchConfig):
        self.config = config

    def send_sub_batches(self, documents: list[tuple[str, str]]) -> list[str]:
        """Send documents in sub-batches to ingest API. Returns execution ARNs.

        Each document is a (filename, text) tuple. Documents are partitioned into
        sub-batches of config.sub_batch_size, sent via POST /case-files/{case_id}/ingest,
        with config.sub_batch_delay seconds between calls.
        """
        if not documents:
            return []

        execution_arns: list[str] = []
        sub_batch_size = self.config.sub_batch_size
        total_batches = math.ceil(len(documents) / sub_batch_size)

        for i in range(0, len(documents), sub_batch_size):
            batch = documents[i : i + sub_batch_size]
            batch_num = (i // sub_batch_size) + 1

            arn = self._send_single_batch(self.config.case_id, batch)
            if arn:
                execution_arns.append(arn)
                short_arn = arn.split(":")[-1] if ":" in str(arn) else arn
                print(f"  Sub-batch {batch_num}/{total_batches}: {len(batch)} docs -> {short_arn}")
            else:
                print(f"  Sub-batch {batch_num}/{total_batches}: no ARN returned")

            # Delay between sub-batches (skip after last batch)
            if i + sub_batch_size < len(documents):
                time.sleep(self.config.sub_batch_delay)

        return execution_arns

    def poll_executions(self, execution_arns: list[str]) -> dict:
        """Poll Step Functions until all reach terminal state.

        Uses exponential backoff: starts at config.poll_initial_delay, doubles each
        iteration, capped at config.poll_max_delay.

        Returns dict mapping {arn: status}.
        """
        if not execution_arns:
            return {}

        sfn_client = boto3.client("stepfunctions", region_name="us-east-1")
        statuses: dict[str, str] = {arn: "RUNNING" for arn in execution_arns}
        iteration = 0

        while True:
            # Check all non-terminal executions
            pending = [arn for arn, status in statuses.items() if status not in TERMINAL_STATES]
            if not pending:
                break

            for arn in pending:
                try:
                    resp = sfn_client.describe_execution(executionArn=arn)
                    statuses[arn] = resp["status"]
                except Exception as e:
                    print(f"  Poll error for {arn}: {e}")

            # Check again after updates
            pending = [arn for arn, status in statuses.items() if status not in TERMINAL_STATES]
            if not pending:
                break

            delay = self.compute_backoff_delay(
                iteration, self.config.poll_initial_delay, self.config.poll_max_delay
            )
            print(f"  Polling: {len(pending)} still running, waiting {delay:.0f}s...")
            time.sleep(delay)
            iteration += 1

        return statuses

    def _send_single_batch(self, case_id: str, texts: list[tuple[str, str]]) -> str | None:
        """POST a single sub-batch to the ingest API. Returns execution ARN.

        Each text tuple is (filename, text_content). Matches the phase1/phase2 pattern:
        - base64-encode the text
        - POST to {api_url}/case-files/{case_id}/ingest with {"files": [...]}
        - Response contains "execution_arn" and "documents_uploaded"

        Retries on HTTP 429 and 5xx errors up to config.max_retries with
        exponential backoff. Logs each retry attempt.
        """
        files_payload = []
        for filename, text_content in texts:
            text_b64 = base64.b64encode(text_content.encode("utf-8")).decode("ascii")
            files_payload.append({"filename": filename, "content_base64": text_b64})

        if not files_payload:
            return None

        url = f"{self.config.api_url}/case-files/{case_id}/ingest"
        body = json.dumps({"files": files_payload}).encode()

        last_error = None
        for attempt in range(self.config.max_retries):
            try:
                req = urllib.request.Request(url, data=body, method="POST")
                req.add_header("Content-Type", "application/json")
                with urllib.request.urlopen(req, timeout=120) as resp:
                    result = json.loads(resp.read().decode())
                    return result.get("execution_arn")
            except urllib.error.HTTPError as e:
                last_error = e
                # Retry on 429 (throttled) and 5xx (server error)
                if e.code == 429 or e.code >= 500:
                    if attempt < self.config.max_retries - 1:
                        backoff = 2 ** attempt
                        logger.warning(
                            "Retry %d/%d for HTTP %d: %s, waiting %ds",
                            attempt + 1,
                            self.config.max_retries,
                            e.code,
                            e,
                            backoff,
                        )
                        time.sleep(backoff)
                        continue
                # Non-retryable HTTP error (4xx other than 429)
                logger.error("Non-retryable HTTP %d for ingest: %s", e.code, e)
                break
            except Exception as e:
                last_error = e
                if attempt < self.config.max_retries - 1:
                    backoff = 2 ** attempt
                    logger.warning(
                        "Retry %d/%d: %s, waiting %ds",
                        attempt + 1,
                        self.config.max_retries,
                        e,
                        backoff,
                    )
                    time.sleep(backoff)

        logger.error("Failed after %d attempts: %s", self.config.max_retries, last_error)
        return None

    @staticmethod
    def compute_backoff_delay(iteration: int, initial_delay: float, max_delay: float) -> float:
        """Compute exponential backoff delay for a given iteration.

        Returns min(initial_delay * 2^iteration, max_delay).
        """
        return min(initial_delay * (2 ** iteration), max_delay)
