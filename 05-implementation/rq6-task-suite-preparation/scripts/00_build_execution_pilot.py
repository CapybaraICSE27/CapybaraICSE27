#!/usr/bin/env python3
"""Build a small balanced RQ6 execution-pilot repo subset."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

LIB = Path(__file__).resolve().parents[1] / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from common import DEFAULT_OUT_DIR, iter_jsonl, load_repo_filter, row_matches_repo_filter, write_csv, write_jsonl  # noqa: E402
from install_validation import INSTALL_VALIDATION_SCHEMA, install_row_is_current_success  # noqa: E402


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runner-app", type=Path, default=DEFAULT_OUT_DIR / "repo_runner_app_results.jsonl")
    ap.add_argument("--candidate-tests", type=Path, default=DEFAULT_OUT_DIR / "candidate_human_tests.jsonl")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--playwright-repos", type=int, default=10)
    ap.add_argument("--cypress-repos", type=int, default=10)
    ap.add_argument("--min-candidate-tests", type=int, default=3)
    ap.add_argument(
        "--install-results",
        type=Path,
        action="append",
        default=[],
        help="Previous install results to use for exclusion/ranking. Can be passed more than once.",
    )
    ap.add_argument(
        "--exclude-repos-file",
        type=Path,
        default=None,
        help="Optional repo_full_name/repo_cache_key list to exclude from this pilot.",
    )
    ap.add_argument(
        "--exclude-install-status",
        action="append",
        default=[],
        help="Exclude repos with this previous install status. Can be passed more than once.",
    )
    ap.add_argument(
        "--prefer-install-pass",
        action="store_true",
        help="Rank repos with a current validated previous install pass before unknown repos.",
    )
    ap.add_argument(
        "--prefer-any-install-pass",
        action="store_true",
        help="Rank repos with any previous install pass before unknown repos, even if the row predates the current validation schema.",
    )
    ap.add_argument(
        "--lightweight-ranking",
        action="store_true",
        help="Rank candidates by install/runtime weight signals in addition to test coverage.",
    )
    ap.add_argument(
        "--max-lockfile-kb",
        type=float,
        default=0.0,
        help="Optional maximum largest package lockfile size in KiB. Repos without readable lockfiles are not filtered by this.",
    )
    ap.add_argument(
        "--max-package-dependencies",
        type=int,
        default=0,
        help="Optional maximum root package dependency count. Repos without readable package.json are not filtered by this.",
    )
    return ap.parse_args()


def candidate_counts(path: Path) -> Counter:
    counts: Counter = Counter()
    if not path.exists():
        return counts
    for row in iter_jsonl(path):
        if row.get("selected_for_baseline_attempt"):
            counts[str(row.get("repo_full_name") or "")] += 1
    return counts


def empty_install_history() -> Dict[str, Any]:
    return {
        "install_ok": False,
        "current_install_ok": False,
        "statuses": [],
        "status": "",
        "durations": [],
        "install_sources": [],
    }


def load_install_results(paths: List[Path]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for path in paths:
        if not path or not path.exists():
            continue
        for row in iter_jsonl(path):
            keys = [str(row.get("repo_full_name") or ""), str(row.get("repo_cache_key") or "")]
            for key in keys:
                if not key:
                    continue
                history = out.setdefault(key, empty_install_history())
                status = str(row.get("status") or "")
                if status and status not in history["statuses"]:
                    history["statuses"].append(status)
                history["status"] = status or history["status"]
                history["install_ok"] = bool(history["install_ok"] or row.get("install_ok"))
                history["current_install_ok"] = bool(history["current_install_ok"] or install_row_is_current_success(row))
                if row.get("duration_sec") is not None:
                    try:
                        history["durations"].append(float(row.get("duration_sec") or 0))
                    except (TypeError, ValueError):
                        pass
                source = str(path)
                if source not in history["install_sources"]:
                    history["install_sources"].append(source)
    return out


def package_weight(row: Dict[str, Any]) -> Dict[str, Any]:
    repo_path = Path(str(row.get("repo_cache_path") or ""))
    lockfile_names = ["package-lock.json", "pnpm-lock.yaml", "yarn.lock"]
    row_lockfile = str(row.get("lockfile") or "")
    if row_lockfile and row_lockfile not in lockfile_names:
        lockfile_names.insert(0, row_lockfile)

    largest_lockfile_bytes = 0
    dependency_count = -1
    package_json_path = repo_path / "package.json"
    if repo_path.exists():
        for name in lockfile_names:
            lockfile_path = repo_path / name
            try:
                if lockfile_path.exists():
                    largest_lockfile_bytes = max(largest_lockfile_bytes, lockfile_path.stat().st_size)
            except OSError:
                continue
    try:
        if package_json_path.exists():
            package_json = json.loads(package_json_path.read_text(encoding="utf-8", errors="replace"))
            dependency_count = sum(
                len(package_json.get(section) or {})
                for section in ["dependencies", "devDependencies", "peerDependencies", "optionalDependencies"]
            )
    except (OSError, json.JSONDecodeError, TypeError):
        dependency_count = -1
    return {
        "package_dependency_count": dependency_count,
        "largest_lockfile_kb": round(largest_lockfile_bytes / 1024, 1),
    }


def lightweight_score(item: Dict[str, Any]) -> float:
    score = min(int(item.get("candidate_tests") or 0), 8) * 8.0
    if item.get("previous_current_install_ok"):
        score += 120.0
    elif item.get("previous_install_ok"):
        score += 80.0
    if item.get("local_base_url"):
        score += 40.0
    if item.get("supports_file_filter"):
        score += 20.0
    if item.get("supports_test_title_filter"):
        score += 20.0

    statuses = {str(status or "") for status in item.get("previous_install_statuses", [])}
    if "install_timeout" in statuses:
        score -= 500.0
    if "install_failed_lockfile" in statuses or "install_missing_dependency_tree" in statuses:
        score -= 150.0

    dependency_count = int(item.get("package_dependency_count") or -1)
    if dependency_count >= 0:
        score -= min(dependency_count, 500) * 0.35
    else:
        score -= 40.0

    lockfile_kb = float(item.get("largest_lockfile_kb") or 0.0)
    score -= min(lockfile_kb, 3000.0) * 0.08

    package_manager = str(item.get("package_manager") or "")
    if package_manager == "pnpm":
        score -= 35.0
    elif package_manager == "yarn":
        score -= 8.0

    app_command = str(item.get("app_start_command") or "").lower()
    if "turbo" in app_command or "nx " in app_command:
        score -= 20.0
    return round(score, 1)


def repo_is_excluded(row: Dict[str, Any], excluded_repos: set[str] | None) -> bool:
    return excluded_repos is not None and row_matches_repo_filter(row, excluded_repos)


def main() -> None:
    args = parse_args()
    counts = candidate_counts(args.candidate_tests)
    install_results = load_install_results(args.install_results)
    excluded_repos = load_repo_filter(args.exclude_repos_file)
    excluded_statuses = {str(status or "").strip() for status in args.exclude_install_status if str(status or "").strip()}
    by_framework: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in iter_jsonl(args.runner_app):
        if row.get("status") != "pass":
            continue
        repo = str(row.get("repo_full_name") or "")
        if repo_is_excluded(row, excluded_repos):
            continue
        install = install_results.get(repo) or install_results.get(str(row.get("repo_cache_key") or "")) or {}
        install_statuses = [str(status or "") for status in install.get("statuses", [])]
        if excluded_statuses and any(status in excluded_statuses for status in install_statuses):
            continue
        count = counts.get(repo, 0)
        if count < args.min_candidate_tests:
            continue
        framework = str(row.get("framework") or row.get("framework_primary") or "").lower()
        if framework not in {"playwright", "cypress"}:
            continue
        weight = package_weight(row)
        dependency_count = int(weight["package_dependency_count"])
        lockfile_kb = float(weight["largest_lockfile_kb"])
        if args.max_package_dependencies and dependency_count >= 0 and dependency_count > args.max_package_dependencies:
            continue
        if args.max_lockfile_kb and lockfile_kb > 0 and lockfile_kb > args.max_lockfile_kb:
            continue
        item = {
            "repo_full_name": repo,
            "repo_cache_key": row.get("repo_cache_key"),
            "framework": framework,
            "candidate_tests": count,
            "package_manager": row.get("package_manager"),
            "lockfile": row.get("lockfile"),
            "app_start_command": row.get("app_start_command"),
            "local_base_url": row.get("local_base_url"),
            "supports_file_filter": row.get("supports_file_filter"),
            "supports_test_title_filter": row.get("supports_test_title_filter"),
            "package_dependency_count": dependency_count,
            "largest_lockfile_kb": lockfile_kb,
            "source_provenance": row.get("source_provenance"),
            "phase2_commit_alignment": row.get("phase2_commit_alignment"),
            "previous_install_ok": install.get("install_ok"),
            "previous_current_install_ok": install.get("current_install_ok"),
            "previous_install_status": install.get("status"),
            "previous_install_duration_sec": min(install.get("durations") or []) if install.get("durations") else None,
            "previous_install_statuses": install_statuses,
            "previous_install_statuses_json": json.dumps(install_statuses, ensure_ascii=False),
            "status": "pilot_selected",
        }
        item["lightweight_score"] = lightweight_score(item)
        by_framework[framework].append(item)

    selected: List[Dict[str, Any]] = []
    for framework, limit in [("playwright", args.playwright_repos), ("cypress", args.cypress_repos)]:
        rows = by_framework[framework]
        if args.lightweight_ranking:
            rows.sort(
                key=lambda r: (
                    0 if args.prefer_install_pass and r.get("previous_current_install_ok") else 1,
                    0 if args.prefer_any_install_pass and r.get("previous_install_ok") else 1,
                    -float(r.get("lightweight_score") or 0.0),
                    -int(r["candidate_tests"]),
                    str(r["repo_full_name"]),
                )
            )
        else:
            rows.sort(
                key=lambda r: (
                    0 if args.prefer_install_pass and r.get("previous_current_install_ok") else 1,
                    0 if args.prefer_any_install_pass and r.get("previous_install_ok") else 1,
                    -int(r["candidate_tests"]),
                    str(r["repo_full_name"]),
                )
            )
        selected.extend(rows[:limit])

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.out_dir / "execution_pilot_repos.jsonl", selected)
    write_csv(args.out_dir / "execution_pilot_repos.csv", selected)
    with (args.out_dir / "execution_pilot_repos.txt").open("w", encoding="utf-8") as f:
        for row in selected:
            f.write(str(row["repo_full_name"]) + "\n")
    print(
        json.dumps(
            {
                "selected_repos": len(selected),
                "by_framework": dict(Counter(r["framework"] for r in selected)),
                "out_dir": str(args.out_dir),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
