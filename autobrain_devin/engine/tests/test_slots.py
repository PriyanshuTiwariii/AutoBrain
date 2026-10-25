"""Tests for slot assignment logic."""
from __future__ import annotations

from app.eligibility import check_all
from app.models import Needs
from app.scoring import rank_variants
from app.slots import assign_slots, build_result


def test_zero_eligible_empty_slots():
    """If nothing qualifies, no positive slots and unknowns has the message."""
    from tests.test_eligibility import _make_variant
    # A variant that will fail on budget
    v = _make_variant(price_inr=5000000)
    needs = Needs(budget_max_inr=1000000, seats_min=4, daily_km=40, home_charging="yes")
    result = build_result(needs, [v], "test", "0.1.0")
    positive = [s for s in result.slots if s.slot != "not_recommended"]
    assert len(positive) == 0
    assert any("None of the vehicles" in u for u in result.unknowns)


def test_single_eligible_only_best_match():
    """If only 1 variant is eligible, only best_match — no forced alternative."""
    from tests.test_eligibility import _make_variant
    v = _make_variant(price_inr=1500000)
    needs = Needs(budget_max_inr=2000000, seats_min=4, daily_km=40, home_charging="yes")
    result = build_result(needs, [v], "test", "0.1.0")
    slot_types = [s.slot for s in result.slots]
    assert "best_match" in slot_types
    assert "strong_alternative" not in slot_types


def test_dont_overpay_only_when_cheaper_exists():
    """dont_overpay slot only appears if a cheaper eligible variant exists."""
    from tests.test_eligibility import _make_variant
    # v1 scores higher (better features) but costs more
    v1 = _make_variant(
        variant_key="BEST-1", price_inr=1800000, model="Model.A",
        adas="L2+", camera="540°", sunroof="Panoramic",
        ncap_status="Rated, applies", ncap_adult_32=30.0,
        range_tested_km=400, efficiency_basis="Independent test",
    )
    # v2 is cheaper but has fewer features
    v2 = _make_variant(
        variant_key="CHEAP-1", price_inr=1200000, model="Model.B",
        adas="None", camera="Rear camera", sunroof="None",
        ncap_status="Not tested", ncap_adult_32=None,
        range_tested_km=None, efficiency_basis="Maker real-world claim (estimate)",
    )
    needs = Needs(
        budget_max_inr=2000000, seats_min=4, daily_km=40,
        home_charging="yes", priority="safety",
    )
    result = build_result(needs, [v1, v2], "test", "0.1.0")
    slot_types = [s.slot for s in result.slots]
    assert "dont_overpay" in slot_types
    overpay_slot = [s for s in result.slots if s.slot == "dont_overpay"][0]
    assert overpay_slot.savings_vs_best_inr is not None
    assert overpay_slot.savings_vs_best_inr > 0


def test_not_recommended_shows_excluded_with_reasons():
    """Excluded variants appear in not_recommended with fail reasons."""
    from tests.test_eligibility import _make_variant
    v_good = _make_variant(variant_key="GOOD-1", price_inr=1500000, model="Model.A")
    v_bad = _make_variant(
        variant_key="BAD-1", price_inr=3000000, model="Model.B",
    )
    needs = Needs(budget_max_inr=2000000, seats_min=4, daily_km=40, home_charging="yes")
    result = build_result(needs, [v_good, v_bad], "test", "0.1.0")
    not_rec = [s for s in result.slots if s.slot == "not_recommended"]
    assert len(not_rec) >= 1
    assert not_rec[0].variant_key == "BAD-1"
    assert len(not_rec[0].reasons) > 0


def test_result_has_required_fields():
    """Result JSON must have all required fields from result.schema.json."""
    from tests.test_eligibility import _make_variant
    v = _make_variant(price_inr=1500000)
    needs = Needs(budget_max_inr=2000000, seats_min=4, daily_km=40, home_charging="yes")
    result = build_result(needs, [v], "test", "0.1.0")
    assert result.result_id
    assert result.dataset_version == "test"
    assert result.engine_version == "0.1.0"
    assert isinstance(result.needs_summary, list)
    assert isinstance(result.slots, list)
    assert isinstance(result.unknowns, list)
    assert result.disclaimer
