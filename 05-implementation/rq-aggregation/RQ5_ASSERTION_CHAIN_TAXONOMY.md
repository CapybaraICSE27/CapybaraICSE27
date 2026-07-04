# RQ5-B assertion chain taxonomy

Milestone 3 adds **AST-tagged assertion chain metadata** linked by `assertion_chain_root_id`.

## Reported Metrics

Report chain metrics as **AST-tagged assertion-chain metrics among assertions with chain metadata**. Always pair:

- `assertions_with_chain_fields`
- `assertions_missing_chain_metadata_count`
- `tagged_chained_assertion_fraction` / `tagged_standalone_assertion_count`

Do not treat missing chain metadata as standalone assertions.

## Matcher-level vs chain-level counts

| Field | Granularity |
|-------|-------------|
| `soft_assertion_count`, `grouped_assertion_count` | **Matcher-level** — one soft/grouped chain with two semantic matchers counts twice |
| `soft_assertion_chain_count`, `grouped_assertion_chain_count` | **Chain-level** — distinct `assertion_chain_root_id` values |
| `chained_assertion_count`, `standalone_assertion_count` | Matcher-level among tagged assertions only |

## Framework labels

| Field | Meaning |
|-------|---------|
| `assertion_framework_context` | Test framework from extraction context (Playwright, Cypress, …) |
| `assertion_library_syntax` | Assertion syntax family inferred from AST (may differ, e.g. Chai-style in Playwright tests) |
| `assertion_framework` | Legacy CSV alias for `assertion_library_syntax` |

## Verification intent evidence

`verification_intent` is AST-first when assertion-chain metadata is available.

| Field | Meaning |
|-------|---------|
| `verification_intent_evidence_basis` | `ast_assertion_matcher`, `ast_assertion_semantic_matcher`, `ast_callback_nested_assertion`, `ast_assertion_subject`, `ast_assertion_subject_network_context`, `subject_name_heuristic_fallback`, `lexical_oracle_category_fallback`, `lexical_fallback`, `lexical_accessibility_context`, `lexical_api_config_boolean_context`, `lexical_html_content_context`, `lexical_style_context`, or `ast_assertion_matcher_unmapped` |
| `verification_intent_confidence` | High for direct AST matcher/subject evidence, medium for oracle-category fallback, low for unmapped/unspecified cases |
| `verification_intent_matched_signal` | Matcher, subject, oracle category, or fallback signal used for the label |
| `assertion_semantic_matcher_basis_ast` | AST source for semantic matcher refinements; currently `ast_cypress_should_argument` for Cypress `should("...")` / `and("...")` string arguments |
| `assertion_subject_basis_ast` | AST subject-expression basis; identifier-name heuristics are not treated as strong subject evidence |
| `assertion_callback_intent_basis_ast` | AST source for Cypress callback summaries; currently `ast_callback_nested_assertion` when nested matcher/property/literal-argument nodes provide a verification-intent hint |

## Review-bundle chain evidence

`review_bundle_rq5/rq5_assertion_chain_sample.csv` is emitted as chain evidence packets. When one row from an assertion chain is sampled, all rows with the same `assertion_chain_root_id` are included.

| Field | Meaning |
|-------|---------|
| `chain_matcher_sequence_json` | Ordered semantic matcher sequence for the chain, e.g. `["should:be.visible", "and:contain.text"]` |
| `non_assertion_chain_methods_json` | Ordered non-assertion methods in the chain, e.g. Cypress query/action methods such as `get`, `find`, or `eq` |
| `chain_group_size` / `chain_group_rows_json` | Review-bundle evidence showing all sibling matcher rows sharing the sampled `assertion_chain_root_id` |

Negation is captured separately by `is_negated_assertion`; it should not change the coarse `verification_intent` category.

## Residual AST coverage limits

- Chai property chains (`.to.equal`, `.to.be.visible`, `.to.include`)
- Nightwatch `browser.assert` / legacy expect wrappers
- WebDriverIO `$('…').toBeDisplayed()` and similar element matchers
- Assertions inside exotic grouped wrappers not walked by ancestor detection
- Partial matcher coverage for TestCafe / legacy frameworks

See `rq5_assertion_chain_taxonomy.json` for machine-readable notes.
