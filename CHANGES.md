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

## Later

- Store watch-outs as codes in the data release instead of sentences, so the engine can filter them by context.
