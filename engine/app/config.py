from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ENGINE_VERSION = "0.1.0"

# Repo root (the folder holding engine/, data/, contracts/)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Settings come from the repo-root .env (never committed); real environment variables win.
load_dotenv(REPO_ROOT / ".env", override=False)

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
