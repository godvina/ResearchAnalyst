"""Scrape Ancient Aliens episode transcripts from subslikescript.com.

Saves each episode as a separate text file in data/transcripts/.
"""

import os
import re
import time

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://subslikescript.com"
SERIES_URL = f"{BASE_URL}/series/Ancient_Aliens-1643266"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "transcripts")
DELAY = 2  # seconds between requests to be polite


def get_episode_links() -> list[dict]:
    """Fetch all episode links from the series page."""
    resp = requests.get(SERIES_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    episodes = []
    current_season = ""

    for el in soup.select(".main-article a, .main-article .season-title, h2"):
        # Detect season headers
        text = el.get_text(strip=True)
        if "Season" in text and el.name in ("h2", "div", "span"):
            current_season = text.replace(" ", "")

        # Detect episode links
        href = el.get("href", "")
        if "/series/Ancient_Aliens" in href and "/episode-" in href:
            title = el.get_text(strip=True)
            if not current_season:
                # Try to extract season from URL
                m = re.search(r"season-(\d+)", href)
                if m:
                    current_season = f"Season{m.group(1)}"
            episodes.append({
                "title": title,
                "url": href if href.startswith("http") else f"{BASE_URL}{href}",
                "season": current_season,
            })

    return episodes


def scrape_transcript(url: str) -> str:
    """Scrape the transcript text from an episode page."""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # The transcript is in the .full-script div
    script_div = soup.select_one(".full-script")
    if script_div:
        return script_div.get_text(separator="\n", strip=True)

    # Fallback: try main-article
    article = soup.select_one(".main-article")
    if article:
        return article.get_text(separator="\n", strip=True)

    return ""


def sanitize_filename(name: str) -> str:
    """Make a string safe for use as a filename."""
    return re.sub(r'[^\w\s\-]', '', name).strip().replace(' ', '_')[:80]


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Fetching episode list...")
    episodes = get_episode_links()
    print(f"Found {len(episodes)} episodes")

    if not episodes:
        # Fallback: manually construct URLs for key episodes
        print("No episodes found via scraping, using manual list...")
        episodes = get_manual_episode_list()

    scraped = 0
    for i, ep in enumerate(episodes):
        title = ep.get("title", f"episode_{i}")
        season = ep.get("season", "Unknown")
        filename = f"{sanitize_filename(season)}_{sanitize_filename(title)}.txt"
        filepath = os.path.join(OUTPUT_DIR, filename)

        if os.path.exists(filepath):
            print(f"  Skipping (exists): {filename}")
            continue

        print(f"  [{i+1}/{len(episodes)}] Scraping: {season} - {title}")
        try:
            transcript = scrape_transcript(ep["url"])
            if transcript and len(transcript) > 500:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(f"# {season} - {title}\n\n{transcript}")
                scraped += 1
                print(f"    Saved: {filename} ({len(transcript)} chars)")
            else:
                print(f"    Skipped: too short ({len(transcript)} chars)")
        except Exception as exc:
            print(f"    Error: {exc}")

        time.sleep(DELAY)

    print(f"\nDone. Scraped {scraped} new transcripts to {OUTPUT_DIR}")


def get_manual_episode_list() -> list[dict]:
    """Manual list of key episodes including crop circle related ones."""
    base = f"{BASE_URL}/series/Ancient_Aliens-1643266"
    return [
        {"title": "Mysterious Places", "url": f"{base}/season-2/episode-1-Mysterious_Places", "season": "Season2"},
        {"title": "Gods and Aliens", "url": f"{base}/season-2/episode-2-Gods_and_Aliens", "season": "Season2"},
        {"title": "Underwater Worlds", "url": f"{base}/season-2/episode-3-Underwater_Worlds", "season": "Season2"},
        {"title": "Underground Aliens", "url": f"{base}/season-2/episode-4-Underground_Aliens", "season": "Season2"},
        {"title": "Aliens and the Third Reich", "url": f"{base}/season-2/episode-5-Aliens_and_the_Third_Reich", "season": "Season2"},
        {"title": "Alien Tech", "url": f"{base}/season-2/episode-6-Alien_Tech", "season": "Season2"},
        {"title": "Angels and Aliens", "url": f"{base}/season-2/episode-7-Angels_and_Aliens", "season": "Season2"},
        {"title": "Unexplained Structures", "url": f"{base}/season-2/episode-8-Unexplained_Structures", "season": "Season2"},
        {"title": "Alien Devastations", "url": f"{base}/season-2/episode-9-Alien_Devastations", "season": "Season2"},
        {"title": "Alien Contacts", "url": f"{base}/season-2/episode-10-Alien_Contacts", "season": "Season2"},
        {"title": "Aliens and the Old West", "url": f"{base}/season-3/episode-1-Aliens_and_the_Old_West", "season": "Season3"},
        {"title": "Aliens and Monsters", "url": f"{base}/season-3/episode-2-Aliens_and_Monsters", "season": "Season3"},
        {"title": "Aliens and Sacred Places", "url": f"{base}/season-3/episode-3-Aliens_and_Sacred_Places", "season": "Season3"},
        {"title": "Aliens and Temples of Gold", "url": f"{base}/season-3/episode-4-Aliens_and_Temples_of_Gold", "season": "Season3"},
        {"title": "Aliens and Mysterious Rituals", "url": f"{base}/season-3/episode-5-Aliens_and_Mysterious_Rituals", "season": "Season3"},
        {"title": "The Power of Three", "url": f"{base}/season-4/episode-1-The_Power_of_Three", "season": "Season4"},
        {"title": "The Crystal Skulls", "url": f"{base}/season-4/episode-2-The_Crystal_Skulls", "season": "Season4"},
        {"title": "The NASA Connection", "url": f"{base}/season-4/episode-5-The_NASA_Connection", "season": "Season4"},
        {"title": "Aliens and Mega-Disasters", "url": f"{base}/season-4/episode-8-Aliens_and_Mega-Disasters", "season": "Season4"},
        {"title": "The Von Daniken Legacy", "url": f"{base}/season-4/episode-10-The_Von_Daniken_Legacy", "season": "Season4"},
    ]
