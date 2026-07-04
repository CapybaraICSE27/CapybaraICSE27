#!/usr/bin/env python3
"""Phase 1F: select candidate human tests for baseline execution."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

LIB = Path(__file__).resolve().parents[1] / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from common import (  # noqa: E402
    DEFAULT_OUT_DIR,
    DEFAULT_PHASE2_RUN_DIR,
    configure_js_tool_env,
    is_executable_test_case,
    is_skipped_test,
    iter_jsonl,
    load_csv_by_test_id,
    normalize_framework,
    parse_bool,
    require_inputs,
    load_repo_filter,
    row_matches_repo_filter,
    to_float,
    to_int,
    write_csv,
    write_jsonl,
)
from test_discovery import DiscoveryCache, run_discovery_check  # noqa: E402


STRING_PROP_RE_TEMPLATE = r"\b{prop}\s*:\s*['\"]([^'\"]+)['\"]"


def safe_log_token(value: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or ""))
    return text[:160].strip("_") or "target"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--phase2-run-dir", type=Path, default=DEFAULT_PHASE2_RUN_DIR)
    ap.add_argument("--runnable-repos", type=Path, default=DEFAULT_OUT_DIR / "repo_runner_app_results.jsonl")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--repos-file", type=Path, default=None, help="Optional repo_full_name/repo_cache_key filter.")
    ap.add_argument("--max-tests-per-repo", type=int, default=8)
    ap.add_argument(
        "--verify-discovery",
        dest="verify_discovery",
        action="store_true",
        default=True,
        help="Run cheap runner-level discovery checks and keep only discoverable Playwright/Cypress tests.",
    )
    ap.add_argument(
        "--skip-discovery-verify",
        dest="verify_discovery",
        action="store_false",
        help="Skip runner-level discovery checks. This is faster but weaker and is not recommended for pilot runs.",
    )
    ap.add_argument("--discovery-timeout-sec", type=int, default=45)
    ap.add_argument(
        "--tool-bin-dir",
        type=Path,
        default=None,
        help="Optional directory prepended to PATH inside Python, e.g. a portable Node bin directory.",
    )
    ap.add_argument(
        "--include-nonpass-repos",
        action="store_true",
        help="Include repos whose runner/app static detection did not pass. Default excludes them.",
    )
    return ap.parse_args()


def load_runnable_repos(path: Path, require_pass: bool) -> Dict[str, Dict[str, Any]]:
    repos: Dict[str, Dict[str, Any]] = {}
    for row in iter_jsonl(path):
        if require_pass and row.get("status") != "pass":
            continue
        repo = str(row.get("repo_full_name") or "")
        if repo:
            repos[repo] = row
    return repos


def read_small_text(path: Path, limit: int = 500_000) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def simple_config_string_prop(config_text: str, prop: str) -> str:
    pattern = re.compile(STRING_PROP_RE_TEMPLATE.format(prop=re.escape(prop)))
    match = pattern.search(config_text)
    return match.group(1) if match else ""


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def runner_scope(test: Dict[str, Any], repo_ctx: Dict[str, Any]) -> Dict[str, str]:
    workdir = Path(str(repo_ctx.get("workdir_path") or repo_ctx.get("repo_cache_path") or ""))
    file_path = Path(str(test.get("file_path") or ""))
    abs_file = workdir / file_path
    if not workdir.is_dir():
        return {"runner_scope_status": "missing_workdir", "runner_test_dir": ""}
    if not abs_file.is_file():
        return {"runner_scope_status": "file_missing_in_workdir", "runner_test_dir": ""}

    framework = normalize_framework(test.get("framework"))
    if framework != "playwright":
        return {"runner_scope_status": "in_scope", "runner_test_dir": ""}

    config = str(repo_ctx.get("runner_config") or "")
    config_text = read_small_text(workdir / config) if config else ""
    test_dir = simple_config_string_prop(config_text, "testDir")
    if not test_dir:
        return {
            "runner_scope_status": "in_scope_unresolved_test_dir",
            "runner_test_dir": "",
            "runner_scope_warning": "",
            "runner_scope_basis": "file_exists_runner_discovery_authoritative",
        }

    abs_test_dir = (workdir / test_dir).resolve()
    if not is_relative_to(abs_file, abs_test_dir):
        return {
            "runner_scope_status": "in_scope_config_test_dir_mismatch_advisory",
            "runner_test_dir": str(Path(test_dir).as_posix()),
            "runner_scope_warning": "config_text_test_dir_mismatch",
            "runner_scope_basis": "file_exists_runner_discovery_authoritative",
        }
    return {
        "runner_scope_status": "in_scope",
        "runner_test_dir": str(Path(test_dir).as_posix()),
        "runner_scope_warning": "",
        "runner_scope_basis": "file_exists_runner_discovery_authoritative",
    }


def candidate_role(test: Dict[str, Any], rq3: Dict[str, str], rq4: Dict[str, str], rq5: Dict[str, str]) -> str:
    action_len = to_int(rq4.get("action_sequence_length"))
    helper_actions = to_int(rq3.get("helper_ui_action_count")) + to_int(rq3.get("custom_command_ui_action_count"))
    page_object = parse_bool(rq3.get("page_object_signal_present"))
    branch_loop = to_int(rq4.get("loop_driven_action_count")) + to_int(rq4.get("non_error_branch_driven_action_count"))
    assertion_count = to_int(rq5.get("assertion_count"))
    if helper_actions > 0 or page_object:
        return "abstraction_heavy"
    if action_len >= 10 or branch_loop > 0 or assertion_count >= 4:
        return "complex"
    return "simple"


def score_for_role(role: str, rq3: Dict[str, str], rq4: Dict[str, str], rq5: Dict[str, str]) -> float:
    action_len = to_int(rq4.get("action_sequence_length"))
    helper_actions = to_int(rq3.get("helper_ui_action_count")) + to_int(rq3.get("custom_command_ui_action_count"))
    assertion_count = to_int(rq5.get("assertion_count"))
    if role == "simple":
        return abs(action_len - 4) + max(0, helper_actions - 1) * 2
    if role == "abstraction_heavy":
        return -helper_actions - (3 if parse_bool(rq3.get("page_object_signal_present")) else 0)
    return -action_len - assertion_count


def main() -> None:
    args = parse_args()
    if args.verify_discovery:
        configure_js_tool_env(tool_bin_dir=args.tool_bin_dir, cache_root=args.out_dir / "tool_cache")
    discovery_cache = DiscoveryCache()
    phase2 = args.phase2_run_dir
    test_cases_path = phase2 / "test_cases.jsonl"
    rq3_path = phase2 / "rq3_patterns_by_test.csv"
    rq4_path = phase2 / "rq4_interaction_complexity_by_test.csv"
    rq5_path = phase2 / "rq5_assertion_complexity_by_test.csv"
    require_inputs([args.runnable_repos, test_cases_path, rq3_path, rq4_path, rq5_path])

    repo_filter = load_repo_filter(args.repos_file)
    runnable = {
        repo: row
        for repo, row in load_runnable_repos(args.runnable_repos, require_pass=not args.include_nonpass_repos).items()
        if row_matches_repo_filter(row, repo_filter)
    }
    rq3 = load_csv_by_test_id(
        rq3_path,
        fields=[
            "helper_ui_action_count",
            "custom_command_ui_action_count",
            "page_object_signal_present",
            "workflow_archetype",
            "abstraction_kind_counts_json",
            "sync_event_count",
        ],
    )
    rq4 = load_csv_by_test_id(
        rq4_path,
        fields=[
            "action_sequence_length",
            "wait_synchronization_count",
            "navigation_count",
            "loop_driven_action_count",
            "non_error_branch_driven_action_count",
            "test_body_sequence_event_count",
        ],
    )
    rq5 = load_csv_by_test_id(
        rq5_path,
        fields=[
            "assertion_count",
            "test_body_assertion_count",
            "assertion_density_all_actions",
            "assertion_placement_test_body",
            "verification_intent_counts",
        ],
    )

    by_repo: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for test in iter_jsonl(test_cases_path):
        if not is_executable_test_case(test):
            continue
        repo = str(test.get("repo") or "")
        if repo not in runnable:
            continue
        test_id = str(test.get("test_id") or "")
        key = (repo, test_id)
        framework = normalize_framework(test.get("framework"))
        if framework not in {"playwright", "cypress"}:
            continue
        if not bool(test.get("has_expanded_ui_actions")):
            continue
        if bool(test.get("extraction_empty")) or is_skipped_test(test):
            continue
        if bool(test.get("parameterization_dynamic") or test.get("is_parameterized")):
            continue
        scope = runner_scope(test, runnable[repo])
        if not str(scope.get("runner_scope_status") or "").startswith("in_scope"):
            continue
        discovery = {
            "discovered": None,
            "discovery_status": "not_checked",
            "discovery_failure_category": "",
            "discovery_command": "",
            "discovery_duration_sec": 0.0,
            "discovery_stdout_path": "",
            "discovery_stderr_path": "",
        }
        if args.verify_discovery:
            discovery = run_discovery_check(
                test,
                runnable[repo],
                timeout_sec=args.discovery_timeout_sec,
                log_dir=args.out_dir / "logs" / "discovery",
                stem=f"{safe_log_token(runnable[repo].get('repo_cache_key') or 'repo')}_{safe_log_token(test_id)}",
                cache=discovery_cache,
            )
            if not discovery.get("discovered"):
                continue
        rq5_row = rq5.get(key, {})
        if to_int(rq5_row.get("assertion_count"), 1 if test.get("has_direct_assertions") else 0) <= 0:
            continue
        rq3_row = rq3.get(key, {})
        rq4_row = rq4.get(key, {})
        role = candidate_role(test, rq3_row, rq4_row, rq5_row)
        row = {
            "repo_full_name": repo,
            "repo_cache_key": runnable[repo].get("repo_cache_key"),
            "source_provenance": runnable[repo].get("source_provenance"),
            "phase2_commit_alignment": runnable[repo].get("phase2_commit_alignment"),
            "source_snapshot_sha256": runnable[repo].get("source_snapshot_sha256"),
            "test_id": test_id,
            "framework": framework,
            "file_path": test.get("file_path"),
            "test_name": test.get("test_name"),
            **scope,
            **discovery,
            "describe_path_json": json.dumps(test.get("describe_path") or [], ensure_ascii=False),
            "candidate_role": role,
            "action_sequence_length": to_int(rq4_row.get("action_sequence_length")),
            "assertion_count": to_int(rq5_row.get("assertion_count")),
            "helper_action_count": to_int(rq3_row.get("helper_ui_action_count")),
            "custom_command_ui_action_count": to_int(rq3_row.get("custom_command_ui_action_count")),
            "wait_count": to_int(rq4_row.get("wait_synchronization_count")),
            "navigation_count": to_int(rq4_row.get("navigation_count")),
            "workflow_archetype": rq3_row.get("workflow_archetype", ""),
            "assertion_placement_test_body": rq5_row.get("assertion_placement_test_body", ""),
            "score": score_for_role(role, rq3_row, rq4_row, rq5_row),
            "selected_for_baseline_attempt": False,
        }
        by_repo[repo].append(row)

    selected: List[Dict[str, Any]] = []
    roles = ["simple", "abstraction_heavy", "complex"]
    for repo in sorted(by_repo):
        rows = by_repo[repo]
        used: Set[str] = set()
        repo_selected: List[Dict[str, Any]] = []
        for role in roles:
            choices = [r for r in rows if r["candidate_role"] == role and r["test_id"] not in used]
            choices.sort(key=lambda r: (float(r["score"]), str(r.get("file_path") or ""), str(r.get("test_name") or "")))
            if choices:
                choice = choices[0]
                used.add(str(choice["test_id"]))
                repo_selected.append(choice)
        remaining = [r for r in rows if r["test_id"] not in used]
        remaining.sort(key=lambda r: (str(r["candidate_role"]), float(r["score"]), str(r.get("file_path") or "")))
        repo_selected.extend(remaining[: max(0, args.max_tests_per_repo - len(repo_selected))])
        for r in repo_selected[: args.max_tests_per_repo]:
            r["selected_for_baseline_attempt"] = True
            selected.append(r)

    selected.sort(key=lambda r: (str(r.get("repo_full_name") or ""), str(r.get("candidate_role") or ""), str(r.get("file_path") or "")))
    write_jsonl(args.out_dir / "candidate_human_tests.jsonl", selected)
    write_csv(args.out_dir / "candidate_human_tests_summary.csv", selected)
    print(json.dumps({"repos": len(by_repo), "candidate_tests": len(selected), "out_dir": str(args.out_dir)}, indent=2))


if __name__ == "__main__":
    main()
