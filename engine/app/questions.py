"""POST /next_question: which easy follow-up to ask next. Pure and deterministic; no LLM.

  * Required fields (budget, seats, daily km, home charging) are asked first, one at a time, always in this order.
  * After that, an optional question is asked only if its answer would materially change the shortlist, found by
    re-running the engine over the plausible answers. At most MAX_OPTIONAL are asked.
  * Question text, answer cards and helpers are fixed templates written here. Nothing the buyer typed reaches this module.
  * "Not sure" is never turned into yes or no: it patches `unsure` (home charging) or nothing at all.
"""
from __future__ import annotations

from typing import Any

from .eligibility import check_all
from .models import Needs, Variant
from .scoring import rank_variants

REQUIRED_ORDER = ["budget_max_inr", "seats_min", "daily_km", "home_charging"]
GATE_FIELDS = ["budget_max_inr", "seats_min", "daily_km"]  # results unlock once these are known
OPTIONAL_ORDER = ["road_conditions", "priority", "longest_regular_trip_km"]
MAX_OPTIONAL = 3
TOP_N = 3
MATERIAL_SCORE = 1.5  # a different best match alone counts; otherwise 2 of the top 3 must differ

_TRIP_CHOICES = [None, 150, 300, 500]
_CANDIDATES: dict[str, list[Any]] = {
    "road_conditions": ["city_highway", "rough_roads", "light_offroad"],
    "priority": ["balanced", "safety", "cost", "range", "features", "space"],
    "longest_regular_trip_km": _TRIP_CHOICES,
}


def _card(card_id: str, label: str, sublabel: str | None = None, **patch: Any) -> dict[str, Any]:
    return {"id": card_id, "label": label, "sublabel": sublabel, "patch": patch}


TEMPLATES: dict[str, dict[str, Any]] = {
    "budget_max_inr": {
        "question": "What is the most you want to spend on the car?",
        "why": "So we never show a car you cannot afford.",
        "example": "For example, 12 lakh.",
        "helper": "budget_emi",
        "cards": [
            _card("b10", "Up to 10 lakh", budget_max_inr=1_000_000),
            _card("b15", "10 to 15 lakh", "We will look up to 15 lakh", budget_max_inr=1_500_000),
            _card("b20", "15 to 20 lakh", "We will look up to 20 lakh", budget_max_inr=2_000_000),
            _card("b30", "20 to 30 lakh", "We will look up to 30 lakh", budget_max_inr=3_000_000),
            _card("b50", "More than 30 lakh", "We will look up to 50 lakh", budget_max_inr=5_000_000),
        ],
    },
    "seats_min": {
        "question": "Who rides with you on most days?",
        "why": "So the car has enough seats for the people you actually carry.",
        "example": "For example, my wife and two kids.",
        "helper": None,
        "cards": [
            _card("s2", "Just me, or me and my partner", "2 seats is enough", seats_min=2),
            _card("s4", "A small family", "Up to 4 people", seats_min=4),
            _card("s5", "Family with parents", "5 people", seats_min=5),
            _card("s7", "A big family", "6 or 7 people", seats_min=7),
        ],
    },
    "daily_km": {
        "question": "How far do you drive on a normal day?",
        "why": "So the battery comfortably covers your day without charging every night.",
        "example": "For example, my office is 15 km from home.",
        "helper": "commute_minutes",
        "cards": [
            _card("d20", "Office is up to 10 km away", "About 20 km a day, there and back", daily_km=20),
            _card("d40", "Office is 10 to 20 km away", "About 40 km a day, there and back", daily_km=40),
            _card("d70", "Office is 20 to 35 km away", "About 70 km a day, there and back", daily_km=70),
            _card("d150", "I drive all day", "Cab, sales or delivery: about 150 km a day", daily_km=150),
            _card("d15", "Only short local trips", "About 15 km a day", daily_km=15),
        ],
    },
    "home_charging": {
        "question": "Where will the car sleep at night?",
        "why": "An electric car is cheapest and easiest to charge at home, so this changes which cars suit you.",
        "example": "For example, I have my own parking in a society.",
        "helper": None,
        "cards": [
            _card("h_house", "My own house with parking", "I can fit a charger", home_charging="yes"),
            _card("h_flat", "Apartment with my own spot", "I would need the society's permission", home_charging="unsure"),
            _card("h_street", "Shared or street parking", "I cannot fit a charger", home_charging="no"),
            _card("h_unsure", "I am not sure", "Costs will assume a home charger, and say so", home_charging="unsure"),
        ],
    },
    "road_conditions": {
        "question": "What are the roads like where you drive?",
        "why": "Bumpy roads suit cars that sit higher off the ground.",
        "example": "For example, lots of potholes near my home.",
        "helper": None,
        "cards": [
            _card("r_city", "Smooth city and highway roads", road_conditions="city_highway"),
            _card("r_rough", "Potholes and speed breakers", "Broken roads most days", road_conditions="rough_roads"),
            _card("r_off", "Hills, gravel or village tracks", "Not serious off-roading", road_conditions="light_offroad"),
            _card("r_skip", "Not sure", "We will assume normal roads"),
        ],
    },
    "priority": {
        "question": "What worries you most about the car?",
        "why": "So we put the cars that do best on that first.",
        "example": "For example, keeping my family safe.",
        "helper": None,
        "cards": [
            _card("p_safety", "Keeping my family safe", priority="safety"),
            _card("p_cost", "Low running cost", priority="cost"),
            _card("p_range", "Going far without charging", priority="range"),
            _card("p_features", "A premium, feature-rich car", priority="features"),
            _card("p_space", "Space and comfort", priority="space"),
            _card("p_balanced", "A bit of everything", priority="balanced"),
        ],
    },
    "longest_regular_trip_km": {
        "question": "Do you regularly take long trips?",
        "why": "A trip longer than your daily drive needs a bigger battery.",
        "example": "For example, a 250 km trip to my hometown every month.",
        "helper": None,
        "cards": [
            _card("t_none", "Never, or only once in a while", "No regular long trip"),
            _card("t150", "Every month, about 150 km one way", longest_regular_trip_km=150),
            _card("t300", "Every month, about 300 km one way", longest_regular_trip_km=300),
            _card("t500", "Every month, 500 km or more one way", longest_regular_trip_km=500),
        ],
    },
}


def missing_required(known: dict[str, Any]) -> list[str]:
    return [f for f in REQUIRED_ORDER if f not in known]


def _build_needs(known: dict[str, Any], **override: Any) -> Needs:
    """Needs for ranking only: unknown required fields never reach the buyer's result, so this is used just to see how a
    choice moves the shortlist. Only called once the gate fields are known."""
    fields = {"home_charging": "unsure", **known, **override}
    return Needs(**{k: v for k, v in fields.items() if v is not None})


def _top(variants: list[Variant], needs: Needs) -> list[str]:
    ranked = rank_variants(variants, check_all(variants, needs), needs)
    return [rv.variant.variant_key for rv in ranked[:TOP_N]]


def change_score(a: list[str], b: list[str]) -> float:
    """How different two shortlists are: half the number of differing cars among the top 3, plus 1.5 if the best match differs."""
    differing = len(set(a) ^ set(b)) / 2
    return differing + (1.5 if (a[:1] != b[:1]) else 0.0)


def sensitivity(field: str, known: dict[str, Any], variants: list[Variant]) -> float:
    """The most the shortlist moves across the plausible answers to `field`. 0 = the answer makes no difference."""
    tops = [_top(variants, _build_needs(known, **{field: value})) for value in _CANDIDATES[field]]
    return max((change_score(a, b) for i, a in enumerate(tops) for b in tops[i + 1:]), default=0.0)


def _response(field: str | None, kind: str, known: dict[str, Any], missing: list[str]) -> dict[str, Any]:
    template = TEMPLATES[field] if field else None
    return {
        "done": kind == "none",
        "kind": kind,
        "field": field,
        "question": template["question"] if template else None,
        "why": template["why"] if template else None,
        "example": template["example"] if template else None,
        "cards": [dict(c, patch=dict(c["patch"])) for c in template["cards"]] if template else [],
        "helper": template["helper"] if template else None,
        "can_show_results": all(f in known for f in GATE_FIELDS),
        "missing_required": missing,
    }


def next_question(known: dict[str, Any], asked: list[str], variants: list[Variant]) -> dict[str, Any]:
    """The next follow-up for what is known so far. `asked` lists optional fields already asked or skipped."""
    missing = missing_required(known)
    if missing:
        return _response(missing[0], "required", known, missing)

    asked_optional = [f for f in asked if f in OPTIONAL_ORDER]
    if len(asked_optional) < MAX_OPTIONAL:
        scored = [
            (sensitivity(f, known, variants), -OPTIONAL_ORDER.index(f), f)
            for f in OPTIONAL_ORDER if f not in asked_optional and f not in known
        ]
        worthwhile = [s for s in scored if s[0] >= MATERIAL_SCORE]
        if worthwhile:
            best = max(worthwhile)
            return _response(best[2], "optional", known, [])
    return _response(None, "none", known, [])
