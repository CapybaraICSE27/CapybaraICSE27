#!/usr/bin/env python3
"""Package-manager detection for isolated RQ6 repo workdirs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


LOCKFILE_PRIORITY = [
    ("pnpm-lock.yaml", "pnpm"),
    ("yarn.lock", "yarn"),
    ("package-lock.json", "npm"),
    ("npm-shrinkwrap.json", "npm"),
    ("bun.lockb", "bun"),
    ("bun.lock", "bun"),
]


def load_package_json(repo_dir: Path) -> Dict[str, Any]:
    path = repo_dir / "package.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def detect_package_manager(repo_dir: Path, package_json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    package_json = package_json if package_json is not None else load_package_json(repo_dir)
    package_manager_field = str(package_json.get("packageManager") or "")

    lockfile = ""
    manager = ""
    for filename, candidate in LOCKFILE_PRIORITY:
        if (repo_dir / filename).exists():
            lockfile = filename
            manager = candidate
            break

    yarn_variant = ""
    if manager == "yarn":
        if "yarn@" in package_manager_field:
            version = package_manager_field.split("yarn@", 1)[1].split("+", 1)[0]
            major = version.split(".", 1)[0]
            yarn_variant = "berry" if major.isdigit() and int(major) >= 2 else "classic"
        elif (repo_dir / ".yarnrc.yml").exists():
            yarn_variant = "berry"
        else:
            yarn_variant = "classic"

    unsupported_reason = ""
    if manager == "bun":
        unsupported_reason = "unsupported_package_manager"
    elif not manager:
        unsupported_reason = "missing_lockfile"

    return {
        "package_manager": manager,
        "lockfile": lockfile,
        "package_manager_field": package_manager_field,
        "yarn_variant": yarn_variant,
        "unsupported_reason": unsupported_reason,
    }


def install_command(manager: str, yarn_variant: str = "") -> List[str]:
    manager = str(manager or "")
    if manager == "npm":
        return ["npm", "ci"]
    if manager == "pnpm":
        return ["pnpm", "install", "--frozen-lockfile"]
    if manager == "yarn" and yarn_variant == "berry":
        return ["yarn", "install", "--immutable"]
    if manager == "yarn":
        return ["yarn", "install", "--frozen-lockfile"]
    return []


def exec_command_prefix(manager: str) -> List[str]:
    manager = str(manager or "")
    if manager == "npm":
        return ["npx"]
    if manager == "pnpm":
        return ["pnpm", "exec"]
    if manager == "yarn":
        return ["yarn"]
    return ["npx"]


def candidate_test_scripts(scripts: Dict[str, Any]) -> Dict[str, str]:
    wanted_tokens = (
        "e2e",
        "ui",
        "playwright",
        "cypress",
        "cy:",
        "test",
    )
    out: Dict[str, str] = {}
    for name, command in scripts.items():
        lower = f"{name} {command}".lower()
        if any(tok in lower for tok in wanted_tokens):
            out[str(name)] = str(command)
    return out


def script_name_tokens(script_name: str) -> set[str]:
    text = str(script_name or "").lower()
    tokens: set[str] = set()
    for part in text.replace("-", ":").replace("_", ":").split(":"):
        tokens.update(token for token in part.split() if token)
    return tokens


def command_words(command: Any) -> set[str]:
    text = str(command or "").lower()
    normalized = "".join(ch if ch.isalnum() else " " for ch in text)
    return {part for part in normalized.split() if part}


def command_looks_like_test_runner(command: Any) -> bool:
    words = command_words(command)
    text = str(command or "").lower()
    runner_words = {
        "cypress",
        "playwright",
        "testcafe",
        "vitest",
        "jest",
        "wdio",
        "webdriverio",
        "selenium",
        "nightwatch",
    }
    composite_words = {"start-server-and-test", "wait-on"}
    return bool(words & runner_words) or any(token in text for token in composite_words)


def candidate_app_scripts(scripts: Dict[str, Any]) -> Dict[str, str]:
    wanted_name_tokens = {"app", "dev", "preview", "serve", "server", "start", "web"}
    wanted_command_tokens = (
        "astro dev",
        "http-server",
        "ng serve",
        "next dev",
        "next start",
        "nuxt dev",
        "nuxt start",
        "nx serve",
        "remix vite:dev",
        "serve ",
        "vite",
        "webpack serve",
    )
    out: Dict[str, str] = {}
    for name, command in scripts.items():
        name_tokens = script_name_tokens(str(name))
        if command_looks_like_test_runner(command):
            continue
        lower_command = str(command).lower()
        if name_tokens & wanted_name_tokens or any(token in lower_command for token in wanted_command_tokens):
            out[str(name)] = str(command)
    return out
