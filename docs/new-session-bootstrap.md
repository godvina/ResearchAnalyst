# New Session Bootstrap Guide

## How to Start a New Kiro Session on This Project

Copy-paste this into the first message of any new Kiro session:

---

CONTEXT TRANSFER: We are continuing work on the Investigative Intelligence Platform.

Read these files BEFORE doing anything:
- docs/lessons-learned.md (52+ production issues and fixes — MANDATORY)
- .kiro/steering/kiro-builder-playbook.md (operating rules)
- .kiro/steering/launch-and-verify-protocol.md (EC2/process launch rules)
- .kiro/steering/entity-extraction-rules.md (extraction pipeline rules)
- docs/master-entity-taxonomy.md (40 entity types across 10 tiers)

Key infrastructure:
- AWS account: 974220725866, us-east-1
- Lambda: ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq
- API: https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1
- Demo case: ed0b6c27 (Epstein Combined — NEVER break this)
- Main case: 7f05e8d5 (Epstein Main — 82K docs, 75K entities)
- Neptune: neptunedbcluster-qoxzlhiau0ao.cluster-cgaj5jxtrulh.us-east-1.neptune.amazonaws.com
- EC2 AMI: ami-0c1fe732b5494dc14 (Amazon Linux 2023 — needs pip3 install boto3)
- EC2 profile: DOJ-Processing-Profile (has S3, Lambda, Bedrock, EC2 permissions)
- S3 bucket: research-analyst-data-lake-974220725866

Critical rules (violations have caused production failures):
1. Deploy Lambda via S3, NEVER --zip-file fileb://
2. Clean __pycache__ before EVERY Lambda deploy
3. Use EC2 for ANY process > 30 minutes (laptop sleeps)
4. Verify EC2 console output within 2 minutes of launch
5. Check running EC2 instances on EVERY prompt
6. NEVER give time estimates without showing the math
7. NEVER terminate a working EC2 process
8. Use __.V() not g.V() for Neptune anonymous traversals
9. Run model bake-off before ANY bulk AI extraction
10. Test IAM permissions before launching EC2 scripts

Check current state:
- Running EC2 instances: check immediately
- Active specs: .kiro/specs/geospatial-travel-intelligence/ (Module 1)
- Active specs: .kiro/specs/investigation-engine/ (Module 2)
- Active specs: .kiro/specs/aws-resource-optimizer/

User: David Eyre, Emerging Tech Solutions, AWS
Two weeks until pilot kickoff. 500TB production target.

---

## How to Start a NEW Project with These Lessons

For a completely new project (not this repo), copy these files to the new repo:

1. `.kiro/steering/kiro-builder-playbook.md` — universal operating rules
2. `.kiro/steering/launch-and-verify-protocol.md` — universal launch rules

Then customize:
3. Create project-specific `docs/lessons-learned.md` (start empty, it'll grow)
4. Create project-specific `.kiro/steering/` files for domain rules
5. Update the infrastructure details in the playbook

The steering files with `inclusion: auto` are automatically loaded into every Kiro session — that's the mechanism that prevents knowledge loss between sessions.
