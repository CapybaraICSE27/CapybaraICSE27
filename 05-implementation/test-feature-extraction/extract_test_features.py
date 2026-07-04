#!/usr/bin/env python3
"""
Phase 2 UI Test Feature Extraction Orchestrator

Reads merged Phase 1 all_ui_test_files.jsonl, groups by repo, calls Node/ts-morph
analyzer per repo, merges test-case-level JSONL/CSV outputs.
"""

from __future__ import annotations

import argparse
import csv
import concurrent.futures
import datetime as _dt
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

DEFAULT_INPUT = Path(
    r"<study-root>"
    r"\github_pilot_census_output\typescript__2026-05-10_09-57-24__min500stars"
    r"\ui_file_inventory_final\all_ui_test_files.jsonl"
)
DEFAULT_REPO_CACHE = Path(r"<repo-cache>")

# Bump when output schema or merge semantics change (invalidates per-repo caches).
PHASE2_SCHEMA_VERSION = 43
# 2C may reuse frozen 2AB artifacts across schema bumps that only affect expansion
# logic, but only when the cached direct-feature schema has M3 Phase 2B fields.
MIN_2AB_REUSE_SCHEMA_VERSION = 33


def _timestamp() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _format_elapsed(started: float | None) -> str:
    if started is None:
        return ""
    elapsed = max(0.0, time.monotonic() - started)
    minutes, seconds = divmod(int(elapsed), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f" elapsed={hours:d}h{minutes:02d}m{seconds:02d}s"
    if minutes:
        return f" elapsed={minutes:d}m{seconds:02d}s"
    return f" elapsed={seconds:d}s"


def log_progress(message: str, *, started: float | None = None) -> None:
    print(f"[{_timestamp()}] {message}{_format_elapsed(started)}", file=sys.stderr, flush=True)


def safe_repo_dir(full_name: str) -> str:
    return full_name.replace("/", "__").replace(":", "_")


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def repo_file_list_hash(files: List[Dict[str, Any]]) -> str:
    parts = sorted(f"{r.get('file_path','')}|{r.get('commit','')}" for r in files)
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:32]


def _hash_js_dependency_roots(lib_roots: Iterable[Path], root: Path) -> str:
    h = hashlib.sha256()
    for lib in lib_roots:
        if not lib.is_dir():
            continue
        for path in sorted(lib.rglob("*.js")):
            try:
                rel = path.relative_to(root).as_posix()
                h.update(rel.encode("utf-8"))
                h.update(b"\0")
                with path.open("rb") as f:
                    for chunk in iter(lambda: f.read(1024 * 1024), b""):
                        h.update(chunk)
                h.update(b"\0")
            except OSError:
                continue
    return h.hexdigest()[:16]


def _analyzer_lib_roots(*names: str) -> List[Path]:
    root = Path(__file__).resolve().parent
    return [root / "lib" / name for name in names]


def _analyzer_direct_dependency_hash() -> str:
    root = Path(__file__).resolve().parent
    return _hash_js_dependency_roots(_analyzer_lib_roots("phase2a", "phase2b", "shared"), root)


def _analyzer_expansion_dependency_hash() -> str:
    root = Path(__file__).resolve().parent
    return _hash_js_dependency_roots(_analyzer_lib_roots("phase2b", "phase2c", "shared"), root)


def _analyzer_dependency_hash() -> str:
    """Combined analyzer hash retained for metadata/audit readability."""
    root = Path(__file__).resolve().parent
    lib_roots = [
        root / "lib" / "phase2a",
        root / "lib" / "phase2b",
        root / "lib" / "phase2c",
        root / "lib" / "shared",
    ]
    return _hash_js_dependency_roots(lib_roots, root)


def analyzer_fingerprint(analyzer_path: Path) -> Dict[str, Any]:
    base = {
        "analyzer_dependency_hash": _analyzer_dependency_hash(),
        "analyzer_direct_dependency_hash": _analyzer_direct_dependency_hash(),
        "analyzer_expansion_dependency_hash": _analyzer_expansion_dependency_hash(),
    }
    try:
        st = analyzer_path.stat()
        return {
            **base,
            "analyzer_path": str(analyzer_path.resolve()),
            "analyzer_mtime_ns": st.st_mtime_ns,
            "analyzer_size": st.st_size,
            "analyzer_entrypoint_sha256": file_sha256(analyzer_path),
        }
    except OSError:
        return {
            **base,
            "analyzer_path": str(analyzer_path.resolve()),
            "analyzer_mtime_ns": None,
            "analyzer_size": None,
            "analyzer_entrypoint_sha256": None,
        }


def input_manifest_fingerprint(input_jsonl: Path) -> Dict[str, Any]:
    try:
        st = input_jsonl.stat()
        return {
            "input_jsonl": str(input_jsonl.resolve()),
            "input_jsonl_mtime_ns": st.st_mtime_ns,
            "input_jsonl_size": st.st_size,
            "input_jsonl_sha256": file_sha256(input_jsonl),
        }
    except OSError:
        return {
            "input_jsonl": str(input_jsonl.resolve()),
            "input_jsonl_mtime_ns": None,
            "input_jsonl_size": None,
            "input_jsonl_sha256": None,
        }


def write_per_repo_meta(
    meta_path: Path,
    analyzer_fp: Dict[str, Any],
    input_fp: Dict[str, Any],
    repo_hash: str,
    subphase: str,
    max_helper_depth: int,
    max_helper_files: int,
) -> None:
    payload = {
        **analyzer_fp,
        **input_fp,
        "repo_file_list_hash": repo_hash,
        "subphase": subphase,
        "max_helper_depth": max_helper_depth,
        "max_helper_files": max_helper_files,
        "phase2_schema_version": PHASE2_SCHEMA_VERSION,
    }
    meta_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def write_split_per_repo_result(out_json: Path, result: Dict[str, Any]) -> None:
    """Write a split_v1 per-repo result from Python, matching repoOutputWriter.js."""
    arrays = {
        "test_cases": result.get("test_cases") or [],
        "bdd_step_definitions": result.get("bdd_step_definitions") or [],
        "features_direct": result.get("features_direct") or [],
        "features_expanded": result.get("features_expanded") or [],
        "helper_edges": result.get("helper_edges") or [],
        "unresolved_calls": result.get("unresolved_calls") or [],
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    for suffix, rows in arrays.items():
        write_jsonl(per_repo_sidecar_path(out_json, suffix), rows)

    index = {
        "repo": result.get("repo"),
        "repo_url": result.get("repo_url"),
        "commit": result.get("commit"),
        "analyzed_commit": result.get("analyzed_commit"),
        "commit_pin_match": result.get("commit_pin_match"),
        "subphases_run": result.get("subphases_run") or [],
        "storage_format": "split_v1",
        "summary": result.get("summary") or {},
        "parse_errors": result.get("parse_errors") or [],
        "counts": {key: len(rows) for key, rows in arrays.items()},
    }
    out_json.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")


def read_jsonl_file(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def per_repo_sidecar_path(out_json: Path, suffix: str) -> Path:
    stem = out_json.name[: -len(".json")] if out_json.name.endswith(".json") else out_json.stem
    return out_json.parent / f"{stem}.{suffix}.jsonl"


def load_per_repo_result(out_json: Path, sidecars: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """Load monolithic per-repo JSON or split_v1 index + sidecar JSONL files."""
    data = json.loads(out_json.read_text(encoding="utf-8"))
    if data.get("storage_format") != "split_v1":
        return data
    loaded = dict(data)
    suffixes = tuple(sidecars) if sidecars is not None else (
        "test_cases",
        "bdd_step_definitions",
        "features_direct",
        "features_expanded",
        "helper_edges",
        "unresolved_calls",
    )
    for suffix in suffixes:
        loaded[suffix] = read_jsonl_file(per_repo_sidecar_path(out_json, suffix))
    return loaded


def split_per_repo_artifacts_ok(out_json: Path) -> bool:
    if not out_json.exists():
        return False
    try:
        data = json.loads(out_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if data.get("storage_format") != "split_v1":
        return True
    return per_repo_sidecar_path(out_json, "test_cases").exists()


def load_per_repo_meta(meta_path: Path) -> Optional[Dict[str, Any]]:
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def commits_match(actual: str, target: str) -> bool:
    """Compare two commit refs (SHA prefixes). Empty target matches anything (pin skip)."""
    actual = (actual or "").strip()
    target = (target or "").strip()
    if not target:
        return True
    if not actual:
        return False
    if actual == target:
        return True
    if len(target) >= 7 and len(actual) >= 7:
        return actual[:7].lower() == target[:7].lower()
    return actual.startswith(target) or target.startswith(actual)


def resolve_merge_commit_target(
    manifest_commit: str,
    repo: str,
    repo_cache: Optional[Path],
) -> Optional[str]:
    """
  Resolve the commit a per-repo cache must match for global merge.
  Manifest HEAD is resolved to the current HEAD of the local clone when available.
  """
    mc = (manifest_commit or "").strip() or "HEAD"
    if mc != "HEAD":
        return mc
    if repo_cache is None:
        return None
    local = repo_cache / safe_repo_dir(repo)
    if not local.exists():
        return None
    head = git_head_commit(local)
    if not head or head == "HEAD":
        return None
    return head


def _analyzer_dependency_hashes_valid(
    meta: Dict[str, Any],
    analyzer_fp: Dict[str, Any],
    *,
    cached_subphase: str,
) -> bool:
    if meta.get("analyzer_direct_dependency_hash") != analyzer_fp.get("analyzer_direct_dependency_hash"):
        return False
    if cached_subphase in ("2c", "all"):
        if meta.get("analyzer_expansion_dependency_hash") != analyzer_fp.get("analyzer_expansion_dependency_hash"):
            return False
    return True


def _analyzer_entrypoint_valid(meta: Dict[str, Any], analyzer_fp: Dict[str, Any]) -> bool:
    cached_hash = meta.get("analyzer_entrypoint_sha256")
    current_hash = analyzer_fp.get("analyzer_entrypoint_sha256")
    if cached_hash and current_hash:
        return cached_hash == current_hash
    for key in ("analyzer_path", "analyzer_mtime_ns", "analyzer_size"):
        if meta.get(key) != analyzer_fp.get(key):
            return False
    return True


def _compatible_2ab_for_2c(
    *,
    result: Dict[str, Any],
    meta: Dict[str, Any],
    analyzer_fp: Dict[str, Any],
    input_fp: Dict[str, Any],
    repo_hash: str,
    cached_schema: int,
    subphase: str,
    cached_subphase: str,
    max_helper_depth: int,
    max_helper_files: int,
) -> bool:
    if subphase != "2c" or cached_subphase != "2ab":
        return False
    if not result.get("test_cases") or not result.get("features_direct"):
        return False
    if cached_schema < MIN_2AB_REUSE_SCHEMA_VERSION:
        return False
    if not _analyzer_entrypoint_valid(meta, analyzer_fp):
        return False
    if meta.get("analyzer_direct_dependency_hash") != analyzer_fp.get("analyzer_direct_dependency_hash"):
        return False
    for key in ("input_jsonl", "input_jsonl_mtime_ns", "input_jsonl_size", "input_jsonl_sha256"):
        if meta.get(key) != input_fp.get(key):
            return False
    if meta.get("repo_file_list_hash") != repo_hash:
        return False
    return True


def cache_validity(
    out_json: Path,
    meta_path: Path,
    analyzer_fp: Dict[str, Any],
    input_fp: Dict[str, Any],
    repo_hash: str,
    subphase: str,
    max_helper_depth: int,
    max_helper_files: int,
    sidecars: Optional[Iterable[str]] = None,
) -> Tuple[Optional[Dict[str, Any]], str]:
    if not out_json.exists():
        return None, "missing_json"
    if not split_per_repo_artifacts_ok(out_json):
        return None, "missing_split_sidecars"
    try:
        result = load_per_repo_result(out_json, sidecars=sidecars)
    except (OSError, json.JSONDecodeError):
        return None, "corrupt_json"
    if not isinstance(result, dict):
        return None, "corrupt_json"

    meta = load_per_repo_meta(meta_path)
    if meta is None:
        return None, "missing_meta"

    meta_sub = str(meta.get("subphase") or "")
    cached_schema = int(meta.get("phase2_schema_version", 0))

    if _compatible_2ab_for_2c(
        result=result,
        meta=meta,
        analyzer_fp=analyzer_fp,
        input_fp=input_fp,
        repo_hash=repo_hash,
        cached_schema=cached_schema,
        subphase=subphase,
        cached_subphase=meta_sub,
        max_helper_depth=max_helper_depth,
        max_helper_files=max_helper_files,
    ):
        return result, "reuse_2ab_for_2c"

    if not _analyzer_entrypoint_valid(meta, analyzer_fp):
        return None, "stale_analyzer"
    if not _analyzer_dependency_hashes_valid(meta, analyzer_fp, cached_subphase=meta_sub):
        return None, "stale_analyzer"

    for key in ("input_jsonl", "input_jsonl_mtime_ns", "input_jsonl_size", "input_jsonl_sha256"):
        if meta.get(key) != input_fp.get(key):
            return None, "stale_input"

    if meta.get("repo_file_list_hash") != repo_hash:
        return None, "stale_repo_manifest"

    if cached_schema != PHASE2_SCHEMA_VERSION:
        return None, "stale_schema_version"

    if meta_sub != subphase:
        return None, "stale_subphase"

    if int(meta.get("max_helper_depth", -1)) != max_helper_depth:
        return None, "stale_helper_config"
    if int(meta.get("max_helper_files", -1)) != max_helper_files:
        return None, "stale_helper_config"

    return result, "ok"


def run(cmd: List[str], check: bool = True, timeout: Optional[int] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
        timeout=timeout,
    )


def is_git_repo(repo_path: Path) -> bool:
    try:
        cp = run(["git", "-C", str(repo_path), "rev-parse", "--git-dir"], check=False, timeout=30)
        return cp.returncode == 0
    except Exception:
        return False


def git_head_commit(repo_path: Path) -> str:
    try:
        return run(["git", "-C", str(repo_path), "rev-parse", "HEAD"], check=True).stdout.strip()
    except Exception:
        return "HEAD"


def git_commit_exists(repo_path: Path, commit: str) -> bool:
    target = (commit or "").strip()
    if not target or target == "HEAD":
        return False
    try:
        cp = run(["git", "-C", str(repo_path), "cat-file", "-e", f"{target}^{{commit}}"], check=False, timeout=30)
        return cp.returncode == 0
    except Exception:
        return False


def git_resolve_commit(repo_path: Path, commit: str) -> str:
    target = (commit or "").strip()
    if not target or target == "HEAD":
        return git_head_commit(repo_path)
    try:
        return run(
            ["git", "-C", str(repo_path), "rev-parse", "--verify", f"{target}^{{commit}}"],
            check=True,
            timeout=30,
        ).stdout.strip()
    except Exception:
        return ""


def fetch_manifest_commit(local: Path, target: str, *, try_unshallow: bool = False) -> None:
    """Try to make `target` available in the local clone without mutating HEAD."""
    try:
        run(["git", "-C", str(local), "fetch", "origin", target, "--depth", "1"], check=False, timeout=120)
    except Exception:
        pass
    try:
        run(["git", "-C", str(local), "fetch", "origin", target, "--depth", "50"], check=False, timeout=180)
    except Exception:
        pass
    try:
        run(["git", "-C", str(local), "fetch", "origin", "--depth", "200"], check=False, timeout=180)
    except Exception:
        pass
    if try_unshallow:
        try:
            is_shallow = run(
                ["git", "-C", str(local), "rev-parse", "--is-shallow-repository"],
                check=False,
            ).stdout.strip()
            if is_shallow == "true":
                run(["git", "-C", str(local), "fetch", "--unshallow"], check=False, timeout=600)
        except Exception:
            pass


def archive_member_should_skip(name: str) -> bool:
    parts = [part for part in name.replace("\\", "/").split("/") if part]
    return "node_modules" in parts


def extract_archive_without_ignored_paths(tar_path: Path, destination: Path) -> None:
    destination_root = destination.resolve(strict=False)
    with tarfile.open(tar_path, "r:*") as archive:
        for member in archive:
            if archive_member_should_skip(member.name):
                continue
            target = (destination / member.name).resolve(strict=False)
            try:
                target.relative_to(destination_root)
            except ValueError as exc:
                raise RuntimeError(f"Unsafe archive member path: {member.name}") from exc
            try:
                archive.extract(member, destination, filter="fully_trusted")
            except TypeError:
                archive.extract(member, destination)


def archive_commit_to_scratch(
    local: Path,
    manifest_commit: str,
    scratch_root: Path,
    repo: str,
    *,
    timeout_seconds: int = 900,
) -> Tuple[Path, str, bool]:
    """Materialize a pinned commit in scratch without creating a Git worktree."""
    target = (manifest_commit or "").strip()
    actual_head = git_head_commit(local)
    if not target or target == "HEAD":
        return local, actual_head, True

    log_progress(f"pin archive {repo}: resolve target={target[:12]}")
    if not git_commit_exists(local, target):
        log_progress(f"pin archive {repo}: fetch target={target[:12]} depth=standard")
        fetch_manifest_commit(local, target)
    actual = git_resolve_commit(local, target)
    if not actual:
        log_progress(f"pin archive {repo}: fetch target={target[:12]} depth=unshallow")
        fetch_manifest_commit(local, target, try_unshallow=True)
        actual = git_resolve_commit(local, target)
    if not actual:
        log_progress(f"pin archive {repo}: failed unresolved target={target[:12]} actual_head={actual_head[:12]}")
        return local, actual_head, False

    token = actual[:12] or target.replace("/", "_")[:12] or "HEAD"
    staged = scratch_root / safe_repo_dir(repo) / token
    archive_path = staged.parent / f".{token}.archive.tar"
    if staged.exists():
        shutil.rmtree(staged, ignore_errors=True)
    staged.parent.mkdir(parents=True, exist_ok=True)
    if archive_path.exists():
        archive_path.unlink()

    try:
        log_progress(f"pin archive {repo}: archive write started commit={actual[:12]}")
        run(
            ["git", "-C", str(local), "archive", "--format=tar", "--output", str(archive_path), actual],
            check=True,
            timeout=timeout_seconds,
        )
        log_progress(f"pin archive {repo}: extract started path={staged}")
        staged.mkdir(parents=True, exist_ok=True)
        extract_archive_without_ignored_paths(archive_path, staged)
        log_progress(f"pin archive {repo}: ready commit={actual[:12]} path={staged}")
        return staged, actual, commits_match(actual, target)
    except Exception as exc:
        log_progress(f"pin archive {repo}: failed materialization target={target[:12]} reason={type(exc).__name__}")
        shutil.rmtree(staged, ignore_errors=True)
        return local, actual_head, False
    finally:
        try:
            archive_path.unlink()
        except FileNotFoundError:
            pass


def prepare_analysis_repo(
    local: Path,
    manifest_commit: str,
    pin: bool,
) -> Tuple[Path, str, bool, Optional[Path]]:
    """
    Return a repo path for analysis without mutating the shared cache checkout.
    Uses a detached git worktree when pinning is requested and commits differ.
    """
    actual = git_head_commit(local)
    target = (manifest_commit or "").strip()
    if not pin or not target or target == "HEAD":
        return local, actual, True, None
    if commits_match(actual, target):
        return local, actual, True, None

    if not git_commit_exists(local, target):
        fetch_manifest_commit(local, target)
    wt_root = local.parent / ".phase2_worktrees" / safe_repo_dir(local.name)
    wt_root.mkdir(parents=True, exist_ok=True)
    wt_path = wt_root / target[:12]
    cleanup_worktree_slot(local, wt_path)

    def try_worktree() -> bool:
        try:
            run(
                ["git", "-C", str(local), "worktree", "add", "--detach", str(wt_path), target],
                check=True,
                timeout=300,
            )
            return True
        except Exception:
            return False

    if try_worktree():
        actual = git_head_commit(wt_path)
        return wt_path, actual, commits_match(actual, target), wt_path

    if not git_commit_exists(local, target):
        fetch_manifest_commit(local, target, try_unshallow=True)
    cleanup_worktree_slot(local, wt_path)
    if try_worktree():
        actual = git_head_commit(wt_path)
        return wt_path, actual, commits_match(actual, target), wt_path

    return local, actual, False, None


def cleanup_worktree_slot(local: Path, worktree_path: Path) -> None:
    if is_generated_phase2_worktree_path(local, worktree_path) and not (worktree_path / ".git").exists():
        if worktree_path.exists():
            shutil.rmtree(worktree_path, ignore_errors=True)
        remove_stale_generated_worktree_metadata(local, worktree_path)
        prune_worktrees(local)
        return
    try:
        run(["git", "-C", str(local), "worktree", "unlock", str(worktree_path)], check=False, timeout=60)
    except Exception:
        pass
    try:
        run(["git", "-C", str(local), "worktree", "remove", "--force", str(worktree_path)], check=False, timeout=600)
    except Exception:
        pass
    try:
        run(
            ["git", "-C", str(local), "worktree", "remove", "--force", "--force", str(worktree_path)],
            check=False,
            timeout=600,
        )
    except Exception:
        pass
    if worktree_path.exists():
        shutil.rmtree(worktree_path, ignore_errors=True)
    remove_stale_generated_worktree_metadata(local, worktree_path)
    prune_worktrees(local)


def prune_worktrees(local: Path) -> None:
    try:
        run(["git", "-C", str(local), "worktree", "prune", "--expire=now"], check=False, timeout=300)
    except Exception:
        pass


def is_generated_phase2_worktree_path(local: Path, worktree_path: Path) -> bool:
    try:
        generated_root = (local.parent / ".phase2_worktrees").resolve(strict=False)
        resolved_worktree = worktree_path.resolve(strict=False)
        resolved_worktree.relative_to(generated_root)
        return True
    except Exception:
        return False


def remove_stale_generated_worktree_metadata(
    local: Path,
    worktree_path: Path,
    *,
    allow_existing: bool = False,
) -> bool:
    """Remove Git admin metadata for missing generated Phase 2 worktrees only."""
    if not is_generated_phase2_worktree_path(local, worktree_path):
        return False
    if worktree_path.exists() and not allow_existing:
        return False
    resolved_worktree = worktree_path.resolve(strict=False)
    try:
        common_dir_raw = run(
            ["git", "-C", str(local), "rev-parse", "--git-common-dir"],
            check=True,
            timeout=30,
        ).stdout.strip()
    except Exception:
        return False
    common_dir = Path(common_dir_raw)
    if not common_dir.is_absolute():
        common_dir = local / common_dir
    admin_root = common_dir / "worktrees"
    if not admin_root.is_dir():
        return False
    expected_gitdir = (resolved_worktree / ".git").resolve(strict=False)
    for admin_dir in admin_root.iterdir():
        gitdir_file = admin_dir / "gitdir"
        if not gitdir_file.is_file():
            continue
        try:
            recorded = Path(gitdir_file.read_text(encoding="utf-8").strip()).resolve(strict=False)
        except Exception:
            continue
        if recorded == expected_gitdir:
            shutil.rmtree(admin_dir, ignore_errors=True)
            return True
    return False


def move_generated_worktree_aside(local: Path, worktree_path: Path) -> bool:
    if not is_generated_phase2_worktree_path(local, worktree_path):
        return False
    remove_stale_generated_worktree_metadata(local, worktree_path, allow_existing=True)
    if worktree_path.exists():
        for attempt in range(10):
            suffix = f".delete-{int(time.time())}-{attempt}"
            tombstone = worktree_path.with_name(worktree_path.name + suffix)
            if tombstone.exists():
                continue
            try:
                worktree_path.rename(tombstone)
                break
            except OSError:
                if attempt == 9:
                    shutil.rmtree(worktree_path, ignore_errors=True)
    prune_worktrees(local)
    return True


def remove_analysis_worktree(local: Path, worktree_path: Optional[Path]) -> None:
    if not worktree_path:
        return
    if move_generated_worktree_aside(local, worktree_path):
        return
    try:
        run(["git", "-C", str(local), "worktree", "remove", "--force", str(worktree_path)], check=False, timeout=600)
    except Exception:
        shutil.rmtree(worktree_path, ignore_errors=True)
    try:
        run(["git", "-C", str(local), "worktree", "prune"], check=False, timeout=300)
    except Exception:
        pass


def stage_analysis_tree(analysis_path: Path, scratch_root: Path, repo: str, commit: str) -> Path:
    """Copy a prepared worktree to scratch so analyzer I/O avoids shared storage."""
    token = (commit or "HEAD").replace("/", "_")[:12] or "HEAD"
    staged = scratch_root / safe_repo_dir(repo) / token
    if staged.exists():
        shutil.rmtree(staged, ignore_errors=True)
    staged.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        analysis_path,
        staged,
        symlinks=True,
        ignore=shutil.ignore_patterns(".git", "node_modules"),
        ignore_dangling_symlinks=True,
    )
    return staged


def remove_staged_analysis_tree(staged_path: Optional[Path]) -> None:
    if not staged_path:
        return
    shutil.rmtree(staged_path, ignore_errors=True)
    try:
        staged_path.parent.rmdir()
    except OSError:
        pass


def clone_repo(full_name: str, html_url: str, cache_dir: Path) -> Tuple[Path, str]:
    import shutil

    dest = cache_dir / safe_repo_dir(full_name)
    if dest.exists() and not is_git_repo(dest):
        quarantine_base = cache_dir / f"{safe_repo_dir(full_name)}.invalid-{int(time.time())}"
        quarantine = quarantine_base
        suffix = 1
        while quarantine.exists():
            quarantine = cache_dir / f"{quarantine_base.name}-{suffix}"
            suffix += 1
        dest.rename(quarantine)
    if not dest.exists():
        clone_url = html_url if html_url.endswith(".git") else html_url.rstrip("/") + ".git"
        run(["git", "clone", "--depth", "1", clone_url, str(dest)], check=True, timeout=900)
    try:
        commit = run(["git", "-C", str(dest), "rev-parse", "HEAD"], check=True).stdout.strip()
    except Exception:
        commit = "HEAD"
    return dest, commit


def _scrub_surrogates(value: Any) -> Any:
    if isinstance(value, str):
        return value.encode("utf-8", "surrogatepass").decode("utf-8", "replace")
    if isinstance(value, dict):
        return {k: _scrub_surrogates(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub_surrogates(v) for v in value]
    return value


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(_scrub_surrogates(row), ensure_ascii=False) + "\n")


def append_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> int:
    n = 0
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(_scrub_surrogates(row), ensure_ascii=False) + "\n")
            n += 1
    return n


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def flatten_test_case(tc: Dict[str, Any]) -> Dict[str, Any]:
    row = dict(tc)
    row["describe_path"] = " > ".join(tc.get("describe_path") or [])
    row["fixtures_used"] = ";".join(tc.get("fixtures_used") or [])
    keys = tc.get("hook_instance_keys") or []
    row["hook_instance_keys"] = ";".join(keys) if isinstance(keys, list) else str(keys)
    return row


def flatten_feature(f: Dict[str, Any]) -> Dict[str, Any]:
    return dict(f)


def aggregate_result(
    result: Dict[str, Any],
    test_cases: List[Dict[str, Any]],
    bdd_step_definitions: List[Dict[str, Any]],
    features_direct: List[Dict[str, Any]],
    features_expanded: List[Dict[str, Any]],
    helper_edges: List[Dict[str, Any]],
    unresolved_calls: List[Dict[str, Any]],
) -> None:
    for tc in result.get("test_cases") or []:
        test_cases.append(tc)
    for row in result.get("bdd_step_definitions") or []:
        bdd_step_definitions.append(row)
    for f in result.get("features_direct") or []:
        features_direct.append(f)
    for f in result.get("features_expanded") or []:
        features_expanded.append(f)
    for e in result.get("helper_edges") or []:
        helper_edges.append(e)
    for u in result.get("unresolved_calls") or []:
        unresolved_calls.append(u)


def filter_inventory_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for r in rows:
        role = str(r.get("file_role") or "test_file").strip().lower()
        conf = str(r.get("confidence") or "high").strip().lower()
        if role != "test_file":
            continue
        if conf not in {"high", "medium"}:
            continue
        out.append(r)
    return out


def expanded_feature_dedupe_key(f: Dict[str, Any]) -> str:
    return "|".join(
        [
            str(f.get("test_id") or ""),
            str(f.get("hook_instance_key") or ""),
            str(f.get("helper_depth") or 0),
            str(f.get("line")),
            str(f.get("feature_type") or ""),
            str(f.get("name") or ""),
            str(f.get("target_file") or ""),
            "hook" if f.get("attached_from_hook") else "",
        ]
    )


def hook_attach_dedupe_key(tid: str, hook_key: str, f: Dict[str, Any]) -> str:
    return expanded_feature_dedupe_key({**f, "test_id": tid, "hook_instance_key": hook_key})


def hook_expansion_was_attempted(key: str, expanded: List[Dict[str, Any]]) -> bool:
    return any(
        f.get("hook_instance_key") == key and (f.get("helper_depth") or 0) > 0
        for f in expanded
    )


def seed_seen_from_expanded(seen: set[str], expanded: List[Dict[str, Any]]) -> None:
    for f in expanded:
        if not f.get("attached_from_hook") or not f.get("test_id"):
            continue
        seen.add(
            hook_attach_dedupe_key(
                str(f["test_id"]),
                str(f.get("hook_instance_key") or ""),
                f,
            )
        )


def attach_hook_features_to_expanded(
    expanded: List[Dict[str, Any]],
    direct: List[Dict[str, Any]],
    test_cases: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Mirror Node attachHookFeaturesToExpanded for merge-time 2ab fallback."""
    if any(f.get("attached_from_hook") for f in expanded):
        return list(expanded)

    hook_by_key: Dict[str, List[Dict[str, Any]]] = {}
    for f in direct:
        if f.get("is_shared_hook_feature") and f.get("hook_instance_key"):
            hook_by_key.setdefault(f["hook_instance_key"], []).append(f)

    out = list(expanded)
    seen: set[str] = set()
    seed_seen_from_expanded(seen, expanded)
    for tc in test_cases:
        tid = tc.get("test_id")
        if not tid:
            continue
        for key in tc.get("hook_instance_keys") or []:
            skip_shallow_custom = hook_expansion_was_attempted(key, expanded)
            for f in hook_by_key.get(key, []):
                if skip_shallow_custom and f.get("feature_type") == "custom_command_call":
                    continue
                dedupe = hook_attach_dedupe_key(str(tid), str(key), f)
                if dedupe in seen:
                    continue
                seen.add(dedupe)
                out.append({
                    **f,
                    "test_id": tid,
                    "helper_depth": f.get("helper_depth", 0),
                    "attached_from_hook": True,
                    "is_shared_hook_feature": False,
                })
    return out


def merge_repo_result_into(
    cached: Dict[str, Any],
    test_cases: List[Dict[str, Any]],
    bdd_step_definitions: List[Dict[str, Any]],
    features_direct: List[Dict[str, Any]],
    features_expanded: List[Dict[str, Any]],
    helper_edges: List[Dict[str, Any]],
    unresolved_calls: List[Dict[str, Any]],
) -> None:
    for tc in cached.get("test_cases") or []:
        test_cases.append(tc)
    for row in cached.get("bdd_step_definitions") or []:
        bdd_step_definitions.append(row)
    for f in cached.get("features_direct") or []:
        features_direct.append(f)
    for e in cached.get("helper_edges") or []:
        helper_edges.append(e)
    for u in cached.get("unresolved_calls") or []:
        unresolved_calls.append(u)

    expanded_base = list(cached.get("features_expanded") or [])
    attached = attach_hook_features_to_expanded(
        expanded_base,
        cached.get("features_direct") or [],
        cached.get("test_cases") or [],
    )
    features_expanded.extend(attached)


@dataclass
class MergeStats:
    test_cases: int = 0
    bdd_step_definitions: int = 0
    features_direct: int = 0
    features_expanded: int = 0
    helper_edges: int = 0
    unresolved_calls: int = 0
    unique_hook_feature_instances: Set[str] = field(default_factory=set)
    unique_hook_feature_instances_from_summary: int = 0
    tests_with_direct_ui_actions: int = 0
    tests_with_hook_ui_actions: int = 0
    tests_with_helper_expanded_ui_actions: int = 0
    tests_with_expanded_ui_actions: int = 0
    medium_confidence_test_cases_with_no_direct_ui_actions: int = 0

    def unique_hook_feature_instances_total(self) -> int:
        return len(self.unique_hook_feature_instances) or self.unique_hook_feature_instances_from_summary


def executable_test_cases_from(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        t
        for t in rows
        if t.get("record_type", "test_case") == "test_case"
        and t.get("test_declaration_type") != "bdd_step"
    ]


def legacy_bdd_from(test_cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        t
        for t in test_cases
        if t.get("test_declaration_type") == "bdd_step" or t.get("record_type") == "bdd_step_definition"
    ]


def update_merge_stats_from_test_cases(stats: MergeStats, executable: List[Dict[str, Any]]) -> None:
    stats.test_cases += len(executable)
    for tc in executable:
        if tc.get("has_direct_ui_actions"):
            stats.tests_with_direct_ui_actions += 1
        if tc.get("has_hook_ui_actions"):
            stats.tests_with_hook_ui_actions += 1
        if tc.get("has_helper_expanded_ui_actions"):
            stats.tests_with_helper_expanded_ui_actions += 1
        if tc.get("has_expanded_ui_actions"):
            stats.tests_with_expanded_ui_actions += 1
        if tc.get("phase1_confidence") == "medium" and not tc.get("has_direct_ui_actions"):
            stats.medium_confidence_test_cases_with_no_direct_ui_actions += 1


def cached_row_count(cached: Dict[str, Any], array_key: str, summary_key: str) -> int:
    rows = cached.get(array_key)
    if isinstance(rows, list):
        return len(rows)
    summary = cached.get("summary") or {}
    counts = cached.get("counts") or {}
    return int(summary.get(summary_key) or counts.get(array_key) or 0)


def stream_merge_repo_into_files(
    cached: Dict[str, Any],
    paths: Dict[str, Path],
    stats: MergeStats,
    *,
    write_feature_roots: bool = True,
) -> None:
    all_test_cases = list(cached.get("test_cases") or [])
    executable = executable_test_cases_from(all_test_cases)
    update_merge_stats_from_test_cases(stats, executable)
    if executable:
        append_jsonl(paths["test_cases"], executable)

    bdd_rows = list(cached.get("bdd_step_definitions") or [])
    legacy_bdd = legacy_bdd_from(all_test_cases)
    bdd_ids = {str(b.get("test_id")) for b in bdd_rows if b.get("test_id")}
    all_bdd = bdd_rows + [b for b in legacy_bdd if str(b.get("test_id") or "") not in bdd_ids]
    stats.bdd_step_definitions += len(all_bdd)
    if all_bdd:
        append_jsonl(paths["bdd"], all_bdd)

    summary = cached.get("summary") or {}

    if not write_feature_roots:
        stats.features_direct += cached_row_count(cached, "features_direct", "features_direct_count")
        stats.features_expanded += cached_row_count(cached, "features_expanded", "features_expanded_count")
        stats.helper_edges += cached_row_count(cached, "helper_edges", "helper_edges_count")
        stats.unresolved_calls += cached_row_count(cached, "unresolved_calls", "unresolved_calls_count")
        direct_rows = cached.get("features_direct")
        if isinstance(direct_rows, list):
            for f in direct_rows:
                if f.get("is_shared_hook_feature") and f.get("hook_instance_key"):
                    stats.unique_hook_feature_instances.add(str(f["hook_instance_key"]))
        else:
            stats.unique_hook_feature_instances_from_summary += int(summary.get("unique_hook_feature_instances") or 0)
        return

    direct = list(cached.get("features_direct") or [])
    stats.features_direct += len(direct)
    if direct:
        append_jsonl(paths["features_direct"], direct)
    for f in direct:
        if f.get("is_shared_hook_feature") and f.get("hook_instance_key"):
            stats.unique_hook_feature_instances.add(str(f["hook_instance_key"]))

    helper_edges = list(cached.get("helper_edges") or [])
    unresolved_calls = list(cached.get("unresolved_calls") or [])
    stats.helper_edges += len(helper_edges)
    stats.unresolved_calls += len(unresolved_calls)
    if write_feature_roots:
        append_jsonl(paths["helper_edges"], helper_edges)
        append_jsonl(paths["unresolved_calls"], unresolved_calls)

    expanded_base = list(cached.get("features_expanded") or [])
    attached = attach_hook_features_to_expanded(expanded_base, direct, all_test_cases)
    stats.features_expanded += len(attached)
    if attached:
        append_jsonl(paths["features_expanded"], attached)


def stream_merge_all_per_repo_outputs(
    per_repo_dir: Path,
    output_dir: Path,
    inventory_repos: List[str],
    analyzer_fp: Dict[str, Any],
    input_fp: Dict[str, Any],
    grouped: Dict[str, List[Dict[str, Any]]],
    subphase: str,
    max_helper_depth: int,
    max_helper_files: int,
    repo_cache: Optional[Path] = None,
    skip_global_feature_merge: bool = False,
) -> Tuple[MergeStats, List[Dict[str, Any]], int]:
    """Stream per-repo sidecars into merged JSONL without loading the full corpus into RAM."""
    paths = {
        "test_cases": output_dir / "test_cases.jsonl",
        "bdd": output_dir / "bdd_step_definitions.jsonl",
        "features_direct": output_dir / "test_case_features_direct.jsonl",
        "features_expanded": output_dir / "test_case_features_expanded.jsonl",
        "helper_edges": output_dir / "helper_edges.jsonl",
        "unresolved_calls": output_dir / "unresolved_calls.jsonl",
    }
    for path in paths.values():
        if path.exists():
            path.unlink()

    stats = MergeStats()
    repo_summaries: List[Dict[str, Any]] = []
    repos_skipped_stale_commit = 0
    merge_sidecars = ("test_cases", "bdd_step_definitions") if skip_global_feature_merge else None

    for repo in inventory_repos:
        files = grouped.get(repo, [])
        if not files:
            continue
        rhash = repo_file_list_hash(files)
        out_json = per_repo_dir / f"{safe_repo_dir(repo)}.json"
        meta_json = per_repo_dir / f"{safe_repo_dir(repo)}.meta.json"
        if not out_json.exists():
            continue

        cached, reason = cache_validity(
            out_json,
            meta_json,
            analyzer_fp,
            input_fp,
            rhash,
            subphase,
            max_helper_depth,
            max_helper_files,
            sidecars=merge_sidecars,
        )
        merge_source = "merged_disk"

        manifest_commit = str(files[0].get("commit") or "HEAD")
        merge_target_commit = resolve_merge_commit_target(manifest_commit, repo, repo_cache)

        if cached is None and subphase == "2c":
            cached_2ab, _reason_2ab = cache_validity(
                out_json,
                meta_json,
                analyzer_fp,
                input_fp,
                rhash,
                "2ab",
                max_helper_depth,
                max_helper_files,
                sidecars=merge_sidecars,
            )
            if cached_2ab is not None:
                cached_commit = str(cached_2ab.get("analyzed_commit") or cached_2ab.get("commit") or "")
                if merge_target_commit and commits_match(cached_commit, merge_target_commit):
                    cached = cached_2ab
                    merge_source = "merged_disk_2ab_fallback"

        if cached is None:
            continue

        cached_commit = str(cached.get("analyzed_commit") or cached.get("commit") or "")
        if not merge_target_commit or not commits_match(cached_commit, merge_target_commit):
            repos_skipped_stale_commit += 1
            continue

        stream_merge_repo_into_files(
            cached,
            paths,
            stats,
            write_feature_roots=not skip_global_feature_merge,
        )
        repo_summaries.append({"repo": repo, **(cached.get("summary") or {}), "analysis_source": merge_source})

    return stats, repo_summaries, repos_skipped_stale_commit


def merge_all_per_repo_outputs(
    per_repo_dir: Path,
    inventory_repos: List[str],
    analyzer_fp: Dict[str, Any],
    input_fp: Dict[str, Any],
    grouped: Dict[str, List[Dict[str, Any]]],
    subphase: str,
    max_helper_depth: int,
    max_helper_files: int,
    repo_cache: Optional[Path] = None,
) -> Tuple[
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    int,
]:
    """Merge all valid per-repo JSON caches for repos in inventory (not only current run batch)."""
    test_cases: List[Dict[str, Any]] = []
    bdd_step_definitions: List[Dict[str, Any]] = []
    features_direct: List[Dict[str, Any]] = []
    features_expanded: List[Dict[str, Any]] = []
    helper_edges: List[Dict[str, Any]] = []
    unresolved_calls: List[Dict[str, Any]] = []
    repo_summaries: List[Dict[str, Any]] = []
    repos_skipped_stale_commit = 0

    for repo in inventory_repos:
        files = grouped.get(repo, [])
        if not files:
            continue
        rhash = repo_file_list_hash(files)
        out_json = per_repo_dir / f"{safe_repo_dir(repo)}.json"
        meta_json = per_repo_dir / f"{safe_repo_dir(repo)}.meta.json"
        if not out_json.exists():
            continue

        cached, reason = cache_validity(
            out_json, meta_json, analyzer_fp, input_fp, rhash, subphase, max_helper_depth, max_helper_files
        )
        merge_source = "merged_disk"

        manifest_commit = str(files[0].get("commit") or "HEAD")
        merge_target_commit = resolve_merge_commit_target(manifest_commit, repo, repo_cache)

        if cached is None and subphase == "2c":
            cached_2ab, reason_2ab = cache_validity(
                out_json, meta_json, analyzer_fp, input_fp, rhash, "2ab", max_helper_depth, max_helper_files
            )
            if cached_2ab is not None:
                cached_commit = str(cached_2ab.get("analyzed_commit") or cached_2ab.get("commit") or "")
                if merge_target_commit and commits_match(cached_commit, merge_target_commit):
                    cached = cached_2ab
                    merge_source = "merged_disk_2ab_fallback"

        if cached is None:
            continue

        cached_commit = str(cached.get("analyzed_commit") or cached.get("commit") or "")
        if not merge_target_commit or not commits_match(cached_commit, merge_target_commit):
            repos_skipped_stale_commit += 1
            continue

        merge_repo_result_into(
            cached,
            test_cases,
            bdd_step_definitions,
            features_direct,
            features_expanded,
            helper_edges,
            unresolved_calls,
        )
        repo_summaries.append({"repo": repo, **(cached.get("summary") or {}), "analysis_source": merge_source})

    return (
        test_cases,
        bdd_step_definitions,
        features_direct,
        features_expanded,
        helper_edges,
        unresolved_calls,
        repo_summaries,
        repos_skipped_stale_commit,
    )


def group_by_repo(rows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        repo = str(r.get("repo") or "").strip()
        if not repo:
            continue
        grouped.setdefault(repo, []).append(r)
    return grouped


@dataclass
class RepoAnalysisOutcome:
    repo: str
    status: str
    summary: Optional[Dict[str, Any]] = None
    error_records: List[Dict[str, Any]] = field(default_factory=list)
    stale_reason: Optional[str] = None
    missing_cache: int = 0
    skipped_commit_pin: int = 0
    incremental_2c: int = 0
    elapsed_seconds: float = 0.0


def _dedupe_rows(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: Set[str] = set()
    out: List[Dict[str, Any]] = []
    for row in rows:
        key = json.dumps(_scrub_surrogates(row), sort_keys=True, ensure_ascii=False)
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _sum_numeric_dicts(dicts: Iterable[Optional[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    out: Dict[str, Any] = {}
    saw = False
    for data in dicts:
        if not isinstance(data, dict):
            continue
        saw = True
        for key, val in data.items():
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                out[key] = out.get(key, 0) + val
            elif key not in out:
                out[key] = val
    return out if saw else None


def _summarize_combined_repo_result(result: Dict[str, Any], subphase: str) -> Dict[str, Any]:
    test_cases = result.get("test_cases") or []
    direct = result.get("features_direct") or []
    expanded = result.get("features_expanded") or []
    helper_edges = result.get("helper_edges") or []
    unresolved = result.get("unresolved_calls") or []
    unique_hook_keys = {
        str(f.get("hook_instance_key"))
        for f in direct
        if f.get("is_shared_hook_feature") and f.get("hook_instance_key")
    }
    registry = _sum_numeric_dicts(
        (r.get("summary") or {}).get("rq2_registry")
        for r in result.get("_shard_results") or []
    )
    return {
        "repo": result.get("repo"),
        "commit": result.get("commit"),
        "subphases_run": ["2a", "2b", "2c"] if subphase in ("2c", "all") else [subphase],
        "reused_from_2ab": False,
        "global_support_hooks": max(
            [int((r.get("summary") or {}).get("global_support_hooks") or 0) for r in result.get("_shard_results") or []],
            default=0,
        ),
        "unique_hook_feature_instances": len(unique_hook_keys),
        "test_case_count": len(test_cases),
        "bdd_step_definition_count": len(result.get("bdd_step_definitions") or []),
        "features_direct_count": len(direct),
        "features_expanded_count": len(expanded),
        "helper_edges_count": len(helper_edges),
        "unresolved_calls_count": len(unresolved),
        "tests_with_direct_ui_actions": sum(1 for t in test_cases if t.get("has_direct_ui_actions")),
        "tests_with_hook_ui_actions": sum(1 for t in test_cases if t.get("has_hook_ui_actions")),
        "tests_with_helper_expanded_ui_actions": sum(1 for t in test_cases if t.get("has_helper_expanded_ui_actions")),
        "tests_with_expanded_ui_actions": sum(1 for t in test_cases if t.get("has_expanded_ui_actions")),
        "medium_confidence_test_cases": sum(1 for t in test_cases if t.get("phase1_confidence") == "medium"),
        "parse_errors": len(result.get("parse_errors") or []),
        "unresolved_rate": (
            len(unresolved) / (len(helper_edges) + len(unresolved))
            if (len(helper_edges) + len(unresolved)) else 0
        ),
        "rq2_registry": registry,
        "shard_count": len(result.get("_shard_results") or []),
    }


def _merge_shard_results(
    *,
    repo: str,
    repo_url: str,
    commit: str,
    out_json: Path,
    shard_results: List[Dict[str, Any]],
    subphase: str,
) -> Dict[str, Any]:
    combined: Dict[str, Any] = {
        "repo": repo,
        "repo_url": repo_url,
        "commit": commit,
        "analyzed_commit": shard_results[0].get("analyzed_commit") if shard_results else commit,
        "commit_pin_match": all(bool(r.get("commit_pin_match")) for r in shard_results),
        "subphases_run": ["2a", "2b", "2c"] if subphase in ("2c", "all") else [subphase],
        "test_cases": _dedupe_rows(tc for r in shard_results for tc in (r.get("test_cases") or [])),
        "bdd_step_definitions": _dedupe_rows(row for r in shard_results for row in (r.get("bdd_step_definitions") or [])),
        "features_direct": _dedupe_rows(f for r in shard_results for f in (r.get("features_direct") or [])),
        "features_expanded": _dedupe_rows(f for r in shard_results for f in (r.get("features_expanded") or [])),
        "helper_edges": _dedupe_rows(e for r in shard_results for e in (r.get("helper_edges") or [])),
        "unresolved_calls": _dedupe_rows(u for r in shard_results for u in (r.get("unresolved_calls") or [])),
        "parse_errors": [e for r in shard_results for e in (r.get("parse_errors") or [])],
        "_shard_results": shard_results,
    }
    combined["summary"] = _summarize_combined_repo_result(combined, subphase)
    write_split_per_repo_result(out_json, combined)
    combined.pop("_shard_results", None)
    return combined


def _write_manifest(path: Path, files: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(files, ensure_ascii=False), encoding="utf-8")


def _build_node_cmd(
    *,
    node_analyzer: Path,
    analysis_path: Path,
    repo: str,
    repo_url: str,
    commit: str,
    manifest_path: Path,
    subphase: str,
    out_json: Path,
    max_helper_depth: int,
    max_helper_files: int,
    reuse_from: Optional[Path] = None,
) -> List[str]:
    cmd = [
        "node",
        str(node_analyzer),
        "--repo-path",
        str(analysis_path),
        "--repo",
        repo,
        "--repo-url",
        repo_url,
        "--commit",
        commit,
        "--manifest",
        str(manifest_path),
        "--subphase",
        subphase,
        "--output",
        str(out_json),
        "--max-helper-depth",
        str(max_helper_depth),
        "--max-helper-files",
        str(max_helper_files),
    ]
    if reuse_from is not None:
        cmd.extend(["--reuse-from", str(reuse_from)])
    return cmd


def _chunk_files(files: List[Dict[str, Any]], shard_count: int) -> List[List[Dict[str, Any]]]:
    shard_count = max(1, min(shard_count, len(files)))
    chunks: List[List[Dict[str, Any]]] = [[] for _ in range(shard_count)]
    for idx, row in enumerate(files):
        chunks[idx % shard_count].append(row)
    return [c for c in chunks if c]


def _run_sharded_repo_analysis(
    *,
    repo: str,
    repo_url: str,
    files: List[Dict[str, Any]],
    analysis_path: Path,
    commit: str,
    manifest_dir: Path,
    out_json: Path,
    node_analyzer: Path,
    subphase: str,
    max_helper_depth: int,
    max_helper_files: int,
    shard_workers: int,
    timeout_seconds: int,
) -> Dict[str, Any]:
    shard_started = time.monotonic()
    shard_dir = out_json.parent / "_shards" / safe_repo_dir(repo)
    if shard_dir.exists():
        shutil.rmtree(shard_dir, ignore_errors=True)
    shard_dir.mkdir(parents=True, exist_ok=True)
    chunks = _chunk_files(files, shard_workers)

    def run_one(shard_idx: int, shard_files: List[Dict[str, Any]]) -> Dict[str, Any]:
        shard_manifest = manifest_dir / f"{safe_repo_dir(repo)}.shard{shard_idx}.manifest.json"
        shard_out = shard_dir / f"{safe_repo_dir(repo)}.shard{shard_idx}.json"
        _write_manifest(shard_manifest, shard_files)
        cmd = _build_node_cmd(
            node_analyzer=node_analyzer,
            analysis_path=analysis_path,
            repo=repo,
            repo_url=repo_url,
            commit=commit,
            manifest_path=shard_manifest,
            subphase=subphase,
            out_json=shard_out,
            max_helper_depth=max_helper_depth,
            max_helper_files=max_helper_files,
        )
        run(cmd, check=True, timeout=timeout_seconds)
        return load_per_repo_result(shard_out)

    shard_results: List[Dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(chunks)) as pool:
        futures = [
            pool.submit(run_one, shard_idx, shard_files)
            for shard_idx, shard_files in enumerate(chunks, start=1)
        ]
        completed = 0
        for fut in concurrent.futures.as_completed(futures):
            shard_results.append(fut.result())
            completed += 1
            log_progress(
                f"Phase 2 extraction repo {repo}: shard {completed}/{len(chunks)} done",
                started=shard_started,
            )

    shard_results.sort(key=lambda r: str((r.get("summary") or {}).get("repo") or r.get("repo") or ""))
    return _merge_shard_results(
        repo=repo,
        repo_url=repo_url,
        commit=commit,
        out_json=out_json,
        shard_results=shard_results,
        subphase=subphase,
    )


def analyze_one_repo(
    *,
    idx: int,
    total: int,
    repo: str,
    files: List[Dict[str, Any]],
    args: argparse.Namespace,
    analyzer_fp: Dict[str, Any],
    input_fp: Dict[str, Any],
    subphase: str,
    per_repo_dir: Path,
    manifest_dir: Path,
    shard_workers: int = 1,
) -> RepoAnalysisOutcome:
    started = time.time()
    worktree_path: Optional[Path] = None
    staged_analysis_path: Optional[Path] = None
    repo_url = str(files[0].get("repo_url") or f"https://github.com/{repo}")
    rhash = repo_file_list_hash(files)
    out_json = per_repo_dir / f"{safe_repo_dir(repo)}.json"
    meta_json = per_repo_dir / f"{safe_repo_dir(repo)}.meta.json"
    manifest_path = manifest_dir / f"{safe_repo_dir(repo)}.manifest.json"

    try:
        reuse_from: Optional[Path] = None
        pending_reuse_2ab: Optional[Path] = None
        cached, reason = cache_validity(
            out_json,
            meta_json,
            analyzer_fp,
            input_fp,
            rhash,
            subphase,
            args.max_helper_depth,
            args.max_helper_files,
        )
        if args.resume and cached is not None and reason == "ok":
            log_progress(f"Phase 2 extraction repo {idx}/{total}: {repo} cached", started=started)
            return RepoAnalysisOutcome(
                repo=repo,
                status="cached",
                summary={"repo": repo, **(cached.get("summary") or {}), "analysis_source": "cached"},
                elapsed_seconds=round(time.time() - started, 2),
            )
        stale_reason = None
        if reason == "reuse_2ab_for_2c":
            pending_reuse_2ab = out_json
        elif reason != "missing_json":
            stale_reason = reason

        if pending_reuse_2ab is None and subphase == "2c" and args.seed_2ab_from:
            seed_json = args.seed_2ab_from / out_json.name
            seed_meta = args.seed_2ab_from / meta_json.name
            if seed_json.exists() and seed_meta.exists():
                _seed_cached, seed_reason = cache_validity(
                    seed_json,
                    seed_meta,
                    analyzer_fp,
                    input_fp,
                    rhash,
                    subphase,
                    args.max_helper_depth,
                    args.max_helper_files,
                )
                if seed_reason == "reuse_2ab_for_2c":
                    pending_reuse_2ab = seed_json

        local = args.repo_cache / safe_repo_dir(repo)
        if not local.exists() or not is_git_repo(local):
            if args.clone_missing:
                try:
                    local, _commit = clone_repo(repo, repo_url, args.repo_cache)
                except Exception as exc:
                    return RepoAnalysisOutcome(
                        repo=repo,
                        status="error",
                        error_records=[{"repo": repo, "error": repr(exc), "reason": "clone_failed"}],
                        missing_cache=1,
                        elapsed_seconds=round(time.time() - started, 2),
                    )
            else:
                error = "repo_missing_from_cache" if not local.exists() else "repo_cache_not_git"
                return RepoAnalysisOutcome(
                    repo=repo,
                    status="error",
                    error_records=[{"repo": repo, "error": error, "repo_cache": str(local)}],
                    missing_cache=1,
                    elapsed_seconds=round(time.time() - started, 2),
                )

        manifest_target = str(files[0].get("commit") or "HEAD")
        if args.pin_manifest_commit and args.analysis_scratch_root and manifest_target and manifest_target != "HEAD":
            analysis_path, actual_commit, pinned_ok = archive_commit_to_scratch(
                local,
                manifest_target,
                args.analysis_scratch_root,
                repo,
                timeout_seconds=args.repo_timeout_seconds,
            )
            if pinned_ok:
                staged_analysis_path = analysis_path
            else:
                worktree_path = None
        else:
            analysis_path, actual_commit, pinned_ok, worktree_path = prepare_analysis_repo(
                local, manifest_target, args.pin_manifest_commit
            )
        commit = actual_commit
        if args.pin_manifest_commit and not pinned_ok and manifest_target and manifest_target != "HEAD":
            remove_analysis_worktree(local, worktree_path)
            return RepoAnalysisOutcome(
                repo=repo,
                status="skipped_commit_pin",
                skipped_commit_pin=1,
                error_records=[{
                    "repo": repo,
                    "error": "commit_pin_failed",
                    "manifest_commit": manifest_target,
                    "actual_commit": actual_commit,
                }],
                elapsed_seconds=round(time.time() - started, 2),
            )

        if args.analysis_scratch_root and staged_analysis_path is None:
            staged_analysis_path = stage_analysis_tree(
                analysis_path,
                args.analysis_scratch_root,
                repo,
                actual_commit,
            )
            analysis_path = staged_analysis_path

        extra_errors: List[Dict[str, Any]] = []
        if args.pin_manifest_commit and not pinned_ok:
            extra_errors.append({
                "repo": repo,
                "warning": "commit_pin_mismatch_head",
                "manifest_commit": manifest_target,
                "actual_commit": actual_commit,
            })

        incremental_2c = 0
        if pending_reuse_2ab is not None:
            try:
                cached_2ab = load_per_repo_result(pending_reuse_2ab)
                cached_commit = str(cached_2ab.get("analyzed_commit") or cached_2ab.get("commit") or "")
                if commits_match(cached_commit, actual_commit):
                    reuse_from = pending_reuse_2ab
                    incremental_2c = 1
                    log_progress(
                        f"Phase 2 extraction repo {idx}/{total}: {repo} 2C from 2AB cache",
                        started=started,
                    )
                else:
                    stale_reason = "stale_commit_for_2c_reuse"
            except (OSError, json.JSONDecodeError):
                stale_reason = "corrupt_json"

        _write_manifest(manifest_path, files)
        log_progress(
            (
                f"Phase 2 extraction repo {idx}/{total}: {repo} started "
                f"files={len(files)}"
                + (f" shards={shard_workers}" if shard_workers > 1 and reuse_from is None else "")
            ),
            started=started,
        )

        if shard_workers > 1 and reuse_from is None:
            result = _run_sharded_repo_analysis(
                repo=repo,
                repo_url=repo_url,
                files=files,
                analysis_path=analysis_path,
                commit=commit,
                manifest_dir=manifest_dir,
                out_json=out_json,
                node_analyzer=args.node_analyzer,
                subphase=subphase,
                max_helper_depth=args.max_helper_depth,
                max_helper_files=args.max_helper_files,
                shard_workers=shard_workers,
                timeout_seconds=args.repo_timeout_seconds,
            )
        else:
            cmd = _build_node_cmd(
                node_analyzer=args.node_analyzer,
                analysis_path=analysis_path,
                repo=repo,
                repo_url=repo_url,
                commit=commit,
                manifest_path=manifest_path,
                subphase=subphase,
                out_json=out_json,
                max_helper_depth=args.max_helper_depth,
                max_helper_files=args.max_helper_files,
                reuse_from=reuse_from,
            )
            run(cmd, check=True, timeout=args.repo_timeout_seconds)
            result = load_per_repo_result(out_json)

        write_per_repo_meta(
            meta_json,
            analyzer_fp,
            input_fp,
            rhash,
            subphase,
            args.max_helper_depth,
            args.max_helper_files,
        )
        summ = result.get("summary") or {}
        summ["analysis_source"] = "fresh_sharded" if shard_workers > 1 and reuse_from is None else "fresh"
        summ["elapsed_seconds"] = round(time.time() - started, 2)
        if shard_workers > 1 and reuse_from is None:
            summ["repo_shard_workers"] = shard_workers
        log_progress(
            (
                f"Phase 2 extraction repo {idx}/{total}: {repo} done "
                f"status=fresh tests={summ.get('test_cases', summ.get('test_case_count', ''))} "
                f"features_direct={summ.get('features_direct', summ.get('features_direct_count', ''))} "
                f"features_expanded={summ.get('features_expanded', summ.get('features_expanded_count', ''))}"
            ),
            started=started,
        )
        return RepoAnalysisOutcome(
            repo=repo,
            status="fresh",
            summary={"repo": repo, **summ},
            error_records=extra_errors,
            stale_reason=stale_reason,
            incremental_2c=incremental_2c,
            elapsed_seconds=round(time.time() - started, 2),
        )
    except subprocess.CalledProcessError as exc:
        return RepoAnalysisOutcome(
            repo=repo,
            status="error",
            error_records=[{
                "repo": repo,
                "error": repr(exc),
                "stderr": (exc.stderr or "")[-2000:],
            }],
            stale_reason=stale_reason if "stale_reason" in locals() else None,
            elapsed_seconds=round(time.time() - started, 2),
        )
    finally:
        remove_staged_analysis_tree(staged_analysis_path)
        try:
            local = args.repo_cache / safe_repo_dir(repo)
            remove_analysis_worktree(local, worktree_path)
        except Exception:
            pass


def _apply_outcome(
    outcome: RepoAnalysisOutcome,
    *,
    repo_summaries: List[Dict[str, Any]],
    error_records: List[Dict[str, Any]],
    stale_reasons: Dict[str, int],
) -> Tuple[int, int, int, int, int]:
    resumed = 1 if outcome.status == "cached" else 0
    fresh = 1 if outcome.status == "fresh" else 0
    missing_cache = outcome.missing_cache
    skipped_commit_pin = outcome.skipped_commit_pin
    incremental_2c = outcome.incremental_2c
    if outcome.summary:
        repo_summaries.append(outcome.summary)
    error_records.extend(outcome.error_records)
    if outcome.stale_reason:
        stale_reasons[outcome.stale_reason] = stale_reasons.get(outcome.stale_reason, 0) + 1
    return resumed, fresh, incremental_2c, missing_cache, skipped_commit_pin


def run_repo_analyses(
    *,
    repos: List[str],
    grouped: Dict[str, List[Dict[str, Any]]],
    args: argparse.Namespace,
    analyzer_fp: Dict[str, Any],
    input_fp: Dict[str, Any],
    subphase: str,
    per_repo_dir: Path,
    manifest_dir: Path,
    stale_reasons: Dict[str, int],
    repo_summaries: List[Dict[str, Any]],
    error_records: List[Dict[str, Any]],
) -> Tuple[int, int, int, int, int]:
    resumed = fresh = incremental_2c = missing_cache = skipped_commit_pin = 0
    total = len(repos)
    workers = max(1, int(args.workers or 1))

    def apply(outcome: RepoAnalysisOutcome) -> None:
        nonlocal resumed, fresh, incremental_2c, missing_cache, skipped_commit_pin
        r, f, inc, miss, skip = _apply_outcome(
            outcome,
            repo_summaries=repo_summaries,
            error_records=error_records,
            stale_reasons=stale_reasons,
        )
        resumed += r
        fresh += f
        incremental_2c += inc
        missing_cache += miss
        skipped_commit_pin += skip
        if args.stop_on_error and outcome.status in ("error", "skipped_commit_pin"):
            raise RuntimeError(f"repo analysis failed: {outcome.repo}")

    def is_large(repo: str) -> bool:
        return (
            workers > 1
            and args.large_repo_shard_threshold > 0
            and len(grouped[repo]) >= args.large_repo_shard_threshold
        )

    normal_batch: List[Tuple[int, str]] = []

    def drain_normal_batch() -> None:
        nonlocal normal_batch
        if not normal_batch:
            return
        if workers == 1:
            for idx, repo in normal_batch:
                apply(analyze_one_repo(
                    idx=idx,
                    total=total,
                    repo=repo,
                    files=grouped[repo],
                    args=args,
                    analyzer_fp=analyzer_fp,
                    input_fp=input_fp,
                    subphase=subphase,
                    per_repo_dir=per_repo_dir,
                    manifest_dir=manifest_dir,
                ))
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [
                    pool.submit(
                        analyze_one_repo,
                        idx=idx,
                        total=total,
                        repo=repo,
                        files=grouped[repo],
                        args=args,
                        analyzer_fp=analyzer_fp,
                        input_fp=input_fp,
                        subphase=subphase,
                        per_repo_dir=per_repo_dir,
                        manifest_dir=manifest_dir,
                    )
                    for idx, repo in normal_batch
                ]
                for fut in concurrent.futures.as_completed(futures):
                    apply(fut.result())
        normal_batch = []

    for idx, repo in enumerate(repos, start=1):
        if is_large(repo):
            drain_normal_batch()
            apply(analyze_one_repo(
                idx=idx,
                total=total,
                repo=repo,
                files=grouped[repo],
                args=args,
                analyzer_fp=analyzer_fp,
                input_fp=input_fp,
                subphase=subphase,
                per_repo_dir=per_repo_dir,
                manifest_dir=manifest_dir,
                shard_workers=workers,
            ))
        else:
            normal_batch.append((idx, repo))
    drain_normal_batch()
    return resumed, fresh, incremental_2c, missing_cache, skipped_commit_pin


def main() -> None:
    run_started = time.monotonic()
    parser = argparse.ArgumentParser(description="Phase 2 test-case feature extraction")
    parser.add_argument("--input-jsonl", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--repo-cache", type=Path, default=DEFAULT_REPO_CACHE)
    parser.add_argument("--output-dir", type=Path, default=Path("ui_test_feature_extraction"))
    parser.add_argument("--node-analyzer", type=Path, required=True)
    parser.add_argument("--subphase", type=str, default="2ab", choices=["2a", "2b", "2ab", "2c", "2d", "all"])
    parser.add_argument(
        "--review-bundle",
        action="store_true",
        help="After 2C merge, build review_bundle/ (compact samples + phase2c_validation_report.json)",
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--merge-only",
        action="store_true",
        help="Skip per-repo analysis; stream-merge existing per_repo_outputs into global JSONL",
    )
    parser.add_argument(
        "--seed-2ab-from",
        type=Path,
        default=None,
        help="Directory of per-repo 2AB caches to reuse for 2C (e.g. phase2ab_full_v21/per_repo_outputs)",
    )
    parser.add_argument("--clone-missing", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--stop-on-error", action="store_true")
    parser.add_argument("--max-helper-depth", type=int, default=2)
    parser.add_argument("--max-helper-files", type=int, default=20)
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of repo-analysis workers. Default 1 preserves legacy sequential behavior.",
    )
    parser.add_argument(
        "--large-repo-shard-threshold",
        type=int,
        default=250,
        help=(
            "When --workers > 1, repos with at least this many manifest files run one repo at a time "
            "but split their manifest across all workers. Use 0 to disable large-repo sharding."
        ),
    )
    parser.add_argument(
        "--repo-timeout-seconds",
        type=int,
        default=1800,
        help="Timeout for each repo materialization step and normal repo or large-repo shard Node analyzer process.",
    )
    parser.add_argument(
        "--analysis-scratch-root",
        type=Path,
        default=None,
        help=(
            "Optional node-local scratch root. Pinned commits are exported there with git archive; "
            "unpinned/cache-matching checkouts are copied there before Node analysis."
        ),
    )
    parser.add_argument(
        "--skip-global-feature-merge",
        "--sidecars-only",
        dest="skip_global_feature_merge",
        action="store_true",
        help=(
            "After per-repo extraction, write root test_cases/bdd files and summary only; "
            "do not write giant root feature/helper JSONLs. Phase 2D can consume per-repo sidecars."
        ),
    )
    parser.add_argument(
        "--pin-manifest-commit",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Try to git checkout the commit recorded in Phase 1 manifest before analysis",
    )
    args = parser.parse_args()

    if args.subphase == "2d":
        print("Use rq_aggregation/run_rq_aggregation.py for subphase 2d.", file=sys.stderr)
        sys.exit(0)

    if not args.input_jsonl.exists():
        raise FileNotFoundError(args.input_jsonl)
    if not args.node_analyzer.exists():
        raise FileNotFoundError(args.node_analyzer)

    inventory = filter_inventory_rows(read_jsonl(args.input_jsonl))
    grouped = group_by_repo(inventory)
    all_inventory_repos = sorted(grouped.keys())
    repos = list(all_inventory_repos)
    if args.limit is not None:
        repos = repos[: args.limit]

    log_progress(
        (
            f"Phase 2 extraction started subphase={args.subphase} "
            f"repos={len(repos)} inventory_rows={len(inventory)} output_dir={args.output_dir}"
        ),
        started=run_started,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    per_repo_dir = args.output_dir / "per_repo_outputs"
    per_repo_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir = args.output_dir / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)

    analyzer_fp = analyzer_fingerprint(args.node_analyzer)
    input_fp = input_manifest_fingerprint(args.input_jsonl)
    subphase = args.subphase if args.subphase != "all" else "2c"

    error_records: List[Dict[str, Any]] = []
    repo_summaries: List[Dict[str, Any]] = []

    resumed = 0
    fresh = 0
    incremental_2c = 0
    missing_cache = 0
    skipped_commit_pin = 0
    stale_reasons: Dict[str, int] = {}

    if not args.merge_only:
        resumed, fresh, incremental_2c, missing_cache, skipped_commit_pin = run_repo_analyses(
            repos=repos,
            grouped=grouped,
            args=args,
            analyzer_fp=analyzer_fp,
            input_fp=input_fp,
            subphase=subphase,
            per_repo_dir=per_repo_dir,
            manifest_dir=manifest_dir,
            stale_reasons=stale_reasons,
            repo_summaries=repo_summaries,
            error_records=error_records,
        )

    merge_stats, merged_summaries, repos_skipped_stale_commit = stream_merge_all_per_repo_outputs(
        per_repo_dir,
        args.output_dir,
        all_inventory_repos,
        analyzer_fp,
        input_fp,
        grouped,
        subphase,
        args.max_helper_depth,
        args.max_helper_files,
        args.repo_cache,
        skip_global_feature_merge=args.skip_global_feature_merge,
    )
    if merged_summaries:
        repo_summaries = merged_summaries

    write_jsonl(args.output_dir / "errors.jsonl", error_records)

    overall = {
        "repos_total": len(all_inventory_repos),
        "repos_processed_this_run": 0 if args.merge_only else len(repos),
        "repos_fresh": fresh,
        "repos_cached": resumed,
        "repos_incremental_2c_from_2ab": incremental_2c,
        "repos_missing_from_cache": missing_cache,
        "repos_errors": len(error_records),
        "repos_skipped_commit_pin": skipped_commit_pin,
        "repos_skipped_stale_commit_merge": repos_skipped_stale_commit,
        "stale_cache_reasons": stale_reasons,
        "workers": max(1, int(args.workers or 1)),
        "large_repo_shard_threshold": int(args.large_repo_shard_threshold or 0),
        "repo_timeout_seconds": int(args.repo_timeout_seconds or 0),
        "skip_global_feature_merge": bool(args.skip_global_feature_merge),
        "metric_notes": {
            "has_direct_ui_actions": "UI actions in test body only (excludes hook/setup UI)",
            "has_direct_assertions": "assertions in test body only (excludes hook/setup assertions)",
            "extraction_empty": "medium-confidence test with no body UI or body assertions (per-test, not file-level)",
            "repos_skipped_stale_commit_merge": (
                "per-repo cache omitted from global JSONL because analyzed_commit != manifest commit "
                "(manifest HEAD resolved against local clone HEAD when repo_cache is available)"
            ),
            "has_expanded_ui_actions": "true when hook UI and/or helper-expanded UI (2C); after 2ab-only, hook UI only",
            "has_helper_expanded_ui_actions": "true only when 2C found UI in expanded helpers",
            "features_expanded_count": "row count; use unique_hook_feature_instances for distinct hook templates",
            "merged_csv": "omitted for large 2C runs; use per-repo sidecars or merged JSONL",
        },
        "test_cases_extracted": merge_stats.test_cases,
        "bdd_step_definitions_extracted": merge_stats.bdd_step_definitions,
        "features_direct_count": merge_stats.features_direct,
        "features_expanded_count": merge_stats.features_expanded,
        "unique_hook_feature_instances": merge_stats.unique_hook_feature_instances_total(),
        "tests_with_direct_ui_actions": merge_stats.tests_with_direct_ui_actions,
        "tests_with_hook_ui_actions": merge_stats.tests_with_hook_ui_actions,
        "tests_with_helper_expanded_ui_actions": merge_stats.tests_with_helper_expanded_ui_actions,
        "tests_with_expanded_ui_actions": merge_stats.tests_with_expanded_ui_actions,
        "phase2_schema_version": PHASE2_SCHEMA_VERSION,
        "medium_confidence_test_cases_with_no_direct_ui_actions": merge_stats.medium_confidence_test_cases_with_no_direct_ui_actions,
        "unresolved_calls_count": merge_stats.unresolved_calls,
        "unresolved_rate": (
            merge_stats.unresolved_calls / (merge_stats.helper_edges + merge_stats.unresolved_calls)
            if (merge_stats.helper_edges or merge_stats.unresolved_calls)
            else 0.0
        ),
        "input_manifest_sha256": input_fp.get("input_jsonl_sha256"),
        "subphase": subphase,
    }
    (args.output_dir / "overall_summary.json").write_text(
        json.dumps(overall, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(overall, indent=2), file=sys.stderr)
    log_progress(
        (
            f"Phase 2 extraction finished processed_repos={len(repos)} "
            f"fresh={fresh} cached={resumed} errors={len(error_records)}"
        ),
        started=run_started,
    )

    if args.review_bundle and subphase == "2c":
        import subprocess

        bundle_script = Path(__file__).resolve().parent / "scripts" / "build_phase2c_review_bundle.py"
        cmd = [
            sys.executable,
            str(bundle_script),
            "--output-dir",
            str(args.output_dir),
        ]
        if args.input_jsonl:
            cmd.extend(["--manifest-jsonl", str(args.input_jsonl)])
        subprocess.run(cmd, check=False)


if __name__ == "__main__":
    main()
