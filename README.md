# Companion Artifact

This directory contains the replication package for the paper “A Large-Scale
Study of Real-World Web UI Testing,” which we submitted to ICSE. It brings
together the constructed dataset, definitions of the analysis categories, manual
review results, implementation code for the analysis model, and the RQ6
agent-generated tests with their harness implementation.

## Main Contents

- `01-dataset-construction/full-ui-test-corpus/`: 352 repositories, 9,941 UI-test files, and 51,657 extracted UI test cases.
- `02-analysis-model/framework-api-mappings/`: framework API mappings for RQ1 setup/teardown intent, RQ4 UI action organization, and RQ5 assertions.
- `03-manual-review-results/rq1-rq5-full-corpus-reviewed/`: human-filled manual review rows, memo, and summary.
- `04-rq6-agent-generation/`: benchmark repository, agent harness, prompts, and archived agent-written test source files.
- `05-implementation/`: implementation sources for file identification, test extraction, expansion, static metrics, RQ aggregation, review bundles, and RQ6 task-suite preparation.


## One-Command Reproduction

From the artifact root:

```bash
python run_companion_pipeline.py \
  --repos-csv <repos.csv> \
  --repo-cache <repo-cache-dir> \
  --output-dir <run-dir> \
  --no-llm
```

This command runs UI-test file identification, test-case extraction, direct
feature-event extraction, helper/hook/fixture/page-object expansion, static
metrics, RQ aggregation, and manual-review bundle generation. Add
`--enable-llm --llm-env-file <path>` to reproduce the LLM-assisted
semantic-classification steps.
