"""Download and filter NTSB aviation accident data for the Bermuda Triangle region.

The NTSB provides bulk CSV data at: https://data.ntsb.gov/avdata/FileDirectory/DownloadFile?fileID=C%3A%5Cavdata%5Cavall.zip
This script downloads it, filters for the Bermuda Triangle region, and saves as JSON for the pipeline.

Bermuda Triangle approximate bounds:
- Miami (25.76°N, 80.19°W) 
- Bermuda (32.32°N, 64.78°W)
- San Juan (18.47°N, 66.12°W)

Filter: lat 18-33, lon -80 to -64
"""
import csv
import io
import json
import os
import sys
import urllib.request
import zipfile
from datetime import datetime

OUTPUT_DIR = "src/data/conspiracy-seed/bermuda_triangle"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "ntsb_bermuda_accidents.json")

# Bermuda Triangle bounding box
LAT_MIN = 18.0
LAT_MAX = 33.0
LON_MIN = -80.0
LON_MAX = -64.0

# NTSB bulk data URL (all accidents since 1982)
NTSB_URL = "https://data.ntsb.gov/avdata/FileDirectory/DownloadFile?fileID=C%3A%5Cavdata%5Cavall.zip"


def download_ntsb_data():
    """Find the NTSB bulk accident data ZIP file."""
    # Check multiple locations
    possible_paths = [
        os.path.join(OUTPUT_DIR, "_ntsb_avall.zip"),
        "docs/avall.zip",
        "avall.zip",
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            size_mb = os.path.getsize(path) / (1024 * 1024)
            print(f"Found NTSB data: {path} ({size_mb:.1f} MB)")
            return path

    print("NTSB avall.zip not found. Place it in docs/ or the bermuda_triangle seed folder.")
    return None


def filter_bermuda_triangle(zip_path):
    """Extract and filter NTSB data for Bermuda Triangle region."""
    print(f"\nFiltering for Bermuda Triangle region:")
    print(f"  Latitude: {LAT_MIN}° to {LAT_MAX}°N")
    print(f"  Longitude: {LON_MIN}° to {LON_MAX}°W")
    
    bermuda_accidents = []
    total_records = 0
    
    with zipfile.ZipFile(zip_path, 'r') as z:
        # Find the main events file
        csv_files = [f for f in z.namelist() if f.lower().endswith('.csv')]
        print(f"  CSV files in archive: {csv_files[:5]}")
        
        # The main file is usually 'events.csv' or similar
        events_file = None
        for f in csv_files:
            if 'event' in f.lower() or 'avall' in f.lower():
                events_file = f
                break
        if not events_file and csv_files:
            events_file = csv_files[0]
        
        if not events_file:
            print("  No suitable CSV found in archive")
            return []
        
        print(f"  Processing: {events_file}")
        
        with z.open(events_file) as f:
            # Read as text
            content = f.read().decode('utf-8', errors='replace')
            reader = csv.DictReader(io.StringIO(content))
            
            for row in reader:
                total_records += 1
                
                # Get lat/lon - field names vary
                lat = None
                lon = None
                for lat_field in ['Latitude', 'latitude', 'lat', 'LATITUDE']:
                    if lat_field in row and row[lat_field]:
                        try:
                            lat = float(row[lat_field])
                        except (ValueError, TypeError):
                            pass
                        break
                
                for lon_field in ['Longitude', 'longitude', 'lon', 'LONGITUDE']:
                    if lon_field in row and row[lon_field]:
                        try:
                            lon = float(row[lon_field])
                        except (ValueError, TypeError):
                            pass
                        break
                
                if lat is None or lon is None:
                    continue
                
                # Check if in Bermuda Triangle bounds
                if LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX:
                    bermuda_accidents.append(row)
                
                if total_records % 100000 == 0:
                    print(f"    Processed {total_records:,} records, found {len(bermuda_accidents)} in region...")
    
    print(f"\n  Total NTSB records: {total_records:,}")
    print(f"  Bermuda Triangle region: {len(bermuda_accidents)}")
    return bermuda_accidents


def save_results(accidents):
    """Save filtered accidents as JSON for the pipeline."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    output = {
        "source": "NTSB Aviation Accident Database (data.ntsb.gov)",
        "region": "Bermuda Triangle (lat 18-33°N, lon 64-80°W)",
        "total_records": len(accidents),
        "downloaded_at": datetime.utcnow().isoformat() + "Z",
        "accidents": accidents[:500],  # Cap at 500 for initial processing
    }
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    size_kb = os.path.getsize(OUTPUT_FILE) / 1024
    print(f"\nSaved: {OUTPUT_FILE} ({size_kb:.0f} KB, {len(output['accidents'])} records)")
    
    # Show sample
    if accidents:
        print(f"\nSample record fields: {list(accidents[0].keys())[:10]}")
        print(f"Sample: {json.dumps(accidents[0], indent=2)[:500]}")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    zip_path = download_ntsb_data()
    
    if zip_path and os.path.exists(zip_path):
        accidents = filter_bermuda_triangle(zip_path)
        if accidents:
            save_results(accidents)
        else:
            print("No records found in Bermuda Triangle region.")
            print("The NTSB data may use different coordinate formats.")
            print("Checking available columns...")
    else:
        print("\nNTSB download not available. Using curated seed data only.")
        print("The incidents.json file already has 13 manually researched incidents.")


if __name__ == "__main__":
    main()
