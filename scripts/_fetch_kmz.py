"""Try to fetch the UVG KMZ file from Wayback Machine."""
import urllib.request
import re

# Get the vortexmaps page from Wayback
url = "https://web.archive.org/web/2019/http://www.vortexmaps.com/hagens-grid-google.php"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
resp = urllib.request.urlopen(req, timeout=15)
html = resp.read().decode("utf-8", errors="replace")

# Find KMZ/KML links
links = re.findall(r'href=["\']([^"\']*\.km[zl][^"\']*)["\']', html, re.IGNORECASE)
print(f"KMZ/KML links found: {len(links)}")
for l in links:
    print(f"  {l}")

# Find any link with 'UVG' or 'grid' 
grid_links = re.findall(r'href=["\']([^"\']*(?:UVG|grid|Grid)[^"\']*)["\']', html, re.IGNORECASE)
print(f"\nGrid-related links: {len(grid_links)}")
for l in grid_links:
    print(f"  {l}")

# Try to download each KMZ link via Wayback
for link in links:
    if not link.startswith("http"):
        link = "https://web.archive.org" + link if link.startswith("/") else f"https://web.archive.org/web/2019/http://www.vortexmaps.com/{link}"
    
    print(f"\nTrying: {link[:100]}")
    try:
        req2 = urllib.request.Request(link, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        resp2 = urllib.request.urlopen(req2, timeout=15)
        data = resp2.read()
        print(f"  Got {len(data)} bytes")
        if len(data) > 500:
            # Check if it's a ZIP (KMZ)
            if data[:2] == b"PK":
                with open(r"src\data\UVG-grid-compiled-by-B-Hagens.kmz", "wb") as f:
                    f.write(data)
                print("  *** KMZ FILE SAVED! ***")
                break
            else:
                print(f"  Not a ZIP. First bytes: {data[:20]}")
    except Exception as e:
        print(f"  Failed: {e}")
