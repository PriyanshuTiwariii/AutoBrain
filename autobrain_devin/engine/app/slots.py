"""Flexible slot assignment: best_match, strong_alternative, same_model, in_between, dont_overpay, not_recommended."""
from __future__ import annotations

import uuid
from typing import Any, TYPE_CHECKING

from .eligibility import (
    _FEATURE_LABELS, FEATURE_CHECKERS, Check, EligibilityResult, check_all,
)
from .costs import budget_cost
from .explain import fmt_lakh, render_tradeoff
from .models import Needs, Result, ReasonCode, Slot, Variant
from .scoring import SLOW_DC_THRESHOLD_KW, RankedVariant, _assign_label, rank_variants

if TYPE_CHECKING:
    from .dataset import Dataset


DISCLAIMER = (
    "This recommendation is based on publicly available data as of the dataset release date. "
    "Prices are ex-showroom and exclude registration, insurance, offers and financing. "
    "Verify all details with the dealer before purchasing."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_slow_dc(v: Variant) -> bool:
    return (v.dc_avg_kw_est or 0) < SLOW_DC_THRESHOLD_KW


def _effective_range(v: Variant) -> int | None:
    return v.range_tested_km or (
        int(v.range_maker_realworld_km) if v.range_maker_realworld_km else None
    )


def _range_label(v: Variant) -> str:
    if v.range_tested_km:
        return f"{v.range_tested_km} km (tested)"
    if v.range_maker_realworld_km:
        return f"{int(v.range_maker_realworld_km)} km (maker real-world)"
    if v.range_claimed_km:
        return f"{v.range_claimed_km} km (claimed)"
    return "not stated"


WALL_CHARGER_WATCH_OUT = "wall charger not in price"


def _watch_outs_list(variant: Variant, needs: Needs) -> list[str]:
    """All watch-outs, except one that doesn't apply to the buyer (AGENTS.md).
    Only case: the wall-charger watch-out when the buyer can't charge at home."""
    if not variant.watch_outs or variant.watch_outs == "None flagged":
        return []
    items = [w.strip() for w in variant.watch_outs.split(";") if w.strip()]
    if needs.home_charging == "no":
        items = [w for w in items if not w.lower().startswith(WALL_CHARGER_WATCH_OUT)]
    return items


def _build_metrics(rv: RankedVariant) -> dict[str, Any]:
    v = rv.variant
    c = rv.costs
    return {
        "range_tested_km": v.range_tested_km,
        "range_maker_realworld_km": v.range_maker_realworld_km,
        "range_claimed_km": v.range_claimed_km,
        "efficiency_km_per_kwh": v.efficiency_km_per_kwh,
        "efficiency_basis": v.efficiency_basis,
        "battery_kwh": v.battery_kwh,
        "running_cost_inr_per_km": c.running_cost_inr_per_km,
        "tariff_basis": c.tariff_basis,
        "cost_to_own_5yr_inr": c.cost_to_own_5yr_inr,
        "electricity_5yr_inr": c.electricity_5yr_inr,
        "charger_note": c.charger_note,
        "dc_avg_kw_est": v.dc_avg_kw_est,
        "minutes_dc_per_100km": v.minutes_dc_per_100km_default,
        "seats": v.seats,
        "boot_l": v.boot_l,
        "ground_clearance_mm": v.ground_clearance_mm,
        "airbags": v.airbags,
        "adaptive_suspension": v.adaptive_suspension,
        "relative_label": rv.relative_label,
    }


# ---------------------------------------------------------------------------
# Specific, data-driven reasons
# ---------------------------------------------------------------------------

def _specific_reasons(rv: RankedVariant, needs: Needs, ranked: list[RankedVariant]) -> list[dict[str, str]]:
    """Generate concrete reasons from the data, not generic labels."""
    reasons: list[dict[str, str]] = []
    v = rv.variant
    c = rv.costs

    if len(ranked) == 1:
        reasons.append({"code": "only_option", "detail": "The only vehicle meeting all your requirements."})
        return reasons

    # Lowest 5-year cost?
    costs_5yr = [r.costs.cost_to_own_5yr_inr for r in ranked if r.costs.cost_to_own_5yr_inr]
    if c.cost_to_own_5yr_inr and costs_5yr and c.cost_to_own_5yr_inr <= min(costs_5yr):
        reasons.append({"code": "lowest_5yr_cost", "detail": f"Lowest estimated 5-year cost among eligible options (~{fmt_lakh(c.cost_to_own_5yr_inr)})."})

    # Highest crash score?
    if v.ncap_status == "Rated, applies" and v.ncap_adult_32:
        best_ncap = max((r.variant.ncap_adult_32 or 0) for r in ranked)
        if v.ncap_adult_32 >= best_ncap:
            reasons.append({"code": "best_crash_score", "detail": f"Highest crash-test score ({v.ncap_adult_32:.0f}/32 adult)."}) 

    # ESP standard?
    if v.esp == "Yes":
        no_esp = sum(1 for r in ranked if r.variant.esp != "Yes")
        if no_esp > 0:
            reasons.append({"code": "esp_standard", "detail": "ESP standard (not listed on some alternatives)."})

    # Best DC charging? (especially relevant for no-home-charging)
    if v.dc_avg_kw_est and v.dc_avg_kw_est >= SLOW_DC_THRESHOLD_KW:
        best_dc = max((r.variant.dc_avg_kw_est or 0) for r in ranked)
        if v.dc_avg_kw_est >= best_dc:
            reasons.append({"code": "best_dc", "detail": f"Fastest DC charging ({v.dc_avg_kw_est:.0f} kW avg)."}) 

    # Range covers daily need?
    eff_range = _effective_range(v)
    if eff_range:
        spare = eff_range - needs.daily_km
        if spare > 0:
            reasons.append({"code": "range_covers_daily", "detail": f"Range of {_range_label(v)} covers your {needs.daily_km} km/day with {spare} km spare."})

    # Battery warranty lifetime?
    if v.battery_warranty == "Lifetime (1st owner)":
        reasons.append({"code": "lifetime_warranty", "detail": "Lifetime battery warranty (first owner)."})

    # If nothing specific, add a generic fallback
    if not reasons:
        reasons.append({"code": "best_fit", "detail": "Best overall fit for your stated needs."})

    return reasons


MIN_5YR_COST_DIFF_INR = 25_000  # smaller 5-year differences are within estimate noise

_NCAP_PHRASE = {
    "Rated, applies": "a Bharat NCAP rating that applies",
    "Rated, coverage unconfirmed": "a crash rating that may not cover its version",
    "Not tested": "no Bharat NCAP crash test",
    "Not stated": "no stated crash rating",
}


def _esp_phrase(esp: str) -> str:
    return "ESP standard" if esp == "Yes" else "ESP not listed by maker"


def _safety_differences(a: Variant, b: Variant, a_name: str, b_name: str) -> list[dict[str, str]]:
    """Safety items where car `a` has something car `b` doesn't (ESP, crash rating, airbags).
    Unknown values are worded as unknown, never as 'no'."""
    diffs: list[dict[str, str]] = []
    if a.esp == "Yes" and b.esp != "Yes":
        diffs.append({
            "code": "esp_difference",
            "detail": f"{a_name}: {_esp_phrase(a.esp)}; {b_name}: {_esp_phrase(b.esp)}.",
        })
    if a.ncap_status == "Rated, applies" and b.ncap_status != "Rated, applies":
        score = f" ({a.ncap_adult_32:.0f}/32 adult)" if a.ncap_adult_32 else ""
        diffs.append({
            "code": "crash_rating_difference",
            "detail": f"{a_name}: Bharat NCAP rating applies{score}; {b_name}: "
                      f"{_NCAP_PHRASE.get(b.ncap_status, b.ncap_status.lower())}.",
        })
    if a.airbags and b.airbags and a.airbags > b.airbags:
        diffs.append({
            "code": "airbags_difference",
            "detail": f"{a_name}: {a.airbags} airbags; {b_name}: {b.airbags}.",
        })
    return diffs


def _alternative_comparison(
    alt: RankedVariant, best: RankedVariant,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """(the alternative's concrete advantages, safety items where it falls short of the best)."""
    av, bv = alt.variant, best.variant
    advantages = _safety_differences(av, bv, "This car", "top pick")

    if av.adas in ("L2", "L2+") and bv.adas not in ("L2", "L2+"):
        top = "none" if bv.adas == "None" else "not stated"
        advantages.append({"code": "has_adas", "detail": f"ADAS {av.adas}; top pick: {top}."})

    alt_range = _effective_range(av)
    best_range = _effective_range(bv)
    if alt_range and best_range and alt_range > best_range:
        advantages.append({"code": "better_range", "detail": f"Range {_range_label(av)} vs {_range_label(bv)} on the top pick."})

    if av.dc_avg_kw_est and av.dc_avg_kw_est > (bv.dc_avg_kw_est or 0):
        top_dc = f"{bv.dc_avg_kw_est:.0f} kW" if bv.dc_avg_kw_est else "not stated"
        advantages.append({"code": "better_dc", "detail": f"Faster DC charging ({av.dc_avg_kw_est:.0f} kW avg vs {top_dc})."})

    if av.battery_warranty == "Lifetime (1st owner)" and bv.battery_warranty != "Lifetime (1st owner)":
        advantages.append({"code": "lifetime_warranty", "detail": "Lifetime battery warranty (first owner); the top pick's is not."})

    a5, b5 = alt.costs.cost_to_own_5yr_inr, best.costs.cost_to_own_5yr_inr
    if a5 and b5 and b5 - a5 >= MIN_5YR_COST_DIFF_INR:
        advantages.append({"code": "lower_5yr", "detail": f"~{fmt_lakh(b5 - a5)} lower estimated 5-year cost."})

    shortfalls = [
        {"code": "safety_vs_top_pick", "detail": d["detail"]}
        for d in _safety_differences(bv, av, "Top pick", "this car")
    ]
    return advantages, shortfalls


# ---------------------------------------------------------------------------
# Trade-offs — only buyer-relevant, no duplicates of watch_outs
# ---------------------------------------------------------------------------

def _range_is_tight(v: Variant, needs: Needs) -> bool:
    """True when the buyer's stated driving uses a large share of the range."""
    target = max(needs.daily_km * 1.5, needs.longest_regular_trip_km or 0)
    eff = _effective_range(v)
    return eff is None or eff < 2 * target


def _buyer_relevant_tradeoffs(v: Variant, needs: Needs, watch_outs: list[str]) -> list[dict[str, str]]:
    """Trade-offs filtered to buyer relevance, not repeating watch-outs."""
    wo_text = " ".join(watch_outs).lower()
    codes: list[dict[str, str]] = []

    def _add(code: str, detail: str, watch_out_keyword: str):
        # Skip when a watch-out already says the same thing
        if watch_out_keyword not in wo_text:
            codes.append({"code": code, "detail": detail})

    # Safety-related (always relevant)
    if v.ncap_status == "Not tested":
        _add("no_crash_test", "No Bharat NCAP crash test for this EV.", "ncap")
    if v.ncap_status == "Rated, coverage unconfirmed":
        _add("crash_unconfirmed", "Crash rating may not cover this version.", "ncap")
    if v.esp != "Yes":
        _add("esp_not_listed", "ESP not listed by maker.", "esp not listed")

    # DC charging (relevant when the buyer depends on public charging or drives long trips)
    relies_on_dc = needs.home_charging != "yes" or needs.longest_regular_trip_km
    if relies_on_dc and v.dc_avg_kw_est and v.dc_avg_kw_est < SLOW_DC_THRESHOLD_KW:
        _add("slow_dc", f"Slow DC fast-charging ({v.dc_avg_kw_est:.0f} kW).", "slow dc")

    # Wall charger (relevant only to buyers who can charge at home)
    if (
        needs.home_charging != "no"
        and not v.charger_included.startswith("Yes")
        and v.pricing_type != "BaaS"
        and v.charger_cost_inr
    ):
        _add("charger_extra", f"Wall charger not in price (~{fmt_lakh(v.charger_cost_inr)}).", "charger")

    # Price status
    if v.price_status == "corroborated":
        _add("price_corroborated", "Price corroborated, confirm before buying.", "price corroborated")
    if v.price_status == "pending":
        _add("price_pending", "Price not yet confirmed.", "price")

    # Range evidence (relevant when range matters to this buyer)
    if v.range_tested_km is None and v.efficiency_basis != "Independent test":
        if needs.priority == "range" or _range_is_tight(v, needs):
            _add("range_only_claimed", "No independent range test; only maker claim.", "independent range")

    return codes


# ---------------------------------------------------------------------------
# Slot builder
# ---------------------------------------------------------------------------

def _build_slot(
    slot_type: str,
    rv: RankedVariant,
    reason_codes: list[dict[str, str]],
    needs: Needs,
    savings_vs_best: int | None = None,
    extra_tradeoffs: list[dict[str, str]] | None = None,
) -> Slot:
    v = rv.variant
    watch_outs = _watch_outs_list(v, needs)
    tradeoffs = (extra_tradeoffs or []) + _buyer_relevant_tradeoffs(v, needs, watch_outs)
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
        watch_outs=watch_outs,
        savings_vs_best_inr=savings_vs_best,
    )


# ---------------------------------------------------------------------------
# Why-not: near misses only (within 10% over budget OR exactly 1 fail), max 3
# ---------------------------------------------------------------------------

def _pick_why_not(
    all_eligibility: list[EligibilityResult],
    all_variants: list[Variant],
    eligible_keys: set[str],
    needs: Needs,
    max_items: int = 3,
) -> list[Slot]:
    excluded = [
        er for er in all_eligibility
        if er.status == "excluded" and er.variant_key not in eligible_keys
    ]
    variant_map = {v.variant_key: v for v in all_variants}
    # (failed check, eligibility, variant)
    candidates: list[tuple[str, EligibilityResult, Variant]] = []

    budget_ceiling = needs.budget_max_inr * 1.10
    # Hard limits the buyer set: a car failing these is not a "near miss"
    not_near_miss = {"seats", "body_type", "exclude_model", "pricing_type"}

    for er in excluded:
        v = variant_map.get(er.variant_key)
        if v is None or v.pricing_type == "BaaS":
            continue
        # Near miss: fails exactly one need; a budget fail must be within 10%
        failed = [k for k, c in er.checks.items() if c == Check.FAIL]
        if len(failed) != 1 or failed[0] in not_near_miss:
            continue
        if failed[0] == "budget":
            total = budget_cost(v, needs)
            if total is None or total > budget_ceiling:
                continue
        candidates.append((failed[0], er, v))

    # Most attractive first: meets more of the must-haves, smallest overrun, then
    # the fuller car closest to the budget.
    def _attractiveness(item: tuple[str, EligibilityResult, Variant]):
        _, er, v = item
        must_passes = sum(
            1 for k, c in er.checks.items() if k.startswith("must_") and c == Check.PASS
        )
        overrun = max(0, (budget_cost(v, needs) or 0) - needs.budget_max_inr)
        return (-must_passes, overrun, -(v.price_inr or 0), v.variant_key)

    candidates.sort(key=_attractiveness)

    # One per distinct failed need first, so the buyer sees each trade-off, then fill.
    # Never two variants of the same model.
    picked: list[tuple[str, EligibilityResult, Variant]] = []
    seen_models: set[str] = set()
    seen_fails: set[str] = set()
    for distinct_pass in (True, False):
        for item in candidates:
            fail, _, v = item
            if len(picked) >= max_items:
                break
            if v.model in seen_models or (distinct_pass and fail in seen_fails):
                continue
            picked.append(item)
            seen_models.add(v.model)
            seen_fails.add(fail)

    slots: list[Slot] = []
    for _, er, v in picked:
        reasons = [{"code": "excluded", "detail": r} for r in er.fail_reasons]
        slots.append(Slot(
            slot="not_recommended",
            variant_key=v.variant_key,
            match_score=0,
            confidence="",  # no confidence for excluded
            price_inr=v.price_inr or 0,
            price_status=v.price_status,
            metrics={"model": v.model, "variant": v.variant, "seats": v.seats},
            reasons=[ReasonCode(code=r["code"], detail=r.get("detail")) for r in reasons],
            tradeoffs=[],
            watch_outs=[],
        ))
        if len(slots) >= max_items:
            break

    return slots


# ---------------------------------------------------------------------------
# Ladder helpers
# ---------------------------------------------------------------------------

def _find_step_down(best_key: str, eligible_keys: set[str], dataset: "Dataset"):
    for step in dataset.ladder:
        if step.to_variant_key == best_key and step.from_variant_key in eligible_keys:
            return step.from_variant_key, step
    return None, None


def _find_step_up(best_key: str, eligible_keys: set[str], dataset: "Dataset"):
    for step in dataset.ladder:
        if step.from_variant_key == best_key and step.to_variant_key in eligible_keys:
            return step.to_variant_key, step
    return None, None


# Ladder field names → buyer wording (ladder "Range km" is the maker's claimed range)
_LADDER_NUMERIC_FIELDS = {
    "Battery kWh": ("battery", "kWh"),
    "Range km": ("claimed range", "km"),
}
_LADDER_NO_VALUE = ("not stated", "not listed", "none", "no", "—", "-", "")


def _ladder_field_name(field: str) -> str:
    return _LADDER_NUMERIC_FIELDS.get(field, (field, ""))[0]


def _is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def _gain_phrases(what_you_gain: str) -> list[str]:
    """'Sunroof: None → Sunroof; Battery kWh: 59 → 79' → ['Sunroof', 'battery 59 → 79 kWh']."""
    phrases: list[str] = []
    for item in what_you_gain.split(";"):
        item = item.strip()
        if ":" not in item or "→" not in item:
            if item:
                phrases.append(item)
            continue
        field, change = (p.strip() for p in item.split(":", 1))
        before, after = (p.strip() for p in change.split("→", 1))
        if after.lower() in _LADDER_NO_VALUE or after.lower().startswith("not stated"):
            continue  # not a gain the buyer can count on
        if _is_number(before) and _is_number(after):
            name, unit = _LADDER_NUMERIC_FIELDS.get(field, (field, ""))
            phrases.append(f"{name} {before} → {after}{' ' + unit if unit else ''}")
        elif after.lower() == field.lower():
            phrases.append(field)
        elif after.lower().startswith("yes"):
            detail = after[3:].strip(" ()")
            phrases.append(f"{field} ({detail})" if detail else field)
        else:
            phrases.append(f"{field}: {after}")
    return phrases


def _factory_only_text(factory_only_gains: str | None) -> str:
    if not factory_only_gains:
        return ""
    return ", ".join(_ladder_field_name(f.strip()) for f in factory_only_gains.split("|") if f.strip())


def _collect_ladder_gains(from_key: str, to_key: str, dataset: "Dataset") -> str | None:
    """Net gains across several ladder steps: one entry per field, first 'from' → last 'to'."""
    changes: dict[str, list[str]] = {}  # field -> [before, after]
    loose: list[str] = []
    current = from_key
    visited: set[str] = set()
    while current != to_key and current not in visited:
        visited.add(current)
        found = False
        for step in dataset.ladder:
            if step.from_variant_key == current:
                for item in step.what_you_gain.split(";"):
                    item = item.strip()
                    if ":" in item and "→" in item:
                        field, change = (p.strip() for p in item.split(":", 1))
                        before, after = (p.strip() for p in change.split("→", 1))
                        changes.setdefault(field, [before, after])[1] = after
                    elif item:
                        loose.append(item)
                current = step.to_variant_key
                found = True
                break
        if not found:
            break
    merged = "; ".join(f"{f}: {b} → {a}" for f, (b, a) in changes.items())
    gains = _gain_phrases(merged) + loose
    return ", ".join(gains) if gains else None


# ---------------------------------------------------------------------------
# Main slot assignment
# ---------------------------------------------------------------------------

def assign_slots(
    ranked: list[RankedVariant],
    all_eligibility: list[EligibilityResult],
    all_variants: list[Variant],
    needs: Needs,
    dataset: "Dataset | None" = None,
) -> list[Slot]:
    slots: list[Slot] = []
    if not ranked:
        return slots

    eligible_keys = {rv.variant.variant_key for rv in ranked}
    ranked_map = {rv.variant.variant_key: rv for rv in ranked}
    used_keys: set[str] = set()

    # --- best_match ---
    best = ranked[0]
    used_keys.add(best.variant.variant_key)
    best_reasons = _specific_reasons(best, needs, ranked)
    slots.append(_build_slot("best_match", best, best_reasons, needs))

    # --- same_model: the next variant up the best match's ladder, if eligible ---
    if dataset is not None:
        step_up_key, step_up = _find_step_up(best.variant.variant_key, eligible_keys, dataset)
        sm_rv = ranked_map.get(step_up_key) if step_up_key else None
        if sm_rv is not None and step_up_key not in used_keys:
            used_keys.add(step_up_key)
            gains = ", ".join(_gain_phrases(step_up.what_you_gain)) or step_up.what_you_gain
            reasons = [{
                "code": "same_model_step_up",
                "detail": f"For {fmt_lakh(step_up.extra_cost_inr or 0)} more you get: {gains}.",
            }]
            sm_range = _effective_range(sm_rv.variant)
            best_range = _effective_range(best.variant)
            if sm_range and best_range and sm_range > best_range:
                reasons.append({
                    "code": "range_advantage",
                    "detail": f"Real-world range {_range_label(sm_rv.variant)} vs {_range_label(best.variant)} on the top pick.",
                })
            factory = _factory_only_text(step_up.factory_only_gains)
            if factory:
                reasons.append({"code": "factory_only", "detail": f"Factory-only (can\u2019t add later): {factory}."})
            slots.append(_build_slot("same_model", sm_rv, reasons, needs))

    # --- strong_alternative: highest-ranked other model with a real advantage over the best ---
    for rv in ranked[1:]:
        if rv.variant.model == best.variant.model or rv.variant.variant_key in used_keys:
            continue
        advantages, shortfalls = _alternative_comparison(rv, best)
        if not advantages:
            continue  # no meaningful advantage: don't show it as an alternative
        used_keys.add(rv.variant.variant_key)
        slots.append(_build_slot(
            "strong_alternative", rv, advantages, needs, extra_tradeoffs=shortfalls,
        ))
        break

    # --- in_between: one ladder step down from best_match, if eligible and not already used ---
    if dataset is not None:
        step_down_key, ladder_step = _find_step_down(best.variant.variant_key, eligible_keys, dataset)
        if step_down_key and step_down_key not in used_keys and ladder_step:
            step_down_rv = ranked_map.get(step_down_key)
            if step_down_rv is not None:
                used_keys.add(step_down_key)
                factory_only = _factory_only_text(ladder_step.factory_only_gains)
                extra = ladder_step.extra_cost_inr or 0
                given_up = ", ".join(_gain_phrases(ladder_step.what_you_gain)) or ladder_step.what_you_gain
                reasons = [{
                    "code": "in_between",
                    "detail": f"You give up {given_up} for {fmt_lakh(extra)} less.",
                }]
                if factory_only:
                    reasons.append({"code": "factory_only", "detail": f"Factory-only (can\u2019t add later): {factory_only}."})
                savings = (best.variant.price_inr or 0) - (step_down_rv.variant.price_inr or 0)
                slots.append(_build_slot(
                    "in_between", step_down_rv, reasons, needs,
                    savings_vs_best=savings if savings > 0 else None,
                ))

    # --- dont_overpay: cheapest eligible, with ladder context ---
    # A buyer without home charging lives on public DC, so a slow-DC car is no saving.
    pool = ranked
    if needs.home_charging == "no":
        pool = [rv for rv in ranked if not _is_slow_dc(rv.variant)] or ranked
    cheapest = min(pool, key=lambda rv: rv.variant.price_inr or 9_999_999)
    if (
        cheapest.variant.variant_key not in used_keys
        and cheapest.variant.price_inr is not None
        and best.variant.price_inr is not None
        and cheapest.variant.price_inr < best.variant.price_inr
    ):
        used_keys.add(cheapest.variant.variant_key)
        savings = best.variant.price_inr - cheapest.variant.price_inr
        reasons_list: list[dict[str, str]] = [
            {"code": "cheapest_eligible", "detail": f"Cheapest option meeting your needs ({fmt_lakh(cheapest.variant.price_inr)})."},
        ]
        if dataset is not None and cheapest.variant.model == best.variant.model:
            ladder_gains = _collect_ladder_gains(
                cheapest.variant.variant_key, best.variant.variant_key, dataset,
            )
            if ladder_gains:
                reasons_list.append({"code": "ladder_gives_up", "detail": f"What the top pick adds over this: {ladder_gains}."})
        slots.append(_build_slot(
            "dont_overpay", cheapest, reasons_list, needs,
            savings_vs_best=savings,
        ))

    # Relative labels follow the order the buyer reads the cards, not the raw rank
    for i, slot in enumerate(slots):
        slot.metrics["relative_label"] = _assign_label(i)

    # --- not_recommended: near misses only ---
    why_not = _pick_why_not(all_eligibility, all_variants, eligible_keys, needs)
    slots.extend(why_not)

    return slots


def _needs_summary(needs: Needs) -> list[str]:
    lines = [
        f"Budget: {fmt_lakh(needs.budget_max_inr)}",
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


def build_result(
    needs: Needs,
    variants: list[Variant],
    dataset_version: str,
    engine_version: str,
    dataset: "Dataset | None" = None,
) -> Result:
    all_eligibility = check_all(variants, needs)
    ranked = rank_variants(variants, all_eligibility, needs)
    slots = assign_slots(ranked, all_eligibility, variants, needs, dataset=dataset)

    unknowns: list[str] = []
    seen_flags: set[str] = set()
    for rv in ranked:
        for flag in rv.eligibility.unknown_flags:
            if flag not in seen_flags:
                unknowns.append(flag)
                seen_flags.add(flag)

    # Nice-to-haves that no eligible option is confirmed to have
    for feature in needs.nice_to_haves:
        checker = FEATURE_CHECKERS.get(feature)
        if ranked and checker and not any(checker(rv.variant) == Check.PASS for rv in ranked):
            label = _FEATURE_LABELS.get(feature, feature.value)
            unknowns.append(render_tradeoff("nice_to_have_unmet", feature=label.lower()))
            if feature.value == "adaptive_suspension":
                unknowns.append(render_tradeoff("suspension_unknown"))

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
