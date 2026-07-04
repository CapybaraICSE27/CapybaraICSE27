# RQ1 setup/teardown semantic intent taxonomy

Milestone 2 adds a **semantic annotation layer** on top of the existing low-level inventory (`rq1_environment_control_*`). The two layers answer different questions and must not be merged.

| Layer | CSV prefix | Question |
|-------|------------|----------|
| Inventory | `rq1_environment_control_*` | What setup/control-related features were extracted? |
| Semantics | `rq1_setup_teardown_intent_*` | Why does each setup/teardown unit exist (phase, scope, intent)? |

## Codebook dimensions

### Phase

- `setup` — prepares state before interactions
- `teardown` — restores/cleans state after interactions
- `setup_and_teardown` — mixed helper **body** (wrapper-only row when expansion succeeded; not propagated to child statements)
- `unclear` — insufficient lifecycle signal

Per-call phase hints use `statement_phase_hint_ast` (from API category). Mixed helper bodies use `helper_body_phase_hint_ast` on wrapper rows only.

### Scope

- `global_or_project` — support/global hooks, project fixtures
- `suite_or_fixture` — `before` / `after` / `beforeAll` / `afterAll` (Mocha/Cypress suite hooks); TestCafe `fixture.before` / `fixture.after` via `hook_owner_kind=fixture`
- `per_test_hook` — `beforeEach` / `afterEach`; TestCafe `test.before` / `test.after` via `hook_owner_kind=test|unknown` (when owner cannot be resolved)
- `helper_or_framework_extension` — custom commands, expanded helpers, fixtures
- `inline_test_body` — direct test-body setup calls
- `unclear`

### Primary intent

See `rq1_setup_teardown_taxonomy.json` for the full label set. Key intents:

- `navigation_bootstrap` — initial page/route entry (heuristic; not every `goto`)
- `auth_session_state` — login/session/storage state
- `test_data_or_backend_state` — seed/API/DB/fixture data
- `network_mock_or_spy` — intercept/route/mock
- `cleanup_restore_state` — residual teardown/cleanup where structured evidence does not identify the target domain; cleanup of auth, browser context, or backend data is classified under that target domain
- `generic_setup_teardown_utility` — named setup helper without resolved body
- `unclear`

### Operation kind

`primary_intent` identifies the target domain of a setup/teardown operation.
Cleanup/reset semantics are preserved separately in `operation_kind` so reported
tables can still distinguish whether cleanup/restore actions occur during setup or
teardown after target-domain reclassification.

- `cleanup_restore` — explicit reset, clear, delete, restore, teardown, close, or remove operation
- `other_setup_teardown` — setup/teardown operation without cleanup/restore action semantics

Network mocks are treated conservatively: a mocked `DELETE` route is still a
mocking operation, while framework APIs that reset or remove mock infrastructure
(for example `resetHandlers`, `unroute`, or `restoreAllMocks`) are cleanup
operations.

For manual review, classify `primary_intent` by the affected target domain, not
by the cleanup verb. Real `POST`/`PUT`/`PATCH`/`DELETE` requests against API
entities or configuration are `test_data_or_backend_state`; auth/session/token
cookie or storage cleanup is `auth_session_state`; generic cookie/storage cleanup
without auth-specific evidence is `browser_context_or_client_state`.
Use `cleanup_restore_state` only when cleanup/reset/restore is visible but the
target domain cannot be identified.

## Helper wrapper vs body statements (Option B)

When helper expansion succeeds, the direct `helper_call` is emitted with `wrapper_only=1` and **excluded from reported intent distributions**. Expanded body statements are separate semantic rows.

Report both:

- `wrapper_call_count` — direct helper wrappers (audit)
- `paper_facing_unit_count` — reported semantic units (schema column name)
- `body_statement_count` — legacy alias for `paper_facing_unit_count` (all non-wrapper units, not helper-body-only)

Static file **load sites** only (`input` rows with `rq2_unit=load_site`, `input_channel_ast=load_site`, `input_load_path_ast`, or load APIs like `cy.fixture` / `cy.readFile`) are eligible setup units mapped to `test_data_or_backend_state` with `phase=setup`. UI text-entry consumers (`page.fill`, `cy.type`, `selectOption` with traced fixture data) stay in RQ2/RQ4 and are **not** RQ1 units.

## Navigation bootstrap heuristic

This is a **static source-line-order heuristic** (not runtime hook execution order). Hook declarations that appear after a test in source text may still apply at runtime; line order can be misleading in rare layouts.

A hook or test-body navigation is `navigation_bootstrap` when:

1. It is the **first** navigation in the test body by line order, **or**
2. It occurs **before** the first non-navigation UI action, **and**
3. No prior setup intent unit exists in the same test — where “prior setup” means any resolved row with `phase` in `{setup, setup_and_teardown}` (including rows whose `primary_intent` is `unclear`), except prior setup in the **same hook instance** when `hook_instance_key` matches.

**Excluded**:

- Mid-test navigation after clicks/interactions
- Navigation after any prior setup-phase unit (conservative; blocks even when prior intent label is `unclear`)
- Navigation after auth/data/network setup in a different hook instance or test body

## RQ1 vs RQ3

RQ3 describes **how** interactions are structured (inline, helper, page object, hook flow). RQ1 describes **why** a setup/teardown unit exists.

## Partial coverage (after Milestone 3)

M2 provenance plus M3 AST fields (`statement_phase_hint_ast`, `helper_body_phase_hint_ast`, `framework_api_category`, `hook_owner_kind`, call-site offsets) are consumed when JSONL is re-extracted at schema v39+. Phase/API fields are treated as structured only when their companion basis fields are structured (`ast_known_framework_api`, `ast_nested_framework_api`, `mixed_structured_framework_api`); `call_text_framework_api`, `callee_name_heuristic`, and legacy unlabeled Cypress command roles remain fallback evidence.

**Control eligibility:** generic `feature_type=control` rows are excluded unless `is_rq1_environment_feature()` matches (e.g. cookies, session, `cy.task`) or framework/Cypress command provenance indicates real setup. Structured bases are high-trust; fallback bases such as `call_text_framework_api`, `callee_name_heuristic`, or legacy Cypress command roles remain eligible only as reviewable fallback evidence. Utility controls (`cy.wrap`, `cy.then`, `cy.as`) are never eligible.

**Residual limits**:

- Unresolved helper expansion bodies (`helper_resolution_status: unresolved`)
- Global support hook extraction without full `astCtx` / import map
- Cypress `cy.each` callback iteration (requires function callback; receiver query excluded from loop context)
- Ambiguous mid-test navigation excluded from `navigation_bootstrap` by design

Assertion-chain coverage limits belong in `RQ5_ASSERTION_CHAIN_TAXONOMY.md`, not RQ1.

## Validation gates (soft)

- Report `needs_review_fraction` — target interpret, not block
- Report `high_confidence_non_unclear_fraction` among classified units
- Report `wrapper_call_count` separately from body statement counts
