"""Scrape ALL Ancient Aliens episode transcripts from subslikescript.com.

Dynamically discovers every episode link from the series page,
fetches transcripts, and saves them to data/transcripts/.
Skips duplicates, existing files, and handles errors gracefully.
"""

import os
import re
import time

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://subslikescript.com"
SERIES_URL = f"{BASE_URL}/series/Ancient_Aliens-1643266"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "transcripts")
DELAY = 1.5  # seconds between requests
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}


def fetch(url: str, retries: int = 1) -> requests.Response | None:
    """Fetch a URL with optional retry on failure."""
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            if attempt < retries:
                print(f"    Retry after error: {e}")
                time.sleep(DELAY)
            else:
                print(f"    Failed after {retries + 1} attempts: {e}")
                return None


def discover_episode_links() -> list[dict]:
    """Fetch the series page and extract all episode links."""
    print(f"Fetching series page: {SERIES_URL}")
    resp = fetch(SERIES_URL)
    if not resp:
        print("ERROR: Could not fetch series page.")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    episodes = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/episode-" not in href:
            continue

        # Build full URL
        url = href if href.startswith("http") else f"{BASE_URL}{href}"

        # Extract season number from URL
        season_match = re.search(r"/season-(\d+)/", url)
        if not season_match:
            continue
        season_num = int(season_match.group(1))

        # Extract title from link text
        title = a.get_text(strip=True)
        if not title:
            # Fallback: derive from URL
            title_match = re.search(r"/episode-\d+-(.+)$", url)
            title = title_match.group(1).replace("_", " ") if title_match else "Unknown"

        episodes.append({
            "season": season_num,
            "title": title,
            "url": url,
        })

    # Deduplicate by URL
    seen = set()
    unique = []
    for ep in episodes:
        if ep["url"] not in seen:
            seen.add(ep["url"])
            unique.append(ep)

    # Sort by season, then by episode order in URL
    def sort_key(ep):
        m = re.search(r"/episode-(\d+)", ep["url"])
        ep_num = int(m.group(1)) if m else 0
        return (ep["season"], ep_num)

    unique.sort(key=sort_key)
    return unique


def sanitize_title(title: str) -> str:
    """Convert a title to a safe filename component."""
    # Remove leading episode numbers like "1. " or "01 - "
    title = re.sub(r"^\d+[\.\-\s]+", "", title).strip()
    # Replace non-alphanumeric (except spaces/hyphens) with nothing
    title = re.sub(r"[^\w\s\-]", "", title)
    # Collapse whitespace to single underscore
    title = re.sub(r"\s+", "_", title).strip("_")
    return title[:80]


def make_filename(season: int, title: str) -> str:
    """Build the output filename: S{season:02d}_{sanitized_title}.txt"""
    return f"S{season:02d}_{sanitize_title(title)}.txt"


def scrape_transcript(url: str) -> str | None:
    """Fetch an episode page and extract the transcript text."""
    resp = fetch(url, retries=1)
    if not resp:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    script_div = soup.select_one(".full-script")
    if not script_div:
        return None

    text = script_div.get_text(separator="\n", strip=True)
    return text if len(text) > 100 else None


def existing_files() -> set[str]:
    """Return set of filenames already in the output directory."""
    if not os.path.isdir(OUTPUT_DIR):
        return set()
    return set(os.listdir(OUTPUT_DIR))


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    already = existing_files()
    print(f"Existing transcripts: {len(already)}")

    episodes = discover_episode_links()
    print(f"Discovered {len(episodes)} episode links\n")

    if not episodes:
        print("No episodes found. Check if the site structure has changed.")
        return

    scraped = 0
    skipped_exists = 0
    skipped_dupe = 0
    skipped_no_transcript = 0
    errors = 0

    for i, ep in enumerate(episodes, 1):
        title = ep["title"]
        season = ep["season"]
        url = ep["url"]

        # Skip episodes marked as duplicates
        if "#DUPE#" in title:
            print(f"  [{i}/{len(episodes)}] SKIP (dupe): {title}")
            skipped_dupe += 1
            continue

        filename = make_filename(season, title)

        # Skip if file already exists
        if filename in already:
            print(f"  [{i}/{len(episodes)}] EXISTS: {filename}")
            skipped_exists += 1
            continue

        print(f"  [{i}/{len(episodes)}] S{season:02d} - {title} ... ", end="", flush=True)

        transcript = scrape_transcript(url)
        if transcript is None:
            print("WARNING: no transcript found, skipping")
            skipped_no_transcript += 1
        else:
            filepath = os.path.join(OUTPUT_DIR, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# S{season:02d} - {title}\n\n{transcript}")
            already.add(filename)
            scraped += 1
            print(f"OK ({len(transcript):,} chars)")

        time.sleep(DELAY)

    print(f"\n{'='*50}")
    print(f"Done!")
    print(f"  New transcripts scraped: {scraped}")
    print(f"  Already existed:         {skipped_exists}")
    print(f"  Skipped (dupe):          {skipped_dupe}")
    print(f"  Skipped (no transcript): {skipped_no_transcript}")
    print(f"  Total files now:         {len(os.listdir(OUTPUT_DIR))}")


if __name__ == "__main__":
    main()
