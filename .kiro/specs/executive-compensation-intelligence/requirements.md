# Requirements Document

## Introduction

The Executive Compensation Intelligence module adds a "second phase" layer to the existing succession planning pipeline. After candidates are scored across 25 criteria with cultural calibration, this module enriches each candidate with compensation data, risk analysis, fit/readiness estimates, and process stage tracking. It enables executive search teams to prioritize candidates not just by leadership quality but by practical feasibility — cost to acquire, flight risk, compliance exposure, and time-to-value. The system integrates with the existing three-layer scoring engine, Aurora PostgreSQL schema, and boardroom-style dashboard.

## Glossary

- **Compensation_Engine**: The backend service that computes total compensation estimates, comp gaps, and market ranges for candidates and target roles.
- **Risk_Analyzer**: The backend service that computes flight risk, poachability, cultural adaptation risk, compliance/reputational risk, and non-compete estimates for each candidate.
- **Readiness_Analyzer**: The backend service that produces gap heatmaps, time-to-readiness, development cost, and ROI estimates by comparing candidate scores against role requirements.
- **Process_Tracker**: The backend service that manages executive search stage transitions and SLA tracking per candidate.
- **Comp_Gap**: The difference between a candidate's estimated current total compensation and the target role's market compensation at the P50 percentile, representing the premium required to attract the candidate.
- **Total_Compensation**: The sum of base salary, annual bonus, long-term equity/incentive value, and benefits (housing, hardship, pension, perquisites).
- **Market_Range**: The P25, P50, and P75 compensation percentiles for a target role in a given sector-country combination.
- **Flight_Risk_Score**: A numeric score (0-100) indicating the likelihood a candidate will leave their current role within 12 months, independent of external approach.
- **Poachability_Score**: A numeric score (0-100) indicating how likely a candidate is to accept an external offer, considering comp delta, career stage, org stability, and personal factors.
- **Cultural_Adaptation_Risk**: A categorical risk assessment (LOW, MEDIUM, HIGH, CRITICAL) based on GLOBE cluster distance between a candidate's origin culture and the target role's operating culture.
- **Process_Stage**: One of the standard executive search phases: LONG_LIST, SHORT_LIST, APPROACH, SCREEN, ASSESS, OFFER, CLOSE, ONBOARD.
- **SLA_Days**: The maximum number of calendar days a candidate should remain in a given Process_Stage before escalation.
- **Lookup_Table**: A structured dataset mapping sector, seniority level, country, and role type to compensation figures derived from public benchmarks.
- **GLOBE_Cluster**: One of the cultural groupings used by the scoring engine: Anglo, Middle_East, Confucian_Asia, Germanic, Latin_America.
- **Sector**: One of PRIVATE, GOVERNMENT, or MILITARY — the employing sector which determines compensation structure.
- **Dashboard**: The existing succession-dashboard.html frontend application using D3.js, Inter font, and navy/gold boardroom theme.
- **Research_Agent**: The existing Python research agent (scripts/succession_live_research.py) that uses Brave Search and Bedrock Haiku for live data gathering.

## Requirements

### Requirement 1: Total Compensation Estimation

**User Story:** As an executive search consultant, I want to see an estimated total compensation package for each candidate, so that I can understand the financial baseline before initiating an approach.

#### Acceptance Criteria

1. WHEN a candidate is selected for compensation analysis, THE Compensation_Engine SHALL compute Total_Compensation as the sum of base salary, annual bonus, long-term equity value, and benefits.
2. WHEN computing Total_Compensation, THE Compensation_Engine SHALL source figures from the Lookup_Table matching the candidate's current sector, seniority level, country, and role type.
3. WHEN the candidate's country has region-specific allowances (cost-of-living adjustment, hardship allowance, housing benefit), THE Compensation_Engine SHALL add those allowances to Total_Compensation.
4. THE Compensation_Engine SHALL express all Total_Compensation values in USD with the local currency equivalent displayed alongside.
5. IF a Lookup_Table entry does not exist for a candidate's sector-country-role combination, THEN THE Compensation_Engine SHALL fall back to the nearest matching seniority-country combination and flag the estimate as LOW confidence.

### Requirement 2: Target Role Market Compensation Range

**User Story:** As an executive search consultant, I want to see the market compensation range for the target role, so that I can calibrate offers and assess candidate affordability.

#### Acceptance Criteria

1. WHEN a target role is configured, THE Compensation_Engine SHALL compute the Market_Range (P25, P50, P75) for that role based on sector, country, and role type from the Lookup_Table.
2. WHEN the sector is GOVERNMENT, THE Compensation_Engine SHALL apply government pay scale constraints (published grade/step maximums) to cap the P75 value.
3. WHEN the sector is MILITARY, THE Compensation_Engine SHALL apply military rank-equivalent compensation bands and include non-monetary benefits (housing, commissary, healthcare) in the Total_Compensation equivalent.
4. THE Compensation_Engine SHALL adjust Market_Range values by country using a cost-of-living index relative to a US baseline.
5. WHEN a role spans multiple countries (regional role), THE Compensation_Engine SHALL compute separate Market_Range values for each country and present the range of ranges.

### Requirement 3: Compensation Gap Calculation

**User Story:** As an executive search consultant, I want to see the "comp gap" for each candidate, so that I can estimate the premium required to attract them to the target role.

#### Acceptance Criteria

1. WHEN both a candidate's Total_Compensation and the target role's Market_Range are available, THE Compensation_Engine SHALL compute Comp_Gap as (candidate Total_Compensation minus target role P50).
2. WHEN the Comp_Gap is negative (candidate earns less than target P50), THE Compensation_Engine SHALL label the gap as "BELOW_MARKET" and display the shortfall amount.
3. WHEN the Comp_Gap is positive (candidate earns more than target P50), THE Compensation_Engine SHALL label the gap as "PREMIUM_REQUIRED" and display the premium amount.
4. THE Compensation_Engine SHALL compute a Comp_Gap percentage as (Comp_Gap / target role P50) multiplied by 100.
5. WHEN the Comp_Gap percentage exceeds 40%, THE Compensation_Engine SHALL flag the candidate as "COST_PROHIBITIVE" in the dashboard display.

### Requirement 4: Flight Risk Assessment

**User Story:** As an executive search consultant, I want to understand each candidate's likelihood of leaving their current role, so that I can time my approach optimally.

#### Acceptance Criteria

1. WHEN a candidate is analyzed, THE Risk_Analyzer SHALL compute a Flight_Risk_Score (0-100) based on tenure in current role, organization stability indicators, sector compensation trends, and career progression velocity.
2. WHEN the Flight_Risk_Score exceeds 70, THE Risk_Analyzer SHALL classify the candidate as HIGH flight risk.
3. WHEN the Flight_Risk_Score is between 40 and 70, THE Risk_Analyzer SHALL classify the candidate as MEDIUM flight risk.
4. WHEN the Flight_Risk_Score is below 40, THE Risk_Analyzer SHALL classify the candidate as LOW flight risk.
5. THE Risk_Analyzer SHALL include up to three contributing factors in the Flight_Risk_Score explanation (e.g., "org restructuring announced", "3+ years without promotion", "sector downturn").

### Requirement 5: Poachability Assessment

**User Story:** As an executive search consultant, I want a poachability score for each candidate, so that I can focus effort on candidates most likely to accept an offer.

#### Acceptance Criteria

1. WHEN a candidate is analyzed, THE Risk_Analyzer SHALL compute a Poachability_Score (0-100) based on Comp_Gap magnitude, career stage (years to retirement), organization stability, historical mobility frequency, and sector growth trajectory.
2. WHEN the Comp_Gap is labeled "BELOW_MARKET" by more than 15%, THE Risk_Analyzer SHALL increase the Poachability_Score by a factor proportional to the gap magnitude.
3. WHEN a candidate has changed organizations fewer than two times in the past 15 years, THE Risk_Analyzer SHALL decrease the Poachability_Score to reflect low historical mobility.
4. THE Risk_Analyzer SHALL classify Poachability_Score into LOW (0-33), MEDIUM (34-66), and HIGH (67-100) categories.
5. THE Risk_Analyzer SHALL present Poachability_Score alongside Flight_Risk_Score on the candidate profile to enable combined interpretation.

### Requirement 6: Cultural Adaptation Risk

**User Story:** As an executive search consultant, I want to understand the cultural adaptation risk when placing a candidate from one GLOBE cluster into a role in another, so that I can factor onboarding difficulty into my recommendation.

#### Acceptance Criteria

1. WHEN a candidate's origin GLOBE_Cluster differs from the target role's GLOBE_Cluster, THE Risk_Analyzer SHALL compute a Cultural_Adaptation_Risk level.
2. THE Risk_Analyzer SHALL classify Cultural_Adaptation_Risk as LOW when the Hofstede dimension distance (Euclidean across 6 dimensions) is below 30, MEDIUM when between 30 and 60, HIGH when between 60 and 90, and CRITICAL when above 90.
3. WHEN the Cultural_Adaptation_Risk is HIGH or CRITICAL, THE Risk_Analyzer SHALL include specific dimension gaps (e.g., "Power Distance gap: 55 points") in the risk explanation.
4. THE Risk_Analyzer SHALL use the existing CULTURAL_PROFILES data from succession-cultural-profiles.js as the source for Hofstede dimension values.
5. WHEN the target role country is in the Middle_East GLOBE_Cluster and the candidate is from the Anglo cluster, THE Risk_Analyzer SHALL add a "high context communication gap" advisory to the risk explanation.

### Requirement 7: Compliance and Reputational Risk

**User Story:** As an executive search consultant, I want to flag compliance and reputational risks for each candidate, so that I can avoid placing candidates who could expose the organization to legal or brand damage.

#### Acceptance Criteria

1. WHEN a candidate is analyzed, THE Risk_Analyzer SHALL assess compliance risk across four dimensions: sanctions exposure, political sensitivity, public controversy, and regulatory disqualification.
2. WHEN a candidate is associated with a sanctioned entity or jurisdiction (OFAC, EU, UN lists), THE Risk_Analyzer SHALL assign a CRITICAL compliance risk flag.
3. WHEN a candidate has public controversy indicators (media mentions with negative sentiment above a threshold), THE Risk_Analyzer SHALL assign a HIGH reputational risk flag.
4. THE Risk_Analyzer SHALL present compliance and reputational risk as separate fields with severity levels (CLEAR, LOW, MEDIUM, HIGH, CRITICAL) and cited sources.
5. IF the Research_Agent cannot find sufficient public information to assess compliance risk, THEN THE Risk_Analyzer SHALL label the assessment as "INSUFFICIENT_DATA" rather than defaulting to CLEAR.

### Requirement 8: Non-Compete and Notice Period Estimation

**User Story:** As an executive search consultant, I want to estimate notice periods and non-compete restrictions for each candidate, so that I can plan realistic timelines for role fulfillment.

#### Acceptance Criteria

1. WHEN a candidate is analyzed, THE Risk_Analyzer SHALL estimate the notice period based on the candidate's country and seniority level using country-specific employment law defaults.
2. WHEN the candidate is based in a jurisdiction with enforceable non-compete clauses (e.g., US pre-FTC rule states, Germany, Singapore), THE Risk_Analyzer SHALL estimate the non-compete duration based on seniority level (default: 6 months for VP, 12 months for C-suite).
3. WHEN the candidate is based in a jurisdiction where non-competes are unenforceable (e.g., California, India), THE Risk_Analyzer SHALL indicate "NON_COMPETE_UNLIKELY" and estimate zero restriction months.
4. THE Risk_Analyzer SHALL combine notice period and non-compete estimate into a "earliest_available_date" relative to the approach date.
5. THE Risk_Analyzer SHALL flag estimates with a confidence level (HIGH for countries with clear statutory rules, MEDIUM for common-law jurisdictions, LOW for jurisdictions with limited public data).

### Requirement 9: Gap Heatmap and Fit Analysis

**User Story:** As an executive search consultant, I want to see a visual heatmap of how each candidate's scores compare to the target role's requirements, so that I can identify development needs at a glance.

#### Acceptance Criteria

1. WHEN a candidate has scoring data from the scoring engine and a target role configuration exists, THE Readiness_Analyzer SHALL compute the gap for each of the 25 criteria as (role requirement threshold minus candidate score).
2. THE Readiness_Analyzer SHALL categorize each gap as EXCEEDS (score > requirement by 2+), MEETS (within 1 of requirement), DEVELOPMENT_NEEDED (2-3 below requirement), or CRITICAL_GAP (4+ below requirement).
3. THE Dashboard SHALL render the gap analysis as a heatmap visualization using D3.js with color coding: green for EXCEEDS, neutral for MEETS, amber for DEVELOPMENT_NEEDED, red for CRITICAL_GAP.
4. THE Readiness_Analyzer SHALL compute a "fit percentage" as the count of criteria at MEETS or EXCEEDS divided by 25, multiplied by 100.
5. THE Dashboard SHALL display the heatmap within the existing boardroom theme (navy/gold accent, Inter font, CSS custom properties).

### Requirement 10: Time-to-Readiness Estimation

**User Story:** As an executive search consultant, I want to estimate how many months a candidate needs before being fully ready for the target role, so that I can compare candidates on timeline.

#### Acceptance Criteria

1. WHEN a gap analysis is complete, THE Readiness_Analyzer SHALL compute time-to-readiness in months based on the sum of estimated closure times for each DEVELOPMENT_NEEDED and CRITICAL_GAP criterion.
2. THE Readiness_Analyzer SHALL apply per-criterion development velocity estimates: 3 months per point for skills-based criteria (functional_excellence, financial_acumen, digital_fluency), 6 months per point for behavioral criteria (emotional_intelligence, adaptability, self_awareness), and 12 months per point for experience-based criteria (board_governance, crisis_leadership).
3. WHEN multiple gaps exist, THE Readiness_Analyzer SHALL apply a concurrency factor of 0.6 (some development happens in parallel) to the raw sum.
4. THE Readiness_Analyzer SHALL cap time-to-readiness at 36 months; candidates exceeding this threshold SHALL be flagged as "NOT_READY_WITHIN_PLANNING_HORIZON".
5. THE Readiness_Analyzer SHALL categorize readiness as READY_NOW (0 months), NEAR_READY (1-6 months), DEVELOPING (7-18 months), LONG_TERM (19-36 months), or BEYOND_HORIZON (36+ months).

### Requirement 11: Development Cost and ROI Estimation

**User Story:** As an executive search consultant, I want to estimate the investment needed to develop a candidate to readiness and compare it against the value of filling the role, so that I can recommend the most cost-effective option.

#### Acceptance Criteria

1. WHEN time-to-readiness and gap analysis are complete, THE Readiness_Analyzer SHALL compute a development cost estimate in USD based on standard cost assumptions per gap type: executive coaching ($25,000/quarter), international rotation ($150,000/assignment), technical upskilling ($10,000/program), board exposure program ($50,000/year).
2. THE Readiness_Analyzer SHALL compute an ROI estimate as (annual value of filled role minus total acquisition cost minus development cost) divided by total acquisition cost, expressed as a percentage.
3. WHEN the ROI estimate is negative, THE Readiness_Analyzer SHALL flag the candidate as "NEGATIVE_ROI" and display the breakeven timeline in months.
4. THE Readiness_Analyzer SHALL allow the user to override standard cost assumptions with organization-specific values stored in the tenant configuration.
5. THE Readiness_Analyzer SHALL rank candidates by ROI estimate as an alternative sorting option alongside composite score.

### Requirement 12: Process Stage Tracking

**User Story:** As an executive search consultant, I want to track each candidate through standard executive search phases, so that I can manage the pipeline efficiently and identify bottlenecks.

#### Acceptance Criteria

1. THE Process_Tracker SHALL support the following ordered stages: LONG_LIST, SHORT_LIST, APPROACH, SCREEN, ASSESS, OFFER, CLOSE, ONBOARD.
2. WHEN a candidate's stage is advanced, THE Process_Tracker SHALL record the transition timestamp, the user who advanced the stage, and an optional note.
3. THE Process_Tracker SHALL compute days_in_stage as the number of calendar days since the candidate entered the current stage.
4. WHEN days_in_stage exceeds the SLA_Days for that stage, THE Process_Tracker SHALL flag the candidate as "SLA_BREACH" and surface the breach in the dashboard.
5. THE Process_Tracker SHALL apply default SLA_Days per stage: LONG_LIST (14), SHORT_LIST (7), APPROACH (10), SCREEN (14), ASSESS (21), OFFER (7), CLOSE (14), ONBOARD (30).

### Requirement 13: Process Timeline Visualization

**User Story:** As an executive search consultant, I want a visual timeline showing how candidates move through search phases, so that I can identify slow stages and optimize the process.

#### Acceptance Criteria

1. THE Dashboard SHALL render a timeline visualization using D3.js showing each candidate's progression through Process_Stages as a horizontal bar chart (Gantt-style).
2. WHEN a candidate is in SLA_BREACH, THE Dashboard SHALL highlight the overdue stage segment in red.
3. THE Dashboard SHALL display average days per stage across all candidates as a benchmark line on the timeline visualization.
4. THE Dashboard SHALL allow filtering the timeline view by current stage, SLA status, and candidate name.
5. THE Dashboard SHALL render the timeline within the existing boardroom theme (navy/gold accent, Inter font, consistent with succession-dashboard.html styling).

### Requirement 14: Compensation Data Persistence

**User Story:** As an executive search consultant, I want compensation intelligence to be stored persistently, so that I can track how estimates change over time and maintain an audit trail.

#### Acceptance Criteria

1. THE Compensation_Engine SHALL persist all compensation estimates to the succession schema in Aurora PostgreSQL with tenant_id isolation via Row-Level Security.
2. THE Compensation_Engine SHALL store each estimate with a timestamp, source confidence level, and the Lookup_Table version used.
3. WHEN a compensation estimate is recomputed for the same candidate, THE Compensation_Engine SHALL retain the previous estimate as a historical record (append-only, no overwrites).
4. THE Compensation_Engine SHALL support retrieval of compensation history for a candidate sorted by timestamp descending.
5. THE Process_Tracker SHALL persist stage transitions to the succession schema with tenant_id isolation, transition timestamps, acting user, and notes.

### Requirement 15: AI-Enhanced Data Enrichment

**User Story:** As an executive search consultant, I want the system to use AI to supplement compensation and risk data from public sources, so that I get the most complete picture without manual research.

#### Acceptance Criteria

1. WHEN Lookup_Table data provides LOW confidence estimates, THE Research_Agent SHALL attempt to enrich compensation data using Brave Search queries for public benchmarks, industry surveys, and proxy data.
2. THE Research_Agent SHALL use Bedrock Haiku to extract structured compensation indicators from search results and map them to the Lookup_Table schema.
3. WHEN enrichment produces higher-confidence data, THE Compensation_Engine SHALL update the estimate and upgrade the confidence level while retaining the original estimate in history.
4. THE Research_Agent SHALL rate-limit enrichment queries to a maximum of 10 candidates per batch to avoid API throttling.
5. IF the Research_Agent enrichment produces no usable data, THEN THE Compensation_Engine SHALL retain the original LOW confidence estimate and log the failed enrichment attempt.

### Requirement 16: Dashboard Integration

**User Story:** As an executive search consultant, I want all compensation intelligence, risk scores, and process tracking to appear within the existing succession dashboard, so that I have a single view for decision-making.

#### Acceptance Criteria

1. THE Dashboard SHALL add a "Compensation & Risk" tab to the existing succession dashboard navigation.
2. WHEN a candidate is selected, THE Dashboard SHALL display a summary card showing Total_Compensation, Comp_Gap, Flight_Risk_Score, Poachability_Score, Cultural_Adaptation_Risk, and current Process_Stage.
3. THE Dashboard SHALL render compensation and risk data using the existing boardroom theme CSS custom properties (--primary, --accent, --surface, --border, --radius, --shadow variables).
4. THE Dashboard SHALL use D3.js for the gap heatmap, process timeline, and any comparative visualizations.
5. WHEN data is loading, THE Dashboard SHALL display a skeleton placeholder consistent with existing dashboard loading patterns.
