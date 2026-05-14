# prism-render

Next.js renderer that turns Sanity `companyAnalysis` docs into live
personalized landing pages at `/p/{slug}`.

This is the third piece of the system, sitting after the Python pipeline
writes to Sanity. End-to-end flow:

```
   URL ──▶ Python pipeline ──▶ Sanity ──▶ this app ──▶ /p/{slug}
                                  │
                                  └──webhook──▶ /api/revalidate
```

## Routes

| Route | What it does |
|---|---|
| `/` | Ranked list of every analyzed company. Click any → personalized page. |
| `/p/[slug]` | Hero, pain, value prop, intent-themed proof cards, CTA strip. Slug = domain with `.` → `-` (e.g. `headway-co`, `www-devoted-com`). |
| `/api/revalidate` | Sanity webhook target. Invalidates the index + targeted slug on doc publish. |

## Quickstart

```bash
cd render
cp .env.example .env.local       # fill in REVALIDATE_SECRET; mirror Sanity values from ../.env
npm install
npm run dev                       # http://localhost:3000
```

The home page lists all 5 demo companies. Click any to see its personalized page.

## Production deploy + webhook

```bash
# Build + run
npm run build && npm start

# Or deploy to Vercel
npx vercel --prod
```

After deploy, configure the Sanity webhook:

1. https://sanity.io/manage → project Prism → **API** → **Webhooks** → **Create webhook**
2. Name: `prism-render-revalidate`
3. URL: `https://<your-deploy>/api/revalidate?secret=<REVALIDATE_SECRET>`
4. Trigger on: Create, Update, Delete
5. Filter: `_type == "companyAnalysis"`
6. Save

Now: marketer edits copy in Studio → clicks Publish → webhook fires →
`revalidateTag("analysis:<slug>")` invalidates just that page's ISR cache →
next visit is fresh.

## Design

- **Server components only.** No client-side JS for the rendering. Faster
  loads, simpler model.
- **ISR with tags.** `revalidate: 60` is the safety floor; the webhook
  drives instant invalidation in practice.
- **CDN reads.** `sanity.client` uses `useCdn: true` for fast reads;
  webhook-triggered revalidation is what keeps content fresh.
- **Single CSS file.** Matches the design system in `../docs/index.html`
  (dark editorial, lime accent, serif headlines, mono numerics).
- **Slug ↔ domain mapping.** `.` ↔ `-`. Lossy on real-domain dashes —
  rare in our target market; falls back to GROQ `match` if exact fails.

## What's NOT here (v2)

- A/B variant routing (Sanity schema is shaped for it; `personalizedPage`
  array w/ experiment IDs)
- UTM-keyed variant selection
- Page-engagement analytics that feed back into the ICP score
- Auth / private preview links for unpublished docs

## Module map

```
render/
├── app/
│   ├── layout.tsx              shell + font loading
│   ├── globals.css             one CSS file, design tokens at top
│   ├── page.tsx                home — ranked list of analyses
│   ├── p/[slug]/page.tsx       the personalized landing page
│   ├── api/revalidate/route.ts Sanity webhook handler
│   └── not-found.tsx           404 with helpful pointer to the CLI
├── lib/
│   └── sanity.ts               client + GROQ queries + TypeScript types
├── package.json
├── tsconfig.json
└── next.config.mjs
```
