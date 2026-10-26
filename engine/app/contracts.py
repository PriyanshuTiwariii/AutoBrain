"""The JSON contracts (contracts/*.schema.json) as validators, with plain-English errors."""
from __future__ import annotations

import json
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from .config import REPO_ROOT

CONTRACTS_DIR = REPO_ROOT / "contracts"


def _load(name: str) -> dict[str, Any]:
    # Always UTF-8: the enums contain "SUV coupé"
    return json.loads((CONTRACTS_DIR / name).read_text(encoding="utf-8"))


NEEDS_SCHEMA = _load("needs.schema.json")
RESULT_SCHEMA = _load("result.schema.json")
EXTRACT_REQUEST_SCHEMA = _load("extract.request.schema.json")
EXTRACT_RESPONSE_SCHEMA = _load("extract.response.schema.json")

_needs_validator = Draft202012Validator(NEEDS_SCHEMA)
_result_validator = Draft202012Validator(RESULT_SCHEMA)
_extract_request_validator = Draft202012Validator(EXTRACT_REQUEST_SCHEMA)
_extract_response_validator = Draft202012Validator(EXTRACT_RESPONSE_SCHEMA)
_needs_field_validators = {name: Draft202012Validator(spec) for name, spec in NEEDS_SCHEMA["properties"].items()}

_TYPE_WORDS = {
    "integer": "a whole number",
    "number": "a number",
    "string": "text",
    "boolean": "true or false",
    "array": "a list",
    "object": "an object",
}


def _field_name(path) -> str:
    """deque(['must_haves', 0]) → 'must_haves[0]'."""
    out = ""
    for part in path:
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out


def _type_message(expected, field: str) -> str:
    types = [expected] if isinstance(expected, str) else list(expected)
    words = [_TYPE_WORDS.get(t, t) for t in types if t != "null"]
    text = " or ".join(words)
    if "null" in types:
        return f"{field} must be {text}, or left out"
    return f"{field} must be {text}"


def _describe(error: ValidationError) -> list[dict[str, str]]:
    """One schema error → one or more {field, message} entries a buyer-facing form can show."""
    field = _field_name(error.absolute_path)
    schema = error.schema if isinstance(error.schema, dict) else {}
    kind = error.validator

    if kind == "required":
        return [
            {"field": name, "message": f"{name} is required"}
            for name in error.validator_value if name not in error.instance
        ]
    if kind == "additionalProperties":
        allowed = ", ".join(schema.get("properties", {}))
        known = set(schema.get("properties", {}))
        return [
            {"field": name, "message": f'Unknown field "{name}". Allowed fields: {allowed}'}
            for name in sorted(error.instance) if name not in known
        ]
    if not field:  # the whole body
        if kind == "type":
            return [{"field": "(body)", "message": "Request body must be a JSON object"}]
        return [{"field": "(body)", "message": error.message}]

    if kind == "type":
        return [{"field": field, "message": _type_message(error.validator_value, field)}]
    if kind in ("minimum", "maximum"):
        lo, hi = schema.get("minimum"), schema.get("maximum")
        if lo is not None and hi is not None:
            return [{"field": field, "message": f"{field} must be a number between {lo} and {hi}"}]
        if kind == "minimum":
            return [{"field": field, "message": f"{field} must be a number of at least {lo}"}]
        return [{"field": field, "message": f"{field} must be a number of at most {hi}"}]
    if kind == "enum":
        options = ", ".join(str(v) for v in error.validator_value)
        return [{"field": field, "message": f"{field} must be one of: {options}"}]
    if kind == "minLength":
        return [{"field": field, "message": f"{field} must not be empty"}]
    if kind == "maxLength":
        return [{"field": field, "message": f"{field} must be at most {error.validator_value} characters"}]
    return [{"field": field, "message": f"{field} is not valid ({error.message})"}]


def _plain_errors(validator: Draft202012Validator, body: Any) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for error in sorted(validator.iter_errors(body), key=lambda e: (list(map(str, e.absolute_path)), e.message)):
        for entry in _describe(error):
            if entry not in found:
                found.append(entry)
    return found


def needs_field_is_valid(name: str, value: Any) -> bool:
    """Is this one value acceptable for this one Needs field, per needs.schema.json?"""
    validator = _needs_field_validators.get(name)
    return validator is not None and validator.is_valid(value)


def extract_request_errors(body: Any) -> list[dict[str, str]]:
    """Plain-English problems with a /extract request body. Empty = valid."""
    return _plain_errors(_extract_request_validator, body)


def extract_response_errors(payload: Any) -> list[str]:
    """Every problem with a /extract response against its contract, with its path, for the log."""
    return [
        f"{'/'.join(str(p) for p in e.absolute_path) or '(root)'}: {e.message}"
        for e in sorted(_extract_response_validator.iter_errors(payload), key=lambda e: list(map(str, e.absolute_path)))
    ]


def needs_errors(body: Any) -> list[dict[str, str]]:
    """Every problem with a Needs body against needs.schema.json, in plain English. Empty = valid."""
    found: list[dict[str, str]] = []
    for error in sorted(_needs_validator.iter_errors(body), key=lambda e: (list(map(str, e.absolute_path)), e.message)):
        for entry in _describe(error):
            if entry not in found:
                found.append(entry)
    return found


def result_errors(payload: Any) -> list[str]:
    """Every problem with a Result against result.schema.json, with its path, for the log."""
    return [
        f"{'/'.join(str(p) for p in e.absolute_path) or '(root)'}: {e.message}"
        for e in sorted(_result_validator.iter_errors(payload), key=lambda e: list(map(str, e.absolute_path)))
    ]


def schema_for_docs(schema: dict[str, Any]) -> dict[str, Any]:
    """A schema copy that can be inlined into the OpenAPI document (no $schema key)."""
    return {k: v for k, v in schema.items() if k != "$schema"}
