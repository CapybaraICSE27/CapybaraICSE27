"""Cache invalidation fingerprints for per-repo static metrics."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_analyzer_fingerprint(node_script: Path) -> Dict[str, str]:
    """
    Hash static-metrics entry + local libs and transitive Phase 2 hook/shared deps.
    Keys are paths relative to ui_test_feature_extraction_phase2/.
    """
    phase2_root = node_script.resolve().parent.parent
    scan_roots = [
        node_script.parent,
        phase2_root / "lib" / "phase2b",
        phase2_root / "lib" / "shared",
    ]
    fp: Dict[str, str] = {}
    if node_script.exists():
        rel_entry = node_script.resolve().relative_to(phase2_root).as_posix()
        fp[rel_entry] = file_sha256(node_script)
    for root in scan_roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.js")):
            rel = path.resolve().relative_to(phase2_root).as_posix()
            fp[rel] = file_sha256(path)
    return fp


def manifest_sha256(repo: str, tests: List[Dict[str, Any]], hooks: List[Dict[str, Any]]) -> str:
    payload = {"repo": repo, "tests": tests, "hooks": hooks}
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def repo_commit_state(tests: List[Dict[str, Any]]) -> tuple[Optional[str], bool]:
    """
    Return (expected_commit, has_mixed_commits).
    expected_commit is set only when all non-empty test-case commits agree.
    """
    commits = {str(tc.get("commit") or "").strip() for tc in tests if str(tc.get("commit") or "").strip()}
    if len(commits) > 1:
        return None, True
    if len(commits) == 1:
        return next(iter(commits)), False
    return None, False


def expected_commit_for_repo(tests: List[Dict[str, Any]]) -> Optional[str]:
    expected, _mixed = repo_commit_state(tests)
    return expected


def git_head_commit(repo_path: Path) -> Optional[str]:
    if not (repo_path / ".git").exists():
        return None
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode == 0:
            return proc.stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def build_repo_cache_fingerprint(
    *,
    payload_version: int,
    manifest_sha: str,
    analyzer_fp: Dict[str, str],
    test_cases_jsonl_sha256: str,
    input_run_dir: str,
    expected_commit: Optional[str],
    analyzed_head: Optional[str],
    allow_commit_mismatch: bool,
) -> Dict[str, Any]:
    return {
        "payload_version": payload_version,
        "manifest_sha256": manifest_sha,
        "analyzer": analyzer_fp,
        "test_cases_jsonl_sha256": test_cases_jsonl_sha256,
        "input_run_dir": input_run_dir,
        "expected_commit": expected_commit,
        "analyzed_head": analyzed_head,
        "allow_commit_mismatch": allow_commit_mismatch,
    }


def fingerprint_matches(cached: Dict[str, Any], current: Dict[str, Any]) -> bool:
    if not cached:
        return False
    for key in (
        "payload_version",
        "manifest_sha256",
        "analyzer",
        "test_cases_jsonl_sha256",
        "input_run_dir",
        "expected_commit",
        "analyzed_head",
        "allow_commit_mismatch",
    ):
        if cached.get(key) != current.get(key):
            return False
    return True


def cache_entry_is_valid(cached_repo_json: Dict[str, Any], current_fp: Dict[str, Any]) -> bool:
    stored = cached_repo_json.get("cache_fingerprint")
    if not isinstance(stored, dict):
        return False
    if int(stored.get("payload_version") or 0) < int(current_fp.get("payload_version") or 0):
        return False
    return fingerprint_matches(stored, current_fp)
