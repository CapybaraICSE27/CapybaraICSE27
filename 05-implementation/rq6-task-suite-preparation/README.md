# RQ6 Task-Suite Preparation

This directory contains the implementation used to prepare the RQ6 human
baseline task suite and the agent-generation evaluation inputs. It screens
candidate repositories, prepares runnable workdirs, selects stable human-written
baseline tests, separates the held-out baseline tests from prompt context, and
records task prompts plus verification commands for agent attempts.

The artifact root's recommended entry point is `../../run_companion_pipeline.py`.
This directory preserves the lower-level
scripts used by that wrapper and the configuration files needed to reproduce the
task-suite construction workflow.

## Workflow Stages

| Study stage | Main scripts | Main outputs |
|-------------|--------------|--------------|
| Candidate repository screening | `scripts/01_build_static_candidate_repos.py` | `rq6_static_candidate_repos.jsonl`, screening summaries |
| Environment and workdir preparation | `scripts/02_check_repo_environment.py`, `scripts/03_install_repos.py` | repository workdirs, install results |
| Runner and app detection | `scripts/04_detect_runner_and_app.py` | runner/app metadata and boot-check results |
| Human-baseline selection | `scripts/05_select_candidate_human_tests.py`, `scripts/06_run_human_baselines.py` | candidate tests, baseline replay results, stability labels |
| Runnable panel construction | `scripts/07_build_local_runnable_panel.py` | selected repository panel and stable baseline test set |
| Agent task construction | `scripts/08_build_phase2_task_suite.py`, `scripts/09_validate_phase2_masking.py` | task suite, prompt files, prompt-separation checks |
| Agent smoke/replay support | `scripts/10_replay_task_suite_human_smoke.py`, `scripts/11_run_prompt_attempt_smoke.py` | smoke-test evidence and prompt-attempt diagnostics |

## Agent Workdir And Baseline-Separation Protocol

For each agent attempt, the harness starts from a runnable repository workdir
with the held-out human baseline test separated from prompt context. The
intended per-task flow is:

1. Copy or clone the runnable repository snapshot into an attempt-specific
   workdir.
2. Remove or mask only the source test block corresponding to the held-out human
   baseline. Unrelated tests remain available as normal project context.
3. Provide the agent with the task prompt, target test path, and allowed project
   files.
4. Require the agent to write the generated test under an `rq6-agent/`
   directory.
5. Run the recorded verification command in the same environment.
6. Save the generated file, diff, command output, status, duration, and failure
   category.

The exact human baseline test is separated from prompt context. Existing
non-answer tests remain in the repository because they represent realistic
developer context and local style.

## Harness-Only Metadata

The evaluation harness may use these files for bookkeeping and scoring, but they
are not prompt inputs:

- `human_test_baseline_runs.jsonl`
- `human_test_stability.jsonl`
- `manual_task_review.jsonl`
- `source_review_packets.jsonl`
- `review_packets/`
- `rq6_tasks_manifest.jsonl` fields that reveal source-file locations or
  baseline status
- original source snippets for the held-out baseline test

Prompt-facing task-suite files include:

- `agent_task_specs.jsonl`
- `agent_prompt_variants.jsonl`
- `prompts/*.md`
- `prompts/high/`, `prompts/medium/`, and `prompts/low/`
- `mask_validation_findings.jsonl`

## Running The Lower-Level Scripts

From this directory, inspect each lower-level script with `--help` before
running it directly:

```bash
python scripts/01_build_static_candidate_repos.py --help
python scripts/02_check_repo_environment.py --help
python scripts/03_install_repos.py --help
python scripts/04_detect_runner_and_app.py --help
python scripts/05_select_candidate_human_tests.py --help
python scripts/06_run_human_baselines.py --help
python scripts/07_build_local_runnable_panel.py --help
```

Installation and test execution scripts plan commands by default; pass
`--execute` only when running in isolated workdirs with the required browser and
Node.js toolchain available.

## Preserved Configuration

- `config/rq6_phase1_config.yaml`: default paths and selection thresholds.
- `config/pretest_setup_commands.jsonl`: repository-specific setup commands.
- `config/app_start_overrides.jsonl`: app startup overrides used during runner
  detection and replay.

The tracked companion artifact focuses on source materials. Cloned
repositories, dependency caches, browser reports, and large run directories are
run products.
