#!/usr/bin/env python3
"""Static runner and app-server detection for RQ6 Phase 1."""

from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from package_manager import candidate_app_scripts, command_looks_like_test_runner, exec_command_prefix, script_name_tokens


PLAYWRIGHT_CONFIGS = [
    "playwright.config.ts",
    "playwright.config.js",
    "playwright.config.mts",
    "playwright.config.cts",
]
CYPRESS_CONFIGS = [
    "cypress.config.ts",
    "cypress.config.js",
    "cypress.config.mts",
    "cypress.config.cts",
]
LOCAL_URL_RE = re.compile(r"https?://(?:localhost|127\.0\.0\.1|\[::1\])(?::\d+)?[^\s'\"`)]*")
BASE_URL_RE = re.compile(r"baseUrl\s*:\s*['\"]([^'\"]+)['\"]", re.I)
WEBSERVER_COMMAND_RE = re.compile(r"command\s*:\s*['\"]([^'\"]+)['\"]", re.I)
WEBSERVER_URL_RE = re.compile(r"url\s*:\s*['\"]([^'\"]+)['\"]", re.I)


def first_existing(repo_dir: Path, names: List[str]) -> str:
    for name in names:
        if (repo_dir / name).exists():
            return name
    return ""


def read_small_text(path: Path, limit: int = 500_000) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def detect_runner(
    repo_dir: Path,
    *,
    framework: str,
    package_manager: str,
    package_json: Dict[str, Any],
) -> Dict[str, Any]:
    deps = {
        **(package_json.get("dependencies") or {}),
        **(package_json.get("devDependencies") or {}),
    }
    scripts = package_json.get("scripts") or {}
    script_blob = "\n".join(f"{k}: {v}" for k, v in scripts.items()).lower()
    prefix = exec_command_prefix(package_manager)

    framework = framework.lower()
    if framework == "playwright":
        config = first_existing(repo_dir, PLAYWRIGHT_CONFIGS)
        has_dep = "@playwright/test" in deps or "playwright" in deps
        has_script = "playwright test" in script_blob
        identified = bool(config or has_dep or has_script)
        return {
            "framework": "playwright",
            "runner_identified": identified,
            "runner_command_base": " ".join(prefix + ["playwright", "test"]) if identified else "",
            "list_command": " ".join(prefix + ["playwright", "test", "--list"]) if identified else "",
            "supports_test_title_filter": True,
            "supports_file_filter": True,
            "runner_config": config,
            "runner_detection_reason": "config_or_dep_or_script" if identified else "runner_not_identified",
        }

    if framework == "cypress":
        config = first_existing(repo_dir, CYPRESS_CONFIGS)
        has_dep = "cypress" in deps
        has_script = "cypress run" in script_blob or "cypress open" in script_blob
        identified = bool(config or has_dep or has_script)
        return {
            "framework": "cypress",
            "runner_identified": identified,
            "runner_command_base": " ".join(prefix + ["cypress", "run"]) if identified else "",
            "list_command": "",
            "supports_test_title_filter": False,
            "supports_file_filter": True,
            "runner_config": config,
            "runner_detection_reason": "config_or_dep_or_script" if identified else "runner_not_identified",
        }

    return {
        "framework": framework,
        "runner_identified": False,
        "runner_detection_reason": "unsupported_framework",
    }


def script_run_command(package_manager: str, script_name: str) -> str:
    if package_manager == "npm":
        return f"npm run {script_name}"
    if package_manager == "pnpm":
        return f"pnpm {script_name}"
    if package_manager == "yarn":
        return f"yarn {script_name}"
    return script_name


def app_script_rank(script_name: str, command: str) -> tuple[int, int, str]:
    tokens = script_name_tokens(script_name)
    lower_name = str(script_name or "").lower()
    lower_command = str(command or "").lower()
    starts_app = bool(tokens & {"dev", "preview", "serve", "server", "start", "web", "app"})
    ci_or_test = bool(tokens & {"ci", "e2e", "test", "local"})
    test_runner_penalty = 100 if command_looks_like_test_runner(command) else 0

    if starts_app and ci_or_test:
        tier = 0
    elif tokens & {"preview", "serve", "server"}:
        tier = 1
    elif lower_name == "start":
        tier = 2
    elif lower_name == "dev":
        tier = 3
    elif starts_app:
        tier = 4
    else:
        tier = 5

    has_port_or_url = bool(LOCAL_URL_RE.search(lower_command) or port_from_command(lower_command))
    port_bonus = 0 if has_port_or_url else 1
    return (tier + test_runner_penalty, port_bonus, lower_name)


def select_app_script(app_scripts: Dict[str, str]) -> tuple[str, str, str]:
    if not app_scripts:
        return "", "", ""
    ranked = sorted(
        ((app_script_rank(name, command), name, command) for name, command in app_scripts.items()),
        key=lambda item: item[0],
    )
    _, name, command = ranked[0]
    return str(name), str(command), "ranked_package_script"


def command_tokens(command: str) -> List[str]:
    try:
        return [str(part) for part in shlex.split(str(command or ""), posix=False)]
    except ValueError:
        return str(command or "").split()


def port_from_command(command: str) -> str:
    tokens = command_tokens(command)
    for index, token in enumerate(tokens):
        clean = token.strip("\"'")
        lower = clean.lower()
        if lower in {"--port", "-p"} and index + 1 < len(tokens):
            value = tokens[index + 1].strip("\"'")
            if value.isdigit():
                return value
        for prefix in ("--port=", "-p=", "port="):
            if lower.startswith(prefix):
                value = clean.split("=", 1)[1]
                if value.isdigit():
                    return value
    lower_blob = " ".join(token.strip("\"'").lower() for token in tokens)
    if "next" in lower_blob and (" dev" in f" {lower_blob}" or " start" in f" {lower_blob}"):
        return "3000"
    if "vite" in lower_blob:
        return "4173" if "preview" in lower_blob else "5173"
    if "nx serve" in lower_blob or "ng serve" in lower_blob:
        return "4200"
    if "webpack" in lower_blob:
        return "8080"
    if "http-server" in lower_blob:
        return "8080"
    return ""


def infer_local_base_url(command: str) -> str:
    port = port_from_command(command)
    return f"http://localhost:{port}" if port else ""


def is_local_base_url(url: str) -> bool:
    parsed = urlparse(str(url or "").strip())
    host = (parsed.hostname or "").lower()
    return parsed.scheme in ("http", "https") and host in ("localhost", "127.0.0.1", "::1")


def detect_app(
    repo_dir: Path,
    *,
    framework: str,
    runner_config: str,
    package_json: Dict[str, Any],
    package_manager: str,
) -> Dict[str, Any]:
    scripts = package_json.get("scripts") or {}
    app_scripts = candidate_app_scripts(scripts)
    selected_script_name = ""
    selected_script_command = ""
    selected_script_reason = ""
    config_text = read_small_text(repo_dir / runner_config) if runner_config else ""

    webserver_command = ""
    webserver_url = ""
    base_url = ""
    detected_from = ""
    app_detection_basis = "none"
    base_url_detection_basis = "none"
    runner_managed_app_possible = bool(framework == "playwright" and runner_config)

    if framework == "playwright" and config_text:
        cmd_match = WEBSERVER_COMMAND_RE.search(config_text)
        url_match = WEBSERVER_URL_RE.search(config_text)
        if cmd_match:
            webserver_command = cmd_match.group(1)
            detected_from = "playwright_config_webServer"
            app_detection_basis = "config_text_heuristic"
        if url_match:
            webserver_url = url_match.group(1)
            base_url = webserver_url
            base_url_detection_basis = "config_text_heuristic"
    elif framework == "cypress" and config_text:
        base_match = BASE_URL_RE.search(config_text)
        if base_match:
            base_url = base_match.group(1)
            detected_from = "cypress_config_baseUrl"
            base_url_detection_basis = "config_text_heuristic"

    if not base_url:
        for command in list(app_scripts.values()) + [config_text]:
            match = LOCAL_URL_RE.search(str(command))
            if match:
                base_url = match.group(0)
                detected_from = detected_from or "local_url_literal"
                base_url_detection_basis = "script_or_config_text_heuristic"
                break

    app_start_command = webserver_command
    if not app_start_command and app_scripts:
        selected_script_name, selected_script_command, selected_script_reason = select_app_script(app_scripts)
        app_start_command = script_run_command(package_manager, selected_script_name)
        detected_from = detected_from or "package_script"
        app_detection_basis = "package_json_script"
    if not base_url and app_start_command:
        script_command = selected_script_command
        inferred = infer_local_base_url(script_command or app_start_command)
        if inferred:
            base_url = inferred
            detected_from = detected_from or "app_script_port_inference"
            base_url_detection_basis = "package_script_port_inference"

    local_base_url = is_local_base_url(base_url)
    production_url_only = bool(base_url.startswith("http") and not local_base_url)

    return {
        "app_start_command": app_start_command,
        "base_url": base_url,
        "webserver_url": webserver_url,
        "app_detected_from": detected_from,
        "app_detection_basis": app_detection_basis,
        "base_url_detection_basis": base_url_detection_basis,
        "runner_managed_app_possible": runner_managed_app_possible,
        "app_script_name": selected_script_name,
        "app_script_command": selected_script_command,
        "app_script_selection_reason": selected_script_reason,
        "app_scripts": app_scripts,
        "local_base_url": local_base_url,
        "production_base_url_only": production_url_only,
        "app_boot_ok": None,
    }
