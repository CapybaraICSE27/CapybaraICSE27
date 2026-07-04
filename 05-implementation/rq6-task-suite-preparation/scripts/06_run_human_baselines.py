#!/usr/bin/env python3
"""Phase 1G: plan or execute human baseline runs for selected tests."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

LIB = Path(__file__).resolve().parents[1] / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from app_server import boot_app, terminate_process_tree  # noqa: E402
from common import (  # noqa: E402
    DEFAULT_OUT_DIR,
    configure_js_tool_env,
    iter_jsonl,
    load_repo_filter,
    prepare_subprocess_command,
    read_csv_rows,
    resolve_command_executable,
    row_matches_repo_filter,
    run_process_capture,
    to_int,
    write_csv,
    write_jsonl,
)
from test_discovery import DiscoveryCache, run_discovery_check, split_command_text  # noqa: E402


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidate-tests", type=Path, default=DEFAULT_OUT_DIR / "candidate_human_tests.jsonl")
    ap.add_argument("--runner-app", type=Path, default=DEFAULT_OUT_DIR / "repo_runner_app_results.jsonl")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--repos-file", type=Path, default=None, help="Optional repo_full_name/repo_cache_key filter.")
    ap.add_argument("--stable-runs", type=int, default=3)
    ap.add_argument("--timeout-sec", type=int, default=180)
    ap.add_argument("--app-boot-timeout-sec", type=int, default=120)
    ap.add_argument("--discovery-timeout-sec", type=int, default=45)
    ap.add_argument(
        "--pretest-setup-file",
        type=Path,
        default=None,
        help="Optional JSONL/CSV file of per-repo setup commands to run before human baselines.",
    )
    ap.add_argument(
        "--app-start-overrides-file",
        type=Path,
        default=None,
        help="Optional JSONL/CSV file of per-repo app start command overrides for baseline execution.",
    )
    ap.add_argument(
        "--pretest-setup-timeout-sec",
        type=int,
        default=300,
        help="Default timeout for each pre-test setup command.",
    )
    ap.add_argument(
        "--ensure-playwright-browsers",
        default="",
        help="Optional browser names to install with `npx playwright install` before pre-test setup, e.g. `chromium`.",
    )
    ap.add_argument(
        "--ensure-playwright-browsers-timeout-sec",
        type=int,
        default=900,
        help="Timeout for the optional Playwright browser install step.",
    )
    ap.add_argument(
        "--playwright-project",
        default="chromium",
        help="Optional Playwright project to run for smoke baselines. Use an empty value to let repo config run all projects.",
    )
    ap.add_argument("--max-tests", type=int, default=0, help="Optional cap for smoke execution.")
    ap.add_argument(
        "--resume",
        action="store_true",
        help="Keep existing run rows and skip already completed test attempts.",
    )
    ap.add_argument(
        "--rerun-failed",
        action="store_true",
        help="With --resume, rerun attempts that did not pass.",
    )
    ap.add_argument(
        "--tool-bin-dir",
        type=Path,
        default=None,
        help="Optional directory prepended to PATH inside Python, e.g. a portable Node bin directory.",
    )
    ap.add_argument(
        "--no-start-app",
        action="store_true",
        help="Do not start an app server before test execution.",
    )
    ap.add_argument(
        "--force-app-start",
        action="store_true",
        help="Start app server even when Playwright config has webServer.",
    )
    ap.add_argument(
        "--execute",
        action="store_true",
        help="Actually run test commands. Without this, writes planned baseline commands only.",
    )
    ap.add_argument(
        "--run-undiscoverable",
        action="store_true",
        help="Run tests even when cheap discovery fails. Default skips undiscoverable tests.",
    )
    return ap.parse_args()


def load_repo_context(path: Path) -> Dict[str, Dict[str, Any]]:
    return {str(r.get("repo_full_name") or ""): r for r in iter_jsonl(path)}


def parse_required_paths(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(v).strip().replace("\\", "/") for v in value if str(v).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = [part.strip() for part in text.split(";")]
    if not isinstance(parsed, list):
        return []
    return [str(v).strip().replace("\\", "/") for v in parsed if str(v).strip()]


def load_pretest_setup(path: Optional[Path]) -> Dict[str, List[Dict[str, Any]]]:
    if path is None or not path.exists():
        return {}
    if path.suffix.lower() == ".jsonl":
        rows = list(iter_jsonl(path))
    else:
        rows = list(read_csv_rows(path))
    out: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for idx, row in enumerate(rows, start=1):
        command = str(row.get("command") or "").strip()
        if not command:
            continue
        entry = {
            "setup_id": str(row.get("setup_id") or f"setup_{idx}"),
            "command": command,
            "cwd_rel": str(row.get("cwd_rel") or ".").strip() or ".",
            "timeout_sec": to_int(row.get("timeout_sec"), 0),
            "required_paths": parse_required_paths(
                row.get("required_paths")
                if "required_paths" in row
                else row.get("required_paths_json")
            ),
        }
        for key in {str(row.get("repo_full_name") or ""), str(row.get("repo_cache_key") or "")}:
            if key:
                out[key].append(entry)
    return dict(out)


def load_app_start_overrides(path: Optional[Path]) -> Dict[str, Dict[str, str]]:
    if path is None or not path.exists():
        return {}
    if path.suffix.lower() == ".jsonl":
        rows = list(iter_jsonl(path))
    else:
        rows = list(read_csv_rows(path))
    out: Dict[str, Dict[str, str]] = {}
    for row in rows:
        command = str(row.get("app_start_command") or "").strip()
        if not command:
            continue
        entry = {
            "app_start_command": command,
            "base_url": str(row.get("base_url") or "").strip(),
            "app_start_command_correction": str(
                row.get("app_start_command_correction") or "configured_app_start_override"
            ),
        }
        for key in {str(row.get("repo_full_name") or ""), str(row.get("repo_cache_key") or "")}:
            if key:
                out[key] = entry
    return out


def apply_app_start_override(repo_ctx: Dict[str, Any], override: Optional[Dict[str, str]]) -> None:
    if not override:
        return
    original = str(repo_ctx.get("app_start_command") or "")
    repo_ctx["app_start_command_original"] = original
    repo_ctx["app_start_command"] = override.get("app_start_command") or original
    if override.get("base_url"):
        repo_ctx["base_url"] = override["base_url"]
    repo_ctx["app_start_command_correction"] = override.get("app_start_command_correction") or "configured_app_start_override"


def path_within(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def required_paths_present(workdir: Path, required_paths: List[str]) -> bool:
    return bool(required_paths) and all((workdir / rel).exists() for rel in required_paths)


def playwright_browser_tokens(value: str) -> List[str]:
    return [part for part in re.split(r"[\s,;]+", str(value or "").strip()) if part]


def run_playwright_browser_setup_for_repo(
    repo: str,
    repo_ctx: Dict[str, Any],
    args: argparse.Namespace,
) -> Dict[str, Any]:
    browsers = playwright_browser_tokens(str(getattr(args, "ensure_playwright_browsers", "") or ""))
    if not browsers or str(repo_ctx.get("framework") or "").lower() != "playwright":
        return {
            "_playwright_browser_setup_status": "not_configured",
            "_playwright_browser_setup_error": "",
            "_playwright_browser_setup_duration_sec": 0.0,
            "_playwright_browser_setup_logs_json": "[]",
        }

    workdir = Path(str(repo_ctx.get("workdir_path") or repo_ctx.get("repo_cache_path") or ""))
    started = time.time()
    if not workdir.is_dir():
        return {
            "_playwright_browser_setup_status": "failed_missing_workdir",
            "_playwright_browser_setup_error": str(workdir),
            "_playwright_browser_setup_duration_sec": round(time.time() - started, 2),
            "_playwright_browser_setup_logs_json": "[]",
        }

    log_dir = args.out_dir / "logs" / "playwright_browsers"
    log_dir.mkdir(parents=True, exist_ok=True)
    repo_token = safe_run_token(repo_ctx.get("repo_cache_key") or repo)
    stdout_path = log_dir / f"{repo_token}_playwright_browsers.stdout.log"
    stderr_path = log_dir / f"{repo_token}_playwright_browsers.stderr.log"
    command = ["npx", "playwright", "install", *browsers]
    timeout_sec = to_int(getattr(args, "ensure_playwright_browsers_timeout_sec", 900), 900)
    if timeout_sec <= 0:
        timeout_sec = 900
    proc = run_process_capture(command, cwd=workdir, timeout=timeout_sec)
    stdout_path.write_text(proc["stdout"], encoding="utf-8", errors="replace")
    stderr_path.write_text(proc["stderr"], encoding="utf-8", errors="replace")

    status = "pass"
    error = ""
    if proc.get("timed_out"):
        status = "failed_timeout"
        error = f"timed out after {timeout_sec}s"
    elif proc.get("returncode") != 0:
        status = "failed_nonzero_exit"
        error = f"exit={proc.get('returncode')}"
    logs = [
        {
            "setup_id": "playwright_browsers",
            "status": status,
            "command": subprocess.list2cmdline(command),
            "timeout_sec": timeout_sec,
            "exit_code": proc.get("returncode"),
            "timed_out": bool(proc.get("timed_out")),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "browsers": browsers,
        }
    ]
    return {
        "_playwright_browser_setup_status": status,
        "_playwright_browser_setup_error": error,
        "_playwright_browser_setup_duration_sec": round(time.time() - started, 2),
        "_playwright_browser_setup_logs_json": json.dumps(logs, ensure_ascii=False),
    }


def playwright_browser_setup_failed(repo_ctx: Dict[str, Any]) -> bool:
    return str(repo_ctx.get("_playwright_browser_setup_status") or "").startswith("failed_")


def run_pretest_setup_for_repo(
    repo: str,
    repo_ctx: Dict[str, Any],
    setup_commands: List[Dict[str, Any]],
    args: argparse.Namespace,
) -> Dict[str, Any]:
    if not setup_commands:
        return {
            "_pretest_setup_status": "not_configured",
            "_pretest_setup_error": "",
            "_pretest_setup_duration_sec": 0.0,
            "_pretest_setup_logs_json": "[]",
        }
    workdir = Path(str(repo_ctx.get("workdir_path") or repo_ctx.get("repo_cache_path") or ""))
    started = time.time()
    command_logs: List[Dict[str, Any]] = []
    if not workdir.is_dir():
        return {
            "_pretest_setup_status": "failed_missing_workdir",
            "_pretest_setup_error": str(workdir),
            "_pretest_setup_duration_sec": round(time.time() - started, 2),
            "_pretest_setup_logs_json": "[]",
        }
    log_dir = args.out_dir / "logs" / "pretest_setup"
    log_dir.mkdir(parents=True, exist_ok=True)
    repo_token = safe_run_token(repo_ctx.get("repo_cache_key") or repo)

    for index, entry in enumerate(setup_commands, start=1):
        setup_id = safe_run_token(entry.get("setup_id") or f"setup_{index}")
        required_paths = list(entry.get("required_paths") or [])
        stdout_path = log_dir / f"{repo_token}_{setup_id}.stdout.log"
        stderr_path = log_dir / f"{repo_token}_{setup_id}.stderr.log"
        if required_paths_present(workdir, required_paths):
            command_logs.append(
                {
                    "setup_id": setup_id,
                    "status": "skipped_required_paths_present",
                    "stdout_path": "",
                    "stderr_path": "",
                    "required_paths": required_paths,
                }
            )
            continue

        cwd = (workdir / str(entry.get("cwd_rel") or ".")).resolve()
        if not path_within(workdir, cwd) or not cwd.is_dir():
            error = f"invalid setup cwd: {cwd}"
            stderr_path.write_text(error, encoding="utf-8", errors="replace")
            command_logs.append(
                {
                    "setup_id": setup_id,
                    "status": "failed_invalid_cwd",
                    "stdout_path": str(stdout_path),
                    "stderr_path": str(stderr_path),
                    "required_paths": required_paths,
                }
            )
            return {
                "_pretest_setup_status": "failed_invalid_cwd",
                "_pretest_setup_error": error,
                "_pretest_setup_duration_sec": round(time.time() - started, 2),
                "_pretest_setup_logs_json": json.dumps(command_logs, ensure_ascii=False),
            }

        command = split_command_text(str(entry.get("command") or ""))
        timeout_sec = to_int(entry.get("timeout_sec"), args.pretest_setup_timeout_sec)
        if timeout_sec <= 0:
            timeout_sec = args.pretest_setup_timeout_sec
        proc = run_process_capture(command, cwd=cwd, timeout=timeout_sec)
        stdout_path.write_text(proc["stdout"], encoding="utf-8", errors="replace")
        stderr_path.write_text(proc["stderr"], encoding="utf-8", errors="replace")
        status = "pass"
        error = ""
        if proc.get("timed_out"):
            status = "failed_timeout"
            error = f"timed out after {timeout_sec}s"
        elif proc.get("returncode") != 0:
            status = "failed_nonzero_exit"
            error = f"exit={proc.get('returncode')}"
        elif required_paths and not required_paths_present(workdir, required_paths):
            status = "failed_missing_required_paths"
            missing = [rel for rel in required_paths if not (workdir / rel).exists()]
            error = "missing: " + ", ".join(missing)

        command_logs.append(
            {
                "setup_id": setup_id,
                "status": status,
                "command": subprocess.list2cmdline(command),
                "cwd_rel": str(entry.get("cwd_rel") or "."),
                "timeout_sec": timeout_sec,
                "exit_code": proc.get("returncode"),
                "timed_out": bool(proc.get("timed_out")),
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
                "required_paths": required_paths,
            }
        )
        if status != "pass":
            return {
                "_pretest_setup_status": status,
                "_pretest_setup_error": error,
                "_pretest_setup_duration_sec": round(time.time() - started, 2),
                "_pretest_setup_logs_json": json.dumps(command_logs, ensure_ascii=False),
            }

    return {
        "_pretest_setup_status": "pass",
        "_pretest_setup_error": "",
        "_pretest_setup_duration_sec": round(time.time() - started, 2),
        "_pretest_setup_logs_json": json.dumps(command_logs, ensure_ascii=False),
    }


def command_for(test: Dict[str, Any], repo_ctx: Dict[str, Any], playwright_project: str = "") -> List[str]:
    base = split_command_text(repo_ctx.get("runner_command_base"))
    file_path = str(test.get("file_path") or "")
    test_name = str(test.get("test_name") or "")
    framework = str(test.get("framework") or "")
    if framework == "playwright":
        command = base + [file_path]
        if str(test.get("execution_scope") or "") == "test_title" and test_name:
            command.extend(["-g", test_name])
        if str(playwright_project or "").strip():
            command.extend(["--project", str(playwright_project).strip()])
        command.append("--reporter=json")
        return command
    if framework == "cypress":
        return base + ["--spec", file_path]
    return base


def safe_run_token(value: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or ""))
    return text[:160].strip("_") or "target"


def run_id_for(test: Dict[str, Any], attempt: int) -> str:
    target_id = str(test.get("execution_target_id") or test.get("test_id") or "")
    return f"rq6_human_{safe_run_token(test.get('repo_cache_key'))}_{safe_run_token(target_id)}_run{attempt:02d}"


def execution_scope_for(test: Dict[str, Any], repo_ctx: Dict[str, Any]) -> str:
    framework = str(test.get("framework") or repo_ctx.get("framework") or "").lower()
    if framework == "playwright" and repo_ctx.get("supports_test_title_filter") and str(test.get("test_name") or "").strip():
        return "test_title"
    if framework in {"playwright", "cypress"}:
        return "spec_file"
    return "runner_default"


def execution_target_id_for(test: Dict[str, Any], repo_ctx: Dict[str, Any]) -> str:
    scope = execution_scope_for(test, repo_ctx)
    if scope == "spec_file":
        return "spec::" + str(test.get("file_path") or "")
    return str(test.get("test_id") or test.get("file_path") or "")


def build_execution_targets(selected: List[Dict[str, Any]], repo_ctx: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    targets: Dict[str, Dict[str, Any]] = {}
    for test in selected:
        repo = str(test.get("repo_full_name") or "")
        ctx = repo_ctx.get(repo, {})
        scope = execution_scope_for(test, ctx)
        target_id = execution_target_id_for(test, ctx)
        key = "|".join([repo, scope, target_id])
        if key not in targets:
            target = dict(test)
            target["execution_scope"] = scope
            target["execution_target_id"] = target_id
            target["representative_test_id"] = test.get("test_id")
            target["_represented_test_ids"] = []
            target["_represented_test_names"] = []
            if scope == "spec_file":
                target["test_id"] = target_id
                target["test_name"] = ""
            targets[key] = target
        target = targets[key]
        represented_ids = target.setdefault("_represented_test_ids", [])
        represented_names = target.setdefault("_represented_test_names", [])
        test_id = str(test.get("test_id") or "")
        test_name = str(test.get("test_name") or "")
        if test_id and test_id not in represented_ids:
            represented_ids.append(test_id)
        if test_name and test_name not in represented_names:
            represented_names.append(test_name)

    out: List[Dict[str, Any]] = []
    for target in targets.values():
        ids = list(target.pop("_represented_test_ids", []))
        names = list(target.pop("_represented_test_names", []))
        target["represented_test_count"] = len(ids) or 1
        target["represented_test_ids_json"] = json.dumps(ids, ensure_ascii=False)
        target["represented_test_names_json"] = json.dumps(names, ensure_ascii=False)
        out.append(target)
    out.sort(
        key=lambda r: (
            str(r.get("repo_full_name") or ""),
            str(r.get("execution_scope") or ""),
            str(r.get("file_path") or ""),
            str(r.get("execution_target_id") or ""),
        )
    )
    return out


def run_key(row: Dict[str, Any]) -> str:
    return "|".join(
        [
            str(row.get("repo_full_name") or ""),
            str(row.get("execution_target_id") or row.get("test_id") or ""),
            str(row.get("attempt_index") or ""),
        ]
    )


def load_existing_runs(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for row in iter_jsonl(path):
        key = run_key(row)
        if key.strip("|"):
            out[key] = row
    return out


def should_keep_existing(row: Dict[str, Any], args: argparse.Namespace) -> bool:
    if not args.resume:
        return False
    if args.rerun_failed:
        return bool(row.get("passed_once"))
    return True


def classify_executed_result(row: Dict[str, Any], proc: Dict[str, Any]) -> Dict[str, Any]:
    stdout = str(proc.get("stdout") or "")
    stderr = str(proc.get("stderr") or "")
    combined = f"{stdout}\n{stderr}".lower()
    if proc["returncode"] == 0:
        return {"discovered": True, "passed_once": True, "failure_category": None, "status": "pass"}
    if str(row.get("framework") or "").lower() == "playwright" and (
        "no tests found" in combined or "did not find any tests" in combined
    ):
        return {
            "discovered": False,
            "passed_once": False,
            "failure_category": "test_not_discovered",
            "status": "test_not_discovered",
        }
    return {"discovered": row.get("discovered"), "passed_once": False, "failure_category": None, "status": "test_failed"}


def should_start_app(test: Dict[str, Any], repo_ctx: Dict[str, Any], args: argparse.Namespace) -> bool:
    if args.no_start_app:
        return False
    if not repo_ctx.get("app_start_command"):
        return False
    if args.force_app_start:
        return True
    framework = str(test.get("framework") or repo_ctx.get("framework") or "")
    detected_from = str(repo_ctx.get("app_detected_from") or "")
    if framework == "playwright" and detected_from == "playwright_config_webServer":
        return False
    return True


def row_boot_fields(boot: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in boot.items() if key != "_process"}


def run_once(
    test: Dict[str, Any],
    repo_ctx: Dict[str, Any],
    attempt: int,
    args: argparse.Namespace,
    *,
    discovery_cache: Optional[DiscoveryCache] = None,
    shared_app_boot: Optional[Dict[str, Any]] = None,
    precomputed_discovery: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    command = command_for(test, repo_ctx, args.playwright_project)
    workdir = Path(str(repo_ctx.get("workdir_path") or repo_ctx.get("repo_cache_path") or ""))
    target_id = str(test.get("execution_target_id") or test.get("test_id") or "")
    run_id = run_id_for(test, attempt)
    row = {
        "run_id": run_id,
        "repo_full_name": test.get("repo_full_name"),
        "repo_cache_key": test.get("repo_cache_key"),
        "test_id": test.get("test_id"),
        "execution_scope": test.get("execution_scope"),
        "execution_target_id": target_id,
        "representative_test_id": test.get("representative_test_id"),
        "represented_test_count": test.get("represented_test_count"),
        "represented_test_ids_json": test.get("represented_test_ids_json"),
        "represented_test_names_json": test.get("represented_test_names_json"),
        "framework": test.get("framework"),
        "file_path": test.get("file_path"),
        "test_name": test.get("test_name"),
        "command": subprocess.list2cmdline(command),
        "app_start_command": repo_ctx.get("app_start_command"),
        "app_start_command_original": repo_ctx.get("app_start_command_original", ""),
        "app_start_command_correction": repo_ctx.get("app_start_command_correction", ""),
        "source_provenance": repo_ctx.get("source_provenance"),
        "phase2_commit_alignment": repo_ctx.get("phase2_commit_alignment"),
        "source_snapshot_sha256": repo_ctx.get("source_snapshot_sha256"),
        "playwright_browser_setup_status": repo_ctx.get("_playwright_browser_setup_status", "not_configured"),
        "playwright_browser_setup_error": repo_ctx.get("_playwright_browser_setup_error", ""),
        "playwright_browser_setup_duration_sec": repo_ctx.get("_playwright_browser_setup_duration_sec", 0.0),
        "playwright_browser_setup_logs_json": repo_ctx.get("_playwright_browser_setup_logs_json", "[]"),
        "pretest_setup_status": repo_ctx.get("_pretest_setup_status", "not_configured"),
        "pretest_setup_error": repo_ctx.get("_pretest_setup_error", ""),
        "pretest_setup_duration_sec": repo_ctx.get("_pretest_setup_duration_sec", 0.0),
        "pretest_setup_logs_json": repo_ctx.get("_pretest_setup_logs_json", "[]"),
        "app_boot_checked": False,
        "app_boot_ok": None,
        "app_boot_status": "not_checked",
        "app_boot_url": "",
        "app_boot_error": "",
        "app_process_returncode": None,
        "app_http_status": None,
        "app_stdout_path": "",
        "app_stderr_path": "",
        "discovered": None,
        "executed": None,
        "passed_once": False,
        "exit_code": None,
        "duration_sec": 0.0,
        "failure_category": None,
        "stdout_path": "",
        "stderr_path": "",
        "reporter_json_path": "",
        "discovery_command": "",
        "discovery_status": "not_checked",
        "discovery_duration_sec": 0.0,
        "discovery_stdout_path": "",
        "discovery_stderr_path": "",
        "discovery_cache_hit": False,
        "attempt_index": attempt,
        "status": "planned_baseline" if not args.execute else "",
    }
    if not args.execute:
        return row
    if not command or not workdir.is_dir():
        row["status"] = "missing_command_or_workdir"
        return row
    if playwright_browser_setup_failed(repo_ctx):
        row["executed"] = False
        row["failure_category"] = str(row.get("playwright_browser_setup_status") or "playwright_browser_setup_failed")
        row["status"] = "playwright_browser_setup_failed"
        return row
    if str(row.get("pretest_setup_status") or "") in {
        "failed_missing_workdir",
        "failed_invalid_cwd",
        "failed_timeout",
        "failed_nonzero_exit",
        "failed_missing_required_paths",
    }:
        row["executed"] = False
        row["failure_category"] = str(row.get("pretest_setup_status") or "pretest_setup_failed")
        row["status"] = "pretest_setup_failed"
        return row
    resolved_command = prepare_subprocess_command(command, cwd=workdir)
    if not resolved_command or not resolve_command_executable(resolved_command[0], cwd=workdir):
        row["status"] = "runtime_command_not_found"
        row["failure_category"] = "runtime_command_not_found"
        return row

    log_dir = args.out_dir / "logs" / "baseline"
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / f"{run_id}.stdout.log"
    stderr_path = log_dir / f"{run_id}.stderr.log"
    started = time.time()
    app_proc = None
    try:
        discovery = precomputed_discovery
        if discovery is None:
            discovery = run_discovery_check(
                test,
                repo_ctx,
                timeout_sec=args.discovery_timeout_sec,
                log_dir=log_dir,
                stem=run_id,
                cache=discovery_cache,
            )
        row.update(discovery)
        if not args.run_undiscoverable and discovery.get("discovered") is False:
            row.update(
                {
                    "duration_sec": round(time.time() - started, 2),
                    "failure_category": discovery.get("discovery_failure_category") or discovery.get("discovery_status"),
                    "status": discovery.get("discovery_status") or "test_not_discovered",
                }
            )
            return row
        if should_start_app(test, repo_ctx, args):
            if shared_app_boot is not None:
                row.update(row_boot_fields(shared_app_boot))
            else:
                boot = boot_app(
                    command=str(repo_ctx.get("app_start_command") or ""),
                    cwd=workdir,
                    base_url=str(repo_ctx.get("base_url") or ""),
                    log_dir=log_dir,
                    stem=run_id,
                    timeout_sec=args.app_boot_timeout_sec,
                )
                app_proc = boot.pop("_process", None)
                row.update(boot)
            if not row.get("app_boot_ok"):
                row.update(
                    {
                        "duration_sec": round(time.time() - started, 2),
                        "failure_category": str(row.get("app_boot_status") or "app_boot_failed"),
                        "status": str(row.get("app_boot_status") or "app_boot_failed"),
                    }
                )
                return row
        proc = run_process_capture(resolved_command, cwd=workdir, timeout=args.timeout_sec)
        stdout_path.write_text(proc["stdout"], encoding="utf-8", errors="replace")
        stderr_path.write_text(proc["stderr"], encoding="utf-8", errors="replace")
        if proc["timed_out"]:
            row.update(
                {
                    "executed": True,
                    "duration_sec": round(time.time() - started, 2),
                    "failure_category": "test_timeout",
                    "stdout_path": str(stdout_path),
                    "stderr_path": str(stderr_path),
                    "status": "test_timeout",
                }
            )
            return row
        row.update(
            {
                "executed": True,
                "exit_code": proc["returncode"],
                "duration_sec": round(time.time() - started, 2),
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
            }
        )
        row.update(classify_executed_result(row, proc))
    except FileNotFoundError as exc:
        stderr_path.write_text(str(exc), encoding="utf-8", errors="replace")
        row.update(
            {
                "duration_sec": round(time.time() - started, 2),
                "failure_category": "runtime_command_not_found",
                "stderr_path": str(stderr_path),
                "status": "runtime_command_not_found",
            }
        )
    finally:
        terminate_process_tree(app_proc)
    return row


def main() -> None:
    args = parse_args()
    tool_env = configure_js_tool_env(tool_bin_dir=args.tool_bin_dir, cache_root=args.out_dir / "tool_cache")
    repo_ctx = load_repo_context(args.runner_app)
    pretest_setup = load_pretest_setup(args.pretest_setup_file)
    app_start_overrides = load_app_start_overrides(args.app_start_overrides_file)
    repo_filter = load_repo_filter(args.repos_file)
    selected = [
        r
        for r in iter_jsonl(args.candidate_tests)
        if r.get("selected_for_baseline_attempt") and row_matches_repo_filter(r, repo_filter)
    ]
    targets = build_execution_targets(selected, repo_ctx)
    if args.max_tests and args.max_tests > 0:
        targets = targets[: args.max_tests]
    existing = load_existing_runs(args.out_dir / "human_test_baseline_runs.jsonl") if args.resume else {}
    runs: List[Dict[str, Any]] = []
    reused_existing = 0
    discovery_cache = DiscoveryCache()
    by_repo: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for target in targets:
        by_repo[str(target.get("repo_full_name") or "")].append(target)
    for repo in sorted(by_repo):
        repo_targets = by_repo[repo]
        ctx = dict(repo_ctx.get(repo, {}))
        app_override = app_start_overrides.get(repo) or app_start_overrides.get(str(ctx.get("repo_cache_key") or ""))
        apply_app_start_override(ctx, app_override)
        if args.execute:
            browser_setup_result = run_playwright_browser_setup_for_repo(repo, ctx, args)
            ctx.update(browser_setup_result)
        setup_commands = pretest_setup.get(repo) or pretest_setup.get(str(ctx.get("repo_cache_key") or "")) or []
        if args.execute and setup_commands and not playwright_browser_setup_failed(ctx):
            setup_result = run_pretest_setup_for_repo(repo, ctx, setup_commands, args)
            ctx.update(setup_result)
        for attempt in range(1, max(1, args.stable_runs) + 1):
            pending: List[Dict[str, Any]] = []
            for test in repo_targets:
                planned_key = "|".join(
                    [
                        str(test.get("repo_full_name") or ""),
                        str(test.get("execution_target_id") or test.get("test_id") or ""),
                        str(attempt),
                    ]
                )
                existing_row = existing.get(planned_key)
                if existing_row and should_keep_existing(existing_row, args):
                    runs.append(existing_row)
                    reused_existing += 1
                else:
                    pending.append(test)
            shared_boot: Optional[Dict[str, Any]] = None
            try:
                runnable_pending: List[tuple[Dict[str, Any], Optional[Dict[str, Any]]]] = [
                    (test, None) for test in pending
                ]
                if args.execute and pending and not args.run_undiscoverable:
                    log_dir = args.out_dir / "logs" / "baseline"
                    runnable_pending = []
                    for test in pending:
                        discovery = run_discovery_check(
                            test,
                            ctx,
                            timeout_sec=args.discovery_timeout_sec,
                            log_dir=log_dir,
                            stem=run_id_for(test, attempt),
                            cache=discovery_cache,
                        )
                        if discovery.get("discovered") is False:
                            runs.append(
                                run_once(
                                    test,
                                    ctx,
                                    attempt,
                                    args,
                                    discovery_cache=discovery_cache,
                                    precomputed_discovery=discovery,
                                )
                            )
                        else:
                            runnable_pending.append((test, discovery))
                pending_for_boot = [test for test, _ in runnable_pending]
                if args.execute and pending_for_boot and any(should_start_app(test, ctx, args) for test in pending_for_boot):
                    workdir = Path(str(ctx.get("workdir_path") or ctx.get("repo_cache_path") or ""))
                    shared_boot = boot_app(
                        command=str(ctx.get("app_start_command") or ""),
                        cwd=workdir,
                        base_url=str(ctx.get("base_url") or ""),
                        log_dir=args.out_dir / "logs" / "baseline",
                        stem=f"rq6_app_{safe_run_token(ctx.get('repo_cache_key') or repo)}_run{attempt:02d}",
                        timeout_sec=args.app_boot_timeout_sec,
                    )
                for test, discovery in runnable_pending:
                    runs.append(
                        run_once(
                            test,
                            ctx,
                            attempt,
                            args,
                            discovery_cache=discovery_cache,
                            shared_app_boot=shared_boot,
                            precomputed_discovery=discovery,
                        )
                    )
            finally:
                terminate_process_tree(shared_boot.get("_process") if shared_boot else None)
    write_jsonl(args.out_dir / "human_test_baseline_runs.jsonl", runs)
    write_csv(args.out_dir / "human_test_baseline_runs_summary.csv", runs)
    print(
        json.dumps(
            {
                "runs": len(runs),
                "selected_tests": len(selected),
                "execution_targets": len(targets),
                "reused_existing": reused_existing,
                "execute": bool(args.execute),
                "tool_bin_dir": tool_env.get("tool_bin_dir", ""),
                "tool_cache_dir": str(args.out_dir / "tool_cache"),
                "out_dir": str(args.out_dir),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
