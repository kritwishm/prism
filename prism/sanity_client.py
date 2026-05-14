import re
import secrets
from datetime import datetime, timezone
from typing import Optional

import httpx
from loguru import logger


def _key() -> str:
    """Sanity requires a unique `_key` on every object in an array.
    Studio refuses to render the array editor without it."""
    return secrets.token_hex(6)


def _keyed(items: list[dict]) -> list[dict]:
    """Inject a Sanity-compliant _key on each item if missing."""
    out = []
    for item in items:
        if "_key" not in item:
            item = {**item, "_key": _key()}
        out.append(item)
    return out

from .config import (
    SANITY_API_VERSION,
    SANITY_DATASET,
    SANITY_PROJECT_ID,
    SANITY_STUDIO_PATH,
    SANITY_TOKEN,
)
from .models import CopyBlocks, ExtractedFacts, ICPAnalysis
from .scoring import SCORING_VERSION


def _slugify_domain(domain: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "-", domain)


def _mutate_url() -> str:
    return f"https://{SANITY_PROJECT_ID}.api.sanity.io/v{SANITY_API_VERSION}/data/mutate/{SANITY_DATASET}"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {SANITY_TOKEN}",
        "Content-Type": "application/json",
    }


async def _post_mutations(payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(_mutate_url(), json=payload, headers=_headers())
        if resp.status_code >= 300:
            logger.error(f"[SANITY] failed: {resp.status_code} {resp.text}")
            raise RuntimeError(f"Sanity write failed: {resp.text}")
        return resp.json()


async def upsert_company_analysis(
    domain: str,
    facts: ExtractedFacts,
    icp: ICPAnalysis,
    copy: Optional[CopyBlocks],
    source_url: str,
    pages_scraped: int,
    data_confidence: str,
) -> str:
    """Create or replace the companyAnalysis doc. Returns the doc id."""
    doc_id = f"companyAnalysis.{_slugify_domain(domain)}"

    doc = {
        "_id": doc_id,
        "_type": "companyAnalysis",
        "domain": domain,
        "companyName": facts.company_name,
        "oneLine": facts.one_line_description,
        "industry": facts.industry,
        "buyerPersonas": facts.buyer_personas,
        "intentThemes": _keyed([t.model_dump() for t in icp.intent_themes]),
        "painPoints": _keyed([pp.model_dump() for pp in icp.pain_points]),
        "icpScore": icp.icp_score,
        "icpTier": icp.icp_tier,
        "icpReasoning": icp.icp_reasoning,
        "scoreConfidence": icp.score_confidence,
        "scoreBreakdown": icp.score_breakdown.model_dump(),
        "scoringVersion": SCORING_VERSION,
        "missingData": icp.missing_data,
        # Copy fields are None when the score fell below COPY_SCORE_FLOOR
        # (see prism/pipeline.py). Explicit nulls so re-runs reset stale copy.
        "heroHeadline":   copy.hero_headline       if copy else None,
        "subheadline":    copy.subheadline         if copy else None,
        "valueProp":      copy.value_prop_one_liner if copy else None,
        "painParagraph":  copy.pain_paragraph      if copy else None,
        "ctaPrimary":     copy.cta_primary.model_dump() if copy else None,
        "ctaSecondary":   (copy.cta_secondary.model_dump() if copy and copy.cta_secondary else None),
        "dataConfidence": data_confidence,
        "sourceUrl": source_url,
        "pagesScraped": pages_scraped,
        "hubspotCompanyId": "",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }

    logger.info(f"[SANITY] upserting {doc_id}")
    await _post_mutations({"mutations": [{"createOrReplace": doc}]})
    logger.success(f"[SANITY] wrote {doc_id}")
    return doc_id


async def patch_hubspot_backlink(doc_id: str, hubspot_company_id: str) -> None:
    """Cheap patch — write only the HubSpot ID, don't replace the whole doc."""
    payload = {
        "mutations": [
            {"patch": {"id": doc_id, "set": {"hubspotCompanyId": hubspot_company_id}}}
        ]
    }
    logger.info(f"[SANITY] patching hubspotCompanyId on {doc_id}")
    await _post_mutations(payload)


def get_sanity_doc_url(doc_id: str) -> str:
    return f"https://{SANITY_PROJECT_ID}.sanity.studio/{SANITY_STUDIO_PATH}/companyAnalysis;{doc_id}"
