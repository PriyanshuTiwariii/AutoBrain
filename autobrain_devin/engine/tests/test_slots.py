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
    # v1 scores highest (safety features) and costs most
    v1 = _make_variant(
        variant_key="BEST-1", price_inr=1800000, model="Model.A",
        adas="L2+", camera="540°", sunroof="Panoramic",
        ncap_status="Rated, applies", ncap_adult_32=30.0,
        range_tested_km=400, efficiency_basis="Independent test",
    )
    # v2 different model (will be strong_alternative)
    v2 = _make_variant(
        variant_key="ALT-1", price_inr=1600000, model="Model.B",
        adas="None", camera="Rear camera", sunroof="None",
        ncap_status="Rated, applies", ncap_adult_32=25.0,
        range_tested_km=350, efficiency_basis="Independent test",
    )
    # v3 is cheapest (will be dont_overpay)
    v3 = _make_variant(
        variant_key="CHEAP-1", price_inr=1200000, model="Model.C",
        adas="None", camera="Rear camera", sunroof="None",
        ncap_status="Not tested", ncap_adult_32=None,
        range_tested_km=None, efficiency_basis="Maker real-world claim (estimate)",
    )
    needs = Needs(
        budget_max_inr=2000000, seats_min=4, daily_km=40,
        home_charging="yes", priority="safety",
    )
    result = build_result(needs, [v1, v2, v3], "test", "0.1.0")
    slot_types = [s.slot for s in result.slots]
    assert "dont_overpay" in slot_types
    overpay_slot = [s for s in result.slots if s.slot == "dont_overpay"][0]
    assert overpay_slot.savings_vs_best_inr is not None
    assert overpay_slot.savings_vs_best_inr > 0


def test_not_recommended_shows_excluded_with_reasons():
    """Near-miss excluded variants (within 10% over budget) appear in not_recommended."""
    from tests.test_eligibility import _make_variant
    v_good = _make_variant(variant_key="GOOD-1", price_inr=1500000, model="Model.A")
    # Just over budget (₹2.1L vs ₹2L limit = 5% over, within 10% ceiling)
    v_near = _make_variant(
        variant_key="NEAR-1", price_inr=2100000, model="Model.B",
    )
    needs = Needs(budget_max_inr=2000000, seats_min=4, daily_km=40, home_charging="yes")
    result = build_result(needs, [v_good, v_near], "test", "0.1.0")
    not_rec = [s for s in result.slots if s.slot == "not_recommended"]
    assert len(not_rec) >= 1
    assert not_rec[0].variant_key == "NEAR-1"
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


def test_tradeoffs_do_not_repeat_watch_outs(dataset):
    """A trade-off already covered by a watch-out (e.g. ESP, NCAP, charger) is not repeated."""
    for needs in (
        Needs(budget_max_inr=1000000, seats_min=4, daily_km=30, home_charging="yes"),
        Needs(budget_max_inr=2500000, seats_min=7, daily_km=40, home_charging="yes"),
        Needs(budget_max_inr=1500000, seats_min=4, daily_km=40, home_charging="no"),
    ):
        result = build_result(needs, dataset.variants, dataset.version, dataset.engine_version, dataset=dataset)
        for s in result.slots:
            wo = " ".join(s.watch_outs).lower()
            codes = {t.code for t in s.tradeoffs}
            if "esp not listed" in wo:
                assert "esp_not_listed" not in codes
            if "ncap" in wo:
                assert "no_crash_test" not in codes
            if "charger" in wo:
                assert "charger_extra" not in codes


def test_why_not_is_near_misses_only(dataset):
    """Why-not: at most 3, one model each, exactly one failed need, never a seat-count miss,
    budget misses within 10%."""
    needs = Needs(budget_max_inr=2500000, seats_min=7, daily_km=40, home_charging="yes")
    result = build_result(needs, dataset.variants, dataset.version, dataset.engine_version, dataset=dataset)
    not_rec = [s for s in result.slots if s.slot == "not_recommended"]
    assert len(not_rec) <= 3
    assert len({dataset.get_variant(s.variant_key).model for s in not_rec}) == len(not_rec)
    for s in not_rec:
        assert len(s.reasons) == 1
        assert "seats" not in s.reasons[0].detail
        assert s.confidence == ""
        v = dataset.get_variant(s.variant_key)
        assert v.seats >= 7


def test_fmt_lakh():
    from app.explain import fmt_lakh
    assert fmt_lakh(699000) == "₹6.99 lakh"
    assert fmt_lakh(200000) == "₹2 lakh"
    assert fmt_lakh(60000) == "₹60,000"
    assert fmt_lakh(None) == "price not confirmed"


def _charger_variant(**kw):
    from tests.test_eligibility import _make_variant
    return _make_variant(
        variant_key="CHG-1", price_inr=1480000, charger_included="No", charger_cost_inr=50000,
        efficiency_km_per_kwh=7.0, **kw,
    )


def test_no_home_charging_adds_no_charger_cost():
    from app.costs import compute_costs
    from app.eligibility import check_eligibility
    v = _charger_variant()
    needs = Needs(budget_max_inr=1500000, seats_min=4, daily_km=40, home_charging="no")
    c = compute_costs(v, needs)
    assert c.total_budget_cost_inr == 1480000
    assert c.charger_cost_inr is None
    assert c.cost_to_own_5yr_inr == round((1480000 + c.electricity_5yr_inr) / 1000) * 1000
    # ₹14.8L + ₹50,000 charger would be over ₹15L; without home charging it fits
    assert check_eligibility(v, needs).checks["budget"].value == "PASS"


def test_unsure_home_charging_includes_assumed_charger():
    from app.costs import compute_costs
    v = _charger_variant()
    needs = Needs(budget_max_inr=1600000, seats_min=4, daily_km=40, home_charging="unsure")
    c = compute_costs(v, needs)
    assert c.total_budget_cost_inr == 1530000
    assert "assumed home charger" in c.charger_note


def test_estimates_rounded_to_nearest_thousand(dataset):
    needs = Needs(budget_max_inr=2500000, seats_min=7, daily_km=40, home_charging="yes")
    result = build_result(needs, dataset.variants, dataset.version, dataset.engine_version, dataset=dataset)
    for s in result.slots:
        for key in ("electricity_5yr_inr", "cost_to_own_5yr_inr"):
            val = s.metrics.get(key)
            if val is not None:
                assert val % 1000 == 0, f"{s.variant_key} {key}={val}"
        # Official prices stay exact
        assert s.price_inr == dataset.get_variant(s.variant_key).price_inr


def test_alternative_reasons_are_real_advantages(dataset):
    """Never 'different model'; cost difference only when >= ₹25,000; and an
    alternative is shown only with at least one advantage."""
    from app.slots import MIN_5YR_COST_DIFF_INR
    for needs in (
        Needs(budget_max_inr=1000000, seats_min=4, daily_km=30, home_charging="yes"),
        Needs(budget_max_inr=1500000, seats_min=4, daily_km=40, home_charging="no"),
        Needs(budget_max_inr=2000000, seats_min=4, daily_km=40, home_charging="yes"),
    ):
        result = build_result(needs, dataset.variants, dataset.version, dataset.engine_version, dataset=dataset)
        best = [s for s in result.slots if s.slot == "best_match"][0]
        for alt in [s for s in result.slots if s.slot == "strong_alternative"]:
            assert alt.reasons
            for r in alt.reasons:
                assert "different model" not in r.detail.lower()
                assert r.code not in ("alt_model", "alt_brand", "alt_eligible")
            if any(r.code == "lower_5yr" for r in alt.reasons):
                diff = best.metrics["cost_to_own_5yr_inr"] - alt.metrics["cost_to_own_5yr_inr"]
                assert diff >= MIN_5YR_COST_DIFF_INR


def test_alternative_names_safety_differences_both_ways():
    from tests.test_eligibility import _make_variant
    best = _make_variant(
        variant_key="BEST-1", model="Model.A", price_inr=1500000, esp="Yes",
        ncap_status="Rated, applies", ncap_adult_32=30.0, airbags=6,
        adas="L2", camera="360°", range_tested_km=400, efficiency_basis="Independent test",
    )
    alt = _make_variant(
        variant_key="ALT-1", model="Model.B", price_inr=1400000, esp="Not listed",
        ncap_status="Not tested", airbags=2, adas="None",
        range_tested_km=450, efficiency_basis="Independent test",
    )
    needs = Needs(budget_max_inr=2000000, seats_min=4, daily_km=40, home_charging="yes", priority="safety")
    result = build_result(needs, [best, alt], "test", "0.1.0")
    alt_slot = [s for s in result.slots if s.slot == "strong_alternative"][0]
    assert any(r.code == "better_range" for r in alt_slot.reasons)
    safety = [t.detail for t in alt_slot.tradeoffs if t.code == "safety_vs_top_pick"]
    assert any("ESP standard" in d and "ESP not listed by maker" in d for d in safety)
    assert any("Bharat NCAP rating applies" in d for d in safety)
    assert any("6 airbags" in d for d in safety)


def test_alternative_without_advantage_not_shown():
    from tests.test_eligibility import _make_variant
    best = _make_variant(
        variant_key="BEST-1", model="Model.A", price_inr=1500000, esp="Yes",
        ncap_status="Rated, applies", ncap_adult_32=30.0, range_tested_km=400,
        efficiency_basis="Independent test",
    )
    weaker = _make_variant(
        variant_key="WEAK-1", model="Model.B", price_inr=1500000, esp="Yes",
        ncap_status="Rated, applies", ncap_adult_32=25.0, range_tested_km=300,
        efficiency_basis="Independent test",
    )
    needs = Needs(budget_max_inr=2000000, seats_min=4, daily_km=40, home_charging="yes", priority="safety")
    result = build_result(needs, [best, weaker], "test", "0.1.0")
    assert "strong_alternative" not in [s.slot for s in result.slots]


def test_wall_charger_watch_out_hidden_only_without_home_charging(dataset):
    """home_charging='no' hides the 'Wall charger not in price' watch-out and nothing else;
    with home charging it is shown."""
    key = "TATA-NEXONEV-CREATIVE45-45"
    raw = [w.strip() for w in dataset.get_variant(key).watch_outs.split(";") if w.strip()]
    assert any(w.startswith("Wall charger not in price") for w in raw)

    def watch_outs_for(home_charging: str) -> list[str]:
        needs = Needs(budget_max_inr=1500000, seats_min=4, daily_km=40, home_charging=home_charging)
        result = build_result(needs, dataset.variants, dataset.version, dataset.engine_version, dataset=dataset)
        return [s for s in result.slots if s.variant_key == key][0].watch_outs

    assert watch_outs_for("no") == [w for w in raw if not w.startswith("Wall charger not in price")]
    assert watch_outs_for("yes") == raw
    assert watch_outs_for("unsure") == raw
