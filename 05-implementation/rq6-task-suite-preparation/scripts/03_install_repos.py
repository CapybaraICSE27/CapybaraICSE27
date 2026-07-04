#!/usr/bin/env python3
"""Phase 1C: install isolated candidate workdirs from lockfiles."""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List

LIB = Path(__file__).resolve().parents[1] / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from common import (  # noqa: E402
    DEFAULT_OUT_DIR,
    configure_js_tool_env,
    iter_jsonl,
    load_repo_filter,
    prepare_subprocess_command,
    resolve_command_executable,
    row_matches_repo_filter,
    run_process_capture,
    write_csv,
    write_jsonl,
)
from install_validation import (  # noqa: E402
    INSTALL_VALIDATION_SCHEMA,
    dependency_tree_present,
    install_row_schema_current,
)
from package_manager import install_command  # noqa: E402


def command_with_local_cache(command: List[str], out_dir: Path) -> List[str]:
    if command and command[0] == "pnpm":
        store_dir = (out_dir / "tool_cache" / "pnpm-store").resolve()
        store_dir.mkdir(parents=True, exist_ok=True)
        return command + ["--store-dir", str(store_dir)]
    return command


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo-env", type=Path, default=DEFAULT_OUT_DIR / "repo_environment.jsonl")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--repos-file", type=Path, default=None, help="Optional repo_full_name/repo_cache_key filter.")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--timeout-sec", type=int, default=600)
    ap.add_argument("--max-repos", type=int, default=0, help="Optional cap for install smoke tests.")
    ap.add_argument(
        "--resume",
        action="store_true",
        help="Keep existing install rows and skip already completed repos.",
    )
    ap.add_argument(
        "--rerun-failed",
        action="store_true",
        help="With --resume, rerun repos whose previous install did not pass.",
    )
    ap.add_argument(
        "--tool-bin-dir",
        type=Path,
        default=None,
        help="Optional directory prepended to PATH inside Python, e.g. a portable Node bin directory.",
    )
    ap.add_argument(
        "--execute",
        action="store_true",
        help="Actually run package-manager install commands. Without this, writes planned_install rows only.",
    )
    ap.add_argument(
        "--allow-repo-cache-install",
        action="store_true",
        help="Permit installing directly in the shared repo cache. Default requires isolated workdir_path.",
    )
    return ap.parse_args()


def install_key(row: Dict[str, Any]) -> str:
    return str(row.get("repo_cache_key") or row.get("repo_full_name") or "")


def load_existing_results(*paths: Path) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for path in paths:
        if not path.exists():
            continue
        for row in iter_jsonl(path):
            key = install_key(row)
            if key:
                out[key] = row
    return out


def should_keep_existing(row: Dict[str, Any], args: argparse.Namespace) -> bool:
    if not args.resume:
        return False
    if not install_row_schema_current(row):
        return False
    if args.rerun_failed:
        return bool(row.get("install_ok")) and bool(row.get("dependency_tree_present"))
    return True


def install_one(row: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    command = command_with_local_cache(
        install_command(str(row.get("package_manager") or ""), str(row.get("yarn_variant") or "")),
        args.out_dir,
    )
    workdir = Path(str(row.get("workdir_path") or ""))
    if not workdir.exists() and args.allow_repo_cache_install:
        workdir = Path(str(row.get("repo_cache_path") or ""))

    result = {
        "stage": "install",
        "repo_full_name": row.get("repo_full_name"),
        "repo_cache_key": row.get("repo_cache_key"),
        "framework_primary": row.get("framework_primary"),
        "source_provenance": row.get("source_provenance"),
        "phase2_commit_alignment": row.get("phase2_commit_alignment"),
        "source_snapshot_sha256": row.get("source_snapshot_sha256"),
        "workdir_path": str(workdir) if workdir else "",
        "install_command": " ".join(command),
        "prepared_install_command": "",
        "install_validation_schema": INSTALL_VALIDATION_SCHEMA,
        "dependency_tree_present": False,
        "install_ok": False,
        "duration_sec": 0.0,
        "exit_code": None,
        "stdout_path": "",
        "stderr_path": "",
        "status": "planned_install" if not args.execute else "",
    }
    if not command:
        result["status"] = "unsupported_package_manager"
        return result
    if not workdir or not workdir.is_dir():
        result["status"] = "missing_isolated_workdir"
        return result
    if not args.execute:
        return result

    resolved_command = prepare_subprocess_command(command, cwd=workdir)
    result["prepared_install_command"] = " ".join(resolved_command)
    if not resolved_command or not resolve_command_executable(resolved_command[0], cwd=workdir):
        result.update(
            {
                "status": "runtime_command_not_found",
                "exit_code": None,
            }
        )
        return result

    log_dir = args.out_dir / "logs" / "install"
    log_dir.mkdir(parents=True, exist_ok=True)
    stem = str(row.get("repo_cache_key") or "repo")
    stdout_path = log_dir / f"{stem}.stdout.log"
    stderr_path = log_dir / f"{stem}.stderr.log"
    started = time.time()
    try:
        proc = run_process_capture(resolved_command, cwd=workdir, timeout=args.timeout_sec)
        stdout_path.write_text(proc["stdout"], encoding="utf-8", errors="replace")
        stderr_path.write_text(proc["stderr"], encoding="utf-8", errors="replace")
        if proc["timed_out"]:
            result.update(
                {
                    "duration_sec": round(time.time() - started, 2),
                    "stdout_path": str(stdout_path),
                    "stderr_path": str(stderr_path),
                    "status": "install_timeout",
                }
            )
            return result
        has_dependency_tree = dependency_tree_present(workdir)
        install_ok = proc["returncode"] == 0 and has_dependency_tree
        status = "pass" if install_ok else "install_failed_lockfile"
        if proc["returncode"] == 0 and not has_dependency_tree:
            status = "install_missing_dependency_tree"
        result.update(
            {
                "dependency_tree_present": has_dependency_tree,
                "install_ok": install_ok,
                "exit_code": proc["returncode"],
                "duration_sec": round(time.time() - started, 2),
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
                "status": status,
            }
        )
    except FileNotFoundError as exc:
        stderr_path.write_text(str(exc), encoding="utf-8", errors="replace")
        result.update(
            {
                "duration_sec": round(time.time() - started, 2),
                "stderr_path": str(stderr_path),
                "status": "runtime_command_not_found",
            }
        )
    return result


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    tool_env = configure_js_tool_env(tool_bin_dir=args.tool_bin_dir, cache_root=args.out_dir / "tool_cache")
    repo_filter = load_repo_filter(args.repos_file)
    rows = [
        r
        for r in iter_jsonl(args.repo_env)
        if str(r.get("status") or "").startswith("pass") and row_matches_repo_filter(r, repo_filter)
    ]
    if args.max_repos and args.max_repos > 0:
        rows = rows[: args.max_repos]
    existing = (
        load_existing_results(args.out_dir / "repo_install_results.jsonl", args.out_dir / "repo_install_results.partial.jsonl")
        if args.resume
        else {}
    )
    retained: List[Dict[str, Any]] = []
    rows_to_run: List[Dict[str, Any]] = []
    for row in rows:
        existing_row = existing.get(install_key(row))
        if existing_row and should_keep_existing(existing_row, args):
            retained.append(existing_row)
        else:
            rows_to_run.append(row)
    workers = max(1, int(args.workers or 1))
    results: List[Dict[str, Any]] = list(retained)
    partial_path = args.out_dir / "repo_install_results.partial.jsonl"
    write_jsonl(partial_path, results)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(install_one, row, args) for row in rows_to_run]
        for fut in as_completed(futures):
            result = fut.result()
            results.append(result)
            with partial_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
    results.sort(key=lambda r: str(r.get("repo_full_name") or ""))
    write_jsonl(args.out_dir / "repo_install_results.jsonl", results)
    write_csv(
        args.out_dir / "repo_install_summary.csv",
        [
            {
                "repo_full_name": r.get("repo_full_name"),
                "repo_cache_key": r.get("repo_cache_key"),
                "install_ok": r.get("install_ok"),
                "install_validation_schema": r.get("install_validation_schema"),
                "dependency_tree_present": r.get("dependency_tree_present"),
                "install_command": r.get("install_command"),
                "prepared_install_command": r.get("prepared_install_command"),
                "source_provenance": r.get("source_provenance"),
                "duration_sec": r.get("duration_sec"),
                "status": r.get("status"),
            }
            for r in results
        ],
    )
    print(
        json.dumps(
            {
                "repos": len(results),
                "reused_existing": len(retained),
                "attempted": len(rows_to_run),
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
