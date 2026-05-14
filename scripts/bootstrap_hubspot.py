"""One-time: create the 7 prism_* custom properties on HubSpot Companies.

Requires the Private App token to have `crm.schemas.companies.write` in
addition to the read/write company scopes. Idempotent — already-existing
properties are skipped.
"""
from __future__ import annotations

import sys

from hubspot import HubSpot
from hubspot.crm.properties.exceptions import ApiException
from loguru import logger

# fmt: off
sys.path.insert(0, ".")
from prism.config import HUBSPOT_ACCESS_TOKEN  # noqa: E402
# fmt: on

client = HubSpot(access_token=HUBSPOT_ACCESS_TOKEN)

PROPERTIES = [
    {"name": "prism_intent_themes",   "label": "Prism: Intent Themes",     "type": "string",  "fieldType": "textarea",   "groupName": "companyinformation"},
    {"name": "prism_icp_score",       "label": "Prism: ICP Score",         "type": "number",  "fieldType": "number",     "groupName": "companyinformation"},
    {"name": "prism_icp_tier",        "label": "Prism: ICP Tier",          "type": "string",  "fieldType": "text",       "groupName": "companyinformation"},
    {"name": "prism_icp_reasoning",   "label": "Prism: ICP Reasoning",     "type": "string",  "fieldType": "textarea",   "groupName": "companyinformation"},
    {"name": "prism_one_line",        "label": "Prism: One-Line Summary",  "type": "string",  "fieldType": "text",       "groupName": "companyinformation"},
    {"name": "prism_sanity_url",      "label": "Prism: Sanity Doc URL",    "type": "string",  "fieldType": "text",       "groupName": "companyinformation"},
    {"name": "prism_data_confidence", "label": "Prism: Data Confidence",   "type": "string",  "fieldType": "text",       "groupName": "companyinformation"},
    {"name": "prism_score_confidence","label": "Prism: ICP Score Confidence","type": "number","fieldType": "number",     "groupName": "companyinformation"},
    {"name": "prism_score_breakdown", "label": "Prism: Score Breakdown",   "type": "string",  "fieldType": "textarea",   "groupName": "companyinformation"},
    {"name": "prism_scoring_version", "label": "Prism: Scoring Version",   "type": "string",  "fieldType": "text",       "groupName": "companyinformation"},
]


def main() -> int:
    created, skipped, failed = 0, 0, 0
    for spec in PROPERTIES:
        try:
            client.crm.properties.core_api.create(
                object_type="companies",
                property_create=spec,
            )
            logger.success(f"created {spec['name']}")
            created += 1
        except ApiException as e:
            body = getattr(e, "body", "") or ""
            if "PROPERTY_ALREADY_EXISTS" in body or e.status == 409:
                logger.info(f"skipping {spec['name']} (already exists)")
                skipped += 1
            else:
                logger.error(f"FAILED {spec['name']}: {e.status} {body[:200]}")
                failed += 1
    logger.info(f"done: {created} created, {skipped} skipped, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
