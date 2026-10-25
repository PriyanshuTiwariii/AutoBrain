"""Shared test fixtures for the AutoBrain engine tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import DATA_RELEASE_DIR
from app.dataset import Dataset, load_dataset


@pytest.fixture(scope="session")
def release_dir() -> Path:
    """Path to the data release the engine loads by default."""
    d = Path(DATA_RELEASE_DIR)
    assert d.exists(), f"Release dir not found: {d}"
    return d


@pytest.fixture(scope="session")
def manifest(release_dir: Path) -> dict:
    return json.loads((release_dir / "manifest.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def dataset(release_dir: Path) -> Dataset:
    """Fully loaded and validated dataset."""
    return load_dataset(release_dir)
