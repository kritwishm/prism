from typing import Optional

from hubspot import HubSpot
from hubspot.crm.companies import (
    SimplePublicObjectInput,
    SimplePublicObjectInputForCreate,
)
from loguru import logger

from .config import HUBSPOT_ACCESS_TOKEN
from .models import ExtractedFacts, ICPAnalysis, ScoreBreakdown
from .scoring import SCORING_VERSION

client = HubSpot(access_token=HUBSPOT_ACCESS_TOKEN)


# Max points per factor — keep in sync with ScoreBreakdown docstring.
_FACTOR_MAX = {
    "industry_fit": 30,
    "scale_signals": 25,
    "provider_network_signal": 25,
    "growth_maturity": 10,
    "buying_readiness": 10,
}


def _format_breakdown(b: ScoreBreakdown) -> str:
    """Human-readable single-string view of the 5-factor breakdown for HubSpot.
    AEs see one block of text on the company record."""
    lines = []
    for name, factor in b.model_dump().items():
        max_pts = _FACTOR_MAX.get(name, 0)
        lines.append(
            f"{name.replace('_', ' ').title()}: {factor['score']}/{max_pts} "
            f"(conf {factor['confidence']}%) — {factor['rationale']}"
        )
    return "\n".join(lines)


def _find_company_by_domain(domain: str) -> Optional[str]:
    """Best-effort search. Any failure → None (caller treats as 'no match')."""
    try:
        result = client.crm.companies.search_api.do_search(
            public_object_search_request={
                "filterGroups": [{
                    "filters": [{"propertyName": "domain", "operator": "EQ", "value": domain}]
                }],
                "limit": 1,
            }
        )
        if result.results:
            return result.results[0].id
    except Exception as e:
        # HubSpot rate limits, network blips, transient 5xx — degrade gracefully
        # by treating as "no existing match" rather than crashing the pipeline.
        logger.warning(f"[HUBSPOT] search failed (treating as no match): {e}")
    return None


def upsert_company(
    domain: str,
    facts: ExtractedFacts,
    icp: ICPAnalysis,
    sanity_url: str,
    data_confidence: str,
) -> str:
    # NOTE: HubSpot's standard `industry` field is a fixed enum
    # (HOSPITAL_HEALTH_CARE, MENTAL_HEALTH_CARE, …). LLM-extracted free-text
    # industries like "Healthcare Technology / Oncology Management" do not
    # map cleanly, so we don't write it. The rich industry analysis is in
    # the Sanity doc; `prism_one_line` carries the elevator-pitch on HubSpot.
    properties = {
        "domain": domain,
        "name": facts.company_name,
        "prism_intent_themes": ", ".join(f"{t.theme} ({t.confidence}%)" for t in icp.intent_themes),
        "prism_icp_score": icp.icp_score,  # number-typed property; SDK handles serialization
        "prism_icp_tier": icp.icp_tier,
        "prism_icp_reasoning": icp.icp_reasoning[:65000],
        "prism_score_confidence": icp.score_confidence,
        "prism_score_breakdown": _format_breakdown(icp.score_breakdown)[:65000],
        "prism_one_line": facts.one_line_description[:255],
        "prism_sanity_url": sanity_url[:255],
        "prism_data_confidence": data_confidence,
        "prism_scoring_version": SCORING_VERSION,
    }

    existing_id = _find_company_by_domain(domain)
    if existing_id:
        logger.info(f"[HUBSPOT] updating company {existing_id}")
        client.crm.companies.basic_api.update(
            company_id=existing_id,
            simple_public_object_input=SimplePublicObjectInput(properties=properties),
        )
        return existing_id

    logger.info(f"[HUBSPOT] creating company for {domain}")
    result = client.crm.companies.basic_api.create(
        simple_public_object_input_for_create=SimplePublicObjectInputForCreate(
            properties=properties
        )
    )
    return result.id
