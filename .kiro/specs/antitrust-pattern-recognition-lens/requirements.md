# Requirements Document

## Introduction

The Antitrust Pattern Recognition Lens adds a dedicated typology visualization for the 6 antitrust crime categories (Procurement Collusion, Price Fixing, Criminal Cartel, Monopolization, Market Allocation, Merger Review). Each category expands into 4-6 sub-category cards displaying evidence examples, typology flags, and prosecution statistics. The feature reuses the existing Pattern Recognition Lens card layout (from `typology-lens.js`) and integrates with the antitrust report page at `/antitrust-report.html`.

## Glossary

- **Pattern_Recognition_Lens**: The existing full-screen overlay component rendered by `typology-lens.js` that displays crime typology sub-categories as a 3-column card grid with evidence examples, indicators, and statistics.
- **Typology_Module**: A JavaScript object defining a crime domain's metadata (name, icon, color, subtitle, auto-detect keywords) registered in `TYPOLOGY_MODULES` within `typology-lens.js`.
- **Sub_Category_Card**: A single card within the Pattern Recognition Lens grid representing one sub-pattern of a typology, containing an icon, name, score badge, indicator list, evidence example box, and statistical footnote.
- **Antitrust_Report_Page**: The existing page at `/antitrust-report.html` showing a portfolio of 100 antitrust cases with a pie chart, Pareto chart, and filterable case table.
- **Category_Module_Array**: A JavaScript array of sub-category objects (each with `id`, `icon`, `name`, `color`, `indicators`, `exampleText`, `stat`) that defines the lens content for one antitrust typology.
- **Typology_Modules_File**: The file `src/frontend/typology-modules.js` where all non-default crime typology category arrays are defined.
- **Antitrust_Category**: One of the 6 antitrust crime types: Procurement Collusion, Price Fixing, Criminal Cartel, Monopolization, Market Allocation, or Merger Review.
- **Pattern_Library_Taxonomy**: The 5-level hierarchy (Domain → Typology → Method → Signature → Case) stored in `src/data/pattern-library-taxonomy.json` containing all proven prosecution pattern signatures with DOJ case precedents.
- **Signature**: A detectable evidence pattern at the lowest level of the taxonomy, containing `vector_text` for embedding, `indicators` for detection signals, `severity` classification, and a `precedent_case` reference to the DOJ prosecution that proves the pattern.
- **Matched_Signature**: A Pattern Library Taxonomy signature that achieves a cosine similarity score ≥ 0.60 against case evidence during k-NN scoring in OpenSearch.

## Requirements

### Requirement 1: Antitrust Typology Module Registration

**User Story:** As an investigative analyst, I want the Pattern Recognition Lens to include an antitrust crime typology module, so that I can view antitrust-specific sub-category patterns alongside existing crime typology modules.

#### Acceptance Criteria

1. THE Typology_Modules_File SHALL define 6 Category_Module_Arrays, one for each Antitrust_Category (Procurement Collusion, Price Fixing, Criminal Cartel, Monopolization, Market Allocation, Merger Review), where each Category_Module_Array contains exactly 6 sub-category objects and each sub-category object contains the properties: id, icon, name, color, indicators, exampleText, and stat.
2. WHEN the Pattern_Recognition_Lens renders an antitrust module for a selected Antitrust_Category, THE Pattern_Recognition_Lens SHALL display the 6 sub-category cards from the corresponding Category_Module_Array in a 3-column card grid, matching the layout used by existing typology modules.
3. THE Pattern_Recognition_Lens SHALL register a new Typology_Module entry named "antitrust" in the TYPOLOGY_MODULES object with a subtitle of "ANTITRUST CRIME TYPOLOGY", an icon property containing a single emoji character, a color property containing a hex color value that does not duplicate any color already assigned to the existing 11 modules, a description string, and an autoDetectKeywords array containing at least 3 keywords.
4. WHEN a user selects the antitrust Typology_Module from the module toggle bar, THE Pattern_Recognition_Lens SHALL display a secondary selector containing 6 labeled buttons (one per Antitrust_Category: Procurement Collusion, Price Fixing, Criminal Cartel, Monopolization, Market Allocation, Merger Review), with the first category selected by default.
5. WHEN a user clicks an Antitrust_Category button in the secondary selector, THE Pattern_Recognition_Lens SHALL replace the currently displayed sub-category cards with the cards from the selected Antitrust_Category's Category_Module_Array within 200 milliseconds.
6. THE getModuleCategories function SHALL return the active Antitrust_Category's Category_Module_Array when called with the "antitrust" module identifier.

### Requirement 2: Sub-Category Card Content for Procurement Collusion

**User Story:** As an investigative analyst, I want to see sub-category patterns specific to Procurement Collusion, so that I can recognize bid-rigging, cover bidding, and related procurement fraud indicators in case evidence.

#### Acceptance Criteria

1. THE Procurement_Collusion Category_Module_Array SHALL contain between 4 and 6 Sub_Category_Card definitions.
2. WHEN the Procurement Collusion module is displayed, THE Pattern_Recognition_Lens SHALL show sub-categories covering at minimum: Bid Rotation, Cover Bidding (complementary bidding), Market Allocation by Customer, and Phantom Bidding.
3. THE Pattern_Recognition_Lens SHALL display each Procurement Collusion Sub_Category_Card with an indicators field containing between 3 and 6 detection signal strings, where each string describes an observable procurement anomaly (e.g., bid spread anomalies, subcontracting patterns, shared advisors, statistical clustering).
4. THE Pattern_Recognition_Lens SHALL display each Procurement Collusion Sub_Category_Card with an evidence example containing a scenario that includes at least one named entity, at least one dollar amount with a numeric value, and at least one typology flag annotation formatted in italic emphasis.
5. THE Pattern_Recognition_Lens SHALL display each Procurement Collusion Sub_Category_Card with a statistics footnote citing at least one prosecution or competition enforcement data source (e.g., DOJ Antitrust Division, USSC, OECD Competition reports).
6. IF a Sub_Category_Card's exampleText field contains a typology flag annotation, THEN THE Pattern_Recognition_Lens SHALL render that annotation using italic emphasis markup.

### Requirement 3: Sub-Category Card Content for Price Fixing

**User Story:** As an investigative analyst, I want to see sub-category patterns specific to Price Fixing, so that I can identify horizontal agreements, output restrictions, and information exchange patterns in case evidence.

#### Acceptance Criteria

1. THE Price_Fixing Category_Module_Array SHALL contain between 4 and 6 Sub_Category_Card definitions.
2. WHEN the Price Fixing module is displayed, THE Pattern_Recognition_Lens SHALL show sub-categories covering at minimum: Horizontal Price Agreement, Bid Rigging, Market Division, and Output Restriction.
3. THE Pattern_Recognition_Lens SHALL display each Price Fixing Sub_Category_Card with an indicators field listing between 3 and 8 detection signals specific to the sub-category's price-fixing typology (e.g., parallel pricing movements, identical bid amounts, advance price announcements, competitor communications), with no indicator string exceeding 120 characters.
4. THE Pattern_Recognition_Lens SHALL display each Price Fixing Sub_Category_Card with an evidence example describing a fictional antitrust violation scenario that includes at least 1 dollar amount, at least 2 named entities, and at least 1 typology flag annotation formatted in italic emphasis.
5. THE Pattern_Recognition_Lens SHALL display each Price Fixing Sub_Category_Card with a statistics footnote citing at least 1 prosecution data source from the following: DOJ Antitrust Division, USSC, or OECD Competition reports.

### Requirement 4: Sub-Category Card Content for Criminal Cartel

**User Story:** As an investigative analyst, I want to see sub-category patterns specific to Criminal Cartels, so that I can recognize international conspiracies, obstruction tactics, and recidivist behavior in case evidence.

#### Acceptance Criteria

1. THE Criminal_Cartel Category_Module_Array SHALL contain between 4 and 6 Sub_Category_Card definitions.
2. WHEN the Criminal Cartel module is displayed, THE Pattern_Recognition_Lens SHALL show sub-categories covering at minimum: International Cartel, Domestic Conspiracy, Obstruction and Cover-up, and Recidivism.
3. THE Pattern_Recognition_Lens SHALL display each Criminal Cartel Sub_Category_Card with an indicators field listing between 3 and 6 detection signals per card drawn from cartel-specific behaviors (coded communications, offshore intermediary payments, document destruction, encrypted messaging, foreign meetings, parallel pricing, bid rotation, market allocation).
4. THE Pattern_Recognition_Lens SHALL display each Criminal Cartel Sub_Category_Card with an exampleText field containing a scenario that includes at least one named entity, at least one dollar amount formatted with currency symbol and comma separators (e.g., "$2,400,000"), at least one numeric quantity (participant count, duration, or transaction count), and between 1 and 3 typology flag annotations each formatted in italic emphasis.
5. THE Pattern_Recognition_Lens SHALL display each Criminal Cartel Sub_Category_Card with a stat field containing a footnote that cites at least one prosecution or enforcement data source (DOJ Antitrust Division, FBI, USSC, OECD, or Amnesty Plus data) and includes at least one numeric statistic (percentage, count, or year range).

### Requirement 5: Sub-Category Card Content for Monopolization

**User Story:** As an investigative analyst, I want to see sub-category patterns specific to Monopolization, so that I can identify exclusionary conduct, predatory pricing, and platform self-preferencing in case evidence.

#### Acceptance Criteria

1. THE Monopolization Category_Module_Array SHALL contain between 4 and 6 Sub_Category_Card definitions.
2. WHEN the Monopolization module is displayed, THE Pattern_Recognition_Lens SHALL show sub-categories covering at minimum: Exclusionary Conduct, Predatory Pricing, Acquisitions to Maintain Monopoly, and Platform Self-Preferencing.
3. THE Pattern_Recognition_Lens SHALL display each Monopolization Sub_Category_Card with an indicators field listing between 3 and 8 detection signals drawn from monopolization-specific conduct (such as exclusive dealing, tying arrangements, below-cost pricing, serial acquisitions, algorithmic bias, and refusal to deal).
4. THE Pattern_Recognition_Lens SHALL display each Monopolization Sub_Category_Card with an evidence example that includes at least one numeric market share percentage, at least one entity count, and at least one typology flag annotation where each typology flag annotation is formatted in italic emphasis.
5. THE Pattern_Recognition_Lens SHALL display each Monopolization Sub_Category_Card with a statistics footnote citing at least one prosecution data source from the following set: DOJ Antitrust Division, FTC, USSC, or Sherman Act Section 2 case data.

### Requirement 6: Sub-Category Card Content for Market Allocation

**User Story:** As an investigative analyst, I want to see sub-category patterns specific to Market Allocation, so that I can identify geographic division, customer allocation, no-poach agreements, and wage-fixing in case evidence.

#### Acceptance Criteria

1. THE Market_Allocation Category_Module_Array SHALL contain between 4 and 6 Sub_Category_Card definitions.
2. WHEN the Market Allocation module is displayed, THE Pattern_Recognition_Lens SHALL show sub-categories covering at minimum: Geographic Division, Customer Allocation, No-Poach Agreements, and Wage-Fixing.
3. THE Pattern_Recognition_Lens SHALL display each Market Allocation Sub_Category_Card with an indicators field listing between 3 and 6 detection signals drawn from the following set or directly mappable to the sub-category's pattern: geographic boundaries, customer assignment lists, non-compete clauses, suppressed wage data, territory-swap evidence.
4. THE Pattern_Recognition_Lens SHALL display each Market Allocation Sub_Category_Card with an evidence example containing a scenario that includes at least one named entity, at least one dollar amount, at least one entity count, a geographic or industry context, and at least one typology flag annotation formatted in italic emphasis.
5. THE Pattern_Recognition_Lens SHALL display each Market Allocation Sub_Category_Card with a statistics footnote citing at least 1 named prosecution or research data source from the following: DOJ Antitrust Division, FTC, labor economics research institutions, or USSC.
6. THE Pattern_Recognition_Lens SHALL render each indicator string within a maximum of 120 characters and each evidence example within a maximum of 500 characters.

### Requirement 7: Sub-Category Card Content for Merger Review

**User Story:** As an investigative analyst, I want to see sub-category patterns specific to Merger Review, so that I can identify horizontal concentration, vertical foreclosure, and innovation harm in proposed or completed mergers.

#### Acceptance Criteria

1. THE Merger_Review Category_Module_Array SHALL contain between 4 and 6 Sub_Category_Card definitions.
2. WHEN the Merger Review module is displayed, THE Pattern_Recognition_Lens SHALL show sub-categories covering at minimum: Horizontal Concentration, Vertical Foreclosure, Coordinated Effects, and Innovation Harm.
3. THE Pattern_Recognition_Lens SHALL display each Merger Review Sub_Category_Card with an indicators field listing between 3 and 6 detection signals drawn from merger harm concepts (HHI concentration levels, market share thresholds, input foreclosure risks, overlapping pipelines, reduced future competition).
4. THE Pattern_Recognition_Lens SHALL display each Merger Review Sub_Category_Card with an evidence example containing a scenario that includes at least one market share percentage value, at least one HHI numeric value, at least one entity count, and at least one typology flag annotation formatted in italic emphasis.
5. THE Pattern_Recognition_Lens SHALL display each Merger Review Sub_Category_Card with a statistics footnote citing at least one prosecution data source (DOJ Antitrust Division, FTC, Horizontal Merger Guidelines, or Hart-Scott-Rodino data).

### Requirement 8: Antitrust Report Page Integration

**User Story:** As an investigative analyst, I want to navigate from the antitrust report page directly to the Pattern Recognition Lens for a specific category, so that I can quickly explore typology patterns for cases I am reviewing.

#### Acceptance Criteria

1. WHEN a user clicks a pie chart slice on the Antitrust_Report_Page, THE Antitrust_Report_Page SHALL open the Pattern_Recognition_Lens filtered to the Antitrust_Category represented by that slice.
2. THE Antitrust_Report_Page SHALL display a "View Patterns" button in the header navigation area that, when clicked, opens the Pattern_Recognition_Lens with no category filter applied, showing all 6 antitrust categories.
3. WHEN the Pattern_Recognition_Lens is opened from the Antitrust_Report_Page, THE Pattern_Recognition_Lens SHALL render as a full-screen overlay on top of the report page within 2 seconds of the user action.
4. WHEN a user clicks the Close button in the Pattern_Recognition_Lens overlay, THE Pattern_Recognition_Lens SHALL close and return the user to the Antitrust_Report_Page preserving the page scroll position, any active table filters, and the selected chart state that were in effect before the overlay was opened.
5. IF the Pattern_Recognition_Lens fails to load within 5 seconds of the user action, THEN THE Antitrust_Report_Page SHALL display an error message indicating the lens is unavailable and allow the user to dismiss the message and remain on the report page.

### Requirement 9: Card Layout and Visual Consistency

**User Story:** As a product owner, I want the antitrust Pattern Recognition Lens to visually match the existing sex-trafficking and fraud typology lens layouts, so that the UI feels cohesive across all crime typology modules.

#### Acceptance Criteria

1. THE Pattern_Recognition_Lens SHALL render antitrust Sub_Category_Cards in a 3-column responsive CSS grid with a maximum container width of 1200 pixels, a column gap of 22 pixels, and equal-width columns, matching the grid structure defined in `sex-trafficking-typology.html`.
2. THE Pattern_Recognition_Lens SHALL apply a 3-pixel solid border-top to each Sub_Category_Card using the color value defined in the corresponding Category_Module_Array entry, and a 1-pixel solid border on the remaining sides using the same color at 35% opacity.
3. THE Pattern_Recognition_Lens SHALL display a score badge placeholder (showing the text "—" when no live scoring data is available) in each Sub_Category_Card header, positioned to the right of the card title using flexbox `justify-content: space-between` alignment.
4. THE Pattern_Recognition_Lens SHALL apply consistent dark-theme styling (background color `rgba(26,35,50,0.9)`, text color `#e2e8f0`, secondary text `#a0aec0`) matching the existing Pattern Recognition Lens cards, with card border-radius of 14 pixels and internal padding of 22 pixels.
5. WHEN the viewport width is less than 1100 pixels, THE Pattern_Recognition_Lens SHALL reflow the grid to 2 columns; WHEN the viewport width is less than 700 pixels, THE Pattern_Recognition_Lens SHALL reflow the grid to 1 column.
6. THE Pattern_Recognition_Lens SHALL display a 3-pixel solid left border on each evidence example box using the Sub_Category_Card's assigned color from the Category_Module_Array, with the evidence box background set to `rgba(0,0,0,0.35)` and border-radius of 0 on the left side and 10 pixels on the right side.
7. IF the Category_Module_Array contains zero sub-category entries for the selected antitrust typology, THEN THE Pattern_Recognition_Lens SHALL display a single centered message within the grid container indicating that no pattern categories are available for the selected typology.

### Requirement 10: Module Selector for Antitrust Sub-Domains

**User Story:** As an investigative analyst, I want to switch between the 6 antitrust typology categories within the lens without closing and reopening it, so that I can compare patterns across different antitrust violation types.

#### Acceptance Criteria

1. WHILE the antitrust Typology_Module is active, THE Pattern_Recognition_Lens SHALL display a secondary selector bar below the module toggle showing all 6 Antitrust_Categories as clickable buttons, with the first category (Procurement Collusion) selected by default on initial activation.
2. WHEN a user clicks an Antitrust_Category button in the secondary selector, THE Pattern_Recognition_Lens SHALL re-render the card grid with the sub-categories from the selected Antitrust_Category within 500 milliseconds without a full page reload.
3. THE Pattern_Recognition_Lens SHALL visually highlight the currently active Antitrust_Category button in the secondary selector using the category's assigned color with a solid border and tinted background.
4. THE Pattern_Recognition_Lens SHALL use the category color values consistent with those defined in the Antitrust_Report_Page (Procurement Collusion: red, Price Fixing: orange, Criminal Cartel: purple, Monopolization: blue, Market Allocation: green, Merger Review: pink).
5. IF the selected Antitrust_Category contains no sub-categories or no associated data, THEN THE Pattern_Recognition_Lens SHALL display an empty-state message indicating no patterns are available for that category while keeping the secondary selector bar accessible.

### Requirement 11: Pattern Library Taxonomy Integration

**User Story:** As an investigative analyst reviewing a specific case (e.g., Epstein Truck Fraud), I want the Pattern Recognition Lens to score case evidence against the full Pattern Library Taxonomy signatures, so that I can see which specific proven prosecution patterns match my case evidence with DOJ case precedent references.

#### Acceptance Criteria

1. THE system SHALL maintain a machine-readable Pattern Library Taxonomy at `src/data/pattern-library-taxonomy.json` containing a 5-level hierarchy (Domain → Typology → Method → Signature → Case) with at least 138 antitrust signatures across all 6 Antitrust_Categories.
2. WHEN the typology scoring pipeline runs for a case, THE `score_typology.py` Lambda SHALL query the `typology-patterns` OpenSearch index using k-NN search with embedded case evidence, and THE index SHALL contain vector embeddings for all signatures defined in the Pattern Library Taxonomy.
3. WHEN a signature achieves a cosine similarity score of 0.60 or higher against case evidence, THE system SHALL classify it as a "matched signature" and include it in the precomputed results stored in Aurora.
4. THE Pattern_Recognition_Lens findings drill-down SHALL display matched signatures grouped by Method, showing: the signature description, the severity level (critical/high/moderate), the DOJ precedent case name, and the cosine similarity score.
5. WHEN no case is loaded (reference mode), THE Pattern_Recognition_Lens SHALL display signature counts per method from the Pattern Library Taxonomy as metadata on each Sub_Category_Card (e.g., "5 prosecution signatures indexed").

### Requirement 12: Signature Indexing Pipeline

**User Story:** As a platform administrator, I want an automated pipeline to embed and index all Pattern Library Taxonomy signatures into OpenSearch, so that they are available for k-NN matching during case scoring.

#### Acceptance Criteria

1. THE system SHALL provide a script at `scripts/index_pattern_library.py` that reads all signatures from `src/data/pattern-library-taxonomy.json`, embeds each signature's `vector_text` field using Amazon Titan Embed Text v2, and indexes the resulting vectors into the `typology-patterns` OpenSearch Serverless index.
2. EACH indexed document in OpenSearch SHALL contain the fields: `pattern_id` (matching `signature_id`), `description`, `severity`, `typology` (matching `typology_id`), `method` (matching `method_id`), `domain` (matching `domain_id`), `precedent_case`, `indicators` (array), and `embedding` (1024-dimension vector).
3. THE indexing script SHALL be idempotent — re-running it SHALL update existing documents by `pattern_id` rather than creating duplicates.
4. THE indexing script SHALL log the count of signatures indexed per domain and typology, and SHALL report any embedding failures without aborting the entire batch.
5. WHEN new signatures are added to the taxonomy JSON, THE indexing script SHALL detect and index only new or modified entries (based on hash comparison of `vector_text` field) to minimize Bedrock embedding API calls.

### Requirement 13: Case-to-Signature Match Display in Findings

**User Story:** As an investigative analyst drilling into a specific typology category's findings for a case, I want to see which Pattern Library signatures matched, so that I can reference the exact DOJ prosecution precedent and understand what evidence triggered the match.

#### Acceptance Criteria

1. WHEN a user clicks into a category's findings from the Pattern_Recognition_Lens, THE findings drill-down view SHALL include a "Pattern Library Matches" section below the existing situation cards.
2. THE "Pattern Library Matches" section SHALL display each matched signature as a compact card showing: the method name (as header), signature description, severity badge (color-coded: critical=red, high=orange, moderate=yellow), cosine similarity percentage, and the DOJ precedent case name as a citation.
3. THE matched signatures SHALL be sorted by cosine similarity score descending, with the strongest matches shown first.
4. IF zero signatures match above the 0.60 threshold for a category, THE "Pattern Library Matches" section SHALL display a message: "No prosecution pattern signatures matched above threshold for this category."
5. WHEN a matched signature's indicators overlap with entities detected in the case evidence, THE signature card SHALL highlight the overlapping indicators in a distinct color to show which specific flags triggered the match.
