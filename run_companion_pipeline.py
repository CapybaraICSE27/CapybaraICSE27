#!/usr/bin/env python3
"""Run the companion UI-test analysis pipeline with one command."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
IMPLEMENTATION = ROOT / "05-implementation"
DISCOVERY = IMPLEMENTATION / "ui-test-file-identification"
EXTRACTION = IMPLEMENTATION / "test-feature-extraction"
STATIC_METRICS = IMPLEMENTATION / "static-metrics"
RQ_AGGREGATION = IMPLEMENTATION / "rq-aggregation"
REVIEW_BUNDLES = IMPLEMENTATION / "review-bundle-generation"


def safe_repo_dir(full_name: str) -> str:
    return full_name.replace("/", "__").replace(":", "_")


def run(cmd: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print("[companion-run] " + " ".join(str(part) for part in cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def merged_node_env() -> dict[str, str]:
    env = os.environ.copy()
    phase2_node_modules = EXTRACTION / "node_modules"
    if phase2_node_modules.is_dir():
        existing = env.get("NODE_PATH")
        env["NODE_PATH"] = str(phase2_node_modules) if not existing else f"{phase2_node_modules}{os.pathsep}{existing}"
    python_paths = [RQ_AGGREGATION, STATIC_METRICS, REVIEW_BUNDLES]
    existing_python_path = env.get("PYTHONPATH")
    env["PYTHONPATH"] = os.pathsep.join(str(path) for path in python_paths)
    if existing_python_path:
        env["PYTHONPATH"] = f"{env['PYTHONPATH']}{os.pathsep}{existing_python_path}"
    return env


def ensure_node_dependencies() -> None:
    if not (EXTRACTION / "node_modules" / "ts-morph").is_dir():
        run(["npm", "install"], cwd=EXTRACTION)
    if not (DISCOVERY / "node_modules" / "ts-morph").is_dir():
        run(["npm", "install"], cwd=DISCOVERY)


def read_repo_names(repos_csv: Path) -> list[str]:
    with repos_csv.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        repos = []
        for row in reader:
            full_name = str(row.get("full_name") or "").strip()
            if full_name:
                repos.append(full_name)
        return repos


def validate_offline_cache(repos_csv: Path, repo_cache: Path) -> None:
    missing = []
    for repo in read_repo_names(repos_csv):
        cached = repo_cache / safe_repo_dir(repo)
        if not (cached / ".git").is_dir():
            missing.append(f"{repo} -> {cached}")
    if missing:
        details = "\n".join(missing)
        raise SystemExit(f"--offline-repo-cache requested, but these repo caches are missing:\n{details}")


def event_csv_has_rows(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    with path.open(encoding="utf-8", errors="ignore") as handle:
        return sum(1 for _ in handle) > 1


def tiny_run_can_have_empty_review_bundles(run_dir: Path) -> bool:
    return not event_csv_has_rows(run_dir / "rq2_input_events.csv")


def write_placeholder_review_bundles(run_dir: Path, reason: str) -> None:
    bundle_names = [f"review_bundle_rq{i}" for i in range(1, 6)]
    for name in bundle_names:
        bundle = run_dir / name
        bundle.mkdir(parents=True, exist_ok=True)
        manifest = {
            "bundle": name,
            "status": "placeholder_for_empty_smoke_run",
            "reason": reason,
        }
        (bundle / "bundle_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        (bundle / "EMPTY_REVIEW_BUNDLE.txt").write_text(
            "This small smoke run did not contain enough rows for the full manual-review bundle builder.\n",
            encoding="utf-8",
        )
    combined = run_dir / "review_bundle_rq1-5.zip"
    with zipfile.ZipFile(combined, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in bundle_names:
            for path in (run_dir / name).rglob("*"):
                if path.is_file():
                    zf.write(path, path.relative_to(run_dir).as_posix())


def materialize_root_jsonl_from_sidecars(run_dir: Path, sidecar_suffix: str, output_name: str) -> None:
    output = run_dir / output_name
    if output.exists() and output.stat().st_size > 0:
        return
    sidecars = sorted((run_dir / "per_repo_outputs").glob(f"*.{sidecar_suffix}.jsonl"))
    if not sidecars:
        return
    with output.open("w", encoding="utf-8") as dst:
        for sidecar in sidecars:
            with sidecar.open(encoding="utf-8") as src:
                for line in src:
                    if line.strip():
                        dst.write(line)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repos-csv", type=Path, required=True, help="CSV with full_name/html_url and include labels.")
    parser.add_argument("--repo-cache", type=Path, required=True, help="Local repository cache, using owner__repo directories.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory where all pipeline outputs are written.")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--offline-repo-cache", action="store_true", help="Fail if a repo is missing from --repo-cache instead of cloning.")
    parser.add_argument("--no-llm", action="store_true", help="Disable LLM semantic correction. This is the default.")
    parser.add_argument("--enable-llm", action="store_true", help="Enable LLM semantic correction for supported RQ labels.")
    parser.add_argument("--llm-env-file", type=Path, default=EXTRACTION / ".env.local")
    args = parser.parse_args()

    if args.enable_llm and args.no_llm:
        raise SystemExit("Use either --enable-llm or --no-llm, not both.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.repo_cache.mkdir(parents=True, exist_ok=True)
    if args.offline_repo_cache:
        validate_offline_cache(args.repos_csv, args.repo_cache)
    ensure_node_dependencies()

    env = merged_node_env()
    inventory_dir = args.output_dir / "ui-test-file-identification"
    run_dir = args.output_dir / "test-feature-extraction"
    static_dir = run_dir / "static_metrics"

    run(
        [
            sys.executable,
            str(DISCOVERY / "discover_all_repos.py"),
            "--repos-csv",
            str(args.repos_csv),
            "--repo-cache",
            str(args.repo_cache),
            "--output-dir",
            str(inventory_dir),
            "--node-analyzer",
            str(DISCOVERY / "analyze_repo_ui_files.cjs"),
            "--only-included",
            "--resume",
        ],
        env=env,
    )

    run(
        [
            sys.executable,
            str(EXTRACTION / "extract_test_features.py"),
            "--input-jsonl",
            str(inventory_dir / "all_ui_test_files.jsonl"),
            "--repo-cache",
            str(args.repo_cache),
            "--output-dir",
            str(run_dir),
            "--node-analyzer",
            str(EXTRACTION / "analyze_repo_test_cases.cjs"),
            "--subphase",
            "2c",
            "--workers",
            str(max(1, args.workers)),
            "--resume",
        ],
        env=env,
    )
    materialize_root_jsonl_from_sidecars(run_dir, "features_expanded", "test_case_features_expanded.jsonl")
    materialize_root_jsonl_from_sidecars(run_dir, "features_direct", "test_case_features_direct.jsonl")
    materialize_root_jsonl_from_sidecars(run_dir, "test_cases", "test_cases.jsonl")

    run(
        [
            sys.executable,
            str(STATIC_METRICS / "extract_static_metrics.py"),
            "--input-run-dir",
            str(run_dir),
            "--repo-cache",
            str(args.repo_cache),
            "--output-dir",
            str(static_dir),
            "--workers",
            str(max(1, args.workers)),
            "--resume",
        ],
        env=env,
    )

    aggregation_cmd = [
        sys.executable,
        str(RQ_AGGREGATION / "run_rq_aggregation.py"),
        "--input-dir",
        str(run_dir),
        "--static-metrics-dir",
        str(static_dir),
        "--workers",
        str(max(1, args.workers)),
    ]
    if args.enable_llm:
        aggregation_cmd.extend(["--enable-llm-correction", "--llm-env-file", str(args.llm_env_file)])
    run(aggregation_cmd, env=env)

    review_cmd = [
        sys.executable,
        str(REVIEW_BUNDLES / "build_all_review_bundles.py"),
        "--run-dir",
        str(run_dir),
        "--workers",
        "1",
    ]
    print("[companion-run] " + " ".join(str(part) for part in review_cmd), flush=True)
    review_result = subprocess.run(review_cmd, cwd=ROOT, env=env)
    if review_result.returncode != 0:
        if not tiny_run_can_have_empty_review_bundles(run_dir):
            raise subprocess.CalledProcessError(review_result.returncode, review_cmd)
        write_placeholder_review_bundles(
            run_dir,
            "Full review-bundle generation requires non-empty RQ event tables; this smoke run has no RQ2 input events.",
        )
        print("[companion-run] Wrote placeholder review bundles for empty smoke run", flush=True)

    print(f"[companion-run] Pipeline finished. Outputs are in {args.output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
