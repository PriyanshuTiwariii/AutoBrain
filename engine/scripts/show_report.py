"""Print the validation report for the current data release."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import REPO_ROOT
from app.validate import validate_release

release_dir = REPO_ROOT / "data" / "releases" / "2026-10-25"
report = validate_release(release_dir)
print(json.dumps(report.model_dump(), indent=2))
