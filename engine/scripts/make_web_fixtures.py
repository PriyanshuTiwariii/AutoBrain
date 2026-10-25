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
