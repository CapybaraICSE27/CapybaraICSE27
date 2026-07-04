# Implementation Sources

This directory contains the implementation sources needed to inspect and rerun
the study pipeline. Generated outputs, dependency folders, caches, logs, and
local environment files are omitted.

## Study Pipeline Map

| Study stage | Implementation source |
|---|---|
| UI-test file identification | `ui-test-file-identification/` |
| Test-case extraction | `test-feature-extraction/` |
| Direct feature-event extraction | `test-feature-extraction/lib/phase2b/` |
| Helper, hook, fixture, and page-object expansion | `test-feature-extraction/lib/phase2c/` |
| Complexity and navigation-metric extraction | `static-metrics/` |
| RQ aggregation and semantic classification | `rq-aggregation/` |
| LLM-assisted semantic classification | `rq-aggregation/llm_semantic_categorizer.py` |
| Manual-audit evidence packaging | `review-bundle-generation/` |
| RQ6 task-suite preparation | `rq6-task-suite-preparation/` |

## One-Command Reproduction

From the artifact root, run:

```bash
python run_companion_pipeline.py \
  --repos-csv <repos.csv> \
  --repo-cache <repo-cache-dir> \
  --output-dir <run-dir> \
  --no-llm
```

Use `--enable-llm --llm-env-file <path>` to reproduce the LLM-assisted semantic classification portions.
