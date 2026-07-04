# Test-Level Feature Extraction

Extracts executable UI test cases and their features, including UI actions,
assertions, inputs, setup/teardown operations, hooks, fixtures, and helper or
page-object expansions.

**Project overview (RQ1-RQ6):** [`../README.md`](../README.md)

The artifact root's recommended entry point is `../../run_companion_pipeline.py`;
this directory preserves the lower-level
extractor used by that wrapper.

## Prerequisites

- Python 3.10+
- Node.js 18+
- Git (only if `--clone-missing`)
- UI test file inventory: `ui_file_inventory_final/all_ui_test_files.jsonl`
- Repo cache: `<repo-cache>` (`owner__repo` directories)

## Setup

```powershell
cd 05-implementation/test-feature-extraction
npm install
```

## Run Test Extraction And Direct Feature Extraction

```powershell
python extract_test_features.py `
  --input-jsonl "..\github_pilot_corpus\ui_file_inventory_final\all_ui_test_files.jsonl" `
  --repo-cache "<repo-cache>" `
  --output-dir "..\github_pilot_corpus\ui_test_feature_extraction_v1" `
  --node-analyzer "./analyze_repo_test_cases.cjs" `
  --subphase 2ab `
  --resume `
  --limit 5
```

## Extraction Stages

| Flag | Outputs |
|------|---------|
| `2a` | `test_cases.jsonl` |
| `2b` | `test_case_features_direct.jsonl` |
| `2ab` | both test cases and direct features |
| `2c` | expanded features, helper edges, unresolved calls |
| `2d` | aggregate RQ1-RQ5 metrics |

## Validation

```powershell
python scripts/validate_2a_sample.py --output-dir <run_dir> --input-jsonl <merged_inventory>
python scripts/validate_2b_sample.py --output-dir <run_dir>
python scripts/validate_2c_sample.py --output-dir <run_dir>
```

## RQ Aggregation

Streaming aggregation (expanded-only features, per-test summaries). See `PHASE2D_ROADMAP.md`.

```powershell
python rq_aggregation/run_rq_aggregation.py --input-dir <run_dir>
python rq_aggregation/test_rq_aggregation.py
```
