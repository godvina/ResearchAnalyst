# Requirements Document

## Introduction

The Conspiracy Theory Taxonomy feature builds a universal 5-level classification system (Domain → Typology → Method → Signature → Precedent Case) that identifies cross-cutting investigative patterns appearing across all conspiracy theories. Unlike the existing Ancient Mysteries taxonomy (which classifies geographic/archaeological patterns), this taxonomy classifies behavioral and informational patterns — evidence suppression, institutional behavior, witness reliability, timeline anomalies, geographic clustering, information asymmetry, and counter-narrative emergence. The taxonomy is seeded from 10 diverse conspiracy theories simultaneously, then validated by fully processing Bermuda Triangle data first (small, diverse, solved), followed by Princess Diana (single dense document), Flat Earth (massive scale), and finally UFO/JFK (with a proven taxonomy). The same agent chain architecture (Broad Scanner → Taxonomy Scanner → Cross-Pattern Agent) and infrastructure (Neptune, OpenSearch, Aurora, S3, Bedrock) are reused with new domain content.

## Glossary

- **Taxonomy_Engine**: The reusable 5-level classification system (Domain → Typology → Method → Signature → Precedent Case) that organizes investigative patterns hierarchically
- **Domain**: Level 1 of the taxonomy — a broad category of cross-cutting pattern (e.g., "Evidence Suppression", "Institutional Behavior", "Witness Reliability")
- **Typology**: Level 2 — a specific pattern type within a domain (e.g., under Evidence Suppression: "Document Classification", "FOIA Denial", "Witness Silencing")
- **Method**: Level 3 — a concrete technique or mechanism used to enact the typology (e.g., under Document Classification: "Retroactive Reclassification", "Over-Classification")
- **Signature**: Level 4 — a measurable, detectable indicator that a method is present in source material (e.g., "Redaction density exceeds 40% of page area", "Classification stamp applied post-publication")
- **Precedent_Case**: Level 5 — a documented historical instance where the signature was confirmed (e.g., "CIA MKUltra document release, 1977")
- **Cross_Pattern_Agent**: The AI agent that identifies when the same signature appears across multiple conspiracy theory datasets, establishing cross-theory connections
- **Taxonomy_Scanner**: The AI agent that scores incoming documents against defined signatures and assigns taxonomy classifications
- **Broad_Scanner**: The AI agent that performs initial document intake, extracting entities, dates, claims, and potential pattern indicators
- **Theory_Dataset**: A collection of source materials (PDFs, images, CSVs, XML, JSON, video metadata) associated with one of the 10 conspiracy theories
- **Pattern_Library**: The OpenSearch index (`typology-patterns`) storing all taxonomy signatures with vector embeddings for k-NN similarity search
- **Seed_Corpus**: The combined representative sample extracted from all 10 conspiracy theory datasets used to derive the initial universal taxonomy
- **Validation_Pipeline**: The end-to-end processing of a complete Theory_Dataset through all three agents to verify taxonomy coverage and scoring accuracy
- **Cross_Theory_Connection**: A relationship stored in Neptune when the same signature is detected in documents from two or more different Theory_Datasets
- **Universal_Pattern**: A behavioral or informational pattern that appears in three or more unrelated conspiracy theories, confirming it is domain-agnostic

## Requirements

### Requirement 1: Universal Taxonomy Structure Definition

**User Story:** As a research analyst, I want a universal taxonomy that captures cross-cutting investigative patterns independent of any specific conspiracy theory, so that I can identify common structural behaviors across unrelated cases.

#### Acceptance Criteria

1. THE Taxonomy_Engine SHALL define a minimum of 7 top-level Domains covering: evidence suppression, institutional behavior, witness reliability, timeline anomalies, geographic clustering, information asymmetry, and counter-narrative emergence
2. THE Taxonomy_Engine SHALL define a minimum of 3 Typologies per Domain, each representing a distinct sub-pattern within that domain
3. THE Taxonomy_Engine SHALL define a minimum of 2 Methods per Typology, each describing a concrete mechanism by which the typology manifests in source material
4. THE Taxonomy_Engine SHALL define a minimum of 2 Signatures per Method, each containing a measurable detection criterion expressible as a vector-embeddable text description of no more than 512 characters
5. THE Taxonomy_Engine SHALL store all taxonomy levels in the same Aurora PostgreSQL schema structure used by the existing Ancient Mysteries taxonomy
6. THE Taxonomy_Engine SHALL store all Signature vector embeddings in the `typology-patterns` OpenSearch index using the `amazon.titan-embed-text-v2:0` embedding model
7. WHEN a new Domain, Typology, Method, or Signature is added, THE Taxonomy_Engine SHALL validate that it is not specific to a single conspiracy theory by requiring that the definition text contains no proper nouns referring to a specific theory (e.g., "JFK", "Roswell", "COVID")
8. THE Taxonomy_Engine SHALL assign a unique hierarchical context_key to each node following the format `conspiracy/{domain}/{typology}/{method}/{signature}` with a maximum length of 512 characters

### Requirement 2: Multi-Theory Seeding Pipeline

**User Story:** As a research analyst, I want the taxonomy seeded from all 10 conspiracy theories simultaneously, so that the resulting structure captures genuinely universal patterns rather than patterns specific to one theory.

#### Acceptance Criteria

1. WHEN the seeding pipeline is initiated, THE Broad_Scanner SHALL process a representative sample of at least 50 documents or data records from each of the 10 Theory_Datasets, extracting entities, claims, dates, and behavioral indicators
2. WHEN the Broad_Scanner completes extraction across all 10 Theory_Datasets, THE Taxonomy_Scanner SHALL identify recurring patterns that appear in at least 3 of the 10 Theory_Datasets and propose them as candidate Universal_Patterns
3. WHEN candidate Universal_Patterns are identified, THE Taxonomy_Engine SHALL classify each into the appropriate Domain and Typology, creating new Methods and Signatures as needed
4. THE Taxonomy_Engine SHALL process the following Theory_Datasets with their respective primary file formats: JFK Assassination (PDF), UFOs/UAPs (PDF and CSV), 9/11 Cover-Up (PDF and photos), COVID-19 Lab Leak (PDF and FASTA), Moon Landing Hoax (TIFF/JPEG), Vaccine Conspiracies (CSV/JSON), Princess Diana (PDF), New World Order (PDF and HTML), Bermuda Triangle (XML and HTML tables), and Flat Earth/Reptilian Elite (JSON)
5. THE Taxonomy_Engine SHALL generate all taxonomy content using Amazon Bedrock Claude Sonnet via prompt engineering without any model fine-tuning or training
6. IF a candidate pattern appears in fewer than 3 Theory_Datasets, THEN THE Taxonomy_Engine SHALL classify it as a theory-specific pattern and store it in a separate `theory_specific_patterns` table rather than the universal taxonomy
7. WHEN seeding is complete, THE Taxonomy_Engine SHALL produce a coverage report showing how many Signatures were derived from each Theory_Dataset and which Domains have fewer than 3 Typologies

### Requirement 3: Bermuda Triangle Validation Pipeline

**User Story:** As a research analyst, I want to validate the universal taxonomy by fully processing the Bermuda Triangle dataset first, so that I can confirm the taxonomy works end-to-end with a small, diverse, solved dataset before processing larger corpora.

#### Acceptance Criteria

1. WHEN the Bermuda Triangle Validation_Pipeline is initiated, THE Broad_Scanner SHALL ingest all available Bermuda Triangle data sources: NTSB accident reports (XML format), Wikipedia tables (HTML), and NOAA oceanographic/meteorological data
2. WHEN the Broad_Scanner completes Bermuda Triangle ingestion, THE Taxonomy_Scanner SHALL score each extracted finding against all Signatures in the Pattern_Library and assign taxonomy classifications with confidence scores between 0.0 and 1.0
3. WHEN the Taxonomy_Scanner completes scoring, THE Cross_Pattern_Agent SHALL identify connections between Bermuda Triangle findings and any existing patterns from the seeding phase, storing each Cross_Theory_Connection in Neptune with source theory, target theory, shared signature, and confidence score
4. THE Validation_Pipeline SHALL complete processing of the entire Bermuda Triangle dataset within 30 minutes of initiation
5. WHEN validation processing is complete, THE Validation_Pipeline SHALL produce a validation report containing: total documents processed, signatures matched, signatures with zero matches, cross-theory connections found, and average confidence score
6. IF fewer than 50% of defined Signatures receive at least one match from the Bermuda Triangle dataset, THEN THE Validation_Pipeline SHALL flag the taxonomy as potentially over-fitted to other theories and recommend expansion of Bermuda Triangle-relevant signatures
7. WHEN Bermuda Triangle validation passes (50% or greater signature match rate), THE Validation_Pipeline SHALL mark the taxonomy as validated and ready for the next theory in the processing order (Princess Diana)

### Requirement 4: Cross-Theory Pattern Detection

**User Story:** As a research analyst, I want the system to automatically detect when the same behavioral pattern appears across multiple conspiracy theories, so that I can identify structural similarities regardless of subject matter.

#### Acceptance Criteria

1. WHEN the Taxonomy_Scanner assigns a Signature match to a document from any Theory_Dataset, THE Cross_Pattern_Agent SHALL query the Pattern_Library via OpenSearch k-NN search (cosine similarity, k=10) to find documents from other Theory_Datasets that matched the same or semantically similar Signatures (similarity threshold of 0.85 or higher)
2. WHEN a cross-theory match is found, THE Cross_Pattern_Agent SHALL create a Cross_Theory_Connection edge in Neptune containing: source_theory, source_document_id, target_theory, target_document_id, shared_signature_id, similarity_score, and detected_at timestamp
3. WHEN a Cross_Theory_Connection is created, THE Cross_Pattern_Agent SHALL verify that the connection represents a genuine behavioral parallel (not merely shared vocabulary) by generating a one-sentence justification via Bedrock explaining the structural similarity
4. THE Cross_Pattern_Agent SHALL detect connections between conspiracy theory patterns and existing Ancient Mysteries patterns when the same geographic coordinates (within 50km radius) or the same signature text embeddings (similarity 0.85 or higher) are shared
5. WHEN the Cross_Pattern_Agent completes a processing batch, THE Cross_Pattern_Agent SHALL produce a cross-theory connection summary listing the top 10 most-connected Signatures (by number of distinct Theory_Datasets matched) and the top 10 strongest inter-theory connections (by similarity score)
6. IF a Signature matches documents in 5 or more distinct Theory_Datasets, THEN THE Cross_Pattern_Agent SHALL promote that Signature to "Universal Confirmed" status in the Pattern_Library

### Requirement 5: Theory-Specific Data Ingestion Adapters

**User Story:** As a system operator, I want data ingestion to handle the diverse file formats across all 10 conspiracy theory datasets, so that the pipeline processes each theory's source material without manual format conversion.

#### Acceptance Criteria

1. THE Broad_Scanner SHALL parse PDF documents by extracting text content, embedded images (as metadata references), and structural elements (headings, tables, footnotes) for the JFK, UFOs, 9/11, COVID-19, Princess Diana, and New World Order Theory_Datasets
2. THE Broad_Scanner SHALL parse XML documents by extracting all element content, attribute values, and nested structures for the Bermuda Triangle NTSB accident reports
3. THE Broad_Scanner SHALL parse CSV and JSON files by extracting column headers as field names and row data as individual records for the UFOs (80K sighting records), Vaccine Conspiracies, and Flat Earth Theory_Datasets
4. THE Broad_Scanner SHALL parse HTML tables by extracting table headers and cell values into structured records for the Bermuda Triangle Wikipedia tables and New World Order HTML data
5. THE Broad_Scanner SHALL extract EXIF metadata (date, location, camera model) from TIFF and JPEG image files for the Moon Landing Hoax Theory_Dataset without performing image content analysis
6. THE Broad_Scanner SHALL parse FASTA genomic sequence files by extracting sequence headers (organism, accession, description) as metadata records for the COVID-19 Lab Leak Theory_Dataset without analyzing sequence content
7. WHEN a file format is not recognized by any configured adapter, THE Broad_Scanner SHALL log the file path and format to a `skipped_files` table in Aurora and continue processing remaining files without interruption
8. THE Broad_Scanner SHALL store all extracted content in S3 under the path `data-lake/conspiracy-theories/{theory_name}/{source_type}/{filename}.json` as normalized JSON regardless of the original file format

### Requirement 6: Taxonomy Scoring and Classification

**User Story:** As a research analyst, I want every ingested document automatically scored against the universal taxonomy, so that I can browse findings by pattern type rather than by source theory.

#### Acceptance Criteria

1. WHEN the Broad_Scanner produces an extracted document record, THE Taxonomy_Scanner SHALL generate a vector embedding of the document's content using `amazon.titan-embed-text-v2:0` and store it in OpenSearch with metadata fields: theory_name, source_file, document_id, and ingestion_timestamp
2. WHEN a document embedding is stored, THE Taxonomy_Scanner SHALL execute a k-NN query against all Signature embeddings in the `typology-patterns` index (k=5, cosine similarity) and assign the document to all Signatures with similarity score of 0.80 or higher
3. WHEN the Taxonomy_Scanner assigns a document to a Signature, THE Taxonomy_Scanner SHALL store the assignment in Aurora with fields: document_id, signature_id, similarity_score, theory_name, assigned_at timestamp, and the matched text excerpt (maximum 1000 characters)
4. THE Taxonomy_Scanner SHALL be scorable by the existing agent chain without modifications to the agent orchestrator's trigger-based execution model
5. IF a document matches no Signatures at the 0.80 threshold, THEN THE Taxonomy_Scanner SHALL log the document as "unclassified" with its highest similarity score and nearest Signature for later review
6. WHEN an analyst queries the Pattern_Library by Signature, THE Pattern_Library SHALL return all matched documents across all Theory_Datasets sorted by similarity score descending, enabling cross-theory browsing

### Requirement 7: Sequential Theory Processing Order

**User Story:** As a research analyst, I want theories processed in a deliberate order (Bermuda Triangle → Princess Diana → Flat Earth → UFO → JFK), so that the taxonomy is validated incrementally from smallest/simplest to largest/most complex datasets.

#### Acceptance Criteria

1. WHEN the Validation_Pipeline for Bermuda Triangle completes with a passing result, THE Taxonomy_Engine SHALL enable processing of the Princess Diana Theory_Dataset (832 pages, single PDF)
2. WHEN the Validation_Pipeline for Princess Diana completes with a passing result, THE Taxonomy_Engine SHALL enable processing of the Flat Earth/Reptilian Elite Theory_Dataset (88M token JSON corpus, 500M+ Reddit comments)
3. WHEN the Validation_Pipeline for Flat Earth completes with a passing result, THE Taxonomy_Engine SHALL enable processing of the UFOs/UAPs Theory_Dataset (15+ GB, PDF/CSV/video metadata)
4. WHEN the Validation_Pipeline for UFOs/UAPs completes with a passing result, THE Taxonomy_Engine SHALL enable processing of the JFK Assassination Theory_Dataset (6M+ pages, PDF-dominant)
5. IF a Validation_Pipeline for any theory fails (below 50% signature match rate), THEN THE Taxonomy_Engine SHALL halt the processing sequence, produce a gap analysis identifying which Domains lack coverage for that theory, and require manual review before continuing
6. WHEN each theory completes validation, THE Taxonomy_Engine SHALL update a processing_status table in Aurora recording: theory_name, status (pending/processing/validated/failed), documents_processed, signatures_matched, cross_connections_found, started_at, and completed_at
7. THE Taxonomy_Engine SHALL support processing the remaining 4 theories (9/11, COVID-19, Moon Landing, Vaccine Conspiracies, New World Order) in any order after the first 5 are validated, without requiring a fixed sequence

### Requirement 8: Neptune Graph Integration for Cross-Theory Relationships

**User Story:** As a research analyst, I want cross-theory relationships stored in Neptune so that I can visualize and traverse connections between theories using the same graph infrastructure used for Ancient Mysteries.

#### Acceptance Criteria

1. THE Taxonomy_Engine SHALL create Neptune vertex labels for: `Theory`, `Document`, `Domain`, `Typology`, `Method`, `Signature`, and `PrecedentCase`
2. THE Taxonomy_Engine SHALL create Neptune edge labels for: `belongs_to` (Document→Theory), `matches` (Document→Signature), `contains` (Domain→Typology→Method→Signature→PrecedentCase hierarchy), and `cross_connects` (Document→Document via shared Signature)
3. WHEN a Cross_Theory_Connection is established, THE Taxonomy_Engine SHALL create a `cross_connects` edge in Neptune with properties: shared_signature_id, similarity_score, justification_text, and detected_at
4. WHEN an analyst queries Neptune for a specific Theory vertex, THE Taxonomy_Engine SHALL return all connected theories (via cross_connects edges traversing through shared Documents and Signatures) within 5 seconds
5. THE Taxonomy_Engine SHALL support traversal queries of the form "find all theories connected to Theory X through Signature Y" returning the path with intermediate Document vertices
6. WHEN the existing Ancient Mysteries taxonomy data in Neptune shares a geographic coordinate (within 50km) with a conspiracy theory Document's extracted location, THE Taxonomy_Engine SHALL create a `geo_correlates` edge between the two vertices with properties: distance_km, ancient_mystery_node_id, and conspiracy_document_id

### Requirement 9: Taxonomy Coverage and Quality Monitoring

**User Story:** As a system operator, I want visibility into taxonomy coverage and quality metrics, so that I can identify gaps and ensure the taxonomy remains balanced across all domains.

#### Acceptance Criteria

1. THE Taxonomy_Engine SHALL expose a GET endpoint at `/taxonomy/conspiracy/coverage` that returns: total domains, total typologies, total methods, total signatures, total precedent cases, and per-domain counts of each subordinate level
2. WHEN the coverage endpoint is queried, THE Taxonomy_Engine SHALL include a balance_score (0.0 to 1.0) calculated as the ratio of the smallest domain's signature count to the largest domain's signature count, where 1.0 indicates perfect balance
3. THE Taxonomy_Engine SHALL expose a GET endpoint at `/taxonomy/conspiracy/cross-theory-report` that returns: total cross-theory connections, connections per theory pair, most-connected signatures, and theories with zero cross-connections
4. IF any Domain has fewer than 5 total Signatures after seeding is complete, THEN THE Taxonomy_Engine SHALL flag that Domain as "under-specified" in the coverage report
5. WHEN a new Theory_Dataset completes validation, THE Taxonomy_Engine SHALL update the coverage report within 60 seconds to reflect new signatures and connections added during that validation run
6. THE Taxonomy_Engine SHALL log all taxonomy modifications (additions, removals, reclassifications) to an audit table in Aurora with fields: action, level, context_key, old_value, new_value, reason, and modified_at timestamp

