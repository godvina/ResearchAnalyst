"""Quick scraper for Ancient Aliens transcripts."""
import os
import re
import time
import requests
from bs4 import BeautifulSoup

BASE = "https://subslikescript.com"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "transcripts")
os.makedirs(OUT, exist_ok=True)

EPISODES = [
    ("S02", "Mysterious Places", "/series/Ancient_Aliens-1643266/season-2/episode-1-Mysterious_Places"),
    ("S02", "Gods and Aliens", "/series/Ancient_Aliens-1643266/season-2/episode-2-Gods_and_Aliens"),
    ("S02", "Underwater Worlds", "/series/Ancient_Aliens-1643266/season-2/episode-3-Underwater_Worlds"),
    ("S02", "Underground Aliens", "/series/Ancient_Aliens-1643266/season-2/episode-4-Underground_Aliens"),
    ("S02", "Aliens and the Third Reich", "/series/Ancient_Aliens-1643266/season-2/episode-5-Aliens_and_the_Third_Reich"),
    ("S02", "Alien Tech", "/series/Ancient_Aliens-1643266/season-2/episode-6-Alien_Tech"),
    ("S02", "Angels and Aliens", "/series/Ancient_Aliens-1643266/season-2/episode-7-Angels_and_Aliens"),
    ("S02", "Unexplained Structures", "/series/Ancient_Aliens-1643266/season-2/episode-8-Unexplained_Structures"),
    ("S02", "Alien Devastations", "/series/Ancient_Aliens-1643266/season-2/episode-9-Alien_Devastations"),
    ("S02", "Alien Contacts", "/series/Ancient_Aliens-1643266/season-2/episode-10-Alien_Contacts"),
    ("S03", "Aliens and the Old West", "/series/Ancient_Aliens-1643266/season-3/episode-1-Aliens_and_the_Old_West"),
    ("S03", "Aliens and Monsters", "/series/Ancient_Aliens-1643266/season-3/episode-2-Aliens_and_Monsters"),
    ("S03", "Aliens and Sacred Places", "/series/Ancient_Aliens-1643266/season-3/episode-3-Aliens_and_Sacred_Places"),
    ("S03", "Aliens and Temples of Gold", "/series/Ancient_Aliens-1643266/season-3/episode-4-Aliens_and_Temples_of_Gold"),
    ("S03", "Aliens and Mysterious Rituals", "/series/Ancient_Aliens-1643266/season-3/episode-5-Aliens_and_Mysterious_Rituals"),
    ("S04", "The Power of Three", "/series/Ancient_Aliens-1643266/season-4/episode-1-The_Power_of_Three"),
    ("S04", "The Crystal Skulls", "/series/Ancient_Aliens-1643266/season-4/episode-2-The_Crystal_Skulls"),
    ("S04", "The NASA Connection", "/series/Ancient_Aliens-1643266/season-4/episode-5-The_NASA_Connection"),
    ("S04", "The Von Daniken Legacy", "/series/Ancient_Aliens-1643266/season-4/episode-10-The_Von_Daniken_Legacy"),
    ("S04", "Aliens and Mega Disasters", "/series/Ancient_Aliens-1643266/season-4/episode-8-Aliens_and_Mega-Disasters"),
]

count = 0
for i, (season, title, path) in enumerate(EPISODES):
    safe = re.sub(r"[^\w]", "_", title)
    fn = f"{season}_{safe}.txt"
    fp = os.path.join(OUT, fn)
    if os.path.exists(fp):
        print(f"  Skip: {fn}")
        continue
    print(f"[{i+1}/{len(EPISODES)}] {season} - {title} ...", end=" ", flush=True)
    try:
        r = requests.get(f"{BASE}{path}", timeout=30)
        soup = BeautifulSoup(r.text, "html.parser")
        sd = soup.select_one(".full-script")
        if sd:
            txt = sd.get_text(separator="\n", strip=True)
            if len(txt) > 500:
                with open(fp, "w", encoding="utf-8") as f:
                    f.write(f"# {season} - {title}\n\n{txt}")
                print(f"OK ({len(txt)} chars)")
                count += 1
            else:
                print("too short")
        else:
            print("no script found")
    except Exception as e:
        print(f"error: {e}")
    time.sleep(1.5)

print(f"\nDone! Scraped {count} transcripts.")
print(f"Total files: {len(os.listdir(OUT))}")
