# UI Test File Inventory

This package implements the UI-test file identification step used by the study
pipeline. It identifies browser-driven web UI test files and records the
framework evidence used by later extraction stages.

## Install

```bash
npm install
```

If reading `.xlsx` input:

```bash
pip install openpyxl
```

## Quick Test

```powershell
python discover_all_repos.py `
  --repos-csv ".\github_pilot_corpus\javascript_subject_predictions_review.csv" `
  --repo-cache ".\repos_cache" `
  --output-dir ".\tmp_ui_file_inventory" `
  --node-analyzer ".\analyze_repo_ui_files.cjs" `
  --only-included `
  --limit 3
```

## Full Run

```powershell
python discover_all_repos.py `
  --repos-csv ".\github_pilot_corpus\javascript_subject_predictions_review.csv" `
  --repo-cache ".\repos_cache" `
  --output-dir ".\github_pilot_corpus\ui_file_inventory" `
  --node-analyzer ".\analyze_repo_ui_files.cjs" `
  --only-included
```

## Outputs

- `all_ui_test_files.csv`
- `all_ui_test_files.jsonl`
- `support_or_setup_files.csv`
- `support_or_setup_files.jsonl`
- `template_files.csv`
- `template_files.jsonl`
- `low_confidence_candidates.csv`
- `low_confidence_candidates.jsonl`
- `repo_ui_file_summary.csv`
- `repo_ui_file_summary.jsonl`
- `per_repo_outputs/<owner>__<repo>.json`
- `errors.jsonl`
- `overall_summary.json`

## Detection Rule

A file is detected as a browser-driven UI test file when it has an executable
test declaration such as `test(...)` or `it(...)` and browser-driven UI evidence
from Playwright, Cypress, WebDriverIO, Puppeteer, TestCafe, or Nightwatch.

## Static Config Handling

The analyzer reads repository configuration through static extraction:

- Layer 1: default filename/path patterns.
- Layer 2: partial evaluation of config files.
- Layer 3: extraction of test directories/globs from `package.json` scripts.
