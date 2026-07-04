#!/usr/bin/env python3
"""Build RQ4 sequence + control-flow manual validation bundle."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from review_bundle_common import (
    copy_if_exists,
    distribution_rows,
    read_csv,
    stratified_sample,
    write_csv,
    write_manifest,
)

DEFAULT_REPO_CACHE = Path(r"<repo-cache>")
MAX_SNIPPET_CHARS = 1500

CF_MANUAL_FIELDS = [
    "sample_origin",
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
    "action_signature",
    "action_signature_v2",
    "ui_action_category",
    "terminal_action_ast",
    "callee_chain_json",
    "locator_strategy_ast",
    "input_channel_ast",
    "control_flow_enclosure",
    "control_flow_loop_depth",
    "control_flow_branch_depth",
    "control_flow_branch_kind",
    "control_flow_branch_arm",
    "control_flow_source",
    "control_flow_callback_method",
    "control_flow_callback_receiver",
    "control_flow_parent_kind",
    "control_flow_parent_line",
    "control_flow_parent_start_offset",
    "control_flow_parent_end_offset",
    "control_flow_ancestor_chain",
    "action_snippet",
    "enclosing_control_flow_snippet",
    "enclosing_function_or_callback_snippet",
    "test_body_or_helper_context_snippet",
    "snippet_truncated",
    "manual_enclosure_ok",
    "manual_notes",
]

NAV_MANUAL_FIELDS = [
    "sample_origin",
    "repo",
    "test_id",
    "framework",
    "source_file",
    "line",
    "name",
    "raw_code",
    "source_start_offset",
    "source_end_offset",
    "category",
    "navigation_target",
    "navigation_target_evidence_basis",
    "action_signature_json",
    "manual_target_ok",
    "manual_basis_ok",
    "manual_notes",
]

SEQ_MANUAL_FIELDS = [
    "repo",
    "test_id",
    "framework",
    "sequence_event_count",
    "test_body_sequence_event_count",
    "repeat_action_fraction",
    "test_body_repeat_action_fraction",
    "repeated_navigation_api_count",
    "navigation_target_revisit_count",
    "loop_driven_action_count",
    "branch_driven_action_count",
    "test_body_conditionalized_action_fraction",
    "ui_actions_with_control_flow_field_present",
    "ui_actions_with_control_flow_enclosure_non_none",
    "manual_notes",
]


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _truth_text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return "true" if str(value or "").strip().lower() in {"1", "true", "yes", "y"} else "false"


def _safe_repo_dir(repo: str) -> str:
    repo = str(repo or "").strip().replace("\\", "/").strip("/")
    if not repo:
        return ""
    parts = [p for p in repo.split("/") if p]
    joined = "__".join(parts) if len(parts) > 1 else repo
    return re.sub(r"[^A-Za-z0-9_.@+-]+", "__", joined)


def _candidate_source_paths(row: Dict[str, str], repo_cache: Path) -> List[Path]:
    candidates: List[Path] = []
    seen = set()
    repo = row.get("repo") or ""
    repo_dir = _safe_repo_dir(repo)
    for raw_path in (row.get("file_path"), row.get("source_file")):
        path_s = str(raw_path or "").strip()
        if not path_s:
            continue
        p = Path(path_s)
        if p.is_absolute():
            choices = [p]
        elif repo_dir:
            choices = [repo_cache / repo_dir / Path(path_s)]
        else:
            choices = [repo_cache / Path(path_s)]
        for choice in choices:
            key = str(choice)
            if key not in seen:
                seen.add(key)
                candidates.append(choice)
    return candidates


def _read_source(
    row: Dict[str, str],
    repo_cache: Path,
    source_cache: Dict[str, Optional[str]],
) -> Tuple[str, str]:
    for path in _candidate_source_paths(row, repo_cache):
        key = str(path)
        if key not in source_cache:
            try:
                source_cache[key] = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                source_cache[key] = None
        text = source_cache.get(key)
        if text:
            return text, key
    return "", ""


def _clip(text: str, max_chars: int = MAX_SNIPPET_CHARS) -> Tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def _slice_offsets(text: str, start: int, end: int, max_chars: int = MAX_SNIPPET_CHARS) -> Tuple[str, bool]:
    if not text or start < 0 or end <= start or start >= len(text):
        return "", False
    bounded_end = min(len(text), end)
    return _clip(text[start:bounded_end], max_chars)


def _slice_span_with_focus(
    text: str,
    span_start: int,
    span_end: int,
    focus_start: int,
    focus_end: int,
    max_chars: int = MAX_SNIPPET_CHARS,
) -> Tuple[str, bool]:
    if not text or span_start < 0 or span_end <= span_start:
        return "", False
    span_end = min(len(text), span_end)
    if span_end - span_start <= max_chars:
        return text[span_start:span_end], False
    if focus_end <= span_start or focus_start >= span_end:
        return text[span_start : min(span_end, span_start + max_chars)], True
    if focus_end - span_start <= max_chars:
        return text[span_start : min(span_end, span_start + max_chars)], True

    separator = "\n...\n"
    prefix_len = min(520, max_chars // 3)
    focus_budget = max_chars - prefix_len - len(separator)
    prefix = text[span_start : min(span_end, span_start + prefix_len)]
    focus_left = max(span_start + prefix_len, focus_start - max(0, (focus_budget - (focus_end - focus_start)) // 2))
    focus_right = min(span_end, focus_left + focus_budget)
    if focus_right < focus_end:
        focus_right = min(span_end, focus_end)
        focus_left = max(span_start + prefix_len, focus_right - focus_budget)
    return prefix + separator + text[focus_left:focus_right], True


def _window_around_offsets(
    text: str,
    start: int,
    end: int,
    max_chars: int = MAX_SNIPPET_CHARS,
) -> Tuple[str, bool]:
    if not text or start < 0 or start >= len(text):
        return "", False
    end = max(end, start + 1)
    width = max_chars
    left = max(0, start - max(0, (width - (end - start)) // 2))
    right = min(len(text), left + width)
    if right < min(len(text), end):
        right = min(len(text), end)
        left = max(0, right - width)
    return text[left:right], left > 0 or right < len(text)


def _line_for_offset(text: str, offset: int) -> str:
    if not text or offset < 0:
        return ""
    return str(text.count("\n", 0, min(offset, len(text))) + 1)


def _offset_for_line(text: str, line: int) -> int:
    if not text or line <= 1:
        return 0
    current_line = 1
    for idx, ch in enumerate(text):
        if ch == "\n":
            current_line += 1
            if current_line >= line:
                return idx + 1
    return len(text)


def _find_action_span_from_raw(text: str, row: Dict[str, str]) -> Tuple[int, int]:
    raw = str(row.get("raw_code") or "")
    if not text or not raw or "..." in raw:
        return -1, -1
    positions: List[int] = []
    pos = text.find(raw)
    while pos >= 0:
        positions.append(pos)
        pos = text.find(raw, pos + 1)
    if not positions:
        return -1, -1
    line_hint = _to_int(row.get("line"), 0)
    if line_hint > 0:
        line_offset = _offset_for_line(text, line_hint)
        positions.sort(key=lambda p: abs(p - line_offset))
    start = positions[0]
    return start, start + len(raw)


def _statement_start(text: str, token_start: int) -> int:
    floor = max(0, token_start - 1200)
    semicolon = text.rfind(";", floor, token_start)
    blank_line = text.rfind("\n\n", floor, token_start)
    start = max(semicolon + 1 if semicolon >= 0 else floor, blank_line + 2 if blank_line >= 0 else floor)
    while start < token_start and text[start].isspace():
        start += 1
    return start


def _balanced_span_end(text: str, start: int, action_end: int) -> int:
    limit = min(len(text), max(action_end + 1200, start + 3000))
    stack: List[str] = []
    opened = False
    pairs = {"(": ")", "{": "}", "[": "]"}
    closing = {")", "}", "]"}
    in_string = ""
    escape = False
    i = start
    while i < limit:
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_string:
                in_string = ""
            i += 1
            continue
        if ch in {"'", '"', "`"}:
            in_string = ch
            i += 1
            continue
        if ch in pairs:
            stack.append(pairs[ch])
            opened = True
        elif ch in closing:
            if stack and ch == stack[-1]:
                stack.pop()
                if opened and not stack and i >= action_end:
                    return min(len(text), i + 1)
            elif opened and not stack and i >= action_end:
                return min(len(text), i + 1)
        i += 1
    return min(len(text), max(action_end + 400, start + MAX_SNIPPET_CHARS))


CONTROL_FLOW_TOKEN_RE = re.compile(
    r"(?P<callback>\.(?:each|forEach|map|filter|some|every|reduce|findIndex|flatMap)\s*\()"
    r"|(?P<branch>\b(?:if|switch|try)\b\s*(?:\(|\{))"
    r"|(?P<loop>\b(?:for|while)\b\s*(?:await\s*)?\()"
    r"|(?P<do>\bdo\b\s*\{)",
    re.MULTILINE,
)


def _find_control_flow_span(text: str, action_start: int, action_end: int) -> Tuple[int, int, str, str]:
    if not text or action_start < 0:
        return -1, -1, "", ""
    matches = [m for m in CONTROL_FLOW_TOKEN_RE.finditer(text, 0, action_start)]
    for match in reversed(matches[-80:]):
        token_start = match.start()
        span_start = _statement_start(text, token_start) if match.group("callback") else token_start
        span_end = _balanced_span_end(text, span_start, action_end)
        if span_start <= action_start < span_end:
            if match.group("callback"):
                method = re.sub(r"[^A-Za-z]", "", match.group("callback"))
                return span_start, span_end, "callback_iteration", method
            if match.group("loop") or match.group("do"):
                return span_start, span_end, "loop", ""
            return span_start, span_end, "branch", ""
    return -1, -1, "", ""


def _find_callback_iteration_span(text: str, action_start: int, action_end: int) -> Tuple[int, int, str]:
    if not text or action_start < 0:
        return -1, -1, ""
    matches = [
        m
        for m in CONTROL_FLOW_TOKEN_RE.finditer(text, 0, action_start)
        if m.group("callback")
    ]
    for match in reversed(matches[-80:]):
        span_start = _statement_start(text, match.start())
        span_end = _balanced_span_end(text, span_start, action_end)
        method = re.sub(r"[^A-Za-z]", "", match.group("callback"))
        if span_start <= action_start < span_end:
            return span_start, span_end, method
        if span_start < action_start and action_start - span_start <= 6000:
            return span_start, min(len(text), action_end + 800), method
    return -1, -1, ""


def _parse_action_signature(row: Dict[str, str]) -> Dict[str, str]:
    raw = row.get("action_signature_v2") or row.get("action_signature_json") or ""
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(k): str(v) for k, v in payload.items() if v is not None}


def _normalized_action_signature(category: str, name: str) -> str:
    cat = " ".join(str(category or "unknown_action").strip().lower().split())
    n = " ".join(str(name or "").strip().lower().split())
    return f"{cat}|{n}" if n else cat


def _compact_code(value: str) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def _action_snippet_matches_row(snippet: str, row: Dict[str, str]) -> bool:
    raw = _compact_code(row.get("raw_code") or "")
    got = _compact_code(snippet)
    if not raw:
        return bool(got)
    if not got:
        return False
    probes = [raw]
    if len(raw) > 80:
        probes.extend([raw[:80], raw[-80:]])
    elif len(raw) > 30:
        probes.append(raw[:30])
    if any(p and p in got for p in probes):
        return True
    name = str(row.get("name") or "")
    terminal = re.split(r"[.\s(]+", name.strip())[-1] if name.strip() else ""
    return bool(terminal and re.search(rf"\b{re.escape(terminal)}\b", snippet))


def _snippet_contains_raw_code(snippet: str, row: Dict[str, str]) -> bool:
    raw = _compact_code(row.get("raw_code") or "")
    got = _compact_code(snippet)
    return bool(raw and got and raw in got)


def _derive_control_flow_source(row: Dict[str, str]) -> str:
    existing = row.get("control_flow_source") or ""
    if existing:
        return existing
    enclosure = row.get("control_flow_enclosure") or ""
    if not enclosure or enclosure == "none":
        return "none"
    if _to_int(row.get("helper_depth")) > 0:
        return "helper_body_or_expanded_helper"
    if _truth_text(row.get("attached_from_hook")) == "true" or re.search(
        r"before|after|hook|fixture", row.get("source_kind") or "", re.I
    ):
        return "hook_or_fixture"
    return "test_body"


def _with_review_evidence(
    row: Dict[str, str],
    repo_cache: Path,
    source_cache: Dict[str, Optional[str]],
) -> Dict[str, str]:
    """Normalize old/new RQ4 rows and add source-backed review evidence."""
    out = dict(row)
    if not out.get("file_path"):
        out["file_path"] = out.get("source_file") or ""

    source_text, _source_path = _read_source(out, repo_cache, source_cache)
    start = _to_int(out.get("source_start_offset"), -1)
    end = _to_int(out.get("source_end_offset"), -1)
    any_truncated = _truth_text(out.get("snippet_truncated")) == "true"

    action_snippet = out.get("action_snippet") or ""
    source_offsets_match_action = False
    if not action_snippet and source_text:
        candidate, truncated = _slice_offsets(source_text, start, end)
        if _action_snippet_matches_row(candidate, out):
            action_snippet = candidate
            source_offsets_match_action = True
            any_truncated = any_truncated or truncated
        else:
            recovered_start, recovered_end = _find_action_span_from_raw(source_text, out)
            if recovered_start >= 0:
                start, end = recovered_start, recovered_end
                action_snippet, truncated = _slice_offsets(source_text, start, end)
                source_offsets_match_action = True
                any_truncated = any_truncated or truncated
    if not action_snippet:
        action_snippet, truncated = _clip(out.get("raw_code") or "")
        any_truncated = any_truncated or truncated
    elif source_text and _action_snippet_matches_row(action_snippet, out):
        source_offsets_match_action = True
    out["action_snippet"] = action_snippet

    cf_span_start = _to_int(out.get("control_flow_parent_start_offset"), -1)
    cf_span_end = _to_int(out.get("control_flow_parent_end_offset"), -1)
    inferred_parent_kind = ""
    inferred_callback_method = ""
    if source_text and source_offsets_match_action and (cf_span_start < 0 or cf_span_end <= cf_span_start):
        cf_span_start, cf_span_end, inferred_parent_kind, inferred_callback_method = _find_control_flow_span(
            source_text, start, end
        )
        if "loop" in (out.get("control_flow_enclosure") or ""):
            cb_start, cb_end, cb_method = _find_callback_iteration_span(source_text, start, end)
            if cb_start >= 0 and cb_end > cb_start:
                cf_span_start, cf_span_end = cb_start, cb_end
                inferred_parent_kind = "callback_iteration"
                inferred_callback_method = cb_method
    elif source_text and source_offsets_match_action and (
        out.get("control_flow_callback_method") or ""
    ):
        cb_start, cb_end, cb_method = _find_callback_iteration_span(source_text, start, end)
        if cb_start >= 0 and cb_end > cb_start:
            cf_span_start, cf_span_end = cb_start, cb_end
            inferred_parent_kind = "callback_iteration"
            inferred_callback_method = cb_method

    cf_snippet = out.get("enclosing_control_flow_snippet") or ""
    callback_method = inferred_callback_method or out.get("control_flow_callback_method") or ""
    missing_callback_receiver = bool(
        callback_method
        and f".{callback_method}" not in cf_snippet
        and callback_method not in {"callback_iteration", "loop"}
    )
    if callback_method:
        missing_action_in_cf = bool(cf_snippet and not _snippet_contains_raw_code(cf_snippet, out))
    else:
        missing_action_in_cf = bool(cf_snippet and not _action_snippet_matches_row(cf_snippet, out))
    should_rebuild_cf_snippet = (
        not cf_snippet
        or cf_snippet == out.get("raw_code")
        or missing_callback_receiver
        or missing_action_in_cf
    )
    if should_rebuild_cf_snippet and source_text and source_offsets_match_action and cf_span_start >= 0:
        cf_snippet, truncated = _slice_span_with_focus(source_text, cf_span_start, cf_span_end, start, end)
        any_truncated = any_truncated or truncated
    if not cf_snippet:
        cf_snippet = action_snippet
    out["enclosing_control_flow_snippet"] = cf_snippet

    function_snippet = out.get("enclosing_function_or_callback_snippet") or ""
    if not function_snippet and source_text and source_offsets_match_action:
        function_snippet, truncated = _window_around_offsets(source_text, start, end)
        any_truncated = any_truncated or truncated
    if not function_snippet:
        function_snippet = cf_snippet or action_snippet
    out["enclosing_function_or_callback_snippet"] = function_snippet

    context_snippet = out.get("test_body_or_helper_context_snippet") or ""
    if not context_snippet and source_text and source_offsets_match_action:
        context_snippet, truncated = _window_around_offsets(source_text, start, end)
        any_truncated = any_truncated or truncated
    if not context_snippet:
        context_snippet = function_snippet
    out["test_body_or_helper_context_snippet"] = context_snippet

    if not out.get("control_flow_parent_kind"):
        enclosure = out.get("control_flow_enclosure") or ""
        if inferred_parent_kind:
            out["control_flow_parent_kind"] = inferred_parent_kind
        elif "branch" in enclosure:
            out["control_flow_parent_kind"] = out.get("control_flow_branch_kind") or "branch"
        elif "loop" in enclosure:
            out["control_flow_parent_kind"] = "loop"
    if not out.get("control_flow_callback_method"):
        if inferred_callback_method:
            out["control_flow_callback_method"] = inferred_callback_method
        else:
            m = re.search(
                r"\.(each|forEach|map|filter|some|every|reduce|findIndex|flatMap)\s*\(",
                cf_snippet,
            )
            if m:
                out["control_flow_callback_method"] = m.group(1)
    if source_text and source_offsets_match_action and cf_span_start >= 0:
        if not out.get("control_flow_parent_start_offset"):
            out["control_flow_parent_start_offset"] = str(cf_span_start)
        if not out.get("control_flow_parent_end_offset"):
            out["control_flow_parent_end_offset"] = str(cf_span_end)
        if not out.get("control_flow_parent_line"):
            out["control_flow_parent_line"] = _line_for_offset(source_text, cf_span_start)

    payload = _parse_action_signature(out)
    category = out.get("category") or payload.get("category") or ""
    name = out.get("name") or ""
    out["feature_type"] = out.get("feature_type") or "ui_action"
    out["action_signature"] = out.get("action_signature") or _normalized_action_signature(category, name)
    out["action_signature_v2"] = out.get("action_signature_v2") or out.get("action_signature_json") or ""
    out["ui_action_category"] = out.get("ui_action_category") or category
    out["terminal_action_ast"] = out.get("terminal_action_ast") or payload.get("terminal_action") or ""
    out["locator_strategy_ast"] = out.get("locator_strategy_ast") or payload.get("locator_strategy") or ""
    out["input_channel_ast"] = out.get("input_channel_ast") or payload.get("input_channel") or ""
    out["callee_chain_json"] = out.get("callee_chain_json") or ""
    out["control_flow_source"] = _derive_control_flow_source(out)
    out["snippet_truncated"] = "true" if any_truncated else "false"
    out.setdefault("hook_instance_key", "")
    out.setdefault("attached_from_hook", "")
    return out


def _event_key(row: Dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("repo") or "",
        row.get("test_id") or "",
        row.get("source_start_offset") or "",
        row.get("source_end_offset") or "",
        row.get("raw_code") or "",
    )


def _packet_row(row: Dict[str, str], sample_origin: str) -> Dict[str, str]:
    return {
        "sample_origin": sample_origin,
        **{
            k: row.get(k, "")
            for k in CF_MANUAL_FIELDS
            if k not in ("sample_origin", "manual_enclosure_ok", "manual_notes")
        },
        "manual_enclosure_ok": "",
        "manual_notes": "",
    }


def _dedupe_events(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    seen = set()
    for row in rows:
        key = _event_key(row)
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Build RQ4 review bundle")
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--bundle-dir", type=Path, default=None)
    ap.add_argument("--cf-sample-total", type=int, default=50)
    ap.add_argument("--seq-sample", type=int, default=80)
    ap.add_argument("--per-stratum", type=int, default=6)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--repo-cache", type=Path, default=DEFAULT_REPO_CACHE)
    args = ap.parse_args()

    run_dir = args.run_dir.resolve()
    bundle_dir = (args.bundle_dir or (run_dir / "review_bundle_rq4")).resolve()
    repo_cache = args.repo_cache.resolve()
    source_cache: Dict[str, Optional[str]] = {}
    bundle_dir.mkdir(parents=True, exist_ok=True)

    events = read_csv(run_dir / "rq4_interaction_events.csv")
    by_test = read_csv(run_dir / "rq4_interaction_complexity_by_test.csv")
    if not events:
        raise FileNotFoundError("Missing rq4_interaction_events.csv")

    cf_rows = [
        r
        for r in events
        if (r.get("control_flow_enclosure") or "").strip()
        and (r.get("control_flow_enclosure") or "").strip() != "none"
    ]
    loop_rows = [r for r in cf_rows if "loop" in (r.get("control_flow_enclosure") or "")]
    branch_rows = [r for r in cf_rows if "branch" in (r.get("control_flow_enclosure") or "")]

    write_csv(
        bundle_dir / "rq4_control_flow_enclosure_distribution.csv",
        distribution_rows(Counter(r.get("control_flow_enclosure") or "" for r in events), "control_flow_enclosure"),
    )
    navigation_rows = [
        r
        for r in events
        if (r.get("category") or "").strip() == "navigation"
        or (r.get("navigation_target") or "").strip()
        or (r.get("navigation_target_evidence_basis") or "").strip()
    ]
    write_csv(
        bundle_dir / "rq4_navigation_target_evidence_basis_distribution.csv",
        distribution_rows(
            Counter(r.get("navigation_target_evidence_basis") or "missing_basis" for r in navigation_rows),
            "navigation_target_evidence_basis",
        ),
        ["navigation_target_evidence_basis", "count"],
    )

    cf_sample = [
        _with_review_evidence(r, repo_cache, source_cache)
        for r in stratified_sample(
            cf_rows,
            lambda r: (
                r.get("framework") or "",
                r.get("control_flow_enclosure") or "",
                "helper" if int(r.get("helper_depth") or 0) > 0 else "test_body",
            ),
            per_bucket=args.per_stratum,
            seed=args.seed,
            max_total=args.cf_sample_total,
        )
    ]

    # Ensure cy.each / callback iteration coverage when present
    each_rows = [r for r in events if ".each(" in (r.get("raw_code") or "")]
    each_in_sample = {_event_key(r) for r in cf_sample}
    for row in each_rows[:10]:
        key = _event_key(row)
        if key not in each_in_sample:
            cf_sample.append(_with_review_evidence(row, repo_cache, source_cache))
            each_in_sample.add(key)

    audit: List[Dict[str, Any]] = []
    for row in cf_sample:
        audit.append(_packet_row(row, "control_flow_stratified"))

    write_csv(bundle_dir / "rq4_control_flow_action_sample.csv", audit, CF_MANUAL_FIELDS)

    loop_branch_candidates = _dedupe_events(loop_rows + branch_rows)
    loop_branch = [
        _with_review_evidence(r, repo_cache, source_cache)
        for r in stratified_sample(
            loop_branch_candidates,
            lambda r: (r.get("framework") or "", r.get("control_flow_enclosure") or ""),
            per_bucket=max(2, args.per_stratum // 2),
            seed=args.seed + 1,
            max_total=args.cf_sample_total,
        )
    ]
    loop_branch_audit = [_packet_row(row, "loop_branch_stratified") for row in loop_branch]
    write_csv(bundle_dir / "rq4_loop_branch_validation_sample.csv", loop_branch_audit, CF_MANUAL_FIELDS)

    navigation_sample = [
        _with_review_evidence(r, repo_cache, source_cache)
        for r in stratified_sample(
            navigation_rows,
            lambda r: (
                r.get("framework") or "",
                r.get("navigation_target_evidence_basis") or "missing_basis",
            ),
            per_bucket=max(2, args.per_stratum // 2),
            seed=args.seed + 3,
            max_total=args.seq_sample,
        )
    ]
    navigation_audit: List[Dict[str, Any]] = []
    for row in navigation_sample:
        navigation_audit.append(
            {
                "sample_origin": "navigation_target_stratified",
                **{
                    k: row.get(k, "")
                    for k in NAV_MANUAL_FIELDS
                    if k not in ("sample_origin", "manual_target_ok", "manual_basis_ok", "manual_notes")
                },
                "manual_target_ok": "",
                "manual_basis_ok": "",
                "manual_notes": "",
            }
        )
    write_csv(bundle_dir / "rq4_navigation_target_sample.csv", navigation_audit, NAV_MANUAL_FIELDS)

    seq_candidates = [
        r
        for r in by_test
        if int(r.get("loop_driven_action_count") or 0) > 0
        or int(r.get("branch_driven_action_count") or 0) > 0
        or float(r.get("test_body_repeat_action_fraction") or 0) > 0
        or int(r.get("repeated_navigation_api_count") or 0) > 0
    ]
    seq_sample = stratified_sample(
        seq_candidates or by_test,
        lambda r: (r.get("framework") or "", "loop" if int(r.get("loop_driven_action_count") or 0) else "other"),
        per_bucket=max(3, args.per_stratum // 2),
        seed=args.seed + 2,
        max_total=args.seq_sample,
    )
    for row in seq_sample:
        row["manual_notes"] = ""
    write_csv(bundle_dir / "rq4_sequence_metrics_sample.csv", seq_sample, SEQ_MANUAL_FIELDS)

    copied = copy_if_exists(
        run_dir,
        bundle_dir,
        ["rq4_interaction_complexity_by_test.csv", "rq_aggregation_summary.json"],
    )

    summary = {}
    sp = run_dir / "rq_aggregation_summary.json"
    if sp.exists():
        summary = json.loads(sp.read_text(encoding="utf-8"))

    manifest = {
        "usage_note": (
            "RQ4 control-flow samples are evidence packets. Validate loop/branch labels using "
            "action_snippet, enclosing_control_flow_snippet, enclosing_function_or_callback_snippet, "
            "and test_body_or_helper_context_snippet. For cy.each/callback iteration, verify the UI action "
            "is in the callback body rather than the receiver query. For helper-expanded actions, check "
            "control_flow_source and the helper/test context snippet. Validate navigation targets and basis "
            "labels in rq4_navigation_target_sample.csv. Sequence sample is per-test aggregates."
        ),
        "run_dir": str(run_dir),
        "repo_cache": str(repo_cache),
        "cf_tagged_ui_action_rows": len(cf_rows),
        "loop_or_branch_rows": len(loop_branch),
        "navigation_target_sample_rows": len(navigation_audit),
        "sequence_sample_rows": len(seq_sample),
        "copied_files": copied,
        "milestone1_rq4_sequence": summary.get("milestone1_rq4_sequence"),
        "milestone3_rq4_control_flow": summary.get("milestone3_rq4_control_flow"),
        "rq3_ast_provenance": summary.get("rq3_ast_provenance"),
    }
    write_manifest(bundle_dir, manifest)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
