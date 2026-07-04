# RQ3 Pattern Taxonomy (framework-neutral)

The analysis characterizes how UI tests structure and manage interactions along
**locator strategy**, **workflow abstraction**, and **synchronization**. Categories are framework-neutral;
`raw_framework_api` and `framework` columns preserve audit evidence.

**Locator robustness:** Reported values are documentation-aligned **robustness signals**, not
ground-truth quality. Positive signals (roles, test contracts, readable text) vs
implementation-coupled or opaque signals are proxies for manual interpretation.

## Locator: normalized strategy → framework APIs

| Normalized strategy | Playwright | Cypress | Puppeteer | TestCafe | WebDriverIO | Selenium / Nightwatch |
|-------------------|------------|---------|-----------|----------|-------------|------------------------|
| role_or_accessibility | getByRole | findByRole / plugins | locator ARIA/text | limited | accessibility selectors | wrappers if present |
| label_or_form_affordance | getByLabel, getByPlaceholder | findByLabelText | text/locator | Selector filters | text/accessibility | By.* + wrappers |
| test_id_or_data_contract | getByTestId | data-cy, data-testid | attribute CSS | attribute filters | CSS/data | CSS/data |
| text_content | getByText | cy.contains | text / XPath | withText | text | linkText / custom |
| css_selector | page.locator('css') | cy.get | $, locator | Selector('.x') | $, $$ | By.cssSelector |
| xpath_selector | locator('xpath=…') | cy.xpath | XPath | XPath if used | XPath | By.xpath |
| framework_selector_object | Locator | chainable | Locator / ElementHandle | Selector() | $() element | WebElement |
| webdriver_by_strategy | — | — | — | — | By.* via $ | By.* |

## Locator composition

`direct_chain`, `standalone_locator_query` (e.g. `cy.get('#x')` without terminal action),
`stored_locator`, `chained_refinement`, `positional_refinement`,
`parameterized_locator`, `page_object_mediated`, `helper_mediated`,
`custom_command_mediated`, `unknown`

## Locator robustness signals

`user_facing_accessibility_signal`, `stable_test_contract_signal`,
`readable_text_signal`, `implementation_coupled_signal`,
`positional_or_structural_signal`, `opaque_or_unresolved_signal`, `mixed_signal`

## Implementation model (provenance vs regex)

| Concern | Phase 2B signal | Phase 2D rule |
|--------|-----------------|---------------|
| Playwright fixtures | `fixture_param_name`, `fixture_declared_by` from `test.extend` / callback destructuring | `playwright_fixture` only when provenance fields present — **not** from `use*` name shape |
| Page vs POM | `page_symbol_origin_ast` from assignment (`context.newPage` vs `new LoginPage`) + native API guard | `page_object_model` vs `framework_page_instance` |
| Cypress commands | `Cypress.Commands.add` registry (Phase 2C expand); body roles: `session_setup`, `test_data_setup`, `locator_helper`, `workflow_abstraction`, `utility` | `session_setup`/`test_data_setup` → `hook_setup_flow` (setup/control-flow, not literal hook); `utility` → `domain_helper`; `workflow_abstraction` → `cypress_custom_command` |
| Standalone locator | composition `standalone_locator_query` | taxonomy alignment only |
| Reporting | — | `rq3_patterns_{event,test,repo}_weighted_summary.csv` |

Run manifest: `rq_aggregation_summary.json` includes `rq3_ast_provenance` counters; warns when AST fields are absent on a large corpus.

## Workflow abstraction kinds

`inline_test_body`, `page_object_model`, `framework_page_instance` (Playwright `userPage`
variables with native `goto`/`getByRole`/`locator` — not POM), `page_object`,
`screenplay_or_task_object`, `domain_helper`,
`cypress_custom_command`, `playwright_fixture`, `testcafe_page_model`,
`webdriverio_page_object`, `selenium_page_object`, `nightwatch_page_object`,
`bdd_step_definition`, `hook_setup_flow`, `unresolved_helper`, `unknown`

### `hook_setup_flow` — setup/control-flow, not necessarily a hook

The label **`hook_setup_flow`** means *setup or control-flow abstraction* (session/auth,
test-data seeding, backend prep), **not** “must run inside `before`/`after` hook.”

Typical sources:

| Source | Example | Notes |
|--------|---------|-------|
| Hook-attached UI | `beforeEach` callback body | `interaction_ownership = hook_attached` |
| Cypress custom command (AST role) | `cy.login()` with `session_setup` / `test_data_setup` body | `abstraction_kind = hook_setup_flow` but ownership often stays `custom_command_body` + `framework_extension` because the call site is still a custom command |
| Direct setup calls | `cy.request`, hook utilities | Classified by feature type / source kind |

When a Cypress custom command is classified as `session_setup` or `test_data_setup`,
Phase 2D sets **`abstraction_kind = hook_setup_flow`** while **retaining**
`interaction_ownership = custom_command_body` and `reuse_scope = framework_extension`.
That pairing is intentional: the *workflow role* is setup/control-flow; the
*implementation locus* is still a reusable Cypress command extension.

The label is retained for taxonomy stability and corresponds to setup or
state-management flow in the reported summaries.

### `page_object_model` vs `page_object` (and framework-specific PO labels)

Both labels appear in the taxonomy and in AST output. They are **related, not duplicate
categories**:

| Label | Role |
|-------|------|
| `page_object_model` | **General / AST / intermediate** — emitted by Phase 2B when provenance or naming indicates a page-object class (`new LoginPage()`, `LoginPage`-style roots). Used in `_WORKFLOW_AST_ABSTRACTION` mapping. |
| `page_object` | **Framework-normalized emitted label** for Playwright, Cypress, and Puppeteer after Phase 2D resolution via `_page_object_kind(framework)`. |
| `webdriverio_page_object`, `selenium_page_object`, … | Same normalization for other frameworks. |

Resolution path:

1. AST may emit `workflow_kind_ast: page_object_model`.
2. `resolve_workflow_pattern()` maps AST kinds through `_WORKFLOW_AST_ABSTRACTION`, then
   `_page_object_kind(framework)` when the abstraction is PO-like.
3. Aggregates treat all entries in `PAGE_OBJECT_MODEL_KINDS` as page-object signal for
   archetypes and stratified sampling (`page_object`, `page_object_model`, `testcafe_page_model`, …).

For prevalence reporting, **`page_object` and `page_object_model` are treated as the
same architectural family** except in AST-vs-emitted-label audits.

## Workflow archetypes (per test)

`inline_direct`, `page_object_centric`, `page_object_centric_unresolved`,
`helper_mediated`, `framework_extension_centric`, `hook_or_fixture_centric`,
`bdd_step_centric`, `structured_step_centric`, `layered`, `unresolved_thin_wrapper`,
`mixed_or_unclear`

`page_object_centric_unresolved`: multiple page-object method calls
(`page_object_call_count` ≥ 2) with little or no expanded page-object UI inside the test
(PO call bodies not inlined). Signals PO-centric structure without observable inlined PO UI.

`page_object_call_count` counts **page-object method/constructor calls** only
(`helper_call`, `page_object_ctor`) whose resolved `abstraction_kind` is a page-object
kind (AST-aware). Expanded UI actions inside PO bodies use `page_object_ui_action_count`
instead; they update `page_object_signal_present` but do not increment `page_object_call_count`.

## Sync patterns (explicit events only)

`fixed_delay`, `element_state_wait`, `navigation_or_load_wait`, `network_wait`,
`predicate_or_custom_condition`, `event_wait` (e.g. `page.waitForEvent`), `assertion_retry_wait`,
`unresolved_custom_wait`

**Auto-wait vs query retry:** `auto_wait_capable_action_count` counts
actionability auto-wait on actions (Playwright/TestCafe/WDIO). `retryable_query_count`
counts Cypress-style retryable queries (`cy.get`, `cy.contains`) separately.
Neither emits fake sync events.

**Locator events CSV:** Only rows with `locator_present=true` are written to
`rq3_locator_pattern_events.csv`. Summary field `rq3_locator_ui_action_rows` counts
all classified UI actions; `rq3_locator_events` counts locator-bearing rows only.

## AST + regex hybrid (pilot)

Phase 2B (`astPatternExtractor.js`) emits optional `*_ast` fields on feature rows.
Phase 2D (`resolve_locator_pattern`, `resolve_wait_pattern`, `resolve_workflow_pattern`) uses:

1. AST fields when present (`evidence_basis` / `locator_evidence_basis`: `ast_call_chain` | `ast_selector_argument` | `resolved_helper_body_locator`)
2. Explicit fallback labels otherwise (`regex_fallback`, `source_metadata`, or `unresolved`)

Locator rows also carry `locator_composition_evidence_basis`, because strategy may be
AST-derived while composition is inferred from source metadata or regex fallback.
Workflow rows carry `workflow_evidence_basis` to distinguish AST body/fixture/import
evidence from feature metadata and fallback labels.

`sync_event_count` in `rq3_patterns_by_test.csv` equals the sum of all sync pattern events
(including assertion-retry sync), matching `rq3_sync_pattern_events.csv` row count per test.

AST-vs-regex locator audit: `rq3_ast_vs_regex_locator_audit.csv` (all rows with
`locator_strategy_ast`; `mismatch_type` tags strategy/composition/selector/low_confidence).
Finalize summaries (manual-review queue, not automatic error counts):

| Metric | Meaning |
|--------|---------|
| `rq3_ast_locator_audit_rows` | All AST-labeled locator rows written to the audit CSV |
| `rq3_ast_regex_locator_mismatches` | Strategy, composition, or selector literal disagreements |
| `rq3_ast_locator_low_confidence_rows` | AST labeled with `ast_confidence=low` |
| `rq3_ast_locator_audit_nonmatch_rows` | Any audit row with `mismatch_type != match` |

Treat audit rows as **disagreement / inspection samples**, not necessarily misclassifications.

Assertion-retry sync events prefer AST evidence (`wait_subtype_ast:
assertion_retry_wait` from parsed matcher calls or Cypress `should` / `and`
assertion-call shape); Python raw-text matching is retained only as explicit
fallback when AST fields are absent.
For AST-located wait rows, `sync_evidence_basis` records whether the subtype came from
an AST wait API, numeric literal, string/array alias, assertion call, assertion
matcher, binary numeric expression, or a lower-confidence symbol-name heuristic.
Hook `cy.wait` / `waitUntil` classify as `wait_synchronization` for RQ3.
Standalone rebuild:
`scripts/rq3_pattern_mining/build_ast_vs_regex_audit.py`

Manual validation sample: `scripts/rq3_pattern_mining/sample_validation.py`

## Outputs

- `rq3_locator_pattern_events.csv`
- `rq3_sync_pattern_events.csv`
- `rq3_workflow_pattern_events.csv`
- `rq3_patterns_by_test.csv`
- `rq3_patterns_by_repo.csv`

Legacy `rq3_structure_by_test.csv` remains for backward compatibility.
