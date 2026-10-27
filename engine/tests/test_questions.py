"""Follow-up question picker: required order, easy templates, sensitivity-based optional questions, the route."""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import questions as q
from app.contracts import needs_field_is_valid, questions_response_errors
from app.dataset import Dataset
from app.main import SECRET_HEADER, create_app

SECRET = "test-secret-not-the-placeholder"
AUTH = {SECRET_HEADER: SECRET}
GATE = {"budget_max_inr": 1_500_000, "seats_min": 4, "daily_km": 40}
FULL = {**GATE, "home_charging": "yes"}


@pytest.fixture(scope="module")
def client(release_dir: Path):
    with TestClient(create_app(secret=SECRET, release_dir=release_dir, dev_cors=False, llm_client=None)) as c:
        yield c


def ask(dataset: Dataset, known: dict, asked: list[str] | None = None) -> dict:
    out = q.next_question(known, asked or [], dataset.variants)
    assert questions_response_errors(out) == []
    return out


# --- required fields: always in the same order, skipping what is known ------------------------------

def test_empty_needs_asks_budget_first(dataset):
    out = ask(dataset, {})
    assert (out["kind"], out["field"], out["done"]) == ("required", "budget_max_inr", False)
    assert out["missing_required"] == q.REQUIRED_ORDER
    assert out["can_show_results"] is False


@pytest.mark.parametrize(
    "known, expected",
    [
        ({"budget_max_inr": 1_500_000}, "seats_min"),
        ({"budget_max_inr": 1_500_000, "seats_min": 5}, "daily_km"),
        (GATE, "home_charging"),
        ({"seats_min": 4, "daily_km": 40, "home_charging": "no"}, "budget_max_inr"),  # skips what is known
        ({"home_charging": "no"}, "budget_max_inr"),
    ],
)
def test_required_fields_are_asked_in_order_and_known_ones_skipped(dataset, known, expected):
    out = ask(dataset, known)
    assert (out["kind"], out["field"]) == ("required", expected)


def test_affordable_family_car_example_asks_budget_seats_distance_then_charging(dataset):
    """'Affordable family car for bad roads and daily office travel': only the road is known."""
    known: dict = {"road_conditions": "rough_roads"}
    order = []
    for _ in range(4):
        out = ask(dataset, known)
        order.append(out["field"])
        known = {**known, **out["cards"][0]["patch"]}
    assert order == ["budget_max_inr", "seats_min", "daily_km", "home_charging"]


def test_results_unlock_once_budget_seats_and_daily_km_are_known_even_if_charging_is_not(dataset):
    out = ask(dataset, GATE)
    assert out["field"] == "home_charging" and out["can_show_results"] is True
    assert q.GATE_FIELDS == ["budget_max_inr", "seats_min", "daily_km"]


# --- templates: easy, plain, valid ------------------------------------------------------------------

@pytest.mark.parametrize("field", sorted(q.TEMPLATES))
def test_every_card_patch_is_valid_against_the_needs_contract(field):
    cards = q.TEMPLATES[field]["cards"]
    assert 3 <= len(cards) <= 6
    assert len({c["id"] for c in cards}) == len(cards)
    for card in cards:
        for name, value in card["patch"].items():
            assert name == field, f"{card['id']} sets {name}, not the field it answers"
            assert needs_field_is_valid(name, value), (card["id"], name, value)


@pytest.mark.parametrize("field", sorted(q.TEMPLATES))
def test_questions_use_no_car_jargon(field):
    t = q.TEMPLATES[field]
    text = " ".join([t["question"], t["why"], t["example"], *(c["label"] + " " + (c["sublabel"] or "") for c in t["cards"])]).lower()
    for jargon in ("adas", "esp", "awd", "kwh", "ground clearance", "ncap", "baas", "dc fast"):
        assert jargon not in text, f"{field} mentions {jargon}"


def test_not_sure_is_never_turned_into_yes_or_no():
    cards = {c["id"]: c["patch"] for c in q.TEMPLATES["home_charging"]["cards"]}
    assert cards["h_unsure"] == {"home_charging": "unsure"}
    assert cards["h_flat"] == {"home_charging": "unsure"}  # needs the society's permission: not a yes
    assert cards["h_house"] == {"home_charging": "yes"} and cards["h_street"] == {"home_charging": "no"}
    optional_skips = {c["id"]: c["patch"] for f in ("road_conditions",) for c in q.TEMPLATES[f]["cards"]}
    assert optional_skips["r_skip"] == {}  # skipping sets nothing


def test_situation_answers_never_create_must_haves():
    for t in q.TEMPLATES.values():
        for card in t["cards"]:
            assert "must_haves" not in card["patch"] and "nice_to_haves" not in card["patch"]


def test_hard_numbers_have_helpers_and_the_rest_do_not():
    assert q.TEMPLATES["budget_max_inr"]["helper"] == "budget_emi"
    assert q.TEMPLATES["daily_km"]["helper"] == "commute_minutes"
    assert all(q.TEMPLATES[f]["helper"] is None for f in ("seats_min", "home_charging", "road_conditions", "priority"))


def test_responses_do_not_share_state_with_the_templates(dataset):
    out = ask(dataset, {})
    out["cards"][0]["patch"]["budget_max_inr"] = 1
    assert q.TEMPLATES["budget_max_inr"]["cards"][0]["patch"]["budget_max_inr"] == 1_000_000


# --- optional questions: only what changes the shortlist --------------------------------------------

def test_change_score_is_zero_for_same_shortlist_and_counts_a_new_best_match():
    assert q.change_score(["a", "b", "c"], ["a", "b", "c"]) == 0
    assert q.change_score(["a", "b", "c"], ["a", "c", "b"]) == 0
    assert q.change_score(["a", "b", "c"], ["a", "b", "d"]) == 1.0 < q.MATERIAL_SCORE
    assert q.change_score(["a", "b", "c"], ["x", "b", "c"]) >= q.MATERIAL_SCORE


def test_sensitivity_is_deterministic(dataset):
    scores = {q.sensitivity(f, FULL, dataset.variants) for f in ["priority"] for _ in range(2)}
    assert len(scores) == 1


def test_optional_question_is_asked_only_when_it_would_change_the_shortlist(dataset):
    out = ask(dataset, FULL)
    if out["kind"] == "optional":
        assert q.sensitivity(out["field"], FULL, dataset.variants) >= q.MATERIAL_SCORE
    else:
        assert out["done"] is True
        for f in q.OPTIONAL_ORDER:
            assert q.sensitivity(f, FULL, dataset.variants) < q.MATERIAL_SCORE


def test_priority_changes_the_shortlist_for_a_normal_buyer(dataset):
    assert q.sensitivity("priority", FULL, dataset.variants) >= q.MATERIAL_SCORE
    assert ask(dataset, FULL)["kind"] == "optional"


def test_asked_and_known_optional_fields_are_never_asked_again(dataset):
    seen = []
    known, asked = dict(FULL), []
    for _ in range(6):
        out = ask(dataset, known, asked)
        if out["done"]:
            break
        seen.append(out["field"])
        asked.append(out["field"])
    assert len(seen) == len(set(seen)) <= q.MAX_OPTIONAL
    known_priority = ask(dataset, {**FULL, "priority": "safety"})
    assert known_priority["field"] != "priority"


def test_at_most_three_optional_questions(dataset):
    out = ask(dataset, FULL, list(q.OPTIONAL_ORDER))
    assert out["done"] is True and out["kind"] == "none" and out["field"] is None and out["cards"] == []


def test_a_done_response_still_says_results_can_be_shown(dataset):
    assert ask(dataset, FULL, list(q.OPTIONAL_ORDER))["can_show_results"] is True


def test_sensitivity_check_is_fast_enough_for_a_chat(dataset):
    start = time.monotonic()
    ask(dataset, FULL)
    assert time.monotonic() - start < 5


# --- the route --------------------------------------------------------------------------------------

def test_route_needs_the_secret(client):
    assert client.post("/next_question", json={"needs": {}}).status_code == 401


def test_route_returns_a_valid_first_question(client):
    r = client.post("/next_question", json={"needs": {}}, headers=AUTH)
    assert r.status_code == 200
    assert questions_response_errors(r.json()) == []
    assert r.json()["field"] == "budget_max_inr"


def test_route_matches_the_direct_call(client, dataset):
    body = {"needs": FULL, "asked": ["priority"]}
    r = client.post("/next_question", json=body, headers=AUTH)
    assert r.status_code == 200
    assert r.json() == q.next_question(FULL, ["priority"], dataset.variants)


@pytest.mark.parametrize(
    "body, field",
    [
        ({}, "needs"),
        ({"needs": {"budget_max_inr": 100}}, "needs.budget_max_inr"),
        ({"needs": {"nonsense": 1}}, "needs.nonsense"),
        ({"needs": {}, "asked": ["budget_max_inr"]}, "asked[0]"),
        ({"needs": {}, "extra": 1}, "extra"),
    ],
)
def test_route_rejects_bad_requests_in_plain_english(client, body, field):
    r = client.post("/next_question", json=body, headers=AUTH)
    assert r.status_code == 422
    assert field in [p["field"] for p in r.json()["detail"]]


def test_route_rejects_empty_and_non_json_bodies(client):
    assert client.post("/next_question", content=b"", headers=AUTH).status_code == 422
    assert client.post("/next_question", content=b"not json", headers=AUTH).status_code == 422


def test_no_llm_is_involved_in_the_question_module():
    text = (Path(__file__).resolve().parent.parent / "app" / "questions.py").read_text(encoding="utf-8")
    imports = [line for line in text.splitlines() if line.startswith(("import ", "from "))]
    assert not any(w in line for line in imports for w in ("llm", "extract", "openai", "explain"))


# --- "not sure" about home charging is never silently treated as a yes ----------------------------------

def test_not_sure_about_home_charging_adds_a_caveat_to_the_result(dataset):
    from app.models import Needs
    from app.slots import NOT_SURE_CHARGING_NOTE, build_result

    def result(home: str):
        needs = Needs(**{**FULL, "home_charging": home})
        return build_result(needs, dataset.variants, dataset.version, dataset.engine_version, dataset=dataset)

    assert NOT_SURE_CHARGING_NOTE in result("unsure").unknowns
    assert NOT_SURE_CHARGING_NOTE not in result("yes").unknowns
    assert NOT_SURE_CHARGING_NOTE not in result("no").unknowns


def test_the_not_sure_card_says_costs_assume_a_home_charger():
    card = next(c for c in q.TEMPLATES["home_charging"]["cards"] if c["id"] == "h_unsure")
    assert "assume" in card["sublabel"].lower() and "say" in card["sublabel"].lower()
