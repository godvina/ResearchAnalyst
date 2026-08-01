"""Load the UVG grid into Neptune as a knowledge graph.

Creates:
- Vertex for each of the 62 grid nodes (with properties: lat, lng, classification, known_site)
- Vertex for each known ancient site (with properties from research)
- Edge: GRID_LINE connecting adjacent grid nodes
- Edge: LOCATED_AT connecting known sites to their nearest grid node
- Edge: ALIGNED_WITH connecting sites that share a great circle alignment

Uses the project's existing NeptuneGraphLoader pattern (CSV bulk load via S3).
"""

import csv
import io
import json
import os
import sys
import uuid

import boto3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "data")
S3_BUCKET = "research-analyst-data-lake-974220725866"
REGION = "us-east-1"

# Load data
with open(os.path.join(DATA_DIR, "uvg-grid-investigation-database.json")) as f:
    grid_db = json.load(f)

with open(os.path.join(DATA_DIR, "uvg-grid-hagens-official.json")) as f:
    hagens = json.load(f)


def generate_nodes_csv():
    """Generate Neptune nodes CSV for all grid vertices + known sites."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["~id", "~label", "node_type:String", "lat:Double", "lng:Double",
                     "classification:String", "continent:String", "known_site:String",
                     "priority:String", "node_id:Int"])

    # Grid nodes
    for node in grid_db["nodes"]:
        node_id = f"grid_node_{node['id']}"
        writer.writerow([
            node_id,
            "GridNode",
            node.get("name", f"UVG {node['id']}"),
            node["lat"],
            node["lng"],
            node["classification"],
            node.get("continent", ""),
            node.get("nearest_known_site", ""),
            node.get("priority", ""),
            node["id"],
        ])

    # Known ancient sites (as separate vertices)
    for site in grid_db.get("reference_sites", []):
        site_id = f"site_{site['name'].lower().replace(' ', '_')[:40]}"
        writer.writerow([
            site_id,
            "AncientSite",
            site["name"],
            site["lat"],
            site["lng"],
            site.get("type", "ancient_monument"),
            "",
            site["name"],
            "documented",
            0,
        ])

    return buf.getvalue()


def generate_edges_csv():
    """Generate Neptune edges CSV for grid connections + site-to-node links."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["~id", "~from", "~to", "~label", "edge_type:String",
                     "distance_km:Double", "confidence:String"])

    nodes = grid_db["nodes"]
    node_map = {n["id"]: n for n in nodes}
    edge_count = 0

    # Grid line edges (connect adjacent nodes)
    # Same latitude band, adjacent longitude
    from itertools import combinations

    bands = {}
    for n in nodes:
        band_key = round(abs(n["lat"]), 1)
        hemisphere = "N" if n["lat"] >= 0 else "S"
        key = f"{hemisphere}_{band_key}"
        if key not in bands:
            bands[key] = []
        bands[key].append(n)

    # Ring connections within bands
    for band_name, band_nodes in bands.items():
        sorted_band = sorted(band_nodes, key=lambda x: x["lng"])
        for i in range(len(sorted_band)):
            curr = sorted_band[i]
            next_node = sorted_band[(i + 1) % len(sorted_band)]
            lng_diff = abs(curr["lng"] - next_node["lng"])
            if lng_diff > 180:
                lng_diff = 360 - lng_diff
            if lng_diff < 80:  # Adjacent in ring
                edge_id = f"grid_edge_{curr['id']}_{next_node['id']}"
                writer.writerow([
                    edge_id,
                    f"grid_node_{curr['id']}",
                    f"grid_node_{next_node['id']}",
                    "GRID_LINE",
                    "ring_connection",
                    0,
                    "geometric",
                ])
                edge_count += 1

    # Cross-band connections
    band_keys = sorted(bands.keys())
    for bi in range(len(band_keys) - 1):
        for bj in range(bi + 1, len(band_keys)):
            band_a = bands[band_keys[bi]]
            band_b = bands[band_keys[bj]]
            for na in band_a:
                for nb in band_b:
                    lng_diff = abs(na["lng"] - nb["lng"])
                    if lng_diff > 180:
                        lng_diff = 360 - lng_diff
                    lat_diff = abs(na["lat"] - nb["lat"])
                    # Connect if close in longitude and adjacent in latitude
                    if lng_diff < 40 and lat_diff < 35:
                        edge_id = f"grid_edge_{na['id']}_{nb['id']}"
                        writer.writerow([
                            edge_id,
                            f"grid_node_{na['id']}",
                            f"grid_node_{nb['id']}",
                            "GRID_LINE",
                            "cross_band",
                            0,
                            "geometric",
                        ])
                        edge_count += 1

    # Site-to-node LOCATED_AT edges
    for node in nodes:
        if node.get("nearest_known_site") and node.get("distance_to_nearest_km", 9999) < 500:
            site_name = node["nearest_known_site"]
            site_id = f"site_{site_name.lower().replace(' ', '_')[:40]}"
            edge_id = f"located_at_{node['id']}_{site_name[:20]}"
            writer.writerow([
                edge_id,
                site_id,
                f"grid_node_{node['id']}",
                "LOCATED_AT",
                "proximity",
                node.get("distance_to_nearest_km", 0),
                "confirmed" if node["distance_to_nearest_km"] < 200 else "probable",
            ])
            edge_count += 1

    # Jim Alison Great Circle alignment edges
    alison_sites = ["Great Pyramid of Giza", "Nazca Lines", "Easter Island",
                    "Machu Picchu", "Mohenjo-daro", "Petra"]
    for i in range(len(alison_sites)):
        for j in range(i + 1, len(alison_sites)):
            edge_id = f"aligned_{alison_sites[i][:10]}_{alison_sites[j][:10]}"
            from_id = f"site_{alison_sites[i].lower().replace(' ', '_')[:40]}"
            to_id = f"site_{alison_sites[j].lower().replace(' ', '_')[:40]}"
            writer.writerow([
                edge_id, from_id, to_id,
                "ALIGNED_WITH",
                "great_circle",
                0,
                "confirmed",
            ])
            edge_count += 1

    return buf.getvalue(), edge_count


def main():
    print("Loading UVG Grid into Neptune Graph Format")
    print("=" * 60)

    # Generate CSVs
    print("Generating nodes CSV...")
    nodes_csv = generate_nodes_csv()
    node_count = nodes_csv.count("\n") - 1
    print(f"  {node_count} nodes")

    print("Generating edges CSV...")
    edges_csv, edge_count = generate_edges_csv()
    print(f"  {edge_count} edges")

    # Upload to S3
    print("\nUploading to S3...")
    s3 = boto3.client("s3", region_name=REGION)

    nodes_key = "neptune-bulk-load/uvg-grid-nodes.csv"
    edges_key = "neptune-bulk-load/uvg-grid-edges.csv"

    s3.put_object(Bucket=S3_BUCKET, Key=nodes_key, Body=nodes_csv.encode(), ContentType="text/csv")
    print(f"  Nodes: s3://{S3_BUCKET}/{nodes_key}")

    s3.put_object(Bucket=S3_BUCKET, Key=edges_key, Body=edges_csv.encode(), ContentType="text/csv")
    print(f"  Edges: s3://{S3_BUCKET}/{edges_key}")

    # Also save locally for reference
    local_nodes = os.path.join(DATA_DIR, "neptune-grid-nodes.csv")
    local_edges = os.path.join(DATA_DIR, "neptune-grid-edges.csv")
    with open(local_nodes, "w") as f:
        f.write(nodes_csv)
    with open(local_edges, "w") as f:
        f.write(edges_csv)
    print(f"\n  Local copies saved to src/data/")

    print(f"\nReady for Neptune bulk load:")
    print(f"  Nodes: s3://{S3_BUCKET}/{nodes_key}")
    print(f"  Edges: s3://{S3_BUCKET}/{edges_key}")
    print(f"\nTo trigger bulk load, run:")
    print(f"  python -c \"from services.neptune_graph_loader import ...; loader.bulk_load('{nodes_key}', '{edges_key}', IAM_ROLE_ARN)\"")


if __name__ == "__main__":
    main()
