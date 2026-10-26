"""Regenerate web/tests/fixtures/*.json: real engine Results for the golden scenarios.

Run from engine/:  python scripts/make_web_fixtures.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import DATA_RELEASE_DIR, REPO_ROOT
from app.dataset import load_dataset
from app.models import Needs
from app.slots import build_result
from tests.test_contract import GOLDEN_NEEDS

FIXTURES = {
    "scenario-1": "1_budget_10L",
    "scenario-3": "3_seven_seats_25L",
    "scenario-5": "5_no_home_15L",
    "scenario-6-nothing-qualifies": "6_nothing_qualifies",
}

ds = load_dataset(DATA_RELEASE_DIR)
out = REPO_ROOT / "web" / "tests" / "fixtures"
out.mkdir(parents=True, exist_ok=True)
for name, key in FIXTURES.items():
    result = build_result(Needs(**GOLDEN_NEEDS[key]), ds.variants, ds.version, ds.engine_version, dataset=ds)
    (out / f"{name}.json").write_text(
        json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )
    print(f"wrote {name}.json ({len(result.slots)} slots)")


# --- /extract responses: real engine output for a scripted model (no network), for the website's tests ----------
from app.extract import extract_needs  # noqa: E402
from app.llm import LLMError, LLMSettings  # noqa: E402


class ScriptedModel:
    """Stands in for OpenAI: returns the answers it was given, in order."""

    def __init__(self, *replies):
        self.replies = list(replies)

    def generate_json(self, **_):
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def model_answer(**fields):
    base = {
        "is_about_buying_an_ev": True, "budget": None, "seats_min": None, "daily_distance": None,
        "longest_regular_trip_km": None, "home_charging": None, "must_haves": [], "nice_to_haves": [],
        "priority": None, "pricing_pref": None, "body_types": [], "exclude_models": [],
    }
    base.update(fields)
    return base


by_brand: dict = {}
for v in ds.variants:
    if v.model not in by_brand.setdefault(v.brand, []):
        by_brand[v.brand].append(v.model)
settings = LLMSettings(api_key="x", primary_model="primary", fallback_model="fallback")
EXTRACTS = {
    "extract-complete": [model_answer(
        budget={"amount": 12.5, "unit": "lakh"}, seats_min=5, daily_distance={"km": 25, "basis": "each_way"},
        home_charging="no", must_haves=["adas", "camera_360"], nice_to_haves=["sunroof", "adas"], priority="safety",
        body_types=["SUV"], exclude_models=["Nexon.ev"],
    )],
    "extract-missing-budget": [model_answer(seats_min=4, home_charging="yes")],
    "extract-partial": [model_answer(budget={"amount": 2, "unit": "lakh"}, seats_min=4), model_answer(budget={"amount": 1, "unit": "lakh"}, seats_min=4, daily_distance={"km": 40, "basis": "per_day"})],
    "extract-off-topic": [model_answer(is_about_buying_an_ev=False)],
    "extract-unavailable": [LLMError("timeout"), LLMError("timeout")],
}
for name, replies in EXTRACTS.items():
    payload = extract_needs("(not stored)", client=ScriptedModel(*replies), settings=settings, models_by_brand=by_brand)
    (out / f"{name}.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {name}.json ({payload['status']})")
