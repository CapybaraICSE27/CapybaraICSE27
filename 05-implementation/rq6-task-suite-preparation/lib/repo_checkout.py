#!/usr/bin/env python3
"""Read-only git checks and optional isolated snapshot creation for RQ6."""

from __future__ import annotations

import io
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import Dict, Iterable

from common import run_command


def _timeout_text(exc: subprocess.TimeoutExpired) -> str:
    timeout = exc.timeout if exc.timeout is not None else "unknown"
    return f"git command timed out after {timeout} seconds: {' '.join(map(str, exc.cmd))}"


def run_git_command(cmd: list[str], repo_dir: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    try:
        return run_command(cmd, cwd=repo_dir, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(cmd, 124, "", _timeout_text(exc))


def git_status(repo_dir: Path) -> Dict[str, object]:
    if not (repo_dir / ".git").exists():
        return {"is_git_repo": False, "status_ok": False, "dirty": None, "porcelain": ""}
    head = run_git_command(["git", "rev-parse", "HEAD"], repo_dir, timeout=20)
    status = run_git_command(["git", "status", "--porcelain"], repo_dir, timeout=30)
    return {
        "is_git_repo": True,
        "status_ok": head.returncode == 0 and status.returncode == 0,
        "current_commit": head.stdout.strip() if head.returncode == 0 else "",
        "dirty": bool(status.stdout.strip()) if status.returncode == 0 else None,
        "porcelain": status.stdout.strip(),
        "error": (head.stderr or status.stderr).strip(),
    }


def commit_exists(repo_dir: Path, commit: str) -> bool:
    if not commit:
        return False
    proc = run_git_command(["git", "cat-file", "-e", f"{commit}^{{commit}}"], repo_dir, timeout=20)
    return proc.returncode == 0


def _safe_extract_tar_bytes(tar_bytes: bytes, dest: Path) -> None:
    dest_resolved = dest.resolve()
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:*") as tf:
        for member in tf.getmembers():
            target = (dest / member.name).resolve()
            try:
                target.relative_to(dest_resolved)
            except ValueError:
                raise RuntimeError(f"Refusing unsafe tar member: {member.name}")
        tf.extractall(dest)


def ensure_workdir_git_metadata(dest: Path) -> Dict[str, object]:
    git_dir = dest / ".git"
    if git_dir.exists():
        return {"git_metadata_status": "exists"}
    if not dest.exists():
        return {"git_metadata_status": "missing_workdir"}
    proc = subprocess.run(
        ["git", "init", "--quiet"],
        cwd=str(dest),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    if proc.returncode == 0:
        return {"git_metadata_status": "initialized"}
    return {
        "git_metadata_status": "init_failed",
        "git_metadata_stderr": (proc.stderr or "")[-2000:],
    }


def create_git_archive_workdir(
    repo_dir: Path,
    commit: str,
    dest: Path,
    *,
    allow_existing: bool = True,
) -> Dict[str, object]:
    if dest.exists() and any(dest.iterdir()):
        metadata = ensure_workdir_git_metadata(dest)
        return {
            "created": False,
            "workdir_path": str(dest),
            "status": "exists",
            **metadata,
        } if allow_existing else {
            "created": False,
            "workdir_path": str(dest),
            "status": "exists_nonempty",
            **metadata,
        }
    dest.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            ["git", "archive", "--format=tar", commit],
            cwd=str(repo_dir),
            capture_output=True,
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "created": False,
            "workdir_path": str(dest),
            "status": "archive_timeout",
            "stderr": _timeout_text(exc),
        }
    if proc.returncode != 0:
        return {
            "created": False,
            "workdir_path": str(dest),
            "status": "archive_failed",
            "stderr": proc.stderr.decode("utf-8", errors="replace")[-2000:],
        }
    _safe_extract_tar_bytes(proc.stdout, dest)
    return {"created": True, "workdir_path": str(dest), "status": "created", **ensure_workdir_git_metadata(dest)}


def copy_source_workdir(
    repo_dir: Path,
    dest: Path,
    *,
    allow_existing: bool = True,
    ignore_names: Iterable[str] = (
        ".git",
        "node_modules",
        ".next",
        ".nuxt",
        "dist",
        "build",
        "coverage",
        "playwright-report",
        "cypress/videos",
        "cypress/screenshots",
    ),
) -> Dict[str, object]:
    if dest.exists() and any(dest.iterdir()):
        metadata = ensure_workdir_git_metadata(dest)
        return {
            "created": False,
            "workdir_path": str(dest),
            "status": "exists",
            **metadata,
        } if allow_existing else {
            "created": False,
            "workdir_path": str(dest),
            "status": "exists_nonempty",
            **metadata,
        }
    dest.parent.mkdir(parents=True, exist_ok=True)
    ignore = shutil.ignore_patterns(*list(ignore_names))
    try:
        shutil.copytree(repo_dir, dest, ignore=ignore, dirs_exist_ok=True)
    except OSError as exc:
        return {
            "created": False,
            "workdir_path": str(dest),
            "status": "copy_failed",
            "stderr": str(exc),
        }
    return {
        "created": True,
        "workdir_path": str(dest),
        "status": "created_from_current_source",
        **ensure_workdir_git_metadata(dest),
    }
