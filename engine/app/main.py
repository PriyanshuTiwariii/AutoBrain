"""FastAPI application: startup validation, GET /health and POST /recommend."""
from __future__ import annotations

import hmac
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader

from . import config
from .contracts import NEEDS_SCHEMA, RESULT_SCHEMA, needs_errors, result_errors, schema_for_docs
from .dataset import Dataset, load_dataset
from .models import Needs
from .slots import build_result

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger("autobrain.main")

SECRET_HEADER = "X-Engine-Secret"
_secret_scheme = APIKeyHeader(
    name=SECRET_HEADER, auto_error=False,
    description="The ENGINE_SECRET from your .env file.",
)

# Pre-filled bodies for the /docs "Try it out" page
_EXAMPLES: dict[str, dict[str, Any]] = {
    "scenario_1_budget_10_lakh": {
        "summary": "Budget ₹10 lakh, 30 km/day, home charging",
        "value": {"budget_max_inr": 1000000, "seats_min": 4, "daily_km": 30, "home_charging": "yes"},
    },
    "scenario_3_seven_seats": {
        "summary": "Budget ₹25 lakh, 7 seats, 300 km regular trip",
        "value": {
            "budget_max_inr": 2500000, "seats_min": 7, "daily_km": 40,
            "longest_regular_trip_km": 300, "home_charging": "yes",
        },
    },
    "scenario_5_no_home_charging": {
        "summary": "Budget ₹15 lakh, 40 km/day, no home charging",
        "value": {"budget_max_inr": 1500000, "seats_min": 4, "daily_km": 40, "home_charging": "no"},
    },
    "bad_input_budget_too_low": {
        "summary": "Bad input: shows the plain-English 422",
        "value": {"budget_max_inr": 100000, "seats_min": 4, "daily_km": 30, "home_charging": "maybe"},
    },
}

_RECOMMEND_DOCS: dict[str, Any] = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {"schema": schema_for_docs(NEEDS_SCHEMA), "examples": _EXAMPLES},
        },
    },
}
_RECOMMEND_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {
        "description": "The Result (contracts/result.schema.json)",
        "content": {"application/json": {"schema": schema_for_docs(RESULT_SCHEMA)}},
    },
    401: {"description": "Missing or wrong X-Engine-Secret header"},
    422: {"description": "The Needs are invalid; each problem names its field in plain English"},
    500: {"description": "The engine failed or produced an invalid Result (logged; nothing is returned)"},
}


def _problem(status: int, field: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": [{"field": field, "message": message}]})


def create_app(
    secret: str | None = None,
    release_dir: Path | None = None,
    dev_cors: bool | None = None,
) -> FastAPI:
    """Build the app. Defaults come from the environment/.env; tests pass their own."""
    engine_secret = config.ENGINE_SECRET if secret is None else secret
    data_dir = Path(config.DATA_RELEASE_DIR if release_dir is None else release_dir)
    cors_on = config.DEV_CORS if dev_cors is None else dev_cors

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if not engine_secret.strip():
            raise RuntimeError(
                "ENGINE_SECRET is empty. Set it in the .env file at the repo root "
                "(copy .env.example) before starting the engine."
            )
        if engine_secret == config.PLACEHOLDER_SECRET:
            logger.warning(
                "!!! ENGINE_SECRET is still the placeholder %r. Anyone who knows it can call "
                "/recommend. Change it before this engine is reachable by anyone else. !!!",
                config.PLACEHOLDER_SECRET,
            )
        if cors_on:
            logger.warning(
                "!!! DEV_CORS is on: browsers on %s may call this engine directly. "
                "Development only; the website must call /recommend from its server routes. !!!",
                config.DEV_CORS_ORIGIN,
            )
        logger.info("Loading data release from %s", data_dir)
        ds = load_dataset(data_dir)
        app.state.dataset = ds
        logger.info("Engine ready — release %s, engine v%s", ds.version, ds.engine_version)
        yield

    app = FastAPI(title="AutoBrain Engine", version=config.ENGINE_VERSION, lifespan=lifespan)
    app.state.secret = engine_secret

    if cors_on:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[config.DEV_CORS_ORIGIN],
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type", SECRET_HEADER],
        )

    def require_secret(request: Request, supplied: str | None = Depends(_secret_scheme)) -> None:
        expected: str = request.app.state.secret
        if not supplied or not hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
            # Same answer for missing and wrong: no hint about which one it was
            raise HTTPException(status_code=401, detail=f"Missing or invalid {SECRET_HEADER} header")

    @app.get("/health")
    def health(request: Request):
        ds: Dataset = request.app.state.dataset
        return {
            "status": "ok",
            "release": ds.manifest.get("release", ds.version),
            "counts": ds.manifest.get("counts", {}),
            "engine_version": ds.engine_version,
        }

    @app.post(
        "/recommend",
        openapi_extra=_RECOMMEND_DOCS,
        responses=_RECOMMEND_RESPONSES,
        dependencies=[Depends(require_secret)],
        summary="Needs in, Result out (pure engine, no LLM)",
    )
    async def recommend(request: Request):
        ds: Dataset = request.app.state.dataset

        raw = await request.body()
        if not raw.strip():
            return _problem(422, "(body)", "Request body is empty; send the Needs as a JSON object")
        try:
            body = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return _problem(422, "(body)", "Request body is not valid JSON")

        problems = needs_errors(body)
        if problems:
            return JSONResponse(status_code=422, content={"detail": problems})

        try:
            needs = Needs(**body)
            result = build_result(needs, ds.variants, ds.version, ds.engine_version, dataset=ds)
            payload = result.model_dump(mode="json")
        except Exception:
            # Valid Needs that the engine cannot handle is an engine bug, never the buyer's fault
            logger.exception("Engine failed on valid Needs (release %s)", ds.version)
            return JSONResponse(
                status_code=500,
                content={"detail": "The engine failed to build a result. This has been logged."},
            )

        invalid = result_errors(payload)
        if invalid:
            logger.error(
                "Result %s failed result.schema.json (release %s, engine %s): %s",
                payload.get("result_id"), ds.version, ds.engine_version, "; ".join(invalid),
            )
            return JSONResponse(
                status_code=500,
                content={"detail": "The engine produced an invalid result. This has been logged; nothing was returned."},
            )

        logger.info(
            "Result %s: release=%s counts=%s engine=%s slots=%d",
            payload["result_id"], ds.version, ds.manifest.get("counts"), ds.engine_version, len(payload["slots"]),
        )
        return JSONResponse(content=payload)

    return app


app = create_app()
