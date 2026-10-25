"""Per-component cost calculations. BaaS never gets a 5-year cost."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from .models import Needs, Variant


# Default tariffs from Assumptions tab
HOME_TARIFF = 8.0       # ₹/kWh
DC_TARIFF = 22.0        # ₹/kWh
DC_SHARE_HOME = 0.10    # 10% DC share when home charging available
DC_SHARE_NO_HOME = 0.90 # 90% DC share when no home charging
BLENDED_TARIFF_HOME = (1 - DC_SHARE_HOME) * HOME_TARIFF + DC_SHARE_HOME * DC_TARIFF      # 9.4
BLENDED_TARIFF_NO_HOME = (1 - DC_SHARE_NO_HOME) * HOME_TARIFF + DC_SHARE_NO_HOME * DC_TARIFF  # 20.6
OWNERSHIP_YEARS = 5


class CostBreakdown(BaseModel):
    price_inr: Optional[int] = None
    price_status: str
    charger_cost_inr: Optional[int] = None
    charger_note: str
    electricity_5yr_inr: Optional[int] = None
    running_cost_inr_per_km: Optional[float] = None
    blended_tariff: float = BLENDED_TARIFF_HOME
    tariff_basis: str = "90% home ₹8/kWh, 10% public DC ₹22/kWh"
    total_budget_cost_inr: Optional[int] = None
    cost_to_own_5yr_inr: Optional[int] = None
    cost_label: str = (
        "Estimated 5-year vehicle + charging cost — "
        "excludes insurance, financing, maintenance and resale."
    )


def round_estimate(v: Optional[int]) -> Optional[int]:
    """Estimates (electricity, 5-year cost) are rounded to the nearest ₹1,000."""
    return None if v is None else int(round(v / 1000.0)) * 1000


def charger_cost(variant: Variant, needs: Needs) -> int:
    """Wall-charger cost this buyer would pay: none if included or if they can't charge at home."""
    if variant.charger_included.startswith("Yes") or needs.home_charging == "no":
        return 0
    return variant.charger_cost_inr or 0


def budget_cost(variant: Variant, needs: Needs) -> Optional[int]:
    """Total cost for the budget check: price + wall charger when the budget includes it."""
    if variant.price_inr is None:
        return None
    if needs.budget_includes_charger:
        return variant.price_inr + charger_cost(variant, needs)
    return variant.price_inr


def compute_costs(variant: Variant, needs: Needs) -> CostBreakdown:
    """Compute separated cost components for a variant given buyer needs."""

    # --- Charger note ---
    effective_charger = charger_cost(variant, needs)
    if variant.charger_included.startswith("Yes"):
        charger_note = "Included"
    elif needs.home_charging == "no":
        charger_note = "Not needed (no home charging)"
    elif variant.charger_included in ("Unclear", "Not stated"):
        charger_note = (
            f"~₹{effective_charger:,} assumed, not confirmed (see charger_basis)"
            if effective_charger else "Not confirmed"
        )
    else:  # "No"
        charger_note = (
            f"~₹{effective_charger:,} (not in price)"
            if effective_charger else "Cost unknown"
        )
    if needs.home_charging == "unsure" and effective_charger:
        charger_note += "; assumed home charger"

    # --- Budget cost (price + charger when applicable) ---
    total_budget = budget_cost(variant, needs)

    # --- Electricity (5yr) ---
    if needs.home_charging == "no":
        tariff = BLENDED_TARIFF_NO_HOME
        tariff_basis = "90% public DC ₹22/kWh, 10% home ₹8/kWh"
    else:
        tariff = BLENDED_TARIFF_HOME
        tariff_basis = "90% home ₹8/kWh, 10% public DC ₹22/kWh"
    electricity_5yr: Optional[int] = None
    running_per_km: Optional[float] = None
    if (
        variant.pricing_type != "BaaS"
        and variant.efficiency_km_per_kwh is not None
        and variant.efficiency_km_per_kwh > 0
    ):
        running_per_km = round(tariff / variant.efficiency_km_per_kwh, 2)
        daily_kwh = needs.daily_km / variant.efficiency_km_per_kwh
        electricity_5yr = round(daily_kwh * tariff * 365 * OWNERSHIP_YEARS)

    # --- 5-year cost (never for BaaS) ---
    cost_5yr: Optional[int] = None
    if variant.pricing_type != "BaaS" and variant.price_inr is not None and electricity_5yr is not None:
        cost_5yr = round_estimate(variant.price_inr + effective_charger + electricity_5yr)
    electricity_5yr = round_estimate(electricity_5yr)

    return CostBreakdown(
        price_inr=variant.price_inr,
        price_status=variant.price_status,
        charger_cost_inr=effective_charger if effective_charger else None,
        charger_note=charger_note,
        electricity_5yr_inr=electricity_5yr,
        running_cost_inr_per_km=running_per_km,
        blended_tariff=tariff,
        tariff_basis=tariff_basis,
        total_budget_cost_inr=total_budget,
        cost_to_own_5yr_inr=cost_5yr,
    )
