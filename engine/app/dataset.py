"""Load a data release into typed models with validation."""
from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Optional

from .config import ENGINE_VERSION
from .models import Accessory, LadderStep, Variant
from .validate import ValidationReport, validate_release

logger = logging.getLogger("autobrain.dataset")


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _opt_int(val: str) -> Optional[int]:
    if not val:
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _opt_float(val: str) -> Optional[float]:
    if not val:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _parse_variant(row: dict[str, str]) -> Variant:
    return Variant(
        variant_key=row["variant_key"],
        sheet_id=row.get("sheet_id", ""),
        brand=row["brand"],
        model=row["model"],
        body_type=row["body_type"],
        variant=row["variant"],
        pricing_type=row["pricing_type"],
        price_inr=_opt_int(row.get("price_inr", "")),
        price_status=row["price_status"],
        battery_kwh=float(row["battery_kwh"]),
        drive=row["drive"],
        seats=_opt_int(row.get("seats", "")),
        seat_options=row.get("seat_options", "Not stated"),
        range_claimed_km=_opt_int(row.get("range_claimed_km", "")),
        range_standard=row.get("range_standard") or None,
        range_maker_realworld_km=_opt_float(row.get("range_maker_realworld_km", "")),
        range_tested_km=_opt_int(row.get("range_tested_km", "")),
        range_test_vehicle=row["range_test_vehicle"],
        range_test_note=row.get("range_test_note") or None,
        tested_vs_claim_pct=_opt_int(row.get("tested_vs_claim_pct", "")),
        efficiency_km_per_kwh=_opt_float(row.get("efficiency_km_per_kwh", "")),
        efficiency_basis=row.get("efficiency_basis", "None"),
        charger_included=row.get("charger_included", "Not stated"),
        charger_cost_inr=_opt_int(row.get("charger_cost_inr", "")),
        charger_basis=row.get("charger_basis") or None,
        boot_l=_opt_int(row.get("boot_l", "")),
        ground_clearance_mm=_opt_int(row.get("ground_clearance_mm", "")),
        battery_clearance_mm=_opt_int(row.get("battery_clearance_mm", "")),
        airbags=_opt_int(row.get("airbags", "")),
        esp=row.get("esp", "Not stated"),
        adas=row.get("adas", "Not stated"),
        camera=row.get("camera", "Not stated"),
        sunroof=row.get("sunroof", "Not stated"),
        ventilated_front=row.get("ventilated_front", "Not stated"),
        adaptive_suspension=row.get("adaptive_suspension", "Not stated"),
        dc_max_kw=_opt_int(row.get("dc_max_kw", "")),
        dc_avg_kw_est=_opt_float(row.get("dc_avg_kw_est", "")),
        ac_full_hours_7kw=_opt_float(row.get("ac_full_hours_7kw", "")),
        onboard_ac_kw=_opt_float(row.get("onboard_ac_kw", "")),
        battery_warranty=row.get("battery_warranty", "Not stated"),
        ncap_status=row.get("ncap_status", "Not stated"),
        ncap_adult_32=_opt_float(row.get("ncap_adult_32", "")),
        ncap_child_49=_opt_float(row.get("ncap_child_49", "")),
        terrain_modes=_opt_int(row.get("terrain_modes", "")),
        wading_mm=_opt_int(row.get("wading_mm", "")),
        watch_outs=row.get("watch_outs", ""),
        running_cost_inr_per_km_default=_opt_float(row.get("running_cost_inr_per_km_default", "")),
        cost_to_own_5yr_default=_opt_int(row.get("cost_to_own_5yr_default", "")),
        minutes_dc_per_100km_default=_opt_int(row.get("minutes_dc_per_100km_default", "")),
    )


def _parse_ladder(row: dict[str, str]) -> LadderStep:
    return LadderStep(
        ladder_key=row["ladder_key"],
        model=row["model"],
        from_variant_key=row["from_variant_key"],
        to_variant_key=row["to_variant_key"],
        from_variant=row.get("from_variant", ""),
        to_variant=row.get("to_variant", ""),
        from_price_inr=_opt_int(row.get("from_price_inr", "")),
        to_price_inr=_opt_int(row.get("to_price_inr", "")),
        extra_cost_inr=_opt_int(row.get("extra_cost_inr", "")),
        what_you_gain=row.get("what_you_gain", ""),
        factory_only_gains=row.get("factory_only_gains") or None,
        note=row.get("note") or None,
        price_status_from=row.get("price_status_from") or None,
        price_status_to=row.get("price_status_to") or None,
    )


def _parse_accessory(row: dict[str, str]) -> Accessory:
    return Accessory(
        accessory_key=row["accessory_key"],
        brand=row["brand"],
        model=row["model"],
        accessory=row["accessory"],
        category=row.get("category") or None,
        applies_to=row.get("applies_to") or None,
        substitutes_factory_feature=row.get("substitutes_factory_feature") or None,
        equivalence=row.get("equivalence") or None,
        equivalence_basis=row.get("equivalence_basis") or None,
        price_inr=_opt_int(row.get("price_inr", "")),
        price_source=row.get("price_source") or None,
        price_status=row.get("price_status") or None,
        installation=row.get("installation") or None,
        warranty_safe=row.get("warranty_safe") or None,
        usable_as_gap_filler=row.get("usable_as_gap_filler", "no"),
        notes=row.get("notes") or None,
    )


class Dataset:
    """In-memory representation of a validated data release."""

    def __init__(
        self,
        version: str,
        variants: list[Variant],
        ladder: list[LadderStep],
        accessories: list[Accessory],
        validation: ValidationReport,
    ) -> None:
        self.version = version
        self.engine_version = ENGINE_VERSION
        self.variants = variants
        self.ladder = ladder
        self.accessories = accessories
        self.validation = validation

        # Build indexes
        self._by_key: dict[str, Variant] = {v.variant_key: v for v in variants}
        self._by_model: dict[str, list[Variant]] = {}
        for v in variants:
            self._by_model.setdefault(v.model, []).append(v)
        self._ladder_by_model: dict[str, list[LadderStep]] = {}
        for s in ladder:
            self._ladder_by_model.setdefault(s.model, []).append(s)
        self._acc_by_model: dict[str, list[Accessory]] = {}
        for a in accessories:
            self._acc_by_model.setdefault(a.model, []).append(a)

    def get_variant(self, key: str) -> Optional[Variant]:
        return self._by_key.get(key)

    def get_variants_by_model(self, model: str) -> list[Variant]:
        return self._by_model.get(model, [])

    def get_ladder_for_model(self, model: str) -> list[LadderStep]:
        steps = self._ladder_by_model.get(model, [])
        return sorted(steps, key=lambda s: s.from_price_inr or 0)

    def get_gap_fillers(self, model: str) -> list[Accessory]:
        return [
            a for a in self._acc_by_model.get(model, [])
            if a.usable_as_gap_filler == "yes"
        ]

    def all_battery_included(self) -> list[Variant]:
        return [v for v in self.variants if v.pricing_type == "battery included"]

    def all_models(self) -> set[str]:
        return set(self._by_model.keys())


def load_dataset(release_dir: Path) -> Dataset:
    """Validate and load a release. Raises RuntimeError on critical validation errors."""
    report = validate_release(release_dir)

    # Log the report
    logger.info(
        "Release %s: checksums_ok=%s, counts=%s, critical=%d, warnings=%d",
        report.release, report.checksums_ok,
        report.counts, len(report.critical_errors), len(report.warnings),
    )
    for err in report.critical_errors:
        logger.error("  CRITICAL: %s", err)
    for warn in report.warnings:
        logger.warning("  WARNING: %s", warn)

    if report.critical_errors:
        raise RuntimeError(
            f"Data release {report.release} has {len(report.critical_errors)} "
            f"critical error(s). Engine cannot start.\n"
            + "\n".join(f"  - {e}" for e in report.critical_errors)
        )

    # Read manifest for version
    manifest = json.loads((release_dir / "manifest.json").read_text(encoding="utf-8"))

    # Parse CSVs
    variants = [
        _parse_variant(r)
        for r in _read_csv_rows(release_dir / "autobrain_engine_variants.csv")
    ]
    ladder = [
        _parse_ladder(r)
        for r in _read_csv_rows(release_dir / "autobrain_variant_ladder.csv")
    ]
    accessories = [
        _parse_accessory(r)
        for r in _read_csv_rows(release_dir / "autobrain_accessories.csv")
    ]

    logger.info(
        "Loaded: %d variants, %d ladder steps, %d accessories (engine v%s)",
        len(variants), len(ladder), len(accessories), ENGINE_VERSION,
    )

    return Dataset(
        version=manifest["release"],
        variants=variants,
        ladder=ladder,
        accessories=accessories,
        validation=report,
    )
