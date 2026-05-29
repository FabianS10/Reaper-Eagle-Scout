"""
Discovery service.
Translates a user's intent into targeted SERP queries, runs them through Bright
Data, and returns candidate URLs to fetch. Supports country-specific and global
opportunity reconnaissance.
"""
import logging
from dataclasses import dataclass
from urllib.parse import urlparse

from app.config import get_settings
from app.services.brightdata_serp import SerpResult, multi_search_serp

logger = logging.getLogger(__name__)
settings = get_settings()

GLOBAL_COUNTRY_ALIASES = {"", "all", "global", "world", "worldwide", "international", None}

COUNTRY_SEARCH_META = {
    "Colombia": ("co", "es"),
    "Mexico": ("mx", "es"),
    "Peru": ("pe", "es"),
    "Chile": ("cl", "es"),
    "Brazil": ("br", "pt"),
    "Argentina": ("ar", "es"),
    "United States": ("us", "en"),
    "United Kingdom": ("uk", "en"),
    "Canada": ("ca", "en"),
    "Australia": ("au", "en"),
    "European Union": ("us", "en"),
    "Worldwide": ("us", "en"),
}

# Known high-trust procurement domains by country/region.
PROCUREMENT_DOMAINS = {
    "Global": [
        "ungm.org",
        "worldbank.org",
        "adb.org",
        "iadb.org",
        "procurement-notices.undp.org",
        "unops.org",
        "devbusiness.un.org",
    ],
    "European Union": [
        "ted.europa.eu",
        "ec.europa.eu",
    ],
    "United States": [
        "sam.gov",
        "gsa.gov",
        "grants.gov",
        "usaspending.gov",
    ],
    "United Kingdom": [
        "find-tender.service.gov.uk",
        "contracts-finder.service.gov.uk",
        "gov.uk",
    ],
    "Canada": [
        "canadabuys.canada.ca",
        "buyandsell.gc.ca",
        "tpsgc-pwgsc.gc.ca",
    ],
    "Australia": [
        "tenders.gov.au",
        "austrade.gov.au",
    ],
    "Colombia": [
        "secop.gov.co",
        "contratos.gov.co",
        "colombiacompra.gov.co",
        "mintic.gov.co",
        "minsalud.gov.co",
        "idu.gov.co",
        "invias.gov.co",
        "innpulsa.gov.co",
        "sena.edu.co",
        "dnp.gov.co",
    ],
    "Mexico": ["compranet.gob.mx", "gob.mx", "imss.gob.mx", "sat.gob.mx"],
    "Peru": ["seace.gob.pe", "gob.pe", "osce.gob.pe"],
    "Chile": ["mercadopublico.cl", "chilecompra.cl"],
    "Brazil": ["comprasnet.gov.br", "gov.br", "licitacoes-e.com.br"],
    "Argentina": ["argentina.gob.ar", "contratar.gob.ar"],
}

SECTOR_KEYWORDS = {
    "AI": [
        "artificial intelligence", "machine learning", "AI", "deep learning",
        "computer vision", "NLP", "inteligencia artificial", "visión por computador",
    ],
    "Software": [
        "software", "digital platform", "information system", "web application",
        "software development", "SaaS", "transformación digital", "plataforma digital",
    ],
    "Data Analytics": [
        "data analytics", "business intelligence", "BI", "data science",
        "data visualization", "analítica de datos", "ciencia de datos",
    ],
    "Healthcare": [
        "digital health", "healthcare", "hospital", "clinical", "telemedicine",
        "diagnostic", "EHR", "salud digital", "diagnóstico",
    ],
    "Traffic": [
        "traffic management", "urban mobility", "intelligent transportation",
        "ITS", "smart city", "tráfico", "movilidad urbana", "gestión vial",
    ],
    "Cybersecurity": [
        "cybersecurity", "information security", "SIEM", "threat intelligence",
        "SOC", "seguridad informática", "ISO 27001",
    ],
    "Cloud": ["cloud", "cloud computing", "AWS", "Azure", "GCP", "DevOps", "cloud services"],
}

TENDER_TERMS_EN = [
    "tender", "RFP", "request for proposal", "procurement", "solicitation",
    "contract opportunity", "bid opportunity", "grant funding",
]

TENDER_TERMS_ES = [
    "licitación", "contratación", "convocatoria", "proceso de selección",
    "invitación a cotizar", "concurso de méritos",
]


@dataclass
class CandidateURL:
    url: str
    title: str
    snippet: str
    domain_trust_score: float
    source_query: str


def _is_global(country: str | None) -> bool:
    return (country or "").strip().lower() in GLOBAL_COUNTRY_ALIASES


def _sector_terms(user_query: str, sector: str | None) -> list[str]:
    if sector and sector in SECTOR_KEYWORDS:
        return SECTOR_KEYWORDS[sector][:4]

    detected: list[str] = []
    q = user_query.lower()
    for terms in SECTOR_KEYWORDS.values():
        if any(t.lower() in q for t in terms):
            detected.extend(terms[:3])

    return detected[:4] or [user_query]


def _domains_for_scope(country: str | None) -> list[str]:
    if _is_global(country):
        domains: list[str] = []
        for key in [
            "Global", "European Union", "United States", "United Kingdom",
            "Canada", "Australia", "Colombia", "Mexico", "Chile", "Brazil", "Argentina", "Peru",
        ]:
            domains.extend(PROCUREMENT_DOMAINS.get(key, []))
        return domains
    return PROCUREMENT_DOMAINS.get(country or "", []) + PROCUREMENT_DOMAINS["Global"][:3]


def build_discovery_queries(user_query: str, country: str | None = None, sector: str | None = None) -> list[str]:
    """Build global/country-specific SERP queries from user intent."""
    queries: list[str] = []
    terms = _sector_terms(user_query, sector)
    sector_phrase = " OR ".join(f'"{t}"' if " " in t else t for t in terms[:3])

    if _is_global(country):
        # Global/default mode: search major public procurement ecosystems first.
        queries.extend([
            f'({sector_phrase}) (tender OR RFP OR procurement OR solicitation) 2025',
            f'({sector_phrase}) "request for proposal" "deadline"',
            f'({sector_phrase}) "bid opportunity" "budget"',
            f'({sector_phrase}) "grant funding" "application deadline"',
            f'site:sam.gov ({sector_phrase}) (solicitation OR opportunity)',
            f'site:ted.europa.eu ({sector_phrase}) tender',
            f'site:find-tender.service.gov.uk ({sector_phrase})',
            f'site:canadabuys.canada.ca ({sector_phrase})',
            f'site:tenders.gov.au ({sector_phrase})',
            f'site:ungm.org ({sector_phrase}) procurement',
            f'site:worldbank.org procurement ({sector_phrase})',
            f'site:iadb.org procurement ({sector_phrase})',
        ])
    else:
        country_term = country or "Colombia"
        tender_terms = TENDER_TERMS_ES if country_term in {"Colombia", "Mexico", "Peru", "Chile", "Argentina"} else TENDER_TERMS_EN
        for term in tender_terms[:5]:
            queries.append(f'{term} ({sector_phrase}) {country_term} 2025')

        for domain in _domains_for_scope(country_term)[:8]:
            queries.append(f'site:{domain} ({sector_phrase})')

        queries.extend([
            f'RFP ({sector_phrase}) {country_term} deadline budget',
            f'grant funding ({sector_phrase}) {country_term} 2025',
            f'contract awarded ({sector_phrase}) {country_term}',
        ])

    # Always include the user's raw intent as a broad recall query.
    queries.insert(0, user_query)

    # Deduplicate while preserving order.
    clean: list[str] = []
    for q in queries:
        q = " ".join(q.split())
        if q not in clean:
            clean.append(q)
    return clean[:12]


def score_domain_trust(url: str, country: str | None = None) -> float:
    """Assign a trust score based on domain recognition."""
    domain = urlparse(url).netloc.lower().replace("www.", "")

    all_procurement = [d for domains in PROCUREMENT_DOMAINS.values() for d in domains]
    if any(domain.endswith(d) or d in domain for d in all_procurement):
        return 0.95

    gov_tlds = [
        ".gov", ".gov.co", ".gov.mx", ".gob.mx", ".gob.pe", ".gov.br",
        ".gob.ar", ".gov.cl", ".gov.uk", ".gc.ca", ".europa.eu", ".edu",
    ]
    if any(tld in domain for tld in gov_tlds):
        return 0.88

    if any(d in domain for d in ["reuters", "bloomberg", "businesswire", "prnewswire"]):
        return 0.72

    if any(d in domain for d in ["linkedin", "crunchbase"]):
        return 0.55

    return 0.45


def _search_meta(country: str | None) -> tuple[str, str]:
    if _is_global(country):
        return COUNTRY_SEARCH_META["Worldwide"]
    return COUNTRY_SEARCH_META.get(country or "Colombia", ("us", "en"))


async def discover_candidates(
    user_query: str,
    country: str | None = None,
    sector: str | None = None,
    max_results: int = 20,
) -> list[CandidateURL]:
    """Build queries → run SERP → score and deduplicate candidate URLs."""
    queries = build_discovery_queries(user_query, country, sector)
    gl, hl = _search_meta(country)

    logger.info("Running %s SERP queries for %r; country=%r sector=%r", len(queries), user_query, country, sector)

    raw_results: list[SerpResult] = await multi_search_serp(
        queries,
        results_per_query=max(3, min(settings.max_serp_results, 10)),
        country=gl,
        language=hl,
    )

    seen: set[str] = set()
    candidates: list[CandidateURL] = []

    for r in raw_results:
        normalized = r.url.rstrip("/")
        if normalized in seen:
            continue
        seen.add(normalized)

        trust = score_domain_trust(r.url, country)
        candidates.append(CandidateURL(
            url=r.url,
            title=r.title,
            snippet=r.snippet,
            domain_trust_score=trust,
            source_query=getattr(r, "source_query", "") or user_query,
        ))

    # Sort by trust, but keep enough diversity for recall.
    candidates.sort(key=lambda c: c.domain_trust_score, reverse=True)
    logger.info("Discovered %s unique candidates", len(candidates))
    return candidates[:max_results]
