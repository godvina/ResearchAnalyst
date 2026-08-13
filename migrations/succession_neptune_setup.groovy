// =============================================================================
// Executive Succession Planning — Neptune Graph Schema
// Target cluster: neptunedbcluster-qoxzlhiau0ao
//
// This is a REFERENCE DOCUMENT — Neptune is schemaless, so this defines
// conventions for node labels, properties, and edge types used by the
// succession planning module.
//
// Node ID Convention: succession:{tenant_id}:{type}:{uuid}
// All nodes include: tenant_id, domain='succession', created_at, source_provenance
//
// Domain isolation: Intelligence Research uses raw UUIDs with case_file_id.
// Succession uses the "succession:" prefix to prevent ID collisions.
// =============================================================================


// =============================================================================
// NODE TYPES
// =============================================================================

// --- Executive (Person being evaluated) ---
// Label: Executive
// ID:    succession:{tenant_id}:person:{uuid}
// Properties:
//   name                 String    (full name)
//   current_title        String    (current job title)
//   current_organization String    (current employer)
//   sector               String    (private | government | military | sovereign_wealth)
//   country              String    (ISO 3166-1 alpha-2, e.g. 'US', 'AE', 'SG')
//   clearance_level      String    (none | confidential | secret | top_secret)
//   seniority_level      String    (director | vp | svp | c_suite | board)
//   years_experience     Integer   (total years in senior roles)
//   consent_recorded     Boolean   (GDPR/PDPL consent flag)
//   consent_timestamp    String    (ISO 8601 datetime)
//   source_provenance    String    (JSON — origin of this record)
//   tenant_id            String    (multi-tenant isolation key)
//   domain               String    (always 'succession')
//   created_at           String    (ISO 8601 datetime)

// --- Organization ---
// Label: Organization
// ID:    succession:{tenant_id}:org:{uuid}
// Properties:
//   name                 String
//   sector               String
//   country              String    (ISO 3166-1 alpha-2)
//   industry             String
//   employee_count       Integer
//   is_competitor        Boolean
//   tenant_id            String
//   domain               String    (always 'succession')
//   created_at           String

// --- Role (Target succession role) ---
// Label: Role
// ID:    succession:{tenant_id}:role:{uuid}
// Properties:
//   title                String    (e.g. "Chief Executive Officer")
//   role_type            String    (CEO | CFO | CIO | CTO | COO | CRO | CAIO)
//   sector               String
//   country              String    (ISO 3166-1 alpha-2)
//   is_critical          Boolean   (critical role = succession required)
//   config_id            String    (FK → Aurora succession.role_configurations.id)
//   tenant_id            String
//   domain               String    (always 'succession')
//   created_at           String

// --- Competency (Skill/attribute being assessed) ---
// Label: Competency
// ID:    succession:{tenant_id}:competency:{snake_case_name}
// Properties:
//   name                 String    (display name, e.g. "Strategic Vision")
//   category             String    (personal_attribute | professional_attribute | master_variable)
//   criterion_index      Integer   (1-25 for criteria, 1-15 for master variables)
//   tenant_id            String
//   domain               String    (always 'succession')
//   created_at           String

// --- Assessment (A specific evaluation event) ---
// Label: Assessment
// ID:    succession:{tenant_id}:assessment:{uuid}
// Properties:
//   platform             String    (SHL | Hogan | DDI | Korn_Ferry | custom)
//   assessment_date      String    (ISO 8601 date)
//   modality             String    (cognitive | personality | peer | 360 | interview | simulation)
//   is_stale             Boolean   (true if older than staleness threshold)
//   tenant_id            String
//   domain               String    (always 'succession')
//   created_at           String

// --- CulturalContext (GLOBE cluster + Hofstede dimensions for a country) ---
// Label: CulturalContext
// ID:    succession:{tenant_id}:culture:{country_code}
// Properties:
//   country              String    (ISO 3166-1 alpha-2)
//   globe_cluster        String    (Anglo | Germanic | Nordic | Latin_Europe | Eastern_Europe |
//                                   Latin_America | Sub_Saharan_Africa | Middle_East |
//                                   Southern_Asia | Confucian_Asia | Southeast_Asia)
//   power_distance       Float     (Hofstede 0-100)
//   individualism        Float     (Hofstede 0-100)
//   uncertainty_avoidance Float    (Hofstede 0-100)
//   masculinity          Float     (Hofstede 0-100)
//   long_term_orientation Float    (Hofstede 0-100)
//   indulgence           Float     (Hofstede 0-100)
//   tenant_id            String
//   domain               String    (always 'succession')
//   created_at           String

// --- DevelopmentPlan (Linked to candidate + target role) ---
// Label: DevelopmentPlan
// ID:    succession:{tenant_id}:devplan:{uuid}
// Properties:
//   status               String    (active | completed | archived)
//   milestones_total     Integer
//   milestones_completed Integer
//   time_to_readiness_months Integer
//   tenant_id            String
//   domain               String    (always 'succession')
//   created_at           String


// =============================================================================
// EDGE TYPES
// =============================================================================

// --- HELD_ROLE: Executive → Role ---
// Direction: Executive --HELD_ROLE--> Role
// Properties:
//   start_date           String    (ISO 8601 date)
//   end_date             String    (ISO 8601 date, null if current)
//   tenure_months        Integer
//   performance_rating   Integer   (1-10 scale)
//   is_rotational        Boolean   (rotational assignment)
//   is_pnl_responsibility Boolean  (P&L oversight)
//   is_cross_functional  Boolean   (cross-functional scope)

// --- DEMONSTRATES: Executive → Competency ---
// Direction: Executive --DEMONSTRATES--> Competency
// Properties:
//   score                Integer   (1-10 scale)
//   assessment_source    String    (which assessment produced this score)
//   assessed_at          String    (ISO 8601 datetime)
//   confidence           Float     (0.0-1.0, reliability of the score)

// --- CONNECTED_TO: Executive → Executive ---
// Direction: Executive --CONNECTED_TO--> Executive (bidirectional semantics)
// Properties:
//   relationship_type    String    (board_coservice | alumni | former_colleagues |
//                                   mentor_mentee | tribal_family | military_unit | wasta)
//   strength             Float     (0.0-1.0, relationship strength)
//   recency_years        Float     (years since last active contact)
//   decayed_weight       Float     (computed: strength * 0.5^(recency_years/3))
//                                   Half-life of 3 years for relationship decay

// --- ASSESSED_BY: Executive → Assessment ---
// Direction: Executive --ASSESSED_BY--> Assessment
// Properties:
//   scores               String    (JSON — raw scores from assessment)
//   mapped_criteria      String    (JSON — how raw scores map to 25 criteria)
//   assessment_date      String    (ISO 8601 date)

// --- OPERATES_IN: Organization → CulturalContext ---
// Direction: Organization --OPERATES_IN--> CulturalContext
// Properties:
//   primary              Boolean   (true if HQ location)

// --- SUCCEEDS: Executive → Role ---
// Direction: Executive --SUCCEEDS--> Role (candidate is on succession pipeline)
// Properties:
//   readiness_level      String    (emergency | accelerated | planned)
//   readiness_score      Float     (0-100 composite)
//   assigned_at          String    (ISO 8601 datetime)
//   last_evaluated       String    (ISO 8601 datetime)

// --- SCORED_FOR: Executive → Role ---
// Direction: Executive --SCORED_FOR--> Role (scoring engine output)
// Properties:
//   role_config_id       String    (FK → Aurora succession.role_configurations.id)
//   composite_score      Float     (0-100)
//   scoring_decision_id  String    (FK → Aurora succession.scoring_decisions.id)
//   scored_at            String    (ISO 8601 datetime)

// --- WORKS_AT: Executive → Organization ---
// Direction: Executive --WORKS_AT--> Organization
// Properties:
//   start_date           String    (ISO 8601 date)
//   end_date             String    (ISO 8601 date, null if current)
//   is_current           Boolean
//   title                String    (title at this org)

// --- DEVELOPS_FOR: DevelopmentPlan → Role ---
// Direction: DevelopmentPlan --DEVELOPS_FOR--> Role
// Properties:
//   target_readiness     String    (emergency | accelerated | planned)

// --- ASSIGNED_TO: DevelopmentPlan → Executive ---
// Direction: DevelopmentPlan --ASSIGNED_TO--> Executive
// Properties:
//   assigned_at          String    (ISO 8601 datetime)


// =============================================================================
// REUSABLE GREMLIN QUERY TEMPLATES
// =============================================================================

// --- Get all competency scores for a candidate ---
// Used by: Scoring Engine (retrieve DEMONSTRATES edges for composite calculation)
g.V('succession:{tenant_id}:person:{exec_id}')
  .outE('DEMONSTRATES')
  .project('competency', 'score', 'source', 'assessed_at', 'confidence')
    .by(inV().values('name'))
    .by(values('score'))
    .by(values('assessment_source'))
    .by(values('assessed_at'))
    .by(values('confidence'))

// --- Get career trajectory for trajectory prediction ---
// Used by: Scoring Engine (career path analysis), CAPER Module
g.V('succession:{tenant_id}:person:{exec_id}')
  .outE('HELD_ROLE')
  .order().by('start_date', Order.asc)
  .project('role', 'org', 'start_date', 'end_date', 'tenure_months', 'performance_rating', 'is_rotational', 'is_pnl')
    .by(inV().values('title'))
    .by(inV().out('WORKS_AT').values('name').fold())
    .by(values('start_date'))
    .by(coalesce(values('end_date'), constant('current')))
    .by(values('tenure_months'))
    .by(coalesce(values('performance_rating'), constant(0)))
    .by(coalesce(values('is_rotational'), constant(false)))
    .by(coalesce(values('is_pnl_responsibility'), constant(false)))

// --- 3-degree relationship network traversal ---
// Used by: Network Centrality Analysis, Shared Connections
// Performance target: < 2s for 1M nodes with decayed_weight filter
g.V('succession:{tenant_id}:person:{exec_id}')
  .repeat(
    bothE('CONNECTED_TO')
      .has('decayed_weight', P.gte(0.1))
      .otherV()
      .simplePath()
  )
  .times(3)
  .path()
  .by(valueMap('name', 'current_title'))
  .by(valueMap('relationship_type', 'strength', 'decayed_weight'))

// --- Shared connections between candidate and target org leadership ---
// Used by: Network Analysis Module
g.V('succession:{tenant_id}:person:{exec_id}')
  .out('CONNECTED_TO')
  .where(out('WORKS_AT').hasId('succession:{tenant_id}:org:{target_org_id}'))
  .project('name', 'title', 'relationship_type')
    .by(values('name'))
    .by(values('current_title'))
    .by(inE('CONNECTED_TO')
        .where(outV().hasId('succession:{tenant_id}:person:{exec_id}'))
        .values('relationship_type'))

// --- Degree centrality for a candidate ---
// Used by: Network Centrality Score (combined_centrality input to scoring)
g.V('succession:{tenant_id}:person:{exec_id}')
  .bothE('CONNECTED_TO').count()

// --- Total Executive nodes for tenant (denominator for centrality) ---
g.V().has('tenant_id', '{tenant_id}')
  .has('domain', 'succession')
  .hasLabel('Executive')
  .count()

// --- Succession pipeline for a role (heat map strength) ---
// Used by: Dashboard heat map, Scenario Planning
g.V('succession:{tenant_id}:role:{role_id}')
  .inE('SUCCEEDS')
  .project('candidate_id', 'candidate_name', 'readiness_level', 'readiness_score', 'last_evaluated')
    .by(outV().id())
    .by(outV().values('name'))
    .by(values('readiness_level'))
    .by(values('readiness_score'))
    .by(values('last_evaluated'))

// --- Upsert Executive node (fold/coalesce pattern) ---
g.V('succession:{tenant_id}:person:{uuid}')
  .fold()
  .coalesce(
    unfold(),
    addV('Executive').property(T.id, 'succession:{tenant_id}:person:{uuid}')
  )
  .property('tenant_id', '{tenant_id}')
  .property('domain', 'succession')
  .property('name', '{name}')
  .property('current_title', '{title}')
  // ... additional properties

// --- Upsert edge (CONNECTED_TO with decay computation) ---
g.V('succession:{tenant_id}:person:{exec_a}').as('a')
  .V('succession:{tenant_id}:person:{exec_b}').as('b')
  .coalesce(
    select('a').outE('CONNECTED_TO').where(inV().as('b')),
    select('a').addE('CONNECTED_TO').to(select('b'))
  )
  .property('relationship_type', '{type}')
  .property('strength', {strength})
  .property('recency_years', {recency})
  .property('decayed_weight', {strength} * Math.pow(0.5, {recency} / 3.0))
