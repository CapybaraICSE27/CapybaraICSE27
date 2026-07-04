# Full UI Test Corpus

This directory records the repository, test-file, and extracted test-case layers
used in the study.

## Study Pipeline Labels

- Repository selection and UI-test file identification: GitHub corpus selection plus static UI-test-file inventory.
- Test-case extraction: AST extraction of runnable test declarations, source ranges, suite paths, fixtures, and framework metadata.
- Feature-event extraction: AST extraction of setup/control/teardown operations, inputs, UI actions, locator calls, synchronization, assertions, and static metrics.
- Helper, hook, fixture, and page-object expansion: resolution of events outside the direct test body.
- RQ-specific aggregation and semantic classification: conversion of shared evidence records into RQ1-RQ5 tables, including LLM-assisted semantic labels where used.

## Scope

- Extracted corpus: 352 repositories, 9,955 test-case-bearing files, 51,657 extracted UI test cases.

## Files

- `dataset_repos.json`: one row per extracted repository, including URL, pinned commit, frameworks, file counts, test-case count, and analyzer coverage flags.
- `dataset_test_files.jsonl`: one row per extracted test file, including original path, URL, test counts, and per-file analyzer coverage counts.
- `dataset_test_cases.jsonl`: one row per extracted test case, including repo, file, test id/name, declaration lines, suite path, fixtures, and direct/expanded UI/assertion flags.
- `DATA_DICTIONARY.md`: field-level schema, units, and interpretation notes for each table.
- `dataset_repos.csv`, `dataset_test_files.csv`: spreadsheet-friendly CSV exports of the lighter tables.
- `dataset_test_cases_sample.csv`: first 1,000 deterministic test-case rows for spreadsheet inspection. Use `dataset_test_cases.jsonl` for full test-case analysis.
- `checksums.sha256`: SHA-256 checksums for every tracked file in this dataset directory except the checksum manifest itself.
