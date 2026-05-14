# Loom recording script

Target length: **5:00**. Three live runs woven between architecture and commentary.

---

## Before recording

1. Pre-cache Jina so the live runs are faster:
   ```bash
   python run.py analyze https://www.devoted.com   --dump examples/runs
   python run.py analyze https://headway.co        --dump examples/runs
   python run.py analyze https://www.goodrx.com    --dump examples/runs
   ```
2. Then wipe the demo state:
   ```bash
   env/bin/python scripts/clean_demo.py
   ```
3. Open three tabs side by side:
   - terminal (in `/Users/kritwish/Documents/Work/prism`)
   - HubSpot dashboard (companies view, sorted by recent)
   - Sanity Studio at `~/prism/` running `npm run dev` (http://localhost:3333)
   - optionally the Next.js renderer at http://localhost:3000 (if you'll show the rendered page)
4. Optional: open `docs/index.html` in another tab for the architecture beat.

---

## The three commands

```bash
# Run 1 — Tier A · the obvious yes
python run.py analyze https://www.devoted.com --dump examples/runs

# Run 2 — Tier B · the buyer hiding in disguise
python run.py analyze https://headway.co --dump examples/runs

# Run 3 — Tier D · the confident no on a healthcare brand
python run.py analyze https://www.goodrx.com --dump examples/runs
```

Why these three: each demonstrates a different dimension of the rubric.
Devoted shows the scoring formula working on the textbook case. Headway
shows the system catching a buyer that does not *look* like a buyer (their
own marketing literally says "credentialing for providers"). GoodRx
demonstrates the confident rejection of a $1.5B healthcare brand — the
harder call to make and the one that earns the system its keep.

---

## The script

### 0:00 – 0:25 · Open

> "Hey, I'm Kritwish. This is Prism — the GTM Engineer take-home for
> CertifyOS. One URL in, ICP-scored intelligence and page-ready landing
> copy out across HubSpot, Sanity, and a Next.js renderer. Three live
> runs. Let me show you the architecture first."

### 0:25 – 1:00 · Architecture + key decisions

*[switch to docs/index.html in browser]*

> "Four stages. Jina Reader for scraping — it solves JS rendering and
> content cleaning in one call. Then three Claude agents in sequence:
> extractor pulls facts, classifier picks enum values along five ICP
> factors, copywriter writes page-ready content.
>
> Critical design choice: the LLM classifies, Python scores. The formula
> is in scoring.py — explicit point bands per category, summed
> deterministically. The same signals always produce the same score.
> The LLM does language understanding, Python does math.
>
> Sanity holds every analysis the system has ever done. The Next.js
> renderer decides which ones become public pages, gated at score 50.
> Sub-floor accounts stay in Sanity for AE reference but do not render."

### 1:00 – 2:15 · Run 1: Devoted Health (Tier A)

*[terminal]*

```bash
python run.py analyze https://www.devoted.com --dump examples/runs
```

> "Live run on Devoted Health, a Medicare Advantage plan in 29 states.
>
> *[as it scrapes]* Scraping ten pages, extractor pulling facts...
>
> *[as classifier runs]* Watch the signals: HEALTH_PLAN, OVER_1M,
> RUNS_MULTI_STATE_NETWORK. The Python formula adds the points:
> 29 + 23 + 24 + 7 + 7 equals 90. Tier A.
>
> *[switch to HubSpot]* Here is the record. Every point is attributable.
> prism_score_breakdown shows industry 29 out of 30, network 24 out of
> 25, scale 23 out of 25 with the enterprise-customer bonus. AE can
> defend or override any single number.
>
> *[switch to Sanity Studio]* Same record in Sanity, edit-able by a
> marketer. Field-grouped: Identity, ICP Scoring, Intent and Pain,
> Page Content, Metadata. Hero headline reads 'Provider credentialing
> built for 29-state Medicare Advantage networks' — grounded in actual
> facts the scraper pulled."

### 2:15 – 3:15 · Run 2: Headway (Tier B, surprising)

```bash
python run.py analyze https://headway.co --dump examples/runs
```

> "Now Headway. Mental health platform. Watch this one carefully.
>
> *[as classifier runs]* Industry: DIGITAL_HEALTH_CLINICAL.
> Network: RUNS_MULTI_STATE_NETWORK. Readiness: EXPLICIT — the high band.
>
> *[when complete, show Sanity Studio]* Look at the top intent theme.
> 'Multi-state provider credentialing automation' at 88% confidence.
> Why? Because Headway's own marketing literally says they 'handle
> insurance credentialing and billing for providers.' The system
> spotted a buyer hiding inside a mental health platform.
>
> Score 79, Tier B. An AE searching for 'health plans' would skip
> Headway entirely. Prism would not."

### 3:15 – 4:00 · Run 3: GoodRx (Tier D, the call that matters)

```bash
python run.py analyze https://www.goodrx.com --dump examples/runs
```

> "And now the call that earns the system its keep. GoodRx — a
> 1.5 billion dollar healthcare brand.
>
> *[as the pipeline runs]* Notice the log: 'skipping copywriter, score
> 19 below floor 50.' No hero, no pain paragraph, no fabricated
> personalization.
>
> *[switch to HubSpot]* The HubSpot record still exists with the full
> breakdown. Industry 2, network 2, readiness 1. The AE sees exactly
> why GoodRx was rejected: not healthcare in the way that matters, no
> provider network of any kind.
>
> *[switch to Next.js renderer at localhost:3000]* And here is the
> public page list — Devoted and Headway show up. GoodRx does not.
> /p/www-goodrx-com returns 404 even though the Sanity doc exists.
>
> That is the call. A system that says 'medium' to everything is
> useless. A system that confidently rejects 70% of inbound frees AE
> attention for the 30% worth pursuing."

### 4:00 – 4:35 · What breaks + what's next

> "Three things break first under load. One: prompt drift on Claude
> version bumps — mitigated with pinned model versions and the
> validation-retry already in agents.py, but an eval harness in CI is
> the real fix and that is not built yet.
>
> Two: HubSpot search rate limits on batch runs. Three: Jina anti-bot
> on heavy SPAs — the confidence flag downgrades and propagates.
>
> What I would build next: Gong signal ingestion — biggest quality
> lever. A credentialing pain mentioned three times on a sales call is
> worth fifty website scrapes. The ICP classifier becomes a multi-source
> synthesizer. Then the eval harness. Then closed-loop attribution back
> to Sanity so the system grades its own copy by outcome."

### 4:35 – 5:00 · Measurement + close

> "How I would measure impact: holdout A/B. Personalized page versus
> generic for inbound. Prism copy versus templated for outbound. Track
> to closed-won by ICP tier. If Tier A does not beat Tier C in 90-day
> win rate, the scorer is decorative and I would rip it out.
>
> Code is in the repo, README has the whiteboard view, /docs has the
> full design doc with the formula and worked examples. Loom ran on a
> fresh database — every record you saw was generated in the last five
> minutes. Looking forward to talking through it."

---

## After the recording

Re-clean for the next take:

```bash
env/bin/python scripts/clean_demo.py
```

If you want to also wipe the local JSON dumps:

```bash
rm -f examples/runs/*.json
```
