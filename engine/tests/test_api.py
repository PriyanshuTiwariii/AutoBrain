"""The engine's HTTP routes, through FastAPI's test client."""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config
from app.contracts import NEEDS_SCHEMA, needs_errors, result_errors
from app.dataset import Dataset
from app.main import SECRET_HEADER, create_app
from app.models import Needs
from app.slots import build_result, make_result_id
from tests.test_contract import GOLDEN_NEEDS

SECRET = "test-secret-not-the-placeholder"
AUTH = {SECRET_HEADER: SECRET}
ENGINE_DIR = Path(__file__).resolve().parent.parent
SCENARIO_1 = GOLDEN_NEEDS["1_budget_10L"]


@pytest.fixture(scope="module")
def client(release_dir: Path):
    app = create_app(secret=SECRET, release_dir=release_dir, dev_cors=False)
    with TestClient(app) as c:  # the `with` runs startup (loads and validates the release)
        yield c


# --- /health --------------------------------------------------------------------

def test_health_reports_release_counts_and_version(client: TestClient, manifest: dict):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {
        "status": "ok",
        "release": manifest["release"],
        "counts": manifest["counts"],
        "engine_version": config.ENGINE_VERSION,
    }


def test_health_needs_no_secret(client: TestClient):
    assert client.get("/health").status_code == 200


# --- /recommend: the six golden scenarios ----------------------------------------

@pytest.mark.parametrize("name", sorted(GOLDEN_NEEDS))
def test_golden_scenario_via_api_equals_direct_engine(client: TestClient, dataset: Dataset, name: str):
    kwargs = GOLDEN_NEEDS[name]
    r = client.post("/recommend", json=kwargs, headers=AUTH)
    assert r.status_code == 200, r.text
    direct = build_result(Needs(**kwargs), dataset.variants, dataset.version, dataset.engine_version, dataset=dataset)
    assert r.json() == json.loads(direct.model_dump_json())
    assert result_errors(r.json()) == []


def test_scenario_6_says_nothing_qualifies(client: TestClient):
    body = client.post("/recommend", json=GOLDEN_NEEDS["6_nothing_qualifies"], headers=AUTH).json()
    assert [s for s in body["slots"] if s["slot"] != "not_recommended"] == []
    assert any("None of the vehicles" in u for u in body["unknowns"])


# --- /recommend: bad input -------------------------------------------------------

def _post(client: TestClient, **changes):
    body = {**SCENARIO_1, **changes}
    return client.post("/recommend", json={k: v for k, v in body.items() if v is not ...}, headers=AUTH)


@pytest.mark.parametrize(
    "changes, field, message",
    [
        (dict(budget_max_inr=100000), "budget_max_inr", "budget_max_inr must be a number of at least 300000"),
        (dict(budget_max_inr="ten lakh"), "budget_max_inr", "budget_max_inr must be a whole number"),
        (dict(budget_max_inr=1500000.5), "budget_max_inr", "budget_max_inr must be a whole number"),
        (dict(budget_max_inr=True), "budget_max_inr", "budget_max_inr must be a whole number"),
        (dict(seats_min=9), "seats_min", "seats_min must be a number between 2 and 7"),
        (dict(daily_km=0), "daily_km", "daily_km must be a number between 1 and 500"),
        (dict(longest_regular_trip_km=0), "longest_regular_trip_km", "longest_regular_trip_km must be a number of at least 1"),
        (dict(longest_regular_trip_km="far"), "longest_regular_trip_km", "longest_regular_trip_km must be a whole number, or left out"),
        (dict(home_charging="maybe"), "home_charging", "home_charging must be one of: yes, no, unsure"),
        (dict(priority="speed"), "priority", "priority must be one of: balanced, safety, cost, range, features, space"),
        (dict(budget_includes_charger="yes"), "budget_includes_charger", "budget_includes_charger must be true or false"),
        (dict(must_haves="adas"), "must_haves", "must_haves must be a list"),
        (dict(must_haves=["adas", "wifi"]), "must_haves[1]", "must_haves[1] must be one of: adas, camera_360,"),
        (dict(body_types=["Truck"]), "body_types[0]", "body_types[0] must be one of: Hatchback, Sedan, SUV, SUV coupé"),
        (dict(daily_km=...), "daily_km", "daily_km is required"),
        (dict(colour="red"), "colour", 'Unknown field "colour". Allowed fields: budget_max_inr,'),
    ],
)
def test_bad_input_gets_422_naming_the_field(client: TestClient, changes, field, message):
    r = _post(client, **changes)
    assert r.status_code == 422, r.text
    entries = r.json()["detail"]
    match = [e for e in entries if e["field"] == field]
    assert match, entries
    assert match[0]["message"].startswith(message), match[0]


def test_every_problem_is_reported_at_once(client: TestClient):
    r = client.post("/recommend", json={"budget_max_inr": 5, "seats_min": 9, "home_charging": "maybe"}, headers=AUTH)
    assert r.status_code == 422
    fields = {e["field"] for e in r.json()["detail"]}
    assert fields == {"budget_max_inr", "seats_min", "home_charging", "daily_km"}


@pytest.mark.parametrize(
    "content, message",
    [
        (b"", "Request body is empty"),
        (b"   ", "Request body is empty"),
        (b"{not json", "Request body is not valid JSON"),
        (b"\xff\xfe", "Request body is not valid JSON"),
        (b"[1, 2]", "Request body must be a JSON object"),
        (b'"text"', "Request body must be a JSON object"),
        (b"null", "Request body must be a JSON object"),
    ],
)
def test_malformed_body_gets_422(client: TestClient, content: bytes, message: str):
    r = client.post("/recommend", content=content, headers={**AUTH, "Content-Type": "application/json"})
    assert r.status_code == 422
    assert r.json()["detail"][0]["field"] == "(body)"
    assert r.json()["detail"][0]["message"].startswith(message)


def test_bad_input_returns_no_result_data(client: TestClient):
    r = _post(client, budget_max_inr=100000)
    assert "slots" not in r.text and "result_id" not in r.text


# --- /recommend: the shared secret ------------------------------------------------

def test_missing_secret_is_401(client: TestClient):
    r = client.post("/recommend", json=SCENARIO_1)
    assert r.status_code == 401
    assert "slots" not in r.text


def test_wrong_secret_is_401_with_same_message(client: TestClient):
    missing = client.post("/recommend", json=SCENARIO_1)
    wrong = client.post("/recommend", json=SCENARIO_1, headers={SECRET_HEADER: "nope"})
    assert wrong.status_code == 401
    assert wrong.json() == missing.json()


def test_secret_is_checked_before_the_body(client: TestClient):
    """Bad input without the secret is 401, not 422: an anonymous caller learns nothing."""
    assert client.post("/recommend", json={"budget_max_inr": 1}).status_code == 401


def test_correct_secret_works(client: TestClient):
    assert client.post("/recommend", json=SCENARIO_1, headers=AUTH).status_code == 200


# --- determinism ------------------------------------------------------------------

def test_same_input_twice_is_byte_identical(client: TestClient):
    for kwargs in GOLDEN_NEEDS.values():
        a = client.post("/recommend", json=kwargs, headers=AUTH)
        b = client.post("/recommend", json=kwargs, headers=AUTH)
        assert a.content == b.content


def test_defaults_spelled_out_give_the_same_result(client: TestClient):
    plain = client.post("/recommend", json=SCENARIO_1, headers=AUTH).json()
    explicit = client.post("/recommend", json={**SCENARIO_1, "priority": "balanced", "must_haves": []}, headers=AUTH).json()
    assert plain == explicit


def test_result_id_is_a_hash_of_needs_release_and_engine(dataset: Dataset):
    n = Needs(**SCENARIO_1)
    base = make_result_id(n, "r1", "0.1.0")
    assert base == make_result_id(Needs(**SCENARIO_1), "r1", "0.1.0")
    assert base != make_result_id(n, "r2", "0.1.0")
    assert base != make_result_id(n, "r1", "0.2.0")
    assert base != make_result_id(Needs(**{**SCENARIO_1, "daily_km": 31}), "r1", "0.1.0")
    assert len(base) == 16 and int(base, 16) >= 0


def test_same_result_across_processes_with_different_hash_seeds():
    """Output must not depend on Python's per-process hash randomisation (set/dict order)."""
    code = (
        "import json, sys\n"
        "from app.config import DATA_RELEASE_DIR\n"
        "from app.dataset import load_dataset\n"
        "from app.models import Needs\n"
        "from app.slots import build_result\n"
        "from tests.test_contract import GOLDEN_NEEDS\n"
        "ds = load_dataset(DATA_RELEASE_DIR)\n"
        "out = {k: json.loads(build_result(Needs(**v), ds.variants, ds.version, ds.engine_version, dataset=ds).model_dump_json())\n"
        "       for k, v in sorted(GOLDEN_NEEDS.items())}\n"
        "sys.stdout.buffer.write(json.dumps(out, sort_keys=True).encode('utf-8'))\n"
    )
    outputs = []
    for seed in ("1", "2", "12345"):
        env = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONIOENCODING": "utf-8"}
        done = subprocess.run([sys.executable, "-c", code], cwd=ENGINE_DIR, env=env, capture_output=True, timeout=120)
        assert done.returncode == 0, done.stderr.decode("utf-8", "replace")
        outputs.append(done.stdout)
    assert outputs[0] == outputs[1] == outputs[2]


# --- never send an invalid Result --------------------------------------------------

def test_invalid_result_is_a_500_that_is_logged(release_dir: Path, monkeypatch, caplog):
    import app.main as main_module

    real_build = main_module.build_result

    def broken_build(*args, **kwargs):
        result = real_build(*args, **kwargs)
        result.slots[0].metrics["range_display"] = ["not", "a", "scalar"]  # breaks result.schema.json
        return result

    monkeypatch.setattr(main_module, "build_result", broken_build)
    app = create_app(secret=SECRET, release_dir=release_dir, dev_cors=False)
    with TestClient(app) as c, caplog.at_level(logging.ERROR, logger="autobrain.main"):
        r = c.post("/recommend", json=SCENARIO_1, headers=AUTH)
    assert r.status_code == 500
    assert r.json() == {"detail": "The engine produced an invalid result. This has been logged; nothing was returned."}
    assert "slots" not in r.text and "variant_key" not in r.text
    logged = " ".join(rec.getMessage() for rec in caplog.records if rec.levelno == logging.ERROR)
    assert "failed result.schema.json" in logged and "slots/0/metrics/range_display" in logged


def test_engine_crash_is_a_500_that_is_logged(release_dir: Path, monkeypatch, caplog):
    import app.main as main_module

    def crash(*args, **kwargs):
        raise ValueError("boom")

    monkeypatch.setattr(main_module, "build_result", crash)
    app = create_app(secret=SECRET, release_dir=release_dir, dev_cors=False)
    with TestClient(app) as c, caplog.at_level(logging.ERROR, logger="autobrain.main"):
        r = c.post("/recommend", json=SCENARIO_1, headers=AUTH)
    assert r.status_code == 500
    assert "boom" not in r.text
    assert any("Engine failed on valid Needs" in rec.getMessage() for rec in caplog.records)


def test_each_result_is_logged_with_release_counts_and_version(client: TestClient, caplog, manifest: dict):
    with caplog.at_level(logging.INFO, logger="autobrain.main"):
        body = client.post("/recommend", json=SCENARIO_1, headers=AUTH).json()
    line = next(rec.getMessage() for rec in caplog.records if body["result_id"] in rec.getMessage())
    assert manifest["release"] in line and config.ENGINE_VERSION in line and "'variants': 87" in line
    assert "daily_km" not in line  # the Needs themselves are not logged


# --- startup: the secret ------------------------------------------------------------

@pytest.mark.parametrize("secret", ["", "   "])
def test_refuses_to_start_without_a_secret(release_dir: Path, secret: str):
    app = create_app(secret=secret, release_dir=release_dir, dev_cors=False)
    with pytest.raises(RuntimeError, match="ENGINE_SECRET is empty"):
        with TestClient(app):
            pass


def test_placeholder_secret_starts_but_warns_loudly(release_dir: Path, caplog):
    app = create_app(secret=config.PLACEHOLDER_SECRET, release_dir=release_dir, dev_cors=False)
    with caplog.at_level(logging.WARNING, logger="autobrain.main"):
        with TestClient(app) as c:
            assert c.get("/health").status_code == 200
    assert any("ENGINE_SECRET is still the placeholder" in r.getMessage() and r.levelno == logging.WARNING for r in caplog.records)


def test_real_secret_does_not_warn(client: TestClient, release_dir: Path, caplog):
    app = create_app(secret=SECRET, release_dir=release_dir, dev_cors=False)
    with caplog.at_level(logging.WARNING, logger="autobrain.main"):
        with TestClient(app):
            pass
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


# --- CORS: off by default ------------------------------------------------------------

PREFLIGHT = {
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": f"content-type,{SECRET_HEADER.lower()}",
}


def test_cors_is_off_by_default(release_dir: Path, monkeypatch):
    monkeypatch.setattr(config, "DEV_CORS", False)
    app = create_app(secret=SECRET, release_dir=release_dir)  # dev_cors left to the environment
    with TestClient(app) as c:
        r = c.options("/recommend", headers={"Origin": config.DEV_CORS_ORIGIN, **PREFLIGHT})
        assert "access-control-allow-origin" not in r.headers
        r = c.post("/recommend", json=SCENARIO_1, headers={**AUTH, "Origin": config.DEV_CORS_ORIGIN})
        assert r.status_code == 200 and "access-control-allow-origin" not in r.headers


def test_dev_cors_setting_turns_it_on(release_dir: Path, monkeypatch, caplog):
    monkeypatch.setattr(config, "DEV_CORS", True)
    app = create_app(secret=SECRET, release_dir=release_dir)
    with caplog.at_level(logging.WARNING, logger="autobrain.main"), TestClient(app) as c:
        r = c.options("/recommend", headers={"Origin": "http://localhost:3000", **PREFLIGHT})
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert any("DEV_CORS is on" in rec.getMessage() for rec in caplog.records)


def test_dev_cors_allows_only_localhost_3000(release_dir: Path):
    app = create_app(secret=SECRET, release_dir=release_dir, dev_cors=True)
    with TestClient(app) as c:
        for origin in ("http://localhost:3001", "https://localhost:3000", "http://evil.example", "http://127.0.0.1:3000"):
            r = c.options("/recommend", headers={"Origin": origin, **PREFLIGHT})
            assert "access-control-allow-origin" not in r.headers, origin
        r = c.get("/health", headers={"Origin": "http://evil.example"})
        assert "access-control-allow-origin" not in r.headers
        r = c.get("/health", headers={"Origin": "http://localhost:3000"})
        assert r.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_does_not_replace_the_secret(release_dir: Path):
    app = create_app(secret=SECRET, release_dir=release_dir, dev_cors=True)
    with TestClient(app) as c:
        r = c.post("/recommend", json=SCENARIO_1, headers={"Origin": "http://localhost:3000"})
        assert r.status_code == 401


# --- /docs ---------------------------------------------------------------------------

def test_docs_page_offers_authorize_and_examples(client: TestClient):
    spec = client.get("/openapi.json").json()
    post = spec["paths"]["/recommend"]["post"]
    schemes = spec["components"]["securitySchemes"].values()
    assert any(s["type"] == "apiKey" and s["in"] == "header" and s["name"] == SECRET_HEADER for s in schemes)
    content = post["requestBody"]["content"]["application/json"]
    assert content["schema"]["required"] == NEEDS_SCHEMA["required"]
    assert "scenario_1_budget_10_lakh" in content["examples"]
    for example in content["examples"].values():
        if not example["summary"].startswith("Bad input"):
            assert needs_errors(example["value"]) == []
    assert client.get("/docs").status_code == 200


# --- contract drift: everything needs.schema.json accepts, the Needs model must accept ----

def _pydantic_accepts(body: dict) -> bool:
    try:
        Needs(**body)
        return True
    except Exception:
        return False


def test_needs_model_accepts_everything_the_schema_accepts():
    props = NEEDS_SCHEMA["properties"]
    assert set(props) == set(Needs.model_fields)
    assert set(NEEDS_SCHEMA["required"]) == {n for n, f in Needs.model_fields.items() if f.is_required()}

    checked = 0
    for name, spec in props.items():
        candidates: list = []
        types = spec.get("type") if isinstance(spec.get("type"), list) else [spec.get("type")]
        if "integer" in types:
            lo, hi = spec.get("minimum"), spec.get("maximum")
            candidates += [v for v in (lo, hi, (lo - 1) if lo is not None else None, (hi + 1) if hi is not None else None) if v is not None]
            candidates += ["text", 1.5, True]
        if "null" in types:
            candidates.append(None)
        if "enum" in spec:
            candidates += list(spec["enum"]) + ["not-an-option"]
        if spec.get("type") == "boolean":
            candidates += [True, False, "yes", 1]
        if spec.get("type") == "array":
            allowed = spec.get("items", {}).get("enum")
            if allowed:
                candidates += [[v] for v in allowed] + [["not-an-option"], "not-a-list"]
            else:
                candidates += [["x"], [1], "not-a-list"]
        if "string" in types and "enum" not in spec:
            candidates += ["Delhi", 5]
        for value in candidates:
            body = {**SCENARIO_1, name: value}
            # The route checks the contract first, so a lenient model is harmless (it never sees
            # that input). A model stricter than the contract would turn valid input into a 500.
            if needs_errors(body) == []:
                assert _pydantic_accepts(body), f"{name}={value!r} is valid per the contract but the model rejects it"
            checked += 1
    assert checked > 60

    # Defaults in the schema are the defaults the model applies
    model = Needs(**SCENARIO_1)
    for name, spec in props.items():
        if "default" in spec:
            actual = getattr(model, name)
            actual = actual.value if hasattr(actual, "value") else actual
            assert actual == spec["default"], name


def test_relative_release_dir_means_relative_to_the_repo_root():
    """.env.example says data/releases/...; that must work whatever folder the engine starts in."""
    code = "from app import config; print(config.DATA_RELEASE_DIR)"
    env = {**os.environ, "DATA_RELEASE_DIR": "data/releases/2026-10-25-r2", "PYTHONIOENCODING": "utf-8"}
    done = subprocess.run([sys.executable, "-c", code], cwd=ENGINE_DIR, env=env, capture_output=True, timeout=60)
    assert Path(done.stdout.decode().strip()) == config.REPO_ROOT / "data" / "releases" / "2026-10-25-r2"
