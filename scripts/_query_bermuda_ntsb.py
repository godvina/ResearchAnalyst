"""Query the NTSB avall.mdb for Bermuda Triangle aviation accidents."""
import pyodbc
import os
import json

mdb = os.path.abspath('src/data/conspiracy-seed/bermuda_triangle/avall.mdb')
conn = pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={mdb};')
cursor = conn.cursor()

query = '''
SELECT ev_id, ntsb_no, ev_type, ev_date, ev_city, ev_state, ev_country,
       dec_latitude, dec_longitude, ev_highest_injury, inj_tot_f, inj_tot_s,
       ev_year, ev_month, light_cond, wx_cond_basic
FROM events
WHERE dec_latitude BETWEEN 18.0 AND 33.0
AND dec_longitude BETWEEN -80.0 AND -64.0
'''

print('Querying Bermuda Triangle region (lat 18-33, lon -80 to -64)...')
cursor.execute(query)
rows = cursor.fetchall()
cols = [desc[0] for desc in cursor.description]
print(f'Found: {len(rows)} accidents in Bermuda Triangle region')

# Convert to dicts
results = []
for row in rows:
    record = {}
    for i, col in enumerate(cols):
        val = row[i]
        if val is not None:
            record[col] = str(val) if not isinstance(val, (int, float, bool)) else val
    results.append(record)

# Save
output = {
    'source': 'NTSB Aviation Accident Database (avall.mdb)',
    'region': 'Bermuda Triangle (lat 18-33N, lon 64-80W)',
    'total_records': len(results),
    'accidents': results
}

out_path = 'src/data/conspiracy-seed/bermuda_triangle/ntsb_bermuda_accidents.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, indent=2, ensure_ascii=False, default=str)

size_kb = os.path.getsize(out_path) / 1024
print(f'Saved: {out_path} ({size_kb:.0f} KB, {len(results)} records)')

# Stats
if results:
    print(f'\nSample record:')
    print(json.dumps(results[0], indent=2, default=str)[:400])
    
    fatals = sum(1 for r in results if r.get('inj_tot_f') and int(float(r.get('inj_tot_f', 0))) > 0)
    years = [int(float(r['ev_year'])) for r in results if r.get('ev_year')]
    print(f'\nWith fatalities: {fatals}')
    if years:
        print(f'Date range: {min(years)} - {max(years)}')

conn.close()
print('\nDone!')
