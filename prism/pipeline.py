import json
from pathlib import Path
from typing import Optional

from loguru import logger

from .agents import run_copywriter, run_extractor, run_icp_scorer
from .hubspot_client import upsert_company
from .sanity_client import (
    get_sanity_doc_url,
    patch_hubspot_backlink,
    upsert_company_analysis,
)
from .scoring import COPY_SCORE_FLOOR
from .scraper import scrape_company


async def run_pipeline(url: str, dump_dir: Optional[str] = None) -> dict:
    logger.info(f"\n{'=' * 60}\n[PIPELINE] starting for {url}\n{'=' * 60}")

    # Stage 1: scrape
    scrape = await scrape_company(url)
    if scrape.pages_succeeded == 0:
        logger.error("[PIPELINE] no pages scraped — aborting before LLM spend")
        return {"success": False, "error": "scraping_failed", "domain": scrape.domain}

    # Stage 2: agent chain (sync calls — Anthropic SDK)
    facts = run_extractor(scrape)
    icp = run_icp_scorer(facts, scrape.confidence)

    # Stage 2b: gate the copywriter on ICP score. Below the floor, we don't
    # commit to copy at all — score + reasoning are still useful for "don't
    # pursue" decisions, but auto-generated copy on a misfit is worse than
    # no copy (see prism/scoring.py:COPY_SCORE_FLOOR).
    if icp.icp_score >= COPY_SCORE_FLOOR:
        copy = run_copywriter(facts, icp)
    else:
        copy = None
        logger.info(
            f"[PIPELINE] skipping copywriter — score {icp.icp_score} "
            f"below floor {COPY_SCORE_FLOOR} (Tier {icp.icp_tier})"
        )

    # Stage 2.5: dump JSON immediately so a downstream write failure
    # doesn't cost us the LLM work.
    if dump_dir:
        _dump_run(
            dump_dir, scrape, facts, icp, copy,
            summary={"domain": scrape.domain, "icp_score": icp.icp_score,
                     "icp_tier": icp.icp_tier, "data_confidence": scrape.confidence,
                     "hubspot_id": None, "sanity_url": None, "writes_complete": False},
        )

    # Stage 3: Sanity write — ONLY for accounts at or above the floor.
    # Sub-floor accounts go to HubSpot only (the ICP score + reasoning is
    # still useful for "don't pursue" calls). Keeping Sanity clean of
    # misfits means the marketer queue is the actionable queue.
    if icp.icp_score >= COPY_SCORE_FLOOR:
        sanity_doc_id = await upsert_company_analysis(
            domain=scrape.domain,
            facts=facts,
            icp=icp,
            copy=copy,
            source_url=url,
            pages_scraped=scrape.pages_succeeded,
            data_confidence=scrape.confidence,
        )
        sanity_url = get_sanity_doc_url(sanity_doc_id)
    else:
        sanity_doc_id = None
        sanity_url = ""
        logger.info(
            f"[PIPELINE] skipping Sanity write — score {icp.icp_score} "
            f"below floor {COPY_SCORE_FLOOR} (Tier {icp.icp_tier})"
        )

    # Stage 4: HubSpot write
    hubspot_id = upsert_company(
        domain=scrape.domain,
        facts=facts,
        icp=icp,
        sanity_url=sanity_url,
        data_confidence=scrape.confidence,
    )

    # Stage 5: backlink HubSpot id into Sanity (only when a Sanity doc exists)
    if sanity_doc_id:
        try:
            await patch_hubspot_backlink(sanity_doc_id, hubspot_id)
        except Exception as e:
            logger.warning(f"[PIPELINE] sanity backlink patch failed (non-fatal): {e}")

    result = {
        "success": True,
        "domain": scrape.domain,
        "company_name": facts.company_name,
        "icp_score": icp.icp_score,
        "icp_tier": icp.icp_tier,
        "hubspot_id": hubspot_id,
        "sanity_url": sanity_url,
        "data_confidence": scrape.confidence,
    }

    if dump_dir:
        _dump_run(dump_dir, scrape, facts, icp, copy, result)

    logger.success(f"\n[PIPELINE] ✓ complete for {scrape.domain}")
    logger.success(f"  company: {facts.company_name}")
    logger.success(f"  ICP: {icp.icp_score} (tier {icp.icp_tier})")
    logger.success(f"  hubspot id: {hubspot_id}")
    logger.success(f"  sanity doc: {sanity_url}")

    return result


def _dump_run(dump_dir: str, scrape, facts, icp, copy, summary: dict) -> None:
    out = Path(dump_dir)
    out.mkdir(parents=True, exist_ok=True)
    slug = scrape.domain.replace(".", "-")
    payload = {
        "summary": summary,
        "scrape": {
            "domain": scrape.domain,
            "pages_attempted": scrape.pages_attempted,
            "pages_succeeded": scrape.pages_succeeded,
            "confidence": scrape.confidence,
            "page_urls": [p["url"] for p in scrape.pages],
        },
        "facts": facts.model_dump(),
        "icp": icp.model_dump(),
        "copy": copy.model_dump() if copy else None,
    }
    (out / f"{slug}.json").write_text(json.dumps(payload, indent=2))
    logger.info(f"[PIPELINE] dumped run to {out / (slug + '.json')}")
