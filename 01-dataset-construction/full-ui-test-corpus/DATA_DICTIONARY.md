# Data Dictionary

This file describes the tracked dataset tables in `01-dataset-construction/full-ui-test-corpus/`. The canonical machine-readable tables are JSON/JSONL. CSV files are convenience exports for spreadsheet inspection. List-valued CSV cells are JSON-encoded strings.

## Corpus Unit

- Repository: a GitHub repository from the JavaScript >=500-star UI-test census and it is owned by an organization.
- Test file: a UI-test-file inventory candidate that produced at least one extracted test case.
- Test case: one executable test declaration identified by test-case extraction.

## Counts

- Inventory layer: 353 repositories, 9,955 UI-test-file candidates, and 51,657 test cases.

## dataset_repos.json / dataset_repos.csv

| Field | Type | Meaning |
|---|---|---|
| `artifact_id` | string | Dataset identifier. |
| `repo` | string | GitHub `owner/name`. |
| `repo_url` | string | Repository URL. |
| `commit` | string | Pinned commit when all extracted files for the repo share one commit. |
| `commits` | list[string] | All pinned commits observed for the repo. |
| `frameworks` | list[string] | UI test frameworks observed in extracted test cases. |
| `inventory_test_file_count` | integer | UI-test inventory files for the repo. |
| `test_case_count` | integer | Extracted test cases for the repo. |
| `high_confidence_test_file_count`, `medium_confidence_test_file_count` | integer | UI-test inventory confidence counts among extracted files. |
| `tests_with_direct_ui_actions` | integer | Tests with direct body UI actions. |
| `tests_with_direct_assertions` | integer | Tests with direct body assertions. |
| `tests_with_hook_ui_actions` | integer | Tests with hook-origin UI actions. |
| `tests_with_helper_expanded_ui_actions` | integer | Tests with helper/page-object/custom-command UI actions found by expansion. |
| `tests_with_expanded_ui_actions` | integer | Tests with hook or helper-expanded UI actions. |
| `tests_extraction_empty` | integer | Medium-confidence tests with no direct body UI action or assertion. |

## dataset_test_files.jsonl / dataset_test_files.csv

| Field | Type | Meaning |
|---|---|---|
| `repo`, `repo_url`, `commit`, `commits` | string/list | Repository identity and pinned revision information. |
| `frameworks` | list[string] | Frameworks observed in tests extracted from the file. |
| `file_path`, `file_url` | string | Repository-relative test file path and GitHub blob URL. |
| `file_role`, `language` | string | UI-test file role and language metadata. |
| `test_case_count` | integer | Extracted tests in the file. |
| `normal_test_count`, `skipped_test_count`, `only_test_count` | integer | Static status counts from test declarations. |
| `first_test_start_line`, `last_test_end_line` | integer | Source line span across extracted tests in the file. |
| `tests_with_*` | integer | Per-file counts for analyzer coverage flags. |

## dataset_test_cases.jsonl

| Field | Type | Meaning |
|---|---|---|
| `repo`, `repo_url`, `commit` | string | Repository identity and pinned revision. |
| `framework` | string | Framework assigned to the test case. |
| `file_path`, `file_url` | string | Repository-relative source path and GitHub blob URL. |
| `test_ordinal_in_file` | integer | Deterministic order of the test within its file. |
| `test_id` | string | Stable analyzer test identifier. |
| `test_name` | string | Static test title/name. |
| `test_status`, `suite_status` | string | Static status such as normal/skipped/only. |
| `describe_path` | list[string] | Nested suite/describe labels. |
| `declaration_line`, `start_line`, `end_line` | integer | Source declaration and full test span. |
| `callback_start_line`, `callback_end_line` | integer | Test callback body span. |
| `test_declaration_type` | string | Test API/declaration form. |
| `fixtures_used` | list[string] | Fixture parameter names observed on the test callback. |
| `has_direct_ui_actions` | boolean | Direct body UI action found. |
| `has_direct_assertions` | boolean | Direct body assertion found. |
| `has_hook_ui_actions` | boolean | Hook-origin UI action found. |
| `has_helper_expanded_ui_actions` | boolean | Helper/page-object/custom-command UI action found. |
| `has_expanded_ui_actions` | boolean | Hook or helper-expanded UI action found. |
| `extraction_empty` | boolean | Medium-confidence test with no direct UI action or assertion. |

## dataset_test_cases_sample.csv

This file contains the first 1,000 rows from `dataset_test_cases.jsonl` after sorting. It is provided for quick spreadsheet inspection; it is not the authoritative full test-case table.

## checksums.sha256

Each line is `<sha256>  <relative path>`. The checksum file covers every tracked file in this dataset directory except `checksums.sha256` itself.
