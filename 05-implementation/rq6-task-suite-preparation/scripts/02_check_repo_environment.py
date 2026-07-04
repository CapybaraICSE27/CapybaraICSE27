#!/usr/bin/env python3
"""Phase 1B: check repo availability, git state, package manager, and scripts."""

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
    DEFAULT_REPO_CACHE,
    file_tree_hash,
    iter_jsonl,
    load_repo_filter,
    require_inputs,
    row_matches_repo_filter,
    write_csv,
    write_jsonl,
)
from package_manager import candidate_test_scripts, detect_package_manager, load_package_json  # noqa: E402
from repo_checkout import commit_exists, copy_source_workdir, create_git_archive_workdir, git_status  # noqa: E402


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidates", type=Path, default=DEFAULT_OUT_DIR / "rq6_static_candidate_repos.jsonl")
    ap.add_argument("--repo-cache", type=Path, default=DEFAULT_REPO_CACHE)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--repos-file", type=Path, default=None, help="Optional repo_full_name/repo_cache_key filter.")
    ap.add_argument(
        "--prepare-workdir",
        action="store_true",
        help="Create an isolated workdir under <out-dir>/workdirs/<repo_cache_key>.",
    )
    ap.add_argument(
        "--snapshot-fallback",
        choices=["none", "copy-current"],
        default="copy-current",
        help="Fallback when git history/commit is unavailable and --prepare-workdir is set.",
    )
    ap.add_argument(
        "--hash-source-tree",
        action="store_true",
        help="Compute a deterministic file-tree hash for the inspected source tree.",
    )
    return ap.parse_args()


def status_for(row: Dict[str, Any]) -> str:
    if not row.get("repo_available"):
        return "missing_repo_cache"
    if row.get("dirty") and not row.get("workdir_path"):
        return "dirty_worktree_needs_isolated_workdir"
    if not row.get("package_json_exists"):
        return "missing_package_json"
    if row.get("package_manager_unsupported_reason"):
        return str(row.get("package_manager_unsupported_reason"))
    if not row.get("commit_object_available"):
        return "pass_commit_unverified"
    return "pass"


def main() -> None:
    args = parse_args()
    require_inputs([args.candidates])
    args.out_dir.mkdir(parents=True, exist_ok=True)
    repo_filter = load_repo_filter(args.repos_file)
    out_rows: List[Dict[str, Any]] = []

    for candidate in iter_jsonl(args.candidates):
        if not row_matches_repo_filter(candidate, repo_filter):
            continue
        repo_key = str(candidate.get("repo_cache_key") or "")
        repo_dir = args.repo_cache / repo_key
        expected_commit = str(candidate.get("expected_commit") or "")
        repo_available = repo_dir.is_dir()
        git = git_status(repo_dir) if repo_available else {}
        commit_available = commit_exists(repo_dir, expected_commit) if repo_available else False

        inspect_dir = repo_dir
        workdir_result: Dict[str, Any] = {}
        if args.prepare_workdir and repo_available and commit_available:
            workdir = args.out_dir / "workdirs" / repo_key
            workdir_result = create_git_archive_workdir(repo_dir, expected_commit, workdir)
            if workdir_result.get("status") in {"created", "exists"}:
                inspect_dir = workdir
        elif args.prepare_workdir and repo_available and args.snapshot_fallback == "copy-current":
            workdir = args.out_dir / "workdirs" / repo_key
            workdir_result = copy_source_workdir(repo_dir, workdir)
            if workdir_result.get("status") in {"created_from_current_source", "exists"}:
                inspect_dir = workdir

        package_json = load_package_json(inspect_dir) if repo_available else {}
        pm = detect_package_manager(inspect_dir, package_json) if repo_available else {
            "package_manager": "",
            "lockfile": "",
            "package_manager_field": "",
            "yarn_variant": "",
            "unsupported_reason": "missing_repo_cache",
        }
        scripts = package_json.get("scripts") or {}
        source_provenance = "git_commit_verified" if commit_available else "snapshot_unverified"
        phase2_commit_alignment = "verified_git_commit" if commit_available else "unverified_snapshot"
        source_snapshot_sha256 = file_tree_hash(inspect_dir) if args.hash_source_tree and repo_available else ""
        row = {
            **candidate,
            "stage": "checkout_env_detect",
            "repo_available": repo_available,
            "is_git_repo": bool(git.get("is_git_repo")),
            "dirty": git.get("dirty"),
            "current_commit": git.get("current_commit", ""),
            "expected_commit": expected_commit,
            "commit_object_available": commit_available,
            "checkout_ok": commit_available,
            "workdir_path": workdir_result.get("workdir_path", ""),
            "workdir_status": workdir_result.get("status", ""),
            "workdir_git_metadata_status": workdir_result.get("git_metadata_status", ""),
            "workdir_git_metadata_stderr": workdir_result.get("git_metadata_stderr", ""),
            "workdir_commit_verified": bool(commit_available and workdir_result.get("status") in {"created", "exists"}),
            "source_provenance": source_provenance,
            "source_snapshot_sha256": source_snapshot_sha256,
            "file_tree_hash": source_snapshot_sha256,
            "source_snapshot_hash_status": "computed" if source_snapshot_sha256 else "not_computed",
            "phase2_commit_alignment": phase2_commit_alignment,
            "inspect_dir": str(inspect_dir) if repo_available else "",
            "package_json_exists": bool(package_json),
            "package_manager": pm.get("package_manager", ""),
            "lockfile": pm.get("lockfile", ""),
            "package_manager_field": pm.get("package_manager_field", ""),
            "yarn_variant": pm.get("yarn_variant", ""),
            "package_manager_unsupported_reason": pm.get("unsupported_reason", ""),
            "scripts": scripts,
            "candidate_test_scripts": candidate_test_scripts(scripts),
        }
        row["status"] = status_for(row)
        out_rows.append(row)

    write_jsonl(args.out_dir / "repo_environment.jsonl", out_rows)
    csv_rows = [
        {
            "repo_full_name": r.get("repo_full_name"),
            "repo_cache_key": r.get("repo_cache_key"),
            "framework_primary": r.get("framework_primary"),
            "repo_available": r.get("repo_available"),
            "checkout_ok": r.get("checkout_ok"),
            "dirty": r.get("dirty"),
            "package_json_exists": r.get("package_json_exists"),
            "package_manager": r.get("package_manager"),
            "lockfile": r.get("lockfile"),
                "workdir_status": r.get("workdir_status"),
                "workdir_git_metadata_status": r.get("workdir_git_metadata_status"),
                "source_provenance": r.get("source_provenance"),
            "phase2_commit_alignment": r.get("phase2_commit_alignment"),
            "source_snapshot_hash_status": r.get("source_snapshot_hash_status"),
            "status": r.get("status"),
        }
        for r in out_rows
    ]
    write_csv(args.out_dir / "repo_environment_summary.csv", csv_rows)
    print(json.dumps({"repos_checked": len(out_rows), "out_dir": str(args.out_dir)}, indent=2))


if __name__ == "__main__":
    main()
