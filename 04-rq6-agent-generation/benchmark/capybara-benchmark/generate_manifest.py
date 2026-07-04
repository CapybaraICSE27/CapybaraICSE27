#!/usr/bin/env python3
"""
Generate a UI-test-inventory-style JSONL manifest for agent-generated Playwright tests.

For each capybara-benchmark project, finds new .spec.ts files (not .bak),
records them relative to the project root, and emits one manifest row per file.

Usage:
    python3 generate_manifest.py [--output manifest.jsonl]
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent

PROJECTS = {
    # ── Phase 1 (original 5) ──────────────────────────────────────────────────
    "gridstack": {
        "repo": "gridstack/gridstack.js",
        "repo_url": "https://github.com/gridstack/gridstack.js",
    },
    "swup": {
        "repo": "swup/swup",
        "repo_url": "https://github.com/swup/swup",
    },
    "openplayerjs": {
        "repo": "openplayerjs/openplayerjs",
        "repo_url": "https://github.com/openplayerjs/openplayerjs",
    },
    "motion-vue": {
        "repo": "motiondivision/motion-vue",
        "repo_url": "https://github.com/motiondivision/motion-vue",
    },
    "zudoku": {
        "repo": "zuplo/zudoku",
        "repo_url": "https://github.com/zuplo/zudoku",
    },
    # ── Batch 1 (5 new complex repos) ─────────────────────────────────────────
    "actual": {
        "repo": "actualbudget/actual",
        "repo_url": "https://github.com/actualbudget/actual",
    },
    "epic-stack": {
        "repo": "epicweb-dev/epic-stack",
        "repo_url": "https://github.com/epicweb-dev/epic-stack",
    },
    "hemmelig": {
        "repo": "HemmeligOrg/Hemmelig.app",
        "repo_url": "https://github.com/HemmeligOrg/Hemmelig.app",
    },
    "cypress-realworld-app": {
        "repo": "cypress-io/cypress-realworld-app",
        "repo_url": "https://github.com/cypress-io/cypress-realworld-app",
    },
    "mermaid": {
        "repo": "mermaid-js/mermaid",
        "repo_url": "https://github.com/mermaid-js/mermaid",
    },
    # ── Batch 2 (10 additional repos) ─────────────────────────────────────────
    "trilium": {
        "repo": "TriliumNext/Trilium",
        "repo_url": "https://github.com/TriliumNext/Trilium",
    },
    "letterpad": {
        "repo": "letterpad/letterpad",
        "repo_url": "https://github.com/letterpad/letterpad",
    },
    "keystone": {
        "repo": "keystonejs/keystone",
        "repo_url": "https://github.com/keystonejs/keystone",
    },
    "react-admin": {
        "repo": "marmelab/react-admin",
        "repo_url": "https://github.com/marmelab/react-admin",
    },
    "super-productivity": {
        "repo": "super-productivity/super-productivity",
        "repo_url": "https://github.com/super-productivity/super-productivity",
    },
    "maputnik": {
        "repo": "maplibre/maputnik",
        "repo_url": "https://github.com/maplibre/maputnik",
    },
    "tldraw": {
        "repo": "tldraw/tldraw",
        "repo_url": "https://github.com/tldraw/tldraw",
    },
    "altair": {
        "repo": "altair-graphql/altair",
        "repo_url": "https://github.com/altair-graphql/altair",
    },
    "git-truck": {
        "repo": "git-truck/git-truck",
        "repo_url": "https://github.com/git-truck/git-truck",
    },
    "todomvc": {
        "repo": "laststance/react-typescript-todomvc-2022",
        "repo_url": "https://github.com/laststance/react-typescript-todomvc-2022",
    },
}


def get_commit(project_dir: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=project_dir,
            text=True,
        ).strip()
    except subprocess.CalledProcessError:
        return "unknown"


def find_generated_specs(project_dir: Path) -> list[Path]:
    """Find agent-generated .spec.ts/.spec.js files under any rq6-agent/ subdirectory."""
    specs = [
        p for p in project_dir.rglob("rq6-agent/**/*.spec.ts")
        if "node_modules" not in p.parts
    ] + [
        p for p in project_dir.rglob("rq6-agent/**/*.spec.js")
        if "node_modules" not in p.parts
    ]
    return sorted(specs)


def make_row(repo: str, repo_url: str, commit: str, file_path: str) -> dict:
    return {
        "repo": repo,
        "repo_url": repo_url,
        "commit": commit,
        "file_path": file_path,
        "file_role": "test_file",
        "confidence": "high",
        "detected_frameworks": ["Playwright"],
        "file_detected_frameworks": ["Playwright"],
        "repo_framework_context": "Playwright",
        "local_framework_context": "Playwright",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", default="manifest.jsonl",
        help="Output JSONL path (default: manifest.jsonl)",
    )
    parser.add_argument(
        "--projects", nargs="+", choices=list(PROJECTS),
        help="Limit to specific projects (default: all)",
    )
    args = parser.parse_args()

    target_projects = args.projects or list(PROJECTS)
    rows = []

    for name in target_projects:
        meta = PROJECTS[name]
        project_dir = ROOT / "projects" / name
        if not project_dir.exists():
            print(f"[skip] {name}: directory not found", file=sys.stderr)
            continue

        commit = get_commit(project_dir)
        specs = find_generated_specs(project_dir)

        if not specs:
            print(f"[skip] {name}: no generated spec files found", file=sys.stderr)
            continue

        for spec in specs:
            rel = spec.relative_to(project_dir).as_posix()
            rows.append(make_row(meta["repo"], meta["repo_url"], commit, rel))
            print(f"  [{name}] {rel}")

    output_path = ROOT / args.output
    with open(output_path, "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")

    print(f"\nWrote {len(rows)} rows to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
