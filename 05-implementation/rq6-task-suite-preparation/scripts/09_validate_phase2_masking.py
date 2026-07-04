#!/usr/bin/env python3
"""Validate RQ6 Phase 2 prompt masking before agent execution.

The validator checks that task prompts do not expose hidden reference-test
source code, source locations, helper names, selectors, or Playwright code
markers. It writes a durable report and can update manual review rows with
the resulting mask status.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


DEFAULT_SUITE_DIR = Path("rq6_outputs/rq6_phase2_task_suite_v2")

BLOCKED_PROMPT_MARKERS = [
    "await ",
    "expect(",
    "page.goto(",
    "page.locator(",
    "page.getBy",
    "locator(",
    "getByTestId",
    "data-testid",
    "test.describe(",
    "test(",
    "css=",
    "xpath=",
]

COMMON_CALL_NAMES = {
    "addEventListener",
    "afterAll",
    "afterEach",
    "async",
    "beforeAll",
    "beforeEach",
    "click",
    "close",
    "describe",
    "evaluate",
    "expect",
    "fill",
    "filter",
    "first",
    "getByLabel",
    "getByPlaceholder",
    "getByRole",
    "getByText",
    "getByTestId",
    "goto",
    "hover",
    "isVisible",
    "last",
    "locator",
    "not",
    "nth",
    "on",
    "page",
    "press",
    "reload",
    "scrollIntoViewIfNeeded",
    "selectOption",
    "setInputFiles",
    "test",
    "toBe",
    "toBeAttached",
    "toBeTruthy",
    "toBeVisible",
    "toContainText",
    "toEqual",
    "toHaveAttribute",
    "toHaveClass",
    "toHaveText",
    "toMatch",
    "toStrictEqual",
    "URL",
    "waitForLoadState",
    "waitForRequest",
    "waitForResponse",
    "waitForSelector",
    "waitForTimeout",
    "waitForURL",
}

ALLOWED_EXACT_PROMPT_TERMS = {
    "API",
    "CSS",
    "HTML",
    "MediaSource",
    "Playwright",
    "VMAP",
    "VueInstance",
    "linkToSelf",
    "swup:any",
    "useScroll",
}


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--suite-dir", type=Path, default=DEFAULT_SUITE_DIR)
    ap.add_argument("--fail-on-blocker", action="store_true")
    ap.add_argument(
        "--update-manual-review",
        action="store_true",
        help="Update manual_task_review.csv/jsonl mask_ok fields after validation.",
    )
    return ap.parse_args()


def read_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def read_csv(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: Sequence[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def normalize_text(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def strip_numbered_source(snippet: str) -> List[str]:
    lines: List[str] = []
    for line in str(snippet or "").splitlines():
        if ": " in line:
            prefix, rest = line.split(": ", 1)
            if prefix.strip().isdigit():
                lines.append(rest)
                continue
        lines.append(line)
    return lines


def extract_call_names(source_lines: Sequence[str]) -> List[str]:
    names: List[str] = []
    seen: set[str] = set()
    source = mask_string_literals("\n".join(source_lines))
    for pattern in [r"\b([A-Za-z_$][\w$]*)\s*\(", r"\.([A-Za-z_$][\w$]*)\s*\("]:
        for match in re.finditer(pattern, source):
            name = match.group(1)
            if name in seen or name in COMMON_CALL_NAMES:
                continue
            seen.add(name)
            names.append(name)
    return names


def mask_string_literals(source: str) -> str:
    def repl(match: re.Match[str]) -> str:
        quote = match.group("quote")
        return f"{quote}{quote}"

    return re.sub(r"""(?P<quote>['"`])(?P<value>(?:\\.|(?!\1).)*?)(?P=quote)""", repl, source, flags=re.DOTALL)


def extract_string_literals(source_lines: Sequence[str]) -> List[str]:
    source = "\n".join(source_lines)
    literals: List[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"""(?P<quote>['"`])(?P<value>(?:\\.|(?!\1).)*?)(?P=quote)""", source, re.DOTALL):
        value = match.group("value").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        literals.append(value)
    return literals


def looks_like_selector(value: str) -> bool:
    text = value.strip()
    lower = text.lower()
    if not text:
        return False
    if lower.startswith(("css=", "xpath=", "//", "data-testid=")):
        return True
    if "data-testid" in lower or "[data-" in lower or "[aria-" in lower:
        return True
    if text.startswith(("#", ".", "[", ">", ":")):
        return True
    if re.search(r"[.#][A-Za-z][\w-]+", text) and " " not in text:
        return True
    return False


def looks_like_route_or_path(value: str) -> bool:
    text = value.strip()
    return text.startswith(("/", "./", "../")) or bool(re.search(r"\.(html|json|ts|tsx|js|jsx|css)$", text))


def is_mask_sensitive_call_name(name: str) -> bool:
    if name in COMMON_CALL_NAMES or name in ALLOWED_EXACT_PROMPT_TERMS:
        return False
    if name.isupper():
        return False
    return bool(re.search(r"[a-z][A-Z]|[_$]", name))


def has_substantial_source_line(prompt_norm: str, source_lines: Sequence[str]) -> List[str]:
    leaked: List[str] = []
    for line in source_lines:
        line_norm = normalize_text(line)
        if len(line_norm) < 42:
            continue
        if line_norm in prompt_norm:
            leaked.append(line_norm[:160])
    return leaked


def add_finding(findings: List[Dict[str, Any]], severity: str, code: str, detail: str) -> None:
    findings.append({"severity": severity, "code": code, "detail": detail})


def prompt_semantics_from_packet(packet: Dict[str, Any]) -> Dict[str, Any]:
    draft_workflow = packet.get("draft_workflow") or {}
    if isinstance(draft_workflow, dict) and isinstance(draft_workflow.get("prompt_semantics"), dict):
        return draft_workflow["prompt_semantics"]
    source_review = packet.get("source_review_semantics") or {}
    if isinstance(source_review, dict) and isinstance(source_review.get("prompt_semantics"), dict):
        return source_review["prompt_semantics"]
    return {}


def validate_task(task: Dict[str, Any], packet: Dict[str, Any], manifest: Dict[str, Any]) -> Dict[str, Any]:
    task_id = str(task.get("task_id") or packet.get("task_id") or manifest.get("task_id") or "")
    prompt = str(task.get("prompt") or packet.get("agent_prompt") or "")
    prompt_norm = normalize_text(prompt)
    source_lines = strip_numbered_source(str(packet.get("source_snippet") or ""))
    source_file = str(manifest.get("source_file") or packet.get("source_file") or "")
    source_abs_path = str(packet.get("source_abs_path") or manifest.get("source_abs_path") or "")
    allowed_literal_context = normalize_text(
        " ".join(
            [
                str(manifest.get("test_name") or packet.get("test_name") or ""),
                " ".join(str(part) for part in packet.get("describe_path") or []),
                str((packet.get("draft_workflow") or {}).get("goal") or ""),
            ]
        )
    )
    findings: List[Dict[str, Any]] = []
    prompt_semantics = prompt_semantics_from_packet(packet)

    if not prompt:
        add_finding(findings, "blocker", "missing_prompt", "Task spec has no prompt.")

    for marker in BLOCKED_PROMPT_MARKERS:
        if marker in prompt:
            add_finding(findings, "blocker", "prompt_code_marker", f"Prompt contains code marker {marker!r}.")

    for forbidden_path in [source_file, source_abs_path]:
        if forbidden_path and forbidden_path in prompt:
            add_finding(findings, "blocker", "source_path_leak", f"Prompt contains hidden source path {forbidden_path!r}.")

    for term in prompt_semantics.get("blocked_terms") or []:
        term = str(term or "").strip()
        if term and re.search(rf"\b{re.escape(term)}\b", prompt):
            add_finding(findings, "blocker", "blocked_prompt_term", f"Prompt contains blocked semantic term {term!r}.")

    for line in has_substantial_source_line(prompt_norm, source_lines):
        add_finding(findings, "blocker", "source_line_overlap", f"Prompt contains substantial source line: {line!r}.")

    for name in extract_call_names(source_lines):
        if not is_mask_sensitive_call_name(name):
            continue
        if re.search(rf"\b{re.escape(name)}\b", prompt):
            add_finding(findings, "blocker", "hidden_helper_name_leak", f"Prompt contains source call/helper name {name!r}.")

    for literal in extract_string_literals(source_lines):
        if literal in ALLOWED_EXACT_PROMPT_TERMS:
            continue
        literal_norm = normalize_text(literal)
        if literal_norm and literal_norm in allowed_literal_context:
            continue
        if len(literal) < 3 or literal not in prompt:
            continue
        if looks_like_selector(literal):
            add_finding(findings, "blocker", "selector_literal_leak", f"Prompt contains selector-like literal {literal!r}.")
        elif looks_like_route_or_path(literal):
            add_finding(findings, "warning", "route_or_path_literal_overlap", f"Prompt contains route/path literal {literal!r}.")
        elif len(literal) >= 12:
            add_finding(findings, "warning", "source_literal_overlap", f"Prompt contains source string literal {literal!r}.")

    agent_test_file = str(task.get("agent_test_file") or "")
    if agent_test_file and agent_test_file not in prompt:
        add_finding(findings, "warning", "agent_file_not_in_prompt", "Prompt does not name the requested agent test file.")

    if prompt_semantics:
        semantic_confidence = str(prompt_semantics.get("semantic_confidence") or "").lower()
        if semantic_confidence == "low":
            add_finding(findings, "warning", "low_semantic_confidence", "Prompt semantics are low confidence.")
        if prompt_semantics.get("needs_manual_review"):
            add_finding(findings, "warning", "semantic_needs_manual_review", "Prompt semantics were marked for manual review.")
        if not prompt_semantics.get("expected_results"):
            add_finding(findings, "warning", "missing_semantic_expected_result", "Prompt semantics do not include an expected result.")
        if not prompt_semantics.get("user_workflow_steps"):
            add_finding(findings, "warning", "missing_semantic_user_workflow", "Prompt semantics do not include a user workflow step.")

    blocker_count = sum(1 for finding in findings if finding["severity"] == "blocker")
    warning_count = sum(1 for finding in findings if finding["severity"] == "warning")
    mask_ok = "yes" if blocker_count == 0 else "needs_revision"
    return {
        "task_id": task_id,
        "prompt_id": str(task.get("prompt_id") or task_id),
        "prompt_level": str(task.get("prompt_level") or "medium"),
        "prompt_policy_version": str(task.get("prompt_policy_version") or ""),
        "repo_full_name": str(task.get("repo_full_name") or packet.get("repo_full_name") or ""),
        "source_file": source_file,
        "test_name": str(manifest.get("test_name") or packet.get("test_name") or ""),
        "mask_ok": mask_ok,
        "blocker_count": blocker_count,
        "warning_count": warning_count,
        "finding_codes": ";".join(sorted({str(f["code"]) for f in findings})),
        "findings_json": json.dumps(findings, ensure_ascii=False, sort_keys=True),
    }


def load_prompt_task_rows(suite_dir: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for task in read_jsonl(suite_dir / "agent_task_specs.jsonl") or []:
        row = dict(task)
        task_id = str(row.get("task_id") or "")
        row.setdefault("prompt_level", "medium")
        row.setdefault("prompt_policy_version", "legacy_primary_medium")
        row.setdefault("prompt_id", f"{task_id}__primary_medium" if task_id else "primary_medium")
        rows.append(row)
    for task in read_jsonl(suite_dir / "agent_prompt_variants.jsonl") or []:
        rows.append(dict(task))
    return rows


def update_manual_review(suite_dir: Path, validation_rows: Sequence[Dict[str, Any]]) -> None:
    rows = read_csv(suite_dir / "manual_task_review.csv")
    if not rows:
        return
    by_task: Dict[str, Dict[str, Any]] = {}
    for row in validation_rows:
        task_id = str(row.get("task_id") or "")
        if str(row.get("prompt_id") or "").endswith("__primary_medium") or task_id not in by_task:
            by_task[task_id] = row
    for row in rows:
        validation = by_task.get(str(row.get("task_id") or ""))
        if not validation:
            row["mask_ok"] = "not_validated"
            row["mask_validation_blocker_count"] = ""
            row["mask_validation_warning_count"] = ""
            row["mask_validation_finding_codes"] = "missing_validation_row"
            continue
        row["mask_ok"] = validation["mask_ok"]
        row["mask_validation_blocker_count"] = validation["blocker_count"]
        row["mask_validation_warning_count"] = validation["warning_count"]
        row["mask_validation_finding_codes"] = validation["finding_codes"]
    write_csv(suite_dir / "manual_task_review.csv", rows)
    write_jsonl(suite_dir / "manual_task_review.jsonl", rows)


def main() -> None:
    args = parse_args()
    suite_dir = args.suite_dir
    task_rows = load_prompt_task_rows(suite_dir)
    packets = {str(row.get("task_id") or ""): row for row in read_jsonl(suite_dir / "source_review_packets.jsonl") or []}
    manifest = {str(row.get("task_id") or ""): row for row in read_jsonl(suite_dir / "rq6_tasks_manifest.jsonl") or []}

    task_ids_with_prompt_rows = {str(row.get("task_id") or "") for row in task_rows}
    missing_task_rows = sorted((set(packets) | set(manifest)) - task_ids_with_prompt_rows)
    for task_id in missing_task_rows:
        task_rows.append({"task_id": task_id})

    validation_rows: List[Dict[str, Any]] = []
    for task in task_rows:
        task_id = str(task.get("task_id") or "")
        validation_rows.append(
            validate_task(
                task,
                packets.get(task_id, {}),
                manifest.get(task_id, {}),
            )
        )

    summary = {
        "suite_dir": str(suite_dir),
        "tasks_validated": len(validation_rows),
        "mask_ok_counts": dict(sorted(Counter(row["mask_ok"] for row in validation_rows).items())),
        "prompt_level_counts": dict(sorted(Counter(row["prompt_level"] for row in validation_rows).items())),
        "mask_ok_counts_by_prompt_level": {
            level: dict(sorted(Counter(row["mask_ok"] for row in validation_rows if row["prompt_level"] == level).items()))
            for level in sorted({str(row["prompt_level"]) for row in validation_rows})
        },
        "tasks_with_blockers": sum(1 for row in validation_rows if int(row["blocker_count"]) > 0),
        "tasks_with_warnings": sum(1 for row in validation_rows if int(row["warning_count"]) > 0),
        "blocker_findings": dict(
            sorted(
                Counter(
                    finding["code"]
                    for row in validation_rows
                    for finding in json.loads(str(row["findings_json"] or "[]"))
                    if finding.get("severity") == "blocker"
                ).items()
            )
        ),
        "warning_findings": dict(
            sorted(
                Counter(
                    finding["code"]
                    for row in validation_rows
                    for finding in json.loads(str(row["findings_json"] or "[]"))
                    if finding.get("severity") == "warning"
                ).items()
            )
        ),
        "manual_review_updated": bool(args.update_manual_review),
    }

    write_csv(suite_dir / "mask_validation_findings.csv", validation_rows)
    write_jsonl(suite_dir / "mask_validation_findings.jsonl", validation_rows)
    (suite_dir / "mask_validation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    if args.update_manual_review:
        update_manual_review(suite_dir, validation_rows)

    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.fail_on_blocker and summary["tasks_with_blockers"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
