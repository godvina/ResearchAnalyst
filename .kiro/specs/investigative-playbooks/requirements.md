# Requirements Document

## Introduction

The investigator UI has been consolidated from 16 tabs to 6 focused tabs (Dashboard, Lead Investigation, Evidence Library, Timeline, Map, Portfolio), but there is no guided workflow connecting these tabs into a coherent investigative methodology. Investigators must figure out the investigation process themselves, switching between tabs without structured guidance. This feature adds Investigation Playbooks — persistent sidebar panels that guide investigators through step-by-step workflows modeled after Palantir Gotham's Investigation Playbooks. Each playbook is a checklist with intelligence: steps know which tab to navigate to, track completion status, support notes, and persist progress per case in localStorage. Three built-in playbook templates cover common investigation types (General, Financial Fraud, Human Trafficking/Exploitation). This is a frontend-only feature — no backend changes, no new API endpoints. All step actions use existing APIs and tab navigation.

## Glossary

- **Playbook_Panel**: A collapsible sidebar panel on the right side of the investigator UI that displays the active playbook's step list, progress bar, and controls
- **Playbook_Toggle_Button**: A small button visible when the Playbook_Panel is collapsed, showing "📋 Playbook" with a progress indicator (e.g., "4/10")
- **Playbook_Template**: A hardcoded JavaScript object defining a playbook's name, description, and ordered list of steps with metadata (title, description, target tab, action type)
- **Playbook_Step**: An individual step within a playbook template, containing a title, description, target tab identifier, status, optional notes, and optional auto-check condition
- **Step_Status**: The workflow state of a playbook step: pending, in_progress, complete, or skipped
- **Playbook_State**: The persisted state of a playbook instance for a specific case, including the selected template, step statuses, step notes, and active step index, stored in localStorage
- **Playbook_Selector**: A dropdown at the top of the Playbook_Panel that allows the investigator to choose from available playbook templates
- **Progress_Bar**: A horizontal bar at the top of the Playbook_Panel showing overall completion percentage based on completed and skipped steps
- **Navigate_Action**: A button on each playbook step that auto-switches the investigator UI to the step's target tab
- **Active_Step**: The currently highlighted step in the playbook, indicated by a blue border
- **Entity_Dossier_Panel**: The existing slide-out panel (z-index 200) that opens when entity names are clicked — the Playbook_Panel must not interfere with this panel
- **Investigator_UI**: The investigator.html single-page application
- **Tab_Bar**: The horizontal navigation bar containing the 6 workflow tabs
- **General_Investigation_Playbook**: The default 10-step playbook template covering a standard investigation workflow across all tabs
- **Financial_Fraud_Playbook**: A 10-step playbook template specialized for financial fraud investigations
- **Human_Trafficking_Playbook**: A 10-step playbook template specialized for human trafficking and exploitation investigations

## Requirements

### Requirement 1: Playbook Panel Layout and Visibility

**User Story:** As an investigator, I want a collapsible playbook sidebar so that I can follow a guided workflow without losing screen space when I don't need it.

#### Acceptance Criteria

1. THE Investigator_UI SHALL render the Playbook_Panel as a fixed-position panel on the right side of the screen, 320 pixels wide, spanning the full height below the header and tab bar
2. THE Playbook_Panel SHALL use a z-index lower than the Entity_Dossier_Panel (z-index 200) so that the Entity_Dossier_Panel overlays the Playbook_Panel when both are visible
3. THE Playbook_Panel SHALL include a collapse button in its header that hides the panel and shows the Playbook_Toggle_Button
4. WHEN the Playbook_Panel is collapsed, THE Investigator_UI SHALL display the Playbook_Toggle_Button as a small fixed-position button on the right edge of the screen showing "📋 Playbook" and a progress indicator in the format "N/M" where N is completed steps and M is total steps
5. WHEN the Playbook_Toggle_Button is clicked, THE Investigator_UI SHALL expand the Playbook_Panel to its full 320-pixel width
6. THE Playbook_Panel SHALL have a dark background consistent with the existing UI theme (#1a2332 background, #2d3748 borders, #48bb78 accent color)
7. WHEN no case is selected, THE Playbook_Panel SHALL display a message prompting the investigator to select a case from the Case Dashboard

### Requirement 2: Playbook Template Selection

**User Story:** As an investigator, I want to choose from different playbook templates so that I can follow a workflow tailored to my investigation type.

#### Acceptance Criteria

1. THE Playbook_Panel SHALL display a Playbook_Selector dropdown at the top of the panel listing all available Playbook_Templates by name
2. THE Playbook_Selector SHALL include the following templates: General Investigation Playbook, Financial Fraud Playbook, Human Trafficking / Exploitation Playbook
3. WHEN an investigator selects a new Playbook_Template from the Playbook_Selector, THE Playbook_Panel SHALL reset all step statuses to "pending", clear all step notes, set the active step to step 1, and update the Progress_Bar to 0%
4. WHEN a new template is selected, THE Playbook_Panel SHALL persist the new Playbook_State to localStorage for the current case
5. WHEN a case is selected and a Playbook_State exists in localStorage for that case, THE Playbook_Panel SHALL restore the previously saved template selection, step statuses, step notes, and active step

### Requirement 3: Playbook Step Display

**User Story:** As an investigator, I want to see all playbook steps with clear status indicators so that I know where I am in the investigation process.

#### Acceptance Criteria

1. THE Playbook_Panel SHALL display all steps of the selected Playbook_Template as a vertical list with step number, title, and a status icon
2. THE Playbook_Step SHALL display a status icon based on Step_Status: a circle outline for pending, a blue filled circle for in_progress, a green checkmark for complete, and a gray dash for skipped
3. THE Active_Step SHALL be visually highlighted with a blue left border (#4299e1) to distinguish it from other steps
4. WHEN an investigator clicks on a Playbook_Step, THE Playbook_Panel SHALL expand that step to show its description, action buttons (Navigate, Mark Complete, Skip, Add Note), and any saved notes
5. THE Playbook_Panel SHALL collapse previously expanded steps when a new step is expanded, showing only one expanded step at a time

### Requirement 4: Step Navigation Action

**User Story:** As an investigator, I want each playbook step to navigate me to the right tab so that I don't have to manually find the correct tool for each step.

#### Acceptance Criteria

1. WHEN an investigator clicks the "Navigate" button on a Playbook_Step, THE Investigator_UI SHALL call the existing switchTab function with the step's target tab identifier, switching the active tab to the step's designated tab
2. WHEN the Navigate action is triggered, THE Playbook_Panel SHALL update the step's status from "pending" to "in_progress" if the step was previously pending
3. THE Navigate action SHALL set the clicked step as the Active_Step in the Playbook_Panel

### Requirement 5: Step Completion and Skip Actions

**User Story:** As an investigator, I want to mark steps as complete or skip them so that I can track my progress through the investigation.

#### Acceptance Criteria

1. WHEN an investigator clicks "Mark Complete" on a Playbook_Step, THE Playbook_Panel SHALL update the step's status to "complete", display a green checkmark icon, and advance the Active_Step to the next pending or in_progress step
2. WHEN an investigator clicks "Skip" on a Playbook_Step, THE Playbook_Panel SHALL update the step's status to "skipped", display a gray dash icon, and advance the Active_Step to the next pending or in_progress step
3. WHEN a step status changes, THE Playbook_Panel SHALL update the Progress_Bar to reflect the new completion percentage calculated as (completed + skipped) / total steps
4. WHEN a step status changes, THE Playbook_Panel SHALL persist the updated Playbook_State to localStorage for the current case
5. WHEN all steps are marked as complete or skipped, THE Playbook_Panel SHALL display a completion message below the Progress_Bar indicating the playbook is finished

### Requirement 6: Step Notes

**User Story:** As an investigator, I want to add notes to individual playbook steps so that I can record observations and findings as I work through the investigation.

#### Acceptance Criteria

1. WHEN an investigator clicks "Add Note" on a Playbook_Step, THE Playbook_Panel SHALL display a text input area below the step's action buttons
2. WHEN the investigator types a note and clicks "Save Note" or presses Enter, THE Playbook_Panel SHALL save the note text to the step's Playbook_State and persist to localStorage
3. WHEN a step has a saved note, THE Playbook_Panel SHALL display the note text below the step description with a small note icon and timestamp
4. THE Playbook_Panel SHALL allow the investigator to edit an existing note by clicking on the displayed note text

### Requirement 7: Progress Bar

**User Story:** As an investigator, I want a visual progress bar so that I can see at a glance how far along I am in the investigation workflow.

#### Acceptance Criteria

1. THE Playbook_Panel SHALL display a Progress_Bar at the top of the step list, below the Playbook_Selector
2. THE Progress_Bar SHALL show a filled portion proportional to the percentage of steps that are complete or skipped, using green (#48bb78) for the filled portion
3. THE Progress_Bar SHALL display the completion percentage as text (e.g., "60%") next to the bar
4. WHEN the Playbook_Toggle_Button is visible (panel collapsed), THE Playbook_Toggle_Button SHALL display the progress as "N/M" where N is the count of completed steps and M is the total step count

### Requirement 8: Playbook State Persistence

**User Story:** As an investigator, I want my playbook progress saved per case so that I can resume where I left off after refreshing the page or switching cases.

#### Acceptance Criteria

1. THE Playbook_Panel SHALL persist the Playbook_State to localStorage using the key format `playbookState_{caseId}` where caseId is the selected case identifier
2. THE Playbook_State SHALL include: selected template identifier, array of step statuses, array of step notes with timestamps, active step index, and panel collapsed/expanded state
3. WHEN the investigator selects a case that has a saved Playbook_State in localStorage, THE Playbook_Panel SHALL restore the full state including template, step statuses, notes, active step, and panel visibility
4. WHEN the investigator selects a case that has no saved Playbook_State, THE Playbook_Panel SHALL default to the General_Investigation_Playbook with all steps set to "pending"
5. IF localStorage read or write fails, THEN THE Playbook_Panel SHALL continue operating with in-memory state and display a brief warning that progress may not be saved

### Requirement 9: General Investigation Playbook Template

**User Story:** As an investigator, I want a general-purpose playbook that walks me through a standard investigation workflow so that I have a structured approach for any case type.

#### Acceptance Criteria

1. THE General_Investigation_Playbook SHALL contain 10 steps in the following order: Review AI Briefing, Triage Top Leads, Investigate Priority Subjects, Review Evidence, Map Connections, Analyze Timeline, Check Geospatial Data, Document Findings, Assess Case Strength, Generate Report
2. THE "Review AI Briefing" step SHALL target the Dashboard tab and include a description instructing the investigator to review the AI-generated case briefing and key findings
3. THE "Triage Top Leads" step SHALL target the Lead Investigation tab and include a description instructing the investigator to review and prioritize the top 5 AI-generated leads
4. THE "Investigate Priority Subjects" step SHALL target the Lead Investigation tab and include a description instructing the investigator to run investigative searches on high-priority leads
5. THE "Review Evidence" step SHALL target the Evidence Library tab and include a description instructing the investigator to review key documents, images, and media
6. THE "Map Connections" step SHALL target the Dashboard tab and include a description instructing the investigator to explore entity relationships in the knowledge graph
7. THE "Analyze Timeline" step SHALL target the Timeline tab and include a description instructing the investigator to review the event sequence and identify patterns
8. THE "Check Geospatial Data" step SHALL target the Map tab and include a description instructing the investigator to review locations and geographic patterns
9. THE "Document Findings" step SHALL target the Dashboard tab and include a description instructing the investigator to save key findings to the Research Notebook
10. THE "Assess Case Strength" step SHALL target the Lead Investigation tab and include a description instructing the investigator to review confidence levels across all assessed leads
11. THE "Generate Report" step SHALL have no target tab and include a description noting that court-ready export is a future enhancement

### Requirement 10: Financial Fraud Playbook Template

**User Story:** As an investigator working a financial fraud case, I want a specialized playbook so that I follow a workflow optimized for tracing financial crimes.

#### Acceptance Criteria

1. THE Financial_Fraud_Playbook SHALL contain 10 steps in the following order: Review AI Briefing, Identify Financial Entities, Trace Money Flow, Cross-Reference Public Records, Map Corporate Structure, Review Transaction Timeline, Identify Regulatory Violations, Document Evidence Chain, Assess Prosecution Readiness, Prepare Case Summary
2. THE "Identify Financial Entities" step SHALL target the Lead Investigation tab and include a description instructing the investigator to search for organizations, accounts, and transactions
3. THE "Trace Money Flow" step SHALL target the Dashboard tab and include a description instructing the investigator to investigate financial connections in the knowledge graph
4. THE "Cross-Reference Public Records" step SHALL target the Dashboard tab and include a description instructing the investigator to use Internal+External search scope
5. THE "Map Corporate Structure" step SHALL target the Dashboard tab and include a description instructing the investigator to explore organization entities in the graph
6. THE "Review Transaction Timeline" step SHALL target the Timeline tab and include a description instructing the investigator to check the timeline for financial events
7. THE "Identify Regulatory Violations" step SHALL target the Dashboard tab and include a description instructing the investigator to search for compliance-related keywords
8. THE "Document Evidence Chain" step SHALL target the Dashboard tab and include a description instructing the investigator to save findings with source citations to the Research Notebook
9. THE "Assess Prosecution Readiness" step SHALL target the Lead Investigation tab and include a description instructing the investigator to review case viability across assessed leads
10. THE "Prepare Case Summary" step SHALL have no target tab and include a description noting that court-ready export is a future enhancement

### Requirement 11: Human Trafficking / Exploitation Playbook Template

**User Story:** As an investigator working a human trafficking or exploitation case, I want a specialized playbook so that I follow a workflow optimized for victim identification and evidence chain building.

#### Acceptance Criteria

1. THE Human_Trafficking_Playbook SHALL contain 10 steps in the following order: Review AI Briefing, Identify Victims and Perpetrators, Map Travel Patterns, Analyze Communication Networks, Review Document Evidence, Cross-Reference External Sources, Build Timeline of Events, Identify Witnesses and Corroboration, Document Chain of Evidence, Case Assessment and Referral
2. THE "Identify Victims and Perpetrators" step SHALL target the Lead Investigation tab and include a description instructing the investigator to triage leads by person type and role
3. THE "Map Travel Patterns" step SHALL target the Map tab and include a description instructing the investigator to check geospatial data for travel locations and patterns
4. THE "Analyze Communication Networks" step SHALL target the Dashboard tab and include a description instructing the investigator to explore graph connections between persons
5. THE "Review Document Evidence" step SHALL target the Evidence Library tab and include a description instructing the investigator to check the evidence library for key documents
6. THE "Cross-Reference External Sources" step SHALL target the Dashboard tab and include a description instructing the investigator to use Internal+External search scope
7. THE "Build Timeline of Events" step SHALL target the Timeline tab and include a description instructing the investigator to review the timeline for event patterns
8. THE "Identify Witnesses and Corroboration" step SHALL target the Lead Investigation tab and include a description instructing the investigator to search for corroborating entities
9. THE "Document Chain of Evidence" step SHALL target the Dashboard tab and include a description instructing the investigator to save findings with source citations
10. THE "Case Assessment and Referral" step SHALL have no target tab and include a description noting that case referral workflow is a future enhancement

### Requirement 12: Panel Does Not Interfere with Existing UI

**User Story:** As an investigator, I want the playbook panel to coexist with the Entity Dossier panel and all existing tabs so that the playbook does not break any existing functionality.

#### Acceptance Criteria

1. THE Playbook_Panel SHALL use a z-index below 200 so that the Entity_Dossier_Panel (z-index 200) renders above the Playbook_Panel when both are visible
2. WHEN the Playbook_Panel is expanded, THE main content area of the active tab SHALL reduce its width to accommodate the 320-pixel panel without horizontal scrolling
3. THE Playbook_Panel SHALL not modify any existing HTML elements, CSS classes, or JavaScript functions in the investigator UI
4. THE Playbook_Panel SHALL be implemented as self-contained HTML, CSS, and JavaScript appended to the existing investigator.html file

### Requirement 13: Keyboard Accessibility

**User Story:** As an investigator, I want to toggle the playbook panel with a keyboard shortcut so that I can quickly show or hide it without using the mouse.

#### Acceptance Criteria

1. WHEN the investigator presses Ctrl+Shift+P (or Cmd+Shift+P on macOS), THE Investigator_UI SHALL toggle the Playbook_Panel between expanded and collapsed states
2. THE keyboard shortcut SHALL not conflict with any existing keyboard shortcuts in the investigator UI (Escape is used for Entity Dossier close)

### Requirement 14: Multiple Playbooks Per Case

**User Story:** As an investigator, I want to switch between playbook templates for the same case so that I can try different investigation approaches.

#### Acceptance Criteria

1. THE Playbook_Panel SHALL allow the investigator to select a different Playbook_Template at any time via the Playbook_Selector
2. WHEN a new Playbook_Template is selected for a case that already has playbook progress, THE Playbook_Panel SHALL reset all step statuses to "pending" and clear all step notes for the new template
3. THE Playbook_Panel SHALL persist only the currently active playbook's state per case — switching templates replaces the saved state

### Requirement 15: Playbook Panel Initial State

**User Story:** As an investigator, I want the playbook panel to start collapsed so that it does not take up screen space until I choose to use it.

#### Acceptance Criteria

1. WHEN the investigator UI loads for the first time (no saved Playbook_State in localStorage), THE Playbook_Panel SHALL start in the collapsed state showing only the Playbook_Toggle_Button
2. WHEN a saved Playbook_State exists with the panel in expanded state, THE Playbook_Panel SHALL restore to the expanded state on page load
