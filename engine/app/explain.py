"""Deterministic template sentences for reason and trade-off codes."""
from __future__ import annotations


def fmt_lakh(v: int | None) -> str:
    """Format rupees for buyers: ₹6.99 lakh, ₹2 lakh, or ₹60,000 below one lakh."""
    if v is None:
        return "price not confirmed"
    if abs(v) < 100_000:
        return f"₹{v:,}"
    lakh = v / 100_000
    if lakh == int(lakh):
        return f"₹{int(lakh)} lakh"
    return f"₹{lakh:.2f} lakh"


def fmt_ncap(score: float | None, out_of: int = 32) -> str:
    """NCAP score exactly as published: 31.09/32, 32/32 (never rounded)."""
    return f"{score:g}/{out_of}" if score is not None else "not stated"


# ---------------------------------------------------------------------------
# Reason codes (why a slot was picked)
# ---------------------------------------------------------------------------

REASON_TEMPLATES: dict[str, str] = {
    "lowest_cost": "Lowest estimated 5-year cost in your budget.",
    "best_range": "Best real-world range among eligible options.",
    "safest": "Highest crash-test score with ADAS.",
    "only_option": "The only vehicle meeting all your requirements.",
    "cheapest_eligible": "Cheapest option that meets all your needs.",
    "different_model_choice": "A competitive alternative from a different brand/model.",
    "best_dc_charging": "Best DC fast-charging speed for public charging.",
    "best_fit_score": "Strongest overall fit for your stated needs.",
}

# ---------------------------------------------------------------------------
# Trade-off codes (what you give up or should know)
# ---------------------------------------------------------------------------

TRADEOFF_TEMPLATES: dict[str, str] = {
    "no_adas": "Does not have ADAS.",
    "no_crash_test": "No Bharat NCAP crash test for this EV.",
    "crash_unconfirmed": "Crash rating may not cover this version.",
    "esp_not_listed": "ESP not listed by maker.",
    "slow_dc": "Slow DC fast-charging.",
    "charger_not_included": "Wall charger not in price (~₹{cost:,}).",
    "nice_to_have_unmet": "None of the options in your budget is confirmed to have {feature}.",
    "price_corroborated": "Price corroborated, confirm before buying.",
    "price_pending": "Price not yet confirmed.",
    "baas_warning": "BaaS: battery paid via separate loan.",
    "range_only_claimed": "No independent range test; only maker claim available.",
    "suspension_unknown": "Adaptive suspension evidence is limited.",
    "ground_clearance_unknown": "Ground clearance not stated by maker.",
    "feature_not_stated": "{feature} not stated by maker — verify before buying.",
    "saves_money": "Saves ₹{amount:,} vs the top pick; see what you give up below.",
    "no_qualifying_vehicle": "None of the vehicles in our current dataset meet all your requirements.",
}


def render_reason(code: str, **kwargs) -> str:
    """Render a reason code into a human-readable sentence."""
    template = REASON_TEMPLATES.get(code, code)
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template


def render_tradeoff(code: str, **kwargs) -> str:
    """Render a trade-off code into a human-readable sentence."""
    template = TRADEOFF_TEMPLATES.get(code, code)
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template


def variant_tradeoffs(variant) -> list[dict[str, str]]:
    """Generate trade-off codes from a Variant's data."""
    codes: list[dict[str, str]] = []

    if variant.adas == "None":
        codes.append({"code": "no_adas", "detail": render_tradeoff("no_adas")})
    if variant.ncap_status == "Not tested":
        codes.append({"code": "no_crash_test", "detail": render_tradeoff("no_crash_test")})
    if variant.ncap_status == "Rated, coverage unconfirmed":
        codes.append({"code": "crash_unconfirmed", "detail": render_tradeoff("crash_unconfirmed")})
    if variant.esp != "Yes":
        codes.append({"code": "esp_not_listed", "detail": render_tradeoff("esp_not_listed")})
    if variant.dc_avg_kw_est and variant.dc_avg_kw_est < 40:
        codes.append({"code": "slow_dc", "detail": render_tradeoff("slow_dc")})
    if not variant.charger_included.startswith("Yes") and variant.pricing_type != "BaaS":
        cost = variant.charger_cost_inr or 0
        codes.append({
            "code": "charger_not_included",
            "detail": render_tradeoff("charger_not_included", cost=cost),
        })
    if variant.price_status == "corroborated":
        codes.append({"code": "price_corroborated", "detail": render_tradeoff("price_corroborated")})
    if variant.price_status == "pending":
        codes.append({"code": "price_pending", "detail": render_tradeoff("price_pending")})
    if variant.pricing_type == "BaaS":
        codes.append({"code": "baas_warning", "detail": render_tradeoff("baas_warning")})
    if variant.range_tested_km is None and variant.efficiency_basis != "Independent test":
        codes.append({"code": "range_only_claimed", "detail": render_tradeoff("range_only_claimed")})
    if variant.adaptive_suspension == "Not stated":
        codes.append({"code": "suspension_unknown", "detail": render_tradeoff("suspension_unknown")})
    if variant.ground_clearance_mm is None:
        codes.append({
            "code": "ground_clearance_unknown",
            "detail": render_tradeoff("ground_clearance_unknown"),
        })

    return codes
