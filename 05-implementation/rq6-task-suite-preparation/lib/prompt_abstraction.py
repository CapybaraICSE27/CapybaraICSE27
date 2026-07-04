"""Prompt abstraction helpers for RQ6 agent task specifications."""

from __future__ import annotations

from typing import Any, Dict, List, Sequence


PROMPT_POLICY_VERSION = "rq6_prompt_abstraction_v1"
PROMPT_LEVELS = ("high", "medium", "low")


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _framework_label(value: Any) -> str:
    framework = _clean(value).lower()
    if framework == "playwright":
        return "Playwright"
    if framework == "cypress":
        return "Cypress"
    if framework:
        return framework
    return "browser"


def _workflow(workflow: Dict[str, Any]) -> Dict[str, Any]:
    candidate = workflow.get("workflow") if isinstance(workflow, dict) else {}
    return candidate if isinstance(candidate, dict) else {}


def _goal(workflow: Dict[str, Any]) -> str:
    return _clean(_workflow(workflow).get("goal")) or "the requested browser UI behavior"


def _visible_actions(workflow: Dict[str, Any]) -> List[Dict[str, Any]]:
    actions = _workflow(workflow).get("actions") or []
    if not isinstance(actions, list):
        return []
    visible: List[Dict[str, Any]] = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        source_layer = _clean(action.get("source_layer")).lower()
        if source_layer in {"beforeeach", "aftereach", "beforeall", "afterall", "hook"}:
            continue
        action_type = _clean(action.get("type")).lower()
        target = _clean(action.get("target_hint"))
        if action_type or target:
            visible.append(action)
    return visible


def _assertions(workflow: Dict[str, Any]) -> List[Dict[str, Any]]:
    assertions = _workflow(workflow).get("assertions") or []
    return [item for item in assertions if isinstance(item, dict)]


def _setup_items(workflow: Dict[str, Any]) -> List[Dict[str, Any]]:
    setup = _workflow(workflow).get("setup") or []
    return [item for item in setup if isinstance(item, dict)]


def _prompt_semantics(workflow: Dict[str, Any]) -> Dict[str, Any]:
    semantics = _workflow(workflow).get("prompt_semantics") or {}
    return semantics if isinstance(semantics, dict) else {}


def _semantic_items(semantics: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    items = semantics.get(key) or []
    return [item for item in items if isinstance(item, dict)]


def _semantic_precondition_phrase(item: Dict[str, Any]) -> str:
    return _clean(item.get("text")) or _clean(item.get("kind"))


def _semantic_step_phrase(item: Dict[str, Any], *, include_detail: bool) -> str:
    phrase = _clean(item.get("text"))
    if not phrase:
        action_type = _clean(item.get("action_type")).lower() or "exercise"
        phrase = f"{action_type} the relevant UI behavior"
    detail = _clean(item.get("safe_detail"))
    if include_detail and detail:
        return f"{phrase} ({detail})"
    return phrase


def _semantic_expected_phrase(item: Dict[str, Any], *, include_detail: bool) -> str:
    phrase = _clean(item.get("observable_outcome")) or _clean(item.get("text"))
    detail = _clean(item.get("safe_detail"))
    if include_detail and detail:
        return f"{phrase}; {detail}"
    return phrase


def _action_phrase(action: Dict[str, Any], *, include_detail: bool) -> str:
    action_type = _clean(action.get("type")).lower() or "exercise"
    target = _clean(action.get("target_hint")) or "the relevant UI behavior"
    if action_type == "navigate":
        phrase = f"navigate to {target}"
    else:
        phrase = f"{action_type} {target}"
    detail = _clean(action.get("prompt_safe_detail"))
    if include_detail and detail:
        phrase = f"{phrase} ({detail})"
    return phrase


def _assertion_phrase(assertion: Dict[str, Any], *, include_detail: bool) -> str:
    intent = _clean(assertion.get("intent")) or _clean(assertion.get("kind")) or "the expected observable behavior occurs"
    detail = _clean(assertion.get("prompt_safe_detail"))
    if include_detail and detail:
        return f"{intent}; {detail}"
    return intent


def _assertion_phrase_with_goal(assertion: Dict[str, Any], goal: str, *, include_detail: bool) -> str:
    phrase = _assertion_phrase(assertion, include_detail=include_detail)
    generic_phrases = {
        "expected browser or ui behavior occurs",
        "the expected observable behavior occurs",
        "observable assertion",
        "generic assertion",
        "unspecified",
    }
    if phrase.lower() in generic_phrases and goal:
        return f"verify that {goal}"
    return phrase


def _setup_phrase(item: Dict[str, Any]) -> str:
    kind = _clean(item.get("kind")) or "required test setup"
    count = _clean(item.get("count"))
    if count and count not in {"0", "1"}:
        return f"{kind} ({count} signals)"
    return kind


def _join(items: Sequence[str], fallback: str) -> str:
    clean_items = [_clean(item) for item in items if _clean(item)]
    if not clean_items:
        return fallback
    return "; ".join(clean_items)


def build_level_scenario(task: Dict[str, Any], workflow: Dict[str, Any], level: str) -> str:
    """Build the level-specific natural language scenario paragraph."""
    goal = _goal(workflow)
    semantics = _prompt_semantics(workflow)
    scenario_summary = _clean(semantics.get("scenario_summary")) or goal
    semantic_preconditions = _semantic_items(semantics, "preconditions")
    semantic_steps = _semantic_items(semantics, "user_workflow_steps")
    semantic_expected = _semantic_items(semantics, "expected_results")
    has_semantics = bool(semantic_preconditions or semantic_steps or semantic_expected or _clean(semantics.get("scenario_summary")))

    if has_semantics:
        if level == "high":
            assertion_summary = _join(
                [_semantic_expected_phrase(item, include_detail=False) for item in semantic_expected[:2]],
                "the user-facing outcome is correct",
            )
            return (
                f"Scenario: Verify the user-facing behavior for {scenario_summary}. "
                f"The test should focus on the business-visible outcome: {assertion_summary}."
            )

        if level == "medium":
            workflow_summary = _join(
                [_semantic_step_phrase(item, include_detail=False) for item in semantic_steps[:6]],
                "exercise the relevant user-visible workflow",
            )
            assertion_summary = _join(
                [_semantic_expected_phrase(item, include_detail=False) for item in semantic_expected[:4]],
                "the expected observable browser or UI behavior occurs",
            )
            setup_summary = _join(
                [_semantic_precondition_phrase(item) for item in semantic_preconditions[:3]],
                "use the repository's normal test setup",
            )
            return (
                f"Scenario: {scenario_summary}. "
                f"Preconditions: {setup_summary}. "
                f"User workflow: {workflow_summary}. "
                f"Expected result: {assertion_summary}."
            )

        if level == "low":
            workflow_summary = _join(
                [_semantic_step_phrase(item, include_detail=True) for item in semantic_steps[:8]],
                "exercise the relevant user-visible workflow",
            )
            assertion_summary = _join(
                [_semantic_expected_phrase(item, include_detail=True) for item in semantic_expected[:5]],
                "the expected observable browser or UI behavior occurs",
            )
            setup_summary = _join(
                [_semantic_precondition_phrase(item) for item in semantic_preconditions[:4]],
                "use the repository's normal test setup",
            )
            return (
                f"Scenario: {scenario_summary}. "
                f"Preconditions: {setup_summary}. "
                f"Detailed user workflow: {workflow_summary}. "
                f"Expected observable state: {assertion_summary}."
            )

    actions = _visible_actions(workflow)
    assertions = _assertions(workflow)
    setup_items = _setup_items(workflow)

    if level == "high":
        assertion_summary = _join(
            [_assertion_phrase_with_goal(assertion, goal, include_detail=False) for assertion in assertions[:2]],
            "the user-facing outcome is correct",
        )
        return (
            f"Scenario: Verify the user-facing behavior for {goal}. "
            f"The test should focus on the business-visible outcome: {assertion_summary}."
        )

    if level == "medium":
        workflow_summary = _join(
            [_action_phrase(action, include_detail=False) for action in actions[:6]],
            "exercise the relevant user-visible workflow",
        )
        assertion_summary = _join(
            [_assertion_phrase_with_goal(assertion, goal, include_detail=False) for assertion in assertions[:4]],
            "the expected observable browser or UI behavior occurs",
        )
        setup_summary = _join(
            [_setup_phrase(item) for item in setup_items[:3]],
            "use the repository's normal test setup",
        )
        return (
            f"Scenario: {goal}. "
            f"Preconditions: {setup_summary}. "
            f"User workflow: {workflow_summary}. "
            f"Expected result: {assertion_summary}."
        )

    if level == "low":
        workflow_summary = _join(
            [_action_phrase(action, include_detail=True) for action in actions[:8]],
            "exercise the relevant user-visible workflow",
        )
        assertion_summary = _join(
            [_assertion_phrase_with_goal(assertion, goal, include_detail=True) for assertion in assertions[:5]],
            "the expected observable browser or UI behavior occurs",
        )
        setup_summary = _join(
            [_setup_phrase(item) for item in setup_items[:4]],
            "use the repository's normal test setup",
        )
        return (
            f"Scenario: {goal}. "
            f"Preconditions: {setup_summary}. "
            f"Detailed user workflow: {workflow_summary}. "
            f"Expected observable state: {assertion_summary}."
        )

    raise ValueError(f"Unsupported prompt level: {level!r}")


def build_prompt(task: Dict[str, Any], workflow: Dict[str, Any], level: str = "medium") -> str:
    """Build a complete prompt for one abstraction level."""
    if level not in PROMPT_LEVELS:
        raise ValueError(f"Unsupported prompt level: {level!r}")
    framework = _framework_label(task.get("framework"))
    agent_test_file = _clean(task.get("agent_test_file"))
    verification_command = _clean(task.get("verification_command"))
    target_file_line = f"- Place the new test at `{agent_test_file}`." if agent_test_file else "- Create exactly one new UI test."
    verification_line = (
        f"- Run this verification command before finishing: `{verification_command}`."
        if verification_command
        else "- Run the smallest relevant UI test command before finishing."
    )
    return "\n".join(
        [
            f"Create one new {framework} UI test in this repository.",
            "",
            "A human-written UI test for this scenario has been removed. Recreate the behavior from the task description without using hidden reference tests.",
            "",
            "Constraints:",
            "- Use the repository's existing UI test framework and conventions.",
            "- You may inspect application code, configuration, existing reusable test utilities, and non-answer tests.",
            "- Do not use the internet.",
            "- Do not modify production source code.",
            "- Prefer stable, user-facing selectors and framework-recommended waiting/assertion patterns.",
            target_file_line,
            verification_line,
            "",
            f"Task description ({level} abstraction):",
            build_level_scenario(task, workflow, level),
        ]
    )


def build_prompt_variants(task: Dict[str, Any], workflow: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build high, medium, and low prompt rows for one RQ6 task."""
    task_id = _clean(task.get("task_id"))
    rows: List[Dict[str, Any]] = []
    for level in PROMPT_LEVELS:
        prompt_id = f"{task_id}__{level}" if task_id else level
        rows.append(
            {
                "task_id": task_id,
                "repo_full_name": _clean(task.get("repo_full_name")),
                "prompt_id": prompt_id,
                "source_task_id": task_id,
                "prompt_level": level,
                "prompt_policy_version": PROMPT_POLICY_VERSION,
                "framework": _clean(task.get("framework")),
                "agent_test_file": _clean(task.get("agent_test_file")),
                "verification_command": _clean(task.get("verification_command")),
                "prompt": build_prompt(task, workflow, level),
            }
        )
    return rows
