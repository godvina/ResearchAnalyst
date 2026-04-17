# Strategic Notes: Investigative Intelligence as an AWS Service

## Date: April 8, 2026
## Author: David Eyre, Emerging Tech Solutions

## Context

The AWS Batch Loader service team is building a managed ingestion solution as an AWS Service. This covers the pipeline/ingestion layer. But every customer use case requires two things:

1. **Pipeline** — ingest, parse, extract, embed, graph-load (the Batch Loader service covers this)
2. **Application layer** — a domain-specific frontend + backend that provides investigative intelligence, case management, entity analysis, prosecution workflows, etc.

The question: could the AWS Service team build a configurable application layer on top of the Batch Loader that ships as a managed AWS Service?

## The Problem

- DOJ/law enforcement customers don't have the people to deploy and maintain a custom investigative intelligence platform
- AWS ProServe doesn't have people who understand investigative intelligence or cross-service solutions at this depth
- The current PoC requires deep domain expertise (investigative methodology, prosecution workflows, evidence admissibility, entity resolution, knowledge graph analysis) that doesn't exist in typical cloud consulting
- Every deployment is a custom build — there's no "install and configure" path

## The Opportunity

What we've built is essentially a **configurable investigative intelligence engine** that sits on top of standard AWS services (Neptune, OpenSearch, Bedrock, Aurora, S3, Step Functions). The domain logic (case viability scoring, threat thread detection, prosecution readiness assessment, entity network analysis) is all in Python services that could be packaged.

### What a Managed Service Could Look Like

**Tier 1: Batch Loader + Intelligence API (AWS Service)**
- Managed ingestion pipeline (already being built)
- Pre-built intelligence APIs: entity extraction, knowledge graph construction, pattern discovery, cross-case analysis
- Configurable via JSON/YAML (like our pipeline_config_service.py)
- Customer brings their own frontend or uses a reference UI

**Tier 2: Full Investigative Intelligence Platform (AWS Service)**
- Everything in Tier 1 plus:
- Configurable case type profiles (antitrust, criminal, financial fraud, trafficking — we already have these)
- Pre-built investigative workflows (playbooks, prosecution funnels, evidence triage)
- Reference frontend that's configurable per case type
- AI briefing engine with domain-specific prompts
- The "Case Intelligence Command Center" as a configurable widget

### Configuration Model

Instead of custom code per customer, the platform would be driven by:
- **Case Type Profile** — defines which entity types matter, which patterns to detect, which prosecution elements to track
- **Workflow Templates** — investigative playbooks per case type
- **AI Prompt Templates** — domain-specific Bedrock prompts for briefings, assessments, threat threads
- **UI Layout Config** — which tabs/panels to show, which indicators to compute

We already have the seeds of this in `case_type_profiles` and `pipeline_config_service`.

## The Challenge: FedRAMP + GovCloud

- Any AWS Service needs FedRAMP authorization before DOJ can use it
- GovCloud deployment adds 12-18 months to the timeline
- The current PoC runs in commercial AWS — moving to GovCloud requires re-architecture for service availability differences
- Bedrock model availability in GovCloud is limited (no Claude 3.5 Sonnet yet, only Haiku)

## Recommendation

**Short term (now → 6 months):** Continue the PoC as a custom deployment. Use it to validate the domain model, prove the value, and refine the case type profiles. This is the "art of the possible" phase.

**Medium term (6-12 months):** Package the intelligence layer as a reusable CDK construct / CloudFormation template that ProServe can deploy. Not a managed service yet, but a "solution accelerator" that reduces deployment from months to days. This is achievable without FedRAMP.

**Long term (12-24 months):** Work with the Batch Loader service team to propose the intelligence layer as an extension to their managed service. The case type profiles and workflow templates become the configuration surface. The reference frontend becomes a hosted UI option.

## Key Insight

The real IP isn't the code — it's the **domain model**. The case type profiles, investigative playbooks, prosecution readiness scoring, and AI prompt engineering for legal/investigative contexts. That's what makes this different from generic document processing. A managed service that captures this domain knowledge and makes it configurable would be genuinely unique in the market.

## Related Files
- Case Type Profiles: `.kiro/specs/case-type-profiles/`
- Pipeline Config: `src/services/pipeline_config_service.py`
- Deployment Wizard: `src/services/deployment_generator.py`
- Customer Deployment Wizard: `.kiro/specs/customer-deployment-wizard/`
