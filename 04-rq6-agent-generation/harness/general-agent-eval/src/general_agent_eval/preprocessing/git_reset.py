from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


class GitVcsError(RuntimeError):
    pass


@dataclass(frozen=True)
class GitResetResult:
    target_dir: Path
    repo_root: Path
    pinned_commit: str
    superproject_root: Path | None = None
    superproject_relative_path: str | None = None


@dataclass(frozen=True)
class GitResetTarget:
    target_dir: Path
    repo_root: Path
    pinned_commit: str
    superproject_root: Path | None = None
    superproject_relative_path: str | None = None


def _run_git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        command = " ".join(["git", "-C", str(cwd), *args])
        detail = result.stderr.strip() or result.stdout.strip()
        raise GitVcsError(f"Git command failed: {command}\n{detail}")
    return result


def _git_output(args: list[str], *, cwd: Path) -> str:
    return _run_git(args, cwd=cwd).stdout.strip()


def _repo_root(directory: Path) -> Path:
    if not directory.exists():
        raise GitVcsError(f"Directory does not exist: {directory}")
    if not directory.is_dir():
        raise GitVcsError(f"Path is not a directory: {directory}")
    return Path(_git_output(["rev-parse", "--show-toplevel"], cwd=directory)).resolve()


def _superproject_root(repo_root: Path) -> Path | None:
    output = _git_output(
        ["rev-parse", "--show-superproject-working-tree"],
        cwd=repo_root,
    )
    if not output:
        return None
    return Path(output).resolve()


def _superproject_relative_path(repo_root: Path, superproject_root: Path) -> str:
    return os.path.relpath(repo_root, superproject_root).replace(os.sep, "/")


def _pinned_submodule_commit(
    *,
    repo_root: Path,
    superproject_root: Path,
) -> str:
    relative_path = _superproject_relative_path(repo_root, superproject_root)
    stage_output = _git_output(
        ["ls-files", "--stage", "--", relative_path],
        cwd=superproject_root,
    )
    for line in stage_output.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "160000":
            return parts[1]
    raise GitVcsError(
        f"Could not find pinned submodule commit for {repo_root} "
        f"in {superproject_root}"
    )


def _reset_nested_submodules(repo_root: Path) -> None:
    status = _run_git(["submodule", "status", "--recursive"], cwd=repo_root)
    if not status.stdout.strip():
        return

    _run_git(
        ["submodule", "foreach", "--recursive", "git reset --hard && git clean -ffdx"],
        cwd=repo_root,
    )
    _run_git(["submodule", "update", "--init", "--recursive", "--force"], cwd=repo_root)
    _run_git(
        ["submodule", "foreach", "--recursive", "git reset --hard && git clean -ffdx"],
        cwd=repo_root,
    )


def resolve_reset_target(directory: str | Path) -> GitResetTarget:
    target_dir = Path(directory).expanduser().resolve()
    repo_root = _repo_root(target_dir)
    superproject_root = _superproject_root(repo_root)

    if superproject_root is None:
        pinned_commit = _git_output(["rev-parse", "HEAD"], cwd=repo_root)
        return GitResetTarget(
            target_dir=target_dir,
            repo_root=repo_root,
            pinned_commit=pinned_commit,
        )

    relative_path = _superproject_relative_path(repo_root, superproject_root)
    pinned_commit = _pinned_submodule_commit(
        repo_root=repo_root,
        superproject_root=superproject_root,
    )
    return GitResetTarget(
        target_dir=target_dir,
        repo_root=repo_root,
        pinned_commit=pinned_commit,
        superproject_root=superproject_root,
        superproject_relative_path=relative_path,
    )


def reset_to_commit(
    directory: str | Path,
    commit: str,
    *,
    reset_target: GitResetTarget | None = None,
) -> GitResetResult:
    target_dir = Path(directory).expanduser().resolve()
    repo_root = _repo_root(target_dir)

    _run_git(["cat-file", "-e", f"{commit}^{{commit}}"], cwd=repo_root)
    _run_git(["reset", "--hard", commit], cwd=repo_root)
    _run_git(["clean", "-ffdx"], cwd=repo_root)
    _reset_nested_submodules(repo_root)

    return GitResetResult(
        target_dir=target_dir,
        repo_root=repo_root,
        pinned_commit=commit,
        superproject_root=(
            reset_target.superproject_root if reset_target is not None else None
        ),
        superproject_relative_path=(
            reset_target.superproject_relative_path
            if reset_target is not None
            else None
        ),
    )


def reset_to_pinned_commit(directory: str | Path) -> GitResetResult:
    reset_target = resolve_reset_target(directory)

    if reset_target.superproject_root is not None:
        if reset_target.superproject_relative_path is None:
            raise GitVcsError(f"Missing submodule path for {reset_target.repo_root}")
        _run_git(["reset", "--hard"], cwd=reset_target.repo_root)
        _run_git(
            [
                "submodule",
                "update",
                "--init",
                "--recursive",
                "--force",
                "--",
                reset_target.superproject_relative_path,
            ],
            cwd=reset_target.superproject_root,
        )
    else:
        _run_git(["reset", "--hard"], cwd=reset_target.repo_root)

    return reset_to_commit(
        directory,
        reset_target.pinned_commit,
        reset_target=reset_target,
    )
