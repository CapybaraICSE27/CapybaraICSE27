#!/usr/bin/env python3
"""Phase 2 static complexity: test-body, hook metrics, navigation heuristics."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

SHARD_TEST_THRESHOLD_DEFAULT = 500
_NODE_SEM: Optional[threading.Semaphore] = None

_SM_DIR = Path(__file__).resolve().parent
if str(_SM_DIR) not in sys.path:
    sys.path.insert(0, str(_SM_DIR))
from cache_fingerprint import (
    build_analyzer_fingerprint,
    build_repo_cache_fingerprint,
    cache_entry_is_valid,
    git_head_commit,
    manifest_sha256,
    repo_commit_state,
)
from jsonl_utils import iter_jsonl_objects
from navigationMetrics import (
    compute_navigation_by_test,
    navigation_row_defaults,
    resolve_navigation_feature_paths,
)

DEFAULT_REPO_CACHE = Path(r"<repo-cache>")

STATIC_METRICS_PAYLOAD_VERSION = 4

HOOK_STATIC_METRIC_FIELDS = [
    "repo",
    "hook_lookup_key",
    "hook_instance_key",
    "file_path",
    "hook_body_file_path",
    "hook_source_kind",
    "start_line",
    "end_line",
    "hook_metrics_status",
    "hook_metrics_match_mode",
    "hook_metrics_error",
    "hook_ncloc",
    "hook_loc",
    "hook_cyclomatic_basic",
    "hook_cyclomatic_extended",
    "hook_branch_count",
    "hook_loop_count",
    "hook_max_nesting_depth",
]


def safe_repo_dir(full_name: str) -> str:
    return full_name.replace("/", "__").replace(":", "_")


def iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def format_elapsed(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{secs:02d}s"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def progress_log(message: str, *, started_at: Optional[float] = None) -> None:
    prefix = time.strftime("%Y-%m-%dT%H:%M:%S")
    if started_at is not None:
        prefix = f"{prefix} elapsed={format_elapsed(time.monotonic() - started_at)}"
    print(f"[static-metrics] {prefix} {message}", file=sys.stderr, flush=True)


def is_executable_test_case(tc: Dict[str, Any]) -> bool:
    if tc.get("record_type", "test_case") != "test_case":
        return False
    if tc.get("test_declaration_type") == "bdd_step":
        return False
    return bool(tc.get("test_id"))


def load_test_cases(path: Path) -> List[Dict[str, Any]]:
    return [tc for tc in iter_jsonl(path) if is_executable_test_case(tc)]


def group_by_repo(test_cases: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for tc in test_cases:
        repo = str(tc.get("repo") or "").strip()
        if repo:
            grouped.setdefault(repo, []).append(tc)
    return grouped


def direct_features_path_for_repo(input_run: Path, repo: str, global_direct: Path) -> Path:
    sidecar = input_run / "per_repo_outputs" / f"{safe_repo_dir(repo)}.features_direct.jsonl"
    return sidecar if sidecar.exists() else global_direct


def hook_lookup_key(file_path: str, hook_instance_key: str) -> str:
    k = str(hook_instance_key or "")
    if k.startswith("support:"):
        return k
    fp = str(file_path or "").replace("\\", "/")
    return f"{fp}::{k}" if fp and k else k


def hook_file_hints_from_direct(
    repo: str,
    direct_path: Path,
    *,
    input_run: Optional[Path] = None,
) -> Dict[str, str]:
    """hook_lookup_key -> file_path (all pairs, not first-wins per hook_instance_key)."""
    hints: Dict[str, str] = {}
    src = direct_features_path_for_repo(input_run, repo, direct_path) if input_run else direct_path
    if not src.exists():
        return hints
    repo_filter: Optional[Set[str]] = {repo} if src == direct_path else None

    def hook_line(line: str) -> bool:
        return "is_shared_hook_feature" in line

    for row in iter_jsonl_objects(src, repos_filter=repo_filter, extra_line_predicate=hook_line):
        if not row.get("is_shared_hook_feature"):
            continue
        k = str(row.get("hook_instance_key") or "")
        fp = str(row.get("file_path") or "").replace("\\", "/")
        if not k or not fp:
            continue
        lk = hook_lookup_key(fp, k)
        hints.setdefault(lk, fp)
    return hints


def build_hooks_manifest(
    repo: str,
    test_cases_in_repo: List[Dict[str, Any]],
    hint_map: Dict[str, str],
) -> List[Dict[str, str]]:
    entries: List[Dict[str, str]] = []
    seen: set[str] = set()
    for tc in test_cases_in_repo:
        test_fp = str(tc.get("file_path") or "").replace("\\", "/")
        for k in tc.get("hook_instance_keys") or []:
            kk = str(k)
            if not kk:
                continue
            lk = hook_lookup_key(test_fp if not kk.startswith("support:") else "", kk)
            if lk in seen:
                continue
            seen.add(lk)
            fp = hint_map.get(lk, "")
            if not fp and kk.startswith("support:"):
                parsed = kk.split(":", 2)
                if len(parsed) >= 2:
                    fp = parsed[1].replace("\\", "/")
            fallback = test_fp if not kk.startswith("support:") else ""
            if not fp and fallback:
                fp = fallback
            entries.append(
                {
                    "hook_lookup_key": lk,
                    "hook_instance_key": kk,
                    "file_path": fp,
                    "fallback_test_file_path": fallback,
                }
            )
    return sorted(entries, key=lambda h: h["hook_lookup_key"])


def write_csv(
    path: Path,
    rows: List[Dict[str, Any]],
    fieldnames: Optional[List[str]] = None,
) -> None:
    if fieldnames is None:
        fieldnames = sorted({k for row in rows for k in row.keys()})
    elif rows:
        known = set(fieldnames)
        fieldnames = list(fieldnames) + sorted(
            {k for row in rows for k in row.keys() if k not in known}
        )
    if not fieldnames:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


def sort_test_metric_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        rows,
        key=lambda r: (
            str(r.get("repo") or ""),
            str(r.get("file_path") or ""),
            str(r.get("test_id") or ""),
        ),
    )


def sort_hook_metric_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        rows,
        key=lambda r: (
            str(r.get("repo") or ""),
            str(r.get("hook_lookup_key") or r.get("hook_instance_key") or ""),
        ),
    )


def _empty_test_body_metrics() -> Dict[str, Any]:
    return {
        "test_body_loc": 0,
        "test_body_ncloc": 0,
        "test_body_statement_count": 0,
        "test_body_call_count": 0,
        "test_body_cyclomatic_basic": 0,
        "test_body_cyclomatic_extended": 0,
        "test_body_branch_count": 0,
        "test_body_loop_count": 0,
        "test_body_switch_case_count": 0,
        "test_body_conditional_expression_count": 0,
        "test_body_logical_condition_count": 0,
        "test_body_try_catch_count": 0,
        "test_body_max_nesting_depth": 0,
    }


def build_missing_repo_cache_metrics(
    repo: str,
    tests: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    empty = _empty_test_body_metrics()
    rows: List[Dict[str, Any]] = []
    for tc in tests:
        rows.append(
            {
                "repo": repo,
                "test_id": tc.get("test_id"),
                "framework": tc.get("framework") or "",
                "file_path": tc.get("file_path") or "",
                "test_name": tc.get("test_name") or "",
                "phase1_confidence": tc.get("phase1_confidence") or "",
                "source_confidence": tc.get("source_confidence") or "",
                "callback_start_line": tc.get("callback_start_line"),
                "callback_end_line": tc.get("callback_end_line"),
                "metrics_status": "missing_repo_cache",
                **empty,
            }
        )
    return rows


def build_commit_mismatch_metrics(
    repo: str,
    tests: List[Dict[str, Any]],
    *,
    expected_commit: Optional[str],
    analyzed_commit: Optional[str],
) -> List[Dict[str, Any]]:
    empty = _empty_test_body_metrics()
    rows: List[Dict[str, Any]] = []
    for tc in tests:
        rows.append(
            {
                "repo": repo,
                "test_id": tc.get("test_id"),
                "framework": tc.get("framework") or "",
                "file_path": tc.get("file_path") or "",
                "test_name": tc.get("test_name") or "",
                "phase1_confidence": tc.get("phase1_confidence") or "",
                "source_confidence": tc.get("source_confidence") or "",
                "callback_start_line": tc.get("callback_start_line"),
                "callback_end_line": tc.get("callback_end_line"),
                "metrics_status": "commit_mismatch",
                "expected_commit": expected_commit,
                "analyzed_commit": analyzed_commit,
                **empty,
            }
        )
    return rows


def percentile(sorted_vals: List[int], p: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = int(round((p / 100.0) * (len(sorted_vals) - 1)))
    return float(sorted_vals[max(0, min(idx, len(sorted_vals) - 1))])


def build_validation_report(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    status = Counter(r.get("metrics_status", "") for r in rows)
    ncloc_vals = sorted(int(r.get("test_body_ncloc") or 0) for r in rows if r.get("metrics_status") == "ok")
    cyc_vals = sorted(int(r.get("test_body_cyclomatic_basic") or 0) for r in rows if r.get("metrics_status") == "ok")
    branch_vals = sorted(int(r.get("test_body_branch_count") or 0) for r in rows if r.get("metrics_status") == "ok")
    loop_vals = sorted(int(r.get("test_body_loop_count") or 0) for r in rows if r.get("metrics_status") == "ok")

    zero_ncloc_ok = sum(
        1 for r in rows if r.get("metrics_status") == "ok" and int(r.get("test_body_ncloc") or 0) == 0
    )
    outliers = [
        {
            "repo": r.get("repo"),
            "test_id": r.get("test_id"),
            "test_body_ncloc": r.get("test_body_ncloc"),
            "test_body_cyclomatic_basic": r.get("test_body_cyclomatic_basic"),
            "reason": (
                "ncloc>1000"
                if int(r.get("test_body_ncloc") or 0) > 1000
                else "cyclomatic>50"
            ),
        }
        for r in rows
        if r.get("metrics_status") == "ok"
        and (
            int(r.get("test_body_ncloc") or 0) > 1000
            or int(r.get("test_body_cyclomatic_basic") or 0) > 50
        )
    ][:50]

    return {
        "test_cases_total": len(rows),
        "metrics_rows_total": len(rows),
        "metrics_status_distribution": dict(status),
        "missing_source_files": status.get("missing_source_file", 0),
        "missing_callback_ranges": status.get("missing_callback_range", 0),
        "parse_errors": status.get("parse_error", 0),
        "parse_or_add_errors": status.get("parse_or_add_error", 0),
        "commit_mismatches": status.get("commit_mismatch", 0),
        "missing_repo_cache": status.get("missing_repo_cache", 0),
        "zero_ncloc_tests_ok_status": zero_ncloc_ok,
        "tests_with_hooks": sum(
            1 for r in rows if int(r.get("hook_count") or 0) > 0
        ),
        "hook_metrics_unresolved_total": sum(
            int(r.get("hook_metrics_unresolved_count") or 0) for r in rows
        ),
        "tests_with_navigation_actions": sum(
            1 for r in rows if int(r.get("navigation_action_count") or 0) > 0
        ),
        "tests_with_dynamic_navigation": sum(
            1 for r in rows if r.get("has_dynamic_navigation") is True
        ),
        "ncloc_distribution": {
            "min": ncloc_vals[0] if ncloc_vals else 0,
            "p50": percentile(ncloc_vals, 50),
            "p90": percentile(ncloc_vals, 90),
            "p99": percentile(ncloc_vals, 99),
            "max": ncloc_vals[-1] if ncloc_vals else 0,
        },
        "cyclomatic_basic_distribution": {
            "min": cyc_vals[0] if cyc_vals else 0,
            "p50": percentile(cyc_vals, 50),
            "p90": percentile(cyc_vals, 90),
            "p99": percentile(cyc_vals, 99),
            "max": cyc_vals[-1] if cyc_vals else 0,
        },
        "branch_count_distribution": {
            "min": branch_vals[0] if branch_vals else 0,
            "p50": percentile(branch_vals, 50),
            "max": branch_vals[-1] if branch_vals else 0,
        },
        "loop_count_distribution": {
            "min": loop_vals[0] if loop_vals else 0,
            "p50": percentile(loop_vals, 50),
            "max": loop_vals[-1] if loop_vals else 0,
        },
        "outlier_tests_count": len(outliers),
        "outlier_tests_sample": outliers,
    }


@dataclass
class RunStats:
    repos_total: int = 0
    repos_processed: int = 0
    repos_missing_cache: int = 0
    repos_commit_mismatch: int = 0
    repos_errors: int = 0


def init_node_semaphore(max_concurrent: int) -> None:
    global _NODE_SEM
    _NODE_SEM = threading.Semaphore(max(1, max_concurrent))


def run_node_analyzer(
    node_script: Path,
    repo_path: Path,
    manifest_path: Path,
    output_path: Path,
    *,
    precomputed_hooks_path: Optional[Path] = None,
) -> None:
    cmd = [
        "node",
        str(node_script),
        "--repo-path",
        str(repo_path),
        "--manifest",
        str(manifest_path),
        "--output",
        str(output_path),
    ]
    if precomputed_hooks_path is not None:
        cmd.extend(["--precomputed-hooks", str(precomputed_hooks_path)])

    def _run() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            cmd, capture_output=True, text=True, cwd=str(node_script.parent)
        )

    if _NODE_SEM is not None:
        with _NODE_SEM:
            proc = _run()
    else:
        proc = _run()
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or f"Node failed: {proc.returncode}")


def git_commit_exists(repo_path: Path, commit: str) -> bool:
    if not commit or not (repo_path / ".git").exists():
        return False
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_path), "cat-file", "-e", f"{commit}^{{commit}}"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def materialize_commit_tree(
    *,
    repo: str,
    repo_path: Path,
    commit: str,
    source_root: Path,
    timeout_seconds: int = 1800,
) -> Path:
    target = source_root / f"{safe_repo_dir(repo)}__{commit[:12]}"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)

    archive = subprocess.Popen(
        ["git", "-C", str(repo_path), "archive", "--format=tar", commit],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert archive.stdout is not None
    try:
        extract = subprocess.run(
            ["tar", "-xf", "-", "-C", str(target)],
            stdin=archive.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
        )
        archive.stdout.close()
        archive_err = archive.stderr.read() if archive.stderr else b""
        if archive.stderr is not None:
            archive.stderr.close()
        archive_rc = archive.wait(timeout=timeout_seconds)
    except Exception:
        if archive.stdout is not None:
            archive.stdout.close()
        if archive.stderr is not None:
            archive.stderr.close()
        archive.kill()
        archive.wait(timeout=30)
        shutil.rmtree(target, ignore_errors=True)
        raise

    if archive_rc != 0 or extract.returncode != 0:
        shutil.rmtree(target, ignore_errors=True)
        err = b"\n".join([archive_err, extract.stderr or b""]).decode("utf-8", "replace")
        raise RuntimeError(
            f"Failed to materialize {repo}@{commit[:12]} from {repo_path}: {err[-2000:]}"
        )
    return target


def cleanup_materialized_tree(path: Optional[Path]) -> None:
    if path is not None:
        shutil.rmtree(path, ignore_errors=True)


def compute_shard_count(test_count: int, *, threshold: int, max_parallel: int) -> int:
    if test_count <= threshold:
        return 1
    return min(max_parallel, max(2, (test_count + threshold - 1) // threshold))


def partition_tests_by_file(tests: List[Dict[str, Any]], num_shards: int) -> List[List[Dict[str, Any]]]:
    """Assign whole test files to shards (greedy bin-packing by test count)."""
    if num_shards <= 1:
        return [tests]
    by_file: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for tc in tests:
        fp = str(tc.get("file_path") or "")
        by_file[fp].append(tc)
    file_groups = sorted(by_file.values(), key=len, reverse=True)
    shards: List[List[Dict[str, Any]]] = [[] for _ in range(num_shards)]
    shard_sizes = [0] * num_shards
    for group in file_groups:
        idx = min(range(num_shards), key=lambda i: shard_sizes[i])
        shards[idx].extend(group)
        shard_sizes[idx] += len(group)
    return [s for s in shards if s]


def merge_shard_outputs(shard_payloads: List[Dict[str, Any]]) -> Dict[str, Any]:
    metrics: List[Dict[str, Any]] = []
    hooks: List[Dict[str, Any]] = []
    base: Dict[str, Any] = {}
    for payload in shard_payloads:
        if not base:
            base = {
                k: payload.get(k)
                for k in (
                    "payload_version",
                    "repo",
                    "expected_commit",
                    "analyzed_commit",
                    "cache_fingerprint",
                )
            }
        metrics.extend(payload.get("metrics") or [])
        if not hooks and payload.get("hooks"):
            hooks = list(payload.get("hooks") or [])
    return {
        **base,
        "metrics": sort_test_metric_rows(metrics),
        "hooks": sort_hook_metric_rows(hooks),
    }


def run_sharded_node_analysis(
    *,
    node_script: Path,
    repo_path: Path,
    repo: str,
    tests: List[Dict[str, Any]],
    hooks_mf: List[Dict[str, Any]],
    per_repo_dir: Path,
    expected_commit: Optional[str],
    analyzed_head: Optional[str],
    cache_fp: Dict[str, str],
    shard_threshold: int,
    max_parallel: int,
) -> Dict[str, Any]:
    safe = safe_repo_dir(repo)
    shard_dir = per_repo_dir / f"{safe}.shards"
    shard_dir.mkdir(parents=True, exist_ok=True)

    hooks_json = shard_dir / "hooks.json"
    hooks_manifest = {
        "repo": repo,
        "tests": [],
        "hooks": hooks_mf,
        "payload_version": STATIC_METRICS_PAYLOAD_VERSION,
        "expected_commit": expected_commit,
        "analyzed_commit": analyzed_head,
        "cache_fingerprint": cache_fp,
    }
    hooks_manifest_path = shard_dir / "hooks.manifest.json"
    hooks_manifest_path.write_text(json.dumps(hooks_manifest), encoding="utf-8")
    hooks_out = shard_dir / "hooks.out.json"
    run_node_analyzer(node_script, repo_path, hooks_manifest_path, hooks_out)
    hooks_payload = json.loads(hooks_out.read_text(encoding="utf-8"))
    hooks_list = hooks_payload.get("hooks") or []
    hooks_json.write_text(json.dumps(hooks_list), encoding="utf-8")

    num_shards = compute_shard_count(
        len(tests), threshold=shard_threshold, max_parallel=max_parallel
    )
    test_shards = partition_tests_by_file(tests, num_shards)
    print(
        f"  sharding {repo}: {len(tests)} tests -> {len(test_shards)} shard(s)",
        file=sys.stderr,
    )

    def run_one_shard(shard_idx: int, shard_tests: List[Dict[str, Any]]) -> Dict[str, Any]:
        manifest_path = shard_dir / f"shard_{shard_idx}.manifest.json"
        out_path = shard_dir / f"shard_{shard_idx}.out.json"
        manifest = {
            "repo": repo,
            "tests": shard_tests,
            "hooks": [],
            "payload_version": STATIC_METRICS_PAYLOAD_VERSION,
            "expected_commit": expected_commit,
            "analyzed_commit": analyzed_head,
            "cache_fingerprint": cache_fp,
        }
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        run_node_analyzer(
            node_script,
            repo_path,
            manifest_path,
            out_path,
            precomputed_hooks_path=hooks_json,
        )
        return json.loads(out_path.read_text(encoding="utf-8"))

    shard_payloads: List[Dict[str, Any]] = []
    if len(test_shards) == 1:
        shard_payloads.append(run_one_shard(0, test_shards[0]))
    else:
        with ThreadPoolExecutor(max_workers=len(test_shards)) as shard_pool:
            future_by_idx = {
                shard_pool.submit(run_one_shard, i, shard_tests): i
                for i, shard_tests in enumerate(test_shards)
            }
            ordered: List[Optional[Dict[str, Any]]] = [None] * len(test_shards)
            for fut in as_completed(future_by_idx):
                ordered[future_by_idx[fut]] = fut.result()
            shard_payloads = [p for p in ordered if p is not None]

    merged = merge_shard_outputs(shard_payloads)
    merged["hooks"] = sort_hook_metric_rows(hooks_list)
    merged["sharded"] = len(test_shards) > 1
    merged["shard_count"] = len(test_shards)
    merged["planned_shard_count"] = num_shards
    merged["largest_shard_size"] = max((len(s) for s in test_shards), default=0)
    return merged


def load_repos_file(path: Path) -> List[str]:
    out: List[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.split("#", 1)[0].strip()
        if s:
            out.append(s)
    return out


@dataclass
class GlobalRunContext:
    test_cases_jsonl_sha256: str
    input_run_dir: str
    analyzer_fingerprint: Dict[str, str]


@dataclass
class RepoJobResult:
    repo: str
    ok: bool
    cached: bool = False
    metrics: List[Dict[str, Any]] | None = None
    hooks: List[Dict[str, Any]] | None = None
    missing_cache: bool = False
    commit_skipped: bool = False
    error: Optional[str] = None
    sharded: bool = False
    shard_count: int = 0
    planned_shard_count: int = 0
    largest_shard_size: int = 0
    materialized_source: bool = False


def _sharding_fields_from_cached(cached: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "sharded": bool(cached.get("sharded")),
        "shard_count": int(cached.get("shard_count") or 0),
        "planned_shard_count": int(cached.get("planned_shard_count") or 0),
        "largest_shard_size": int(cached.get("largest_shard_size") or 0),
        "materialized_source": bool(cached.get("source_materialized_from_mismatch")),
    }


def _apply_sharding_defaults(
    cached: Dict[str, Any],
    *,
    test_count: int,
    placeholder: bool = False,
) -> None:
    """Ensure per-repo JSON always carries sharding metadata for downstream analysis."""
    if placeholder:
        cached.setdefault("sharded", False)
        cached.setdefault("shard_count", 0)
        cached.setdefault("planned_shard_count", 0)
        cached.setdefault("largest_shard_size", 0)
    else:
        cached.setdefault("sharded", False)
        cached.setdefault("shard_count", 1)
        cached.setdefault("planned_shard_count", 1)
        cached.setdefault("largest_shard_size", test_count)


def process_one_repo(
    *,
    repo: str,
    repo_path: Path,
    tests: List[Dict[str, Any]],
    node_script: Path,
    per_repo_dir: Path,
    input_run: Path,
    features_direct_path: Path,
    resume: bool,
    run_ctx: GlobalRunContext,
    allow_commit_mismatch: bool,
    shard_threshold: int = SHARD_TEST_THRESHOLD_DEFAULT,
    max_node_workers: int = 8,
    materialize_mismatched_commits: bool = False,
    materialized_source_root: Optional[Path] = None,
    keep_materialized_sources: bool = False,
) -> RepoJobResult:
    out_json = per_repo_dir / f"{safe_repo_dir(repo)}.json"

    hint_map = hook_file_hints_from_direct(repo, features_direct_path, input_run=input_run)
    hooks_mf = build_hooks_manifest(repo, tests, hint_map)
    manifest_sha = manifest_sha256(repo, tests, hooks_mf)
    expected_commit, _mixed_commits = repo_commit_state(tests)
    repo_head = git_head_commit(repo_path) if repo_path.is_dir() else None
    head_differs_from_expected = (
        bool(expected_commit)
        and repo_path.is_dir()
        and repo_head != expected_commit
        and not allow_commit_mismatch
    )
    mismatch_requires_materialization = (
        head_differs_from_expected and materialize_mismatched_commits
    )
    can_materialize_expected_commit = (
        bool(mismatch_requires_materialization)
        and git_commit_exists(repo_path, expected_commit or "")
    )
    analyzed_head = expected_commit if can_materialize_expected_commit else repo_head

    cache_fp = build_repo_cache_fingerprint(
        payload_version=STATIC_METRICS_PAYLOAD_VERSION,
        manifest_sha=manifest_sha,
        analyzer_fp=run_ctx.analyzer_fingerprint,
        test_cases_jsonl_sha256=run_ctx.test_cases_jsonl_sha256,
        input_run_dir=run_ctx.input_run_dir,
        expected_commit=expected_commit,
        analyzed_head=analyzed_head,
        allow_commit_mismatch=allow_commit_mismatch,
    )

    if resume and out_json.exists():
        try:
            cached = json.loads(out_json.read_text(encoding="utf-8"))
            if cache_entry_is_valid(cached, cache_fp):
                return RepoJobResult(
                    repo=repo,
                    ok=True,
                    cached=True,
                    metrics=cached.get("metrics") or [],
                    hooks=cached.get("hooks") or [],
                    **_sharding_fields_from_cached(cached),
                )
        except (OSError, json.JSONDecodeError):
            pass

    if not repo_path.is_dir():
        missing_rows = build_missing_repo_cache_metrics(repo, tests)
        out = {
            "payload_version": STATIC_METRICS_PAYLOAD_VERSION,
            "repo": repo,
            "cache_fingerprint": cache_fp,
            "hooks": [],
            "metrics": missing_rows,
        }
        _apply_sharding_defaults(out, test_count=len(tests), placeholder=True)
        out_json.write_text(json.dumps(out), encoding="utf-8")
        return RepoJobResult(
            repo=repo,
            ok=True,
            missing_cache=True,
            metrics=missing_rows,
            hooks=[],
            **_sharding_fields_from_cached(out),
        )

    if (
        head_differs_from_expected
        and not can_materialize_expected_commit
    ):
        mismatch_rows = build_commit_mismatch_metrics(
            repo,
            tests,
            expected_commit=expected_commit,
            analyzed_commit=repo_head,
        )
        out = {
            "payload_version": STATIC_METRICS_PAYLOAD_VERSION,
            "repo": repo,
            "expected_commit": expected_commit,
            "analyzed_commit": repo_head,
            "cache_fingerprint": cache_fp,
            "hooks": [],
            "metrics": mismatch_rows,
        }
        _apply_sharding_defaults(out, test_count=len(tests), placeholder=True)
        out_json.write_text(json.dumps(out), encoding="utf-8")
        return RepoJobResult(
            repo=repo,
            ok=True,
            commit_skipped=True,
            metrics=mismatch_rows,
            hooks=[],
            **_sharding_fields_from_cached(out),
        )

    manifest = {
        "repo": repo,
        "tests": tests,
        "hooks": hooks_mf,
        "payload_version": STATIC_METRICS_PAYLOAD_VERSION,
        "expected_commit": expected_commit,
        "analyzed_commit": analyzed_head,
        "cache_fingerprint": cache_fp,
    }
    source_path = repo_path
    materialized_path: Optional[Path] = None
    source_materialized = False
    try:
        if can_materialize_expected_commit:
            source_root = materialized_source_root or (per_repo_dir.parent / "_materialized_sources")
            materialized_path = materialize_commit_tree(
                repo=repo,
                repo_path=repo_path,
                commit=expected_commit or "",
                source_root=source_root,
            )
            source_path = materialized_path
            source_materialized = True
        shard_count = compute_shard_count(
            len(tests), threshold=shard_threshold, max_parallel=max_node_workers
        )
        use_shards = len(tests) > shard_threshold and shard_count > 1
        if use_shards:
            cached = run_sharded_node_analysis(
                node_script=node_script,
                repo_path=source_path,
                repo=repo,
                tests=tests,
                hooks_mf=hooks_mf,
                per_repo_dir=per_repo_dir,
                expected_commit=expected_commit,
                analyzed_head=analyzed_head,
                cache_fp=cache_fp,
                shard_threshold=shard_threshold,
                max_parallel=max_node_workers,
            )
        else:
            manifest_path = per_repo_dir / f"{safe_repo_dir(repo)}.manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            run_node_analyzer(node_script, source_path, manifest_path, out_json)
            cached = json.loads(out_json.read_text(encoding="utf-8"))
        cached["cache_fingerprint"] = cache_fp
        cached["expected_commit"] = expected_commit
        cached["analyzed_commit"] = analyzed_head
        cached["payload_version"] = STATIC_METRICS_PAYLOAD_VERSION
        cached["repo_cache_head_commit"] = repo_head
        cached["source_materialized_from_mismatch"] = source_materialized
        cached["metrics"] = sort_test_metric_rows(cached.get("metrics") or [])
        cached["hooks"] = sort_hook_metric_rows(cached.get("hooks") or [])
        if not use_shards:
            _apply_sharding_defaults(cached, test_count=len(tests))
        out_json.write_text(json.dumps(cached), encoding="utf-8")
        return RepoJobResult(
            repo=repo,
            ok=True,
            metrics=cached.get("metrics") or [],
            hooks=cached.get("hooks") or [],
            **_sharding_fields_from_cached(cached),
        )
    except (RuntimeError, OSError, json.JSONDecodeError) as e:
        return RepoJobResult(repo=repo, ok=False, error=str(e))
    finally:
        if materialized_path is not None and not keep_materialized_sources:
            cleanup_materialized_tree(materialized_path)


def main() -> None:
    run_started_at = time.monotonic()
    parser = argparse.ArgumentParser(description="Extract static complexity metrics (Phase 2 static)")
    parser.add_argument("--input-run-dir", type=Path, required=True)
    parser.add_argument("--repo-cache", type=Path, default=DEFAULT_REPO_CACHE)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Defaults to <input-run-dir>/static_metrics",
    )
    parser.add_argument("--limit", type=int, default=None, help="Limit number of repos (validation)")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--skip-navigation",
        action="store_true",
        help="Skip feature-stream navigation heuristics (faster development runs)",
    )
    parser.add_argument(
        "--repos-file",
        type=Path,
        default=None,
        help="Whitespace-separated repos (full_name, one per line); # starts comment. Overrides --limit.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Parallel Node jobs (default: min(8, CPU count); use 1 for sequential)",
    )
    parser.add_argument(
        "--allow-commit-mismatch",
        action="store_true",
        help="Analyze even when repo cache HEAD != test_cases.jsonl commit (records both SHAs)",
    )
    parser.add_argument(
        "--materialize-mismatched-commits",
        action="store_true",
        help=(
            "When repo cache HEAD differs from the expected test-case commit, "
            "extract the expected commit with git archive into a temporary source tree and analyze it."
        ),
    )
    parser.add_argument(
        "--materialized-source-root",
        type=Path,
        default=None,
        help="Temporary root for expected-commit source trees (default: <output-dir>/_materialized_sources).",
    )
    parser.add_argument(
        "--keep-materialized-sources",
        action="store_true",
        help="Keep temporary expected-commit source trees for debugging instead of deleting them after analysis.",
    )
    parser.add_argument(
        "--shard-threshold",
        type=int,
        default=SHARD_TEST_THRESHOLD_DEFAULT,
        help="Auto-split repos with more than this many tests into parallel Node shards (default: 500)",
    )
    args = parser.parse_args()

    input_run = args.input_run_dir
    test_cases_path = input_run / "test_cases.jsonl"
    features_direct_path = input_run / "test_case_features_direct.jsonl"
    if not test_cases_path.exists():
        raise FileNotFoundError(f"Missing {test_cases_path}")

    output_dir = args.output_dir or (input_run / "static_metrics")
    per_repo_dir = output_dir / "per_repo_outputs"
    per_repo_dir.mkdir(parents=True, exist_ok=True)
    materialized_source_root = args.materialized_source_root or (output_dir / "_materialized_sources")
    progress_log(
        f"start input_run_dir={input_run} output_dir={output_dir} repo_cache={args.repo_cache}",
        started_at=run_started_at,
    )

    node_script = Path(__file__).resolve().parent / "analyze_static_metrics.cjs"
    test_cases_sha = file_sha256(test_cases_path)
    run_ctx = GlobalRunContext(
        test_cases_jsonl_sha256=test_cases_sha,
        input_run_dir=str(input_run.resolve()),
        analyzer_fingerprint=build_analyzer_fingerprint(node_script),
    )

    test_cases = load_test_cases(test_cases_path)
    grouped = group_by_repo(test_cases)
    progress_log(
        f"loaded test_cases={len(test_cases)} repos_in_run={len(grouped)}",
        started_at=run_started_at,
    )
    repos_from_file_warnings = 0
    if args.repos_file is not None:
        if not args.repos_file.exists():
            raise FileNotFoundError(args.repos_file)
        raw_repos = load_repos_file(args.repos_file)
        repos = []
        seen_rf: Set[str] = set()
        for r in raw_repos:
            if r in seen_rf:
                continue
            seen_rf.add(r)
            if r not in grouped:
                repos_from_file_warnings += 1
                print(f"Repos file: skipping unknown repo (not in test_cases.jsonl): {r}", file=sys.stderr)
                continue
            repos.append(r)
    else:
        repos = sorted(grouped.keys())
        if args.limit is not None:
            repos = repos[: args.limit]
    progress_log(
        f"selected repos={len(repos)} limit={args.limit or 'none'} repos_file={args.repos_file or 'none'}",
        started_at=run_started_at,
    )

    stats = RunStats(repos_total=len(repos))
    repos_with_mixed_expected_commits = sorted(
        r for r in repos if repo_commit_state(grouped[r])[1]
    )
    if repos_with_mixed_expected_commits:
        print(
            json.dumps(
                {
                    "repos_with_mixed_expected_commits": len(repos_with_mixed_expected_commits),
                    "repos_sample": repos_with_mixed_expected_commits[:20],
                },
                indent=2,
            ),
            file=sys.stderr,
        )

    all_rows: List[Dict[str, Any]] = []
    all_hook_rows: List[Dict[str, Any]] = []
    sharded_repos: List[str] = []
    materialized_repos: List[str] = []
    max_shard_count = 0
    largest_shard_size = 0
    completed_repos = 0

    workers = args.workers
    if workers is None:
        workers = min(8, os.cpu_count() or 1)
    workers = max(1, workers)
    init_node_semaphore(workers)
    shard_threshold = max(1, int(args.shard_threshold))
    progress_log(
        f"using workers={workers} shard_threshold={shard_threshold} resume={bool(args.resume)} "
        f"materialize_mismatched_commits={bool(args.materialize_mismatched_commits)}",
        started_at=run_started_at,
    )

    def apply_result(res: RepoJobResult, idx: int) -> None:
        nonlocal max_shard_count, largest_shard_size, completed_repos

        test_count = len(grouped.get(res.repo, []))
        status = "ok"
        completed_repos += 1
        if res.cached:
            status = "cached"
        elif res.missing_cache:
            stats.repos_missing_cache += 1
            status = "missing_repo_cache_placeholder_rows"
        elif res.commit_skipped:
            stats.repos_commit_mismatch += 1
            status = "commit_mismatch_skipped_analysis"
        elif res.ok:
            status = "ok"
        else:
            stats.repos_errors += 1
            progress_log(
                "repo "
                f"input_idx={idx}/{len(repos)} completed={completed_repos}/{len(repos)} "
                f"repo={res.repo} status=error tests={test_count} error={res.error}",
                started_at=run_started_at,
            )
            return
        stats.repos_processed += 1
        all_rows.extend(res.metrics or [])
        for hk in res.hooks or []:
            all_hook_rows.append({**hk, "repo": res.repo})
        if res.sharded:
            sharded_repos.append(res.repo)
        if res.materialized_source:
            materialized_repos.append(res.repo)
        max_shard_count = max(max_shard_count, res.shard_count)
        largest_shard_size = max(largest_shard_size, res.largest_shard_size)
        progress_log(
            "repo "
            f"input_idx={idx}/{len(repos)} completed={completed_repos}/{len(repos)} "
            f"repo={res.repo} status={status} tests={test_count} "
            f"metric_rows={len(res.metrics or [])} hook_rows={len(res.hooks or [])} "
            f"sharded={bool(res.sharded)} shard_count={res.shard_count} "
            f"materialized_source={bool(res.materialized_source)} "
            f"errors={stats.repos_errors} missing_cache={stats.repos_missing_cache} "
            f"commit_mismatch={stats.repos_commit_mismatch}",
            started_at=run_started_at,
        )

    if workers == 1:
        for idx, repo in enumerate(repos, start=1):
            res = process_one_repo(
                repo=repo,
                repo_path=args.repo_cache / safe_repo_dir(repo),
                tests=grouped[repo],
                node_script=node_script,
                per_repo_dir=per_repo_dir,
                input_run=input_run,
                features_direct_path=features_direct_path,
                resume=args.resume,
                run_ctx=run_ctx,
                allow_commit_mismatch=args.allow_commit_mismatch,
                shard_threshold=shard_threshold,
                max_node_workers=workers,
                materialize_mismatched_commits=args.materialize_mismatched_commits,
                materialized_source_root=materialized_source_root,
                keep_materialized_sources=args.keep_materialized_sources,
            )
            apply_result(res, idx)
    else:
        progress_log(
            f"starting parallel Node analysis (shard when repo > {shard_threshold} tests)",
            started_at=run_started_at,
        )
        with ThreadPoolExecutor(max_workers=workers) as pool:
            future_map = {
                pool.submit(
                    process_one_repo,
                    repo=repo,
                    repo_path=args.repo_cache / safe_repo_dir(repo),
                    tests=grouped[repo],
                    node_script=node_script,
                    per_repo_dir=per_repo_dir,
                    input_run=input_run,
                    features_direct_path=features_direct_path,
                    resume=args.resume,
                    run_ctx=run_ctx,
                    allow_commit_mismatch=args.allow_commit_mismatch,
                    shard_threshold=shard_threshold,
                    max_node_workers=workers,
                    materialize_mismatched_commits=args.materialize_mismatched_commits,
                    materialized_source_root=materialized_source_root,
                    keep_materialized_sources=args.keep_materialized_sources,
                ): (idx, repo)
                for idx, repo in enumerate(repos, start=1)
            }
            for fut in as_completed(future_map):
                idx, repo = future_map[fut]
                try:
                    res = fut.result()
                except Exception as e:
                    res = RepoJobResult(repo=repo, ok=False, error=repr(e))
                apply_result(res, idx)

    if not args.skip_navigation:
        repos_filter: Optional[Set[str]] = set(repos)
        nav_paths, nav_source = resolve_navigation_feature_paths(input_run, repos_filter)
        progress_log(
            f"navigation start source={nav_source} feature_files={len(nav_paths)}",
            started_at=run_started_at,
        )
        nav_map = compute_navigation_by_test(input_run, repos_filter=repos_filter)
        nav_defaults = navigation_row_defaults()
        for row in all_rows:
            gk = f"{row['repo']}::{row['test_id']}"
            row.update(nav_map.get(gk, dict(nav_defaults)))
        progress_log(
            f"navigation joined tests_with_navigation_rows={len(nav_map)}",
            started_at=run_started_at,
        )
    else:
        progress_log("navigation skipped; writing default navigation fields", started_at=run_started_at)
        nav_defaults = navigation_row_defaults()
        for row in all_rows:
            row.update(nav_defaults)

    progress_log(
        f"sorting rows test_metric_rows={len(all_rows)} hook_rows={len(all_hook_rows)}",
        started_at=run_started_at,
    )
    all_rows = sort_test_metric_rows(all_rows)
    all_hook_rows = sort_hook_metric_rows(all_hook_rows)

    jsonl_path = output_dir / "test_case_static_metrics.jsonl"
    progress_log(f"writing {jsonl_path}", started_at=run_started_at)
    with jsonl_path.open("w", encoding="utf-8") as f:
        for row in all_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    hook_jsonl_path = output_dir / "hook_static_metrics.jsonl"
    progress_log(f"writing {hook_jsonl_path}", started_at=run_started_at)
    with hook_jsonl_path.open("w", encoding="utf-8") as f:
        for row in all_hook_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    progress_log("writing CSV outputs", started_at=run_started_at)
    write_csv(output_dir / "test_case_static_metrics.csv", all_rows)
    write_csv(output_dir / "hook_static_metrics.csv", all_hook_rows, HOOK_STATIC_METRIC_FIELDS)

    progress_log("building validation report", started_at=run_started_at)
    validation = build_validation_report(all_rows)

    phase1_manifest_sha = None
    overall_summary_path = input_run / "overall_summary.json"
    if overall_summary_path.exists():
        try:
            phase1_manifest_sha = json.loads(overall_summary_path.read_text(encoding="utf-8")).get(
                "input_manifest_sha256"
            )
        except (OSError, json.JSONDecodeError):
            pass

    summary = {
        "input_run_dir": str(input_run),
        "repos_file": str(args.repos_file.resolve()) if args.repos_file else None,
        "repos_from_file_unknown": repos_from_file_warnings,
        "static_metrics_payload_version": STATIC_METRICS_PAYLOAD_VERSION,
        "test_cases_jsonl_sha256": test_cases_sha,
        "analyzer_fingerprint": run_ctx.analyzer_fingerprint,
        "input_manifest_sha256": phase1_manifest_sha,
        "output_dir": str(output_dir),
        "allow_commit_mismatch": bool(args.allow_commit_mismatch),
        "repos_total": stats.repos_total,
        "repos_processed": stats.repos_processed,
        "repos_missing_cache": stats.repos_missing_cache,
        "repos_commit_mismatch": stats.repos_commit_mismatch,
        "repos_with_mixed_expected_commits": len(repos_with_mixed_expected_commits),
        "repos_with_mixed_expected_commits_list": repos_with_mixed_expected_commits,
        "repos_errors": stats.repos_errors,
        "hook_rows_total": len(all_hook_rows),
        "skipped_navigation": bool(args.skip_navigation),
        "navigation_feature_source": nav_source if not args.skip_navigation else None,
        "workers": workers,
        "elapsed_seconds": round(time.monotonic() - run_started_at, 3),
        "shard_threshold": shard_threshold,
        "materialize_mismatched_commits": bool(args.materialize_mismatched_commits),
        "materialized_source_root": str(materialized_source_root),
        "keep_materialized_sources": bool(args.keep_materialized_sources),
        "materialized_mismatched_repos": materialized_repos,
        "materialized_mismatched_repos_count": len(materialized_repos),
        "sharded_repos": sharded_repos,
        "sharded_repos_count": len(sharded_repos),
        "max_shard_count": max_shard_count,
        "largest_shard_size": largest_shard_size,
        **validation,
    }
    (output_dir / "static_metrics_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    progress_log("summary written", started_at=run_started_at)
    print(json.dumps(summary, indent=2), file=sys.stderr)


if __name__ == "__main__":
    main()
