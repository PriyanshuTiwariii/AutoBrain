# AutoBrain: start here

AutoBrain gives honest, evidence-backed EV buying advice for Mahindra and Tata buyers in India.
This folder is everything needed to build the **demo**: a buyer enters their needs and gets a ranked,
honest shortlist built only from the data in `data/releases/`.

## Read in this order

1. `HANDOFF.md` (this file): what's here and how it fits together
2. `AGENTS.md`: rules you must follow. Non-negotiable.
3. `CHANGES.md`: corrections to the demo plan, expected test results, feature mapping. **Where CHANGES.md and any other document disagree, CHANGES.md wins.**
4. `docs/DESIGN.md`: the full architecture and system design (the long-term MVP; the demo is a subset)
5. `docs/mockup_results_web.html` and `docs/mockup_results_phone.html`: open in a browser to see the results screen to build

## Folder layout (place files exactly like this in the repo root)

```
autobrain/
├── HANDOFF.md
├── AGENTS.md
├── CHANGES.md
├── .env.example
├── .gitignore
├── docs/
│   ├── DESIGN.md
│   ├── mockup_results_web.html
│   └── mockup_results_phone.html
├── contracts/
│   ├── needs.schema.json          # engine input
│   └── result.schema.json         # engine output
└── data/
    ├── master/
    │   └── AutoBrain_EV_Data.xlsx # master data: the ONLY place car data is edited
    ├── scripts/
    │   └── enrich.py              # rebuilds the release from the master, with validation
    └── releases/
        └── 2026-10-25/
            ├── autobrain_engine_variants.csv
            ├── autobrain_variant_ladder.csv
            ├── autobrain_accessories.csv
            ├── autobrain_data_dictionary.csv
            └── manifest.json
```

`engine/` (FastAPI) and `web/` (Next.js) are what you build, next to these folders.

## The data files

| File | Data rows | What it is | Used by the demo? |
| --- | --- | --- | --- |
| `autobrain_engine_variants.csv` | 87 | One row per variant: price, range (claimed, maker real-world, independent test), costs, safety, features, watch-outs | Yes, core |
| `autobrain_variant_ladder.csv` | 54 | Each price step within a model: extra cost, what you gain, factory-only gains | Yes ("Save money" / in-between) |
| `autobrain_accessories.csv` | 794 | Genuine accessories; `usable_as_gap_filler = yes` marks the few that can stand in for a factory feature | Optional |
| `autobrain_data_dictionary.csv` | 26 | Column meanings, types, allowed values, usage rules | Reference + enum validation |
| `manifest.json` | – | Release date, row counts, SHA-256 of each CSV | Engine logs it and checks the checksums at startup |

Row counts exclude the header line (each CSV file has one more line than its data rows).

The master spreadsheet has 12 tabs. The ones you may need to look at: `Engine_Variants` (same as the engine CSV),
`Variant_Ladder`, `Assumptions` (default tariffs), `Engine_Rules` (how recommendations must behave),
`Sources` (where every number came from), `Open_Questions` (known gaps).

## Data pipeline: the only way data changes

1. Edit source tabs in `data/master/AutoBrain_EV_Data.xlsx` (Variants, Features, Sources, Accessories). Save in Excel.
2. From the repo root run:
   `python data/scripts/enrich.py data/master/AutoBrain_EV_Data.xlsx data/releases/<YYYY-MM-DD>`
   It needs Python 3.10+ and `openpyxl`. It validates keys, numeric fields, allowed values, ladder prices and
   accessory links, writes the 4 CSVs and `manifest.json`, and exits with an error if anything fails.
3. Commit the new release folder. The engine loads the newest folder under `data/releases/` at startup.

Never edit the CSVs by hand. Never write a script that generates the master spreadsheet.

## Join keys

- `variant_key` (e.g. `TATA-NEXONEV-EMPOWEREDPLUSA45-45`) is permanent and links the engine and ladder files.
- Accessories link by `brand` + `model`.
- `sheet_id` is an internal spreadsheet row id. Never join on it.

## Scope and known gaps

- Mahindra: BE 6 SPORTEQ, XEV 9e, XEV 9S, XUV 3XO EV. Tata: Tiago.ev, Tigor.ev, Punch.ev, Nexon.ev, Curvv.ev, Harrier.ev, Sierra.ev.
- Prices: 65 verified (official), 20 corroborated (2+ independent sources agree), 2 pending (blank).
- Not in the data: kerb weight, current offers/discounts, Tata BaaS, on-road prices, independent efficiency for about two-thirds of variants. Show these as unknown. Never fill them in.

## The goal of the demo

Prove AutoBrain improves one decision, "which variant should I buy, and am I overpaying?", for Delhi NCR EV
buyers spending ₹10–20 lakh. Build only what that test needs: needs input, results page, PDF download and a
feedback link (see CHANGES.md).
