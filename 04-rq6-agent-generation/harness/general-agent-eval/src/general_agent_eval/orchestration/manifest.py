"""Summarize agent results and write the run manifest."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

from general_agent_eval.general_agents.agent_specs import AGENT_SPECS
from general_agent_eval.orchestration.cli import parse_key_value_key
from general_agent_eval.orchestration.docker import ImagePlan
from general_agent_eval.orchestration.services import resolve_service_manifest_path

AGENT_RESULT_SUMMARY_KEYS = (
    "type",
    "subtype",
    "is_error",
    "duration_ms",
    "duration_api_ms",
    "num_turns",
    "total_cost_usd",
    # Codex reports token usage and a status instead of a dollar cost.
    "usage",
    "status",
    "session_id",
    # Error context copied straight from the agent's result message when present.
    "stop_reason",
    "api_error_status",
    "errors",
)

# Qualifies total_cost_usd when a custom --base-url makes it a CLI estimate.
COST_ESTIMATE_NOTE = (
    "total_cost_usd is computed by the Claude Code CLI from token counts using "
    "its built-in Anthropic model price table. A custom --base-url was used "
    "(non-Anthropic gateway, e.g. OpenRouter), so for a non-Anthropic model the "
    "CLI falls back to default Anthropic rates and this figure is an estimate "
    "that may not match the gateway's actual billed cost. Check the provider's "
    "dashboard/usage API for the real cost."
)


def is_agent_result_message(message: object) -> bool:
    if not isinstance(message, dict):
        return False
    return (
        "total_cost_usd" in message
        or "num_turns" in message
        or "duration_ms" in message
    )


def collect_agent_result_summary(
    output_dir: Path,
    output_jsonl_name: str | None,
    *,
    cost_is_estimate: bool = False,
) -> dict[str, Any] | None:
    if output_jsonl_name is None:
        return None

    summary: dict[str, Any] = {
        "source_jsonl": output_jsonl_name,
        "available": False,
    }
    output_jsonl_path = output_dir / output_jsonl_name
    if not output_jsonl_path.is_file():
        return summary

    summary["available"] = True
    result_message: dict[str, Any] | None = None
    invalid_json_lines = 0
    with output_jsonl_path.open(encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                invalid_json_lines += 1
                continue
            if is_agent_result_message(message):
                result_message = message

    if invalid_json_lines:
        summary["invalid_json_lines"] = invalid_json_lines
    if result_message is None:
        return summary

    for key in AGENT_RESULT_SUMMARY_KEYS:
        if key in result_message:
            summary[key] = result_message[key]
    # Guard on a non-null value so the Anthropic-pricing note is never attached to a
    # Codex result, whose total_cost_usd is always null.
    if cost_is_estimate and summary.get("total_cost_usd") is not None:
        summary["total_cost_usd_is_estimate"] = True
        summary["total_cost_usd_note"] = COST_ESTIMATE_NOTE
    return summary


def sanitized_manifest(
    *,
    args: argparse.Namespace,
    input_dir: Path,
    run_dir: Path,
    staged_input: Path,
    output_dir: Path,
    staging_method: str,
    host_env_names: tuple[str, ...],
    preprocessing: dict[str, Any],
    image_plan: ImagePlan,
    service: dict[str, Any] | None = None,
    service_scripts_dir: Path | None = None,
) -> dict[str, Any]:
    service_manifest = None
    if service is not None:
        service_manifest = str(resolve_service_manifest_path(args))
    system_template = getattr(args, "system_template", None)
    user_template = getattr(args, "user_template", None)
    return {
        "created_at": dt.datetime.now(dt.UTC).isoformat(),
        "service": service,
        "service_manifest": service_manifest,
        "service_scripts_dir": str(service_scripts_dir) if service_scripts_dir else None,
        "agent": args.agent,
        "agent_description": AGENT_SPECS[args.agent].description,
        "agent_output_jsonl": AGENT_SPECS[args.agent].output_jsonl_name,
        "input_dir": str(input_dir),
        "output_root": str(run_dir.parent),
        "run_dir": str(run_dir),
        "staged_input": str(staged_input),
        "output_dir": str(output_dir),
        "staging_method": staging_method,
        "preprocessing": preprocessing,
        "docker": {
            "image": image_plan.image,
            "image_built": image_plan.build,
            # The ordered build chain (base -> agent -> workload [-> overlay]).
            # Empty when a pre-built or pre-existing image ran.
            "layers": [
                {
                    "name": layer.name,
                    "dockerfile": str(layer.dockerfile),
                    "image": layer.image,
                }
                for layer in image_plan.layers
            ],
            "network": args.network,
            "memory": args.memory,
            "cpus": args.cpus,
            "pids_limit": args.pids_limit,
            "skip_build": args.skip_build,
        },
        "agent_options": {
            "model": args.model,
            "small_model": getattr(args, "small_model", None),
            "permission_mode": args.permission_mode,
            "effort": getattr(args, "effort", None),
            "sandbox": getattr(args, "sandbox", None),
            "system_prompt_config": args.system_prompt_config,
            # Host paths; null means the packaged template was used.
            "system_template": str(system_template) if system_template else None,
            "user_template": str(user_template) if user_template else None,
            "prompt_vars": list(getattr(args, "prompt_var", [])),
            "base_url": args.base_url,
            "api_key_env": args.api_key_env,
            "auth_token_env": args.auth_token_env,
            "oauth_token_env": args.oauth_token_env,
            "max_turns": args.max_turns,
            "max_budget_usd": args.max_budget_usd,
            "reset_git": args.reset_git,
            "clear_tests": args.clear_tests,
            "inject_rest_assured": args.inject_rest_assured,
            "workload": getattr(args, "workload", "java"),
            "agent_env_keys": [
                parse_key_value_key(value, option_name="--env") for value in args.env
            ],
            "extra_args": list(args.extra_arg),
        },
        "host_env_passthrough": list(host_env_names),
    }


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
