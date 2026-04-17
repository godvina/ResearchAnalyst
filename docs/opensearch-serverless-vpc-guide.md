# OpenSearch Serverless (AOSS) — VPC Lambda Connectivity Guide

## The Problem

Lambda functions in a VPC cannot reach OpenSearch Serverless (AOSS) endpoints directly because:
1. AOSS is a public AWS service (like S3, DynamoDB)
2. Lambda in VPC gets a private ENI — no public IP, even in public subnets
3. `allow_public_subnet=True` in CDK only suppresses warnings, doesn't give Lambda a public IP
4. Unlike Neptune/Aurora (VPC-native services), AOSS requires a VPC endpoint

## What Does NOT Work

| Approach | Result | Why |
|----------|--------|-----|
| Lambda in public subnet → AOSS public endpoint | `Connection timed out` (errno 110) | Lambda has no public IP |
| Lambda in public subnet with IGW route | `Connection timed out` | IGW requires public IP on the ENI |
| IPv6 connection attempts | `Cannot assign requested address` (errno 99) | VPC Lambda doesn't support IPv6 |
| VPC endpoint with private DNS + collection endpoint URL | `Connection timed out` | DNS resolves to VPC endpoint IPs but connection still fails if network policy isn't configured |
| `AllowFromPublic: True` network policy alone | Still times out from VPC | Lambda can't reach public endpoint |

## What DOES Work

### Required Components

1. **VPC Interface Endpoint** for `com.amazonaws.{region}.aoss`
   - Only deploy in supported AZs (us-east-1: a, b, c — NOT d, e, f)
   - Enable Private DNS: `True`
   - Security group: Allow HTTPS (443) inbound from VPC CIDR and all Lambda SGs

2. **AOSS Network Policy** with `SourceVPCEs`
   ```json
   [{
     "Rules": [
       {"ResourceType": "collection", "Resource": ["collection/{name}"]},
       {"ResourceType": "dashboard", "Resource": ["collection/{name}"]}
     ],
     "AllowFromPublic": false,
     "SourceVPCEs": ["vpce-0xxxxxxxxx"]
   }]
   ```

3. **AOSS Data Access Policy** with Lambda role ARNs
   ```json
   [{
     "Rules": [
       {"ResourceType": "index", "Resource": ["index/{name}/*"],
        "Permission": ["aoss:CreateIndex","aoss:UpdateIndex","aoss:DescribeIndex","aoss:ReadDocument","aoss:WriteDocument"]},
       {"ResourceType": "collection", "Resource": ["collection/{name}"],
        "Permission": ["aoss:CreateCollectionItems","aoss:UpdateCollectionItems","aoss:DescribeCollectionItems"]}
     ],
     "Principal": ["arn:aws:iam::{account}:root"]
   }]
   ```

4. **IAM Policy** on Lambda roles: `aoss:APIAccessAll` on the collection ARN

5. **HTTP Client Configuration** — connect via VPC endpoint URL, sign for collection endpoint:
   - `OPENSEARCH_ENDPOINT` = collection endpoint (for SigV4 signing + Host header)
   - `OPENSEARCH_VPCE_URL` = VPC endpoint DNS (for actual TCP connection)
   - Set `Host` header to collection hostname so AOSS routes to correct collection
   - Disable TLS hostname verification (VPC endpoint cert won't match collection hostname)
   - Force IPv4 resolution (Lambda VPC doesn't support IPv6)

## Key Differences from Neptune/Aurora

| Aspect | Neptune/Aurora | OpenSearch Serverless |
|--------|---------------|----------------------|
| Service type | VPC-native | Public service |
| Lambda connectivity | Direct via VPC | Requires VPC endpoint |
| DNS resolution | Private DNS in VPC | Needs VPC endpoint private DNS |
| Authentication | IAM or password | SigV4 + data access policy |
| Network policy | Security groups only | AOSS network policy + SGs |
| AZ support | All AZs | Limited AZs (check per region) |

## AOSS VPC Endpoint AZ Support (us-east-1)

- Supported: us-east-1a, us-east-1b, us-east-1c
- NOT supported: us-east-1d, us-east-1e, us-east-1f
- Cross-AZ traffic works — Lambda in any AZ can reach endpoint ENIs in supported AZs

## Deployment Order

1. Create encryption policy
2. Create data access policy (with Lambda role ARNs + account root)
3. Create AOSS-managed VPC endpoint via `aws opensearchserverless create-vpc-endpoint` (NOT ec2 create-vpc-endpoint)
4. Create network policy with AOSS VPC endpoint ID from step 3
5. Create AOSS collection (depends on encryption + network + data access policies)
6. Add `aoss:APIAccessAll` IAM policy to all Lambda execution roles
7. Deploy Lambda code with `OPENSEARCH_ENDPOINT` env var (collection endpoint URL)
8. Wait 5-10 minutes for all policy propagation

CRITICAL: Use `opensearchserverless create-vpc-endpoint`, NOT `ec2 create-vpc-endpoint`. They are different. The EC2 VPC endpoint connects but AOSS can't route requests (returns UnknownOperationException). The AOSS-managed VPC endpoint handles DNS and routing correctly.

## CDK Gotchas

- `cdk.Fn.sub()` tokens inside `json.dumps()` → CloudFormation `Fn::Sub` error
  - Fix: Use `cdk.Fn.sub()` on the entire JSON string, not inside it
  - Or use `cdk.Fn.join()` for ARN construction with token references
- Lambda role ARNs are CDK tokens — can't serialize into AOSS data access policy via `json.dumps`
  - Fix: Use account root principal in data access policy, control access via IAM policies
- `python3` command doesn't exist on Windows — use `python` in `cdk.json`

## Environment Variables

```
OPENSEARCH_ENDPOINT=https://{collection-id}.{region}.aoss.amazonaws.com
OPENSEARCH_COLLECTION_ID={collection-id}
```

No `OPENSEARCH_VPCE_URL` needed when using AOSS-managed VPC endpoint — the collection endpoint hostname resolves to the VPC endpoint's private IPs via private DNS automatically.

## Current Status (as of session end)

- VPC connectivity: SOLVED via AOSS-managed VPC endpoint (`opensearchserverless create-vpc-endpoint`)
- Network routing: SOLVED (no more UnknownOperationException)
- Read access (HEAD): WORKING
- Write access (PUT index creation): SOLVED — required `X-Amz-Content-Sha256` header
- Bulk indexing: WORKING — AOSS VECTORSEARCH collections don't support custom `_id` in bulk ops
- End-to-end: Index created, documents being indexed into OpenSearch Serverless

## Critical SigV4 Requirement for AOSS

AOSS requires the `X-Amz-Content-Sha256` header with the SHA256 hash of the request body for ALL requests (especially writes). Without this header, write operations return 403 Forbidden even with correct IAM and data access policies.

```python
import hashlib
headers["X-Amz-Content-Sha256"] = hashlib.sha256(body_bytes).hexdigest()
```

This is different from standard OpenSearch where the body hash is optional in SigV4.

## IAM Permissions Required

Lambda execution roles need BOTH:
- `aoss:APIAccessAll` — for data plane API access
- `aoss:DashboardsAccessAll` — required for full collection access

## AOSS VECTORSEARCH Limitations

- Custom document `_id` not supported in bulk index operations — AOSS auto-generates IDs
- Use `document_id` as a field in the document body instead for lookups
- Index names must be lowercase
