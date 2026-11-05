"""Release metadata."""

from __future__ import annotations

import json
from pathlib import Path
import tomllib

ROOT = Path(__file__).parent.parent


def test_manifest_version_matches_project_version() -> None:
    """The release workflow checks both against the tag, so they must agree."""
    manifest = json.loads(
        (ROOT / "custom_components/qingping_cgd1/manifest.json").read_text()
    )
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())

    assert manifest["version"] == project["project"]["version"]
