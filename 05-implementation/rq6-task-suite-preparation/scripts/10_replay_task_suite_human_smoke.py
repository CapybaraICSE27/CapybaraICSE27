#!/usr/bin/env python3
"""Replay transferred RQ6 task-suite human baselines on the compute cluster.

This runner preserves the successful the compute cluster v6 smoke-harness behavior while
making suite paths, task caps, and output paths configurable for Slurm jobs.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import threading
import time
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from shlex import quote
from typing import Any, Dict, Iterable, List, Optional, Sequence


DEFAULT_REPOS = [
    "swup/swup",
    "openplayerjs/openplayerjs",
    "motiondivision/motion-vue",
    "zuplo/zudoku",
]

DEFAULT_RERUN_STATUSES = [
    "failed",
    "timeout",
    "pretest_setup_failed",
    "app_boot_failed",
    "browser_install_failed",
    "install_failed",
    "missing_repo",
]

DEFAULT_PILOT_DIRS = {
    "swup/swup": "phase1_execution_pilot_v4_swup_expanded",
    "openplayerjs/openplayerjs": "phase1_execution_pilot_v4_openplayer_targeted_stable",
    "motiondivision/motion-vue": "phase1_execution_pilot_v4_motion_vue_targeted",
    "zuplo/zudoku": "phase1_execution_pilot_v4_zudoku_targeted",
}

REPO_PRETEST_SETUP_OVERRIDES = {
    "swup/swup": [
        {
            "setup_id": "build_swup_dist",
            "command": "npm run build",
            "required_paths": ["dist/Swup.modern.js"],
            "setup_reason": "build dist before swup Playwright webServer instruments and serves it",
        }
    ],
}

PLAYWRIGHT_WEBSERVER_REPO_KEYS = {
    "gridstack__gridstack.js",
    "swup__swup",
    "openplayerjs__openplayerjs",
    "motiondivision__motion-vue",
    "zuplo__zudoku",
}

GENERATED_DIRS = {
    ".git",
    "node_modules",
    "test-results",
    "playwright-report",
    ".cache",
    ".turbo",
    ".next",
    ".nuxt",
    "dist",
    "build",
    "coverage",
}

JSONL_LOCK = threading.Lock()
PROGRESS_LOCK = threading.Lock()


def repo_cache_key(repo_full_name: str) -> str:
    return str(repo_full_name or "").replace("/", "__").replace(":", "_")


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with JSONL_LOCK:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def read_repo_file(path: Optional[Path]) -> List[str]:
    if path is None:
        return []
    repos: List[str] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            clean = line.strip()
            if not clean or clean.startswith("#"):
                continue
            if "," in clean:
                clean = clean.split(",", 1)[0].strip()
            repos.append(clean)
    return repos


def split_tokens(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        tokens: List[str] = []
        for item in value:
            tokens.extend(split_tokens(item))
        return tokens
    text = str(value).replace(",", " ").replace(";", " ")
    return [token.strip() for token in text.split() if token.strip()]


def read_token_file(path: Optional[Path]) -> List[str]:
    if path is None:
        return []
    tokens: List[str] = []
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            clean = line.split("#", 1)[0].strip()
            tokens.extend(split_tokens(clean))
    return tokens


def env_int(value: Any, default: int) -> int:
    try:
        text = str(value or "").strip()
        if not text:
            return default
        return int(text)
    except (TypeError, ValueError):
        return default


def env_bool(value: Any, default: bool = False) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return default
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def progress_line(event: str, **fields: Any) -> str:
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    parts = [f"[rq6-replay {timestamp}]", str(event)]
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, (dict, list)):
            clean = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            clean = str(value)
        parts.append(f"{key}={clean}")
    return " ".join(parts)


def progress(event: str, **fields: Any) -> None:
    with PROGRESS_LOCK:
        print(progress_line(event, **fields), flush=True)


def effective_repo_workers(value: int, *, repo_total: int) -> int:
    if repo_total <= 0:
        return 1
    return max(1, min(int(value or 1), repo_total))


def timeout_value(value: int) -> Optional[int]:
    value = int(value or 0)
    return value if value > 0 else None


def env_path(name: str) -> Optional[Path]:
    value = os.environ.get(name, "").strip()
    return Path(value) if value else None


def repo_workdir(args: argparse.Namespace, repo_key: str) -> Path:
    root = getattr(args, "workdir_root", None) or (Path(args.out_dir) / "workdirs")
    return Path(root) / repo_key


def repo_tool_cache_root(args: argparse.Namespace, repo_key: str) -> Path:
    root = getattr(args, "tool_cache_root", None) or (Path(args.out_dir) / "tool_cache")
    return Path(root) / repo_key


def should_skip_install(args: argparse.Namespace, workdir: Path) -> bool:
    return bool(getattr(args, "reuse_installed_workdirs", False)) and (Path(workdir) / "node_modules").is_dir()


def has_cached_playwright_browser(cache_root: Path) -> bool:
    browser_root = Path(cache_root) / "playwright-browsers"
    if not browser_root.is_dir():
        return False
    return any(path.name.startswith("chromium") for path in browser_root.iterdir())


def filter_plan_by_task_ids(
    plan: Sequence[Dict[str, Any]],
    task_ids: Sequence[str],
) -> List[Dict[str, Any]]:
    selected = {str(task_id) for task_id in task_ids if str(task_id).strip()}
    if not selected:
        return [dict(row) for row in plan]
    return [dict(row) for row in plan if str(row.get("task_id") or "") in selected]


def filter_plan_by_previous_results(
    plan: Sequence[Dict[str, Any]],
    *,
    previous_results: Path,
    statuses: Sequence[str],
) -> List[Dict[str, Any]]:
    previous_results = Path(previous_results)
    wanted_statuses = {str(status) for status in statuses if str(status).strip()}
    selected_task_ids: set[str] = set()
    for row in read_jsonl(previous_results):
        status = str(row.get("status") or "")
        if wanted_statuses and status not in wanted_statuses:
            continue
        task_id = str(row.get("task_id") or "")
        if task_id:
            selected_task_ids.add(task_id)
    return [dict(row) for row in plan if str(row.get("task_id") or "") in selected_task_ids]


def effective_setup_timeout(
    setup: Dict[str, Any],
    *,
    default_timeout: int,
    min_timeout: int,
) -> int:
    timeout = env_int(setup.get("timeout_sec"), default_timeout)
    if timeout <= 0 and int(default_timeout or 0) > 0:
        timeout = int(default_timeout)
    if int(min_timeout or 0) > 0:
        timeout = max(timeout, int(min_timeout))
    return timeout


def load_package_json(workdir: Path) -> Dict[str, Any]:
    path = Path(workdir) / "package.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return {}


def package_manager_field_version(package_json: Dict[str, Any], manager: str, default: str) -> str:
    value = str(package_json.get("packageManager") or "")
    prefix = f"{manager}@"
    if value.startswith(prefix):
        return value.split("@", 1)[1].split("+", 1)[0]
    return default


def pnpm_prepare(package_json: Dict[str, Any]) -> str:
    version = package_manager_field_version(package_json, "pnpm", "10.33.0")
    return f"corepack prepare pnpm@{quote(version)} --activate"


def yarn_prepare(package_json: Dict[str, Any]) -> str:
    version = package_manager_field_version(package_json, "yarn", "1.22.22")
    return f"corepack prepare yarn@{quote(version)} --activate"


def uses_pnpm(workdir: Path, package_json: Optional[Dict[str, Any]] = None) -> bool:
    package_json = package_json if package_json is not None else load_package_json(workdir)
    return (Path(workdir) / "pnpm-lock.yaml").exists() or str(
        package_json.get("packageManager") or ""
    ).startswith("pnpm@")


def uses_yarn(workdir: Path, package_json: Optional[Dict[str, Any]] = None) -> bool:
    package_json = package_json if package_json is not None else load_package_json(workdir)
    return (Path(workdir) / "yarn.lock").exists() or str(
        package_json.get("packageManager") or ""
    ).startswith("yarn@")


def install_command(workdir: Path) -> str:
    workdir = Path(workdir)
    package_json = load_package_json(workdir)
    if uses_pnpm(workdir, package_json):
        return pnpm_prepare(package_json) + " && pnpm install --frozen-lockfile --config.engine-strict=false"
    if uses_yarn(workdir, package_json):
        immutable = "--immutable" if (workdir / ".yarnrc.yml").exists() else "--frozen-lockfile"
        return yarn_prepare(package_json) + f" && yarn install {immutable}"
    if (workdir / "package-lock.json").exists() or (workdir / "npm-shrinkwrap.json").exists():
        return "npm ci"
    return "npm install"


def playwright_install_command(workdir: Path) -> str:
    workdir = Path(workdir)
    package_json = load_package_json(workdir)
    if uses_pnpm(workdir, package_json):
        return pnpm_prepare(package_json) + " && pnpm exec playwright install chromium"
    if uses_yarn(workdir, package_json):
        return yarn_prepare(package_json) + " && yarn exec playwright install chromium"
    return "npx playwright install chromium"


def split_required_paths(entry: Dict[str, Any]) -> List[str]:
    raw = entry.get("required_paths_json")
    if raw:
        try:
            value = json.loads(raw)
            if isinstance(value, list):
                return [str(item) for item in value]
        except (TypeError, json.JSONDecodeError):
            pass
    raw = entry.get("required_paths")
    if isinstance(raw, list):
        return [str(item) for item in raw]
    if isinstance(raw, str) and raw.strip():
        if raw.strip().startswith("["):
            try:
                value = json.loads(raw)
                if isinstance(value, list):
                    return [str(item) for item in value]
            except json.JSONDecodeError:
                pass
        return [raw.strip()]
    return []


def select_manifest_rows(
    manifest_rows: Sequence[Dict[str, Any]],
    *,
    repos: Optional[Sequence[str]] = None,
    tasks_per_repo: int = 0,
    max_tasks: int = 0,
) -> List[Dict[str, Any]]:
    repo_filter = {str(repo) for repo in repos or [] if str(repo).strip()}
    repo_filter.update(repo_cache_key(repo) for repo in list(repo_filter))
    counts: Counter[str] = Counter()
    selected: List[Dict[str, Any]] = []
    for row in manifest_rows:
        repo = str(row.get("repo_full_name") or "")
        key = str(row.get("repo_cache_key") or repo_cache_key(repo))
        if repo_filter and repo not in repo_filter and key not in repo_filter:
            continue
        if tasks_per_repo > 0 and counts[repo] >= tasks_per_repo:
            continue
        selected.append(dict(row))
        counts[repo] += 1
        if max_tasks > 0 and len(selected) >= max_tasks:
            break
    return selected


def passing_baseline_by_id(path: Path) -> Dict[str, Dict[str, Any]]:
    rows = [row for row in read_jsonl(path) if row.get("status") == "pass"]
    by_id: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        for key in (
            row.get("test_id"),
            row.get("representative_test_id"),
            row.get("execution_target_id"),
        ):
            if key:
                by_id.setdefault(str(key), row)
    return by_id


def normalize_python_server(command: str) -> str:
    return str(command or "").replace("python -m http.server", "/usr/bin/python3 -m http.server")


def build_replay_plan(
    *,
    suite_dir: Path,
    evidence_root: Path,
    repos: Optional[Sequence[str]],
    tasks_per_repo: int,
    max_tasks: int,
) -> List[Dict[str, Any]]:
    manifest_rows = read_jsonl(Path(suite_dir) / "rq6_tasks_manifest.jsonl")
    specs = {str(row.get("task_id")): row for row in read_jsonl(Path(suite_dir) / "agent_task_specs.jsonl")}
    selected = select_manifest_rows(
        manifest_rows,
        repos=repos or DEFAULT_REPOS,
        tasks_per_repo=tasks_per_repo,
        max_tasks=max_tasks,
    )

    baseline_cache: Dict[str, Dict[str, Dict[str, Any]]] = {}
    plan: List[Dict[str, Any]] = []
    for task in selected:
        repo = str(task.get("repo_full_name") or "")
        pilot_dir = DEFAULT_PILOT_DIRS.get(repo)
        manifest_command = str(task.get("human_command") or "")
        if not pilot_dir and not manifest_command:
            raise RuntimeError(f"No pilot evidence directory is configured for {repo}")
        if pilot_dir and repo not in baseline_cache:
            baseline_cache[repo] = passing_baseline_by_id(
                Path(evidence_root) / pilot_dir / "human_test_baseline_runs.jsonl"
            )
        source_test_id = str(task.get("source_test_id") or "")
        baseline = baseline_cache.get(repo, {}).get(source_test_id)
        if baseline is None and not manifest_command:
            raise RuntimeError(f"No passing baseline row for {task.get('task_id')} {source_test_id}")
        spec = specs.get(str(task.get("task_id"))) or {}
        baseline = baseline or {}
        app_start = baseline.get("app_start_command") or task.get("app_start_command") or spec.get("app_start_command") or ""
        setup_commands = list(spec.get("pretest_setup_commands") or [])
        setup_commands.extend(REPO_PRETEST_SETUP_OVERRIDES.get(repo, []))
        plan.append(
            {
                "task_id": task.get("task_id"),
                "repo_full_name": repo,
                "repo_cache_key": task.get("repo_cache_key") or repo_cache_key(repo),
                "source_test_id": source_test_id,
                "source_file": task.get("source_file"),
                "test_name": task.get("test_name"),
                "human_command": baseline.get("command") or manifest_command,
                "app_start_command": normalize_python_server(str(app_start)),
                "app_boot_url": baseline.get("app_boot_url") or task.get("base_url") or spec.get("base_url") or "",
                "pretest_setup_commands": setup_commands,
            }
        )
    return plan


def ignore_generated(parent: str, names: Sequence[str]) -> set[str]:
    parent_parts = {part.lower() for part in Path(parent).parts}
    ignored: set[str] = set()
    for name in names:
        if name not in GENERATED_DIRS:
            continue
        if name in {"build", "dist"} and "src" in parent_parts:
            continue
        ignored.add(name)
    return ignored


def make_container_base() -> List[str]:
    runtime = os.environ.get("RQ6_CONTAINER_RUNTIME", "").strip()
    image = os.environ.get("RQ6_CONTAINER_IMAGE", "").strip()
    if not runtime or not image:
        return []
    command = [runtime, "exec"]
    bind = os.environ.get("RQ6_CONTAINER_BIND", "").strip()
    if bind:
        command.extend(["--bind", bind])
    command.append(image)
    return command


def quote_path(path: Path) -> str:
    return quote(Path(path).as_posix())


def shell_script(
    command: str,
    cwd: Path,
    *,
    out_dir: Path,
    cache_root: Optional[Path] = None,
    node_tool_bin_dir: Optional[Path] = None,
    node22_dir: Optional[Path] = None,
) -> str:
    node22_dir = node22_dir or Path(
        os.environ.get(
            "RQ6_NODE22_DIR",
            str(Path(os.environ.get("HPC_DATA", "")) / "tools" / "node-v22.12.0-linux-x64"),
        )
    )
    cache_root = cache_root or (out_dir / "tool_cache")
    lines = [
        "set -euo pipefail",
        f"cd {quote_path(cwd)}",
        f"export RQ6_REPLAY_OUT={quote_path(out_dir)}",
        f"export COREPACK_HOME={quote_path(cache_root / 'corepack')}",
        f"export PNPM_HOME={quote_path(cache_root / 'pnpm-home')}",
        f"export npm_config_cache={quote_path(cache_root / 'npm-cache')}",
        f"export PLAYWRIGHT_BROWSERS_PATH={quote_path(cache_root / 'playwright-browsers')}",
        "mkdir -p \"$COREPACK_HOME\" \"$PNPM_HOME\" \"$npm_config_cache\" \"$PLAYWRIGHT_BROWSERS_PATH\"",
        "export CI=1",
    ]
    if node_tool_bin_dir:
        lines.append(f"export PATH={quote_path(node_tool_bin_dir)}:$PATH")
    lines.extend(
        [
            f"export PATH={quote_path(node22_dir / 'bin')}:$PATH",
            "export PATH=$PNPM_HOME:$PATH",
            "export COREPACK_ENABLE_DOWNLOAD_PROMPT=0",
            "export COREPACK_INTEGRITY_KEYS=0",
            f"export RQ6_NODE22_BIN={quote_path(node22_dir / 'bin' / 'node')}",
            f"export RQ6_COREPACK_JS={quote_path(node22_dir / 'lib' / 'node_modules' / 'corepack' / 'dist' / 'corepack.js')}",
            'cat > "$PNPM_HOME/corepack" <<\'RQ6_COREPACK_SHIM\'',
            "#!/usr/bin/env bash",
            'exec "$RQ6_NODE22_BIN" "$RQ6_COREPACK_JS" "$@"',
            "RQ6_COREPACK_SHIM",
            'cat > "$PNPM_HOME/pnpm" <<\'RQ6_PNPM_SHIM\'',
            "#!/usr/bin/env bash",
            'exec "$RQ6_NODE22_BIN" "$RQ6_COREPACK_JS" pnpm "$@"',
            "RQ6_PNPM_SHIM",
            'cat > "$PNPM_HOME/pnpx" <<\'RQ6_PNPX_SHIM\'',
            "#!/usr/bin/env bash",
            'exec "$RQ6_NODE22_BIN" "$RQ6_COREPACK_JS" pnpx "$@"',
            "RQ6_PNPX_SHIM",
            'cat > "$PNPM_HOME/yarn" <<\'RQ6_YARN_SHIM\'',
            "#!/usr/bin/env bash",
            'exec "$RQ6_NODE22_BIN" "$RQ6_COREPACK_JS" yarn "$@"',
            "RQ6_YARN_SHIM",
            'chmod +x "$PNPM_HOME/corepack" "$PNPM_HOME/pnpm" "$PNPM_HOME/pnpx" "$PNPM_HOME/yarn"',
            'corepack() { "$RQ6_NODE22_BIN" "$RQ6_COREPACK_JS" "$@"; }',
            'pnpm() { "$RQ6_NODE22_BIN" "$RQ6_COREPACK_JS" pnpm "$@"; }',
            'pnpx() { "$RQ6_NODE22_BIN" "$RQ6_COREPACK_JS" pnpx "$@"; }',
            'yarn() { "$RQ6_NODE22_BIN" "$RQ6_COREPACK_JS" yarn "$@"; }',
            command,
        ]
    )
    return "\n".join(lines)


def container_shell_command(
    command: str,
    cwd: Path,
    *,
    out_dir: Path,
    cache_root: Path,
    node_tool_bin_dir: Optional[Path],
    node22_dir: Optional[Path],
) -> List[str]:
    base = make_container_base()
    return base + [
        "bash",
        "-lc",
        shell_script(
            command,
            cwd,
            out_dir=out_dir,
            cache_root=cache_root,
            node_tool_bin_dir=node_tool_bin_dir,
            node22_dir=node22_dir,
        ),
    ]


def run_container(
    command: str,
    cwd: Path,
    stdout_path: Path,
    stderr_path: Path,
    *,
    timeout: int,
    out_dir: Path,
    cache_root: Path,
    node_tool_bin_dir: Optional[Path],
    node22_dir: Optional[Path],
) -> Dict[str, Any]:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    full = container_shell_command(
        command,
        cwd,
        out_dir=out_dir,
        cache_root=cache_root,
        node_tool_bin_dir=node_tool_bin_dir,
        node22_dir=node22_dir,
    )
    started = time.time()
    timeout_value_sec = timeout_value(timeout)
    with stdout_path.open("w", encoding="utf-8", errors="replace") as out, stderr_path.open(
        "w", encoding="utf-8", errors="replace"
    ) as err:
        try:
            proc = subprocess.run(full, stdout=out, stderr=err, timeout=timeout_value_sec, text=True)
            return {
                "exit_code": proc.returncode,
                "timed_out": False,
                "duration_sec": round(time.time() - started, 2),
                "timeout_sec": timeout_value_sec,
            }
        except subprocess.TimeoutExpired:
            return {
                "exit_code": None,
                "timed_out": True,
                "duration_sec": round(time.time() - started, 2),
                "timeout_sec": timeout_value_sec,
            }


def start_container(
    command: str,
    cwd: Path,
    stdout_path: Path,
    stderr_path: Path,
    *,
    out_dir: Path,
    cache_root: Path,
    node_tool_bin_dir: Optional[Path],
    node22_dir: Optional[Path],
):
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    full = container_shell_command(
        command,
        cwd,
        out_dir=out_dir,
        cache_root=cache_root,
        node_tool_bin_dir=node_tool_bin_dir,
        node22_dir=node22_dir,
    )
    out = stdout_path.open("w", encoding="utf-8", errors="replace")
    err = stderr_path.open("w", encoding="utf-8", errors="replace")
    kwargs: Dict[str, Any] = {}
    if os.name != "nt":
        kwargs["preexec_fn"] = os.setsid
    proc = subprocess.Popen(full, stdout=out, stderr=err, text=True, **kwargs)
    return proc, out, err


def stop_process(proc, out, err) -> None:
    if proc.poll() is None:
        try:
            if os.name != "nt":
                os.killpg(proc.pid, signal.SIGTERM)
            else:
                proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            try:
                if os.name != "nt":
                    os.killpg(proc.pid, signal.SIGKILL)
                else:
                    proc.kill()
            except Exception:
                pass
    out.close()
    err.close()


def wait_url(url: str, timeout: int = 120) -> Dict[str, Any]:
    if not url:
        return {"ok": False, "status": None, "error": "missing_url", "duration_sec": 0.0}
    started = time.time()
    last_error = ""
    while time.time() - started < timeout:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                status = getattr(resp, "status", resp.getcode())
                if 200 <= int(status) < 500:
                    return {
                        "ok": True,
                        "status": int(status),
                        "error": "",
                        "duration_sec": round(time.time() - started, 2),
                    }
        except Exception as exc:
            last_error = str(exc)
        time.sleep(2)
    return {
        "ok": False,
        "status": None,
        "error": last_error,
        "duration_sec": round(time.time() - started, 2),
    }


def should_start_app(repo_key: str, command: str, mode: str = "auto") -> bool:
    if not str(command or "").strip():
        return False
    clean_mode = str(mode or "auto").strip().lower()
    if clean_mode in {"never", "false", "0", "no"}:
        return False
    if clean_mode in {"force", "always", "true", "1", "yes"}:
        return True
    return repo_key not in PLAYWRIGHT_WEBSERVER_REPO_KEYS


def run_setup_commands(
    *,
    rows: Sequence[Dict[str, Any]],
    workdir: Path,
    repo_log: Path,
    cache_root: Path,
    args: argparse.Namespace,
) -> Optional[Dict[str, Any]]:
    seen_setup: set[str] = set()
    for row in rows:
        for setup in row.get("pretest_setup_commands") or []:
            setup_id = str(setup.get("setup_id") or setup.get("command") or "setup")
            if setup_id in seen_setup:
                continue
            seen_setup.add(setup_id)
            required = split_required_paths(setup)
            if required and all((workdir / rel).exists() for rel in required):
                continue
            setup_cwd = workdir / str(setup.get("cwd_rel") or ".")
            timeout = effective_setup_timeout(
                setup,
                default_timeout=args.setup_timeout_sec,
                min_timeout=args.min_setup_timeout_sec,
            )
            result = run_container(
                str(setup["command"]),
                setup_cwd,
                repo_log / f"setup_{setup_id}.stdout.log",
                repo_log / f"setup_{setup_id}.stderr.log",
                timeout=timeout,
                out_dir=args.out_dir,
                cache_root=cache_root,
                node_tool_bin_dir=args.node_tool_bin_dir,
                node22_dir=args.node22_dir,
            )
            if result["exit_code"] != 0 or result["timed_out"]:
                return {"setup_id": setup_id, "result": result}
    return None


def replay_repo_rows(
    *,
    repo_key: str,
    rows: Sequence[Dict[str, Any]],
    repo_index: int,
    repo_total: int,
    results_path: Path,
    args: argparse.Namespace,
) -> None:
    repo = str(rows[0]["repo_full_name"])
    src = args.repo_cache / repo_key
    workdir = repo_workdir(args, repo_key)
    repo_log = args.out_dir / "logs" / repo_key
    cache_root = repo_tool_cache_root(args, repo_key)
    repo_log.mkdir(parents=True, exist_ok=True)

    progress(
        "repo_start",
        repo_index=repo_index,
        repo_total=repo_total,
        repo=repo,
        repo_key=repo_key,
        tasks=len(rows),
    )
    if not src.is_dir():
        progress("repo_missing", repo=repo, repo_key=repo_key, source=src)
        for row in rows:
            append_jsonl(results_path, {**row, "stage": "copy", "status": "missing_repo", "workdir": str(workdir)})
        return

    progress("copy_start", repo=repo, repo_key=repo_key, source=src, workdir=workdir)
    if args.refresh_workdir and workdir.exists():
        shutil.rmtree(workdir)
    if not workdir.exists():
        shutil.copytree(src, workdir, ignore=ignore_generated)
    progress("copy_done", repo=repo, repo_key=repo_key, workdir=workdir)

    progress("git_init_start", repo=repo, repo_key=repo_key)
    git_result = run_container(
        "git init",
        workdir,
        repo_log / "git_init.stdout.log",
        repo_log / "git_init.stderr.log",
        timeout=60,
        out_dir=args.out_dir,
        cache_root=cache_root,
        node_tool_bin_dir=args.node_tool_bin_dir,
        node22_dir=args.node22_dir,
    )
    progress(
        "git_init_done",
        repo=repo,
        repo_key=repo_key,
        exit_code=git_result.get("exit_code"),
        timed_out=git_result.get("timed_out"),
        duration_sec=git_result.get("duration_sec"),
    )
    install = install_command(workdir)
    if should_skip_install(args, workdir):
        install_result = {
            "exit_code": 0,
            "timed_out": False,
            "duration_sec": 0.0,
            "timeout_sec": None,
            "reused_existing": True,
        }
        progress("install_skipped", repo=repo, repo_key=repo_key, reason="reused_installed_workdir")
    else:
        progress("install_start", repo=repo, repo_key=repo_key, command=install)
        install_result = run_container(
            install,
            workdir,
            repo_log / "install.stdout.log",
            repo_log / "install.stderr.log",
            timeout=args.install_timeout_sec,
            out_dir=args.out_dir,
            cache_root=cache_root,
            node_tool_bin_dir=args.node_tool_bin_dir,
            node22_dir=args.node22_dir,
        )
        progress(
            "install_done",
            repo=repo,
            repo_key=repo_key,
            exit_code=install_result.get("exit_code"),
            timed_out=install_result.get("timed_out"),
            duration_sec=install_result.get("duration_sec"),
        )
    if install_result["exit_code"] != 0 or install_result["timed_out"]:
        progress("repo_stop", repo=repo, repo_key=repo_key, status="install_failed")
        for row in rows:
            append_jsonl(
                results_path,
                {
                    **row,
                    "stage": "install",
                    "status": "install_failed",
                    "git_init": git_result,
                    "install_command": install,
                    "install": install_result,
                    "workdir": str(workdir),
                },
            )
        return

    browser_cmd = playwright_install_command(workdir)
    if bool(getattr(args, "reuse_installed_workdirs", False)) and has_cached_playwright_browser(cache_root):
        browser_result = {
            "exit_code": 0,
            "timed_out": False,
            "duration_sec": 0.0,
            "timeout_sec": None,
            "reused_existing": True,
        }
        progress("browser_install_skipped", repo=repo, repo_key=repo_key, reason="reused_browser_cache")
    else:
        progress("browser_install_start", repo=repo, repo_key=repo_key, command=browser_cmd)
        browser_result = run_container(
            browser_cmd,
            workdir,
            repo_log / "playwright_install.stdout.log",
            repo_log / "playwright_install.stderr.log",
            timeout=args.browser_install_timeout_sec,
            out_dir=args.out_dir,
            cache_root=cache_root,
            node_tool_bin_dir=args.node_tool_bin_dir,
            node22_dir=args.node22_dir,
        )
        progress(
            "browser_install_done",
            repo=repo,
            repo_key=repo_key,
            exit_code=browser_result.get("exit_code"),
            timed_out=browser_result.get("timed_out"),
            duration_sec=browser_result.get("duration_sec"),
        )
    if browser_result["exit_code"] != 0 or browser_result["timed_out"]:
        progress("repo_stop", repo=repo, repo_key=repo_key, status="browser_install_failed")
        for row in rows:
            append_jsonl(
                results_path,
                {
                    **row,
                    "stage": "browser_install",
                    "status": "browser_install_failed",
                    "git_init": git_result,
                    "install_command": install,
                    "browser_install_command": browser_cmd,
                    "browser_install": browser_result,
                    "workdir": str(workdir),
                },
            )
        return

    progress("pretest_setup_start", repo=repo, repo_key=repo_key)
    setup_failed = run_setup_commands(rows=rows, workdir=workdir, repo_log=repo_log, cache_root=cache_root, args=args)
    if setup_failed:
        progress("repo_stop", repo=repo, repo_key=repo_key, status="pretest_setup_failed", setup_failure=setup_failed)
        for row in rows:
            append_jsonl(
                results_path,
                {
                    **row,
                    "stage": "pretest_setup",
                    "status": "pretest_setup_failed",
                    "setup_failure": setup_failed,
                    "workdir": str(workdir),
                },
            )
        return
    progress("pretest_setup_done", repo=repo, repo_key=repo_key, status="pass")

    app_command = str(rows[0].get("app_start_command") or "")
    app_url = str(rows[0].get("app_boot_url") or "")
    app_proc = app_out = app_err = None
    app_boot = {"ok": True, "status": None, "error": "not_required", "duration_sec": 0.0}
    try:
        if should_start_app(repo_key, app_command, args.app_start_mode):
            progress("app_boot_start", repo=repo, repo_key=repo_key, url=app_url, command=app_command)
            app_proc, app_out, app_err = start_container(
                app_command,
                workdir,
                repo_log / "app.stdout.log",
                repo_log / "app.stderr.log",
                out_dir=args.out_dir,
                cache_root=cache_root,
                node_tool_bin_dir=args.node_tool_bin_dir,
                node22_dir=args.node22_dir,
            )
            app_boot = wait_url(app_url, timeout=args.app_boot_timeout_sec)
            progress("app_boot_done", repo=repo, repo_key=repo_key, ok=app_boot.get("ok"), app_boot=app_boot)
            if not app_boot["ok"]:
                progress("repo_stop", repo=repo, repo_key=repo_key, status="app_boot_failed")
                for row in rows:
                    append_jsonl(
                        results_path,
                        {
                            **row,
                            "stage": "app_boot",
                            "status": "app_boot_failed",
                            "app_boot": app_boot,
                            "workdir": str(workdir),
                        },
                    )
                return
        else:
            progress("app_boot_skipped", repo=repo, repo_key=repo_key, mode=args.app_start_mode)

        status_counts: Counter[str] = Counter()
        for task_index, row in enumerate(rows, start=1):
            token = str(row["task_id"])
            progress(
                "task_start",
                repo=repo,
                repo_key=repo_key,
                task_index=task_index,
                task_total=len(rows),
                task_id=token,
            )
            result = run_container(
                str(row["human_command"]),
                workdir,
                repo_log / f"{token}.stdout.log",
                repo_log / f"{token}.stderr.log",
                timeout=args.test_timeout_sec,
                out_dir=args.out_dir,
                cache_root=cache_root,
                node_tool_bin_dir=args.node_tool_bin_dir,
                node22_dir=args.node22_dir,
            )
            status = "pass" if result["exit_code"] == 0 and not result["timed_out"] else (
                "timeout" if result["timed_out"] else "failed"
            )
            status_counts[status] += 1
            append_jsonl(
                results_path,
                {
                    **row,
                    "stage": "test",
                    "status": status,
                    "test_result": result,
                    "app_boot": app_boot,
                    "workdir": str(workdir),
                    "git_init": git_result,
                    "install_command": install,
                    "browser_install_command": browser_cmd,
                },
            )
            progress(
                "task_done",
                repo=repo,
                repo_key=repo_key,
                task_index=task_index,
                task_total=len(rows),
                task_id=token,
                status=status,
                exit_code=result.get("exit_code"),
                timed_out=result.get("timed_out"),
                duration_sec=result.get("duration_sec"),
                repo_status_counts=dict(status_counts),
            )
        progress("repo_done", repo=repo, repo_key=repo_key, status_counts=dict(status_counts))
    finally:
        if app_proc is not None:
            stop_process(app_proc, app_out, app_err)
            progress("app_stopped", repo=repo, repo_key=repo_key)


def write_summary(out_dir: Path, results_path: Path) -> Dict[str, Any]:
    rows = read_jsonl(results_path) if results_path.exists() else []
    summary: Dict[str, Any] = {
        "out_dir": str(out_dir),
        "total": len(rows),
        "status_counts": {},
        "repo_status_counts": {},
    }
    status_counts = Counter(str(row.get("status") or "") for row in rows)
    summary["status_counts"] = dict(status_counts)
    repo_counts: Dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        repo_counts[str(row.get("repo_full_name") or "")][str(row.get("status") or "")] += 1
    summary["repo_status_counts"] = {repo: dict(counts) for repo, counts in repo_counts.items()}
    (out_dir / "replay_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-dir", type=Path, default=Path(os.environ.get("RQ6_REPLAY_SUITE_DIR") or os.environ.get("RQ6_TASK_SUITE_DIR", "rq6_outputs/rq6_phase2_task_suite_v2")))
    parser.add_argument("--evidence-root", type=Path, default=None)
    parser.add_argument("--repo-cache", type=Path, default=Path(os.environ.get("HPC_REPOS", "repos_cache")))
    parser.add_argument("--out-dir", type=Path, default=Path(os.environ.get("RQ6_REPLAY_OUT_DIR", "rq6_outputs/replay_task_suite")))
    parser.add_argument("--workdir-root", type=Path, default=env_path("RQ6_REPLAY_WORKDIR_ROOT"))
    parser.add_argument("--tool-cache-root", type=Path, default=env_path("RQ6_REPLAY_TOOL_CACHE_ROOT"))
    parser.add_argument("--repo", action="append", default=[], help="Repo full name or cache key to replay. May repeat.")
    parser.add_argument("--repos", default=os.environ.get("RQ6_REPLAY_REPOS", ""), help="Comma, semicolon, or whitespace separated repos to replay.")
    parser.add_argument("--repos-file", type=Path, default=None)
    parser.add_argument("--task-id", action="append", default=[], help="Task id to replay. May repeat.")
    parser.add_argument("--task-ids", default=os.environ.get("RQ6_REPLAY_TASK_IDS", ""), help="Comma, semicolon, or whitespace separated task ids to replay.")
    parser.add_argument("--task-ids-file", type=Path, default=env_path("RQ6_REPLAY_TASK_IDS_FILE"))
    parser.add_argument("--previous-results", type=Path, default=env_path("RQ6_REPLAY_PREVIOUS_RESULTS"), help="Previous replay_results.jsonl used to select failed/timed-out tasks.")
    parser.add_argument("--rerun-statuses", default=os.environ.get("RQ6_REPLAY_RERUN_STATUSES", ",".join(DEFAULT_RERUN_STATUSES)))
    parser.add_argument("--tasks-per-repo", type=int, default=env_int(os.environ.get("RQ6_REPLAY_TASKS_PER_REPO"), 0))
    parser.add_argument("--max-tasks", type=int, default=env_int(os.environ.get("RQ6_REPLAY_MAX_TASKS"), 0))
    parser.add_argument("--node-tool-bin-dir", type=Path, default=Path(os.environ["NODE_TOOL_BIN_DIR"]) if os.environ.get("NODE_TOOL_BIN_DIR") else None)
    parser.add_argument("--node22-dir", type=Path, default=Path(os.environ["RQ6_NODE22_DIR"]) if os.environ.get("RQ6_NODE22_DIR") else None)
    parser.add_argument("--install-timeout-sec", type=int, default=env_int(os.environ.get("RQ6_REPLAY_INSTALL_TIMEOUT_SEC"), 1800))
    parser.add_argument("--browser-install-timeout-sec", type=int, default=env_int(os.environ.get("RQ6_REPLAY_BROWSER_INSTALL_TIMEOUT_SEC"), 1200))
    parser.add_argument("--setup-timeout-sec", type=int, default=env_int(os.environ.get("RQ6_REPLAY_SETUP_TIMEOUT_SEC"), 900))
    parser.add_argument("--min-setup-timeout-sec", type=int, default=env_int(os.environ.get("RQ6_REPLAY_MIN_SETUP_TIMEOUT_SEC"), 0))
    parser.add_argument("--app-boot-timeout-sec", type=int, default=env_int(os.environ.get("RQ6_REPLAY_APP_BOOT_TIMEOUT_SEC"), 180))
    parser.add_argument("--test-timeout-sec", type=int, default=env_int(os.environ.get("RQ6_REPLAY_TEST_TIMEOUT_SEC"), 420))
    parser.add_argument("--app-start-mode", default=os.environ.get("RQ6_REPLAY_APP_START_MODE", "auto"), choices=["auto", "force", "never"])
    parser.add_argument("--repo-workers", type=int, default=env_int(os.environ.get("RQ6_REPLAY_REPO_WORKERS"), 1))
    parser.add_argument(
        "--keep-workdirs",
        action="store_true",
        default=env_bool(os.environ.get("RQ6_REPLAY_KEEP_WORKDIRS"), False),
        help="Reuse existing copied workdirs instead of refreshing from repo cache.",
    )
    parser.add_argument(
        "--reuse-installed-workdirs",
        action="store_true",
        default=env_bool(os.environ.get("RQ6_REPLAY_REUSE_INSTALLED_WORKDIRS"), False),
        help="When an existing workdir has node_modules, skip dependency install and reuse cached Playwright browsers when present.",
    )
    return parser.parse_args()


def replay_repos(
    *,
    by_repo: Dict[str, List[Dict[str, Any]]],
    results_path: Path,
    args: argparse.Namespace,
) -> None:
    repo_items = list(by_repo.items())
    repo_total = len(repo_items)
    workers = effective_repo_workers(args.repo_workers, repo_total=repo_total)
    progress("workers_start", repo_workers=workers, repos=repo_total)
    if workers == 1:
        for repo_index, (repo_key, rows) in enumerate(repo_items, start=1):
            replay_repo_rows(
                repo_key=repo_key,
                rows=rows,
                repo_index=repo_index,
                repo_total=repo_total,
                results_path=results_path,
                args=args,
            )
        return

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                replay_repo_rows,
                repo_key=repo_key,
                rows=rows,
                repo_index=repo_index,
                repo_total=repo_total,
                results_path=results_path,
                args=args,
            ): repo_key
            for repo_index, (repo_key, rows) in enumerate(repo_items, start=1)
        }
        for future in as_completed(futures):
            repo_key = futures[future]
            future.result()
            progress("worker_repo_finished", repo_key=repo_key)


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "logs").mkdir(parents=True, exist_ok=True)
    (args.workdir_root or (args.out_dir / "workdirs")).mkdir(parents=True, exist_ok=True)
    (args.tool_cache_root or (args.out_dir / "tool_cache")).mkdir(parents=True, exist_ok=True)
    args.refresh_workdir = not args.keep_workdirs

    evidence_root = args.evidence_root or args.suite_dir.parent
    repos = split_tokens(args.repos) + split_tokens(args.repo) + read_repo_file(args.repos_file)
    if not repos:
        repos = DEFAULT_REPOS

    plan = build_replay_plan(
        suite_dir=args.suite_dir,
        evidence_root=evidence_root,
        repos=repos,
        tasks_per_repo=args.tasks_per_repo,
        max_tasks=args.max_tasks,
    )
    task_ids = split_tokens(args.task_ids) + split_tokens(args.task_id) + read_token_file(args.task_ids_file)
    if task_ids:
        before = len(plan)
        plan = filter_plan_by_task_ids(plan, task_ids)
        progress(
            "task_filter_applied",
            tasks_before=before,
            tasks_after=len(plan),
            selected_task_ids=len(set(task_ids)),
        )
    if args.previous_results:
        before = len(plan)
        rerun_statuses = split_tokens(args.rerun_statuses) or DEFAULT_RERUN_STATUSES
        plan = filter_plan_by_previous_results(
            plan,
            previous_results=args.previous_results,
            statuses=rerun_statuses,
        )
        progress(
            "previous_results_filter_applied",
            previous_results=args.previous_results,
            rerun_statuses=rerun_statuses,
            tasks_before=before,
            tasks_after=len(plan),
        )
    write_jsonl(args.out_dir / "replay_plan.jsonl", plan)
    repos_in_plan = sorted({str(row.get("repo_full_name") or "") for row in plan})
    progress(
        "plan_written",
        out_dir=args.out_dir,
        tasks=len(plan),
        repos=len(repos_in_plan),
        suite_dir=args.suite_dir,
        evidence_root=evidence_root,
    )

    results_path = args.out_dir / "replay_results.jsonl"
    if results_path.exists():
        results_path.unlink()
    results_path.touch()

    by_repo: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in plan:
        by_repo[str(row["repo_cache_key"])].append(row)

    replay_repos(by_repo=by_repo, results_path=results_path, args=args)

    summary = write_summary(args.out_dir, results_path)
    progress("summary_written", out_dir=args.out_dir, total=summary.get("total"), status_counts=summary.get("status_counts"))
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
