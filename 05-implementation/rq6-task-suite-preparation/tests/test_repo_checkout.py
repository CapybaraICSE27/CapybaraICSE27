#!/usr/bin/env python3
"""Unit tests for RQ6 isolated workdir preparation."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


LIB = Path(__file__).resolve().parents[1] / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from repo_checkout import commit_exists, copy_source_workdir, git_status  # noqa: E402


class TestRepoCheckoutGitDiagnostics(unittest.TestCase):
    def test_git_status_records_status_timeout_without_raising(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / ".git").mkdir()

            def fake_run_command(cmd, *, cwd, timeout):
                if cmd[:2] == ["git", "rev-parse"]:
                    return subprocess.CompletedProcess(cmd, 0, "abc123\n", "")
                raise subprocess.TimeoutExpired(cmd, timeout)

            with patch("repo_checkout.run_command", side_effect=fake_run_command):
                result = git_status(repo)

            self.assertTrue(result["is_git_repo"])
            self.assertFalse(result["status_ok"])
            self.assertEqual(result["current_commit"], "abc123")
            self.assertIsNone(result["dirty"])
            self.assertIn("timed out", result["error"])

    def test_commit_exists_returns_false_on_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)

            with patch("repo_checkout.run_command", side_effect=subprocess.TimeoutExpired(["git"], 20)):
                self.assertFalse(commit_exists(repo, "abc123"))


@unittest.skipUnless(shutil.which("git"), "git is required to initialize isolated workdir metadata")
class TestRepoCheckout(unittest.TestCase):
    def test_copy_source_workdir_initializes_minimal_git_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source"
            dest = root / "dest"
            source.mkdir()
            (source / "package.json").write_text("{}", encoding="utf-8")
            (source / "node_modules").mkdir()
            (source / "node_modules" / "ignored.txt").write_text("ignored", encoding="utf-8")
            (source / ".git").mkdir()
            (source / ".git" / "source-only").write_text("ignored", encoding="utf-8")

            result = copy_source_workdir(source, dest)

            self.assertEqual(result["status"], "created_from_current_source")
            self.assertEqual(result["git_metadata_status"], "initialized")
            self.assertTrue((dest / "package.json").exists())
            self.assertTrue((dest / ".git").exists())
            self.assertFalse((dest / ".git" / "source-only").exists())
            self.assertFalse((dest / "node_modules").exists())


if __name__ == "__main__":
    unittest.main()
