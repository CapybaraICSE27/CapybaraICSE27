#!/usr/bin/env python3
"""Unit tests for app-server helpers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from app_server import (  # noqa: E402
    boot_app,
    concrete_local_url,
    first_command_token,
    http_status_is_ready,
    is_local_http_url,
    package_script_from_command,
    resolve_shell_command,
    split_command_parts,
)


def write_fake_executable(path: Path) -> None:
    path.write_text("@echo off\r\n" if sys.platform.startswith("win") else "#!/bin/sh\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o755)


class TestAppServer(unittest.TestCase):
    def test_concrete_local_url_replaces_port_tokens(self) -> None:
        self.assertEqual(concrete_local_url("http://127.0.0.1:${port}", 4173), "http://127.0.0.1:4173")
        self.assertEqual(concrete_local_url("http://localhost:$PORT/app", 3001), "http://localhost:3001/app")

    def test_local_url_detection(self) -> None:
        self.assertTrue(is_local_http_url("http://localhost:3000"))
        self.assertTrue(is_local_http_url("http://127.0.0.1:3000"))
        self.assertTrue(is_local_http_url("http://[::1]:3000"))
        self.assertFalse(is_local_http_url("https://example.com"))

    def test_http_status_readiness_accepts_not_found_as_server_alive(self) -> None:
        for status in [200, 302, 400, 401, 403, 404]:
            self.assertTrue(http_status_is_ready(status))
        for status in [500, None]:
            self.assertFalse(http_status_is_ready(status))

    def test_first_command_token_handles_quoted_command(self) -> None:
        self.assertEqual(first_command_token('"C:\\Program Files\\node\\npm.cmd" run dev'), "C:\\Program Files\\node\\npm.cmd")

    def test_package_script_from_command_expands_npm_run(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "package.json").write_text('{"scripts":{"start":"vite --host 127.0.0.1"}}', encoding="utf-8")
            self.assertEqual(package_script_from_command("npm run start", root), "vite --host 127.0.0.1")

    def test_resolve_shell_command_prefers_local_cmd_shim(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bin_dir = root / "node_modules" / ".bin"
            bin_dir.mkdir(parents=True)
            shim = bin_dir / ("vite.cmd" if sys.platform.startswith("win") else "vite")
            shim.write_text("@echo off\r\n" if sys.platform.startswith("win") else "#!/bin/sh\n", encoding="utf-8")
            resolved = resolve_shell_command("vite --host 127.0.0.1", root)
            self.assertIn(shim.name, resolved)
            self.assertIn("--host 127.0.0.1", resolved)

    def test_resolve_shell_command_wraps_yarn_with_corepack(self) -> None:
        import os
        import tempfile

        before = os.environ.get("PATH", "")
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                corepack = root / ("corepack.cmd" if sys.platform.startswith("win") else "corepack")
                yarn = root / ("yarn.cmd" if sys.platform.startswith("win") else "yarn")
                write_fake_executable(corepack)
                write_fake_executable(yarn)
                from common import apply_tool_bin_dir

                apply_tool_bin_dir(root)
                resolved = resolve_shell_command("yarn dev", root)
                self.assertIn(corepack.name, resolved)
                self.assertIn("yarn dev", resolved)
        finally:
            os.environ["PATH"] = before

    def test_split_command_parts_preserves_corepack_yarn_command(self) -> None:
        self.assertEqual(split_command_parts("corepack yarn dev"), ["corepack", "yarn", "dev"])

    def test_boot_app_fails_fast_when_runtime_command_missing(self) -> None:
        result = boot_app(
            command="definitely_missing_rq6_runtime_command run dev",
            cwd=Path(__file__).resolve().parent,
            base_url="http://localhost:3000",
            log_dir=Path(__file__).resolve().parent,
            stem="missing_runtime_test",
            timeout_sec=30,
        )
        self.assertEqual(result["app_boot_status"], "runtime_command_not_found")

    def test_boot_app_stops_when_process_exits_before_http_ready(self) -> None:
        result = boot_app(
            command=f'"{sys.executable}" -c "print(123)"',
            cwd=Path(__file__).resolve().parent,
            base_url="http://localhost:65530",
            log_dir=Path(__file__).resolve().parent,
            stem="early_exit_test",
            timeout_sec=30,
        )
        self.assertEqual(result["app_boot_status"], "app_process_exited")


if __name__ == "__main__":
    unittest.main()
