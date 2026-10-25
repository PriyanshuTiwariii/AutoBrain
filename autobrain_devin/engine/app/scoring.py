"""Fit score, evidence confidence, and ranking."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

from .costs import CostBreakdown, compute_costs
from .eligibility import Check, EligibilityResult, FEATURE_CHECKERS, check_eligibility
from .models import FeatureEnum, Needs, Variant


class RankedVariant(BaseModel):
    variant: Variant
    eligibility: EligibilityResult
    costs: CostBreakdown
    fit_score: int  # 0-100, internal
    confidence: Literal["High", "Medium", "Low"]
    relative_label: str  # "Strongest fit", "Close second", etc.


# ---------------------------------------------------------------------------
# Fit score (0-100, 4 dimensions × 25 each)
# ---------------------------------------------------------------------------

def _budget_score(variant: Variant, costs: CostBreakdown, budget: int) -> float:
    """0-25: cheaper relative to budget = higher."""
    total = costs.total_budget_cost_inr
    if total is None or budget <= 0:
        return 0.0
    ratio = total / budget
    if ratio > 1.0:
        return 0.0
    return (1.0 - ratio) * 25.0


def _range_score(variant: Variant, needs: Needs) -> float:
    """0-25: how well range meets daily + trip needs."""
    # Prefer tested range, fall back to maker real-world
    effective_range = variant.range_tested_km or (
        int(variant.range_maker_realworld_km) if variant.range_maker_realworld_km else None
    )
    if effective_range is None:
        return 5.0  # some credit for having a claimed range

    # Daily need with safety factor (need to get home + buffer)
    daily_need = needs.daily_km * 1.5  # 50% buffer for real-world driving
    trip_need = needs.longest_regular_trip_km or 0

    target = max(daily_need, trip_need)
    if target <= 0:
        return 25.0

    ratio = effective_range / target
    if ratio >= 2.0:
        return 25.0
    if ratio >= 1.0:
        return 15.0 + (ratio - 1.0) * 10.0
    return max(0.0, ratio * 15.0)


def _nice_to_have_score(variant: Variant, needs: Needs) -> float:
    """0-25: fraction of nice-to-have features that PASS."""
    if not needs.nice_to_haves:
        return 12.5  # neutral if none specified

    passes = 0
    for feature in needs.nice_to_haves:
        checker = FEATURE_CHECKERS.get(feature)
        if checker and checker(variant) == Check.PASS:
            passes += 1
    return (passes / len(needs.nice_to_haves)) * 25.0


def _priority_score(variant: Variant, needs: Needs, costs: CostBreakdown) -> float:
    """0-25: how well variant performs on the buyer's stated priority."""
    p = needs.priority

    if p == "safety":
        score = 0.0
        if variant.ncap_status == "Rated, applies":
            score += 10.0
            if variant.ncap_adult_32:
                score += min(5.0, variant.ncap_adult_32 / 32.0 * 5.0)
        if variant.esp == "Yes":
            score += 3.0
        if variant.adas in ("L2", "L2+"):
            score += 4.0
        if variant.airbags and variant.airbags >= 6:
            score += 3.0
        return min(25.0, score)

    if p == "cost":
        c5 = costs.cost_to_own_5yr_inr
        if c5 is None:
            return 5.0
        # Lower cost = higher score. Normalize against budget.
        ratio = c5 / needs.budget_max_inr if needs.budget_max_inr > 0 else 1.0
        if ratio <= 0.8:
            return 25.0
        if ratio <= 1.5:
            return max(0.0, 25.0 - (ratio - 0.8) * 25.0 / 0.7)
        return 0.0

    if p == "range":
        eff_range = variant.range_tested_km or (
            int(variant.range_maker_realworld_km) if variant.range_maker_realworld_km else 0
        )
        if eff_range >= 500:
            return 25.0
        if eff_range >= 300:
            return 10.0 + (eff_range - 300) / 200 * 15.0
        return max(0.0, eff_range / 300 * 10.0)

    if p == "features":
        score = 0.0
        if variant.adas in ("L2", "L2+"):
            score += 5.0
        if variant.camera in ("360°", "540°"):
            score += 4.0
        if variant.sunroof in ("Sunroof", "Panoramic", "Openable panoramic"):
            score += 3.0
        if variant.ventilated_front == "Yes":
            score += 4.0
        if variant.adaptive_suspension == "Yes":
            score += 4.0
        if variant.terrain_modes and variant.terrain_modes >= 4:
            score += 3.0
        if variant.battery_warranty == "Lifetime (1st owner)":
            score += 2.0
        return min(25.0, score)

    if p == "space":
        score = 0.0
        if variant.seats and variant.seats >= 7:
            score += 10.0
        elif variant.seats and variant.seats >= 5:
            score += 5.0
        if variant.boot_l and variant.boot_l >= 400:
            score += 8.0
        elif variant.boot_l and variant.boot_l >= 300:
            score += 4.0
        if variant.body_type == "SUV":
            score += 5.0
        elif variant.body_type == "SUV coupé":
            score += 3.0
        return min(25.0, score)

    return 12.5  # default neutral


def compute_fit_score(
    variant: Variant, needs: Needs, costs: CostBreakdown
) -> int:
    """Compute overall fit score 0-100."""
    total = (
        _budget_score(variant, costs, needs.budget_max_inr)
        + _range_score(variant, needs)
        + _nice_to_have_score(variant, needs)
        + _priority_score(variant, needs, costs)
    )
    return min(100, max(0, round(total)))


# ---------------------------------------------------------------------------
# Evidence confidence
# ---------------------------------------------------------------------------

def compute_confidence(variant: Variant) -> Literal["High", "Medium", "Low"]:
    """Per-variant evidence confidence."""
    if variant.price_status == "pending" or variant.efficiency_basis == "None":
        return "Low"

    has_good_price = variant.price_status == "verified"
    has_good_range = (
        variant.range_tested_km is not None
        or variant.efficiency_basis == "Independent test"
    )
    has_clear_ncap = variant.ncap_status in ("Rated, applies", "Not tested")

    if has_good_price and has_good_range and has_clear_ncap:
        return "High"
    return "Medium"


# ---------------------------------------------------------------------------
# DC charging boost for no-home-charging buyers
# ---------------------------------------------------------------------------

def _dc_charging_tiebreak(variant: Variant) -> float:
    """Higher = better DC charging. Used to boost ranking when home_charging=no."""
    score = 0.0
    if variant.dc_avg_kw_est:
        score += min(100.0, variant.dc_avg_kw_est)  # higher avg power = better
    if variant.minutes_dc_per_100km_default:
        score -= variant.minutes_dc_per_100km_default  # fewer minutes = better
    return score


# ---------------------------------------------------------------------------
# Relative labels
# ---------------------------------------------------------------------------

_RANK_LABELS = [
    "Strongest fit",
    "Close second",
    "Third option",
    "Fourth option",
    "Fifth option",
]


def _assign_label(rank_index: int) -> str:
    if rank_index < len(_RANK_LABELS):
        return _RANK_LABELS[rank_index]
    return f"Option #{rank_index + 1}"


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

def rank_variants(
    variants: list[Variant],
    eligibility_results: list[EligibilityResult],
    needs: Needs,
) -> list[RankedVariant]:
    """Score, rank, and label eligible variants."""
    eligible_map = {
        er.variant_key: er for er in eligibility_results
        if er.status in ("eligible", "eligible_with_unknowns")
    }

    ranked: list[RankedVariant] = []
    for v in variants:
        er = eligible_map.get(v.variant_key)
        if er is None:
            continue
        costs = compute_costs(v, needs)
        score = compute_fit_score(v, needs, costs)
        confidence = compute_confidence(v)
        ranked.append(RankedVariant(
            variant=v,
            eligibility=er,
            costs=costs,
            fit_score=score,
            confidence=confidence,
            relative_label="",  # assigned after sorting
        ))

    # Sort: score desc → confidence desc → DC boost if no home charging → price asc
    conf_order = {"High": 0, "Medium": 1, "Low": 2}

    def sort_key(rv: RankedVariant):
        dc_boost = 0.0
        if needs.home_charging == "no":
            dc_boost = -_dc_charging_tiebreak(rv.variant)
        return (
            -rv.fit_score,
            conf_order.get(rv.confidence, 2),
            dc_boost,
            rv.variant.price_inr or 9_999_999,
        )

    ranked.sort(key=sort_key)

    # Assign relative labels
    for i, rv in enumerate(ranked):
        rv.relative_label = _assign_label(i)

    return ranked
