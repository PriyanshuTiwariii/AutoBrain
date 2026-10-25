"""Tests for release validation: checksums, schema, keys, counts."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from app.validate import validate_release


def test_real_release_passes(release_dir: Path):
    """The 2026-10-25 release must have zero critical errors."""
    report = validate_release(release_dir)
    assert report.checksums_ok is True
    assert report.critical_errors == [], report.critical_errors


def test_real_release_counts_match_manifest(release_dir: Path, manifest: dict):
    """Row counts in the report match what manifest.json declares."""
    report = validate_release(release_dir)
    for key in ("variants", "ladder_steps", "accessories", "dictionary_rows"):
        assert report.counts[key] == manifest["counts"][key], (
            f"{key}: report={report.counts[key]}, manifest={manifest['counts'][key]}"
        )


def test_tampered_csv_fails(release_dir: Path, tmp_path: Path):
    """A CSV with a wrong checksum must produce a critical error."""
    fake_dir = tmp_path / "tampered"
    shutil.copytree(release_dir, fake_dir)
    # Append a byte to one CSV
    csv_path = fake_dir / "autobrain_engine_variants.csv"
    with open(csv_path, "a", encoding="utf-8") as f:
        f.write("\n")
    report = validate_release(fake_dir)
    assert report.checksums_ok is False
    assert any("SHA-256 mismatch" in e for e in report.critical_errors)


def test_duplicate_variant_key_fails(release_dir: Path, tmp_path: Path):
    """Duplicate variant_key must be a critical error."""
    fake_dir = tmp_path / "dupekey"
    shutil.copytree(release_dir, fake_dir)
    csv_path = fake_dir / "autobrain_engine_variants.csv"
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    # Duplicate the second line (first data row)
    lines.append(lines[1])
    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # Update manifest checksum and count so checksum doesn't fail first
    manifest_path = fake_dir / "manifest.json"
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    m["files"]["autobrain_engine_variants.csv"] = hashlib.sha256(
        csv_path.read_bytes()
    ).hexdigest()
    m["counts"]["variants"] = len(lines) - 1  # header excluded
    manifest_path.write_text(json.dumps(m), encoding="utf-8")
    report = validate_release(fake_dir)
    assert any("Duplicate variant_key" in e for e in report.critical_errors)


def test_manifest_count_mismatch_fails(release_dir: Path, tmp_path: Path):
    """Row count mismatch vs manifest must be a critical error."""
    fake_dir = tmp_path / "countmismatch"
    shutil.copytree(release_dir, fake_dir)
    manifest_path = fake_dir / "manifest.json"
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    m["counts"]["variants"] = 999
    manifest_path.write_text(json.dumps(m), encoding="utf-8")
    report = validate_release(fake_dir)
    assert any("Row count mismatch" in e for e in report.critical_errors)


def test_missing_manifest_fails(tmp_path: Path):
    """A release dir without manifest.json must fail critically."""
    report = validate_release(tmp_path)
    assert any("manifest.json missing" in e for e in report.critical_errors)
