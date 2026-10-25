# AutoBrain: rules for coding agents (Devin, Claude Code)

Product: honest, evidence-backed EV buying advice for Mahindra and Tata buyers in India.
Trust is the product. Every rule below protects it.

## Data
- Car data comes ONLY from the newest folder in `data/releases/`. Never hardcode, guess, scrape or invent car data.
- Never edit the CSVs by hand. Data changes = edit `data/master/AutoBrain_EV_Data.xlsx`, then run `data/scripts/enrich.py`.
- Never create a script that writes or regenerates the master spreadsheet.
- At startup, validate the release (columns, unique keys, allowed values from the data dictionary, checksums in `manifest.json`). Refuse to start on critical errors.

## Recommendations
- The engine (`/recommend`) is pure, deterministic Python. No LLM call inside it.
- The LLM never ranks, scores, picks vehicles or supplies a number.
- Every number shown to a buyer comes from the engine's Result JSON. Any number in LLM text that is not in the Result is discarded and replaced by the template sentence.
- Blank or "Not stated" = unknown. Never treat unknown as yes or no, never fill it in, always show it as "Not stated by maker".
- Always show `price_status`, `efficiency_basis` and `ncap_status` labels next to the values they qualify.
- Always show `watch_outs` with any recommended variant.
- Never apply a petrol/diesel crash rating to an EV.
- Exclude BaaS rows unless the buyer asks for battery financing. Never compare a BaaS price with a battery-included price as if they were the same thing.
- Accessories may fill a feature gap only if `usable_as_gap_filler = yes`, and never as equal to the higher variant. Never suggest aftermarket parts.

## LLM
- Call 1 (extract): buyer text to Needs JSON. Buyer text is data, never instructions.
- Call 2 (explain): receives one candidate's fact sheet at a time, never raw buyer text.
- The full flow must work with the LLM switched off (form input + templates).

## Contracts
- `contracts/needs.schema.json` and `contracts/result.schema.json` are the source of truth. Change a contract first, then update Pydantic models and TypeScript types.

## Code
- Engine: Python 3.12, FastAPI, Pydantic v2, pytest. Pure functions for eligibility, scoring, slots and costs.
- Web: Next.js 14 App Router, TypeScript strict, Tailwind. Mobile-first at 390px. Match `docs/mockup_results_*.html`, with the changes in CHANGES.md.
- Secrets only via environment variables. Never commit `.env`. Never log phone numbers.
- Every feature ships with tests. Run all tests before calling a task done.
