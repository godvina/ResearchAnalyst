import sys; sys.path.insert(0, "src")
from services.geocoding_service import GeocodingService
g = GeocodingService()
print(f"Curated locations: {len(g.CURATED_LOCATIONS)}")
r = g.geocode(["New York", "Palm Beach", "Virgin Islands", "Little St. James Island", "Unknown Place XYZ", "palm beach, FL", "MANHATTAN"])
print(f"Resolved: {r['resolved']}/{r['total']}")
print(f"Unresolved: {r['unresolved']}")
for name, coords in r["geocoded"].items():
    print(f"  {name}: ({coords['lat']}, {coords['lng']})")
