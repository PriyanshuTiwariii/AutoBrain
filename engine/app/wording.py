"""Plain-language feature wording, ordered by relevance to the buyer.

Used for ladder gains ("what the top pick adds"), factory-only gains and
"what this car lacks" comparisons. Nothing here is specific to a car.
"""
from __future__ import annotations

from typing import Optional

from .models import FeatureEnum, Needs

# Relevance groups, in default order (most relevant first)
DEFAULT_GROUP_ORDER = [
    "safety", "range", "warranty", "capability", "charging",
    "comfort", "space", "convenience", "infotainment",
]

PRIORITY_GROUPS: dict[str, list[str]] = {
    "balanced": ["safety", "range"],
    "safety": ["safety"],
    "range": ["range", "charging"],
    "cost": ["warranty"],
    "features": ["comfort", "convenience", "capability"],
    "space": ["space", "comfort"],
}

# Ladder field → (relevance group, Needs feature it maps to)
LADDER_FIELDS: dict[str, tuple[str, Optional[FeatureEnum]]] = {
    "ADAS": ("safety", FeatureEnum.adas),
    "Airbags": ("safety", None),
    "ESP": ("safety", FeatureEnum.esp),
    "Crash test": ("safety", FeatureEnum.crash_tested),
    "Battery kWh": ("range", None),
    "Range km": ("range", None),
    "Battery warranty": ("warranty", FeatureEnum.lifetime_battery_warranty),
    "Drive": ("capability", FeatureEnum.awd),
    "Terrain modes": ("capability", None),
    "Adaptive suspension": ("capability", FeatureEnum.adaptive_suspension),
    "Charger in box": ("charging", FeatureEnum.charger_included),
    "Vent. seats": ("comfort", FeatureEnum.ventilated_seats),
    "Sunroof": ("comfort", FeatureEnum.sunroof),
    "Climate": ("comfort", None),
    "Upholstery": ("comfort", None),
    "Powered seat": ("comfort", None),
    "Seats": ("space", FeatureEnum.seven_seats),
    "Camera": ("convenience", FeatureEnum.camera_360),
    "Cruise": ("convenience", None),
    "Keyless": ("convenience", None),
    "Power tailgate": ("convenience", None),
    "Auto park": ("convenience", None),
    "HUD": ("convenience", None),
    "Wireless charger": ("convenience", None),
    "Audio": ("infotainment", None),
    "Screens": ("infotainment", None),
    "Wheels": ("infotainment", None),
    "App suite": ("infotainment", None),
}

# Needs feature → relevance group (for "what this car lacks" comparisons)
FEATURE_GROUPS: dict[FeatureEnum, str] = {
    FeatureEnum.adas: "safety",
    FeatureEnum.esp: "safety",
    FeatureEnum.crash_tested: "safety",
    FeatureEnum.lifetime_battery_warranty: "warranty",
    FeatureEnum.awd: "capability",
    FeatureEnum.adaptive_suspension: "capability",
    FeatureEnum.charger_included: "charging",
    FeatureEnum.ventilated_seats: "comfort",
    FeatureEnum.sunroof: "comfort",
    FeatureEnum.seven_seats: "space",
    FeatureEnum.camera_360: "convenience",
}

_NO_VALUE = ("not stated", "not listed", "none", "none listed", "no", "—", "-", "")

# Short nouns for factory-only lists
_FIELD_NOUNS: dict[str, str] = {
    "Battery kWh": "bigger battery",
    "Range km": "more range",
    "Vent. seats": "ventilated seats",
    "Drive": "all-wheel drive",
    "Terrain modes": "terrain modes",
    "Crash test": "crash-test coverage",
    "HUD": "head-up display",
}


def lower_first(s: str) -> str:
    """'Leatherette' → 'leatherette', but keep acronyms: 'ADAS' stays 'ADAS'."""
    return s if s[:2].isupper() else s[:1].lower() + s[1:]


def relevance_key(group: str, feature: Optional[FeatureEnum], needs: Needs, index: int = 0) -> tuple:
    """Sort key: range and charging first without home charging, then the buyer's
    stated must-haves and nice-to-haves, then their priority, then the default order."""
    if needs.home_charging == "no" and group in ("range", "charging"):
        tier = 0
    elif feature is not None and (feature in needs.must_haves or feature in needs.nice_to_haves):
        tier = 1
    elif group in PRIORITY_GROUPS.get(needs.priority.value, []):
        tier = 2
    else:
        tier = 3
    return (tier, DEFAULT_GROUP_ORDER.index(group), index)


def _is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def _yes_detail(after: str) -> str:
    """'yes (6-way powered, memory)' → '6-way powered, memory'."""
    return after[3:].strip(" ()") if after.lower().startswith("yes") else ""


def _with_detail(base: str, detail: str) -> str:
    return f"{base} ({detail})" if detail else base


def ladder_phrase(field: str, before: str, after: str) -> Optional[str]:
    """One ladder change in plain words, or None when it is not a gain the buyer can count on."""
    low = after.lower()
    if low in _NO_VALUE or low.startswith("not stated"):
        return None
    if _is_number(before) and _is_number(after):
        if float(after) <= float(before):
            return None  # a decrease is not a gain
        if field == "Battery kWh":
            return f"bigger battery ({before} → {after} kWh)"
        if field == "Range km":
            return f"more claimed range ({before} → {after} km)"
        if field == "Airbags":
            return f"{after} airbags instead of {before}"
        if field == "Seats":
            return f"{after} seats"
        return f"more {field.lower()} ({before} → {after})"
    detail = _yes_detail(after)
    if field == "ADAS":
        return f"ADAS driver assistance ({after})"
    if field == "Camera":
        return "rear camera" if low == "rear camera" else f"{after} camera"
    if field == "Sunroof":
        return "sunroof" if low == "sunroof" else f"{low} sunroof"
    if field == "Vent. seats":
        return "ventilated front seats"
    if field == "Upholstery":
        return f"{lower_first(after)} seats"
    if field == "Audio":
        return f"better sound system ({after})"
    if field == "Screens":
        return f"bigger screens ({after})"
    if field == "Wheels":
        return f"upgraded wheels ({after})"
    if field == "Climate":
        return f"better climate control ({after})"
    if field == "Powered seat":
        return _with_detail("powered driver seat", detail)
    if field == "Wireless charger":
        return "wireless phone charger"
    if field == "Power tailgate":
        return _with_detail("powered tailgate", detail)
    if field == "App suite":
        return f"connected-car apps ({after})"
    if field == "Keyless":
        return _with_detail("keyless entry", detail)
    if field == "Cruise":
        return "adaptive cruise control" if low == "adaptive" else "cruise control"
    if field == "Auto park":
        return "automatic parking"
    if field == "HUD":
        return _with_detail("head-up display", detail)
    if field == "Adaptive suspension":
        return "adaptive suspension"
    if field == "Drive":
        return "all-wheel drive" if low == "awd" else f"{after} drive"
    if field == "Battery warranty":
        return "lifetime battery warranty (first owner)" if low.startswith("lifetime") else f"battery warranty: {after}"
    if field == "ESP":
        return "ESP (stability control)"
    if field == "Charger in box":
        return _with_detail("wall charger included", detail)
    if field == "Crash test":
        return "Bharat NCAP rating that covers this version" if low == "rated, applies" else None
    return f"better {field.lower()} ({after})"


def parse_ladder(what_you_gain: str) -> list[tuple[str, str, str]]:
    """'Field: before → after; …' → [(field, before, after), …]. Items without an arrow keep
    their text as the field, with empty before/after."""
    changes: list[tuple[str, str, str]] = []
    for item in what_you_gain.split(";"):
        item = item.strip()
        if ":" in item and "→" in item:
            field, change = (p.strip() for p in item.split(":", 1))
            before, after = (p.strip() for p in change.split("→", 1))
            changes.append((field, before, after))
        elif item:
            changes.append((item, "", ""))
    return changes


def ladder_gains(changes: list[tuple[str, str, str]], needs: Needs, limit: Optional[int] = None) -> list[str]:
    """Plain-language gains ordered by relevance to the buyer, at most `limit`."""
    scored: list[tuple[tuple, str]] = []
    for i, (field, before, after) in enumerate(changes):
        group, feature = LADDER_FIELDS.get(field, ("infotainment", None))
        if field == "Charger in box" and needs.home_charging == "no":
            continue  # a wall charger is no use without home charging
        phrase = ladder_phrase(field, before, after) if after or before else field.lower()
        if phrase:
            scored.append((relevance_key(group, feature, needs, i), phrase))
    scored.sort(key=lambda x: x[0])
    phrases = [p for _, p in scored]
    return phrases[:limit] if limit else phrases


def factory_only_nouns(factory_only_gains: Optional[str], needs: Needs) -> list[str]:
    if not factory_only_gains:
        return []
    fields = [f.strip() for f in factory_only_gains.split("|") if f.strip()]
    keyed = []
    for i, f in enumerate(fields):
        group, feature = LADDER_FIELDS.get(f, ("infotainment", None))
        keyed.append((relevance_key(group, feature, needs, i), _FIELD_NOUNS.get(f, lower_first(f))))
    keyed.sort(key=lambda x: x[0])
    return [n for _, n in keyed]


def join_list(items: list[str]) -> str:
    """['a'] → 'a'; ['a', 'b'] → 'a and b'; ['a', 'b', 'c'] → 'a, b and c'."""
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]
