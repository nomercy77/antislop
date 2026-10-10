"""Shared utilities for Python verification tools inside a runner image."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


ARTIFACTS = Path(os.environ.get("ANTISLOP_ARTIFACTS_DIR", "/artifacts"))


def python_files() -> list[Path]:
    ignored = {".git", ".venv", "venv", "node_modules", "__pycache__"}
    return [path for path in Path(".").rglob("*.py") if not ignored.intersection(path.parts)]


def location(path: Path, line: int | None = None) -> dict[str, Any]:
    relative = path.relative_to(Path(".")).as_posix()
    result: dict[str, Any] = {"path": relative}
    if line is not None:
        result["line"] = line
    return result


def write_findings(findings: list[dict[str, Any]]) -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "findings.json").write_text(json.dumps(findings, indent=2), encoding="utf-8")
