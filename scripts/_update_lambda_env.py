"""Update all pipeline Lambda environment variables."""
import boto3

client = boto3.client("lambda", region_name="us-east-1")

ENV_VARS = {
    "AURORA_DB_NAME": "research_analyst",
    "AURORA_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:974220725866:secret:AuroraClusterSecret8E4F2BC8-4zmQsxQuyYQJ-TOjJyL",
    "AURORA_PROXY_ENDPOINT": "research-analyst-proxy.proxy-cgaj5jxtrulh.us-east-1.rds.amazonaws.com",
    "NEPTUNE_ENDPOINT": "neptunedbcluster-qoxzlhiau0ao.cluster-cgaj5jxtrulh.us-east-1.neptune.amazonaws.com",
    "NEPTUNE_PORT": "8182",
    "OPENSEARCH_ENDPOINT": "https://hzrvvva3hodw069v9442.us-east-1.aoss.amazonaws.com",
    "OPENSEARCH_ENABLED": "true",
    "OPENSEARCH_COLLECTION_ID": "hzrvvva3hodw069v9442",
}

FUNCTIONS = [
    "TypologyPipeline-ThresholdCheck",
    "TypologyPipeline-AcquireLock",
    "TypologyPipeline-ExtractSubgraph",
    "TypologyPipeline-ScoreTypology",
    "TypologyPipeline-BuildSummaryGraph",
    "TypologyPipeline-ReleaseLock",
]

for fn in FUNCTIONS:
    resp = client.update_function_configuration(
        FunctionName=fn,
        Environment={"Variables": ENV_VARS},
    )
    print(f"  Updated: {fn} -> {resp['LastUpdateStatus']}")

print("\nAll pipeline Lambdas updated with Aurora + Neptune + OpenSearch env vars.")
