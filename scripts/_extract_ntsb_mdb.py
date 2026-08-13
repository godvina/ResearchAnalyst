"""Extract and filter NTSB avall.mdb (MS Access) for Bermuda Triangle region.

The NTSB provides data as a Microsoft Access .mdb file.
We use pyodbc or mdbtools to read it and filter for the Bermuda Triangle region.
"""
import json
import os
import sys
import zipfile

OUTPUT_DIR = "src/data/conspiracy-seed/bermuda_triangle"
MDB_PATH = os.path.join(OUTPUT_DIR, "avall.mdb")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "ntsb_bermuda_accidents.json")

# Bermuda Triangle bounding box
LAT_MIN = 18.0
LAT_MAX = 33.0
LON_MIN = -80.0
LON_MAX = -64.0


def extract_mdb():
    """Extract avall.mdb from the ZIP if needed."""
    if os.path.exists(MDB_PATH):
        size_mb = os.path.getsize(MDB_PATH) / (1024 * 1024)
        print(f"MDB already extracted: {MDB_PATH} ({size_mb:.1f} MB)")
        return True

    zip_path = "docs/avall.zip"
    if not os.path.exists(zip_path):
        print("docs/avall.zip not found!")
        return False

    print("Extracting avall.mdb from ZIP...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extract('avall.mdb', OUTPUT_DIR)
    
    size_mb = os.path.getsize(MDB_PATH) / (1024 * 1024)
    print(f"Extracted: {size_mb:.1f} MB")
    return True


def read_with_pyodbc():
    """Read MDB using pyodbc with MS Access ODBC driver."""
    import pyodbc

    # Try both 32-bit and 64-bit Access drivers
    drivers = [d for d in pyodbc.drivers() if 'access' in d.lower() or 'mdb' in d.lower()]
    print(f"Available Access drivers: {drivers}")

    if not drivers:
        print("No MS Access ODBC driver found.")
        print("Install: https://www.microsoft.com/en-us/download/details.aspx?id=54920")
        return None

    driver = drivers[0]
    abs_path = os.path.abspath(MDB_PATH)
    conn_str = f"DRIVER={{{driver}}};DBQ={abs_path};"
    
    print(f"Connecting with driver: {driver}")
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    # List tables
    tables = [row.table_name for row in cursor.tables(tableType='TABLE')]
    print(f"Tables: {tables[:10]}")

    # Find the events table
    events_table = None
    for t in tables:
        if 'event' in t.lower():
            events_table = t
            break
    if not events_table:
        events_table = tables[0]
    
    print(f"Using table: {events_table}")

    # Get columns
    columns = [col.column_name for col in cursor.columns(table=events_table)]
    print(f"Columns ({len(columns)}): {columns[:15]}")

    # Find lat/lon columns
    lat_col = None
    lon_col = None
    for col in columns:
        cl = col.lower()
        if 'lat' in cl and lat_col is None:
            lat_col = col
        if 'lon' in cl and lon_col is None:
            lon_col = col

    if not lat_col or not lon_col:
        print(f"Could not find lat/lon columns in: {columns}")
        print("Looking for coordinate-like columns...")
        for col in columns:
            print(f"  {col}")
        conn.close()
        return None

    print(f"Lat column: {lat_col}, Lon column: {lon_col}")

    # Query for Bermuda Triangle region
    query = f"""
        SELECT * FROM [{events_table}]
        WHERE [{lat_col}] BETWEEN {LAT_MIN} AND {LAT_MAX}
        AND [{lon_col}] BETWEEN {LON_MIN} AND {LON_MAX}
    """
    print(f"Querying Bermuda Triangle region...")
    cursor.execute(query)

    rows = cursor.fetchall()
    print(f"Found {len(rows)} records in Bermuda Triangle region")

    # Convert to list of dicts
    results = []
    for row in rows:
        record = {}
        for i, col in enumerate(columns):
            val = row[i]
            if val is not None:
                record[col] = str(val) if not isinstance(val, (int, float, bool)) else val
        results.append(record)

    conn.close()
    return results


def main():
    if not extract_mdb():
        return

    print(f"\nAttempting to read MDB file...")
    
    try:
        results = read_with_pyodbc()
    except ImportError:
        print("pyodbc not installed. Installing...")
        os.system(f"{sys.executable} -m pip install pyodbc --quiet")
        try:
            results = read_with_pyodbc()
        except Exception as e:
            print(f"pyodbc failed: {e}")
            results = None
    except Exception as e:
        print(f"Error reading MDB: {e}")
        results = None

    if results:
        # Save to JSON
        output = {
            "source": "NTSB Aviation Accident Database (avall.mdb)",
            "region": "Bermuda Triangle (lat 18-33N, lon 64-80W)",
            "total_records": len(results),
            "accidents": results[:500],
        }
        
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False, default=str)
        
        size_kb = os.path.getsize(OUTPUT_FILE) / 1024
        print(f"\nSaved: {OUTPUT_FILE} ({size_kb:.0f} KB, {min(len(results), 500)} records)")
    else:
        print("\nCould not read MDB file. Alternative: open in MS Access and export as CSV.")
        print(f"MDB location: {os.path.abspath(MDB_PATH)}")


if __name__ == "__main__":
    main()
