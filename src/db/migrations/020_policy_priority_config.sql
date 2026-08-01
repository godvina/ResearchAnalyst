-- Migration 020: Policy Priority Configuration
-- Stores enforcement policy directives that boost case backlog scoring
-- for leads aligned with active executive orders, AG memos, and interagency priorities.

BEGIN;

CREATE TABLE IF NOT EXISTS policy_priority_config (
    directive_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    directive_title TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN (
        'executive_order', 'ag_memo', 'congressional_referral', 'interagency'
    )),
    effective_date DATE NOT NULL,
    expiration_date DATE,  -- NULL = indefinite
    target_industries TEXT[] NOT NULL DEFAULT '{}',
    target_case_types TEXT[] NOT NULL DEFAULT '{}',
    boost_multiplier NUMERIC(3,2) NOT NULL CHECK (boost_multiplier BETWEEN 1.0 AND 2.0),
    citation_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_policy_active ON policy_priority_config(effective_date, expiration_date);

-- Seed data: 3 known enforcement directives

-- EO 14036: Promoting Competition in the American Economy
INSERT INTO policy_priority_config (directive_title, source, effective_date, expiration_date, target_industries, target_case_types, boost_multiplier, citation_url)
VALUES (
    'EO 14036 - Competition in the American Economy',
    'executive_order',
    '2021-07-09',
    NULL,
    ARRAY['agriculture', 'healthcare', 'technology', 'labor', 'financial_services'],
    ARRAY['price_fixing', 'monopolization', 'merger_review'],
    1.8,
    'https://www.whitehouse.gov/briefing-room/presidential-actions/2021/07/09/executive-order-on-promoting-competition-in-the-american-economy/'
);

-- DOJ Procurement Collusion Strike Force
INSERT INTO policy_priority_config (directive_title, source, effective_date, expiration_date, target_industries, target_case_types, boost_multiplier, citation_url)
VALUES (
    'DOJ Procurement Collusion Strike Force',
    'ag_memo',
    '2019-11-01',
    NULL,
    ARRAY['construction', 'defense', 'infrastructure', 'government_services'],
    ARRAY['procurement_collusion', 'criminal_cartel'],
    1.7,
    'https://www.justice.gov/procurement-collusion-strike-force'
);

-- Whistleblower Rewards Program (July 2025)
INSERT INTO policy_priority_config (directive_title, source, effective_date, expiration_date, target_industries, target_case_types, boost_multiplier, citation_url)
VALUES (
    'Antitrust Whistleblower Rewards Program',
    'ag_memo',
    '2025-07-01',
    NULL,
    ARRAY['all'],
    ARRAY['procurement_collusion', 'price_fixing', 'criminal_cartel', 'market_allocation'],
    1.5,
    'https://www.justice.gov/atr/whistleblower-program'
);

COMMIT;
