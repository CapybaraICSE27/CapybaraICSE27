#!/usr/bin/env python3
"""Install-result validation helpers for RQ6 execution pilots."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


INSTALL_VALIDATION_SCHEMA = "rq6_install_v2_dependency_tree"


def dependency_tree_present(workdir: Path) -> bool:
    if not workdir.is_dir():
        return False
    markers = [
        workdir / "node_modules",
        workdir / ".pnp.cjs",
        workdir / ".pnp.js",
    ]
    return any(path.exists() for path in markers)


def install_row_schema_current(row: Dict[str, Any]) -> bool:
    return str(row.get("install_validation_schema") or "") == INSTALL_VALIDATION_SCHEMA


def install_row_is_current_success(row: Dict[str, Any]) -> bool:
    return bool(row.get("install_ok")) and install_row_schema_current(row) and bool(row.get("dependency_tree_present"))
