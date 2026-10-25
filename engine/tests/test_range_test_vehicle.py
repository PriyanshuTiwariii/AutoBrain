"""range_test_vehicle: tests done on an earlier version are labelled and never earn High confidence.

Everything here is driven by the data column, never by model names.
"""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path

from app.costs import compute_costs
from app.dataset import Dataset
from app.eligibility import check_all
from app.models import Needs
from app.scoring import compute_confidence, compute_fit_score, rank_variants
from app.slots import EARLIER_VERSION_LABEL, _build_metrics, build_result
from app.validate import validate_release

SCENARIOS = [
    dict(budget_max_inr=1000000, seats_min=4, daily_km=30, home_charging="yes"),
    dict(budget_max_inr=2500000, seats_min=7, daily_km=40, longest_regular_trip_km=300, home_charging="yes"),
    dict(budget_max_inr=1500000, seats_min=4, daily_km=40, home_charging="no"),
]
# Wide open (BaaS rows too), so every row is eligible and gets ranked
EVERYTHING = Needs(
    budget_max_inr=9_000_000, seats_min=2, daily_km=40, home_charging="yes", pricing_pref="either",
)


def _ranked_all(dataset: Dataset):
    return rank_variants(dataset.variants, check_all(dataset.variants, EVERYTHING), EVERYTHING)


def _legacy_confidence(v) -> str:
    """The confidence rule before range_test_vehicle existed."""
    if v.price_status == "pending" or v.efficiency_basis == "None":
        return "Low"
    good_range = v.range_tested_km is not None or v.efficiency_basis == "Independent test"
    if v.price_status == "verified" and good_range and v.ncap_status in ("Rated, applies", "Not tested"):
        return "High"
    return "Medium"


def test_data_has_all_three_vehicle_values(dataset: Dataset):
    """Guard, so the tests below cannot pass by testing nothing."""
    assert {v.range_test_vehicle for v in dataset.variants} == {"Same model", "Earlier version", "Not tested"}


def test_earlier_version_rows_labelled_and_never_high(dataset: Dataset):
    rows = [v for v in dataset.variants if v.range_test_vehicle == "Earlier version"]
    assert rows
    ranked = {rv.variant.variant_key: rv for rv in _ranked_all(dataset)}
    for v in rows:
        # the data carries the explanation and the generated watch-out
        assert v.range_test_note
        assert "earlier version" in v.watch_outs.lower()
        # never High, even when everything else is as good as it gets
        assert compute_confidence(v) != "High", v.variant_key
        assert compute_confidence(v.model_copy(update={"price_status": "verified"})) == "Medium"
        # the card labels the tested range, shows the note, and never says plain "independent test"
        assert v.variant_key in ranked, f"{v.variant_key} not ranked"
        m = _build_metrics(ranked[v.variant_key])
        assert m["range_display"] == f"{v.range_tested_km} km ({EARLIER_VERSION_LABEL})"
        assert "independent test" not in m["range_display"]
        assert m["range_test_note"] == v.range_test_note
        assert m["efficiency_display"] == f"{v.efficiency_km_per_kwh:g} km/kWh ({EARLIER_VERSION_LABEL})"
        assert m["range_test_vehicle"] == "Earlier version"


def test_earlier_version_label_reaches_cards_and_sentences(dataset: Dataset):
    """In real results, any card for an Earlier version row carries the label, the note and its
    watch-out, and any sentence quoting its tested range says it was an earlier version."""
    seen = 0
    for kwargs in SCENARIOS:
        result = build_result(Needs(**kwargs), dataset.variants, dataset.version, dataset.engine_version, dataset=dataset)
        for s in result.slots:
            v = dataset.get_variant(s.variant_key)
            if s.slot == "not_recommended" or v.range_test_vehicle != "Earlier version":
                continue
            seen += 1
            assert s.metrics["range_display"].endswith(f"({EARLIER_VERSION_LABEL})")
            assert s.metrics["range_test_note"] == v.range_test_note
            assert any("earlier version" in w.lower() for w in s.watch_outs)
            for r in s.reasons + s.tradeoffs:
                text = r.detail or ""
                assert f"{v.range_tested_km} km (tested)" not in text, text
    assert seen, "no Earlier version card appeared in any scenario"


def test_same_model_rows_unaffected(dataset: Dataset):
    rows = [v for v in dataset.variants if v.range_test_vehicle == "Same model"]
    assert rows
    ranked = {rv.variant.variant_key: rv for rv in _ranked_all(dataset)}
    saw_high = False
    for v in rows:
        assert compute_confidence(v) == _legacy_confidence(v), v.variant_key
        saw_high |= compute_confidence(v) == "High"
        m = _build_metrics(ranked[v.variant_key])
        assert m["range_display"] == f"{v.range_tested_km} km (independent test)"
        assert m["range_test_note"] is None
        expected = "independent test" if v.efficiency_basis == "Independent test" else "maker estimate"
        assert m["efficiency_display"] == f"{v.efficiency_km_per_kwh:g} km/kWh ({expected})"
        assert "earlier version" not in v.watch_outs.lower()
    assert saw_high, "expected some Same model rows to still earn High confidence"


def test_earlier_version_still_counts_for_ranking(dataset: Dataset):
    """An earlier-version test counts for the fit score; only confidence is capped."""
    v = next(x for x in dataset.variants if x.range_test_vehicle == "Earlier version")
    same = v.model_copy(update={"range_test_vehicle": "Same model"})
    assert compute_fit_score(v, EVERYTHING, compute_costs(v, EVERYTHING)) == \
        compute_fit_score(same, EVERYTHING, compute_costs(same, EVERYTHING))


def test_not_tested_rows_have_no_tested_figures(dataset: Dataset):
    for v in dataset.variants:
        if v.range_test_vehicle == "Not tested":
            assert v.range_tested_km is None
            assert v.efficiency_basis != "Independent test"
            assert compute_confidence(v) != "High"


# --- validation -----------------------------------------------------------------

def _release_with_row_changed(release_dir: Path, tmp_path: Path, row_filter, **changes) -> Path:
    fake = tmp_path / "changed"
    shutil.copytree(release_dir, fake)
    path = fake / "autobrain_engine_variants.csv"
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields, rows = reader.fieldnames, list(reader)
    next(r for r in rows if row_filter(r)).update(changes)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    mp = fake / "manifest.json"
    m = json.loads(mp.read_text(encoding="utf-8"))
    m["files"]["autobrain_engine_variants.csv"] = hashlib.sha256(path.read_bytes()).hexdigest()
    mp.write_text(json.dumps(m), encoding="utf-8")
    return fake


def test_validation_rejects_unknown_vehicle_value(release_dir: Path, tmp_path: Path):
    fake = _release_with_row_changed(
        release_dir, tmp_path, lambda r: r["range_test_vehicle"] == "Same model", range_test_vehicle="Maybe",
    )
    assert any("range_test_vehicle='Maybe'" in e for e in validate_release(fake).critical_errors)


def test_validation_rejects_earlier_version_without_note(release_dir: Path, tmp_path: Path):
    fake = _release_with_row_changed(
        release_dir, tmp_path, lambda r: r["range_test_vehicle"] == "Earlier version", range_test_note="",
    )
    assert any("needs a range_test_note" in e for e in validate_release(fake).critical_errors)


def test_validation_rejects_not_tested_with_tested_range(release_dir: Path, tmp_path: Path):
    fake = _release_with_row_changed(
        release_dir, tmp_path, lambda r: r["range_test_vehicle"] == "Same model", range_test_vehicle="Not tested",
    )
    assert any("'Not tested' but a tested" in e for e in validate_release(fake).critical_errors)


def test_efficiency_wording_matches_range_wording(dataset: Dataset):
    """Efficiency is worded like the range: independent test / tested on an earlier version /
    maker estimate. No row falls through to another wording."""
    ranked = _ranked_all(dataset)
    seen = set()
    for rv in ranked:
        shown = _build_metrics(rv)["efficiency_display"]
        if shown is None:
            assert not rv.variant.efficiency_km_per_kwh
            continue
        basis = shown[shown.index("(") + 1:-1]
        assert basis in ("independent test", EARLIER_VERSION_LABEL, "maker estimate"), shown
        seen.add(basis)
    assert seen == {"independent test", EARLIER_VERSION_LABEL, "maker estimate"}
