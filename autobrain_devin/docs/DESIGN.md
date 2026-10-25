# AutoBrain MVP: Architecture & System Design

As of 2026-10-25. Author: Madhu Sudan Thakar.

> **For the demo build:** this is the full MVP design. The demo is a subset of it (no database, no leads, no admin).
> Where this document and `CHANGES.md` disagree, `CHANGES.md` wins. In particular: use relative fit labels instead of a
> 0–100 score, and use the three-state eligibility from the demo plan.

The MVP is a web app where an EV buyer describes their needs in plain language and gets a ranked, evidence-backed
Mahindra/Tata shortlist in under 30 seconds.

## Goals and scope

The MVP exists to prove three things: buyers trust the advice, they act on it, and it can earn money.

**In scope for the full MVP:** chat or quick-form input with at most two clarifying questions; a results page like
the mockup (best fit, alternative, in-between, save money, why not these, side-by-side table); fit and evidence
confidence computed by code; variant detail and compare views; lead capture (test drive, on-road quotes, group buy);
a one-tap feedback prompt; shareable report links.

**Success metrics (first 8–12 weeks)**

| Metric | Target |
| --- | --- |
| Buyers who complete a recommendation | 1,000+ |
| Say it changed or confirmed their choice | 30%+ |
| Leads (test drive, quote, group buy) | 10%+ of completions |
| Group-buy interest for one model in Delhi NCR | 15–20 buyers |
| Median time to result | Under 30 seconds |

## System overview

Code picks the cars; the LLM only reads needs and writes words. No number shown to a buyer comes from the LLM.

```
 Buyer (web / phone) ──► Next.js web app (Vercel) ──save──► Postgres (Supabase)   [Postgres: full MVP only]
                              │      ▲
                needs, private API   Result JSON + wording
                              ▼      │
 ┌──────────────── Python engine (FastAPI) ─────────────────┐
 │ 1. Extract needs ──► 2. Recommend ──► 3. Phrase result   │──► Claude API (steps 1 and 3 only)
 │    LLM call 1        pure Python,      LLM call 2,       │
 │    text → Needs      no LLM            number check      │
 └───────────────────────────▲──────────────────────────────┘
                             │ loaded into memory at startup
 Master spreadsheet ──► data/scripts/enrich.py ──► Dataset release (4 CSVs + manifest, read-only)
```

One request: the buyer types their needs; the web app sends them to the engine; step 1 turns them into structured
Needs; step 2 filters and ranks from the in-memory dataset; step 3 words the result and checks every number; the
web app renders the cards.

## Tech stack

| Layer | Choice | Why |
| --- | --- | --- |
| Web app | Next.js 14 (App Router), TypeScript, Tailwind CSS | Fast to build, server rendering for share links |
| Engine API | Python 3.12, FastAPI, Pydantic v2 | Strict input/output schemas; pure-Python engine |
| Dataset at runtime | CSVs from the newest release, loaded into memory | Tiny data; every recommendation runs in milliseconds |
| Database (full MVP) | PostgreSQL on Supabase | Sessions, results, leads, feedback |
| LLM | Claude API: Haiku 5.5 (`claude-haiku-5-5`) first, Sonnet 5.5 (`claude-sonnet-5-5`) fallback | Two narrow jobs, structured JSON output |
| Analytics / errors (full MVP) | PostHog, Sentry | Free tiers |
| Hosting | Vercel (web), Railway or Render (engine) | Push-to-deploy |
| CI | GitHub Actions | Data validation + tests on every push |

The dataset is read-only at runtime. It is rebuilt from the master spreadsheet by `data/scripts/enrich.py`, never
edited in code or in a database.

## Data layer

**Pipeline (run on every data change)**

1. Edit source tabs in `data/master/AutoBrain_EV_Data.xlsx` (Variants, Features, Sources, Accessories).
2. Run `python data/scripts/enrich.py data/master/AutoBrain_EV_Data.xlsx data/releases/<YYYY-MM-DD>`. It rebuilds
   the decision tabs, the four CSVs and `manifest.json`, and exits with an error on any validation failure.
3. Commit the release folder. CI re-runs validation; the engine loads the newest release and records its version in
   every result.

**Runtime dataset**

| File | Key | Used for |
| --- | --- | --- |
| `autobrain_engine_variants.csv` | `variant_key` | Eligibility, fit, cards, watch-outs |
| `autobrain_variant_ladder.csv` | `ladder_key` | In-between and save-money explanations |
| `autobrain_accessories.csv` | `accessory_key` | Gap-filler suggestions (`usable_as_gap_filler = yes` only) |
| `autobrain_data_dictionary.csv` | file + column | Allowed values and rules, used for validation |

**Postgres tables (full MVP only)**

| Table | Main columns |
| --- | --- |
| `sessions` | id, created_at, channel, city, utm_source |
| `needs` | session_id, raw_text, needs_json, extraction_model, version |
| `results` | id, session_id, needs_id, result_json, dataset_version, engine_version |
| `leads` | id, result_id, type (test_drive / quote / group_buy), variant_key, name, phone, city, consent_at |
| `feedback` | result_id, helpful, changed_choice, note |
| `price_reports` | variant_key, city, quoted_price, paid_price, dealer, date, source |
| `dataset_versions` | version, loaded_at, manifest_json |

Store `dataset_version` and `engine_version` with every result so any recommendation can be reproduced.

## Recommendation engine

Plain, tested Python: `Needs` in, `Result` out, deterministically. The LLM never ranks, scores or supplies a number.

**Input:** `contracts/needs.schema.json` (budget, charger in budget, seats, daily km, longest regular trip, home
charging, city, body types, must-haves, nice-to-haves, priority, pricing preference, excluded models). Feature
mapping to CSV columns: `CHANGES.md` section 4.

**Steps**

1. **Eligibility** (three-state, per the demo plan): each requirement is PASS, FAIL or UNKNOWN. FAIL excludes; UNKNOWN
   keeps the variant but flags it. BaaS rows excluded unless the buyer allows them. Budget = price + charger cost.
2. **Fit:** budget headroom, range fit (independent test first, then maker real-world claim, labelled; compare with
   1.25 × longest trip, or 2 × daily km if no trip given), nice-to-haves met, priority alignment.
3. **Rank** by fit, then by the priority: safety → `ncap_adult_32`, ESP, airbags, ADAS; cost → 5-year cost;
   range → real-world range; space → `boot_l`; features → nice-to-haves met.
4. **Evidence confidence:** high when price is verified, range or efficiency independently tested and the crash rating
   covers the variant; lower as any of these is missing or unconfirmed.
5. **Slots:** best fit; alternative from a different model (only if one genuinely competes); in-between (one ladder
   step down from the best fit, if eligible); save money (cheapest variant meeting all critical needs, with
   `factory_only_gains` it lacks); why not these (attractive variants excluded, with reasons). If nothing qualifies,
   say so.
6. **Personal costs:** running cost and 5-year cost from the buyer's daily km and tariff (defaults ₹8/kWh home,
   ₹22/kWh DC, 10% DC share).

**Output:** `contracts/result.schema.json`. Reasons and trade-offs are emitted as codes with values, not sentences.
Every code has a deterministic template; the LLM may only rephrase them.

## LLM layer

- **Call 1, extract:** buyer messages → Needs JSON + missing fields + at most one clarifying question at a time
  (two in total). Defaults are shown to the buyer as editable chips.
- **Call 2, explain:** one candidate's fact sheet at a time → sentences per reason/trade-off code. Never sees raw
  buyer text or other candidates.
- **Guardrails:** number check (any number not in the Result is discarded, the template is used); template fallback
  if the API is down; buyer text treated as data; fixed reply for out-of-scope questions; no financing, legal or tax
  advice.
- **Cost and speed:** prompt caching; roughly 3,000–6,000 tokens per completed recommendation; render cards from
  the Result immediately, then fade in LLM wording.

## API design

**Engine (FastAPI)**

| Route | Purpose |
| --- | --- |
| `POST /extract` | Call 1: messages → Needs + missing fields |
| `POST /recommend` | Needs → Result. Pure, deterministic, no LLM |
| `POST /phrase` | Call 2: candidate fact sheets → sentences, with number check and fallback |
| `GET /variants/{key}`, `GET /compare?keys=` | Read-only lookups |
| `GET /health` | Release version, row counts, engine version |

**Web (Next.js API routes, full MVP):** `/api/session`, `/api/chat`, `/api/recommend`, `/api/results/:id`,
`/api/variants/:key`, `/api/compare`, `/api/leads` (consent required), `/api/feedback`, `/api/price-report`.
The browser never sees the engine URL, database keys or the Claude API key.

## Frontend

Mobile-first at 390px, matching `docs/mockup_results_*.html` with the CHANGES.md adjustments.

| Screen | Route | Purpose |
| --- | --- | --- |
| Landing | `/` | One promise, one button, three proof points |
| Needs | `/start` | Chat plus tappable chips; buyer can edit any chip before results |
| Results | `/r` (demo) or `/r/:id` (full MVP) | Best fit, alternative, in-between, save money, why not these, side-by-side table, PDF download, feedback link |
| Variant detail (full MVP) | `/v/:key` | Specs with source labels, ladder steps, gap-filler accessories |
| Compare (full MVP) | `/compare` | 2–4 variants side by side |

UI rules: every number shows its status label; "Not stated by maker" is shown, never hidden; nothing is shared with a
dealer without a ticked consent box.

## Leads, analytics and metrics (full MVP)

Events: `session_started`, `needs_completed`, `result_viewed`, `slot_expanded`, `lead_created`, `feedback_given`,
`price_reported`, `report_shared`. Leads are handled manually at first: posted to a private team channel, called the
same day, passed to a partner dealer only with consent. Group-buy interest is counted per model and city.

## Security, privacy and compliance

India's Digital Personal Data Protection Act, 2023 applies to names and phone numbers. Get a legal review of consent
wording before collecting them. Anonymous by default; explicit unticked consent box before any sharing; delete raw
chat text after 90 days; secrets only in server env vars; rate limits and message-length caps; a fixed disclaimer on
every result (ex-showroom prices, check on-road price and offers, data as of the release date, AutoBrain is
independent of Tata and Mahindra).

## Testing and evaluation

| Layer | Test | Pass bar |
| --- | --- | --- |
| Data | `enrich.py` validation on every build; engine startup validation | Zero errors |
| Engine | Unit tests per rule; golden scenarios in CHANGES.md section 9 | 100% pass |
| Engine | Property tests: nothing over budget; FAIL never recommended; every number traceable to a CSV row | Always true |
| LLM call 1 | 30 sample buyer messages (Hinglish included) with expected Needs | 90%+ fields correct |
| LLM call 2 | Number check on every explanation | Zero unmatched numbers shown |
| Safety | Prompt injection, off-topic, other brands, API down | Safe fixed behaviour |
| End to end | 50 real buyer requests, run blind | Fix every failure before wider launch |

## Deployment and costs (full MVP)

Vercel for web, Railway or Render for the engine, Supabase for Postgres, Claude API pay-per-use. Well under ₹10,000 a
month at launch volumes; confirm current prices when signing up. Refresh prices and offers monthly and publish a new
release.

## Risks and out of scope

| Risk | Mitigation |
| --- | --- |
| Stale prices or offers | Monthly refresh; release date on every result; "get an on-road quote" on every result |
| LLM misreads a buyer | Needs shown as editable chips before results |
| LLM states a wrong number | Numbers render from the Result; number check discards mismatches |
| Two brands feels biased | Say so on the landing page; add MG next |
| Dealers don't value leads | Test with 3–5 dealers before scaling |

Out of scope for the MVP: user accounts, payments or bookings, a WhatsApp bot, automated group-buy negotiation,
used EVs, other brands, on-road price by city, a native app.
