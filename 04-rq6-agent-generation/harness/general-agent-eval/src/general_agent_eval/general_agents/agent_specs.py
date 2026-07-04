from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class AgentRunRequest:
    container_input_dir: str
    container_output_dir: str
    model: str
    permission_mode: str
    system_prompt_config: str
    base_url: str | None = None
    # Claude Code small/fast model override; ignored by the codex agent.
    small_model: str | None = None
    # Claude Code reasoning effort; ignored by the codex agent.
    effort: str = "high"
    api_key_env: str | None = None
    auth_token_env: str | None = None
    oauth_token_env: str | None = None
    max_turns: int | None = None
    max_budget_usd: float | None = None
    reset_git: bool = False
    agent_env: tuple[str, ...] = ()
    prompt_vars: tuple[str, ...] = ()
    extra_args: tuple[str, ...] = ()
    # Container paths of custom prompt templates; None lets the in-container
    # agent select the packaged default for the chosen workload.
    system_template: str | None = None
    user_template: str | None = None
    # Codex sandbox mode; ignored by the claude-code agent.
    sandbox: str = "full_access"
    # Target workload ecosystem; controls default prompt templates.
    workload: str = "java"


@dataclass(frozen=True)
class AgentSpec:
    name: str
    description: str
    output_jsonl_name: str | None
    build_command: Callable[[AgentRunRequest], list[str]] = field(repr=False)


def _append_optional(command: list[str], option: str, value: object | None) -> None:
    if value is not None:
        command.extend([option, str(value)])


def _append_repeated(command: list[str], option: str, values: tuple[str, ...]) -> None:
    for value in values:
        command.extend([option, value])


def build_claude_code_command(request: AgentRunRequest) -> list[str]:
    command = [
        "python",
        "-m",
        "general_agent_eval.general_agents.claude_code",
        "--input-dir",
        request.container_input_dir,
        "--model",
        request.model,
        "--permission-mode",
        request.permission_mode,
        "--effort",
        request.effort,
        "--system-prompt-config",
        request.system_prompt_config,
        "--output-jsonl",
        f"{request.container_output_dir}/messages.jsonl",
    ]
    _append_optional(command, "--system-template", request.system_template)
    _append_optional(command, "--user-template", request.user_template)
    _append_optional(command, "--small-model", request.small_model)
    _append_optional(command, "--base-url", request.base_url)
    _append_optional(command, "--api-key-env", request.api_key_env)
    _append_optional(command, "--auth-token-env", request.auth_token_env)
    _append_optional(command, "--oauth-token-env", request.oauth_token_env)
    _append_optional(command, "--max-turns", request.max_turns)
    _append_optional(command, "--max-budget-usd", request.max_budget_usd)
    command.extend(["--workload", request.workload])
    _append_repeated(command, "--env", request.agent_env)
    _append_repeated(command, "--prompt-var", request.prompt_vars)
    _append_repeated(command, "--extra-arg", request.extra_args)
    if request.reset_git:
        command.append("--reset-git")
    return command


def build_codex_command(request: AgentRunRequest) -> list[str]:
    command = [
        "python",
        "-m",
        "general_agent_eval.general_agents.codex",
        "--input-dir",
        request.container_input_dir,
        "--model",
        request.model,
        "--system-prompt-config",
        request.system_prompt_config,
        "--sandbox",
        request.sandbox,
        "--output-jsonl",
        f"{request.container_output_dir}/messages.jsonl",
    ]
    _append_optional(command, "--system-template", request.system_template)
    _append_optional(command, "--user-template", request.user_template)
    _append_optional(command, "--base-url", request.base_url)
    _append_optional(command, "--api-key-env", request.api_key_env)
    _append_optional(command, "--max-turns", request.max_turns)
    command.extend(["--workload", request.workload])
    _append_repeated(command, "--env", request.agent_env)
    _append_repeated(command, "--prompt-var", request.prompt_vars)
    if request.reset_git:
        command.append("--reset-git")
    return command


AGENT_SPECS: dict[str, AgentSpec] = {
    "claude-code": AgentSpec(
        name="claude-code",
        description="Run Claude Code through the experiment SDK harness.",
        output_jsonl_name="messages.jsonl",
        build_command=build_claude_code_command,
    ),
    "codex": AgentSpec(
        name="codex",
        description="Run OpenAI Codex through the experiment SDK harness.",
        output_jsonl_name="messages.jsonl",
        build_command=build_codex_command,
    ),
}
