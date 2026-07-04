"""Entry point: stage a project, preprocess it, and run an agent inside Docker."""

from __future__ import annotations

import argparse
import subprocess
import sys
from typing import Any

from general_agent_eval.general_agents.agent_specs import (
    AGENT_SPECS,
    AgentRunRequest,
)
from general_agent_eval.orchestration.cli import (
    build_parser,
    required_host_env_names,
    resolve_agent_defaults,
    validate_agent_options,
    validate_agent_values,
    validate_host_env,
)
from general_agent_eval.orchestration.docker import (
    CONTAINER_INPUT_DIR,
    CONTAINER_OUTPUT_DIR,
    TemplateMount,
    build_docker_command,
    build_image_plan,
    require_local_image,
    resolve_image_plan,
    resolve_template_mounts,
    stream_command,
)
from general_agent_eval.orchestration.errors import DockerRunError
from general_agent_eval.orchestration.manifest import (
    collect_agent_result_summary,
    sanitized_manifest,
    write_manifest,
)
from general_agent_eval.orchestration.preprocess import preprocess_staged_input
from general_agent_eval.orchestration.services import (
    resolve_service,
    resolve_service_scripts_dir,
    rest_assured_prompt_vars,
    service_prompt_vars,
)
from general_agent_eval.orchestration.staging import (
    build_run_id,
    collect_git_artifacts,
    default_output_root,
    prepare_run_dir,
    stage_input,
)


def build_agent_request(
    args: argparse.Namespace,
    service: dict[str, Any] | None = None,
    template_mounts: tuple[TemplateMount, ...] = (),
) -> AgentRunRequest:
    agent_env = tuple(args.env)
    prompt_vars: tuple[str, ...] = ()
    if service is not None:
        # Expose the base URL both to generated tests (env) and to the prompt templates.
        agent_env = (*agent_env, f"SERVICE_BASE_URL={service['base_url']}")
        prompt_vars = service_prompt_vars(service)
        if getattr(args, "inject_rest_assured", False):
            prompt_vars = (*prompt_vars, *rest_assured_prompt_vars(service))
    user_prompt_vars = tuple(getattr(args, "prompt_var", []))
    service_keys = {var.split("=", 1)[0] for var in prompt_vars}
    collisions = sorted(
        {key for var in user_prompt_vars if (key := var.split("=", 1)[0]) in service_keys}
    )
    if collisions:
        # The orchestrator owns service vars (it started the service), so a user
        # override would silently desync the prompt from SERVICE_BASE_URL.
        raise DockerRunError(
            "--prompt-var keys collide with service-derived prompt vars: "
            + ", ".join(collisions)
        )
    container_templates = {m.role: m.container_path for m in template_mounts}
    return AgentRunRequest(
        container_input_dir=CONTAINER_INPUT_DIR,
        container_output_dir=CONTAINER_OUTPUT_DIR,
        model=args.model,
        permission_mode=args.permission_mode,
        effort=getattr(args, "effort", "high"),
        system_prompt_config=args.system_prompt_config,
        base_url=args.base_url,
        small_model=getattr(args, "small_model", None),
        api_key_env=args.api_key_env,
        auth_token_env=args.auth_token_env,
        oauth_token_env=args.oauth_token_env,
        max_turns=args.max_turns,
        max_budget_usd=args.max_budget_usd,
        # Docker preprocessing owns reset order so tests cannot be restored later.
        reset_git=False,
        agent_env=agent_env,
        prompt_vars=(*prompt_vars, *user_prompt_vars),
        extra_args=tuple(args.extra_arg),
        system_template=container_templates.get("system"),
        user_template=container_templates.get("user"),
        sandbox=getattr(args, "sandbox", "full_access"),
        workload=getattr(args, "workload", "java"),
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        validate_agent_options(args)
        resolve_agent_defaults(args)
        input_dir = args.input_dir.expanduser().resolve()
        if not input_dir.exists():
            raise DockerRunError(f"--input-dir does not exist: {args.input_dir}")
        if not input_dir.is_dir():
            raise DockerRunError(f"--input-dir is not a directory: {args.input_dir}")

        output_root = (
            args.output_dir.expanduser().resolve()
            if args.output_dir
            else default_output_root(input_dir=input_dir).resolve()
        )
        run_dir = output_root / build_run_id(input_dir=input_dir, agent_name=args.agent)
        host_env_names = required_host_env_names(args)
        validate_host_env(host_env_names)
        validate_agent_values(args)
        service = resolve_service(args)
        service_scripts_dir = (
            resolve_service_scripts_dir(args) if service is not None else None
        )
        if args.inject_rest_assured and service is None:
            raise DockerRunError(
                "--inject-rest-assured requires --service; the rest_assured config "
                "is read from the service manifest"
            )
        # Resolved before any staging or build so bad paths/option combos fail fast.
        image_plan = resolve_image_plan(args, agent=args.agent, workload=args.workload, service=service)
        if image_plan.requires_local_image:
            # --skip-build: confirm the tag exists now, not after staging via a
            # doomed docker run pull.
            require_local_image(image_plan.image)
        template_mounts = resolve_template_mounts(args)
        agent_spec = AGENT_SPECS[args.agent]
        agent_command = agent_spec.build_command(
            build_agent_request(args, service, template_mounts)
        )
        reset_target = None
        if args.reset_git:
            from general_agent_eval.preprocessing.git_reset import (
                GitVcsError,
                resolve_reset_target,
            )

            try:
                reset_target = resolve_reset_target(input_dir)
            except GitVcsError as exc:
                raise DockerRunError(
                    f"Failed to resolve Git reset target: {exc}"
                ) from exc
        prepare_run_dir(run_dir, input_dir=input_dir)

        staged_input = run_dir / "input"
        output_dir = run_dir / "output"
        output_dir.mkdir()

        if image_plan.build:
            build_image_plan(image_plan)

        staging_method = stage_input(input_dir, staged_input)
        preprocessing = preprocess_staged_input(
            args=args,
            staged_input=staged_input,
            output_dir=output_dir,
            reset_target=reset_target,
            service=service,
        )
        manifest_path = run_dir / "manifest.json"
        manifest = sanitized_manifest(
            args=args,
            input_dir=input_dir,
            run_dir=run_dir,
            staged_input=staged_input,
            output_dir=output_dir,
            staging_method=staging_method,
            host_env_names=host_env_names,
            preprocessing=preprocessing,
            service=service,
            service_scripts_dir=service_scripts_dir,
            image_plan=image_plan,
        )
        write_manifest(manifest_path, manifest)

        docker_command = build_docker_command(
            args=args,
            staged_input=staged_input,
            output_dir=output_dir,
            agent_command=agent_command,
            host_env_names=host_env_names,
            service=service,
            service_scripts_dir=service_scripts_dir,
            image=image_plan.image,
            template_mounts=template_mounts,
        )
        print(f"[docker-run] run_dir={run_dir}", flush=True)
        print(
            f"[docker-run] agent={args.agent} image={image_plan.image}", flush=True
        )
        if service is not None:
            print(
                f"[docker-run] service={service['id']} base_url={service['base_url']}",
                flush=True,
            )
        exit_code = stream_command(
            docker_command,
            log_path=output_dir / "docker.log",
        )
        manifest["exit_code"] = exit_code
        manifest["agent_result"] = collect_agent_result_summary(
            output_dir,
            agent_spec.output_jsonl_name,
            cost_is_estimate=args.base_url is not None,
        )
        manifest["artifacts"] = collect_git_artifacts(staged_input, output_dir)
        write_manifest(manifest_path, manifest)
        return exit_code
    except DockerRunError as exc:
        parser.exit(2, f"error: {exc}\n")
    except subprocess.CalledProcessError as exc:
        parser.exit(exc.returncode or 1, f"error: command failed: {exc.cmd}\n")
    except KeyboardInterrupt:
        parser.exit(130, "interrupted\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
