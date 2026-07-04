#!/usr/bin/env python3
"""
Pick a stratified list of repos for pilot static-metrics validation.

Strata (default 30 repos):
  - Primary framework bucket: Playwright, Cypress, Other (rare / mixed).
  - Within each bucket: small / medium / large by test-count tertiles (within bucket).
  - Within each cell: prefer repos with hook_instance_keys or has_hook_ui_actions.

Writes one repo per line for extract_static_metrics.py --repos-file.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

_P2SM = Path(__file__).resolve().parent.parent
if str(_P2SM) not in sys.path:
    sys.path.insert(0, str(_P2SM))

from extract_static_metrics import (  # noqa: E402
    group_by_repo,
    is_executable_test_case,
    iter_jsonl,
    safe_repo_dir,
)


def norm_fw(s: str) -> str:
    x = (s or "").strip().lower()
    if "playwright" in x:
        return "playwright"
    if "cypress" in x:
        return "cypress"
    if "webdriver" in x or "wdio" in x:
        return "webdriverio"
    if "puppeteer" in x:
        return "puppeteer"
    if "selenium" in x:
        return "selenium"
    if "testcafe" in x:
        return "testcafe"
    if "nightwatch" in x:
        return "nightwatch"
    return "other"


@dataclass
class RepoProf:
    repo: str
    n_tests: int = 0
    fw_counts: Counter = field(default_factory=Counter)
    any_hook_keys: bool = False
    any_hook_ui: bool = False

    @property
    def primary_bucket(self) -> str:
        if not self.fw_counts:
            return "other"
        mode = self.fw_counts.most_common(1)[0][0]
        if mode == "playwright":
            return "playwright"
        if mode == "cypress":
            return "cypress"
        return "other"

    def hook_priority(self) -> int:
        return 1 if (self.any_hook_keys or self.any_hook_ui) else 0


def build_profiles(test_cases_path: Path) -> Dict[str, RepoProf]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in iter_jsonl(test_cases_path):
        if not is_executable_test_case(row):
            continue
        repo = str(row.get("repo") or "").strip()
        if repo:
            grouped[repo].append(row)

    out: Dict[str, RepoProf] = {}
    for repo, rows in grouped.items():
        p = RepoProf(repo=repo, n_tests=len(rows))
        for tc in rows:
            p.fw_counts[norm_fw(str(tc.get("framework") or ""))] += 1
            if tc.get("hook_instance_keys"):
                p.any_hook_keys = True
            if tc.get("has_hook_ui_actions"):
                p.any_hook_ui = True
        out[repo] = p
    return out


def tertile_cutoffs(counts: List[int]) -> Tuple[int, int]:
    if not counts:
        return 0, 0
    s = sorted(counts)
    n = len(s)
    i33 = max(0, int(round(0.33 * (n - 1))))
    i66 = max(0, int(round(0.66 * (n - 1))))
    return s[i33], s[i66]


def size_bin(n: int, t1: int, t2: int) -> str:
    if n <= t1:
        return "small"
    if n <= t2:
        return "medium"
    return "large"


def sorted_pool(cell_repos: List[RepoProf], rng: random.Random) -> List[RepoProf]:
    """Hook-rich first, then shuffle among ties for variety, then re-stabilize by name."""
    cell_repos = list(cell_repos)
    rng.shuffle(cell_repos)
    return sorted(cell_repos, key=lambda p: (-p.hook_priority(), p.repo))


def pick_until(
    pool: List[RepoProf],
    need: int,
    selected: Set[str],
    stratum_prefix: str,
    trace: List[Dict[str, Any]],
    size_suffix: str,
) -> int:
    got = 0
    for p in pool:
        if got >= need:
            break
        if p.repo in selected:
            continue
        selected.add(p.repo)
        trace.append(
            {
                "repo": p.repo,
                "stratum": f"{stratum_prefix}:{size_suffix}",
                "n_tests": p.n_tests,
                "hooks": p.hook_priority(),
            }
        )
        got += 1
    return got


def fill_bucket_targets(
    profiles: Dict[str, RepoProf],
    bucket_key: str,
    target: int,
    selected: Set[str],
    trace: List[Dict[str, Any]],
    rng: random.Random,
) -> None:
    repos = [p for p in profiles.values() if p.primary_bucket == bucket_key]
    if not repos or target <= 0:
        return

    trace_start = len(trace)
    counts = [p.n_tests for p in repos]
    t1, t2 = tertile_cutoffs(counts)
    cells: Dict[str, List[RepoProf]] = defaultdict(list)
    for p in repos:
        cells[size_bin(p.n_tests, t1, t2)].append(p)

    base, rem = divmod(target, 3)
    want = {"small": base + (1 if rem > 0 else 0), "medium": base + (1 if rem > 1 else 0), "large": base}
    for sz in want:
        pick_until(sorted_pool(cells[sz], rng), want[sz], selected, bucket_key, trace, sz)

    have = len(trace) - trace_start
    shortage = target - have
    if shortage <= 0:
        return

    overflow_pool = sorted_pool(
        [p for p in repos if p.repo not in selected],
        rng,
    )
    pick_until(overflow_pool, shortage, selected, bucket_key, trace, "backfill")


def stratified_select(
    profiles: Dict[str, RepoProf],
    *,
    total: int,
    rng: random.Random,
    quotas_default: Tuple[int, int, int],
) -> Tuple[List[str], List[Dict[str, Any]]]:
    pw_t, cy_t, ot_t = quotas_default
    assert pw_t + cy_t + ot_t == total

    n_pw = sum(1 for p in profiles.values() if p.primary_bucket == "playwright")
    n_cy = sum(1 for p in profiles.values() if p.primary_bucket == "cypress")
    n_ot = sum(1 for p in profiles.values() if p.primary_bucket == "other")

    # Shrink quotas if bucket is thin; redistribute surplus in corpus order playwright -> cypress -> other
    pw_t = min(pw_t, n_pw)
    cy_t = min(cy_t, n_cy)
    ot_t = min(ot_t, n_ot)
    deficit = total - (pw_t + cy_t + ot_t)
    order_extra = []
    order_extra.extend(["playwright"] * (n_pw - pw_t))
    order_extra.extend(["cypress"] * (n_cy - cy_t))
    order_extra.extend(["other"] * (n_ot - ot_t))
    rng.shuffle(order_extra)

    ii = 0
    while deficit > 0 and ii < len(order_extra):
        b = order_extra[ii]
        ii += 1
        if b == "playwright" and pw_t < n_pw:
            pw_t += 1
            deficit -= 1
        elif b == "cypress" and cy_t < n_cy:
            cy_t += 1
            deficit -= 1
        elif b == "other" and ot_t < n_ot:
            ot_t += 1
            deficit -= 1

    selected: Set[str] = set()
    trace: List[Dict[str, Any]] = []

    fill_bucket_targets(profiles, "playwright", pw_t, selected, trace, rng)
    fill_bucket_targets(profiles, "cypress", cy_t, selected, trace, rng)
    fill_bucket_targets(profiles, "other", ot_t, selected, trace, rng)

    # Global backfill if still short (degenerate corpus)
    short = total - len(selected)
    if short > 0:
        rest = sorted(
            [p for p in profiles.values() if p.repo not in selected],
            key=lambda p: (-p.hook_priority(), p.repo),
        )
        rng.shuffle(rest)
        rest = sorted(rest, key=lambda p: (-p.hook_priority(), p.repo))
        for p in rest:
            if short <= 0:
                break
            selected.add(p.repo)
            trace.append(
                {
                    "repo": p.repo,
                    "stratum": "global_backfill",
                    "n_tests": p.n_tests,
                    "hooks": p.hook_priority(),
                }
            )
            short -= 1

    ordered = sorted(selected, key=lambda r: profiles[r].repo)
    return ordered, trace


def main() -> None:
    ap = argparse.ArgumentParser(description="Stratified repo list for static metrics pilot")
    ap.add_argument("--input-run-dir", type=Path, required=True)
    ap.add_argument("--repo-cache", type=Path, default=Path(r"<repo-cache>"))
    ap.add_argument("--total", type=int, default=30)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--quotas",
        type=str,
        default="12,12,6",
        help="playwright,cypress,other quotas (comma-separated); must sum to --total",
    )
    ap.add_argument("--require-cache", action="store_true", help="Only repos with a cloned cache dir")
    ap.add_argument(
        "--max-tests-per-repo",
        type=int,
        default=None,
        help="Exclude repos above this test count from the sampling pool (avoids UI5-scale giants in pilots)",
    )
    ap.add_argument("--write-list", type=Path, required=True)
    ap.add_argument("--write-meta", type=Path, default=None)
    args = ap.parse_args()

    tc_path = args.input_run_dir / "test_cases.jsonl"
    if not tc_path.exists():
        raise FileNotFoundError(tc_path)

    quotas_parts = [int(x.strip()) for x in args.quotas.split(",")]
    if len(quotas_parts) != 3 or sum(quotas_parts) != args.total:
        raise SystemExit("--quotas must be three ints summing to --total")

    profiles = build_profiles(tc_path)
    if args.max_tests_per_repo is not None:
        cap = args.max_tests_per_repo
        excluded = [p.repo for p in profiles.values() if p.n_tests > cap]
        profiles = {k: v for k, v in profiles.items() if v.n_tests <= cap}
        print(
            json.dumps(
                {
                    "max_tests_per_repo": cap,
                    "excluded_repos_count": len(excluded),
                    "excluded_repos_sample": sorted(excluded)[:15],
                    "pool_after_cap": len(profiles),
                },
                indent=2,
            ),
            file=sys.stderr,
        )
    if args.require_cache:
        before = len(profiles)
        profiles = {
            k: v
            for k, v in profiles.items()
            if (args.repo_cache / safe_repo_dir(k)).is_dir()
        }
        print(
            json.dumps(
                {
                    "require_cache": True,
                    "repos_in_corpus": before,
                    "repos_with_clone_dir": len(profiles),
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        if len(profiles) < args.total:
            print(
                f"WARN: Only {len(profiles)} repos have cache clones; stratified sample "
                f"may be smaller than --total.",
                file=sys.stderr,
            )

    rng = random.Random(args.seed)

    ordered, trace = stratified_select(
        profiles, total=args.total, rng=rng, quotas_default=tuple(quotas_parts)  # type: ignore[arg-type]
    )

    args.write_list.parent.mkdir(parents=True, exist_ok=True)
    args.write_list.write_text("\n".join(ordered) + "\n", encoding="utf-8")

    if args.write_meta:
        args.write_meta.parent.mkdir(parents=True, exist_ok=True)
        args.write_meta.write_text(
            json.dumps(
                {
                    "total_requested": args.total,
                    "total_selected": len(ordered),
                    "seed": args.seed,
                    "quotas": quotas_parts,
                    "require_cache": args.require_cache,
                    "repos": trace,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    print(json.dumps({"selected": len(ordered), "write_list": str(args.write_list)}, indent=2), file=sys.stderr)


if __name__ == "__main__":
    main()
