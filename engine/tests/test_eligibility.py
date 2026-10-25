"""Tests for three-state eligibility checks."""
from __future__ import annotations

from app.eligibility import Check, check_eligibility
from app.models import Needs, Variant


def _make_variant(**overrides) -> Variant:
    """Create a minimal Variant with sensible defaults, overridden as needed."""
    defaults = dict(
        variant_key="TEST-VARIANT-1",
        sheet_id="V999",
        brand="Tata",
        model="Test.ev",
        body_type="SUV",
        variant="Test Variant",
        pricing_type="battery included",
        price_inr=1500000,
        price_status="verified",
        battery_kwh=45.0,
        drive="FWD",
        seats=5,
        seat_options="5",
        range_claimed_km=400,
        range_standard="MIDC",
        range_maker_realworld_km=300.0,
        range_tested_km=280,
        range_test_vehicle="Same model",
        tested_vs_claim_pct=70,
        efficiency_km_per_kwh=6.0,
        efficiency_basis="Independent test",
        charger_included="Yes (3.3 kW)",
        charger_cost_inr=0,
        charger_basis="Included",
        boot_l=350,
        ground_clearance_mm=200,
        battery_clearance_mm=190,
        airbags=6,
        esp="Yes",
        adas="L2",
        camera="360°",
        sunroof="Panoramic",
        ventilated_front="Yes",
        adaptive_suspension="No",
        dc_max_kw=50,
        dc_avg_kw_est=40.0,
        ac_full_hours_7kw=7.0,
        onboard_ac_kw=7.2,
        battery_warranty="Lifetime (1st owner)",
        ncap_status="Rated, applies",
        ncap_adult_32=29.0,
        ncap_child_49=42.0,
        terrain_modes=None,
        wading_mm=None,
        watch_outs="None flagged",
        running_cost_inr_per_km_default=1.57,
        cost_to_own_5yr_default=1600000,
        minutes_dc_per_100km_default=25,
    )
    defaults.update(overrides)
    return Variant(**defaults)


def _make_needs(**overrides) -> Needs:
    defaults = dict(
        budget_max_inr=2000000,
        seats_min=5,
        daily_km=40,
        home_charging="yes",
    )
    defaults.update(overrides)
    return Needs(**defaults)


# --- Budget tests ---

def test_over_budget_fails():
    v = _make_variant(price_inr=2500000)
    n = _make_needs(budget_max_inr=2000000)
    er = check_eligibility(v, n)
    assert er.status == "excluded"
    assert er.checks["budget"] == Check.FAIL


def test_within_budget_passes():
    v = _make_variant(price_inr=1500000)
    n = _make_needs(budget_max_inr=2000000)
    er = check_eligibility(v, n)
    assert er.checks["budget"] == Check.PASS


def test_budget_includes_charger():
    """Budget check must add charger_cost_inr when charger not included."""
    v = _make_variant(price_inr=1900000, charger_included="No", charger_cost_inr=60000)
    n = _make_needs(budget_max_inr=1950000, budget_includes_charger=True)
    er = check_eligibility(v, n)
    # 1900000 + 60000 = 1960000 > 1950000
    assert er.checks["budget"] == Check.FAIL


def test_unknown_price_is_unknown():
    v = _make_variant(price_inr=None, price_status="pending")
    n = _make_needs()
    er = check_eligibility(v, n)
    assert er.checks["budget"] == Check.UNKNOWN
    assert er.status in ("eligible_with_unknowns",)


# --- Seats tests ---

def test_seats_met():
    v = _make_variant(seats=5)
    n = _make_needs(seats_min=5)
    er = check_eligibility(v, n)
    assert er.checks["seats"] == Check.PASS


def test_seats_too_few():
    v = _make_variant(seats=4)
    n = _make_needs(seats_min=5)
    er = check_eligibility(v, n)
    assert er.checks["seats"] == Check.FAIL


def test_unknown_seats_with_min_5_is_unknown():
    """Seats blank + requirement < 6 → UNKNOWN, included with flag."""
    v = _make_variant(seats=None, seat_options="Not stated")
    n = _make_needs(seats_min=5)
    er = check_eligibility(v, n)
    assert er.checks["seats"] == Check.UNKNOWN
    assert er.status == "eligible_with_unknowns"


def test_unknown_seats_with_min_6_fails():
    """CHANGES.md §5: seats ≥ 6 requirement must NEVER pass as UNKNOWN."""
    v = _make_variant(seats=None, seat_options="Not stated")
    n = _make_needs(seats_min=6)
    er = check_eligibility(v, n)
    assert er.checks["seats"] == Check.FAIL
    assert er.status == "excluded"


# --- Feature tests ---

def test_must_have_adas_none_fails():
    v = _make_variant(adas="None")
    n = _make_needs(must_haves=["adas"])
    er = check_eligibility(v, n)
    assert er.checks["must_adas"] == Check.FAIL
    assert er.status == "excluded"


def test_must_have_adas_not_stated_is_unknown():
    v = _make_variant(adas="Not stated")
    n = _make_needs(must_haves=["adas"])
    er = check_eligibility(v, n)
    assert er.checks["must_adas"] == Check.UNKNOWN


def test_must_have_adas_l2_passes():
    v = _make_variant(adas="L2")
    n = _make_needs(must_haves=["adas"])
    er = check_eligibility(v, n)
    assert er.checks["must_adas"] == Check.PASS


def test_esp_never_fails():
    """ESP: 'Not listed' counts as UNKNOWN, never FAIL per CHANGES.md §4."""
    v = _make_variant(esp="Not listed")
    n = _make_needs(must_haves=["esp"])
    er = check_eligibility(v, n)
    assert er.checks["must_esp"] == Check.UNKNOWN
    assert er.status != "excluded"


def test_esp_not_stated_is_unknown():
    v = _make_variant(esp="Not stated")
    n = _make_needs(must_haves=["esp"])
    er = check_eligibility(v, n)
    assert er.checks["must_esp"] == Check.UNKNOWN


def test_crash_tested_rated_applies_passes():
    v = _make_variant(ncap_status="Rated, applies")
    n = _make_needs(must_haves=["crash_tested"])
    er = check_eligibility(v, n)
    assert er.checks["must_crash_tested"] == Check.PASS


def test_crash_tested_not_tested_fails():
    v = _make_variant(ncap_status="Not tested")
    n = _make_needs(must_haves=["crash_tested"])
    er = check_eligibility(v, n)
    assert er.checks["must_crash_tested"] == Check.FAIL


def test_crash_tested_coverage_unconfirmed_is_unknown():
    v = _make_variant(ncap_status="Rated, coverage unconfirmed")
    n = _make_needs(must_haves=["crash_tested"])
    er = check_eligibility(v, n)
    assert er.checks["must_crash_tested"] == Check.UNKNOWN


def test_awd_fwd_fails():
    v = _make_variant(drive="FWD")
    n = _make_needs(must_haves=["awd"])
    er = check_eligibility(v, n)
    assert er.checks["must_awd"] == Check.FAIL


def test_adaptive_suspension_yes_passes():
    v = _make_variant(adaptive_suspension="Yes")
    n = _make_needs(must_haves=["adaptive_suspension"])
    er = check_eligibility(v, n)
    assert er.checks["must_adaptive_suspension"] == Check.PASS


def test_adaptive_suspension_not_stated_is_unknown():
    v = _make_variant(adaptive_suspension="Not stated")
    n = _make_needs(must_haves=["adaptive_suspension"])
    er = check_eligibility(v, n)
    assert er.checks["must_adaptive_suspension"] == Check.UNKNOWN


# --- BaaS filter ---

def test_baas_excluded_when_pref_buy():
    v = _make_variant(pricing_type="BaaS")
    n = _make_needs(pricing_pref="buy")
    er = check_eligibility(v, n)
    assert er.checks["pricing_type"] == Check.FAIL
    assert er.status == "excluded"


def test_baas_included_when_pref_either():
    v = _make_variant(pricing_type="BaaS")
    n = _make_needs(pricing_pref="either")
    er = check_eligibility(v, n)
    assert er.checks["pricing_type"] == Check.PASS


# --- Body type ---

def test_body_type_match():
    v = _make_variant(body_type="SUV")
    n = _make_needs(body_types=["SUV"])
    er = check_eligibility(v, n)
    assert er.checks["body_type"] == Check.PASS


def test_body_type_mismatch():
    v = _make_variant(body_type="Hatchback")
    n = _make_needs(body_types=["SUV"])
    er = check_eligibility(v, n)
    assert er.checks["body_type"] == Check.FAIL


# --- Overall status ---

def test_eligible_no_unknowns():
    v = _make_variant()
    n = _make_needs()
    er = check_eligibility(v, n)
    assert er.status == "eligible"


def test_eligible_with_unknowns():
    v = _make_variant(adas="Not stated")
    n = _make_needs(must_haves=["adas"])
    er = check_eligibility(v, n)
    assert er.status == "eligible_with_unknowns"
    assert len(er.unknown_flags) > 0
