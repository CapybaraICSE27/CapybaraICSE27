from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

from general_agent_eval.preprocessing.java_test_clearing import (
    SOURCE_SET_NAMES,
    TEST_FILE_PATTERN,
    TEST_ROOT_DIR_NAMES,
    TEST_SUPPORT_DIR_NAMES,
)

# Build/config files an agent may legitimately touch to wire up test dependencies.
# Flagged separately from production code so the report stays honest either way.
BUILD_FILE_NAMES = frozenset(
    {
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "settings.gradle",
        "settings.gradle.kts",
        "gradle.properties",
        "build.xml",
        "ivy.xml",
    }
)
BUILD_FILE_SUFFIXES = (".gradle", ".gradle.kts")
TEST_PATH_PART_NAMES = SOURCE_SET_NAMES | TEST_ROOT_DIR_NAMES | TEST_SUPPORT_DIR_NAMES


class RecoverError(RuntimeError):
    pass


def run_git(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args] if cwd is None else ["git", "-C", str(cwd), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def run_git_checked(args: list[str], *, cwd: Path | None = None) -> str:
    result = run_git(args, cwd=cwd)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        command = " ".join(["git", *(["-C", str(cwd)] if cwd else []), *args])
        raise RecoverError(f"Git command failed: {command}\n{detail}")
    return result.stdout


def normalized_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def derive_repo_name(repo: Path) -> str:
    name = repo.name
    if name.endswith(".git"):
        name = name[: -len(".git")]
    return name or "repo"


def load_manifest(run_dir: Path) -> dict[str, Any]:
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        raise RecoverError(f"run dir is missing manifest.json: {manifest_path}")
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RecoverError(f"manifest.json is invalid JSON: {manifest_path}") from exc


def resolve_artifacts(run_dir: Path) -> tuple[Path, Path | None, Path | None, Path | None]:
    """Locate run artifacts relative to run_dir so a moved run dir still resolves."""
    output_dir = run_dir / "output"
    git_diff_patch = output_dir / "git_diff.patch"
    if not git_diff_patch.is_file():
        raise RecoverError(f"run dir is missing the agent patch: {git_diff_patch}")
    cleared_tests = output_dir / "cleared_tests.json"
    injection_patch = output_dir / "dependency_injection.patch"
    clearing_patch = output_dir / "test_clearing.patch"
    return (
        git_diff_patch,
        cleared_tests if cleared_tests.is_file() else None,
        injection_patch if injection_patch.is_file() else None,
        clearing_patch if clearing_patch.is_file() else None,
    )


def resolve_commit(manifest: dict[str, Any], override: str | None) -> dict[str, Any]:
    if override:
        return {"commit": override, "source": "override"}

    preprocessing = manifest.get("preprocessing") or {}
    reset_git = preprocessing.get("reset_git") or {}
    if reset_git.get("enabled") and reset_git.get("pinned_commit"):
        return {"commit": reset_git["pinned_commit"], "source": "reset_git.pinned_commit"}

    git_baseline = (preprocessing.get("test_clearing") or {}).get("git_baseline") or {}
    if git_baseline.get("original_head"):
        return {
            "commit": git_baseline["original_head"],
            "source": "test_clearing.git_baseline.original_head",
        }

    top_baseline = preprocessing.get("git_baseline") or {}
    if top_baseline.get("original_head"):
        return {
            "commit": top_baseline["original_head"],
            "source": "git_baseline.original_head",
        }

    raise RecoverError(
        "Could not determine the original commit from manifest.json. "
        "Pass --commit to specify it explicitly."
    )


def collect_caveats(manifest: dict[str, Any]) -> list[str]:
    caveats: list[str] = []
    preprocessing = manifest.get("preprocessing") or {}
    reset_git = preprocessing.get("reset_git") or {}
    test_clearing = preprocessing.get("test_clearing") or {}

    if not test_clearing.get("enabled"):
        caveats.append(
            "Test clearing was not enabled for this run: the patch baseline is the "
            "staged worktree rather than a testless tree, so collisions are unexpected "
            "but the patch may still touch files present in the clone."
        )
    if not reset_git.get("enabled"):
        caveats.append(
            "Git reset was not enabled for this run: the patch baseline may include "
            "uncommitted source changes, so a clean clone at the recorded commit can "
            "diverge and non-test hunks may fail to apply."
        )
    return caveats


def is_test_path(path: str) -> bool:
    parts = PurePosixPath(path).parts
    if not parts:
        return False
    if TEST_FILE_PATTERN.fullmatch(parts[-1]):
        return True
    return any(normalized_name(part) in TEST_PATH_PART_NAMES for part in parts)


def is_build_path(path: str) -> bool:
    name = PurePosixPath(path).name
    if name in BUILD_FILE_NAMES:
        return True
    return any(name.endswith(suffix) for suffix in BUILD_FILE_SUFFIXES)


def classify_path(path: str) -> str:
    if is_test_path(path):
        return "test"
    if is_build_path(path):
        return "build"
    return "production"


def parse_apply_summary(patch_output: str) -> dict[str, list[str]]:
    """Parse `git apply --summary` into created/deleted/other path buckets."""
    created: list[str] = []
    deleted: list[str] = []
    other: list[str] = []
    for raw_line in patch_output.splitlines():
        line = raw_line.strip()
        if line.startswith("create mode "):
            # "create mode 100644 <path>"
            created.append(line.split(" ", 3)[3])
        elif line.startswith("delete mode "):
            deleted.append(line.split(" ", 3)[3])
        elif line.startswith(("rename ", "copy ", "mode change ", "rewrite ")):
            other.append(line)
    return {"created": created, "deleted": deleted, "other": other}


def parse_numstat(numstat_output: str) -> list[str]:
    """Return every path touched by the patch (rename arrows collapsed to the target)."""
    paths: list[str] = []
    for raw_line in numstat_output.splitlines():
        fields = raw_line.split("\t")
        if len(fields) != 3:
            continue
        path = fields[2]
        # Renames render as "old => new" or "dir/{old => new}/file"; keep the target.
        if "=>" in path:
            path = path.replace("{", "").replace("}", "")
            path = path.split("=>", 1)[1].strip().replace("//", "/")
        paths.append(path)
    return paths


def load_cleared_paths(cleared_tests_path: Path | None) -> list[dict[str, str]]:
    if cleared_tests_path is None:
        return []
    try:
        payload = json.loads(cleared_tests_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    removed = payload.get("removed")
    if not isinstance(removed, list):
        return []
    return [
        {"path": item["path"], "kind": item.get("kind", "file")}
        for item in removed
        if isinstance(item, dict) and "path" in item
    ]


def matches_cleared(path: str, cleared_paths: list[dict[str, str]]) -> bool:
    for entry in cleared_paths:
        cleared = entry["path"]
        if entry.get("kind") == "directory":
            if path == cleared or path.startswith(cleared.rstrip("/") + "/"):
                return True
        elif path == cleared:
            return True
    return False


def clone_and_checkout(repo: Path, commit: str, dest: Path) -> None:
    if dest.exists():
        raise RecoverError(f"recovery target already exists: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    # A full (non-shallow) clone of the local repo carries every reachable commit,
    # so the recorded commit is present even if it is not the tip of any branch.
    run_git_checked(["clone", "--no-checkout", str(repo), str(dest)])
    result = run_git(["checkout", "--force", commit], cwd=dest)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RecoverError(
            f"Failed to checkout commit {commit} in {repo}:\n{detail}"
        )


def replay_patch(
    repo: Path,
    patch_path: Path | None,
    name: str,
    *,
    allow_whitespace_fallback: bool = False,
) -> dict[str, Any]:
    """Replay a preprocessing patch (recorded against the original tree) onto the
    clone before the agent patch, so the clone matches the run's baseline."""
    if patch_path is None:
        return {"applied": False, "reason": f"no {name}"}
    if patch_path.stat().st_size == 0:
        return {"applied": False, "reason": "empty patch", "patch": str(patch_path)}
    strict = run_git(["apply", "--index", str(patch_path)], cwd=repo)
    if strict.returncode == 0:
        return {"applied": True, "apply_mode": "strict", "patch": str(patch_path)}
    strict_stderr = (strict.stderr or strict.stdout).strip()
    if allow_whitespace_fallback:
        fallback = run_git(
            ["apply", "--index", "--ignore-whitespace", str(patch_path)], cwd=repo
        )
        if fallback.returncode == 0:
            return {
                "applied": True,
                "apply_mode": "ignore-whitespace",
                "reason": "strict apply failed; applied with --ignore-whitespace",
                "strict_stderr": strict_stderr,
                "patch": str(patch_path),
            }
    return {
        "applied": False,
        "reason": "apply failed",
        "apply_mode": "strict",
        "stderr": strict_stderr,
        "patch": str(patch_path),
    }


def apply_patch(
    repo: Path, patch_path: Path, collisions: list[str]
) -> dict[str, Any]:
    # Agent wins: drop the original file at every colliding path so the patch's
    # creation hunks apply onto a clean slot.
    for path in collisions:
        run_git(["rm", "--force", "--", path], cwd=repo)

    clean = run_git(["apply", "--index", str(patch_path)], cwd=repo)
    if clean.returncode == 0:
        return {"status": "clean", "rejected_files": [], "stderr": ""}

    # Fall back to a worktree-only apply that salvages what it can and records the
    # rejected hunks instead of leaving an empty recovery.
    partial = run_git(["apply", "--reject", str(patch_path)], cwd=repo)
    rejected = sorted(str(p.relative_to(repo)) for p in repo.rglob("*.rej"))
    return {
        "status": "clean" if partial.returncode == 0 else "partial",
        "rejected_files": rejected,
        "stderr": (clean.stderr or clean.stdout).strip(),
    }


def build_recovery_manifest(
    *,
    run_dir: Path,
    repo: Path,
    repo_dir: Path,
    commit_info: dict[str, Any],
    created: list[str],
    deleted: list[str],
    touched: list[str],
    collisions: list[dict[str, Any]],
    apply_result: dict[str, Any],
    clearing_result: dict[str, Any],
    injection_result: dict[str, Any],
    caveats: list[str],
) -> dict[str, Any]:
    non_test = sorted(p for p in touched if classify_path(p) != "test")
    return {
        "created_at": dt.datetime.now(dt.UTC).isoformat(),
        "run_dir": str(run_dir),
        "repo": str(repo),
        "repo_dir": str(repo_dir),
        "commit": commit_info["commit"],
        "commit_source": commit_info["source"],
        "base_source": "local-clone",
        "collision_policy": "agent-wins",
        "test_clearing": clearing_result,
        "dependency_injection": injection_result,
        "apply_status": apply_result["status"],
        "rejected_files": apply_result["rejected_files"],
        "apply_error": apply_result["stderr"],
        "counts": {
            "created": len(created),
            "deleted": len(deleted),
            "touched": len(touched),
            "collisions": len(collisions),
            "non_test_touched": len(non_test),
        },
        "created_files": sorted(created),
        "deleted_files": sorted(deleted),
        "collisions": collisions,
        "non_test_touched": [
            {"path": path, "classification": classify_path(path)} for path in non_test
        ],
        "caveats": caveats,
    }


def write_recovery_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def recover(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir.expanduser().resolve()
    if not run_dir.is_dir():
        raise RecoverError(f"--run-dir is not a directory: {run_dir}")

    repo = args.repo.expanduser().resolve()
    if not repo.is_dir():
        raise RecoverError(f"--repo is not a directory: {repo}")

    manifest = load_manifest(run_dir)
    git_diff_patch, cleared_tests_path, injection_patch_path, clearing_patch_path = (
        resolve_artifacts(run_dir)
    )
    commit_info = resolve_commit(manifest, args.commit)
    caveats = collect_caveats(manifest)

    output_parent = (
        args.output_dir.expanduser().resolve()
        if args.output_dir
        else run_dir / "recovered"
    )
    repo_name = derive_repo_name(repo)
    repo_dir = output_parent / repo_name

    clone_and_checkout(repo, commit_info["commit"], repo_dir)

    # Replay the recorded test deletions first so the clone matches the testless
    # baseline the agent diffed against; otherwise original tests the agent never
    # recreated (e.g. UI suites) silently survive into the recovery.
    clearing_result = replay_patch(
        repo_dir,
        clearing_patch_path,
        "test_clearing.patch",
        allow_whitespace_fallback=True,
    )
    test_clearing = (manifest.get("preprocessing") or {}).get("test_clearing") or {}
    if test_clearing.get("enabled") and not clearing_result["applied"]:
        caveats.append(
            f"test_clearing.patch was not replayed ({clearing_result['reason']}): "
            "original test files the agent did not recreate may survive in the "
            "recovered repo (see recovery_manifest.json test_clearing)."
        )

    # Replay the injected build-file change next; the agent patch lands on top.
    injection_result = replay_patch(
        repo_dir, injection_patch_path, "dependency_injection.patch"
    )
    if injection_patch_path is not None and not injection_result["applied"]:
        caveats.append(
            "dependency_injection.patch did not apply: the recovered repo lacks the "
            "injected RestAssured dependency, so the agent's RestAssured tests may not "
            "compile (see recovery_manifest.json dependency_injection)."
        )

    summary = parse_apply_summary(
        run_git_checked(["apply", "--summary", str(git_diff_patch)], cwd=repo_dir)
    )
    touched = parse_numstat(
        run_git_checked(["apply", "--numstat", str(git_diff_patch)], cwd=repo_dir)
    )

    cleared_paths = load_cleared_paths(cleared_tests_path)
    collisions = []
    for path in summary["created"]:
        if (repo_dir / path).exists():
            collisions.append(
                {"path": path, "expected_cleared": matches_cleared(path, cleared_paths)}
            )

    apply_result = apply_patch(
        repo_dir, git_diff_patch, [c["path"] for c in collisions]
    )

    recovery_manifest = build_recovery_manifest(
        run_dir=run_dir,
        repo=repo,
        repo_dir=repo_dir,
        commit_info=commit_info,
        created=summary["created"],
        deleted=summary["deleted"],
        touched=touched,
        collisions=collisions,
        apply_result=apply_result,
        clearing_result=clearing_result,
        injection_result=injection_result,
        caveats=caveats,
    )
    write_recovery_manifest(
        output_parent / "recovery_manifest.json", recovery_manifest
    )
    return recovery_manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Recover an agent's generated tests into the full repository structure "
            "by cloning the original repo and applying the run's git_diff.patch."
        )
    )
    parser.add_argument(
        "--run-dir",
        required=True,
        type=Path,
        help="Completed run directory containing manifest.json and output/git_diff.patch.",
    )
    parser.add_argument(
        "--repo",
        required=True,
        type=Path,
        help=(
            "Path to the original cloned repository (the same checkout passed to the "
            "run's --input-dir). Its recorded commit is checked out into a fresh clone "
            "and the agent patch is applied onto that full tree."
        ),
    )
    parser.add_argument(
        "--commit",
        help=(
            "Commit to checkout before applying the patch. Defaults to the run's "
            "pinned/original commit recorded in manifest.json."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Parent directory for the recovered repo. Defaults to <run-dir>/recovered.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        manifest = recover(args)
    except RecoverError as exc:
        parser.exit(2, f"error: {exc}\n")
    except KeyboardInterrupt:
        parser.exit(130, "interrupted\n")
        return 130

    print(f"[recover] repo_dir={manifest['repo_dir']}", flush=True)
    print(
        "[recover] "
        f"commit={manifest['commit']} ({manifest['commit_source']}) "
        f"apply={manifest['apply_status']}",
        flush=True,
    )
    for replay_name in ("test_clearing", "dependency_injection"):
        replay = manifest[replay_name]
        if replay.get("applied") or replay.get("reason") != f"no {replay_name}.patch":
            print(
                "[recover] "
                f"{replay_name} applied={replay.get('applied')} "
                f"{replay.get('reason', '')}".rstrip(),
                flush=True,
            )
    counts = manifest["counts"]
    print(
        "[recover] "
        f"created={counts['created']} collisions={counts['collisions']} "
        f"non_test_touched={counts['non_test_touched']}",
        flush=True,
    )
    for caveat in manifest["caveats"]:
        print(f"[recover] caveat: {caveat}", flush=True)
    if manifest["non_test_touched"]:
        print(
            "[recover] warning: patch touches non-test paths "
            "(see recovery_manifest.json non_test_touched)",
            flush=True,
        )
    return 0 if manifest["apply_status"] == "clean" else 1


if __name__ == "__main__":
    sys.exit(main())
