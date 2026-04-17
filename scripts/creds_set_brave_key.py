"""
Set the Brave Search API key on the Lambda function.

Usage:
  1. Paste your Brave API key on the line below (replace PASTE_YOUR_KEY_HERE)
  2. Run: python scripts/set_brave_key.py
"""
import boto3
import sys

# ============================================================
# PASTE YOUR BRAVE API KEY HERE (between the quotes):
BRAVE_KEY = "PASTE_YOUR_KEY_HERE"
# ============================================================

FUNCTION_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"

if BRAVE_KEY == "PASTE_YOUR_KEY_HERE" or not BRAVE_KEY.strip():
    print("ERROR: You need to paste your Brave API key in the script first.")
    print("Open scripts/set_brave_key.py and replace PASTE_YOUR_KEY_HERE")
    sys.exit(1)

client = boto3.client("lambda", region_name="us-east-1")

# Get current env vars so we don't lose them
print("Reading current Lambda configuration...")
config = client.get_function_configuration(FunctionName=FUNCTION_NAME)
env_vars = config.get("Environment", {}).get("Variables", {})

# Add the Brave key
env_vars["BRAVE_SEARCH_API_KEY"] = BRAVE_KEY.strip()

print(f"Setting BRAVE_SEARCH_API_KEY on {FUNCTION_NAME}...")
client.update_function_configuration(
    FunctionName=FUNCTION_NAME,
    Environment={"Variables": env_vars},
)
print("Done! Brave Search API key is now set on the Lambda.")
print("Go back to the app and click 'Refresh Research' on any pattern.")
