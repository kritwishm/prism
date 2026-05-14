"""Website scraper. Uses Jina Reader for fetching + cleaning.

URL discovery is layered:
  1. /sitemap.xml (best signal — site tells us its own URLs)
  2. Homepage link extraction (Jina returns clean markdown w/ links)
  3. Hardcoded keyword paths (last-resort fallback)

Each candidate page is fetched independently. A 403/timeout on /about does
not kill /product. The pipeline always gets *something* unless every page
fails — in which case `pages_succeeded == 0` and the caller aborts before
spending an LLM call on slop.
"""

from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

import httpx
from loguru import logger

from .config import (
    DISCOVERY_KEYWORDS,
    DISCOVERY_PATH_HINTS,
    JINA_API_KEY,
    JINA_READER_BASE,
)
from .models import ScrapeResult

MAX_PAGES = 10
PER_PAGE_CHAR_CAP = 8000
THIN_CONTENT_THRESHOLD = 100


# --- page role tagging (used by the extractor digest) ---

_ROLE_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^/?$"), "HOMEPAGE"),
    (re.compile(r"/(about|company|story|why|team|mission)", re.I), "ABOUT"),
    (re.compile(r"/(product|solution|platform|service|feature)", re.I), "PRODUCT"),
    (re.compile(r"/(customer|case-stud|case_stud|partner)", re.I), "CUSTOMERS"),
    (re.compile(r"/(blog|news|press|insight|resource)", re.I), "BLOG"),
]


def _role_for(path: str) -> str:
    for pat, role in _ROLE_RULES:
        if pat.search(path):
            return role
    return "OTHER"


def _normalize(url: str) -> str:
    p = urlparse(url)
    path = p.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return f"{p.scheme}://{p.netloc}{path}"


def _same_host(candidate: str, host: str) -> bool:
    try:
        h = urlparse(candidate).netloc.lower()
    except Exception:
        return False
    return h == host.lower() or h.endswith("." + host.lower())


def _looks_relevant(url: str) -> bool:
    path = urlparse(url).path.lower()
    if any(x in path for x in (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".zip", ".mp4")):
        return False
    if re.search(r"/(login|signin|signup|register|cart|checkout|legal|privacy|terms|cookie)", path):
        return False
    return any(kw in path for kw in DISCOVERY_KEYWORDS) or path in ("", "/")


# --- discovery layers ---

async def _from_sitemap(client: httpx.AsyncClient, base: str) -> list[str]:
    urls: list[str] = []
    sitemap_url = f"{base}/sitemap.xml"
    try:
        resp = await client.get(sitemap_url)
        if resp.status_code != 200 or "<" not in resp.text[:200]:
            return []
        root = ET.fromstring(resp.text)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        for loc in root.findall(".//sm:loc", ns):
            if loc.text:
                urls.append(loc.text.strip())
        logger.info(f"[SCRAPE] sitemap.xml yielded {len(urls)} URLs")
    except Exception as e:
        logger.debug(f"[SCRAPE] sitemap fetch failed: {e}")
    return urls


async def _from_homepage_links(client: httpx.AsyncClient, base: str) -> list[str]:
    try:
        jina_url = f"{JINA_READER_BASE}{base}"
        headers = {"Accept": "application/json"}
        if JINA_API_KEY:
            headers["Authorization"] = f"Bearer {JINA_API_KEY}"
        resp = await client.get(jina_url, headers=headers)
        if resp.status_code != 200:
            return []
        text = resp.text
        # Markdown links: [text](url)
        urls = re.findall(r"\]\((https?://[^\s)]+)\)", text)
        # Also handle relative paths
        rel = re.findall(r"\]\((/[^\s)]+)\)", text)
        urls += [urljoin(base, r) for r in rel]
        logger.info(f"[SCRAPE] homepage links yielded {len(urls)} URLs")
        return urls
    except Exception as e:
        logger.debug(f"[SCRAPE] homepage link extraction failed: {e}")
        return []


def _from_hints(base: str) -> list[str]:
    return [urljoin(base, p) for p in DISCOVERY_PATH_HINTS]


async def discover_urls(client: httpx.AsyncClient, base: str, host: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []

    # Always start with the homepage
    home = _normalize(base)
    ordered.append(home)
    seen.add(home)

    for source in (
        await _from_sitemap(client, base),
        await _from_homepage_links(client, base),
        _from_hints(base),
    ):
        for u in source:
            if not _same_host(u, host):
                continue
            if not _looks_relevant(u):
                continue
            n = _normalize(u)
            if n in seen:
                continue
            seen.add(n)
            ordered.append(n)
            if len(ordered) >= MAX_PAGES:
                return ordered

    return ordered


# --- main entry ---

async def scrape_company(url: str) -> ScrapeResult:
    parsed = urlparse(url if url.startswith(("http://", "https://")) else f"https://{url}")
    host = parsed.netloc
    base = f"https://{host}"

    headers = {"Accept": "application/json"}
    if JINA_API_KEY:
        headers["Authorization"] = f"Bearer {JINA_API_KEY}"

    pages: list[dict] = []

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        candidates = await discover_urls(client, base, host)
        logger.info(f"[SCRAPE] {len(candidates)} candidate URLs for {host}")

        for candidate in candidates:
            jina_url = f"{JINA_READER_BASE}{candidate}"
            logger.info(f"[SCRAPE] fetching {candidate}")
            try:
                resp = await client.get(jina_url, headers=headers)
                if resp.status_code != 200:
                    logger.warning(f"[SCRAPE] {resp.status_code} from {candidate}")
                    continue

                ctype = resp.headers.get("content-type", "")
                if "application/json" in ctype:
                    data = resp.json()
                    content = (
                        data.get("data", {}).get("content", "")
                        if isinstance(data.get("data"), dict)
                        else resp.text
                    )
                else:
                    content = resp.text

                if not content or len(content) < THIN_CONTENT_THRESHOLD:
                    logger.warning(f"[SCRAPE] thin content from {candidate}")
                    continue

                path = urlparse(candidate).path or "/"
                pages.append({
                    "url": candidate,
                    "content": content[:PER_PAGE_CHAR_CAP],
                    "role": _role_for(path),
                    "success": True,
                })
                logger.success(f"[SCRAPE] {len(content)} chars from {candidate}")
            except Exception as e:
                logger.warning(f"[SCRAPE] failed {candidate}: {e}")
                continue

    pages_succeeded = len(pages)
    pages_attempted = len(candidates) if "candidates" in locals() else 0

    if pages_succeeded == 0:
        confidence = "low"
    elif pages_succeeded < 3:
        confidence = "medium"
    else:
        confidence = "high"

    return ScrapeResult(
        domain=host,
        pages_attempted=pages_attempted,
        pages_succeeded=pages_succeeded,
        pages=pages,
        confidence=confidence,
    )
