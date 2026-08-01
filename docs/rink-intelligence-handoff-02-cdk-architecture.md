# Rink Intelligence — Handoff Doc 2: CDK Architecture & Deploy Procedure

Paste this as your SECOND message in the new Kiro workspace. This documents
the EXACT working CDK setup from the Research Analyst project so you don't
have to re-solve the same problems.

## COST DECISION: Reuse Existing Neptune + OpenSearch (don't provision new)

OpenSearch Serverless has an AWS-enforced minimum billing floor (~$700/mo
for the smallest OCU allocation) REGARDLESS of actual usage. Neptune adds
another ~$65-150/mo minimum. Standing up a second full stack roughly
doubles these two line items for no real benefit on a demo project.

**Decision: new codebase/workspace (for clean separation of concerns), but
point at the EXISTING Neptune cluster and EXISTING OpenSearch Serverless
collection already running in this AWS account** (same account:
974220725866, us-east-1). Do NOT deploy new Neptune/OpenSearch resources
for this project unless there's a specific isolation requirement later.

Existing endpoints to reuse (from Research Analyst's `env.json`):
```
NEPTUNE_ENDPOINT=neptunedbcluster-qoxzlhiau0ao.cluster-cgaj5jxtrulh.us-east-1.neptune.amazonaws.com
NEPTUNE_PORT=8182
OPENSEARCH_ENDPOINT=https://u260nrrtc0q87ji8iu0k.us-east-1.aoss.amazonaws.com
OPENSEARCH_COLLECTION_ID=u260nrrtc0q87ji8iu0k
```

**How to keep hockey data isolated from case data in the shared cluster:**
- Neptune: Research Analyst uses a per-case vertex label convention
  `Entity_{case_id}`. Use an equivalent convention for hockey, e.g.
  `Player_{season}` / `Goal_{season}` or a single `Hockey` namespace label
  that never overlaps with `Entity_*` labels. Confirm the exact label
  scheme before writing data.
- OpenSearch: use a distinct index name (e.g. `hockey-goals-2024-2025`),
  never write into any index Research Analyst uses.
- New Lambda/API Gateway/S3 bucket — these are cheap and SHOULD be new
  and separate (this is where the real cost is trivial: a few dollars/mo
  at demo volume). Only the two expensive ambient services (Neptune,
  OpenSearch) get shared.

**What this means for the CDK stack below:** skip the `NeptuneConstruct`
and `OpenSearchConstruct` entirely in the new stack (reuse existing
endpoints instead). VPC is only needed if your Lambda must reach Neptune
privately — check whether Neptune's current setup allows public subnet
access (Research Analyst's config used `neptune.subnet_type: "PUBLIC"`)
before assuming you need a full new VPC with NAT gateways etc.

**UPDATE — Aurora decision reversed: KEEP Aurora.** Earlier draft of this
doc suggested skipping Aurora entirely. That was a suggestion for a
minimal MVP, not a requirement — if you want relational storage for
structured season/team/player/game metadata (schedules, rosters,
aggregated stats — things that are naturally tabular and benefit from SQL
joins/aggregation), or if a prior session already built an Aurora schema,
KEEP the `AuroraConstruct` in the new stack. This is a genuinely new,
small Aurora Serverless v2 database for this project (~$45+/mo minimum for
the smallest capacity range) — it is NOT shared with Research Analyst's
Aurora cluster, since the data models are unrelated (case/entity data vs.
hockey game/player data). A small dedicated Aurora instance for this
project is a reasonable, low-cost choice if you want SQL-style queries
alongside the graph (Neptune) and pattern search (OpenSearch) capabilities.

So the net cost-conscious architecture is:
- **Reused (no new cost):** Neptune, OpenSearch Serverless
- **New, cheap:** S3, Lambda, API Gateway
- **New, small but real cost:** Aurora Serverless v2 (~$45+/mo minimum) —
  keep this if you want relational/tabular queries

If you skip Neptune/OpenSearch entirely for a first pass (e.g. start with
just S3 + local analysis), you can defer ALL of the infra below and start
with a plain Python script. Recommended: do exactly that first (see
Handoff Doc 1, phase 1-2) before deploying anything.

## Architecture Pattern To Reuse

This is a config-driven, modular CDK stack. Structure:

```
infra/cdk/
  app.py                    # CDK entry point — reads config, instantiates stack
  deploy.py                 # Custom deploy script (NOT `cdk deploy` directly — see why below)
  config_loader.py          # Loads + validates deployment-configs/*.json
  cdk.json                  # Standard CDK app config
  cdk.context.json          # CDK context cache (auto-generated, gitignore this)
  deployment-configs/
    default.json            # The environment config (account, region, sizing, feature flags)
  stacks/
    research_analyst_stack.py   # Main stack — wires constructs together
  cdk_constructs/
    (one file per AWS service: Vpc, Security, Aurora, Neptune, OpenSearch,
     Lambda, Pipeline, Api, Observability)
```

**Key design decision that made this work well:** the stack is split into
one Construct class per AWS service (`VpcConstruct`, `NeptuneConstruct`,
`OpenSearchConstruct`, `LambdaConstruct`, `ApiConstruct`, etc.), all wired
together in `research_analyst_stack.py`. Each construct reads from a single
`config: dict` passed down from `deployment-configs/default.json`. This
means:
- One config file controls sizing, region, account, feature flags
  (e.g. `neptune.enabled`, `opensearch.mode`) without touching code
- Easy to add a new environment (staging/demo) by copying the config JSON

**For Rink Intelligence, reuse this pattern** (see cost decision above —
Neptune/OpenSearch are REUSED, Aurora is NEW-but-small, S3/Lambda/API GW
are NEW-and-cheap):
- S3 (raw play-by-play JSON + processed data) — NEW bucket, cheap
- Aurora Serverless v2 — NEW, small dedicated database for this project
  (structured season/team/player/game metadata). Keep the
  `AuroraConstruct` pattern from Research Analyst, point it at a NEW
  cluster (not the existing Research Analyst Aurora — different data
  model, keep separate).
- Lambda (API dispatcher — one mega-Lambda behind API Gateway, NOT one
  Lambda per route — see "500 resource limit" gotcha below) — NEW, cheap.
  Configure with env vars pointing at the EXISTING Neptune/OpenSearch
  endpoints (see values above) PLUS the NEW Aurora endpoint/secret.
- API Gateway with `{proxy+}` — NEW, cheap. All routing logic lives IN the
  Lambda code, not in API Gateway resource definitions.
- VPC — needed for the new Aurora cluster regardless. Check whether it can
  also reach the existing Neptune cluster (may need a peering connection
  or Neptune's public subnet accessibility, depending on Neptune's current
  VPC placement) rather than assuming a fresh VPC gives you that for free.
- NO Neptune construct, NO OpenSearch construct in the new stack — those
  two are reused via endpoint values, not provisioned. Aurora construct
  IS included (new, dedicated instance).

## Why We Don't Run Plain `cdk deploy`

`deploy.py` is a custom wrapper because `cdk deploy` alone had issues with
large Lambda assets and multi-environment config switching. The wrapper:
1. Runs `cdk synth` via `app.py` with a config path in CDK context
2. Publishes assets (zipped Lambda code, etc.) to the account's CDK staging
   bucket manually via boto3 (handles large templates that exceed the
   51200-byte inline limit by uploading to S3 first)
3. Deploys via `boto3 cloudformation create_stack`/`update_stack` directly
   (not the CDK CLI's deploy command)
4. Prints a summary of key outputs (API URL, endpoints) at the end

**Recommendation: copy this exact `deploy.py` pattern.** It's the thing
that "was difficult to set up" — reusing it verbatim (adjusted for your
stack name) saves you from re-debugging CDK asset publishing and large
template handling.

## Known Gotchas (from lessons-learned.md — read before you deploy)

These bit us hard on Research Analyst. Prevent them from day one:

1. **CloudFormation 500-resource limit.** If you create one Lambda per API
   route, you blow past 500 resources fast (~5 resources per Lambda:
   function, role, policy, SG, ingress rule). FIX: use ONE mega-Lambda
   behind `apigw.LambdaRestApi(handler=lambda_fn, proxy=True)`. All routing
   logic lives in Python inside the Lambda (`if path == "/goals/{id}" ...`).
2. **CORS on `{proxy+}`.** `LambdaRestApi` with `proxy=True` does NOT
   auto-create OPTIONS methods for CORS preflight. FIX: pass
   `default_cors_preflight_options=apigw.CorsOptions(...)` when creating
   the `LambdaRestApi`. Do this from day one — don't discover it later.
3. **`{proxy+}` doesn't populate `pathParameters` like named routes do.**
   `event["pathParameters"]` only contains `{"proxy": "goals/123/detail"}`
   — you must parse the path yourself in a `_normalize_resource()`-style
   helper and populate named params (`id`, etc.) manually.
4. **Neptune/OpenSearch Lambda VPC networking.** If Neptune and your Lambda
   are in a VPC:
   - Neptune SG must allow inbound port 8182 from the Lambda's SG
   - If Lambda self-invokes (async patterns), you need a Lambda VPC
     interface endpoint + SG rule
   - Secrets Manager VPC endpoint SG must allow the Lambda's SG on 443
   - **Rule of thumb:** after every deploy, check EVERY Lambda SG is in
     EVERY VPC endpoint SG's inbound rules that it needs to reach.
5. **OpenSearch Serverless orphaned resources.** AOSS security policies,
   VPC endpoints, and collections are ACCOUNT-level, not stack-scoped. A
   failed/rolled-back deploy leaves them orphaned and the next deploy fails
   with "already exists." FIX: clean up before retrying:
   ```bash
   aws opensearchserverless delete-security-policy --name <name> --type encryption
   aws opensearchserverless delete-security-policy --name <name> --type network
   aws opensearchserverless delete-access-policy --name <name> --type data
   aws opensearchserverless list-collections --query "collectionSummaries[?name=='<name>'].id" --output text | xargs -I{} aws opensearchserverless delete-collection --id {}
   ```
6. **Lambda timeout defaults are too short.** Default Lambda timeout (3s)
   is never enough for anything touching Neptune/OpenSearch/Bedrock through
   a VPC (cold start + Secrets Manager + actual work easily exceeds 60s).
   FIX: set minimum 300s timeout and 512MB memory for any Lambda that
   calls these services. More memory = proportionally more CPU = faster
   cold starts.
7. **Deploy Lambda code via S3, never `--zip-file fileb://` directly** for
   anything beyond a trivial zip size — it times out/fails silently for
   larger packages. Always: zip → upload to S3 → `update-function-code
   --s3-bucket --s3-key`.
8. **Clean `__pycache__` before every deploy.** Stale `.pyc` files in the
   zip can cause confusing import errors.

## Config File Shape (copy this structure, adjust values)

Trimmed down per the cost decision — no Neptune/OpenSearch/Aurora
constructs, just the endpoint values passed through as Lambda env vars:

```json
{
  "environment_name": "dev",
  "account": "974220725866",
  "region": "us-east-1",
  "partition": "aws",
  "vpc": {
    "create_new": true
  },
  "aurora": {
    "min_capacity": 0.5,
    "max_capacity": 4,
    "subnet_type": "PUBLIC"
  },
  "existing_resources": {
    "neptune_endpoint": "neptunedbcluster-qoxzlhiau0ao.cluster-cgaj5jxtrulh.us-east-1.neptune.amazonaws.com",
    "neptune_port": "8182",
    "opensearch_endpoint": "https://u260nrrtc0q87ji8iu0k.us-east-1.aoss.amazonaws.com",
    "opensearch_collection_id": "u260nrrtc0q87ji8iu0k"
  },
  "encryption": {
    "kms_key_arn": null,
    "enforce_tls": false
  },
  "bedrock": {
    "llm_model_id": "anthropic.claude-3-haiku-20240307-v1:0",
    "embedding_model_id": "amazon.titan-embed-text-v2:0"
  },
  "tags": {},
  "logging": {
    "vpc_flow_logs": false
  }
}
```

Notes:
- `vpc.create_new: true` — this project needs its own new Aurora cluster,
  so it needs its own VPC (or you evaluate whether reusing the default VPC
  with new subnets is simpler; start with a new VPC for cleanliness).
- `aurora` block is a NEW, small, dedicated cluster for this project — NOT
  shared with Research Analyst's Aurora. Sized small (0.5-4 ACU) since
  this is a demo, not production load.
- `existing_resources` block — this project only CONSUMES the Neptune/
  OpenSearch endpoints, it never provisions or deletes them. Be careful
  with IAM permissions: this Lambda's role should have READ/WRITE Gremlin
  + OpenSearch API access but should NOT have permission to delete/modify
  the Neptune cluster or OpenSearch collection itself.
- Neptune/OpenSearch sections are absent because those two services are
  reused from Research Analyst's existing deployment (endpoint values
  only), not deployed here. Aurora IS deployed here (new + separate).
- `bedrock` block only needed if you want AI-generated insight text (e.g.
  "this line combo generates goals 40% more often when starting in the
  defensive zone") — optional nice-to-have, not core to MVP.

## Deploy Commands (exact sequence that works)

```bash
# One-time: bootstrap CDK in the target account/region (only if never done)
cdk bootstrap aws://<ACCOUNT_ID>/us-east-1

# Every deploy:
cd infra/cdk
python deploy.py --config deployment-configs/default.json
```

That's it — `deploy.py` handles synth, asset publishing, and the actual
CloudFormation deploy/update in one command. If it fails partway, check
the OpenSearch orphan cleanup (gotcha #5) before retrying blindly.

## Post-Deploy Checklist

- [ ] Note the API Gateway URL from the deploy summary output
- [ ] Verify Neptune SG allows Lambda SG on 8182
- [ ] Verify OpenSearch collection is reachable from the Lambda
- [ ] Smoke test: invoke the Lambda directly with a test event before
      testing through API Gateway (isolates VPC/networking issues from
      API Gateway routing issues)
- [ ] Deploy Lambda code updates via S3 (see gotcha #7), not `cdk deploy`
      for quick iteration — much faster than a full CDK deploy cycle once
      infra is stood up.

## What To Tell Me When You Start The New Session

Paste both handoff docs, then say something like:

> "Set up Rink Intelligence reusing the EXISTING Neptune and OpenSearch
> Serverless endpoints from the Research Analyst account (see endpoint
> values in this doc) — do not provision new Neptune/OpenSearch. New
> stack should only deploy S3 + one mega-Lambda + API Gateway proxy+,
> using the deploy.py pattern from the handoff doc. Skip Aurora entirely.
> Start with the ingestion script first before touching AWS — pull 10
> games of play-by-play data and show me the shape of a goal event with
> its assist chain."

I'll pick up from there and build it fresh, informed by everything in
these two docs.
