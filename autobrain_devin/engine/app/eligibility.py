"""Three-state eligibility checks: PASS / FAIL / UNKNOWN per requirement."""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel

from .costs import budget_cost
from .explain import fmt_lakh
from .models import FeatureEnum, Needs, Variant


class Check(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class EligibilityResult(BaseModel):
    variant_key: str
    status: Literal["eligible", "excluded", "eligible_with_unknowns"]
    checks: dict[str, Check]
    fail_reasons: list[str]
    unknown_flags: list[str]


# ---------------------------------------------------------------------------
# Feature mapping — CHANGES.md §4, exact
# ---------------------------------------------------------------------------

def _check_adas(v: Variant) -> Check:
    if v.adas in ("L2", "L2+"):
        return Check.PASS
    if v.adas == "None":
        return Check.FAIL
    return Check.UNKNOWN  # "Not stated"


def _check_camera_360(v: Variant) -> Check:
    if v.camera in ("360°", "540°"):
        return Check.PASS
    if v.camera in ("Rear camera", "Sensors only"):
        return Check.FAIL
    return Check.UNKNOWN


def _check_sunroof(v: Variant) -> Check:
    if v.sunroof in ("Sunroof", "Panoramic", "Openable panoramic"):
        return Check.PASS
    if v.sunroof == "None":
        return Check.FAIL
    return Check.UNKNOWN


def _check_ventilated_seats(v: Variant) -> Check:
    if v.ventilated_front == "Yes":
        return Check.PASS
    if v.ventilated_front in ("No", "Passive only"):
        return Check.FAIL
    return Check.UNKNOWN


def _check_esp(v: Variant) -> Check:
    if v.esp == "Yes":
        return Check.PASS
    # ESP never FAILs — "Not listed" counts as unknown per §4
    return Check.UNKNOWN


def _check_awd(v: Variant) -> Check:
    if v.drive == "AWD":
        return Check.PASS
    if v.drive in ("FWD", "RWD"):
        return Check.FAIL
    return Check.UNKNOWN


def _check_seven_seats(v: Variant) -> Check:
    if v.seats is not None and v.seats >= 7:
        return Check.PASS
    if v.seats is not None and v.seats < 7:
        return Check.FAIL
    return Check.UNKNOWN  # seats blank


def _check_lifetime_battery_warranty(v: Variant) -> Check:
    if v.battery_warranty == "Lifetime (1st owner)":
        return Check.PASS
    if v.battery_warranty == "8 yrs / 1.6L km":
        return Check.FAIL
    return Check.UNKNOWN


def _check_crash_tested(v: Variant) -> Check:
    if v.ncap_status == "Rated, applies":
        return Check.PASS
    if v.ncap_status == "Not tested":
        return Check.FAIL
    return Check.UNKNOWN  # "Rated, coverage unconfirmed" or "Not stated"


def _check_charger_included(v: Variant) -> Check:
    if v.charger_included.startswith("Yes"):
        return Check.PASS
    if v.charger_included == "No":
        return Check.FAIL
    return Check.UNKNOWN  # "Unclear" or "Not stated"


def _check_adaptive_suspension(v: Variant) -> Check:
    if v.adaptive_suspension == "Yes":
        return Check.PASS
    if v.adaptive_suspension == "No":
        return Check.FAIL
    return Check.UNKNOWN


FEATURE_CHECKERS: dict[FeatureEnum, callable] = {
    FeatureEnum.adas: _check_adas,
    FeatureEnum.camera_360: _check_camera_360,
    FeatureEnum.sunroof: _check_sunroof,
    FeatureEnum.ventilated_seats: _check_ventilated_seats,
    FeatureEnum.esp: _check_esp,
    FeatureEnum.awd: _check_awd,
    FeatureEnum.seven_seats: _check_seven_seats,
    FeatureEnum.lifetime_battery_warranty: _check_lifetime_battery_warranty,
    FeatureEnum.crash_tested: _check_crash_tested,
    FeatureEnum.charger_included: _check_charger_included,
    FeatureEnum.adaptive_suspension: _check_adaptive_suspension,
}

# Human-readable names for flag messages
_FEATURE_LABELS: dict[FeatureEnum, str] = {
    FeatureEnum.adas: "ADAS",
    FeatureEnum.camera_360: "360° camera",
    FeatureEnum.sunroof: "Sunroof",
    FeatureEnum.ventilated_seats: "Ventilated seats",
    FeatureEnum.esp: "ESP",
    FeatureEnum.awd: "AWD",
    FeatureEnum.seven_seats: "7 seats",
    FeatureEnum.lifetime_battery_warranty: "Lifetime battery warranty",
    FeatureEnum.crash_tested: "Crash test rating",
    FeatureEnum.charger_included: "Charger included",
    FeatureEnum.adaptive_suspension: "Adaptive suspension",
}


# ---------------------------------------------------------------------------
# Main eligibility check
# ---------------------------------------------------------------------------

def check_eligibility(variant: Variant, needs: Needs) -> EligibilityResult:
    """Check a single variant against buyer needs. Returns three-state result."""
    checks: dict[str, Check] = {}
    fail_reasons: list[str] = []
    unknown_flags: list[str] = []

    # --- BaaS filter ---
    if needs.pricing_pref == "buy" and variant.pricing_type == "BaaS":
        checks["pricing_type"] = Check.FAIL
        fail_reasons.append("BaaS variant excluded (buyer prefers battery-included)")
    elif needs.pricing_pref == "baas" and variant.pricing_type != "BaaS":
        checks["pricing_type"] = Check.FAIL
        fail_reasons.append("Battery-included variant excluded (buyer prefers BaaS)")
    else:
        checks["pricing_type"] = Check.PASS

    # --- Excluded models ---
    if needs.exclude_models and variant.model in needs.exclude_models:
        checks["exclude_model"] = Check.FAIL
        fail_reasons.append(f"Model {variant.model} excluded by buyer")
    elif needs.exclude_models:
        checks["exclude_model"] = Check.PASS

    # --- Body type ---
    if needs.body_types:
        if variant.body_type in [bt.value for bt in needs.body_types]:
            checks["body_type"] = Check.PASS
        else:
            checks["body_type"] = Check.FAIL
            fail_reasons.append(
                f"Body type {variant.body_type} not in [{', '.join(bt.value for bt in needs.body_types)}]"
            )

    # --- Budget ---
    total_cost = budget_cost(variant, needs)
    if total_cost is None:
        checks["budget"] = Check.UNKNOWN
        unknown_flags.append("Price not confirmed — verify before buying")
    elif total_cost <= needs.budget_max_inr:
        checks["budget"] = Check.PASS
    else:
        checks["budget"] = Check.FAIL
        with_charger = " incl. charger" if total_cost != variant.price_inr else ""
        fail_reasons.append(
            f"Over budget: {fmt_lakh(total_cost)}{with_charger} vs your {fmt_lakh(needs.budget_max_inr)} budget"
        )

    # --- Seats ---
    if variant.seats is not None:
        if variant.seats >= needs.seats_min:
            checks["seats"] = Check.PASS
        else:
            checks["seats"] = Check.FAIL
            fail_reasons.append(
                f"Only {variant.seats} seats (need {needs.seats_min}+)"
            )
    else:
        # CHANGES.md §5: seats ≥ 6 requirement must NEVER pass as UNKNOWN
        if needs.seats_min >= 6:
            checks["seats"] = Check.FAIL
            fail_reasons.append(
                f"Seats not stated; requirement of {needs.seats_min}+ cannot pass without confirmation"
            )
        else:
            checks["seats"] = Check.UNKNOWN
            unknown_flags.append("Seating not confirmed by maker — verify before buying")

    # --- Must-have features ---
    for feature in needs.must_haves:
        checker = FEATURE_CHECKERS.get(feature)
        if checker is None:
            continue
        result = checker(variant)
        checks[f"must_{feature.value}"] = result
        label = _FEATURE_LABELS.get(feature, feature.value)
        if result == Check.FAIL:
            fail_reasons.append(f"{label}: not available")
        elif result == Check.UNKNOWN:
            unknown_flags.append(f"{label} not stated by maker — verify before buying")

    # --- Determine overall status ---
    has_fail = any(c == Check.FAIL for c in checks.values())
    has_unknown = any(c == Check.UNKNOWN for c in checks.values())

    if has_fail:
        status = "excluded"
    elif has_unknown:
        status = "eligible_with_unknowns"
    else:
        status = "eligible"

    return EligibilityResult(
        variant_key=variant.variant_key,
        status=status,
        checks=checks,
        fail_reasons=fail_reasons,
        unknown_flags=unknown_flags,
    )


def check_all(variants: list[Variant], needs: Needs) -> list[EligibilityResult]:
    """Check all variants against buyer needs."""
    return [check_eligibility(v, needs) for v in variants]
