"""Set up Neptune bulk loader IAM role and configure Lambda env var."""
import boto3
import json

REGION = "us-east-1"
ROLE_NAME = "NeptuneLoadFromS3"
ROLE_ARN = "arn:aws:iam::974220725866:role/NeptuneLoadFromS3"
GRAPH_LOAD_LAMBDA = "ResearchAnalystStack-IngestionGraphLoadLambda9C8CC-64fx1gSSh7Fg"

iam = boto3.client("iam", region_name=REGION)
lam = boto3.client("lambda", region_name=REGION)

# Trust policy already has rds.amazonaws.com which Neptune uses
print("Trust policy already correct (rds.amazonaws.com)")

# Associate the role with the Neptune cluster
print("\nAssociating role with Neptune cluster...")
neptune = boto3.client("neptune", region_name=REGION)
clusters = neptune.describe_db_clusters()["DBClusters"]
neptune_cluster = None
for c in clusters:
    if "researchanalyst" in c["DBClusterIdentifier"].lower():
        neptune_cluster = c
        break

if neptune_cluster:
    cluster_id = neptune_cluster["DBClusterIdentifier"]
    existing_roles = [r["RoleArn"] for r in neptune_cluster.get("AssociatedRoles", [])]
    if ROLE_ARN in existing_roles:
        print(f"  Role already associated with {cluster_id}")
    else:
        try:
            neptune.add_role_to_db_cluster(DBClusterIdentifier=cluster_id, RoleArn=ROLE_ARN)
            print(f"  Role associated with {cluster_id}")
        except Exception as e:
            print(f"  Association error: {e}")
else:
    print("  No Neptune cluster found!")

# Set NEPTUNE_IAM_ROLE_ARN on the graph load Lambda
print(f"\nSetting NEPTUNE_IAM_ROLE_ARN on {GRAPH_LOAD_LAMBDA}...")
config = lam.get_function_configuration(FunctionName=GRAPH_LOAD_LAMBDA)
env_vars = config.get("Environment", {}).get("Variables", {})
env_vars["NEPTUNE_IAM_ROLE_ARN"] = ROLE_ARN
lam.update_function_configuration(FunctionName=GRAPH_LOAD_LAMBDA, Environment={"Variables": env_vars})
waiter = lam.get_waiter("function_updated_v2")
waiter.wait(FunctionName=GRAPH_LOAD_LAMBDA)
print("  Done!")

print("\nNeptune bulk loader is configured. Deploy Lambda code and re-run pipeline.")
