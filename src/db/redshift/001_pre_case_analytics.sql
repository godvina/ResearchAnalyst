-- ============================================================================
-- Redshift Serverless Schema: Pre-Case Analytics
-- Module: Antitrust Pre-Case Intelligence
-- Description: Analytical data warehouse tables for structured procurement data
--              at scale, enabling cross-case pattern detection across millions
--              of bid tabulation records.
-- ============================================================================

-- Table: bid_tabulations
-- Stores state DOT bid tabulation records for cross-case analysis
-- DISTKEY on vendor_id for co-located vendor queries
-- SORTKEY on submission_date + state for time-range and geographic filtering
CREATE TABLE bid_tabulations (
    bid_id BIGINT IDENTITY(1,1),
    vendor_id VARCHAR(64) NOT NULL,
    contract_id VARCHAR(128) NOT NULL,
    bid_amount DECIMAL(15, 2) NOT NULL,
    submission_date DATE NOT NULL,
    awarding_agency VARCHAR(256),
    state VARCHAR(2),
    award_status VARCHAR(32),
    source_file VARCHAR(512),
    loaded_at TIMESTAMP DEFAULT GETDATE(),
    PRIMARY KEY (vendor_id, contract_id, submission_date)
)
DISTSTYLE KEY DISTKEY (vendor_id)
SORTKEY (submission_date, state);

-- Table: sam_registrations
-- Stores SAM.gov entity registrations for vendor identity resolution
-- DISTKEY on entity_id for entity-centric queries
-- SORTKEY on legal_name for name-based lookups and fuzzy matching
CREATE TABLE sam_registrations (
    entity_id VARCHAR(64) PRIMARY KEY,
    legal_name VARCHAR(512) NOT NULL,
    duns_number VARCHAR(13),
    cage_code VARCHAR(5),
    naics_codes VARCHAR(1024),
    sam_status VARCHAR(32),
    exclusion_records SUPER,
    physical_address VARCHAR(512),
    registration_date DATE,
    loaded_at TIMESTAMP DEFAULT GETDATE()
)
DISTSTYLE KEY DISTKEY (entity_id)
SORTKEY (legal_name);

-- Table: fpds_awards
-- Stores FPDS.gov federal contract award data
-- DISTKEY on vendor_id for vendor-centric award analysis
-- SORTKEY on award_date for temporal queries
CREATE TABLE fpds_awards (
    contract_number VARCHAR(128) PRIMARY KEY,
    vendor_id VARCHAR(64) NOT NULL,
    awarding_agency VARCHAR(256),
    award_amount DECIMAL(15, 2),
    award_date DATE,
    place_of_performance VARCHAR(256),
    competition_type VARCHAR(64),
    subcontracting_plan SUPER,
    loaded_at TIMESTAMP DEFAULT GETDATE()
)
DISTSTYLE KEY DISTKEY (vendor_id)
SORTKEY (award_date);

-- Table: usaspending_transactions
-- Stores USASpending.gov federal spending transaction data
-- DISTKEY on recipient_id for recipient-centric analysis
-- SORTKEY on period_of_performance_start for temporal queries
CREATE TABLE usaspending_transactions (
    award_id VARCHAR(128) PRIMARY KEY,
    recipient_id VARCHAR(64) NOT NULL,
    federal_action_obligation DECIMAL(15, 2),
    awarding_agency VARCHAR(256),
    period_of_performance_start DATE,
    period_of_performance_end DATE,
    sub_award_data SUPER,
    loaded_at TIMESTAMP DEFAULT GETDATE()
)
DISTSTYLE KEY DISTKEY (recipient_id)
SORTKEY (period_of_performance_start);

-- Table: vendor_aliases
-- Stores fuzzy-matched vendor name mappings for cross-reference
-- DISTKEY on canonical_vendor_id for canonical lookups
-- SORTKEY on alias_name for name-based searches
CREATE TABLE vendor_aliases (
    alias_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    canonical_vendor_id VARCHAR(64) NOT NULL,
    alias_name VARCHAR(512) NOT NULL,
    alias_source VARCHAR(64),
    match_confidence DECIMAL(5, 2),
    created_at TIMESTAMP DEFAULT GETDATE()
)
DISTSTYLE KEY DISTKEY (canonical_vendor_id)
SORTKEY (alias_name);

-- ============================================================================
-- Materialized Views for Cross-Case Queries
-- Cached analytical results refreshed daily for query performance
-- ============================================================================

-- Materialized View: mv_vendor_win_rates
-- Aggregates vendor win rates by state for detecting suspicious win patterns
CREATE MATERIALIZED VIEW mv_vendor_win_rates AS
SELECT vendor_id, state,
    COUNT(*) AS total_bids,
    SUM(CASE WHEN award_status = 'awarded' THEN 1 ELSE 0 END) AS wins,
    ROUND(SUM(CASE WHEN award_status = 'awarded' THEN 1.0 ELSE 0 END) / COUNT(*) * 100, 2) AS win_rate_pct
FROM bid_tabulations
GROUP BY vendor_id, state;

-- Materialized View: mv_vendor_co_occurrence
-- Identifies vendor pairs that frequently co-bid on the same contracts
-- Minimum threshold of 3 co-bids to filter noise
CREATE MATERIALIZED VIEW mv_vendor_co_occurrence AS
SELECT a.vendor_id AS vendor_a, b.vendor_id AS vendor_b, a.state,
    COUNT(DISTINCT a.contract_id) AS co_bid_count
FROM bid_tabulations a
JOIN bid_tabulations b ON a.contract_id = b.contract_id AND a.vendor_id < b.vendor_id
GROUP BY a.vendor_id, b.vendor_id, a.state
HAVING COUNT(DISTINCT a.contract_id) >= 3;
