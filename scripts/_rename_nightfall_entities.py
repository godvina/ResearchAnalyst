"""Rename all real person entities in Operation Nightfall to fictional names."""
import boto3

CASE_ID = "0b24a307-a674-41b6-8d22-581c4a4aa566"
DB_ARN = "arn:aws:rds:us-east-1:974220725866:cluster:researchanalyststack-auroracluster23d869c0-18up0bpmkaco"
SECRET_ARN = "arn:aws:secretsmanager:us-east-1:974220725866:secret:AuroraClusterSecret8E4F2BC8-4zmQsxQuyYQJ-TOjJyL"

rds = boto3.client("rds-data", region_name="us-east-1")

# Map all real names to fictional replacements
RENAME_MAP = {
    # Already done by clone script (keeping for completeness)
    # "Jeffrey Epstein": "Marcus Blackwell",
    # "Ghislaine Maxwell": "Catherine Sterling",
    
    # Pilot / staff
    "Larry Visoski": "Daniel Whitmore",
    "Dave Rodgers": "Keith Patterson",
    
    # Known associates / real public figures
    "Leon Black": "Victor Nash",
    "Ronald Lauder": "Philip Grant",
    "Peggy Siegal": "Sandra Voss",
    "Les Wexner": "Richard Caldwell",
    "Rich Kahn": "Thomas Vance",
    "Richard Kahn": "Thomas Vance",
    "Eric Roth": "Jonathan Mercer",
    "Jeff Hawkins": "Brian Delaney",
    "Cecile de Jongh": "Renee Fontaine",
    
    # Abbreviations / partials that reference real names
    "JE": "MB",
    "Jefffrey Blackwell": "Marcus Blackwell",
    "Marcus E.": "M. Blackwell",
    "Marcus E. Blackwell": "Marcus Blackwell",
    "Ehud": "Ambassador Rosen",
    
    # Victims / witnesses (real people who testified)
    "Natalia Molotkova": "Elena Vasquez",
    "Natasha Molotkova": "Elena Vasquez",
    "Bella Klein": "Sophia Reyes",
    "Bebe Avdiu": "Nadia Kovar",
    "Bebe": "Nadia",
    "Merwin Dela cruz": "Carlos Rivera",
    "Merwin Dela Cruz": "Carlos Rivera",
    "Merwin": "Carlos",
    "Jojo Fontanilla": "Marco Delgado",
    "Jojo": "Marco",
    "Karyna Shuliak": "Anya Petrov",
    "Karyna": "Anya",
    "Melanie Spinella": "Rachel Dumont",
    "Daphne Wallace": "Claire Ashford",
    "Daphne": "Claire",
    "Laura Bard": "Megan Fischer",
    "Erica D. Peterson": "Samantha Rhodes",
    "Leo Loking": "Viktor Soren",
    "Leo": "Viktor",
    "Leon": "Victor",
    "Nili": "Miriam",
    "Tess": "Simone",
    "Joanne": "Elaine",
    "Karen": "Denise",
    "Cecilia": "Isabelle",
    "Marilyn": "Evelyn",
    "Darren": "Trevor",
    "Dr. Chen": "Dr. Park",
}

def run():
    success = 0
    skipped = 0
    errors = 0
    
    for old_name, new_name in RENAME_MAP.items():
        try:
            r = rds.execute_statement(
                resourceArn=DB_ARN,
                secretArn=SECRET_ARN,
                database="research_analyst",
                sql=f"UPDATE entities SET canonical_name='{new_name}' WHERE case_file_id='{CASE_ID}' AND canonical_name='{old_name}'",
            )
            count = r.get("numberOfRecordsUpdated", 0)
            if count > 0:
                print(f"  ✓ {old_name} → {new_name} ({count} rows)")
                success += count
            else:
                skipped += 1
        except Exception as e:
            if "duplicate key" in str(e).lower():
                # Entity with new name already exists — delete the old one instead
                try:
                    rds.execute_statement(
                        resourceArn=DB_ARN,
                        secretArn=SECRET_ARN,
                        database="research_analyst",
                        sql=f"DELETE FROM entities WHERE case_file_id='{CASE_ID}' AND canonical_name='{old_name}'",
                    )
                    print(f"  ✓ {old_name} → DELETED (duplicate of {new_name})")
                    success += 1
                except Exception as e2:
                    print(f"  ✗ {old_name}: delete also failed: {e2}")
                    errors += 1
            else:
                print(f"  ✗ {old_name}: {str(e)[:100]}")
                errors += 1
    
    print(f"\nDone! Renamed: {success}, Skipped (not found): {skipped}, Errors: {errors}")
    
    # Also clear the command center cache so briefing regenerates
    try:
        rds.execute_statement(
            resourceArn=DB_ARN,
            secretArn=SECRET_ARN,
            database="research_analyst",
            sql=f"DELETE FROM command_center_cache WHERE case_file_id='{CASE_ID}'",
        )
        print("  Cleared command center cache — briefing will regenerate fresh.")
    except Exception:
        pass


if __name__ == "__main__":
    print(f"Renaming entities for Operation Nightfall ({CASE_ID[:12]}...)")
    print(f"  {len(RENAME_MAP)} substitutions to apply\n")
    run()
