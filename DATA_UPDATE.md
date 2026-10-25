# Data update: release 2026-10-25-r2

## What changed

Two new columns in `autobrain_engine_variants.csv`, placed right after `range_tested_km`:

| Column | Values | Meaning |
| --- | --- | --- |
| `range_test_vehicle` | `Same model` / `Earlier version` / `Not tested` | Whether `range_tested_km` and the tested efficiency come from the exact version sold now, an earlier version of the car, or there is no independent test |
| `range_test_note` | text, blank when `Not tested` | Plain-language description of the test vehicle, for display |

Current counts: 12 variants are `Earlier version` (all BE 6 SPORTEQ 79 kWh rows: tested before the SPORTEQ update, same battery and motor per Autocar; Tiago.ev Pure+ 24 and Creative+ 24: tested before the May 2026 facelift, same 24 kWh battery size). 33 are `Same model`. 42 are `Not tested`.

A new watch-out is generated for the 12 `Earlier version` rows: "Range/efficiency test was on an earlier version of this car".

Everything else is unchanged: same 87 variants, 54 ladder steps, 794 accessories, same prices and keys. The data dictionary grows from 26 to 28 rows. Golden scenario eligibility results in CHANGES.md §9 are unaffected.

## Files in this update (unzip at the repo root, replacing existing files)

```
data/master/AutoBrain_EV_Data.xlsx              (updated master)
data/scripts/enrich.py                          (updated pipeline)
data/releases/2026-10-25-r2/                    (new release folder, 4 CSVs + manifest.json)
DATA_UPDATE.md                                  (this file)
```

Keep the old `data/releases/2026-10-25/` folder for history; the engine should load the newest release.

## What the engine must do

1. Point the default release at `data/releases/2026-10-25-r2` (config default and `.env.example`). Update references to the release name in HANDOFF.md.
2. Add `range_test_vehicle` to the enum validation (it's in the data dictionary) and to the Variant model.
3. Evidence confidence: a variant can only be **High** if its tested figures come from `Same model`. `Earlier version` counts as a test for ranking, but caps confidence at Medium.
4. Display: whenever a tested range or efficiency is shown for an `Earlier version` row, label it "tested on an earlier version" and show `range_test_note` (on the card or as a tooltip). Never just "(independent test)".
5. Tests: add one test asserting that every `Earlier version` row shows the label and never gets High confidence, and one asserting `Same model` rows are unaffected. Do not hardcode model names; drive everything from the column.

## Rebuild check

From the repo root:

```
python data/scripts/enrich.py data/master/AutoBrain_EV_Data.xlsx data/releases/2026-10-25-r2
```

This must reproduce the same files and checksums as in the shipped `manifest.json` (built_at will differ).
