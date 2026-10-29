"""Comparison: facts from the data only, fair category winners, honest withholding, the routes."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import compare as cmp
from app.contracts import cars_response_errors, compare_response_errors
from app.dataset import Dataset
from app.main import SECRET_HEADER, create_app

SECRET = "test-secret-not-the-placeholder"
AUTH = {SECRET_HEADER: SECRET}


@pytest.fixture(scope="module")
def client(release_dir: Path):
    with TestClient(create_app(secret=SECRET, release_dir=release_dir, dev_cors=False, llm_client=None)) as c:
        yield c


def pick(ds: Dataset, **where):
    return [v for v in ds.variants if all(getattr(v, k) == val for k, val in where.items())]


def run(ds: Dataset, *variants) -> dict:
    out = cmp.compare_cars([v.variant_key for v in variants], ds.variants, ds.version)
    assert compare_response_errors(out) == []
    return out


def winner(out: dict, category: str) -> dict:
    return next(w for w in out["winners"] if w["category"] == category)


def cell(out: dict, row: str, index: int) -> dict:
    return next(r for s in out["sections"] for r in s["rows"] if r["key"] == row)["cells"][index]


@pytest.fixture(scope="module")
def three(dataset: Dataset):
    """Three battery-included cars from different models."""
    vs = [v for v in dataset.variants if v.pricing_type == "battery included"]
    return [next(v for v in vs if v.model == m) for m in ("Punch.ev", "Nexon.ev", "Curvv.ev")]


# --- /cars ------------------------------------------------------------------------------------------

def test_cars_lists_every_variant_once_and_matches_the_contract(dataset):
    out = cmp.list_cars(dataset.variants, dataset.version)
    assert cars_response_errors(out) == []
    keys = [c["variant_key"] for c in out["cars"]]
    assert len(keys) == len(set(keys)) == len(dataset.variants)


# --- shape and honesty of the facts -----------------------------------------------------------------

def test_two_or_three_cars_in_the_order_given(dataset, three):
    out = run(dataset, three[2], three[0])
    assert [c["variant_key"] for c in out["cars"]] == [three[2].variant_key, three[0].variant_key]
    assert len(run(dataset, *three)["cars"]) == 3


def test_every_row_has_one_cell_per_car_and_every_section_is_present(dataset, three):
    out = run(dataset, *three)
    assert [s["title"] for s in out["sections"]] == [
        "Price and cost", "Range and charging", "Safety", "Comfort and features", "Space and ground",
    ]
    for section in out["sections"]:
        for row in section["rows"]:
            assert len(row["cells"]) == 3, row["key"]


def test_price_status_is_shown_next_to_the_price_and_matches_the_data(dataset, three):
    out = run(dataset, *three)
    for i, car in enumerate(three):
        text = cell(out, "price", i)["text"]
        assert f"({car.price_status})" in text
        assert cmp.fmt_lakh(car.price_inr) in text


def test_crash_rating_never_appears_without_its_status_label(dataset):
    for car in pick(dataset, ncap_status="Rated, coverage unconfirmed")[:1] + pick(dataset, ncap_status="Not tested")[:1]:
        other = next(v for v in dataset.variants if v.variant_key != car.variant_key and v.pricing_type == car.pricing_type)
        text = cell(run(dataset, car, other), "ncap", 0)["text"]
        assert "Bharat NCAP" in text
    rated = pick(dataset, ncap_status="Not tested")[0]
    other = pick(dataset, ncap_status="Not tested")[1]
    assert "No Bharat NCAP crash test" in cell(run(dataset, rated, other), "ncap", 0)["text"]


def test_unknown_values_are_shown_as_not_stated_by_maker_never_filled_in(dataset):
    unknown = next(v for v in dataset.variants if v.sunroof == "Not stated")
    other = next(v for v in dataset.variants if v.variant_key != unknown.variant_key and v.pricing_type == unknown.pricing_type)
    c = cell(run(dataset, unknown, other), "sunroof", 0)
    assert (c["text"], c["state"]) == ("Not stated by maker", "not_stated")
    esp_unknown = next(v for v in dataset.variants if v.esp == "Not listed")
    c = cell(run(dataset, esp_unknown, other), "esp", 0)
    assert c["state"] == "not_stated" and "No" != c["text"]


def test_watch_outs_are_always_included_for_every_car(dataset, three):
    out = run(dataset, *three)
    assert [w["variant_key"] for w in out["watch_outs"]] == [c.variant_key for c in three]
    for car, w in zip(three, out["watch_outs"]):
        expected = [] if car.watch_outs in ("", "None flagged") else [x.strip() for x in car.watch_outs.split(";") if x.strip()]
        assert w["items"] == expected


def test_default_assumption_note_and_no_overall_winner(dataset, three):
    notes = " ".join(run(dataset, *three)["notes"])
    assert "do not pick an overall winner" in notes and "default assumptions" in notes and "insurance" in notes


# --- winners follow fixed rules ---------------------------------------------------------------------

def test_cheapest_car_wins_price_and_its_cell_is_marked_best(dataset, three):
    out = run(dataset, *three)
    cheapest = min(three, key=lambda v: v.price_inr)
    assert winner(out, "price")["variant_key"] == cheapest.variant_key
    flags = [cell(out, "price", i)["best"] for i in range(3)]
    assert flags == [c.variant_key == cheapest.variant_key for c in three]


def test_winner_text_numbers_come_from_the_data(dataset, three):
    out = run(dataset, *three)
    text = winner(out, "price")["text"]
    ordered = sorted(three, key=lambda v: v.price_inr)
    assert cmp.fmt_lakh(ordered[0].price_inr) in text
    assert cmp.fmt_lakh(ordered[1].price_inr - ordered[0].price_inr) in text


def test_ties_have_no_winner(dataset):
    a = pick(dataset, pricing_type="battery included")[0]
    b = a.model_copy(update={"variant_key": "COPY-OF-A", "variant": "Copy"})
    out = cmp.compare_cars([a.variant_key, "COPY-OF-A"], [*dataset.variants, b], dataset.version)
    assert winner(out, "price")["variant_key"] is None and "level" in winner(out, "price")["text"]
    assert not any(cell(out, "price", i)["best"] for i in range(2))


def test_baas_is_never_compared_with_battery_included_on_price_or_cost(dataset):
    baas = pick(dataset, pricing_type="BaaS", price_status="verified")[0]
    bought = next(v for v in pick(dataset, pricing_type="battery included") if v.model == baas.model)
    out = run(dataset, baas, bought)
    assert winner(out, "price")["variant_key"] is None and "battery rental" in winner(out, "price")["text"]
    assert winner(out, "cost_5yr")["variant_key"] is None
    assert cell(out, "cost_5yr", 0)["text"] == "Not calculated for battery rental"
    assert any("BaaS" in n for n in out["notes"])


def test_two_baas_cars_may_be_compared_on_price_but_never_on_5_year_cost(dataset):
    baas = [v for v in pick(dataset, pricing_type="BaaS") if v.price_status == "verified"][:2]
    out = run(dataset, *baas)
    assert winner(out, "price")["variant_key"] is not None or "level" in winner(out, "price")["text"]
    assert winner(out, "cost_5yr")["variant_key"] is None


def test_a_pending_price_never_wins_and_is_called_out(dataset):
    pending = pick(dataset, price_status="pending")[0]
    other = next(v for v in pick(dataset, pricing_type=pending.pricing_type, price_status="verified") if v.variant_key != pending.variant_key)
    third = [v for v in pick(dataset, pricing_type=pending.pricing_type, price_status="verified") if v.variant_key not in (pending.variant_key, other.variant_key)][0]
    out = run(dataset, pending, other, third)
    assert winner(out, "price")["variant_key"] in (other.variant_key, third.variant_key)
    assert cell(out, "price", 0)["state"] == "not_stated" and cell(out, "price", 0)["text"] == "Price not confirmed"
    assert any("not confirmed yet" in n for n in out["notes"])


def test_a_tested_range_is_never_compared_with_a_maker_figure(dataset):
    by_range = {v.range_tested_km: v for v in pick(dataset, pricing_type="battery included") if v.range_tested_km}
    tested = [by_range[k] for k in sorted(by_range)[:2]]
    maker = next(v for v in pick(dataset, pricing_type="battery included") if not v.range_tested_km and v.range_maker_realworld_km)
    out = run(dataset, *tested, maker)
    w = winner(out, "range")
    assert w["variant_key"] in {t.variant_key for t in tested}
    assert maker.variant_key != w["variant_key"] and "not comparable" in w["text"]
    only_one_each = run(dataset, tested[0], maker)
    assert winner(only_one_each, "range")["variant_key"] is None and "not like for like" in winner(only_one_each, "range")["text"]


def test_an_independent_efficiency_test_is_never_compared_with_a_maker_estimate(dataset):
    tested = next(v for v in dataset.variants if v.efficiency_basis == "Independent test" and v.pricing_type == "battery included")
    estimate = next(v for v in dataset.variants if v.efficiency_basis != "Independent test" and v.efficiency_km_per_kwh and v.pricing_type == "battery included")
    w = winner(run(dataset, tested, estimate), "efficiency")
    assert w["variant_key"] is None and "not like for like" in w["text"]


def test_safety_compares_only_rated_cars_and_never_penalises_an_unrated_one(dataset):
    rated = [v for v in dataset.variants if v.ncap_status in cmp._RATED and v.ncap_adult_32 and v.pricing_type == "battery included"]
    unrated = next(v for v in dataset.variants if v.ncap_status == "Not tested" and v.pricing_type == "battery included")
    best, other = sorted({v.ncap_adult_32: v for v in rated}.values(), key=lambda v: -v.ncap_adult_32)[:2]
    out = run(dataset, best, other, unrated)
    w = winner(out, "safety")
    assert w["variant_key"] == best.variant_key and "no Bharat NCAP rating" in w["text"]
    assert cmp.fmt_ncap(best.ncap_adult_32) in w["text"]
    one_rated = run(dataset, best, unrated)
    assert winner(one_rated, "safety")["variant_key"] is None and "Only one" in winner(one_rated, "safety")["text"]


def test_a_missing_figure_is_left_out_not_counted_as_worst(dataset):
    by_dc = {v.dc_avg_kw_est: v for v in dataset.variants if v.dc_avg_kw_est and v.pricing_type == "battery included"}
    a, b = [by_dc[k] for k in sorted(by_dc)[:2]]
    c = a.model_copy(update={"variant_key": "NO-DC", "dc_avg_kw_est": None})
    out = cmp.compare_cars([a.variant_key, b.variant_key, "NO-DC"], [*dataset.variants, c], dataset.version)
    w = winner(out, "dc_charging")
    assert w["variant_key"] in (a.variant_key, b.variant_key) and "left out" in w["text"]


def test_no_winner_when_fewer_than_two_cars_state_a_figure(dataset):
    a, b = pick(dataset, pricing_type="battery included")[:2]
    x = a.model_copy(update={"variant_key": "X", "boot_l": None})
    y = b.model_copy(update={"variant_key": "Y", "boot_l": None})
    out = cmp.compare_cars(["X", "Y"], [*dataset.variants, x, y], dataset.version)
    assert winner(out, "boot")["variant_key"] is None and "Not enough" in winner(out, "boot")["text"]


def test_best_flags_match_the_winners_exactly(dataset, three):
    out = run(dataset, *three)
    row_for = cmp._ROW_FOR_CATEGORY
    for w in out["winners"]:
        flags = [cell(out, row_for[w["category"]], i)["best"] for i in range(3)]
        expected = [c.variant_key == w["variant_key"] for c in three]
        assert flags == expected, w["category"]


def test_unknown_keys_are_reported_by_position(dataset):
    with pytest.raises(cmp.UnknownCars) as exc:
        cmp.compare_cars([dataset.variants[0].variant_key, "NOT-A-CAR"], dataset.variants, dataset.version)
    assert exc.value.indexes == [1]


def test_comparison_is_deterministic(dataset, three):
    assert run(dataset, *three) == run(dataset, *three)


def test_module_never_touches_the_llm():
    text = (Path(__file__).resolve().parent.parent / "app" / "compare.py").read_text(encoding="utf-8")
    imports = [line for line in text.splitlines() if line.startswith(("import ", "from "))]
    assert not any(w in line for line in imports for w in ("llm", "extract", "openai"))


# --- the routes -------------------------------------------------------------------------------------

def test_routes_need_the_secret(client):
    assert client.get("/cars").status_code == 401
    assert client.post("/compare", json={"variant_keys": ["a", "b"]}).status_code == 401


def test_cars_route_returns_the_release(client, dataset):
    r = client.get("/cars", headers=AUTH)
    assert r.status_code == 200 and cars_response_errors(r.json()) == []
    assert len(r.json()["cars"]) == len(dataset.variants)


def test_compare_route_matches_the_direct_call(client, dataset, three):
    keys = [c.variant_key for c in three[:2]]
    r = client.post("/compare", json={"variant_keys": keys}, headers=AUTH)
    assert r.status_code == 200
    assert r.json() == cmp.compare_cars(keys, dataset.variants, dataset.version)


@pytest.mark.parametrize(
    "body, field",
    [
        ({}, "variant_keys"),
        ({"variant_keys": ["only-one"]}, "variant_keys"),
        ({"variant_keys": ["a", "b", "c", "d"]}, "variant_keys"),
        ({"variant_keys": ["a", "a"]}, "variant_keys"),
        ({"variant_keys": ["a", 2]}, "variant_keys[1]"),
        ({"variant_keys": ["a", "b"], "extra": 1}, "extra"),
    ],
)
def test_compare_route_rejects_bad_requests_in_plain_english(client, body, field):
    r = client.post("/compare", json=body, headers=AUTH)
    assert r.status_code == 422
    assert field in [p["field"] for p in r.json()["detail"]]


def test_compare_route_names_the_unknown_car(client, dataset):
    r = client.post("/compare", json={"variant_keys": [dataset.variants[0].variant_key, "NOT-A-CAR"]}, headers=AUTH)
    assert r.status_code == 422
    assert r.json()["detail"] == [{"field": "variant_keys[1]", "message": "variant_keys[1] is not a car in our data"}]
