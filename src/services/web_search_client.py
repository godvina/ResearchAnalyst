"""Web Search Client — thin wrapper around Brave Search API.

Uses urllib.request only (no external HTTP libraries) for Lambda VPC compatibility.
Provides web search and page content fetching with timeout handling.
"""

import json
import logging
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)


class WebSearchError(Exception):
    """Raised when the web search API returns an error."""
    pass


# URL patterns to skip when fetching page content
_BLOCKED_EXTENSIONS = re.compile(
    r"\.(pdf|docx?|xlsx?|pptx?|zip|tar|gz|mp4|mp3|avi|mov|wmv|flv|wav|ogg)(\?|#|$)",
    re.IGNORECASE,
)

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; InvestigativeIntelligence/1.0; +https://aws.amazon.com)"
)


class WebSearchClient:
    """Brave Search API client using urllib.request."""

    BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: str, timeout: int = 10) -> None:
        self._api_key = api_key
        self._timeout = timeout
        self._ssl_ctx = ssl.create_default_context()

    def search(self, query: str, count: int = 10) -> list:
        """Execute a web search query via Brave Search API.

        Args:
            query: Search query string.
            count: Number of results to return (max 20).

        Returns:
            List of dicts with keys: url, title, snippet.

        Raises:
            WebSearchError: On API failure or timeout.
        """
        params = urllib.parse.urlencode({"q": query, "count": min(count, 20)})
        url = f"{self.BRAVE_SEARCH_URL}?{params}"

        req = urllib.request.Request(url)
        req.add_header("Accept", "application/json")
        req.add_header("Accept-Encoding", "identity")
        req.add_header("X-Subscription-Token", self._api_key)

        try:
            with urllib.request.urlopen(
                req, context=self._ssl_ctx, timeout=self._timeout
            ) as resp:
                body = json.loads(resp.read().decode("utf-8"))

            results = []
            for item in body.get("web", {}).get("results", []):
                results.append({
                    "url": item.get("url", ""),
                    "title": item.get("title", ""),
                    "snippet": item.get("description", ""),
                })
            return results

        except urllib.error.HTTPError as exc:
            raise WebSearchError(
                f"Brave Search API error: HTTP {exc.code} — {exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            raise WebSearchError(
                f"Brave Search API connection error: {exc.reason}"
            ) from exc
        except Exception as exc:
            raise WebSearchError(f"Brave Search API error: {exc}") from exc

    def fetch_page(self, url: str) -> Optional[str]:
        """Fetch full page HTML from a URL.

        Args:
            url: The URL to fetch.

        Returns:
            Raw HTML string, or None on error/timeout.
            Skips blocked URL patterns (PDFs, videos, archives).
        """
        # Skip blocked file types
        if _BLOCKED_EXTENSIONS.search(url):
            logger.debug("Skipping blocked URL pattern: %s", url[:120])
            return None

        req = urllib.request.Request(url)
        req.add_header("User-Agent", _DEFAULT_USER_AGENT)
        req.add_header("Accept", "text/html,application/xhtml+xml")
        req.add_header("Accept-Encoding", "identity")

        try:
            with urllib.request.urlopen(
                req, context=self._ssl_ctx, timeout=self._timeout
            ) as resp:
                content_type = resp.headers.get("Content-Type", "")
                if "text/html" not in content_type and "xhtml" not in content_type:
                    logger.debug("Skipping non-HTML content: %s", content_type)
                    return None

                # Read up to 500KB to avoid memory issues
                raw = resp.read(512_000)
                # Try to detect encoding from headers
                charset = "utf-8"
                if "charset=" in content_type:
                    charset = content_type.split("charset=")[-1].strip().split(";")[0]
                try:
                    return raw.decode(charset, errors="replace")
                except (LookupError, UnicodeDecodeError):
                    return raw.decode("utf-8", errors="replace")

        except Exception as exc:
            logger.debug("Failed to fetch %s: %s", url[:120], str(exc)[:200])
            return None
