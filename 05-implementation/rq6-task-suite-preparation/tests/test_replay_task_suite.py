#!/usr/bin/env python3
"""Unit tests for the RQ6 transferred task-suite replay runner."""

from __future__ import annotations

import importlib.util
import json
import argparse
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "10_replay_task_suite_human_smoke.py"
)


def load_runner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("rq6_replay_task_suite", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


class TestReplayTaskSuite(unittest.TestCase):
    def test_select_manifest_rows_caps_per_repo_in_manifest_order(self) -> None:
        runner = load_runner()
        rows = [
            {"task_id": "a1", "repo_full_name": "owner/a"},
            {"task_id": "a2", "repo_full_name": "owner/a"},
            {"task_id": "a3", "repo_full_name": "owner/a"},
            {"task_id": "b1", "repo_full_name": "owner/b"},
            {"task_id": "b2", "repo_full_name": "owner/b"},
        ]

        selected = runner.select_manifest_rows(rows, repos=["owner/a", "owner/b"], tasks_per_repo=2)

        self.assertEqual([row["task_id"] for row in selected], ["a1", "a2", "b1", "b2"])

    def test_build_replay_plan_matches_passing_baseline_and_normalizes_python_server(self) -> None:
        runner = load_runner()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            suite = root / "rq6_phase2_task_suite_v2"
            write_jsonl(
                suite / "rq6_tasks_manifest.jsonl",
                [
                    {
                        "task_id": "task_swup_001",
                        "repo_full_name": "swup/swup",
                        "repo_cache_key": "swup__swup",
                        "source_test_id": "test-1",
                        "source_file": "tests/a.spec.ts",
                        "test_name": "loads page",
                    }
                ],
            )
            write_jsonl(
                suite / "agent_task_specs.jsonl",
                [
                    {
                        "task_id": "task_swup_001",
                        "base_url": "http://127.0.0.1:3000",
                        "app_start_command": "python -m http.server 3000",
                        "pretest_setup_commands": [{"setup_id": "prep", "command": "npm run build"}],
                    }
                ],
            )
            write_jsonl(
                root / "phase1_execution_pilot_v4_swup_expanded" / "human_test_baseline_runs.jsonl",
                [
                    {"test_id": "test-1", "status": "failed", "command": "npx playwright test wrong"},
                    {
                        "test_id": "test-1",
                        "status": "pass",
                        "command": "npx playwright test tests/a.spec.ts -g loads",
                        "app_start_command": "python -m http.server 3000",
                        "app_boot_url": "http://127.0.0.1:3000",
                    },
                ],
            )

            plan = runner.build_replay_plan(
                suite_dir=suite,
                evidence_root=root,
                repos=["swup/swup"],
                tasks_per_repo=0,
                max_tasks=0,
            )

        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["human_command"], "npx playwright test tests/a.spec.ts -g loads")
        self.assertEqual(plan[0]["app_start_command"], "/usr/bin/python3 -m http.server 3000")
        self.assertEqual(plan[0]["pretest_setup_commands"][0]["setup_id"], "prep")

    def test_build_replay_plan_adds_swup_dist_build_setup_when_missing(self) -> None:
        runner = load_runner()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            suite = root / "rq6_phase2_task_suite_v2"
            write_jsonl(
                suite / "rq6_tasks_manifest.jsonl",
                [
                    {
                        "task_id": "task_swup_001",
                        "repo_full_name": "swup/swup",
                        "repo_cache_key": "swup__swup",
                        "source_test_id": "test-1",
                        "source_file": "tests/functional/events.spec.ts",
                        "test_name": "loads page",
                    }
                ],
            )
            write_jsonl(suite / "agent_task_specs.jsonl", [{"task_id": "task_swup_001"}])
            write_jsonl(
                root / "phase1_execution_pilot_v4_swup_expanded" / "human_test_baseline_runs.jsonl",
                [{"test_id": "test-1", "status": "pass", "command": "npx playwright test"}],
            )

            plan = runner.build_replay_plan(
                suite_dir=suite,
                evidence_root=root,
                repos=["swup/swup"],
                tasks_per_repo=0,
                max_tasks=0,
            )

        setup_ids = [setup["setup_id"] for setup in plan[0]["pretest_setup_commands"]]
        self.assertIn("build_swup_dist", setup_ids)

    def test_build_replay_plan_allows_manifest_command_without_baseline_evidence(self) -> None:
        runner = load_runner()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            suite = root / "rq6_phase2_task_suite_v2"
            write_jsonl(
                suite / "rq6_tasks_manifest.jsonl",
                [
                    {
                        "task_id": "task_gridstack_001",
                        "repo_full_name": "gridstack/gridstack.js",
                        "repo_cache_key": "gridstack__gridstack.js",
                        "source_test_id": "grid-test-1",
                        "source_file": "e2e/gridstack-e2e.spec.ts",
                        "test_name": "should handle responsive behavior",
                        "human_command": "yarn playwright test e2e/gridstack-e2e.spec.ts -g responsive --project chromium --reporter=json",
                    }
                ],
            )
            write_jsonl(
                suite / "agent_task_specs.jsonl",
                [
                    {
                        "task_id": "task_gridstack_001",
                        "base_url": "http://localhost:8080",
                        "pretest_setup_commands": [{"setup_id": "grunt_css_copy", "command": "node node_modules/grunt/bin/grunt"}],
                    }
                ],
            )

            plan = runner.build_replay_plan(
                suite_dir=suite,
                evidence_root=root,
                repos=["gridstack/gridstack.js"],
                tasks_per_repo=0,
                max_tasks=0,
            )

        self.assertEqual(plan[0]["human_command"], "yarn playwright test e2e/gridstack-e2e.spec.ts -g responsive --project chromium --reporter=json")
        self.assertEqual(plan[0]["app_boot_url"], "http://localhost:8080")
        self.assertEqual(plan[0]["pretest_setup_commands"][0]["setup_id"], "grunt_css_copy")

    def test_ignore_generated_keeps_source_directories_named_build_or_dist(self) -> None:
        runner = load_runner()

        self.assertIn("build", runner.ignore_generated("/tmp/repo", ["build", "dist", "node_modules"]))
        self.assertNotIn(
            "build",
            runner.ignore_generated("/tmp/repo/packages/zudoku/src/cli", ["build", "node_modules"]),
        )
        self.assertNotIn(
            "dist",
            runner.ignore_generated("/tmp/repo/packages/app/src", ["dist", "node_modules"]),
        )
        self.assertIn(
            "node_modules",
            runner.ignore_generated("/tmp/repo/packages/app/src", ["dist", "node_modules"]),
        )

    def test_pnpm_install_uses_corepack_and_disables_engine_strict(self) -> None:
        runner = load_runner()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "package.json").write_text(
                json.dumps({"packageManager": "pnpm@9.15.0+sha1.deadbeef"}),
                encoding="utf-8",
            )
            (root / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")

            command = runner.install_command(root)

        self.assertIn("corepack prepare pnpm@9.15.0 --activate", command)
        self.assertNotIn("corepack enable", command)
        self.assertIn("pnpm install --frozen-lockfile --config.engine-strict=false", command)
        self.assertNotIn("+sha1", command)

    def test_yarn_install_avoids_corepack_enable_for_read_only_containers(self) -> None:
        runner = load_runner()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "package.json").write_text(
                json.dumps({"packageManager": "yarn@1.22.22+sha512.deadbeef"}),
                encoding="utf-8",
            )
            (root / "yarn.lock").write_text("# yarn lockfile\n", encoding="utf-8")

            command = runner.install_command(root)

        self.assertIn("corepack prepare yarn@1.22.22 --activate", command)
        self.assertNotIn("corepack enable", command)
        self.assertIn("yarn install --frozen-lockfile", command)
        self.assertNotIn("+sha512", command)

    def test_shell_script_uses_direct_node22_corepack_wrapper(self) -> None:
        runner = load_runner()
        script = runner.shell_script(
            "pnpm install",
            Path("/tmp/repo"),
            out_dir=Path("/tmp/out"),
            node_tool_bin_dir=Path("/tools/node/bin"),
            node22_dir=Path("/tools/node-v22.12.0-linux-x64"),
        )

        self.assertIn("export COREPACK_INTEGRITY_KEYS=0", script)
        self.assertIn('cat > "$PNPM_HOME/pnpm"', script)
        self.assertIn('exec "$RQ6_NODE22_BIN" "$RQ6_COREPACK_JS" pnpm "$@"', script)
        self.assertIn('cat > "$PNPM_HOME/yarn"', script)
        self.assertIn('chmod +x "$PNPM_HOME/corepack" "$PNPM_HOME/pnpm" "$PNPM_HOME/pnpx" "$PNPM_HOME/yarn"', script)
        self.assertIn('corepack() { "$RQ6_NODE22_BIN" "$RQ6_COREPACK_JS" "$@"; }', script)
        self.assertIn('pnpm() { "$RQ6_NODE22_BIN" "$RQ6_COREPACK_JS" pnpm "$@"; }', script)
        self.assertIn('yarn() { "$RQ6_NODE22_BIN" "$RQ6_COREPACK_JS" yarn "$@"; }', script)
        self.assertIn("export PATH=/tools/node/bin:$PATH", script)
        self.assertIn("export PATH=/tools/node-v22.12.0-linux-x64/bin:$PATH", script)

    def test_shell_script_can_use_repo_scoped_cache_root(self) -> None:
        runner = load_runner()
        script = runner.shell_script(
            "npm ci",
            Path("/tmp/repo"),
            out_dir=Path("/tmp/out"),
            cache_root=Path("/tmp/out/tool_cache/swup__swup"),
        )

        self.assertIn("export COREPACK_HOME=/tmp/out/tool_cache/swup__swup/corepack", script)
        self.assertIn("export PNPM_HOME=/tmp/out/tool_cache/swup__swup/pnpm-home", script)

    def test_auto_app_start_skips_repos_with_playwright_webserver(self) -> None:
        runner = load_runner()

        self.assertFalse(runner.should_start_app("motiondivision__motion-vue", "npm run dev", "auto"))
        self.assertFalse(runner.should_start_app("gridstack__gridstack.js", "python -m http.server 8080", "auto"))
        self.assertTrue(runner.should_start_app("other__repo", "npm run dev", "auto"))
        self.assertTrue(runner.should_start_app("motiondivision__motion-vue", "npm run dev", "force"))

    def test_env_int_falls_back_for_blank_or_malformed_values(self) -> None:
        runner = load_runner()

        self.assertEqual(runner.env_int("", 0), 0)
        self.assertEqual(runner.env_int("not an integer", 7), 7)
        self.assertEqual(runner.env_int("12", 0), 12)

    def test_effective_repo_workers_clamps_to_available_repos(self) -> None:
        runner = load_runner()

        self.assertEqual(runner.effective_repo_workers(0, repo_total=4), 1)
        self.assertEqual(runner.effective_repo_workers(2, repo_total=4), 2)
        self.assertEqual(runner.effective_repo_workers(8, repo_total=4), 4)
        self.assertEqual(runner.effective_repo_workers(4, repo_total=0), 1)

    def test_timeout_value_allows_zero_to_disable_timeout(self) -> None:
        runner = load_runner()

        self.assertIsNone(runner.timeout_value(0))
        self.assertIsNone(runner.timeout_value(-1))
        self.assertEqual(runner.timeout_value(30), 30)

    def test_env_bool_parses_common_truthy_values(self) -> None:
        runner = load_runner()

        self.assertTrue(runner.env_bool("1", False))
        self.assertTrue(runner.env_bool("true", False))
        self.assertTrue(runner.env_bool("yes", False))
        self.assertFalse(runner.env_bool("0", True))
        self.assertFalse(runner.env_bool("false", True))
        self.assertTrue(runner.env_bool("", True))

    def test_repo_workdir_and_tool_cache_use_persistent_roots_when_configured(self) -> None:
        runner = load_runner()
        args = argparse.Namespace(
            out_dir=Path("/tmp/out"),
            workdir_root=Path("/tmp/reusable_workdirs"),
            tool_cache_root=Path("/tmp/reusable_tool_cache"),
        )

        self.assertEqual(
            runner.repo_workdir(args, "openplayerjs__openplayerjs"),
            Path("/tmp/reusable_workdirs/openplayerjs__openplayerjs"),
        )
        self.assertEqual(
            runner.repo_tool_cache_root(args, "openplayerjs__openplayerjs"),
            Path("/tmp/reusable_tool_cache/openplayerjs__openplayerjs"),
        )

    def test_repo_workdir_and_tool_cache_default_under_out_dir(self) -> None:
        runner = load_runner()
        args = argparse.Namespace(out_dir=Path("/tmp/out"), workdir_root=None, tool_cache_root=None)

        self.assertEqual(
            runner.repo_workdir(args, "swup__swup"),
            Path("/tmp/out/workdirs/swup__swup"),
        )
        self.assertEqual(
            runner.repo_tool_cache_root(args, "swup__swup"),
            Path("/tmp/out/tool_cache/swup__swup"),
        )

    def test_should_skip_install_requires_reuse_flag_and_node_modules(self) -> None:
        runner = load_runner()
        args = argparse.Namespace(reuse_installed_workdirs=True)
        disabled = argparse.Namespace(reuse_installed_workdirs=False)
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td)

            self.assertFalse(runner.should_skip_install(disabled, workdir))
            self.assertFalse(runner.should_skip_install(args, workdir))
            (workdir / "node_modules").mkdir()
            self.assertTrue(runner.should_skip_install(args, workdir))

    def test_has_cached_playwright_browser_detects_persistent_browser_cache(self) -> None:
        runner = load_runner()
        with tempfile.TemporaryDirectory() as td:
            cache_root = Path(td)

            self.assertFalse(runner.has_cached_playwright_browser(cache_root))
            (cache_root / "playwright-browsers" / "chromium-123").mkdir(parents=True)
            self.assertTrue(runner.has_cached_playwright_browser(cache_root))

    def test_split_tokens_accepts_commas_semicolons_and_whitespace(self) -> None:
        runner = load_runner()

        self.assertEqual(
            runner.split_tokens("failed, timeout;pretest_setup_failed pass"),
            ["failed", "timeout", "pretest_setup_failed", "pass"],
        )

    def test_filter_plan_by_previous_results_keeps_requested_statuses(self) -> None:
        runner = load_runner()
        with tempfile.TemporaryDirectory() as td:
            previous = Path(td) / "results.jsonl"
            write_jsonl(
                previous,
                [
                    {"task_id": "rq6_0001", "status": "failed"},
                    {"task_id": "rq6_0002", "status": "pass"},
                    {"task_id": "rq6_0003", "status": "timeout"},
                    {"task_id": "rq6_0004", "status": "pretest_setup_failed"},
                ],
            )
            plan = [{"task_id": f"rq6_000{i}"} for i in range(1, 5)]

            filtered = runner.filter_plan_by_previous_results(
                plan,
                previous_results=previous,
                statuses=["failed", "timeout"],
            )

        self.assertEqual([row["task_id"] for row in filtered], ["rq6_0001", "rq6_0003"])

    def test_effective_setup_timeout_honors_minimum_override(self) -> None:
        runner = load_runner()

        self.assertEqual(
            runner.effective_setup_timeout({"timeout_sec": 120}, default_timeout=300, min_timeout=900),
            900,
        )
        self.assertEqual(
            runner.effective_setup_timeout({"timeout_sec": 1200}, default_timeout=300, min_timeout=900),
            1200,
        )
        self.assertEqual(
            runner.effective_setup_timeout({}, default_timeout=300, min_timeout=0),
            300,
        )

    def test_progress_line_includes_event_and_key_fields(self) -> None:
        runner = load_runner()

        line = runner.progress_line(
            "repo_start",
            repo_index=2,
            repo_total=4,
            repo="swup/swup",
            tasks=20,
        )

        self.assertIn("rq6-replay", line)
        self.assertIn("repo_start", line)
        self.assertIn("repo_index=2", line)
        self.assertIn("repo_total=4", line)
        self.assertIn("repo=swup/swup", line)
        self.assertIn("tasks=20", line)


if __name__ == "__main__":
    unittest.main()
