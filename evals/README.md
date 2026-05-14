# Evals (sketch — not built)

Eval harness design for the agent chain. The point of evals here isn't accuracy
in some abstract sense — it's catching prompt regressions before they ship.

## Golden set

~30 hand-labeled companies covering:
- Tier A (true positives): Oscar, Devoted, Cityblock, Included Health
- Tier B (mid-market health plans, growth-stage digital health)
- Tier C (adjacent healthcare: RCM, EHR vendors)
- Tier D (true negatives): Glossier, Notion, generic SaaS

Each golden entry stores: domain, expected tier, expected intent themes
(soft match), one-line description (for extractor sanity).

## Three eval layers

1. **Extractor accuracy** — diff `company_name`, `industry`, `products_services`
   against ground truth. Exact match where deterministic, LLM-as-judge for the
   prose fields.
2. **ICP tier accuracy** — confusion matrix. The only hard guarantee: D should
   never be scored A, and A should never be scored D. One-tier slippage is fine.
3. **Copy quality** — LLM-as-judge with a rubric: (a) no fluff words from
   blocklist, (b) references at least one specific fact from extraction,
   (c) hero ≤80 chars, (d) honest tone for Tier D.

## Wiring

- `evals/run.py` invokes the same agents directly (no Sanity/HubSpot writes)
- Golden set in `evals/golden/*.json` — one file per domain with frozen scrape
  output so we eval the agents, not the scraper
- CI: run on every prompt change, fail the build on any A↔D flip or >20% tier
  shift across the set

Not built in v1. The structure is here so the next iteration drops straight in.
