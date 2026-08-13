"""Check which Aurora cluster the RDS Proxy points to."""
import boto3

client = boto3.client('rds', region_name='us-east-1')

# List RDS Proxies
proxies = client.describe_db_proxies()
for p in proxies.get('DBProxies', []):
    if 'research' in p.get('DBProxyName', '').lower():
        name = p['DBProxyName']
        print(f"Proxy: {name}")
        print(f"  Endpoint: {p['Endpoint']}")
        print(f"  Status: {p['Status']}")
        
        # Get targets
        targets = client.describe_db_proxy_targets(DBProxyName=name)
        for t in targets.get('Targets', []):
            rds_id = t.get('RdsResourceId', '?')
            t_type = t.get('Type', '?')
            cluster = t.get('TrackedClusterId', '?')
            endpoint = t.get('Endpoint', '?')
            port = t.get('Port', '?')
            print(f"  Target: {rds_id}")
            print(f"    Type: {t_type}")
            print(f"    Cluster: {cluster}")
            print(f"    Endpoint: {endpoint}:{port}")

# Also list all Aurora clusters
print("\n=== All Aurora Clusters ===")
clusters = client.describe_db_clusters()
for c in clusters.get('DBClusters', []):
    if 'research' in c.get('DBClusterIdentifier', '').lower():
        print(f"  {c['DBClusterIdentifier']}")
        print(f"    Endpoint: {c['Endpoint']}")
        print(f"    Status: {c['Status']}")
        print(f"    DB: {c.get('DatabaseName', '?')}")
