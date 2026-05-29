"""
Bright Data SERP API integration.

This version is tuned for Bright Data SERP API zones configured as Light JSON.
For Light JSON, Bright Data expects:
    format: "raw"
    data_format: "parsed_light"
The parsed payload contains an `organic` array.
"""
import json
import logging
from urllib.parse import urlencode, quote_plus

import httpx
from bs4 import BeautifulSoup

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

BRIGHTDATA_REQUEST_URL = "https://api.brightdata.com/request"


class SerpResult:
    def __init__(self, title: str, url: str, snippet: str, position: int, source_query: str = ""):
        self.title = title
        self.url = url
        self.snippet = snippet
        self.position = position
        self.source_query = source_query

    def __repr__(self):
        return f"SerpResult(pos={self.position}, url={self.url[:60]})"


def _google_serp_url(query: str, num_results: int, country: str, language: str) -> str:
    # Bright Data recommends that q= is the first query parameter.
    params = {
        "q": query,
        "num": min(max(num_results, 1), 10),
        "gl": (country or "us").lower(),
        "hl": language or "en",
    }
    return "https://www.google.com/search?" + urlencode(params)


def _safe_json_from_response(response: httpx.Response):
    """Return parsed JSON even when Bright Data returns JSON as a raw string."""
    try:
        data = response.json()
    except Exception:
        try:
            data = json.loads(response.text)
        except Exception:
            logger.error("Bright Data non-JSON response preview: %s", response.text[:500])
            return {}

    if isinstance(data, str):
        try:
            return json.loads(data)
        except Exception:
            logger.error("Bright Data JSON string could not be decoded. Preview: %s", data[:500])
            return {}

    return data


def _find_organic(obj):
    """Find an organic results array anywhere in a nested Bright Data payload."""
    if isinstance(obj, dict):
        for key in ("organic", "organic_results"):
            value = obj.get(key)
            if isinstance(value, list):
                return value
        for value in obj.values():
            found = _find_organic(value)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_organic(item)
            if found:
                return found
    return []


def _parse_serp_json(data) -> list[SerpResult]:
    """Parse Bright Data SERP JSON response into SerpResult objects."""
    results: list[SerpResult] = []
    organic = _find_organic(data)

    for i, item in enumerate(organic):
        if not isinstance(item, dict):
            continue
        url = item.get("link") or item.get("url") or item.get("href") or ""
        title = item.get("title") or item.get("source") or item.get("name") or ""
        snippet = item.get("description") or item.get("snippet") or item.get("text") or ""
        if url and title:
            results.append(SerpResult(title=title, url=url, snippet=snippet, position=i + 1))

    return results


async def _search_brightdata_serp(
    query: str,
    num_results: int = 10,
    country: str = "us",
    language: str = "en",
) -> list[SerpResult]:
    """Use Bright Data Direct API access for Light JSON SERP results."""
    if not settings.brightdata_api_key:
        logger.warning("BRIGHTDATA_API_KEY is missing; skipping Bright Data SERP.")
        return []

    target_url = _google_serp_url(query, num_results, country, language)
    payload = {
        "zone": settings.brightdata_serp_zone,
        "url": target_url,
        # Required for Light JSON / parsed_light zones.
        "format": "raw",
        "data_format": "parsed_light",
    }
    headers = {
        "Authorization": f"Bearer {settings.brightdata_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(BRIGHTDATA_REQUEST_URL, json=payload, headers=headers)

        if response.status_code >= 400:
            logger.error("Bright Data status: %s", response.status_code)
            logger.error("Bright Data response body: %s", response.text[:1000])

        response.raise_for_status()
        data = _safe_json_from_response(response)
        results = _parse_serp_json(data)

        if not results:
            if isinstance(data, dict):
                logger.warning("Bright Data SERP returned 0 organic results. Top-level keys: %s", list(data.keys()))
            else:
                logger.warning("Bright Data SERP returned 0 organic results. Payload type: %s", type(data).__name__)
            logger.warning("Bright Data response preview: %s", response.text[:1000])

        for r in results:
            r.source_query = query
        logger.info("Bright Data SERP returned %s results for %r", len(results), query)
        return results[:num_results]
    except Exception as e:
        logger.error("Bright Data SERP failed for %r: %s", query, e)
        return []


async def _search_duckduckgo_fallback(query: str, num_results: int = 10) -> list[SerpResult]:
    """
    Development fallback when Bright Data credentials are missing/misconfigured.
    This keeps the pipeline testable locally, but should not replace Bright Data
    in the hackathon submission.
    """
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ReaperEagleScout/1.0)"}
    results: list[SerpResult] = []

    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=headers) as client:
            response = await client.get(url)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")
        rows = soup.select(".result") or soup.select("div.web-result")
        for i, row in enumerate(rows[:num_results]):
            link = row.select_one("a.result__a") or row.select_one("a")
            if not link:
                continue
            title = link.get_text(" ", strip=True)
            href = link.get("href", "")
            snippet_el = row.select_one(".result__snippet")
            snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
            if title and href.startswith("http"):
                results.append(SerpResult(title, href, snippet, i + 1, source_query=query))

        logger.info("Fallback SERP returned %s results for %r", len(results), query)
    except Exception as e:
        logger.error("Fallback SERP failed for %r: %s", query, e)

    return results


async def search_serp(
    query: str,
    engine: str = "google",
    num_results: int = 10,
    country: str = "us",
    language: str = "en",
) -> list[SerpResult]:
    """
    Search engine results.
    1. Bright Data Direct API.
    2. DuckDuckGo fallback for local development if Bright Data returns nothing.
    """
    results = await _search_brightdata_serp(query, num_results, country, language)
    if results:
        return results

    if settings.allow_search_fallback:
        logger.warning("Using non-Bright-Data fallback search for local development.")
        return await _search_duckduckgo_fallback(query, num_results)

    return []


async def multi_search_serp(
    queries: list[str],
    results_per_query: int = 10,
    country: str = "us",
    language: str = "en",
) -> list[SerpResult]:
    """Run multiple SERP queries and deduplicate by URL."""
    all_results: list[SerpResult] = []
    seen_urls: set[str] = set()

    for query in queries:
        results = await search_serp(
            query=query,
            num_results=results_per_query,
            country=country,
            language=language,
        )
        for r in results:
            normalized = r.url.rstrip("/")
            if normalized not in seen_urls:
                seen_urls.add(normalized)
                all_results.append(r)

    return all_results
