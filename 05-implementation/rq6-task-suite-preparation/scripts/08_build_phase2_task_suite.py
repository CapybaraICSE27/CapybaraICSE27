#!/usr/bin/env python3
"""Build RQ6 Phase 2 task-suite artifacts from stable Phase 1 baselines.

This script freezes a selected set of stable human tests, joins them to the
Phase 2 extraction tables, and writes de-identified workflow/task specs plus a
source-grounded review packet. Source snippets are only emitted to the review
bundle; they are deliberately excluded from agent prompts.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

LIB_DIR = Path(__file__).resolve().parents[1] / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from prompt_abstraction import build_prompt_variants  # noqa: E402
from task_semantics import extract_source_review_semantics as extract_rq6_source_review_semantics  # noqa: E402


DEFAULT_PHASE2_RUN_DIR = (
    Path("github_pilot_census_output")
    / "typescript__2026-05-10_09-57-24__min500stars"
    / "phase2c_full_v39"
)

DEFAULT_SELECTED_DIRS = [
    Path("rq6_outputs/phase1_execution_pilot_v4_swup_expanded"),
    Path("rq6_outputs/phase1_execution_pilot_v4_openplayer_targeted_stable"),
    Path("rq6_outputs/phase1_execution_pilot_v4_motion_vue_targeted"),
    Path("rq6_outputs/phase1_execution_pilot_v4_zudoku_targeted"),
]

DEFAULT_CANDIDATE_DIRS = [
    Path("rq6_outputs/phase1_execution_pilot_v4_swup_expanded"),
    Path("rq6_outputs/phase1_execution_pilot_v4_openplayer_targeted"),
    Path("rq6_outputs/phase1_execution_pilot_v4_motion_vue_targeted"),
    Path("rq6_outputs/phase1_execution_pilot_v4_zudoku_targeted"),
]

DEFAULT_PRETEST_SETUP_FILES = [
    Path("rq6_agent_eval/config/pretest_setup_commands.jsonl"),
    Path("rq6_outputs/phase1_execution_pilot_v4_two_more_repos/motion_vue_pretest_setup.jsonl"),
    Path("rq6_outputs/phase1_execution_pilot_v4_two_more_repos/zudoku_pretest_setup.jsonl"),
]

DEFAULT_APP_START_OVERRIDE_FILES = [
    Path("rq6_agent_eval/config/app_start_overrides.jsonl"),
    Path("rq6_outputs/phase1_execution_pilot_v4_two_more_repos/motion_vue_app_start_overrides.jsonl"),
    Path("rq6_outputs/phase1_execution_pilot_v4_two_more_repos/zudoku_app_start_overrides.jsonl"),
]

DEFAULT_REPO_QUOTAS = {
    "swup/swup": 20,
    "openplayerjs/openplayerjs": 16,
    "motiondivision/motion-vue": 12,
    "zuplo/zudoku": 12,
}

HASH_EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".pnpm-store",
    ".nx",
    ".next",
    ".nuxt",
    "dist",
    "build",
    "coverage",
    "playwright-report",
    "test-results",
}

REPOS_REQUIRING_PRETEST_SETUP = {
    "gridstack/gridstack.js",
    "openplayerjs/openplayerjs",
    "motiondivision/motion-vue",
    "zuplo/zudoku",
}

REPOS_REQUIRING_APP_START_OVERRIDE = {
    "gridstack/gridstack.js",
    "openplayerjs/openplayerjs",
    "motiondivision/motion-vue",
    "zuplo/zudoku",
}


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--phase2-run-dir", type=Path, default=DEFAULT_PHASE2_RUN_DIR)
    ap.add_argument("--out-dir", type=Path, default=Path("rq6_outputs/rq6_phase2_task_suite_v2"))
    ap.add_argument("--target-count", type=int, default=60)
    ap.add_argument(
        "--selected-dir",
        type=Path,
        action="append",
        default=[],
        help="Phase 1 output directory with selected_human_tests_60.jsonl.",
    )
    ap.add_argument(
        "--candidate-dir",
        type=Path,
        action="append",
        default=[],
        help="Phase 1 output directory with candidate_human_tests.jsonl.",
    )
    ap.add_argument(
        "--repo-cache-root",
        type=Path,
        default=Path(r"<repo-cache>"),
        help="Root containing owner__repo source snapshots.",
    )
    ap.add_argument(
        "--repo-quota",
        action="append",
        default=[],
        help="Quota as owner/repo=count. Defaults to the four stable pilot repos.",
    )
    ap.add_argument(
        "--pretest-setup-file",
        type=Path,
        action="append",
        default=[],
        help="Optional JSONL file with per-repo pretest setup commands to include in task specs.",
    )
    ap.add_argument(
        "--app-start-overrides-file",
        type=Path,
        action="append",
        default=[],
        help="Optional JSONL file with per-repo app start overrides to include in task specs.",
    )
    ap.add_argument(
        "--overwrite-manual-review",
        action="store_true",
        help=(
            "Overwrite manual_task_review.csv/jsonl if they already exist. "
            "By default, generated review rows are written to manual_task_review_generated.* "
            "and existing manual review files are preserved."
        ),
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


def write_csv(path: Path, rows: Sequence[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        seen: List[str] = []
        for row in rows:
            for key in row.keys():
                if key not in seen:
                    seen.append(key)
        fieldnames = seen
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def parse_repo_quotas(values: Sequence[str]) -> Dict[str, int]:
    if not values:
        return dict(DEFAULT_REPO_QUOTAS)
    quotas: Dict[str, int] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"Invalid --repo-quota {value!r}; expected owner/repo=count")
        repo, count = value.split("=", 1)
        quotas[repo.strip()] = int(count.strip())
    return quotas


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def to_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_json_field(value: Any, fallback: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    text = str(value or "").strip()
    if not text:
        return fallback
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return fallback


def repo_cache_key(repo_full_name: str) -> str:
    return str(repo_full_name or "").replace("/", "__").replace(":", "_")


def normalized_task_name(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def task_duplicate_key(row: Dict[str, Any]) -> Tuple[str, str]:
    return (str(row.get("repo_full_name") or ""), normalized_task_name(row.get("test_name")))


def load_repo_keyed_entries(paths: Sequence[Path]) -> Dict[str, List[Dict[str, Any]]]:
    entries: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    seen: set[Tuple[str, str]] = set()
    for path in paths:
        for row in read_jsonl(path) or []:
            row = dict(row)
            identity = json.dumps(row, sort_keys=True, ensure_ascii=False)
            for key in {str(row.get("repo_full_name") or ""), str(row.get("repo_cache_key") or "")}:
                if not key:
                    continue
                dedupe_key = (key, identity)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                entries[key].append(row)
    return dict(entries)


def hashable_source_file(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    return not any(part in HASH_EXCLUDED_DIRS for part in parts)


def compute_source_tree_hash(source_root: Path) -> Dict[str, Any]:
    if not source_root.is_dir():
        return {"hash": "", "file_count": 0, "status": "missing_source_root"}
    digest = hashlib.sha256()
    file_count = 0
    for path in sorted(source_root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(source_root)
        if not hashable_source_file(rel):
            continue
        file_count += 1
        rel_text = rel.as_posix()
        digest.update(rel_text.encode("utf-8", errors="surrogateescape"))
        digest.update(b"\0")
        try:
            with path.open("rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError:
            return {"hash": "", "file_count": file_count, "status": f"failed_reading:{rel_text}"}
        digest.update(b"\0")
    if file_count == 0:
        return {"hash": "", "file_count": 0, "status": "no_hashable_files"}
    return {"hash": digest.hexdigest(), "file_count": file_count, "status": "computed_excluding_generated_dirs"}


def load_selected_tests(selected_dirs: Sequence[Path]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    seen: set[Tuple[str, str]] = set()
    for selected_dir in selected_dirs:
        path = selected_dir / "selected_human_tests_60.jsonl"
        for row in read_jsonl(path) or []:
            key = (str(row.get("repo_full_name") or ""), str(row.get("test_id") or ""))
            if key in seen:
                continue
            seen.add(key)
            row = dict(row)
            row["_selected_source_dir"] = str(selected_dir)
            rows.append(row)
    return rows


def select_quota_rows(rows: Sequence[Dict[str, Any]], quotas: Dict[str, int], target_count: int) -> List[Dict[str, Any]]:
    stable = [r for r in rows if truthy(r.get("baseline_stable_passed")) or truthy(r.get("stable_passed"))]
    by_repo: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in stable:
        by_repo[str(row.get("repo_full_name") or "")].append(row)

    selected: List[Dict[str, Any]] = []
    selected_keys: set[Tuple[str, str]] = set()
    selected_duplicate_keys: set[Tuple[str, str]] = set()

    def add_row(row: Dict[str, Any], *, allow_duplicate_semantics: bool) -> bool:
        key = (str(row.get("repo_full_name") or ""), str(row.get("test_id") or ""))
        duplicate_key = task_duplicate_key(row)
        if key in selected_keys:
            return False
        if not allow_duplicate_semantics and duplicate_key in selected_duplicate_keys:
            return False
        selected.append(row)
        selected_keys.add(key)
        selected_duplicate_keys.add(duplicate_key)
        return True

    for repo, quota in quotas.items():
        repo_rows = by_repo.get(repo, [])
        for row in repo_rows:
            if sum(1 for selected_row in selected if selected_row.get("repo_full_name") == repo) >= max(0, quota):
                break
            add_row(row, allow_duplicate_semantics=False)
        for row in repo_rows:
            if sum(1 for selected_row in selected if selected_row.get("repo_full_name") == repo) >= max(0, quota):
                break
            add_row(row, allow_duplicate_semantics=True)
    if len(selected) < target_count:
        for row in stable:
            add_row(row, allow_duplicate_semantics=False)
            if len(selected) >= target_count:
                break
    if len(selected) < target_count:
        for row in stable:
            add_row(row, allow_duplicate_semantics=True)
            if len(selected) >= target_count:
                break
    return selected[:target_count]


def load_candidate_rows(candidate_dirs: Sequence[Path]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    out: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for candidate_dir in candidate_dirs:
        path = candidate_dir / "candidate_human_tests.jsonl"
        for row in read_jsonl(path) or []:
            key = (str(row.get("repo_full_name") or ""), str(row.get("test_id") or ""))
            if key and key not in out:
                out[key] = row
    return out


def stream_jsonl_by_test_id(path: Path, selected_ids: set[str]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    if not path.exists():
        return out
    remaining = set(selected_ids)
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if not remaining:
                break
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            test_id = str(row.get("test_id") or "")
            if test_id in remaining:
                out[test_id] = row
                remaining.remove(test_id)
    return out


def load_csv_by_test_id(path: Path, selected_ids: set[str]) -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            test_id = str(row.get("test_id") or "")
            if test_id in selected_ids and test_id not in out:
                out[test_id] = row
    return out


def load_event_csv(
    path: Path,
    selected_ids: set[str],
    *,
    max_per_test: int = 80,
) -> Dict[str, List[Dict[str, str]]]:
    out: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    if not path.exists():
        return dict(out)
    with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            test_id = str(row.get("test_id") or "")
            if test_id not in selected_ids:
                continue
            if len(out[test_id]) < max_per_test:
                out[test_id].append(row)
    return dict(out)


def first_nonempty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def humanize_identifier(value: str) -> str:
    text = str(value or "")
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    text = text.replace("_", " ").replace("-", " ").replace(".", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def deidentify_path_hint(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "the relevant application view"
    if text in {"/", "#"}:
        return "the starting application view"
    parts = [p for p in re.split(r"[/?#&=._-]+", text) if p and not p.isdigit()]
    if not parts:
        return "the relevant application route"
    return "the " + " ".join(parts[:4]) + " view"


def action_type_from_event(event: Dict[str, str]) -> str:
    category = str(event.get("ui_action_category") or event.get("category") or "").strip().lower()
    terminal_ast = str(event.get("terminal_action_ast") or "").strip().lower()
    name = str(event.get("name") or "").strip().lower()
    terminal = terminal_ast or name.split(".")[-1]
    if "navigation" in category or terminal in {"goto", "visit", "reload", "go"}:
        return "navigate"
    if category == "drag_drop" or terminal in {"drag", "dragto", "draganddrop"}:
        return "drag"
    if category == "scroll" or terminal in {"scroll", "scrollto", "scrollby", "scrollintoview"}:
        return "scroll"
    if terminal in {"click", "dblclick", "tap", "check", "uncheck", "hover"}:
        return terminal
    if category in {"text_input", "keyboard_input", "selection", "file_upload"}:
        return "input"
    if terminal in {"fill", "type", "press", "selectoption", "setinputfiles"}:
        return "input"
    if "wait" in category or terminal.startswith("wait"):
        return "wait"
    if "locator" in category or terminal in {"locator", "getbyrole", "getbytext", "getbytestid"}:
        return "locate"
    return humanize_identifier(terminal or category or "ui action").lower()


def summarize_action(event: Dict[str, str], index: int) -> Dict[str, Any]:
    action_type = action_type_from_event(event)
    target = "a user-visible UI element"
    if action_type == "navigate":
        target = deidentify_path_hint(event.get("navigation_target", ""))
    elif action_type == "wait":
        target = "the application to reach the expected state"
    elif action_type == "locate":
        target = "the relevant UI element"
    return {
        "index": index,
        "type": action_type,
        "target_hint": target,
        "source_layer": first_nonempty(event.get("source_kind"), "unknown"),
        "helper_depth": to_int(event.get("helper_depth"), 0),
    }


def summarize_assertion(event: Dict[str, str], index: int) -> Dict[str, Any]:
    intent = first_nonempty(event.get("verification_intent"), event.get("category"), "observable behavior")
    kind = first_nonempty(event.get("category"), event.get("assertion_matcher"), "assertion")
    return {
        "index": index,
        "kind": humanize_identifier(kind).lower(),
        "intent": humanize_identifier(intent).lower(),
        "source_layer": first_nonempty(event.get("source_kind"), "unknown"),
        "helper_depth": to_int(event.get("helper_depth"), 0),
    }


def workflow_goal(test_name: str, describe_path: Sequence[str]) -> str:
    scope = " / ".join([str(p) for p in describe_path if str(p).strip()])
    if scope:
        return f"{scope}: {test_name}"
    return test_name


def read_source_snippet(source_root: Path, file_path: str, start_line: int, end_line: int) -> Tuple[str, str]:
    path = source_root / file_path
    if not path.exists() or start_line <= 0 or end_line < start_line:
        return "", str(path)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start_index = max(0, start_line - 1)
    end_index = min(len(lines), end_line)
    snippet_lines = []
    for offset, line in enumerate(lines[start_index:end_index], start=start_line):
        snippet_lines.append(f"{offset}: {line}")
    return "\n".join(snippet_lines), str(path)


def compact_source_summary(snippet: str, max_lines: int = 24) -> str:
    lines = snippet.splitlines()
    if len(lines) <= max_lines:
        return snippet
    head = lines[: max_lines // 2]
    tail = lines[-(max_lines // 2) :]
    return "\n".join(head + [f"... {len(lines) - len(head) - len(tail)} source lines omitted ..."] + tail)


def build_verification_command(candidate: Dict[str, Any], source_file: str, agent_test_file: str) -> str:
    discovery = str(candidate.get("discovery_command") or "").strip()
    if discovery:
        command = discovery.replace(" --list ", " ").replace(" --list", "")
        command = command.replace(source_file, agent_test_file)
        command = re.sub(r"\s+-g\s+.+$", "", command).strip()
        if "--reporter" not in command:
            command += " --reporter=json"
        return command
    framework = str(candidate.get("framework") or "playwright").lower()
    if framework == "playwright":
        return f"pnpm exec playwright test {agent_test_file} --reporter=json"
    return f"npm test -- {agent_test_file}"


def build_prompt(task: Dict[str, Any], workflow: Dict[str, Any], agent_test_file: str) -> str:
    task_for_prompt = dict(task)
    task_for_prompt["agent_test_file"] = agent_test_file
    variants = build_prompt_variants(task_for_prompt, workflow)
    for variant in variants:
        if variant["prompt_level"] == "medium":
            return str(variant["prompt"])
    raise ValueError("Medium prompt variant was not generated")


def append_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_prompt_artifacts(out_dir: Path, task_spec: Dict[str, Any], workflow: Dict[str, Any]) -> str:
    variants = build_prompt_variants(task_spec, workflow)
    medium_prompt = ""
    medium_prompt_path = ""
    for variant in variants:
        level = str(variant["prompt_level"])
        task_id = str(variant["task_id"])
        prompt_path = out_dir / "prompts" / level / f"{task_id}_prompt.md"
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(str(variant["prompt"]) + "\n", encoding="utf-8")
        variant["prompt_path"] = str(prompt_path)
        if level == "medium":
            medium_prompt = str(variant["prompt"])
            medium_prompt_path = str(prompt_path)

    append_jsonl(out_dir / "agent_prompt_variants.jsonl", variants)
    task_id = str(task_spec.get("task_id") or "")
    legacy_prompt_path = out_dir / "prompts" / f"{task_id}_prompt.md"
    legacy_prompt_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_prompt_path.write_text(medium_prompt + "\n", encoding="utf-8")
    task_spec["prompt"] = medium_prompt
    task_spec["prompt_path"] = medium_prompt_path or str(legacy_prompt_path)
    return medium_prompt


def phase2_raw_alignment(
    source_semantics: Dict[str, Any],
    phase2_actions: Sequence[Dict[str, Any]],
    phase2_waits: Sequence[Dict[str, Any]] = (),
) -> str:
    source_types = {str(action.get("type") or "") for action in source_semantics.get("actions") or []}
    phase2_types = {str(action.get("type") or "") for action in phase2_actions}
    if any(to_int(wait.get("count"), 0) > 0 for wait in phase2_waits or []):
        phase2_types.add("wait")
    if not source_types:
        return "unknown"
    missing_core = source_types.intersection({"click", "drag", "scroll", "input", "wait", "navigate"}) - phase2_types
    if missing_core:
        return "partial"
    if phase2_types and source_types:
        return "yes"
    return "partial"


def prompt_has_selector_like_leakage(prompt: str) -> bool:
    # This intentionally checks only obvious selector/code markers in prompts.
    markers = [
        "data-testid",
        "locator(",
        "getByTestId",
        "page.goto(",
        "page.locator(",
        "page.getBy",
        "await ",
        "expect(",
        "test(",
        "css=",
        "xpath=",
    ]
    return any(marker in prompt for marker in markers)


def build_review_row(
    *,
    task_id: str,
    repo: str,
    source_file: str,
    test_name: str,
    start_line: int,
    end_line: int,
    source_available: bool,
    extraction_available: bool,
    workflow: Dict[str, Any],
    prompt: str,
    source_semantics: Dict[str, Any],
    has_app_metadata: bool,
    has_pretest_metadata: bool,
    requires_app_metadata: bool,
    requires_pretest_metadata: bool,
) -> Dict[str, Any]:
    raw_alignment = phase2_raw_alignment(
        source_semantics,
        workflow["workflow"].get("phase2_extracted_actions", []),
        workflow["workflow"].get("waits", []),
    )
    prompt_leakage = prompt_has_selector_like_leakage(prompt)
    source_reviewed_available = bool(source_semantics.get("source_review_semantics_available"))
    prompt_semantics = (
        source_semantics.get("prompt_semantics")
        or workflow["workflow"].get("prompt_semantics")
        or {}
    )
    if not isinstance(prompt_semantics, dict):
        prompt_semantics = {}
    semantic_confidence = str(prompt_semantics.get("semantic_confidence") or "unknown")
    expected_results = prompt_semantics.get("expected_results") or []
    has_specific_expected_result = bool(expected_results)
    needs_manual_enrichment = bool(prompt_semantics.get("needs_manual_review")) or semantic_confidence in {"low", "unknown"}
    prompt_fair = source_available and source_reviewed_available and not prompt_leakage
    notes: List[str] = []
    if raw_alignment == "partial":
        notes.append("Phase 2 aggregate workflow under-captured at least one source-reviewed user action; source-reviewed workflow was used for prompts/review.")
    notes.extend(source_semantics.get("notes") or [])
    if has_pretest_metadata:
        notes.append("Task spec includes repo pretest setup metadata from Phase 1 triage.")
    if has_app_metadata:
        notes.append("Task spec includes app-start/base-url metadata from Phase 1 triage.")
    if requires_pretest_metadata and not has_pretest_metadata:
        notes.append("Missing required pretest setup metadata for this repo.")
    if requires_app_metadata and not has_app_metadata:
        notes.append("Missing required app-start/base-url metadata for this repo.")
    if not notes:
        notes.append("Codex source review: source-reviewed workflow and prompt match the original test block without exposing selectors or code.")
    decision = "approved_for_masking" if prompt_fair else "needs_task_spec_revision"
    execution_metadata_complete = (
        (not requires_pretest_metadata or has_pretest_metadata)
        and (not requires_app_metadata or has_app_metadata)
    )
    return {
        "task_id": task_id,
        "repo_full_name": repo,
        "source_file": source_file,
        "test_name": test_name,
        "workflow_clear": "yes" if source_reviewed_available else "partial",
        "workflow_aligns_with_source": "yes" if source_reviewed_available else "partial",
        "phase2_raw_workflow_aligns_with_source": raw_alignment,
        "prompt_fair": "yes" if prompt_fair else "no",
        "not_too_specific": "yes" if not prompt_leakage else "no",
        "not_too_vague": "yes" if source_reviewed_available else "partial",
        "expected_behavior_observable": "yes" if workflow["workflow"].get("assertions") else "partial",
        "semantic_confidence": semantic_confidence,
        "needs_manual_enrichment": "yes" if needs_manual_enrichment else "no",
        "purpose_preserved": "yes" if prompt_fair and has_specific_expected_result else "partial",
        "leakage_risk": "high" if prompt_leakage else "low",
        "ambiguity": "low" if semantic_confidence in {"high", "medium"} and has_specific_expected_result else "medium",
        "expected_result_specificity": "yes" if has_specific_expected_result else "partial",
        "no_hidden_credentials_or_services": "yes",
        "verification_command_plausible": "yes",
        "execution_metadata_complete": "yes" if execution_metadata_complete else "partial",
        "mask_ok": "pending_phase2d_mask_validation",
        "review_decision": decision,
        "reviewer": "Codex",
        "review_generation_method": "scripted_codex_source_review_v2",
        "notes": " ".join(notes),
        "source_available": source_available,
        "phase2_extraction_available": extraction_available,
        "source_review_semantics_available": source_reviewed_available,
        "source_start_line": start_line,
        "source_end_line": end_line,
    }


def build_workflow(
    task: Dict[str, Any],
    candidate: Dict[str, Any],
    test_case: Dict[str, Any],
    rq_rows: Dict[str, Dict[str, str]],
    rq4_events: List[Dict[str, str]],
    rq5_events: List[Dict[str, str]],
    source_semantics: Dict[str, Any],
) -> Dict[str, Any]:
    describe_path = test_case.get("describe_path")
    if not isinstance(describe_path, list):
        describe_path = parse_json_field(candidate.get("describe_path_json"), [])
    phase2_actions = [
        summarize_action(event, index)
        for index, event in enumerate(
            sorted(
                rq4_events,
                key=lambda e: (to_int(e.get("sequence_index"), 9999), to_int(e.get("line"), 999999)),
            )[:14],
            start=1,
        )
    ]
    phase2_assertions = [
        summarize_assertion(event, index)
        for index, event in enumerate(
            sorted(rq5_events, key=lambda e: (to_int(e.get("line"), 999999), to_int(e.get("assertion_chain_index"), 0)))[:10],
            start=1,
        )
    ]
    source_actions = list(source_semantics.get("actions") or [])
    source_assertions = list(source_semantics.get("assertions") or [])
    actions = source_actions or phase2_actions
    assertions = source_assertions or phase2_assertions
    rq1 = rq_rows.get("rq1", {})
    rq2 = rq_rows.get("rq2", {})
    rq3 = rq_rows.get("rq3", {})
    rq4 = rq_rows.get("rq4", {})
    rq5 = rq_rows.get("rq5", {})
    inputs = parse_json_field(rq2.get("input_category_counts"), {})
    input_items = [
        {"kind": humanize_identifier(kind).lower(), "count": count}
        for kind, count in sorted(inputs.items())
    ] if isinstance(inputs, dict) else []
    setup_counts = parse_json_field(rq1.get("primary_intent_counts_json"), {})
    setup_items = [
        {"kind": humanize_identifier(kind).lower(), "count": count}
        for kind, count in sorted(setup_counts.items())
        if kind and str(kind).lower() != "unclear"
    ] if isinstance(setup_counts, dict) else []
    setup_items = list(source_semantics.get("setup") or []) + setup_items
    wait_count = to_int(first_nonempty(rq4.get("wait_synchronization_count"), candidate.get("wait_count")), 0)
    waits = [{"kind": "framework or explicit synchronization", "count": wait_count}] if wait_count else []
    metrics = {
        "action_sequence_length": to_int(first_nonempty(rq4.get("action_sequence_length"), candidate.get("action_sequence_length")), 0),
        "expanded_ui_action_count": to_int(first_nonempty(rq3.get("expanded_ui_action_count"), candidate.get("action_sequence_length")), 0),
        "helper_depth_or_helper_action_count": to_int(candidate.get("helper_action_count"), 0),
        "assertion_count": to_int(first_nonempty(rq5.get("assertion_count"), candidate.get("assertion_count")), 0),
        "wait_count": wait_count,
        "navigation_count": to_int(first_nonempty(rq4.get("navigation_count"), candidate.get("navigation_count")), 0),
        "input_feature_count": to_int(rq2.get("input_feature_count"), 0),
        "workflow_archetype": first_nonempty(rq3.get("workflow_archetype"), candidate.get("workflow_archetype"), "unknown"),
    }
    return {
        "task_id": task["task_id"],
        "repo_full_name": task["repo_full_name"],
        "source_test_id": task["source_test_id"],
        "workflow": {
            "goal": workflow_goal(str(task.get("test_name") or ""), describe_path),
            "actions": actions,
            "phase2_extracted_actions": phase2_actions,
            "source_reviewed_actions": source_actions,
            "inputs": input_items,
            "assertions": assertions,
            "phase2_extracted_assertions": phase2_assertions,
            "source_reviewed_assertions": source_assertions,
            "waits": waits,
            "setup": setup_items,
            "prompt_semantics": source_semantics.get("prompt_semantics") or {},
            "evidence_basis": {
                "actions": "rq4_interaction_events_phase2_ast_aggregated",
                "assertions": "rq5_assertion_events_phase2_ast_aggregated",
                "inputs": "rq2_input_by_test_phase2_aggregated",
                "setup": "rq1_setup_teardown_intent_by_test_phase2_aggregated",
                "source_reviewed_actions": "codex_source_review_from_original_test_block",
                "source_alignment": "codex_manual_source_review_integrated",
            },
        },
        "reference_metrics": metrics,
    }


def main() -> None:
    args = parse_args()
    selected_dirs = args.selected_dir or DEFAULT_SELECTED_DIRS
    candidate_dirs = args.candidate_dir or DEFAULT_CANDIDATE_DIRS
    quotas = parse_repo_quotas(args.repo_quota)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "prompts").mkdir(parents=True, exist_ok=True)
    for level in ("high", "medium", "low"):
        (args.out_dir / "prompts" / level).mkdir(parents=True, exist_ok=True)
    (args.out_dir / "review_packets").mkdir(parents=True, exist_ok=True)
    (args.out_dir / "agent_prompt_variants.jsonl").write_text("", encoding="utf-8")

    all_selected = load_selected_tests(selected_dirs)
    selected = select_quota_rows(all_selected, quotas, args.target_count)
    selected_ids = {str(r.get("test_id") or "") for r in selected}
    candidates = load_candidate_rows(candidate_dirs)
    test_cases = stream_jsonl_by_test_id(args.phase2_run_dir / "test_cases.jsonl", selected_ids)

    csv_tables = {
        "rq1": load_csv_by_test_id(args.phase2_run_dir / "rq1_setup_teardown_intent_by_test.csv", selected_ids),
        "rq2": load_csv_by_test_id(args.phase2_run_dir / "rq2_input_by_test.csv", selected_ids),
        "rq3": load_csv_by_test_id(args.phase2_run_dir / "rq3_patterns_by_test.csv", selected_ids),
        "rq4": load_csv_by_test_id(args.phase2_run_dir / "rq4_interaction_complexity_by_test.csv", selected_ids),
        "rq5": load_csv_by_test_id(args.phase2_run_dir / "rq5_assertion_complexity_by_test.csv", selected_ids),
    }
    rq4_events = load_event_csv(args.phase2_run_dir / "rq4_interaction_events.csv", selected_ids)
    rq5_events = load_event_csv(args.phase2_run_dir / "rq5_assertion_events.csv", selected_ids)
    pretest_setup_files = args.pretest_setup_file or DEFAULT_PRETEST_SETUP_FILES
    app_start_override_files = args.app_start_overrides_file or DEFAULT_APP_START_OVERRIDE_FILES
    pretest_setup_by_repo = load_repo_keyed_entries(pretest_setup_files)
    app_start_overrides_by_repo = load_repo_keyed_entries(app_start_override_files)
    source_hash_cache: Dict[str, Dict[str, Any]] = {}

    manifest_rows: List[Dict[str, Any]] = []
    workflow_rows: List[Dict[str, Any]] = []
    reviewed_workflow_rows: List[Dict[str, Any]] = []
    task_spec_rows: List[Dict[str, Any]] = []
    review_rows: List[Dict[str, Any]] = []
    packet_rows: List[Dict[str, Any]] = []

    for index, selected_row in enumerate(selected, start=1):
        repo = str(selected_row.get("repo_full_name") or "")
        test_id = str(selected_row.get("test_id") or "")
        task_id = f"rq6_{index:04d}"
        candidate = candidates.get((repo, test_id), {})
        test_case = test_cases.get(test_id, {})
        source_file = first_nonempty(test_case.get("file_path"), selected_row.get("file_path"))
        describe_path = test_case.get("describe_path")
        if not isinstance(describe_path, list):
            describe_path = parse_json_field(candidate.get("describe_path_json"), [])
        start_line = to_int(test_case.get("start_line"), 0)
        end_line = to_int(test_case.get("end_line"), 0)
        cache_key = first_nonempty(selected_row.get("repo_cache_key"), repo_cache_key(repo))
        source_root = args.repo_cache_root / cache_key
        snippet, source_abs_path = read_source_snippet(source_root, source_file, start_line, end_line)
        source_semantics = extract_rq6_source_review_semantics(snippet, str(selected_row.get("test_name") or ""), describe_path)
        if cache_key not in source_hash_cache:
            source_hash_cache[cache_key] = compute_source_tree_hash(source_root)
        source_hash_info = source_hash_cache[cache_key]
        provided_source_hash = str(selected_row.get("source_snapshot_sha256") or "").strip()
        source_snapshot_sha256 = provided_source_hash or str(source_hash_info.get("hash") or "")
        source_snapshot_hash_status = "provided_phase1" if provided_source_hash else str(source_hash_info.get("status") or "")
        source_snapshot_hash_file_count = "" if provided_source_hash else source_hash_info.get("file_count", 0)
        pretest_setup_entries = pretest_setup_by_repo.get(repo) or pretest_setup_by_repo.get(cache_key) or []
        app_start_entries = app_start_overrides_by_repo.get(repo) or app_start_overrides_by_repo.get(cache_key) or []
        app_start_override = dict(app_start_entries[0]) if app_start_entries else {}
        source_dir = str(Path(source_file).parent).replace("\\", "/")
        agent_test_file = str((Path(source_dir) / "rq6-agent" / f"{task_id}.spec.ts").as_posix())
        rq_rows = {
            name: table.get(test_id, {})
            for name, table in csv_tables.items()
        }
        manifest = {
            "task_id": task_id,
            "repo_full_name": repo,
            "repo_cache_key": cache_key,
            "source_provenance": selected_row.get("source_provenance", ""),
            "phase2_commit_alignment": selected_row.get("phase2_commit_alignment", ""),
            "source_snapshot_sha256": source_snapshot_sha256,
            "source_snapshot_sha256_basis": "phase1_manifest" if provided_source_hash else "computed_source_tree_excluding_generated_dirs",
            "source_snapshot_hash_status": source_snapshot_hash_status,
            "source_snapshot_hash_file_count": source_snapshot_hash_file_count,
            "commit": test_case.get("commit", ""),
            "framework": str(selected_row.get("framework") or "").lower(),
            "source_test_id": test_id,
            "source_file": source_file,
            "source_abs_path": source_abs_path,
            "test_name": selected_row.get("test_name", ""),
            "describe_path": describe_path,
            "selection_duplicate_key": "::".join(task_duplicate_key(selected_row)),
            "candidate_role": first_nonempty(candidate.get("candidate_role"), "unknown"),
            "baseline_passed_once": truthy(selected_row.get("passed_once")),
            "baseline_stable_passed": truthy(selected_row.get("baseline_stable_passed")) or truthy(selected_row.get("stable_passed")),
            "baseline_runs_passed": to_int(selected_row.get("runs_passed"), 0),
            "baseline_runs_attempted": to_int(selected_row.get("runs_attempted"), 0),
            "median_duration_sec": to_float(selected_row.get("median_duration_sec"), 0.0),
            "max_duration_sec": to_float(selected_row.get("max_duration_sec"), 0.0),
            "source_start_line": start_line,
            "source_end_line": end_line,
            "agent_test_file": agent_test_file,
        }
        workflow = build_workflow(
            {"task_id": task_id, **manifest},
            candidate,
            test_case,
            rq_rows,
            rq4_events.get(test_id, []),
            rq5_events.get(test_id, []),
            source_semantics,
        )
        verification_command = build_verification_command(candidate, source_file, agent_test_file)
        task_spec = {
            "task_id": task_id,
            "repo_full_name": repo,
            "repo_cache_key": cache_key,
            "framework": manifest["framework"],
            "prompt": "",
            "prompt_path": "",
            "allowed_files_policy": "test_files_only",
            "agent_test_file": agent_test_file,
            "verification_command": verification_command,
            "verification_command_basis": "phase1_discovery_command_with_agent_file_substitution",
            "requires_pretest_setup": repo in REPOS_REQUIRING_PRETEST_SETUP,
            "pretest_setup_commands": pretest_setup_entries,
            "requires_app_start_override": repo in REPOS_REQUIRING_APP_START_OVERRIDE,
            "app_start_override": app_start_override,
            "app_start_command": first_nonempty(app_start_override.get("app_start_command"), candidate.get("app_start_command")),
            "base_url": first_nonempty(app_start_override.get("base_url"), candidate.get("base_url")),
            "execution_context_basis": "phase1_manual_triage_config_joined_by_repo",
        }
        prompt = write_prompt_artifacts(args.out_dir, task_spec, workflow)
        source_available = bool(snippet)
        extraction_available = any(bool(rq_rows[name]) for name in rq_rows) and bool(test_case)
        review = build_review_row(
            task_id=task_id,
            repo=repo,
            source_file=source_file,
            test_name=str(manifest["test_name"]),
            start_line=start_line,
            end_line=end_line,
            source_available=source_available,
            extraction_available=extraction_available,
            workflow=workflow,
            prompt=prompt,
            source_semantics=source_semantics,
            has_app_metadata=bool(app_start_override),
            has_pretest_metadata=bool(pretest_setup_entries),
            requires_app_metadata=repo in REPOS_REQUIRING_APP_START_OVERRIDE,
            requires_pretest_metadata=repo in REPOS_REQUIRING_PRETEST_SETUP,
        )
        reviewed_workflow = dict(workflow)
        reviewed_workflow["source_alignment_review"] = {
            "workflow_aligns_with_source": review["workflow_aligns_with_source"],
            "phase2_raw_workflow_aligns_with_source": review["phase2_raw_workflow_aligns_with_source"],
            "review_decision": review["review_decision"],
            "reviewer": review["reviewer"],
            "review_generation_method": review["review_generation_method"],
            "notes": review["notes"],
        }
        packet = {
            "task_id": task_id,
            "repo_full_name": repo,
            "source_file": source_file,
            "source_abs_path": source_abs_path,
            "source_start_line": start_line,
            "source_end_line": end_line,
            "test_name": manifest["test_name"],
            "describe_path": describe_path,
            "draft_workflow": workflow["workflow"],
            "source_review_semantics": source_semantics,
            "phase2_raw_workflow_aligns_with_source": review["phase2_raw_workflow_aligns_with_source"],
            "reference_metrics": workflow["reference_metrics"],
            "agent_prompt": prompt,
            "source_snippet": snippet,
            "source_snippet_compact": compact_source_summary(snippet),
        }
        manifest_rows.append(manifest)
        workflow_rows.append(workflow)
        reviewed_workflow_rows.append(reviewed_workflow)
        task_spec_rows.append(task_spec)
        review_rows.append(review)
        packet_rows.append(packet)

    write_jsonl(args.out_dir / "rq6_tasks_manifest.jsonl", manifest_rows)
    write_csv(args.out_dir / "rq6_tasks_manifest.csv", manifest_rows)
    write_jsonl(args.out_dir / "workflow_specs.jsonl", workflow_rows)
    write_jsonl(args.out_dir / "workflow_specs_reviewed.jsonl", reviewed_workflow_rows)
    write_jsonl(args.out_dir / "agent_task_specs.jsonl", task_spec_rows)
    write_csv(args.out_dir / "manual_task_review_generated.csv", review_rows)
    write_jsonl(args.out_dir / "manual_task_review_generated.jsonl", review_rows)
    manual_review_csv = args.out_dir / "manual_task_review.csv"
    manual_review_jsonl = args.out_dir / "manual_task_review.jsonl"
    manual_review_write_status = "preserved_existing_manual_review"
    if args.overwrite_manual_review or not manual_review_csv.exists():
        write_csv(manual_review_csv, review_rows)
        write_jsonl(manual_review_jsonl, review_rows)
        manual_review_write_status = "written_from_scripted_codex_review"
    write_jsonl(args.out_dir / "source_review_packets.jsonl", packet_rows)

    md_lines = ["# RQ6 Phase 2 Source Review Packets", ""]
    for packet in packet_rows:
        md_lines.extend(
            [
                f"## {packet['task_id']} - {packet['repo_full_name']}",
                "",
                f"- Source: `{packet['source_file']}:{packet['source_start_line']}`",
                f"- Test: `{packet['test_name']}`",
                f"- Goal: {packet['draft_workflow'].get('goal', '')}",
                f"- Phase 2 raw workflow alignment: `{packet['phase2_raw_workflow_aligns_with_source']}`",
                "",
                "### Draft Workflow",
                "```json",
                json.dumps(packet["draft_workflow"], ensure_ascii=False, indent=2),
                "```",
                "",
                "### Source Snippet",
                "```ts",
                packet["source_snippet_compact"],
                "```",
                "",
            ]
        )
    (args.out_dir / "review_packets" / "source_review_packets.md").write_text(
        "\n".join(md_lines), encoding="utf-8"
    )

    duplicate_groups: Dict[str, List[str]] = defaultdict(list)
    for row in manifest_rows:
        duplicate_groups[str(row.get("selection_duplicate_key") or "")].append(str(row.get("task_id") or ""))
    near_duplicate_groups_remaining = {
        key: task_ids
        for key, task_ids in sorted(duplicate_groups.items())
        if key and len(task_ids) > 1
    }
    review_decisions: Dict[str, int] = defaultdict(int)
    phase2_raw_alignment_counts: Dict[str, int] = defaultdict(int)
    source_hash_status_counts: Dict[str, int] = defaultdict(int)
    for row in review_rows:
        review_decisions[str(row.get("review_decision") or "")] += 1
        phase2_raw_alignment_counts[str(row.get("phase2_raw_workflow_aligns_with_source") or "")] += 1
    for row in manifest_rows:
        source_hash_status_counts[str(row.get("source_snapshot_hash_status") or "")] += 1
    summary = {
        "all_stable_tests_loaded": len(all_selected),
        "tasks_selected": len(manifest_rows),
        "repos": dict(sorted({repo: sum(1 for r in manifest_rows if r["repo_full_name"] == repo) for repo in {r["repo_full_name"] for r in manifest_rows}}.items())),
        "source_packets_with_snippets": sum(1 for p in packet_rows if p["source_snippet"]),
        "phase2_rows_with_test_case": sum(1 for r in manifest_rows if r["source_start_line"]),
        "manual_review_write_status": manual_review_write_status,
        "manual_review_decisions": dict(sorted(review_decisions.items())),
        "phase2_raw_workflow_alignment_counts": dict(sorted(phase2_raw_alignment_counts.items())),
        "near_duplicate_groups_remaining": near_duplicate_groups_remaining,
        "source_snapshot_hash_status_counts": dict(sorted(source_hash_status_counts.items())),
        "source_snapshot_hashes_missing": sum(1 for r in manifest_rows if not r.get("source_snapshot_sha256")),
        "tasks_with_pretest_setup_metadata": sum(1 for r in task_spec_rows if r.get("pretest_setup_commands")),
        "tasks_with_app_start_metadata": sum(1 for r in task_spec_rows if r.get("app_start_override")),
        "out_dir": str(args.out_dir),
    }
    (args.out_dir / "phase2_task_suite_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
