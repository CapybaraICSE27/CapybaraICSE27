#!/usr/bin/env python3
"""Build RQ5 density, verification intent, and assertion-chain review bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from review_bundle_common import (
    copy_if_exists,
    distribution_rows,
    framework_summary,
    read_csv,
    stratified_sample,
    write_csv,
    write_manifest,
)

CHAIN_MANUAL_FIELDS = [
    "sample_origin",
    "repo",
    "test_id",
    "framework",
    "line",
    "name",
    "raw_code",
    "assertion_chain_root_id",
    "assertion_chain_index",
    "assertion_chain_length",
    "sampled_chain_anchor_key",
    "chain_group_size",
    "chain_group_indices_json",
    "chain_matcher_sequence_json",
    "non_assertion_chain_methods_json",
    "chain_group_rows_json",
    "assertion_matcher",
    "assertion_semantic_matcher_ast",
    "assertion_semantic_matcher_basis_ast",
    "assertion_subject_kind",
    "assertion_subject_basis_ast",
    "assertion_subject_root_ast",
    "assertion_subject_path_json",
    "assertion_subject_text_ast",
    "assertion_subject_semantic_role_ast",
    "assertion_subject_semantic_role_basis_ast",
    "assertion_callback_intent_hint_ast",
    "assertion_callback_intent_basis_ast",
    "assertion_callback_intent_hints_json",
    "assertion_callback_nested_assertion_count",
    "assertion_callback_nested_matchers_json",
    "assertion_callback_subject_properties_json",
    "assertion_callback_literal_args_json",
    "is_negated_assertion",
    "promise_modifier",
    "chai_modifier_deep",
    "assertion_modifiers_json",
    "assertion_chain_raw_code",
    "assertion_chain_raw_code_length",
    "assertion_chain_raw_code_truncated",
    "assertion_framework_context",
    "assertion_library_syntax",
    "is_soft_assertion",
    "is_grouped_assertion",
    "assertion_group_kind",
    "verification_intent",
    "verification_intent_deterministic",
    "verification_intent_llm",
    "verification_intent_final",
    "verification_intent_final_basis",
    "verification_intent_llm_trigger_reason",
    "verification_intent_llm_confidence",
    "verification_intent_llm_rationale",
    "verification_intent_llm_codebook_step",
    "llm_model",
    "llm_prompt_version",
    "llm_input_hash",
    "verification_intent_evidence_basis",
    "verification_intent_confidence",
    "verification_intent_matched_signal",
    "verification_intent_codebook_path",
    "manual_chain_ok",
    "manual_matcher_ok",
    "manual_notes",
]

INTENT_MANUAL_FIELDS = [
    "sample_origin",
    "repo",
    "test_id",
    "framework",
    "line",
    "name",
    "raw_code",
    "verification_intent",
    "verification_intent_deterministic",
    "verification_intent_llm",
    "verification_intent_final",
    "verification_intent_final_basis",
    "verification_intent_llm_trigger_reason",
    "verification_intent_llm_confidence",
    "verification_intent_llm_rationale",
    "verification_intent_llm_codebook_step",
    "llm_model",
    "llm_prompt_version",
    "llm_input_hash",
    "verification_intent_evidence_basis",
    "verification_intent_confidence",
    "verification_intent_matched_signal",
    "verification_intent_codebook_path",
    "assertion_matcher",
    "assertion_semantic_matcher_ast",
    "assertion_semantic_matcher_basis_ast",
    "assertion_subject_kind",
    "assertion_subject_basis_ast",
    "assertion_subject_root_ast",
    "assertion_subject_path_json",
    "assertion_subject_text_ast",
    "assertion_subject_semantic_role_ast",
    "assertion_subject_semantic_role_basis_ast",
    "assertion_callback_intent_hint_ast",
    "assertion_callback_intent_basis_ast",
    "assertion_callback_intent_hints_json",
    "assertion_callback_nested_assertion_count",
    "assertion_callback_nested_matchers_json",
    "assertion_callback_subject_properties_json",
    "assertion_callback_literal_args_json",
    "assertion_framework_context",
    "assertion_library_syntax",
    "manual_intent_ok",
    "manual_intent_should_be",
    "manual_notes",
]

CHAIN_COVERAGE_FIELDS = [
    "framework",
    "test_count",
    "assertions_with_chain_fields",
    "assertions_missing_chain_metadata_count",
    "chained_assertion_count",
    "soft_assertion_count",
    "soft_assertion_chain_count",
    "chain_metadata_coverage_fraction",
]


def stable_seed_offset(value: str, modulo: int = 1000) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:12], 16) % modulo


def event_key(row: Dict[str, str]) -> tuple[str, ...]:
    return (
        row.get("repo") or "",
        row.get("test_id") or "",
        row.get("line") or "",
        row.get("name") or "",
        row.get("assertion_chain_root_id") or "",
        row.get("assertion_chain_index") or "",
        row.get("raw_code") or "",
    )


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_json_list(value: str) -> List[Any]:
    if not value:
        return []
    try:
        loaded = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return loaded if isinstance(loaded, list) else []


def chain_group_key(row: Dict[str, str]) -> tuple[str, str, str]:
    return (
        row.get("repo") or "",
        row.get("test_id") or "",
        row.get("assertion_chain_root_id") or "",
    )


def sorted_chain_group(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    return sorted(rows, key=lambda r: (_int(r.get("assertion_chain_index")), event_key(r)))


def matcher_sequence_from_group(rows: List[Dict[str, str]]) -> List[str]:
    sequence: List[str] = []
    for row in sorted_chain_group(rows):
        matcher = row.get("assertion_matcher") or ""
        semantic = row.get("assertion_semantic_matcher_ast") or ""
        if semantic and semantic != matcher:
            sequence.append(f"{matcher}:{semantic}")
        elif matcher:
            sequence.append(matcher)
    return sequence


def chain_group_rows_packet(rows: List[Dict[str, str]]) -> str:
    packet = []
    for row in sorted_chain_group(rows):
        packet.append(
            {
                "assertion_chain_index": row.get("assertion_chain_index") or "",
                "assertion_matcher": row.get("assertion_matcher") or "",
                "assertion_semantic_matcher_ast": row.get("assertion_semantic_matcher_ast") or "",
                "line": row.get("line") or "",
                "name": row.get("name") or "",
                "verification_intent": row.get("verification_intent") or "",
                "raw_code": (row.get("raw_code") or "")[:500],
            }
        )
    return json.dumps(packet, ensure_ascii=False)


def chain_group_evidence(
    row: Dict[str, str],
    group_rows: List[Dict[str, str]],
    anchor_key: tuple[str, ...],
) -> Dict[str, str]:
    ordered = sorted_chain_group(group_rows)
    matcher_sequence = _safe_json_list(row.get("chain_matcher_sequence_json") or "")
    if not matcher_sequence:
        matcher_sequence = matcher_sequence_from_group(ordered)
    non_assertion_methods = _safe_json_list(row.get("non_assertion_chain_methods_json") or "")
    if not non_assertion_methods:
        for sibling in ordered:
            non_assertion_methods = _safe_json_list(sibling.get("non_assertion_chain_methods_json") or "")
            if non_assertion_methods:
                break
    return {
        "sampled_chain_anchor_key": "|".join(anchor_key),
        "chain_group_size": str(len(ordered)),
        "chain_group_indices_json": json.dumps(
            [r.get("assertion_chain_index") or "" for r in ordered],
            ensure_ascii=False,
        ),
        "chain_matcher_sequence_json": json.dumps(matcher_sequence, ensure_ascii=False),
        "non_assertion_chain_methods_json": json.dumps(non_assertion_methods, ensure_ascii=False),
        "chain_group_rows_json": chain_group_rows_packet(ordered),
    }


def combine_intent_samples(
    *,
    baseline: List[Dict[str, str]],
    focused: List[Dict[str, str]],
    max_total: int,
) -> List[Dict[str, str]]:
    """Keep focused unknown/unmapped rows while preserving broad intent coverage."""
    out: List[Dict[str, str]] = []
    seen: set[tuple[str, ...]] = set()
    for row in focused + baseline:
        key = event_key(row)
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
        if max_total and len(out) >= max_total:
            break
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Build RQ5 review bundle")
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--bundle-dir", type=Path, default=None)
    ap.add_argument("--chain-per-framework", type=int, default=50)
    ap.add_argument("--intent-sample", type=int, default=120)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    run_dir = args.run_dir.resolve()
    bundle_dir = (args.bundle_dir or (run_dir / "review_bundle_rq5")).resolve()
    bundle_dir.mkdir(parents=True, exist_ok=True)

    events = read_csv(run_dir / "rq5_assertion_events.csv")
    by_test = read_csv(run_dir / "rq5_assertion_complexity_by_test.csv")
    if not events:
        raise FileNotFoundError("Missing rq5_assertion_events.csv")

    write_csv(
        bundle_dir / "rq5_verification_intent_distribution.csv",
        distribution_rows(Counter(r.get("verification_intent") or "" for r in events), "verification_intent"),
    )
    write_csv(
        bundle_dir / "rq5_verification_intent_evidence_basis_distribution.csv",
        distribution_rows(
            Counter(r.get("verification_intent_evidence_basis") or "missing_basis" for r in events),
            "verification_intent_evidence_basis",
        ),
    )

    write_csv(
        bundle_dir / "rq5_assertion_density_summary.csv",
        framework_summary(
            by_test,
            [
                ("assertion_count", "sum"),
                ("chained_assertion_count", "sum"),
                ("assertions_with_chain_fields", "sum"),
                ("assertions_missing_chain_metadata_count", "sum"),
                ("tests_with_no_assertions", "sum"),
            ],
        ),
    )

    # Chain coverage by framework (aggregated from per-test rows)
    chain_by_framework: Dict[str, Dict[str, Any]] = {}
    for row in by_test:
        fw = row.get("framework") or "Unknown"
        rec = chain_by_framework.setdefault(
            fw,
            {
                "framework": fw,
                "test_count": 0,
                "assertions_with_chain_fields": 0,
                "assertions_missing_chain_metadata_count": 0,
                "chained_assertion_count": 0,
                "soft_assertion_count": 0,
                "soft_assertion_chain_count": 0,
            },
        )
        tagged = int(row.get("assertions_with_chain_fields") or 0)
        missing = int(row.get("assertions_missing_chain_metadata_count") or 0)
        rec["test_count"] += 1
        rec["assertions_with_chain_fields"] += tagged
        rec["assertions_missing_chain_metadata_count"] += missing
        rec["chained_assertion_count"] += int(row.get("chained_assertion_count") or 0)
        rec["soft_assertion_count"] += int(row.get("soft_assertion_count") or 0)
        rec["soft_assertion_chain_count"] += int(row.get("soft_assertion_chain_count") or 0)
    chain_cov = []
    for rec in sorted(chain_by_framework.values(), key=lambda r: r["framework"]):
        total = rec["assertions_with_chain_fields"] + rec["assertions_missing_chain_metadata_count"]
        rec["chain_metadata_coverage_fraction"] = (
            round(rec["assertions_with_chain_fields"] / total, 6) if total else ""
        )
        chain_cov.append(rec)
    write_csv(bundle_dir / "rq5_chain_coverage_by_framework.csv", chain_cov, CHAIN_COVERAGE_FIELDS)

    chained = [r for r in events if int(r.get("assertion_chain_length") or 0) > 1]
    with_chain = [r for r in events if (r.get("assertion_chain_root_id") or "").strip()]
    groups_by_root: Dict[tuple[str, str, str], List[Dict[str, str]]] = {}
    for row in with_chain:
        groups_by_root.setdefault(chain_group_key(row), []).append(row)

    chain_sample: List[Dict[str, str]] = []
    for fw in sorted({r.get("framework") or "Unknown" for r in with_chain}):
        fw_rows = [r for r in with_chain if (r.get("framework") or "Unknown") == fw]
        chain_sample.extend(
            stratified_sample(
                fw_rows,
                lambda r: (r.get("assertion_chain_length") or "", r.get("assertion_matcher") or ""),
                per_bucket=max(5, args.chain_per_framework // 5),
                seed=args.seed + stable_seed_offset(fw),
                max_total=args.chain_per_framework,
            )
        )

    audit_chain: List[Dict[str, Any]] = []
    seen_chain_rows: set[tuple[str, ...]] = set()
    for row in chain_sample:
        anchor_key = event_key(row)
        group_rows = groups_by_root.get(chain_group_key(row), [row])
        evidence = chain_group_evidence(row, group_rows, anchor_key)
        for member in sorted_chain_group(group_rows):
            key = event_key(member)
            if key in seen_chain_rows:
                continue
            seen_chain_rows.add(key)
            audit_chain.append(
                {
                    "sample_origin": "chain_stratified_group",
                    **{k: member.get(k, "") for k in CHAIN_MANUAL_FIELDS if not k.startswith("manual_")},
                    **evidence,
                    "manual_chain_ok": "",
                    "manual_matcher_ok": "",
                    "manual_notes": "",
                }
            )
    write_csv(bundle_dir / "rq5_assertion_chain_sample.csv", audit_chain, CHAIN_MANUAL_FIELDS)

    unknown_or_unmapped_pool = [
        r
        for r in events
        if (r.get("verification_intent") or "") in ("unspecified", "generic_assertion", "")
        or (r.get("verification_intent") or "").startswith("ui_")
    ]
    broad_intent_sample = stratified_sample(
        events,
        lambda r: (
            r.get("framework") or "",
            r.get("verification_intent") or "",
            r.get("verification_intent_evidence_basis") or "",
        ),
        per_bucket=4,
        seed=args.seed + 7,
        max_total=args.intent_sample,
    )
    focused_intent_sample = stratified_sample(
        unknown_or_unmapped_pool,
        lambda r: (
            r.get("framework") or "",
            r.get("verification_intent") or "",
            r.get("verification_intent_evidence_basis") or "",
        ),
        per_bucket=8,
        seed=args.seed + 17,
        max_total=max(0, min(args.intent_sample // 3, len(unknown_or_unmapped_pool))),
    )
    intent_sample = combine_intent_samples(
        baseline=broad_intent_sample,
        focused=focused_intent_sample,
        max_total=args.intent_sample,
    )
    intent_audit = []
    for row in intent_sample:
        intent_audit.append(
            {
                "sample_origin": "verification_intent",
                **{k: row.get(k, "") for k in INTENT_MANUAL_FIELDS if not k.startswith("manual_")},
                "manual_intent_ok": "",
                "manual_intent_should_be": "",
                "manual_notes": "",
            }
        )
    write_csv(bundle_dir / "rq5_verification_intent_sample.csv", intent_audit, INTENT_MANUAL_FIELDS)

    copied = copy_if_exists(
        run_dir,
        bundle_dir,
        ["rq5_assertion_complexity_by_test.csv", "rq_aggregation_summary.json"],
    )

    summary = {}
    sp = run_dir / "rq_aggregation_summary.json"
    if sp.exists():
        summary = json.loads(sp.read_text(encoding="utf-8"))

    manifest = {
        "usage_note": (
            "Chain sample is stratified by framework (~50 per major framework). "
            "Sampled chain roots are expanded to all sibling matcher rows, with "
            "chain_matcher_sequence_json and chain_group_rows_json for manual chain-length review. "
            "Report assertions_with_chain_fields and assertions_missing_chain_metadata_count with all chain tables. "
            "Matcher-level vs chain-level soft/grouped counts documented in RQ5_ASSERTION_CHAIN_TAXONOMY.md."
        ),
        "run_dir": str(run_dir),
        "assertion_event_rows": len(events),
        "chained_assertion_event_rows": len(chained),
        "chain_sample_rows": len(audit_chain),
        "copied_files": copied,
        "milestone1_rq5_density": summary.get("milestone1_rq5_density"),
        "milestone3_rq5_assertion_chains": summary.get("milestone3_rq5_assertion_chains"),
    }
    write_manifest(bundle_dir, manifest)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
