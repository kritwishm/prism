# Setup

End-to-end provisioning steps to get Prism running. Plan for ~20 minutes
of dashboard clicking, the first time.

---

## 1. API keys

| Service | Where to get the key | Notes |
|---|---|---|
| Anthropic | https://console.anthropic.com → API Keys | Required. Sonnet 4.x for all 3 agents. |
| Jina | https://jina.ai/?sui=apikey | Optional but recommended for higher rate limits. Free tier is fine. |
| HubSpot | Settings → Integrations → **Private Apps** → Create | Scopes: `crm.objects.companies.read`, `crm.objects.companies.write` |
| Sanity | https://sanity.io/manage → your project → API → Tokens | Editor role minimum. |

Drop them into `.env` (copy from `.env.example`).

---

## 2. HubSpot custom properties

In **HubSpot → Settings → Properties → Company Properties → Create property**, create these 7. Internal names must match exactly:

| Internal name | Label | Field type | Group |
|---|---|---|---|
| `prism_intent_themes` | Prism: Intent Themes | Multi-line text | Information |
| `prism_icp_score` | Prism: ICP Score | Number | Information |
| `prism_icp_tier` | Prism: ICP Tier | Single-line text | Information |
| `prism_icp_reasoning` | Prism: ICP Reasoning | Multi-line text | Information |
| `prism_one_line` | Prism: One-Line Summary | Single-line text | Information |
| `prism_sanity_url` | Prism: Sanity Doc URL | Single-line text | Information |
| `prism_data_confidence` | Prism: Data Confidence | Single-line text | Information |

Verify with the HubSpot Properties API or by manually creating a test
company — all 7 should show up under "Information".

---

## 3. Sanity project + schema

```bash
# in a separate directory
npm create sanity@latest -- --template clean --create-project "Prism" --dataset production
cd <new-sanity-folder>
```

Copy `sanity/schemaTypes/companyAnalysis.ts` and
`sanity/schemaTypes/index.ts` from this repo into your Studio's
`schemaTypes/` folder. Then:

```bash
npm install
sanity dev    # local studio
# or
sanity deploy  # hosted studio
```

Grab `projectId` (from `sanity.config.ts`) and create an Editor-role token
at sanity.io/manage. Put both into `.env`.

`SANITY_STUDIO_PATH` is `desk` (Studio v2) or `structure` (Studio v3+).
Default is `desk`.

---

## 4. Install Prism

```bash
git clone <repo>
cd prism
python -m venv .venv && source .venv/bin/activate
pip install -e .
# or, if you prefer requirements.txt:
pip install -r requirements.txt
```

---

## 5. Smoke test

```bash
# scraper only — no LLM, no writes
python -c "import asyncio; from prism.scraper import scrape_company; \
  r = asyncio.run(scrape_company('https://www.hioscar.com')); \
  print(r.pages_succeeded, r.confidence, r.domain)"

# full pipeline + dump the JSON output for inspection
python run.py analyze https://www.hioscar.com --dump examples/runs
python run.py analyze https://www.glossier.com --dump examples/runs
```

If both runs complete and the HubSpot/Sanity records appear, you're done.

---

## Troubleshooting

- **`Missing required env vars`**: `.env` not loaded (wrong directory) or a key is blank
- **`HubSpot property doesn't exist`**: you missed one of the 7 properties — re-check internal names
- **Sanity 401**: token doesn't have write permission; regenerate as Editor
- **Sanity 400 on `_type`**: schema isn't deployed to your Studio
- **All Jina fetches fail**: free tier rate limit hit — add `JINA_API_KEY`
