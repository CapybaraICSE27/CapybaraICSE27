#!/usr/bin/env python3
"""
Build a compact RQ3 pattern review bundle after Phase 2D.

Includes stratified samples (archetype × framework) and summary distributions.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List

SNIPPET_LIMIT = 1500

EVIDENCE_PACKET_FIELDS = [
    "file_path",
    "source_start_offset",
    "source_end_offset",
    "event_snippet",
    "enclosing_function_or_helper_snippet",
    "test_body_context_snippet",
    "snippet_truncated",
]

LOCATOR_STRUCTURED_FIELDS = [
    "selector_channel_ast",
    "selector_value_origin_ast",
    "selector_channel_basis",
]

SYNC_STRUCTURED_FIELDS = [
    "sync_call_kind_ast",
    "sync_arg_kind_ast",
]

LOCATOR_MANUAL_FIELDS = [
    "manual_locator_strategy_ok",
    "manual_locator_strategy_should_be",
    "manual_locator_composition_ok",
    "manual_locator_composition_should_be",
    "manual_selector_literal_kind_ok",
    "manual_selector_literal_kind_should_be",
    "manual_notes",
]

SYNC_MANUAL_FIELDS = [
    "manual_sync_pattern_ok",
    "manual_sync_pattern_should_be",
    "manual_sync_target_ok",
    "manual_sync_target_should_be",
    "manual_sync_arg_kind_ok",
    "manual_sync_arg_kind_should_be",
    "manual_notes",
]

WORKFLOW_MANUAL_FIELDS = [
    "manual_abstraction_kind_ok",
    "manual_abstraction_kind_should_be",
    "manual_workflow_evidence_ok",
    "manual_workflow_evidence_should_be",
    "manual_notes",
]

ARCHETYPE_MANUAL_FIELDS = [
    "manual_workflow_archetype_ok",
    "manual_workflow_archetype_should_be",
    "manual_notes",
]


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: List[Dict[str, Any]], extra_fields: List[str] | None = None) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    for ef in extra_fields or []:
        if ef not in fields:
            fields.append(ef)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


def write_csv_with_fields(path: Path, rows: List[Dict[str, Any]], fields: List[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


def stratified_sample(
    rows: List[Dict[str, str]],
    key_fn,
    per_bucket: int,
    seed: int,
    max_total: int = 0,
) -> List[Dict[str, str]]:
    by_bucket: Dict[Any, List[Dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_bucket[key_fn(row)].append(row)
    rng = random.Random(seed)
    out: List[Dict[str, str]] = []
    for _key in sorted(by_bucket.keys(), key=lambda k: str(k)):
        bucket = by_bucket[_key]
        rng.shuffle(bucket)
        out.extend(bucket[:per_bucket])
    if max_total and len(out) > max_total:
        rng.shuffle(out)
        out = out[:max_total]
    return out


def add_manual_and_evidence_fields(rows: List[Dict[str, str]], manual_fields: List[str]) -> List[Dict[str, str]]:
    for row in rows:
        for field in manual_fields:
            row.setdefault(field, "")
        if "workflow_top_two_sources_json" in row:
            row.setdefault("top_two_workflow_sources", row.get("workflow_top_two_sources_json") or "")
        raw = row.get("event_snippet") or row.get("raw_code") or ""
        row["event_snippet"] = raw[:SNIPPET_LIMIT]
        row["snippet_truncated"] = "true" if len(raw) > SNIPPET_LIMIT else "false"
        row.setdefault("file_path", row.get("source_file") or "")
        row.setdefault("source_start_offset", "")
        row.setdefault("source_end_offset", "")
        row.setdefault(
            "enclosing_function_or_helper_snippet",
            row.get("enclosing_function_or_callback_snippet") or row.get("helper_context_snippet") or "",
        )
        row.setdefault("test_body_context_snippet", row.get("test_body_or_helper_context_snippet") or "")
    return rows


def sync_call_kind_from_row(row: Dict[str, str]) -> str:
    existing = (row.get("sync_call_kind_ast") or "").strip()
    if existing:
        return existing
    raw = (row.get("raw_code") or "").strip()
    name = (row.get("name") or "").strip()
    sync_pattern = (row.get("sync_pattern") or "").strip()
    if sync_pattern == "assertion_retry_wait":
        return "assertion"
    if sync_pattern == "predicate_or_custom_condition":
        return "predicate"
    lowered = f"{name} {raw}".lower()
    if ".wait" in lowered or lowered.endswith("wait") or "wait(" in lowered:
        return "wait_api"
    if "topass" in lowered:
        return "predicate"
    return "unknown"


def add_structured_alias_fields(rows: List[Dict[str, str]], event_file: str) -> List[Dict[str, str]]:
    for row in rows:
        if event_file == "rq3_locator_pattern_events.csv":
            row.setdefault("selector_channel_ast", row.get("selector_channel") or "")
            row.setdefault("selector_value_origin_ast", row.get("selector_value_origin") or "")
            row.setdefault(
                "selector_channel_basis",
                row.get("selector_channel_basis")
                or row.get("locator_evidence_basis")
                or row.get("evidence_basis")
                or "",
            )
        elif event_file == "rq3_sync_pattern_events.csv":
            row.setdefault("sync_call_kind_ast", sync_call_kind_from_row(row))
            row.setdefault("sync_arg_kind_ast", row.get("sync_arg_kind") or "")
    return rows


def counter_from_column(rows: List[Dict[str, str]], col: str) -> Counter:
    c: Counter = Counter()
    for row in rows:
        c[row.get(col) or ""] += 1
    return c


def distribution_rows(counter: Counter, key_name: str = "value") -> List[Dict[str, Any]]:
    return [{key_name: k, "count": v} for k, v in counter.most_common()]


def incorrect_rows(rows: List[Dict[str, str]], ok_fields: List[str]) -> List[Dict[str, str]]:
    out = []
    for row in rows:
        if any((row.get(field) or "").strip().lower() == "incorrect" for field in ok_fields):
            out.append(row)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=Path, required=True, help="Phase 2D output directory")
    ap.add_argument(
        "--bundle-dir",
        type=Path,
        default=None,
        help="Output bundle dir (default: <run-dir>/review_bundle_rq3)",
    )
    ap.add_argument("--per-archetype", type=int, default=10)
    ap.add_argument("--per-framework", type=int, default=8)
    ap.add_argument("--per-audit-mismatch", type=int, default=50)
    ap.add_argument("--per-event-pattern", type=int, default=20)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    run_dir = args.run_dir.resolve()
    bundle_dir = (args.bundle_dir or (run_dir / "review_bundle_rq3")).resolve()
    bundle_dir.mkdir(parents=True, exist_ok=True)

    patterns_path = run_dir / "rq3_patterns_by_test.csv"
    patterns = read_csv(patterns_path)
    if not patterns:
        raise FileNotFoundError(f"Missing or empty {patterns_path}; run Phase 2D first.")

    # Stratified test sample: archetype × framework
    strat_tests = stratified_sample(
        patterns,
        lambda r: (r.get("workflow_archetype") or "mixed_or_unclear", r.get("framework") or ""),
        per_bucket=min(args.per_archetype, args.per_framework),
        seed=args.seed,
        max_total=500,
    )
    add_manual_and_evidence_fields(strat_tests, ARCHETYPE_MANUAL_FIELDS)
    write_csv(
        bundle_dir / "stratified_patterns_by_test_sample.csv",
        strat_tests,
        ARCHETYPE_MANUAL_FIELDS + EVIDENCE_PACKET_FIELDS,
    )

    # Also per-archetype only (larger cap per archetype)
    arch_only = stratified_sample(
        patterns,
        lambda r: r.get("workflow_archetype") or "mixed_or_unclear",
        per_bucket=args.per_archetype,
        seed=args.seed + 1,
    )
    add_manual_and_evidence_fields(arch_only, ARCHETYPE_MANUAL_FIELDS)
    write_csv(
        bundle_dir / "stratified_by_archetype_sample.csv",
        arch_only,
        ARCHETYPE_MANUAL_FIELDS + EVIDENCE_PACKET_FIELDS,
    )

    # Audit mismatches (non-match only)
    audit_path = run_dir / "rq3_ast_vs_regex_locator_audit.csv"
    audit_rows = read_csv(audit_path)
    audit_mism = [r for r in audit_rows if (r.get("mismatch_type") or "match") != "match"]
    audit_sample = stratified_sample(
        audit_mism,
        lambda r: r.get("mismatch_type") or "unknown",
        per_bucket=args.per_audit_mismatch,
        seed=args.seed + 2,
        max_total=300,
    )
    add_manual_and_evidence_fields(audit_sample, LOCATOR_MANUAL_FIELDS)
    write_csv(
        bundle_dir / "ast_vs_regex_audit_mismatch_sample.csv",
        audit_sample,
        LOCATOR_MANUAL_FIELDS + EVIDENCE_PACKET_FIELDS,
    )

    # Event pattern samples
    for event_file, pattern_col, extra_key_cols in [
        (
            "rq3_locator_pattern_events.csv",
            "normalized_strategy",
            ["locator_evidence_basis", "locator_composition_evidence_basis"],
        ),
        ("rq3_sync_pattern_events.csv", "sync_pattern", ["sync_evidence_basis"]),
        ("rq3_workflow_pattern_events.csv", "abstraction_kind", ["workflow_evidence_basis"]),
    ]:
        events = read_csv(run_dir / event_file)
        if not events:
            continue
        sample = stratified_sample(
            events,
            lambda r, col=pattern_col, extras=extra_key_cols: (
                r.get(col) or "unknown",
                *[r.get(extra) or "" for extra in extras],
            ),
            per_bucket=args.per_event_pattern,
            seed=args.seed + 3,
            max_total=400,
        )
        out_name = event_file.replace(".csv", "_stratified_sample.csv")
        if event_file == "rq3_locator_pattern_events.csv":
            manual_fields = LOCATOR_MANUAL_FIELDS
        elif event_file == "rq3_sync_pattern_events.csv":
            manual_fields = SYNC_MANUAL_FIELDS
        else:
            manual_fields = WORKFLOW_MANUAL_FIELDS
        add_structured_alias_fields(sample, event_file)
        add_manual_and_evidence_fields(sample, manual_fields)
        structured_fields: List[str] = []
        if event_file == "rq3_locator_pattern_events.csv":
            structured_fields = LOCATOR_STRUCTURED_FIELDS
        elif event_file == "rq3_sync_pattern_events.csv":
            structured_fields = SYNC_STRUCTURED_FIELDS
        write_csv(bundle_dir / out_name, sample, manual_fields + structured_fields + EVIDENCE_PACKET_FIELDS)
        if event_file == "rq3_sync_pattern_events.csv":
            write_csv(
                bundle_dir / "sync_evidence_basis_distribution.csv",
                distribution_rows(counter_from_column(events, "sync_evidence_basis"), "sync_evidence_basis"),
            )
        if event_file == "rq3_locator_pattern_events.csv":
            write_csv(
                bundle_dir / "locator_evidence_basis_distribution.csv",
                distribution_rows(counter_from_column(events, "locator_evidence_basis"), "locator_evidence_basis"),
            )
            write_csv(
                bundle_dir / "locator_composition_evidence_basis_distribution.csv",
                distribution_rows(
                    counter_from_column(events, "locator_composition_evidence_basis"),
                    "locator_composition_evidence_basis",
                ),
            )
        if event_file == "rq3_workflow_pattern_events.csv":
            write_csv(
                bundle_dir / "workflow_evidence_basis_distribution.csv",
                distribution_rows(counter_from_column(events, "workflow_evidence_basis"), "workflow_evidence_basis"),
            )

    # Distributions
    write_csv(
        bundle_dir / "workflow_archetype_distribution.csv",
        distribution_rows(counter_from_column(patterns, "workflow_archetype"), "workflow_archetype"),
    )
    write_csv(
        bundle_dir / "framework_distribution.csv",
        distribution_rows(counter_from_column(patterns, "framework"), "framework"),
    )

    # Copy core outputs (small enough for review)
    copy_names = [
        "rq3_patterns_by_repo.csv",
        "rq_aggregation_summary.json",
        "rq3_ast_vs_regex_locator_audit.csv",
    ]
    copied = []
    for name in copy_names:
        src = run_dir / name
        if src.exists():
            shutil.copy2(src, bundle_dir / name)
            copied.append(name)

    summary_path = run_dir / "rq_aggregation_summary.json"
    agg_summary = {}
    if summary_path.exists():
        agg_summary = json.loads(summary_path.read_text(encoding="utf-8"))

    locator_sample = read_csv(bundle_dir / "rq3_locator_pattern_events_stratified_sample.csv")
    sync_sample = read_csv(bundle_dir / "rq3_sync_pattern_events_stratified_sample.csv")
    workflow_sample = read_csv(bundle_dir / "rq3_workflow_pattern_events_stratified_sample.csv")
    manual_summary = {
        "usage_note": "Fill manual_*_ok as correct/incorrect/uncertain and *_should_be when incorrect. Accuracy denominators should exclude blank fields until review is complete.",
        "locator_rows": len(locator_sample),
        "sync_rows": len(sync_sample),
        "workflow_rows": len(workflow_sample),
        "test_level_workflow_archetype_rows": len(strat_tests),
        "locator_manual_reviewed_rows": sum(1 for r in locator_sample if (r.get("manual_locator_strategy_ok") or "").strip()),
        "sync_manual_reviewed_rows": sum(1 for r in sync_sample if (r.get("manual_sync_pattern_ok") or "").strip()),
        "workflow_manual_reviewed_rows": sum(1 for r in workflow_sample if (r.get("manual_abstraction_kind_ok") or "").strip()),
    }
    (bundle_dir / "rq3_manual_audit_summary.json").write_text(
        json.dumps(manual_summary, indent=2),
        encoding="utf-8",
    )
    write_csv_with_fields(
        bundle_dir / "rq3_locator_manual_audit_incorrect_detail.csv",
        incorrect_rows(locator_sample, ["manual_locator_strategy_ok", "manual_locator_composition_ok", "manual_selector_literal_kind_ok"]),
        list(locator_sample[0].keys()) if locator_sample else LOCATOR_MANUAL_FIELDS + EVIDENCE_PACKET_FIELDS,
    )
    write_csv_with_fields(
        bundle_dir / "rq3_sync_manual_audit_incorrect_detail.csv",
        incorrect_rows(sync_sample, ["manual_sync_pattern_ok", "manual_sync_target_ok", "manual_sync_arg_kind_ok"]),
        list(sync_sample[0].keys()) if sync_sample else SYNC_MANUAL_FIELDS + EVIDENCE_PACKET_FIELDS,
    )
    write_csv_with_fields(
        bundle_dir / "rq3_workflow_manual_audit_incorrect_detail.csv",
        incorrect_rows(workflow_sample, ["manual_abstraction_kind_ok", "manual_workflow_evidence_ok"]),
        list(workflow_sample[0].keys()) if workflow_sample else WORKFLOW_MANUAL_FIELDS + EVIDENCE_PACKET_FIELDS,
    )

    manifest = {
        "usage_note": (
            "Event *_stratified_sample.csv files are balanced by label for validation and now include "
            "manual correctness columns. Do not use sampled rows for prevalence. Use workflow_archetype_distribution.csv "
            "or rq3_patterns_by_test.csv for corpus-level shares."
        ),
        "ast_provenance_note": (
            "Phase 2B emits AST-located locator_strategy_ast / wait_subtype_ast fields. "
            "wait_subtype_ast is paired with sync_evidence_basis so numeric literals, "
            "wait APIs, assertion matchers, and symbol-name heuristics can be audited separately. "
            "Audit mismatch samples are retained as a regression check against legacy regex signals."
        ),
        "run_dir": str(run_dir),
        "bundle_dir": str(bundle_dir),
        "patterns_by_test_rows": len(patterns),
        "stratified_test_sample_rows": len(strat_tests),
        "stratified_archetype_sample_rows": len(arch_only),
        "audit_rows_total": len(audit_rows),
        "audit_mismatch_rows": len(audit_mism),
        "audit_mismatch_sample_rows": len(audit_sample),
        "copied_files": copied,
        "aggregation_summary": agg_summary,
        "sampling": {
            "per_archetype_framework_bucket": min(args.per_archetype, args.per_framework),
            "per_archetype": args.per_archetype,
            "per_audit_mismatch_type": args.per_audit_mismatch,
            "per_event_pattern": args.per_event_pattern,
            "seed": args.seed,
        },
    }
    (bundle_dir / "bundle_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
