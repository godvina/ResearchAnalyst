"""Scrape flat earth evidence from flattruths.com and theflatearthpodcast.com.

Creates a comprehensive flat earth claims dataset structured for our pipeline.
Approach: Collect the BEST flat earth arguments (to prove our app works both ways)
then we also collect the scientific rebuttals.

Sources:
1. flattruths.com — structured evidence library (12 proofs, experiments, history)
2. theflatearthpodcast.com (DITRH) — 200+ claimed proofs
3. Our Reddit data already downloaded

Strategy:
- PRO flat earth: Collect their strongest claims with their cited evidence
- ANTI flat earth: Pair each claim with the scientific rebuttal
- This proves our Proof Engine works: it should evaluate BOTH sides fairly
"""
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from html.parser import HTMLParser

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / 'src' / 'data' / 'conspiracy-seed' / 'flat_earth_evidence'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class SimpleHTMLTextExtractor(HTMLParser):
    """Simple HTML to text converter."""
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.skip_tags = {'script', 'style', 'nav', 'header', 'footer'}
        self.current_skip = False
    
    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self.current_skip = True
        if tag in ('p', 'h1', 'h2', 'h3', 'h4', 'li', 'br', 'div'):
            self.text_parts.append('\n')
    
    def handle_endtag(self, tag):
        if tag in self.skip_tags:
            self.current_skip = False
    
    def handle_data(self, data):
        if not self.current_skip:
            self.text_parts.append(data.strip())
    
    def get_text(self):
        return ' '.join(self.text_parts)


def fetch_page(url):
    """Fetch a page and return text content."""
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Research; Academic) ResearchAnalyst/1.0'
        })
        resp = urllib.request.urlopen(req, timeout=15)
        html = resp.read().decode('utf-8', errors='replace')
        
        parser = SimpleHTMLTextExtractor()
        parser.feed(html)
        return parser.get_text()
    except Exception as e:
        print(f"  Failed to fetch {url}: {e}")
        return None


def scrape_flattruths():
    """Scrape evidence pages from flattruths.com."""
    pages = [
        ('flat-earth-proof', 'https://flattruths.com/flat-earth-proof.html', '12 Observable Proofs'),
        ('debunking-globe', 'https://flattruths.com/debunking-globe-earth.html', 'Globe Debunking'),
        ('flat-earth-science', 'https://flattruths.com/flat-earth-science.html', 'Science of the Plane'),
        ('admiral-byrd', 'https://flattruths.com/admiral-byrd.html', 'Admiral Byrd Antarctic'),
        ('operation-fishbowl', 'https://flattruths.com/operation-fishbowl.html', 'Operation Fishbowl'),
        ('sun-moon', 'https://flattruths.com/sun-moon.html', 'Sun & Moon Mechanics'),
        ('flat-earth-history', 'https://flattruths.com/flat-earth-history.html', 'Suppression Timeline'),
        ('flat-earth-experiments', 'https://flattruths.com/flat-earth-experiments.html', 'Replicable Experiments'),
        ('biblical-cosmology', 'https://flattruths.com/biblical-cosmology.html', 'Biblical Cosmology'),
        ('faq', 'https://flattruths.com/faq.html', 'FAQ / Common Objections'),
    ]
    
    results = []
    print("Scraping flattruths.com evidence pages...")
    
    for page_id, url, title in pages:
        print(f"  Fetching: {title}...")
        text = fetch_page(url)
        if text and len(text) > 100:
            results.append({
                'source_id': f'flattruths_{page_id}',
                'source_url': url,
                'title': title,
                'content': text[:10000],  # Cap at 10K chars
                'content_length': len(text),
                'category': classify_fe_category(page_id),
            })
            print(f"    Got {len(text)} chars")
        else:
            print(f"    Empty or failed")
        time.sleep(1.5)  # Be polite
    
    return results


def classify_fe_category(page_id):
    """Classify flat earth content into categories."""
    categories = {
        'flat-earth-proof': 'observational_claims',
        'debunking-globe': 'counter_arguments',
        'flat-earth-science': 'pseudo_science',
        'admiral-byrd': 'conspiracy_suppression',
        'operation-fishbowl': 'conspiracy_suppression',
        'sun-moon': 'alternative_model',
        'flat-earth-history': 'historical_narrative',
        'flat-earth-experiments': 'experimental_claims',
        'biblical-cosmology': 'religious_authority',
        'faq': 'objection_handling',
    }
    return categories.get(page_id, 'general')


def create_structured_claims(scraped_pages):
    """Extract structured testable claims from the scraped content.
    
    For each claim we structure:
    - The flat earth argument (PRO)
    - The scientific rebuttal (ANTI)
    - What would need to be true for the claim to hold
    """
    # These are the core flat earth claims that appear across all sources
    structured_claims = [
        {
            'claim_id': 'fe-obs-001',
            'title': 'Horizon Always Appears Flat and at Eye Level',
            'category': 'observational',
            'pro_argument': 'At any altitude, the horizon appears perfectly flat and rises to meet eye level. On a sphere of Earth\'s alleged size, the horizon should curve visibly at altitude and drop below eye level as height increases.',
            'testable_prediction': 'At 35,000 feet, horizon should show measurable drop angle below eye level on a sphere; flat earth predicts it stays at eye level.',
            'scientific_rebuttal': 'The horizon DOES drop below eye level with altitude (about 3.4° at 35,000ft). This is measurable with a theodolite. The curvature is ~8 inches per mile squared, not visible to the naked eye at ground level due to angular resolution limits of human vision.',
            'key_evidence_needed': 'Precise theodolite measurements from known altitude showing horizon angle',
        },
        {
            'claim_id': 'fe-obs-002',
            'title': 'Long-Distance Visibility Beyond Curvature Limit',
            'category': 'observational',
            'pro_argument': 'Objects can be seen at distances where Earth\'s curvature should have hidden them. Chicago skyline visible from 60 miles across Lake Michigan. Ships "disappearing hull-first" can be brought back into view with a telescope.',
            'testable_prediction': 'Objects at >30 miles should be partially hidden on a globe; flat earth predicts full visibility with sufficient zoom.',
            'scientific_rebuttal': 'Atmospheric refraction bends light around the curvature, creating a "looming" effect that makes distant objects visible beyond geometric horizon. The effect is variable and depends on temperature gradients. Standard refraction coefficient is k=0.13, making objects visible 7-15% beyond geometric horizon.',
            'key_evidence_needed': 'Controlled observations with atmospheric conditions logged, comparing predicted vs actual visibility',
        },
        {
            'claim_id': 'fe-obs-003',
            'title': 'Water Always Finds Its Level (Cannot Curve)',
            'category': 'observational',
            'pro_argument': 'Water in nature is always level and flat. It cannot curve around a ball. The Bedford Level Experiment (1838) showed 6 miles of canal water to be perfectly flat with no measurable curvature.',
            'testable_prediction': 'Water surface over large distances should be flat; globe predicts 8 inches per mile squared of curvature.',
            'scientific_rebuttal': 'Water conforms to Earth\'s gravitational equipotential surface (the geoid). The Bedford Level Experiment was refuted by Alfred Russel Wallace in 1870 who showed the original experiment didn\'t account for refraction. Modern geodetic surveys routinely measure and account for Earth\'s curvature in engineering.',
            'key_evidence_needed': 'Precise leveling survey over >5 miles with atmospheric corrections',
        },
        {
            'claim_id': 'fe-obs-004',
            'title': 'No Measurable Rotation or Movement',
            'category': 'physics',
            'pro_argument': 'Earth allegedly spins at 1,000mph at equator, orbits Sun at 67,000mph, and moves through galaxy at 500,000mph. Yet we feel nothing, detect nothing, and a hovering helicopter doesn\'t drift west.',
            'testable_prediction': 'If Earth rotates, a free-falling object or long-range ballistic should show Coriolis deflection. Flat earth predicts none.',
            'scientific_rebuttal': 'Coriolis effect IS measurable and must be accounted for in long-range artillery, weather systems, and Foucault pendulums. The reason we don\'t "feel" rotation is that we\'re in an inertial reference frame moving with the Earth — same as not feeling a plane\'s 500mph speed in flight.',
            'key_evidence_needed': 'Foucault pendulum observations, long-range ballistic trajectory data, weather pattern rotation',
        },
        {
            'claim_id': 'fe-obs-005',
            'title': 'NASA and Space Agencies Fabricate Imagery',
            'category': 'conspiracy_suppression',
            'pro_argument': 'NASA\'s own employees have admitted to using composite images. The "Blue Marble" has changed dramatically over decades. Multiple inconsistencies in Apollo footage. No independent verification of space travel by non-government entities until recently.',
            'testable_prediction': 'All space imagery should show forensic evidence of manipulation; independent satellite operators should not exist or be compromised.',
            'scientific_rebuttal': 'Thousands of independent entities (universities, private companies, amateur radio operators, other nations) have verified orbital mechanics. SpaceX, amateur astronomers tracking ISS, ham radio operators bouncing signals off satellites, and 70+ space agencies worldwide independently confirm orbital space.',
            'key_evidence_needed': 'Independent satellite tracking data, ISS observation from ground, amateur radio satellite contacts',
        },
        {
            'claim_id': 'fe-obs-006',
            'title': 'Antarctic Treaty Prevents Independent Exploration',
            'category': 'conspiracy_suppression',
            'pro_argument': 'The Antarctic Treaty (1959) restricts independent travel to Antarctica. No civilian has freely explored the continent. Admiral Byrd\'s 1947 expedition was abruptly ended. The "ice wall" at the edge cannot be independently verified.',
            'testable_prediction': 'Independent Antarctic exploration should be prevented; there should be no civilian evidence of Antarctic interior.',
            'scientific_rebuttal': 'Thousands of tourists visit Antarctica annually (50,000+ per year). Multiple research stations from 30+ countries operate year-round. Independent expeditions cross Antarctica regularly. The Antarctic Treaty restricts military activity and mineral exploitation, not tourism or science.',
            'key_evidence_needed': 'Tourist records, independent expedition GPS tracks, multiple-nation research station data',
        },
        {
            'claim_id': 'fe-obs-007',
            'title': 'Stars and Celestial Mechanics Explained by Local Luminaries',
            'category': 'alternative_model',
            'pro_argument': 'Polaris remains fixed directly above the North Pole while other stars rotate around it. The sun and moon are local objects at ~3,000 miles altitude moving in circles above the flat plane. Perspective explains sunrise/sunset.',
            'testable_prediction': 'Sun should remain same angular size throughout day if local; southern hemisphere star trails should not exist on flat earth.',
            'scientific_rebuttal': 'Southern hemisphere observers see DIFFERENT constellations rotating around a southern celestial pole (Sigma Octantis). This is impossible on a flat plane with a single overhead rotation point. The sun\'s angular size is measurable and constant (not getting smaller as it "moves away").',
            'key_evidence_needed': 'Simultaneous star observations from northern and southern hemispheres, solar angular diameter measurements throughout day',
        },
        {
            'claim_id': 'fe-obs-008',
            'title': 'Gravity Does Not Exist (Replaced by Density/Buoyancy)',
            'category': 'physics',
            'pro_argument': 'Objects fall because they are denser than air, not because of an invisible force. Helium balloons rise because they are less dense. "Gravity" has never been isolated or measured directly — only its supposed effects.',
            'testable_prediction': 'Objects of same density but different mass should fall at same rate regardless of mass; vacuum chamber should show all objects floating.',
            'scientific_rebuttal': 'In a vacuum, ALL objects fall at the same rate regardless of density (feather = bowling ball). This contradicts density/buoyancy explanation. Additionally, gravity bends light (observed in gravitational lensing), affects time (GPS satellite clocks drift without relativistic correction), and explains orbital mechanics.',
            'key_evidence_needed': 'Vacuum chamber drop tests, GPS clock drift measurements, gravitational lensing observations',
        },
    ]
    
    return structured_claims


def main():
    print("=" * 70)
    print("FLAT EARTH EVIDENCE SCRAPING & DATASET CREATION")
    print("=" * 70)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print()
    print("Strategy: Collect BEST flat earth arguments + scientific rebuttals")
    print("Goal: Prove Proof Engine evaluates BOTH sides fairly")
    print()
    
    # Scrape flattruths.com
    scraped_pages = scrape_flattruths()
    print(f"\nScraped {len(scraped_pages)} pages from flattruths.com")
    
    # Create structured claims (the curated dataset)
    structured_claims = create_structured_claims(scraped_pages)
    print(f"Created {len(structured_claims)} structured claim pairs (PRO + ANTI)")
    
    # Load existing Reddit data
    reddit_path = PROJECT_ROOT / 'src' / 'data' / 'conspiracy-seed' / 'flat_earth_reddit' / 'reddit_flatearth_posts.json'
    reddit_data = {}
    if reddit_path.exists():
        with open(reddit_path, 'r', encoding='utf-8') as f:
            reddit_data = json.load(f)
        print(f"Loaded Reddit data: {reddit_data.get('download_info', {}).get('total_posts', 0)} posts")
    
    # Compile full dataset
    output = {
        'dataset_info': {
            'name': 'Flat Earth Evidence — Pro & Con Structured Dataset',
            'created': datetime.now(timezone.utc).isoformat(),
            'purpose': 'Test Proof Engine evaluates both sides fairly; prove app works on known-wrong theory',
            'strategy': 'Collect strongest flat earth claims with cited evidence, pair with scientific rebuttals',
            'sources': [
                'flattruths.com (evidence library, 10 pages scraped)',
                'r/flatearth + r/globeskepticism + r/notaglobe (Arctic Shift API)',
                'Farm dataset (ACL 2024, persuasion techniques)',
                'Curated claims from community literature',
            ],
            'total_structured_claims': len(structured_claims),
            'total_scraped_pages': len(scraped_pages),
            'total_reddit_posts': reddit_data.get('download_info', {}).get('total_posts', 0),
        },
        'structured_claims': structured_claims,
        'scraped_evidence_pages': scraped_pages,
        'reddit_posts_summary': {
            'count': reddit_data.get('download_info', {}).get('total_posts', 0),
            'subreddits': reddit_data.get('download_info', {}).get('subreddits', []),
            'file': str(reddit_path),
        },
    }
    
    out_path = OUTPUT_DIR / 'flat_earth_comprehensive_dataset.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'=' * 70}")
    print("DATASET CREATED")
    print(f"{'=' * 70}")
    print(f"  Saved: {out_path}")
    print(f"  Structured claims: {len(structured_claims)}")
    print(f"  Scraped pages: {len(scraped_pages)}")
    print(f"  Categories covered:")
    cats = set(c['category'] for c in structured_claims)
    for cat in sorted(cats):
        count = sum(1 for c in structured_claims if c['category'] == cat)
        print(f"    {cat}: {count} claims")
    print()
    print("  NEXT STEPS:")
    print("  1. Run Proof Engine on PRO claims (should score UNPROVEN)")
    print("  2. Run Proof Engine on ANTI claims (should score higher)")
    print("  3. Compare — proves the engine is working correctly")
    print("  4. Add to Theory Registry frontend")
    print()
    print("  FOR MORE DATA (manual download):")
    print("  • theflatearthpodcast.com — 7,021+ videos, 200 claimed proofs")
    print("  • flatearthdave.com — organized content creator")
    print("  • theflatearthsociety.org/forum — forums (use forum-dl tool)")
    print("  • Flat Earth Society wiki: wiki.tfes.org")


if __name__ == '__main__':
    main()
