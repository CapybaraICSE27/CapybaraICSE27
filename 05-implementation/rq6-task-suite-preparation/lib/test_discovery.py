#!/usr/bin/env python3
"""Cheap runner-discovery checks for RQ6 human baseline candidates."""

from __future__ import annotations

import os
import shlex
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from common import normalize_framework, prepare_subprocess_command, resolve_command_executable, run_process_capture


DISCOVERY_CACHE_FIELDS = [
    "discovered",
    "discovery_status",
    "discovery_failure_category",
    "discovery_stdout_path",
    "discovery_stderr_path",
]


class DiscoveryCache:
    def __init__(self) -> None:
        self._rows: Dict[str, Dict[str, Any]] = {}

    def key_for(self, test: Dict[str, Any], repo_ctx: Dict[str, Any]) -> str:
        framework = normalize_framework(test.get("framework") or repo_ctx.get("framework"))
        workdir = repo_workdir(repo_ctx)
        command = discovery_command(test, repo_ctx)
        if framework == "cypress":
            return "|".join([framework, str(workdir), " ".join(command)])
        return "|".join(
            [
                framework,
                str(workdir),
                str(test.get("file_path") or ""),
                str(test.get("test_name") or ""),
                " ".join(command),
            ]
        )

    def get(self, test: Dict[str, Any], repo_ctx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        row = self._rows.get(self.key_for(test, repo_ctx))
        return dict(row) if row else None

    def set(self, test: Dict[str, Any], repo_ctx: Dict[str, Any], row: Dict[str, Any]) -> None:
        self._rows[self.key_for(test, repo_ctx)] = {
            field: row.get(field) for field in DISCOVERY_CACHE_FIELDS if field in row
        }


def split_command_text(command_text: Any) -> List[str]:
    text = str(command_text or "").strip()
    if not text:
        return []
    try:
        return shlex.split(text, posix=os.name != "nt")
    except ValueError:
        return text.split()


def repo_workdir(repo_ctx: Dict[str, Any]) -> Path:
    return Path(str(repo_ctx.get("workdir_path") or repo_ctx.get("repo_cache_path") or ""))


def test_file_path(test: Dict[str, Any], repo_ctx: Dict[str, Any]) -> Path:
    path = Path(str(test.get("file_path") or ""))
    if path.is_absolute():
        return path
    return repo_workdir(repo_ctx) / path


def playwright_list_command(test: Dict[str, Any], repo_ctx: Dict[str, Any]) -> List[str]:
    base = split_command_text(repo_ctx.get("list_command"))
    if not base:
        base = split_command_text(repo_ctx.get("runner_command_base"))
        if base:
            base.append("--list")
    elif "--list" not in base:
        base.append("--list")
    if not base:
        return []
    command = base + [str(test.get("file_path") or "")]
    test_name = str(test.get("test_name") or "").strip()
    if test_name:
        command.extend(["-g", test_name])
    return command


def cypress_verify_command(repo_ctx: Dict[str, Any]) -> List[str]:
    base = split_command_text(repo_ctx.get("runner_command_base"))
    if not base:
        return ["cypress", "verify"]
    for index, token in enumerate(base):
        clean = Path(str(token).strip("\"'")).stem.lower()
        if clean == "cypress":
            return base[: index + 1] + ["verify"]
    if base and base[-1].lower() == "run":
        return base[:-1] + ["verify"]
    return base + ["verify"]


def discovery_command(test: Dict[str, Any], repo_ctx: Dict[str, Any]) -> List[str]:
    framework = normalize_framework(test.get("framework") or repo_ctx.get("framework"))
    if framework == "playwright":
        return playwright_list_command(test, repo_ctx)
    if framework == "cypress":
        return cypress_verify_command(repo_ctx)
    return []


def classify_playwright_discovery(proc: Dict[str, Any]) -> Dict[str, Any]:
    stdout = proc.get("stdout") or ""
    stderr = proc.get("stderr") or ""
    combined = f"{stdout}\n{stderr}".lower()
    if proc.get("timed_out"):
        return {
            "discovered": False,
            "discovery_status": "test_discovery_timeout",
            "discovery_failure_category": "test_discovery_timeout",
        }
    if proc.get("returncode") == 0:
        return {
            "discovered": True,
            "discovery_status": "pass",
            "discovery_failure_category": "",
        }
    if "no tests found" in combined or "did not find any tests" in combined:
        return {
            "discovered": False,
            "discovery_status": "test_not_discovered",
            "discovery_failure_category": "test_not_discovered",
        }
    return {
        "discovered": False,
        "discovery_status": "test_discovery_failed",
        "discovery_failure_category": "test_discovery_failed",
    }


def classify_cypress_verify(proc: Dict[str, Any]) -> Dict[str, Any]:
    stdout = proc.get("stdout") or ""
    stderr = proc.get("stderr") or ""
    combined = f"{stdout}\n{stderr}".lower()
    if proc.get("timed_out"):
        return {
            "discovered": False,
            "discovery_status": "cypress_verify_timeout",
            "discovery_failure_category": "cypress_verify_timeout",
        }
    if proc.get("returncode") == 0:
        return {
            "discovered": True,
            "discovery_status": "cypress_binary_verified",
            "discovery_failure_category": "",
        }
    if "no version of cypress is installed" in combined or "cypress executable not found" in combined:
        return {
            "discovered": False,
            "discovery_status": "cypress_binary_missing",
            "discovery_failure_category": "cypress_binary_missing",
        }
    return {
        "discovered": False,
        "discovery_status": "cypress_verify_failed",
        "discovery_failure_category": "cypress_verify_failed",
    }


def static_discovery_check(test: Dict[str, Any], repo_ctx: Dict[str, Any]) -> Dict[str, Any]:
    framework = normalize_framework(test.get("framework") or repo_ctx.get("framework"))
    workdir = repo_workdir(repo_ctx)
    if not workdir.is_dir():
        return {
            "discovered": False,
            "discovery_status": "missing_workdir",
            "discovery_failure_category": "missing_workdir",
        }
    if not test_file_path(test, repo_ctx).is_file():
        return {
            "discovered": False,
            "discovery_status": "test_file_missing",
            "discovery_failure_category": "test_file_missing",
        }
    if framework in {"playwright", "cypress"}:
        command = discovery_command(test, repo_ctx)
        if not command:
            return {
                "discovered": False,
                "discovery_status": "missing_discovery_command",
                "discovery_failure_category": "missing_discovery_command",
            }
        prepared = prepare_subprocess_command(command, cwd=workdir)
        if not prepared or not resolve_command_executable(prepared[0], cwd=workdir):
            return {
                "discovered": False,
                "discovery_status": "runtime_command_not_found",
                "discovery_failure_category": "runtime_command_not_found",
            }
    return {
        "discovered": True,
        "discovery_status": "file_exists_unverified_runner_scope" if framework == "cypress" else "static_pass",
        "discovery_failure_category": "",
    }


def run_discovery_check(
    test: Dict[str, Any],
    repo_ctx: Dict[str, Any],
    *,
    timeout_sec: int,
    log_dir: Optional[Path] = None,
    stem: str = "rq6_discovery",
    cache: Optional[DiscoveryCache] = None,
) -> Dict[str, Any]:
    framework = normalize_framework(test.get("framework") or repo_ctx.get("framework"))
    static = static_discovery_check(test, repo_ctx)
    command = discovery_command(test, repo_ctx)
    row: Dict[str, Any] = {
        "discovery_command": " ".join(command),
        "discovery_duration_sec": 0.0,
        "discovery_stdout_path": "",
        "discovery_stderr_path": "",
        "discovery_cache_hit": False,
        **static,
    }
    if not static.get("discovered") or framework not in {"playwright", "cypress"}:
        return row

    cached = cache.get(test, repo_ctx) if cache else None
    if cached:
        row.update(cached)
        row["discovery_duration_sec"] = 0.0
        row["discovery_cache_hit"] = True
        return row

    workdir = repo_workdir(repo_ctx)
    started = time.time()
    stdout_path: Optional[Path] = None
    stderr_path: Optional[Path] = None
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = log_dir / f"{stem}.discovery.stdout.log"
        stderr_path = log_dir / f"{stem}.discovery.stderr.log"

    proc = run_process_capture(command, cwd=workdir, timeout=timeout_sec)
    if stdout_path:
        stdout_path.write_text(proc["stdout"], encoding="utf-8", errors="replace")
        row["discovery_stdout_path"] = str(stdout_path)
    if stderr_path:
        stderr_path.write_text(proc["stderr"], encoding="utf-8", errors="replace")
        row["discovery_stderr_path"] = str(stderr_path)
    if framework == "cypress":
        row.update(classify_cypress_verify(proc))
    else:
        row.update(classify_playwright_discovery(proc))
    row["discovery_duration_sec"] = round(time.time() - started, 2)
    if cache:
        cache.set(test, repo_ctx, row)
    return row
