#!/usr/bin/env python3
"""
Build rq3_ast_vs_regex_locator_audit.csv from features JSONL.

Requires Phase 2B rows with locator_strategy_ast (after astPatternExtractor).
Compares AST strategy vs regex-inferred strategy per ui_action row.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "rq_aggregation"))

from pattern_classify import (
    classify_interaction,
    classify_locator_from_ui_action,
    locator_ast_audit_mismatch_type,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--features",
        required=True,
        help="Path to test_case_features_direct.jsonl or expanded",
    )
    ap.add_argument("--output", required=True, help="Output CSV path")
    ap.add_argument("--limit", type=int, default=0, help="Max rows (0=all)")
    ap.add_argument(
        "--mismatches-only",
        action="store_true",
        help="Only rows where ast != inferred",
    )
    args = ap.parse_args()

    fields = [
        "repo",
        "test_id",
        "framework",
        "line",
        "raw_code",
        "locator_strategy_ast",
        "locator_strategy_inferred",
        "locator_composition_ast",
        "locator_composition_inferred",
        "selector_literal_kind_ast",
        "selector_literal_kind_inferred",
        "selector_channel_ast",
        "selector_value_origin_ast",
        "locator_evidence_basis",
        "ast_confidence",
        "mismatch_type",
    ]

    rows = []
    n = 0
    with Path(args.features).open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("feature_type") != "ui_action":
                continue
            ast_s = (row.get("locator_strategy_ast") or "").strip()
            if not ast_s:
                continue
            raw = str(row.get("raw_code") or "")
            name = str(row.get("name") or "")
            fw = str(row.get("framework") or "")
            cat = classify_interaction(name, raw)
            inf = classify_locator_from_ui_action(
                name,
                raw,
                fw,
                str(row.get("source_kind") or ""),
                int(row.get("helper_depth") or 0),
                "ui_action",
                cat,
            )
            regex_s = inf.get("normalized_strategy", "")
            comp_ast = str(row.get("locator_composition_ast") or "")
            comp_inf = inf.get("locator_composition", "")
            sel_ast = str(row.get("selector_literal_kind_ast") or "")
            sel_inf = inf.get("selector_literal_kind", "")
            ast_conf = str(row.get("ast_confidence") or "")
            mismatch_type = locator_ast_audit_mismatch_type(
                ast_s, regex_s, comp_ast, comp_inf, sel_ast, sel_inf, ast_conf
            )
            if args.mismatches_only and mismatch_type == "match":
                continue
            basis = (
                "ast_call_chain"
                if row.get("callee_chain_json")
                else "ast_selector_argument"
            )
            rows.append(
                {
                    "repo": row.get("repo", ""),
                    "test_id": row.get("test_id", ""),
                    "framework": fw,
                    "line": row.get("line", ""),
                    "raw_code": raw[:400],
                    "locator_strategy_ast": ast_s,
                    "locator_strategy_inferred": regex_s,
                    "locator_composition_ast": comp_ast,
                    "locator_composition_inferred": comp_inf,
                    "selector_literal_kind_ast": sel_ast,
                    "selector_literal_kind_inferred": sel_inf,
                    "selector_channel_ast": row.get("selector_channel_ast", ""),
                    "selector_value_origin_ast": row.get("selector_value_origin_ast", ""),
                    "locator_evidence_basis": basis,
                    "ast_confidence": ast_conf,
                    "mismatch_type": mismatch_type,
                }
            )
            n += 1
            if args.limit and n >= args.limit:
                break

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    mism = sum(1 for r in rows if r["mismatch_type"] != "match")
    print(
        json.dumps(
            {
                "rows_written": len(rows),
                "mismatches": mism,
                "match_rate": round(1 - mism / len(rows), 4) if rows else None,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
