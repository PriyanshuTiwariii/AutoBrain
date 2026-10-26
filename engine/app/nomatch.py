"""When no variant meets every need: say why, name the closest option and what it would take.

Everything here is derived from the same three-state checks the engine already ran
(app.eligibility), so the explanation can never disagree with the verdict. Unknown is never
counted as "has it" or "lacks it": a variant that is only unknown on a need is still eligible
for that need, exactly as in eligibility.
"""
from __future__ import annotations

from itertools import combinations

from .costs import budget_cost, charger_cost
from .eligibility import _FEATURE_LABELS, FEATURE_CHECKERS, Check, EligibilityResult
from .explain import fmt_lakh
from .models import FeatureEnum, NoMatch, Needs, ReasonCode, Slot, Variant

# "No variant within ₹8 lakh has ___"
_HAS_PHRASE: dict[FeatureEnum, str] = {
    FeatureEnum.adas: "ADAS",
    FeatureEnum.camera_360: "a 360° camera",
    FeatureEnum.sunroof: "a sunroof",
    FeatureEnum.ventilated_seats: "ventilated front seats",
    FeatureEnum.esp: "ESP listed by the maker",
    FeatureEnum.awd: "AWD",
    FeatureEnum.seven_seats: "7 seats",
    FeatureEnum.lifetime_battery_warranty: "a lifetime battery warranty",
    FeatureEnum.crash_tested: "a Bharat NCAP crash-test rating for the EV",
    FeatureEnum.charger_included: "a home charger included",
    FeatureEnum.adaptive_suspension: "adaptive suspension",
}

# Choices that scope the search ("only SUVs", "never model X", "battery included only").
# They are not needs the buyer could trade away in the same breath, so they define the pool.
_SCOPE_CHECKS = ("pricing_type", "exclude_model", "body_type")


def _car_name(v: Variant) -> str:
    return f"{v.brand} {v.model} {v.variant}"


def _names(variants: list[Variant], limit: int = 3) -> str:
    names = [_car_name(v) for v in sorted(variants, key=lambda v: v.variant_key)]
    if len(names) > limit:
        names = names[:limit] + [f"{len(variants) - limit} more"]
    return ", ".join(names[:-1]) + (" and " if len(names) > 1 else "") + names[-1]


def _seats_phrase(needs: Needs) -> str:
    return "7 seats" if needs.seats_min >= 7 else f"{needs.seats_min} or more seats"


def _feature_phrase(feature: FeatureEnum) -> str:
    return _HAS_PHRASE.get(feature, _FEATURE_LABELS.get(feature, feature.value))


def _requirements(needs: Needs) -> list[tuple[str, str]]:
    """(check key in EligibilityResult.checks, what a variant must have), in the order we report."""
    reqs = [("seats", _seats_phrase(needs))]
    for feature in needs.must_haves:
        if feature == FeatureEnum.seven_seats and needs.seats_min >= 7:
            continue  # the seats requirement already says it
        reqs.append((f"must_{feature.value}", _feature_phrase(feature)))
    return reqs


def _failed_requirements(er: EligibilityResult) -> list[str]:
    return [k for k, c in er.checks.items() if c == Check.FAIL and (k in ("budget", "seats") or k.startswith("must_"))]


def _what_it_takes(v: Variant, er: EligibilityResult, needs: Needs) -> list[str]:
    """What the buyer would have to change to get this variant: budget, seats, or a must-have."""
    lines: list[str] = []
    for key in _failed_requirements(er):
        if key == "budget":
            total = budget_cost(v, needs)
            if total is None:
                continue
            extra = charger_cost(v, needs) if needs.budget_includes_charger else 0
            note = f", which includes ~{fmt_lakh(extra)} for the wall charger" if extra else ""
            lines.append(f"Raise your budget to at least {fmt_lakh(total)}{note}.")
        elif key == "seats":
            if v.seats is None:
                lines.append("Seat count is not stated by the maker; confirm it before relying on this car.")
            else:
                asked = str(needs.seats_min) if needs.seats_min >= 7 else f"{needs.seats_min} or more"
                lines.append(f"Accept {v.seats} seats; you asked for {asked}.")
        else:
            feature = FeatureEnum(key.removeprefix("must_"))
            label = _FEATURE_LABELS.get(feature, feature.value)
            lines.append(f"Drop \"{label}\" from your must-haves: this variant does not have it.")

    # Needs this variant meets only on paper: the maker has not stated them, so say what to check
    for key, check in er.checks.items():
        if check != Check.UNKNOWN:
            continue
        if key.startswith("must_"):
            label = _FEATURE_LABELS.get(FeatureEnum(key.removeprefix("must_")), key)
            lines.append(f"Confirm with the maker: {label} is not stated for this variant.")
        elif key == "budget":
            lines.append("Confirm the price: it is not yet confirmed for this variant.")
        elif key == "seats":
            lines.append("Confirm the seat count: it is not stated for this variant.")
    return lines


def explain_no_match(
    variants: list[Variant],
    eligibility: list[EligibilityResult],
    needs: Needs,
) -> tuple[NoMatch, Slot | None]:
    """Reasons nothing qualifies, plus the closest variant (as a not_recommended slot) and what it would take."""
    by_key = {er.variant_key: er for er in eligibility}
    pool = [
        v for v in variants
        if v.variant_key in by_key
        and not any(by_key[v.variant_key].checks.get(c) == Check.FAIL for c in _SCOPE_CHECKS)
    ]

    if not pool:
        return NoMatch(
            reasons=["Your pricing, body type and excluded-model choices leave no variants to consider."],
            closest_variant_key=None,
            what_it_would_take=["Loosen one of those choices (pricing, body type or excluded models)."],
        ), None

    def passes(v: Variant, key: str) -> bool:
        return by_key[v.variant_key].checks.get(key) != Check.FAIL  # unknown still counts as possible

    within_budget = [v for v in pool if passes(v, "budget")]
    budget_text = fmt_lakh(needs.budget_max_inr)
    reasons: list[str] = []

    if within_budget:
        scope, where = within_budget, f"within {budget_text}"
    else:
        scope, where = pool, "in our data"
        priced = [(budget_cost(v, needs), v) for v in pool if budget_cost(v, needs) is not None]
        if priced:
            cheapest_cost, cheapest = min(priced, key=lambda x: (x[0], x[1].variant_key))
            reasons.append(
                f"No variant is priced within {budget_text}; the cheapest is {_car_name(cheapest)} "
                f"at {fmt_lakh(cheapest_cost)}."
            )
        else:
            reasons.append(f"No variant has a confirmed price within {budget_text}.")

    requirements = _requirements(needs)
    for key, phrase in requirements:
        possible = [v for v in scope if passes(v, key)]
        if not possible:
            reasons.append(f"No variant {where} has {phrase}.")
        elif all(by_key[v.variant_key].checks.get(key) == Check.UNKNOWN for v in possible):
            # Unknown is never "no": we can only say none is confirmed, and for whom it is unstated
            reasons.append(
                f"No variant {where} is confirmed to have {phrase} "
                f"(not stated by the maker for {_names(possible)})."
            )

    if within_budget and not reasons:
        # Every need can be met by some variant, just not by the same one
        conflicts = [
            f"No variant {where} has both {pa} and {pb}."
            for (ka, pa), (kb, pb) in combinations(requirements, 2)
            if not any(passes(v, ka) and passes(v, kb) for v in scope)
        ][:3]
        reasons.extend(conflicts)
        if not conflicts:
            reasons.append(f"Each of your needs can be met by some variant {where}, but no single variant meets them all together.")

    # Closest: fewest needs missed; then the smallest budget overrun; then the most car for the money
    def closeness(v: Variant):
        er = by_key[v.variant_key]
        total = budget_cost(v, needs)
        overrun = max(0, total - needs.budget_max_inr) if total is not None else 0
        return (len(_failed_requirements(er)), overrun, -(v.price_inr or 0), v.variant_key)

    closest = min(pool, key=closeness)
    er = by_key[closest.variant_key]
    slot = Slot(
        slot="not_recommended",
        variant_key=closest.variant_key,
        match_score=0,
        confidence="",
        price_inr=closest.price_inr or 0,
        price_status=closest.price_status,
        metrics={"brand": closest.brand, "model": closest.model, "variant": closest.variant, "seats": closest.seats},
        reasons=[ReasonCode(code="excluded", detail=r) for r in er.fail_reasons],
        tradeoffs=[],
        watch_outs=[],
    )
    return NoMatch(
        reasons=reasons,
        closest_variant_key=closest.variant_key,
        what_it_would_take=_what_it_takes(closest, er, needs),
    ), slot
