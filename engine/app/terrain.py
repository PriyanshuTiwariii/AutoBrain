"""Rough-road and light off-road fit: pure functions on stated data. Blank or "Not stated" is unknown, never a yes or a no."""
from __future__ import annotations

from .models import Variant

GOOD_CLEARANCE_MM = 200  # at or above: full credit
OK_CLEARANCE_MM = 180    # at or above: partial credit

_USE_TEXT = {"rough_roads": "rough roads", "light_offroad": "light off-road driving"}


def is_rough(road_conditions: str) -> bool:
    return road_conditions in _USE_TEXT


def _clearance_points(mm: int | None, full: float, partial: float) -> float:
    if mm is None:
        return 0.0
    if mm >= GOOD_CLEARANCE_MM:
        return full
    return partial if mm >= OK_CLEARANCE_MM else 0.0


def terrain_score(v: Variant, road_conditions: str) -> float:
    """0-25. Credit only for what the maker states; an unstated figure earns nothing."""
    if road_conditions == "rough_roads":
        return (
            _clearance_points(v.ground_clearance_mm, 15.0, 9.0)
            + _clearance_points(v.battery_clearance_mm, 5.0, 3.0)
            + (5.0 if v.adaptive_suspension == "Yes" else 0.0)
        )
    if road_conditions == "light_offroad":
        return (
            _clearance_points(v.ground_clearance_mm, 10.0, 6.0)
            + _clearance_points(v.battery_clearance_mm, 5.0, 3.0)
            + (10.0 if v.drive == "AWD" else 0.0)
        )
    return 0.0


def terrain_tradeoffs(v: Variant, road_conditions: str) -> list[dict[str, str]]:
    """What the buyer should know about this variant for the road they described."""
    use = _USE_TEXT.get(road_conditions)
    if use is None:
        return []
    out: list[dict[str, str]] = []
    mm = v.ground_clearance_mm
    if mm is None:
        out.append({"code": "ground_clearance_unknown", "detail": "Ground clearance not stated by maker."})
    elif mm < GOOD_CLEARANCE_MM:
        out.append({"code": "low_ground_clearance", "detail": f"Ground clearance {mm} mm is on the low side for {use}."})
    if v.battery_clearance_mm is None:
        out.append({"code": "battery_clearance_unknown", "detail": "Clearance under the battery pack not stated by maker."})
    elif v.battery_clearance_mm < GOOD_CLEARANCE_MM:
        out.append({
            "code": "low_battery_clearance",
            "detail": f"Clearance under the battery pack is {v.battery_clearance_mm} mm, on the low side for {use}.",
        })
    if road_conditions == "light_offroad":
        if v.drive in ("FWD", "RWD"):
            kind = "Front-wheel" if v.drive == "FWD" else "Rear-wheel"
            out.append({"code": "no_awd", "detail": f"{kind} drive only: less grip on loose surfaces than all-wheel drive."})
        elif v.drive != "AWD":
            out.append({"code": "drive_unknown", "detail": "Drive type not stated by maker."})
    return out


def terrain_reasons(v: Variant, road_conditions: str) -> list[dict[str, str]]:
    """Stated strengths for the road they described."""
    use = _USE_TEXT.get(road_conditions)
    if use is None:
        return []
    out: list[dict[str, str]] = []
    if v.ground_clearance_mm is not None and v.ground_clearance_mm >= GOOD_CLEARANCE_MM:
        out.append({"code": "good_ground_clearance", "detail": f"Ground clearance {v.ground_clearance_mm} mm, stated by the maker."})
    if road_conditions == "light_offroad" and v.drive == "AWD":
        out.append({"code": "has_awd", "detail": "All-wheel drive."})
    if road_conditions == "rough_roads" and v.adaptive_suspension == "Yes":
        out.append({"code": "has_adaptive_suspension", "detail": "Adaptive suspension."})
    return out


NOT_OFFROAD_NOTE = (
    "Light off-road here means gravel, dirt tracks and broken roads. No EV in our data is rated for serious off-roading."
)
