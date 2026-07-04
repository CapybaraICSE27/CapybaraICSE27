#!/usr/bin/env python3
"""Build RQ1-RQ5 review bundles from an aggregated Phase 2C/2D run directory."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import datetime as _dt
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

BUNDLE_BUILDERS = (
    ("build_rq1_review_bundle.py", "review_bundle_rq1"),
    ("build_rq2_review_bundle.py", "review_bundle_rq2"),
    ("rq3_pattern_mining/build_rq3_review_bundle.py", "review_bundle_rq3"),
    ("build_rq4_review_bundle.py", "review_bundle_rq4"),
    ("build_rq5_review_bundle.py", "review_bundle_rq5"),
)

DISALLOWED_LLM_MODELS = {"gpt-5.4-nano"}


def _timestamp() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _format_elapsed(started: float | None) -> str:
    if started is None:
        return ""
    elapsed = max(0.0, time.monotonic() - started)
    minutes, seconds = divmod(int(elapsed), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f" elapsed={hours:d}h{minutes:02d}m{seconds:02d}s"
    if minutes:
        return f" elapsed={minutes:d}m{seconds:02d}s"
    return f" elapsed={seconds:d}s"


def log_progress(message: str, *, started: float | None = None) -> None:
    print(f"[{_timestamp()}] {message}{_format_elapsed(started)}", flush=True)


def reset_bundle_dir(run_dir: Path, bundle_name: str) -> Path:
    bundle_dir = (run_dir / bundle_name).resolve()
    if bundle_dir.parent != run_dir:
        raise RuntimeError(f"Refusing to reset bundle outside run dir: {bundle_dir}")
    if not bundle_dir.name.startswith("review_bundle_rq"):
        raise RuntimeError(f"Refusing to reset unexpected bundle directory: {bundle_dir}")
    archive_path = bundle_dir.with_suffix(".zip")
    if archive_path.parent != run_dir:
        raise RuntimeError(f"Refusing to reset bundle zip outside run dir: {archive_path}")
    if archive_path.exists():
        archive_path.unlink()
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    return bundle_dir


def zip_bundle(bundle_dir: Path) -> Path:
    if not bundle_dir.is_dir():
        raise FileNotFoundError(f"Missing review bundle directory: {bundle_dir}")
    archive_base = bundle_dir.with_suffix("")
    archive_path = bundle_dir.with_suffix(".zip")
    if archive_path.exists():
        archive_path.unlink()
    shutil.make_archive(str(archive_base), "zip", root_dir=bundle_dir)
    return archive_path


def zip_combined_bundles(run_dir: Path, bundle_names: tuple[str, ...]) -> Path:
    archive_path = run_dir / "review_bundle_rq1-5.zip"
    if archive_path.exists():
        archive_path.unlink()
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for bundle_name in bundle_names:
            bundle_dir = run_dir / bundle_name
            if not bundle_dir.is_dir():
                raise FileNotFoundError(f"Missing review bundle directory: {bundle_dir}")
            for path in bundle_dir.rglob("*"):
                if path.is_file():
                    zf.write(path, path.relative_to(run_dir))
    return archive_path


def assert_no_disallowed_llm_models(run_dir: Path, *, allow_nano_llm: bool = False) -> None:
    """Fail combined regenerated bundles when source events still carry old Nano LLM labels."""
    if allow_nano_llm:
        return
    offenders: list[tuple[Path, str]] = []
    for path in run_dir.glob("*.csv"):
        try:
            with path.open(encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                if "llm_model" not in (reader.fieldnames or []):
                    continue
                seen: set[str] = set()
                for row in reader:
                    model = str(row.get("llm_model") or "").strip()
                    if model in DISALLOWED_LLM_MODELS and model not in seen:
                        offenders.append((path, model))
                        seen.add(model)
                        break
        except UnicodeDecodeError:
            continue
    if offenders:
        details = ", ".join(f"{path.name}:{model}" for path, model in offenders[:8])
        raise RuntimeError(
            "Refusing to regenerate RQ1-RQ5 review bundles with disallowed LLM model "
            f"values ({details}). Rerun Phase 2D with gpt-5.4-mini or pass --allow-nano-llm "
            "only when intentionally rebuilding historical Nano artifacts."
        )


def build_one_review_bundle(
    idx: int,
    total: int,
    script_name: str,
    bundle_name: str,
    run_dir_path: Path,
    scripts_dir: Path,
    run_started: float,
) -> Path:
    bundle_started = time.monotonic()
    log_progress(
        f"Review bundle {idx}/{total} {bundle_name} started",
        started=run_started,
    )
    reset_bundle_dir(run_dir_path, bundle_name)
    cmd = [sys.executable, str(scripts_dir / script_name), "--run-dir", str(run_dir_path)]
    log_progress("Running: " + " ".join(cmd), started=bundle_started)
    subprocess.run(cmd, check=True)
    zip_path = zip_bundle(run_dir_path / bundle_name)
    log_progress(
        f"Review bundle {idx}/{total} {bundle_name} done zip={zip_path}",
        started=bundle_started,
    )
    return zip_path


def build_review_bundles(
    run_dir_path: Path,
    *,
    workers: int = 1,
    allow_nano_llm: bool = False,
) -> list[Path]:
    run_started = time.monotonic()
    scripts = Path(__file__).resolve().parent
    run_dir_path = run_dir_path.resolve()
    log_progress(
        f"Review bundle generation started run_dir={run_dir_path} bundles={len(BUNDLE_BUILDERS)}",
        started=run_started,
    )
    assert_no_disallowed_llm_models(run_dir_path, allow_nano_llm=allow_nano_llm)
    max_workers = max(1, min(int(workers or 1), len(BUNDLE_BUILDERS)))
    indexed_builders = [
        (idx, name, bundle_name)
        for idx, (name, bundle_name) in enumerate(BUNDLE_BUILDERS, start=1)
    ]
    zip_paths_by_idx: dict[int, Path] = {}
    if max_workers == 1:
        for idx, name, bundle_name in indexed_builders:
            zip_paths_by_idx[idx] = build_one_review_bundle(
                idx,
                len(BUNDLE_BUILDERS),
                name,
                bundle_name,
                run_dir_path,
                scripts,
                run_started,
            )
    else:
        log_progress(f"Running review bundles with workers={max_workers}", started=run_started)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(
                    build_one_review_bundle,
                    idx,
                    len(BUNDLE_BUILDERS),
                    name,
                    bundle_name,
                    run_dir_path,
                    scripts,
                    run_started,
                ): idx
                for idx, name, bundle_name in indexed_builders
            }
            for fut in concurrent.futures.as_completed(futures):
                zip_paths_by_idx[futures[fut]] = fut.result()

    zip_paths = [zip_paths_by_idx[idx] for idx, _name, _bundle_name in indexed_builders]
    combined_zip = zip_combined_bundles(run_dir_path, tuple(bundle_name for _, bundle_name in BUNDLE_BUILDERS))
    zip_paths.append(combined_zip)
    log_progress(f"Combined review bundle zip created: {combined_zip}", started=run_started)
    log_progress("Review bundle generation finished", started=run_started)
    return zip_paths


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument(
        "--allow-nano-llm",
        action="store_true",
        help="Allow historical gpt-5.4-nano LLM columns when intentionally rebuilding old artifacts.",
    )
    ap.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of RQ review-bundle builders to run concurrently.",
    )
    args = ap.parse_args()
    zip_paths = build_review_bundles(
        args.run_dir,
        workers=args.workers,
        allow_nano_llm=args.allow_nano_llm,
    )
    print("Review bundle zips:")
    for path in zip_paths:
        print(f"  {path}")


if __name__ == "__main__":
    main()
