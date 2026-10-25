"""Per-component cost calculations. BaaS never gets a 5-year cost."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from .models import Needs, Variant


# Default tariffs from Assumptions tab
HOME_TARIFF = 8.0       # ₹/kWh
DC_TARIFF = 22.0        # ₹/kWh
DC_SHARE = 0.10         # 10% of charging on public DC
BLENDED_TARIFF = (1 - DC_SHARE) * HOME_TARIFF + DC_SHARE * DC_TARIFF  # 9.4
OWNERSHIP_YEARS = 5


class CostBreakdown(BaseModel):
    price_inr: Optional[int] = None
    price_status: str
    charger_cost_inr: Optional[int] = None
    charger_note: str
    electricity_5yr_inr: Optional[int] = None
    blended_tariff: float = BLENDED_TARIFF
    total_budget_cost_inr: Optional[int] = None
    cost_to_own_5yr_inr: Optional[int] = None
    cost_label: str = (
        "Estimated 5-year vehicle + charging cost — "
        "excludes insurance, financing, maintenance and resale."
    )


def compute_costs(variant: Variant, needs: Needs) -> CostBreakdown:
    """Compute separated cost components for a variant given buyer needs."""

    # --- Charger note ---
    if variant.charger_included.startswith("Yes"):
        charger_note = "Included"
        effective_charger = 0
    elif variant.charger_included in ("Unclear", "Not stated"):
        effective_charger = variant.charger_cost_inr or 0
        charger_note = (
            f"~₹{effective_charger:,} assumed, not confirmed (see charger_basis)"
            if effective_charger else "Not confirmed"
        )
    else:  # "No"
        effective_charger = variant.charger_cost_inr or 0
        charger_note = (
            f"~₹{effective_charger:,} (not in price)"
            if effective_charger else "Cost unknown"
        )

    # --- Budget cost (price + charger when applicable) ---
    if variant.price_inr is not None:
        if needs.budget_includes_charger and not variant.charger_included.startswith("Yes"):
            total_budget = variant.price_inr + effective_charger
        else:
            total_budget = variant.price_inr
    else:
        total_budget = None

    # --- Electricity (5yr) ---
    electricity_5yr: Optional[int] = None
    if (
        variant.pricing_type != "BaaS"
        and variant.efficiency_km_per_kwh is not None
        and variant.efficiency_km_per_kwh > 0
    ):
        daily_kwh = needs.daily_km / variant.efficiency_km_per_kwh
        electricity_5yr = round(daily_kwh * BLENDED_TARIFF * 365 * OWNERSHIP_YEARS)

    # --- 5-year cost (never for BaaS) ---
    cost_5yr: Optional[int] = None
    if variant.pricing_type != "BaaS" and variant.price_inr is not None and electricity_5yr is not None:
        cost_5yr = variant.price_inr + effective_charger + electricity_5yr

    return CostBreakdown(
        price_inr=variant.price_inr,
        price_status=variant.price_status,
        charger_cost_inr=effective_charger if effective_charger else None,
        charger_note=charger_note,
        electricity_5yr_inr=electricity_5yr,
        total_budget_cost_inr=total_budget,
        cost_to_own_5yr_inr=cost_5yr,
    )
