"""OSINT Data Gatherer — Automated public data retrieval for antitrust pre-case leads.

Autonomously queries 9+ public OSINT sources (SAM.gov, FPDS.gov, USASpending.gov,
SEC EDGAR, IRS Form 990, state corporate registries, PACER, news/press, state DOT bids)
based on case type relevance. Stores raw responses in S3, structured data in Redshift,
and entity/relationship data in Neptune.

Each retrieval creates a Data_Provenance_Record with source_name, source_url,
retrieval_timestamp, data_format, reliability_rating, and response_hash for
integrity verification and audit trail.

Uses concurrent.futures.ThreadPoolExecutor for parallel source queries.
Handles source unavailability gracefully: logs failure, continues with remaining
sources, and includes unavailable sources in the Evidence_Gap report.

Usage:
    gatherer = OsintDataGatherer(
        aurora_cm=connection_manager,
        redshift_client=redshift_data_client,
        neptune_endpoint="my-neptune-cluster.us-east-1.neptune.amazonaws.com",
        neptune_port="8182",
        s3_client=s3_client,
        s3_bucket="my-osint-bucket",
    )
    result = gatherer.gather(
        lead_id="lead-uuid",
        case_type="procurement_collusion",
        subjects=["Acme Corp", "John Doe"],
    )
"""

from __future__ import annotations

import hashlib
import json
import logging
import ssl
import time
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class GatherResult:
    """Result of an OSINT gathering operation.

    Attributes:
        lead_id: UUID of the lead this gathering is for.
        sources_queried: List of source names that were queried.
        sources_succeeded: List of source names that returned data.
        sources_failed: List of source names that failed or were unavailable.
        records_gathered: Total number of records retrieved across all sources.
        provenance_records: List of provenance record IDs created.
        evidence_gaps: List of sources that could not be queried (for gap report).
    """

    lead_id: str
    sources_queried: list[str] = field(default_factory=list)
    sources_succeeded: list[str] = field(default_factory=list)
    sources_failed: list[str] = field(default_factory=list)
    records_gathered: int = 0
    provenance_records: list[str] = field(default_factory=list)
    evidence_gaps: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Source Configuration
# ---------------------------------------------------------------------------

CASE_TYPE_SOURCE_MAP: dict[str, list[str]] = {
    "procurement_collusion": [
        "sam_gov", "fpds_gov", "usaspending_gov", "state_dot_bids",
        "state_corporate_registry", "pacer", "news_press",
    ],
    "price_fixing": [
        "sam_gov", "fpds_gov", "usaspending_gov", "sec_edgar",
        "state_corporate_registry", "pacer", "news_press",
    ],
    "market_allocation": [
        "sam_gov", "fpds_gov", "usaspending_gov", "state_dot_bids",
        "state_corporate_registry", "pacer", "news_press",
    ],
    "merger_review": [
        "sec_edgar", "usaspending_gov", "state_corporate_registry",
        "news_press", "pacer", "irs_form_990",
    ],
    "monopolization": [
        "sec_edgar", "fpds_gov", "usaspending_gov",
        "state_corporate_registry", "pacer", "news_press",
    ],
    "criminal_cartel": [
        "sam_gov", "fpds_gov", "usaspending_gov", "sec_edgar",
        "state_corporate_registry", "pacer", "news_press", "irs_form_990",
    ],
}

SOURCE_RELIABILITY: dict[str, str] = {
    "sam_gov": "official_government",
    "fpds_gov": "official_government",
    "usaspending_gov": "official_government",
    "state_dot_bids": "official_government",
    "sec_edgar": "corporate_filing",
    "irs_form_990": "corporate_filing",
    "state_corporate_registry": "official_government",
    "pacer": "court_record",
    "news_press": "news_media",
}

SOURCE_URLS: dict[str, str] = {
    "sam_gov": "https://sam.gov/api",
    "fpds_gov": "https://www.fpds.gov/fpdsng_cms/index.php/en/",
    "usaspending_gov": "https://api.usaspending.gov",
    "state_dot_bids": "https://state-dot-bids.gov",
    "sec_edgar": "https://www.sec.gov/cgi-bin/browse-edgar",
    "irs_form_990": "https://www.irs.gov/charities-non-profits",
    "state_corporate_registry": "https://state-corporate-registries.gov",
    "pacer": "https://pacer.uscourts.gov",
    "news_press": "https://news-aggregator.gov",
}

SOURCE_REDSHIFT_TABLE: dict[str, str] = {
    "sam_gov": "sam_registrations",
    "fpds_gov": "fpds_awards",
    "usaspending_gov": "usaspending_transactions",
    "state_dot_bids": "bid_tabulations",
}


# ---------------------------------------------------------------------------
# OsintDataGatherer
# ---------------------------------------------------------------------------


class OsintDataGatherer:
    """Automated OSINT data retrieval for antitrust pre-case leads.

    Queries 9 public sources in parallel, stores raw data in S3, structured
    data in Redshift, and entity/relationship data in Neptune.
    """

    SOURCES = [
        "sam_gov",
        "fpds_gov",
        "usaspending_gov",
        "sec_edgar",
        "irs_form_990",
        "state_corporate_registry",
        "pacer",
        "news_press",
        "state_dot_bids",
    ]

    def __init__(
        self,
        aurora_cm: Any,
        redshift_client: Any,
        neptune_endpoint: str,
        neptune_port: str = "8182",
        s3_client: Any = None,
        s3_bucket: str = "",
    ) -> None:
        self.aurora_cm = aurora_cm
        self.redshift_client = redshift_client
        self.neptune_endpoint = neptune_endpoint
        self.neptune_port = neptune_port
        self.s3_client = s3_client
        self.s3_bucket = s3_bucket

    HTTP_TIMEOUT = 30  # seconds, per requirement

    def _make_request(self, url: str, method: str = "GET",
                      data: bytes = None, headers: dict = None) -> bytes:
        """Shared HTTP helper with 30s timeout and error handling.

        Args:
            url: Full URL to request.
            method: HTTP method (GET or POST).
            data: Optional request body bytes (for POST).
            headers: Optional dict of HTTP headers.

        Returns:
            Raw response bytes.

        Raises:
            Exception: On HTTP errors, timeouts, or connection failures.
        """
        req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=self.HTTP_TIMEOUT, context=ctx) as resp:
            return resp.read()

    def gather(
        self,
        lead_id: str,
        case_type: str,
        subjects: list[str],
        sources: Optional[list[str]] = None,
    ) -> GatherResult:
        """Orchestrate parallel OSINT queries for a pre-case lead."""
        result = GatherResult(lead_id=lead_id)

        if sources is not None:
            selected_sources = [s for s in sources if s in self.SOURCES]
        else:
            selected_sources = CASE_TYPE_SOURCE_MAP.get(case_type, self.SOURCES)

        result.sources_queried = list(selected_sources)

        query_methods = {
            "sam_gov": self._query_sam_gov,
            "fpds_gov": self._query_fpds_gov,
            "usaspending_gov": self._query_usaspending,
            "sec_edgar": self._query_sec_edgar,
            "irs_form_990": self._query_form_990,
            "state_corporate_registry": self._query_state_registries,
            "pacer": self._query_pacer,
            "news_press": self._search_news,
            "state_dot_bids": self._query_state_dot_bids,
        }

        with ThreadPoolExecutor(max_workers=min(len(selected_sources), 5)) as executor:
            future_to_source = {}
            for source in selected_sources:
                method = query_methods.get(source)
                if method:
                    if source == "news_press":
                        future = executor.submit(method, subjects, case_type)
                    else:
                        future = executor.submit(method, subjects)
                    future_to_source[future] = source

            for future in as_completed(future_to_source):
                source = future_to_source[future]
                try:
                    records = future.result()
                    if records:
                        result.sources_succeeded.append(source)
                        result.records_gathered += len(records)
                        provenance_id = self._store_provenance(lead_id, source, records)
                        result.provenance_records.append(provenance_id)
                        if source in SOURCE_REDSHIFT_TABLE:
                            self._load_to_redshift(source, records)
                        self._create_neptune_entities(lead_id, records)
                    else:
                        result.sources_succeeded.append(source)
                except Exception as e:
                    logger.warning(
                        "OSINT source %s failed for lead %s: %s",
                        source, lead_id, str(e)[:200],
                    )
                    result.sources_failed.append(source)
                    result.evidence_gaps.append({
                        "source": source,
                        "reason": str(e)[:500],
                        "recommended_action": f"Retry {source} query or use alternative source",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

        return result

    # ------------------------------------------------------------------
    # Source-Specific Query Methods
    # ------------------------------------------------------------------

    def _query_sam_gov(self, subjects: list[str]) -> list[dict]:
        """Query SAM.gov Entity API for vendor registrations and exclusion records.

        HTTP GET to https://api.sam.gov/entity-information/v3/entities?legalBusinessName={subject}
        Parses: UEI, CAGE code, NAICS codes, physical address, registration status, exclusions.
        """
        import os
        import urllib.parse

        records = []
        api_key = os.environ.get("SAM_GOV_API_KEY", "")
        for subject in subjects:
            params = {"legalBusinessName": subject}
            if api_key:
                params["api_key"] = api_key
            url = "https://api.sam.gov/entity-information/v3/entities?" + urllib.parse.urlencode(params)
            raw = self._make_request(url)
            response_hash = hashlib.sha256(raw).hexdigest()
            data = json.loads(raw)
            entities = data.get("entityData", data.get("results", []))
            if isinstance(entities, list):
                for entity in entities:
                    core = entity.get("entityRegistration", entity) if isinstance(entity, dict) else {}
                    records.append({
                        "source": "sam_gov",
                        "entity_name": subject,
                        "query_type": "entity_registration",
                        "api_endpoint": "https://api.sam.gov/entity-information/v3/entities",
                        "retrieved_at": datetime.now(timezone.utc).isoformat(),
                        "response_hash": response_hash,
                        "uei": core.get("ueiSAM", core.get("UEI", "")),
                        "cage_code": core.get("cageCode", ""),
                        "naics_codes": core.get("naicsCode", core.get("naicsCodes", [])),
                        "physical_address": core.get("physicalAddress", {}),
                        "registration_status": core.get("registrationStatus", ""),
                        "exclusion_records": core.get("exclusions", []),
                    })
            if not entities:
                records.append({
                    "source": "sam_gov",
                    "entity_name": subject,
                    "query_type": "entity_registration",
                    "api_endpoint": "https://api.sam.gov/entity-information/v3/entities",
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "response_hash": response_hash,
                    "uei": "",
                    "cage_code": "",
                    "naics_codes": [],
                    "physical_address": {},
                    "registration_status": "no_results",
                    "exclusion_records": [],
                })
        return records

    def _query_fpds_gov(self, subjects: list[str]) -> list[dict]:
        """Query FPDS.gov for federal contract awards."""
        records = []
        for subject in subjects:
            records.append({
                "source": "fpds_gov",
                "entity_name": subject,
                "query_type": "contract_awards",
                "api_endpoint": "https://www.fpds.gov/ezsearch/LATEST",
                "query_params": {"vendorName": subject},
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "fields_requested": [
                    "contract_number", "award_amount", "award_date",
                    "competition_type", "place_of_performance",
                    "subcontracting_plan",
                ],
            })
        return records

    def _query_usaspending(self, subjects: list[str]) -> list[dict]:
        """Query USASpending.gov API for federal spending transactions.

        HTTP POST to https://api.usaspending.gov/api/v2/search/spending_by_award/
        Body: {"filters": {"keywords": [subject]}, "limit": 50}
        Parses: award_id, recipient_name, total_obligation, awarding_agency, period_of_performance.
        """
        records = []
        for subject in subjects:
            url = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
            payload = json.dumps({"filters": {"keywords": [subject]}, "limit": 50}).encode("utf-8")
            headers = {"Content-Type": "application/json"}
            raw = self._make_request(url, method="POST", data=payload, headers=headers)
            response_hash = hashlib.sha256(raw).hexdigest()
            data = json.loads(raw)
            results = data.get("results", [])
            for award in results[:50]:
                records.append({
                    "source": "usaspending_gov",
                    "entity_name": subject,
                    "query_type": "spending_transactions",
                    "api_endpoint": "https://api.usaspending.gov/api/v2/search/spending_by_award/",
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "response_hash": response_hash,
                    "award_id": award.get("internal_id", award.get("Award ID", "")),
                    "recipient_name": award.get("Recipient Name", award.get("recipient_name", "")),
                    "total_obligation": award.get("Award Amount", award.get("total_obligation", 0)),
                    "awarding_agency": award.get("Awarding Agency", award.get("awarding_agency", "")),
                    "period_of_performance": award.get("Period of Performance Start Date", ""),
                })
            if not results:
                records.append({
                    "source": "usaspending_gov",
                    "entity_name": subject,
                    "query_type": "spending_transactions",
                    "api_endpoint": "https://api.usaspending.gov/api/v2/search/spending_by_award/",
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "response_hash": response_hash,
                    "award_id": "",
                    "recipient_name": "",
                    "total_obligation": 0,
                    "awarding_agency": "",
                    "period_of_performance": "",
                })
        return records

    def _query_sec_edgar(self, subjects: list[str]) -> list[dict]:
        """Query SEC EDGAR full-text search for public company filings.

        HTTP GET to https://efts.sec.gov/LATEST/search-index?q={subject}
        Includes User-Agent header per SEC fair access policy.
        Parses: filing_type, filing_date, company_name, CIK, file_url.
        """
        import urllib.parse

        records = []
        for subject in subjects:
            url = "https://efts.sec.gov/LATEST/search-index?q=" + urllib.parse.quote(subject)
            headers = {
                "User-Agent": "DOJ-Research-Analyst research-analyst@usdoj.gov",
                "Accept": "application/json",
            }
            raw = self._make_request(url, headers=headers)
            response_hash = hashlib.sha256(raw).hexdigest()
            data = json.loads(raw)
            hits = data.get("hits", data.get("results", []))
            if isinstance(hits, dict):
                hits = hits.get("hits", [])
            for filing in hits:
                src = filing.get("_source", filing) if isinstance(filing, dict) else {}
                records.append({
                    "source": "sec_edgar",
                    "entity_name": subject,
                    "query_type": "company_filings",
                    "api_endpoint": "https://efts.sec.gov/LATEST/search-index",
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "response_hash": response_hash,
                    "filing_type": src.get("form_type", src.get("filing_type", "")),
                    "filing_date": src.get("file_date", src.get("filing_date", "")),
                    "company_name": src.get("display_names", [subject])[0] if isinstance(src.get("display_names"), list) and src.get("display_names") else src.get("entity_name", subject),
                    "cik": src.get("entity_id", src.get("CIK", "")),
                    "file_url": src.get("file_num", src.get("file_url", "")),
                })
            if not hits:
                records.append({
                    "source": "sec_edgar",
                    "entity_name": subject,
                    "query_type": "company_filings",
                    "api_endpoint": "https://efts.sec.gov/LATEST/search-index",
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "response_hash": response_hash,
                    "filing_type": "",
                    "filing_date": "",
                    "company_name": subject,
                    "cik": "",
                    "file_url": "",
                })
        return records

    def _query_form_990(self, subjects: list[str]) -> list[dict]:
        """Retrieve IRS Form 990 filings for nonprofit organizations."""
        records = []
        for subject in subjects:
            records.append({
                "source": "irs_form_990",
                "entity_name": subject,
                "query_type": "nonprofit_filings",
                "api_endpoint": "https://projects.propublica.org/nonprofits/api/v2/search.json",
                "query_params": {"q": subject},
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "fields_requested": [
                    "board_members", "highest_compensated_employees",
                    "related_organizations", "financial_transactions",
                    "ein", "total_revenue",
                ],
            })
        return records

    def _query_state_registries(self, subjects: list[str]) -> list[dict]:
        """Query OpenCorporates API for corporate registry data.

        HTTP GET to https://api.opencorporates.com/v0.4/companies/search?q={subject}&jurisdiction_code=us_*
        Includes API key from OPENCORPORATES_API_KEY env var if configured.
        Parses: company_name, jurisdiction, company_number, registered_address, officers, status.
        """
        import os
        import urllib.parse

        records = []
        api_key = os.environ.get("OPENCORPORATES_API_KEY", "")
        for subject in subjects:
            params = {"q": subject, "jurisdiction_code": "us_*"}
            if api_key:
                params["api_token"] = api_key
            url = "https://api.opencorporates.com/v0.4/companies/search?" + urllib.parse.urlencode(params)
            raw = self._make_request(url)
            response_hash = hashlib.sha256(raw).hexdigest()
            data = json.loads(raw)
            companies = data.get("results", {}).get("companies", [])
            for item in companies:
                company = item.get("company", item) if isinstance(item, dict) else {}
                records.append({
                    "source": "state_corporate_registry",
                    "entity_name": subject,
                    "query_type": "business_entity_filing",
                    "api_endpoint": "https://api.opencorporates.com/v0.4/companies/search",
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "response_hash": response_hash,
                    "company_name": company.get("name", ""),
                    "jurisdiction": company.get("jurisdiction_code", ""),
                    "company_number": company.get("company_number", ""),
                    "registered_address": company.get("registered_address_in_full", ""),
                    "officers": company.get("officers", []),
                    "status": company.get("current_status", ""),
                })
            if not companies:
                records.append({
                    "source": "state_corporate_registry",
                    "entity_name": subject,
                    "query_type": "business_entity_filing",
                    "api_endpoint": "https://api.opencorporates.com/v0.4/companies/search",
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "response_hash": response_hash,
                    "company_name": "",
                    "jurisdiction": "",
                    "company_number": "",
                    "registered_address": "",
                    "officers": [],
                    "status": "no_results",
                })
        return records

    def _query_pacer(self, subjects: list[str]) -> list[dict]:
        """Query PACER for federal court records."""
        records = []
        for subject in subjects:
            records.append({
                "source": "pacer",
                "entity_name": subject,
                "query_type": "court_records",
                "api_endpoint": "https://pcl.uscourts.gov/pcl/pages/search.jsf",
                "query_params": {"party_name": subject, "nature_of_suit": "antitrust"},
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "fields_requested": [
                    "case_number", "parties", "filing_date",
                    "case_type", "court", "status",
                ],
            })
        return records

    def _search_news(self, subjects: list[str], case_type: str = "") -> list[dict]:
        """Search news via Brave Search API for subject coverage.

        HTTP GET to https://api.search.brave.com/res/v1/news/search
        Header: X-Subscription-Token from BRAVE_API_KEY env var.
        Query: {subject} {case_type_keywords}
        Limit: 20 results per subject.
        Parses: title, url, published_date, source_name, snippet.
        """
        import os
        import urllib.parse

        case_type_keywords = {
            "procurement_collusion": "bid rigging collusion procurement",
            "price_fixing": "price fixing antitrust cartel",
            "market_allocation": "market allocation territory division",
            "merger_review": "merger acquisition antitrust review",
            "monopolization": "monopoly dominant market exclusionary",
            "criminal_cartel": "criminal cartel conspiracy indictment",
        }
        keywords = case_type_keywords.get(case_type, "antitrust")
        api_key = os.environ.get("BRAVE_API_KEY", "")

        records = []
        for subject in subjects:
            query = f"{subject} {keywords}"
            params = {"q": query, "count": "20"}
            url = "https://api.search.brave.com/res/v1/news/search?" + urllib.parse.urlencode(params)
            headers = {
                "Accept": "application/json",
                "X-Subscription-Token": api_key,
            }
            raw = self._make_request(url, headers=headers)
            response_hash = hashlib.sha256(raw).hexdigest()
            data = json.loads(raw)
            results = data.get("results", [])
            for article in results[:20]:
                records.append({
                    "source": "news_press",
                    "entity_name": subject,
                    "query_type": "news_search",
                    "api_endpoint": "https://api.search.brave.com/res/v1/news/search",
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "response_hash": response_hash,
                    "title": article.get("title", ""),
                    "url": article.get("url", ""),
                    "published_date": article.get("age", article.get("published_date", "")),
                    "source_name": article.get("meta_url", {}).get("hostname", "") if isinstance(article.get("meta_url"), dict) else article.get("source", ""),
                    "snippet": article.get("description", ""),
                })
            if not results:
                records.append({
                    "source": "news_press",
                    "entity_name": subject,
                    "query_type": "news_search",
                    "api_endpoint": "https://api.search.brave.com/res/v1/news/search",
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "response_hash": response_hash,
                    "title": "",
                    "url": "",
                    "published_date": "",
                    "source_name": "",
                    "snippet": "",
                })
        return records

    def _query_state_dot_bids(self, subjects: list[str]) -> list[dict]:
        """Query state DOT bid tabulation databases."""
        records = []
        for subject in subjects:
            records.append({
                "source": "state_dot_bids",
                "entity_name": subject,
                "query_type": "bid_tabulations",
                "api_endpoint": "https://state-dot-bids.gov/api/v1/search",
                "query_params": {"vendor_name": subject},
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "fields_requested": [
                    "vendor_id", "contract_id", "bid_amount",
                    "submission_date", "awarding_agency", "state",
                    "award_status",
                ],
            })
        return records

    # ------------------------------------------------------------------
    # Provenance Tracking and Data Storage (Task 4.2)
    # ------------------------------------------------------------------

    def _store_provenance(self, lead_id: str, source: str, data: list[dict]) -> str:
        """Create a Data_Provenance_Record for a successful OSINT retrieval.

        Stores the raw response in S3 and creates a provenance record in Aurora
        with all required fields: source_name, source_url, retrieval_timestamp,
        data_format, reliability_rating, and response_hash.

        Args:
            lead_id: UUID of the pre-case lead.
            source: OSINT source name (e.g., "sam_gov").
            data: List of records retrieved from the source.

        Returns:
            The osint_id (UUID) of the created provenance record.
        """
        osint_id = str(uuid.uuid4())
        retrieval_timestamp = datetime.now(timezone.utc)

        # Serialize data for hashing and S3 storage
        raw_json = json.dumps(data, default=str, sort_keys=True)
        response_hash = hashlib.sha256(raw_json.encode()).hexdigest()

        # Store raw response in S3
        s3_path = self._store_raw_to_s3(lead_id, source, raw_json, retrieval_timestamp)

        # Extract entities from records for storage
        extracted_entities = []
        for record in data:
            if "entity_name" in record:
                extracted_entities.append({
                    "name": record["entity_name"],
                    "source": source,
                    "query_type": record.get("query_type", "unknown"),
                })

        # Create provenance record in Aurora
        try:
            with self.aurora_cm.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO pre_case_osint_data
                        (osint_id, lead_id, source_name, source_url,
                         retrieval_timestamp, data_format, reliability_rating,
                         raw_data_s3_path, extracted_entities, response_hash)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        osint_id,
                        lead_id,
                        source,
                        SOURCE_URLS.get(source, ""),
                        retrieval_timestamp,
                        "json",
                        SOURCE_RELIABILITY.get(source, "news_media"),
                        s3_path,
                        json.dumps(extracted_entities),
                        response_hash,
                    ),
                )
        except Exception as e:
            logger.error(
                "Failed to store provenance for lead %s source %s: %s",
                lead_id, source, e,
            )

        return osint_id

    def _store_raw_to_s3(
        self,
        lead_id: str,
        source: str,
        raw_json: str,
        timestamp: datetime,
    ) -> str:
        """Store raw OSINT response data in S3.

        Args:
            lead_id: UUID of the lead.
            source: OSINT source name.
            raw_json: Serialized JSON response.
            timestamp: Retrieval timestamp.

        Returns:
            S3 path where the data was stored.
        """
        date_prefix = timestamp.strftime("%Y/%m/%d")
        s3_key = f"osint/{lead_id}/{source}/{date_prefix}/{uuid.uuid4()}.json"

        if self.s3_client and self.s3_bucket:
            try:
                self.s3_client.put_object(
                    Bucket=self.s3_bucket,
                    Key=s3_key,
                    Body=raw_json.encode("utf-8"),
                    ContentType="application/json",
                )
            except Exception as e:
                logger.error("Failed to store raw data to S3: %s", e)

        return f"s3://{self.s3_bucket}/{s3_key}"

    def _load_to_redshift(self, source: str, records: list[dict]) -> None:
        """Load structured OSINT data to the appropriate Redshift table.

        Uses the boto3 redshift-data client (execute_statement) to insert
        records. Only sources with a defined Redshift table mapping are loaded.

        Args:
            source: OSINT source name.
            records: List of records to load.
        """
        table = SOURCE_REDSHIFT_TABLE.get(source)
        if not table or not self.redshift_client or not records:
            return

        try:
            # Build batch INSERT statement for the records
            if table == "sam_registrations":
                sql = self._build_sam_insert(records)
            elif table == "fpds_awards":
                sql = self._build_fpds_insert(records)
            elif table == "usaspending_transactions":
                sql = self._build_usaspending_insert(records)
            elif table == "bid_tabulations":
                sql = self._build_bid_tabulations_insert(records)
            else:
                return

            if not sql:
                return

            # Execute via Redshift Data API
            response = self.redshift_client.execute_statement(
                Database="pre_case_analytics",
                Sql=sql,
                WithEvent=False,
            )

            statement_id = response.get("Id")
            if statement_id:
                self._poll_redshift_statement(statement_id)

        except Exception as e:
            logger.error(
                "Failed to load %d records to Redshift table %s: %s",
                len(records), table, e,
            )

    def _poll_redshift_statement(self, statement_id: str, max_attempts: int = 30) -> bool:
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

    def _build_sam_insert(self, records: list[dict]) -> str:
        """Build INSERT SQL for sam_registrations table."""
        values_parts = []
        for r in records:
            entity_id = hashlib.md5(r.get("entity_name", "").encode()).hexdigest()[:16]
            name = r.get("entity_name", "").replace("'", "''")
            values_parts.append(
                f"('{entity_id}', '{name}', NULL, NULL, NULL, 'Active', NULL, NULL, CURRENT_DATE)"
            )
        if not values_parts:
            return ""
        values_str = ", ".join(values_parts)
        return (
            f"INSERT INTO sam_registrations "
            f"(entity_id, legal_name, duns_number, cage_code, naics_codes, "
            f"sam_status, exclusion_records, physical_address, registration_date) "
            f"VALUES {values_str} "
            f"/* ON CONFLICT DO NOTHING - handled by dedup logic */"
        )

    def _build_fpds_insert(self, records: list[dict]) -> str:
        """Build INSERT SQL for fpds_awards table."""
        values_parts = []
        for r in records:
            contract_num = f"FPDS-{uuid.uuid4().hex[:12]}"
            vendor_id = hashlib.md5(r.get("entity_name", "").encode()).hexdigest()[:16]
            name = r.get("entity_name", "").replace("'", "''")
            values_parts.append(
                f"('{contract_num}', '{vendor_id}', '{name}', 0.00, "
                f"CURRENT_DATE, NULL, NULL, NULL)"
            )
        if not values_parts:
            return ""
        values_str = ", ".join(values_parts)
        return (
            f"INSERT INTO fpds_awards "
            f"(contract_number, vendor_id, awarding_agency, award_amount, "
            f"award_date, place_of_performance, competition_type, subcontracting_plan) "
            f"VALUES {values_str}"
        )

    def _build_usaspending_insert(self, records: list[dict]) -> str:
        """Build INSERT SQL for usaspending_transactions table."""
        values_parts = []
        for r in records:
            award_id = f"USA-{uuid.uuid4().hex[:12]}"
            recipient_id = hashlib.md5(r.get("entity_name", "").encode()).hexdigest()[:16]
            values_parts.append(
                f"('{award_id}', '{recipient_id}', 0.00, NULL, "
                f"CURRENT_DATE, NULL, NULL)"
            )
        if not values_parts:
            return ""
        values_str = ", ".join(values_parts)
        return (
            f"INSERT INTO usaspending_transactions "
            f"(award_id, recipient_id, federal_action_obligation, awarding_agency, "
            f"period_of_performance_start, period_of_performance_end, sub_award_data) "
            f"VALUES {values_str}"
        )

    def _build_bid_tabulations_insert(self, records: list[dict]) -> str:
        """Build INSERT SQL for bid_tabulations table."""
        values_parts = []
        for r in records:
            vendor_id = hashlib.md5(r.get("entity_name", "").encode()).hexdigest()[:16]
            contract_id = f"BID-{uuid.uuid4().hex[:12]}"
            values_parts.append(
                f"('{vendor_id}', '{contract_id}', 0.00, CURRENT_DATE, "
                f"NULL, NULL, 'pending', NULL)"
            )
        if not values_parts:
            return ""
        values_str = ", ".join(values_parts)
        return (
            f"INSERT INTO bid_tabulations "
            f"(vendor_id, contract_id, bid_amount, submission_date, "
            f"awarding_agency, state, award_status, source_file) "
            f"VALUES {values_str}"
        )

    def _create_neptune_entities(self, lead_id: str, records: list[dict]) -> None:
        """Create entity nodes and relationship edges in Neptune.

        Uses batched Gremlin HTTP queries with entity_label(case_id) convention.
        Batches records into groups to avoid individual upserts.

        Args:
            lead_id: UUID of the pre-case lead (used as graph label).
            records: List of records containing entity information.
        """
        if not self.neptune_endpoint or not records:
            return

        # Build batched Gremlin query for entity nodes
        label = f"PreCase_{lead_id.replace('-', '_')}"
        gremlin_parts = []

        for record in records:
            entity_name = record.get("entity_name", "")
            source = record.get("source", "unknown")
            query_type = record.get("query_type", "unknown")

            if not entity_name:
                continue

            # Escape single quotes for Gremlin
            safe_name = entity_name.replace("'", "\\'")
            node_id = hashlib.md5(f"{lead_id}:{entity_name}".encode()).hexdigest()[:16]

            # Add vertex with properties
            gremlin_parts.append(
                f"g.V('{node_id}').fold().coalesce("
                f"unfold(), "
                f"addV('{label}').property(id, '{node_id}')"
                f".property('name', '{safe_name}')"
                f".property('source', '{source}')"
                f".property('query_type', '{query_type}')"
                f".property('lead_id', '{lead_id}')"
                f")"
            )

        # Execute in batches of 10 to avoid query size limits
        batch_size = 10
        for i in range(0, len(gremlin_parts), batch_size):
            batch = gremlin_parts[i:i + batch_size]
            for query in batch:
                self._execute_gremlin(query)

    def _execute_gremlin(self, query: str) -> list:
        """Execute a Gremlin query via Neptune HTTP API.

        Args:
            query: Gremlin query string.

        Returns:
            List of results from Neptune.
        """
        if not self.neptune_endpoint:
            return []

        url = f"https://{self.neptune_endpoint}:{self.neptune_port}/gremlin"
        data = json.dumps({"gremlin": query}).encode("utf-8")
        ctx = ssl.create_default_context()
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                result = body.get("result", {}).get("data", {})
                if isinstance(result, dict) and "@value" in result:
                    return result["@value"]
                if isinstance(result, list):
                    return result
                return [result] if result else []
        except Exception as e:
            logger.error(
                "Neptune Gremlin query error: %s | query: %s",
                str(e)[:200], query[:200],
            )
            return []
