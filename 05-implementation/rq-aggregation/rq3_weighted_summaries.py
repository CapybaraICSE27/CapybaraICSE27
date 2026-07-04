"""Event-, test-, and repo-weighted RQ3 pattern prevalence summaries."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from typing import Any, Dict, List, Tuple


def _counter_share(counter: Counter, total: int) -> List[Dict[str, Any]]:
    if total <= 0:
        return []
    rows = []
    for label, count in sorted(counter.items(), key=lambda x: (-x[1], x[0])):
        if not label:
            continue
        rows.append({
            "label": label,
            "count": count,
            "share": round(count / total, 6),
        })
    return rows


def build_event_weighted_summary(
    *,
    locator_events: int,
    locator_composition: Counter,
    locator_strategy: Counter,
    sync_events: int,
    sync_pattern: Counter,
    workflow_events: int,
    abstraction_kind: Counter,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in _counter_share(locator_composition, locator_events):
        rows.append({"dimension": "locator_composition", "weighting": "event", **item})
    for item in _counter_share(locator_strategy, locator_events):
        rows.append({"dimension": "locator_strategy", "weighting": "event", **item})
    for item in _counter_share(sync_pattern, sync_events):
        rows.append({"dimension": "sync_pattern", "weighting": "event", **item})
    for item in _counter_share(abstraction_kind, workflow_events):
        rows.append({"dimension": "workflow_abstraction", "weighting": "event", **item})
    return rows


def build_test_weighted_summary(by_key_values) -> List[Dict[str, Any]]:
    n_tests = len(by_key_values)
    if n_tests <= 0:
        return []

    loc_comp_tests: Counter = Counter()
    sync_tests: Counter = Counter()
    wf_tests: Counter = Counter()

    for agg in by_key_values:
        if agg.locator_event_count > 0:
            for comp in agg.locator_composition_counts:
                if agg.locator_composition_counts[comp] > 0:
                    loc_comp_tests[comp] += 1
        if agg.sync_pattern_counts:
            for sp in agg.sync_pattern_counts:
                if agg.sync_pattern_counts[sp] > 0:
                    sync_tests[sp] += 1
        if agg.abstraction_kind_counts:
            for ab in agg.abstraction_kind_counts:
                if agg.abstraction_kind_counts[ab] > 0:
                    wf_tests[ab] += 1

    rows: List[Dict[str, Any]] = []
    for item in _counter_share(loc_comp_tests, n_tests):
        rows.append({"dimension": "locator_composition", "weighting": "test", **item})
    for item in _counter_share(sync_tests, n_tests):
        rows.append({"dimension": "sync_pattern", "weighting": "test", **item})
    for item in _counter_share(wf_tests, n_tests):
        rows.append({"dimension": "workflow_abstraction", "weighting": "test", **item})
    return rows


def build_repo_weighted_summary(by_key_values) -> List[Dict[str, Any]]:
    by_repo: Dict[str, list] = defaultdict(list)
    for agg in by_key_values:
        if agg.repo:
            by_repo[agg.repo].append(agg)

    if not by_repo:
        return []

    # Per-repo shares, then mean across repos (equal repo weight).
    dim_counters: Dict[Tuple[str, str], List[float]] = defaultdict(list)

    for _repo, tests in by_repo.items():
        n = len(tests)
        if n <= 0:
            continue
        loc_comp = Counter()
        sync_p = Counter()
        wf_ab = Counter()
        for agg in tests:
            for comp, c in agg.locator_composition_counts.items():
                if c > 0:
                    loc_comp[comp] += 1
            for sp, c in agg.sync_pattern_counts.items():
                if c > 0:
                    sync_p[sp] += 1
            for ab, c in agg.abstraction_kind_counts.items():
                if c > 0:
                    wf_ab[ab] += 1
        for comp, c in loc_comp.items():
            dim_counters[("locator_composition", comp)].append(c / n)
        for sp, c in sync_p.items():
            dim_counters[("sync_pattern", sp)].append(c / n)
        for ab, c in wf_ab.items():
            dim_counters[("workflow_abstraction", ab)].append(c / n)

    rows: List[Dict[str, Any]] = []
    n_repos = len(by_repo)
    for (dimension, label), shares in sorted(dim_counters.items()):
        if not label:
            continue
        mean_share = sum(shares) / n_repos if n_repos else 0.0
        rows.append({
            "dimension": dimension,
            "weighting": "repo_mean",
            "label": label,
            "mean_test_prevalence_per_repo": round(mean_share, 6),
            "repos_with_label": len(shares),
            "repo_count": n_repos,
        })
    return rows


def write_weighted_summaries(output_dir, aggregator) -> None:
    from stream_io import write_csv

    by_values = list(aggregator.by_key.values())
    event_loc_comp: Counter = Counter()
    event_loc_strat: Counter = Counter()
    event_sync: Counter = Counter()
    event_wf: Counter = Counter()

    for agg in by_values:
        event_loc_comp.update(agg.locator_composition_counts)
        event_loc_strat.update(agg.locator_strategy_norm)
        event_sync.update(agg.sync_pattern_counts)
        event_wf.update(agg.abstraction_kind_counts)

    event_rows = build_event_weighted_summary(
        locator_events=aggregator.rq3_locator_sink.count,
        locator_composition=event_loc_comp,
        locator_strategy=event_loc_strat,
        sync_events=aggregator.rq3_sync_sink.count,
        sync_pattern=event_sync,
        workflow_events=aggregator.rq3_workflow_sink.count,
        abstraction_kind=event_wf,
    )
    test_rows = build_test_weighted_summary(by_values)
    repo_rows = build_repo_weighted_summary(by_values)

    write_csv(output_dir / "rq3_patterns_event_weighted_summary.csv", event_rows)
    write_csv(output_dir / "rq3_patterns_test_weighted_summary.csv", test_rows)
    write_csv(output_dir / "rq3_patterns_repo_weighted_summary.csv", repo_rows)
