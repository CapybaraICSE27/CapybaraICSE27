#!/usr/bin/env python3
"""Build compact RQ2 review bundle after Phase 2C + rq_aggregation."""

from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "rq_aggregation"))
from input_classify import classify_rq2_value_bearing_input
from input_plausibility import map_input_plausibility_paper_label
from rq2_audit_fields import REVIEW_BUNDLE_AUDIT_FIELDS, RQ2_AUDIT_EVIDENCE_FIELDS

RQ2_REVIEW_QUEUE_ENRICH_FIELDS = [
    "input_plausibility_codebook_path",
    "input_target_role_ast",
    "input_target_role_basis_ast",
    "input_target_context_ast",
    "input_target_context_normalized_ast",
    "input_target_context_basis_ast",
    "input_value_expression_kind_ast",
    "input_endpoint_construction_ast",
    "input_endpoint_construction_basis_ast",
    "llm_model",
    "llm_prompt_version",
    "llm_input_hash",
    "input_plausibility_pre_adjudication_final",
    "input_plausibility_adjudication_label",
    "input_plausibility_adjudication_confidence",
    "input_plausibility_adjudication_trigger_reason",
    "input_plausibility_adjudication_codebook_step",
    "input_plausibility_adjudication_rationale",
    "input_origin_kind",
    "input_origin_evidence",
    "rq2_value_bearing_input",
    "rq2_value_exclusion_reason",
    "rq2_value_bearing_basis",
    "external_file_path",
    "field_path",
    "linked_definition_file",
    "linked_definition_line",
    "is_static_file_candidate",
]


def rq2_value_boundary(row: Dict[str, str]) -> Tuple[str, str, str]:
    flag = str(row.get("rq2_value_bearing_input") or "").strip().lower()
    if flag in {"true", "false"}:
        return (
            flag,
            row.get("rq2_value_exclusion_reason", ""),
            row.get("rq2_value_bearing_basis", "") or "precomputed",
        )
    return classify_rq2_value_bearing_input(row)


def is_value_bearing(row: Dict[str, str]) -> bool:
    return rq2_value_boundary(row)[0] == "true"


def with_value_boundary(row: Dict[str, str]) -> Dict[str, str]:
    out = dict(row)
    flag, reason, basis = rq2_value_boundary(out)
    out["rq2_value_bearing_input"] = flag
    out["rq2_value_exclusion_reason"] = reason
    out["rq2_value_bearing_basis"] = basis
    return out


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str] | None = None) -> None:
    if not rows:
        if fieldnames:
            with path.open("w", encoding="utf-8", newline="") as fh:
                csv.DictWriter(fh, fieldnames=fieldnames).writeheader()
            return
        path.write_text("", encoding="utf-8")
        return
    fields = fieldnames or list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


def distribution_rows(counter: Counter, key_name: str = "value") -> List[Dict[str, Any]]:
    return [{key_name: k, "count": v} for k, v in counter.most_common()]


def crosstab(rows: Iterable[Dict[str, str]], row_key: str, col_key: str) -> List[Dict[str, Any]]:
    counts: Counter[Tuple[str, str]] = Counter()
    for row in rows:
        counts[(row.get(row_key) or "", row.get(col_key) or "")] += 1
    out = [
        {row_key: rk, col_key: ck, "count": n}
        for (rk, ck), n in sorted(counts.items(), key=lambda x: (-x[1], x[0][0], x[0][1]))
    ]
    return out


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
    for key in sorted(by_bucket.keys(), key=lambda k: str(k)):
        bucket = by_bucket[key]
        rng.shuffle(bucket)
        out.extend(bucket[:per_bucket])
    if max_total and len(out) > max_total:
        rng.shuffle(out)
        out = out[:max_total]
    return out


def _audit_fields_from_row(row: Dict[str, str]) -> Dict[str, str]:
    out = {field: row.get(field, "") for field in RQ2_AUDIT_EVIDENCE_FIELDS}
    deterministic = out.get("input_plausibility_deterministic") or row.get("input_plausibility", "")
    final = out.get("input_plausibility_final") or deterministic
    out["input_plausibility_deterministic"] = deterministic
    out["input_plausibility_final"] = final
    out["input_plausibility_paper_label"] = out.get("input_plausibility_paper_label") or map_input_plausibility_paper_label(final)
    out["input_plausibility_review_family"] = out.get("input_plausibility_review_family") or _input_plausibility_review_family(row)
    if final and not out.get("input_plausibility_final_basis"):
        out["input_plausibility_final_basis"] = "deterministic"
    return out


def _input_plausibility_review_family(row: Dict[str, str]) -> str:
    text = " ".join(
        row.get(field, "")
        for field in (
            "raw_code",
            "value_summary",
            "field_context",
            "input_target_context_ast",
            "input_target_context_normalized_ast",
            "field_path",
            "input_plausibility_codebook_path",
        )
    ).lower()
    if any(token in text for token in ("setinputfiles", "selectfile", "upload", "file", "image", "video", "path.resolve", "path.join")):
        return "file_upload"
    if any(token in text for token in ("keyboard.press", "realpress", ".press(", "{enter}", "{tab}", "{ctrl}", "{meta}", "arrow")):
        return "keyboard_control"
    if any(token in text for token in ("apiwidget", "resourceurl", "datasource", "baseurl", "endpoint", "select route", "port", "methodselect", "startframe", "overlapsize", "table-modal-columns")):
        return "endpoint_resource_config"
    if any(token in text for token in ("invalid", "malformed", "nonmatching", "wrong", "bad", "empty", "expired", "preserve", "too")):
        return "validation_edge"
    if any(token in text for token in ("filterinput", "inputvalue", "replytextbox", "promptinput", "toneselect", "serialnumber", "modelnumber", "dosage form", "searchinput", "editor", "tiptap")):
        return "visible_member_target"
    if any(token in text for token in ("dummy", "sample", "hello", "foobar", "lorem", "ipsum", "test room")):
        return "weak_literal"
    return "other"


def _event_key(row: Dict[str, str]) -> Tuple[str, ...]:
    return (
        row.get("repo", ""),
        row.get("test_id", ""),
        row.get("line", ""),
        row.get("name", ""),
        (row.get("raw_code", "") or "")[:500],
        row.get("input_source_class", ""),
        row.get("input_plausibility", ""),
        row.get("value_summary", ""),
        row.get("input_channel", ""),
    )


def enrich_review_queue_from_events(
    review_queue: List[Dict[str, str]],
    events: List[Dict[str, str]],
) -> None:
    """Fill newer evidence columns for legacy review-queue CSVs.

    Older aggregation outputs wrote the queue before the structured RQ2 columns
    were added to the queue field list. The event CSV already contains those
    columns, so the bundle can safely recover them by joining on stable row
    identity without changing any labels or review reasons.
    """
    event_index: Dict[Tuple[str, ...], Dict[str, str]] = {}
    for row in events:
        key = _event_key(row)
        if key not in event_index:
            event_index[key] = row

    for row in review_queue:
        match = event_index.get(_event_key(row))
        if not match:
            continue
        for field in RQ2_REVIEW_QUEUE_ENRICH_FIELDS:
            if not row.get(field) and match.get(field):
                row[field] = match.get(field, "")


def build_source_plausibility_audit(
    events: List[Dict[str, str]],
    review_queue: List[Dict[str, str]],
    provenance_audit: List[Dict[str, str]],
    bundle_dir: Path,
    *,
    per_cell: int,
    seed: int,
) -> Dict[str, Any]:
    crosstab_rows = crosstab(events, "input_source_class", "input_plausibility")
    write_csv(bundle_dir / "source_plausibility_crosstab.csv", crosstab_rows)

    visibility_crosstab = crosstab(events, "input_source_class", "value_visibility")
    write_csv(bundle_dir / "source_visibility_crosstab.csv", visibility_crosstab)

    event_sample = stratified_sample(
        events,
        lambda r: (
            r.get("input_source_class") or "",
            r.get("input_plausibility") or "",
            r.get("input_evidence_basis") or "",
        ),
        per_bucket=per_cell,
        seed=seed,
        max_total=500,
    )
    review_sample = stratified_sample(
        review_queue,
        lambda r: (
            r.get("input_source_class") or "",
            r.get("input_plausibility") or "",
            r.get("input_evidence_basis") or "",
        ),
        per_bucket=max(3, per_cell // 2),
        seed=seed + 1,
        max_total=400,
    )

    audit_rows: List[Dict[str, Any]] = []
    for row in event_sample:
        audit_rows.append(
            {
                "sample_origin": "all_events_stratified",
                **_audit_fields_from_row(row),
                "review_reason": "",
                "manual_source_ok": "",
                "manual_plausibility_ok": "",
                "manual_plausibility_should_be": "",
                "manual_notes": "",
            }
        )
    for row in review_sample:
        audit_rows.append(
            {
                "sample_origin": "review_queue_stratified",
                **_audit_fields_from_row(row),
                "review_reason": row.get("review_reason", ""),
                "manual_source_ok": "",
                "manual_plausibility_ok": "",
                "manual_plausibility_should_be": "",
                "manual_notes": "",
            }
        )
    for row in provenance_audit:
        audit_rows.append(
            {
                "sample_origin": f"provenance_audit:{row.get('audit_bucket', '')}",
                **_audit_fields_from_row(row),
                "review_reason": "",
                "manual_source_ok": "",
                "manual_plausibility_ok": "",
                "manual_plausibility_should_be": "",
                "manual_notes": "",
            }
        )

    write_csv(bundle_dir / "source_plausibility_audit_sample.csv", audit_rows, REVIEW_BUNDLE_AUDIT_FIELDS)

    return {
        "source_plausibility_cells": len(crosstab_rows),
        "event_stratified_rows": len(event_sample),
        "review_queue_stratified_rows": len(review_sample),
        "provenance_audit_rows": len(provenance_audit),
        "audit_sample_total_rows": len(audit_rows),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Build RQ2 review bundle")
    ap.add_argument("--run-dir", type=Path, required=True, help="Phase 2C run + aggregation output dir")
    ap.add_argument("--bundle-dir", type=Path, default=None, help="Default: <run-dir>/review_bundle_rq2")
    ap.add_argument("--per-source-plausibility-cell", type=int, default=8)
    ap.add_argument("--per-audit-mismatch", type=int, default=40)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    run_dir = args.run_dir.resolve()
    bundle_dir = (args.bundle_dir or (run_dir / "review_bundle_rq2")).resolve()
    bundle_dir.mkdir(parents=True, exist_ok=True)

    events_path = run_dir / "rq2_input_events.csv"
    events = read_csv(events_path)
    if not events:
        raise FileNotFoundError(f"Missing or empty {events_path}; run rq_aggregation first.")
    events = [with_value_boundary(row) for row in events]
    value_events = [row for row in events if is_value_bearing(row)]
    excluded_control_events = [row for row in events if not is_value_bearing(row)]

    review_queue = read_csv(run_dir / "rq2_input_semantics_review_queue.csv")
    enrich_review_queue_from_events(review_queue, events)
    review_queue = [with_value_boundary(row) for row in review_queue]
    value_review_queue = [row for row in review_queue if is_value_bearing(row)]
    provenance_audit = read_csv(run_dir / "rq2_provenance_audit_sample.csv")
    provenance_audit = [with_value_boundary(row) for row in provenance_audit]
    value_provenance_audit = [row for row in provenance_audit if is_value_bearing(row)]
    audit_mism = [
        r for r in read_csv(run_dir / "rq2_ast_vs_regex_input_audit.csv")
        if (r.get("mismatch_type") or "match") != "match"
    ]
    audit_mism_fields = list(audit_mism[0].keys()) if audit_mism else [
        "repo",
        "test_id",
        "framework",
        "line",
        "name",
        "raw_code",
        "input_source_ast",
        "input_source_inferred",
        "mismatch_type",
        "input_plausibility",
        "value_visibility_ast",
        "manual_notes",
    ]
    if "manual_notes" not in audit_mism_fields:
        audit_mism_fields = [*audit_mism_fields, "manual_notes"]

    write_csv(
        bundle_dir / "input_source_class_distribution.csv",
        distribution_rows(Counter(r.get("input_source_class") or "" for r in value_events), "input_source_class"),
    )
    write_csv(
        bundle_dir / "input_plausibility_distribution.csv",
        distribution_rows(Counter(r.get("input_plausibility") or "" for r in value_events), "input_plausibility"),
    )
    write_csv(
        bundle_dir / "value_visibility_distribution.csv",
        distribution_rows(Counter(r.get("value_visibility") or "" for r in value_events), "value_visibility"),
    )
    write_csv(
        bundle_dir / "input_origin_kind_distribution.csv",
        distribution_rows(Counter(r.get("input_origin_kind") or "" for r in value_events), "input_origin_kind"),
    )
    write_csv(
        bundle_dir / "input_evidence_basis_distribution.csv",
        distribution_rows(Counter(r.get("input_evidence_basis") or "" for r in value_events), "input_evidence_basis"),
    )
    write_csv(
        bundle_dir / "excluded_control_reason_distribution.csv",
        distribution_rows(Counter(r.get("rq2_value_exclusion_reason") or "" for r in excluded_control_events), "rq2_value_exclusion_reason"),
    )

    audit_stats = build_source_plausibility_audit(
        value_events,
        value_review_queue,
        value_provenance_audit,
        bundle_dir,
        per_cell=args.per_source_plausibility_cell,
        seed=args.seed,
    )
    excluded_sample = stratified_sample(
        excluded_control_events,
        lambda r: (
            r.get("input_channel") or "",
            r.get("rq2_value_exclusion_reason") or "",
            r.get("rq2_value_bearing_basis") or "",
        ),
        per_bucket=20,
        seed=args.seed + 4,
        max_total=300,
    )
    excluded_rows = [
        {
            "sample_origin": "excluded_control_token",
            **_audit_fields_from_row(row),
            "review_reason": row.get("rq2_value_exclusion_reason", ""),
            "manual_source_ok": "",
            "manual_plausibility_ok": "",
            "manual_plausibility_should_be": "",
            "manual_notes": "",
        }
        for row in excluded_sample
    ]
    write_csv(bundle_dir / "rq2_excluded_control_token_sample.csv", excluded_rows, REVIEW_BUNDLE_AUDIT_FIELDS)

    mismatch_sample = stratified_sample(
        audit_mism,
        lambda r: r.get("mismatch_type") or "unknown",
        per_bucket=args.per_audit_mismatch,
        seed=args.seed + 2,
        max_total=300,
    )
    for row in mismatch_sample:
        row["manual_notes"] = ""
    write_csv(bundle_dir / "ast_vs_regex_input_mismatch_sample.csv", mismatch_sample, audit_mism_fields)

    review_sample = stratified_sample(
        value_review_queue,
        lambda r: r.get("review_reason") or "unknown",
        per_bucket=20,
        seed=args.seed + 3,
        max_total=400,
    )
    for row in review_sample:
        row["manual_notes"] = ""
    review_fields = list(value_review_queue[0].keys()) if value_review_queue else REVIEW_BUNDLE_AUDIT_FIELDS
    for field in RQ2_AUDIT_EVIDENCE_FIELDS:
        if field not in review_fields:
            review_fields.append(field)
    if "manual_notes" not in review_fields:
        review_fields = [*review_fields, "manual_notes"]
    if "manual_plausibility_should_be" not in review_fields:
        review_fields = [*review_fields, "manual_plausibility_should_be"]
    write_csv(bundle_dir / "review_queue_reason_sample.csv", review_sample, review_fields)

    copy_names = [
        "rq2_provenance_gates.json",
        "rq2_provenance_audit_sample_summary.json",
        "rq2_inputs_summary.csv",
        "rq_aggregation_summary.json",
    ]
    copied: List[str] = []
    for name in copy_names:
        src = run_dir / name
        if src.exists():
            shutil.copy2(src, bundle_dir / name)
            copied.append(name)

    agg_summary = {}
    summary_path = run_dir / "rq_aggregation_summary.json"
    if summary_path.exists():
        agg_summary = json.loads(summary_path.read_text(encoding="utf-8"))

    manifest = {
        "usage_note": (
            "source_plausibility_audit_sample.csv mixes stratified event samples, review-queue samples, "
            "and provenance audit rows for manual validation. Crosstab CSVs reflect corpus prevalence."
        ),
        "run_dir": str(run_dir),
        "bundle_dir": str(bundle_dir),
        "rq2_event_rows": len(events),
        "rq2_value_bearing_event_rows": len(value_events),
        "rq2_excluded_control_event_rows": len(excluded_control_events),
        "review_queue_rows": len(review_queue),
        "audit_mismatch_rows": len(audit_mism),
        "copied_files": copied,
        "source_plausibility_audit": audit_stats,
        "aggregation_summary": agg_summary,
        "sampling": {
            "per_source_plausibility_cell": args.per_source_plausibility_cell,
            "per_audit_mismatch_type": args.per_audit_mismatch,
            "seed": args.seed,
        },
    }
    (bundle_dir / "bundle_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
