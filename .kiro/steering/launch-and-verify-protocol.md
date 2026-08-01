---
inclusion: auto
---

# Launch & Verify Protocol

Every time you launch a process (EC2, Lambda, batch job, deployment), follow this protocol. No exceptions.

## Pre-Launch Checklist

Before writing ANY code for a new process:

1. **Read lessons-learned.md** — Check for known issues with the approach you're about to use
2. **Calculate time estimate** — `total_items × time_per_item = total_time`. If > 30 min, consider batching
3. **Check IAM permissions** — Does the EC2 role have S3 write, Bedrock access, Lambda invoke, etc.?
4. **Check dependencies** — Does the target AMI have the right Python/boto3 version for the APIs you need?
5. **Test with 1-2 items locally** before building the full pipeline

## Post-Launch Verification (MANDATORY)

After every launch, verify within 2 minutes:

### EC2 Processes
```
T+0:    Launch EC2
T+90s:  Check console output — look for script's first print statement
T+3min: If no script output → investigate immediately (don't wait)
T+5min: Check first progress indicator (count, "Processing...", etc.)
T+15min: Verify metric is increasing (entity count, node count, etc.)
```

### Bedrock Batch Jobs
```
T+0:    Submit job
T+1min: Check status (should be Submitted or Validating)
T+5min: Check status (should be Validating or InProgress)
T+10min: If still Validating → normal for large jobs. If Failed → check message immediately
```

### Lambda Deployments
```
T+0:    Deploy Lambda
T+30s:  Wait for function-updated
T+1min: Test with a simple invoke (not the full workload)
T+2min: Test with the actual use case (small batch)
```

## Ongoing Monitoring

- **Every hour**: Check count/metric for any running process
- **If count unchanged for 30+ min**: Investigate — don't assume it's working
- **Never tell the user "it's running" without a verified metric increase**

## Estimation Rules

- **NEVER give an estimate without showing the math**: `total_items × time_per_item = total_time`
- **If you don't know the item count, query it first** — don't guess
- **Show the calculation to the user**: e.g. "75K entities × 0.05s per Gremlin call = 62 min + 50% buffer = ~90 min"
- **Add 50% buffer** to all estimates for unknowns
- **If estimate > 1 hour**: Tell the user the honest number, not the optimistic one
- **Track actual vs estimated**: Update lessons-learned when estimates are wrong
- **If you can't calculate**: Say "I don't have enough data to estimate — let me measure first" instead of guessing
- **Never say "go ahead and test" while a write-heavy process is running against the same database** — write load causes read timeouts and unreliable results

## Batch Processing Rules

- **Never process items one-at-a-time via Lambda** if count > 1,000
- **Batch size**: 100+ items per Lambda call, or use direct DB connection
- **For bulk Aurora inserts**: Use `execute_values()` or multi-row INSERT, not individual INSERTs
- **For bulk Bedrock calls**: Use Batch Inference API, not serial invoke_model

## Error Recovery

- **If a process fails**: Don't immediately relaunch with the same code. Diagnose first.
- **If a process is stuck**: Check the metric (count), not just the EC2 state
- **Never terminate a working process** to replace it with an "improved" version unless the improvement is tested
