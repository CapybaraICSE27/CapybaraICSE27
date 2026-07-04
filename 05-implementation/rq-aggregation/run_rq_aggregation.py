#!/usr/bin/env python3
"""Phase 2D: streaming RQ1-RQ5 aggregation from Phase 2 JSONL outputs."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import datetime as _dt
import json
import pickle
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aggregate import Aggregator
from static_metrics_join import (
    StaticMetricsLoadResult,
    load_static_metrics,
    resolve_static_metrics_path,
)
from feature_merge import (
    build_hook_by_key_from_direct,
    is_direct_test_body_feature,
    iter_deduped_features,
    iter_direct_non_shared_features,
    iter_direct_test_body_features,
    iter_hook_attached_features,
)

DEFAULT_LLM_CONCURRENCY = 8


def _timestamp() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _format_elapsed(started: float | None) -> str:
    if started is None:
        return ""
    elapsed = max(0.0, time.monotonic() - started)
    minutes, seconds = divmod(int(elapsed), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f" elapsed={hours:d}h{minutes:02d}m{seconds:02d}s"
    if minutes:
        return f" elapsed={minutes:d}m{seconds:02d}s"
    return f" elapsed={seconds:d}s"


def log_progress(message: str, *, started: float | None = None) -> None:
    print(f"[{_timestamp()}] {message}{_format_elapsed(started)}", file=sys.stderr, flush=True)
from rq2_registry_rollup import load_per_repo_registry_metrics, summarize_registry_rollup
from rq2_provenance_gates import write_provenance_gates
from rq2_provenance_audit_sample import build_audit_samples
from llm_semantic_cache import LlmSemanticCache
from llm_semantic_categorizer import LlmSemanticCorrector, load_openai_api_key_from_env_file
from stream_io import (
    iter_helper_edges,
    iter_jsonl,
    load_test_cases,
    resolve_feature_sources,
    test_key,
)


def _expanded_paths(input_dir: Path, per_repo_dir: Path | None) -> List[Path]:
    sources = resolve_feature_sources(input_dir)
    if sources["expanded"] is not None:
        return [sources["expanded"]]
    if per_repo_dir and per_repo_dir.is_dir():
        paths = sorted(per_repo_dir.glob("*.features_expanded.jsonl"))
        if paths:
            return paths
    return []


EVENT_CSVS: List[Tuple[str, List[str]]] = [
    ("rq1_environment_control_events.csv", Aggregator.RQ1_FIELDS),
    ("rq2_input_events.csv", Aggregator.RQ2_FIELDS),
    ("rq2_ast_vs_regex_input_audit.csv", Aggregator.RQ2_AST_INPUT_AUDIT_FIELDS),
    ("rq3_ast_vs_regex_locator_audit.csv", Aggregator.RQ3_AST_LOCATOR_AUDIT_FIELDS),
    ("rq3_locator_pattern_events.csv", Aggregator.RQ3_LOCATOR_FIELDS),
    ("rq3_sync_pattern_events.csv", Aggregator.RQ3_SYNC_FIELDS),
    ("rq3_workflow_pattern_events.csv", Aggregator.RQ3_WORKFLOW_FIELDS),
    ("rq4_interaction_events.csv", Aggregator.RQ4_FIELDS),
    ("rq5_assertion_events.csv", Aggregator.RQ5_FIELDS),
]


def safe_repo_dir(full_name: str) -> str:
    return full_name.replace("/", "__").replace(":", "_")


def repos_from_test_cases(test_cases: Dict[str, Dict[str, Any]]) -> List[str]:
    return sorted({
        str(tc.get("repo") or "").strip()
        for tc in test_cases.values()
        if str(tc.get("repo") or "").strip()
    })


def _repo_sidecar(per_repo_dir: Path, repo: str, suffix: str) -> Path:
    return per_repo_dir / f"{safe_repo_dir(repo)}.{suffix}.jsonl"


def _repo_weight(per_repo_dir: Path, repo: str) -> int:
    weight = 0
    for suffix in ("features_expanded", "features_direct", "helper_edges", "test_cases"):
        path = _repo_sidecar(per_repo_dir, repo, suffix)
        if path.exists():
            weight += max(1, path.stat().st_size)
    return weight or 1


def _iter_jsonl_with_byte_progress(
    path: Path,
    *,
    on_progress: Callable[[int], None] | None = None,
) -> Iterator[Dict[str, Any]]:
    if not path.exists():
        return
    with path.open("rb") as f:
        while True:
            line = f.readline()
            if not line:
                break
            if line.strip():
                yield json.loads(line)
            if on_progress is not None:
                on_progress(f.tell())


def stream_repo_partition_helper_edges_with_progress(
    *,
    repos: Sequence[str],
    per_repo_dir: Path,
    started: float,
) -> Iterator[Dict[str, Any]]:
    total = len(repos)
    log_progress(f"Phase 2D helper-edge streaming started for {total} repos", started=started)
    for idx, repo in enumerate(repos, start=1):
        path = _repo_sidecar(per_repo_dir, repo, "helper_edges")
        repo_edges = 0
        if path.exists():
            for edge in iter_jsonl(path):
                repo_edges += 1
                yield edge
        log_progress(
            f"Phase 2D helper edges repo {idx}/{total}: {repo} done edges={repo_edges}",
            started=started,
        )


def stream_repo_partition_features_with_progress(
    *,
    repos: Sequence[str],
    per_repo_dir: Path,
    test_cases: Dict[str, Dict[str, Any]],
    started: float,
    interval_seconds: float,
    percent_step: int,
) -> Iterator[Dict[str, Any]]:
    seen: set[str] = set()
    total_repos = len(repos)
    step = max(1, int(percent_step or 10))
    interval = max(1.0, float(interval_seconds or 30))
    log_progress(f"Phase 2D feature streaming started for {total_repos} repos", started=started)

    for repo_idx, repo in enumerate(repos, start=1):
        direct_path = _repo_sidecar(per_repo_dir, repo, "features_direct")
        expanded_path = _repo_sidecar(per_repo_dir, repo, "features_expanded")
        active_paths = [p for p in (direct_path, expanded_path) if p.exists()]
        if not expanded_path.exists() and direct_path.exists():
            active_paths = [direct_path]
        total_bytes = sum(max(1, p.stat().st_size) for p in active_paths) or 1
        bytes_by_stage: Dict[str, int] = {}
        emitted = 0
        next_percent = 0
        last_log = 0.0

        def maybe_log(stage: str, pos: int, *, force: bool = False) -> None:
            nonlocal next_percent, last_log
            bytes_by_stage[stage] = pos
            done_bytes = min(total_bytes, sum(bytes_by_stage.values()))
            percent = min(100, int((done_bytes / total_bytes) * 100))
            now = time.monotonic()
            if force or percent >= next_percent or now - last_log >= interval:
                log_progress(
                    (
                        f"Phase 2D repo {repo_idx}/{total_repos}: {repo} "
                        f"{percent}% stage={stage} features_emitted={emitted}"
                    ),
                    started=started,
                )
                last_log = now
                next_percent = min(100, percent + step)

        log_progress(
            (
                f"Phase 2D repo {repo_idx}/{total_repos}: {repo} started "
                f"files={len(active_paths)} bytes={total_bytes}"
            ),
            started=started,
        )

        expanded_includes_hooks = False

        if direct_path.exists():

            def direct_rows() -> Iterator[Dict[str, Any]]:
                for f in _iter_jsonl_with_byte_progress(
                    direct_path,
                    on_progress=lambda pos: maybe_log("direct", pos),
                ):
                    if is_direct_test_body_feature(f):
                        yield f

            for feature in iter_deduped_features(direct_rows(), seen):
                emitted += 1
                yield feature

        if expanded_path.exists():

            def expanded_rows() -> Iterator[Dict[str, Any]]:
                nonlocal expanded_includes_hooks
                for f in _iter_jsonl_with_byte_progress(
                    expanded_path,
                    on_progress=lambda pos: maybe_log("expanded", pos),
                ):
                    if f.get("attached_from_hook"):
                        expanded_includes_hooks = True
                    yield f

            for feature in iter_deduped_features(expanded_rows(), seen):
                emitted += 1
                yield feature
        elif direct_path.exists():

            def direct_non_shared_rows() -> Iterator[Dict[str, Any]]:
                for f in _iter_jsonl_with_byte_progress(
                    direct_path,
                    on_progress=lambda pos: maybe_log("direct", pos),
                ):
                    if f.get("is_shared_hook_feature"):
                        continue
                    if f.get("test_id"):
                        yield f

            for feature in iter_deduped_features(direct_non_shared_rows(), seen):
                emitted += 1
                yield feature

        if direct_path.exists() and not expanded_includes_hooks:
            repo_tests = {
                key: tc
                for key, tc in test_cases.items()
                if str(tc.get("repo") or "").strip() == repo
            }
            hook_by_key = build_hook_by_key_from_direct(direct_path)
            for feature in iter_hook_attached_features(repo_tests, hook_by_key, seen):
                emitted += 1
                yield feature

        maybe_log("done", total_bytes, force=True)


def partition_repos_by_weight(
    repos: Sequence[str],
    per_repo_dir: Path,
    workers: int,
) -> List[List[str]]:
    buckets: List[List[str]] = [[] for _ in range(max(1, workers))]
    weights = [0 for _ in buckets]
    for repo in sorted(repos, key=lambda r: _repo_weight(per_repo_dir, r), reverse=True):
        idx = min(range(len(buckets)), key=lambda i: weights[i])
        buckets[idx].append(repo)
        weights[idx] += _repo_weight(per_repo_dir, repo)
    return [b for b in buckets if b]


def load_repo_test_cases(
    *,
    repos: Sequence[str],
    input_dir: Path,
    per_repo_dir: Path,
) -> Dict[str, Dict[str, Any]]:
    selected = set(repos)
    out: Dict[str, Dict[str, Any]] = {}
    loaded_repos: set[str] = set()
    for repo in selected:
        path = _repo_sidecar(per_repo_dir, repo, "test_cases")
        if not path.exists():
            continue
        repo_loaded = False
        for tc in iter_jsonl(path):
            repo_name = str(tc.get("repo") or repo).strip()
            tid = str(tc.get("test_id") or "").strip()
            if repo_name and tid:
                tc = {**tc, "repo": repo_name, "test_id": tid}
                out[test_key(repo_name, tid)] = tc
                repo_loaded = True
        if repo_loaded:
            loaded_repos.add(repo)
    missing_repos = selected - loaded_repos
    if not missing_repos:
        return out

    # Fallback for old or partially migrated outputs without every per-repo
    # test-case sidecar. Stream the root file only for missing repos.
    root = input_dir / "test_cases.jsonl"
    for tc in iter_jsonl(root):
        repo_name = str(tc.get("repo") or "").strip()
        if repo_name not in missing_repos:
            continue
        tid = str(tc.get("test_id") or "").strip()
        if repo_name and tid:
            tc = {**tc, "repo": repo_name, "test_id": tid}
            out[test_key(repo_name, tid)] = tc
    return out


def stream_repo_partition_features(
    *,
    repos: Sequence[str],
    per_repo_dir: Path,
    test_cases: Dict[str, Dict[str, Any]],
) -> Iterator[Dict[str, Any]]:
    seen: set[str] = set()
    for repo in repos:
        direct_path = _repo_sidecar(per_repo_dir, repo, "features_direct")
        expanded_path = _repo_sidecar(per_repo_dir, repo, "features_expanded")
        expanded_includes_hooks = False

        if direct_path.exists():
            yield from iter_deduped_features(iter_direct_test_body_features(direct_path), seen)

        if expanded_path.exists():

            def expanded_iter() -> Iterator[Dict[str, Any]]:
                nonlocal expanded_includes_hooks
                for f in iter_jsonl(expanded_path):
                    if f.get("attached_from_hook"):
                        expanded_includes_hooks = True
                    yield f

            yield from iter_deduped_features(expanded_iter(), seen)
        elif direct_path.exists():
            yield from iter_deduped_features(iter_direct_non_shared_features(direct_path), seen)

        if direct_path.exists() and not expanded_includes_hooks:
            repo_tests = {
                key: tc
                for key, tc in test_cases.items()
                if str(tc.get("repo") or "").strip() == repo
            }
            hook_by_key = build_hook_by_key_from_direct(direct_path)
            yield from iter_hook_attached_features(repo_tests, hook_by_key, seen)


def stream_repo_partition_helper_edges(
    *,
    repos: Sequence[str],
    per_repo_dir: Path,
) -> Iterator[Dict[str, Any]]:
    for repo in repos:
        path = _repo_sidecar(per_repo_dir, repo, "helper_edges")
        if path.exists():
            yield from iter_jsonl(path)


def merge_csv_partials(
    *,
    partial_dirs: Sequence[Path],
    output_dir: Path,
) -> None:
    for name, fieldnames in EVENT_CSVS:
        out_path = output_dir / name
        existing_partials = [partial / name for partial in partial_dirs if (partial / name).exists()]
        with out_path.open("w", encoding="utf-8", newline="") as out_f:
            writer = csv.writer(out_f)
            writer.writerow(fieldnames)
            for path in existing_partials:
                with path.open("r", encoding="utf-8", newline="") as in_f:
                    reader = csv.reader(in_f)
                    try:
                        next(reader)
                    except StopIteration:
                        continue
                    for row in reader:
                        writer.writerow(row)


def stream_all_features(input_dir: Path, per_repo_dir: Path | None, test_cases: Dict[str, Any]):
    """
    Yield deduped features for aggregation.

    When expanded JSONL exists (typical 2C run):
      1. Direct test_body features from test_case_features_direct.jsonl
      2. Expanded features from test_case_features_expanded.jsonl
      3. Hook attach from direct only if expanded has no attached_from_hook rows

    When expanded is absent (2AB fallback):
      - All non-shared direct features + hook attach from direct
    """
    sources = resolve_feature_sources(input_dir)
    seen: set[str] = set()
    direct_path = sources.get("direct")
    expanded_paths = _expanded_paths(input_dir, per_repo_dir)
    expanded_includes_hooks = False

    # 1. Always merge direct test_body rows when direct file exists (2C runs omit these from expanded).
    if direct_path is not None:
        yield from iter_deduped_features(iter_direct_test_body_features(direct_path), seen)

    # 2. Expanded overlay (helpers, hooks, cypress command bodies, …).
    if expanded_paths:

        def expanded_iter() -> Iterator[Dict[str, Any]]:
            nonlocal expanded_includes_hooks
            for path in expanded_paths:
                for f in iter_jsonl(path):
                    if f.get("attached_from_hook"):
                        expanded_includes_hooks = True
                    yield f

        yield from iter_deduped_features(expanded_iter(), seen)
    elif direct_path is not None:
        # 2AB-only: remaining direct rows (hooks already in file with test_id, etc.).
        yield from iter_deduped_features(iter_direct_non_shared_features(direct_path), seen)

    # 3. Hook attach fallback when expanded did not materialize hook features.
    if direct_path is not None and not expanded_includes_hooks:
        hook_by_key = build_hook_by_key_from_direct(direct_path)
        yield from iter_hook_attached_features(test_cases, hook_by_key, seen)

    # Per-repo direct sidecars when no merged direct/expanded at input_dir root.
    if not direct_path and not expanded_paths and per_repo_dir and per_repo_dir.is_dir():
        for path in sorted(per_repo_dir.glob("*.features_direct.jsonl")):
            yield from iter_deduped_features(iter_direct_non_shared_features(path), seen)


def _aggregate_repo_partition(
    *,
    worker_idx: int,
    repos: Sequence[str],
    input_dir: Path,
    per_repo_dir: Path,
    partial_root: Path,
) -> Dict[str, Any]:
    partial_dir = partial_root / f"worker_{worker_idx:03d}"
    if partial_dir.exists():
        shutil.rmtree(partial_dir)
    partial_dir.mkdir(parents=True, exist_ok=True)

    test_cases = load_repo_test_cases(
        repos=repos,
        input_dir=input_dir,
        per_repo_dir=per_repo_dir,
    )
    agg = Aggregator(test_cases, partial_dir)

    n_edges = 0
    for edge in stream_repo_partition_helper_edges(repos=repos, per_repo_dir=per_repo_dir):
        agg.ingest_helper_edge(edge)
        n_edges += 1

    n_feat = 0
    for feature in stream_repo_partition_features(
        repos=repos,
        per_repo_dir=per_repo_dir,
        test_cases=test_cases,
    ):
        agg.ingest_feature(feature)
        n_feat += 1

    agg.close_event_sinks()
    # Keep the pickled worker state small; the parent owns full test/static maps.
    agg.test_cases = {}
    agg.static_metrics_by_key = None
    agg.static_metrics_load = None

    state_path = partial_dir / "aggregator_state.pkl"
    with state_path.open("wb") as fh:
        pickle.dump(agg, fh, protocol=pickle.HIGHEST_PROTOCOL)

    return {
        "worker_idx": worker_idx,
        "repos": len(repos),
        "test_cases": len(test_cases),
        "features": n_feat,
        "helper_edges": n_edges,
        "partial_dir": str(partial_dir),
        "state_path": str(state_path),
    }


def _load_worker_aggregator(state_path: Path) -> Aggregator:
    with state_path.open("rb") as fh:
        return pickle.load(fh)


def validate_parallel_temp_dir(partial_root: Path, input_dir: Path, per_repo_dir: Path) -> Path:
    """Return a resolved temp dir, rejecting paths that are unsafe to delete."""
    resolved = partial_root.resolve()
    input_resolved = input_dir.resolve()
    per_repo_resolved = per_repo_dir.resolve()

    if resolved == input_resolved:
        raise RuntimeError("--parallel-temp-dir must not be the run input directory")
    if resolved == per_repo_resolved or per_repo_resolved in resolved.parents:
        raise RuntimeError("--parallel-temp-dir must not be per_repo_outputs or a child of it")
    if input_resolved not in resolved.parents:
        raise RuntimeError("--parallel-temp-dir must be a child directory of --input-dir")
    if "phase2d_partials" not in resolved.name.lower():
        raise RuntimeError("--parallel-temp-dir name must include 'phase2d_partials'")
    return resolved


def _merge_worker_state(master: Aggregator, worker: Aggregator) -> None:
    master.by_key.update(worker.by_key)
    master.rq2_review_rows.extend(worker.rq2_review_rows)
    for key, value in worker.rq3_ast_provenance.items():
        master.rq3_ast_provenance[key] = master.rq3_ast_provenance.get(key, 0) + int(value or 0)

    for name in (
        "rq1_sink",
        "rq2_sink",
        "rq2_ast_input_audit_sink",
        "rq4_sink",
        "rq5_sink",
        "rq3_locator_sink",
        "rq3_sync_sink",
        "rq3_workflow_sink",
        "rq3_ast_locator_audit_sink",
    ):
        getattr(master, name).count += getattr(worker, name).count


def run_parallel_aggregation(
    *,
    input_dir: Path,
    per_repo_dir: Path,
    test_cases: Dict[str, Dict[str, Any]],
    workers: int,
    static_by_key: Dict[str, Dict[str, Any]] | None,
    static_load: StaticMetricsLoadResult | None,
    partial_root: Path,
    keep_partials: bool,
) -> Tuple[Aggregator, int, Dict[str, Any]]:
    if not per_repo_dir.is_dir():
        raise FileNotFoundError(
            f"Parallel aggregation requires per-repo sidecars at {per_repo_dir}"
        )

    repos = repos_from_test_cases(test_cases)
    if not repos:
        raise RuntimeError("No repos found in test_cases.jsonl")

    partial_root = validate_parallel_temp_dir(partial_root, input_dir, per_repo_dir)
    if partial_root.exists():
        shutil.rmtree(partial_root)
    partial_root.mkdir(parents=True, exist_ok=True)

    partitions = partition_repos_by_weight(repos, per_repo_dir, workers)
    print(
        f"Parallel Phase 2D: {len(repos)} repos across {len(partitions)} workers "
        f"(temp: {partial_root})",
        file=sys.stderr,
    )

    worker_results: List[Dict[str, Any]] = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=len(partitions)) as pool:
        futures = [
            pool.submit(
                _aggregate_repo_partition,
                worker_idx=idx,
                repos=partition,
                input_dir=input_dir,
                per_repo_dir=per_repo_dir,
                partial_root=partial_root,
            )
            for idx, partition in enumerate(partitions, start=1)
        ]
        for fut in concurrent.futures.as_completed(futures):
            result = fut.result()
            worker_results.append(result)
            print(
                "  worker {worker_idx}: {repos} repos, {test_cases} tests, "
                "{features} features, {helper_edges} edges".format(**result),
                file=sys.stderr,
            )

    worker_results.sort(key=lambda r: int(r["worker_idx"]))
    partial_dirs = [Path(r["partial_dir"]) for r in worker_results]
    merge_csv_partials(partial_dirs=partial_dirs, output_dir=input_dir)

    master = Aggregator(
        test_cases,
        input_dir,
        static_metrics_by_key=static_by_key,
        static_metrics_load=static_load,
    )
    for result in worker_results:
        worker = _load_worker_aggregator(Path(result["state_path"]))
        _merge_worker_state(master, worker)

    n_feat = sum(int(r["features"]) for r in worker_results)
    metadata = {
        "phase2d_parallel": True,
        "phase2d_workers": len(partitions),
        "phase2d_worker_results": [
            {
                "worker_idx": r["worker_idx"],
                "repos": r["repos"],
                "test_cases": r["test_cases"],
                "features": r["features"],
                "helper_edges": r["helper_edges"],
            }
            for r in worker_results
        ],
        "phase2d_partial_dir": str(partial_root) if keep_partials else None,
    }
    if not keep_partials:
        shutil.rmtree(partial_root, ignore_errors=True)
    return master, n_feat, metadata


def validate_aggregation(agg: Aggregator, test_cases: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Sanity checks: test-body metrics must not be empty on a real 2C corpus."""
    from collections import Counter

    placement = Counter()
    tests_tb_ui = 0
    tests_direct_assert = 0

    for row in agg.by_key.values():
        if row.test_body_ui_action_count > 0:
            tests_tb_ui += 1
        if row.direct_assertion_count > 0:
            tests_direct_assert += 1
        ui_lines = sorted(row.test_body_ui_action_lines)
        assert_lines = sorted(row.test_body_assertion_lines)
        from aggregate import assertion_placement

        placement[assertion_placement(assert_lines, ui_lines)] += 1

    expected_direct_ui = sum(1 for tc in test_cases.values() if tc.get("has_direct_ui_actions"))

    result = {
        "tests_with_test_body_ui_action_count_gt_0": tests_tb_ui,
        "tests_with_direct_assertion_count_gt_0": tests_direct_assert,
        "test_cases_with_has_direct_ui_actions": expected_direct_ui,
        "assertion_placement_test_body_distribution": dict(placement),
    }

    errors: List[str] = []
    if tests_tb_ui == 0:
        errors.append("no tests with test_body_ui_action_count > 0")
    if tests_direct_assert == 0:
        errors.append("no tests with direct_assertion_count > 0")
    if len(agg.by_key) > 0 and placement.get("none", 0) == len(agg.by_key):
        errors.append("assertion_placement_test_body is 'none' for every test")

    prov = getattr(agg, "rq3_ast_provenance", {}) or {}
    ast_enabled = True
    ui_rows = int(prov.get("ui_action_rows") or 0)
    ast_loc = int(prov.get("locator_rows_with_ast_strategy") or 0)
    ui_sig = int(prov.get("ui_rows_with_action_signature_json") or 0)
    ui_cf = int(prov.get("ui_rows_with_control_flow_field_present") or 0)
    assert_chain = int(prov.get("assertion_rows_with_chain_fields") or 0)
    assert_rows = sum(
        int(getattr(row, "rq5_count", 0) or 0) for row in agg.by_key.values()
    )
    rq1_api_cat = int(prov.get("features_with_framework_api_category") or 0)
    ast_warnings: List[str] = []
    if ast_enabled and ui_rows > 100 and ast_loc == 0:
        ast_warnings.append(
            "rq3_ast_enabled but locator_rows_with_ast_strategy=0 "
            "(likely regex-only JSONL; rerun Phase 2B with AST fields)"
        )
    if ui_rows > 100 and ui_sig == 0:
        ast_warnings.append(
            "m3_ast_enabled but ui_rows_with_action_signature_json=0 "
            "(likely stale JSONL; rerun Phase 2B/2C with M3 action signatures)"
        )
    if ui_rows > 100 and ui_cf == 0:
        ast_warnings.append(
            "m3_ast_enabled but ui_rows_with_control_flow_field_present=0 "
            "(likely stale JSONL; rerun Phase 2B with control-flow fields)"
        )
    if assert_rows > 100 and assert_chain == 0:
        ast_warnings.append(
            "m3_ast_enabled but assertion_rows_with_chain_fields=0 "
            "(likely stale JSONL; rerun Phase 2B with assertion-chain fields)"
        )
    if len(agg.by_key) > 50 and rq1_api_cat == 0:
        ast_warnings.append(
            "m3_rq1_enabled but features_with_framework_api_category=0 "
            "(likely stale JSONL; rerun Phase 2B with setup/teardown AST fields)"
        )
    result["rq3_ast_provenance"] = prov
    result["rq3_ast_warnings"] = ast_warnings
    result["m3_ast_warnings"] = [w for w in ast_warnings if w.startswith("m3_")]

    result["validation_passed"] = len(errors) == 0
    result["validation_errors"] = errors
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 2D RQ aggregation (streaming)")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument(
        "--per-repo-dir",
        type=Path,
        default=None,
        help="Optional per_repo_outputs (default: <input-dir>/per_repo_outputs)",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Do not fail when test-body validation checks fail",
    )
    parser.add_argument(
        "--static-metrics-dir",
        type=Path,
        default=None,
        help=(
            "Directory with test_case_static_metrics.jsonl "
            "(run dir or <run>/static_metrics); left-joins sm_* columns onto RQ per-test CSVs"
        ),
    )
    parser.add_argument(
        "--fail-on-ast-warning",
        action="store_true",
        help="Exit non-zero when rq3_ast_warnings is non-empty",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help=(
            "Number of Phase 2D repo-partition workers. Default 1 keeps the legacy "
            "single-process streaming path. Values >1 require per_repo_outputs sidecars."
        ),
    )
    parser.add_argument(
        "--parallel-temp-dir",
        type=Path,
        default=None,
        help="Temporary directory for parallel worker partial CSVs/states (default: <input-dir>/_phase2d_partials)",
    )
    parser.add_argument(
        "--keep-parallel-partials",
        action="store_true",
        help="Keep worker partial directories after a successful parallel aggregation.",
    )
    parser.add_argument(
        "--enable-llm-correction",
        action="store_true",
        help="Enable automatic LLM semantic correction for selected hard RQ2/RQ3/RQ5-C rows.",
    )
    parser.add_argument(
        "--llm-model",
        default="gpt-5.4-mini",
        help="Model for --enable-llm-correction.",
    )
    parser.add_argument(
        "--llm-cache-dir",
        type=Path,
        default=None,
        help="Cache directory for LLM correction outputs (default: <input-dir>/.llm_cache).",
    )
    parser.add_argument(
        "--llm-max-rows",
        type=int,
        default=0,
        help="Maximum rows to send to LLM correction; 0 means no limit.",
    )
    parser.add_argument(
        "--llm-batch-size",
        type=int,
        default=64,
        help="Rows per same-RQ LLM correction request. Use 64 for Mini validation; 1 disables batching.",
    )
    parser.add_argument(
        "--llm-concurrency",
        type=int,
        default=DEFAULT_LLM_CONCURRENCY,
        help=f"Maximum concurrent LLM correction requests. Default is {DEFAULT_LLM_CONCURRENCY}; lower it for conservative debugging.",
    )
    parser.add_argument(
        "--llm-timeout-seconds",
        type=int,
        default=120,
        help="Per-request OpenAI Responses API timeout in seconds.",
    )
    parser.add_argument(
        "--llm-retry-attempts",
        type=int,
        default=5,
        help="Maximum OpenAI request attempts per LLM correction batch.",
    )
    parser.add_argument(
        "--llm-retry-sleep-seconds",
        type=float,
        default=2.0,
        help="Initial sleep before retrying transient OpenAI request failures; backoff is exponential and capped.",
    )
    parser.add_argument(
        "--llm-progress-interval",
        type=int,
        default=100,
        help="Log LLM correction progress every N uncached rows per RQ batch flush.",
    )
    parser.add_argument(
        "--llm-dry-run",
        action="store_true",
        help="Populate deterministic/final columns and trigger reasons without API calls.",
    )
    parser.add_argument(
        "--llm-cache-only",
        action="store_true",
        help=(
            "When LLM correction is enabled, use only cached LLM decisions and do not "
            "send API requests. Combine with --llm-fail-closed to fail on any cache miss."
        ),
    )
    parser.add_argument(
        "--llm-fail-closed",
        action="store_true",
        help="Fail aggregation if an enabled LLM correction request fails.",
    )
    parser.add_argument(
        "--llm-env-file",
        type=Path,
        default=Path(__file__).resolve().parents[1] / ".env.local",
        help="Untracked env file containing OPENAI_API_KEY for enabled LLM correction.",
    )
    parser.add_argument(
        "--per-repo-progress",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "When per_repo_outputs sidecars exist and --workers=1, stream from sidecars "
            "and log repo-level progress. Use --no-per-repo-progress for legacy root JSONL streaming."
        ),
    )
    parser.add_argument(
        "--progress-log-interval-seconds",
        type=float,
        default=30.0,
        help="Emit per-repo Phase 2D progress at least this often for large sidecar files.",
    )
    parser.add_argument(
        "--progress-percent-step",
        type=int,
        default=10,
        help="Emit per-repo Phase 2D progress whenever this percentage step is crossed.",
    )
    args = parser.parse_args()

    run_started = time.monotonic()
    input_dir = args.input_dir
    per_repo_dir = args.per_repo_dir or (input_dir / "per_repo_outputs")
    test_cases_path = input_dir / "test_cases.jsonl"

    if not test_cases_path.exists():
        raise FileNotFoundError(f"Missing {test_cases_path}")

    log_progress(f"Phase 2D aggregation started input_dir={input_dir}", started=run_started)
    log_progress(f"Loading test cases from {test_cases_path}", started=run_started)
    test_cases = load_test_cases(test_cases_path)
    log_progress(f"Loaded {len(test_cases)} test cases", started=run_started)

    static_by_key: Dict[str, Dict[str, Any]] | None = None
    static_load: StaticMetricsLoadResult | None = None
    static_metrics_path: Path | None = None
    if args.static_metrics_dir is not None:
        static_metrics_path = resolve_static_metrics_path(args.static_metrics_dir)
        if not static_metrics_path.exists():
            raise FileNotFoundError(
                f"Missing static metrics JSONL at {static_metrics_path} "
                f"(from --static-metrics-dir {args.static_metrics_dir})"
            )
        log_progress(f"Loading static metrics from {static_metrics_path}", started=run_started)
        static_load = load_static_metrics(static_metrics_path)
        static_by_key = static_load.by_key
        log_progress(
            f"  {static_load.unique_keys} unique keys "
            f"({static_load.rows_read} rows read, "
            f"{static_load.duplicate_rows} duplicate rows, "
            f"{static_load.rows_malformed} malformed)",
            started=run_started,
        )

    llm_corrector: LlmSemanticCorrector | None = None
    if args.enable_llm_correction or args.llm_dry_run:
        if args.enable_llm_correction and not args.llm_dry_run:
            api_key = load_openai_api_key_from_env_file(args.llm_env_file)
            if not api_key and args.llm_fail_closed:
                raise SystemExit(
                    "OPENAI_API_KEY is not set. Set it in the process environment or in "
                    f"{args.llm_env_file} before running with --enable-llm-correction --llm-fail-closed."
                )
        elif args.llm_dry_run:
            load_openai_api_key_from_env_file(args.llm_env_file)
        cache_dir = args.llm_cache_dir or (input_dir / ".llm_cache")
        llm_corrector = LlmSemanticCorrector(
            enabled=bool(args.enable_llm_correction),
            model=args.llm_model,
            cache=LlmSemanticCache(cache_dir),
            dry_run=bool(args.llm_dry_run),
            max_rows=max(0, int(args.llm_max_rows or 0)),
            fail_closed=bool(args.llm_fail_closed),
            cache_only=bool(args.llm_cache_only),
            batch_size=max(1, int(args.llm_batch_size or 1)),
            max_concurrent_requests=max(1, int(args.llm_concurrency or 1)),
            client_timeout_seconds=max(1, int(args.llm_timeout_seconds or 1)),
            client_retry_attempts=max(1, int(args.llm_retry_attempts or 1)),
            client_retry_sleep_seconds=max(0.0, float(args.llm_retry_sleep_seconds or 0.0)),
            progress_interval=max(1, int(args.llm_progress_interval or 1)),
            progress_stream=sys.stderr,
        )

    parallel_metadata: Dict[str, Any] = {"phase2d_parallel": False, "phase2d_workers": 1}
    workers = max(1, int(args.workers or 1))
    if llm_corrector is not None and workers > 1:
        log_progress(
            "LLM semantic correction is enabled; forcing --workers 1 so corrected final labels "
            "and summary counters stay consistent.",
            started=run_started,
        )
        workers = 1
    if workers > 1:
        partial_root = args.parallel_temp_dir or (input_dir / "_phase2d_partials")
        agg, n_feat, parallel_metadata = run_parallel_aggregation(
            input_dir=input_dir,
            per_repo_dir=per_repo_dir,
            test_cases=test_cases,
            workers=workers,
            static_by_key=static_by_key,
            static_load=static_load,
            partial_root=partial_root,
            keep_partials=args.keep_parallel_partials,
        )
        log_progress(f"{n_feat} unique features ingested across workers", started=run_started)
    else:
        agg = Aggregator(
            test_cases,
            input_dir,
            static_metrics_by_key=static_by_key,
            static_metrics_load=static_load,
            llm_corrector=llm_corrector,
        )

        sources = resolve_feature_sources(input_dir)
        use_per_repo_progress = bool(args.per_repo_progress and per_repo_dir.is_dir())
        if use_per_repo_progress:
            log_progress(f"Streaming features from per-repo sidecars at {per_repo_dir}", started=run_started)
        elif sources["expanded"]:
            log_progress(f"Merging direct test_body + expanded from {sources['expanded']}", started=run_started)
        elif sources["direct"]:
            log_progress(f"Streaming features (direct + hooks) from {sources['direct']}", started=run_started)
        else:
            log_progress("Streaming features from per-repo sidecars", started=run_started)

        edges_path = sources.get("helper_edges")
        if edges_path or per_repo_dir.is_dir():
            log_progress("Streaming helper edges before features for RQ1 wrapper detection", started=run_started)
            n_edges = 0
            edge_iter: Iterator[Dict[str, Any]]
            if use_per_repo_progress:
                edge_repos = repos_from_test_cases(test_cases)
                edge_iter = stream_repo_partition_helper_edges_with_progress(
                    repos=edge_repos,
                    per_repo_dir=per_repo_dir,
                    started=run_started,
                )
            else:
                edge_iter = iter_helper_edges(input_dir, per_repo_dir)
            for e in edge_iter:
                agg.ingest_helper_edge(e)
                n_edges += 1
            log_progress(f"{n_edges} helper edges counted", started=run_started)

        n_feat = 0
        if use_per_repo_progress:
            feature_iter = stream_repo_partition_features_with_progress(
                repos=repos_from_test_cases(test_cases),
                per_repo_dir=per_repo_dir,
                test_cases=test_cases,
                started=run_started,
                interval_seconds=float(args.progress_log_interval_seconds or 30.0),
                percent_step=int(args.progress_percent_step or 10),
            )
        else:
            feature_iter = stream_all_features(input_dir, per_repo_dir, test_cases)
        for f in feature_iter:
            agg.ingest_feature(f)
            n_feat += 1
            if n_feat % 500_000 == 0:
                log_progress(f"{n_feat} features ingested", started=run_started)
        log_progress(f"{n_feat} unique features ingested", started=run_started)

        agg.close_event_sinks()
    log_progress("Finalizing per-test summary tables", started=run_started)
    counts = agg.finalize()

    validation = validate_aggregation(agg, test_cases)
    print("Validation:", json.dumps(validation, indent=2), file=sys.stderr)

    for warn in validation.get("rq3_ast_warnings") or []:
        print(f"AST WARNING: {warn}", file=sys.stderr)

    if args.fail_on_ast_warning and validation.get("rq3_ast_warnings"):
        print("VALIDATION FAILED: AST/M3 coverage warnings present", file=sys.stderr)
        sys.exit(1)

    if validation["validation_errors"] and not args.skip_validation:
        print("VALIDATION FAILED:", file=sys.stderr)
        for err in validation["validation_errors"]:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    summary = {
        "input_dir": str(input_dir),
        "test_cases": len(test_cases),
        "features_ingested": n_feat,
        "static_metrics_dir": str(args.static_metrics_dir) if args.static_metrics_dir else None,
        "static_metrics_jsonl": str(static_metrics_path) if static_metrics_path else None,
        **parallel_metadata,
        **counts,
        **validation,
    }
    if llm_corrector is not None:
        summary["llm_semantic_correction"] = {
            "enabled": bool(args.enable_llm_correction),
            "dry_run": bool(args.llm_dry_run),
            "cache_only": bool(args.llm_cache_only),
            "model": args.llm_model,
            "cache_dir": str(args.llm_cache_dir or (input_dir / ".llm_cache")),
            "batch_size": max(1, int(args.llm_batch_size or 1)),
            "max_concurrent_requests": max(1, int(args.llm_concurrency or 1)),
            "progress_interval": max(1, int(args.llm_progress_interval or 1)),
            "rows_seen_by_corrector": llm_corrector.rows_seen,
            "rows_triggered": llm_corrector.rows_triggered,
            "rows_corrected_or_cached": llm_corrector.rows_corrected,
            "rows_guarded": llm_corrector.rows_guarded,
            "rows_cache_hits": llm_corrector.rows_cache_hits,
            "rows_sent_to_api": llm_corrector.rows_api_calls,
            "api_batches": llm_corrector.api_batches,
            "rows_dry_run_or_limited": llm_corrector.rows_dry_run_or_limited,
            "rows_failed_open": llm_corrector.rows_failed_open,
            "rows_cache_only_misses": llm_corrector.rows_cache_only_misses,
        }
    registry_rows = load_per_repo_registry_metrics(per_repo_dir)
    if registry_rows:
        summary["rq2_registry_rollup"] = summarize_registry_rollup(registry_rows)
        summary["rq2_registry_by_repo"] = registry_rows
    summary["rq2_review_queue_rows"] = len(getattr(agg, "rq2_review_rows", []))
    prov_gates = write_provenance_gates(input_dir)
    if prov_gates:
        summary["rq2_provenance_gates"] = prov_gates
    events_csv = input_dir / "rq2_input_events.csv"
    if events_csv.exists():
        build_audit_samples(events_csv, input_dir)
        summary["rq2_provenance_audit_sample"] = str(input_dir / "rq2_provenance_audit_sample.csv")
    (input_dir / "rq_aggregation_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2), file=sys.stderr)


if __name__ == "__main__":
    main()
