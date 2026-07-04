#!/usr/bin/env python3
"""Run an exploratory RQ6 prompt-attempt smoke for one task.

This is not a blinded agent harness. It records prompt-level generated tests
written by the current Codex thread, then verifies them in isolated workdirs.
Use it for prompt debugging only, not final RQ6 paper measurements.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple


DEFAULT_BASE_WORKDIR = Path("<artifact-storage-root>/runs/rq6/reusable_workdirs/swup__swup")
DEFAULT_OUT_DIR = Path("<artifact-storage-root>/runs/rq6/codex_prompt_attempts_swup")
DEFAULT_REFERENCE_SOURCE_FILE = Path(
    "<artifact-storage-root>/repos/swup__swup/tests/functional/events.spec.ts"
)
DEFAULT_AGENT_TEST_FILE = Path("tests/functional/rq6-agent/rq6_0001.spec.ts")
DEFAULT_VERIFICATION_COMMAND = (
    "npx playwright test --config ./tests/config/playwright.config.ts "
    "tests/functional/rq6-agent/rq6_0001.spec.ts --project chromium --reporter=json"
)


PROMPTS = {
    "high": (
        "Create a Playwright UI test that verifies that Swup exposes its "
        "link-navigation lifecycle when a user activates an internal navigation link."
    ),
    "medium": (
        "Create a Playwright UI test that verifies that Swup reports its `link:click` "
        "lifecycle hook when a user clicks an internal link that navigates from the "
        "first page to the second page."
    ),
    "low": (
        "Open `/page-1.html`. Add a page or window listener for Swup's "
        "`swup:link:click` DOM event, click the internal link to `/page-2.html`, "
        "and verify that the event detail reports the Swup hook name `link:click`."
    ),
}


GENERATED_TESTS = {
    "high": """
import { test, expect } from '@playwright/test';

test.describe('RQ6 generated high abstraction', () => {
\ttest.beforeEach(async ({ page }) => {
\t\tawait page.goto('/page-1.html');
\t});

\ttest('exposes link navigation lifecycle for an internal link click', async ({ page }) => {
\t\tawait page.evaluate(() => {
\t\t\t(window as any).__rq6LifecycleHook = undefined;
\t\t\t(window as any)._swup.hooks.on('link:click', () => {
\t\t\t\t(window as any).__rq6LifecycleHook = 'link:click';
\t\t\t}, { once: true });
\t\t});

\t\tawait page.getByTestId('link-to-page-2').click();

\t\tawait expect
\t\t\t.poll(() => page.evaluate(() => (window as any).__rq6LifecycleHook))
\t\t\t.toBe('link:click');
\t});
});
""".strip()
    + "\n",
    "medium": """
import { test, expect } from '@playwright/test';

test.describe('RQ6 generated medium abstraction', () => {
\ttest.beforeEach(async ({ page }) => {
\t\tawait page.goto('/page-1.html');
\t});

\ttest('reports the link click lifecycle hook during internal navigation', async ({ page }) => {
\t\tawait page.evaluate(() => {
\t\t\t(window as any).__rq6HookName = undefined;
\t\t\t(window as any)._swup.hooks.on('link:click', () => {
\t\t\t\t(window as any).__rq6HookName = 'link:click';
\t\t\t}, { once: true });
\t\t});

\t\tawait page.getByTestId('link-to-page-2').click();

\t\tawait expect
\t\t\t.poll(() => page.evaluate(() => (window as any).__rq6HookName))
\t\t\t.toBe('link:click');
\t});
});
""".strip()
    + "\n",
    "low": """
import { test, expect } from '@playwright/test';

test.describe('RQ6 generated low abstraction', () => {
\ttest('captures the swup link click DOM event on window', async ({ page }) => {
\t\tawait page.goto('/page-1.html');
\t\tawait page.evaluate(() => {
\t\t\t(window as any).__rq6HookName = undefined;
\t\t\twindow.addEventListener('swup:link:click', (event: Event) => {
\t\t\t\t(window as any).__rq6HookName = (event as CustomEvent).detail.hook;
\t\t\t}, { once: true });
\t\t});

\t\tawait page.getByTestId('link-to-page-2').click();

\t\tawait expect
\t\t\t.poll(() => page.evaluate(() => (window as any).__rq6HookName))
\t\t\t.toBe('link:click');
\t});
});
""".strip()
    + "\n",
}


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-workdir", type=Path, default=DEFAULT_BASE_WORKDIR)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--in-place-base-workdir", action="store_true")
    ap.add_argument("--reference-source-file", type=Path, default=DEFAULT_REFERENCE_SOURCE_FILE)
    ap.add_argument("--agent-test-file", type=Path, default=DEFAULT_AGENT_TEST_FILE)
    ap.add_argument("--verification-command", default=DEFAULT_VERIFICATION_COMMAND)
    ap.add_argument("--overwrite", action="store_true")
    return ap.parse_args()


def mask_hidden_reference_test(source: str) -> Tuple[str, bool]:
    start = "\ttest('custom dom events bubble to window', async ({ page }) => {"
    start_index = source.find(start)
    if start_index == -1:
        return source, False
    end_index = source.find("\n\ttest(", start_index + len(start))
    if end_index == -1:
        end_index = source.find("\n});", start_index + len(start))
        if end_index == -1:
            return source, False
    replacement = (
        "\ttest.skip('custom dom events bubble to window', async () => {\n"
        "\t\t// hidden RQ6 reference test masked for agent attempt\n"
        "\t});"
    )
    return source[:start_index] + replacement + source[end_index:], True


def copy_attempt_workdir(base: Path, dest: Path, *, overwrite: bool) -> None:
    if dest.exists():
        if not overwrite:
            raise FileExistsError(f"Attempt workdir already exists: {dest}")
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["cp", "-al", str(base.resolve()), str(dest)],
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Failed to copy attempt workdir from {base} to {dest}:\n{proc.stderr}"
        )


def replace_text_file(path: Path, text: str) -> None:
    """Replace a file path without mutating any hardlinked source file."""
    tmp = path.with_name(f"{path.name}.rq6_tmp")
    tmp.write_text(text)
    tmp.replace(path)


def run_one_attempt(
    *,
    level: str,
    base_workdir: Path,
    out_dir: Path,
    in_place_base_workdir: bool,
    reference_source_file: Path | None,
    agent_test_file: Path,
    verification_command: str,
    overwrite: bool,
) -> Dict[str, Any]:
    attempt_root = out_dir / level
    attempt_workdir = base_workdir.resolve() if in_place_base_workdir else attempt_root / "swup__swup"
    if attempt_root.exists() and overwrite:
        shutil.rmtree(attempt_root)
    attempt_root.mkdir(parents=True, exist_ok=True)
    if not in_place_base_workdir:
        copy_attempt_workdir(base_workdir, attempt_workdir, overwrite=overwrite)

    hidden_source = attempt_workdir / "tests/functional/events.spec.ts"
    restore_source = (
        reference_source_file.read_text()
        if reference_source_file is not None and reference_source_file.is_file()
        else hidden_source.read_text()
    )
    if in_place_base_workdir:
        replace_text_file(hidden_source, restore_source)
    masked_source, masked = mask_hidden_reference_test(hidden_source.read_text())

    prompt = PROMPTS[level]
    generated_test = GENERATED_TESTS[level]
    (attempt_root / "prompt.md").write_text(prompt + "\n")
    (attempt_root / "generated_test.ts").write_text(generated_test)
    test_path = attempt_workdir / agent_test_file
    test_path.parent.mkdir(parents=True, exist_ok=True)
    replace_text_file(test_path, generated_test)

    try:
        replace_text_file(hidden_source, masked_source)
        started = time.time()
        proc = subprocess.run(
            verification_command,
            cwd=attempt_workdir,
            shell=True,
            text=True,
            capture_output=True,
            timeout=240,
        )
        duration = time.time() - started
    finally:
        if in_place_base_workdir:
            replace_text_file(hidden_source, restore_source)
    stdout_path = attempt_root / "stdout.txt"
    stderr_path = attempt_root / "stderr.txt"
    stdout_path.write_text(proc.stdout)
    stderr_path.write_text(proc.stderr)
    return {
        "agent_name": "codex_current_thread_exploratory_unblinded",
        "task_id": "rq6_0001",
        "repo_full_name": "swup/swup",
        "prompt_level": level,
        "prompt": prompt,
        "reference_test_masked": masked,
        "attempt_workdir": str(attempt_workdir),
        "generated_test_path": str(test_path),
        "verification_command": verification_command,
        "exit_code": proc.returncode,
        "status": "passed" if proc.returncode == 0 else "failed",
        "duration_sec": round(duration, 3),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
    }


def main() -> None:
    args = parse_args()
    if not args.base_workdir.is_dir():
        raise SystemExit(f"Missing base workdir: {args.base_workdir}")
    if args.out_dir.exists() and not args.overwrite:
        raise SystemExit(f"Output directory already exists; pass --overwrite: {args.out_dir}")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, Any]] = []
    for level in ("high", "medium", "low"):
        rows.append(
            run_one_attempt(
                level=level,
                base_workdir=args.base_workdir,
                out_dir=args.out_dir,
                in_place_base_workdir=args.in_place_base_workdir,
                reference_source_file=args.reference_source_file,
                agent_test_file=args.agent_test_file,
                verification_command=args.verification_command,
                overwrite=args.overwrite,
            )
        )

    (args.out_dir / "attempt_results.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    )
    print(json.dumps({"out_dir": str(args.out_dir), "results": rows}, ensure_ascii=False, indent=2))
    if any(row["status"] != "passed" for row in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
