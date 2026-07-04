#!/usr/bin/env python3
"""Tests for RQ2 input_classify."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from input_classify import resolve_input_pattern


class TestResolveInputPattern(unittest.TestCase):
    def test_literal_with_ast(self):
        r = resolve_input_pattern(
            "input:fill:alice@example.com",
            "await page.getByLabel('Email').fill('alice@example.com')",
            feature={
                "input_source_ast": "literal_input",
                "value_visibility_ast": "visible",
                "input_value_redacted": "alice@example.com",
                "field_context_ast": "Email",
                "field_context_basis_ast": "getByLabel",
            },
        )
        self.assertEqual(r["input_source_class"], "literal_input")
        self.assertEqual(r["input_plausibility"], "domain_plausible_input")

    def test_fixture_load_site(self):
        r = resolve_input_pattern(
            "cy.fixture",
            'cy.fixture("users.json")',
            feature={
                "input_source_ast": "fixture_file_input",
                "input_load_path_ast": "users.json",
                "value_visibility_ast": "visible",
                "input_channel_ast": "load_site",
            },
        )
        self.assertEqual(r["input_source_class"], "fixture_file_input")
        self.assertEqual(r["external_file_path"], "users.json")

    def test_provenance_upgrades_variable(self):
        r = resolve_input_pattern(
            "input:type:data.email",
            "cy.get('#e').type(data.email)",
            feature={
                "input_source_ast": "variable_input",
                "input_provenance_ast": "fixture_file:cypress/fixtures/users.json#email",
                "value_visibility_ast": "opaque",
            },
        )
        self.assertEqual(r["input_source_class"], "variable_from_external_file")
        self.assertEqual(r["field_path"], "email")

    def test_composite_provenance_fields_are_preserved(self):
        r = resolve_input_pattern(
            "input:type:composite",
            "cy.get('#next').type(this.dataSet.paginationUrl + testdata.nextUrl)",
            feature={
                "input_source_ast": "variable_from_external_file",
                "input_origin_kind_ast": "composite_expression",
                "input_origin_confidence_ast": "high",
                "input_origin_evidence_ast": "this.dataSet.paginationUrl + testdata.nextUrl",
                "input_provenance_ast": "composite_expression",
                "input_provenance_family_ast": "composite_expression",
                "input_provenance_components_json": '[{"provenance":"fixture_file:data.json#paginationUrl"},{"provenance":"external_file:testdata.json#nextUrl"}]',
                "value_visibility_ast": "opaque",
                "input_evidence_basis_ast": "ast_binary_expression_components",
                "is_static_file_candidate_ast": True,
            },
        )
        self.assertEqual(r["input_provenance"], "composite_expression")
        self.assertEqual(r["input_provenance_family"], "composite_expression")
        self.assertIn("fixture_file:data.json#paginationUrl", r["input_provenance_components_json"])
        self.assertTrue(r["is_static_file_candidate"])

    def test_non_file_provenance_does_not_populate_external_file_path(self):
        for provenance in (
            "inline_object:object_literal",
            "generated:factory_or_generator",
            "api_seed:cy.request('/users')",
            "alias:user",
        ):
            with self.subTest(provenance=provenance):
                r = resolve_input_pattern(
                    "input:type:user.email",
                    "cy.get('#e').type(user.email)",
                    feature={
                        "input_source_ast": "variable_input",
                        "input_provenance_ast": provenance,
                        "value_visibility_ast": "opaque",
                    },
                )
                self.assertEqual(r["external_file_path"], "")
                self.assertEqual(r["field_path"], "")

    def test_parameterized_provenance_only_populates_field_path(self):
        r = resolve_input_pattern(
            "input:type:row.email",
            "cy.get('#e').type(row.email)",
            feature={
                "input_source_ast": "parameterized_input",
                "input_provenance_ast": "parameterized_row:test.each#email",
                "value_visibility_ast": "opaque",
            },
        )
        self.assertEqual(r["external_file_path"], "")
        self.assertEqual(r["field_path"], "email")

    def test_legacy_bare_file_provenance_still_parses_as_external_file(self):
        r = resolve_input_pattern(
            "input:type:data.email",
            "cy.get('#e').type(data.email)",
            feature={
                "input_source_ast": "variable_input",
                "input_provenance_ast": "fixtures/users.json#email",
                "value_visibility_ast": "opaque",
            },
        )
        self.assertEqual(r["external_file_path"], "fixtures/users.json")
        self.assertEqual(r["field_path"], "email")

    def test_external_provenance_derives_missing_origin_kind(self):
        r = resolve_input_pattern(
            "input:fill:jwt",
            "jwtEditorInput.fill(jwt)",
            feature={
                "input_source_ast": "variable_from_external_file",
                "input_provenance_ast": "external_file:e2e/jwt.json",
                "value_visibility_ast": "opaque",
                "input_evidence_basis_ast": "ast_provenance",
            },
        )
        self.assertEqual(r["input_origin_kind"], "static_file_root")
        self.assertEqual(r["input_provenance_family"], "external_file")
        self.assertEqual(r["external_file_path"], "e2e/jwt.json")

    def test_external_member_provenance_derives_missing_origin_kind(self):
        r = resolve_input_pattern(
            "input:type:data.email",
            "cy.get('#e').type(data.email)",
            feature={
                "input_source_ast": "variable_from_external_file",
                "input_provenance_ast": "fixture_file:cypress/fixtures/users.json#email",
                "value_visibility_ast": "opaque",
                "input_evidence_basis_ast": "ast_provenance",
            },
        )
        self.assertEqual(r["input_origin_kind"], "static_file_root_member")
        self.assertEqual(r["input_provenance_family"], "external_file")
        self.assertEqual(r["field_path"], "email")

    def test_realpress_array_literal_keyboard_input(self):
        r = resolve_input_pattern(
            'input:realPress:["Shift", "Tab"]',
            'cy.realPress(["Shift", "Tab"])',
            feature={
                "input_source_ast": "literal_input",
                "input_value_kind_ast": "array_literal",
                "value_visibility_ast": "visible",
                "input_value_redacted": '["Shift", "Tab"]',
                "input_channel_ast": "keyboard_input",
            },
        )
        self.assertEqual(r["input_source_class"], "literal_input")
        self.assertEqual(r["input_channel"], "keyboard_input")
        self.assertEqual(r["input_plausibility"], "technical_or_control_input")
        self.assertEqual(r["rq2_value_bearing_input"], "false")
        self.assertEqual(r["rq2_value_exclusion_reason"], "keyboard_control_token")

    def test_enter_only_text_entry_is_not_value_bearing_input(self):
        r = resolve_input_pattern(
            "input:type:{enter}",
            "cy.get('input').type('{enter}')",
            feature={
                "input_source_ast": "literal_input",
                "value_visibility_ast": "visible",
                "input_value_redacted": "{enter}",
                "input_channel_ast": "ui_text_entry",
                "input_evidence_basis_ast": "ast_value_argument",
                "input_origin_kind_ast": "inline_literal",
                "input_origin_evidence_ast": "{enter}",
            },
        )
        self.assertEqual(r["input_plausibility_codebook_path"], "keyboard_or_control_token")
        self.assertEqual(r["rq2_value_bearing_input"], "false")
        self.assertEqual(r["rq2_value_exclusion_reason"], "pure_control_text_entry")

    def test_select_all_backspace_text_entry_is_not_value_bearing_input(self):
        r = resolve_input_pattern(
            "input:type:{selectall}{backspace}",
            "cy.get('input').type('{selectall}{backspace}')",
            feature={
                "input_source_ast": "literal_input",
                "value_visibility_ast": "visible",
                "input_value_redacted": "{selectall}{backspace}",
                "input_channel_ast": "ui_text_entry",
                "input_evidence_basis_ast": "ast_value_argument",
                "input_origin_kind_ast": "inline_literal",
                "input_origin_evidence_ast": "{selectall}{backspace}",
            },
        )
        self.assertEqual(r["rq2_value_bearing_input"], "false")
        self.assertEqual(r["rq2_value_bearing_basis"], "pure_control_token")

    def test_keyboard_shortcut_chord_is_not_value_bearing_input(self):
        r = resolve_input_pattern(
            "input:type:{ctrl+a}",
            "cy.get('body').type('{ctrl+a}')",
            feature={
                "input_source_ast": "literal_input",
                "value_visibility_ast": "visible",
                "input_value_redacted": "{ctrl+a}",
                "input_channel_ast": "ui_text_entry",
                "input_evidence_basis_ast": "ast_value_argument",
                "input_origin_kind_ast": "inline_literal",
                "input_origin_evidence_ast": "{ctrl+a}",
            },
        )
        self.assertEqual(r["rq2_value_bearing_input"], "false")
        self.assertEqual(r["rq2_value_bearing_basis"], "pure_control_token")

    def test_literal_empty_braces_remain_value_bearing_input(self):
        r = resolve_input_pattern(
            "input:type:{}",
            "cy.get('#template').type('{}')",
            feature={
                "input_source_ast": "literal_input",
                "value_visibility_ast": "visible",
                "input_value_redacted": "{}",
                "input_channel_ast": "ui_text_entry",
                "input_evidence_basis_ast": "ast_value_argument",
                "input_origin_kind_ast": "inline_literal",
                "input_origin_evidence_ast": "{}",
            },
        )
        self.assertEqual(r["rq2_value_bearing_input"], "true")
        self.assertEqual(r["rq2_value_bearing_basis"], "value_argument")

    def test_template_value_plus_enter_remains_value_bearing_input(self):
        r = resolve_input_pattern(
            "input:type:`${text}{enter}`",
            "cy.focused().type(`${text}{enter}`)",
            feature={
                "input_source_ast": "variable_input",
                "value_visibility_ast": "opaque",
                "input_value_redacted": "`${text}{enter}`",
                "input_channel_ast": "ui_text_entry",
                "input_evidence_basis_ast": "ast_template_expression_components",
                "input_origin_kind_ast": "composite_expression",
                "input_provenance_ast": "composite_expression",
                "input_provenance_family_ast": "composite_expression",
                "input_provenance_components_json": (
                    '[{"originKind":"local_variable","evidence":"text"},'
                    '{"originKind":"inline_literal","evidence":"{enter}"}]'
                ),
            },
        )
        self.assertEqual(r["rq2_value_bearing_input"], "true")
        self.assertEqual(r["rq2_value_bearing_basis"], "component_provenance")

    def test_inline_literal_component_without_evidence_does_not_override_control_token(self):
        r = resolve_input_pattern(
            "input:type:{enter}",
            "cy.get('input').type('{enter}')",
            feature={
                "input_source_ast": "literal_input",
                "value_visibility_ast": "visible",
                "input_value_redacted": "{enter}",
                "input_channel_ast": "ui_text_entry",
                "input_evidence_basis_ast": "ast_template_expression_components",
                "input_origin_kind_ast": "composite_expression",
                "input_provenance_ast": "composite_expression",
                "input_provenance_family_ast": "composite_expression",
                "input_provenance_components_json": '[{"originKind":"inline_literal","provenance":"inline_literal:string_literal"}]',
                "input_plausibility_codebook_path": "keyboard_or_control_token",
            },
        )
        self.assertEqual(r["rq2_value_bearing_input"], "false")
        self.assertEqual(r["rq2_value_bearing_basis"], "pure_control_token")

    def test_template_modifier_shortcut_is_not_value_bearing_input(self):
        r = resolve_input_pattern(
            "input:type:`{${modifierKey}}a`",
            "cy.get('body').type(`{${modifierKey}}a`)",
            feature={
                "input_source_ast": "variable_input",
                "value_visibility_ast": "opaque",
                "input_value_redacted": "`{${modifierKey}}a`",
                "input_channel_ast": "ui_text_entry",
                "input_evidence_basis_ast": "ast_template_expression_components",
                "input_origin_kind_ast": "composite_expression",
                "input_provenance_ast": "composite_expression",
                "input_provenance_family_ast": "composite_expression",
                "input_plausibility_codebook_path": "keyboard_or_control_token",
            },
        )
        self.assertEqual(r["rq2_value_bearing_input"], "false")
        self.assertEqual(r["rq2_value_exclusion_reason"], "pure_control_text_entry")

    def test_network_mock_fallback_uses_taxonomy_label(self):
        r = resolve_input_pattern(
            "cy.intercept",
            "cy.intercept('/api', { body: { id: 1 } })",
        )
        self.assertEqual(r["input_source_class"], "network_mock_payload_input")
        self.assertEqual(r["input_evidence_basis"], "regex_fallback")

    def test_missing_ast_basis_is_not_promoted_to_value_argument_evidence(self):
        r = resolve_input_pattern(
            "input:fill:user.name",
            "await page.fill('#name', user.name)",
            feature={
                "input_source_ast": "variable_input",
                "value_visibility_ast": "opaque",
                "input_value_redacted": "user.name",
                "input_channel_ast": "ui_text_entry",
            },
        )
        self.assertEqual(r["input_evidence_basis"], "missing_input_evidence_basis")
        self.assertEqual(r["input_source_confidence"], "low")
        self.assertTrue(r["needs_review"])

    def test_environment_endpoint_expression_uses_raw_code_for_plausibility(self):
        r = resolve_input_pattern(
            "new URL",
            "new URL('/modern-challenge-completed', process.env.API_LOCATION).toString()",
            feature={
                "input_source_ast": "environment_input",
                "value_visibility_ast": "unknown",
                "input_channel_ast": "unknown",
                "input_value_redacted": "",
            },
        )
        self.assertEqual(r["input_source_class"], "environment_input")
        self.assertEqual(r["input_plausibility"], "technical_or_control_input")

    def test_non_consumer_value_construction_is_not_consumer_input_unit(self):
        r = resolve_input_pattern(
            "Array.from.fill",
            "Array.from<RegExp>({length: 4}).fill(/\\d/)",
            feature={
                "rq2_unit": "value_construction",
                "input_source_ast": "literal_input",
                "input_value_redacted": "/\\d/",
                "value_visibility_ast": "opaque",
                "input_channel_ast": "generated_value",
                "input_evidence_basis_ast": "ast_value_construction",
            },
        )
        self.assertEqual(r["rq2_unit"], "value_construction")
        self.assertEqual(r["input_plausibility"], "not_observable")
        self.assertTrue(r["exclude_from_rq2_consumer_events"])

    def test_value_construction_fill_is_excluded_even_without_rq2_unit(self):
        r = resolve_input_pattern(
            "input:fill:/\\d/",
            "Array.from<RegExp>({length: 4}).fill(/\\d/)",
            feature={
                "input_source_ast": "unknown_input",
                "input_value_redacted": "/\\d/",
                "value_visibility_ast": "unknown",
                "input_channel_ast": "ui_text_entry",
                "input_evidence_basis_ast": "ast_value_argument",
            },
        )
        self.assertEqual(r["rq2_unit"], "value_construction")
        self.assertTrue(r["exclude_from_rq2_consumer_events"])

    def test_plausibility_uses_call_context_when_field_context_is_missing(self):
        cases = [
            (
                'input:type:Cypress.env("PASSWORD")',
                'cy.get(welcomePage.password).type(Cypress.env("PASSWORD"))',
                {
                    "input_source_ast": "environment_input",
                    "input_value_redacted": 'Cypress.env("PASSWORD")',
                    "value_visibility_ast": "opaque",
                    "input_channel_ast": "ui_text_entry",
                    "input_evidence_basis_ast": "ast_value_argument",
                },
                "domain_plausible_input",
            ),
            (
                "input:type:url + parameters",
                "cy.get(apiwidget.editResourceUrl).first().type(url + parameters)",
                {
                    "input_source_ast": "unknown_input",
                    "input_value_redacted": "url + parameters",
                    "value_visibility_ast": "unknown",
                    "input_channel_ast": "ui_text_entry",
                    "input_evidence_basis_ast": "ast_value_argument",
                },
                "technical_or_control_input",
            ),
            (
                "input:type:this.dataSet.paginationUrl + testdata.prevUrl",
                "cy.get(apiPageLocators.apiPaginationPrevText).type(this.dataSet.paginationUrl + testdata.prevUrl)",
                {
                    "input_source_ast": "variable_from_external_file",
                    "input_value_redacted": "this.dataSet.paginationUrl + testdata.prevUrl",
                    "value_visibility_ast": "opaque",
                    "input_channel_ast": "ui_text_entry",
                    "input_evidence_basis_ast": "ast_value_argument",
                },
                "technical_or_control_input",
            ),
            (
                "input:setInputFiles:{ name: fileName, mimeType: 'application/pdf', buffer: examplePdfBuffer }",
                "getEnvelopeItemDropzoneInput(root).setInputFiles({ name: fileName, mimeType: 'application/pdf', buffer: examplePdfBuffer })",
                {
                    "input_source_ast": "file_upload_input",
                    "input_value_redacted": "mimeType=application/pdf",
                    "value_visibility_ast": "visible",
                    "input_channel_ast": "ui_file_upload",
                    "input_evidence_basis_ast": "ast_value_argument",
                },
                "domain_plausible_input",
            ),
        ]
        for name, raw, feature, expected in cases:
            with self.subTest(name=name):
                r = resolve_input_pattern(name, raw, feature=feature)
                self.assertEqual(r["input_plausibility"], expected)

    def test_structured_target_role_drives_plausibility_without_raw_guessing(self):
        cases = [
            (
                "credential env config",
                "input:type:Cypress.env",
                'cy.get(googleForm.googleClientId).type(Cypress.env("APPSMITH_OAUTH2_GOOGLE_CLIENT_ID"))',
                {
                    "input_source_ast": "environment_input",
                    "input_value_redacted": 'Cypress.env("APPSMITH_OAUTH2_GOOGLE_CLIENT_ID")',
                    "value_visibility_ast": "opaque",
                    "input_channel_ast": "ui_text_entry",
                    "input_target_role_ast": "credential_or_config_field",
                    "input_target_context_ast": "googleForm.googleClientId",
                    "input_value_expression_kind_ast": "call_expression",
                    "input_evidence_basis_ast": "ast_value_argument",
                },
                "domain_plausible_input",
            ),
            (
                "endpoint name config",
                "input:type:datasourceName",
                "cy.get('.t--edit-datasource-name input').clear().type(datasourceName, { force: true })",
                {
                    "input_source_ast": "variable_input",
                    "input_value_redacted": "datasourceName",
                    "value_visibility_ast": "opaque",
                    "input_channel_ast": "ui_text_entry",
                    "input_target_role_ast": "endpoint_or_resource_config_field",
                    "input_target_context_ast": "datasource name",
                    "input_value_expression_kind_ast": "identifier",
                    "input_endpoint_construction_ast": "resource_config_identifier",
                    "input_evidence_basis_ast": "ast_value_argument",
                },
                "technical_or_control_input",
            ),
            (
                "domain target test variable",
                "input:fill:testInput",
                "inputUrl.fill(testInput)",
                {
                    "input_source_ast": "variable_input",
                    "input_value_redacted": "testInput",
                    "value_visibility_ast": "opaque",
                    "input_channel_ast": "ui_text_entry",
                    "input_target_role_ast": "domain_text_field",
                    "input_target_context_ast": "inputUrl",
                    "input_value_expression_kind_ast": "identifier",
                    "input_evidence_basis_ast": "ast_value_argument",
                },
                "domain_plausible_input",
            ),
        ]
        for label, name, raw, feature, expected in cases:
            with self.subTest(label=label):
                r = resolve_input_pattern(name, raw, feature=feature)
                self.assertEqual(r["input_plausibility"], expected)


if __name__ == "__main__":
    unittest.main()
