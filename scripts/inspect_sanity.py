"""Read-only: list every companyAnalysis doc, sorted by ICP score.
Usage:  env/bin/python scripts/inspect_sanity.py [domain]

Without args: shows a compact roster of every analysis in the dataset.
With a domain arg: dumps the full doc (facts, signals, intent, pain, copy).
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, ".")
from prism.config import (  # noqa: E402
    SANITY_API_VERSION,
    SANITY_DATASET,
    SANITY_PROJECT_ID,
    SANITY_STUDIO_PATH,
    SANITY_TOKEN,
)


BASE = f"https://{SANITY_PROJECT_ID}.api.sanity.io/v{SANITY_API_VERSION}/data/query/{SANITY_DATASET}"
HEADERS = {"Authorization": f"Bearer {SANITY_TOKEN}"}


def _studio_url(doc_id: str) -> str:
    return f"https://{SANITY_PROJECT_ID}.sanity.studio/{SANITY_STUDIO_PATH}/companyAnalysis;{doc_id}"


async def _query(groq: str) -> list:
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get(BASE, params={"query": groq}, headers=HEADERS)
        r.raise_for_status()
        return r.json().get("result", [])


async def list_all() -> None:
    docs = await _query(
        "*[_type=='companyAnalysis'] | order(icpScore desc) "
        "{domain, companyName, icpScore, icpTier, scoreConfidence, oneLine, hubspotCompanyId, _id}"
    )
    if not docs:
        print("no companyAnalysis docs in this dataset")
        return

    print(f"\n{len(docs)} analyses in dataset='{SANITY_DATASET}'\n")
    print(f"  {'DOMAIN':<26}  {'TIER':<4}  {'SCORE':<5}  {'CONF':<4}  COMPANY")
    print(f"  {'-'*26}  {'-'*4}  {'-'*5}  {'-'*4}  {'-'*40}")
    for d in docs:
        tier = d.get("icpTier") or "—"
        score = d.get("icpScore")
        conf = d.get("scoreConfidence")
        print(
            f"  {(d.get('domain') or '')[:26]:<26}  "
            f"{tier:<4}  "
            f"{(str(score) if score is not None else '—'):<5}  "
            f"{(str(conf) + '%' if conf is not None else '—'):<4}  "
            f"{(d.get('companyName') or '')[:40]}"
        )
    print("\nopen any doc in Studio:")
    for d in docs[:3]:
        print(f"  {_studio_url(d['_id'])}")


async def show_one(domain: str) -> None:
    docs = await _query(
        f"*[_type=='companyAnalysis' && (domain=='{domain}' || domain match '{domain}*')]"
    )
    if not docs:
        print(f"no doc found for domain '{domain}'")
        return
    print(json.dumps(docs[0], indent=2))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        asyncio.run(show_one(sys.argv[1]))
    else:
        asyncio.run(list_all())
