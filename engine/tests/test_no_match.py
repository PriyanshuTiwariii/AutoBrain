"""When nothing qualifies: the engine says why, names the closest option and what it would take."""
from __future__ import annotations

import json

import jsonschema

from app.contracts import RESULT_SCHEMA, result_errors
from app.costs import budget_cost
from app.dataset import Dataset
from app.eligibility import Check, check_all
from app.explain import fmt_lakh
from app.models import Needs
from app.slots import build_result
from tests.test_contract import GOLDEN_NEEDS
from tests.test_eligibility import _make_variant

SCENARIO_6 = Needs(**GOLDEN_NEEDS["6_nothing_qualifies"])  # ₹8 lakh, 7+ seats, must-have AWD


def _result(dataset: Dataset, needs: Needs):
    return build_result(needs, dataset.variants, dataset.version, dataset.engine_version, dataset=dataset)


def _failed_needs(er) -> list[str]:
    return [k for k, c in er.checks.items() if c == Check.FAIL and (k in ("budget", "seats") or k.startswith("must_"))]


# --- golden scenario 6 -------------------------------------------------------------------

def test_golden_6_lists_the_actual_reasons(dataset: Dataset):
    result = _result(dataset, SCENARIO_6)
    assert result.no_match is not None
    assert result.no_match.reasons == [
        "No variant within ₹8 lakh has 7 seats.",
        # Only one variant fits the budget and its drive is not stated, so "none has AWD" would be a guess
        "No variant within ₹8 lakh is confirmed to have AWD (not stated by the maker for Tata Tiago.ev Smart 19).",
    ]


def test_golden_6_states_plainly_that_nothing_qualifies_without_a_dangling_promise(dataset: Dataset):
    result = _result(dataset, SCENARIO_6)
    assert result.unknowns[0] == "None of the vehicles in our current dataset meet all your requirements."
    assert "Here's why" not in " ".join(result.unknowns)
    assert [s for s in result.slots if s.slot != "not_recommended"] == []


def test_golden_6_closest_option_and_what_it_would_take(dataset: Dataset):
    result = _result(dataset, SCENARIO_6)
    nm = result.no_match
    assert nm.closest_variant_key == "TATA-TIAGOEV-SMART19-192"
    assert nm.what_it_would_take == [
        "Accept 5 seats; you asked for 7.",
        "Confirm with the maker: AWD is not stated for this variant.",
    ]
    # The closest option is also returned as a card, with the engine's own fail reason
    assert [(s.slot, s.variant_key) for s in result.slots] == [("not_recommended", nm.closest_variant_key)]
    assert [r.detail for r in result.slots[0].reasons] == ["Only 5 seats (need 7+)"]
    assert result.slots[0].metrics["model"] == "Tiago.ev"


def test_golden_6_closest_really_is_the_closest(dataset: Dataset):
    """Brute force over the whole dataset: nobody misses fewer of the buyer's needs."""
    ers = {er.variant_key: er for er in check_all(dataset.variants, SCENARIO_6)}
    in_scope = [
        v for v in dataset.variants
        if ers[v.variant_key].checks["pricing_type"] != Check.FAIL
    ]
    fewest = min(len(_failed_needs(ers[v.variant_key])) for v in in_scope)
    closest = _result(dataset, SCENARIO_6).no_match.closest_variant_key
    assert len(_failed_needs(ers[closest])) == fewest


def test_golden_6_reasons_hold_for_every_variant(dataset: Dataset):
    """Each stated reason is true of the data: no in-budget variant passes the need it names."""
    ers = {er.variant_key: er for er in check_all(dataset.variants, SCENARIO_6)}
    in_budget = [v for v in dataset.variants
                 if ers[v.variant_key].checks["pricing_type"] != Check.FAIL and ers[v.variant_key].checks["budget"] != Check.FAIL]
    assert in_budget  # the reasons are about a real, non-empty set
    assert not any(ers[v.variant_key].checks["seats"] == Check.PASS for v in in_budget)
    assert not any(ers[v.variant_key].checks["must_awd"] == Check.PASS for v in in_budget)


def test_golden_6_result_matches_the_contract(dataset: Dataset):
    payload = json.loads(_result(dataset, SCENARIO_6).model_dump_json())
    jsonschema.validate(payload, RESULT_SCHEMA)
    assert result_errors(payload) == []
    assert set(payload["no_match"]) == {"reasons", "closest_variant_key", "what_it_would_take"}


def test_results_with_matches_have_no_no_match(dataset: Dataset):
    result = _result(dataset, Needs(**GOLDEN_NEEDS["1_budget_10L"]))
    assert result.no_match is None


# --- the other ways nothing can qualify ---------------------------------------------------

def test_budget_below_everything_names_the_cheapest(dataset: Dataset):
    needs = Needs(budget_max_inr=300_000, seats_min=4, daily_km=40, home_charging="yes")
    nm = _result(dataset, needs).no_match
    battery_included = [v for v in dataset.variants if v.pricing_type == "battery included" and budget_cost(v, needs) is not None]
    cheapest = min(battery_included, key=lambda v: (budget_cost(v, needs), v.variant_key))
    cost = budget_cost(cheapest, needs)
    assert nm.reasons == [
        f"No variant is priced within ₹3 lakh; the cheapest is {cheapest.brand} {cheapest.model} {cheapest.variant} at {fmt_lakh(cost)}."
    ]
    assert nm.closest_variant_key == cheapest.variant_key
    assert nm.what_it_would_take == [f"Raise your budget to at least {fmt_lakh(cost)}."]


def test_adas_plus_crash_test_on_real_data_says_not_confirmed(dataset: Dataset):
    """Within ₹11 lakh, no variant has ADAS stated: several are unstated (not "no"), so the engine
    says "not confirmed", and names for whom it is unstated."""
    needs = Needs(budget_max_inr=1_100_000, seats_min=5, daily_km=40, home_charging="yes", must_haves=["adas", "crash_tested"])
    result = _result(dataset, needs)
    [reason] = result.no_match.reasons
    assert reason.startswith("No variant within ₹11 lakh is confirmed to have ADAS (not stated by the maker for ")
    assert "and 1 more)." in reason  # more than three: the first three are named, the rest counted
    ers = {er.variant_key: er for er in check_all(dataset.variants, needs)}
    in_budget = [k for k, er in ers.items() if er.checks["pricing_type"] != Check.FAIL and er.checks["budget"] != Check.FAIL]
    assert not any(ers[k].checks["must_adas"] == Check.PASS for k in in_budget)
    assert any(ers[k].checks["must_adas"] == Check.UNKNOWN for k in in_budget)
    assert result.no_match.what_it_would_take == ['Drop "ADAS" from your must-haves: this variant does not have it.']


def test_needs_that_exist_separately_but_not_together():
    adas_only = _make_variant(variant_key="A", model="A.ev", adas="L2", ncap_status="Not tested")
    crash_only = _make_variant(variant_key="B", model="B.ev", adas="None", ncap_status="Rated, applies")
    nm = _build([adas_only, crash_only], must_haves=["adas", "crash_tested"]).no_match
    assert nm.reasons == ["No variant within ₹20 lakh has both ADAS and a Bharat NCAP crash-test rating for the EV."]


def test_choices_that_leave_no_variants(dataset: Dataset):
    needs = Needs(
        budget_max_inr=1_500_000, seats_min=4, daily_km=40, home_charging="yes",
        exclude_models=sorted({v.model for v in dataset.variants}),
    )
    result = _result(dataset, needs)
    assert result.slots == []
    assert result.no_match.closest_variant_key is None
    assert "leave no variants to consider" in result.no_match.reasons[0]


# --- the wording rules, on small hand-made data --------------------------------------------

def _build(variants, **needs):
    base = dict(budget_max_inr=2_000_000, seats_min=4, daily_km=40, home_charging="yes")
    return build_result(Needs(**{**base, **needs}), variants, "test", "0.1.0")


def test_not_confirmed_is_not_the_same_as_none_has_it():
    fwd = _make_variant(variant_key="A", model="A.ev", drive="FWD")
    # every in-budget variant is FWD: it is true that none has AWD
    assert _build([fwd], must_haves=["awd"]).no_match.reasons == ["No variant within ₹20 lakh has AWD."]
    # B's drive is not stated (and B fails on seats): we cannot say none has AWD, only that none is confirmed
    unstated = _make_variant(variant_key="B", model="B.ev", drive="Not stated", seats=3)
    nm = _build([fwd, unstated], must_haves=["awd"], seats_min=4).no_match
    assert nm.reasons == ["No variant within ₹20 lakh is confirmed to have AWD (not stated by the maker for Tata B.ev Test Variant)."]
    # A and B each miss exactly one need; A wins the tie (same overrun, same price, earlier key)
    assert nm.closest_variant_key == "A"
    assert nm.what_it_would_take == ['Drop "AWD" from your must-haves: this variant does not have it.']

    # When the unstated-drive car is the closest, we say what to check instead of guessing
    only_b = _build([unstated], must_haves=["awd"], seats_min=4).no_match
    assert only_b.closest_variant_key == "B"
    assert only_b.what_it_would_take == [
        "Accept 3 seats; you asked for 4 or more.",
        "Confirm with the maker: AWD is not stated for this variant.",
    ]


def test_seats_wording():
    cars = [_make_variant(variant_key="A", seats=5)]
    assert _build(cars, seats_min=6).no_match.reasons == ["No variant within ₹20 lakh has 6 or more seats."]
    assert _build(cars, seats_min=7).no_match.reasons == ["No variant within ₹20 lakh has 7 seats."]


def test_budget_what_it_would_take_includes_the_wall_charger_only_when_it_counts():
    car = _make_variant(variant_key="A", price_inr=790_000, charger_included="No", charger_cost_inr=60_000)
    with_home = _build([car], budget_max_inr=800_000, home_charging="yes").no_match
    assert with_home.what_it_would_take == ["Raise your budget to at least ₹8.50 lakh, which includes ~₹60,000 for the wall charger."]
    no_home = _build([car], budget_max_inr=700_000, home_charging="no").no_match
    assert no_home.what_it_would_take == ["Raise your budget to at least ₹7.90 lakh."]


def test_closest_prefers_fewer_missed_needs_then_smaller_overrun():
    two_misses = _make_variant(variant_key="TWO", model="Two.ev", seats=4, price_inr=1_000_000, drive="FWD")
    one_miss_far = _make_variant(variant_key="ONE-FAR", model="OneFar.ev", seats=7, price_inr=2_500_000, drive="AWD")
    one_miss_near = _make_variant(variant_key="ONE-NEAR", model="OneNear.ev", seats=7, price_inr=2_100_000, drive="AWD")
    nm = _build([two_misses, one_miss_far, one_miss_near], budget_max_inr=2_000_000, seats_min=7, must_haves=["awd"]).no_match
    assert nm.closest_variant_key == "ONE-NEAR"
    assert nm.what_it_would_take == ["Raise your budget to at least ₹21 lakh."]


def test_what_it_would_take_names_each_thing_to_change():
    car = _make_variant(variant_key="A", seats=5, price_inr=2_400_000, drive="FWD", sunroof="None")
    nm = _build([car], budget_max_inr=2_000_000, seats_min=7, must_haves=["awd", "sunroof"]).no_match
    assert nm.what_it_would_take == [
        "Raise your budget to at least ₹24 lakh.",
        "Accept 5 seats; you asked for 7.",
        'Drop "AWD" from your must-haves: this variant does not have it.',
        'Drop "Sunroof" from your must-haves: this variant does not have it.',
    ]


def test_the_closest_card_carries_the_engines_fail_reasons_and_no_confidence():
    car = _make_variant(variant_key="A", seats=5)
    result = _build([car], seats_min=7)
    [slot] = result.slots
    assert slot.slot == "not_recommended" and slot.confidence == "" and slot.match_score == 0
    assert [r.detail for r in slot.reasons] == ["Only 5 seats (need 7+)"]
