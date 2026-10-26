"""Flexible slot assignment: best_match, strong_alternative, same_model, in_between, dont_overpay, not_recommended."""
from __future__ import annotations

import hashlib
import json
from typing import Any, TYPE_CHECKING

from .eligibility import (
    _FEATURE_LABELS, FEATURE_CHECKERS, Check, EligibilityResult, check_all,
)
from .costs import budget_cost
from .explain import fmt_lakh, fmt_ncap, render_tradeoff
from .terrain import NOT_OFFROAD_NOTE, terrain_reasons, terrain_tradeoffs
from .models import FeatureEnum, Needs, Result, ReasonCode, Slot, Variant
from .nomatch import explain_no_match
from .scoring import SLOW_DC_THRESHOLD_KW, RankedVariant, _assign_label, rank_variants
from .wording import (
    FEATURE_GROUPS, factory_only_nouns, join_list, ladder_gains, lower_first, parse_ladder,
    relevance_key,
)

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


def _car_name(v: Variant) -> str:
    return f"{v.model} {v.variant}"


def _relies_on_dc(needs: Needs) -> bool:
    return needs.home_charging != "yes" or bool(needs.longest_regular_trip_km)


def _effective_range(v: Variant) -> int | None:
    return v.range_tested_km or (
        int(v.range_maker_realworld_km) if v.range_maker_realworld_km else None
    )


EARLIER_VERSION_LABEL = "tested on an earlier version"


def _is_earlier_version_test(v: Variant) -> bool:
    return v.range_test_vehicle == "Earlier version"


def _range_label(v: Variant) -> str:
    if v.range_tested_km:
        basis = EARLIER_VERSION_LABEL if _is_earlier_version_test(v) else "tested"
        return f"{v.range_tested_km} km ({basis})"
    if v.range_maker_realworld_km:
        return f"{int(v.range_maker_realworld_km)} km (maker real-world)"
    if v.range_claimed_km:
        return f"{v.range_claimed_km} km (claimed)"
    return "not stated"


def _range_display(v: Variant) -> str:
    """Range for a card: the figure, its basis, and the earlier-version label when it applies."""
    if v.range_tested_km:
        basis = EARLIER_VERSION_LABEL if _is_earlier_version_test(v) else "independent test"
        return f"{v.range_tested_km} km ({basis})"
    if v.range_maker_realworld_km:
        return f"{int(v.range_maker_realworld_km)}+ km (maker real-world)"
    if v.range_claimed_km:
        return f"{v.range_claimed_km} km (claimed only)"
    return "not stated"


def _ncap_display(v: Variant) -> str:
    """Crash rating with its status label, so a score is never shown without what it covers.
    A petrol/diesel rating is never applied to an EV (AGENTS.md)."""
    score = f"{fmt_ncap(v.ncap_adult_32)} adult" if v.ncap_adult_32 else None
    if v.ncap_status == "Rated, applies" and score:
        return f"{score} (Bharat NCAP, covers this version)"
    if v.ncap_status == "Rated, coverage unconfirmed" and score:
        return f"{score} (Bharat NCAP, may not cover this version)"
    if v.ncap_status == "Not tested":
        return "No Bharat NCAP crash test for this EV"
    return "Crash rating not stated by maker"


def _dc_display(v: Variant) -> str | None:
    if not v.dc_avg_kw_est:
        return None
    text = f"{v.dc_avg_kw_est:g} kW avg"
    if v.minutes_dc_per_100km_default:
        text += f", about {v.minutes_dc_per_100km_default} min to add 100 km"
    return text


def _efficiency_basis_label(v: Variant) -> str:
    """Short basis for an efficiency figure, worded like the range: independent test,
    tested on an earlier version, or maker estimate."""
    if v.efficiency_basis == "Independent test":
        return EARLIER_VERSION_LABEL if _is_earlier_version_test(v) else "independent test"
    if v.efficiency_basis == "Maker real-world claim (estimate)":
        return "maker estimate"
    return v.efficiency_basis.lower()


def _efficiency_display(v: Variant) -> str | None:
    if not v.efficiency_km_per_kwh:
        return None
    return f"{v.efficiency_km_per_kwh:g} km/kWh ({_efficiency_basis_label(v)})"


def _range_plain(v: Variant) -> str:
    """Range with its basis, without brackets, for use inside a bracketed comparison."""
    return _range_label(v).replace(" (", " ").rstrip(")")


def _range_vs_need(v: Variant, needs: Needs) -> str | None:
    """'covers your 300 km trip with 178 km spare' / 'falls 20 km short of your 300 km trip'."""
    eff = _effective_range(v)
    if not eff:
        return None
    if needs.longest_regular_trip_km:
        need, what = needs.longest_regular_trip_km, f"{needs.longest_regular_trip_km} km trip"
    else:
        need, what = needs.daily_km, f"{needs.daily_km} km/day"
    if eff >= need:
        return f"covers your {what} with {eff - need} km spare"
    return f"falls {need - eff} km short of your {what}"


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
        "brand": v.brand,
        "model": v.model,
        "variant": v.variant,
        "body_type": v.body_type,
        "drive": v.drive,
        "ncap_status": v.ncap_status,
        "ncap_display": _ncap_display(v),
        "range_tested_km": v.range_tested_km,
        "range_maker_realworld_km": v.range_maker_realworld_km,
        "range_claimed_km": v.range_claimed_km,
        "efficiency_km_per_kwh": v.efficiency_km_per_kwh,
        "efficiency_basis": v.efficiency_basis,
        "efficiency_basis_label": _efficiency_basis_label(v),
        "efficiency_display": _efficiency_display(v),
        "range_display": _range_display(v),
        "range_test_vehicle": v.range_test_vehicle,
        # Shown next to tested figures; only an earlier-version test needs the explanation
        "range_test_note": v.range_test_note if _is_earlier_version_test(v) else None,
        "battery_kwh": v.battery_kwh,
        "running_cost_inr_per_km": c.running_cost_inr_per_km,
        "tariff_basis": c.tariff_basis,
        "cost_to_own_5yr_inr": c.cost_to_own_5yr_inr,
        "electricity_5yr_inr": c.electricity_5yr_inr,
        "charger_note": c.charger_note,
        "dc_avg_kw_est": v.dc_avg_kw_est,
        "dc_display": _dc_display(v),
        "minutes_dc_per_100km": v.minutes_dc_per_100km_default,
        "seats": v.seats,
        "boot_l": v.boot_l,
        "ground_clearance_mm": v.ground_clearance_mm,
        "battery_clearance_mm": v.battery_clearance_mm,
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
            reasons.append({"code": "best_crash_score", "detail": f"Highest crash-test score ({fmt_ncap(v.ncap_adult_32)} adult)."})

    # ESP standard? (the cars without it are named once the cards are known; see _name_esp_gaps)
    if v.esp == "Yes":
        no_esp = sum(1 for r in ranked if r.variant.esp != "Yes")
        if no_esp > 0:
            reasons.append({"code": "esp_standard", "detail": "ESP standard."})

    # Best DC charging? (especially relevant for no-home-charging)
    if v.dc_avg_kw_est and v.dc_avg_kw_est >= SLOW_DC_THRESHOLD_KW:
        best_dc = max((r.variant.dc_avg_kw_est or 0) for r in ranked)
        if v.dc_avg_kw_est >= best_dc:
            reasons.append({"code": "best_dc", "detail": f"Fastest DC charging ({v.dc_avg_kw_est:.0f} kW avg)."})

    # Range covers the longest regular trip (or the daily need when no trip is given)?
    coverage = _range_vs_need(v, needs)
    if coverage and coverage.startswith("covers"):
        reasons.append({"code": "range_covers_need", "detail": f"Range of {_range_label(v)} {coverage}."})

    # Battery warranty lifetime?
    if v.battery_warranty == "Lifetime (1st owner)":
        reasons.append({"code": "lifetime_warranty", "detail": "Lifetime battery warranty (first owner)."})

    reasons.extend(terrain_reasons(v, needs.road_conditions.value))

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
        score = f" ({fmt_ncap(a.ncap_adult_32)} adult)" if a.ncap_adult_32 else ""
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


def _both_rated(a: Variant, b: Variant) -> bool:
    return (
        a.ncap_status == "Rated, applies" and b.ncap_status == "Rated, applies"
        and a.ncap_adult_32 is not None and b.ncap_adult_32 is not None
    )


def _crash_shortfall(best: Variant, other: Variant) -> str | None:
    """How `other`'s crash evidence falls short of the top pick's, or None."""
    if best.ncap_status != "Rated, applies" or best.ncap_adult_32 is None:
        return None
    top = f"top pick: {fmt_ncap(best.ncap_adult_32)} adult"
    if _both_rated(best, other):
        if other.ncap_adult_32 < best.ncap_adult_32:
            return f"lower crash score ({fmt_ncap(other.ncap_adult_32)} adult vs {fmt_ncap(best.ncap_adult_32)} on the top pick)"
        return None
    if other.ncap_status == "Not tested":
        return f"no Bharat NCAP crash test ({top})"
    if other.ncap_status == "Rated, coverage unconfirmed":
        return f"crash rating may not cover this version ({top})"
    return f"no stated crash rating ({top})"


# Feature checks scanned for "what the top pick has that this car lacks"
# (ESP and crash rating are handled first, as safety; seats are a hard requirement)
_COMPARED_FEATURES = [
    f for f in FEATURE_CHECKERS
    if f not in (FeatureEnum.esp, FeatureEnum.crash_tested, FeatureEnum.seven_seats)
]


def _feature_name(feature: FeatureEnum) -> str:
    return lower_first(_FEATURE_LABELS.get(feature, feature.value))


def _lacks_vs_top_pick(best: Variant, other: Variant, needs: Needs) -> list[dict[str, str]]:
    """What the top pick has that `other` lacks, most relevant to this buyer first.
    Safety (ESP, crash rating, airbags) always comes first. Unknown is worded as unknown."""
    items: list[tuple[tuple, str, str]] = []
    if best.esp == "Yes" and other.esp != "Yes":
        items.append(((-1, 0), "esp", "ESP not listed by maker (top pick has ESP)"))
    crash = _crash_shortfall(best, other)
    if crash:
        items.append(((-1, 1), "crash", crash))
    if best.airbags and other.airbags and best.airbags > other.airbags:
        items.append(((-1, 2), "airbags", f"{other.airbags} airbags vs {best.airbags} on the top pick"))

    if _relies_on_dc(needs) and not _is_slow_dc(best) and _is_slow_dc(other) and other.dc_avg_kw_est:
        items.append((
            relevance_key("charging", None, needs), "slow_dc",
            f"slow DC charging ({other.dc_avg_kw_est:g} kW vs {best.dc_avg_kw_est:g} kW on the top pick)",
        ))
    best_range, other_range = _effective_range(best), _effective_range(other)
    if best_range and other_range and other_range < best_range:
        items.append((
            relevance_key("range", None, needs), "less_range",
            f"less range ({_range_plain(other)} vs {_range_plain(best)} on the top pick)",
        ))

    for i, feature in enumerate(_COMPARED_FEATURES):
        if feature == FeatureEnum.charger_included and needs.home_charging == "no":
            continue
        checker = FEATURE_CHECKERS[feature]
        if checker(best) != Check.PASS:
            continue
        state = checker(other)
        if state == Check.PASS:
            continue
        name = _feature_name(feature)
        short = f"no {name} (top pick has it)" if state == Check.FAIL else f"{name} not stated by maker (top pick has it)"
        items.append((relevance_key(FEATURE_GROUPS[feature], feature, needs, i), feature.value, short))

    items.sort(key=lambda x: x[0])
    return [{"code": code, "short": short} for _, code, short in items]


# Generic trade-off codes already covered by a comparison item
_COVERED_BY = {
    "esp": {"esp_not_listed"},
    "crash": {"no_crash_test", "crash_unconfirmed"},
    "slow_dc": {"slow_dc"},
}


def _price_vs_top_pick(other: Variant, best: Variant) -> dict[str, str]:
    diff = (other.price_inr or 0) - (best.price_inr or 0)
    if diff > 0:
        text = f"{fmt_lakh(diff)} more than the top pick."
    elif diff < 0:
        text = f"{fmt_lakh(-diff)} less than the top pick."
    else:
        text = "Same price as the top pick."
    return {"code": "price_vs_top_pick", "detail": text}


def _alternative_tradeoffs(alt: Variant, best: Variant, needs: Needs) -> tuple[list[dict[str, str]], set[str]]:
    """Trade-offs against the top pick: price difference, crash scores, and up to 4 of the
    top pick's features this car lacks. Returns (trade-offs, generic codes they cover)."""
    tradeoffs = [_price_vs_top_pick(alt, best)]
    lacks = _lacks_vs_top_pick(best, alt, needs)
    if _both_rated(alt, best):
        tradeoffs.append({
            "code": "crash_scores",
            "detail": f"Crash test: {fmt_ncap(alt.ncap_adult_32)} adult vs {fmt_ncap(best.ncap_adult_32)} on the top pick.",
        })
    else:
        crash = next((l for l in lacks if l["code"] == "crash"), None)
        if crash:
            tradeoffs.append({"code": "crash_vs_top_pick", "detail": crash["short"][0].upper() + crash["short"][1:] + "."})
    features = [l for l in lacks if l["code"] != "crash"][:4]
    for l in features:
        tradeoffs.append({"code": f"lacks_{l['code']}", "detail": l["short"][0].upper() + l["short"][1:] + "."})
    covered: set[str] = set()
    for l in lacks:
        covered |= _COVERED_BY.get(l["code"], set())
    return tradeoffs, covered


def _alternative_comparison(
    alt: RankedVariant, best: RankedVariant,
) -> list[dict[str, str]]:
    """The alternative's concrete advantages over the top pick."""
    av, bv = alt.variant, best.variant
    advantages = _safety_differences(av, bv, "This car", "top pick")
    if _both_rated(av, bv) and av.ncap_adult_32 > bv.ncap_adult_32:
        advantages.append({
            "code": "higher_crash_score",
            "detail": f"Higher crash score: {fmt_ncap(av.ncap_adult_32)} adult vs {fmt_ncap(bv.ncap_adult_32)} on the top pick.",
        })

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

    return advantages


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

    # Rough roads / light off-road (only when the buyer said so)
    for t in terrain_tradeoffs(v, needs.road_conditions.value):
        _add(t["code"], t["detail"], "clearance")

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
    covered_codes: set[str] | None = None,
) -> Slot:
    v = rv.variant
    watch_outs = _watch_outs_list(v, needs)
    generic = [
        t for t in _buyer_relevant_tradeoffs(v, needs, watch_outs)
        if t["code"] not in (covered_codes or set())
    ]
    tradeoffs = (extra_tradeoffs or []) + generic
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

_BEYOND_ELIGIBLE_NAMES = {
    FeatureEnum.esp: "ESP",
    FeatureEnum.crash_tested: "a Bharat NCAP rating that covers this version",
}


def _beyond_eligible(v: Variant, eligible: list[Variant], needs: Needs) -> list[str]:
    """Features this car has that none of the eligible options is confirmed to have."""
    extras: list[tuple[tuple, str]] = []
    for i, (feature, checker) in enumerate(FEATURE_CHECKERS.items()):
        if feature == FeatureEnum.seven_seats:
            continue
        if feature == FeatureEnum.charger_included and needs.home_charging == "no":
            continue
        if checker(v) == Check.PASS and not any(checker(e) == Check.PASS for e in eligible):
            name = _BEYOND_ELIGIBLE_NAMES.get(feature, _feature_name(feature))
            extras.append((relevance_key(FEATURE_GROUPS[feature], feature, needs, i), name))
    most_airbags = max((e.airbags or 0 for e in eligible), default=0)
    if v.airbags and most_airbags and v.airbags > most_airbags:
        extras.append(((-1, 0), f"{v.airbags} airbags (eligible options have up to {most_airbags})"))
    extras.sort(key=lambda x: x[0])
    return [name for _, name in extras]


def _pick_why_not(
    all_eligibility: list[EligibilityResult],
    all_variants: list[Variant],
    eligible_keys: set[str],
    needs: Needs,
    max_items: int = 3,
) -> list[Slot]:
    eligible_variants = [v for v in all_variants if v.variant_key in eligible_keys]
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
        extras = _beyond_eligible(v, eligible_variants, needs)
        if extras:
            reasons.append({
                "code": "adds_beyond_eligible",
                "detail": f"Has what none of your eligible options is confirmed to have: {join_list(extras)}.",
            })
        slots.append(Slot(
            slot="not_recommended",
            variant_key=v.variant_key,
            match_score=0,
            confidence="",  # no confidence for excluded
            price_inr=v.price_inr or 0,
            price_status=v.price_status,
            metrics={"brand": v.brand, "model": v.model, "variant": v.variant, "seats": v.seats},
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


MAX_TOP_PICK_ADDS = 5


def _factory_only_text(factory_only_gains: str | None, needs: Needs) -> str:
    return join_list(factory_only_nouns(factory_only_gains, needs))


def _collect_ladder_gains(
    from_key: str, to_key: str, dataset: "Dataset", needs: Needs, limit: int | None = None,
) -> list[str]:
    """Net gains across several ladder steps, in plain words and most relevant first:
    one entry per field, from its first 'before' to its last 'after'."""
    changes: dict[str, list[str]] = {}  # field -> [before, after]
    current = from_key
    visited: set[str] = set()
    while current != to_key and current not in visited:
        visited.add(current)
        step = next((s for s in dataset.ladder if s.from_variant_key == current), None)
        if step is None:
            break
        for field, before, after in parse_ladder(step.what_you_gain):
            changes.setdefault(field, [before, after])[1] = after
        current = step.to_variant_key
    return ladder_gains([(f, b, a) for f, (b, a) in changes.items()], needs, limit=limit)


def _name_esp_gaps(best_slot: Slot, shown: list[Variant], eligible: list[Variant]) -> None:
    """Replace 'ESP standard.' with the names of the cars concerned: those shown on other
    cards first, otherwise the eligible options without ESP."""
    for reason in best_slot.reasons:
        if reason.code != "esp_standard":
            continue
        lacking = [v for v in shown if v.esp != "Yes"] or [v for v in eligible if v.esp != "Yes"]
        names = [_car_name(v) for v in lacking]
        if len(names) > 3:
            names = names[:3] + [f"{len(lacking) - 3} more eligible options"]
        reason.detail = f"ESP standard; not listed by maker for the {join_list(names)}."


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
            gains = join_list(ladder_gains(parse_ladder(step_up.what_you_gain), needs)) or step_up.what_you_gain
            reasons = [{
                "code": "same_model_step_up",
                "detail": f"For {fmt_lakh(step_up.extra_cost_inr or 0)} more you get {gains}.",
            }]
            sm_range = _effective_range(sm_rv.variant)
            best_range = _effective_range(best.variant)
            if sm_range and best_range and sm_range > best_range:
                reasons.append({
                    "code": "range_advantage",
                    "detail": f"Range {_range_label(sm_rv.variant)} vs {_range_label(best.variant)} on the top pick.",
                })
            factory = _factory_only_text(step_up.factory_only_gains, needs)
            if factory:
                reasons.append({"code": "factory_only", "detail": f"Factory-only (can\u2019t add later): {factory}."})
            slots.append(_build_slot("same_model", sm_rv, reasons, needs))

    # --- strong_alternative: highest-ranked other model with a real advantage over the best ---
    for rv in ranked[1:]:
        if rv.variant.model == best.variant.model or rv.variant.variant_key in used_keys:
            continue
        advantages = _alternative_comparison(rv, best)
        if not advantages:
            continue  # no meaningful advantage: don't show it as an alternative
        used_keys.add(rv.variant.variant_key)
        alt_tradeoffs, covered = _alternative_tradeoffs(rv.variant, best.variant, needs)
        slots.append(_build_slot(
            "strong_alternative", rv, advantages, needs,
            extra_tradeoffs=alt_tradeoffs, covered_codes=covered,
        ))
        break

    # --- in_between: one ladder step down from best_match, if eligible and not already used ---
    if dataset is not None:
        step_down_key, ladder_step = _find_step_down(best.variant.variant_key, eligible_keys, dataset)
        if step_down_key and step_down_key not in used_keys and ladder_step:
            step_down_rv = ranked_map.get(step_down_key)
            if step_down_rv is not None:
                used_keys.add(step_down_key)
                factory_only = _factory_only_text(ladder_step.factory_only_gains, needs)
                extra = ladder_step.extra_cost_inr or 0
                given_up = join_list(ladder_gains(parse_ladder(ladder_step.what_you_gain), needs)) or ladder_step.what_you_gain
                reasons = [{
                    "code": "in_between",
                    "detail": f"You give up {given_up} for {fmt_lakh(extra)} less.",
                }]
                sd_range = _effective_range(step_down_rv.variant)
                best_range = _effective_range(best.variant)
                if sd_range and best_range and sd_range < best_range:
                    coverage = _range_vs_need(step_down_rv.variant, needs)
                    reasons.append({
                        "code": "range_tradeoff",
                        "detail": f"Range {_range_label(step_down_rv.variant)} vs "
                                  f"{_range_label(best.variant)} on the top pick; {coverage}.",
                    })
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
        cheapest_reason = {
            "code": "cheapest_eligible",
            "detail": f"Cheapest option meeting your needs ({fmt_lakh(cheapest.variant.price_inr)}).",
        }
        covered: set[str] = set()
        if cheapest.variant.model == best.variant.model:
            reasons_list = [cheapest_reason]
            if dataset is not None:
                adds = _collect_ladder_gains(
                    cheapest.variant.variant_key, best.variant.variant_key, dataset, needs,
                    limit=MAX_TOP_PICK_ADDS,
                )
                if adds:
                    reasons_list.append({"code": "ladder_gives_up", "detail": f"What the top pick adds over this: {join_list(adds)}."})
        else:
            # Different model: lead with what the saving costs in safety and features
            lacks = _lacks_vs_top_pick(best.variant, cheapest.variant, needs)[:MAX_TOP_PICK_ADDS]
            saving = f"{fmt_lakh(savings)} less than the top pick ({_car_name(best.variant)})"
            main = (
                f"{saving}, but: {join_list([l['short'] for l in lacks])}."
                if lacks else f"{saving}."
            )
            reasons_list = [{"code": "saving_with_compromises", "detail": main}, cheapest_reason]
            for l in lacks:
                covered |= _COVERED_BY.get(l["code"], set())
        slots.append(_build_slot(
            "dont_overpay", cheapest, reasons_list, needs,
            savings_vs_best=savings, covered_codes=covered,
        ))

    # Name the cars without ESP that the top pick's "ESP standard" reason refers to
    _name_esp_gaps(
        slots[0],
        shown=[ranked_map[s.variant_key].variant for s in slots[1:]],
        eligible=[rv.variant for rv in ranked[1:]],
    )

    # Relative fit labels only on the cards that compete for the top spot, in reading order;
    # in-between and don't-overpay cards are defined by their price, not their fit.
    labelled = 0
    for slot in slots:
        if slot.slot in ("best_match", "same_model", "strong_alternative"):
            slot.metrics["relative_label"] = _assign_label(labelled)
            labelled += 1
        else:
            slot.metrics.pop("relative_label", None)

    # --- not_recommended: near misses only ---
    why_not = _pick_why_not(all_eligibility, all_variants, eligible_keys, needs)
    slots.extend(why_not)

    return slots


# Buyer-facing wording for the Needs chips (the raw enum values are for code, not for people)
_HOME_CHARGING_TEXT = {"yes": "yes", "no": "no", "unsure": "not sure"}
_PRIORITY_TEXT = {"cost": "lowest cost"}
_ROAD_TEXT = {"rough_roads": "rough roads", "light_offroad": "light off-road"}
_PRICING_TEXT = {
    "baas": "battery financing (BaaS)",
    "either": "battery included or battery financing (BaaS)",
}


def _feature_names(features: list[FeatureEnum]) -> str:
    return ", ".join(_FEATURE_LABELS.get(f, f.value) for f in features)


def _needs_summary(needs: Needs) -> list[str]:
    lines = [
        f"Budget: {fmt_lakh(needs.budget_max_inr)}",
        f"Seats: {needs.seats_min}+",
        f"Daily driving: {needs.daily_km} km",
        f"Home charging: {_HOME_CHARGING_TEXT.get(needs.home_charging.value, needs.home_charging.value)}",
    ]
    if needs.longest_regular_trip_km:
        lines.append(f"Longest regular trip: {needs.longest_regular_trip_km} km")
    if needs.body_types:
        lines.append(f"Body types: {', '.join(bt.value for bt in needs.body_types)}")
    if needs.must_haves:
        lines.append(f"Must-haves: {_feature_names(needs.must_haves)}")
    if needs.nice_to_haves:
        lines.append(f"Nice-to-haves: {_feature_names(needs.nice_to_haves)}")
    lines.append(f"Priority: {_PRIORITY_TEXT.get(needs.priority.value, needs.priority.value)}")
    if needs.road_conditions.value != "city_highway":
        lines.append(f"Roads: {_ROAD_TEXT[needs.road_conditions.value]}")
    if needs.pricing_pref != "buy":
        lines.append(f"Pricing: {_PRICING_TEXT.get(needs.pricing_pref.value, needs.pricing_pref.value)}")
    return lines


def make_result_id(needs: Needs, dataset_version: str, engine_version: str) -> str:
    """Deterministic id of a result: a hash of the Needs, the data release and the engine version.

    The same inputs always give the same id, so a result can be reproduced and compared.
    It identifies a result, never a buyer: two buyers with identical Needs share it.
    """
    canonical = json.dumps(
        {"needs": needs.model_dump(mode="json"), "release": dataset_version, "engine": engine_version},
        sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


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

    if needs.road_conditions.value == "light_offroad":
        unknowns.append(NOT_OFFROAD_NOTE)

    no_match = None
    if not ranked:
        unknowns.insert(0, render_tradeoff("no_qualifying_vehicle"))
        # Say why, and show the closest option with what it would take
        no_match, closest = explain_no_match(variants, all_eligibility, needs)
        slots = [closest] if closest is not None else []

    return Result(
        result_id=make_result_id(needs, dataset_version, engine_version),
        dataset_version=dataset_version,
        engine_version=engine_version,
        needs_summary=_needs_summary(needs),
        slots=slots,
        unknowns=unknowns,
        disclaimer=DISCLAIMER,
        no_match=no_match,
    )
