"""FastAPI application with startup validation and /health endpoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from .config import DATA_RELEASE_DIR, ENGINE_VERSION
from .dataset import Dataset, load_dataset

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger("autobrain.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    release_dir = Path(DATA_RELEASE_DIR)
    logger.info("Loading data release from %s", release_dir)
    ds = load_dataset(release_dir)
    app.state.dataset = ds
    logger.info("Engine ready — release %s, engine v%s", ds.version, ds.engine_version)
    yield


app = FastAPI(title="AutoBrain Engine", version=ENGINE_VERSION, lifespan=lifespan)


@app.get("/health")
def health():
    ds: Dataset = app.state.dataset
    return {
        "status": "ok",
        "dataset_version": ds.version,
        "engine_version": ds.engine_version,
        "counts": {
            "variants": len(ds.variants),
            "ladder_steps": len(ds.ladder),
            "accessories": len(ds.accessories),
        },
    }
