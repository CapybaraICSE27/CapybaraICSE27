from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    CLIJSONDecodeError,
    CLINotFoundError,
    ClaudeAgentOptions,
    ProcessError,
    query,
)
from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateError

MODULE_DIR = Path(__file__).resolve().parent
PACKAGE_DIR = MODULE_DIR.parent
PROJECT_ROOT = (
    PACKAGE_DIR.parent.parent if PACKAGE_DIR.parent.name == "src" else Path.cwd()
).resolve()
PROMPTS_DIR = PACKAGE_DIR / "prompts"

DEFAULT_SYSTEM_TEMPLATE = PROMPTS_DIR / "system_prompt.jinja2"
DEFAULT_USER_TEMPLATE = PROMPTS_DIR / "user_prompt.jinja2"
DEFAULT_SYSTEM_TEMPLATE_JS_UI = PROMPTS_DIR / "system_prompt_js_ui.jinja2"
DEFAULT_USER_TEMPLATE_JS_UI = PROMPTS_DIR / "user_prompt_js_ui.jinja2"
PERMISSION_MODES = (
    "default",
    "acceptEdits",
    "plan",
    "auto",
    "dontAsk",
    "bypassPermissions",
)
DEFAULT_PERMISSION_MODE = "bypassPermissions"
# Reasoning effort levels accepted by ClaudeAgentOptions.effort (forwarded to the
# CLI as --effort). xhigh is Opus 4.7 only and falls back to high elsewhere.
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")
DEFAULT_EFFORT = "high"
DISALLOWED_TOOLS = ("WebSearch", "WebFetch")

# Base context keys that --prompt-var must not clobber.
RESERVED_PROMPT_VARS = frozenset(
    {"input_dir", "input_dir_name", "repo_root", "script_dir", "model"}
)
# Service keys are always defined (empty by default) so templates can guard them with
# {% if service_base_url %} under StrictUndefined even when no --service is in play.
SERVICE_CONTEXT_DEFAULTS = {
    "service_id": "",
    "service_base_url": "",
    "rest_assured": "",
    "test_module": "",
}


class HarnessError(RuntimeError):
    pass


def parse_key_value(raw_value: str, *, option_name: str) -> tuple[str, str]:
    if "=" not in raw_value:
        raise HarnessError(f"{option_name} values must use KEY=VALUE format")

    key, value = raw_value.split("=", 1)
    key = key.strip()
    if not key:
        raise HarnessError(f"{option_name} key cannot be empty")
    return key, value


def parse_env_values(raw_values: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for raw_value in raw_values:
        key, value = parse_key_value(raw_value, option_name="--env")
        parsed[key] = value
    return parsed


def parse_prompt_vars(raw_values: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for raw_value in raw_values:
        key, value = parse_key_value(raw_value, option_name="--prompt-var")
        if key in RESERVED_PROMPT_VARS:
            raise HarnessError(
                f"--prompt-var key '{key}' is reserved and cannot be overridden"
            )
        parsed[key] = value
    return parsed


def parse_extra_args(raw_values: list[str]) -> dict[str, str | None]:
    parsed: dict[str, str | None] = {}
    for raw_value in raw_values:
        flag, separator, value = raw_value.partition("=")
        # SDK extra_args keys omit the leading --; a bare flag becomes a boolean.
        flag = flag.strip().lstrip("-")
        if not flag:
            raise HarnessError("--extra-arg flag name cannot be empty")
        parsed[flag] = value if separator else None
    return parsed


def parse_headers(raw_values: list[str]) -> list[str]:
    headers: list[str] = []
    for raw_value in raw_values:
        if ":" not in raw_value:
            raise HarnessError("--custom-header values must use 'Name: Value' format")
        name, value = raw_value.split(":", 1)
        name = name.strip()
        if not name:
            raise HarnessError("--custom-header name cannot be empty")
        headers.append(f"{name}: {value.strip()}")
    return headers


def render_template(template_path: Path, context: dict[str, Any]) -> str:
    resolved_path = template_path.expanduser().resolve()
    if not resolved_path.exists():
        raise HarnessError(f"Template does not exist: {template_path}")
    if not resolved_path.is_file():
        raise HarnessError(f"Template is not a file: {template_path}")

    environment = Environment(
        loader=FileSystemLoader(str(resolved_path.parent)),
        undefined=StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
    )
    try:
        return environment.get_template(resolved_path.name).render(context)
    except TemplateError as exc:
        raise HarnessError(f"Failed to render {resolved_path}: {exc}") from exc


def build_template_context(
    *,
    input_dir: Path,
    model: str,
    prompt_vars: dict[str, str] | None = None,
) -> dict[str, Any]:
    context: dict[str, Any] = {
        "input_dir": str(input_dir),
        "input_dir_name": input_dir.name,
        "repo_root": str(PROJECT_ROOT),
        "script_dir": str(MODULE_DIR),
        "model": model,
        **SERVICE_CONTEXT_DEFAULTS,
    }
    if prompt_vars:
        context.update(prompt_vars)
    return context


def build_system_prompt(
    system_prompt_config: str, rendered_system_prompt: str
) -> object:
    system_prompt = rendered_system_prompt.strip()
    if system_prompt_config == "none":
        return {"type": "preset", "preset": "claude_code"}
    if system_prompt_config == "replace":
        if not system_prompt:
            raise HarnessError(
                "--system-prompt-config replace requires a non-empty rendered "
                "system prompt, but the system template rendered empty"
            )
        return system_prompt
    if system_prompt:
        return {
            "type": "preset",
            "preset": "claude_code",
            "append": rendered_system_prompt,
        }
    return {"type": "preset", "preset": "claude_code"}


def build_agent_env(args: argparse.Namespace) -> dict[str, str]:
    env_values = parse_env_values(args.env)

    if args.small_model:
        # Pin Claude Code's auxiliary small/fast model (defaults to Haiku 4.5); the
        # dedicated flag wins over any --env of the same key.
        env_values["ANTHROPIC_SMALL_FAST_MODEL"] = args.small_model

    if args.base_url:
        env_values["ANTHROPIC_BASE_URL"] = args.base_url
        env_values.setdefault("ANTHROPIC_CUSTOM_MODEL_OPTION", args.model)
        # Custom gateways reject Claude Code's experimental anthropic-beta headers;
        # disable them by default (override with --env ..._BETAS=0 for beta-capable endpoints).
        env_values.setdefault("CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS", "1")

    if args.api_key_env:
        if args.api_key_env not in os.environ:
            raise HarnessError(
                f"--api-key-env points to an unset variable: {args.api_key_env}"
            )
        env_values["ANTHROPIC_API_KEY"] = os.environ[args.api_key_env]
    if args.auth_token_env:
        if args.auth_token_env not in os.environ:
            raise HarnessError(
                f"--auth-token-env points to an unset variable: {args.auth_token_env}"
            )
        env_values["ANTHROPIC_AUTH_TOKEN"] = os.environ[args.auth_token_env]
    if args.oauth_token_env:
        if args.oauth_token_env not in os.environ:
            raise HarnessError(
                f"--oauth-token-env points to an unset variable: {args.oauth_token_env}"
            )
        env_values["CLAUDE_CODE_OAUTH_TOKEN"] = os.environ[args.oauth_token_env]

    if args.api_key:
        env_values["ANTHROPIC_API_KEY"] = args.api_key
    if args.auth_token:
        env_values["ANTHROPIC_AUTH_TOKEN"] = args.auth_token

    headers = parse_headers(args.custom_header)
    if headers:
        existing_headers = env_values.get("ANTHROPIC_CUSTOM_HEADERS")
        env_values["ANTHROPIC_CUSTOM_HEADERS"] = "\n".join(
            [header for header in [existing_headers, *headers] if header]
        )

    return env_values


def build_claude_options_kwargs(
    *,
    args: argparse.Namespace,
    input_dir: Path,
    system_prompt: object,
) -> dict[str, Any]:
    options_kwargs: dict[str, Any] = {
        "cwd": input_dir,
        "env": build_agent_env(args),
        "model": args.model,
        "permission_mode": args.permission_mode,
        "effort": args.effort,
        "disallowed_tools": list(DISALLOWED_TOOLS),
        "setting_sources": ["user"],
        "system_prompt": system_prompt,
        "tools": {"type": "preset", "preset": "claude_code"},
    }
    if args.max_turns is not None:
        options_kwargs["max_turns"] = args.max_turns
    if args.max_budget_usd is not None:
        options_kwargs["max_budget_usd"] = args.max_budget_usd
    extra_args = parse_extra_args(args.extra_arg)
    if extra_args:
        options_kwargs["extra_args"] = extra_args
    return options_kwargs


def coerce_message(message: object) -> Any:
    if is_dataclass(message) and not isinstance(message, type):
        return asdict(message)
    if hasattr(message, "model_dump"):
        return message.model_dump()
    if hasattr(message, "__dict__"):
        return vars(message)
    return repr(message)


def print_message(message: object) -> None:
    message_type = type(message).__name__

    if message_type == "AssistantMessage":
        for block in getattr(message, "content", []):
            if type(block).__name__ == "TextBlock":
                print(getattr(block, "text", ""), end="", flush=True)
            elif type(block).__name__ == "ToolUseBlock":
                print(f"\n[tool] {getattr(block, 'name', 'unknown')}", flush=True)
        return

    if message_type == "ResultMessage":
        result = getattr(message, "result", None)
        if result:
            print(f"\n{result}", flush=True)
        print(
            "\n[result] "
            f"subtype={getattr(message, 'subtype', 'unknown')} "
            f"turns={getattr(message, 'num_turns', 'unknown')} "
            f"cost_usd={getattr(message, 'total_cost_usd', None)}",
            flush=True,
        )
        return

    if message_type == "SystemMessage":
        subtype = getattr(message, "subtype", None)
        if subtype:
            print(f"\n[system] {subtype}", flush=True)


async def run_claude(
    *,
    user_prompt: str,
    system_prompt: object,
    args: argparse.Namespace,
    input_dir: Path,
) -> int:
    options_kwargs = build_claude_options_kwargs(
        args=args,
        input_dir=input_dir,
        system_prompt=system_prompt,
    )

    output_jsonl = None
    if args.output_jsonl is not None:
        output_path = args.output_jsonl.expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_jsonl = output_path.open("w", encoding="utf-8")

    exit_code = 0
    try:
        try:
            async for message in query(
                prompt=user_prompt,
                options=ClaudeAgentOptions(**options_kwargs),
            ):
                print_message(message)
                if output_jsonl is not None:
                    output_jsonl.write(
                        json.dumps(coerce_message(message), default=str) + "\n"
                    )
                    output_jsonl.flush()

                if type(message).__name__ == "ResultMessage" and getattr(
                    message, "is_error", False
                ):
                    # Don't return mid-iteration: let the loop end naturally so the SDK
                    # generator tears itself down instead of raising on a forced aclose().
                    exit_code = 1
        except CLINotFoundError as exc:
            raise HarnessError(
                "Claude Code CLI was not found. Install it and ensure `claude` "
                "is on PATH."
            ) from exc
        except ProcessError as exc:
            exit_code = getattr(exc, "exit_code", "unknown")
            raise HarnessError(
                f"Claude Code process failed with exit code: {exit_code}"
            ) from exc
        except CLIJSONDecodeError as exc:
            raise HarnessError(f"Claude Code emitted invalid SDK JSON: {exc}") from exc
    finally:
        if output_jsonl is not None:
            output_jsonl.close()

    return exit_code


def positive_int(raw_value: str) -> int:
    value = int(raw_value)
    if value <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return value


def positive_float(raw_value: str) -> float:
    value = float(raw_value)
    if value <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a Claude Code evaluation against a directory."
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        type=Path,
        help="Directory Claude Code should use as its working directory.",
    )
    parser.add_argument(
        "--workload",
        choices=("java", "javascript"),
        default="java",
        help=(
            "Target workload ecosystem. Selects the default prompt templates "
            "when --system-template / --user-template are not supplied: "
            "'java' uses the Java API-test prompts, 'javascript' uses the "
            "Cypress UI-test prompts. Defaults to java."
        ),
    )
    parser.add_argument(
        "--system-template",
        type=Path,
        default=None,
        help=(
            "Jinja2 template for system prompt additions. Defaults to the "
            "packaged Java or JavaScript template selected by --workload."
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
            "How to apply the rendered system template. Defaults to replace, "
            "which uses the rendered template as the entire system prompt "
            "(no Claude Code preset) and errors if it renders empty."
        ),
    )
    parser.add_argument(
        "--model",
        default="sonnet",
        help="Claude Code model alias, Anthropic model ID, or gateway model ID.",
    )
    parser.add_argument(
        "--small-model",
        help=(
            "Override Claude Code's small/fast model via ANTHROPIC_SMALL_FAST_MODEL. "
            "This model only handles auxiliary background work (conversation titles, "
            "summaries, topic detection), never the main agent loop or subagents, and "
            "defaults to Haiku 4.5 when unset."
        ),
    )
    parser.add_argument(
        "--permission-mode",
        choices=PERMISSION_MODES,
        default=DEFAULT_PERMISSION_MODE,
        help=(
            "Claude Code permission mode. Defaults to bypassPermissions so "
            "isolated evaluation runs do not pause for edit approval."
        ),
    )
    parser.add_argument(
        "--effort",
        choices=EFFORT_LEVELS,
        default=DEFAULT_EFFORT,
        help=(
            "Reasoning effort Claude Code spends per response, forwarded natively "
            "to the harness as --effort to guide adaptive thinking depth. xhigh "
            "applies to Opus 4.7 only and falls back to high elsewhere. Defaults "
            "to high."
        ),
    )
    parser.add_argument(
        "--base-url",
        help=(
            "Base URL of an Anthropic-compatible API (e.g. a LiteLLM proxy). "
            "Pass only the root, e.g. http://localhost:4000, and Claude Code "
            "appends /v1/messages. Mapped to ANTHROPIC_BASE_URL."
        ),
    )
    parser.add_argument(
        "--api-key-env",
        help="Environment variable containing an API key for ANTHROPIC_API_KEY.",
    )
    parser.add_argument(
        "--auth-token-env",
        help="Environment variable containing a bearer token for ANTHROPIC_AUTH_TOKEN.",
    )
    parser.add_argument(
        "--oauth-token-env",
        help=(
            "Environment variable containing a Claude Code OAuth token for "
            "CLAUDE_CODE_OAUTH_TOKEN."
        ),
    )
    parser.add_argument(
        "--api-key",
        help="Direct one-off value for ANTHROPIC_API_KEY.",
    )
    parser.add_argument(
        "--auth-token",
        help="Direct one-off value for ANTHROPIC_AUTH_TOKEN.",
    )
    parser.add_argument(
        "--custom-header",
        action="append",
        default=[],
        metavar="NAME: VALUE",
        help="Custom request header. Can be repeated.",
    )
    parser.add_argument(
        "--env",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Additional Claude Code environment variable. Can be repeated.",
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
        "--extra-arg",
        action="append",
        default=[],
        metavar="FLAG[=VALUE]",
        help=(
            "Extra Claude Code CLI flag passed through to "
            "ClaudeAgentOptions.extra_args. Use FLAG=VALUE for valued flags or a "
            "bare FLAG for boolean flags. Can be repeated."
        ),
    )
    parser.add_argument(
        "--max-turns",
        type=positive_int,
        help="Maximum agentic turns before Claude Code exits.",
    )
    parser.add_argument(
        "--max-budget-usd",
        type=positive_float,
        help="Maximum dollar budget before Claude Code exits.",
    )
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        help="Optional path for raw SDK messages as JSONL.",
    )
    parser.add_argument(
        "--reset-git",
        action="store_true",
        help=(
            "Before running Claude, discard Git changes in --input-dir and reset "
            "to the current repo HEAD or superproject-pinned submodule commit."
        ),
    )
    return parser


def prepare_run(args: argparse.Namespace) -> tuple[Path, str, object]:
    input_dir = args.input_dir.expanduser().resolve()
    if not input_dir.exists():
        raise HarnessError(f"--input-dir does not exist: {args.input_dir}")
    if not input_dir.is_dir():
        raise HarnessError(f"--input-dir is not a directory: {args.input_dir}")

    # Resolve effective templates: an explicit flag wins; otherwise select the
    # packaged default for the chosen workload.
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
    system_prompt = build_system_prompt(
        args.system_prompt_config, rendered_system_prompt
    )

    return input_dir, rendered_user_prompt, system_prompt


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        input_dir, user_prompt, system_prompt = prepare_run(args)
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
        return asyncio.run(
            run_claude(
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                args=args,
                input_dir=input_dir,
            )
        )
    except HarnessError as exc:
        parser.exit(2, f"error: {exc}\n")
    except KeyboardInterrupt:
        parser.exit(130, "interrupted\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
