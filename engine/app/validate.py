"""Release validation: checksums, schema, unique keys, enums, completeness."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class ValidationReport(BaseModel):
    release: str
    checksums_ok: bool
    counts: dict[str, int]
    critical_errors: list[str]
    warnings: list[str]
    completeness: dict[str, dict[str, int]]  # field -> {present, missing}


# Columns the engine requires in each CSV
REQUIRED_VARIANT_COLS = {
    "variant_key", "brand", "model", "body_type", "variant",
    "pricing_type", "price_inr", "price_status", "battery_kwh",
    "drive", "seats", "seat_options",
    "range_claimed_km", "range_maker_realworld_km", "range_tested_km",
    "efficiency_km_per_kwh", "efficiency_basis",
    "charger_included", "charger_cost_inr", "charger_basis",
    "airbags", "esp", "adas", "camera", "sunroof",
    "ventilated_front", "adaptive_suspension",
    "dc_max_kw", "dc_avg_kw_est", "ac_full_hours_7kw",
    "battery_warranty", "ncap_status", "ncap_adult_32", "ncap_child_49",
    "watch_outs",
    "running_cost_inr_per_km_default", "cost_to_own_5yr_default",
    "minutes_dc_per_100km_default",
}

REQUIRED_LADDER_COLS = {
    "ladder_key", "model", "from_variant_key", "to_variant_key",
    "from_price_inr", "to_price_inr", "extra_cost_inr",
    "what_you_gain", "factory_only_gains",
}

REQUIRED_ACCESSORY_COLS = {
    "accessory_key", "brand", "model", "accessory",
    "usable_as_gap_filler", "price_inr", "equivalence",
}

REQUIRED_DICT_COLS = {"file", "column", "type", "meaning_and_rules"}

# Fields to check for completeness (variant CSV)
COMPLETENESS_FIELDS = [
    "price_inr", "seats", "range_claimed_km", "range_maker_realworld_km",
    "range_tested_km", "efficiency_km_per_kwh",
    "charger_cost_inr",
]

# Enum fields where "Not stated" / "Not listed" count as unknown, not present
COMPLETENESS_ENUM_FIELDS = [
    "esp", "adas", "camera", "sunroof", "ventilated_front",
    "adaptive_suspension", "charger_included", "ncap_status",
    "battery_warranty",
]

_UNKNOWN_VALUES = {"Not stated", "Not listed"}

MANIFEST_COUNT_KEYS = {
    "variants": "autobrain_engine_variants.csv",
    "ladder_steps": "autobrain_variant_ladder.csv",
    "accessories": "autobrain_accessories.csv",
    "dictionary_rows": "autobrain_data_dictionary.csv",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Return (headers, rows) from a CSV file."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = list(reader)
    return headers, rows


def _parse_enums_from_dictionary(dict_rows: list[dict[str, str]]) -> dict[str, set[str]]:
    """Extract allowed enum values from the (all enums) row in the data dictionary."""
    enums: dict[str, set[str]] = {}
    for row in dict_rows:
        if row.get("column", "").strip() == "(all enums)":
            text = row.get("meaning_and_rules", "")
            # Format: "Allowed values: field1: val1/val2; field2: val3/val4"
            text = re.sub(r"^Allowed values:\s*", "", text)
            for part in text.split(";"):
                part = part.strip()
                if ":" not in part:
                    continue
                field, vals = part.split(":", 1)
                # Split on "/" that is NOT surrounded by spaces (avoids
                # breaking values like "8 yrs / 1.6L km").
                enums[field.strip()] = {
                    v.strip() for v in re.split(r"(?<! )/(?! )", vals)
                }
    return enums


def validate_release(release_dir: Path) -> ValidationReport:
    """Validate a data release. Returns a report; caller decides whether to abort."""
    critical: list[str] = []
    warnings: list[str] = []
    counts: dict[str, int] = {}
    completeness: dict[str, dict[str, int]] = {}
    checksums_ok = True
    release = release_dir.name

    # --- 1. manifest.json ---
    manifest_path = release_dir / "manifest.json"
    if not manifest_path.exists():
        critical.append("manifest.json missing")
        return ValidationReport(
            release=release, checksums_ok=False, counts=counts,
            critical_errors=critical, warnings=warnings, completeness=completeness,
        )

    try:
        manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        critical.append(f"manifest.json unreadable: {exc}")
        return ValidationReport(
            release=release, checksums_ok=False, counts=counts,
            critical_errors=critical, warnings=warnings, completeness=completeness,
        )

    # --- 2. SHA-256 checksums ---
    manifest_files: dict[str, str] = manifest.get("files", {})
    for filename, expected_hash in manifest_files.items():
        csv_path = release_dir / filename
        if not csv_path.exists():
            critical.append(f"File listed in manifest missing: {filename}")
            checksums_ok = False
            continue
        actual_hash = _sha256(csv_path)
        if actual_hash != expected_hash:
            critical.append(
                f"SHA-256 mismatch for {filename}: "
                f"expected {expected_hash[:16]}…, got {actual_hash[:16]}…"
            )
            checksums_ok = False

    # --- Read all CSVs ---
    csv_files = {
        "variants": "autobrain_engine_variants.csv",
        "ladder": "autobrain_variant_ladder.csv",
        "accessories": "autobrain_accessories.csv",
        "dictionary": "autobrain_data_dictionary.csv",
    }
    headers: dict[str, list[str]] = {}
    rows_by_csv: dict[str, list[dict[str, str]]] = {}
    for key, fname in csv_files.items():
        p = release_dir / fname
        if not p.exists():
            critical.append(f"Required CSV missing: {fname}")
            headers[key] = []
            rows_by_csv[key] = []
        else:
            h, r = _read_csv(p)
            headers[key] = h
            rows_by_csv[key] = r

    # --- 3. Row counts vs manifest ---
    manifest_counts: dict[str, int] = manifest.get("counts", {})
    actual_counts = {
        "variants": len(rows_by_csv.get("variants", [])),
        "ladder_steps": len(rows_by_csv.get("ladder", [])),
        "accessories": len(rows_by_csv.get("accessories", [])),
        "dictionary_rows": len(rows_by_csv.get("dictionary", [])),
    }
    counts = actual_counts
    for count_key, actual in actual_counts.items():
        expected = manifest_counts.get(count_key)
        if expected is not None and actual != expected:
            critical.append(
                f"Row count mismatch for {count_key}: "
                f"manifest says {expected}, CSV has {actual}"
            )

    # --- 4. Required columns ---
    col_checks = [
        ("variants", REQUIRED_VARIANT_COLS),
        ("ladder", REQUIRED_LADDER_COLS),
        ("accessories", REQUIRED_ACCESSORY_COLS),
        ("dictionary", REQUIRED_DICT_COLS),
    ]
    for key, required in col_checks:
        present = set(headers.get(key, []))
        missing = required - present
        if missing:
            critical.append(f"{csv_files.get(key, key)}: missing columns {sorted(missing)}")

    # --- 5. Unique keys ---
    variant_rows = rows_by_csv.get("variants", [])
    variant_keys = [r.get("variant_key", "") for r in variant_rows]
    if len(variant_keys) != len(set(variant_keys)):
        dupes = [k for k in set(variant_keys) if variant_keys.count(k) > 1]
        critical.append(f"Duplicate variant_key(s): {dupes}")

    ladder_rows = rows_by_csv.get("ladder", [])
    ladder_keys = [r.get("ladder_key", "") for r in ladder_rows]
    if len(ladder_keys) != len(set(ladder_keys)):
        dupes = [k for k in set(ladder_keys) if ladder_keys.count(k) > 1]
        critical.append(f"Duplicate ladder_key(s): {dupes}")

    acc_rows = rows_by_csv.get("accessories", [])
    acc_keys = [r.get("accessory_key", "") for r in acc_rows]
    if len(acc_keys) != len(set(acc_keys)):
        dupes = [k for k in set(acc_keys) if acc_keys.count(k) > 1]
        critical.append(f"Duplicate accessory_key(s): {dupes}")

    # --- Warnings: enum validation ---
    dict_rows = rows_by_csv.get("dictionary", [])
    allowed_enums = _parse_enums_from_dictionary(dict_rows)
    for row in variant_rows:
        vk = row.get("variant_key", "?")
        for field, allowed in allowed_enums.items():
            val = row.get(field, "")
            if val and val not in allowed:
                warnings.append(f"{vk}: {field}={val!r} not in allowed set")

    # --- Warnings: pricing consistency ---
    for row in variant_rows:
        vk = row.get("variant_key", "?")
        pt = row.get("pricing_type", "")
        pi = row.get("price_inr", "")
        ps = row.get("price_status", "")
        if pt == "battery included" and not pi:
            warnings.append(f"{vk}: pricing_type=battery included but price_inr is empty")
        if ps == "verified" and not pi:
            warnings.append(f"{vk}: price_status=verified but price_inr is empty")

    # --- Warnings: ladder cross-references ---
    variant_key_set = set(variant_keys)
    for row in ladder_rows:
        for col in ("from_variant_key", "to_variant_key"):
            k = row.get(col, "")
            if k and k not in variant_key_set:
                warnings.append(f"Ladder {col}={k!r} not in variants")

    # --- Warnings: accessory model cross-references ---
    variant_models = {r.get("model", "") for r in variant_rows}
    for row in acc_rows:
        m = row.get("model", "")
        if m and m not in variant_models:
            warnings.append(f"Accessory model={m!r} not in variant models")

    # --- Completeness ---
    for field in COMPLETENESS_FIELDS:
        present = sum(1 for r in variant_rows if r.get(field, ""))
        missing = len(variant_rows) - present
        completeness[field] = {"present": present, "missing": missing}

    # Enum fields: "Not stated" / "Not listed" count as unknown
    for field in COMPLETENESS_ENUM_FIELDS:
        known = 0
        unknown = 0
        blank = 0
        for r in variant_rows:
            val = r.get(field, "")
            if not val:
                blank += 1
            elif val in _UNKNOWN_VALUES:
                unknown += 1
            else:
                known += 1
        completeness[field] = {"known": known, "unknown": unknown, "blank": blank}

    # Efficiency split by basis
    eff_independent = sum(
        1 for r in variant_rows
        if r.get("efficiency_basis", "") == "Independent test"
    )
    eff_maker = sum(
        1 for r in variant_rows
        if r.get("efficiency_basis", "") == "Maker real-world claim (estimate)"
    )
    eff_none = len(variant_rows) - eff_independent - eff_maker
    completeness["efficiency_basis"] = {
        "independent_test": eff_independent,
        "maker_estimate": eff_maker,
        "none": eff_none,
    }

    return ValidationReport(
        release=release,
        checksums_ok=checksums_ok,
        counts=counts,
        critical_errors=critical,
        warnings=warnings,
        completeness=completeness,
    )
