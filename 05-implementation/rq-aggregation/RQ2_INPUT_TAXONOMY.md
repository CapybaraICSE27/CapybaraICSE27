# RQ2 Input Taxonomy

RQ2 separates **the immediate input source shape** (`input_source_class`) from
**deeper value provenance** (`input_provenance*`) and **whether the value looks
domain-plausible** (`input_plausibility`). Reported summaries keep these
dimensions separate. A call such as `page.fill(selector, draftMessage)` has
`input_source_class=variable_input`; provenance is a separate trace of where
`draftMessage` was defined or produced.

## Reported Dimensions

### `input_source_class` (use-site source shape)

| Label | Meaning |
|-------|---------|
| `literal_input` | Visible literal at UI action |
| `variable_input` | Identifier/member/call; origin not resolved |
| `variable_from_external_file` | Variable traced to JSON/YAML/CSV/fixture file + field path |
| `fixture_file_input` | Framework fixture load (`cy.fixture`, Playwright fixture data file) |
| `external_file_input` | Generic static file load (`readFile`, `readFileSync`, JSON import) |
| `environment_input` | `process.env`, `Cypress.env`, etc. |
| `generated_input` | faker/random/uuid/nanoid/Math.random |
| `parameterized_input` | `test.each` / table row / param arg |
| `file_upload_input` | `setInputFiles`, `setFilesToUpload`, `selectFile` |
| `api_seed_input` | Inline API/seed response (bounded static trace) |
| `network_mock_payload_input` | Fixture/readFile used only as intercept/route mock body |
| `unknown_input` | Fallback when AST and provenance fail |

### `input_provenance_family` and `input_provenance`

| Label family | Meaning |
|--------------|---------|
| `inline_literal` | Literal value appears directly at the UI input argument |
| `literal_constant` | Identifier/member traces to a local literal definition |
| `inline_object` / `inline_array` | Identifier/member or direct argument traces to an inline container |
| `external_file` | Identifier/member traces to JSON/YAML/CSV/fixture data |
| `parameterized_row` | Value comes from `test.each` / table-row parameterization |
| `generated` | Value comes from faker/chance/uuid/nanoid/factory-style generation |
| `environment` | Value comes from `process.env`, `Cypress.env`, `Deno.env`, or equivalent |
| `api_seed` | Value comes from an API/request callback or seeded backend response |
| `alias` | Value flows through a Cypress alias |
| `composite_expression` | UI input combines multiple resolved components, e.g. fixture data plus imported JSON |
| `missing` | No robust AST/symbol provenance trace was available |

Composite expressions expose `input_provenance_components_json`; manual audits
use those components rather than treating the composite as one opaque source.

**Plausibility note for `api_seed_input`:** default plausibility is `technical_or_control_input` because the value is usually opaque API-created setup state. When the member path and field context jointly suggest a domain-facing field (e.g. `testUser.email` into an email field), plausibility may upgrade to `domain_plausible_input` with medium confidence and review.

**Inline object origins:** variables traced to object literals keep `input_source_class=variable_input` and expose `input_origin_kind=object_literal` / `object_literal_member` with `input_evidence_basis=ast_object_literal`. They are not counted as `generated_input`, which is reserved for generator/factory-style values.

**Upload object literals:** when `selectFile`/`setInputFiles` passes `{ fileName, mimeType, ... }`, visible metadata is surfaced as `partially_visible` and plausibility defaults to `domain_plausible_input` (medium).

### `input_plausibility` (semantic plausibility, not provenance)

| Label | Meaning |
|-------|---------|
| `domain_plausible_input` | Visible value + field context suggest real domain data (e.g. email in email field) |
| `placeholder_or_dummy_input` | Obvious dummy tokens (`asdf`, `foo`, `lorem`, `test123`) |
| `validation_or_edge_case_input` | Empty string, boundary values, invalid-format probes |
| `technical_or_control_input` | Env tokens, headers, mock status codes, localStorage keys |
| `not_observable` | Opaque variable/fixture/env; plausibility not assessable |
| `unclear` | Visible but ambiguous (`admin`, `default`, `sample`) |

### `value_visibility`

| Label | Meaning |
|-------|---------|
| `visible` | Literal or fully resolved fixture field value |
| `partially_visible` | Template literal with static head, or partial path |
| `opaque` | Variable/call without provenance |
| `unknown` | Extraction failed |

## Pipeline

1. **Phase 2B** — `inputPatternExtractor.js` emits AST facts on `input` rows and UI text-entry companions.
2. **Phase 2C** — `inputDataRegistry.js` resolves static file paths; `inputProvenanceLinker.js` binds variables and value expressions to registry entries, local definitions, generated calls, environment reads, API callbacks, aliases, and composite-expression components.
3. **Phase 2D** — `resolve_input_pattern()` chooses `input_source_class`; `input_plausibility.py` assigns plausibility **after** source resolution.

Regex is **audit/fallback only** for legacy JSONL (`rq2_ast_vs_regex_input_audit.csv`).

## Cypress fixture rule

`cy.fixture(...)` is a **load-site / input** by default. Classify as `network_mock_payload_input` only when the same alias/path is wired through `cy.intercept` / `page.route` mock response (provenance pass).
