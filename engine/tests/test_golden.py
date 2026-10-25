"""Golden scenario tests from CHANGES.md §9. Assert eligible sets and flags, not exact scores."""
from __future__ import annotations

from app.dataset import Dataset
from app.eligibility import check_all
from app.models import Needs
from app.scoring import rank_variants
from app.slots import build_result


def _eligible_keys(dataset: Dataset, needs: Needs) -> set[str]:
    """Return set of variant_keys that pass eligibility (battery-included only by default)."""
    eligibility = check_all(dataset.variants, needs)
    return {
        er.variant_key for er in eligibility
        if er.status in ("eligible", "eligible_with_unknowns")
    }


def _ranked_results(dataset: Dataset, needs: Needs):
    """Return (ranked list, full result)."""
    result = build_result(needs, dataset.variants, dataset.version, dataset.engine_version, dataset=dataset)
    eligibility = check_all(dataset.variants, needs)
    ranked = rank_variants(dataset.variants, eligibility, needs)
    return ranked, result


# ---------------------------------------------------------------------------
# Scenario 1: Budget ₹10L, seats≥4, 30 km/day, home charging
# ---------------------------------------------------------------------------

def test_golden_1_eligible_set(dataset: Dataset):
    needs = Needs(
        budget_max_inr=1000000, seats_min=4, daily_km=30, home_charging="yes",
    )
    eligible = _eligible_keys(dataset, needs)
    expected = {
        "TATA-PUNCHEV-SMART30-30",
        "TATA-TIAGOEV-SMART19-192",
        "TATA-TIAGOEV-PUREPLUS19-192",
        "TATA-TIAGOEV-PUREPLUS24-24",
    }
    assert eligible == expected, f"Expected {expected}, got {eligible}"


def test_golden_1_esp_flags(dataset: Dataset):
    """Every Tiago.ev shows 'ESP not listed'; Punch.ev Smart 30 shows ESP Yes."""
    needs = Needs(
        budget_max_inr=1000000, seats_min=4, daily_km=30, home_charging="yes",
    )
    ranked, result = _ranked_results(dataset, needs)

    for rv in ranked:
        v = rv.variant
        if v.model == "Tiago.ev":
            assert v.esp != "Yes", f"{v.variant_key} should not have ESP Yes"
            assert "ESP not listed" in v.watch_outs, (
                f"{v.variant_key} missing 'ESP not listed' in watch_outs"
            )
        if v.variant_key == "TATA-PUNCHEV-SMART30-30":
            assert v.esp == "Yes", "Punch.ev Smart 30 should have ESP Yes"


# ---------------------------------------------------------------------------
# Scenario 2: Budget ₹20L, seats≥4, 40 km/day, adaptive_suspension nice-to-have
# ---------------------------------------------------------------------------

def test_golden_2_eligible_count(dataset: Dataset):
    needs = Needs(
        budget_max_inr=2000000, seats_min=4, daily_km=40, home_charging="yes",
        nice_to_haves=["adaptive_suspension"],
    )
    eligible = _eligible_keys(dataset, needs)
    assert len(eligible) == 25, f"Expected 25 eligible, got {len(eligible)}: {sorted(eligible)}"


def test_golden_2_no_adaptive_in_budget(dataset: Dataset):
    """None of the eligible variants has adaptive_suspension=Yes."""
    needs = Needs(
        budget_max_inr=2000000, seats_min=4, daily_km=40, home_charging="yes",
        nice_to_haves=["adaptive_suspension"],
    )
    eligible = _eligible_keys(dataset, needs)
    for key in eligible:
        v = dataset.get_variant(key)
        assert v is not None
        assert v.adaptive_suspension != "Yes", (
            f"{key} has adaptive_suspension=Yes but shouldn't"
        )


def test_golden_2_says_suspension_evidence_limited(dataset: Dataset):
    needs = Needs(
        budget_max_inr=2000000, seats_min=4, daily_km=40, home_charging="yes",
        nice_to_haves=["adaptive_suspension"],
    )
    _, result = _ranked_results(dataset, needs)
    assert "Adaptive suspension evidence is limited." in result.unknowns


def test_golden_2_ground_clearance_not_stated(dataset: Dataset):
    """Tiago.ev and Tigor.ev variants show ground_clearance as Not stated."""
    needs = Needs(
        budget_max_inr=2000000, seats_min=4, daily_km=40, home_charging="yes",
        nice_to_haves=["adaptive_suspension"],
    )
    eligible = _eligible_keys(dataset, needs)
    for key in eligible:
        v = dataset.get_variant(key)
        assert v is not None
        if v.model in ("Tiago.ev", "Tigor.ev"):
            assert v.ground_clearance_mm is None, (
                f"{key} should have blank ground_clearance_mm"
            )


# ---------------------------------------------------------------------------
# Scenario 3: Budget ₹25L, seats≥7, long trips
# ---------------------------------------------------------------------------

def test_golden_3_eligible_set(dataset: Dataset):
    needs = Needs(
        budget_max_inr=2500000, seats_min=7, daily_km=40, longest_regular_trip_km=300, home_charging="yes",
    )
    eligible = _eligible_keys(dataset, needs)
    expected = {
        "MAHINDRA-XEV9S-PACKONEABOVE-59",
        "MAHINDRA-XEV9S-PACKONEABOVE-79",
    }
    assert eligible == expected, f"Expected {expected}, got {eligible}"


def test_golden_3_ncap_and_charger_flags(dataset: Dataset):
    """Both show 'No Bharat NCAP crash test' and the ~₹60,000 charger note."""
    needs = Needs(
        budget_max_inr=2500000, seats_min=7, daily_km=40, longest_regular_trip_km=300, home_charging="yes",
    )
    eligible = _eligible_keys(dataset, needs)
    for key in eligible:
        v = dataset.get_variant(key)
        assert v is not None
        assert "No Bharat NCAP crash test" in v.watch_outs, (
            f"{key} missing crash test warning"
        )
        assert "60,000" in v.watch_outs, (
            f"{key} missing charger cost note"
        )


# ---------------------------------------------------------------------------
# Scenario 4: Budget ₹18L, seats≥5, must adas + crash_tested
# ---------------------------------------------------------------------------

def test_golden_4_eligible_set(dataset: Dataset):
    needs = Needs(
        budget_max_inr=1800000, seats_min=5, daily_km=40, home_charging="yes",
        must_haves=["adas", "crash_tested"],
    )
    eligible = _eligible_keys(dataset, needs)
    expected = {"TATA-NEXONEV-EMPOWEREDPLUSA45-45"}
    assert eligible == expected, f"Expected {expected}, got {eligible}"


def test_golden_4_xuv3xo_in_why_not(dataset: Dataset):
    """XUV3XOEV-AX7L-394 has ADAS but is not crash-tested → appears in why-not (CHANGES.md §9)."""
    needs = Needs(
        budget_max_inr=1800000, seats_min=5, daily_km=40, home_charging="yes",
        must_haves=["adas", "crash_tested"],
    )
    _, result = _ranked_results(dataset, needs)
    not_rec = {s.variant_key: s for s in result.slots if s.slot == "not_recommended"}
    assert "MAHINDRA-XUV3XOEV-AX7L-394" in not_rec, (
        f"Expected XUV3XOEV-AX7L-394 in why-not, got {list(not_rec)}"
    )
    reasons = [r.detail for r in not_rec["MAHINDRA-XUV3XOEV-AX7L-394"].reasons]
    assert reasons == ["Crash test rating: not available"]
    assert not_rec["MAHINDRA-XUV3XOEV-AX7L-394"].confidence == ""


# ---------------------------------------------------------------------------
# Scenario 5: Budget ₹15L, seats≥4, 40 km/day, home_charging=no
# ---------------------------------------------------------------------------

def test_golden_5_includes_expected_models(dataset: Dataset):
    needs = Needs(
        budget_max_inr=1500000, seats_min=4, daily_km=40, home_charging="no",
    )
    eligible = _eligible_keys(dataset, needs)
    models_present = {dataset.get_variant(k).model for k in eligible if dataset.get_variant(k)}
    for expected_model in ("Punch.ev", "Nexon.ev", "Tiago.ev", "Tigor.ev", "XUV 3XO EV"):
        assert expected_model in models_present, (
            f"Expected {expected_model} in eligible models, got {models_present}"
        )


def test_golden_5_slow_dc_flagged(dataset: Dataset):
    """Specific variants must carry 'Slow DC fast-charging' in watch_outs."""
    needs = Needs(
        budget_max_inr=1500000, seats_min=4, daily_km=40, home_charging="no",
    )
    eligible = _eligible_keys(dataset, needs)

    slow_dc_expected = {
        "MAHINDRA-XUV3XOEV-AX5-394",
    }
    # All Tiago.ev and Tigor.ev in eligible set
    for key in eligible:
        v = dataset.get_variant(key)
        if v and v.model in ("Tiago.ev", "Tigor.ev"):
            slow_dc_expected.add(key)
    # Both Nexon.ev MR variants
    for key in eligible:
        v = dataset.get_variant(key)
        if v and v.model == "Nexon.ev" and "MR" in v.variant:
            slow_dc_expected.add(key)

    for key in slow_dc_expected:
        if key not in eligible:
            continue
        v = dataset.get_variant(key)
        assert v is not None
        assert "Slow DC fast-charging" in v.watch_outs, (
            f"{key} missing 'Slow DC fast-charging' in watch_outs"
        )


def test_golden_5_ranking_favors_dc(dataset: Dataset):
    """Ranking should favor variants with better DC charging when home_charging=no."""
    needs = Needs(
        budget_max_inr=1500000, seats_min=4, daily_km=40, home_charging="no",
    )
    ranked, _ = _ranked_results(dataset, needs)
    assert len(ranked) > 1
    # Top-ranked variant should have reasonable DC charging
    top = ranked[0].variant
    assert top.dc_avg_kw_est is not None, "Top variant should have dc_avg_kw_est"


def test_golden_5_best_match_not_slow_dc(dataset: Dataset):
    """Best match for scenario 5 (no home charging) must not be a slow-DC variant."""
    from app.scoring import SLOW_DC_THRESHOLD_KW
    needs = Needs(
        budget_max_inr=1500000, seats_min=4, daily_km=40, home_charging="no",
    )
    _, result = _ranked_results(dataset, needs)
    best = [s for s in result.slots if s.slot == "best_match"]
    assert len(best) == 1
    best_key = best[0].variant_key
    v = dataset.get_variant(best_key)
    assert v is not None
    assert v.dc_avg_kw_est is not None, f"Best match {best_key} has no DC data"
    assert v.dc_avg_kw_est >= SLOW_DC_THRESHOLD_KW, (
        f"Best match {best_key} has slow DC ({v.dc_avg_kw_est} kW < {SLOW_DC_THRESHOLD_KW} kW)"
    )


def test_golden_5_no_slow_dc_recommended_to_save_money(dataset: Dataset):
    """Without home charging, the 'don't overpay' pick must not be a slow-DC variant."""
    from app.scoring import SLOW_DC_THRESHOLD_KW
    needs = Needs(budget_max_inr=1500000, seats_min=4, daily_km=40, home_charging="no")
    _, result = _ranked_results(dataset, needs)
    for s in result.slots:
        if s.slot == "dont_overpay":
            assert dataset.get_variant(s.variant_key).dc_avg_kw_est >= SLOW_DC_THRESHOLD_KW


def test_golden_5_running_cost_uses_public_dc_tariff(dataset: Dataset):
    """No home charging → running cost at the 90% public-DC blend (₹20.6/kWh), not the ₹9.4 default."""
    from app.costs import BLENDED_TARIFF_NO_HOME
    needs = Needs(budget_max_inr=1500000, seats_min=4, daily_km=40, home_charging="no")
    _, result = _ranked_results(dataset, needs)
    best = [s for s in result.slots if s.slot == "best_match"][0]
    v = dataset.get_variant(best.variant_key)
    expected = round(BLENDED_TARIFF_NO_HOME / v.efficiency_km_per_kwh, 2)
    assert best.metrics["running_cost_inr_per_km"] == expected
    assert best.metrics["running_cost_inr_per_km"] > v.running_cost_inr_per_km_default


# ---------------------------------------------------------------------------
# Scenario 6: Budget ₹8L, seats≥7, must awd → nothing qualifies
# ---------------------------------------------------------------------------

def test_golden_6_nothing_qualifies(dataset: Dataset):
    needs = Needs(
        budget_max_inr=800000, seats_min=7, daily_km=40, home_charging="yes",
        must_haves=["awd"],
    )
    eligible = _eligible_keys(dataset, needs)
    assert len(eligible) == 0, f"Expected 0 eligible, got {len(eligible)}: {eligible}"


def test_golden_6_result_says_nothing_qualifies(dataset: Dataset):
    needs = Needs(
        budget_max_inr=800000, seats_min=7, daily_km=40, home_charging="yes",
        must_haves=["awd"],
    )
    _, result = _ranked_results(dataset, needs)
    positive_slots = [s for s in result.slots if s.slot != "not_recommended"]
    assert len(positive_slots) == 0
    assert any("None of the vehicles" in u for u in result.unknowns), (
        f"Expected 'nothing qualifies' message, got unknowns={result.unknowns}"
    )
