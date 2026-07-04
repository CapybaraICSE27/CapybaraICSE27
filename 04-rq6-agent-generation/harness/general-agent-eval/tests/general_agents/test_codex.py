from __future__ import annotations

import json
from pathlib import Path

import pytest

from general_agent_eval.general_agents import codex
from general_agent_eval.general_agents.agent_specs import (
    AGENT_SPECS,
    AgentRunRequest,
    build_codex_command,
)
from general_agent_eval.general_agents.codex import (
    HarnessError,
    build_parser,
    build_system_prompt,
)
from general_agent_eval.orchestration import cli, manifest
from general_agent_eval.orchestration.errors import DockerRunError

RENDERED = "You are a test generation agent.\n"


# --- system-prompt-config mapping --------------------------------------------


def test_replace_returns_base_instructions() -> None:
    assert build_system_prompt("replace", RENDERED) == {
        "base_instructions": RENDERED.strip()
    }


def test_replace_errors_when_rendered_prompt_is_empty() -> None:
    with pytest.raises(HarnessError):
        build_system_prompt("replace", "   \n  ")


def test_append_returns_developer_instructions() -> None:
    assert build_system_prompt("append", RENDERED) == {
        "developer_instructions": RENDERED
    }


def test_append_empty_returns_empty_dict() -> None:
    assert build_system_prompt("append", "   ") == {}


def test_none_returns_empty_dict() -> None:
    assert build_system_prompt("none", RENDERED) == {}


# --- parser -------------------------------------------------------------------


def test_model_is_required() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--input-dir", "."])


def test_parser_defaults() -> None:
    args = build_parser().parse_args(["--input-dir", ".", "--model", "gpt-5-codex"])
    # The standalone runner executes on the host, so it defaults to the safer mode.
    assert args.sandbox == "workspace_write"
    assert args.system_prompt_config == "replace"


@pytest.mark.parametrize(
    "flag",
    ["--permission-mode", "--oauth-token-env", "--max-budget-usd", "--custom-header"],
)
def test_parser_rejects_claude_only_flags(flag: str) -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--input-dir", ".", "--model", "m", flag, "x"])


# --- gateway config overrides (SDK-free) -------------------------------------


def test_config_overrides_with_base_url() -> None:
    args = build_parser().parse_args(
        ["--input-dir", ".", "--model", "m", "--base-url", "http://gw:4000"]
    )
    overrides = codex.build_codex_config_overrides(args)
    assert f"model_provider={codex.GATEWAY_PROVIDER_ID}" in overrides
    assert any("base_url=http://gw:4000" in override for override in overrides)


def test_config_overrides_empty_without_base_url() -> None:
    args = build_parser().parse_args(["--input-dir", ".", "--model", "m"])
    assert codex.build_codex_config_overrides(args) == ()


# --- result record ------------------------------------------------------------


class _Status:
    def __init__(self, value: str) -> None:
        self.value = value


class _Turn:
    def __init__(self, status: str, duration_ms: int) -> None:
        self.status = _Status(status)
        self.duration_ms = duration_ms
        self.error = None


class _Usage:
    def model_dump(self, mode: str = "json") -> dict[str, object]:
        return {"total": {"input_tokens": 10, "output_tokens": 5}}


def test_synthesize_result_record_success_is_detected_by_orchestration() -> None:
    record = codex.synthesize_result_record(
        _Turn("completed", 1234), _Usage(), final_response="done"
    )
    assert record["duration_ms"] == 1234
    assert record["total_cost_usd"] is None
    assert record["is_error"] is False
    assert record["status"] == "completed"
    assert record["usage"] == {"total": {"input_tokens": 10, "output_tokens": 5}}
    assert record["result"] == "done"
    # Cross-module guarantee: the orchestration summary must recognize this as the
    # result message.
    assert manifest.is_agent_result_message(record) is True


def test_synthesize_result_record_failure_marks_error() -> None:
    record = codex.synthesize_result_record(
        _Turn("failed", 7), None, final_response=None
    )
    assert record["is_error"] is True
    assert record["usage"] is None


# --- build_codex_command ------------------------------------------------------


def _request(**overrides: object) -> AgentRunRequest:
    base: dict[str, object] = dict(
        container_input_dir="/workspace/input",
        container_output_dir="/workspace/output",
        model="gpt-5-codex",
        permission_mode="bypassPermissions",
        system_prompt_config="replace",
    )
    base.update(overrides)
    return AgentRunRequest(**base)  # type: ignore[arg-type]


def test_codex_registered_in_agent_specs() -> None:
    assert AGENT_SPECS["codex"].build_command is build_codex_command


def test_build_codex_command_uses_packaged_module() -> None:
    command = build_codex_command(_request())
    assert command[:3] == ["python", "-m", "general_agent_eval.general_agents.codex"]


def test_build_codex_command_forwards_shared_flags_and_omits_claude_flags() -> None:
    command = build_codex_command(
        _request(
            base_url="http://gw",
            api_key_env="OPENAI_API_KEY",
            sandbox="workspace_write",
        )
    )
    for flag in (
        "--model",
        "--system-prompt-config",
        "--sandbox",
        "--output-jsonl",
        "--base-url",
        "--api-key-env",
    ):
        assert flag in command
    assert "--permission-mode" not in command
    assert "--oauth-token-env" not in command
    assert "--effort" not in command
    assert command[command.index("--sandbox") + 1] == "workspace_write"


# --- orchestration wiring -----------------------------------------------------


def test_docker_parser_registers_codex_and_defaults_model_none() -> None:
    args = cli.build_parser().parse_args(
        ["--input-dir", "/tmp/p", "--agent", "codex"]
    )
    assert args.agent == "codex"
    assert args.model is None
    # Agent-specific options stay unset until resolve_agent_defaults fills them.
    assert args.sandbox is None


def test_resolve_agent_defaults_fills_codex_sandbox_full_access() -> None:
    args = cli.build_parser().parse_args(
        ["--input-dir", "/tmp/p", "--agent", "codex", "--model", "m"]
    )
    cli.resolve_agent_defaults(args)
    # Under Docker the container is the boundary, so it defaults to full_access.
    assert args.sandbox == "full_access"


def test_resolve_agent_defaults_fills_claude_effort_high() -> None:
    args = cli.build_parser().parse_args(["--input-dir", "/tmp/p"])
    # Agent-specific options stay unset until resolve_agent_defaults fills them.
    assert args.effort is None
    cli.resolve_agent_defaults(args)
    assert args.effort == "high"


def test_resolve_agent_defaults_requires_model_for_codex() -> None:
    args = cli.build_parser().parse_args(
        ["--input-dir", "/tmp/p", "--agent", "codex"]
    )
    with pytest.raises(DockerRunError, match="--model is required"):
        cli.resolve_agent_defaults(args)


# --- agent-specific option guards --------------------------------------------


def _docker_args(*extra: str) -> object:
    return cli.build_parser().parse_args(["--input-dir", "/tmp/p", *extra])


@pytest.mark.parametrize(
    "extra",
    [
        ["--max-budget-usd", "5"],
        ["--permission-mode", "plan"],
        ["--auth-token-env", "ANTHROPIC_AUTH_TOKEN"],
        ["--oauth-token-env", "CLAUDE_CODE_OAUTH_TOKEN"],
        ["--small-model", "haiku"],
        ["--effort", "high"],
        ["--extra-arg=--foo"],
    ],
)
def test_validate_rejects_claude_only_options_for_codex(extra: list[str]) -> None:
    args = _docker_args("--agent", "codex", "--model", "m", *extra)
    with pytest.raises(DockerRunError):
        cli.validate_agent_options(args)


def test_validate_rejects_sandbox_for_claude_code() -> None:
    args = _docker_args("--agent", "claude-code", "--sandbox", "read_only")
    with pytest.raises(DockerRunError):
        cli.validate_agent_options(args)


def test_validate_allows_supported_options_per_agent() -> None:
    codex = _docker_args("--agent", "codex", "--model", "m", "--sandbox", "read_only")
    claude = _docker_args(
        "--max-budget-usd", "5", "--permission-mode", "plan", "--effort", "max"
    )
    # Neither raises: each option is supported by the agent it was passed to.
    cli.validate_agent_options(codex)
    cli.validate_agent_options(claude)


def test_validate_rejects_explicit_default_sandbox_for_claude_code() -> None:
    # Even the default value, explicitly supplied, is rejected: --sandbox is detected
    # by presence (parser default is None), so the help's "Rejected for claude-code"
    # holds without the default-valued escape hatch.
    args = _docker_args("--agent", "claude-code", "--sandbox", "full_access")
    with pytest.raises(DockerRunError):
        cli.validate_agent_options(args)


def test_collect_summary_no_cost_note_for_null_codex_cost(tmp_path: Path) -> None:
    jsonl = tmp_path / "messages.jsonl"
    jsonl.write_text(
        json.dumps({"duration_ms": 123, "total_cost_usd": None, "status": "completed"})
        + "\n",
        encoding="utf-8",
    )
    summary = manifest.collect_agent_result_summary(
        tmp_path, "messages.jsonl", cost_is_estimate=True
    )
    assert summary is not None
    assert summary["available"] is True
    assert summary["duration_ms"] == 123
    assert summary["total_cost_usd"] is None
    assert summary["status"] == "completed"
    assert "total_cost_usd_note" not in summary
