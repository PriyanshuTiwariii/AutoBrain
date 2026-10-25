"""Pydantic models matching contracts/needs.schema.json and contracts/result.schema.json."""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Feature / priority enums
# ---------------------------------------------------------------------------

class FeatureEnum(str, Enum):
    adas = "adas"
    camera_360 = "camera_360"
    sunroof = "sunroof"
    ventilated_seats = "ventilated_seats"
    esp = "esp"
    awd = "awd"
    seven_seats = "seven_seats"
    lifetime_battery_warranty = "lifetime_battery_warranty"
    crash_tested = "crash_tested"
    charger_included = "charger_included"
    adaptive_suspension = "adaptive_suspension"


class PriorityEnum(str, Enum):
    balanced = "balanced"
    safety = "safety"
    cost = "cost"
    range = "range"
    features = "features"
    space = "space"


class PricingPrefEnum(str, Enum):
    buy = "buy"
    baas = "baas"
    either = "either"


class HomeChargingEnum(str, Enum):
    yes = "yes"
    no = "no"
    unsure = "unsure"


class BodyTypeEnum(str, Enum):
    hatchback = "Hatchback"
    sedan = "Sedan"
    suv = "SUV"
    suv_coupe = "SUV coupé"


# ---------------------------------------------------------------------------
# Needs (engine input) — matches contracts/needs.schema.json
# ---------------------------------------------------------------------------

class Needs(BaseModel):
    budget_max_inr: int = Field(ge=300000)
    budget_includes_charger: bool = True
    seats_min: int = Field(ge=2, le=7)
    daily_km: int = Field(ge=1, le=500)
    longest_regular_trip_km: Optional[int] = Field(default=None, ge=1)
    home_charging: HomeChargingEnum
    city: Optional[str] = None
    body_types: list[BodyTypeEnum] = Field(default_factory=list)
    must_haves: list[FeatureEnum] = Field(default_factory=list)
    nice_to_haves: list[FeatureEnum] = Field(default_factory=list)
    priority: PriorityEnum = PriorityEnum.balanced
    pricing_pref: PricingPrefEnum = PricingPrefEnum.buy
    exclude_models: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Data models — loaded from CSVs
# ---------------------------------------------------------------------------

class Variant(BaseModel):
    variant_key: str
    sheet_id: str
    brand: str
    model: str
    body_type: str
    variant: str
    pricing_type: str
    price_inr: Optional[int] = None
    price_status: str
    battery_kwh: float
    drive: str
    seats: Optional[int] = None
    seat_options: str
    range_claimed_km: Optional[int] = None
    range_standard: Optional[str] = None
    range_maker_realworld_km: Optional[float] = None
    range_tested_km: Optional[int] = None
    range_test_vehicle: Literal["Same model", "Earlier version", "Not tested"]
    range_test_note: Optional[str] = None
    tested_vs_claim_pct: Optional[int] = None
    efficiency_km_per_kwh: Optional[float] = None
    efficiency_basis: str
    charger_included: str
    charger_cost_inr: Optional[int] = None
    charger_basis: Optional[str] = None
    boot_l: Optional[int] = None
    ground_clearance_mm: Optional[int] = None
    battery_clearance_mm: Optional[int] = None
    airbags: Optional[int] = None
    esp: str
    adas: str
    camera: str
    sunroof: str
    ventilated_front: str
    adaptive_suspension: str
    dc_max_kw: Optional[int] = None
    dc_avg_kw_est: Optional[float] = None
    ac_full_hours_7kw: Optional[float] = None
    onboard_ac_kw: Optional[float] = None
    battery_warranty: str
    ncap_status: str
    ncap_adult_32: Optional[float] = None
    ncap_child_49: Optional[float] = None
    terrain_modes: Optional[int] = None
    wading_mm: Optional[int] = None
    watch_outs: str
    running_cost_inr_per_km_default: Optional[float] = None
    cost_to_own_5yr_default: Optional[int] = None
    minutes_dc_per_100km_default: Optional[int] = None


class LadderStep(BaseModel):
    ladder_key: str
    model: str
    from_variant_key: str
    to_variant_key: str
    from_variant: str
    to_variant: str
    from_price_inr: Optional[int] = None
    to_price_inr: Optional[int] = None
    extra_cost_inr: Optional[int] = None
    what_you_gain: str
    factory_only_gains: Optional[str] = None
    note: Optional[str] = None
    price_status_from: Optional[str] = None
    price_status_to: Optional[str] = None


class Accessory(BaseModel):
    accessory_key: str
    brand: str
    model: str
    accessory: str
    category: Optional[str] = None
    applies_to: Optional[str] = None
    substitutes_factory_feature: Optional[str] = None
    equivalence: Optional[str] = None
    equivalence_basis: Optional[str] = None
    price_inr: Optional[int] = None
    price_source: Optional[str] = None
    price_status: Optional[str] = None
    installation: Optional[str] = None
    warranty_safe: Optional[str] = None
    usable_as_gap_filler: str = "no"
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Result (engine output) — matches contracts/result.schema.json
# ---------------------------------------------------------------------------

class ReasonCode(BaseModel):
    code: str
    detail: Optional[str] = None

    model_config = {"extra": "allow"}


class Slot(BaseModel):
    slot: Literal[
        "best_match", "strong_alternative", "same_model", "in_between",
        "dont_overpay", "not_recommended",
    ]
    variant_key: str
    match_score: int = Field(ge=0, le=100)
    confidence: Literal["High", "Medium", "Low", ""]
    price_inr: int
    price_status: Literal["verified", "corroborated", "pending"]
    metrics: dict[str, Any] = Field(default_factory=dict)
    reasons: list[ReasonCode] = Field(default_factory=list)
    tradeoffs: list[ReasonCode] = Field(default_factory=list)
    watch_outs: list[str] = Field(default_factory=list)
    savings_vs_best_inr: Optional[int] = None
    gap_filler_accessories: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class Result(BaseModel):
    result_id: str
    dataset_version: str
    engine_version: str
    needs_summary: list[str]
    slots: list[Slot]
    unknowns: list[str]
    disclaimer: str
