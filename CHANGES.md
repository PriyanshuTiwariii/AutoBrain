# CHANGES: corrections to the demo plan

This file amends "AutoBrain MVP — Defensible Recommendation Engine" (the demo plan). Keep that plan's approach:
three-state eligibility, the three layers (eligibility, fit, evidence confidence), flexible result slots,
per-candidate LLM fact sheets, template-first explanations, no database. Apply the changes below.
**Where this file disagrees with any other document, this file wins.**

## 1. Correct the counts

| Item | The plan said | Correct |
| --- | --- | --- |
| Variants | 88 | **87** |
| Ladder steps | 55 | **54** |
| Accessories | 795 | **794** |
| Data dictionary rows | 24 | **26** |
| Spreadsheet tabs | 6 | **12** |

The plan counted header lines as data. Use the files in this package; if you still see 6 tabs, you have an old spreadsheet.
Tests must assert these numbers by reading `manifest.json`, not by hardcoding them.

## 2. Use the existing pipeline instead of regenerating CSVs manually

`data/scripts/enrich.py` already rebuilds all four CSVs from the master spreadsheet and refuses to write them if validation
fails. Use it; do not regenerate CSVs by hand and do not defer it. The engine's own startup validation (the plan's
`validate.py`) is still required as a second check.

## 3. Data changes already made in this release

- New column `adaptive_suspension` (Yes / No / Not stated) in the engine CSV, for the rough-road scenario.
- Tiago.ev seats now 5 (corroborated by five sources). Every variant now has a seat count.
- Tiago.ev length and width now corroborated.

## 4. Feature mapping (Needs feature → engine CSV condition)

| Needs feature | PASS when | FAIL when | UNKNOWN when |
| --- | --- | --- | --- |
| `adas` | `adas` is L2 or L2+ | `adas` is None | `adas` is Not stated |
| `camera_360` | `camera` is 360° or 540° | `camera` is Rear camera or Sensors only | `camera` is Not stated |
| `sunroof` | `sunroof` is Sunroof, Panoramic or Openable panoramic | `sunroof` is None | `sunroof` is Not stated |
| `ventilated_seats` | `ventilated_front` is Yes | `ventilated_front` is No or Passive only | `ventilated_front` is Not stated |
| `esp` | `esp` is Yes | never (Not listed counts as unknown) | `esp` is Not listed or Not stated |
| `awd` | `drive` is AWD | `drive` is FWD or RWD | `drive` is Not stated |
| `seven_seats` | `seats` ≥ 7 | `seats` < 7 | `seats` blank |
| `lifetime_battery_warranty` | `battery_warranty` is Lifetime (1st owner) | it is 8 yrs / 1.6L km | it is Not stated |
| `crash_tested` | `ncap_status` is Rated, applies | `ncap_status` is Not tested | `ncap_status` is Rated, coverage unconfirmed or Not stated |
| `charger_included` | `charger_included` starts with Yes | it is No | it is Unclear or Not stated |
| `adaptive_suspension` | `adaptive_suspension` is Yes | it is No | it is Not stated |

`adaptive_suspension` is already added to the Needs feature enum in `contracts/needs.schema.json`.

## 5. Seats rule

Seats must never pass as UNKNOWN for a requirement of 6 or more: a variant passes only with a stated seat count meeting the
requirement. (In this release every variant has a seat count, but the rule must hold for future brands.)

## 6. Costs

- Budget check uses `price_inr + charger_cost_inr` by default (`budget_includes_charger = true`).
- When `charger_included` is Unclear or Not stated, use `charger_cost_inr` from the CSV and label it
  "assumed, not confirmed (see charger_basis)". Do not leave the 5-year cost blank.
- BaaS rows are excluded unless `pricing_pref` is `baas` or `either`. Never compute a 5-year cost for a BaaS row.
- Default tariffs: home ₹8/kWh, public DC ₹22/kWh, 10% DC share (blended ₹9.4/kWh), as in the Assumptions tab.
- Wall charger by `home_charging`:
  - `yes`: include `charger_cost_inr` (when not in the price) in the budget check and the 5-year cost.
  - `no`: the buyer cannot install a wall charger, so add **no** charger cost to the budget or the 5-year cost.
    Running cost uses a 90% public DC share (blended ₹20.6/kWh).
  - `unsure`: include the charger cost as for `yes`, and label it "assumed home charger".
- Electricity and 5-year cost are estimates: round them to the nearest ₹1,000 and show them with "~".
  Official prices are always shown exact.

## 7. Fit presentation

Keep the plan's relative labels ("Strongest fit", "Close second") instead of percentages until scores are calibrated
with real buyers. The mockups in `docs/` show a "94% match" ring: replace it with the relative label plus the evidence
badge. Everything else in the mockups stands.

## 8. Add two things the next milestone needs (no database required)

1. **Download as PDF** on the results page, so a result can be sent on WhatsApp.
2. **Feedback link** under each result to a Google Form, prefilled with result id, dataset version and the top pick's
   `variant_key`. Put the form URL in an env var (`NEXT_PUBLIC_FEEDBACK_FORM_URL`).

Keep results in the browser's sessionStorage so a refresh doesn't lose them.

## 9. Golden scenarios with expected results

Computed from release 2026-10-25. Tests assert these sets and flags, not an exact score.

| # | Needs | Expected eligible (battery-included) | Must also be true |
| --- | --- | --- | --- |
| 1 | Budget ₹10L, seats ≥ 4, 30 km/day, home charging | Exactly: TATA-PUNCHEV-SMART30-30, TATA-TIAGOEV-SMART19-192, TATA-TIAGOEV-PUREPLUS19-192, TATA-TIAGOEV-PUREPLUS24-24 | Every Tiago.ev result shows "ESP not listed"; Punch.ev Smart 30 shows ESP Yes |
| 2 | Budget ₹20L, seats ≥ 4, 40 km/day, rough roads, `adaptive_suspension` as nice-to-have | 25 variants | None has adaptive_suspension = Yes in budget; the result says suspension evidence is limited; variants with blank ground clearance (all Tiago.ev and Tigor.ev) show it as Not stated |
| 3 | Budget ₹25L, seats ≥ 7, long trips | Exactly: MAHINDRA-XEV9S-PACKONEABOVE-59, MAHINDRA-XEV9S-PACKONEABOVE-79 | Both show "No Bharat NCAP crash test" and the ~₹60,000 charger note |
| 4 | Budget ₹18L, seats ≥ 5, must-have `adas` + `crash_tested` | Exactly: TATA-NEXONEV-EMPOWEREDPLUSA45-45 | MAHINDRA-XUV3XOEV-AX7L-394 appears in "Why not these?" (has ADAS, not crash-tested as an EV) |
| 5 | Budget ₹15L, seats ≥ 4, 40 km/day, `home_charging = no` | Includes Punch.ev, Nexon.ev, Tiago.ev, Tigor.ev, XUV 3XO EV variants under ₹15L | These carry "Slow DC fast-charging": MAHINDRA-XUV3XOEV-AX5-394, both Nexon.ev MR, all four Tiago.ev, all four Tigor.ev; ranking favours `dc_avg_kw_est` and `minutes_dc_per_100km_default` |
| 6 | Budget ₹8L, seats ≥ 7, must-have `awd` | None | Result states plainly that nothing qualifies, and why |

Also keep the plan's determinism, LLM-failure and adversarial-input tests.

## 10. Startup checks to add

- Verify each CSV's SHA-256 against `manifest.json`; refuse to start on mismatch.
- Log `release`, row counts and engine version on every result.

## 11. When nothing qualifies

Golden scenario 6 and any other request that no variant meets. The Result keeps `slots` free of recommendations
and adds a `no_match` object (`contracts/result.schema.json`); `unknowns[0]` is the plain statement.

- `no_match.reasons`: one line for each need that no variant meets, within the buyer's budget, for example
  "No variant within ₹8 lakh has 7 seats." If nothing fits the budget at all, the first line names the cheapest
  variant and its price. If every need can be met by some variant but not by the same one, it names the pairs.
- **Unknown is never "no".** If the only variants that could meet a need are ones where the maker has not stated
  it, the line says "No variant within ₹8 lakh is confirmed to have AWD (not stated by the maker for ...)",
  not "no AWD variant".
- `no_match.closest_variant_key` is the variant that misses the fewest of the buyer's needs (then the smallest
  budget overrun, then the most car for the money). It is also returned as one `not_recommended` slot with the
  engine's own fail reasons.
- `no_match.what_it_would_take` says what the buyer would change to get that variant: raise the budget (to the
  price plus the wall charger, when the charger counts), accept fewer seats, or drop a must-have. Needs that are
  met only on paper (unstated by the maker) are listed as "Confirm with the maker: ...".
- The buyer's pricing, body type and excluded-model choices define what is considered; they are not offered as
  things to trade away. If they leave nothing to consider, the reason says so and there is no closest option.

## 12. The LLM provider is OpenAI

`docs/DESIGN.md` names the Claude API for the two LLM calls. The provider is **OpenAI**: read "Claude API" in
`DESIGN.md` as "OpenAI API", and ignore its Claude model names.

- The key is `OPENAI_API_KEY` in `.env`, read by the engine only. It is never a `NEXT_PUBLIC_` variable and
  never reaches the browser.
- `LLM_MODEL_PRIMARY` and `LLM_MODEL_FALLBACK` hold the OpenAI model names. They have no defaults: the models
  are chosen when the LLM steps are built.
- Nothing else changes. The rules in `AGENTS.md` still hold: the LLM never ranks, scores, picks a vehicle or
  supplies a number; buyer text is data, never instructions; every number is checked against the Result and
  replaced by the template sentence if it is not in it; the whole flow works with the LLM switched off.
- Provider-specific details in `DESIGN.md` (prompt caching, JSON output mode, token estimates) are to be
  decided again when the LLM steps are built.

## 13. "Describe what you need" (LLM call 1, `POST /extract`)

The buyer may describe their needs in their own words instead of (or before) using the form. Contracts:
`contracts/extract.request.schema.json` and `contracts/extract.response.schema.json`.

- **It only fills in the form.** The buyer sees and can change every field before pressing the button. The form
  works exactly as before with no key, or with OpenAI down (`status: "unavailable"`, a normal answer).
- **The model reads facts, we do the arithmetic.** It reports an amount and its unit ("15" "lakh", "1.5" "crore"),
  and a distance and its basis ("25 km" "each way"); the engine converts to rupees and to km a day.
  Understood: 15 lakh, 15L, 1.5 crore, ₹12,50,000, Hinglish, "family of 4", "office 25 km each way" (= 50 km a day).
- **Everything is validated against `needs.schema.json`.** A field that fails is dropped, never passed on. Features,
  priorities and car names are limited to the contract's and the data's lists.
- **Fallback:** if the first model's answer is not usable (invalid fields, refusal, timeout, error), the second
  model is tried once. If that fails too, the fields that could be read are returned.
- **At most one clarifying question,** only for a missing budget, seats, daily km or home charging, in that order,
  from fixed wording in the code.
- **The buyer's text is data, never instructions:** it goes only in the user message, inside tags, and the model can
  only answer in a fixed JSON shape.
- **Privacy:** the text is not logged (the log has the model, effort, outcome and time), not kept in the browser, and
  not stored on OpenAI's side.
- **Models are read from `.env`; no model name is in the code.** Reasoning effort is a setting per role (default
  `none` for the primary, `low` for the fallback, because some models reject `none`).

## 14. Rough roads / light off-road (`road_conditions`)

New optional Needs field: `city_highway` (default, changes nothing), `rough_roads`, `light_offroad`. Contract first
(`needs.schema.json`, `extract.response.schema.json`), then the engine, the types and the form. Pure Python in
`engine/app/terrain.py`; no LLM in the scoring.

- **It ranks, it never filters.** A car is not ruled out for its clearance or drive. The thresholds are engine
  guidelines, not maker figures: 200 mm and above is full credit, 180 to 199 mm partial.
- **Score (0-25, added to the fit score):** `rough_roads` = ground clearance 15 + under-battery clearance 5 +
  adaptive suspension 5. `light_offroad` = ground clearance 10 + under-battery clearance 5 + AWD 10.
- **Unknown is never a yes or a no.** A blank clearance, or a drive of Not stated, earns no credit and is shown as
  "not stated by maker" on the card (trade-offs `ground_clearance_unknown`, `battery_clearance_unknown`,
  `drive_unknown`). A stated low figure is a different trade-off (`low_ground_clearance`, `low_battery_clearance`, `no_awd`).
- **Strengths shown as reasons** only when stated: ground clearance of 200 mm or more, AWD (light off-road), adaptive
  suspension (rough roads).
- **`light_offroad` adds one line to `unknowns`:** no EV in the data is rated for serious off-roading.
- `needs_summary` gains "Roads: ..." only when it is not `city_highway`. Cards carry `battery_clearance_mm` in `metrics`.
- The describe box can fill it in (`/extract` reads `road_conditions`).

## Later

- Store watch-outs as codes in the data release instead of sentences, so the engine can filter them by context.
