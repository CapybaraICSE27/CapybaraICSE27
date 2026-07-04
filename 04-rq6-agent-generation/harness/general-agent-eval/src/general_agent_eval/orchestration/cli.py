"""Command-line parsing, option validation, and per-agent defaults."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from general_agent_eval.general_agents.agent_specs import AGENT_SPECS
from general_agent_eval.general_agents.claude_code import (
    DEFAULT_EFFORT,
    DEFAULT_PERMISSION_MODE,
    EFFORT_LEVELS,
    PERMISSION_MODES,
    RESERVED_PROMPT_VARS,
)
from general_agent_eval.orchestration.errors import DockerRunError
from general_agent_eval.orchestration.staging import RUN_ID_DELIMITER

# Docker default sandbox: the container (cap-drop ALL, no-new-privileges) is the
# boundary, so the codex agent runs unrestricted inside it. The standalone codex
# runner defaults lower (workspace_write) because it executes on the host.
DEFAULT_SANDBOX = "full_access"


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


def parse_key_value_key(raw_value: str, *, option_name: str) -> str:
    if "=" not in raw_value:
        raise DockerRunError(f"{option_name} values must use KEY=VALUE format")
    key = raw_value.split("=", 1)[0].strip()
    if not key:
        raise DockerRunError(f"{option_name} key cannot be empty")
    return key


def required_host_env_names(args: argparse.Namespace) -> tuple[str, ...]:
    names = [args.api_key_env, args.auth_token_env, args.oauth_token_env]
    return tuple(dict.fromkeys(name for name in names if name))


def validate_host_env(names: tuple[str, ...]) -> None:
    missing = [name for name in names if name not in os.environ]
    if missing:
        raise DockerRunError(
            "Required host environment variables are unset: " + ", ".join(missing)
        )


def validate_agent_values(args: argparse.Namespace) -> None:
    for value in args.env:
        parse_key_value_key(value, option_name="--env")
    # Checked here as well as in the in-container runner so a bad key fails the
    # run before staging and the image build.
    for value in args.prompt_var:
        key = parse_key_value_key(value, option_name="--prompt-var")
        if key in RESERVED_PROMPT_VARS:
            raise DockerRunError(
                f"--prompt-var key '{key}' is reserved and cannot be overridden"
            )
    if getattr(args, "inject_rest_assured", False) and getattr(args, "workload", "java") != "java":
        raise DockerRunError(
            "--inject-rest-assured applies only to --workload java; it injects a "
            "dependency into a Maven POM, which is not applicable to JavaScript projects"
        )


def validate_agent_options(args: argparse.Namespace) -> None:
    """Reject agent-specific options supplied for an agent that ignores them, so a
    flag like --max-budget-usd is never accepted then silently dropped. The parser
    leaves agent-specific options unset (None) until resolve_agent_defaults fills
    them, so "is not None" means the user supplied it -- even at the default value."""
    options_by_owner: dict[str, dict[str, bool]] = {
        "claude-code": {
            "--permission-mode": args.permission_mode is not None,
            "--auth-token-env": args.auth_token_env is not None,
            "--oauth-token-env": args.oauth_token_env is not None,
            "--max-budget-usd": args.max_budget_usd is not None,
            "--small-model": args.small_model is not None,
            "--effort": args.effort is not None,
            "--extra-arg": bool(args.extra_arg),
        },
        "codex": {
            "--sandbox": getattr(args, "sandbox", None) is not None,
        },
    }
    unsupported = sorted(
        flag
        for owner, flags in options_by_owner.items()
        if owner != args.agent
        for flag, supplied in flags.items()
        if supplied
    )
    if unsupported:
        raise DockerRunError(
            f"--agent {args.agent} does not support these options (they apply to a "
            f"different agent): {', '.join(unsupported)}"
        )


def resolve_agent_defaults(args: argparse.Namespace) -> None:
    """Fill effective defaults for options the parser left unset. Runs after
    validate_agent_options, which relies on unset (None) meaning "not supplied"."""
    if args.model is None:
        if args.agent == "codex":
            raise DockerRunError("--model is required for the codex agent")
        args.model = "sonnet"
    if args.permission_mode is None:
        args.permission_mode = DEFAULT_PERMISSION_MODE
    if args.effort is None:
        args.effort = DEFAULT_EFFORT
    if args.sandbox is None:
        args.sandbox = DEFAULT_SANDBOX


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a general coding agent against a staged project in Docker."
    )
    parser.add_argument(
        "--agent",
        choices=sorted(AGENT_SPECS),
        default="claude-code",
        help="Agent spec to run inside the shared Docker runtime.",
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        type=Path,
        help="Project directory to stage into the container.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help=(
            "Parent directory for run outputs. A unique "
            f"<timestamp>{RUN_ID_DELIMITER}<agent>{RUN_ID_DELIMITER}<project> "
            "run directory is created inside it."
        ),
    )
    parser.add_argument(
        "--service",
        help=(
            "Service id to build, start, and health-gate in the container "
            "before the agent runs. Requires --service-scripts-dir and a "
            "services.json manifest. "
            "The agent receives its base URL via the prompt and SERVICE_BASE_URL."
        ),
    )
    parser.add_argument(
        "--service-manifest",
        type=Path,
        help=(
            "Path to a services.json manifest. If omitted with --service, "
            "--service-scripts-dir/services.json is used."
        ),
    )
    parser.add_argument(
        "--service-scripts-dir",
        type=Path,
        help=(
            "Path to the service scripts directory containing run-with-service.sh. "
            "Required with --service so the directory can be mounted into Docker."
        ),
    )
    parser.add_argument(
        "--service-port",
        type=positive_int,
        help="HTTP port override for --service (default: the service's default port).",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Run the existing default stack image without (re)building it first.",
    )
    parser.add_argument(
        "--image",
        help=(
            "Docker image to run. With --dockerfile it is the tag for the built "
            "image; alone it names a pre-built image and skips the build. Without "
            "either flag, the composed default stack image is built and run."
        ),
    )
    parser.add_argument(
        "--dockerfile",
        type=Path,
        help=(
            "Custom single Dockerfile to build the runtime image from (build "
            "context is its directory), bypassing the composed default stack "
            "(docker/Dockerfile.base + agent + java [+ genome-nexus]). "
            "Conflicts with --skip-build."
        ),
    )
    parser.add_argument(
        "--network",
        default="bridge",
        help="Docker network mode. Use none only for non-networked smoke runs.",
    )
    parser.add_argument(
        "--memory",
        default="4g",
        help="Docker memory limit, or an empty string for Docker's default.",
    )
    parser.add_argument(
        "--cpus",
        type=positive_float,
        help="Docker CPU quota.",
    )
    parser.add_argument(
        "--pids-limit",
        type=positive_int,
        default=512,
        help="Docker process limit.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help=(
            "Model value passed through to the selected agent. Defaults to "
            "'sonnet' for claude-code; required for the codex agent."
        ),
    )
    parser.add_argument(
        "--small-model",
        default=None,
        help=(
            "Override Claude Code's small/fast model via ANTHROPIC_SMALL_FAST_MODEL "
            "(claude-code agent only). This model only handles auxiliary background "
            "work (conversation titles, summaries, topic detection), never the main "
            "loop or subagents, and defaults to Haiku 4.5 when unset. Rejected for "
            "codex."
        ),
    )
    parser.add_argument(
        "--sandbox",
        choices=("read_only", "workspace_write", "full_access"),
        default=None,
        help=(
            "Codex sandbox mode (codex agent only). Defaults to full_access because "
            "the Docker container is the security boundary; lower to workspace_write "
            "or read_only for stricter runs. Rejected for claude-code."
        ),
    )
    parser.add_argument(
        "--permission-mode",
        choices=PERMISSION_MODES,
        default=None,
        help=(
            "Claude Code permission mode (claude-code agent only). Defaults to "
            "bypassPermissions. Rejected for codex."
        ),
    )
    parser.add_argument(
        "--effort",
        choices=EFFORT_LEVELS,
        default=None,
        help=(
            "Reasoning effort, forwarded natively to Claude Code as --effort to "
            "guide adaptive thinking depth (claude-code agent only at the moment). "
            "xhigh applies to Opus 4.7 only and falls back to high elsewhere. "
            "Defaults to high. Rejected for codex."
        ),
    )
    parser.add_argument(
        "--system-template",
        type=Path,
        help=(
            "Custom Jinja2 system prompt template (both agents), mounted read-only "
            "into the container. Its directory is mounted, so includes of sibling "
            "templates resolve. Defaults to the packaged template."
        ),
    )
    parser.add_argument(
        "--user-template",
        type=Path,
        help=(
            "Custom Jinja2 user prompt template (both agents), mounted "
            "read-only into the container. Its directory is mounted, so includes "
            "of sibling templates resolve. Defaults to the packaged template."
        ),
    )
    parser.add_argument(
        "--prompt-var",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help=(
            "Extra variable injected into the prompt templates (both agents). "
            "Reserved template keys and service-derived keys are rejected. "
            "Can be repeated."
        ),
    )
    parser.add_argument(
        "--system-prompt-config",
        choices=("append", "replace", "none"),
        default="replace",
        help=(
            "How the selected agent applies its rendered system template (both "
            "agents). replace makes it the entire system prompt (errors if it "
            "renders empty), append adds it as supplemental instructions, none "
            "omits it. Defaults to replace."
        ),
    )
    parser.add_argument(
        "--base-url",
        help=(
            "Custom OpenAI/Anthropic-compatible gateway endpoint for the selected "
            "agent (claude-code sets ANTHROPIC_BASE_URL; codex registers a model "
            "provider pointed at it)."
        ),
    )
    parser.add_argument(
        "--api-key-env",
        help=(
            "Host env var passed into Docker and used as the agent's API key "
            "(ANTHROPIC_API_KEY for claude-code, OPENAI_API_KEY for codex)."
        ),
    )
    parser.add_argument(
        "--auth-token-env",
        help=(
            "Host env var passed into Docker and used as ANTHROPIC_AUTH_TOKEN "
            "(claude-code agent only)."
        ),
    )
    parser.add_argument(
        "--oauth-token-env",
        help="Host env var containing a Claude Code OAuth token (claude-code agent only).",
    )
    parser.add_argument(
        "--env",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help=(
            "Additional environment variable for the selected agent's process "
            "(both agents). Can be repeated."
        ),
    )
    parser.add_argument(
        "--extra-arg",
        action="append",
        default=[],
        metavar="FLAG[=VALUE]",
        help=(
            "Extra passthrough argument forwarded verbatim to the claude-code agent "
            "(claude-code agent only). Can be repeated."
        ),
    )
    parser.add_argument(
        "--max-turns",
        type=positive_int,
        help=(
            "Maximum agentic turns before the agent exits. Enforced by claude-code; "
            "codex runs a single turn per invocation."
        ),
    )
    parser.add_argument(
        "--max-budget-usd",
        type=positive_float,
        help=(
            "Maximum dollar budget before the agent exits (claude-code agent only; "
            "codex does not enforce a budget)."
        ),
    )
    parser.add_argument(
        "--reset-git",
        action="store_true",
        help=(
            "Reset staged Git state before Docker preprocessing. This runs "
            "before --clear-tests and is not forwarded to the agent."
        ),
    )
    parser.add_argument(
        "--clear-tests",
        action="store_true",
        help=(
            "Remove Java test directories/files before the agent runs; strongly "
            "recommended for isolated test construction analysis."
        ),
    )
    parser.add_argument(
        "--inject-rest-assured",
        action="store_true",
        help=(
            "Inject RestAssured as a test dependency before the agent runs, using "
            "the matched service's rest_assured config from the manifest. Requires "
            "--service and --workload java. Runs after --clear-tests; the POM edit "
            "lands in the testless baseline, so it stays out of the agent's diff."
        ),
    )
    parser.add_argument(
        "--workload",
        choices=("java", "javascript"),
        default="java",
        help=(
            "Target workload ecosystem. Selects the Docker workload layer "
            "(Dockerfile.java or Dockerfile.javascript) and the default prompt "
            "templates. Defaults to java. Agent-agnostic."
        ),
    )
    return parser
