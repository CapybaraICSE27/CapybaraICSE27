"""RQ4-B: control-flow enclosure metrics from AST-tagged UI actions (Milestone 3)."""

from __future__ import annotations

from typing import Any, Dict, List

PAPER_FACING_EXCLUDED_ACTION_CATEGORIES = frozenset({
    "locator_query",
    "wait_synchronization",
    "unknown_action",
})


def _s(val: Any) -> str:
    return str(val or "").strip().lower()


def is_loop_enclosed(enclosure: str) -> bool:
    return enclosure in ("loop", "loop_and_branch")


def is_branch_enclosed(enclosure: str) -> bool:
    return enclosure in ("branch", "loop_and_branch")


def is_try_catch_branch(kind: str) -> bool:
    return _s(kind) == "try_catch"


def build_control_flow_fields(
    ui_action_events: List[Dict[str, Any]],
    *,
    helper_depth_key: str = "helper_depth",
    metric_prefix: str = "",
) -> Dict[str, Any]:
    """
    Aggregate loop/branch enclosure counts from per-action AST fields.

    conditionalized_action_fraction excludes try_catch enclosure (paper framing).
    non_error_branch_driven_action_count excludes try/catch from branch counts.
    """
    loop_driven = 0
    branch_driven = 0
    loop_and_branch = 0
    helper_loop = 0
    helper_branch = 0
    conditionalized = 0
    non_error_branch = 0
    try_catch_actions = 0
    max_loop_depth = 0
    total = len(ui_action_events)

    for ev in ui_action_events:
        enclosure = _s(ev.get("control_flow_enclosure"))
        branch_kind = _s(ev.get("control_flow_branch_kind"))
        loop_depth = int(ev.get("control_flow_loop_depth") or 0)
        depth = int(ev.get(helper_depth_key) or 0)
        in_helper = depth > 0

        if loop_depth > max_loop_depth:
            max_loop_depth = loop_depth

        if enclosure == "loop_and_branch":
            loop_and_branch += 1
            loop_driven += 1
            branch_driven += 1
        elif enclosure == "loop":
            loop_driven += 1
        elif enclosure == "branch":
            branch_driven += 1

        if is_loop_enclosed(enclosure) and in_helper:
            helper_loop += 1
        if is_branch_enclosed(enclosure) and in_helper:
            helper_branch += 1

        if is_try_catch_branch(branch_kind):
            try_catch_actions += 1
        elif is_branch_enclosed(enclosure):
            conditionalized += 1
            non_error_branch += 1

    prefix = metric_prefix
    return {
        f"{prefix}loop_driven_action_count": loop_driven,
        f"{prefix}branch_driven_action_count": branch_driven,
        f"{prefix}non_error_branch_driven_action_count": non_error_branch,
        f"{prefix}loop_and_branch_action_count": loop_and_branch,
        f"{prefix}helper_loop_driven_action_count": helper_loop,
        f"{prefix}helper_branch_driven_action_count": helper_branch,
        f"{prefix}conditionalized_action_count": conditionalized,
        f"{prefix}conditionalized_action_fraction": (
            round(conditionalized / total, 6) if total else ""
        ),
        f"{prefix}try_catch_enclosed_action_count": try_catch_actions,
        f"{prefix}max_ui_action_loop_depth": max_loop_depth,
        f"{prefix}ui_actions_with_control_flow_field_present": sum(
            1 for ev in ui_action_events if _s(ev.get("control_flow_enclosure"))
        ),
        f"{prefix}ui_actions_with_control_flow_enclosure_non_none": sum(
            1
            for ev in ui_action_events
            if _s(ev.get("control_flow_enclosure")) not in ("", "none")
        ),
    }


def classified_user_action_control_flow_events(
    ui_action_events: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    return [
        ev
        for ev in ui_action_events
        if _s(ev.get("category")) not in PAPER_FACING_EXCLUDED_ACTION_CATEGORIES
    ]


def compute_dual_scope_control_flow_metrics(
    all_layer_events: List[Dict[str, Any]],
    test_body_events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """All-layer + test-body-only control-flow metrics (prefer test_body for paper)."""
    all_metrics = build_control_flow_fields(all_layer_events)
    tb_metrics = build_control_flow_fields(test_body_events)
    classified_all_metrics = build_control_flow_fields(
        classified_user_action_control_flow_events(all_layer_events),
        metric_prefix="classified_user_action_",
    )
    classified_tb_metrics = build_control_flow_fields(
        classified_user_action_control_flow_events(test_body_events),
        metric_prefix="test_body_classified_user_action_",
    )
    includes_non_test_body = len(all_layer_events) != len(test_body_events)
    return {
        **all_metrics,
        "test_body_conditionalized_action_fraction": tb_metrics["conditionalized_action_fraction"],
        "test_body_conditionalized_action_count": tb_metrics["conditionalized_action_count"],
        "test_body_loop_driven_action_count": tb_metrics["loop_driven_action_count"],
        "test_body_non_error_branch_driven_action_count": tb_metrics[
            "non_error_branch_driven_action_count"
        ],
        "all_layer_conditionalized_action_fraction": all_metrics["conditionalized_action_fraction"],
        **classified_all_metrics,
        **classified_tb_metrics,
        "control_flow_scope_all_layers_includes_non_test_body_events": (
            1 if includes_non_test_body else 0
        ),
    }
