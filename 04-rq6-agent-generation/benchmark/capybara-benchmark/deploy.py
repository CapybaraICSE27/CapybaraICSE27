"""Deploy one or all benchmark projects."""

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent / "scripts"

DIST_DIR = Path(__file__).parent / "dist"

PROJECTS = {
    "swup": SCRIPTS_DIR / "deploy_swup.sh",
    "openplayerjs": SCRIPTS_DIR / "deploy_openplayerjs.sh",
    "motion-vue": SCRIPTS_DIR / "deploy_motion_vue.sh",
    "zudoku": SCRIPTS_DIR / "deploy_zudoku.sh",
    "gridstack": SCRIPTS_DIR / "deploy_gridstack.sh",
}


def deploy(name: str, script: Path) -> bool:
    print(f"\n{'='*60}")
    print(f"Deploying: {name}")
    print(f"{'='*60}")
    result = subprocess.run(["bash", str(script)], check=False)
    dest = DIST_DIR / name
    if result.returncode == 0 and dest.exists():
        n = sum(1 for _ in dest.rglob("*") if _.is_file())
        print(f"\n  Deployed to: {dest}  ({n} files)")
    return result.returncode == 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "projects",
        nargs="*",
        choices=[*PROJECTS.keys(), "all"],
        default=["all"],
        help="Project(s) to deploy, or 'all' (default)",
    )
    args = parser.parse_args()

    targets = list(PROJECTS.keys()) if "all" in args.projects else args.projects

    failed: list[str] = []
    for name in targets:
        ok = deploy(name, PROJECTS[name])
        if not ok:
            failed.append(name)

    print()
    if failed:
        print(f"FAILED: {', '.join(failed)}")
        sys.exit(1)
    else:
        print(f"All {len(targets)} project(s) deployed successfully.")


if __name__ == "__main__":
    main()
