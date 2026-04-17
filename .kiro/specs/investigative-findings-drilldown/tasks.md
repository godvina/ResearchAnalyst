# Implementation Plan: Investigative Findings Drilldown

## Overview

Replace the entity drill-down panel's static "⚡ KEY INSIGHTS" section with a 3-level progressive investigation drilldown powered by AI-generated narrative leads. Backend introduces LeadGeneratorService and EvidenceAssemblerService with two new API routes. Frontend rewrites the DrillDown panel insights section into a stateful, breadcrumb-navigated, slide-animated 3-level experience.

## Tasks

- [x] 1. Create data models and LeadGeneratorService
  - [x] 1.1 Define data model classes (InvestigationLead, EvidenceThread, EvidenceDocument, EvidenceEntity, TimelineEntry, RelationshipEdge)
    - Create `src/services/lead_generator_service.py` with dataclass definitions for all six data models
    - InvestigationLead: lead_id, narrative, lead_type, confidence, supporting_entity_names, document_count, date_range
    - EvidenceThread: documents (List[EvidenceDocument]), entities (List[EvidenceEntity]), timeline (List[TimelineEntry]), relationship_edges (List[RelationshipEdge])
    - _Requirements: 5.2, 6.2_

  - [x] 1.2 Implement LeadGeneratorService.generate_leads
    - Constructor takes aurora_cm, bedrock_client, neptune_endpoint, neptune_port, optional pattern_svc
    - Query Aurora for documents mentioning entity_name, query Neptune for 2-hop neighborhood and degree centrality
    - Build Bedrock Claude prompt with gathered context, parse structured JSON response into InvestigationLead objects
    - Assign lead_type from allowed set {temporal_gap, cross_case_link, entity_cluster, document_pattern, financial_anomaly, geographic_convergence, relationship_anomaly}
    - Assign confidence 0.0–1.0, sort by confidence descending, return 3–7 leads
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.3, 2.4_

  - [x] 1.3 Implement LeadGeneratorService._generate_fallback_leads
    - Generate 2+ fallback leads from graph statistics with narrative framing when Bedrock invocation fails
    - Fallback leads must have valid lead_type and confidence fields
    - _Requirements: 5.4_

  - [ ]* 1.4 Write property tests for LeadGeneratorService
    - **Property 1: Lead count bounds** — verify 3–7 leads returned for any valid entity context
    - **Property 2: Lead field value constraints** — verify lead_type in allowed set and confidence in [0.0, 1.0]
    - **Property 3: Lead narrative contains entity context** — verify narrative is non-empty and contains at least one input entity name
    - **Property 5: Leads sorted by confidence descending** — verify leads[i].confidence >= leads[i+1].confidence for all consecutive pairs
    - **Property 10: Fallback leads on Bedrock failure** — verify at least 2 fallback leads with valid fields when Bedrock fails
    - **Validates: Requirements 1.1, 1.2, 1.4, 1.5, 2.3, 5.4**

- [x] 2. Create EvidenceAssemblerService
  - [x] 2.1 Implement EvidenceAssemblerService.assemble_evidence
    - Create `src/services/evidence_assembler_service.py`
    - Constructor takes aurora_cm, neptune_endpoint, neptune_port
    - Query Aurora for documents containing any of entity_names, extract key quotes (up to 200 chars each)
    - Score document relevance to lead narrative, build chronological timeline of entity mentions
    - Query Neptune for relationship edges between entity_names
    - Cap at 20 documents, 30 entities; return EvidenceThread
    - _Requirements: 3.1, 3.2, 3.3, 3.6, 6.1, 6.2, 6.4_

  - [ ]* 2.2 Write property tests for EvidenceAssemblerService
    - **Property 6: Evidence documents match queried entities** — every document contains at least one mention of a queried entity
    - **Property 7: Key quote length cap** — every key_quote string has length <= 200
    - **Property 8: Timeline chronological order** — timeline entries sorted by date ascending
    - **Property 9: Evidence thread response caps** — len(documents) <= 20 and len(entities) <= 30
    - **Validates: Requirements 3.1, 3.2, 3.3, 6.4**

- [x] 3. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Add API routes for entity-leads and evidence-thread
  - [x] 4.1 Implement entity_leads_handler and evidence_thread_handler in investigator_analysis.py
    - Add `entity_leads_handler(event, context)` — extract case_id from pathParameters, parse JSON body for entity_name (required), entity_type, neighbors, doc_excerpts; call LeadGeneratorService.generate_leads; return JSON array of leads
    - Add `evidence_thread_handler(event, context)` — extract case_id, parse body for lead_id, entity_names, lead_type, narrative (all required); call EvidenceAssemblerService.assemble_evidence; return JSON response
    - Return HTTP 400 for missing required fields with descriptive error messages
    - Register both routes in the `dispatch_handler` routes dict: `("POST", "/case-files/{id}/entity-leads")` and `("POST", "/case-files/{id}/evidence-thread")`
    - _Requirements: 5.1, 5.2, 5.3, 6.1, 6.2, 6.3_

  - [x] 4.2 Wire routes in case_files.py dispatch_handler
    - Add path matching for `/entity-leads` and `/evidence-thread` in the case_files.py dispatch_handler to route to `investigator_analysis.dispatch_handler`
    - Place the routing block alongside existing investigator analysis route matching (near `/investigator-analysis`, `/entity-neighborhood`, etc.)
    - _Requirements: 5.1, 6.1_

  - [ ]* 4.3 Write unit tests for API handlers
    - Test entity_leads_handler with valid request, missing entity_name (400), Bedrock failure fallback
    - Test evidence_thread_handler with valid request, missing required fields (400)
    - Test routing in case_files.py dispatch_handler for new paths
    - _Requirements: 5.1, 5.2, 5.3, 6.1, 6.2, 6.3_

- [x] 5. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement frontend Level 1 — Investigation Leads
  - [x] 6.1 Add drilldown navigation state and breadcrumb rendering
    - Add `DrillDown.drilldownStack` array to hold `[{level, data, title, entityName, entityType}]` entries
    - Implement `DrillDown.breadcrumb()` to render clickable breadcrumb from stack (e.g., "Leads > Evidence Thread > Source Document")
    - Clicking a breadcrumb level restores that view from cached stack data without re-fetching
    - Add CSS slide animations (300ms horizontal slide: left for deeper, right for back)
    - _Requirements: 1.8, 7.1, 7.2, 7.3_

  - [x] 6.2 Implement DrillDown.renderLevel1(leads)
    - Replace the existing `_generateKeyInsights` call in `openEntity` with an async fetch to `POST /case-files/{id}/entity-leads`
    - Render each InvestigationLead as a card with: narrative text, lead_type badge, color-coded priority indicator (red >= 0.8, amber >= 0.5, green < 0.5)
    - Sort leads by confidence descending in the display
    - Show contextual loading indicator while fetching: "Generating investigation leads for '{entityName}'..."
    - On click of a lead card, push Level 2 onto drilldownStack and call renderLevel2
    - _Requirements: 1.1, 1.6, 1.7, 2.1, 2.2, 2.3, 7.4_

  - [ ]* 6.3 Write property test for confidence-to-color mapping
    - **Property 4: Confidence-to-color mapping** — red when confidence >= 0.8, amber when >= 0.5 and < 0.8, green when < 0.5
    - **Validates: Requirements 2.1**

- [x] 7. Implement frontend Level 2 — Evidence Thread
  - [x] 7.1 Implement DrillDown.renderLevel2(evidenceThread)
    - Fetch evidence thread via `POST /case-files/{id}/evidence-thread` with lead context
    - Render supporting documents list with key quotes and relevance scores
    - Render entity mention timeline sorted chronologically
    - Render focused relationship map showing only entities and edges relevant to the selected lead
    - Display summary count: number of documents, unique entities, date range
    - Show contextual loading indicator: "Assembling evidence thread for '{leadNarrative}'..."
    - On click of a document, push Level 3 onto drilldownStack and call renderLevel3
    - OSINT button must NOT appear at this level
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 7.4, 8.2_

- [x] 8. Implement frontend Level 3 — Source Documents
  - [x] 8.1 Implement DrillDown.renderLevel3(document)
    - Display document excerpt with relevant passages highlighted using distinct background color
    - Show document metadata: filename, ingestion date, extracted entities
    - Render "🌐 Research This Externally" OSINT button pre-populated with full drilldown path context (entity name, lead narrative, evidence thread summary, current document reference)
    - On OSINT click, POST to `/case-files/{id}/osint-research` with research_type "entity" and full context
    - Render "📌 Save to Case" button that saves finding via existing FindingsService (POST /case-files/{id}/findings) with finding_type "investigation_lead", lead narrative as title, evidence thread summary as full_assessment, relevant entity_names
    - Show inline error with retry for Save to Case failures
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 8.1, 8.3_

  - [ ]* 8.2 Write property test for OSINT button placement
    - **Property 11: OSINT button absent at non-source levels** — verify rendered HTML for Level 1 and Level 2 does NOT contain the OSINT research button element
    - **Validates: Requirements 8.2**

- [x] 9. Integration wiring and existing OSINT section coexistence
  - [x] 9.1 Ensure OSINT button coexistence
    - The existing "🌐 EXTERNAL INTELLIGENCE" section OSINT button in the entity drill-down panel must continue to render independently of the 3-level drilldown flow
    - The new Level 3 OSINT button is a separate instance within the drilldown panel only
    - _Requirements: 8.4_

  - [x] 9.2 Add CSS styles for drilldown levels
    - Add slide animation CSS (300ms transition for horizontal slide left/right)
    - Style lead cards with priority color indicators, lead_type badges
    - Style breadcrumb navigation, evidence thread layout, source viewer highlights
    - _Requirements: 7.3, 2.1, 2.2, 1.8_

- [x] 10. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate the 11 correctness properties from the design document
- The backend uses Python (matching existing services), frontend uses JavaScript (matching investigator.html)
- The existing FindingsService and OSINT Research Agent are reused, not reimplemented
