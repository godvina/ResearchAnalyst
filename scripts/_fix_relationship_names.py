"""Fix relationship source/target names to match renamed entities."""
import boto3

DB_ARN = "arn:aws:rds:us-east-1:974220725866:cluster:researchanalyststack-auroracluster23d869c0-18up0bpmkaco"
SECRET_ARN = "arn:aws:secretsmanager:us-east-1:974220725866:secret:AuroraClusterSecret8E4F2BC8-4zmQsxQuyYQJ-TOjJyL"
CASE_ID = "0b24a307-a674-41b6-8d22-581c4a4aa566"
rds = boto3.client("rds-data", region_name="us-east-1")

RENAME_MAP = {
    "Bella Klein": "Sophia Reyes",
    "Karyna Shuliak": "Anya Petrov",
    "Karyna": "Anya",
    "Richard Kahn": "Thomas Vance",
    "Rich Kahn": "Thomas Vance",
    "Natalia Molotkova": "Elena Vasquez",
    "Natasha Molotkova": "Elena Vasquez",
    "Bebe Avdiu": "Nadia Kovar",
    "Bebe": "Nadia",
    "Merwin Dela cruz": "Carlos Rivera",
    "Merwin Dela Cruz": "Carlos Rivera",
    "Merwin": "Carlos",
    "Jojo Fontanilla": "Marco Delgado",
    "Jojo": "Marco",
    "Melanie Spinella": "Rachel Dumont",
    "Daphne Wallace": "Claire Ashford",
    "Daphne": "Claire",
    "Laura Bard": "Megan Fischer",
    "Erica D. Peterson": "Samantha Rhodes",
    "Leo Loking": "Viktor Soren",
    "Leo": "Viktor",
    "Leon": "Victor",
    "Leon Black": "Victor Nash",
    "Ronald Lauder": "Philip Grant",
    "Peggy Siegal": "Sandra Voss",
    "Eric Roth": "Jonathan Mercer",
    "Jeff Hawkins": "Brian Delaney",
    "Cecile de Jongh": "Renee Fontaine",
    "Dr. Chen": "Dr. Park",
    "Larry Visoski": "Daniel Whitmore",
    "Dave Rodgers": "Keith Patterson",
    "JE": "MB",
    "Marcus E.": "M. Blackwell",
}

def run():
    success = 0
    for old, new in RENAME_MAP.items():
        for col in ["source_entity", "target_entity"]:
            try:
                esc_old = old.replace("'", "''")
                esc_new = new.replace("'", "''")
                r = rds.execute_statement(
                    resourceArn=DB_ARN, secretArn=SECRET_ARN, database="research_analyst",
                    sql=f"UPDATE relationships SET {col}='{esc_new}' WHERE case_file_id='{CASE_ID}' AND {col}='{esc_old}'",
                )
                cnt = r.get("numberOfRecordsUpdated", 0)
                if cnt > 0:
                    print(f"  {col}: {old} -> {new} ({cnt} rows)")
                    success += cnt
            except Exception as e:
                if "duplicate" in str(e).lower():
                    # Delete the old ones instead
                    rds.execute_statement(
                        resourceArn=DB_ARN, secretArn=SECRET_ARN, database="research_analyst",
                        sql=f"DELETE FROM relationships WHERE case_file_id='{CASE_ID}' AND {col}='{esc_old}'",
                    )
                    print(f"  {col}: {old} -> DELETED (dup)")
                    success += 1
    print(f"\nDone! {success} updates applied.")

if __name__ == "__main__":
    print("Fixing relationship names for Operation Nightfall...")
    run()
