#!/usr/bin/env python3
"""Shared helpers for RQ6 Phase 1 scripts."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CENSUS_DIR = (
    PROJECT_ROOT
    / "github_pilot_census_output"
    / "typescript__2026-05-10_09-57-24__min500stars"
)
DEFAULT_PHASE1_INVENTORY = (
    DEFAULT_CENSUS_DIR / "ui_file_inventory_final" / "all_ui_test_files.jsonl"
)
DEFAULT_PHASE2_RUN_DIR = DEFAULT_CENSUS_DIR / "phase2c_full_v39"
DEFAULT_REPO_CACHE = Path(r"<repo-cache>")
DEFAULT_OUT_DIR = PROJECT_ROOT / "rq6_outputs" / "phase1_local_runnable_panel"

CONFIDENCE_RANK = {"": 0, "low": 1, "medium": 2, "high": 3}
TOOL_BIN_ENV = "RQ6_TOOL_BIN_DIR"
CONTAINER_RUNTIME_ENV = "RQ6_CONTAINER_RUNTIME"
CONTAINER_IMAGE_ENV = "RQ6_CONTAINER_IMAGE"
CONTAINER_BIND_ENV = "RQ6_CONTAINER_BIND"
COREPACK_MANAGED_TOOLS = {"pnpm", "yarn"}
HOST_ONLY_COMMANDS = {"git"}
CONTAINER_ENV_PASSTHROUGH = [
    "COREPACK_ENABLE_DOWNLOAD_PROMPT",
    "COREPACK_HOME",
    "NPM_CONFIG_CACHE",
    "npm_config_cache",
    "PNPM_HOME",
    "YARN_CACHE_FOLDER",
    "XDG_CACHE_HOME",
    "XDG_DATA_HOME",
    "CYPRESS_CACHE_FOLDER",
    "PLAYWRIGHT_BROWSERS_PATH",
    "HUSKY",
    "HUSKY_SKIP_INSTALL",
]


def repo_cache_key(repo_full_name: str) -> str:
    return str(repo_full_name or "").replace("/", "__").replace(":", "_")


def split_repo(repo_full_name: str) -> Tuple[str, str]:
    parts = str(repo_full_name or "").split("/", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return str(repo_full_name or ""), ""


def normalize_framework(value: Any) -> str:
    text = str(value or "").strip().lower()
    if "playwright" in text:
        return "playwright"
    if "cypress" in text:
        return "cypress"
    if "testcafe" in text:
        return "testcafe"
    if "webdriver" in text or "wdio" in text:
        return "webdriverio"
    if "puppeteer" in text:
        return "puppeteer"
    if "selenium" in text:
        return "selenium"
    if "nightwatch" in text:
        return "nightwatch"
    return text


def confidence_max(values: Iterable[str]) -> str:
    best = ""
    best_rank = -1
    for value in values:
        clean = str(value or "").strip().lower()
        rank = CONFIDENCE_RANK.get(clean, 0)
        if rank > best_rank:
            best = clean
            best_rank = rank
    return best


def primary_counter_value(counter: Counter) -> str:
    if not counter:
        return ""
    return counter.most_common(1)[0][0]


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y"}


def to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def iter_jsonl(path: Path) -> Iterator[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def read_csv_rows(path: Path) -> Iterator[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f)


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys = []
        seen = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    keys.append(key)
                    seen.add(key)
        fieldnames = keys
    elif rows:
        seen = set(fieldnames)
        for row in rows:
            for key in row:
                if key not in seen:
                    fieldnames.append(key)
                    seen.add(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if fieldnames:
            writer.writeheader()
            for row in rows:
                writer.writerow(row)


def load_repo_filter(path: Optional[Path]) -> Optional[set[str]]:
    if path is None:
        return None
    repos: set[str] = set()
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            clean = line.strip()
            if not clean or clean.startswith("#"):
                continue
            if "," in clean:
                clean = clean.split(",", 1)[0].strip()
            repos.add(clean)
            repos.add(repo_cache_key(clean))
    return repos


def row_matches_repo_filter(row: Dict[str, Any], repo_filter: Optional[set[str]]) -> bool:
    if repo_filter is None:
        return True
    return (
        str(row.get("repo_full_name") or "") in repo_filter
        or str(row.get("repo") or "") in repo_filter
        or str(row.get("repo_cache_key") or "") in repo_filter
    )


DEFAULT_TREE_HASH_IGNORE_DIRS = {
    ".git",
    "node_modules",
    ".next",
    ".nuxt",
    "dist",
    "build",
    "coverage",
    "playwright-report",
    "test-results",
    ".turbo",
    ".cache",
}


def file_tree_hash(root: Path, ignore_dirs: Optional[set[str]] = None) -> str:
    ignore_dirs = ignore_dirs or DEFAULT_TREE_HASH_IGNORE_DIRS
    if not root.is_dir():
        return ""
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        parts = set(Path(rel).parts)
        if parts & ignore_dirs:
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        digest.update(rel.encode("utf-8", errors="replace"))
        digest.update(b"\0")
        digest.update(str(stat.st_size).encode("ascii"))
        digest.update(b"\0")
        with path.open("rb") as f:
            h = hashlib.sha256()
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
            digest.update(h.hexdigest().encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def load_csv_by_test_id(path: Path, fields: Optional[Sequence[str]] = None) -> Dict[Tuple[str, str], Dict[str, str]]:
    out: Dict[Tuple[str, str], Dict[str, str]] = {}
    if not path.exists():
        return out
    wanted = set(fields or [])
    for row in read_csv_rows(path):
        key = (row.get("repo") or "", row.get("test_id") or "")
        if not key[0] or not key[1]:
            continue
        out[key] = {k: row.get(k, "") for k in wanted} if wanted else dict(row)
    return out


def is_executable_test_case(row: Dict[str, Any]) -> bool:
    if row.get("record_type", "test_case") != "test_case":
        return False
    if row.get("test_declaration_type") == "bdd_step":
        return False
    return bool(row.get("test_id"))


def is_skipped_test(row: Dict[str, Any]) -> bool:
    status_fields = [
        row.get("test_status"),
        row.get("suite_status"),
        row.get("test_declaration_type"),
        row.get("suite_declaration_type"),
    ]
    skip_values = {
        "skip",
        "skipped",
        "pending",
        "todo",
        "test.skip",
        "it.skip",
        "describe.skip",
        "suite.skip",
    }
    for value in status_fields:
        text = str(value or "").strip().lower()
        if text in skip_values or text.endswith(".skip"):
            return True
    return False


def run_command(
    cmd: Sequence[str],
    *,
    cwd: Optional[Path] = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        prepare_subprocess_command(cmd, cwd=cwd),
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def terminate_process_tree(proc: Optional[subprocess.Popen[Any]]) -> None:
    if proc is None or proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def local_node_bin_dir(cwd: Optional[Path]) -> Optional[Path]:
    if not cwd:
        return None
    candidate = Path(cwd).absolute() / "node_modules" / ".bin"
    return candidate if candidate.is_dir() else None


def path_env_key(env: Dict[str, str]) -> str:
    for key in env:
        if key.upper() == "PATH":
            return key
    return "PATH"


def subprocess_env(cwd: Optional[Path] = None) -> Dict[str, str]:
    env = os.environ.copy()
    env.setdefault("COREPACK_ENABLE_DOWNLOAD_PROMPT", "0")
    env.setdefault("HUSKY", "0")
    env.setdefault("HUSKY_SKIP_INSTALL", "1")
    local_bin = local_node_bin_dir(cwd)
    if local_bin:
        key = path_env_key(env)
        env[key] = str(local_bin) + os.pathsep + env.get(key, "")
        for other_key in list(env):
            if other_key.upper() == "PATH" and other_key != key:
                env.pop(other_key, None)
    return env


def run_process_capture(
    cmd: Sequence[str],
    *,
    cwd: Optional[Path] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    command = prepare_subprocess_command(cmd, cwd=cwd)
    proc = subprocess.Popen(
        command,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=subprocess_env(cwd),
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return {
            "returncode": proc.returncode,
            "stdout": stdout or "",
            "stderr": stderr or "",
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        terminate_process_tree(proc)
        stdout = subprocess_output_text(exc.stdout)
        stderr = subprocess_output_text(exc.stderr)
        try:
            more_stdout, more_stderr = proc.communicate(timeout=5)
            stdout = (stdout or "") + subprocess_output_text(more_stdout)
            stderr = (stderr or "") + subprocess_output_text(more_stderr)
        except subprocess.TimeoutExpired:
            pass
        return {
            "returncode": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": True,
        }


def subprocess_output_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def prepend_path_dir(path: Optional[Path | str]) -> bool:
    if not path:
        return False
    candidate = Path(path)
    if not candidate.is_dir():
        return False
    key = path_env_key(dict(os.environ))
    current = os.environ.get(key, "")
    parts = [p for p in current.split(os.pathsep) if p]
    path_text = str(candidate.absolute())
    if not parts or parts[0].lower() != path_text.lower():
        os.environ[key] = path_text + (os.pathsep + current if current else "")
        for other_key in list(os.environ):
            if other_key.upper() == "PATH" and other_key != key:
                os.environ.pop(other_key, None)
    return True


def apply_tool_bin_dir(path: Optional[Path | str] = None) -> str:
    candidate = path or os.environ.get(TOOL_BIN_ENV)
    if prepend_path_dir(candidate):
        return str(Path(candidate).absolute())
    return ""


def configure_js_tool_env(
    *,
    tool_bin_dir: Optional[Path | str] = None,
    cache_root: Optional[Path | str] = None,
) -> Dict[str, str]:
    applied_tool_bin = apply_tool_bin_dir(tool_bin_dir)
    applied: Dict[str, str] = {}
    if applied_tool_bin:
        os.environ[TOOL_BIN_ENV] = applied_tool_bin
        applied["tool_bin_dir"] = applied_tool_bin

    if cache_root:
        root = Path(cache_root).absolute()
        root.mkdir(parents=True, exist_ok=True)
        cache_paths = {
            "NPM_CONFIG_CACHE": root / "npm-cache",
            "npm_config_cache": root / "npm-cache",
            "COREPACK_HOME": root / "corepack",
            "YARN_CACHE_FOLDER": root / "yarn-cache",
            "PNPM_HOME": root / "pnpm-home",
            "XDG_CACHE_HOME": root / "xdg-cache",
            "XDG_DATA_HOME": root / "xdg-data",
            "CYPRESS_CACHE_FOLDER": root / "cypress-cache",
            "PLAYWRIGHT_BROWSERS_PATH": root / "playwright-browsers",
        }
        for name, path in cache_paths.items():
            path.mkdir(parents=True, exist_ok=True)
            value = str(path)
            os.environ[name] = value
            applied[name] = value
        os.environ["COREPACK_ENABLE_DOWNLOAD_PROMPT"] = "0"
        applied["COREPACK_ENABLE_DOWNLOAD_PROMPT"] = "0"
    os.environ.setdefault("HUSKY", "0")
    applied["HUSKY"] = os.environ["HUSKY"]
    os.environ.setdefault("HUSKY_SKIP_INSTALL", "1")
    applied["HUSKY_SKIP_INSTALL"] = os.environ["HUSKY_SKIP_INSTALL"]
    return applied


def command_stem(executable: str) -> str:
    clean = str(executable or "").strip().strip('"')
    if not clean:
        return ""
    return Path(clean).stem.lower()


def resolve_command_executable(executable: str, cwd: Optional[Path] = None) -> Optional[str]:
    """Resolve command shims explicitly, including Windows .cmd/.bat wrappers."""
    clean = str(executable or "").strip().strip('"')
    if not clean:
        return None

    local_bin = local_node_bin_dir(cwd)
    path_like = "\\" in clean or "/" in clean
    suffix = Path(clean).suffix

    if os.name != "nt":
        if local_bin:
            local_candidate = local_bin / clean
            if local_candidate.exists():
                return str(local_candidate)
        found = shutil.which(clean)
        return found or None

    candidates: List[str] = []
    if suffix:
        candidates.append(clean)
    else:
        pathext = os.environ.get("PATHEXT") or ".COM;.EXE;.BAT;.CMD"
        exts = [ext for ext in pathext.split(os.pathsep) if ext]
        preferred_exts = [".cmd", ".exe", ".bat", ".com"]
        ordered_exts = preferred_exts + [ext.lower() for ext in exts if ext.lower() not in preferred_exts]
        candidates.extend(clean + ext for ext in ordered_exts)
        candidates.extend(clean + ext.upper() for ext in ordered_exts)

    if path_like:
        for candidate in candidates:
            path = Path(candidate)
            if path.exists():
                return str(path)
        return None

    if local_bin:
        for candidate in candidates:
            path = local_bin / candidate
            if path.exists():
                return str(path)
    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return found
    found = shutil.which(clean)
    if found and Path(found).suffix:
        return found
    return None


def resolve_local_tool_executable(executable: str, cwd: Optional[Path]) -> Optional[str]:
    clean = str(executable or "").strip().strip('"')
    local_bin = local_node_bin_dir(cwd)
    if not clean or not local_bin:
        return None
    suffix = Path(clean).suffix
    names: List[str] = [clean] if suffix else [clean]
    if os.name == "nt" and not suffix:
        names = []
        pathext = os.environ.get("PATHEXT") or ".COM;.EXE;.BAT;.CMD"
        preferred_exts = [".cmd", ".exe", ".bat", ".com"]
        exts = preferred_exts + [ext.lower() for ext in pathext.split(os.pathsep) if ext and ext.lower() not in preferred_exts]
        names.extend(clean + ext for ext in exts)
        names.extend(clean + ext.upper() for ext in exts)
    for name in names:
        path = local_bin / name
        if path.exists():
            return str(path)
    return None


def rewrite_local_tool_command(command: List[str], cwd: Optional[Path]) -> List[str]:
    if not command:
        return command
    first = command_stem(command[0])
    if first == "corepack":
        return command
    candidates: List[List[str]] = []
    if first == "npx" and len(command) >= 2:
        candidates.append(command[1:])
    elif first == "pnpm" and len(command) >= 3 and command[1].lower() == "exec":
        candidates.append(command[2:])
    elif first == "yarn" and len(command) >= 2:
        candidates.append(command[1:])
    for candidate in candidates:
        if candidate:
            local = resolve_local_tool_executable(candidate[0], cwd=cwd)
            if local:
                return [local, *candidate[1:]]
    if first in COREPACK_MANAGED_TOOLS and resolve_command_executable("corepack", cwd=cwd):
        return ["corepack", *command]
    return command


def split_container_binds(value: str) -> List[str]:
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def command_is_container_exec(command: Sequence[str], runtime: str) -> bool:
    if len(command) < 2 or str(command[1]) != "exec":
        return False
    first = str(command[0])
    runtime_text = str(runtime or "")
    if first == runtime_text:
        return True
    return command_stem(first) == command_stem(runtime_text)


def container_wrapping_requested(command: Sequence[str]) -> bool:
    runtime = os.environ.get(CONTAINER_RUNTIME_ENV, "").strip()
    image = os.environ.get(CONTAINER_IMAGE_ENV, "").strip()
    first = command_stem(command[0]) if command else ""
    return bool(runtime and image and first not in HOST_ONLY_COMMANDS and not command_is_container_exec(command, runtime))


def rewrite_container_tool_command(command: List[str]) -> List[str]:
    first = command_stem(command[0]) if command else ""
    if first in COREPACK_MANAGED_TOOLS:
        return ["corepack", *command]
    return command


def container_env_assignments() -> List[str]:
    assignments: List[str] = []
    if os.environ.get(TOOL_BIN_ENV):
        key = path_env_key(dict(os.environ))
        path_value = os.environ.get(key, "")
        if path_value:
            assignments.append(f"PATH={path_value}")
    for name in CONTAINER_ENV_PASSTHROUGH:
        value = os.environ.get(name)
        if value:
            assignments.append(f"{name}={value}")
    return assignments


def wrap_container_command(command: List[str], cwd: Optional[Path]) -> List[str]:
    runtime = os.environ.get(CONTAINER_RUNTIME_ENV, "").strip()
    image = os.environ.get(CONTAINER_IMAGE_ENV, "").strip()
    if not runtime or not image or command_is_container_exec(command, runtime):
        return command

    resolved_runtime = resolve_command_executable(runtime, cwd=cwd) or runtime
    wrapped = [resolved_runtime, "exec"]
    if cwd:
        wrapped.extend(["--pwd", str(Path(cwd).absolute())])
    for bind in split_container_binds(os.environ.get(CONTAINER_BIND_ENV, "")):
        wrapped.extend(["--bind", bind])
    wrapped.append(image)
    env_assignments = container_env_assignments()
    if env_assignments:
        wrapped.extend(["env", *env_assignments])
    wrapped.extend(command)
    return wrapped


def prepare_subprocess_command(cmd: Sequence[str], cwd: Optional[Path] = None) -> List[str]:
    command = [str(part) for part in cmd]
    if not command:
        return command
    command = rewrite_local_tool_command(command, cwd)
    if container_wrapping_requested(command):
        command = rewrite_container_tool_command(command)
        return wrap_container_command(command, cwd)
    resolved = resolve_command_executable(command[0], cwd=cwd)
    if not resolved:
        command = rewrite_local_tool_command(command, cwd)
        resolved = resolve_command_executable(command[0], cwd=cwd)
    if resolved:
        command[0] = resolved
    if container_wrapping_requested(command):
        command = rewrite_container_tool_command(command)
        return wrap_container_command(command, cwd)
    return command


def require_inputs(paths: Sequence[Path]) -> None:
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        raise FileNotFoundError("Missing required input(s): " + ", ".join(missing))


def add_lib_to_path() -> None:
    lib_dir = Path(__file__).resolve().parent
    if str(lib_dir) not in sys.path:
        sys.path.insert(0, str(lib_dir))
