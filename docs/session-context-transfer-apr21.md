# Session Context Transfer — April 21, 2026

## NEXT SESSION: Continue from here

### What Happened This Session

**Entity Extraction Re-Run (Nova Pro):**
- Re-extracted 75K docs with Nova Pro (constrained taxonomy prompt) — $144
- Results loaded into Aurora: 584K entity mentions, 247K unique entities
- 71,163 entities with occurrence >= 2 (high quality)

**Neptune Sync:**
- Vertex sync: 48K vertices added (~32 min)
- Edge sync: 12,259 of 27,430 edges created (terminated — too slow at 71/min)
- Neptune: 991K nodes, 13.17M edges (mixed old + new)

**DS12 Pipeline Test:**
- 122 documents inserted into Aurora with source_metadata.dataset = "DS12"
- Entity extraction failed: dataset filter not uploaded to S3, processed all 76K docs
- Accidental Bedrock batch job running for 76K docs (~$144) — cannot cancel
- When it completes, load results — entities will include DS12 docs

**Pipeline Fixes Needed:**
1. entity_extraction_pipeline.py: default to incremental, require --all for full
2. Verify S3-uploaded scripts match local before launching EC2
3. Neptune needs S3 VPC endpoint for bulk loader
4. Neptune edge sync incomplete

**Data Inventory:**
- 76K docs in Aurora (DS1-8 + teyler partial + DS12)
- DS10 (503K), DS11 (332K) available from standardworks.ai
- Master entity taxonomy: 40 types, 10 tiers

### Currently Running
- Bedrock batch y51fjlj9fkb9: InProgress (76K docs, ~$144, cannot cancel)
- All EC2s: Terminated

### Key Files
- docs/lessons-learned.md (Issues 1-57)
- .kiro/steering/kiro-builder-playbook.md
- docs/master-entity-taxonomy.md
- docs/data-inventory-and-ingestion-plan.md
- scripts/entity_extraction_pipeline.py (needs dataset-filter fix verified on S3)
- scripts/ingest_dataset.py
- scripts/comprehensive_test.py
