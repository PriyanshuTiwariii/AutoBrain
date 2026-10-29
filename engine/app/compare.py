"""POST /compare and GET /cars: two or three cars side by side. Pure and deterministic; no LLM.

Everything shown is read from the data release. Category winners follow fixed rules and are withheld, with the reason,
when the figures are not like for like (AGENTS.md):
  * a battery-rental (BaaS) price is never compared with a battery-included price;
  * a tested range is never compared with a maker's own figure, nor an independent efficiency test with a maker estimate;
  * a car with no stated figure never wins and never loses on it: it is shown as "Not stated by maker";
  * a petrol/diesel crash rating is never used (only Bharat NCAP ratings for these EVs);
  * there is no overall winner: the right car depends on what matters to the buyer.
"""
from __future__ import annotations

from typing import Any, Callable

from .costs import BLENDED_TARIFF_HOME, round_estimate
from .explain import fmt_lakh, fmt_ncap
from .models import Variant
from .slots import (
    DISCLAIMER, _dc_display, _efficiency_display, _is_earlier_version_test, _ncap_display, _range_display,
)
from .wording import join_list

NOT_STATED = "Not stated by maker"
MIN_CARS, MAX_CARS = 2, 3
_UNKNOWN_RAW = {None, "", "Not stated", "Not listed"}
_RATED = ("Rated, applies", "Rated, coverage unconfirmed")


class UnknownCars(Exception):
    def __init__(self, indexes: list[int]):
        self.indexes = indexes


def _name(v: Variant) -> str:
    return f"{v.model} {v.variant}"


def list_cars(variants: list[Variant], dataset_version: str) -> dict[str, Any]:
    return {
        "dataset_version": dataset_version,
        "cars": [
            {
                "variant_key": v.variant_key, "brand": v.brand, "model": v.model, "variant": v.variant,
                "body_type": v.body_type, "pricing_type": v.pricing_type, "price_inr": v.price_inr,
                "price_status": v.price_status,
            }
            for v in sorted(variants, key=lambda v: (v.brand, v.model, v.price_inr or 0, v.variant))
        ],
    }


# --- cells ------------------------------------------------------------------------------------------

def _cell(text: str, stated: bool = True) -> dict[str, Any]:
    return {"text": text, "state": "stated" if stated else "not_stated", "best": False}


def _unknown() -> dict[str, Any]:
    return _cell(NOT_STATED, stated=False)


def _raw_cell(raw: str | None, mapping: Callable[[str], str] = lambda s: s) -> dict[str, Any]:
    return _unknown() if raw in _UNKNOWN_RAW else _cell(mapping(raw))  # type: ignore[arg-type]


def _price(v: Variant) -> dict[str, Any]:
    if v.price_status == "pending" or v.price_inr is None:
        return _cell("Price not confirmed", stated=False)
    text = f"{fmt_lakh(v.price_inr)} ({v.price_status})"
    return _cell(text + "; battery rented separately" if v.pricing_type == "BaaS" else text)


def _cost_5yr(v: Variant) -> dict[str, Any]:
    if v.pricing_type == "BaaS":
        return _cell("Not calculated for battery rental", stated=False)
    if v.cost_to_own_5yr_default is None:
        return _unknown()
    return _cell(f"~{fmt_lakh(round_estimate(v.cost_to_own_5yr_default))} (default assumptions)")


def _charger(v: Variant) -> dict[str, Any]:
    cost = f"about {fmt_lakh(v.charger_cost_inr)}" if v.charger_cost_inr else None
    if v.charger_included.startswith("Yes"):
        return _cell(f"Included ({v.charger_included[5:-1]})")
    if v.charger_included == "No":
        return _cell(f"Not in the price, {cost} extra" if cost else "Not in the price")
    return _cell(f"Not confirmed by maker; {cost} assumed" if cost else NOT_STATED, stated=False)


def _range(v: Variant) -> dict[str, Any]:
    text = _range_display(v)
    return _unknown() if text == "not stated" else _cell(text)


def _or_unknown(text: str | None) -> dict[str, Any]:
    return _unknown() if not text else _cell(text)


_ADAS = {"L2": "Yes, Level 2", "L2+": "Yes, Level 2+", "None": "No"}
_VENTILATED = {"Yes": "Yes", "No": "No", "Passive only": "Passive cooling only"}


def _camera(raw: str) -> str:
    if raw.startswith(("360", "540")):
        return f"{raw[:3]} degree camera"
    return {"Rear camera": "Rear camera only", "Sensors only": "Parking sensors only"}.get(raw, raw)


_ROWS: list[tuple[str, list[tuple[str, str, Callable[[Variant], dict[str, Any]]]]]] = [
    ("Price and cost", [
        ("price", "Price (ex-showroom)", _price),
        ("pricing_type", "How the battery is sold", lambda v: _cell(
            "Battery rental (BaaS): price excludes the battery" if v.pricing_type == "BaaS" else "Battery included")),
        ("cost_5yr", "5-year cost to own", _cost_5yr),
        ("running_cost", "Running cost per km", lambda v: _or_unknown(
            f"₹{v.running_cost_inr_per_km_default:.2f}/km" if v.running_cost_inr_per_km_default else None)),
        ("charger", "Home wall charger", _charger),
    ]),
    ("Range and charging", [
        ("range", "Range", _range),
        ("efficiency", "Efficiency", lambda v: _or_unknown(_efficiency_display(v))),
        ("battery", "Battery size", lambda v: _cell(f"{v.battery_kwh:g} kWh")),
        ("dc", "DC fast charging", lambda v: _or_unknown(_dc_display(v))),
        ("warranty", "Battery warranty", lambda v: _raw_cell(v.battery_warranty)),
    ]),
    ("Safety", [
        ("ncap", "Crash test (adult)", lambda v: _unknown() if _ncap_display(v).startswith("Crash rating not") else _cell(_ncap_display(v))),
        ("airbags", "Airbags", lambda v: _or_unknown(str(v.airbags) if v.airbags is not None else None)),
        ("esp", "Stability control (ESP)", lambda v: _raw_cell(v.esp)),
        ("adas", "Driver assistance (ADAS)", lambda v: _raw_cell(v.adas, lambda s: _ADAS.get(s, s))),
        ("camera", "Parking camera", lambda v: _raw_cell(v.camera, _camera)),
    ]),
    ("Comfort and features", [
        ("sunroof", "Sunroof", lambda v: _raw_cell(v.sunroof, lambda s: "No" if s == "None" else s)),
        ("ventilated", "Ventilated front seats", lambda v: _raw_cell(v.ventilated_front, lambda s: _VENTILATED.get(s, s))),
        ("adaptive", "Adaptive suspension", lambda v: _raw_cell(v.adaptive_suspension)),
        ("drive", "Drive", lambda v: _raw_cell(v.drive)),
    ]),
    ("Space and ground", [
        ("seats", "Seats", lambda v: _or_unknown(str(v.seats) if v.seats is not None else None)),
        ("boot", "Boot", lambda v: _or_unknown(f"{v.boot_l} L" if v.boot_l is not None else None)),
        ("clearance", "Ground clearance", lambda v: _or_unknown(f"{v.ground_clearance_mm} mm" if v.ground_clearance_mm is not None else None)),
    ]),
]


# --- winners ----------------------------------------------------------------------------------------

def _withheld(category: str, label: str, text: str) -> dict[str, Any]:
    return {"category": category, "label": label, "variant_key": None, "text": text}


def _decide(
    category: str, label: str, cars: list[Variant], values: dict[str, float | None], higher: bool,
    say: Callable[[Variant, Variant, float], str], excluded_note: str = "not stated",
) -> dict[str, Any]:
    """The fair winner among cars that have a stated figure; a tie or fewer than two figures is withheld."""
    have = [c for c in cars if values.get(c.variant_key) is not None]
    left_out = [c for c in cars if c not in have]
    if len(have) < 2:
        return _withheld(category, label, "Not enough stated figures to compare these cars fairly on this.")
    best_value = (max if higher else min)(values[c.variant_key] for c in have)  # type: ignore[type-var]
    leaders = [c for c in have if values[c.variant_key] == best_value]
    if len(leaders) > 1:
        return _withheld(category, label, f"{join_list([_name(c) for c in leaders])} are level, so there is no single leader.")
    winner = leaders[0]
    others = sorted((c for c in have if c is not winner), key=lambda c: values[c.variant_key], reverse=higher)  # type: ignore[arg-type,return-value]
    text = say(winner, others[0], abs(best_value - values[others[0].variant_key]))  # type: ignore[operator]
    if left_out:
        text += f" ({join_list([_name(c) for c in left_out])}: {excluded_note}, so left out.)"
    return {"category": category, "label": label, "variant_key": winner.variant_key, "text": text}


def _range_basis(v: Variant) -> tuple[str, float] | None:
    if v.range_tested_km:
        return "independently tested", float(v.range_tested_km)
    if v.range_maker_realworld_km:
        return "the maker's own real-world figure", float(v.range_maker_realworld_km)
    return None


def _winners(cars: list[Variant]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    mixed_pricing = len({c.pricing_type for c in cars}) > 1
    any_baas = any(c.pricing_type == "BaaS" for c in cars)

    # price: only among cars sold the same way, and only confirmed prices
    if mixed_pricing:
        out.append(_withheld(
            "price", "Lowest price",
            "Some of these cars are sold with battery rental (BaaS) and some with the battery included. Their prices are not "
            "the same thing, so we do not compare them.",
        ))
    else:
        confirmed = {c.variant_key: float(c.price_inr) if c.price_status != "pending" and c.price_inr else None for c in cars}
        out.append(_decide(
            "price", "Lowest price", cars, confirmed, higher=False,
            say=lambda w, o, d: f"{_name(w)} has the lowest price at {fmt_lakh(w.price_inr)}, {fmt_lakh(int(d))} less than {_name(o)}.",
            excluded_note="price not confirmed",
        ))

    # 5-year cost: never for battery rental
    if any_baas:
        out.append(_withheld("cost_5yr", "Lowest 5-year cost", "A 5-year cost is never worked out for battery-rental (BaaS) cars, so it is not compared."))
    else:
        costs = {c.variant_key: float(round_estimate(c.cost_to_own_5yr_default)) if c.cost_to_own_5yr_default else None for c in cars}
        out.append(_decide(
            "cost_5yr", "Lowest 5-year cost", cars, costs, higher=False,
            say=lambda w, o, d: f"{_name(w)} has the lowest estimated 5-year cost, about {fmt_lakh(int(d))} less than {_name(o)} (default assumptions).",
        ))

    # range and efficiency: tested with tested, maker figure with maker figure, never across
    bases = {c.variant_key: _range_basis(c) for c in cars}
    tested = {k: b for k, b in bases.items() if b and b[0] == "independently tested"}
    maker = {k: b for k, b in bases.items() if b and b[0] != "independently tested"}
    group, kind, left = (tested, "independently tested", "only a maker figure, not comparable with a test") if len(tested) >= 2 else (
        maker, "the maker's own real-world figure", "independently tested, not comparable with a maker figure"
    )
    if len(group) < 2 and len(tested) and len(maker):
        out.append(_withheld(
            "range", "Longest range",
            "These ranges are not like for like: some are independently tested and some are the maker's own figure, so we do not pick a winner.",
        ))
    else:
        earlier = any(_is_earlier_version_test(c) for c in cars if c.variant_key in group) and kind == "independently tested"
        suffix = " One test was on an earlier version of that car." if earlier else ""
        out.append(_decide(
            "range", "Longest range", cars, {k: (b[1] if k in group else None) for k, b in bases.items()}, higher=True,
            say=lambda w, o, d: f"{_name(w)} goes furthest, {int(d)} km more than {_name(o)} ({kind}).{suffix}",
            excluded_note=left if len(tested) and len(maker) else "range not stated",
        ))

    tested_eff = {c.variant_key for c in cars if c.efficiency_km_per_kwh and c.efficiency_basis == "Independent test"}
    maker_eff = {c.variant_key for c in cars if c.efficiency_km_per_kwh and c.efficiency_basis != "Independent test"}
    eff_group, eff_kind = (tested_eff, "independent test") if len(tested_eff) >= 2 else (maker_eff, "maker estimate")
    if len(eff_group) < 2 and tested_eff and maker_eff:
        out.append(_withheld(
            "efficiency", "Most efficient",
            "These efficiency figures are not like for like: some are independent tests and some are maker estimates, so we do not pick a winner.",
        ))
    else:
        out.append(_decide(
            "efficiency", "Most efficient", cars,
            {c.variant_key: (c.efficiency_km_per_kwh if c.variant_key in eff_group else None) for c in cars}, higher=True,
            say=lambda w, o, d: f"{_name(w)} is the most efficient at {w.efficiency_km_per_kwh:g} km/kWh, {d:.2f} km/kWh more than {_name(o)} ({eff_kind}).",
            excluded_note="a different kind of figure, not comparable" if tested_eff and maker_eff else "efficiency not stated",
        ))

    # safety: Bharat NCAP adult score, only for rated cars
    rated = {c.variant_key: c.ncap_adult_32 if c.ncap_status in _RATED else None for c in cars}
    unrated = [c for c in cars if rated[c.variant_key] is None]
    safety = _decide(
        "safety", "Highest crash-test score", cars, rated, higher=True,
        say=lambda w, o, d: f"{_name(w)} has the higher Bharat NCAP adult score ({fmt_ncap(w.ncap_adult_32)} against {fmt_ncap(o.ncap_adult_32)} for {_name(o)}).",
        excluded_note="no Bharat NCAP rating",
    )
    if any(c.ncap_status == "Rated, coverage unconfirmed" for c in cars if rated[c.variant_key] is not None) and safety["variant_key"]:
        safety["text"] += " Some of these ratings were for a related version of the car and may not cover this exact one."
    if safety["variant_key"] is None and len(unrated) == len(cars) - 1:
        safety["text"] = "Only one of these cars has a Bharat NCAP rating, so crash safety cannot be compared fairly."
    out.append(safety)

    out.append(_decide(
        "dc_charging", "Fastest DC charging", cars, {c.variant_key: c.dc_avg_kw_est for c in cars}, higher=True,
        say=lambda w, o, d: f"{_name(w)} charges fastest on a DC fast charger, {w.dc_avg_kw_est:g} kW on average against {o.dc_avg_kw_est:g} kW for {_name(o)} (estimates).",
    ))
    out.append(_decide(
        "boot", "Biggest boot", cars, {c.variant_key: float(c.boot_l) if c.boot_l is not None else None for c in cars}, higher=True,
        say=lambda w, o, d: f"{_name(w)} has the biggest boot, {w.boot_l} L, {int(d)} L more than {_name(o)}.",
    ))
    out.append(_decide(
        "seats", "Most seats", cars, {c.variant_key: float(c.seats) if c.seats is not None else None for c in cars}, higher=True,
        say=lambda w, o, d: f"{_name(w)} seats {w.seats}, {int(d)} more than {_name(o)}.",
    ))
    return out


_ROW_FOR_CATEGORY = {
    "price": "price", "cost_5yr": "cost_5yr", "range": "range", "efficiency": "efficiency", "safety": "ncap",
    "dc_charging": "dc", "boot": "boot", "seats": "seats",
}


def _notes(cars: list[Variant]) -> list[str]:
    notes = [
        "We do not pick an overall winner. The right car depends on what matters to you; these are the facts and where each car leads.",
        f"Running cost and 5-year cost use our default assumptions (charging mostly at home at about ₹{BLENDED_TARIFF_HOME:g} per kWh, "
        "40 km a day for 5 years). They exclude insurance, registration, service, resale and offers. Your own numbers will differ.",
    ]
    if any(c.pricing_type == "BaaS" for c in cars):
        notes.append(
            "Cars sold with battery rental (BaaS) have a price that excludes the battery, which is rented separately. "
            "We never compare that price with one that includes the battery."
        )
    pending = [_name(c) for c in cars if c.price_status == "pending"]
    if pending:
        notes.append(f"The price of {' and '.join(pending)} is not confirmed yet, so it is left out of price comparisons.")
    if any(_is_earlier_version_test(c) for c in cars):
        notes.append("Where a range or efficiency figure says 'tested on an earlier version', the test was on the car before an update; confirm before buying.")
    return notes


def compare_cars(keys: list[str], variants: list[Variant], dataset_version: str) -> dict[str, Any]:
    """The comparison for these variant keys, in the order given. Raises UnknownCars for keys not in the release."""
    by_key = {v.variant_key: v for v in variants}
    missing = [i for i, k in enumerate(keys) if k not in by_key]
    if missing:
        raise UnknownCars(missing)
    cars = [by_key[k] for k in keys]
    winners = _winners(cars)
    best_row = {_ROW_FOR_CATEGORY[w["category"]]: w["variant_key"] for w in winners if w["variant_key"]}

    sections = []
    for title, rows in _ROWS:
        out_rows = []
        for key, label, build in rows:
            cells = [build(c) for c in cars]
            for car, cell in zip(cars, cells):
                cell["best"] = best_row.get(key) == car.variant_key
            out_rows.append({"key": key, "label": label, "cells": cells})
        sections.append({"title": title, "rows": out_rows})

    return {
        "dataset_version": dataset_version,
        "cars": [
            {
                "variant_key": c.variant_key, "name": _name(c), "brand": c.brand, "model": c.model, "variant": c.variant,
                "body_type": c.body_type, "pricing_type": c.pricing_type, "price_status": c.price_status,
            }
            for c in cars
        ],
        "winners": winners,
        "sections": sections,
        "notes": _notes(cars),
        "watch_outs": [
            {
                "variant_key": c.variant_key,
                "items": [] if c.watch_outs in ("", "None flagged") else [w.strip() for w in c.watch_outs.split(";") if w.strip()],
            }
            for c in cars
        ],
        "disclaimer": DISCLAIMER,
    }
