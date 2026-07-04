#!/usr/bin/env python3
"""Unit tests for RQ6 common helpers."""

from __future__ import annotations

import unittest
from pathlib import Path
import sys
import tempfile

LIB = Path(__file__).resolve().parents[1] / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from common import (  # noqa: E402
    apply_tool_bin_dir,
    configure_js_tool_env,
    file_tree_hash,
    is_skipped_test,
    normalize_framework,
    prepare_subprocess_command,
    resolve_command_executable,
    resolve_local_tool_executable,
    run_process_capture,
    repo_cache_key,
    row_matches_repo_filter,
    subprocess_env,
)


def write_fake_executable(path: Path) -> None:
    path.write_text("@echo off\r\n" if sys.platform.startswith("win") else "#!/bin/sh\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o755)


class TestCommon(unittest.TestCase):
    def test_repo_cache_key(self) -> None:
        self.assertEqual(repo_cache_key("owner/repo"), "owner__repo")

    def test_normalize_framework(self) -> None:
        self.assertEqual(normalize_framework("Playwright, Cypress"), "playwright")
        self.assertEqual(normalize_framework("@wdio/test-runner"), "webdriverio")

    def test_skip_detection_ignores_title_text(self) -> None:
        self.assertFalse(is_skipped_test({"test_name": "skip onboarding when optional"}))
        self.assertTrue(is_skipped_test({"test_status": "skipped"}))
        self.assertTrue(is_skipped_test({"test_declaration_type": "test.skip"}))

    def test_repo_filter_matches_full_name_or_cache_key(self) -> None:
        row = {"repo_full_name": "owner/repo", "repo_cache_key": "owner__repo"}
        self.assertTrue(row_matches_repo_filter(row, {"owner/repo"}))
        self.assertTrue(row_matches_repo_filter(row, {"owner__repo"}))
        self.assertFalse(row_matches_repo_filter(row, {"other/repo"}))

    def test_file_tree_hash_ignores_node_modules(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "src").mkdir()
            (root / "src" / "a.ts").write_text("const a = 1;\n", encoding="utf-8")
            before = file_tree_hash(root)
            (root / "node_modules").mkdir()
            (root / "node_modules" / "ignored.js").write_text("x", encoding="utf-8")
            after = file_tree_hash(root)
            self.assertEqual(before, after)

    def test_prepare_subprocess_command_keeps_arguments(self) -> None:
        command = prepare_subprocess_command([sys.executable, "-c", "print('ok')"])
        self.assertTrue(command[0])
        self.assertEqual(command[1:], ["-c", "print('ok')"])

    def test_prepare_subprocess_command_rewrites_missing_npx_to_local_bin(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bin_dir = root / "node_modules" / ".bin"
            bin_dir.mkdir(parents=True)
            shim = bin_dir / ("playwright.cmd" if sys.platform.startswith("win") else "playwright")
            shim.write_text("@echo off\r\n" if sys.platform.startswith("win") else "#!/bin/sh\n", encoding="utf-8")
            command = prepare_subprocess_command(["npx", "playwright", "test"], cwd=root)
            self.assertEqual(Path(command[0]).name.lower(), shim.name.lower())
            self.assertEqual(command[1:], ["test"])

    def test_prepare_subprocess_command_wraps_with_container(self) -> None:
        import os

        names = ["RQ6_CONTAINER_RUNTIME", "RQ6_CONTAINER_IMAGE", "RQ6_CONTAINER_BIND"]
        before = {name: os.environ.get(name) for name in names}
        before_path = os.environ.get("PATH", "")
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                host_bin = root / "host_bin"
                host_bin.mkdir()
                host_node = host_bin / ("node.cmd" if sys.platform.startswith("win") else "node")
                host_node.write_text("@echo off\r\n" if sys.platform.startswith("win") else "#!/bin/sh\n", encoding="utf-8")
                apply_tool_bin_dir(host_bin)
                image = root / "playwright.sif"
                bind = root / "data"
                image.write_text("sif", encoding="utf-8")
                bind.mkdir()
                os.environ["RQ6_CONTAINER_RUNTIME"] = sys.executable
                os.environ["RQ6_CONTAINER_IMAGE"] = str(image)
                os.environ["RQ6_CONTAINER_BIND"] = str(bind)

                command = prepare_subprocess_command(["node", "--version"], cwd=root)

                self.assertEqual(command[:2], [sys.executable, "exec"])
                self.assertIn("--pwd", command)
                self.assertEqual(command[command.index("--pwd") + 1], str(root))
                self.assertIn("--bind", command)
                self.assertEqual(command[command.index("--bind") + 1], str(bind))
                self.assertEqual(command[-2:], ["node", "--version"])
                self.assertIn(str(image), command)
        finally:
            for name, value in before.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
            os.environ["PATH"] = before_path

    def test_prepare_subprocess_command_does_not_double_wrap_container(self) -> None:
        import os

        names = ["RQ6_CONTAINER_RUNTIME", "RQ6_CONTAINER_IMAGE", "RQ6_CONTAINER_BIND"]
        before = {name: os.environ.get(name) for name in names}
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                image = root / "playwright.sif"
                image.write_text("sif", encoding="utf-8")
                os.environ["RQ6_CONTAINER_RUNTIME"] = sys.executable
                os.environ["RQ6_CONTAINER_IMAGE"] = str(image)
                wrapped = [sys.executable, "exec", "--pwd", str(root), str(image), "node", "--version"]

                command = prepare_subprocess_command(wrapped, cwd=root)

                self.assertEqual(command, wrapped)
        finally:
            for name, value in before.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def test_prepare_subprocess_command_passes_tool_path_into_container(self) -> None:
        import os

        names = ["RQ6_CONTAINER_RUNTIME", "RQ6_CONTAINER_IMAGE", "RQ6_CONTAINER_BIND", "RQ6_TOOL_BIN_DIR"]
        before = {name: os.environ.get(name) for name in names}
        before_path = os.environ.get("PATH", "")
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                tool_bin = root / "tools" / "bin"
                tool_bin.mkdir(parents=True)
                image = root / "playwright.sif"
                image.write_text("sif", encoding="utf-8")
                os.environ["RQ6_CONTAINER_RUNTIME"] = sys.executable
                os.environ["RQ6_CONTAINER_IMAGE"] = str(image)
                configure_js_tool_env(tool_bin_dir=tool_bin)

                command = prepare_subprocess_command(["pnpm", "--version"], cwd=root)

                image_index = command.index(str(image))
                self.assertEqual(command[image_index + 1], "env")
                self.assertTrue(command[image_index + 2].startswith("PATH="))
                self.assertIn(str(tool_bin.absolute()), command[image_index + 2])
                self.assertEqual(command[-3:], ["corepack", "pnpm", "--version"])
        finally:
            os.environ["PATH"] = before_path
            for name, value in before.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def test_prepare_subprocess_command_keeps_git_on_host_when_container_enabled(self) -> None:
        import os

        names = ["RQ6_CONTAINER_RUNTIME", "RQ6_CONTAINER_IMAGE", "RQ6_CONTAINER_BIND"]
        before = {name: os.environ.get(name) for name in names}
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                image = root / "playwright.sif"
                image.write_text("sif", encoding="utf-8")
                os.environ["RQ6_CONTAINER_RUNTIME"] = sys.executable
                os.environ["RQ6_CONTAINER_IMAGE"] = str(image)

                command = prepare_subprocess_command(["git", "status", "--porcelain"], cwd=root)

                self.assertNotEqual(command[:2], [sys.executable, "exec"])
                self.assertEqual(command[-2:], ["status", "--porcelain"])
        finally:
            for name, value in before.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def test_run_process_capture_decodes_timeout_bytes(self) -> None:
        import subprocess
        from unittest.mock import patch

        class FakeProcess:
            def __init__(self) -> None:
                self.returncode = None
                self.calls = 0
                self.terminated = False

            def communicate(self, timeout=None):
                self.calls += 1
                if self.calls == 1:
                    exc = subprocess.TimeoutExpired(["fake"], timeout)
                    exc.stdout = b"before "
                    exc.stderr = b"err "
                    raise exc
                self.returncode = -15
                return "after", "more"

            def poll(self):
                return None if not self.terminated else self.returncode

            def terminate(self) -> None:
                self.terminated = True

            def wait(self, timeout=None):
                self.returncode = -15
                return self.returncode

            def kill(self) -> None:
                self.returncode = -9

        with (
            patch("subprocess.Popen", return_value=FakeProcess()),
            patch("common.terminate_process_tree", side_effect=lambda proc: proc.terminate()),
        ):
            result = run_process_capture([sys.executable, "--fake"], timeout=1)

        self.assertTrue(result["timed_out"])
        self.assertEqual(result["stdout"], "before after")
        self.assertEqual(result["stderr"], "err more")

    def test_prepare_subprocess_command_preserves_container_cwd_symlink_path(self) -> None:
        import os

        names = ["RQ6_CONTAINER_RUNTIME", "RQ6_CONTAINER_IMAGE", "RQ6_CONTAINER_BIND"]
        before = {name: os.environ.get(name) for name in names}
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                real_repo = root / "real_repo"
                real_repo.mkdir()
                linked_repo = root / "linked_repo"
                try:
                    os.symlink(real_repo, linked_repo, target_is_directory=True)
                except OSError as exc:
                    self.skipTest(f"symlink unavailable: {exc}")
                image = root / "playwright.sif"
                image.write_text("sif", encoding="utf-8")
                os.environ["RQ6_CONTAINER_RUNTIME"] = sys.executable
                os.environ["RQ6_CONTAINER_IMAGE"] = str(image)

                command = prepare_subprocess_command(["node", "--version"], cwd=linked_repo)

                self.assertIn("--pwd", command)
                self.assertEqual(command[command.index("--pwd") + 1], str(linked_repo.absolute()))
        finally:
            for name, value in before.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def test_resolve_local_tool_executable_preserves_symlink_path(self) -> None:
        import os

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            real_repo = root / "real_repo"
            local_bin = real_repo / "node_modules" / ".bin"
            local_bin.mkdir(parents=True)
            tool = local_bin / ("playwright.cmd" if sys.platform.startswith("win") else "playwright")
            tool.write_text("@echo off\r\n" if sys.platform.startswith("win") else "#!/bin/sh\n", encoding="utf-8")
            linked_repo = root / "linked_repo"
            try:
                os.symlink(real_repo, linked_repo, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink unavailable: {exc}")

            resolved = resolve_local_tool_executable("playwright", linked_repo)

            self.assertEqual(
                resolved,
                str(linked_repo / "node_modules" / ".bin" / tool.name),
            )

    def test_prepare_subprocess_command_uses_corepack_for_missing_pnpm(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bin_dir = root / "node_modules" / ".bin"
            bin_dir.mkdir(parents=True)
            shim = bin_dir / ("corepack.cmd" if sys.platform.startswith("win") else "corepack")
            write_fake_executable(shim)
            command = prepare_subprocess_command(["pnpm", "install"], cwd=root)
            self.assertEqual(Path(command[0]).name.lower(), shim.name.lower())
            self.assertEqual(command[1:], ["pnpm", "install"])

    def test_prepare_subprocess_command_prefers_corepack_over_global_yarn(self) -> None:
        import os

        before = os.environ.get("PATH", "")
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                corepack = root / ("corepack.cmd" if sys.platform.startswith("win") else "corepack")
                yarn = root / ("yarn.cmd" if sys.platform.startswith("win") else "yarn")
                write_fake_executable(corepack)
                write_fake_executable(yarn)
                apply_tool_bin_dir(root)
                command = prepare_subprocess_command(["yarn", "install", "--frozen-lockfile"], cwd=root)
                self.assertEqual(Path(command[0]).name.lower(), corepack.name.lower())
                self.assertEqual(command[1:], ["yarn", "install", "--frozen-lockfile"])
        finally:
            os.environ["PATH"] = before

    def test_wrapper_rewrite_uses_only_repo_local_tool(self) -> None:
        import os

        before = os.environ.get("PATH", "")
        try:
            with tempfile.TemporaryDirectory() as global_td, tempfile.TemporaryDirectory() as repo_td:
                global_root = Path(global_td)
                repo_root = Path(repo_td)
                global_cypress = global_root / ("cypress.cmd" if sys.platform.startswith("win") else "cypress")
                write_fake_executable(global_cypress)
                corepack = global_root / ("corepack.cmd" if sys.platform.startswith("win") else "corepack")
                write_fake_executable(corepack)
                apply_tool_bin_dir(global_root)
                self.assertIsNone(resolve_local_tool_executable("cypress", repo_root))
                command = prepare_subprocess_command(["pnpm", "exec", "cypress", "run"], cwd=repo_root)
                self.assertEqual(Path(command[0]).name.lower(), corepack.name.lower())
                self.assertEqual(command[1:], ["pnpm", "exec", "cypress", "run"])
        finally:
            os.environ["PATH"] = before

    def test_apply_tool_bin_dir_prepends_path(self) -> None:
        import os

        before = os.environ.get("PATH", "")
        try:
            with tempfile.TemporaryDirectory() as td:
                applied = apply_tool_bin_dir(td)
                self.assertEqual(Path(applied), Path(td))
                self.assertEqual(os.environ.get("PATH", "").split(os.pathsep)[0], td)
        finally:
            os.environ["PATH"] = before

    def test_apply_tool_bin_dir_preserves_symlink_path(self) -> None:
        import os

        before = os.environ.get("PATH", "")
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                target = root / "target_bin"
                target.mkdir()
                link = root / "linked_bin"
                try:
                    os.symlink(target, link, target_is_directory=True)
                except OSError as exc:
                    self.skipTest(f"symlink unavailable: {exc}")

                applied = apply_tool_bin_dir(link)

                self.assertEqual(applied, str(link.absolute()))
                self.assertEqual(os.environ.get("PATH", "").split(os.pathsep)[0], str(link.absolute()))
        finally:
            os.environ["PATH"] = before

    def test_configure_js_tool_env_sets_local_caches(self) -> None:
        import os

        names = ["NPM_CONFIG_CACHE", "COREPACK_HOME", "CYPRESS_CACHE_FOLDER", "HUSKY", "HUSKY_SKIP_INSTALL"]
        before = {name: os.environ.get(name) for name in names}
        try:
            with tempfile.TemporaryDirectory() as td:
                env = configure_js_tool_env(cache_root=Path(td) / "cache")
                for name in ["NPM_CONFIG_CACHE", "COREPACK_HOME", "CYPRESS_CACHE_FOLDER"]:
                    self.assertIn(name, env)
                    self.assertTrue(Path(env[name]).is_dir())
                    self.assertTrue(str(env[name]).startswith(str(Path(td))))
                self.assertEqual(env["HUSKY"], "0")
                self.assertEqual(env["HUSKY_SKIP_INSTALL"], "1")
        finally:
            for name, value in before.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def test_subprocess_env_disables_husky_hooks(self) -> None:
        env = subprocess_env()
        self.assertEqual(env["HUSKY"], "0")
        self.assertEqual(env["HUSKY_SKIP_INSTALL"], "1")
        self.assertEqual(env["COREPACK_ENABLE_DOWNLOAD_PROMPT"], "0")

    @unittest.skipUnless(sys.platform.startswith("win"), "Windows shim preference")
    def test_resolve_command_prefers_cmd_wrapper_on_windows(self) -> None:
        import os

        before = os.environ.get("PATH", "")
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                (root / "tool").write_text("unix shim", encoding="utf-8")
                (root / "tool.cmd").write_text("@echo off\r\n", encoding="utf-8")
                apply_tool_bin_dir(root)
                resolved = resolve_command_executable("tool")
                self.assertTrue(str(resolved).lower().endswith("tool.cmd"))
        finally:
            os.environ["PATH"] = before


if __name__ == "__main__":
    unittest.main()
