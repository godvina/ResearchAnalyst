"""Seed the statutes and statutory_elements tables with 6 federal statutes.

Runnable as:
    python src/db/seeds/seed_statutes.py

Uses INSERT ... ON CONFLICT DO NOTHING for idempotency — safe to run multiple times.

Supports two modes:
  1. Direct psycopg2 via ConnectionManager (Lambda / VPC environment)
  2. RDS Data API via boto3 (local dev with Data API enabled)

Set environment variable SEED_MODE=data_api to use RDS Data API.
Otherwise defaults to psycopg2 ConnectionManager.
"""

import os
import sys
import uuid

# ---------------------------------------------------------------------------
# Statute seed data — 6 federal statutes per Requirement 1.2
# ---------------------------------------------------------------------------

STATUTES = [
    {
        "citation": "18 U.S.C. § 1591",
        "title": "Sex Trafficking of Children or by Force, Fraud, or Coercion",
        "description": (
            "Criminalizes sex trafficking involving force, fraud, or coercion, "
            "or where the victim is under 18 years of age. Carries severe federal "
            "penalties including mandatory minimum sentences."
        ),
        "elements": [
            {
                "display_name": "Recruiting, Harboring, or Transporting",
                "description": (
                    "The defendant recruited, enticed, harbored, transported, "
                    "provided, obtained, advertised, maintained, patronized, or "
                    "solicited by any means a person."
                ),
            },
            {
                "display_name": "Commercial Sex Acts",
                "description": (
                    "The defendant knew or recklessly disregarded that the person "
                    "would be caused to engage in a commercial sex act."
                ),
            },
            {
                "display_name": "Force, Fraud, or Coercion",
                "description": (
                    "The defendant used force, threats of force, fraud, or coercion "
                    "to cause the person to engage in commercial sex acts, or knew "
                    "that such means would be used."
                ),
            },
            {
                "display_name": "Victim Under 18",
                "description": (
                    "The victim had not attained the age of 18 years at the time "
                    "of the offense, or the defendant had a reasonable opportunity "
                    "to observe the victim and believed the victim was under 18."
                ),
            },
            {
                "display_name": "Interstate Commerce",
                "description": (
                    "The offense was in or affecting interstate or foreign commerce, "
                    "or the conduct occurred within the special maritime and "
                    "territorial jurisdiction of the United States."
                ),
            },
            {
                "display_name": "Knowledge of Age",
                "description": (
                    "The defendant knew or recklessly disregarded the fact that the "
                    "victim had not attained the age of 18 years."
                ),
            },
            {
                "display_name": "Conspiracy",
                "description": (
                    "The defendant conspired with one or more persons to commit "
                    "the offense, and at least one overt act was committed in "
                    "furtherance of the conspiracy."
                ),
            },
        ],
    },
    {
        "citation": "18 U.S.C. § 1341",
        "title": "Mail Fraud",
        "description": (
            "Prohibits the use of the United States Postal Service or any "
            "interstate mail carrier to further a scheme to defraud. A cornerstone "
            "federal fraud statute with broad prosecutorial application."
        ),
        "elements": [
            {
                "display_name": "Scheme to Defraud",
                "description": (
                    "The defendant devised or intended to devise a scheme or "
                    "artifice to defraud, or to obtain money or property by means "
                    "of false or fraudulent pretenses, representations, or promises."
                ),
            },
            {
                "display_name": "Material Misrepresentation",
                "description": (
                    "The scheme involved a material misrepresentation — a false "
                    "statement or omission of fact that a reasonable person would "
                    "consider important in making a decision."
                ),
            },
            {
                "display_name": "Use of Mails",
                "description": (
                    "The defendant used or caused the use of the United States "
                    "Postal Service or a private or commercial interstate carrier "
                    "for the purpose of executing the scheme."
                ),
            },
            {
                "display_name": "Intent to Defraud",
                "description": (
                    "The defendant acted with the specific intent to defraud — "
                    "that is, with the intent to deceive or cheat for the purpose "
                    "of obtaining money, property, or something of value."
                ),
            },
        ],
    },
    {
        "citation": "18 U.S.C. § 1343",
        "title": "Wire Fraud",
        "description": (
            "Prohibits the use of wire, radio, or television communications in "
            "interstate or foreign commerce to further a scheme to defraud. "
            "Parallel to mail fraud but covers electronic communications."
        ),
        "elements": [
            {
                "display_name": "Scheme to Defraud",
                "description": (
                    "The defendant devised or intended to devise a scheme or "
                    "artifice to defraud, or to obtain money or property by means "
                    "of false or fraudulent pretenses, representations, or promises."
                ),
            },
            {
                "display_name": "Material Misrepresentation",
                "description": (
                    "The scheme involved a material misrepresentation — a false "
                    "statement or omission of fact that a reasonable person would "
                    "consider important in making a decision."
                ),
            },
            {
                "display_name": "Use of Wire Communications",
                "description": (
                    "The defendant used or caused the use of wire, radio, or "
                    "television communication in interstate or foreign commerce "
                    "for the purpose of executing the scheme."
                ),
            },
            {
                "display_name": "Intent to Defraud",
                "description": (
                    "The defendant acted with the specific intent to defraud — "
                    "that is, with the intent to deceive or cheat for the purpose "
                    "of obtaining money, property, or something of value."
                ),
            },
        ],
    },
    {
        "citation": "18 U.S.C. § 2241",
        "title": "Aggravated Sexual Abuse",
        "description": (
            "Criminalizes sexual acts committed through force, threat, or "
            "rendering the victim unconscious or involuntarily drugged. Carries "
            "severe mandatory minimum sentences under federal law."
        ),
        "elements": [
            {
                "display_name": "Sexual Act",
                "description": (
                    "The defendant knowingly caused another person to engage in a "
                    "sexual act as defined under 18 U.S.C. § 2246."
                ),
            },
            {
                "display_name": "By Force or Threat",
                "description": (
                    "The defendant used force, the threat of serious bodily injury, "
                    "or rendered the victim unconscious, or administered a drug or "
                    "intoxicant to substantially impair the victim's ability to "
                    "appraise or control conduct."
                ),
            },
            {
                "display_name": "Against Will",
                "description": (
                    "The sexual act was committed without the consent of the victim "
                    "and against the victim's will."
                ),
            },
            {
                "display_name": "Resulting in Bodily Injury or Fear",
                "description": (
                    "The offense resulted in bodily injury to the victim, or the "
                    "defendant's conduct placed the victim in fear of death, "
                    "serious bodily injury, or kidnapping."
                ),
            },
        ],
    },
    {
        "citation": "18 U.S.C. § 1951",
        "title": "Hobbs Act — Robbery and Extortion",
        "description": (
            "Prohibits robbery or extortion that affects interstate or foreign "
            "commerce. Frequently used in federal prosecutions involving organized "
            "crime, public corruption, and gang-related offenses."
        ),
        "elements": [
            {
                "display_name": "Robbery or Extortion",
                "description": (
                    "The defendant committed or attempted to commit robbery or "
                    "extortion as defined under the Hobbs Act — the unlawful "
                    "taking or obtaining of property from another, or the obtaining "
                    "of property through wrongful use of fear."
                ),
            },
            {
                "display_name": "Affecting Interstate Commerce",
                "description": (
                    "The robbery or extortion obstructed, delayed, or affected "
                    "commerce or the movement of any article or commodity in "
                    "interstate or foreign commerce."
                ),
            },
            {
                "display_name": "Use of Force or Threat",
                "description": (
                    "The defendant used actual or threatened force, violence, or "
                    "fear to accomplish the robbery or extortion."
                ),
            },
            {
                "display_name": "Obtaining Property",
                "description": (
                    "The defendant obtained or attempted to obtain property from "
                    "another person, including tangible and intangible property "
                    "rights."
                ),
            },
        ],
    },
    {
        "citation": "18 U.S.C. § 846",
        "title": "Drug Conspiracy",
        "description": (
            "Criminalizes conspiracy to manufacture, distribute, or dispense "
            "controlled substances, or to possess with intent to do so. Penalties "
            "mirror the underlying substantive drug offense."
        ),
        "elements": [
            {
                "display_name": "Agreement to Violate Drug Laws",
                "description": (
                    "Two or more persons reached an agreement or understanding to "
                    "violate federal controlled substance laws, including "
                    "manufacturing, distributing, dispensing, or possessing with "
                    "intent to distribute a controlled substance."
                ),
            },
            {
                "display_name": "Knowledge of Conspiracy",
                "description": (
                    "The defendant knew of the existence of the conspiracy and its "
                    "objective to violate federal drug laws."
                ),
            },
            {
                "display_name": "Voluntary Participation",
                "description": (
                    "The defendant voluntarily and intentionally joined the "
                    "conspiracy, agreeing to participate in the unlawful plan."
                ),
            },
            {
                "display_name": "Overt Act",
                "description": (
                    "At least one member of the conspiracy committed an overt act "
                    "in furtherance of the conspiracy's objective."
                ),
            },
        ],
    },
]


# ---------------------------------------------------------------------------
# SQL templates — ON CONFLICT DO NOTHING for idempotency
# ---------------------------------------------------------------------------

INSERT_STATUTE_SQL = """
INSERT INTO statutes (statute_id, citation, title, description)
VALUES (%s, %s, %s, %s)
ON CONFLICT (citation) DO NOTHING;
"""

INSERT_ELEMENT_SQL = """
INSERT INTO statutory_elements (element_id, statute_id, display_name, description, element_order)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (statute_id, element_order) DO NOTHING;
"""


def _generate_deterministic_uuid(namespace: str, name: str) -> str:
    """Generate a deterministic UUID5 so re-runs produce the same IDs."""
    ns = uuid.uuid5(uuid.NAMESPACE_URL, namespace)
    return str(uuid.uuid5(ns, name))


def build_seed_params() -> tuple[list[tuple], list[tuple]]:
    """Build parameter tuples for statute and element inserts.

    Returns (statute_params, element_params) ready for executemany.
    """
    statute_params: list[tuple] = []
    element_params: list[tuple] = []

    for statute in STATUTES:
        statute_id = _generate_deterministic_uuid(
            "prosecutor-statutes", statute["citation"]
        )
        statute_params.append(
            (statute_id, statute["citation"], statute["title"], statute["description"])
        )
        for order, element in enumerate(statute["elements"], start=1):
            element_id = _generate_deterministic_uuid(
                f"statute-elements:{statute['citation']}", element["display_name"]
            )
            element_params.append(
                (element_id, statute_id, element["display_name"], element["description"], order)
            )

    return statute_params, element_params


# ---------------------------------------------------------------------------
# Execution modes
# ---------------------------------------------------------------------------

def seed_via_connection_manager():
    """Insert seed data using the project's ConnectionManager (psycopg2 pool)."""
    # Add project root to path so we can import src.db.connection
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from src.db.connection import ConnectionManager

    cm = ConnectionManager()
    statute_params, element_params = build_seed_params()

    with cm.cursor() as cur:
        for params in statute_params:
            cur.execute(INSERT_STATUTE_SQL, params)
        for params in element_params:
            cur.execute(INSERT_ELEMENT_SQL, params)

    cm.close()
    print(f"Seeded {len(statute_params)} statutes and {len(element_params)} elements via ConnectionManager.")


def seed_via_data_api():
    """Insert seed data using the RDS Data API (for local dev without VPC access)."""
    import boto3

    region = os.environ.get("AWS_REGION", "us-east-1")
    rds_data = boto3.client("rds-data", region_name=region)
    sm = boto3.client("secretsmanager", region_name=region)

    # Resolve cluster ARN and secret ARN
    cluster_id = os.environ.get("AURORA_CLUSTER_ID", "")
    if not cluster_id:
        rds = boto3.client("rds", region_name=region)
        clusters = rds.describe_db_clusters()["DBClusters"]
        for c in clusters:
            if "researchanalyst" in c["DBClusterIdentifier"].lower():
                cluster_id = c["DBClusterIdentifier"]
                break
        if not cluster_id:
            raise RuntimeError("Could not find Aurora cluster. Set AURORA_CLUSTER_ID.")

    rds_client = boto3.client("rds", region_name=region)
    cluster_info = rds_client.describe_db_clusters(DBClusterIdentifier=cluster_id)["DBClusters"][0]
    cluster_arn = cluster_info["DBClusterArn"]

    secrets = sm.list_secrets(Filters=[{"Key": "name", "Values": ["AuroraClusterSecret"]}])
    if not secrets["SecretList"]:
        raise RuntimeError("Could not find AuroraClusterSecret in Secrets Manager.")
    secret_arn = secrets["SecretList"][0]["ARN"]

    db_name = os.environ.get("AURORA_DB_NAME", "research_analyst")

    statute_params, element_params = build_seed_params()
    total = 0

    for params in statute_params:
        sql = (
            f"INSERT INTO statutes (statute_id, citation, title, description) "
            f"VALUES ('{params[0]}', '{params[1]}', $1, $2) "
            f"ON CONFLICT (citation) DO NOTHING;"
        )
        rds_data.execute_statement(
            resourceArn=cluster_arn,
            secretArn=secret_arn,
            database=db_name,
            sql=sql,
            parameters=[
                {"name": "p1", "value": {"stringValue": params[2]}},
                {"name": "p2", "value": {"stringValue": params[3]}},
            ],
        )
        total += 1

    for params in element_params:
        sql = (
            f"INSERT INTO statutory_elements (element_id, statute_id, display_name, description, element_order) "
            f"VALUES ('{params[0]}', '{params[1]}', $1, $2, {params[4]}) "
            f"ON CONFLICT (statute_id, element_order) DO NOTHING;"
        )
        rds_data.execute_statement(
            resourceArn=cluster_arn,
            secretArn=secret_arn,
            database=db_name,
            sql=sql,
            parameters=[
                {"name": "p1", "value": {"stringValue": params[2]}},
                {"name": "p2", "value": {"stringValue": params[3]}},
            ],
        )
        total += 1

    print(f"Seeded {len(statute_params)} statutes and {len(element_params)} elements via Data API ({total} statements).")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    mode = os.environ.get("SEED_MODE", "connection_manager").lower()
    print(f"Seeding statutes (mode={mode})...")

    if mode == "data_api":
        seed_via_data_api()
    else:
        seed_via_connection_manager()

    print("Done.")


if __name__ == "__main__":
    main()
