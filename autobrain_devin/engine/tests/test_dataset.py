"""Tests for dataset loading, typed models, and lookups."""
from __future__ import annotations

from app.dataset import Dataset


def test_variant_count_matches_manifest(dataset: Dataset, manifest: dict):
    """Variant count must match manifest, not a hardcoded number."""
    assert len(dataset.variants) == manifest["counts"]["variants"]


def test_ladder_count_matches_manifest(dataset: Dataset, manifest: dict):
    assert len(dataset.ladder) == manifest["counts"]["ladder_steps"]


def test_accessory_count_matches_manifest(dataset: Dataset, manifest: dict):
    assert len(dataset.accessories) == manifest["counts"]["accessories"]


def test_get_variant_nexon(dataset: Dataset):
    """Known variant lookup returns correct price."""
    v = dataset.get_variant("TATA-NEXONEV-EMPOWEREDPLUSA45-45")
    assert v is not None
    assert v.price_inr is not None
    assert v.brand == "Tata"
    assert v.model == "Nexon.ev"


def test_all_battery_included_excludes_baas(dataset: Dataset):
    """all_battery_included must not contain any BaaS rows."""
    bi = dataset.all_battery_included()
    assert len(bi) > 0
    for v in bi:
        assert v.pricing_type == "battery included", v.variant_key


def test_tiago_ev_seats_five(dataset: Dataset):
    """CHANGES.md §3: every Tiago.ev variant now has seats=5."""
    tiago = dataset.get_variants_by_model("Tiago.ev")
    assert len(tiago) > 0
    for v in tiago:
        assert v.seats == 5, f"{v.variant_key} has seats={v.seats}"


def test_adaptive_suspension_field_exists(dataset: Dataset):
    """CHANGES.md §3: adaptive_suspension column exists and is typed."""
    for v in dataset.variants:
        assert hasattr(v, "adaptive_suspension")
        assert v.adaptive_suspension in ("Yes", "No", "Not stated"), (
            f"{v.variant_key}: adaptive_suspension={v.adaptive_suspension!r}"
        )


def test_get_ladder_for_model(dataset: Dataset):
    """Ladder lookup returns steps sorted by from_price_inr."""
    steps = dataset.get_ladder_for_model("BE 6 SPORTEQ")
    assert len(steps) > 0
    prices = [s.from_price_inr for s in steps if s.from_price_inr]
    assert prices == sorted(prices), "Ladder steps not sorted by price"


def test_get_gap_fillers(dataset: Dataset):
    """Gap-filler lookup returns only accessories with usable_as_gap_filler=yes."""
    fillers = dataset.get_gap_fillers("Nexon.ev")
    for a in fillers:
        assert a.usable_as_gap_filler == "yes", a.accessory_key


def test_all_models_non_empty(dataset: Dataset):
    models = dataset.all_models()
    assert len(models) >= 10  # 11 models expected


def test_version_from_manifest(dataset: Dataset, manifest: dict):
    assert dataset.version == manifest["release"]
