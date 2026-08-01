# Spec: Typology Sub-Category Evidence Drill-Down

## Overview

When an analyst sees a scored sub-category (e.g., "financial_control" under "sex_trafficking" at 0.74), they need to drill into the actual evidence — the specific entities, money flows, and connections that produced that score. This scoped view queries Neptune for just the relevant slice (50-500 entities) rather than the full 248K graph.

## User Flow

1. User is on Crime Typology page → sees 11 typologies with scores
2. Expands a typology (e.g., sex_trafficking) → sees 6 sub-categories scored
3. Clicks "Investigate" on a sub-category (e.g., financial_control)
4. Gets a focused evidence view:
   - Entity list (people, orgs, accounts involved)
   - Relationship graph (who connects to whom)
   - Money flow diagram (if financial sub-category)
   - Geo map (only entities with location data)
   - Key evidence summary

## API Endpoint

```
GET /case-files/{id}/typology/{module_id}/{sub_category_id}/evidence-graph
```

### Response

```json
{
  "case_id": "uuid",
  "typology_module_id": "sex_trafficking",
  "sub_category_id": "financial_control",
  "score": 0.746,
  "match_strength": "moderate",
  "entities": [
    {
      "id": "neptune-vertex-id",
      "name": "Shell Corp LLC",
      "type": "financial_institution",
      "properties": { "location": "Miami, FL", "lat": 25.76, "lon": -80.19 }
    }
  ],
  "relationships": [
    {
      "source": "entity-id-1",
      "target": "entity-id-2", 
      "type": "wire_transfer",
      "properties": { "amount": "$45,000", "date": "2019-03-15" }
    }
  ],
  "money_flows": [
    {
      "from_entity": "Entity A",
      "to_entity": "Entity B",
      "via": ["Shell Corp LLC"],
      "total_amount": "$2.3M",
      "transaction_count": 14
    }
  ],
  "geo_entities": [
    { "name": "Shell Corp LLC", "lat": 25.76, "lon": -80.19, "type": "financial_institution" }
  ],
  "summary": "AI-generated 2-sentence summary of what this evidence shows"
}
```

## Backend Implementation

### File: `src/lambdas/api/typology_evidence_graph.py`

```python
def handler(event, context):
    case_id = event["pathParameters"]["id"]
    module_id = event["pathParameters"]["module_id"]     # e.g. "sex_trafficking"
    sub_category_id = event["pathParameters"]["sub_id"]  # e.g. "financial_control"
    
    # 1. Get entity types for this sub-category from typology_query_definitions
    entity_types = get_sub_category_entity_types(module_id, sub_category_id)
    # e.g. ["financial_institution", "shell_company", "wire_transfer", "bank_account"]
    
    # 2. Get key_entities from Aurora (already stored by pipeline)
    key_entity_names = get_key_entities_from_aurora(case_id, module_id, sub_category_id)
    
    # 3. Query Neptune — SCOPED to just these entity types + key entities
    # This is fast because we're querying ~50-500 entities, not 248K
    gremlin_query = build_scoped_query(case_id, entity_types, key_entity_names, limit=500)
    entities, edges = execute_neptune_query(gremlin_query)
    
    # 4. Extract geo entities (those with lat/lon properties)
    geo_entities = [e for e in entities if e.get("lat") and e.get("lon")]
    
    # 5. Extract money flows (edges of type wire_transfer, payment, etc.)
    money_flows = extract_money_flows(entities, edges)
    
    # 6. Optional: one-sentence AI summary
    summary = synthesize_evidence_summary(module_id, sub_category_id, entities, edges)
    
    return response
```

### Neptune Query Strategy

The key insight: **scope the query using entity_type + case label**. This turns a 248K traversal into a 50-500 vertex lookup.

```gremlin
// Get entities of relevant types for this sub-category
g.V().hasLabel('Entity_{case_id}')
  .has('entity_type', within('financial_institution','shell_company','wire_transfer'))
  .limit(500)
  .project('id','name','type','properties')
  .by(id())
  .by(values('name'))
  .by(values('entity_type'))
  .by(valueMap())

// Get edges between those entities
g.V().hasLabel('Entity_{case_id}')
  .has('entity_type', within('financial_institution','shell_company','wire_transfer'))
  .limit(500)
  .bothE().limit(3000)
  .project('source','target','type','props')
  .by(outV().id())
  .by(inV().id())
  .by(label())
  .by(valueMap())
```

### Existing Data to Leverage

- `typology_query_definitions.py` already maps each sub-category to relevant entity types and relationship types
- `typology_precomputed_results.key_entities` has the top 10 entity names per sub-category (stored by extract_subgraph)
- `typology_precomputed_results.subgraph_summary` has entity_count and edge_count (tells us the expected result size)

## Frontend Implementation

### In the Crime Typology page (typology-lens.js)

Add an "Investigate" button next to each sub-category score bar:

```javascript
// When user clicks "Investigate" on a sub-category
async function investigateSubCategory(caseId, moduleId, subCategoryId) {
    var data = await api('GET', `/case-files/${caseId}/typology/${moduleId}/${subCategoryId}/evidence-graph`);
    renderEvidenceGraph(data);
}
```

### Evidence Graph View (new panel or modal)

Three tabs:
1. **Graph** — Force-directed graph of entities + edges (reuse existing graph renderer)
2. **Map** — Plot geo_entities on Mapbox/Leaflet (reuse existing map component)
3. **Money Flow** — Sankey or flow diagram showing financial movement

## Route Addition (case_files.py)

```python
# Typology evidence drill-down: /case-files/{id}/typology/{module}/{sub}/evidence-graph
if "/evidence-graph" in path and "/typology/" in path and method == "GET":
    from lambdas.api.typology_evidence_graph import handler as _evidence_handler
    return _evidence_handler(event, context)
```

## Key Design Decisions

1. **Neptune query is scoped** — Never query all 248K entities. Filter by entity_type specific to the sub-category
2. **Limit to 500 entities** — Even within a sub-category, cap results for UX
3. **Use stored key_entities as seeds** — The pipeline already identified the most relevant entities; prioritize those
4. **Geo is optional** — Only show map tab if geo_entities exist in the result
5. **Money flow is type-specific** — Only show for financial sub-categories (financial_control, placement, layering, billing_schemes, etc.)

## Estimated Effort

- Backend handler: ~2 hours
- Neptune query builder (scoped): ~1 hour  
- Frontend evidence panel: ~2 hours
- Wire routing + test: ~30 min

Total: ~1 session (5-6 hours)

## Dependencies

- Pipeline must have run for the case (key_entities populated)
- Neptune must be accessible from the Lambda VPC
- Entity types must be correctly mapped in typology_query_definitions.py (already done)
