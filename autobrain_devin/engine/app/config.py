from __future__ import annotations

import os
from pathlib import Path

ENGINE_VERSION = "0.1.0"

# Repo root is autobrain_devin/
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

DATA_RELEASE_DIR: Path = Path(
    os.environ.get("DATA_RELEASE_DIR", str(REPO_ROOT / "data" / "releases" / "2026-10-25"))
)

ENGINE_SECRET: str = os.environ.get("ENGINE_SECRET", "change-me")
