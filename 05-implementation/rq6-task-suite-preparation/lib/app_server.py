#!/usr/bin/env python3
"""App-server lifecycle helpers for RQ6 baseline execution."""

from __future__ import annotations

import os
import shlex
import subprocess
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse
from pathlib import Path
from typing import Any, Dict, Optional

from common import local_node_bin_dir, prepare_subprocess_command, resolve_command_executable, subprocess_env
from package_manager import load_package_json


def concrete_local_url(url: str, default_port: int = 3000) -> str:
    text = str(url or "").strip()
    if not text:
        return ""
    for token in ("${port}", "${PORT}", "$PORT", "%PORT%"):
        text = text.replace(token, str(default_port))
    return text


def is_local_http_url(url: str) -> bool:
    parsed = urlparse(str(url or "").strip())
    host = (parsed.hostname or "").lower()
    return parsed.scheme in ("http", "https") and host in ("localhost", "127.0.0.1", "::1")


def http_status_is_ready(status: Optional[int]) -> bool:
    if status is None:
        return False
    return 200 <= int(status) < 400 or int(status) in {400, 401, 402, 403, 404}


def split_command_parts(command: str) -> list[str]:
    text = str(command or "").strip()
    if not text:
        return []
    try:
        parts = shlex.split(text, posix=os.name != "nt")
    except ValueError:
        parts = text.split()
    return [str(part).strip("\"'") for part in parts]


def first_command_token(command: str) -> str:
    parts = split_command_parts(command)
    return parts[0] if parts else ""


def package_script_from_command(command: str, cwd: Path) -> str:
    parts = split_command_parts(command)
    if not parts:
        return ""

    manager = parts[0].lower()
    script_name = ""
    if manager == "npm" and len(parts) >= 3 and parts[1].lower() == "run":
        script_name = parts[2]
    elif manager == "pnpm" and len(parts) >= 2 and parts[1].lower() not in {"exec", "install", "add"}:
        script_name = parts[1]
    elif manager == "yarn" and len(parts) >= 2 and not parts[1].startswith("-") and parts[1].lower() not in {"install", "add"}:
        script_name = parts[1]
    if not script_name:
        return ""

    scripts = load_package_json(cwd).get("scripts") or {}
    script_command = str(scripts.get(script_name) or "").strip()
    if not script_command:
        return ""
    extra_args = parts[3:] if manager == "npm" else parts[2:]
    return " ".join([script_command, *extra_args]).strip()


def quote_shell_path(path: str) -> str:
    clean = str(path or "")
    if not clean:
        return clean
    if clean.startswith('"') and clean.endswith('"'):
        return clean
    return f'"{clean}"' if any(ch.isspace() for ch in clean) else clean


def resolve_shell_command(command: str, cwd: Path) -> str:
    parts = split_command_parts(command)
    if not parts:
        return command
    prepared = prepare_subprocess_command(parts, cwd=cwd)
    if not prepared or not resolve_command_executable(prepared[0], cwd=cwd):
        return command
    return " ".join([quote_shell_path(prepared[0]), *prepared[1:]])


def wait_for_http(url: str, timeout_sec: int = 120) -> Dict[str, Any]:
    deadline = time.time() + max(1, timeout_sec)
    last_error = ""
    concrete = concrete_local_url(url)
    while time.time() < deadline:
        try:
            req = urllib.request.Request(concrete, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                status = int(resp.status)
                if http_status_is_ready(status):
                    return {
                        "ok": True,
                        "http_status": status,
                        "error": "",
                        "url": concrete,
                    }
                last_error = f"HTTP {status}"
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            if http_status_is_ready(status):
                return {
                    "ok": True,
                    "http_status": status,
                    "error": "",
                    "url": concrete,
                }
            last_error = f"HTTP {status}"
        except Exception as exc:  # noqa: BLE001 - this is diagnostic polling.
            last_error = str(exc)
        time.sleep(2)
    return {
        "ok": False,
        "http_status": None,
        "error": last_error,
        "url": concrete,
    }


def wait_for_http_or_process_exit(url: str, proc: subprocess.Popen, timeout_sec: int = 120) -> Dict[str, Any]:
    deadline = time.time() + max(1, timeout_sec)
    last_error = ""
    concrete = concrete_local_url(url)
    while time.time() < deadline:
        try:
            req = urllib.request.Request(concrete, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                status = int(resp.status)
                if http_status_is_ready(status):
                    return {"ok": True, "http_status": status, "error": "", "url": concrete, "process_exited": False}
                last_error = f"HTTP {status}"
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            if http_status_is_ready(status):
                return {"ok": True, "http_status": status, "error": "", "url": concrete, "process_exited": False}
            last_error = f"HTTP {status}"
        except Exception as exc:  # noqa: BLE001 - diagnostic polling.
            last_error = str(exc)
        if proc.poll() is not None:
            return {
                "ok": False,
                "http_status": None,
                "error": last_error,
                "url": concrete,
                "process_exited": True,
                "process_returncode": proc.returncode,
            }
        time.sleep(2)
    return {"ok": False, "http_status": None, "error": last_error, "url": concrete, "process_exited": False}


def start_app_process(command: str, cwd: Path, stdout_path: Path, stderr_path: Path) -> subprocess.Popen:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_f = stdout_path.open("w", encoding="utf-8", errors="replace")
    stderr_f = stderr_path.open("w", encoding="utf-8", errors="replace")
    try:
        parts = split_command_parts(command)
        shell_meta = {"&&", "||", "|", ";", "&", ">", "<"}
        use_shell = not parts or any(part in shell_meta for part in parts)
        popen_command: Any = resolve_shell_command(command, cwd) if use_shell else prepare_subprocess_command(parts, cwd=cwd)
        proc = subprocess.Popen(
            popen_command,
            cwd=str(cwd),
            shell=use_shell,
            stdout=stdout_f,
            stderr=stderr_f,
            text=True,
            env=subprocess_env(cwd),
        )
        return proc
    except Exception:
        raise
    finally:
        stdout_f.close()
        stderr_f.close()


def terminate_process_tree(proc: Optional[subprocess.Popen]) -> None:
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


def boot_app(
    *,
    command: str,
    cwd: Path,
    base_url: str,
    log_dir: Path,
    stem: str,
    timeout_sec: int,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "app_boot_checked": True,
        "app_boot_ok": False,
        "app_boot_status": "not_started",
        "app_boot_duration_sec": 0.0,
        "app_http_status": None,
        "app_boot_url": concrete_local_url(base_url),
        "app_stdout_path": "",
        "app_stderr_path": "",
        "_process": None,
    }
    if not command:
        result["app_boot_status"] = "missing_app_start_command"
        return result
    if not is_local_http_url(concrete_local_url(base_url)):
        result["app_boot_status"] = "missing_local_base_url"
        return result
    if not cwd.is_dir():
        result["app_boot_status"] = "missing_workdir"
        return result
    effective_command = command
    executable = first_command_token(effective_command)
    prepared = prepare_subprocess_command(split_command_parts(effective_command), cwd=cwd)
    prepared_executable = prepared[0] if prepared else executable
    if prepared_executable and not resolve_command_executable(prepared_executable, cwd=cwd):
        if executable.lower() in {"pnpm", "yarn"} and resolve_command_executable("corepack", cwd=cwd):
            effective_command = f"corepack {effective_command}"
            executable = "corepack"
        fallback = package_script_from_command(effective_command, cwd) if executable != "corepack" else ""
        fallback_executable = first_command_token(fallback)
        if executable != "corepack" and fallback and (
            not fallback_executable
            or resolve_command_executable(fallback_executable, cwd=cwd)
            or local_node_bin_dir(cwd)
        ):
            effective_command = fallback
            executable = fallback_executable
    prepared = prepare_subprocess_command(split_command_parts(effective_command), cwd=cwd)
    prepared_executable = prepared[0] if prepared else executable
    if prepared_executable and not resolve_command_executable(prepared_executable, cwd=cwd):
        result["app_boot_status"] = "runtime_command_not_found"
        result["app_boot_error"] = f"Could not resolve app command executable: {prepared_executable}"
        return result
    effective_command = resolve_shell_command(effective_command, cwd)

    stdout_path = log_dir / f"{stem}.app.stdout.log"
    stderr_path = log_dir / f"{stem}.app.stderr.log"
    started = time.time()
    try:
        proc = start_app_process(effective_command, cwd, stdout_path, stderr_path)
        waited = wait_for_http_or_process_exit(base_url, proc, timeout_sec=timeout_sec)
        status = "pass" if waited["ok"] else "app_boot_timeout"
        if waited.get("process_exited"):
            status = "app_process_exited"
        result.update(
            {
                "app_boot_ok": bool(waited["ok"]),
                "app_boot_status": status,
                "app_boot_duration_sec": round(time.time() - started, 2),
                "app_http_status": waited.get("http_status"),
                "app_boot_url": waited.get("url"),
                "app_boot_error": waited.get("error", ""),
                "app_process_returncode": waited.get("process_returncode"),
                "app_stdout_path": str(stdout_path),
                "app_stderr_path": str(stderr_path),
                "_process": proc,
            }
        )
        if not waited["ok"]:
            terminate_process_tree(proc)
            result["_process"] = None
        return result
    except Exception as exc:  # noqa: BLE001 - persisted as execution diagnostics.
        result.update(
            {
                "app_boot_status": "app_boot_failed",
                "app_boot_error": str(exc),
                "app_boot_duration_sec": round(time.time() - started, 2),
                "app_stdout_path": str(stdout_path),
                "app_stderr_path": str(stderr_path),
            }
        )
        return result
