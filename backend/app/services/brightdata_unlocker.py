"""
Bright Data Web Unlocker integration.
Uses direct HTTP first, then Bright Data Direct API access when a page is blocked.
"""
import logging
import time

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

BRIGHTDATA_REQUEST_URL = "https://api.brightdata.com/request"


class FetchResult:
    def __init__(
        self,
        url: str,
        content: str,
        content_type: str,
        status_code: int,
        used_unlocker: bool,
        fetch_time_ms: float,
    ):
        self.url = url
        self.content = content
        self.content_type = content_type
        self.status_code = status_code
        self.used_unlocker = used_unlocker
        self.fetch_time_ms = fetch_time_ms
        self.success = 200 <= status_code < 300

    def is_pdf(self) -> bool:
        return "application/pdf" in self.content_type or self.url.lower().endswith(".pdf")

    def is_html(self) -> bool:
        return "text/html" in self.content_type or "<html" in self.content[:500].lower()

    def is_json(self) -> bool:
        return "application/json" in self.content_type


def _decode_body(raw: bytes, content_type: str) -> str:
    if "application/pdf" in content_type:
        return raw.decode("latin-1", errors="ignore")
    return raw.decode("utf-8", errors="replace")


async def fetch_with_unlocker(url: str, timeout: float = 60.0) -> FetchResult:
    """Fetch a URL through Bright Data Web Unlocker Direct API."""
    if not settings.brightdata_api_key:
        logger.warning("BRIGHTDATA_API_KEY not set — skipping Web Unlocker.")
        return FetchResult(url, "", "text/html", 0, True, 0)

    payload = {
        "zone": settings.brightdata_unlocker_zone,
        "url": url,
        "format": "raw",
    }
    headers = {
        "Authorization": f"Bearer {settings.brightdata_api_key}",
        "Content-Type": "application/json",
    }

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.post(BRIGHTDATA_REQUEST_URL, json=payload, headers=headers)
            response.raise_for_status()

        elapsed = (time.monotonic() - start) * 1000
        content_type = response.headers.get("content-type", "text/html")

        # Some API responses can arrive as a JSON wrapper with body/status_code.
        if "application/json" in content_type:
            try:
                data = response.json()
                if isinstance(data, dict) and "body" in data:
                    body = data.get("body") or ""
                    headers_obj = data.get("headers") or {}
                    content_type = headers_obj.get("content-type", "text/html")
                    status_code = int(data.get("status_code") or response.status_code)
                    return FetchResult(url, body, content_type, status_code, True, elapsed)
            except Exception:
                pass

        content = _decode_body(response.content, content_type)
        return FetchResult(url, content, content_type, response.status_code, True, elapsed)

    except httpx.TimeoutException:
        logger.warning("Unlocker timeout for %s", url)
        return FetchResult(url, "", "text/html", 408, True, 0)
    except Exception as e:
        logger.error("Unlocker error for %s: %s", url, e)
        return FetchResult(url, "", "text/html", 500, True, 0)


async def fetch_direct(url: str, timeout: float = 15.0) -> FetchResult:
    """Attempt a direct HTTP fetch before falling back to Web Unlocker."""
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ReaperEagleScout/1.0)"},
        ) as client:
            response = await client.get(url)

        elapsed = (time.monotonic() - start) * 1000
        content_type = response.headers.get("content-type", "text/html")
        content = _decode_body(response.content, content_type)
        return FetchResult(url, content, content_type, response.status_code, False, elapsed)

    except Exception:
        return FetchResult(url, "", "text/html", 0, False, 0)


async def smart_fetch(url: str) -> FetchResult:
    """
    Strategy:
    1. Try direct HTTP fetch.
    2. If blocked/empty, fall back to Bright Data Web Unlocker.
    """
    result = await fetch_direct(url)
    if result.success and len(result.content) > 500:
        return result

    logger.info("Direct fetch failed for %s (status=%s), using Web Unlocker", url, result.status_code)
    return await fetch_with_unlocker(url)
