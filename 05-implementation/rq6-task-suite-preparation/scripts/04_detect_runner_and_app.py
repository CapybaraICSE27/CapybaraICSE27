#!/usr/bin/env python3
"""Phase 1D/1E: statically detect test runner and local app boot candidates."""

from __future__ import annotations

import argparse
import json
import sys
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
    normalize_framework,
    row_matches_repo_filter,
    write_csv,
    write_jsonl,
)
from app_server import boot_app, concrete_local_url, terminate_process_tree  # noqa: E402
from install_validation import install_row_is_current_success  # noqa: E402
from package_manager import load_package_json  # noqa: E402
from runner_detection import detect_app, detect_runner  # noqa: E402


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo-env", type=Path, default=DEFAULT_OUT_DIR / "repo_environment.jsonl")
    ap.add_argument("--install-results", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--repos-file", type=Path, default=None, help="Optional repo_full_name/repo_cache_key filter.")
    ap.add_argument(
        "--tool-bin-dir",
        type=Path,
        default=None,
        help="Optional directory prepended to PATH inside Python, e.g. a portable Node bin directory.",
    )
    ap.add_argument(
        "--check-app-boot",
        action="store_true",
        help="Actually start detected app commands and wait for local HTTP readiness.",
    )
    ap.add_argument("--app-boot-timeout-sec", type=int, default=120)
    ap.add_argument(
        "--require-install-pass",
        action="store_true",
        help="Only detect runner/app for repos with a current validated install pass in --install-results.",
    )
    return ap.parse_args()


def load_installed(path: Path | None) -> set[str]:
    if not path or not path.exists():
        return set()
    return {str(row.get("repo_cache_key") or "") for row in iter_jsonl(path) if install_row_is_current_success(row)}


def status_for(row: Dict[str, Any], *, check_app_boot: bool = False) -> str:
    if not row.get("runner_identified"):
        return "runner_not_identified"
    if row.get("production_base_url_only") and not row.get("runner_managed_app_possible"):
        return "production_base_url_only"
    if not row.get("app_start_command") and not row.get("base_url"):
        if row.get("framework") == "playwright" and row.get("runner_managed_app_possible"):
            return "pass"
        return "no_local_base_url"
    if check_app_boot and not row.get("app_boot_ok"):
        return str(row.get("app_boot_status") or "app_boot_failed")
    return "pass"


def main() -> None:
    args = parse_args()
    tool_env = configure_js_tool_env(tool_bin_dir=args.tool_bin_dir, cache_root=args.out_dir / "tool_cache")
    installed = load_installed(args.install_results)
    repo_filter = load_repo_filter(args.repos_file)
    results: List[Dict[str, Any]] = []
    for env in iter_jsonl(args.repo_env):
        if not row_matches_repo_filter(env, repo_filter):
            continue
        if not str(env.get("status") or "").startswith("pass"):
            continue
        if args.require_install_pass and str(env.get("repo_cache_key") or "") not in installed:
            continue
        repo_dir = Path(str(env.get("workdir_path") or env.get("repo_cache_path") or ""))
        package_json = load_package_json(repo_dir)
        framework = normalize_framework(env.get("framework_primary"))
        runner = detect_runner(
            repo_dir,
            framework=framework,
            package_manager=str(env.get("package_manager") or ""),
            package_json=package_json,
        )
        app = detect_app(
            repo_dir,
            framework=framework,
            runner_config=str(runner.get("runner_config") or ""),
            package_json=package_json,
            package_manager=str(env.get("package_manager") or ""),
        )
        row = {**env, "stage": "runner_app_detect", **runner, **app}
        row["base_url"] = concrete_local_url(str(row.get("base_url") or ""))
        row["app_boot_checked"] = False
        row["app_boot_status"] = "not_checked"
        if args.check_app_boot and status_for(row) == "pass":
            stem = str(row.get("repo_cache_key") or "repo")
            boot = boot_app(
                command=str(row.get("app_start_command") or ""),
                cwd=repo_dir,
                base_url=str(row.get("base_url") or ""),
                log_dir=args.out_dir / "logs" / "app_boot",
                stem=stem,
                timeout_sec=args.app_boot_timeout_sec,
            )
            proc = boot.pop("_process", None)
            row.update(boot)
            terminate_process_tree(proc)
        row["status"] = status_for(row, check_app_boot=args.check_app_boot)
        results.append(row)

    write_jsonl(args.out_dir / "repo_runner_app_results.jsonl", results)
    write_csv(
        args.out_dir / "repo_runner_app_summary.csv",
        [
            {
                "repo_full_name": r.get("repo_full_name"),
                "repo_cache_key": r.get("repo_cache_key"),
                "framework": r.get("framework"),
                "runner_identified": r.get("runner_identified"),
                "runner_command_base": r.get("runner_command_base"),
                "runner_config": r.get("runner_config"),
                "app_start_command": r.get("app_start_command"),
                "app_detection_basis": r.get("app_detection_basis"),
                "base_url_detection_basis": r.get("base_url_detection_basis"),
                "runner_managed_app_possible": r.get("runner_managed_app_possible"),
                "app_script_name": r.get("app_script_name"),
                "app_script_command": r.get("app_script_command"),
                "app_script_selection_reason": r.get("app_script_selection_reason"),
                "base_url": r.get("base_url"),
                "local_base_url": r.get("local_base_url"),
                "app_boot_checked": r.get("app_boot_checked"),
                "app_boot_ok": r.get("app_boot_ok"),
                "app_boot_status": r.get("app_boot_status"),
                "app_boot_error": r.get("app_boot_error"),
                "app_process_returncode": r.get("app_process_returncode"),
                "app_http_status": r.get("app_http_status"),
                "source_provenance": r.get("source_provenance"),
                "status": r.get("status"),
            }
            for r in results
        ],
    )
    print(
        json.dumps(
            {
                "repos": len(results),
                "tool_bin_dir": tool_env.get("tool_bin_dir", ""),
                "tool_cache_dir": str(args.out_dir / "tool_cache"),
                "out_dir": str(args.out_dir),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
