"""The real Result for every golden scenario validates against contracts/result.schema.json."""
from __future__ import annotations

import json

import jsonschema
import pytest

from app.config import REPO_ROOT
from app.dataset import Dataset
from app.models import Needs
from app.slots import build_result

RESULT_SCHEMA = json.loads((REPO_ROOT / "contracts" / "result.schema.json").read_text(encoding="utf-8"))

# CHANGES.md §9
GOLDEN_NEEDS = {
    "1_budget_10L": dict(budget_max_inr=1000000, seats_min=4, daily_km=30, home_charging="yes"),
    "2_rough_roads_20L": dict(
        budget_max_inr=2000000, seats_min=4, daily_km=40, home_charging="yes",
        nice_to_haves=["adaptive_suspension"],
    ),
    "3_seven_seats_25L": dict(budget_max_inr=2500000, seats_min=7, daily_km=40, longest_regular_trip_km=300, home_charging="yes"),
    "4_adas_crash_18L": dict(
        budget_max_inr=1800000, seats_min=5, daily_km=40, home_charging="yes",
        must_haves=["adas", "crash_tested"],
    ),
    "5_no_home_15L": dict(budget_max_inr=1500000, seats_min=4, daily_km=40, home_charging="no"),
    "6_nothing_qualifies": dict(
        budget_max_inr=800000, seats_min=7, daily_km=40, home_charging="yes", must_haves=["awd"],
    ),
}


@pytest.mark.parametrize("name", sorted(GOLDEN_NEEDS))
def test_golden_result_matches_contract(dataset: Dataset, name: str):
    needs = Needs(**GOLDEN_NEEDS[name])
    result = build_result(needs, dataset.variants, dataset.version, dataset.engine_version, dataset=dataset)
    jsonschema.validate(json.loads(result.model_dump_json()), RESULT_SCHEMA)
