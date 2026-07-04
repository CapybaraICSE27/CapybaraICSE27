from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = (
    PACKAGE_DIR.parent.parent if PACKAGE_DIR.parent.name == "src" else Path.cwd()
).resolve()
