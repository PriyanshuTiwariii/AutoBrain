from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

ENGINE_VERSION = "0.1.0"

# Repo root (the folder holding engine/, data/, contracts/)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Settings come from the repo-root .env (never committed); real environment variables win.
_file_values = dotenv_values(REPO_ROOT / ".env")
load_dotenv(REPO_ROOT / ".env", override=False)
# Names (never values) of variables whose value in the real environment differs from the .env file.
# The environment wins, which silently surprises people: a machine-wide OPENAI_API_KEY beats the
# project's .env. The engine warns about these at startup.
ENV_OVERRIDES_FILE: list[str] = sorted(
    name for name, value in _file_values.items() if value and name in os.environ and os.environ[name] != value
)

def _release_dir() -> Path:
    """DATA_RELEASE_DIR from the environment; a relative path means relative to the repo root,
    wherever the engine was started from."""
    configured = os.environ.get("DATA_RELEASE_DIR")
    if not configured:
        return REPO_ROOT / "data" / "releases" / "2026-10-25-r2"
    path = Path(configured)
    return path if path.is_absolute() else REPO_ROOT / path


DATA_RELEASE_DIR: Path = _release_dir()

# No default: the engine refuses to start without a secret (see app.main).
ENGINE_SECRET: str = os.environ.get("ENGINE_SECRET", "")
PLACEHOLDER_SECRET = "change-me"

# Development only: let a website on localhost:3000 call the engine from the browser.
# Off by default; the real website calls the engine from its server routes.
DEV_CORS: bool = os.environ.get("DEV_CORS", "").strip().lower() in ("1", "true", "yes", "on")
DEV_CORS_ORIGIN = "http://localhost:3000"

# --- LLM (the two optional steps; the engine works with all of this empty) ---------------------
# Provider, key and model names come from .env. No model name appears anywhere in the code.
LLM_PROVIDER: str = os.environ.get("LLM_PROVIDER", "openai").strip().lower() or "openai"
OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
LLM_MODEL_PRIMARY: str = os.environ.get("LLM_MODEL_PRIMARY", "").strip()
LLM_MODEL_FALLBACK: str = os.environ.get("LLM_MODEL_FALLBACK", "").strip()
# Reasoning effort per role. Which values a model accepts differs by model (some reject "none"),
# so these are settings, not code: set them in .env when you change models.
LLM_PRIMARY_REASONING_EFFORT: str = os.environ.get("LLM_PRIMARY_REASONING_EFFORT", "none").strip().lower()
LLM_FALLBACK_REASONING_EFFORT: str = os.environ.get("LLM_FALLBACK_REASONING_EFFORT", "low").strip().lower()
LLM_TIMEOUT_SECONDS: float = float(os.environ.get("LLM_TIMEOUT_SECONDS", "15") or 15)
LLM_MAX_OUTPUT_TOKENS: int = int(os.environ.get("LLM_MAX_OUTPUT_TOKENS", "2000") or 2000)
