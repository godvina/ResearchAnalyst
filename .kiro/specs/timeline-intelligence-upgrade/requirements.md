# Requirements Document

## Introduction

The Timeline Intelligence Upgrade transforms the existing investigative timeline from a raw date-entity plot into a production-grade investigative analysis tool. The current implementation (delivered by the investigative-timeline spec) suffers from critical usability problems observed in production testing with the Epstein Combined case (33 events, 75 entities, 19 gaps): noise dates from historical references (e.g., "Immigration Act of 1882") stretch the timeline to span 135+ years, making the relevant 1990s–2017 events unreadable; the clustering algorithm returns 0 clusters despite 33 events; event labels show truncated graph IDs instead of readable names; the default flat view is less useful than swim lanes; and the AI analysis treats noise gaps as real investigative findings. This upgrade addresses all of these problems by adding noise date filtering, investigative phase detection, auto-fit zoom, compact layout, readable labels, quick zoom presets, an investigative narrative header, and clustering fixes — bringing the tool in line with best-practice investigative platforms (Palantir Gotham, i2 Analyst's Notebook, Nuix).

## Glossary

- **Timeline_Service**: The existing Python backend service (src/services/timeline_service.py) that reconstructs chronological events, performs clustering, and detects gaps — extended by this upgrade
- **Timeline_UI**: The Timeline tab in the Investigator frontend (src/frontend/investigator.html) — modified by this upgrade
- **Noise_Date**: A date entity extracted by NLP that references a historical event, legislation, or other non-case-relevant date (e.g., "Immigration Act of 1882", "founded in 1953") rather than an actual event in the case timeline
- **Relevant_Date_Range**: The contiguous time window containing the dense cluster of actual case events, auto-detected by analyzing event density distribution
- **Investigative_Phase**: A labeled period within the timeline representing a stage of criminal or investigative activity (e.g., "Pre-Criminal Activity", "Active Criminal Period", "Investigation Phase", "Legal Proceedings"), detected by AI or rule-based analysis
- **Narrative_Header**: A one-line AI-generated summary displayed above the timeline that describes what the timeline shows in investigative terms (e.g., "Criminal activity spanning 1999–2019 involving 12 key persons across 4 locations")
- **Density_Cluster**: The largest contiguous group of events identified by kernel density estimation or histogram analysis, used to determine the Relevant_Date_Range
- **Quick_Zoom_Preset**: A predefined zoom button that instantly adjusts the timeline viewport to a specific time window (e.g., "Last Year", "Last 5 Years", "Dense Period", "Full Range")
- **Event_Label**: The human-readable text displayed on a timeline event marker, composed of entity names, date, and event description rather than raw graph IDs

## Requirements

### Requirement 1: Noise Date Filtering

**User Story:** As an investigator, I want the timeline to automatically filter out historical reference dates that are not actual case events, so that the timeline shows only the relevant time period without being stretched by noise data from NLP extraction.

#### Acceptance Criteria

1. WHEN the Timeline_Service reconstructs a timeline, THE Timeline_Service SHALL compute a noise date cutoff by analyzing the event density distribution and identifying the Relevant_Date_Range where the majority of events are concentrated
2. THE Timeline_Service SHALL classify any event with a timestamp more than 20 years before the start of the Density_Cluster as a Noise_Date by default, unless the investigator has overridden the cutoff
3. THE Timeline_Service SHALL accept an optional `noise_cutoff_year` parameter that allows the investigator to manually set the earliest year to include in the timeline
4. WHEN Noise_Dates are filtered, THE Timeline_Service SHALL include a `filtered_noise_events` array in the response containing the excluded events with their timestamps and entity names, so the investigator can review what was removed
5. THE Timeline_Service SHALL include a `noise_filter_summary` object in the response containing: the auto-detected cutoff year, the number of events filtered, and the Relevant_Date_Range start and end dates
6. THE Timeline_UI SHALL display a toggle control labeled "Show noise dates" that allows the investigator to include or exclude Noise_Dates from the timeline view
7. WHEN the "Show noise dates" toggle is enabled, THE Timeline_UI SHALL render Noise_Dates with a distinct muted visual style (reduced opacity, dashed border) to differentiate them from relevant events
8. IF all events in a case fall within a 20-year window, THEN THE Timeline_Service SHALL apply no noise filtering and set the cutoff to the earliest event date

### Requirement 2: Relevant Date Range Auto-Fit

**User Story:** As an investigator, I want the timeline to automatically zoom to the dense cluster of events when it loads, so that I see the relevant activity period filling the screen instead of a 135-year span with events crammed into a tiny sliver.

#### Acceptance Criteria

1. WHEN the timeline loads, THE Timeline_UI SHALL auto-fit the viewport to the Relevant_Date_Range (after noise filtering) with 5% padding on each side, instead of fitting to the full min-max range of all events
2. THE Timeline_Service SHALL compute the Relevant_Date_Range by finding the smallest time window that contains at least 80% of the non-noise events
3. WHEN the Relevant_Date_Range is computed, THE Timeline_Service SHALL return it as `relevant_range` with `start` and `end` ISO 8601 timestamps in the response
4. IF the investigator enables "Show noise dates", THEN THE Timeline_UI SHALL maintain the current viewport position and add noise events at their positions without re-fitting to the full range

### Requirement 3: Investigative Phase Detection

**User Story:** As an investigator, I want the timeline to show labeled investigative phases (e.g., "Early Activity", "Peak Criminal Period", "Investigation", "Legal Proceedings"), so that I can understand the narrative arc of the case at a glance.

#### Acceptance Criteria

1. WHEN the Timeline_Service reconstructs a timeline with 5 or more events, THE Timeline_Service SHALL detect and label Investigative_Phases by analyzing event types, entity patterns, and temporal distribution
2. THE Timeline_Service SHALL detect phases from the following categories: "Pre-Criminal Activity", "Early Activity", "Escalation", "Peak Activity", "Active Criminal Period", "Investigation Phase", "Legal Proceedings", and "Post-Resolution" — selecting the phases that apply to the case data
3. THE Timeline_Service SHALL assign each Investigative_Phase a start date, end date, label, and a one-sentence description explaining the phase
4. THE Timeline_UI SHALL render Investigative_Phases as labeled horizontal bands behind the event markers, with distinct background colors for each phase category
5. WHEN an investigator hovers over an Investigative_Phase band, THE Timeline_UI SHALL display a tooltip showing the phase description and the number of events within that phase
6. IF the Timeline_Service cannot confidently detect phases (fewer than 5 events or insufficient event type variety), THEN THE Timeline_Service SHALL omit the phases array and THE Timeline_UI SHALL not render phase bands

### Requirement 4: Investigative Narrative Header

**User Story:** As an investigator, I want a one-line AI-generated summary above the timeline that tells me what the timeline represents in investigative terms, so that I immediately understand the scope and significance of what I am looking at.

#### Acceptance Criteria

1. WHEN the timeline loads with events, THE Timeline_Service SHALL generate a Narrative_Header summarizing the timeline in one sentence, including: the time span of relevant activity, the count of key persons and locations, and the primary event types observed
2. THE Timeline_Service SHALL generate the Narrative_Header using Bedrock Claude with a prompt that produces investigative-style language (e.g., "Criminal activity spanning 1999–2019 involving 12 key persons across 4 locations with 8 financial transactions and 15 communications")
3. THE Timeline_UI SHALL display the Narrative_Header in a prominent banner above the timeline canvas, styled with the accent color (#48bb78) and a font size of at least 14px
4. WHILE the Narrative_Header is being generated, THE Timeline_UI SHALL display a placeholder text "Generating investigative summary..." with a loading indicator
5. IF the Narrative_Header generation fails, THEN THE Timeline_UI SHALL display a fallback summary computed from the event data without AI (e.g., "33 events from Jan 1999 to Dec 2019 involving 12 entities")

### Requirement 5: Better Event Labels

**User Story:** As an investigator, I want event markers to show readable entity names, dates, and event descriptions instead of truncated graph IDs, so that I can understand each event without clicking on it.

#### Acceptance Criteria

1. THE Timeline_UI SHALL display each event marker label as: the event type icon, followed by the top 2 entity names (full names, not truncated), followed by the formatted date (e.g., "📞 John Smith, Jane Doe — Mar 15, 2019")
2. WHEN an entity name exceeds 25 characters, THE Timeline_UI SHALL truncate the name at 25 characters with an ellipsis, preserving the first and last name components where possible
3. THE Timeline_UI SHALL render event labels with a minimum font size of 11px and a maximum width of 200px, with text wrapping to a second line if needed
4. THE Timeline_Service SHALL return a `display_label` field for each event containing a pre-formatted human-readable label composed of entity names and event type, excluding raw graph IDs or internal identifiers
5. IF an event has no associated entity names, THEN THE Timeline_UI SHALL display the event type label and formatted date as the marker label (e.g., "📄 Document — Mar 15, 2019")

### Requirement 6: Default Swim Lane View

**User Story:** As an investigator, I want the timeline to default to swim lane view instead of flat view, so that I can immediately compare parallel entity activity without switching views manually.

#### Acceptance Criteria

1. WHEN the timeline loads, THE Timeline_UI SHALL default to the swim lane view mode instead of the flat view mode
2. THE Timeline_UI SHALL pre-select the top 5 entities by event count for the initial swim lane display, consistent with the existing entity picker behavior
3. WHEN the investigator switches to flat or cluster view and then reloads the timeline, THE Timeline_UI SHALL restore the swim lane view as the default

### Requirement 7: Quick Zoom Presets

**User Story:** As an investigator, I want quick zoom preset buttons (e.g., "Last Year", "Last 5 Years", "Dense Period", "Full Range"), so that I can rapidly navigate to time windows of interest without manual zooming and panning.

#### Acceptance Criteria

1. THE Timeline_UI SHALL display a row of Quick_Zoom_Preset buttons above the timeline canvas, adjacent to the existing zoom controls
2. THE Timeline_UI SHALL provide the following preset buttons: "1Y" (last 1 year of events), "5Y" (last 5 years of events), "Dense" (the Relevant_Date_Range), and "All" (full range including noise dates)
3. WHEN the investigator clicks a Quick_Zoom_Preset button, THE Timeline_UI SHALL animate the viewport transition to the selected time window within 300ms
4. THE Timeline_UI SHALL visually highlight the currently active Quick_Zoom_Preset button with the accent color (#48bb78)
5. WHEN the investigator manually zooms or pans after selecting a preset, THE Timeline_UI SHALL deselect the active preset button to indicate a custom view

### Requirement 8: Compact Layout

**User Story:** As an investigator, I want the timeline and AI analysis panel to form a single compact view with no wasted space, so that I can see both the visual timeline and the AI insights without scrolling past blank areas.

#### Acceptance Criteria

1. THE Timeline_UI SHALL render the AI analysis panel as a collapsible section directly below the timeline canvas with zero gap between them
2. THE Timeline_UI SHALL remove any fixed-height spacers or padding between the timeline canvas and the AI analysis panel
3. WHEN the AI analysis panel is collapsed, THE Timeline_UI SHALL display a single-line summary bar showing "AI Analysis" with an expand button, occupying no more than 40px of vertical space
4. THE Timeline_UI SHALL set the timeline canvas height to dynamically fit its content (number of swim lanes or event density) with a minimum height of 200px and a maximum height of 500px
5. THE Timeline_UI SHALL ensure the density bar, timeline canvas, and AI panel stack vertically with no more than 8px of spacing between each component

### Requirement 9: Clustering Algorithm Fix

**User Story:** As an investigator, I want the event clustering to actually produce clusters when events exist within the time window, so that I can identify bursts of coordinated activity as designed.

#### Acceptance Criteria

1. WHEN the Timeline_Service clusters events with a 48-hour window and the case contains events within 48 hours of each other, THE Timeline_Service SHALL produce at least one Activity_Cluster
2. THE Timeline_Service SHALL use the Relevant_Date_Range (post noise filtering) as the basis for clustering, so that noise dates separated by decades do not prevent clustering of relevant events
3. WHEN computing shared entities for clustering, THE Timeline_Service SHALL consider entity co-occurrence within the same source documents as a shared entity relationship, even if the entities are not directly connected by graph edges
4. THE Timeline_Service SHALL log the clustering input (event count, window hours, entity overlap counts) and output (cluster count) at INFO level for debugging
5. IF the clustering algorithm produces 0 clusters for a case with 10 or more events within the Relevant_Date_Range, THEN THE Timeline_Service SHALL log a WARNING with diagnostic information including: the number of events considered, the time span, and the entity overlap statistics

### Requirement 10: AI Analysis Noise Awareness

**User Story:** As an investigator, I want the AI analysis to only analyze relevant events and not treat noise date gaps as real investigative findings, so that the analysis provides actionable intelligence instead of flagging "81-year gaps" caused by historical reference dates.

#### Acceptance Criteria

1. WHEN generating AI analysis, THE Timeline_Service SHALL send only non-noise events and non-noise gaps to the Bedrock Claude model
2. THE Timeline_Service SHALL include the noise filter summary in the AI analysis prompt so that the model understands that historical reference dates have been excluded
3. THE Timeline_Service SHALL instruct the Bedrock Claude model to focus analysis on the Relevant_Date_Range and to not reference any dates outside that range
4. WHEN the AI analysis references temporal gaps, THE Timeline_Service SHALL ensure the gaps provided to the model are computed from the noise-filtered event set only
