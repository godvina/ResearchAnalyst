"""Fix Neptune entity names for Operation Nightfall via Lambda invocation.

The Lambda has VPC access to Neptune. We invoke it with a Gremlin query
to update the vertex properties.
"""
import boto3
import json

LAMBDA_NAME = "ResearchAnalystStack-CaseFilesLambda91230A57-gN7wQJqzNlFq"
CASE_ID = "0b24a307-a674-41b6-8d22-581c4a4aa566"
LABEL = "Entity_0b24a307-a674-41b6-8d22-581c4a4aa566"

lam = boto3.client("lambda", region_name="us-east-1")

# Names to fix in Neptune
RENAME_MAP = {
    "Jeffrey Epstein": "Marcus Blackwell",
    "Ghislaine Maxwell": "Catherine Sterling",
    "Lesley Groff": "Patricia Harmon",
    "Larry Visoski": "Daniel Whitmore",
    "Dave Rodgers": "Keith Patterson",
    "Leon Black": "Victor Nash",
    "Ronald Lauder": "Philip Grant",
    "Peggy Siegal": "Sandra Voss",
    "Rich Kahn": "Thomas Vance",
    "Richard Kahn": "Thomas Vance",
    "Eric Roth": "Jonathan Mercer",
    "Jeff Hawkins": "Brian Delaney",
    "Cecile de Jongh": "Renee Fontaine",
    "Les Wexner": "Richard Caldwell",
    "Natalia Molotkova": "Elena Vasquez",
    "Natasha Molotkova": "Elena Vasquez",
    "Bella Klein": "Sophia Reyes",
    "Bebe Avdiu": "Nadia Kovar",
    "Karyna Shuliak": "Anya Petrov",
    "Melanie Spinella": "Rachel Dumont",
    "Daphne Wallace": "Claire Ashford",
    "Laura Bard": "Megan Fischer",
    "Erica D. Peterson": "Samantha Rhodes",
    "Leo Loking": "Viktor Soren",
    "Jojo Fontanilla": "Marco Delgado",
    "Merwin Dela cruz": "Carlos Rivera",
    "Merwin Dela Cruz": "Carlos Rivera",
    "Dr. Chen": "Dr. Park",
}


def invoke_gremlin(query):
    """Invoke a Gremlin query via the Lambda (which has Neptune VPC access)."""
    payload = {
        "action": "query_neptune",
        "gremlin": query,
    }
    resp = lam.invoke(
        FunctionName=LAMBDA_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload).encode(),
    )
    result = json.loads(resp["Payload"].read().decode())
    return result


# First check if Neptune is accessible via Lambda
print("Testing Neptune access via Lambda...")
test = invoke_gremlin(f"g.V().hasLabel('{LABEL}').count()")
print(f"  Neptune vertex count for label: {test}")

if "error" in str(test).lower() and "neptune" not in str(test).lower():
    print("\n  Trying alternative approach — direct property update via relationships endpoint...")

print(f"\nUpdating {len(RENAME_MAP)} names in Neptune...")
success = 0
errors = 0

for old_name, new_name in RENAME_MAP.items():
    esc_old = old_name.replace("'", "\\'")
    esc_new = new_name.replace("'", "\\'")
    query = f"g.V().hasLabel('{LABEL}').has('canonical_name','{esc_old}').property('canonical_name','{esc_new}')"
    result = invoke_gremlin(query)
    if "error" in str(result).lower():
        print(f"  ✗ {old_name}: {str(result)[:80]}")
        errors += 1
    else:
        print(f"  ✓ {old_name} → {new_name}")
        success += 1

print(f"\nDone! Success: {success}, Errors: {errors}")
