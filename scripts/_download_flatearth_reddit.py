"""Download r/flatearth Reddit posts via Arctic Shift API.

Arctic Shift is the successor to Pushshift - contains archived Reddit data.
We pull the top posts from r/flatearth for processing through our taxonomy pipeline.
"""
import json
import urllib.request
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / 'src' / 'data' / 'conspiracy-seed' / 'flat_earth_reddit'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def fetch_posts(subreddit, limit=100, sort='score', order='desc', after=None):
    """Fetch posts from Arctic Shift API."""
    url = f'https://arctic-shift.photon-reddit.com/api/posts/search?subreddit={subreddit}&limit={limit}'
    if after:
        url += f'&after={after}'
    
    req = urllib.request.Request(url, headers={'User-Agent': 'ResearchAnalyst/1.0 (academic research)'})
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read())
        return data.get('data', [])
    except Exception as e:
        print(f'  Error fetching: {e}')
        return []


def fetch_comments(subreddit, limit=100, sort='score', order='desc'):
    """Fetch comments from Arctic Shift API."""
    url = f'https://arctic-shift.photon-reddit.com/api/comments/search?subreddit={subreddit}&limit={limit}'
    
    req = urllib.request.Request(url, headers={'User-Agent': 'ResearchAnalyst/1.0 (academic research)'})
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read())
        return data.get('data', [])
    except Exception as e:
        print(f'  Error fetching comments: {e}')
        return []


def main():
    print("=" * 70)
    print("DOWNLOADING r/flatearth DATA via Arctic Shift API")
    print("=" * 70)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print()
    
    # Fetch top posts (multiple pages)
    all_posts = []
    print("Fetching top posts from r/flatearth...")
    
    # Get top scored posts
    posts = fetch_posts('flatearth', limit=100, sort='score', order='desc')
    all_posts.extend(posts)
    print(f"  Batch 1 (top score): {len(posts)} posts")
    time.sleep(1)
    
    # Get newest posts
    posts = fetch_posts('flatearth', limit=100, sort='created_utc', order='desc')
    all_posts.extend(posts)
    print(f"  Batch 2 (newest): {len(posts)} posts")
    time.sleep(1)
    
    # Also try r/theflatearth and r/globeskepticism
    for sub in ['theflatearth', 'globeskepticism', 'notaglobe']:
        posts = fetch_posts(sub, limit=50, sort='score', order='desc')
        if posts:
            all_posts.extend(posts)
            print(f"  r/{sub}: {len(posts)} posts")
        time.sleep(1)
    
    # Fetch top comments (often more substantive than post titles)
    print("\nFetching top comments from r/flatearth...")
    comments = fetch_comments('flatearth', limit=100, sort='score', order='desc')
    print(f"  Got {len(comments)} comments")
    
    # Deduplicate posts by ID
    seen_ids = set()
    unique_posts = []
    for post in all_posts:
        pid = post.get('id', '')
        if pid and pid not in seen_ids:
            seen_ids.add(pid)
            unique_posts.append(post)
    
    print(f"\nTotal unique posts: {len(unique_posts)}")
    print(f"Total comments: {len(comments)}")
    
    # Extract useful fields
    cleaned_posts = []
    for post in unique_posts:
        cleaned_posts.append({
            'id': post.get('id', ''),
            'title': post.get('title', ''),
            'selftext': post.get('selftext', ''),
            'score': post.get('score', 0),
            'num_comments': post.get('num_comments', 0),
            'created_utc': post.get('created_utc', 0),
            'author': post.get('author', ''),
            'subreddit': post.get('subreddit', ''),
            'url': post.get('url', ''),
            'link_flair_text': post.get('link_flair_text', ''),
        })
    
    cleaned_comments = []
    for comment in comments:
        body = comment.get('body', '')
        if len(body) > 50:  # Skip very short comments
            cleaned_comments.append({
                'id': comment.get('id', ''),
                'body': body,
                'score': comment.get('score', 0),
                'created_utc': comment.get('created_utc', 0),
                'author': comment.get('author', ''),
                'subreddit': comment.get('subreddit', ''),
            })
    
    # Save
    output = {
        'download_info': {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'source': 'Arctic Shift API (reddit archive)',
            'subreddits': ['flatearth', 'theflatearth', 'globeskepticism', 'notaglobe'],
            'total_posts': len(cleaned_posts),
            'total_comments': len(cleaned_comments),
        },
        'posts': cleaned_posts,
        'comments': cleaned_comments,
    }
    
    out_path = OUTPUT_DIR / 'reddit_flatearth_posts.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\nSaved to: {out_path}")
    print(f"  Posts: {len(cleaned_posts)}")
    print(f"  Comments: {len(cleaned_comments)}")
    
    # Show some samples
    if cleaned_posts:
        print("\nSample posts (top scored):")
        for p in sorted(cleaned_posts, key=lambda x: x['score'], reverse=True)[:5]:
            title = p['title'][:70]
            score = p['score']
            sub = p['subreddit']
            print(f"  [{score:4d}] r/{sub}: {title}")
    
    if cleaned_comments:
        print("\nSample comments:")
        for c in sorted(cleaned_comments, key=lambda x: x['score'], reverse=True)[:3]:
            body = c['body'][:120].replace('\n', ' ')
            print(f"  [{c['score']:4d}] {body}")


if __name__ == '__main__':
    main()
