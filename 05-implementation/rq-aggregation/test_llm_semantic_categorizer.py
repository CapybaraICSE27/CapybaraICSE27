import tempfile
import threading
import time
import unittest
import os
import json
import socket
import urllib.error
from unittest import mock
from pathlib import Path

from llm_semantic_cache import LlmSemanticCache, build_input_hash
from llm_semantic_categorizer import (
    ALLOWED_LABELS,
    LLM_SEMANTIC_PROMPT_VERSION,
    LlmSemanticCorrector,
    LlmSemanticDecision,
    OpenAiResponsesSemanticClient,
    apply_deterministic_semantic_columns,
    apply_llm_semantic_decision,
    apply_rq2_indeterminate_adjudication_decision,
    build_llm_instruction_block,
    build_llm_semantic_request,
    build_llm_semantic_batch_request,
    load_openai_api_key_from_env_file,
    should_trigger_rq2_indeterminate_adjudication,
    should_trigger_llm_correction,
)


class TestLlmSemanticCache(unittest.TestCase):
    def test_cache_round_trips_by_model_prompt_and_input_hash(self):
        with tempfile.TemporaryDirectory() as td:
            cache = LlmSemanticCache(Path(td))
            input_hash = build_input_hash({"rq": "rq2", "raw_code": "cy.focused().type(mockTicket.summary)"})
            payload = {"label": "domain_plausible_input", "confidence": "high", "abstain": False}

            self.assertIsNone(cache.get(model="gpt-5.4-mini", prompt_version=LLM_SEMANTIC_PROMPT_VERSION, input_hash=input_hash))
            cache.put(model="gpt-5.4-mini", prompt_version=LLM_SEMANTIC_PROMPT_VERSION, input_hash=input_hash, payload=payload)

            self.assertEqual(
                cache.get(model="gpt-5.4-mini", prompt_version=LLM_SEMANTIC_PROMPT_VERSION, input_hash=input_hash),
                payload,
            )


class TestLlmSemanticCategorizer(unittest.TestCase):
    def test_prompt_version_is_v13_after_determinate_label_cleanup(self):
        self.assertEqual(LLM_SEMANTIC_PROMPT_VERSION, "rq-semantic-v13-determinate-labels")

    def test_abandoned_categories_are_not_llm_choices(self):
        self.assertNotIn("technical_or_control_input", ALLOWED_LABELS["rq2"])
        self.assertNotIn("unspecified", ALLOWED_LABELS["rq5c"])
        for label in (
            "page_object_centric_unresolved",
            "bdd_step_centric",
            "unresolved_thin_wrapper",
            "mixed_or_unclear",
        ):
            self.assertNotIn(label, ALLOWED_LABELS["rq3_workflow"])

        self.assertNotIn(
            "technical_or_control_input",
            build_llm_instruction_block("rq2")["allowed_labels"],
        )
        self.assertNotIn("unspecified", build_llm_instruction_block("rq5c")["allowed_labels"])

    def test_abandoned_deterministic_labels_are_normalized_before_final_output(self):
        rq2 = apply_deterministic_semantic_columns(
            "rq2",
            {"input_plausibility": "technical_or_control_input"},
        )
        self.assertEqual(rq2["input_plausibility_final"], "not_observable")
        self.assertEqual(rq2["input_plausibility_paper_label"], "")

        rq3 = apply_deterministic_semantic_columns(
            "rq3_workflow",
            {"workflow_archetype": "page_object_centric_unresolved"},
        )
        self.assertEqual(rq3["workflow_archetype_final"], "")

        rq3_thin_wrapper = apply_deterministic_semantic_columns(
            "rq3_workflow",
            {"workflow_archetype": "unresolved_thin_wrapper"},
        )
        self.assertEqual(rq3_thin_wrapper["workflow_archetype_final"], "")

        rq5 = apply_deterministic_semantic_columns(
            "rq5c",
            {"verification_intent": "unspecified"},
        )
        self.assertEqual(rq5["verification_intent_final"], "")

    def test_env_local_loader_reads_key_without_overriding_process_env(self):
        old = os.environ.pop("OPENAI_API_KEY", None)
        try:
            with tempfile.TemporaryDirectory() as td:
                env_path = Path(td) / ".env.local"
                env_path.write_text("OPENAI_API_KEY=sk-test-local\nOTHER=value\n", encoding="utf-8")
                self.assertEqual(load_openai_api_key_from_env_file(env_path), "sk-test-local")
                self.assertEqual(os.environ["OPENAI_API_KEY"], "sk-test-local")

                os.environ["OPENAI_API_KEY"] = "sk-test-process"
                self.assertEqual(load_openai_api_key_from_env_file(env_path), "sk-test-process")
                self.assertEqual(os.environ["OPENAI_API_KEY"], "sk-test-process")
        finally:
            if old is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = old

    def test_trigger_uses_risky_evidence_patterns_not_low_confidence_only(self):
        self.assertEqual(
            should_trigger_llm_correction(
                "rq2",
                {
                    "input_plausibility": "technical_or_control_input",
                    "input_plausibility_confidence": "high",
                    "input_target_role_ast": "unknown",
                    "input_source_class": "generated_input",
                    "input_value_expression_kind_ast": "member_expression",
                    "value_summary": "mockTicket.summary",
                },
            ),
            "rq2_unknown_target_opaque_or_member_value",
        )
        self.assertEqual(
            should_trigger_llm_correction(
                "rq2",
                {
                    "input_plausibility": "domain_plausible_input",
                    "input_plausibility_confidence": "high",
                    "input_target_role_ast": "unknown",
                    "input_source_class": "literal_input",
                    "input_value_expression_kind_ast": "string_literal",
                    "value_summary": "test Mandatory",
                    "raw_code": 'cy.get(jsonform.jsformInput).type("test Mandatory")',
                },
            ),
            "rq2_weak_literal_unknown_target_not_observable_candidate",
        )
        self.assertEqual(
            should_trigger_llm_correction(
                "rq2",
                {
                    "input_plausibility": "domain_plausible_input",
                    "input_plausibility_confidence": "high",
                    "input_source_class": "file_upload_input",
                    "input_upload_consumer_ast": "setInputFiles",
                    "value_summary": "path.resolve(dirname, './duck.glb')",
                    "raw_code": "page.setInputFiles('input[type=\"file\"]', path.resolve(dirname, './duck.glb'))",
                },
            ),
            "rq2_path_or_file_construction_edge_conflict",
        )
        self.assertEqual(
            should_trigger_llm_correction(
                "rq2",
                {
                    "input_plausibility": "domain_plausible_input",
                    "input_plausibility_confidence": "medium",
                    "input_target_role_ast": "text_field",
                    "input_source_class": "generated_input",
                    "value_summary": "faker.string.alphanumeric(10)",
                    "field_context": "search activity definition",
                    "raw_code": "page.getByPlaceholder(/search/i).fill(faker.string.alphanumeric(10))",
                },
            ),
            "rq2_generated_value_visible_domain_context",
        )

    def test_visible_text_boundary_does_not_trigger_plain_domain_rows(self):
        self.assertEqual(
            should_trigger_llm_correction(
                "rq2",
                {
                    "input_plausibility": "domain_plausible_input",
                    "input_plausibility_confidence": "high",
                    "input_target_role_ast": "unknown",
                    "input_source_class": "literal_input",
                    "input_value_expression_kind_ast": "string_literal",
                    "value_summary": "Alice",
                    "raw_code": "cy.get('@input').type('Alice')",
                },
            ),
            "",
        )

    def test_pure_cypress_control_token_does_not_trigger_llm(self):
        self.assertEqual(
            should_trigger_llm_correction(
                "rq2",
                {
                    "input_plausibility": "technical_or_control_input",
                    "input_plausibility_confidence": "high",
                    "input_target_role_ast": "unknown",
                    "input_source_class": "literal_input",
                    "input_value_expression_kind_ast": "string_literal",
                    "field_context": "body",
                    "value_summary": "{esc}",
                    "raw_code": "cy.get('body').type('{esc}')",
                },
            ),
            "",
        )

    def test_visible_text_boundary_triggers_risky_member_domain_context(self):
        self.assertEqual(
            should_trigger_llm_correction(
                "rq2",
                {
                    "input_plausibility": "not_observable",
                    "input_plausibility_confidence": "medium",
                    "input_target_role_ast": "text_field",
                    "input_source_class": "variable_input",
                    "input_value_expression_kind_ast": "member_expression",
                    "value_summary": "ldapUser.username",
                    "field_context": "Search users",
                    "raw_code": "cy.findByPlaceholderText('Search users').type(ldapUser.username)",
                },
            ),
            "rq2_visible_text_input_semantic_boundary",
        )
        self.assertEqual(
            should_trigger_llm_correction(
                "rq2",
                {
                    "input_plausibility": "technical_or_control_input",
                    "input_plausibility_confidence": "high",
                    "raw_code": "cy.get('#after-button').realClick().realPress(['Shift', 'Tab'])",
                    "input_channel": "keyboard_entry",
                },
            ),
            "rq2_keyboard_control_observability_boundary",
        )
        self.assertEqual(
            should_trigger_llm_correction(
                "rq5c",
                {
                    "verification_intent": "api_or_data_contract",
                    "verification_intent_confidence": "high",
                    "verification_intent_evidence_basis": "lexical_fallback",
                },
            ),
            "rq5c_lexical_or_missing_subject_role",
        )
        self.assertEqual(
            should_trigger_llm_correction(
                "rq5c",
                {
                    "verification_intent": "content_correctness",
                    "verification_intent_confidence": "high",
                    "verification_intent_evidence_basis": "ast_assertion_matcher",
                    "assertion_subject_semantic_role_ast": "text_payload",
                    "raw_code": "await expect(locator).toHaveAccessibleName('Save')",
                    "matcher": "toHaveAccessibleName",
                },
            ),
            "rq5c_accessibility_matcher_semantic_conflict",
        )
        self.assertEqual(
            should_trigger_llm_correction(
                "rq5c",
                {
                    "verification_intent": "api_or_data_contract",
                    "verification_intent_confidence": "high",
                    "verification_intent_evidence_basis": "ast_assertion_subject_semantic_role",
                    "assertion_subject_semantic_role_ast": "api_object_contract",
                    "raw_code": "cy.url().should('contain', '/dashboard')",
                },
            ),
            "rq5c_navigation_subject_semantic_conflict",
        )
        self.assertEqual(
            should_trigger_llm_correction(
                "rq5c",
                {
                    "verification_intent": "style_or_visual_state",
                    "verification_intent_confidence": "high",
                    "verification_intent_evidence_basis": "ast_assertion_subject_semantic_role",
                    "assertion_subject_semantic_role_ast": "style_property",
                    "raw_code": "cy.get('#demo-content input').should('be.visible')",
                    "matcher": "be.visible",
                },
            ),
            "rq5c_presence_matcher_semantic_conflict",
        )
        self.assertEqual(
            should_trigger_llm_correction(
                "rq5c",
                {
                    "verification_intent": "element_presence",
                    "assertion_subject_semantic_role_ast": "element_presence",
                    "raw_code": "t.expect(t.ctx.usa.getNodes().count).eql(1)",
                    "matcher": "eql",
                },
            ),
            "rq5c_collection_count_semantic_conflict",
        )
        self.assertEqual(
            should_trigger_llm_correction(
                "rq3_workflow",
                {
                    "workflow_archetype": "page_object_centric",
                    "dominant_workflow_source": "helper_mediated",
                    "workflow_evidence_score_json": '{"helper_mediated": 8, "page_object_centric": 2}',
                },
            ),
            "rq3_workflow_dominant_evidence_label_conflict",
        )
        self.assertEqual(
            should_trigger_llm_correction(
                "rq3_workflow",
                {
                    "workflow_archetype": "inline_direct",
                    "dominant_workflow_source": "bdd_step",
                    "workflow_evidence_score_json": '{"bdd_step": 8, "test_body_ui": 1}',
                },
            ),
            "rq3_workflow_dominant_evidence_label_conflict",
        )
        self.assertEqual(
            should_trigger_llm_correction(
                "rq3_workflow",
                {
                    "workflow_archetype": "page_object_centric",
                    "dominant_workflow_source": "helper_ui",
                    "workflow_evidence_score_json": '{"helper_ui": 10, "page_object_ui": 2}',
                },
            ),
            "rq3_workflow_dominant_evidence_label_conflict",
        )
        self.assertEqual(
            should_trigger_llm_correction(
                "rq3_workflow",
                {
                    "workflow_archetype": "page_object_centric",
                    "workflow_evidence_score_json": '{"helper_ui": 10, "page_object_ui": 2}',
                },
            ),
            "rq3_workflow_dominant_evidence_label_conflict",
        )
        self.assertEqual(
            should_trigger_llm_correction(
                "rq3_workflow",
                {
                    "workflow_archetype": "page_object_centric",
                    "dominant_workflow_source": "helper_calls",
                    "workflow_evidence_score_json": '{"helper_calls": 11, "helper_ui": 4, "test_body_ui": 3}',
                    "abstraction_kind_counts_json": '{"domain_helper": 15}',
                },
            ),
            "rq3_workflow_dominant_evidence_label_conflict",
        )

    def test_manual_audit_columns_do_not_drive_production_llm_triggers(self):
        self.assertEqual(
            should_trigger_llm_correction(
                "rq3_workflow",
                {
                    "workflow_archetype": "inline_direct",
                    "manual_workflow_archetype_should_be": "helper_mediated",
                },
            ),
            "",
        )

    def test_request_contains_structured_fields_without_secrets_or_static_taxonomy(self):
        request = build_llm_semantic_request(
            rq="rq5c",
            row={
                "raw_code": "expect(await pluginCheckbox.isDisabled()).toEqual(true)",
                "verification_intent": "api_or_data_contract",
                "verification_intent_evidence_basis": "lexical_fallback",
                "verification_intent_deterministic": "api_or_data_contract",
                "verification_intent_llm": "api_or_data_contract",
                "verification_intent_final": "api_or_data_contract",
                "verification_intent_final_basis": "deterministic",
                "verification_intent_llm_trigger_reason": "rq5c_lexical_or_missing_subject_role",
                "manual_notes": "Should be interactive_state",
                "manual_intent_should_be": "interactive_state",
                "review_reason": "sampled because incorrect",
            },
            trigger_reason="rq5c_lexical_or_missing_subject_role",
        )
        self.assertEqual(request["rq"], "rq5c")
        self.assertIn("interactive_state", request["allowed_labels"])
        self.assertIn("structured_fields", request)
        self.assertEqual(request["prompt_version"], LLM_SEMANTIC_PROMPT_VERSION)
        self.assertNotIn("few_shot_examples", request)
        self.assertNotIn("classification_guidelines", request)
        self.assertNotIn("taxonomy_definitions", request)
        self.assertNotIn("OPENAI_API_KEY", str(request))
        self.assertNotIn("private-token-sentinel", str(request))
        self.assertNotIn("manual_notes", request["structured_fields"])
        self.assertNotIn("manual_intent_should_be", request["structured_fields"])
        self.assertNotIn("review_reason", request["structured_fields"])
        self.assertNotIn("verification_intent_deterministic", request["structured_fields"])
        self.assertNotIn("verification_intent_llm", request["structured_fields"])
        self.assertNotIn("verification_intent_final", request["structured_fields"])
        self.assertNotIn("verification_intent_final_basis", request["structured_fields"])
        self.assertNotIn("verification_intent_llm_trigger_reason", request["structured_fields"])
        self.assertNotIn("Should be interactive_state", str(request))

    def test_instruction_block_holds_stable_taxonomy_and_few_shots_once(self):
        block = build_llm_instruction_block("rq5c")
        self.assertEqual(block["prompt_version"], LLM_SEMANTIC_PROMPT_VERSION)
        self.assertIn("taxonomy_definitions", block)
        self.assertIn("classification_guidelines", block)
        self.assertIn("few_shot_examples", block)
        self.assertIn("expect(status).toBe('healthy')", json.dumps(block))
        self.assertIn("expect(response.status).toBe(200)", json.dumps(block))

    def test_medium_or_high_non_abstain_decision_promotes_to_final_label(self):
        row = {
            "input_plausibility": "technical_or_control_input",
            "input_plausibility_confidence": "high",
        }
        decision = LlmSemanticDecision(
            label="domain_plausible_input",
            confidence="medium",
            abstain=False,
            evidence_fields=["value_summary"],
            short_rationale="member path is a realistic domain value",
            codebook_step="domain_target_context",
        )
        out = apply_llm_semantic_decision("rq2", row, decision, "rq2_unknown_target_opaque_or_member_value")
        self.assertEqual(out["input_plausibility_deterministic"], "not_observable")
        self.assertEqual(out["input_plausibility_llm"], "domain_plausible_input")
        self.assertEqual(out["input_plausibility_final"], "domain_plausible_input")
        self.assertEqual(out["input_plausibility_final_basis"], "llm_semantic_correction")
        self.assertEqual(out["input_plausibility_llm_codebook_step"], "domain_target_context")

    def test_low_confidence_or_abstain_keeps_deterministic_label(self):
        row = {"verification_intent": "api_or_data_contract"}
        decision = LlmSemanticDecision(
            label="interactive_state",
            confidence="low",
            abstain=False,
            evidence_fields=[],
            short_rationale="not enough evidence",
        )
        out = apply_llm_semantic_decision("rq5c", row, decision, "rq5c_lexical_or_missing_subject_role")
        self.assertEqual(out["verification_intent_final"], "api_or_data_contract")
        self.assertEqual(out["verification_intent_final_basis"], "deterministic")

    def test_rq2_guard_routes_pure_realpress_to_technical_control(self):
        row = {
            "input_plausibility": "technical_or_control_input",
            "raw_code": "cy.realPress(['Alt', 'ArrowDown'])",
        }
        decision = LlmSemanticDecision(
            label="not_observable",
            confidence="high",
            abstain=False,
            evidence_fields=["raw_code"],
            short_rationale="old codebook said keyboard shortcut was unobservable",
        )
        out = apply_llm_semantic_decision("rq2", row, decision, "rq2_keyboard_control_observability_boundary")
        self.assertEqual(out["input_plausibility_llm"], "")
        self.assertEqual(out["input_plausibility_final"], "not_observable")
        self.assertEqual(out["input_plausibility_final_basis"], "deterministic_llm_guard")

    def test_rq2_guard_routes_mixed_control_token_typing_to_technical(self):
        row = {
            "input_plausibility": "unclear",
            "raw_code": "cy.get('@input').type('42').type('{leftArrow}').type('.')",
        }
        decision = LlmSemanticDecision(
            label="validation_or_edge_case_input",
            confidence="medium",
            abstain=False,
            evidence_fields=["raw_code"],
            short_rationale="edge-looking edit",
        )
        out = apply_llm_semantic_decision("rq2", row, decision, "rq2_keyboard_token_chain_ambiguity")
        self.assertEqual(out["input_plausibility_final"], "not_observable")
        self.assertEqual(out["input_plausibility_final_basis"], "deterministic_llm_guard")

    def test_rq2_tail_guards_cover_keyboard_config_upload_and_tax_id(self):
        cases = [
            (
                {"input_plausibility": "indeterminate_or_insufficient_evidence", "raw_code": "page.keyboard.press('Control+Space')"},
                "not_observable",
            ),
            (
                {
                    "input_plausibility": "validation_or_edge_case_input",
                    "raw_code": "ui.autocomplete.findByLabel('Object Storage Endpoint').type(updatedDomain)",
                    "field_context": "Object Storage Endpoint",
                },
                "not_observable",
            ),
            (
                {
                    "input_plausibility": "validation_or_edge_case_input",
                    "raw_code": "setInputFiles([path.resolve(dirname, './image.png'), path.resolve(dirname, './2mb.jpg'), // exceeds 2MB\n path.resolve(dirname, './small.png')])",
                    "input_source_class": "file_upload_input",
                },
                "domain_plausible_input",
            ),
            (
                {
                    "input_plausibility": "indeterminate_or_insufficient_evidence",
                    "raw_code": "cy.focused().type(newAccountData['tax_id'])",
                    "value_summary": "newAccountData['tax_id']",
                },
                "domain_plausible_input",
            ),
        ]
        for row, expected in cases:
            with self.subTest(row=row):
                decision = LlmSemanticDecision(
                    label="validation_or_edge_case_input",
                    confidence="high",
                    abstain=False,
                    evidence_fields=["raw_code"],
                    short_rationale="model chose a conflicting label",
                )
                out = apply_llm_semantic_decision("rq2", row, decision, "rq2_tail_false_family")
                self.assertEqual(out["input_plausibility_final"], expected)
                self.assertEqual(out["input_plausibility_final_basis"], "deterministic_llm_guard")

    def test_rq2_guard_does_not_treat_options_object_as_keyboard_token(self):
        row = {
            "input_plausibility": "not_observable",
            "raw_code": "cy.get(profileForm.displayName).type(user.displayName, { parseSpecialCharSequences: false })",
        }
        decision = LlmSemanticDecision(
            label="domain_plausible_input",
            confidence="high",
            abstain=False,
            evidence_fields=["raw_code"],
            short_rationale="visible pagination field",
        )
        out = apply_llm_semantic_decision("rq2", row, decision, "rq2_keyboard_token_chain_ambiguity")
        self.assertEqual(out["input_plausibility_final"], "domain_plausible_input")
        self.assertEqual(out["input_plausibility_final_basis"], "llm_semantic_correction")

    def test_355am_rq5c_status_and_event_counter_llm_boundaries(self):
        self.assertEqual(
            should_trigger_llm_correction(
                "rq5c",
                {
                    "verification_intent": "value_or_attribute_correctness",
                    "verification_intent_evidence_basis": "lexical_scalar_status_context",
                    "raw_code": "expect(status).to.equal(201)",
                    "assertion_subject_text_ast": "expect(status).to.equal(201)",
                    "assertion_subject_semantic_role_ast": "scalar_property",
                    "assertion_matcher": "equal",
                },
            ),
            "rq5c_lexical_or_missing_subject_role",
        )

        row = {
            "verification_intent": "value_or_attribute_correctness",
            "raw_code": "expect(clickCount).toBe(1)",
            "assertion_subject_text_ast": "clickCount",
            "assertion_matcher": "toBe",
        }
        decision = LlmSemanticDecision(
            label="api_or_data_contract",
            confidence="high",
            abstain=False,
            evidence_fields=["raw_code"],
            short_rationale="model chose a generic object label",
        )
        out = apply_llm_semantic_decision("rq5c", row, decision, "rq5c_lexical_or_missing_subject_role")
        self.assertEqual(out["verification_intent_final"], "interactive_state")
        self.assertEqual(out["verification_intent_final_basis"], "deterministic_llm_guard")

    def test_rq2_guard_keeps_empty_fill_as_validation_edge(self):
        row = {
            "input_plausibility": "validation_or_edge_case_input",
            "raw_code": "searchInput.fill('')",
        }
        decision = LlmSemanticDecision(
            label="validation_or_edge_case_input",
            confidence="high",
            abstain=False,
            evidence_fields=["raw_code"],
            short_rationale="empty string",
        )
        out = apply_llm_semantic_decision("rq2", row, decision, "rq2_weak_literal_unknown_target_not_observable_candidate")
        self.assertEqual(out["input_plausibility_final"], "validation_or_edge_case_input")
        self.assertEqual(out["input_plausibility_final_basis"], "llm_semantic_correction")

    def test_rq2_guard_routes_ip_and_cvc_member_values_to_domain(self):
        for raw_code in (
            "cy.focused().type(mockSubnets[0].ipv4!)",
            "cy.get('[name=\"cvc\"]').clear().type(billing.invalidvisa.cvc)",
        ):
            with self.subTest(raw_code=raw_code):
                row = {
                    "input_plausibility": "not_observable",
                    "raw_code": raw_code,
                }
                decision = LlmSemanticDecision(
                    label="not_observable",
                    confidence="high",
                    abstain=False,
                    evidence_fields=["raw_code"],
                    short_rationale="opaque",
                )
                out = apply_llm_semantic_decision("rq2", row, decision, "rq2_visible_text_input_semantic_boundary")
                self.assertEqual(out["input_plausibility_final"], "domain_plausible_input")
                self.assertEqual(out["input_plausibility_final_basis"], "deterministic_llm_guard")

    def test_rq2_guard_keeps_ordinary_file_path_upload_domain_plausible(self):
        row = {
            "input_plausibility": "domain_plausible_input",
            "raw_code": "page.setInputFiles('input[type=\"file\"]', path.join(dirname, 'test-image.jpg'))",
        }
        decision = LlmSemanticDecision(
            label="domain_plausible_input",
            confidence="high",
            abstain=False,
            evidence_fields=["raw_code"],
            short_rationale="plausible asset",
        )
        out = apply_llm_semantic_decision("rq2", row, decision, "rq2_path_or_file_construction_edge_conflict")
        self.assertEqual(out["input_plausibility_final"], "domain_plausible_input")
        self.assertEqual(out["input_plausibility_final_basis"], "llm_semantic_correction")

    def test_rq2_guard_routes_explicit_upload_limit_to_validation(self):
        row = {
            "input_plausibility": "domain_plausible_input",
            "raw_code": "fileInput.setInputFiles({ name: 'exceed-limit-test.csv', buffer: Buffer.from(csvFile) })",
        }
        decision = LlmSemanticDecision(
            label="domain_plausible_input",
            confidence="high",
            abstain=False,
            evidence_fields=["raw_code"],
            short_rationale="upload asset",
        )
        out = apply_llm_semantic_decision("rq2", row, decision, "rq2_path_or_file_construction_edge_conflict")
        self.assertEqual(out["input_plausibility_final"], "validation_or_edge_case_input")
        self.assertEqual(out["input_plausibility_final_basis"], "deterministic_llm_guard")

    def test_rq5_tail_guards_preserve_structured_deterministic_labels(self):
        cases = [
            (
                {
                    "verification_intent": "accessibility_compliance",
                    "raw_code": "expect(result.totalFocusableElements).toBeLessThanOrEqual(maxFocusableElements)",
                    "assertion_subject_path_json": '["result", "totalFocusableElements"]',
                    "assertion_subject_text_ast": "result.totalFocusableElements",
                },
                "accessibility_compliance",
            ),
            (
                {
                    "verification_intent": "api_or_data_contract",
                    "raw_code": "expect(requestPayload['public']).to.equal(null)",
                    "assertion_subject_path_json": '["requestPayload", "public"]',
                    "assertion_subject_text_ast": "requestPayload['public']",
                },
                "api_or_data_contract",
            ),
            (
                {
                    "verification_intent": "network_contract",
                    "raw_code": "expect(matchedRequests.length).toBeLessThanOrEqual(allowedNumberOfRequests)",
                    "assertion_subject_path_json": '["matchedRequests", "length"]',
                    "assertion_subject_text_ast": "matchedRequests.length",
                },
                "network_contract",
            ),
        ]
        for row, expected in cases:
            with self.subTest(row=row):
                decision = LlmSemanticDecision(
                    label="collection_size",
                    confidence="high",
                    abstain=False,
                    evidence_fields=["raw_code"],
                    short_rationale="model chose a conflicting label",
                )
                out = apply_llm_semantic_decision("rq5c", row, decision, "rq5c_tail_false_family")
                self.assertEqual(out["verification_intent_final"], expected)
                self.assertEqual(out["verification_intent_final_basis"], "deterministic_llm_guard")

    def test_rq2_guard_preserves_meaningful_domain_targets_from_llm_demotions(self):
        cases = [
            {
                "input_plausibility": "domain_plausible_input",
                "raw_code": "page.locator('#field-localizedTitle').fill('Test title in english')",
                "value_summary": "Test title in english",
                "input_channel": "ui_text_entry",
                "value_visibility": "visible",
                "input_target_role_ast": "domain_text_field",
                "field_context": "localized Title",
            },
            {
                "input_plausibility": "unclear",
                "raw_code": 'page.selectOption("select", "Cuba")',
                "value_summary": "Cuba",
                "input_channel": "ui_selection",
                "value_visibility": "visible",
                "input_target_role_ast": "domain_selection_field",
                "field_context": "select",
            },
            {
                "input_plausibility": "unclear",
                "raw_code": "cy.focused().type(`Payments`)",
                "value_summary": "Payments",
                "input_channel": "ui_text_entry",
                "value_visibility": "visible",
                "input_target_role_ast": "unknown",
            },
            {
                "input_plausibility": "unclear",
                "raw_code": "inputLocator.fill(filter)",
                "value_summary": "filter",
                "input_source_class": "variable_input",
                "input_channel": "ui_text_entry",
                "value_visibility": "opaque",
                "input_target_role_ast": "unknown",
                "input_value_expression_kind_ast": "identifier",
            },
        ]
        decision = LlmSemanticDecision(
            label="placeholder_or_dummy_input",
            confidence="high",
            abstain=False,
            evidence_fields=["raw_code"],
            short_rationale="LLM thought the value was filler.",
        )
        for row in cases:
            with self.subTest(raw=row["raw_code"]):
                out = apply_llm_semantic_decision("rq2", row, decision, "rq2_visible_literal_unknown_target_boundary")
                self.assertEqual(out["input_plausibility_final"], "domain_plausible_input")
                self.assertEqual(out["input_plausibility_final_basis"], "deterministic_llm_guard")

    def test_rq2_guard_uses_revised_keyboard_and_config_codebook(self):
        keyboard_domain = {
            "input_plausibility": "unclear",
            "raw_code": "page.keyboard.type('2345')",
            "value_summary": "2345",
            "input_channel": "ui_text_entry",
            "value_visibility": "visible",
            "input_target_role_ast": "unknown",
        }
        keyboard_dummy = {
            "input_plausibility": "unclear",
            "raw_code": 'page.keyboard.type("val2")',
            "value_summary": "val2",
            "input_channel": "ui_text_entry",
            "value_visibility": "visible",
            "input_target_role_ast": "unknown",
        }
        port_config = {
            "input_plausibility": "validation_or_edge_case_input",
            "raw_code": "cy.get('[id=port-1]').type('8080')",
            "value_summary": "8080",
            "input_channel": "ui_text_entry",
            "field_context": "[id=port 1]",
            "input_target_context_ast": "[id=port-1]",
        }
        weak_dummy_fill = {
            "input_plausibility": "unclear",
            "raw_code": 'q1Input.fill("abc")',
            "value_summary": "abc",
            "input_channel": "ui_text_entry",
            "value_visibility": "visible",
            "input_target_role_ast": "unknown",
        }
        numeric_max_unknown = {
            "input_plausibility": "validation_or_edge_case_input",
            "raw_code": 'symbolMaxInput.fill("30")',
            "value_summary": "30",
            "input_channel": "ui_text_entry",
            "value_visibility": "visible",
            "input_target_role_ast": "unknown",
        }
        meaningful_value_field = {
            "input_plausibility": "unclear",
            "raw_code": "secondValueField.fill('Test 2')",
            "value_summary": "Test 2",
            "input_channel": "ui_text_entry",
            "value_visibility": "visible",
            "input_target_role_ast": "unknown",
        }
        bad_decision = LlmSemanticDecision(
            label="validation_or_edge_case_input",
            confidence="high",
            abstain=False,
            evidence_fields=["raw_code"],
            short_rationale="LLM picked edge.",
        )
        out_domain = apply_llm_semantic_decision("rq2", keyboard_domain, bad_decision, "rq2_keyboard_control_observability_boundary")
        self.assertEqual(out_domain["input_plausibility_final"], "domain_plausible_input")
        self.assertEqual(out_domain["input_plausibility_final_basis"], "deterministic_llm_guard")

        out_dummy = apply_llm_semantic_decision("rq2", keyboard_dummy, bad_decision, "rq2_keyboard_control_observability_boundary")
        self.assertEqual(out_dummy["input_plausibility_final"], "placeholder_or_dummy_input")
        self.assertEqual(out_dummy["input_plausibility_final_basis"], "deterministic_llm_guard")

        out_port = apply_llm_semantic_decision("rq2", port_config, bad_decision, "rq2_validation_config_or_domain_boundary_adjudication")
        self.assertEqual(out_port["input_plausibility_final"], "not_observable")
        self.assertEqual(out_port["input_plausibility_final_basis"], "deterministic_llm_guard")

        domain_decision = LlmSemanticDecision(
            label="domain_plausible_input",
            confidence="high",
            abstain=False,
            evidence_fields=["raw_code"],
            short_rationale="LLM picked domain.",
        )
        out_abc = apply_llm_semantic_decision("rq2", weak_dummy_fill, domain_decision, "rq2_visible_literal_unknown_target_boundary")
        self.assertEqual(out_abc["input_plausibility_final"], "placeholder_or_dummy_input")
        self.assertEqual(out_abc["input_plausibility_final_basis"], "deterministic_llm_guard")

        out_max = apply_llm_semantic_decision("rq2", numeric_max_unknown, bad_decision, "rq2_visible_literal_unknown_target_boundary")
        self.assertEqual(out_max["input_plausibility_final"], "not_observable")
        self.assertEqual(out_max["input_plausibility_paper_label"], "")
        self.assertEqual(out_max["input_plausibility_final_basis"], "deterministic_llm_guard")

        placeholder_decision = LlmSemanticDecision(
            label="placeholder_or_dummy_input",
            confidence="high",
            abstain=False,
            evidence_fields=["raw_code"],
            short_rationale="LLM picked filler.",
        )
        out_value_field = apply_llm_semantic_decision("rq2", meaningful_value_field, placeholder_decision, "rq2_visible_literal_unknown_target_boundary")
        self.assertEqual(out_value_field["input_plausibility_final"], "domain_plausible_input")
        self.assertEqual(out_value_field["input_plausibility_final_basis"], "deterministic_llm_guard")

    def test_rq2_949pm_guard_vetoes_endpoint_config_domain_promotion(self):
        decision = LlmSemanticDecision(
            label="domain_plausible_input",
            confidence="high",
            abstain=False,
            evidence_fields=["raw_code", "field_context"],
            short_rationale="LLM treated visible text field as user data.",
        )
        cases = [
            {
                "input_plausibility": "domain_plausible_input",
                "raw_code": 'baseUrlInput.fill("https://jsonplaceholder.typicode.com/")',
                "value_summary": "https://jsonplaceholder.typicode.com/",
                "field_context": "baseUrlInput",
                "input_target_context_ast": "baseUrlInput",
                "input_channel": "ui_text_entry",
            },
            {
                "input_plausibility": "domain_plausible_input",
                "raw_code": "cy.get(apiwidget.resourceUrl).type(datasource)",
                "value_summary": "datasource",
                "field_context": "apiwidget.resourceUrl",
                "input_target_context_ast": "apiwidget.resourceUrl",
                "input_channel": "ui_text_entry",
            },
            {
                "input_plausibility": "domain_plausible_input",
                "raw_code": "page.getByPlaceholder(/Select Route/i).fill(route)",
                "value_summary": "route",
                "field_context": "/Select Route/i",
                "input_target_context_ast": "Select Route",
                "input_channel": "ui_text_entry",
            },
        ]
        for row in cases:
            with self.subTest(raw=row["raw_code"]):
                out = apply_llm_semantic_decision("rq2", row, decision, "rq2_visible_text_input_semantic_boundary")
                self.assertEqual(out["input_plausibility_final"], "not_observable")
                self.assertEqual(out["input_plausibility_paper_label"], "")
                self.assertEqual(out["input_plausibility_final_basis"], "deterministic_llm_guard")

    def test_rq2_949pm_indeterminate_helper_targets_promote_to_domain(self):
        decision = LlmSemanticDecision(
            label="placeholder_or_dummy_input",
            confidence="high",
            abstain=False,
            evidence_fields=["raw_code"],
            short_rationale="LLM overread one-letter text as filler.",
        )
        cases = [
            {
                "input_plausibility": "unclear",
                "input_plausibility_paper_label": "indeterminate_or_insufficient_evidence",
                "raw_code": "agHelper.GetNClick(table._filterInputValue, 0).clear().type('i')",
                "value_summary": "i",
                "field_context": "table._filterInputValue",
                "input_channel": "ui_text_entry",
                "value_visibility": "visible",
            },
            {
                "input_plausibility": "unclear",
                "input_plausibility_paper_label": "indeterminate_or_insufficient_evidence",
                "raw_code": "cy.get(publish.inputValue).type('bind')",
                "value_summary": "bind",
                "field_context": "publish.inputValue",
                "input_channel": "ui_text_entry",
                "value_visibility": "visible",
            },
        ]
        for row in cases:
            with self.subTest(raw=row["raw_code"]):
                out = apply_rq2_indeterminate_adjudication_decision(
                    row,
                    decision,
                    "rq2_indeterminate_visible_or_contextual_value_adjudication",
                )
                self.assertEqual(out["input_plausibility_final"], "domain_plausible_input")
                self.assertEqual(out["input_plausibility_final_basis"], "deterministic_llm_guard")

    def test_rq3_guard_uses_dominant_workflow_source(self):
        row = {
            "workflow_archetype": "layered",
            "dominant_workflow_source": "cypress_command_ui",
            "workflow_evidence_score_json": '{"cypress_command_ui": 10, "test_body_ui": 2}',
        }
        decision = LlmSemanticDecision(
            label="layered",
            confidence="high",
            abstain=False,
            evidence_fields=["workflow_evidence_score_json"],
            short_rationale="several layers",
        )
        out = apply_llm_semantic_decision(
            "rq3_workflow",
            row,
            decision,
            "rq3_workflow_dominant_evidence_label_conflict",
        )
        self.assertEqual(out["workflow_archetype_final"], "framework_extension_centric")
        self.assertEqual(out["workflow_archetype_final_basis"], "deterministic_llm_guard")

    def test_rq5_guard_routes_presence_conflict_to_element_presence(self):
        row = {
            "verification_intent": "style_or_visual_state",
            "raw_code": "cy.get('#demo-content input').should('be.visible')",
        }
        decision = LlmSemanticDecision(
            label="style_or_visual_state",
            confidence="high",
            abstain=False,
            evidence_fields=["raw_code"],
            short_rationale="style context",
        )
        out = apply_llm_semantic_decision("rq5c", row, decision, "rq5c_presence_matcher_semantic_conflict")
        self.assertEqual(out["verification_intent_final"], "element_presence")
        self.assertEqual(out["verification_intent_final_basis"], "deterministic_llm_guard")

    def test_rq5_guard_does_not_let_presence_token_override_current_css_matcher(self):
        row = {
            "verification_intent": "element_presence",
            "raw_code": "cy.get('[class*=visible-overflow-button]').should('be.visible').should('have.css', 'justify-content', 'end')",
            "assertion_semantic_matcher_ast": "have.css",
        }
        decision = LlmSemanticDecision(
            label="element_presence",
            confidence="high",
            abstain=False,
            evidence_fields=["assertion_semantic_matcher_ast"],
            short_rationale="earlier matcher was visible",
        )
        out = apply_llm_semantic_decision("rq5c", row, decision, "rq5c_presence_matcher_semantic_conflict")
        self.assertEqual(out["verification_intent_final"], "style_or_visual_state")
        self.assertEqual(out["verification_intent_final_basis"], "deterministic_llm_guard")

    def test_rq5_guard_routes_stub_call_count_to_interactive_state(self):
        row = {
            "verification_intent": "collection_size",
            "raw_code": "expect(stub).to.have.been.callCount(4)",
        }
        decision = LlmSemanticDecision(
            label="collection_size",
            confidence="high",
            abstain=False,
            evidence_fields=["raw_code"],
            short_rationale="count matcher",
        )
        out = apply_llm_semantic_decision("rq5c", row, decision, "rq5c_lexical_or_missing_subject_role")
        self.assertEqual(out["verification_intent_final"], "interactive_state")
        self.assertEqual(out["verification_intent_final_basis"], "deterministic_llm_guard")

    def test_rq5_guard_preserves_strong_structured_current_labels(self):
        cases = [
            (
                {
                    "verification_intent": "style_or_visual_state",
                    "assertion_subject_semantic_role_ast": "style_layout_property",
                    "assertion_semantic_matcher_ast": "have.length",
                    "raw_code": "cy.get('.tiptap').find('pre>code.language-css').should('have.length', 1)",
                },
                "collection_size",
                "style_or_visual_state",
            ),
            (
                {
                    "verification_intent": "network_contract",
                    "assertion_subject_semantic_role_ast": "network_payload",
                    "assertion_subject_path_json": '["interception", "request", "body", "filters"]',
                    "raw_code": "expect(interception.request.body.filters).to.have.length(3)",
                },
                "collection_size",
                "network_contract",
            ),
            (
                {
                    "verification_intent": "navigation_outcome",
                    "assertion_subject_semantic_role_ast": "navigation_location",
                    "raw_code": "expect(currentUrl).toContain('org_identifier=_meta')",
                },
                "value_or_attribute_correctness",
                "navigation_outcome",
            ),
            (
                {
                    "verification_intent": "interactive_state",
                    "assertion_subject_semantic_role_ast": "ui_control_state",
                    "assertion_semantic_matcher_ast": "be.enabled",
                    "raw_code": "ui.button.findByTitle('Save').should('be.visible').should('be.enabled')",
                },
                "element_presence",
                "interactive_state",
            ),
            (
                {
                    "verification_intent": "api_or_data_contract",
                    "assertion_subject_semantic_role_ast": "api_object_contract",
                    "assertion_semantic_matcher_ast": "be.an",
                    "raw_code": "expect(nodePools[0]).to.be.an('object')",
                },
                "value_or_attribute_correctness",
                "api_or_data_contract",
            ),
        ]
        for row, llm_label, expected in cases:
            with self.subTest(raw=row["raw_code"]):
                decision = LlmSemanticDecision(
                    label=llm_label,
                    confidence="high",
                    abstain=False,
                    evidence_fields=["raw_code"],
                    short_rationale="conflicting LLM label",
                )
                out = apply_llm_semantic_decision(
                    "rq5c",
                    row,
                    decision,
                    "rq5c_subject_matcher_semantic_conflict",
                )
                self.assertEqual(out["verification_intent_final"], expected)
                self.assertEqual(out["verification_intent_final_basis"], "deterministic_llm_guard")

    def test_dry_run_records_prompt_metadata_and_trigger_without_api_call(self):
        with tempfile.TemporaryDirectory() as td:
            corrector = LlmSemanticCorrector(
                enabled=True,
                model="gpt-5.4-mini",
                cache=LlmSemanticCache(Path(td)),
                dry_run=True,
                fail_closed=True,
            )
            out = corrector.correct(
                "rq2",
                {
                    "input_plausibility": "domain_plausible_input",
                    "input_target_role_ast": "unknown",
                    "input_source_class": "literal_input",
                    "input_value_expression_kind_ast": "string_literal",
                    "value_summary": "test Mandatory",
                    "raw_code": 'cy.get(jsonform.jsformInput).type("test Mandatory")',
                },
            )
            self.assertEqual(
                out["input_plausibility_llm_trigger_reason"],
                "rq2_weak_literal_unknown_target_not_observable_candidate",
            )
            self.assertEqual(out["input_plausibility_final_basis"], "deterministic")
            self.assertEqual(out["llm_model"], "gpt-5.4-mini")
            self.assertEqual(out["llm_prompt_version"], LLM_SEMANTIC_PROMPT_VERSION)
            self.assertRegex(out["llm_input_hash"], r"^[0-9a-f]{64}$")

    def test_trigger_reason_overwrites_existing_blank_review_bundle_column(self):
        out = apply_deterministic_semantic_columns(
            "rq5c",
            {
                "verification_intent": "content_correctness",
                "verification_intent_llm_trigger_reason": "",
            },
            "rq5c_accessibility_matcher_semantic_conflict",
        )
        self.assertEqual(
            out["verification_intent_llm_trigger_reason"],
            "rq5c_accessibility_matcher_semantic_conflict",
        )

    def test_openai_client_retries_transient_503_once(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(
                    {
                        "output_text": json.dumps(
                            {
                                "label": "domain_plausible_input",
                                "confidence": "high",
                                "abstain": False,
                                "evidence_fields": ["field_context"],
                                "short_rationale": "Visible field context supplies domain semantics.",
                            }
                        )
                    }
                ).encode("utf-8")

        transient = urllib.error.HTTPError(
            "https://api.openai.com/v1/responses",
            503,
            "Service Unavailable",
            hdrs=None,
            fp=None,
        )
        client = OpenAiResponsesSemanticClient(
            model="gpt-5.4-mini",
            api_key="test-key",
            retry_attempts=2,
            retry_sleep_seconds=0,
        )
        request = build_llm_semantic_request(
            rq="rq2",
            row={"input_plausibility": "not_observable"},
            trigger_reason="rq2_visible_text_input_semantic_boundary",
        )
        with mock.patch(
            "llm_semantic_categorizer.urllib.request.urlopen",
            side_effect=[transient, FakeResponse()],
        ) as mocked_urlopen:
            decision = client.classify(request)

        self.assertEqual(mocked_urlopen.call_count, 2)
        self.assertEqual(decision.label, "domain_plausible_input")
        self.assertEqual(decision.confidence, "high")

    def test_openai_client_retries_read_timeout_once(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(
                    {
                        "output_text": json.dumps(
                            {
                                "label": "element_presence",
                                "confidence": "high",
                                "abstain": False,
                                "evidence_fields": ["raw_code"],
                                "short_rationale": "Visibility matcher checks element presence.",
                            }
                        )
                    }
                ).encode("utf-8")

        client = OpenAiResponsesSemanticClient(
            model="gpt-5.4-mini",
            api_key="test-key",
            retry_attempts=2,
            retry_sleep_seconds=0,
        )
        request = build_llm_semantic_request(
            rq="rq5c",
            row={"verification_intent": "value_or_attribute_correctness", "raw_code": "cy.get('#x').should('be.visible')"},
            trigger_reason="rq5c_presence_matcher_semantic_conflict",
        )
        with mock.patch(
            "llm_semantic_categorizer.urllib.request.urlopen",
            side_effect=[TimeoutError("read timed out"), FakeResponse()],
        ) as mocked_urlopen:
            decision = client.classify(request)

        self.assertEqual(mocked_urlopen.call_count, 2)
        self.assertEqual(decision.label, "element_presence")
        self.assertEqual(decision.confidence, "high")

    def test_build_batch_request_keeps_taxonomy_once_and_items_separate(self):
        row_a = {
            "input_plausibility": "not_observable",
            "raw_code": "cy.get('#name').type(user.name)",
            "value_summary": "user.name",
        }
        row_b = {
            "input_plausibility": "placeholder_or_dummy_input",
            "raw_code": "cy.get('#name').type('test name')",
            "value_summary": "test name",
        }
        req_a = build_llm_semantic_request(
            rq="rq2",
            row=row_a,
            trigger_reason="rq2_visible_text_input_semantic_boundary",
        )
        req_b = build_llm_semantic_request(
            rq="rq2",
            row=row_b,
            trigger_reason="rq2_dummy_word_domain_context_conflict",
        )
        batch = build_llm_semantic_batch_request(
            rq="rq2",
            items=[
                {"row_id": "r0", "request": req_a},
                {"row_id": "r1", "request": req_b},
            ],
        )

        self.assertEqual(batch["rq"], "rq2")
        self.assertEqual(len(batch["items"]), 2)
        self.assertIn("instruction_block", batch)
        self.assertIn("taxonomy_definitions", batch["instruction_block"])
        self.assertNotIn("taxonomy_definitions", batch)
        self.assertNotIn("taxonomy_definitions", batch["items"][0])
        self.assertEqual(batch["items"][0]["row_id"], "r0")
        self.assertEqual(batch["items"][1]["trigger_reason"], "rq2_dummy_word_domain_context_conflict")

    def test_openai_client_uses_developer_instruction_and_strict_label_enum_schema(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(
                    {
                        "output_text": json.dumps(
                            {
                                "label": "value_or_attribute_correctness",
                                "confidence": "high",
                                "abstain": False,
                                "evidence_fields": ["structured_fields.raw_code"],
                                "short_rationale": "Bare status is scalar without HTTP provenance.",
                                "codebook_step": "scalar_property_or_attribute",
                            }
                        )
                    }
                ).encode("utf-8")

        client = OpenAiResponsesSemanticClient(
            model="gpt-5.4-mini",
            api_key="test-key",
            retry_attempts=1,
        )
        request = build_llm_semantic_request(
            rq="rq5c",
            row={
                "verification_intent": "network_contract",
                "raw_code": "expect(status).toBe('healthy')",
            },
            trigger_reason="rq5c_scalar_network_boundary",
        )
        with mock.patch(
            "llm_semantic_categorizer.urllib.request.urlopen",
            return_value=FakeResponse(),
        ) as mocked_urlopen:
            decision = client.classify(request)

        body = json.loads(mocked_urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(body["input"][0]["role"], "developer")
        self.assertIn("taxonomy_definitions", body["input"][0]["content"])
        self.assertNotIn("taxonomy_definitions", body["input"][1]["content"])
        schema = body["text"]["format"]
        self.assertTrue(schema["strict"])
        self.assertEqual(schema["schema"]["properties"]["label"]["enum"], request["allowed_labels"])
        self.assertIn("codebook_step", schema["schema"]["required"])
        self.assertEqual(decision.codebook_step, "scalar_property_or_attribute")

    def test_openai_client_classifies_batch_with_one_request(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(
                    {
                        "output_text": json.dumps(
                            {
                                "items": [
                                    {
                                        "row_id": "r0",
                                        "label": "domain_plausible_input",
                                        "confidence": "high",
                                        "abstain": False,
                                        "evidence_fields": ["structured_fields.value_summary"],
                                        "short_rationale": "Member value fits the visible field.",
                                    },
                                    {
                                        "row_id": "r1",
                                        "label": "placeholder_or_dummy_input",
                                        "confidence": "medium",
                                        "abstain": False,
                                        "evidence_fields": ["source_snippet"],
                                        "short_rationale": "The literal is explicit filler.",
                                    },
                                ]
                            }
                        )
                    }
                ).encode("utf-8")

        client = OpenAiResponsesSemanticClient(
            model="gpt-5.4-mini",
            api_key="test-key",
            retry_attempts=1,
        )
        batch = {
            "rq": "rq2",
            "items": [
                {"row_id": "r0"},
                {"row_id": "r1"},
            ],
        }
        with mock.patch(
            "llm_semantic_categorizer.urllib.request.urlopen",
            return_value=FakeResponse(),
        ) as mocked_urlopen:
            decisions = client.classify_batch("rq2", batch)

        self.assertEqual(mocked_urlopen.call_count, 1)
        self.assertEqual(decisions["r0"].label, "domain_plausible_input")
        self.assertEqual(decisions["r1"].label, "placeholder_or_dummy_input")

    def test_openai_batch_client_retries_socket_timeout_once(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(
                    {
                        "output_text": json.dumps(
                            {
                                "items": [
                                    {
                                        "row_id": "r0",
                                        "label": "element_presence",
                                        "confidence": "high",
                                        "abstain": False,
                                        "evidence_fields": ["structured_fields.raw_code"],
                                        "short_rationale": "Visibility matcher checks element presence.",
                                        "codebook_step": "presence_matcher",
                                    }
                                ]
                            }
                        )
                    }
                ).encode("utf-8")

        client = OpenAiResponsesSemanticClient(
            model="gpt-5.4-mini",
            api_key="test-key",
            retry_attempts=2,
            retry_sleep_seconds=0,
        )
        batch = {
            "rq": "rq5c",
            "items": [
                {
                    "row_id": "r0",
                    "request": build_llm_semantic_request(
                        rq="rq5c",
                        row={
                            "verification_intent": "value_or_attribute_correctness",
                            "raw_code": "cy.get('#x').should('be.visible')",
                        },
                        trigger_reason="rq5c_presence_matcher_semantic_conflict",
                    ),
                }
            ],
        }
        with mock.patch(
            "llm_semantic_categorizer.urllib.request.urlopen",
            side_effect=[socket.timeout("The read operation timed out"), FakeResponse()],
        ) as mocked_urlopen:
            decisions = client.classify_batch("rq5c", batch)

        self.assertEqual(mocked_urlopen.call_count, 2)
        self.assertEqual(decisions["r0"].label, "element_presence")
        self.assertEqual(decisions["r0"].confidence, "high")

    def test_correct_many_batches_uncached_rows_and_writes_per_row_cache(self):
        class FakeClient:
            def __init__(self):
                self.batch_sizes = []

            def classify_batch(self, rq, request):
                self.batch_sizes.append(len(request["items"]))
                return {
                    item["row_id"]: LlmSemanticDecision(
                        label="domain_plausible_input",
                        confidence="high",
                        abstain=False,
                        evidence_fields=["source_snippet"],
                        short_rationale="Visible/member context is plausible.",
                    )
                    for item in request["items"]
                }

        with tempfile.TemporaryDirectory() as td:
            client = FakeClient()
            corrector = LlmSemanticCorrector(
                enabled=True,
                model="gpt-5.4-mini",
                cache=LlmSemanticCache(Path(td)),
                client=client,
                batch_size=2,
                progress_interval=1,
            )
            rows = [
                {
                    "input_plausibility": "domain_plausible_input",
                    "input_plausibility_confidence": "high",
                    "input_source_class": "literal_input",
                    "input_value_expression_kind_ast": "string_literal",
                    "input_target_role_ast": "unknown",
                    "input_channel": "ui_text_entry",
                    "value_summary": "test Mandatory",
                    "raw_code": f"cy.get(jsonform.jsformInput{i}).type('test Mandatory')",
                }
                for i in range(3)
            ]

            out = corrector.correct_many("rq2", rows)
            self.assertEqual(client.batch_sizes, [2, 1])
            self.assertEqual([r["input_plausibility"] for r in out], ["domain_plausible_input"] * 3)
            self.assertEqual(corrector.rows_triggered, 3)
            self.assertEqual(corrector.rows_api_calls, 3)
            self.assertEqual(corrector.api_batches, 2)
            self.assertEqual(corrector.rows_corrected, 3)

            second = corrector.correct_many("rq2", rows)
            self.assertEqual(client.batch_sizes, [2, 1])
            self.assertEqual([r["input_plausibility"] for r in second], ["domain_plausible_input"] * 3)
            self.assertEqual(corrector.rows_cache_hits, 3)

    def test_cache_only_uses_cached_decision_without_api_call(self):
        class FailingClient:
            def classify_batch(self, rq, request):
                raise AssertionError("cache-only mode must not call the LLM client")

        row = {
            "input_plausibility": "domain_plausible_input",
            "input_plausibility_confidence": "high",
            "input_source_class": "literal_input",
            "input_value_expression_kind_ast": "string_literal",
            "input_target_role_ast": "unknown",
            "input_channel": "ui_text_entry",
            "value_summary": "test Mandatory",
            "raw_code": "cy.get(jsonform.jsformInput).type('test Mandatory')",
        }
        request = build_llm_semantic_request(
            rq="rq2",
            row=row,
            trigger_reason=should_trigger_llm_correction("rq2", row),
        )
        input_hash = build_input_hash(request)

        with tempfile.TemporaryDirectory() as td:
            cache = LlmSemanticCache(Path(td))
            cache.put(
                model="gpt-5.4-mini",
                prompt_version=LLM_SEMANTIC_PROMPT_VERSION,
                input_hash=input_hash,
                payload={
                    "label": "placeholder_or_dummy_input",
                    "confidence": "high",
                    "abstain": False,
                    "evidence_fields": ["value_summary"],
                    "short_rationale": "Cached decision.",
                },
            )
            corrector = LlmSemanticCorrector(
                enabled=True,
                model="gpt-5.4-mini",
                cache=cache,
                client=FailingClient(),
                cache_only=True,
                fail_closed=True,
            )

            out = corrector.correct_many("rq2", [row])
            self.assertEqual(out[0]["input_plausibility"], "placeholder_or_dummy_input")
            self.assertEqual(corrector.rows_cache_hits, 1)
            self.assertEqual(corrector.rows_api_calls, 0)
            self.assertEqual(corrector.rows_cache_only_misses, 0)

    def test_cache_only_fail_closed_raises_on_cache_miss(self):
        class FailingClient:
            def classify_batch(self, rq, request):
                raise AssertionError("cache-only mode must not call the LLM client")

        row = {
            "input_plausibility": "domain_plausible_input",
            "input_plausibility_confidence": "high",
            "input_source_class": "literal_input",
            "input_value_expression_kind_ast": "string_literal",
            "input_target_role_ast": "unknown",
            "input_channel": "ui_text_entry",
            "value_summary": "test Mandatory",
            "raw_code": "cy.get(jsonform.jsformInput).type('test Mandatory')",
        }
        with tempfile.TemporaryDirectory() as td:
            corrector = LlmSemanticCorrector(
                enabled=True,
                model="gpt-5.4-mini",
                cache=LlmSemanticCache(Path(td)),
                client=FailingClient(),
                cache_only=True,
                fail_closed=True,
            )

            with self.assertRaisesRegex(RuntimeError, "LLM cache-only miss"):
                corrector.correct_many("rq2", [row])
            self.assertEqual(corrector.rows_api_calls, 0)
            self.assertEqual(corrector.rows_cache_only_misses, 1)

    def test_correct_many_can_send_multiple_batches_concurrently(self):
        class FakeClient:
            def __init__(self):
                self.lock = threading.Lock()
                self.active = 0
                self.max_active = 0
                self.batch_sizes = []

            def classify_batch(self, rq, request):
                with self.lock:
                    self.active += 1
                    self.max_active = max(self.max_active, self.active)
                    self.batch_sizes.append(len(request["items"]))
                time.sleep(0.05)
                with self.lock:
                    self.active -= 1
                return {
                    item["row_id"]: LlmSemanticDecision(
                        label="domain_plausible_input",
                        confidence="high",
                        abstain=False,
                        evidence_fields=["source_snippet"],
                        short_rationale="Visible/member context is plausible.",
                    )
                    for item in request["items"]
                }

        with tempfile.TemporaryDirectory() as td:
            client = FakeClient()
            corrector = LlmSemanticCorrector(
                enabled=True,
                model="gpt-5.4-mini",
                cache=LlmSemanticCache(Path(td)),
                client=client,
                batch_size=2,
                max_concurrent_requests=3,
                progress_interval=1,
            )
            rows = [
                {
                    "input_plausibility": "domain_plausible_input",
                    "input_plausibility_confidence": "high",
                    "input_source_class": "literal_input",
                    "input_value_expression_kind_ast": "string_literal",
                    "input_target_role_ast": "unknown",
                    "input_channel": "ui_text_entry",
                    "value_summary": "test Mandatory",
                    "raw_code": f"cy.get(jsonform.jsformInput{i}).type('test Mandatory')",
                }
                for i in range(6)
            ]

            out = corrector.correct_many("rq2", rows)
            self.assertEqual(sorted(client.batch_sizes), [2, 2, 2])
            self.assertGreaterEqual(client.max_active, 2)
            self.assertLessEqual(client.max_active, 3)
            self.assertEqual([r["input_plausibility"] for r in out], ["domain_plausible_input"] * 6)
            self.assertEqual(corrector.rows_api_calls, 6)
            self.assertEqual(corrector.api_batches, 3)

    def test_rq2_indeterminate_adjudication_triggers_on_semantic_risk_categories(self):
        domain_context_row = {
            "input_plausibility": "not_observable",
            "input_plausibility_final": "not_observable",
            "input_plausibility_paper_label": "indeterminate_or_insufficient_evidence",
            "input_source_class": "literal_input",
            "input_channel": "ui_text_entry",
            "value_visibility": "visible",
            "value_summary": "item1",
            "field_context": "sv-list input",
            "raw_code": "page.locator('.sv-list__input').fill('item1')",
        }
        self.assertEqual(
            should_trigger_rq2_indeterminate_adjudication(domain_context_row),
            "rq2_indeterminate_visible_or_contextual_value_adjudication",
        )

        opaque_row = {
            "input_plausibility": "not_observable",
            "input_plausibility_final": "not_observable",
            "input_plausibility_paper_label": "indeterminate_or_insufficient_evidence",
            "input_source_class": "variable_input",
            "input_channel": "ui_text_entry",
            "value_visibility": "opaque",
            "value_summary": "weightInput",
            "raw_code": "weightInput.fill(weight_field)",
        }
        self.assertEqual(
            should_trigger_rq2_indeterminate_adjudication(opaque_row),
            "rq2_indeterminate_opaque_member_or_receiver_adjudication",
        )

        genuinely_blank = {
            "input_plausibility": "not_observable",
            "input_plausibility_final": "not_observable",
            "input_plausibility_paper_label": "indeterminate_or_insufficient_evidence",
            "input_source_class": "variable_input",
            "input_channel": "",
            "value_visibility": "opaque",
            "value_summary": "",
            "raw_code": "helper(value)",
        }
        self.assertEqual(should_trigger_rq2_indeterminate_adjudication(genuinely_blank), "")

    def test_rq2_indeterminate_adjudication_promotes_with_separate_columns(self):
        class FakeClient:
            def __init__(self):
                self.requests = []

            def classify_batch(self, rq, request):
                self.requests.append(request)
                return {
                    item["row_id"]: LlmSemanticDecision(
                        label="domain_plausible_input" if item["trigger_reason"].startswith("rq2_indeterminate") else "",
                        confidence="high" if item["trigger_reason"].startswith("rq2_indeterminate") else "low",
                        abstain=not item["trigger_reason"].startswith("rq2_indeterminate"),
                        evidence_fields=[
                            "structured_fields.field_context",
                            "structured_fields.value_summary",
                        ] if item["trigger_reason"].startswith("rq2_indeterminate") else [],
                        short_rationale="The target context and value are meaningful UI data."
                        if item["trigger_reason"].startswith("rq2_indeterminate")
                        else "First pass abstains.",
                        codebook_step="adjudicate_indeterminate_domain_context"
                        if item["trigger_reason"].startswith("rq2_indeterminate")
                        else "abstain",
                    )
                    for item in request["items"]
                }

        with tempfile.TemporaryDirectory() as td:
            corrector = LlmSemanticCorrector(
                enabled=True,
                model="gpt-5.4-mini",
                cache=LlmSemanticCache(Path(td)),
                client=FakeClient(),
                batch_size=64,
                max_concurrent_requests=8,
                progress_interval=1,
            )
            rows = [
                {
                    "input_plausibility": "not_observable",
                    "input_plausibility_confidence": "high",
                    "input_plausibility_paper_label": "indeterminate_or_insufficient_evidence",
                    "input_source_class": "literal_input",
                    "input_channel": "ui_text_entry",
                    "value_visibility": "visible",
                    "value_summary": "item1",
                    "field_context": "sv-list input",
                    "raw_code": "page.locator('.sv-list__input').fill('item1')",
                }
            ]

            out = corrector.correct_many("rq2", rows)[0]
            self.assertEqual(out["input_plausibility_final"], "placeholder_or_dummy_input")
            self.assertEqual(out["input_plausibility_final_basis"], "deterministic_llm_guard")
            self.assertEqual(out["input_plausibility_paper_label"], "placeholder_or_dummy_input")

    def test_rq2_indeterminate_adjudication_keeps_keypress_technical_without_text_context(self):
        class FakeClient:
            def classify_batch(self, rq, request):
                return {
                    item["row_id"]: LlmSemanticDecision(
                        label="domain_plausible_input",
                        confidence="high",
                        abstain=False,
                        evidence_fields=["structured_fields.raw_code"],
                        short_rationale="The key could be text.",
                        codebook_step="domain_text_value",
                    )
                    for item in request["items"]
                }

        with tempfile.TemporaryDirectory() as td:
            corrector = LlmSemanticCorrector(
                enabled=True,
                model="gpt-5.4-mini",
                cache=LlmSemanticCache(Path(td)),
                client=FakeClient(),
                batch_size=64,
                max_concurrent_requests=8,
            )
            row = {
                "input_plausibility": "technical_or_control_input",
                "input_plausibility_confidence": "high",
                "input_plausibility_paper_label": "technical_or_configuration_or_control_input",
                "input_source_class": "literal_input",
                "input_channel": "keyboard_entry",
                "value_visibility": "visible",
                "value_summary": "3",
                "raw_code": 'page.keyboard.press("3")',
            }
            out = corrector.correct_many("rq2", [row])[0]
            self.assertEqual(out["input_plausibility_final"], "not_observable")
            self.assertEqual(out["input_plausibility_final_basis"], "deterministic_llm_guard")

    def test_rq2_adjudication_guard_keeps_repeated_control_token_technical(self):
        row = {
            "input_plausibility": "technical_or_control_input",
            "input_plausibility_confidence": "medium",
            "input_plausibility_paper_label": "technical_or_configuration_or_control_input",
            "input_source_class": "literal_input",
            "input_channel": "ui_text_entry",
            "value_visibility": "visible",
            "value_summary": "'{leftArrow}'.repeat('27'.length)",
            "field_context": "@input",
            "raw_code": "cy.get('@input').type('42,27').type('{leftArrow}'.repeat('27'.length))",
        }
        decision = LlmSemanticDecision(
            label="domain_plausible_input",
            confidence="high",
            abstain=False,
            evidence_fields=["structured_fields.raw_code"],
            short_rationale="The chain includes a previous visible numeric value.",
            codebook_step="visible_domain_text",
        )
        out = apply_rq2_indeterminate_adjudication_decision(
            row,
            decision,
            "rq2_unknown_target_opaque_or_member_value",
        )
        self.assertEqual(out["input_plausibility_final"], "not_observable")
        self.assertEqual(out["input_plausibility_final_basis"], "deterministic_llm_guard")
        self.assertEqual(out["input_plausibility_paper_label"], "")

    def test_rq2_keyboard_token_in_previous_chain_step_does_not_override_current_domain_value(self):
        row = {
            "input_plausibility": "domain_plausible_input",
            "input_plausibility_confidence": "medium",
            "input_plausibility_paper_label": "domain_plausible_input",
            "input_source_class": "api_seed_input",
            "input_channel": "ui_text_entry",
            "value_visibility": "opaque",
            "value_summary": "otherUser.username",
            "field_context": "username",
            "input_target_role_ast": "domain_text_field",
            "raw_code": "cy.get('#username').clear().type(prefix).type('{backspace}.').type(otherUser.username)",
        }
        decision = LlmSemanticDecision(
            label="technical_or_control_input",
            confidence="high",
            abstain=False,
            evidence_fields=["structured_fields.raw_code"],
            short_rationale="The chain contains a backspace token.",
            codebook_step="keyboard_control",
        )
        out = apply_llm_semantic_decision(
            "rq2",
            row,
            decision,
            "rq2_keyboard_token_chain_ambiguity",
        )
        self.assertEqual(out["input_plausibility_final"], "domain_plausible_input")
        self.assertEqual(out["input_plausibility_final_basis"], "deterministic_llm_guard")
        self.assertEqual(out["input_plausibility_paper_label"], "domain_plausible_input")

    def test_rq2_adjudication_guards_config_like_numeric_fields_from_validation(self):
        row = {
            "input_plausibility": "not_observable",
            "input_plausibility_confidence": "high",
            "input_plausibility_paper_label": "indeterminate_or_insufficient_evidence",
            "input_source_class": "literal_input",
            "input_channel": "ui_text_entry",
            "value_visibility": "visible",
            "value_summary": "30",
            "raw_code": 'symbolMaxInput.fill("30")',
        }
        decision = LlmSemanticDecision(
            label="validation_or_edge_case_input",
            confidence="high",
            abstain=False,
            evidence_fields=["structured_fields.raw_code", "structured_fields.value_summary"],
            short_rationale="The value is a max boundary.",
            codebook_step="boundary_value",
        )
        out = apply_rq2_indeterminate_adjudication_decision(
            row,
            decision,
            "rq2_indeterminate_visible_or_contextual_value_adjudication",
        )
        self.assertEqual(out["input_plausibility_final"], "not_observable")
        self.assertEqual(out["input_plausibility_paper_label"], "")
        self.assertEqual(out["input_plausibility_final_basis"], "deterministic_llm_guard")

    def test_rq2_adjudication_guards_meaningful_unknown_target_text_as_domain(self):
        row = {
            "input_plausibility": "not_observable",
            "input_plausibility_confidence": "high",
            "input_plausibility_paper_label": "indeterminate_or_insufficient_evidence",
            "input_source_class": "literal_input",
            "input_channel": "ui_text_entry",
            "value_visibility": "visible",
            "value_summary": "non-occurring-string",
            "raw_code": "input.fill('non-occurring-string')",
        }
        decision = LlmSemanticDecision(
            label="not_observable",
            confidence="medium",
            abstain=False,
            evidence_fields=["structured_fields.raw_code", "structured_fields.value_summary"],
            short_rationale="The target is opaque.",
            codebook_step="insufficient_target_context",
        )
        out = apply_rq2_indeterminate_adjudication_decision(
            row,
            decision,
            "rq2_indeterminate_visible_or_contextual_value_adjudication",
        )
        self.assertEqual(out["input_plausibility_final"], "domain_plausible_input")
        self.assertEqual(out["input_plausibility_paper_label"], "domain_plausible_input")
        self.assertEqual(out["input_plausibility_final_basis"], "deterministic_llm_guard")

    def test_concurrent_batches_respect_max_rows_before_scheduling(self):
        class FakeClient:
            def __init__(self):
                self.batch_sizes = []

            def classify_batch(self, rq, request):
                self.batch_sizes.append(len(request["items"]))
                return {
                    item["row_id"]: LlmSemanticDecision(
                        label="domain_plausible_input",
                        confidence="high",
                        abstain=False,
                        evidence_fields=["source_snippet"],
                        short_rationale="Visible/member context is plausible.",
                    )
                    for item in request["items"]
                }

        with tempfile.TemporaryDirectory() as td:
            client = FakeClient()
            corrector = LlmSemanticCorrector(
                enabled=True,
                model="gpt-5.4-mini",
                cache=LlmSemanticCache(Path(td)),
                client=client,
                batch_size=2,
                max_concurrent_requests=3,
                max_rows=3,
                progress_interval=1,
            )
            rows = [
                {
                    "input_plausibility": "domain_plausible_input",
                    "input_plausibility_confidence": "high",
                    "input_source_class": "literal_input",
                    "input_value_expression_kind_ast": "string_literal",
                    "input_target_role_ast": "unknown",
                    "input_channel": "ui_text_entry",
                    "value_summary": "test Mandatory",
                    "raw_code": f"cy.get(jsonform.jsformInput{i}).type('test Mandatory')",
                }
                for i in range(6)
            ]

            out = corrector.correct_many("rq2", rows)
            self.assertEqual(client.batch_sizes, [2, 1])
            self.assertEqual(corrector.rows_api_calls, 3)
            self.assertEqual(corrector.rows_dry_run_or_limited, 3)
            self.assertEqual([r["input_plausibility"] for r in out[:3]], ["domain_plausible_input"] * 3)
            self.assertEqual([r["input_plausibility"] for r in out[3:]], ["domain_plausible_input"] * 3)
            self.assertEqual([r["input_plausibility_final_basis"] for r in out[3:]], ["deterministic"] * 3)

    def test_correct_many_applies_guarded_rows_before_api_batch(self):
        class FakeClient:
            def __init__(self):
                self.batch_sizes = []

            def classify_batch(self, rq, request):
                self.batch_sizes.append(len(request["items"]))
                return {}

        with tempfile.TemporaryDirectory() as td:
            client = FakeClient()
            corrector = LlmSemanticCorrector(
                enabled=True,
                model="gpt-5.4-mini",
                cache=LlmSemanticCache(Path(td)),
                client=client,
                batch_size=16,
            )
            rows = [
                {
                    "verification_intent": "content_correctness",
                    "verification_intent_confidence": "high",
                    "verification_intent_evidence_basis": "ast_assertion_subject_semantic_role",
                    "assertion_subject_semantic_role_ast": "text_content_payload",
                    "raw_code": "cy.findByText('Autocomplete').should('be.visible')",
                    "matcher": "be.visible",
                }
            ]

            out = corrector.correct_many("rq5c", rows)
            self.assertEqual(client.batch_sizes, [])
            self.assertEqual(corrector.rows_triggered, 1)
            self.assertEqual(corrector.rows_guarded, 1)
            self.assertEqual(corrector.rows_api_calls, 0)
            self.assertEqual(out[0]["verification_intent_final"], "element_presence")
            self.assertEqual(out[0]["verification_intent_final_basis"], "deterministic_llm_guard")


if __name__ == "__main__":
    unittest.main()
