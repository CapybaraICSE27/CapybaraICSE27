from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from openai_codex import ApprovalMode, Codex, CodexConfig, Sandbox
from openai_codex.models import (
    AgentMessageDeltaNotification,
    ErrorNotification,
    ThreadTokenUsageUpdatedNotification,
    TurnCompletedNotification,
)

# Reuse the agent-agnostic prompt/parse helpers; claude_agent_sdk (imported by
# claude_code) is a core dependency, so this import is always satisfiable.
from general_agent_eval.general_agents.claude_code import (
    DEFAULT_USER_TEMPLATE,
    DEFAULT_SYSTEM_TEMPLATE,
    DEFAULT_USER_TEMPLATE_JS_UI,
    DEFAULT_SYSTEM_TEMPLATE_JS_UI,
    HarnessError,
    build_template_context,
    parse_env_values,
    parse_prompt_vars,
    positive_int,
    render_template,
)

SANDBOX_MODES = ("read_only", "workspace_write", "full_access")
# The standalone runner executes on the host, so it defaults to workspace_write
# (edits confined to the working dir). general-agent-eval-docker-run passes
# --sandbox full_access explicitly, since the container is the boundary there.
DEFAULT_SANDBOX = "workspace_write"
SANDBOX_BY_NAME = {
    "read_only": Sandbox.read_only,
    "workspace_write": Sandbox.workspace_write,
    "full_access": Sandbox.full_access,
}
# Custom-gateway model provider id used when --base-url is supplied.
GATEWAY_PROVIDER_ID = "general_agent_eval_gateway"

# Codex reports token usage and duration but no dollar cost, so total_cost_usd is
# always null; this note travels with the synthesized result record.
CODEX_NO_COST_NOTE = (
    "Codex does not report a dollar cost. total_cost_usd is null; use the token "
    "counts in 'usage' and the provider's billing dashboard for actual spend."
)


def build_codex_config_overrides(args: argparse.Namespace) -> tuple[str, ...]:
    """Codex `--config key=value` overrides; SDK-free so it is unit-testable offline."""
    if not args.base_url:
        return ()
    return (
        f"model_provider={GATEWAY_PROVIDER_ID}",
        f"model_providers.{GATEWAY_PROVIDER_ID}.name=GeneralAgentEvalGateway",
        f"model_providers.{GATEWAY_PROVIDER_ID}.base_url={args.base_url}",
        f"model_providers.{GATEWAY_PROVIDER_ID}.env_key=OPENAI_API_KEY",
    )


def build_codex_config(args: argparse.Namespace, *, input_dir: Path) -> CodexConfig:
    env = parse_env_values(args.env)
    if args.base_url:
        env.setdefault("OPENAI_BASE_URL", args.base_url)
    return CodexConfig(
        cwd=str(input_dir),
        env=env or None,
        config_overrides=build_codex_config_overrides(args),
    )


def build_system_prompt(
    system_prompt_config: str, rendered_system_prompt: str
) -> dict[str, str]:
    """Map the shared system-prompt-config to Codex thread_start kwargs.

    replace -> base_instructions (full replacement of Codex's built-in prompt);
    append  -> developer_instructions (additive); none -> neither.
    """
    system_prompt = rendered_system_prompt.strip()
    if system_prompt_config == "replace":
        if not system_prompt:
            raise HarnessError(
                "--system-prompt-config replace requires a non-empty rendered "
                "system prompt, but the system template rendered empty"
            )
        return {"base_instructions": system_prompt}
    if system_prompt_config == "append" and system_prompt:
        return {"developer_instructions": rendered_system_prompt}
    return {}


def _dump(value: object) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return value
    return repr(value)


def coerce_notification(notification: object) -> dict[str, Any]:
    payload = getattr(notification, "payload", None)
    return {
        "method": getattr(notification, "method", None),
        "payload": _dump(payload),
    }


def print_notification(notification: object) -> None:
    payload = getattr(notification, "payload", None)
    if isinstance(payload, AgentMessageDeltaNotification):
        print(payload.delta, end="", flush=True)
    elif isinstance(payload, ErrorNotification):
        print(f"\n[error] {getattr(payload.error, 'message', payload.error)}", flush=True)
    elif isinstance(payload, TurnCompletedNotification):
        print(
            f"\n[result] status={getattr(payload.turn.status, 'value', payload.turn.status)} "
            f"duration_ms={payload.turn.duration_ms}",
            flush=True,
        )


def synthesize_result_record(
    final_turn: object, token_usage: object, *, final_response: str | None
) -> dict[str, Any]:
    """Trailing JSONL record the orchestration manifest detects (keys on duration_ms)."""
    status = getattr(final_turn, "status", None)
    status_str = getattr(status, "value", status)
    error = getattr(final_turn, "error", None)
    return {
        "type": "result",
        "subtype": status_str or "unknown",
        # TurnStatus.completed is the only success state.
        "is_error": status_str != "completed",
        "duration_ms": getattr(final_turn, "duration_ms", None),
        "num_turns": 1,
        "total_cost_usd": None,
        "total_cost_usd_note": CODEX_NO_COST_NOTE,
        "result": final_response,
        "status": status_str,
        "usage": _dump(token_usage),
        "error": _dump(error),
    }


def run_codex(
    *,
    user_prompt: str,
    system_prompt_kwargs: dict[str, str],
    args: argparse.Namespace,
    input_dir: Path,
) -> int:
    if args.api_key_env and args.api_key_env not in os.environ:
        raise HarnessError(
            f"--api-key-env points to an unset variable: {args.api_key_env}"
        )

    output_jsonl = None
    if args.output_jsonl is not None:
        output_path = args.output_jsonl.expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_jsonl = output_path.open("w", encoding="utf-8")

    final_text: list[str] = []
    final_turn: object | None = None
    token_usage: object | None = None
    try:
        with Codex(config=build_codex_config(args, input_dir=input_dir)) as codex:
            if args.api_key_env:
                codex.login_api_key(os.environ[args.api_key_env])
            thread = codex.thread_start(
                approval_mode=ApprovalMode.auto_review,
                sandbox=SANDBOX_BY_NAME[args.sandbox],
                model=args.model,
                cwd=str(input_dir),
                **system_prompt_kwargs,
            )
            handle = thread.turn(user_prompt)
            for notification in handle.stream():
                print_notification(notification)
                if output_jsonl is not None:
                    output_jsonl.write(
                        json.dumps(coerce_notification(notification), default=str) + "\n"
                    )
                    output_jsonl.flush()

                payload = notification.payload
                if isinstance(payload, AgentMessageDeltaNotification):
                    final_text.append(payload.delta)
                elif isinstance(payload, ThreadTokenUsageUpdatedNotification):
                    token_usage = payload.token_usage
                elif isinstance(payload, TurnCompletedNotification):
                    final_turn = payload.turn
    except HarnessError:
        raise
    except Exception as exc:  # noqa: BLE001 - surface any SDK/binary failure uniformly
        raise HarnessError(f"Codex run failed: {type(exc).__name__}: {exc}") from exc
    finally:
        if output_jsonl is not None and final_turn is not None:
            result_record = synthesize_result_record(
                final_turn, token_usage, final_response="".join(final_text) or None
            )
            output_jsonl.write(json.dumps(result_record, default=str) + "\n")
            output_jsonl.flush()
        if output_jsonl is not None:
            output_jsonl.close()

    status = getattr(getattr(final_turn, "status", None), "value", None)
    return 0 if status == "completed" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run an OpenAI Codex evaluation against a directory."
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        type=Path,
        help="Directory Codex should use as its working directory.",
    )
    parser.add_argument(
        "--workload",
        choices=("java", "javascript"),
        default="java",
        help=(
            "Target workload ecosystem. Selects the default prompt templates "
            "when --system-template / --user-template are not supplied. "
            "Defaults to java."
        ),
    )
    parser.add_argument(
        "--system-template",
        type=Path,
        default=None,
        help=(
            "Jinja2 template for the system prompt. Defaults to the packaged "
            "Java or JavaScript template selected by --workload."
        ),
    )
    parser.add_argument(
        "--user-template",
        type=Path,
        default=None,
        help=(
            "Jinja2 template for the user prompt. Defaults to the packaged "
            "Java or JavaScript template selected by --workload."
        ),
    )
    parser.add_argument(
        "--system-prompt-config",
        choices=("append", "replace", "none"),
        default="replace",
        help=(
            "How to apply the rendered system template. replace maps to Codex "
            "base_instructions (full replacement), append to developer_instructions "
            "(additive), none to neither. Defaults to replace."
        ),
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Codex model (e.g. gpt-5-codex). Required; there is no default.",
    )
    parser.add_argument(
        "--sandbox",
        choices=SANDBOX_MODES,
        default=DEFAULT_SANDBOX,
        help=(
            "Codex sandbox mode. Defaults to workspace_write because the standalone "
            "runner executes on the host; raise to full_access (used under Docker, "
            "where the container is the boundary) or lower to read_only as needed."
        ),
    )
    parser.add_argument(
        "--base-url",
        help=(
            "Base URL of a custom OpenAI-compatible gateway. Registers a Codex model "
            "provider pointed at this URL (auth via OPENAI_API_KEY)."
        ),
    )
    parser.add_argument(
        "--api-key-env",
        help="Environment variable holding the API key passed to codex.login_api_key.",
    )
    parser.add_argument(
        "--env",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Additional environment variable for the Codex process. Can be repeated.",
    )
    parser.add_argument(
        "--prompt-var",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help=(
            "Extra variable injected into the user/system prompt templates "
            "(e.g. service_base_url). Can be repeated."
        ),
    )
    parser.add_argument(
        "--max-turns",
        type=positive_int,
        help="Accepted for harness parity; Codex runs a single turn per invocation.",
    )
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        help="Optional path for raw SDK notifications as JSONL.",
    )
    parser.add_argument(
        "--reset-git",
        action="store_true",
        help=(
            "Before running Codex, discard Git changes in --input-dir and reset to "
            "the current repo HEAD or superproject-pinned submodule commit."
        ),
    )
    return parser


def prepare_run(args: argparse.Namespace) -> tuple[Path, str, dict[str, str]]:
    input_dir = args.input_dir.expanduser().resolve()
    if not input_dir.exists():
        raise HarnessError(f"--input-dir does not exist: {args.input_dir}")
    if not input_dir.is_dir():
        raise HarnessError(f"--input-dir is not a directory: {args.input_dir}")

    workload = getattr(args, "workload", "java")
    is_js = workload == "javascript"
    effective_system = args.system_template or (
        DEFAULT_SYSTEM_TEMPLATE_JS_UI if is_js else DEFAULT_SYSTEM_TEMPLATE
    )
    effective_user = args.user_template or (
        DEFAULT_USER_TEMPLATE_JS_UI if is_js else DEFAULT_USER_TEMPLATE
    )

    context = build_template_context(
        input_dir=input_dir,
        model=args.model,
        prompt_vars=parse_prompt_vars(args.prompt_var),
    )
    rendered_user_prompt = render_template(effective_user, context)
    if not rendered_user_prompt.strip():
        raise HarnessError("Rendered user prompt is empty")

    rendered_system_prompt = render_template(effective_system, context)
    system_prompt_kwargs = build_system_prompt(
        args.system_prompt_config, rendered_system_prompt
    )
    return input_dir, rendered_user_prompt, system_prompt_kwargs


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        input_dir, user_prompt, system_prompt_kwargs = prepare_run(args)
        if args.reset_git:
            from general_agent_eval.preprocessing.git_reset import (
                GitVcsError,
                reset_to_pinned_commit,
            )

            try:
                result = reset_to_pinned_commit(input_dir)
            except GitVcsError as exc:
                raise HarnessError(f"Failed to reset Git state: {exc}") from exc
            print(
                "[git-reset] " f"repo={result.repo_root} commit={result.pinned_commit}",
                flush=True,
            )
        return run_codex(
            user_prompt=user_prompt,
            system_prompt_kwargs=system_prompt_kwargs,
            args=args,
            input_dir=input_dir,
        )
    except HarnessError as exc:
        parser.exit(2, f"error: {exc}\n")
    except KeyboardInterrupt:
        parser.exit(130, "interrupted\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
