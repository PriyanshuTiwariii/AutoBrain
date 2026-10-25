"""Tests for ladder-powered same_model, in_between and dont_overpay slots, and their wording."""
from __future__ import annotations

import re

from app.dataset import Dataset
from app.models import Needs
from app.slots import MAX_TOP_PICK_ADDS, _collect_ladder_gains, build_result
from app.wording import ladder_gains, parse_ladder


def _result(dataset: Dataset, needs: Needs):
    return build_result(needs, dataset.variants, dataset.version, dataset.engine_version, dataset=dataset)


def _slots(result, slot_type: str):
    return [s for s in result.slots if s.slot == slot_type]


SAFETY_NEEDS = dict(
    budget_max_inr=1800000, seats_min=5, daily_km=40,
    home_charging="yes", priority="safety", must_haves=["crash_tested"],
)
SCENARIO_1 = dict(budget_max_inr=1000000, seats_min=4, daily_km=30, home_charging="yes")
SCENARIO_3 = dict(
    budget_max_inr=2500000, seats_min=7, daily_km=40, longest_regular_trip_km=300, home_charging="yes",
)
SCENARIO_5 = dict(budget_max_inr=1500000, seats_min=4, daily_km=40, home_charging="no")

# Raw ladder field labels must never reach the buyer
RAW_LABEL = re.compile(r"\b(Audio|Screens|Upholstery|Vent\. seats|Battery kWh|Range km|App suite|Wheels):")


def test_in_between_is_one_step_down_with_give_up_wording(dataset: Dataset):
    """Best match Nexon.ev Empowered+A 45 → Empowered 45 is the in-between,
    worded as 'you give up X for Y less', in plain words."""
    result = _result(dataset, Needs(**SAFETY_NEEDS))
    assert _slots(result, "best_match")[0].variant_key == "TATA-NEXONEV-EMPOWEREDPLUSA45-45"

    in_between = _slots(result, "in_between")
    assert len(in_between) == 1
    ib = in_between[0]
    assert ib.variant_key == "TATA-NEXONEV-EMPOWERED45-45"
    assert ib.savings_vs_best_inr == 135000
    first = ib.reasons[0].detail
    assert first.startswith("You give up ADAS driver assistance (L2)")
    assert first.endswith("for ₹1.35 lakh less.")
    assert not RAW_LABEL.search(first)
    assert "relative_label" not in ib.metrics


def test_scenario_3_long_trip_in_between_states_range(dataset: Dataset):
    """Golden 3 with a 300 km trip: the 79 kWh leads; the 59 kWh in-between states the
    real-world range gap and how it covers the trip."""
    result = _result(dataset, Needs(**SCENARIO_3))
    assert _slots(result, "best_match")[0].variant_key == "MAHINDRA-XEV9S-PACKONEABOVE-79"
    ib = _slots(result, "in_between")[0]
    assert ib.variant_key == "MAHINDRA-XEV9S-PACKONEABOVE-59"
    codes = {r.code: r.detail for r in ib.reasons}
    assert "478 km (tested)" in codes["range_tradeoff"]
    assert "300 km trip" in codes["range_tradeoff"]
    assert "more claimed range (521 → 679 km)" in codes["in_between"]


def test_same_model_step_up_with_range_advantage(dataset: Dataset):
    """Without the long trip the 59 kWh leads and the 79 kWh is the same-model step up,
    with its range advantage and a fit label."""
    needs = Needs(budget_max_inr=2500000, seats_min=7, daily_km=40, home_charging="yes")
    result = _result(dataset, needs)
    assert _slots(result, "best_match")[0].variant_key == "MAHINDRA-XEV9S-PACKONEABOVE-59"
    sm = _slots(result, "same_model")[0]
    assert sm.variant_key == "MAHINDRA-XEV9S-PACKONEABOVE-79"
    assert sm.metrics["relative_label"] == "Close second"
    codes = {r.code: r.detail for r in sm.reasons}
    assert "478 km (tested)" in codes["range_advantage"]
    assert "more claimed range (521 → 679 km)" in codes["same_model_step_up"]


def test_dont_overpay_different_model_leads_with_compromises(dataset: Dataset):
    """Scenario 1: Tiago.ev Smart 19 vs top pick Punch.ev Smart 30. The main reason states
    the safety compromises (ESP, crash test first), not only the saving."""
    result = _result(dataset, Needs(**SCENARIO_1))
    best = _slots(result, "best_match")[0]
    do = _slots(result, "dont_overpay")[0]
    assert do.variant_key == "TATA-TIAGOEV-SMART19-192"
    assert do.savings_vs_best_inr == best.price_inr - do.price_inr
    main = do.reasons[0]
    assert main.code == "saving_with_compromises"
    assert main.detail.startswith("₹2.80 lakh less than the top pick (Punch.ev Smart 30), but: ")
    assert main.detail.index("ESP not listed") < main.detail.index("no Bharat NCAP crash test")
    assert "31.09/32" in main.detail
    assert "relative_label" not in do.metrics


def test_dont_overpay_same_model_adds_at_most_five_plain_items(dataset: Dataset):
    """Scenario 5 (no home charging): at most 5 plain-word items, range first."""
    result = _result(dataset, Needs(**SCENARIO_5))
    do = _slots(result, "dont_overpay")[0]
    adds = next(r.detail for r in do.reasons if r.code == "ladder_gives_up")
    items = adds.removeprefix("What the top pick adds over this: ").rstrip(".")
    assert not RAW_LABEL.search(adds)
    assert len(re.split(r", | and (?![^(]*\))", items)) <= MAX_TOP_PICK_ADDS
    assert items.startswith("bigger battery") or items.startswith("more claimed range")


def test_no_in_between_when_best_is_base(dataset: Dataset):
    """Scenario 1: best match has no eligible step down, so no in_between."""
    result = _result(dataset, Needs(**SCENARIO_1))
    assert len(_slots(result, "in_between")) == 0


def test_ladder_gains_plain_words_and_order():
    needs = Needs(**SCENARIO_5)
    changes = parse_ladder(
        "Audio: 4 speakers → 8 speakers; Upholstery: — → Leatherette; "
        "Sunroof: None → Panoramic; Battery kWh: 30 → 40; ESP: Yes → Not stated; "
        "Charger in box: Unclear → Yes (7.2 kW)"
    )
    # No home charging: range first, wall charger dropped, "Not stated" is not a gain
    assert ladder_gains(changes, needs) == [
        "bigger battery (30 → 40 kWh)", "leatherette seats", "panoramic sunroof",
        "better sound system (8 speakers)",
    ]


def test_multi_step_ladder_gains_merge_fields(dataset: Dataset):
    """Punch.ev Smart 30 → Empowered+ S 40 spans several ladder steps; each feature once."""
    gains = _collect_ladder_gains(
        "TATA-PUNCHEV-SMART30-30", "TATA-PUNCHEV-EMPOWEREDPLUSS40-40", dataset, Needs(**SCENARIO_1),
    )
    text = ", ".join(gains)
    assert text.count("camera") == 1
    assert text.count("screens") == 1
    assert "360° camera" in text
