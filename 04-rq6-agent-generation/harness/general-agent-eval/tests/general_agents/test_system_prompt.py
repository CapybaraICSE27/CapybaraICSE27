from __future__ import annotations

import pytest

from general_agent_eval.general_agents import claude_code
from general_agent_eval.general_agents.claude_code import (
    HarnessError,
    build_parser,
    build_system_prompt,
)

RENDERED = "You are a test generation agent.\n"


def test_replace_returns_rendered_prompt_as_entire_system_prompt() -> None:
    result = build_system_prompt("replace", RENDERED)
    assert result == RENDERED.strip()


def test_replace_errors_when_rendered_prompt_is_empty() -> None:
    with pytest.raises(HarnessError):
        build_system_prompt("replace", "   \n  ")


def test_append_wraps_rendered_prompt_in_preset() -> None:
    result = build_system_prompt("append", RENDERED)
    assert result == {
        "type": "preset",
        "preset": "claude_code",
        "append": RENDERED,
    }


def test_append_falls_back_to_preset_when_empty() -> None:
    assert build_system_prompt("append", "  ") == {
        "type": "preset",
        "preset": "claude_code",
    }


def test_none_ignores_rendered_prompt() -> None:
    assert build_system_prompt("none", RENDERED) == {
        "type": "preset",
        "preset": "claude_code",
    }


def test_default_system_prompt_config_is_replace() -> None:
    args = build_parser().parse_args(["--input-dir", "."])
    assert args.system_prompt_config == "replace"
    assert claude_code.build_system_prompt is build_system_prompt


# ---------------------------------------------------------------------------
# JavaScript UI prompt templates
# ---------------------------------------------------------------------------

def _js_context(tmp_path: object, *, service_base_url: str = "") -> dict:
    return claude_code.build_template_context(
        input_dir=claude_code.PROJECT_ROOT,
        model="sonnet",
        prompt_vars={"service_base_url": service_base_url} if service_base_url else None,
    )


def test_js_system_template_renders_without_error() -> None:
    rendered = claude_code.render_template(
        claude_code.DEFAULT_SYSTEM_TEMPLATE_JS_UI,
        _js_context(None),
    )
    assert "Playwright" in rendered or "E2E" in rendered or "frontend" in rendered


def test_js_user_template_renders_with_service_base_url() -> None:
    rendered = claude_code.render_template(
        claude_code.DEFAULT_USER_TEMPLATE_JS_UI,
        _js_context(None, service_base_url="http://localhost:5173"),
    )
    assert "http://localhost:5173" in rendered


def test_js_user_template_renders_without_service_base_url() -> None:
    rendered = claude_code.render_template(
        claude_code.DEFAULT_USER_TEMPLATE_JS_UI,
        _js_context(None),
    )
    # The template has an else branch that does not require a URL.
    assert rendered  # non-empty
    assert "http://localhost:5173" not in rendered or "already running" not in rendered
