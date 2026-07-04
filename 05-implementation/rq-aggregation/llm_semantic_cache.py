"""Small file-backed cache for LLM semantic correction outputs."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Optional


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def build_input_hash(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def _safe_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value or "unknown")[:120]


class LlmSemanticCache:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _path(self, *, model: str, prompt_version: str, input_hash: str) -> Path:
        return self.root / _safe_part(model) / _safe_part(prompt_version) / f"{_safe_part(input_hash)}.json"

    def get(self, *, model: str, prompt_version: str, input_hash: str) -> Optional[Dict[str, Any]]:
        path = self._path(model=model, prompt_version=prompt_version, input_hash=input_hash)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def put(self, *, model: str, prompt_version: str, input_hash: str, payload: Dict[str, Any]) -> None:
        path = self._path(model=model, prompt_version=prompt_version, input_hash=input_hash)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
