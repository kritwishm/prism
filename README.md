```
 ╔════════════════════════════════════════════════════════════════════╗
 ║                                                                    ║
 ║   P R I S M                                                        ║
 ║   account research → personalized content pipeline                 ║
 ║                                                                    ║
 ║   one URL in → ICP score + intent themes + page-ready copy out     ║
 ║                across HubSpot + Sanity + local JSON                ║
 ║                                                                    ║
 ╚════════════════════════════════════════════════════════════════════╝
```

---

## the board

```
                           ┌────────────┐
   one company URL  ─────▶ │  SCRAPER   │  Jina Reader, layered discovery
                           └─────┬──────┘
                                 │ sitemap.xml ──┐
                                 │ homepage links ┤ → ≤10 pages, role-tagged
                                 │ keyword paths  ┘
                                 ▼
                ┌──────────────────────────────────┐
                │  AGENT 1   ▸  EXTRACTOR          │  facts only, no copy
                │            (Claude Sonnet, tool-use)
                └──────────────┬───────────────────┘
                               ▼
                ┌──────────────────────────────────┐
                │  AGENT 2   ▸  ICP SCORER         │  5-factor weighted rubric
                │            (Claude Sonnet, tool-use)
                └──────────────┬───────────────────┘
                               ▼
                ┌──────────────────────────────────┐
                │  AGENT 3   ▸  COPYWRITER         │  hero/sub/pain/CTA
                │            (Claude Sonnet, tool-use)
                └──────────────┬───────────────────┘
                               │
            ┌──────────────────┼──────────────────┐
            ▼                  ▼                  ▼
        ┌────────┐       ┌──────────┐      ┌───────────┐
        │ SANITY │       │  HUBSPOT │      │ local JSON│
        │  CMS   │ ◀──── │  CRM     │      │  --dump   │
        └────────┘       └──────────┘      └───────────┘
         full doc        AE-facing fields    audit/replay
         + page copy     + ICP summary       + full payload
```

---

## the scoring formula  ☆   (deterministic — `prism/scoring.py`)

```
   LLM CLASSIFIES                  PYTHON SCORES
   ──────────────                  ─────────────
                                   
   facts ──▶ classify factors ──▶ lookup table ──▶ sum ──▶ tier
              into enums            (per factor)
              + evidence
              + confidence
```

The LLM never emits numbers. It picks one enum value per factor (e.g.
`HEALTH_PLAN`, `OVER_1M`, `RUNS_MULTI_STATE_NETWORK`). A pure Python
function in `scoring.py` maps each enum to its point value and sums.

WHY split this way:

```
   ┌──────────────────────────────────────────────────────────────┐
   │ AUDITABLE     read scoring.py → know exactly how scores form │
   │ REPRODUCIBLE  same signals → same score, every time          │
   │ TUNABLE       reweight a factor by editing a constant        │
   │ TESTABLE      score_company(synthetic_signals) == expected   │
   │ A/B-ABLE     ship SCORING_VERSION v2.0, route a cohort,     │
   │               measure which formula better predicts win rate │
   │ EVALUABLE     signal extraction quality + formula correctness│
   │               become independent evals                       │
   └──────────────────────────────────────────────────────────────┘
```

### the formula

```
  ICP_SCORE  =  INDUSTRY_POINTS[industry_signal.category]      (max 30)
             +  SCALE_BAND_POINTS[scale.member_count_band]
                  + ENTERPRISE_BONUS  if has_enterprise_customers
                  + NAMED_BONUS       if has_named_customers
                  (capped at 25)
             +  NETWORK_POINTS[provider_network.network_type]  (max 25)
             +  GROWTH_POINTS[growth.stage]                    (max 10)
             +  READINESS_POINTS[buying_readiness.level]       (max 10)
             ─────────────────────────────────────────────────
             =  total                                          (0–100)

         ┌─────────┬─────────────────────────────────────────────────┐
         │ Tier A  │  90–100   elite fit                             │
         │ Tier B  │  70– 89   strong fit                            │
         │ Tier C  │  40– 69   adjacent                              │
         │ Tier D  │   0– 39   misfit                                │
         └─────────┴─────────────────────────────────────────────────┘
```

### the lookup tables

```
   INDUSTRY (max 30)                          NETWORK (max 25)
   ────────────────                           ────────────────
   HEALTH_PLAN              29                RUNS_MULTI_STATE_NETWORK  24
   DIGITAL_HEALTH_CLINICAL  25                MANAGES_FOR_PARTNERS      19
   STAFFING_IPA_MSO         19                PROVIDERS_PERIPHERAL      13
   ADJACENT_HEALTHCARE      13                TANGENTIAL                 7
   HEALTHCARE_ADJACENT       7                NONE                       2
   NOT_HEALTHCARE            2

   SCALE band (max 22 base)                   GROWTH (max 10)
   ────────────────                           ────────────────
   OVER_1M       22                           HYPER_GROWTH         10
   100K_TO_1M    17                           ACTIVE_GROWTH         7
   10K_TO_100K   11                           STABLE                4
   UNDER_10K      6                           FLAT_OR_CONTRACTING   1
   PRE_REVENUE    2
   UNKNOWN       10  (conservative midpoint)  READINESS (max 10)
                                              ────────────────
   + ENTERPRISE_BONUS  +3  (if has_enterprise)EXPLICIT          10
   + NAMED_BONUS       +1  (if has_named)     STRONG_THEMES      7
   capped at 25                               ADJACENT_THEMES    4
                                              NONE               1
```

### why these weights

```
  FACTOR              │ MAX │ WHY THIS WEIGHT
  ────────────────────┼─────┼──────────────────────────────────────────
  industry_fit        │ 30  │ if not healthcare-with-providers, nothing
                      │     │ else matters → highest single weight
  scale_signals       │ 25  │ determines deal size. 1M-life plan ≫
                      │     │ 10K-life plan in revenue terms
  provider_network    │ 25  │ THE literal use case. without it they're
                      │     │ "healthcare" but not "buyer"
  growth_maturity     │ 10  │ affects urgency, not fit. fast growth
                      │     │ feels credentialing pain harder
  buying_readiness    │ 10  │ stated pains predict WHEN not WHETHER.
                      │     │ tells AE where to prioritize
```

### what gets returned per factor

```
   {
     score        int     points awarded by the formula
     rationale    str     "[enum_value] {evidence from facts}"
     confidence   0-100   LLM's confidence in its enum classification
                            90+  directly stated
                            70+  strongly implied
                            50+  reasonable inference
                            <30  speculative
   }
```

Plus an overall **score_confidence**, computed as a weighted average of
the five signal-level confidences (weights mirror factor caps).

```
   data_confidence    →  scrape completeness (high / med / low)
   score_confidence   →  weighted avg of signal confidences (0–100)

                       data_confidence
                      LOW  MED  HIGH
                    ┌─────┬─────┬─────┐
   score_conf  LOW  │ 🤷  │ ⚠️   │ ⚠️   │   facts are there but model
                    │     │     │     │   couldn't classify cleanly
                    ├─────┼─────┼─────┤
   score_conf  MED  │ ⚠️   │ ✓   │ ✓✓  │
                    ├─────┼─────┼─────┤
   score_conf HIGH  │ ❌   │ ✓✓  │ ✓✓✓ │   trust this row
                    └─────┴─────┴─────┘
```

### worked examples (from the unit harness)

```
   shape                 industry  scale  net  grw  rdy  =  TIER
   ─────────────────────────────────────────────────────────────
   oscar-like              29/30   25/25 24/25  7   7    92  A
   oncohealth-like         25/30   25/25 24/25  7   4    85  B
   alma-like               25/30   11/25 24/25  7   7    74  B
   ehr-vendor              13/30   20/25 13/25  4   4    54  C
   glossier                 2/30   11/25  2/25  4   1    20  D
```

### `SCORING_VERSION` is stamped on every record

In Sanity (`scoringVersion`) and HubSpot (`prism_scoring_version`). Old
scores stay comparable across formula changes; downstream eval can hold
the version constant to isolate signal-quality drift from formula drift.

---

## the data model

### what lives where, and WHY

```
                      ┌──────────────┐
                      │   facts +    │     full structured payload
                      │   icp +      │     editable by marketers
                      │   copy       │     → drives /p/{slug} render
   SANITY  ◀──────────│  (full doc)  │     keyed: companyAnalysis.<slug>
                      └──────────────┘     mutation: createOrReplace
                            ▲
                            │
                            │  prism_sanity_url  (the bridge)
                            │
                            ▼
                      ┌──────────────┐
                      │  ICP score   │     surface AEs actually look at
                      │  ICP tier    │     in their daily workflow
   HUBSPOT ◀──────────│  intent      │     keyed: domain
                      │  + reasoning │     mutation: search → upsert
                      │  + breakdown │     ⚠️ industry: NOT written
                      └──────────────┘        (HubSpot enum mismatch)
                            ▲
                            │
   LOCAL JSON  ◀────────────┘     audit/replay/share without API access
   examples/runs/*.json           summary + scrape + facts + icp + copy
```

### split rationale

```
   "why not put everything in HubSpot?"
                    │
                    ▼
      HubSpot is good at:  structured scalar fields, custom props
      HubSpot is bad at:   long-form, nested objects (pain_points
                           = array of {pain, evidence, confidence})

   "why not put everything in Sanity?"
                    │
                    ▼
      Sanity is where the CONTENT lives (marketers edit there)
      HubSpot is where ACCOUNT OWNERS work (AEs live there)

   → bridge them. don't duplicate them.
```

### HubSpot custom properties (the 9)

```
  prism_icp_score            number    │  the 0-100 number
  prism_icp_tier             string    │  A / B / C / D
  prism_icp_reasoning        textarea  │  why this score (≤400 chars)
  prism_score_confidence     number    │  0-100, how sure
  prism_score_breakdown      textarea  │  5-factor expanded view
  prism_intent_themes        textarea  │  "theme (78%), theme (72%), …"
  prism_one_line             string    │  elevator pitch
  prism_data_confidence      string    │  high / medium / low
  prism_sanity_url           string    │  → full doc in Sanity
```

---

## decisions  ▸  WHY  ▸  REJECTED

```
   ┌─────────────────────┬──────────────────────────┬────────────────────┐
   │ Jina Reader scrape  │ rendering + cleaning in  │ Playwright chain — │
   │                     │ one call — saves 60 min  │ overkill for POC   │
   ├─────────────────────┼──────────────────────────┼────────────────────┤
   │ 3 Claude calls, not │ each call has ONE job —  │ mega-prompt mixes  │
   │ one mega-prompt     │ inspectable, evaluable,  │ concerns; orches-  │
   │                     │ cost-tierable later      │ tration overkill   │
   ├─────────────────────┼──────────────────────────┼────────────────────┤
   │ Claude tool-use +   │ schema enforced at API   │ free-form JSON     │
   │ Pydantic validate   │ + retry on validation    │ parse — fragile    │
   ├─────────────────────┼──────────────────────────┼────────────────────┤
   │ 5-factor explicit   │ defensible per-factor;   │ vibes-only LLM     │
   │ scoring rubric      │ debuggable; can A/B      │ score — opaque,    │
   │                     │ each weight              │ no eval surface    │
   ├─────────────────────┼──────────────────────────┼────────────────────┤
   │ Layered URL         │ real sites use           │ hardcoded path     │
   │ discovery           │ /our-story, /why, etc.   │ list — misses non- │
   │ (sitemap + links)   │                          │ standard layouts   │
   ├─────────────────────┼──────────────────────────┼────────────────────┤
   │ HubSpot props       │ AEs work on the company  │ HubSpot custom     │
   │ (not custom obj)    │ record. Properties show  │ object — heavier,  │
   │                     │ on standard views        │ hard to find       │
   ├─────────────────────┼──────────────────────────┼────────────────────┤
   │ Python (for now)    │ fastest path to working  │ TypeScript — would │
   │                     │ pipeline; LLM tooling is │ unify w/ Sanity +  │
   │                     │ Python-native            │ Next.js. v2 move.  │
   └─────────────────────┴──────────────────────────┴────────────────────┘
```

---

## failure modes ▸ what breaks first under load

```
   ┌─ #1 ─────────────────────────────────────────────────────────┐
   │ PROMPT DRIFT on Claude version bumps                         │
   │   ▸ schema breaks silently when model gets newly verbose     │
   │   ▸ tool-input field types shift                             │
   │   FIX: eval harness in CI + pinned model versions            │
   │         + retry-with-error-feedback (already in agents.py)   │
   └──────────────────────────────────────────────────────────────┘

   ┌─ #2 ─────────────────────────────────────────────────────────┐
   │ HUBSPOT SEARCH RATE LIMITS                                   │
   │   ▸ _find_company_by_domain is the first to throttle         │
   │   FIX: semaphore + exponential backoff                       │
   │         + pre-load existing domains at batch start           │
   └──────────────────────────────────────────────────────────────┘

   ┌─ #3 ─────────────────────────────────────────────────────────┐
   │ JINA RATE LIMITS + AGGRESSIVE ANTI-BOT SITES                 │
   │   ▸ free tier ~20 RPM; some sites Cloudflare-block entirely  │
   │   FIX: confidence flag downgrade → propagates to HubSpot;    │
   │         hard abort before LLM spend if 0 pages succeed;      │
   │         self-host Browserless for the long tail              │
   └──────────────────────────────────────────────────────────────┘
```

### three layers of degradation in the scraper

```
   per-page failure   →   one 403 doesn't kill the run
        │
        ▼
   confidence flag    →   high (≥3 pages) / medium (1-2) / low (0)
        │                 propagates ALL the way to HubSpot AE view
        ▼
   hard abort         →   0 pages → return before LLM call
                          (no slop generation on blocked sites)
```

---

## sites that block scraping / return thin content

```
   site type              │ behavior                  │ confidence
   ───────────────────────┼───────────────────────────┼───────────
   normal SPA             │ Jina renders + cleans     │ HIGH
   JS-heavy + slow        │ partial pages succeed     │ MED
   Cloudflare blocked     │ all 403, pipeline aborts  │ LOW
   thin marketing site    │ <100 chars/page = drop    │ LOW
```

At scale → self-hosted Browserless for cooperative-but-weird sites.
Unreachable sites → flag for manual research, don't fake it.

---

## scaling to hundreds of accounts

```
   ┌──────────────────────────────────────────────────────────────┐
   │  TODAY                       AT 1K/MONTH         AT 10K/MONTH│
   ├──────────────────────────────┼───────────────────┼───────────┤
   │ sequential CLI               │ queue + workers   │ same +    │
   │                              │ (SQS/BullMQ)      │ region-   │
   │                              │                   │ aware     │
   │ no per-domain lock           │ per-domain lock   │ same      │
   │                              │ (prevent races on │           │
   │                              │  upsert)          │           │
   │                              │                   │           │
   │ no caching                   │ 7d scrape cache   │ prompt-   │
   │                              │                   │ version   │
   │                              │                   │ keyed LLM │
   │                              │                   │ cache     │
   │                              │                   │           │
   │ Sonnet on all 3 agents       │ same              │ Haiku on  │
   │                              │                   │ extractor │
   │                              │                   │ (tiering) │
   │                              │                   │           │
   │ cost ≈ $0.05/company         │ ≈ $15/mo LLM      │ ≈ $80/mo  │
   └──────────────────────────────┴───────────────────┴───────────┘
```

---

## extending the signal layer ▸ Gong + Salesforce

```
   today                          tomorrow
   ─────                          ────────
   scrape only                    scrape  ──┐
   = "what they say               Gong    ──┼──▶  account_signals
      publicly"                   SFDC    ──┘     (Postgres / DuckDB,
                                                   keyed: domain)
                                                        │
                                                        ▼
                                                  ICP scorer becomes
                                                  multi-source synthesizer

   ┌────────────────┬──────────────────────────────────────────────┐
   │ GONG           │ transcript-derived = highest signal-to-effort│
   │                │ "credentialing pain mentioned 3× on a call"  │
   │                │ is worth 50 website scrapes                  │
   ├────────────────┼──────────────────────────────────────────────┤
   │ SALESFORCE     │ behavior, not intent. opens, meeting density,│
   │                │ contact role spread, opp stage transitions.  │
   │                │ → behavioral lift on the ICP score           │
   │                │ → quiet Tier A < engaged Tier B (often)      │
   ├────────────────┼──────────────────────────────────────────────┤
   │ COPY GROUNDING │ copywriter now references real customer      │
   │                │ language from Gong, not just public marketing│
   └────────────────┴──────────────────────────────────────────────┘

   BUILD ORDER:  Gong first. Best ratio.
```

---

## triggering page renders from Sanity

```
                                   webhook on publish
   ┌───────────────┐                        ▼
   │ Sanity Studio │ ───▶ doc publish ───▶ Next.js endpoint
   └───────────────┘                        │
        marketer                            │ ISR revalidate
        edits copy                          ▼
        previews live                ┌─────────────────┐
        clicks publish               │  /p/oscar-com   │
                                     │  /p/devoted-com │
                                     │  /p/{slug}      │
                                     └─────────────────┘
                                       reads via GROQ
                                       UTM-aware analytics
                                       → engagement signal
                                         feeds back into
                                         ICP score
```

Schema is already shaped for A/B variants (extend `personalizedPage` array
with experiment IDs).  Not built — 3-4 hours on the Next.js side.

---

## measurement ▸ four layers

```
   LAYER 1  SYSTEM HEALTH
   ─────────────────────────────────────────────────────────────
     scrape success rate     latency p50 / p95
     LLM parse success rate  cost per company  ← catches drift
     write success rate

   LAYER 2  CONTENT QUALITY (proxy)
   ─────────────────────────────────────────────────────────────
     5% manual review against anti-fluff rubric
     LLM-as-judge to scale
     track trend across prompt changes

   LAYER 3  PIPELINE IMPACT (causal)
   ─────────────────────────────────────────────────────────────
     INBOUND   50% personalized, 50% generic → demo book rate
     OUTBOUND  prism copy vs templated → reply rate, meeting rate
     HOLDOUT  is non-negotiable. without it, every uplift is suspect.

   LAYER 4  REVENUE (the only one that matters)
   ─────────────────────────────────────────────────────────────
     closed-won attributable to prism accounts vs not
     90d rolling win rate by ICP tier
       ▸ if A doesn't beat C, the scorer is decorative
```

```
   gut metric:  are AEs OPENING the Sanity research doc before
                their first call?
                  high open + better win rate  →  it works
                  ignored                      →  it's slop dressed
                                                   up as intelligence
                                                   (worse than no system)
```

---

## quickstart

```
   git clone <repo> && cd prism
   cp .env.example .env                # fill in keys
   python -m venv .venv && source .venv/bin/activate
   pip install -e .                    # or: pip install -r requirements.txt

   # first time only:
   python scripts/bootstrap_hubspot.py     # creates the 9 custom props
   # → and deploy sanity/schemaTypes/* in your Studio

   python run.py analyze https://www.hioscar.com --dump examples/runs
   python run.py analyze https://www.glossier.com --dump examples/runs

   # batch:
   python run.py batch urls.txt --dump examples/runs
```

See `SETUP.md` for HubSpot/Sanity provisioning details.

---

## repo map

```
   prism/
   ├─ README.md              ◀── you are here
   ├─ SETUP.md                   provisioning
   ├─ CLAUDE.md                  module boundaries + conventions
   ├─ pyproject.toml / requirements.txt
   ├─ .env.example
   ├─ run.py                     typer CLI
   │
   ├─ prism/
   │  ├─ models.py               Pydantic — single source of truth
   │  ├─ scraper.py              Jina + sitemap/link discovery
   │  ├─ agents.py               3 Claude calls + retry + tool-use
   │  ├─ sanity_client.py        Sanity HTTP API
   │  ├─ hubspot_client.py       HubSpot SDK
   │  ├─ pipeline.py             orchestrator
   │  └─ config.py               env + constants
   │
   ├─ sanity/schemaTypes/        drop into your Sanity Studio
   ├─ scripts/bootstrap_hubspot.py  idempotent property setup
   ├─ evals/README.md            eval harness design (sketch)
   └─ examples/runs/             JSON snapshots of real runs
```

---

## not built (yet)

```
   ✗  eval harness in CI               ← biggest gap; designed in evals/
   ✗  Playwright fallback layer        ← Browserless at scale
   ✗  scrape + LLM caching             ← required >100/day
   ✗  queue + worker pool              ← required >1K/day
   ✗  HubSpot → Sanity webhook         ← closed-loop attribution
   ✗  human-in-the-loop edit flow      ← AI original vs human-edited
   ✗  Next.js rendering layer
   ✗  Gong + Salesforce ingestion      ← biggest quality lever
   ✗  unit tests                       ← golden-fixture evals first
```

---

## next moves

```
   1.  Gong signal ingestion   ◀── biggest quality lever
   2.  eval harness in CI      ◀── stop prompt drift
   3.  Next.js render layer    ◀── close the demo loop
   4.  closed-loop attribution ◀── grade copy by outcome
   5.  caching + queue         ◀── scale unlock
   6.  model tiering           ◀── cost unlock at 10K+/mo
```
