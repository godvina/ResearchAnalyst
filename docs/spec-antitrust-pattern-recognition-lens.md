# Spec: Antitrust Pattern Recognition Lens

## Overview

Build a Pattern Recognition Lens (identical UX to the Human Trafficking / Fraud typology view) for each of the 6 antitrust case typologies. When a user clicks on a category in the antitrust report, they see the sub-category cards with evidence patterns, flags, and examples — just like the existing crime typology lens.

## Reference Implementation

The existing Pattern Recognition Lens is at:
- Frontend: `src/frontend/typology-lens.js` (renders the cards)
- Data: `src/frontend/investigator.html` (contains typology module definitions)
- Screenshot: The "Fraud, Waste & Abuse" view with 6 sub-category cards

## The 6 Antitrust Typology Modules

Each module needs 4-6 sub-categories with:
- Name and icon
- Description (what patterns to look for)
- Evidence Example (specific scenario with data)
- Typology Flags (detection indicators)
- Statistics footnote (prosecution data)

### 1. Price Fixing
Sub-categories:
- **Horizontal Price Agreement**: Competitors agreeing on prices, price floors, or price increases
  - Flags: parallel pricing, communication between competitors, identical bid amounts
  - Example: "4 airlines simultaneously raised baggage fees by identical $35 within 48 hours. Internal emails reference 'industry coordination meeting.' Flags: *identical timing + identical amount + competitor communication*"
- **Bid Rigging**: Coordinated bidding on contracts (rotating winners, complementary bidding)
  - Flags: bid rotation patterns, losing bids above winner, same subcontractors
  - Example: "Over 36 government contracts, Company A and B alternated winning. Losing bids consistently 5-8% above winner. Both share same legal counsel. Flags: *bid rotation + consistent spread + shared advisors*"
- **Market Division**: Geographic or customer allocation among competitors
  - Flags: non-compete in adjacent markets, customer lists shared, territorial boundaries
- **Output Restriction**: Coordinated production limits to inflate prices
  - Flags: simultaneous capacity reduction, supply shortage + price spike, production quota communication
- **Information Exchange**: Sharing competitively sensitive data
  - Flags: trade association meetings with pricing discussion, advance price announcements, capacity sharing

### 2. Criminal Cartel
Sub-categories:
- **International Cartel**: Cross-border price fixing or market allocation
  - Flags: foreign meetings, coded language, offshore payments
  - Example: "Executives from 5 countries met quarterly at 'trade conferences.' Meeting minutes use code names ('Project Blue'). Wire transfers to Swiss intermediary after each meeting. Flags: *international meetings + coded references + intermediary payments*"
- **Domestic Conspiracy**: US-based coordinated anticompetitive behavior
  - Flags: text message coordination, shared pricing spreadsheets, witness intimidation
- **Obstruction & Cover-up**: Destroying evidence, witness tampering
  - Flags: document destruction after subpoena, encrypted communication shifts, employee NDAs
- **Recidivism**: Repeat offenders or ongoing conduct
  - Flags: prior consent decrees violated, same individuals in new schemes, shell company rotation

### 3. Monopolization
Sub-categories:
- **Exclusionary Conduct**: Using market power to exclude competitors
  - Flags: exclusive dealing contracts, tying arrangements, refusal to deal
  - Example: "Platform requires merchants to use its payment system exclusively. Merchants using competitor payment dropped from search results. 94% market share in relevant market. Flags: *exclusive dealing + retaliation + dominant position*"
- **Predatory Pricing**: Below-cost pricing to eliminate competition
  - Flags: pricing below marginal cost, targeted geographic areas, raising prices after exit
- **Acquisitions to Maintain Monopoly**: Buying nascent competitors
  - Flags: serial acquisitions of small competitors, "kill zone" strategy, internal docs about competitive threats
- **Platform Self-Preferencing**: Favoring own products on dominant platform
  - Flags: algorithmic bias, data advantage exploitation, copy-then-suppress tactics
- **Essential Facility Denial**: Refusing access to critical infrastructure
  - Flags: infrastructure bottleneck, discriminatory access terms, vertical integration leverage

### 4. Procurement Collusion
Sub-categories:
- **Bid Rotation**: Systematic alternation of winning bidders
  - Flags: statistical bid patterns, predetermined winner signals, complementary bids
  - Example: "5 construction firms won exactly 20% of 100 contracts each over 4 years. Phone records show calls between firms 48hrs before each bid deadline. Flags: *statistical anomaly + pre-bid communication + equal distribution*"
- **Cover Bidding**: Deliberately high bids to support chosen winner
  - Flags: inflated cover bids, identical calculation errors, subcontracting to losers
- **Market Allocation by Customer**: Dividing customers among competitors
  - Flags: customer-specific non-compete, referral patterns, customer trading
- **Phantom Bidding**: Fictitious companies submitting bids
  - Flags: shared addresses/phones, newly formed entities, no prior work history

### 5. Market Allocation
Sub-categories:
- **Geographic Division**: Dividing territories among competitors
  - Flags: sharp geographic boundaries, expansion refusals, territory-swap evidence
  - Example: "Waste hauling companies serve non-overlapping zip codes with surgical precision. When customer requests quotes from competitor's territory, they receive 'we don't service that area.' Customer complaints show 200% premium vs competitive markets. Flags: *geographic non-overlap + refusal to compete + price premium*"
- **Customer Allocation**: Assigning specific customers to specific suppliers
  - Flags: customer assignment lists, refusal to bid on allocated accounts, compensation payments
- **Product Market Division**: Each competitor specializes in different segments
  - Flags: coordinated product line decisions, simultaneous exit from segments, referral patterns
- **Time-Based Allocation**: Rotating who competes in different periods
  - Flags: seasonal bid patterns, calendar-based rotation, advance scheduling

### 6. Merger Review
Sub-categories:
- **Horizontal Concentration**: Merger reduces competitors in relevant market
  - Flags: HHI increase > 200 points, market share > 30%, eliminated maverick competitor
  - Example: "Post-merger entity controls 67% of domestic airline routes on 45 city pairs. Merger eliminates the only low-cost carrier on 12 routes. Historical data shows 15-25% price increases on routes where competitor exited. Flags: *high concentration + maverick elimination + historical price increase*"
- **Vertical Foreclosure**: Merger enables input denial to competitors
  - Flags: critical input control, raising rivals' costs, refusal to supply post-merger
- **Coordinated Effects**: Merger facilitates tacit collusion
  - Flags: reduced competitors, increased symmetry, market transparency, multimarket contact
- **Innovation Harm**: Merger reduces R&D competition
  - Flags: overlapping pipelines, reduced future competition, patent portfolio consolidation

## Frontend Implementation

### Option A: Extend existing typology-lens.js
Add an `antitrust` mode that loads from the antitrust cases data. When user clicks a category in the antitrust report pie chart or case list, open the Pattern Recognition Lens with antitrust-specific sub-categories.

### Option B: Standalone page
`src/frontend/antitrust-typology-lens.html` — self-contained page with the same card layout, accessible from the antitrust report via a "View Patterns" button on each category.

### Recommendation: Option A
Less duplication. Add a `typologyDomain` parameter to the lens: `openTypologyLens('antitrust', 'price_fixing')`. The lens loads the correct module definitions based on domain.

## Data Structure (same as existing typology)

```javascript
var ANTITRUST_TYPOLOGY_MODULES = {
    'price_fixing': {
        name: 'Price Fixing',
        icon: '💰',
        color: '#fc8181',
        sub_categories: [
            { id: 'horizontal_price_agreement', name: 'Horizontal Price Agreement', ... },
            { id: 'bid_rigging', name: 'Bid Rigging', ... },
            ...
        ]
    },
    // ...
};
```

## Estimated Effort
- Define all 6 modules × 4-5 sub-categories with examples: ~2 hours
- Frontend integration (extend typology-lens or new page): ~2 hours
- Wire into antitrust report (click category → open lens): ~30 min
- Total: ~1 session

## Key Files to Modify
- `src/frontend/typology-lens.js` — add antitrust module definitions
- `src/frontend/antitrust-report.html` — add "View Patterns" buttons
- `src/frontend/investigator.html` — (if sharing the same lens component)
