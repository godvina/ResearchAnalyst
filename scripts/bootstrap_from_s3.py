"""Bootstrap: pull all steering and docs from S3."""
import subprocess
cmds = [
    "aws s3 sync s3://research-analyst-data-lake-974220725866/kiro-steering/ .kiro/steering/",
    "aws s3 sync s3://research-analyst-data-lake-974220725866/docs/ docs/",
]
for c in cmds:
    print(f"Running: {c}")
    subprocess.run(c, shell=True, check=True)
print("\nDone! Steering and docs synced from S3.")
print("Key file: docs/session-context-transfer-20260625.md")