#!/usr/bin/env python3
"""Build RQ1 setup/teardown intent manual validation bundle."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

RQ_AGGREGATION_DIR = Path(__file__).resolve().parents[1] / "rq_aggregation"
if str(RQ_AGGREGATION_DIR) not in sys.path:
    sys.path.insert(0, str(RQ_AGGREGATION_DIR))

from setup_teardown_intent import (  # noqa: E402
    _is_diagnostic_cypress_task,
    _is_fixture_only_load,
    _is_read_only_ast_call,
    _is_runtime_lifecycle_call,
    _is_ui_clear_or_focus_chain,
    _is_value_construction_utility,
    _is_wait_synchronization_feature,
    is_eligible_setup_teardown_unit,
)

from review_bundle_common import (
    copy_if_exists,
    distribution_rows,
    framework_summary,
    read_csv,
    stratified_sample,
    write_csv,
    write_manifest,
)

MANUAL_FIELDS = [
    "sample_origin",
    "repo",
    "test_id",
    "framework",
    "line",
    "name",
    "raw_code",
    "feature_type",
    "source_kind",
    "phase",
    "scope",
    "primary_intent",
    "primary_intent_evidence_basis",
    "confidence",
    "needs_review",
    "review_reason",
    "uncertain_reason",
    "fallback_used",
    "structured_evidence_available",
    "helper_resolution_status",
    "child_setup_unit_count",
    "child_intent_counts_json",
    "dominant_child_intent",
    "mixed_intent_score",
    "eligibility_basis",
    "provenance_basis",
    "wrapper_only",
    "manual_eligibility_ok",
    "manual_phase_ok",
    "manual_scope_ok",
    "manual_intent_ok",
    "manual_suggested_phase",
    "manual_suggested_scope",
    "manual_suggested_intent",
    "manual_error_type",
    "manual_notes",
]

EXCLUDED_PATTERN_FAMILIES = [
    "wait_synchronization",
    "read_only_getter",
    "logging_only_cy_task",
    "ui_focus_chain",
    "value_construction_utility",
    "fixture_only_load",
    "app_lifecycle_call",
]

EXCLUDED_PATTERN_FIELDS = [
    "expected_exclusion_family",
    "eligibility_rejection_reason",
    "repo",
    "test_id",
    "framework",
    "file_path",
    "source_kind",
    "helper_depth",
    "attached_from_hook",
    "hook_instance_key",
    "line",
    "source_start_offset",
    "source_end_offset",
    "feature_type",
    "category",
    "name",
    "raw_code",
    "callee_chain_json",
    "literal_args_json",
    "framework_api_category",
    "framework_api_category_basis_ast",
    "input_source_class",
    "input_channel_ast",
    "is_load_site",
    "helper_resolution_status",
    "helper_body_phase_hint_ast",
    "helper_body_phase_hint_basis_ast",
    "statement_phase_hint_ast",
    "statement_phase_hint_basis_ast",
    "cypress_task_role_ast",
    "cypress_task_role_basis_ast",
    "cypress_command_role_ast",
    "cypress_command_role_basis_ast",
    "manual_eligibility_ok",
    "manual_notes",
]


def _audit_row(origin: str, row: Dict[str, str]) -> Dict[str, Any]:
    out = {k: row.get(k, "") for k in MANUAL_FIELDS if not k.startswith("manual_")}
    out["sample_origin"] = origin
    out["manual_eligibility_ok"] = ""
    out["manual_phase_ok"] = ""
    out["manual_scope_ok"] = ""
    out["manual_intent_ok"] = ""
    out["manual_suggested_phase"] = ""
    out["manual_suggested_scope"] = ""
    out["manual_suggested_intent"] = ""
    out["manual_error_type"] = ""
    out["manual_notes"] = ""
    return out


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "1.0", "true", "yes", "y"}


def _feature_sources(run_dir: Path) -> List[Path]:
    candidates = [
        run_dir / "test_case_features_expanded.jsonl",
        run_dir / "test_case_features_direct.jsonl",
    ]
    per_repo = run_dir / "per_repo_outputs"
    if per_repo.is_dir():
        candidates.extend(sorted(per_repo.glob("*.features_expanded.jsonl")))
        candidates.extend(sorted(per_repo.glob("*.features_direct.jsonl")))
    seen: set[Path] = set()
    out: List[Path] = []
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen or not path.exists():
            continue
        seen.add(resolved)
        out.append(path)
    return out


def _iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _excluded_pattern_family(feature: Dict[str, Any]) -> str:
    name = str(feature.get("name") or "")
    raw = str(feature.get("raw_code") or "")
    if _is_wait_synchronization_feature(feature, name, raw):
        return "wait_synchronization"
    if _is_read_only_ast_call(feature):
        return "read_only_getter"
    if _is_diagnostic_cypress_task(feature):
        return "logging_only_cy_task"
    if _is_ui_clear_or_focus_chain(name, raw, feature):
        return "ui_focus_chain"
    if _is_value_construction_utility(feature, name, raw):
        return "value_construction_utility"
    if _is_fixture_only_load(feature):
        return "fixture_only_load"
    if _is_runtime_lifecycle_call(feature):
        return "app_lifecycle_call"
    return ""


def _excluded_pattern_row(family: str, reason: str, feature: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: feature.get(k, "") for k in EXCLUDED_PATTERN_FIELDS}
    out["expected_exclusion_family"] = family
    out["eligibility_rejection_reason"] = reason
    out["manual_eligibility_ok"] = ""
    out["manual_notes"] = ""
    return out


def _collect_excluded_false_pattern_sample(
    run_dir: Path,
    *,
    per_family: int = 25,
) -> tuple[List[Dict[str, Any]], Counter]:
    rows: List[Dict[str, Any]] = []
    counts: Counter = Counter()
    target = set(EXCLUDED_PATTERN_FAMILIES)
    for path in _feature_sources(run_dir):
        for feature in _iter_jsonl(path):
            family = _excluded_pattern_family(feature)
            if not family or counts[family] >= per_family:
                continue
            eligible, reason = is_eligible_setup_teardown_unit(feature)
            if eligible:
                continue
            rows.append(_excluded_pattern_row(family, reason, feature))
            counts[family] += 1
            if target and all(counts[fam] >= per_family for fam in target):
                return rows, counts
    return rows, counts


def main() -> None:
    ap = argparse.ArgumentParser(description="Build RQ1 review bundle")
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--bundle-dir", type=Path, default=None)
    ap.add_argument("--intent-sample-total", type=int, default=200)
    ap.add_argument("--per-stratum", type=int, default=4)
    ap.add_argument("--review-queue-sample", type=int, default=150)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    run_dir = args.run_dir.resolve()
    bundle_dir = (args.bundle_dir or (run_dir / "review_bundle_rq1")).resolve()
    bundle_dir.mkdir(parents=True, exist_ok=True)

    intent_path = run_dir / "rq1_setup_teardown_intent_events.csv"
    events = read_csv(intent_path)
    if not events:
        raise FileNotFoundError(f"Missing {intent_path}; run rq_aggregation on v39 corpus first.")

    review_queue = read_csv(run_dir / "rq1_setup_teardown_intent_review_queue.csv")
    paper_events = [r for r in events if not _truthy(r.get("wrapper_only"))]
    paper_review_queue = [r for r in review_queue if not _truthy(r.get("wrapper_only"))]

    write_csv(
        bundle_dir / "rq1_intent_distribution.csv",
        distribution_rows(Counter(r.get("primary_intent") or "" for r in paper_events), "primary_intent"),
    )
    write_csv(
        bundle_dir / "rq1_phase_distribution.csv",
        distribution_rows(Counter(r.get("phase") or "" for r in paper_events), "phase"),
    )
    write_csv(
        bundle_dir / "rq1_scope_distribution.csv",
        distribution_rows(Counter(r.get("scope") or "" for r in paper_events), "scope"),
    )
    write_csv(
        bundle_dir / "rq1_confidence_distribution.csv",
        distribution_rows(Counter(r.get("confidence") or "" for r in paper_events), "confidence"),
    )
    write_csv(
        bundle_dir / "rq1_primary_intent_evidence_basis_distribution.csv",
        distribution_rows(
            Counter(r.get("primary_intent_evidence_basis") or "" for r in paper_events),
            "primary_intent_evidence_basis",
        ),
    )
    write_csv(
        bundle_dir / "rq1_needs_review_distribution.csv",
        distribution_rows(Counter(r.get("needs_review") or "" for r in paper_events), "needs_review"),
    )

    write_csv(
        bundle_dir / "rq1_by_framework_summary.csv",
        framework_summary(
            paper_events,
            [
                ("needs_review", "sum"),
                ("wrapper_only", "sum"),
            ],
        ),
    )

    intent_sample = stratified_sample(
        paper_events,
        lambda r: (
            r.get("framework") or "",
            r.get("confidence") or "",
            r.get("primary_intent") or "",
            r.get("primary_intent_evidence_basis") or "",
            r.get("needs_review") or "",
        ),
        per_bucket=args.per_stratum,
        seed=args.seed,
        max_total=args.intent_sample_total,
    )
    audit_rows = [_audit_row("intent_stratified", r) for r in intent_sample]

    rq_sample = stratified_sample(
        paper_review_queue,
        lambda r: (r.get("framework") or "", r.get("review_reason") or ""),
        per_bucket=max(3, args.per_stratum // 2),
        seed=args.seed + 1,
        max_total=args.review_queue_sample,
    )
    audit_rows.extend(_audit_row("review_queue", r) for r in rq_sample)

    write_csv(bundle_dir / "rq1_setup_teardown_intent_stratified_sample.csv", audit_rows, MANUAL_FIELDS)
    write_csv(
        bundle_dir / "rq1_review_queue_sample.csv",
        [_audit_row("review_queue", r) for r in rq_sample],
        MANUAL_FIELDS,
    )

    excluded_false_patterns, excluded_false_pattern_counts = _collect_excluded_false_pattern_sample(run_dir)
    write_csv(
        bundle_dir / "rq1_excluded_false_pattern_sample.csv",
        excluded_false_patterns,
        EXCLUDED_PATTERN_FIELDS,
    )

    copied = copy_if_exists(
        run_dir,
        bundle_dir,
        [
            "rq1_setup_teardown_intent_by_test.csv",
            "rq1_environment_control_events.csv",
            "rq_aggregation_summary.json",
        ],
    )

    summary = {}
    sp = run_dir / "rq_aggregation_summary.json"
    if sp.exists():
        summary = json.loads(sp.read_text(encoding="utf-8-sig"))

    manifest = {
        "usage_note": (
            "rq1_setup_teardown_intent_stratified_sample.csv is the primary manual validation sheet "
            f"(target ~{args.intent_sample_total} rows). Fill manual_* columns. "
            "Pair with milestone2_rq1_intent and rq3_ast_provenance from rq_aggregation_summary.json."
        ),
        "run_dir": str(run_dir),
        "bundle_dir": str(bundle_dir),
        "intent_event_rows": len(paper_events),
        "raw_intent_event_rows": len(events),
        "review_queue_rows": len(paper_review_queue),
        "raw_review_queue_rows": len(review_queue),
        "audit_sample_rows": len(audit_rows),
        "excluded_false_pattern_sample_rows": len(excluded_false_patterns),
        "excluded_false_pattern_counts": dict(excluded_false_pattern_counts),
        "copied_files": copied,
        "milestone2_rq1_intent": summary.get("milestone2_rq1_intent"),
        "sampling": {
            "intent_sample_total": args.intent_sample_total,
            "per_stratum": args.per_stratum,
            "review_queue_sample": args.review_queue_sample,
            "seed": args.seed,
        },
    }
    write_manifest(bundle_dir, manifest)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
