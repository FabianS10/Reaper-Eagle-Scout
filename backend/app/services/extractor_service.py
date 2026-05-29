"""
Extractor service.
Uses the Anthropic API to extract structured opportunity data from raw document text.
Returns a validated OpportunityExtract Pydantic model.
No freeform output — the LLM is forced into a JSON schema.
"""
import json
import logging
import re
from urllib.parse import urlparse
from typing import Optional, Any
from anthropic import AsyncAnthropic
from app.config import get_settings
from app.schemas.opportunity_schema import OpportunityExtract
from app.services.parser_service import ParsedDocument, truncate_for_llm

logger = logging.getLogger(__name__)
settings = get_settings()

SYSTEM_PROMPT = """You are a procurement intelligence extraction engine.
Given document text from a website or PDF, extract structured opportunity data.
You must respond ONLY with a valid JSON object matching the schema below.
No explanation. No markdown. No code fences. Just the JSON object.

Schema:
{
  "title": string | null,
  "organization": string | null,
  "country": string | null,
  "city": string | null,
  "sector": one of ["AI", "Software", "Data Analytics", "Healthcare", "Traffic", "Cybersecurity", "Cloud", "Other"] | null,
  "opportunity_type": one of ["public_tender", "private_rfp", "grant", "accelerator", "competitor_signal", "market_signal", "unknown"],
  "budget_amount": number | null,
  "budget_currency": "COP" | "USD" | "MXN" | "PEN" | "CLP" | "EUR" | null,
  "deadline": "YYYY-MM-DD" | null,
  "publication_date": "YYYY-MM-DD" | null,
  "requirements": [string, ...],
  "eligibility": [string, ...],
  "documents": [string, ...],
  "contact_email": string | null,
  "summary": string,
  "evidence_snippets": [string, ...],
  "extraction_confidence": number between 0.0 and 1.0
}

Rules:
- extraction_confidence reflects how certain you are given the text quality
- evidence_snippets are short direct quotes (under 20 words each) that prove key facts
- requirements: list the actual stated requirements, not guesses
- If a field is not present in the text, use null or empty list
- budget_amount should be numeric (no currency symbols)
- dates must be YYYY-MM-DD format
"""

USER_TEMPLATE = """Source URL: {url}

Document text:
{text}

Extract the procurement/tender/opportunity data from the above."""


async def extract_opportunity(
    doc: ParsedDocument,
    user_query: str = "",
) -> Optional[OpportunityExtract]:
    """
    Call Claude to extract a structured OpportunityExtract from a parsed document.
    Returns None if the document doesn't contain a real opportunity.
    """
    if not settings.anthropic_api_key:
        logger.warning("ANTHROPIC_API_KEY not set — extraction will fail.")
        return None

    if not doc.main_text or doc.word_count < 50:
        logger.debug(f"Skipping extraction — too little text from {doc.url}")
        return None

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    text_block = truncate_for_llm(doc, max_chars=8000)
    prompt = USER_TEMPLATE.format(url=doc.url, text=text_block)

    try:
        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=settings.anthropic_max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip()

        # Strip any accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        data = json.loads(raw)
        extract = OpportunityExtract.model_validate(data)

        # Sanity check: discard obvious non-opportunities
        if extract.opportunity_type == "unknown" and extract.extraction_confidence < 0.3:
            logger.debug(f"Low-confidence unknown opportunity discarded: {doc.url}")
            return None

        if not extract.title and not extract.organization:
            logger.debug(f"No title or org extracted — discarding: {doc.url}")
            return None

        return extract

    except json.JSONDecodeError as e:
        logger.warning(f"LLM returned invalid JSON for {doc.url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Extraction error for {doc.url}: {e}")
        return None



# ── Fast rule-based enrichment for hackathon MVP ──────────────────────────────

COUNTRY_HINTS = {
    "Belgium": ["belgium", "belgian"],
    "United States": ["united states", "u.s.", "usa", "sam.gov", ".gov"],
    "United Kingdom": ["united kingdom", "uk ", "find-tender.service.gov.uk"],
    "Canada": ["canada", "canadabuys"],
    "Australia": ["australia", "austender", "tenders.gov.au"],
    "European Union": ["ted.europa.eu", "european union"],
    "Colombia": ["colombia", "secop", ".gov.co", "colombiacompra"],
    "Mexico": ["mexico", "méxico", ".gob.mx", "compranet"],
    "Peru": ["peru", "perú", "seace", ".gob.pe"],
    "Chile": ["chile", "mercadopublico", "chilecompra"],
    "Brazil": ["brazil", "brasil", "comprasnet", ".gov.br"],
    "Argentina": ["argentina", "contratar.gob.ar", ".gob.ar"],
}

SECTOR_HINTS = {
    "AI": ["artificial intelligence", "machine learning", " ai ", "ai-based", "deep learning", "computer vision", "llm", "nlp"],
    "Software": ["software", "platform", "application", "system", "web development", "api", "saas", "digital service"],
    "Data Analytics": ["data analytics", "business intelligence", "dashboard", "data platform", "data science", "analytics"],
    "Healthcare": ["health", "hospital", "clinical", "medical", "cancer", "diagnostic", "imaging", "patient"],
    "Traffic": ["traffic", "transport", "mobility", "road", "urban mobility", "intelligent transport"],
    "Cybersecurity": ["cybersecurity", "security", "soc", "siem", "threat", "vulnerability"],
    "Cloud": ["cloud", "aws", "azure", "gcp", "hosting", "infrastructure"],
}

ORG_BY_DOMAIN = {
    "ted.europa.eu": "TED / European public procurement",
    "sam.gov": "U.S. Federal Government / SAM.gov",
    "ungm.org": "United Nations Global Marketplace",
    "worldbank.org": "World Bank Procurement",
    "find-tender.service.gov.uk": "UK Find a Tender Service",
    "canadabuys.canada.ca": "Government of Canada / CanadaBuys",
    "tenders.gov.au": "Australian Government / AusTender",
    "secop.gov.co": "Colombia Compra Eficiente / SECOP",
    "colombiacompra.gov.co": "Colombia Compra Eficiente",
}

CURRENCY_PATTERNS = [
    ("EUR", r"(?:€|EUR)\s*([0-9][0-9,\. ]+)(?:\s*(million|billion|m|bn))?"),
    ("USD", r"(?:US\$|USD|\$)\s*([0-9][0-9,\. ]+)(?:\s*(million|billion|m|bn))?"),
    ("GBP", r"(?:£|GBP)\s*([0-9][0-9,\. ]+)(?:\s*(million|billion|m|bn))?"),
    ("CAD", r"(?:CAD)\s*([0-9][0-9,\. ]+)(?:\s*(million|billion|m|bn))?"),
    ("COP", r"(?:COP|\$)\s*([0-9][0-9,\. ]+)(?:\s*(millones?|million|billion|m|bn))?"),
]


def _candidate_value(candidate: Any, name: str, default: str = "") -> str:
    return str(getattr(candidate, name, default) or default)


def _combined_candidate_text(doc: ParsedDocument, candidate: Any | None = None) -> str:
    pieces = [doc.title, doc.meta_description, doc.main_text[:6000]]
    if candidate is not None:
        pieces.insert(0, _candidate_value(candidate, "title"))
        pieces.insert(1, _candidate_value(candidate, "snippet"))
        pieces.insert(2, _candidate_value(candidate, "url"))
    return "\n".join(p for p in pieces if p)


def _domain_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def infer_country(text: str, url: str = "") -> Optional[str]:
    haystack = f"{url}\n{text}".lower()
    # Prefer explicit country words over broad EU/public procurement domains.
    for country, hints in COUNTRY_HINTS.items():
        if country == "European Union":
            continue
        if any(h in haystack for h in hints):
            return country
    if any(h in haystack for h in COUNTRY_HINTS["European Union"]):
        return "European Union"
    return None


def infer_organization(text: str, url: str = "") -> Optional[str]:
    domain = _domain_from_url(url)
    for dom, org in ORG_BY_DOMAIN.items():
        if dom in domain or dom in url.lower():
            return org

    # Common procurement page labels.
    patterns = [
        r"(?:Contracting authority|Buyer|Organisation|Organization|Entity|Entidad contratante|Órgano de contratación)\s*[:\-]\s*([^\n\r|]{3,120})",
        r"(?:Published by|Issued by|Agency|Department)\s*[:\-]\s*([^\n\r|]{3,120})",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()[:180]
    return None


def infer_sector(text: str) -> Optional[str]:
    haystack = f" {text.lower()} "
    # Healthcare AI should show both concepts when present.
    if any(h in haystack for h in SECTOR_HINTS["Healthcare"]) and any(h in haystack for h in SECTOR_HINTS["AI"]):
        return "Healthcare"
    best_sector = None
    best_score = 0
    for sector, hints in SECTOR_HINTS.items():
        score = sum(1 for h in hints if h in haystack)
        if score > best_score:
            best_sector, best_score = sector, score
    return best_sector


def infer_opportunity_type(text: str, url: str = "") -> str:
    haystack = f"{url}\n{text}".lower()
    if any(x in haystack for x in ["ted.europa.eu", "sam.gov", "ungm.org", "find-tender", "canadabuys", "tenders.gov.au", "tender", "procurement", "solicitation", "competition", "licitación"]):
        return "public_tender"
    if any(x in haystack for x in ["request for proposal", "rfp", "bid opportunity"]):
        return "private_rfp"
    if any(x in haystack for x in ["grant", "funding", "accelerator", "convocatoria", "subvención"]):
        return "grant"
    return "unknown"


def _parse_number(num: str, multiplier_word: str | None = None) -> float | None:
    cleaned = re.sub(r"[^0-9,\.]", "", num or "")
    if not cleaned:
        return None
    # Treat comma as thousands separator when both comma and dot are present.
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(",", "")
    # Treat single comma decimal as dot; otherwise commas are thousands.
    elif "," in cleaned and cleaned.count(",") == 1 and len(cleaned.rsplit(",", 1)[-1]) <= 2:
        cleaned = cleaned.replace(",", ".")
    else:
        cleaned = cleaned.replace(",", "")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    mult = (multiplier_word or "").lower()
    if mult in {"million", "millions", "millón", "millones", "m"}:
        value *= 1_000_000
    elif mult in {"billion", "billions", "bn"}:
        value *= 1_000_000_000
    return value


def infer_budget(text: str) -> tuple[Optional[float], Optional[str]]:
    for currency, pat in CURRENCY_PATTERNS:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            value = _parse_number(m.group(1), m.group(2) if len(m.groups()) > 1 else None)
            if value and value > 0:
                return value, currency
    return None, None


def infer_dates(text: str) -> tuple[Optional[Any], Optional[Any]]:
    """Return best-effort deadline and publication date using dateparser."""
    try:
        from dateparser.search import search_dates
        from datetime import date
    except Exception:
        return None, None

    deadline = None
    publication = None
    # Prioritize contextual dates.
    context_patterns = [
        r"(?:deadline|closing date|submission deadline|due date|response deadline|date limite|fecha límite|fecha de cierre)[^\n\r:]{0,40}[:\-]?\s*([^\n\r]{6,80})",
        r"([^\n\r]{0,40}(?:deadline|closing date|submission deadline|fecha límite|fecha de cierre)[^\n\r]{0,80})",
    ]
    for pat in context_patterns:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            found = search_dates(m.group(1), languages=["en", "es", "fr", "de"], settings={"PREFER_DATES_FROM": "future", "RETURN_AS_TIMEZONE_AWARE": False})
            if found:
                deadline = found[0][1].date()
                break
        if deadline:
            break

    # General publication-ish dates.
    found = search_dates(text[:5000], languages=["en", "es", "fr", "de"], settings={"PREFER_DATES_FROM": "future", "RETURN_AS_TIMEZONE_AWARE": False}) or []
    if not deadline:
        # Pick the first future-ish date, otherwise the first date.
        today = date.today()
        for _, dt in found:
            d = dt.date()
            if d >= today:
                deadline = d
                break
        if not deadline and found:
            deadline = found[0][1].date()
    if found:
        publication = found[0][1].date()
    return deadline, publication


def clean_title(text: str, candidate_title: str = "", url: str = "") -> str:
    source = f"{candidate_title}\n{text}"
    # TED pattern: 484917-2025 - Competition Belgium – Research and development services...
    m = re.search(r"\b(\d{5,7}-\d{4})\s*-\s*(Competition|Result|Planning|Direct award preannouncement)\s+([^\n\r]{10,220})", source, flags=re.IGNORECASE)
    if m:
        tail = re.sub(r"\s+", " ", m.group(3)).strip(" -–—|")
        return f"{m.group(1)} — {tail[:160]}"
    if candidate_title and len(candidate_title.strip()) > 3:
        return re.sub(r"\s+", " ", candidate_title).strip()[:220]
    if text:
        first = next((ln.strip() for ln in text.splitlines() if len(ln.strip()) > 8), "")
        if first:
            return re.sub(r"\s+", " ", first).strip()[:220]
    return url.rstrip("/").split("/")[-1][:220] or "Untitled opportunity"


def evidence_from_text(text: str, candidate: Any | None = None, limit: int = 4) -> list[str]:
    ev: list[str] = []
    snippet = _candidate_value(candidate, "snippet") if candidate is not None else ""
    if snippet:
        ev.append(snippet[:240])
    for keyword in ["deadline", "closing", "budget", "contract", "tender", "procurement", "competition", "grant", "AI", "artificial intelligence"]:
        m = re.search(rf"[^\n\r]{{0,80}}{re.escape(keyword)}[^\n\r]{{0,160}}", text, flags=re.IGNORECASE)
        if m:
            phrase = re.sub(r"\s+", " ", m.group(0)).strip()
            if phrase and phrase not in ev:
                ev.append(phrase[:240])
        if len(ev) >= limit:
            break
    return ev[:limit]


def enrich_extract_with_candidate(
    extract: OpportunityExtract,
    doc: ParsedDocument,
    candidate: Any | None = None,
    user_query: str = "",
) -> OpportunityExtract:
    """
    Fill empty fields using candidate SERP metadata, URL/domain heuristics,
    regex extraction, and parser hits. This is the fast hackathon hardening layer:
    it makes the UI useful even when LLM extraction or portal-specific parsing is thin.
    """
    url = _candidate_value(candidate, "url", doc.url) if candidate is not None else doc.url
    candidate_title = _candidate_value(candidate, "title") if candidate is not None else ""
    text = _combined_candidate_text(doc, candidate)

    budget, currency = infer_budget(text)
    deadline, publication = infer_dates(text)
    org = infer_organization(text, url)
    country = infer_country(text, url)
    sector = infer_sector(text)
    opp_type = infer_opportunity_type(text, url)
    evidence = evidence_from_text(text, candidate)

    title = extract.title or clean_title(text, candidate_title, url)
    # If title is just a code like "484917-2025 - Competition", try to upgrade it.
    if re.fullmatch(r"\d{5,7}-\d{4}\s*-\s*\w+.*", title or ""):
        upgraded = clean_title(text, candidate_title, url)
        if len(upgraded) > len(title):
            title = upgraded

    # Build a readable summary if the LLM/fallback didn't.
    summary = extract.summary or ""
    if not summary or summary.strip() in {"—", "-"} or len(summary) < 40:
        summary_source = _candidate_value(candidate, "snippet") if candidate is not None else ""
        if not summary_source:
            summary_source = doc.meta_description or doc.main_text[:500]
        summary = re.sub(r"\s+", " ", summary_source).strip()[:700]

    # Requirements: lightweight extraction from procurement wording.
    requirements = list(extract.requirements or [])
    if not requirements:
        req_matches = re.findall(r"(?:requires?|requirement|scope|services?|supply of|provision of|development of)[^\.\n]{20,180}", text, flags=re.IGNORECASE)
        requirements = [re.sub(r"\s+", " ", r).strip() for r in req_matches[:5]]

    documents = list(extract.documents or [])
    if url.lower().endswith(".pdf") and url not in documents:
        documents.append(url)
    for link in getattr(doc, "download_links", [])[:5]:
        if link not in documents:
            documents.append(link)

    # Confidence rises when we fill useful user-facing fields from trusted evidence.
    confidence = extract.extraction_confidence or 0.35
    filled_signals = sum(bool(x) for x in [title, org, country, sector, opp_type != "unknown", budget, deadline, evidence])
    confidence = max(confidence, min(0.85, 0.25 + filled_signals * 0.075))

    return extract.model_copy(update={
        "title": title,
        "organization": extract.organization or org,
        "country": extract.country or country,
        "city": extract.city,
        "sector": extract.sector or sector,
        "opportunity_type": extract.opportunity_type if extract.opportunity_type != "unknown" else opp_type,
        "budget_amount": extract.budget_amount or budget,
        "budget_currency": extract.budget_currency or currency,
        "deadline": extract.deadline or deadline,
        "publication_date": extract.publication_date or publication,
        "requirements": requirements,
        "eligibility": extract.eligibility or [],
        "documents": documents[:8],
        "contact_email": extract.contact_email or (doc.detected_emails[0] if doc.detected_emails else None),
        "summary": summary,
        "evidence_snippets": extract.evidence_snippets or evidence,
        "extraction_confidence": confidence,
    })


def build_fallback_extract(doc: ParsedDocument) -> OpportunityExtract:
    """
    Rule-based fallback when the LLM is unavailable.
    Assembles a best-effort extract from regex hits.
    """
    import re
    from datetime import datetime

    title = doc.title or doc.url.split("/")[-1]

    # Try to guess opportunity type from text
    text_lower = doc.main_text.lower()
    opp_type = "unknown"
    if any(kw in text_lower for kw in ["licitación", "contratación pública", "secop", "proceso de selección"]):
        opp_type = "public_tender"
    elif any(kw in text_lower for kw in ["rfp", "request for proposal", "cotización"]):
        opp_type = "private_rfp"
    elif any(kw in text_lower for kw in ["convocatoria", "subvención", "grant", "cofinanciación"]):
        opp_type = "grant"

    # Budget
    budget = None
    currency = None
    for amt in doc.detected_amounts[:3]:
        nums = re.findall(r"[\d,\.]+", amt)
        if nums:
            try:
                val = float(nums[0].replace(",", ""))
                if "millones" in amt.lower() or "million" in amt.lower():
                    val *= 1_000_000
                budget = val
                currency = "COP" if "cop" in amt.lower() or "peso" in amt.lower() else "USD"
                break
            except ValueError:
                pass

    return OpportunityExtract(
        title=title[:500],
        organization=None,
        country=None,
        city=None,
        sector=None,
        opportunity_type=opp_type,
        budget_amount=budget,
        budget_currency=currency,
        deadline=None,
        publication_date=None,
        requirements=[],
        eligibility=[],
        documents=doc.download_links[:5],
        contact_email=doc.detected_emails[0] if doc.detected_emails else None,
        summary=doc.meta_description or doc.main_text[:400],
        evidence_snippets=[],
        extraction_confidence=doc.parse_confidence * 0.5,
    )
