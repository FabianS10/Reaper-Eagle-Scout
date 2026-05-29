"""
Parser service.
Takes raw HTTP responses and extracts clean text + structured metadata.
Pipeline: content-type detection → boilerplate removal → text extraction → field regex.
"""
import re
import io
import logging
from dataclasses import dataclass, field
from typing import Optional
from app.services.brightdata_unlocker import FetchResult

logger = logging.getLogger(__name__)


@dataclass
class ParsedDocument:
    url: str
    title: str = ""
    main_text: str = ""
    meta_description: str = ""
    content_type: str = "html"  # html | pdf | json | text
    detected_dates: list[str] = field(default_factory=list)
    detected_emails: list[str] = field(default_factory=list)
    detected_amounts: list[str] = field(default_factory=list)
    download_links: list[str] = field(default_factory=list)
    word_count: int = 0
    parse_confidence: float = 0.5
    error: Optional[str] = None


# ── Regex patterns ─────────────────────────────────────────────────────────────

DATE_PATTERNS = [
    r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
    r'\b\d{1,2}\s+(?:de\s+)?(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+(?:de\s+)?\d{4}\b',
    r'\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},?\s+\d{4}\b',
    r'\b\d{4}-\d{2}-\d{2}\b',
]

EMAIL_PATTERN = r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b'

AMOUNT_PATTERNS = [
    r'\$\s*[\d,\.]+(?:\s*(?:millones?|miles?|M|K|B))?\b',
    r'\bCOP\s*[\d,\.]+\b',
    r'\bUSD\s*[\d,\.]+\b',
    r'\b[\d,\.]+\s*(?:millones?|pesos|dólares)\b',
    r'\b[\d\.]+\s*(?:billion|million|trillion)\b',
]

PDF_LINK_PATTERN = r'href=["\']([^"\']*\.pdf[^"\']*)["\']'


def _extract_regex(text: str, patterns: list[str]) -> list[str]:
    found = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        found.extend(matches)
    return list(dict.fromkeys(found))[:20]  # dedupe, cap


# ── HTML parser ────────────────────────────────────────────────────────────────

def parse_html(fetch_result: FetchResult) -> ParsedDocument:
    doc = ParsedDocument(url=fetch_result.url, content_type="html")

    try:
        from bs4 import BeautifulSoup
        import trafilatura

        html = fetch_result.content

        # Title and meta via BS4
        soup = BeautifulSoup(html, "lxml")
        doc.title = (soup.title.get_text(strip=True) if soup.title else "")[:500]
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            doc.meta_description = (meta_desc.get("content") or "")[:500]

        # PDF attachment links
        doc.download_links = re.findall(PDF_LINK_PATTERN, html, re.IGNORECASE)[:10]

        # Main text via trafilatura (best for article-like content)
        main_text = trafilatura.extract(
            html,
            include_tables=True,
            include_links=False,
            include_images=False,
            no_fallback=False,
        )

        if not main_text or len(main_text) < 200:
            # Fallback: BS4 body text
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
            main_text = soup.get_text(separator="\n", strip=True)

        doc.main_text = main_text or ""
        doc.word_count = len(doc.main_text.split())

        combined = doc.title + " " + doc.meta_description + " " + doc.main_text
        doc.detected_dates = _extract_regex(combined, DATE_PATTERNS)
        doc.detected_emails = _extract_regex(combined, [EMAIL_PATTERN])
        doc.detected_amounts = _extract_regex(combined, AMOUNT_PATTERNS)

        # Confidence based on text volume and field hits
        confidence = 0.3
        if doc.word_count > 300:
            confidence += 0.2
        if doc.detected_dates:
            confidence += 0.15
        if doc.detected_amounts:
            confidence += 0.15
        if doc.detected_emails:
            confidence += 0.1
        if doc.title:
            confidence += 0.1
        doc.parse_confidence = min(confidence, 1.0)

    except Exception as e:
        doc.error = str(e)
        logger.error(f"HTML parse error for {fetch_result.url}: {e}")

    return doc


# ── PDF parser ─────────────────────────────────────────────────────────────────

def parse_pdf(fetch_result: FetchResult) -> ParsedDocument:
    doc = ParsedDocument(url=fetch_result.url, content_type="pdf")

    try:
        import fitz  # PyMuPDF

        raw_bytes = fetch_result.content.encode("latin-1")
        pdf = fitz.open(stream=io.BytesIO(raw_bytes), filetype="pdf")

        pages_text = []
        for page_num in range(min(len(pdf), 30)):  # cap at 30 pages
            page = pdf[page_num]
            pages_text.append(page.get_text())

        doc.main_text = "\n".join(pages_text)
        doc.word_count = len(doc.main_text.split())

        # Title from PDF metadata or first heading
        meta = pdf.metadata
        doc.title = (meta.get("title") or "").strip()[:500]
        if not doc.title and pages_text:
            first_lines = [l.strip() for l in pages_text[0].split("\n") if len(l.strip()) > 20]
            doc.title = first_lines[0][:500] if first_lines else ""

        doc.detected_dates = _extract_regex(doc.main_text, DATE_PATTERNS)
        doc.detected_emails = _extract_regex(doc.main_text, [EMAIL_PATTERN])
        doc.detected_amounts = _extract_regex(doc.main_text, AMOUNT_PATTERNS)

        confidence = 0.4
        if doc.word_count > 500:
            confidence += 0.2
        if doc.detected_dates:
            confidence += 0.15
        if doc.detected_amounts:
            confidence += 0.15
        if doc.title:
            confidence += 0.1
        doc.parse_confidence = min(confidence, 1.0)

    except Exception as e:
        doc.error = str(e)
        logger.error(f"PDF parse error for {fetch_result.url}: {e}")

    return doc


# ── JSON parser ────────────────────────────────────────────────────────────────

def parse_json(fetch_result: FetchResult) -> ParsedDocument:
    import json
    doc = ParsedDocument(url=fetch_result.url, content_type="json")

    try:
        data = json.loads(fetch_result.content)
        doc.main_text = json.dumps(data, ensure_ascii=False, indent=2)
        doc.word_count = len(doc.main_text.split())
        doc.parse_confidence = 0.7
    except Exception as e:
        doc.error = str(e)
        doc.main_text = fetch_result.content

    return doc


# ── Router ─────────────────────────────────────────────────────────────────────

def parse_document(fetch_result: FetchResult) -> ParsedDocument:
    """Route to the correct parser based on content type."""
    if not fetch_result.success or not fetch_result.content:
        return ParsedDocument(
            url=fetch_result.url,
            error=f"Fetch failed with status {fetch_result.status_code}",
        )

    if fetch_result.is_pdf():
        return parse_pdf(fetch_result)
    elif fetch_result.is_json():
        return parse_json(fetch_result)
    else:
        return parse_html(fetch_result)


def truncate_for_llm(doc: ParsedDocument, max_chars: int = 8000) -> str:
    """
    Build a clean text block for the LLM extraction pass.
    Prioritises title, meta, then main text.
    """
    parts = []
    if doc.title:
        parts.append(f"TITLE: {doc.title}")
    if doc.meta_description:
        parts.append(f"DESCRIPTION: {doc.meta_description}")
    if doc.detected_dates:
        parts.append(f"DETECTED DATES: {', '.join(doc.detected_dates[:5])}")
    if doc.detected_amounts:
        parts.append(f"DETECTED AMOUNTS: {', '.join(doc.detected_amounts[:5])}")
    if doc.detected_emails:
        parts.append(f"DETECTED EMAILS: {', '.join(doc.detected_emails[:3])}")
    parts.append(f"\nMAIN TEXT:\n{doc.main_text}")

    combined = "\n".join(parts)
    return combined[:max_chars]
