from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import pytest

from general_agent_eval.general_agents import claude_code
from general_agent_eval.general_agents.agent_specs import build_claude_code_command
from general_agent_eval.orchestration import cli, docker, services
from general_agent_eval.orchestration.errors import DockerRunError
from general_agent_eval.orchestration.manifest import (
    COST_ESTIMATE_NOTE,
    collect_agent_result_summary,
    sanitized_manifest,
)
from general_agent_eval.orchestration.run import build_agent_request


def write_service_manifest(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "services": {
                    "features-service": {
                        "description": "Feature service",
                        "repo_subdir": "features-service",
                        "java_version": 8,
                        "build": ["mvn -B -DskipTests clean package"],
                        "run": "java -jar app.jar",
                        "default_port": 8080,
                        "base_path": "/",
                        "health_path": "/products",
                    },
                    "genome-nexus": {
                        "description": "Genome Nexus",
                        "repo_subdir": "genome-nexus",
                        "java_version": 8,
                        "build": ["mvn -B -DskipTests clean install"],
                        "run": "java -jar web.war",
                        "default_port": 8888,
                        "base_path": "/",
                        "health_path": "/actuator/health",
                    },
                    "restcountries": {
                        "description": "REST Countries",
                        "repo_subdir": "restcountries",
                        "java_version": 8,
                        "build": ["mvn -B -DskipTests clean package"],
                        "run": "mvn jetty:run",
                        "default_port": 8080,
                        "base_path": "/rest",
                        "health_path": "/rest/v2/all",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def write_service_scripts(path: Path) -> Path:
    path.mkdir()
    (path / "run-with-service.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    return path


def docker_args(**overrides: object) -> argparse.Namespace:
    base: dict[str, object] = dict(
        service=None,
        service_manifest=None,
        service_scripts_dir=None,
        service_port=None,
        env=[],
        extra_arg=[],
        model="sonnet",
        permission_mode="auto",
        system_prompt_config="append",
        base_url=None,
        api_key_env=None,
        auth_token_env=None,
        oauth_token_env=None,
        max_turns=None,
        max_budget_usd=None,
        reset_git=False,
        inject_rest_assured=False,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def test_permission_mode_defaults_to_bypass_permissions() -> None:
    claude_args = claude_code.build_parser().parse_args(["--input-dir", "/tmp/p"])
    docker_args = cli.build_parser().parse_args(["--input-dir", "/tmp/p"])
    # The orchestration parser leaves it unset until resolution so explicit
    # provision is detectable.
    assert docker_args.permission_mode is None
    cli.resolve_agent_defaults(docker_args)

    assert claude_args.permission_mode == "bypassPermissions"
    assert docker_args.permission_mode == "bypassPermissions"


# --- claude_code --prompt-var -------------------------------------------------


def test_parse_prompt_vars_parses_pairs() -> None:
    assert claude_code.parse_prompt_vars(["a=1", "b=x=y"]) == {"a": "1", "b": "x=y"}


@pytest.mark.parametrize("key", sorted(claude_code.RESERVED_PROMPT_VARS))
def test_parse_prompt_vars_rejects_reserved_keys(key: str) -> None:
    with pytest.raises(claude_code.HarnessError, match="reserved"):
        claude_code.parse_prompt_vars([f"{key}=value"])


def test_parse_prompt_vars_requires_equals() -> None:
    with pytest.raises(claude_code.HarnessError, match="KEY=VALUE"):
        claude_code.parse_prompt_vars(["novalue"])


def test_build_template_context_seeds_service_defaults_and_merges() -> None:
    ctx = claude_code.build_template_context(
        input_dir=Path("/tmp/x"),
        model="sonnet",
        prompt_vars={"service_base_url": "http://127.0.0.1:8888/"},
    )
    assert ctx["service_base_url"] == "http://127.0.0.1:8888/"
    # Unset service keys default to empty so templates can guard them under StrictUndefined.
    assert ctx["service_id"] == ""
    assert ctx["model"] == "sonnet"


def test_claude_code_parser_accepts_repeated_prompt_var() -> None:
    parser = claude_code.build_parser()
    args = parser.parse_args(
        ["--input-dir", "/tmp/p", "--prompt-var", "a=1", "--prompt-var", "b=2"]
    )
    assert args.prompt_var == ["a=1", "b=2"]


def test_templates_render_with_and_without_service() -> None:
    def render(name: str, prompt_vars: dict[str, str]) -> str:
        ctx = claude_code.build_template_context(
            input_dir=Path("/tmp/x"), model="sonnet", prompt_vars=prompt_vars
        )
        return claude_code.render_template(claude_code.PROMPTS_DIR / name, ctx)

    svc = {"service_base_url": "http://127.0.0.1:8888/"}
    # The user prompt carries the live-service block; the system prompt does not.
    without = render("user_prompt_js_ui.jinja2", {})
    assert "already running" not in without
    assert "No running instance" in without
    with_service = render("user_prompt_js_ui.jinja2", svc)
    assert "http://127.0.0.1:8888/" in with_service
    assert "already running" in with_service

    assert "already running" not in render("system_prompt_js_ui.jinja2", svc)


# --- orchestration service resolution ----------------------------------------


def test_resolve_service_returns_none_without_service() -> None:
    assert services.resolve_service(docker_args()) is None


def test_resolve_service_port_requires_service() -> None:
    with pytest.raises(DockerRunError, match="requires --service"):
        services.resolve_service(docker_args(service_port=9000))


def test_resolve_service_requires_manifest_or_scripts_dir() -> None:
    with pytest.raises(DockerRunError, match="service-manifest"):
        services.resolve_service(docker_args(service="genome-nexus"))


def test_resolve_service_unknown_id(tmp_path: Path) -> None:
    manifest = write_service_manifest(tmp_path / "services.json")

    with pytest.raises(DockerRunError, match="unknown --service"):
        services.resolve_service(
            docker_args(service="does-not-exist", service_manifest=manifest)
        )


def test_resolve_service_genome_nexus_urls(tmp_path: Path) -> None:
    manifest = write_service_manifest(tmp_path / "services.json")

    svc = services.resolve_service(
        docker_args(service="genome-nexus", service_manifest=manifest)
    )
    assert svc == {
        "id": "genome-nexus",
        "port": 8888,
        "base_url": "http://127.0.0.1:8888/",
    }


def test_resolve_service_uses_scripts_dir_manifest_by_default(tmp_path: Path) -> None:
    scripts_dir = write_service_scripts(tmp_path / "scripts")
    write_service_manifest(scripts_dir / "services.json")

    svc = services.resolve_service(
        docker_args(service="restcountries", service_scripts_dir=scripts_dir)
    )
    assert svc is not None
    assert svc["base_url"] == "http://127.0.0.1:8080/rest"


def test_resolve_service_port_override(tmp_path: Path) -> None:
    manifest = write_service_manifest(tmp_path / "services.json")

    svc = services.resolve_service(
        docker_args(
            service="genome-nexus", service_manifest=manifest, service_port=9999
        )
    )
    assert svc is not None
    assert svc["port"] == 9999
    assert svc["base_url"] == "http://127.0.0.1:9999/"


def test_build_agent_request_injects_service_env_and_prompt_vars(
    tmp_path: Path,
) -> None:
    manifest = write_service_manifest(tmp_path / "services.json")
    svc = services.resolve_service(
        docker_args(service="genome-nexus", service_manifest=manifest)
    )
    request = build_agent_request(
        docker_args(service="genome-nexus", env=["FOO=bar"]), svc
    )
    assert "FOO=bar" in request.agent_env
    assert "SERVICE_BASE_URL=http://127.0.0.1:8888/" in request.agent_env
    assert "service_id=genome-nexus" in request.prompt_vars
    assert "service_base_url=http://127.0.0.1:8888/" in request.prompt_vars


def test_build_agent_request_no_service_has_empty_prompt_vars() -> None:
    request = build_agent_request(docker_args(), None)
    assert request.prompt_vars == ()
    assert all(not e.startswith("SERVICE_BASE_URL=") for e in request.agent_env)


def _service_with_rest_assured(service_id: str, base_url: str, target_pom: str) -> dict:
    return {
        "id": service_id,
        "base_url": base_url,
        "rest_assured": {
            "target_pom": target_pom,
            "group_id": "io.rest-assured",
            "artifact_id": "rest-assured",
            "version": None,
            "scope": "test",
        },
    }


def test_rest_assured_prompt_vars_absent_without_inject_flag() -> None:
    service = _service_with_rest_assured(
        "genome-nexus", "http://127.0.0.1:8888/", "web/pom.xml"
    )
    request = build_agent_request(
        docker_args(service="genome-nexus", inject_rest_assured=False), service
    )
    assert all(not v.startswith("rest_assured=") for v in request.prompt_vars)
    assert all(not v.startswith("test_module=") for v in request.prompt_vars)


def test_user_prompt_vars_append_after_service_vars(tmp_path: Path) -> None:
    manifest = write_service_manifest(tmp_path / "services.json")
    svc = services.resolve_service(
        docker_args(service="genome-nexus", service_manifest=manifest)
    )
    request = build_agent_request(
        docker_args(service="genome-nexus", prompt_var=["task=summarize"]), svc
    )
    assert request.prompt_vars[-1] == "task=summarize"
    assert "service_id=genome-nexus" in request.prompt_vars


def test_prompt_vars_colliding_with_service_vars_are_rejected(tmp_path: Path) -> None:
    manifest = write_service_manifest(tmp_path / "services.json")
    svc = services.resolve_service(
        docker_args(service="genome-nexus", service_manifest=manifest)
    )
    with pytest.raises(DockerRunError, match="service_base_url"):
        build_agent_request(
            docker_args(
                service="genome-nexus",
                prompt_var=["service_base_url=http://example.invalid/"],
            ),
            svc,
        )


def test_claude_code_command_emits_prompt_vars(tmp_path: Path) -> None:
    manifest = write_service_manifest(tmp_path / "services.json")
    svc = services.resolve_service(
        docker_args(service="genome-nexus", service_manifest=manifest)
    )
    command = build_claude_code_command(
        build_agent_request(docker_args(service="genome-nexus"), svc)
    )
    assert command.count("--prompt-var") == 2
    idx = command.index("--prompt-var")
    assert command[idx + 1] == "service_id=genome-nexus"


def _docker_command_args(**overrides: object) -> argparse.Namespace:
    return docker_args(
        network="bridge", memory="4g", cpus=None, pids_limit=512, **overrides
    )


def test_build_docker_command_wraps_with_service_shim(tmp_path: Path) -> None:
    manifest = write_service_manifest(tmp_path / "services.json")
    scripts_dir = write_service_scripts(tmp_path / "scripts")
    svc = services.resolve_service(
        docker_args(service="genome-nexus", service_manifest=manifest)
    )
    command = docker.build_docker_command(
        args=_docker_command_args(service="genome-nexus"),
        staged_input=Path("/tmp/in"),
        output_dir=Path("/tmp/out"),
        agent_command=["python", "-m", "agent"],
        host_env_names=(),
        service=svc,
        service_scripts_dir=scripts_dir,
    )
    image_idx = command.index(docker.DEFAULT_IMAGE)
    assert f"{scripts_dir}:{docker.CONTAINER_SERVICE_SCRIPTS_DIR}:ro" in command
    assert command[image_idx + 1] == "bash"
    assert command[image_idx + 2].endswith("run-with-service.sh")
    assert command[image_idx + 3] == "genome-nexus"
    assert "--repo" in command and docker.CONTAINER_INPUT_DIR in command
    # the agent command follows the `--` separator
    sep = command.index("--", image_idx)
    assert command[sep + 1 :] == ["python", "-m", "agent"]


def test_build_docker_command_requires_service_scripts_dir(tmp_path: Path) -> None:
    manifest = write_service_manifest(tmp_path / "services.json")
    svc = services.resolve_service(
        docker_args(service="genome-nexus", service_manifest=manifest)
    )

    with pytest.raises(DockerRunError, match="service_scripts_dir"):
        docker.build_docker_command(
            args=_docker_command_args(service="genome-nexus"),
            staged_input=Path("/tmp/in"),
            output_dir=Path("/tmp/out"),
            agent_command=["python", "-m", "agent"],
            host_env_names=(),
            service=svc,
        )


def test_build_docker_command_no_service_appends_agent_directly() -> None:
    command = docker.build_docker_command(
        args=_docker_command_args(),
        staged_input=Path("/tmp/in"),
        output_dir=Path("/tmp/out"),
        agent_command=["python", "-m", "agent"],
        host_env_names=(),
        service=None,
    )
    image_idx = command.index(docker.DEFAULT_IMAGE)
    assert command[image_idx + 1 :] == ["python", "-m", "agent"]
    assert "run-with-service.sh" not in " ".join(command)


def test_build_docker_command_mounts_templates_and_custom_image(
    tmp_path: Path,
) -> None:
    system = tmp_path / "system.jinja2"
    system.write_text("system prompt", encoding="utf-8")
    mounts = docker.resolve_template_mounts(
        argparse.Namespace(system_template=system, user_template=None)
    )

    command = docker.build_docker_command(
        args=_docker_command_args(),
        staged_input=Path("/tmp/in"),
        output_dir=Path("/tmp/out"),
        agent_command=["python", "-m", "agent"],
        host_env_names=(),
        service=None,
        image="custom:1.0",
        template_mounts=mounts,
    )

    assert f"{tmp_path}:{docker.CONTAINER_TEMPLATES_DIR}/system:ro" in command
    assert "custom:1.0" in command
    assert docker.DEFAULT_IMAGE not in command


def test_docker_parser_accepts_service_options() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "--input-dir",
            "/tmp/p",
            "--service",
            "genome-nexus",
            "--service-port",
            "9000",
            "--service-manifest",
            "/tmp/services.json",
            "--service-scripts-dir",
            "/tmp/scripts",
        ]
    )
    assert args.service == "genome-nexus"
    assert args.service_port == 9000
    assert args.service_manifest == Path("/tmp/services.json")
    assert args.service_scripts_dir == Path("/tmp/scripts")


def test_sanitized_manifest_records_service_paths(tmp_path: Path) -> None:
    manifest_path = write_service_manifest(tmp_path / "services.json")
    scripts_dir = write_service_scripts(tmp_path / "scripts")
    svc = services.resolve_service(
        docker_args(service="genome-nexus", service_manifest=manifest_path)
    )
    args = _docker_command_args(
        agent="claude-code",
        clear_tests=False,
        skip_build=False,
        service="genome-nexus",
        service_manifest=manifest_path,
    )
    stack = docker.layered_stack(agent="claude-code", service=svc)
    plan = docker.ImagePlan(image=stack[-1].image, layers=stack)
    manifest = sanitized_manifest(
        args=args,
        input_dir=Path("/tmp/in"),
        run_dir=Path("/tmp/run"),
        staged_input=Path("/tmp/run/input"),
        output_dir=Path("/tmp/run/output"),
        staging_method="copytree",
        host_env_names=(),
        preprocessing={},
        image_plan=plan,
        service=svc,
        service_scripts_dir=scripts_dir,
    )
    assert manifest["service"] == svc
    assert manifest["service_manifest"] == str(manifest_path.resolve())
    assert manifest["service_scripts_dir"] == str(scripts_dir)
    assert manifest["docker"]["image"] == plan.image
    assert manifest["docker"]["image_built"] is True
    assert [layer["name"] for layer in manifest["docker"]["layers"]] == [
        "base",
        "claude-code",
        "javascript",
    ]
    assert manifest["docker"]["layers"][0]["dockerfile"] == str(docker.BASE_DOCKERFILE)
    # No template/prompt-var overrides in this run.
    assert manifest["agent_options"]["system_template"] is None
    assert manifest["agent_options"]["user_template"] is None
    assert manifest["agent_options"]["prompt_vars"] == []


def test_sanitized_manifest_prebuilt_image_has_no_dockerfile(tmp_path: Path) -> None:
    args = _docker_command_args(agent="claude-code", clear_tests=False, skip_build=False)
    manifest = sanitized_manifest(
        args=args,
        input_dir=Path("/tmp/in"),
        run_dir=Path("/tmp/run"),
        staged_input=Path("/tmp/run/input"),
        output_dir=Path("/tmp/run/output"),
        staging_method="copytree",
        host_env_names=(),
        preprocessing={},
        image_plan=docker.ImagePlan(image="custom:1.0", layers=()),
    )
    assert manifest["docker"]["image"] == "custom:1.0"
    assert manifest["docker"]["layers"] == []
    assert manifest["docker"]["image_built"] is False


def test_collect_agent_result_summary_reads_compact_result(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "messages.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"message": "assistant text"}),
                json.dumps(
                    {
                        "subtype": "success",
                        "duration_ms": 628766,
                        "duration_api_ms": 512000,
                        "num_turns": 88,
                        "total_cost_usd": 0.8528051,
                        "result": "long final answer stays in JSONL",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = collect_agent_result_summary(output_dir, "messages.jsonl")

    assert summary == {
        "source_jsonl": "messages.jsonl",
        "available": True,
        "subtype": "success",
        "duration_ms": 628766,
        "duration_api_ms": 512000,
        "num_turns": 88,
        "total_cost_usd": 0.8528051,
    }


def test_collect_agent_result_summary_handles_missing_jsonl(tmp_path: Path) -> None:
    assert collect_agent_result_summary(
        tmp_path, "messages.jsonl"
    ) == {
        "source_jsonl": "messages.jsonl",
        "available": False,
    }


def test_collect_agent_result_summary_captures_error_details(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "messages.jsonl").write_text(
        json.dumps(
            {
                "subtype": "error_during_execution",
                "is_error": True,
                "num_turns": 48,
                "total_cost_usd": 6.91902,
                "stop_reason": "end_turn",
                "api_error_status": None,
                "errors": ["[ede_diagnostic] last_content_type=none"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = collect_agent_result_summary(output_dir, "messages.jsonl")

    assert summary["subtype"] == "error_during_execution"
    assert summary["is_error"] is True
    assert summary["stop_reason"] == "end_turn"
    assert summary["api_error_status"] is None
    assert summary["errors"] == ["[ede_diagnostic] last_content_type=none"]
    # No custom base URL passed -> cost is treated as authoritative, no note.
    assert "total_cost_usd_is_estimate" not in summary
    assert "total_cost_usd_note" not in summary


def test_collect_agent_result_summary_flags_cost_estimate(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "messages.jsonl").write_text(
        json.dumps({"subtype": "success", "total_cost_usd": 6.91902}) + "\n",
        encoding="utf-8",
    )

    summary = collect_agent_result_summary(
        output_dir, "messages.jsonl", cost_is_estimate=True
    )

    assert summary["total_cost_usd"] == 6.91902
    assert summary["total_cost_usd_is_estimate"] is True
    assert summary["total_cost_usd_note"] == COST_ESTIMATE_NOTE


def test_collect_agent_result_summary_no_cost_note_without_cost(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "messages.jsonl").write_text(
        json.dumps({"subtype": "success", "num_turns": 3}) + "\n",
        encoding="utf-8",
    )

    summary = collect_agent_result_summary(
        output_dir, "messages.jsonl", cost_is_estimate=True
    )

    # The note rides on total_cost_usd; absent that field there is nothing to qualify.
    assert "total_cost_usd_is_estimate" not in summary
    assert "total_cost_usd_note" not in summary


def test_load_service_manifest_rejects_invalid_shape(tmp_path: Path) -> None:
    path = tmp_path / "services.json"
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(DockerRunError, match="services"):
        services.load_service_manifest(path)


def test_load_service_manifest_reads_services(tmp_path: Path) -> None:
    manifest = write_service_manifest(tmp_path / "services.json")

    assert {
        "features-service",
        "restcountries",
        "genome-nexus",
    } <= set(services.load_service_manifest(manifest))


def test_agent_command_uses_packaged_module() -> None:
    command = build_claude_code_command(
        build_agent_request(docker_args(), None)
    )
    assert command[:3] == [
        "python",
        "-m",
        "general_agent_eval.general_agents.claude_code",
    ]


def test_service_scripts_dir_validation(tmp_path: Path) -> None:
    with pytest.raises(DockerRunError, match="service-scripts-dir"):
        services.resolve_service_scripts_dir(
            docker_args(service_scripts_dir=tmp_path / "missing")
        )


def test_setup_script_dir_requires_runner(tmp_path: Path) -> None:
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()

    with pytest.raises(DockerRunError, match="run-with-service.sh"):
        services.resolve_service_scripts_dir(
            docker_args(service_scripts_dir=scripts_dir)
        )


def test_service_manifest_json_errors(tmp_path: Path) -> None:
    path = tmp_path / "services.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(DockerRunError, match="invalid JSON"):
        services.load_service_manifest(path)


def test_service_scripts_shell_fixture_is_executable_shape(tmp_path: Path) -> None:
    scripts_dir = write_service_scripts(tmp_path / "scripts")

    result = subprocess.run(
        ["test", "-f", str(scripts_dir / "run-with-service.sh")],
        check=False,
    )
    assert result.returncode == 0
