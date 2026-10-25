"""Flexible slot assignment: best_fit, alternative, dont_overpay, not_recommended."""
from __future__ import annotations

import uuid
from typing import Any

from .costs import compute_costs
from .eligibility import EligibilityResult, check_all
from .explain import render_reason, render_tradeoff, variant_tradeoffs
from .models import Needs, Result, ReasonCode, Slot, Variant
from .scoring import RankedVariant, rank_variants


DISCLAIMER = (
    "This recommendation is based on publicly available data as of the dataset release date. "
    "Prices are ex-showroom and exclude registration, insurance, offers and financing. "
    "Verify all details with the dealer before purchasing."
)


def _watch_outs_list(variant: Variant) -> list[str]:
    """Split CSV watch_outs into a list."""
    if not variant.watch_outs or variant.watch_outs == "None flagged":
        return []
    return [w.strip() for w in variant.watch_outs.split(";") if w.strip()]


def _build_metrics(rv: RankedVariant) -> dict[str, Any]:
    """Build the metrics dict for a slot."""
    v = rv.variant
    c = rv.costs
    metrics: dict[str, Any] = {}
    metrics["range_tested_km"] = v.range_tested_km
    metrics["range_maker_realworld_km"] = v.range_maker_realworld_km
    metrics["range_claimed_km"] = v.range_claimed_km
    metrics["efficiency_km_per_kwh"] = v.efficiency_km_per_kwh
    metrics["efficiency_basis"] = v.efficiency_basis
    metrics["battery_kwh"] = v.battery_kwh
    metrics["running_cost_inr_per_km"] = v.running_cost_inr_per_km_default
    metrics["cost_to_own_5yr_inr"] = c.cost_to_own_5yr_inr
    metrics["electricity_5yr_inr"] = c.electricity_5yr_inr
    metrics["charger_note"] = c.charger_note
    metrics["dc_avg_kw_est"] = v.dc_avg_kw_est
    metrics["minutes_dc_per_100km"] = v.minutes_dc_per_100km_default
    metrics["seats"] = v.seats
    metrics["boot_l"] = v.boot_l
    metrics["ground_clearance_mm"] = v.ground_clearance_mm
    metrics["airbags"] = v.airbags
    metrics["adaptive_suspension"] = v.adaptive_suspension
    metrics["relative_label"] = rv.relative_label
    return metrics


def _build_slot(
    slot_type: str,
    rv: RankedVariant,
    reason_codes: list[dict[str, str]],
    savings_vs_best: int | None = None,
) -> Slot:
    """Build a Slot from a RankedVariant."""
    v = rv.variant
    tradeoffs = variant_tradeoffs(v)
    return Slot(
        slot=slot_type,
        variant_key=v.variant_key,
        match_score=rv.fit_score,
        confidence=rv.confidence,
        price_inr=v.price_inr or 0,
        price_status=v.price_status,
        metrics=_build_metrics(rv),
        reasons=[ReasonCode(code=r["code"], detail=r.get("detail")) for r in reason_codes],
        tradeoffs=[ReasonCode(code=t["code"], detail=t.get("detail")) for t in tradeoffs],
        watch_outs=_watch_outs_list(v),
        savings_vs_best_inr=savings_vs_best,
    )


def _pick_why_not(
    all_eligibility: list[EligibilityResult],
    all_variants: list[Variant],
    eligible_keys: set[str],
    needs: Needs,
    max_items: int = 5,
) -> list[Slot]:
    """Pick excluded variants that looked relevant, with per-variant reasons."""
    excluded = [
        er for er in all_eligibility
        if er.status == "excluded" and er.variant_key not in eligible_keys
    ]

    # Prefer variants that failed on fewer checks (almost made it)
    excluded.sort(key=lambda er: len(er.fail_reasons))

    variant_map = {v.variant_key: v for v in all_variants}
    slots: list[Slot] = []

    seen_models: set[str] = set()
    for er in excluded:
        v = variant_map.get(er.variant_key)
        if v is None or v.pricing_type == "BaaS":
            continue
        # Show at most one per model in why-not
        if v.model in seen_models:
            continue
        seen_models.add(v.model)

        reasons = [
            {"code": "excluded", "detail": reason}
            for reason in er.fail_reasons
        ]
        tradeoffs = variant_tradeoffs(v)
        slots.append(Slot(
            slot="not_recommended",
            variant_key=v.variant_key,
            match_score=0,
            confidence="Low",
            price_inr=v.price_inr or 0,
            price_status=v.price_status,
            metrics={
                "model": v.model,
                "variant": v.variant,
                "seats": v.seats,
                "adas": v.adas,
                "ncap_status": v.ncap_status,
            },
            reasons=[ReasonCode(code=r["code"], detail=r.get("detail")) for r in reasons],
            tradeoffs=[ReasonCode(code=t["code"], detail=t.get("detail")) for t in tradeoffs],
            watch_outs=_watch_outs_list(v),
        ))
        if len(slots) >= max_items:
            break

    return slots


def assign_slots(
    ranked: list[RankedVariant],
    all_eligibility: list[EligibilityResult],
    all_variants: list[Variant],
    needs: Needs,
) -> list[Slot]:
    """Assign flexible result slots from ranked eligible variants."""
    slots: list[Slot] = []

    if not ranked:
        return slots

    # --- best_match ---
    best = ranked[0]
    if len(ranked) == 1:
        reason_code = "only_option"
    else:
        reason_code = "best_fit_score"
    slots.append(_build_slot(
        "best_match", best,
        [{"code": reason_code, "detail": render_reason(reason_code)}],
    ))

    # --- strong_alternative: different model from best ---
    alt = None
    for rv in ranked[1:]:
        if rv.variant.model != best.variant.model:
            alt = rv
            break
    if alt is not None:
        slots.append(_build_slot(
            "strong_alternative", alt,
            [{"code": "different_model_choice", "detail": render_reason("different_model_choice")}],
        ))

    # --- dont_overpay: cheapest eligible that meets all must-haves ---
    cheapest = min(ranked, key=lambda rv: rv.variant.price_inr or 9_999_999)
    if (
        cheapest.variant.variant_key != best.variant.variant_key
        and cheapest.variant.price_inr is not None
        and best.variant.price_inr is not None
        and cheapest.variant.price_inr < best.variant.price_inr
    ):
        savings = best.variant.price_inr - cheapest.variant.price_inr
        slots.append(_build_slot(
            "dont_overpay", cheapest,
            [{"code": "cheapest_eligible", "detail": render_reason("cheapest_eligible")}],
            savings_vs_best=savings,
        ))

    # --- not_recommended: excluded variants that looked relevant ---
    eligible_keys = {rv.variant.variant_key for rv in ranked}
    why_not = _pick_why_not(all_eligibility, all_variants, eligible_keys, needs)
    slots.extend(why_not)

    return slots


def _needs_summary(needs: Needs) -> list[str]:
    """Build a human-readable summary of the buyer's needs."""
    lines = [
        f"Budget: ₹{needs.budget_max_inr:,}",
        f"Seats: {needs.seats_min}+",
        f"Daily driving: {needs.daily_km} km",
        f"Home charging: {needs.home_charging.value}",
    ]
    if needs.longest_regular_trip_km:
        lines.append(f"Longest regular trip: {needs.longest_regular_trip_km} km")
    if needs.body_types:
        lines.append(f"Body types: {', '.join(bt.value for bt in needs.body_types)}")
    if needs.must_haves:
        lines.append(f"Must-haves: {', '.join(f.value for f in needs.must_haves)}")
    if needs.nice_to_haves:
        lines.append(f"Nice-to-haves: {', '.join(f.value for f in needs.nice_to_haves)}")
    lines.append(f"Priority: {needs.priority.value}")
    if needs.pricing_pref != "buy":
        lines.append(f"Pricing: {needs.pricing_pref.value}")
    return lines


def build_result(needs: Needs, variants: list[Variant], dataset_version: str, engine_version: str) -> Result:
    """Full recommendation pipeline: eligibility → costs → score → rank → slots → Result."""
    all_eligibility = check_all(variants, needs)
    ranked = rank_variants(variants, all_eligibility, needs)

    slots = assign_slots(ranked, all_eligibility, variants, needs)

    # Collect unknowns from eligible variants
    unknowns: list[str] = []
    seen_flags: set[str] = set()
    for rv in ranked:
        for flag in rv.eligibility.unknown_flags:
            if flag not in seen_flags:
                unknowns.append(flag)
                seen_flags.add(flag)

    # If nothing qualifies, add a top-level message
    if not ranked:
        unknowns.insert(0, render_tradeoff("no_qualifying_vehicle"))

    return Result(
        result_id=str(uuid.uuid4()),
        dataset_version=dataset_version,
        engine_version=engine_version,
        needs_summary=_needs_summary(needs),
        slots=slots,
        unknowns=unknowns,
        disclaimer=DISCLAIMER,
    )
