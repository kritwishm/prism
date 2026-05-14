# CLAUDE.md — engineering practices for this repo

This file is read by Claude Code (and human contributors) when working on
this repository. It's the short, opinionated answer to "how do we work
here?"

---

## 1. What this codebase is

A 3-stage Claude pipeline (extractor → ICP scorer → copywriter) that turns
a company URL into structured ICP intelligence and personalized landing
page content, then writes those into Sanity (CMS) and HubSpot (CRM).

Designed for a take-home, so:
- Optimized for **legibility over abstraction**
- Each module has a single job and ≤200 lines
- No frameworks where a function will do

---

## 2. Module boundaries (don't muddle them)

| Module | Owns | Does NOT |
|---|---|---|
| `config.py` | Env loading, constants, fail-fast validation | Business logic |
| `models.py` | Pydantic schemas — single source of truth for data shapes | API calls, side effects |
| `scraper.py` | Fetching + cleaning page content; URL discovery | LLM calls, downstream writes |
| `agents.py` | Three Claude calls + structured-output parsing + retry | Knowing about Sanity, HubSpot, or HTTP. The ICP score itself — that's `scoring.py`. |
| `scoring.py` | Deterministic 5-factor ICP scoring from LLM-extracted signals | Calling the LLM (it's pure functions) |
| `sanity_client.py` | Sanity Content Lake writes | Calling the LLM, calling HubSpot |
| `hubspot_client.py` | HubSpot SDK calls | Knowing about Sanity, calling the LLM |
| `pipeline.py` | Wiring the stages together, optional run-dump | Implementing any one stage |
| `run.py` | CLI surface only (typer) | Any business logic |

If you're tempted to import `hubspot_client` from `agents.py`, stop. The
agent chain is provider-agnostic — that's a feature.

---

## 3. Coding conventions

- **Pydantic is the contract.** All inter-stage handoffs are typed
  Pydantic models. The Sanity schema mirrors them, the HubSpot properties
  mirror a subset. Never pass dicts between stages — if you need a new
  field, add it to a model in `models.py` first.
- **Logging is the UX.** loguru with stage prefixes (`[SCRAPE]`,
  `[AGENT 1]`, `[SANITY]`, `[HUBSPOT]`, `[PIPELINE]`). The Loom demo reads
  the log directly — keep it clean and informative.
- **Fail fast on config.** `config.py` raises on missing env vars at
  import time. Don't move that into a deferred path.
- **Defensive at boundaries, trustful within.** Wrap external calls
  (Jina, HubSpot, Sanity, Anthropic) in try/except and log. Don't wrap
  pure Python calls between modules — let typing catch those.
- **Async only where it matters** (httpx for I/O). Anthropic calls are
  sync in this build — three short calls don't need async; clarity wins.

---

## 4. Prompts

- All prompts live as string constants in `agents.py`. No prompt files,
  no template engines. Three prompts, three pages, easy to diff.
- Tool input schemas are derived from Pydantic models via
  `model.model_json_schema()`. Don't hand-write them — Pydantic is the
  source of truth.
- Anti-fluff word list lives in the copywriter system prompt. When you
  see slop in outputs, expand it there.

---

## 5. When something fails

Failure | Right move | Wrong move
---|---|---
LLM returns invalid JSON | The one-shot retry in `_call_claude_structured` already handles this | Add more retries (creates infinite-loop risk on systemic failures)
Sanity write fails | Abort pipeline before HubSpot write | Write to HubSpot anyway and "fix later"
HubSpot write fails | Sanity doc exists; log the orphan id | Roll back the Sanity write (creates more partial state, not less)
Scraping fails entirely | Abort before LLM spend | Generate copy from nothing
Pydantic validation fails | Retry once with error fed back into the prompt | Loosen the schema

---

## 6. Adding a new stage / model / field

1. Add the field to the relevant model in `models.py`.
2. If it's an LLM output, update the prompt in `agents.py` and the field
   shows up in the tool schema automatically (Pydantic → JSON Schema).
3. Update `sanity/schemaTypes/companyAnalysis.ts` to mirror.
4. Update `sanity_client.py` to write the field.
5. If it should land on HubSpot too: add a custom property in the
   HubSpot dashboard (document the name in `SETUP.md`) and add the line
   to `hubspot_client.upsert_company`.

No silent skips. If a downstream system isn't ready, the pipeline should
either write `null`/empty or fail loud.

---

## 7. What NOT to do

- Don't add tests as the first move — the build is intentionally
  test-light. If you add tests, start with one golden-fixture eval per
  agent in `evals/`, not unit tests on plumbing.
- Don't introduce a framework (LangChain, LlamaIndex, an agents
  orchestrator). The whole point of three explicit Claude calls is
  legibility.
- Don't add caching without versioning the cache key by prompt hash. A
  cache that survives a prompt change is a bug factory.
- Don't catch exceptions silently. Log them with the stage prefix at
  warning or error level. The Loom demo will show them.
- Don't add markdown files Claude wasn't asked to create.

---

## 8. Where things are

```
prism/agents.py            three Claude calls + retry + tool-use
prism/scraper.py           Jina + sitemap/link discovery
prism/models.py            Pydantic — start here when changing data shape
prism/pipeline.py          wiring + run dump
sanity/schemaTypes/        Sanity Studio schema (mirrors models.py)
SETUP.md                   one-time provisioning
evals/                     eval harness sketch (not built)
examples/runs/             JSON snapshots of real runs
```
