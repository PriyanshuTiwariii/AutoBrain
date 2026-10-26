"""Rough roads / light off-road: scoring, trade-offs, reasons and the result text."""
from __future__ import annotations

import pytest

from app.models import Needs
from app.slots import build_result
from app.terrain import NOT_OFFROAD_NOTE, terrain_reasons, terrain_score, terrain_tradeoffs
from tests.test_eligibility import _make_variant

CODES = lambda items: {t["code"] for t in items}  # noqa: E731


def _needs(**kw) -> Needs:
    base = dict(budget_max_inr=3_500_000, seats_min=5, daily_km=40, home_charging="yes")
    base.update(kw)
    return Needs(**base)


def test_default_is_city_and_highway_and_changes_nothing():
    v = _make_variant(ground_clearance_mm=210, battery_clearance_mm=220, drive="AWD")
    assert _needs().road_conditions.value == "city_highway"
    assert terrain_score(v, "city_highway") == 0
    assert terrain_tradeoffs(v, "city_highway") == []
    assert terrain_reasons(v, "city_highway") == []


def test_unknown_values_earn_nothing_and_are_shown_as_not_stated():
    v = _make_variant(ground_clearance_mm=None, battery_clearance_mm=None, drive="Not stated", adaptive_suspension="Not stated")
    for road in ("rough_roads", "light_offroad"):
        assert terrain_score(v, road) == 0
    found = terrain_tradeoffs(v, "light_offroad")
    assert CODES(found) == {"ground_clearance_unknown", "battery_clearance_unknown", "drive_unknown"}
    assert all("not stated by maker" in t["detail"] for t in found)
    assert CODES(terrain_tradeoffs(v, "rough_roads")) == {"ground_clearance_unknown", "battery_clearance_unknown"}


def test_known_low_clearance_is_a_stated_tradeoff_not_unknown():
    v = _make_variant(ground_clearance_mm=186, battery_clearance_mm=None, drive="FWD")
    assert "low_ground_clearance" in CODES(terrain_tradeoffs(v, "rough_roads"))
    assert "no_awd" not in CODES(terrain_tradeoffs(v, "rough_roads"))  # drive only matters for light off-road
    assert {"low_ground_clearance", "no_awd"} <= CODES(terrain_tradeoffs(v, "light_offroad"))


def test_higher_clearance_and_awd_score_higher():
    low = _make_variant(ground_clearance_mm=170, battery_clearance_mm=None, drive="FWD")
    mid = _make_variant(ground_clearance_mm=190, battery_clearance_mm=None, drive="FWD")
    high = _make_variant(ground_clearance_mm=205, battery_clearance_mm=220, drive="RWD")
    awd = _make_variant(ground_clearance_mm=205, battery_clearance_mm=220, drive="AWD")
    for road in ("rough_roads", "light_offroad"):
        assert terrain_score(low, road) < terrain_score(mid, road) < terrain_score(high, road) <= 25
    assert terrain_score(high, "light_offroad") < terrain_score(awd, "light_offroad") <= 25
    assert terrain_score(high, "rough_roads") == terrain_score(awd, "rough_roads")


def test_adaptive_suspension_counts_for_rough_roads_only():
    base = dict(ground_clearance_mm=205, battery_clearance_mm=220, drive="RWD")
    plain, adaptive = _make_variant(adaptive_suspension="No", **base), _make_variant(adaptive_suspension="Yes", **base)
    assert terrain_score(adaptive, "rough_roads") > terrain_score(plain, "rough_roads")
    assert terrain_score(adaptive, "light_offroad") == terrain_score(plain, "light_offroad")


@pytest.fixture(scope="module")
def dataset():
    from app.config import REPO_ROOT
    from app.dataset import load_dataset
    return load_dataset(sorted((REPO_ROOT / "data" / "releases").iterdir())[-1])


def _result(dataset, **kw):
    return build_result(_needs(**kw), dataset.variants, "test", "test", dataset=dataset)


def test_light_offroad_ranks_awd_with_stated_clearance_first_and_says_what_it_is(dataset):
    top = _result(dataset, road_conditions="light_offroad").slots[0]
    assert top.metrics["drive"] == "AWD"
    assert top.metrics["ground_clearance_mm"] and top.metrics["ground_clearance_mm"] >= 200
    assert "Roads: light off-road" in _result(dataset, road_conditions="light_offroad").needs_summary
    assert NOT_OFFROAD_NOTE in _result(dataset, road_conditions="light_offroad").unknowns


def test_the_note_and_summary_line_only_appear_when_asked(dataset):
    for road in ("city_highway", "rough_roads"):
        r = _result(dataset, road_conditions=road)
        assert NOT_OFFROAD_NOTE not in r.unknowns
    assert not any(line.startswith("Roads:") for line in _result(dataset).needs_summary)


def test_default_result_has_no_terrain_text(dataset):
    r = _result(dataset)
    for s in r.slots:
        assert not any(t.code in {"low_ground_clearance", "no_awd", "battery_clearance_unknown"} for t in s.tradeoffs)


def test_result_is_deterministic_and_the_choice_changes_the_id(dataset):
    a = _result(dataset, road_conditions="rough_roads")
    assert a.model_dump() == _result(dataset, road_conditions="rough_roads").model_dump()
    assert a.result_id != _result(dataset).result_id


def test_every_card_shows_battery_clearance_figure_or_none(dataset):
    for s in _result(dataset, road_conditions="rough_roads").slots:
        assert "battery_clearance_mm" in s.metrics
