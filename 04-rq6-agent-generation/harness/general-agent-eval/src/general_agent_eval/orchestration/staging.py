"""Stage input projects into run directories and capture staged Git state."""

from __future__ import annotations

import datetime as dt
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from general_agent_eval.orchestration.errors import DockerRunError
from general_agent_eval.orchestration.paths import PROJECT_ROOT

RUN_ID_DELIMITER = "__"


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9.-]+", "-", value.strip()).strip("-")
    return slug or "project"


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def build_run_id(*, input_dir: Path, agent_name: str) -> str:
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    return RUN_ID_DELIMITER.join([stamp, slugify(agent_name), slugify(input_dir.name)])


def default_output_root(*, input_dir: Path) -> Path:
    base_dir = PROJECT_ROOT / "runs"
    if is_relative_to(base_dir, input_dir):
        base_dir = Path(tempfile.gettempdir()) / "general-agent-eval-runs"
    return base_dir


def prepare_run_dir(run_dir: Path, *, input_dir: Path) -> None:
    output_root = run_dir.parent
    if is_relative_to(output_root, input_dir):
        raise DockerRunError(
            "--output-dir must not be inside --input-dir; it would be copied "
            "into the agent workspace"
        )
    if output_root.exists() and not output_root.is_dir():
        raise DockerRunError(f"--output-dir is not a directory: {output_root}")
    if run_dir.exists():
        raise DockerRunError(f"Run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)


def run_checked(command: list[str], *, cwd: Path | None = None) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise DockerRunError(f"Command failed: {command[0]}\n{detail}")
    return result.stdout


def git_repo_root(directory: Path) -> Path | None:
    result = subprocess.run(
        ["git", "-C", str(directory), "rev-parse", "--show-toplevel"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip()).resolve()


def git_output(directory: Path, git_args: list[str]) -> str:
    return run_checked(["git", "-C", str(directory), *git_args]).strip()


def sync_worktree(source: Path, destination: Path) -> None:
    if shutil.which("rsync") is None:
        raise DockerRunError(
            "rsync is required to stage Git worktrees while preserving cloned "
            "Git metadata"
        )
    run_checked(
        [
            "rsync",
            "-a",
            "--checksum",
            "--delete",
            "--exclude",
            ".git",
            f"{source}/",
            f"{destination}/",
        ]
    )


def stage_input(source: Path, destination: Path) -> str:
    repo_root = git_repo_root(source)
    if repo_root == source:
        run_checked(
            [
                "git",
                "clone",
                "--local",
                "--no-hardlinks",
                str(source),
                str(destination),
            ]
        )
        sync_worktree(source, destination)
        return "git-clone-rsync"

    shutil.copytree(source, destination, symlinks=True)
    return "copytree"


def write_git_patch(
    *,
    staged_input: Path,
    output_path: Path,
    relative_paths: list[str],
) -> None:
    if not relative_paths:
        output_path.write_bytes(b"")
        return

    result = subprocess.run(
        [
            "git",
            "-C",
            str(staged_input),
            "diff",
            "--binary",
            "--",
            *relative_paths,
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).decode(
            "utf-8", errors="replace"
        ).strip()
        raise DockerRunError(f"Failed to write Git patch: {detail}")
    output_path.write_bytes(result.stdout)


def remove_git_metadata(root: Path) -> None:
    for current_dir, dir_names, file_names in os.walk(root, topdown=True):
        current_path = Path(current_dir)
        if ".git" in dir_names:
            git_path = current_path / ".git"
            if git_path.is_symlink() or git_path.is_file():
                git_path.unlink()
            else:
                shutil.rmtree(git_path)
            dir_names.remove(".git")
        if ".git" in file_names:
            (current_path / ".git").unlink()


def initialize_synthetic_git_baseline(staged_input: Path) -> dict[str, str | None]:
    original_head = None
    original_branch = None
    if git_repo_root(staged_input) == staged_input:
        original_head = git_output(staged_input, ["rev-parse", "HEAD"])
        original_branch = git_output(staged_input, ["branch", "--show-current"]) or None

    remove_git_metadata(staged_input)
    run_checked(["git", "init"], cwd=staged_input)
    run_checked(["git", "add", "--all"], cwd=staged_input)
    run_checked(
        [
            "git",
            "-c",
            "user.name=General Agent Eval",
            "-c",
            "user.email=general-agent-eval@example.invalid",
            "commit",
            "--allow-empty",
            "-m",
            "chore: testless baseline",
        ],
        cwd=staged_input,
    )
    return {
        "original_head": original_head,
        "original_branch": original_branch,
        "synthetic_baseline_commit": git_output(staged_input, ["rev-parse", "HEAD"]),
    }


def collect_git_artifacts(staged_input: Path, output_dir: Path) -> dict[str, str]:
    if git_repo_root(staged_input) != staged_input:
        return {}

    artifacts: dict[str, str] = {}

    def write_git_artifact(filename: str, git_args: list[str]) -> None:
        result = subprocess.run(
            ["git", "-C", str(staged_input), *git_args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        path = output_dir / filename
        if result.returncode == 0:
            path.write_text(result.stdout, encoding="utf-8")
        else:
            path.write_text(result.stderr or result.stdout, encoding="utf-8")
        artifacts[filename] = str(path)

    def write_git_binary_artifact(filename: str, git_args: list[str]) -> None:
        result = subprocess.run(
            ["git", "-C", str(staged_input), *git_args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        path = output_dir / filename
        path.write_bytes(
            result.stdout if result.returncode == 0 else result.stderr or result.stdout
        )
        artifacts[filename] = str(path)

    write_git_artifact("git_status.txt", ["status", "--short"])
    write_git_artifact(
        "git_untracked.txt", ["ls-files", "--others", "--exclude-standard"]
    )
    subprocess.run(
        ["git", "-C", str(staged_input), "add", "--intent-to-add", "--all"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    write_git_binary_artifact("git_diff.patch", ["diff", "--binary"])
    return artifacts
