"""Build the shared agent runtime image and compose the docker run command."""

from __future__ import annotations

import argparse
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from general_agent_eval.orchestration.errors import DockerRunError
from general_agent_eval.orchestration.paths import PROJECT_ROOT

MODULE_DIR = Path(__file__).resolve().parent
# Top-level docker/ in the source tree. Not bundled in the wheel: the base layer's
# build context is the project source, so the default build needs a checkout anyway
# (resolve_image_plan guards this). PROJECT_ROOT falls back to cwd for installed
# wheels, where the guard fires rather than silently probing ./docker.
DOCKER_DIR = PROJECT_ROOT / "docker"

# Dockerfiles for the composable runtime stack. The default image is built as an
# ordered chain (base -> agent -> workload [-> service overlay]); each layer
# builds `FROM ${BASE_IMAGE}` on top of the previous layer's tag.
BASE_DOCKERFILE = DOCKER_DIR / "Dockerfile.base"
AGENT_DOCKERFILES = {
    "claude-code": DOCKER_DIR / "Dockerfile.claude-code",
    "codex": DOCKER_DIR / "Dockerfile.codex",
}
JAVA_DOCKERFILE = DOCKER_DIR / "Dockerfile.java"
JAVASCRIPT_DOCKERFILE = DOCKER_DIR / "Dockerfile.javascript"
GENOME_NEXUS_DOCKERFILE = DOCKER_DIR / "Dockerfile.genome-nexus"

WORKLOAD_DOCKERFILES: dict[str, Path] = {
    "java": JAVA_DOCKERFILE,
    "javascript": JAVASCRIPT_DOCKERFILE,
}

IMAGE_PREFIX = "general-agent-eval"
BASE_IMAGE = f"{IMAGE_PREFIX}-base:latest"
# Tag used by the single-Dockerfile escape hatch (--dockerfile without --image).
DEFAULT_IMAGE = f"{IMAGE_PREFIX}-agent:latest"

CONTAINER_APP_DIR = "/app"
CONTAINER_INPUT_DIR = "/workspace/input"
CONTAINER_OUTPUT_DIR = "/workspace/output"
CONTAINER_SERVICE_SCRIPTS_DIR = "/workspace/service-scripts"
CONTAINER_TEMPLATES_DIR = "/workspace/templates"


@dataclass(frozen=True)
class BuildLayer:
    """One image in the build chain: a Dockerfile, the tag it produces, and the
    build context plus extra build args it needs (e.g. BASE_IMAGE)."""

    name: str
    dockerfile: Path
    image: str
    context: Path
    build_args: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ImagePlan:
    """The image to run plus the ordered layers to build first. `layers` is empty
    when no build is needed (a pre-built image is run as-is)."""

    image: str
    layers: tuple[BuildLayer, ...]
    # True only for --skip-build: we run the default stack tag without building it.
    # That tag is local-only (never in a registry), so the caller must confirm it
    # exists locally before staging -- otherwise docker run tries to pull it and
    # fails late with a misleading "pull access denied". A pre-built --image is left
    # False so Docker may still pull it.
    requires_local_image: bool = False

    @property
    def build(self) -> bool:
        return bool(self.layers)


def _stack_tag(*tokens: str) -> str:
    return f"{IMAGE_PREFIX}-" + "-".join(tokens) + ":latest"


def _build_uid_gid() -> tuple[str, str]:
    uid = getattr(os, "getuid", lambda: 1000)()
    gid = getattr(os, "getgid", lambda: 1000)()
    return str(uid), str(gid)


def _require_source_checkout() -> None:
    """The layered build needs the docker/ Dockerfiles and the project source as the
    base layer's build context, so it only works from a source checkout. An installed
    wheel bundles neither (and PROJECT_ROOT then falls back to the caller's cwd), so
    fail early and clearly instead of letting the build hunt for ./docker in cwd."""
    if not BASE_DOCKERFILE.is_file():
        raise DockerRunError(
            f"runtime Dockerfiles not found at {DOCKER_DIR}. Building the default "
            "image stack must run from a source checkout of this repository -- the "
            "base layer's build context is the project source, so an installed wheel "
            "cannot build it regardless. Run from a checkout, or pass --image to run "
            "a pre-built image or --dockerfile to build a custom one."
        )


def layered_stack(
    *, agent: str, workload: str = "java", service: dict[str, Any] | None = None
) -> tuple[BuildLayer, ...]:
    """The default runtime stack: base -> agent -> <workload>, plus the
    genome-nexus overlay when that service is selected with the java workload."""
    if agent not in AGENT_DOCKERFILES:
        raise DockerRunError(f"no runtime layer is defined for agent '{agent}'")
    if workload not in WORKLOAD_DOCKERFILES:
        raise DockerRunError(
            f"no workload layer is defined for '{workload}'; "
            f"available: {sorted(WORKLOAD_DOCKERFILES)}"
        )
    uid, gid = _build_uid_gid()
    base = BuildLayer(
        name="base",
        dockerfile=BASE_DOCKERFILE,
        image=BASE_IMAGE,
        # The base COPYs this project, so it builds from the repo root; the overlay
        # layers only RUN, so they build from the tiny docker/ context.
        context=PROJECT_ROOT,
        build_args=(("AGENT_UID", uid), ("AGENT_GID", gid)),
    )
    agent_layer = BuildLayer(
        name=agent,
        dockerfile=AGENT_DOCKERFILES[agent],
        image=_stack_tag(agent),
        context=DOCKER_DIR,
        build_args=(("BASE_IMAGE", base.image),),
    )
    workload_layer = BuildLayer(
        name=workload,
        dockerfile=WORKLOAD_DOCKERFILES[workload],
        image=_stack_tag(agent, workload),
        context=DOCKER_DIR,
        build_args=(("BASE_IMAGE", agent_layer.image),),
    )
    layers = [base, agent_layer, workload_layer]
    if workload == "java" and service is not None and service.get("id") == "genome-nexus":
        layers.append(
            BuildLayer(
                name="genome-nexus",
                dockerfile=GENOME_NEXUS_DOCKERFILE,
                image=_stack_tag(agent, "java", "genome-nexus"),
                context=DOCKER_DIR,
                build_args=(("BASE_IMAGE", workload_layer.image),),
            )
        )
    return tuple(layers)


def resolve_image_plan(
    args: argparse.Namespace,
    *,
    agent: str,
    workload: str = "java",
    service: dict[str, Any] | None = None,
) -> ImagePlan:
    """Resolve what to run and what to build first.

    Default: build the composable stack (base + agent + java [+ genome-nexus]),
    and run its final layer. Escape hatches: `--image` alone names a pre-built
    image and skips the build; `--dockerfile` builds a single custom Dockerfile
    (its own directory is the build context), tagged with `--image` or the
    default tag.
    """
    image = getattr(args, "image", None)
    dockerfile = getattr(args, "dockerfile", None)

    if dockerfile is not None:
        if args.skip_build:
            raise DockerRunError(
                "--skip-build conflicts with --dockerfile; pass --image to run a "
                "previously built image instead"
            )
        dockerfile = dockerfile.expanduser().resolve()
        if not dockerfile.is_file():
            raise DockerRunError(f"--dockerfile is not a file: {dockerfile}")
        uid, gid = _build_uid_gid()
        tag = image or DEFAULT_IMAGE
        layer = BuildLayer(
            name="custom",
            dockerfile=dockerfile,
            image=tag,
            context=dockerfile.parent,
            build_args=(("AGENT_UID", uid), ("AGENT_GID", gid)),
        )
        return ImagePlan(image=tag, layers=(layer,))

    if image is not None:
        # A pre-built image (registry, or an earlier build); skip the build entirely.
        return ImagePlan(image=image, layers=())

    stack = layered_stack(agent=agent, workload=workload, service=service)
    final_image = stack[-1].image
    if args.skip_build:
        # Skipping the build only needs the tag, not the Dockerfiles -- but the tag
        # must already exist locally (require_local_image enforces that pre-staging).
        return ImagePlan(image=final_image, layers=(), requires_local_image=True)
    _require_source_checkout()
    return ImagePlan(image=final_image, layers=stack)


@dataclass(frozen=True)
class TemplateMount:
    """A custom prompt template bind-mounted read-only into the container."""

    role: str  # "system" or "user"
    host_path: Path
    container_dir: str
    container_path: str


def resolve_template_mounts(args: argparse.Namespace) -> tuple[TemplateMount, ...]:
    mounts: list[TemplateMount] = []
    for role, raw_path in (
        ("system", getattr(args, "system_template", None)),
        ("user", getattr(args, "user_template", None)),
    ):
        if raw_path is None:
            continue
        host_path = raw_path.expanduser().resolve()
        if not host_path.is_file():
            raise DockerRunError(f"--{role}-template is not a file: {raw_path}")
        # The parent directory is mounted (not just the file) so Jinja includes of
        # sibling templates keep resolving inside the container.
        container_dir = f"{CONTAINER_TEMPLATES_DIR}/{role}"
        mounts.append(
            TemplateMount(
                role=role,
                host_path=host_path,
                container_dir=container_dir,
                container_path=f"{container_dir}/{host_path.name}",
            )
        )
    return tuple(mounts)


def _require_buildx() -> None:
    buildx_check = subprocess.run(
        ["docker", "buildx", "version"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if buildx_check.returncode != 0:
        detail = buildx_check.stderr.strip() or buildx_check.stdout.strip()
        raise DockerRunError(
            "Docker Buildx is required to build the agent runtime image. "
            "Install the Docker Buildx CLI plugin and verify `docker buildx version` "
            f"works. {detail}"
        )


def build_layer(layer: BuildLayer) -> None:
    if not layer.dockerfile.is_file():
        raise DockerRunError(f"Dockerfile is not a file: {layer.dockerfile}")
    command = [
        "docker",
        "buildx",
        "build",
        "--load",
        "-f",
        str(layer.dockerfile),
        "-t",
        layer.image,
    ]
    for name, value in layer.build_args:
        command.extend(["--build-arg", f"{name}={value}"])
    command.append(str(layer.context))
    subprocess.run(command, check=True)


def require_local_image(image: str) -> None:
    """Fail fast when --skip-build's image is not present locally. The default stack
    tag lives in no registry, so letting `docker run` discover the gap would attempt
    a doomed pull and surface a confusing "pull access denied" only after staging.
    `docker image inspect` is a local-only probe (no network), but it exits nonzero
    for *any* failure -- a missing image and an unreachable/denied daemon look the
    same -- so on failure we probe the daemon (`docker version` exits nonzero only
    when it is unreachable) to report the right cause instead of always blaming the
    image."""
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", image],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        raise DockerRunError(
            "Docker CLI not found; install Docker to run the agent runtime."
        ) from exc
    if result.returncode == 0:
        return
    inspect_error = result.stderr.strip()
    daemon = subprocess.run(
        ["docker", "version"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    if daemon.returncode != 0:
        detail = daemon.stderr.strip() or inspect_error
        raise DockerRunError(
            f"Cannot reach the Docker daemon to check the runtime image '{image}'. "
            "Start Docker and verify access, then retry."
            + (f" {detail}" if detail else "")
        )
    message = (
        f"--skip-build was given but the runtime image '{image}' is not present "
        "locally. Build it first by running without --skip-build, or pass --image "
        "to run a different pre-built image."
    )
    if inspect_error:
        message += f" ({inspect_error})"
    raise DockerRunError(message)


def build_image_plan(plan: ImagePlan) -> None:
    """Build each layer in order so every `FROM ${BASE_IMAGE}` resolves the tag the
    previous layer produced. No-op for a pre-built image (empty `layers`)."""
    if not plan.layers:
        return
    _require_buildx()
    for layer in plan.layers:
        print(
            f"[docker-run] building layer {layer.name} -> {layer.image}", flush=True
        )
        build_layer(layer)


def build_docker_command(
    *,
    args: argparse.Namespace,
    staged_input: Path,
    output_dir: Path,
    agent_command: list[str],
    host_env_names: tuple[str, ...],
    service: dict[str, Any] | None = None,
    service_scripts_dir: Path | None = None,
    image: str = DEFAULT_IMAGE,
    template_mounts: tuple[TemplateMount, ...] = (),
) -> list[str]:
    command = [
        "docker",
        "run",
        "--rm",
        "--workdir",
        "/app",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--network",
        args.network,
        "--pids-limit",
        str(args.pids_limit),
    ]
    if args.memory:
        command.extend(["--memory", args.memory])
    if args.cpus:
        command.extend(["--cpus", str(args.cpus)])
    for env_name in host_env_names:
        command.extend(["-e", env_name])
    command.extend(["-v", f"{PROJECT_ROOT}:{CONTAINER_APP_DIR}:ro"])
    if service is not None:
        if service_scripts_dir is None:
            raise DockerRunError("service_scripts_dir is required when service is set")
        command.extend(
            [
                "-v",
                f"{service_scripts_dir}:{CONTAINER_SERVICE_SCRIPTS_DIR}:ro",
            ]
        )
    for mount in template_mounts:
        command.extend(["-v", f"{mount.host_path.parent}:{mount.container_dir}:ro"])
    command.extend(
        [
            "-v",
            f"{staged_input}:{CONTAINER_INPUT_DIR}:rw",
            "-v",
            f"{output_dir}:{CONTAINER_OUTPUT_DIR}:rw",
            image,
        ]
    )
    if service is not None:
        # Start the service (health-gated, backgrounded) before exec'ing the agent.
        command.extend(
            [
                "bash",
                f"{CONTAINER_SERVICE_SCRIPTS_DIR}/run-with-service.sh",
                service["id"],
                "--repo",
                CONTAINER_INPUT_DIR,
                "--host",
                "127.0.0.1",
                "--port",
                str(service["port"]),
                "--",
            ]
        )
    command.extend(agent_command)
    return command


def stream_command(command: list[str], *, log_path: Path) -> int:
    with subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    ) as process:
        if process.stdout is None:
            raise DockerRunError("Failed to capture Docker output")
        with log_path.open("w", encoding="utf-8") as log_file:
            for line in process.stdout:
                print(line, end="")
                log_file.write(line)
                log_file.flush()
        return process.wait()
