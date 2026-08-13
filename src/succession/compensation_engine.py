"""
Executive Succession Planning — Compensation Engine

Computes total compensation estimates, market ranges, and compensation gaps
for executive candidates using lookup-table-based market data.

Key computations:
  - Total Comp = base + bonus + equity + benefits + allowances
  - Market Range = p25/p50/p75 from sector-country-seniority lookup
  - Comp Gap = candidate_comp - role_p50 (premium or below-market)

Correctness Properties:
  P1: Arithmetic Consistency — total == base + bonus + equity + benefits + allowances (within $1)
  P2: Gap Label Accuracy — positive gap → "PREMIUM_REQUIRED", negative gap → "BELOW_MARKET"
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# =============================================================================
# Data Types
# =============================================================================

@dataclass
class CompEstimate:
    """Total compensation estimate for a candidate."""
    base: float
    bonus: float
    equity: float
    benefits: float
    allowances: float
    total: float
    currency: str = 'USD'
    confidence: str = 'MEDIUM'
    source: str = 'lookup_table'


@dataclass
class MarketRange:
    """Market compensation range for a role."""
    p25: float
    p50: float
    p75: float
    sector: str
    country: str
    role_type: str


@dataclass
class CompGap:
    """Compensation gap between candidate comp and role market rate."""
    amount: float
    percentage: float
    label: str
    cost_prohibitive: bool


# =============================================================================
# Compensation Engine
# =============================================================================

class CompensationEngine:
    """
    Computes executive compensation estimates, market ranges, and gaps
    using sector-country-seniority lookup tables.
    """

    def compute_total_comp(self, candidate: dict, lookup: dict) -> CompEstimate:
        """
        Compute total compensation for a candidate from lookup data.

        Args:
            candidate: dict with keys 'sector', 'country', 'seniority'
            lookup: dict keyed by "{sector}_{country}_{seniority}" with comp data

        Returns:
            CompEstimate with all compensation components and total
        """
        key = f"{candidate['sector']}_{candidate['country']}_{candidate['seniority']}"
        confidence = 'MEDIUM'

        if key in lookup:
            entry = lookup[key]
        else:
            entry = self._nearest_fallback(candidate, lookup)
            confidence = entry.pop('confidence', 'LOW')

        base = entry['base']['p50']
        bonus = base * (entry['bonus_pct']['p50'] / 100)
        equity = entry['equity']['p50']
        benefits = entry['benefits']
        allowances = sum(entry.get('allowances', {}).values())
        total = base + bonus + equity + benefits + allowances

        return CompEstimate(
            base=base,
            bonus=bonus,
            equity=equity,
            benefits=benefits,
            allowances=allowances,
            total=total,
            currency='USD',
            confidence=confidence,
            source='lookup_table',
        )

    def compute_market_range(self, role: dict, lookup: dict) -> MarketRange:
        """
        Compute market compensation range for a role.

        Args:
            role: dict with keys 'sector', 'country', 'seniority'
            lookup: dict keyed by "{sector}_{country}_{seniority}"

        Returns:
            MarketRange with p25/p50/p75 and role metadata
        """
        key = f"{role['sector']}_{role['country']}_{role['seniority']}"
        entry = lookup[key]

        return MarketRange(
            p25=entry['total']['p25'],
            p50=entry['total']['p50'],
            p75=entry['total']['p75'],
            sector=role['sector'],
            country=role['country'],
            role_type=role['seniority'],
        )

    def compute_comp_gap(self, candidate_comp: float, role_p50: float) -> CompGap:
        """
        Compute the compensation gap between candidate comp and market rate.

        Args:
            candidate_comp: candidate's total compensation
            role_p50: market p50 for the target role

        Returns:
            CompGap with amount, percentage, label, and cost_prohibitive flag
        """
        if role_p50 == 0:
            return CompGap(
                amount=0,
                percentage=0,
                label='NO_MARKET_DATA',
                cost_prohibitive=False,
            )

        gap = candidate_comp - role_p50
        pct = (gap / role_p50) * 100

        if gap > 0:
            label = 'PREMIUM_REQUIRED'
        else:
            label = 'BELOW_MARKET'

        cost_prohibitive = gap > 0 and abs(pct) > 40

        return CompGap(
            amount=gap,
            percentage=pct,
            label=label,
            cost_prohibitive=cost_prohibitive,
        )

    def _nearest_fallback(self, candidate: dict, lookup: dict) -> dict:
        """
        Find nearest matching entry when exact key is missing.

        Strategy:
          1. Try same country with different seniority levels
          2. Try same seniority with US as fallback country

        Args:
            candidate: dict with 'sector', 'country', 'seniority'
            lookup: dict of compensation entries

        Returns:
            dict with compensation entry and confidence='LOW' added
        """
        sector = candidate['sector']
        country = candidate['country']
        seniority = candidate['seniority']

        # Try same country with different seniority levels
        for alt_seniority in ['VP', 'C_SUITE', 'DIRECTOR']:
            alt_key = f"{sector}_{country}_{alt_seniority}"
            if alt_key in lookup:
                entry = dict(lookup[alt_key])
                entry['confidence'] = 'LOW'
                return entry

        # Try same seniority with US as fallback country
        us_key = f"{sector}_US_{seniority}"
        if us_key in lookup:
            entry = dict(lookup[us_key])
            entry['confidence'] = 'LOW'
            return entry

        # Try US with any seniority
        for alt_seniority in ['VP', 'C_SUITE', 'DIRECTOR']:
            us_alt_key = f"{sector}_US_{alt_seniority}"
            if us_alt_key in lookup:
                entry = dict(lookup[us_alt_key])
                entry['confidence'] = 'LOW'
                return entry

        # Last resort: return first entry in lookup with LOW confidence
        if lookup:
            first_key = next(iter(lookup))
            entry = dict(lookup[first_key])
            entry['confidence'] = 'LOW'
            return entry

        raise ValueError(
            f"No compensation data found for candidate: {candidate}"
        )
