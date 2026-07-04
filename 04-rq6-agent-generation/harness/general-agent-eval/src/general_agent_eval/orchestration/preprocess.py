"""Preprocess the staged input: git reset, test clearing, dependency injection."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING, Any

from general_agent_eval.orchestration.errors import DockerRunError
from general_agent_eval.orchestration.manifest import write_manifest
from general_agent_eval.orchestration.staging import (
    git_repo_root,
    initialize_synthetic_git_baseline,
    write_git_patch,
)

if TYPE_CHECKING:
    from general_agent_eval.preprocessing.git_reset import GitResetTarget


def _inject_rest_assured_step(
    *,
    staged_input: Path,
    output_dir: Path,
    service: dict[str, Any] | None,
) -> dict[str, Any]:
    rest_assured_config = service.get("rest_assured") if service else None
    if rest_assured_config is None:
        # e.g. features-service ships a legacy RestAssured and omits the manifest block.
        print(
            "[rest-assured] skipped: service has no rest_assured config in the manifest",
            flush=True,
        )
        return {"enabled": True, "status": "skipped", "reason": "no rest_assured config"}

    from general_agent_eval.preprocessing.rest_assured_injection import (
        InjectionConfig,
        RestAssuredInjectionError,
        inject_rest_assured,
    )

    try:
        config = InjectionConfig.from_dict(rest_assured_config)
        result = inject_rest_assured(staged_input, config)
    except RestAssuredInjectionError as exc:
        raise DockerRunError(f"Failed to inject RestAssured: {exc}") from exc

    injection_patch = None
    if git_repo_root(staged_input) == staged_input:
        injection_patch_path = output_dir / "dependency_injection.patch"
        write_git_patch(
            staged_input=staged_input,
            output_path=injection_patch_path,
            relative_paths=[config.target_pom],
        )
        injection_patch = str(injection_patch_path)

    print(
        f"[rest-assured] {result.status} pom={config.target_pom} "
        f"version={'managed' if result.managed else result.version}",
        flush=True,
    )
    return {
        "enabled": True,
        **result.to_dict(),
        "dependency_injection_patch": injection_patch,
    }


def preprocess_staged_input(
    *,
    args: argparse.Namespace,
    staged_input: Path,
    output_dir: Path,
    reset_target: GitResetTarget | None = None,
    service: dict[str, Any] | None = None,
) -> dict[str, Any]:
    inject_enabled = getattr(args, "inject_rest_assured", False)
    preprocessing: dict[str, Any] = {
        "reset_git": {"enabled": args.reset_git},
        "test_clearing": {"enabled": args.clear_tests},
        "rest_assured_injection": {"enabled": inject_enabled},
    }

    if args.reset_git:
        from general_agent_eval.preprocessing.git_reset import (
            GitVcsError,
            reset_to_commit,
            reset_to_pinned_commit,
        )

        try:
            if reset_target is None:
                result = reset_to_pinned_commit(staged_input)
            else:
                result = reset_to_commit(
                    staged_input,
                    reset_target.pinned_commit,
                    reset_target=reset_target,
                )
        except GitVcsError as exc:
            raise DockerRunError(f"Failed to reset staged Git state: {exc}") from exc
        preprocessing["reset_git"] = {
            "enabled": True,
            "repo_root": str(result.repo_root),
            "pinned_commit": result.pinned_commit,
            "source_repo_root": (
                str(reset_target.repo_root) if reset_target is not None else None
            ),
            "superproject_root": (
                str(result.superproject_root) if result.superproject_root else None
            ),
            "superproject_relative_path": result.superproject_relative_path,
        }
        print(
            "[git-reset] " f"repo={result.repo_root} commit={result.pinned_commit}",
            flush=True,
        )

    if args.clear_tests:
        from general_agent_eval.preprocessing.java_test_clearing import TestClearingError

        if getattr(args, "workload", "java") == "javascript":
            from general_agent_eval.preprocessing.js_test_clearing import clear_js_tests as _clear_fn
        else:
            from general_agent_eval.preprocessing.java_test_clearing import clear_java_tests as _clear_fn  # type: ignore[assignment]

        try:
            clear_result = _clear_fn(staged_input)
        except TestClearingError as exc:
            raise DockerRunError(f"Failed to clear tests: {exc}") from exc

        clearing_manifest_path = output_dir / "cleared_tests.json"
        write_manifest(clearing_manifest_path, clear_result.to_dict())

        clearing_patch_path = output_dir / "test_clearing.patch"
        clearing_patch = None
        if git_repo_root(staged_input) == staged_input:
            write_git_patch(
                staged_input=staged_input,
                output_path=clearing_patch_path,
                relative_paths=[item.path for item in clear_result.removed],
            )
            clearing_patch = str(clearing_patch_path)

        preprocessing["test_clearing"] = {
            "enabled": True,
            "removed_count": len(clear_result.removed),
            "manifest_path": str(clearing_manifest_path),
            "test_clearing_patch": clearing_patch,
        }
        print(
            "[test-clearing] "
            f"removed={len(clear_result.removed)} manifest={clearing_manifest_path}",
            flush=True,
        )

    if inject_enabled:
        preprocessing["rest_assured_injection"] = _inject_rest_assured_step(
            staged_input=staged_input,
            output_dir=output_dir,
            service=service,
        )

    # Commit the testless baseline once, after clearing and injection, so both the
    # cleared tree and the injected dependency land in the baseline and stay out of
    # the agent's diff. Patches above were captured first, against the original git.
    if args.clear_tests or inject_enabled:
        git_baseline = initialize_synthetic_git_baseline(staged_input)
        preprocessing["git_baseline"] = git_baseline
        if args.clear_tests:
            preprocessing["test_clearing"]["git_history_sanitized"] = True
            preprocessing["test_clearing"]["git_baseline"] = git_baseline

    return preprocessing
