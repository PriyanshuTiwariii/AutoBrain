"""Print full buyer-readable results for golden scenarios 1, 3, and 5."""
import sys, io
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import DATA_RELEASE_DIR
from app.dataset import load_dataset
from app.models import Needs
from app.slots import build_result, fmt_lakh

ds = load_dataset(DATA_RELEASE_DIR)

SCENARIOS = {
    "Scenario 1: Budget ₹10 lakh, seats≥4, 30 km/day, home charging": Needs(
        budget_max_inr=1000000, seats_min=4, daily_km=30, home_charging="yes",
    ),
    "Scenario 3: Budget ₹25 lakh, seats≥7, long trips (300 km)": Needs(
        budget_max_inr=2500000, seats_min=7, daily_km=40, longest_regular_trip_km=300, home_charging="yes",
    ),
    "Scenario 5: Budget ₹15 lakh, seats≥4, 40 km/day, no home charging": Needs(
        budget_max_inr=1500000, seats_min=4, daily_km=40, home_charging="no",
    ),
}

SLOT_TITLES = {
    "best_match": "BEST MATCH",
    "strong_alternative": "STRONG ALTERNATIVE",
    "same_model": "SAME MODEL",
    "in_between": "IN BETWEEN",
    "dont_overpay": "DON'T OVERPAY",
    "not_recommended": "NEAR MISS",
}


def print_result(title, needs):
    result = build_result(needs, ds.variants, ds.version, ds.engine_version, dataset=ds)
    print("=" * 80)
    print(f"  {title}")
    print("=" * 80)
    print()
    for line in result.needs_summary:
        print(f"  {line}")
    print()

    if not result.slots:
        print("  No vehicles qualify.")
    
    for slot in result.slots:
        v = ds.get_variant(slot.variant_key)
        label = SLOT_TITLES.get(slot.slot, slot.slot.upper())
        print(f"  ┌─ {label} ─────────────────────────────────")
        print(f"  │ {v.model} — {v.variant}" if v else f"  │ {slot.variant_key}")

        # Confidence only for recommended slots
        if slot.slot != "not_recommended":
            fit_label = slot.metrics.get('relative_label')
            fit = f"Fit: {fit_label}   " if fit_label else ""
            print(f"  │ {fit}Evidence: {slot.confidence}")
        print(f"  │")

        print(f"  │ Price: {fmt_lakh(slot.price_inr)} ({slot.price_status})")
        m = slot.metrics
        charger = m.get("charger_note", "")
        if charger and charger != "Included":
            print(f"  │ Charger: {charger}")
        e5 = m.get("electricity_5yr_inr")
        if e5:
            print(f"  │ Electricity (5yr): ~{fmt_lakh(e5)}")
        c5 = m.get("cost_to_own_5yr_inr")
        if c5:
            print(f"  │ 5-year cost: ~{fmt_lakh(c5)}")
        rc = m.get("running_cost_inr_per_km")
        if rc:
            print(f"  │ Running cost: ₹{rc:.2f}/km ({m.get('tariff_basis', '')})")
        if slot.savings_vs_best_inr:
            print(f"  │ Saves: {fmt_lakh(slot.savings_vs_best_inr)} vs top pick")
        print(f"  │")

        # Range (labelled by the engine, including tests done on an earlier version)
        if m.get("range_display"):
            print(f"  │ Range: {m['range_display']}")
        if m.get("efficiency_display"):
            print(f"  │ Efficiency: {m['efficiency_display']}")
        if m.get("range_test_note"):
            print(f"  │ Test note: {m['range_test_note']}")
        dc = m.get("dc_avg_kw_est")
        mins = m.get("minutes_dc_per_100km")
        if dc:
            print(f"  │ DC charging: {dc:.0f} kW avg" + (f", {mins} min/100 km" if mins else ""))
        seats = m.get("seats")
        if seats:
            print(f"  │ Seats: {seats}")
        gc = m.get("ground_clearance_mm")
        if gc:
            print(f"  │ Ground clearance: {gc} mm")
        print(f"  │")

        # Reasons
        if slot.reasons:
            print(f"  │ Why:")
            for r in slot.reasons:
                detail = r.detail or r.code
                print(f"  │   • {detail}")

        # Trade-offs
        if slot.tradeoffs:
            print(f"  │ Trade-offs:")
            for t in slot.tradeoffs:
                detail = t.detail or t.code
                print(f"  │   ⚠ {detail}")

        # Watch-outs
        if slot.watch_outs:
            print(f"  │ Watch-outs:")
            for w in slot.watch_outs:
                print(f"  │   ⚠ {w}")

        print(f"  └──────────────────────────────────────────")
        print()

    if result.unknowns:
        print("  Unknowns:")
        for u in result.unknowns:
            print(f"    • {u}")
        print()

    print(f"  {result.disclaimer}")
    print(f"  Dataset: {result.dataset_version}  Engine: {result.engine_version}")
    print()
    print()


outpath = Path(__file__).resolve().parent.parent / "scenario_output.txt"
with open(outpath, "w", encoding="utf-8") as fh:
    old_stdout = sys.stdout
    sys.stdout = fh
    for title, needs in SCENARIOS.items():
        print_result(title, needs)
    sys.stdout = old_stdout
print(f"Written to {outpath}")
