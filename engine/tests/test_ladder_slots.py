"""Tests for ladder-powered same_model, in_between and dont_overpay slots."""
from __future__ import annotations

from app.dataset import Dataset
from app.models import Needs
from app.slots import _gain_phrases, build_result


def _result(dataset: Dataset, needs: Needs):
    return build_result(needs, dataset.variants, dataset.version, dataset.engine_version, dataset=dataset)


def _slots(result, slot_type: str):
    return [s for s in result.slots if s.slot == slot_type]


SAFETY_NEEDS = dict(
    budget_max_inr=1800000, seats_min=5, daily_km=40,
    home_charging="yes", priority="safety", must_haves=["crash_tested"],
)


def test_in_between_is_one_step_down_with_give_up_wording(dataset: Dataset):
    """Best match Nexon.ev Empowered+A 45 → Empowered 45 is the in-between,
    worded as 'you give up X for Y less'."""
    result = _result(dataset, Needs(**SAFETY_NEEDS))
    assert _slots(result, "best_match")[0].variant_key == "TATA-NEXONEV-EMPOWEREDPLUSA45-45"

    in_between = _slots(result, "in_between")
    assert len(in_between) == 1
    ib = in_between[0]
    assert ib.variant_key == "TATA-NEXONEV-EMPOWERED45-45"
    assert ib.savings_vs_best_inr == 135000
    first = ib.reasons[0].detail
    assert first.startswith("You give up ")
    assert "ADAS: L2" in first
    assert first.endswith("for ₹1.35 lakh less.")
    # Raw ladder arrows ("None → Sunroof") must not leak into give-up wording
    assert "→" not in first


def test_same_model_step_up_scenario_3(dataset: Dataset):
    """Scenario 3: XEV 9S One Above 79 kWh appears as same_model with its range advantage."""
    needs = Needs(budget_max_inr=2500000, seats_min=7, daily_km=40, home_charging="yes")
    result = _result(dataset, needs)
    assert _slots(result, "best_match")[0].variant_key == "MAHINDRA-XEV9S-PACKONEABOVE-59"

    same_model = _slots(result, "same_model")
    assert len(same_model) == 1
    sm = same_model[0]
    assert sm.variant_key == "MAHINDRA-XEV9S-PACKONEABOVE-79"
    assert sm.metrics["relative_label"] == "Close second"
    codes = {r.code: r.detail for r in sm.reasons}
    assert "range_advantage" in codes
    assert "478 km (tested)" in codes["range_advantage"]
    # Ladder range is the maker's claim, so it must be labelled as claimed
    assert "claimed range 521 → 679 km" in codes["same_model_step_up"]


def test_dont_overpay_with_ladder_context(dataset: Dataset):
    """Scenario 1: cheapest (Tiago.ev Smart 19) differs in model from the best match,
    so no ladder context; savings must equal the price gap."""
    needs = Needs(budget_max_inr=1000000, seats_min=4, daily_km=30, home_charging="yes")
    result = _result(dataset, needs)
    best = _slots(result, "best_match")[0]
    dont_overpay = _slots(result, "dont_overpay")
    assert len(dont_overpay) == 1
    do = dont_overpay[0]
    assert do.variant_key == "TATA-TIAGOEV-SMART19-192"
    assert do.savings_vs_best_inr == best.price_inr - do.price_inr
    assert do.reasons[0].code == "cheapest_eligible"


def test_no_in_between_when_best_is_base(dataset: Dataset):
    """Scenario 1: best match has no eligible step down, so no in_between."""
    needs = Needs(budget_max_inr=1000000, seats_min=4, daily_km=30, home_charging="yes")
    result = _result(dataset, needs)
    assert len(_slots(result, "in_between")) == 0


def test_gain_phrases():
    text = "Sunroof: None → Sunroof; Vent. seats: No → Yes; Battery kWh: 59 → 79; " \
           "Power tailgate: no → yes (gesture); ESP: Yes → Not stated"
    assert _gain_phrases(text) == [
        "Sunroof", "Vent. seats", "battery 59 → 79 kWh", "Power tailgate (gesture)",
    ]


def test_multi_step_ladder_gains_merge_fields(dataset: Dataset):
    """Scenario 5 'don't overpay' (Punch.ev Smart 30 vs Empowered+ S 40) spans several
    ladder steps; each field is listed once with its final value."""
    from app.slots import _collect_ladder_gains
    text = _collect_ladder_gains("TATA-PUNCHEV-SMART30-30", "TATA-PUNCHEV-EMPOWEREDPLUSS40-40", dataset)
    assert text is not None
    assert text.count("Camera") == 1
    assert text.count("Screens") == 1
    assert "Camera: 360°" in text
