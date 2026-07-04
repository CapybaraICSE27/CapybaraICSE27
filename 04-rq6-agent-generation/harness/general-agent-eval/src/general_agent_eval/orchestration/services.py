"""Resolve live-service configuration from the services manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from general_agent_eval.orchestration.errors import DockerRunError


def load_service_manifest(manifest_path: Path) -> dict[str, Any]:
    resolved_path = manifest_path.expanduser().resolve()
    if not resolved_path.is_file():
        raise DockerRunError(f"service manifest is not a file: {resolved_path}")
    try:
        payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DockerRunError(
            f"service manifest is invalid JSON: {resolved_path}"
        ) from exc
    services = payload.get("services")
    if not isinstance(services, dict):
        raise DockerRunError(
            f"service manifest must contain an object at 'services': {resolved_path}"
        )
    return services


def resolve_service_manifest_path(args: argparse.Namespace) -> Path:
    service_manifest = getattr(args, "service_manifest", None)
    service_scripts_dir = getattr(args, "service_scripts_dir", None)
    if service_manifest is not None:
        return service_manifest.expanduser().resolve()
    if service_scripts_dir is not None:
        return (service_scripts_dir.expanduser().resolve() / "services.json")
    raise DockerRunError(
        "--service requires --service-manifest or --service-scripts-dir"
    )


def resolve_service_scripts_dir(args: argparse.Namespace) -> Path:
    service_scripts_dir = getattr(args, "service_scripts_dir", None)
    if service_scripts_dir is None:
        raise DockerRunError("--service requires --service-scripts-dir")
    scripts_dir = service_scripts_dir.expanduser().resolve()
    if not scripts_dir.is_dir():
        raise DockerRunError(f"--service-scripts-dir is not a directory: {scripts_dir}")
    run_script = scripts_dir / "run-with-service.sh"
    if not run_script.is_file():
        raise DockerRunError(
            f"--service-scripts-dir must contain run-with-service.sh: {scripts_dir}"
        )
    return scripts_dir


def resolve_service(args: argparse.Namespace) -> dict[str, Any] | None:
    if not args.service:
        if args.service_port is not None:
            raise DockerRunError("--service-port requires --service")
        return None
    services = load_service_manifest(resolve_service_manifest_path(args))
    if args.service not in services:
        known = ", ".join(sorted(services))
        raise DockerRunError(f"unknown --service '{args.service}' (known: {known})")
    svc = services[args.service]
    port = args.service_port or int(svc["default_port"])

    def url(path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"http://127.0.0.1:{port}{path}"

    return {
        "id": args.service,
        "port": port,
        "base_url": url(svc.get("base_path", "/")),
        "rest_assured": svc.get("rest_assured"),
    }


def service_prompt_vars(service: dict[str, Any]) -> tuple[str, ...]:
    return (
        f"service_id={service['id']}",
        f"service_base_url={service['base_url']}",
    )


def rest_assured_prompt_vars(service: dict[str, Any]) -> tuple[str, ...]:
    """Prompt vars exposed only when RestAssured was injected: a presence flag and,
    for multi-module builds, the module directory whose tests carry the dependency."""
    config = service.get("rest_assured")
    if not config:
        return ()
    prompt_vars = ("rest_assured=1",)
    target_pom = str(config.get("target_pom", "pom.xml"))
    if "/" in target_pom:
        prompt_vars = (*prompt_vars, f"test_module={target_pom.rsplit('/', 1)[0]}")
    return prompt_vars
