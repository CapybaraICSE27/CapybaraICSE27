#!/usr/bin/env python3

"""Tests for RQ2 input plausibility."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from input_plausibility import (
    format_upload_display_value,
    format_value_for_display,
    map_input_plausibility_paper_label,
    parse_upload_object_metadata,
    resolve_input_plausibility,
    resolve_input_plausibility_detail,
    resolve_upload_visibility,
)


class TestInputPlausibility(unittest.TestCase):
    def test_placeholder(self):
        p, c, review = resolve_input_plausibility(
            value_redacted="asdf",
            field_context="Name",
            value_visibility="visible",
            input_source_class="literal_input",
        )
        self.assertEqual(p, "placeholder_or_dummy_input")
        self.assertEqual(c, "high")
        self.assertFalse(review)

    def test_non_semantic_opaque_identifier_is_not_observable(self):
        p, _, review = resolve_input_plausibility(
            value_redacted="opaqueValue",
            field_context="",
            value_visibility="opaque",
            input_source_class="variable_input",
        )
        self.assertEqual(p, "not_observable")
        self.assertFalse(review)

    def test_validation_empty(self):
        p, c, review = resolve_input_plausibility(
            value_redacted="",
            field_context="Email",
            value_visibility="visible",
            input_source_class="literal_input",
        )
        self.assertEqual(p, "validation_or_edge_case_input")
        self.assertEqual(c, "high")
        self.assertFalse(review)

    def test_keyboard_special(self):
        p, c, review = resolve_input_plausibility(
            value_redacted="{enter}",
            field_context="",
            value_visibility="visible",
            input_source_class="literal_input",
            input_channel="keyboard_entry",
        )
        self.assertEqual(p, "technical_or_control_input")
        self.assertEqual(c, "high")
        self.assertFalse(review)

    def test_test_prefix_dummy(self):
        p, c, review = resolve_input_plausibility(
            value_redacted="testcity",
            field_context="city",
            value_visibility="visible",
            input_source_class="literal_input",
        )
        self.assertEqual(p, "domain_plausible_input")
        self.assertEqual(c, "medium")

    def test_natural_language_message(self):
        p, c, review = resolve_input_plausibility(
            value_redacted="message to private channel",
            field_context="body",
            value_visibility="visible",
            input_source_class="literal_input",
        )
        self.assertEqual(p, "domain_plausible_input")

    def test_file_upload_path(self):
        p, c, review = resolve_input_plausibility(
            value_redacted="cypress/fixtures/testFile.mov",
            field_context="file",
            value_visibility="visible",
            input_source_class="file_upload_input",
            input_channel="ui_file_upload",
        )
        self.assertEqual(p, "domain_plausible_input")
        self.assertEqual(c, "medium")
        self.assertFalse(review)

    def test_file_upload_path_expression(self):
        for value in (
            "getSampleFilePath(\"riot.png\")",
            "path.resolve(dirname, './image.png')",
            "README.md",
        ):
            with self.subTest(value=value):
                p, c, review = resolve_input_plausibility(
                    value_redacted=value,
                    field_context="input[type=file]",
                    value_visibility="visible",
                    input_source_class="file_upload_input",
                    input_channel="ui_file_upload",
                )
                self.assertEqual(p, "domain_plausible_input")
                self.assertEqual(c, "medium")
                self.assertFalse(review)

    def test_generated_opaque_domain_member(self):
        p, c, review = resolve_input_plausibility(
            value_redacted="organizationParams.fullName",
            field_context="",
            value_visibility="opaque",
            input_source_class="generated_input",
        )
        self.assertEqual(p, "domain_plausible_input")
        self.assertEqual(c, "medium")

    def test_format_empty_string(self):
        self.assertEqual(format_value_for_display(""), "<EMPTY_STRING>")
        self.assertEqual(format_value_for_display("   "), "<WHITESPACE_ONLY>")

    def test_upload_object_metadata_visibility(self):
        raw = "[{ contents: 'x', fileName: 'report.pdf', mimeType: 'application/pdf' }]"
        self.assertEqual(
            resolve_upload_visibility(raw, "unknown"),
            "partially_visible",
        )
        meta = parse_upload_object_metadata(raw)
        self.assertEqual(meta["fileName"], "report.pdf")
        self.assertEqual(meta["mimeType"], "application/pdf")

    def test_upload_object_metadata_plausibility(self):
        raw = "[{ contents, fileName: 'photo.png', mimeType: 'image/png' }]"
        p, c, review = resolve_input_plausibility(
            value_redacted=raw,
            field_context="",
            value_visibility="unknown",
            input_source_class="file_upload_input",
        )
        self.assertEqual(p, "domain_plausible_input")
        self.assertEqual(c, "medium")
        self.assertFalse(review)

    def test_upload_object_literal_is_not_keyboard_token(self):
        raw = "{ name: fileName, mimeType: 'application/pdf', buffer: examplePdfBuffer }"
        p, c, review = resolve_input_plausibility(
            value_redacted=raw,
            field_context="setInputFiles",
            value_visibility="visible",
            input_source_class="file_upload_input",
            input_channel="ui_file_upload",
        )
        self.assertEqual(p, "domain_plausible_input")
        self.assertEqual(c, "medium")
        self.assertFalse(review)

    def test_upload_limit_filename_is_validation_edge_case(self):
        p, c, review = resolve_input_plausibility(
            value_redacted="{ name: 'exceed-limit-test.csv', buffer: Buffer.from(csvFile), mimeType: 'text/csv' }",
            field_context="setInputFiles",
            value_visibility="visible",
            input_source_class="file_upload_input",
            input_channel="ui_file_upload",
        )
        self.assertEqual(p, "validation_or_edge_case_input")
        self.assertEqual(c, "medium")
        self.assertTrue(review)

    def test_upload_object_with_variable_metadata_is_domain_plausible(self):
        p, c, review = resolve_input_plausibility(
            value_redacted="{ name: fileName, mimeType, buffer: fileBuffer, }",
            field_context="fileInput.setInputFiles",
            value_visibility="visible",
            input_source_class="file_upload_input",
            input_channel="ui_file_upload",
        )
        self.assertEqual(p, "domain_plausible_input")
        self.assertEqual(c, "medium")
        self.assertTrue(review)

    def test_upload_object_display(self):
        raw = "[{ fileName: 'doc.pdf', mimeType: 'application/pdf' }]"
        self.assertEqual(
            format_upload_display_value(raw),
            "fileName=doc.pdf; mimeType=application/pdf",
        )

    def test_api_seed_default_technical(self):
        p, c, review = resolve_input_plausibility(
            value_redacted="testUser.internalId",
            field_context="",
            value_visibility="opaque",
            input_source_class="api_seed_input",
        )
        self.assertEqual(p, "technical_or_control_input")
        self.assertFalse(review)

    def test_api_seed_domain_with_field_context(self):
        p, c, review = resolve_input_plausibility(
            value_redacted="testUser.email",
            field_context="email",
            value_visibility="opaque",
            input_source_class="api_seed_input",
        )
        self.assertEqual(p, "domain_plausible_input")
        self.assertTrue(review)

    def test_api_seed_channel_team_names_are_domain_plausible(self):
        for value in ("channelName", "channel.display_name", "testChannelName", "team.display_name"):
            with self.subTest(value=value):
                p, c, review = resolve_input_plausibility(
                    value_redacted=value,
                    field_context="",
                    value_visibility="opaque",
                    input_source_class="api_seed_input",
                )
                self.assertEqual(p, "domain_plausible_input")
                self.assertEqual(c, "medium")
                self.assertTrue(review)

    def test_generated_random_template(self):
        p, c, review = resolve_input_plausibility(
            value_redacted="${randomNumber(10000, 50000)}",
            field_context="amount",
            value_visibility="visible",
            input_source_class="generated_input",
        )
        self.assertEqual(p, "technical_or_control_input")
        self.assertFalse(review)

    def test_generated_random_template_opaque(self):
        p, c, review = resolve_input_plausibility(
            value_redacted="${randomIp()}/${randomNumber(0, 32)}",
            field_context="",
            value_visibility="opaque",
            input_source_class="generated_input",
        )
        self.assertEqual(p, "technical_or_control_input")
        self.assertFalse(review)

    def test_latest_audit_visible_credentials_and_domain_expressions(self):
        cases = [
            (
                "token",
                "MFA Code",
                "opaque",
                "api_seed_input",
                "ui_text_entry",
                "domain_plausible_input",
            ),
            (
                'Cypress.env("USERNAME")',
                "Email",
                "opaque",
                "environment_input",
                "ui_text_entry",
                "domain_plausible_input",
            ),
            (
                'Cypress.env("PASSWORD")',
                "Password",
                "opaque",
                "environment_input",
                "ui_text_entry",
                "domain_plausible_input",
            ),
            (
                'new URL("/modern-challenge-completed", process.env.API_LOCATION).toString()',
                "",
                "opaque",
                "environment_input",
                "api_request_body",
                "technical_or_control_input",
            ),
            (
                'cleanPhoneNumber || ""',
                "Search by Patient Phone Number",
                "unknown",
                "unknown_input",
                "ui_text_entry",
                "domain_plausible_input",
            ),
            (
                'description + " - edited"',
                "Description",
                "unknown",
                "variable_input",
                "ui_text_entry",
                "domain_plausible_input",
            ),
            (
                "organizationParams.shortName",
                "Organization",
                "opaque",
                "variable_from_external_file",
                "ui_text_entry",
                "domain_plausible_input",
            ),
            (
                "ldapUser.username",
                "",
                "opaque",
                "variable_from_external_file",
                "ui_text_entry",
                "domain_plausible_input",
            ),
        ]
        for value, field, visibility, source, channel, expected in cases:
            with self.subTest(value=value):
                p, c, review = resolve_input_plausibility(
                    value_redacted=value,
                    field_context=field,
                    value_visibility=visibility,
                    input_source_class=source,
                    input_channel=channel,
                )
                self.assertEqual(p, expected)
                self.assertIn(c, {"medium", "high"})

    def test_latest_audit_edge_dummy_and_keyboard_plausibility(self):
        cases = [
            (
                "billing.invalidvisa.cvc",
                "CVC",
                "opaque",
                "variable_from_external_file",
                "ui_text_entry",
                "validation_or_edge_case_input",
            ),
            (
                "faker.lorem.sentence()",
                "Description",
                "opaque",
                "generated_input",
                "ui_text_entry",
                "placeholder_or_dummy_input",
            ),
            (
                "Test title client side",
                "Title",
                "visible",
                "literal_input",
                "ui_text_entry",
                "placeholder_or_dummy_input",
            ),
            (
                'this.isMac ? "{meta}A" : "{ctrl}A"',
                "",
                "unknown",
                "unknown_input",
                "ui_text_entry",
                "technical_or_control_input",
            ),
            (
                'agHelper.isMac ? "{meta}Z" : "{ctrl}Z"',
                "",
                "unknown",
                "unknown_input",
                "keyboard_entry",
                "technical_or_control_input",
            ),
        ]
        for value, field, visibility, source, channel, expected in cases:
            with self.subTest(value=value):
                p, c, review = resolve_input_plausibility(
                    value_redacted=value,
                    field_context=field,
                    value_visibility=visibility,
                    input_source_class=source,
                    input_channel=channel,
                )
                self.assertEqual(p, expected)
                self.assertIn(c, {"medium", "high"})

    def test_latest_audit_partially_visible_external_domain_members(self):
        for value, field in (
            ("organizationParams.shortName", "slug"),
            ("this.dataSet.ylabel", ""),
            ("table.widgetName", ""),
        ):
            with self.subTest(value=value):
                p, c, review = resolve_input_plausibility(
                    value_redacted=value,
                    field_context=field,
                    value_visibility="partially_visible",
                    input_source_class="variable_from_external_file",
                    input_channel="ui_text_entry",
                )
                self.assertEqual(p, "domain_plausible_input")
                self.assertEqual(c, "medium")

    def test_latest_review_upload_and_visible_context_plausibility(self):
        cases = [
            ("validImagePath", "input[type='file']", "opaque", "file_upload_input", "ui_file_upload", "domain_plausible_input"),
            ("testPluginPath", "FILE_INPUT", "opaque", "file_upload_input", "ui_file_upload", "domain_plausible_input"),
            ("videoPaths", 'input[type="file"]', "opaque", "file_upload_input", "ui_file_upload", "domain_plausible_input"),
            ("testUser.id", "#input_searchTerm", "opaque", "api_seed_input", "ui_text_entry", "domain_plausible_input"),
            ("searchTerm", "Search Box", "opaque", "generated_input", "ui_text_entry", "domain_plausible_input"),
            ("ldapUser.username", "Search users", "opaque", "variable_from_external_file", "ui_text_entry", "domain_plausible_input"),
            ("TestPassword123!", "currentPassword", "visible", "literal_input", "ui_text_entry", "domain_plausible_input"),
        ]
        for value, field, visibility, source, channel, expected in cases:
            with self.subTest(value=value, field=field):
                p, c, review = resolve_input_plausibility(
                    value_redacted=value,
                    field_context=field,
                    value_visibility=visibility,
                    input_source_class=source,
                    input_channel=channel,
                )
                self.assertEqual(p, expected)
                self.assertIn(c, {"medium", "high"})

    def test_latest_review_endpoint_keyboard_and_dummy_precedence(self):
        cases = [
            ("url", "#url", "opaque", "environment_input", "ui_text_entry", "technical_or_control_input"),
            ("url + parameters", "apiwidget.editResourceUrl", "opaque", "variable_input", "ui_text_entry", "technical_or_control_input"),
            (
                "this.dataSet.paginationUrl + testdata.prevUrl",
                "apiPaginationPrevText",
                "opaque",
                "variable_from_external_file",
                "ui_text_entry",
                "technical_or_control_input",
            ),
            ('url + "{enter}"', "image-url-input", "opaque", "variable_input", "ui_text_entry", "technical_or_control_input"),
            ("'{leftArrow}'.repeat('27'.length)", "@input", "visible", "literal_input", "ui_text_entry", "technical_or_control_input"),
            ("Dummy college 2", "college input", "visible", "literal_input", "ui_text_entry", "placeholder_or_dummy_input"),
            ("Test room", "Name", "visible", "literal_input", "ui_text_entry", "placeholder_or_dummy_input"),
            ("red", "fontcolor", "visible", "literal_input", "ui_text_entry", "domain_plausible_input"),
            ("testPrefix", "Task name", "opaque", "generated_input", "ui_text_entry", "domain_plausible_input"),
        ]
        for value, field, visibility, source, channel, expected in cases:
            with self.subTest(value=value, field=field):
                p, c, review = resolve_input_plausibility(
                    value_redacted=value,
                    field_context=field,
                    value_visibility=visibility,
                    input_source_class=source,
                    input_channel=channel,
                )
                self.assertEqual(p, expected)
                self.assertIn(c, {"medium", "high"})

    def test_non_keyboard_conditional_upload_expression_stays_upload(self):
        p, c, review = resolve_input_plausibility(
            value_redacted='fileNames.map((file) => file.endsWith(".xlsx") ? `tests/fixtures/${file}` : `tests/fixtures/images/${file}`)',
            field_context='input[type="file"]',
            value_visibility="opaque",
            input_source_class="file_upload_input",
            input_channel="ui_file_upload",
        )
        self.assertEqual(p, "domain_plausible_input")
        self.assertEqual(c, "medium")
        self.assertFalse(review)

    def test_reviewed_file_upload_limit_names_are_validation_edges(self):
        cases = [
            ("{ name: 'exceed-limit-test.csv', buffer: Buffer.from(csvFile), mimeType: 'text/csv' }", "fileInput.setInputFiles"),
        ]
        for value, field in cases:
            with self.subTest(value=value):
                p, c, review = resolve_input_plausibility(
                    value_redacted=value,
                    field_context=field,
                    value_visibility="opaque",
                    input_source_class="file_upload_input",
                    input_channel="ui_file_upload",
                )
                self.assertEqual(p, "validation_or_edge_case_input")
                self.assertEqual(c, "medium")

    def test_invalid_upload_path_is_validation_edge_not_domain_upload(self):
        p, c, review = resolve_input_plausibility(
            value_redacted="invalidFilePath",
            field_context="input[type=file]",
            value_visibility="opaque",
            input_source_class="file_upload_input",
            input_channel="ui_file_upload",
        )
        self.assertEqual(p, "validation_or_edge_case_input")
        self.assertEqual(c, "medium")
        self.assertTrue(review)

    def test_reviewed_focused_member_paths_are_domain_inputs_without_locator_context(self):
        cases = [
            "mockTicket.summary",
            "nodeBal.ipv4",
            "mockSSHKey.ssh_key",
            "newUser",
        ]
        for value in cases:
            with self.subTest(value=value):
                p, c, review = resolve_input_plausibility(
                    value_redacted=value,
                    field_context="",
                    value_visibility="opaque",
                    input_source_class="generated_input",
                    input_channel="ui_text_entry",
                )
                self.assertEqual(p, "domain_plausible_input")
                self.assertEqual(c, "medium")

    def test_weak_visible_literals_without_target_context_are_indeterminate(self):
        for value in ("abc", "log", "test Mandatory", "wombat@mail.mail"):
            with self.subTest(value=value):
                p, c, review = resolve_input_plausibility(
                    value_redacted=value,
                    field_context="",
                    value_visibility="visible",
                    input_source_class="literal_input",
                    input_channel="ui_text_entry",
                )
                self.assertIn(p, {"not_observable", "unclear"})
                self.assertEqual(
                    map_input_plausibility_paper_label(p),
                    "indeterminate_or_insufficient_evidence",
                )
                self.assertTrue(review)

    def test_audited_member_paths_are_domain_plausible_even_when_target_is_focused(self):
        for value in (
            "zone.domain",
            "mockFormFields.publicInfo",
            "mockFormFields.useCase",
            "mockFormFields.numberOfEntities",
            "monitorUrl",
            "entityTag",
        ):
            with self.subTest(value=value):
                p, c, review = resolve_input_plausibility(
                    value_redacted=value,
                    field_context="",
                    value_visibility="opaque",
                    input_source_class="variable_input",
                    input_channel="ui_text_entry",
                )
                self.assertEqual(p, "domain_plausible_input")
                self.assertEqual(c, "medium")
                self.assertTrue(review)

    def test_audited_editor_filler_literals_are_placeholder_dummy(self):
        for value in ("* foobar", "- foobar", "> foobar", '"hello"', "+ foobar"):
            with self.subTest(value=value):
                p, c, review = resolve_input_plausibility(
                    value_redacted=value,
                    field_context=".tiptap",
                    value_visibility="visible",
                    input_source_class="literal_input",
                    input_channel="ui_text_entry",
                )
                self.assertEqual(p, "placeholder_or_dummy_input")
                self.assertIn(c, {"medium", "high"})

    def test_editor_targeted_markdownish_text_is_domain_plausible(self):
        for value in ("`$foobar`", "Test", "green serif"):
            with self.subTest(value=value):
                p, c, review = resolve_input_plausibility(
                    value_redacted=value,
                    field_context=".tiptap",
                    value_visibility="visible",
                    input_source_class="literal_input",
                    input_channel="ui_text_entry",
                )
                self.assertEqual(p, "domain_plausible_input")
                self.assertEqual(c, "medium")

    def test_keyboard_press_and_targetless_keyboard_type_follow_codebook(self):
        for value in ("a", "1"):
            with self.subTest(value=value):
                p, c, review = resolve_input_plausibility(
                    value_redacted=value,
                    field_context="",
                    value_visibility="visible",
                    input_source_class="literal_input",
                    input_channel="keyboard_press",
                )
                self.assertEqual(p, "technical_or_control_input")
                self.assertEqual(
                    map_input_plausibility_paper_label(p),
                    "technical_or_configuration_or_control_input",
                )

        p, c, review = resolve_input_plausibility(
            value_redacted="test",
            field_context="",
            value_visibility="visible",
            input_source_class="literal_input",
            input_channel="keyboard_entry",
        )
        self.assertEqual(p, "placeholder_or_dummy_input")

        for value in ("", "None"):
            with self.subTest(value=value):
                p, c, review = resolve_input_plausibility(
                    value_redacted=value,
                    field_context="None",
                    value_visibility="opaque",
                    input_source_class="literal_input",
                    input_channel="keyboard_input",
                )
                self.assertEqual(p, "technical_or_control_input")
                self.assertEqual(
                    map_input_plausibility_paper_label(p),
                    "technical_or_configuration_or_control_input",
                )

    def test_config_fields_and_preservation_edges_are_not_domain_by_default(self):
        p, c, review = resolve_input_plausibility(
            value_redacted="8080",
            field_context="[id=port-1]",
            value_visibility="visible",
            input_source_class="literal_input",
            input_channel="ui_text_entry",
        )
        self.assertEqual(p, "technical_or_control_input")
        self.assertEqual(
            map_input_plausibility_paper_label(p),
            "technical_or_configuration_or_control_input",
        )

        for value in (
            "(process.env.INGESTION_URL || process.env.ZO_BASE_URL || 'http://localhost:5080').replace(/\\/$/, '')",
            "updatedDomain",
        ):
            with self.subTest(value=value):
                p, c, review = resolve_input_plausibility(
                    value_redacted=value,
                    field_context="Object Storage Endpoint endpoint_or_resource_config_field",
                    value_visibility="opaque",
                    input_source_class="environment_input" if "process.env" in value else "variable_input",
                    input_channel="ui_text_entry",
                )
                self.assertEqual(p, "technical_or_control_input")
                self.assertEqual(
                    map_input_plausibility_paper_label(p),
                    "technical_or_configuration_or_control_input",
                )

        p, c, review = resolve_input_plausibility(
            value_redacted="should-preserve",
            field_context="#field-prefix",
            value_visibility="visible",
            input_source_class="literal_input",
            input_channel="ui_text_entry",
        )
        self.assertEqual(p, "validation_or_edge_case_input")

    def test_949pm_endpoint_resource_config_rows_are_technical_control(self):
        cases = [
            ("route", "/Select Route/i", "opaque", "variable_input"),
            ("https://jsonplaceholder.typicode.com/", "baseUrlInput", "visible", "literal_input"),
            ("datasource", "apiwidget.resourceUrl", "opaque", "variable_input"),
            ("URL", "datasourceEditor.url", "opaque", "variable_input"),
            ("datasourceName", ".t--edit-datasource-name input", "opaque", "variable_input"),
            ("advancedConfigurationParams.startFrame", "#startFrame", "opaque", "variable_input"),
            ("advancedConfigurationParams.overlapSize", "#overlapSize", "opaque", "variable_input"),
            ("columns", 'input[data-test-id="table-modal-columns"]', "opaque", "variable_input"),
        ]
        for value, context, visibility, source in cases:
            with self.subTest(value=value, context=context):
                p, c, review = resolve_input_plausibility(
                    value_redacted=value,
                    field_context=context,
                    value_visibility=visibility,
                    input_source_class=source,
                    input_channel="ui_text_entry",
                )
                self.assertEqual(p, "technical_or_control_input")
                self.assertEqual(
                    map_input_plausibility_paper_label(p),
                    "technical_or_configuration_or_control_input",
                )

    def test_949pm_helper_member_targets_can_be_domain_plausible(self):
        cases = [
            ("i", "table._filterInputValue"),
            ("bind", "publish.inputValue"),
            ("A", "cy.uiGetReplyTextBox"),
            ("projectId", "promptInput"),
            ("enthusiastic", "toneSelect"),
            ("newSerialNumber", "serialNumberInput"),
            ("newModelNumber", "modelNumberInput"),
            ("dosageForm", "Select Dosage Form"),
        ]
        for value, context in cases:
            with self.subTest(value=value, context=context):
                p, c, review = resolve_input_plausibility(
                    value_redacted=value,
                    field_context=context,
                    value_visibility="visible" if value in {"i", "bind", "A", "enthusiastic"} else "opaque",
                    input_source_class="literal_input" if value in {"i", "bind", "A", "enthusiastic"} else "variable_input",
                    input_channel="ui_text_entry",
                )
                self.assertEqual(p, "domain_plausible_input")

    def test_949pm_keyboard_control_and_html_filler_precedence(self):
        for value, channel in (("1", "keyboard_press"), ("2", "keyboard_press"), ("7", "keyboard_press"), ("{enter}", "keyboard_entry")):
            with self.subTest(value=value):
                p, c, review = resolve_input_plausibility(
                    value_redacted=value,
                    field_context='textbox name="Survey Title"',
                    value_visibility="visible",
                    input_source_class="literal_input",
                    input_channel=channel,
                )
                self.assertEqual(p, "technical_or_control_input")

        p, c, review = resolve_input_plausibility(
            value_redacted='html`<h1>Foo</h1><pre>const x = "hello world";</pre><p>Hello <b><i>world</i></b></p>`',
            field_context="",
            value_visibility="visible",
            input_source_class="literal_input",
            input_channel="keyboard_entry",
        )
        self.assertEqual(p, "placeholder_or_dummy_input")

    def test_949pm_negative_search_query_stays_validation_edge(self):
        p, c, review = resolve_input_plausibility(
            value_redacted="nonMatchingQuery",
            field_context="searchInput",
            value_visibility="opaque",
            input_source_class="variable_input",
            input_channel="ui_text_entry",
        )
        self.assertEqual(p, "validation_or_edge_case_input")

    def test_408pm_tail_keyboard_upload_editor_and_member_paths(self):
        for value in ("Control+Space", "s", "3", " "):
            with self.subTest(value=value):
                p, c, review = resolve_input_plausibility(
                    value_redacted=value,
                    field_context="",
                    value_visibility="visible",
                    input_source_class="literal_input",
                    input_channel="keyboard_press",
                )
                self.assertEqual(p, "technical_or_control_input")
                self.assertEqual(c, "high")

        upload_raw = """[
            path.resolve(dirname, './image.png'),
            path.resolve(dirname, './2mb.jpg'), // exceeds 2MB
            path.resolve(dirname, './small.png')
        ]"""
        p, c, review = resolve_input_plausibility(
            value_redacted=upload_raw,
            field_context="bulkUploadModal .dropzone input[type=\"file\"] setInputFiles",
            value_visibility="visible",
            input_source_class="file_upload_input",
            input_channel="ui_file_upload",
        )
        self.assertEqual(p, "domain_plausible_input")

        p, c, review = resolve_input_plausibility(
            value_redacted="item1",
            field_context=".sv-list__input",
            value_visibility="visible",
            input_source_class="literal_input",
            input_channel="ui_text_entry",
        )
        self.assertEqual(p, "placeholder_or_dummy_input")

        p, c, review = resolve_input_plausibility(
            value_redacted="---",
            field_context=".tiptap",
            value_visibility="visible",
            input_source_class="literal_input",
            input_channel="ui_text_entry",
        )
        self.assertEqual(p, "technical_or_control_input")

        p, c, review = resolve_input_plausibility(
            value_redacted="newAccountData['tax_id']",
            field_context="",
            value_visibility="opaque",
            input_source_class="variable_input",
            input_channel="ui_text_entry",
        )
        self.assertEqual(p, "domain_plausible_input")

    def test_paper_label_merges_indeterminate_and_technical_config_control(self):
        self.assertEqual(
            map_input_plausibility_paper_label("not_observable"),
            "indeterminate_or_insufficient_evidence",
        )
        self.assertEqual(
            map_input_plausibility_paper_label("unclear"),
            "indeterminate_or_insufficient_evidence",
        )
        self.assertEqual(
            map_input_plausibility_paper_label("technical_or_control_input"),
            "technical_or_configuration_or_control_input",
        )

    def test_plausibility_detail_reports_codebook_path(self):
        detail = resolve_input_plausibility_detail(
            value_redacted="validImagePath",
            field_context="input[type='file'] setInputFiles",
            value_visibility="opaque",
            input_source_class="file_upload_input",
            input_channel="ui_file_upload",
        )
        self.assertEqual(detail["input_plausibility"], "domain_plausible_input")
        self.assertEqual(detail["input_plausibility_codebook_path"], "upload_consumer_domain_path")

    def test_keyboard_control_context_wins_over_numeric_boundary(self):
        for value, context in (
            ("1", 'keyboard_control_target page.keyboard.press("1") input:press:1'),
            ("8", "keyboard_control_target page.keyboard.press('8') input:press:8"),
            ("7", 'keyboard_control_target page.getByRole("textbox").press("7") input:press:7'),
        ):
            with self.subTest(value=value, context=context):
                detail = resolve_input_plausibility_detail(
                    value_redacted=value,
                    field_context=context,
                    value_visibility="visible",
                    input_source_class="literal_input",
                    input_channel="keyboard_entry",
                )
                self.assertEqual(detail["input_plausibility"], "technical_or_control_input")
                self.assertEqual(
                    detail["input_plausibility_paper_label"],
                    "technical_or_configuration_or_control_input",
                )
                self.assertEqual(detail["input_plausibility_codebook_path"], "keyboard_or_control_token")

    def test_355am_user_facing_settings_are_domain_not_config(self):
        cases = [
            ("siteName", "TeamSettings.SiteNameinput"),
            ("text", "#channel_settings_header_textbox"),
        ]
        for value, context in cases:
            with self.subTest(value=value, context=context):
                detail = resolve_input_plausibility_detail(
                    value_redacted=value,
                    field_context=context,
                    value_visibility="opaque",
                    input_source_class="variable_input",
                    input_channel="ui_text_entry",
                )
                self.assertEqual(detail["input_plausibility"], "domain_plausible_input")
                self.assertEqual(detail["input_plausibility_paper_label"], "domain_plausible_input")

    def test_355am_domain_member_targets_and_config_overrides(self):
        domain_cases = [
            ("bannerBgColor", "input"),
            ("value", "ads v2 select dropdown .ads v2 input input section input"),
            ("attributes.values", "cvat attribute values input"),
        ]
        for value, context in domain_cases:
            with self.subTest(value=value, context=context):
                detail = resolve_input_plausibility_detail(
                    value_redacted=value,
                    field_context=context,
                    value_visibility="opaque",
                    input_source_class="variable_input",
                    input_channel="ui_text_entry",
                )
                self.assertEqual(detail["input_plausibility"], "domain_plausible_input")

        config_cases = [
            ("dummyBugTrackerUrl", "#bugTracker"),
            ("data.manifest", '[placeholder="manifest.jsonl"]'),
            ("createPolygonParams.numberOfPoints", "ant input number input"),
        ]
        for value, context in config_cases:
            with self.subTest(value=value, context=context):
                detail = resolve_input_plausibility_detail(
                    value_redacted=value,
                    field_context=context,
                    value_visibility="opaque",
                    input_source_class="variable_input",
                    input_channel="ui_text_entry",
                )
                self.assertEqual(detail["input_plausibility"], "technical_or_control_input")
                self.assertEqual(
                    detail["input_plausibility_paper_label"],
                    "technical_or_configuration_or_control_input",
                )

    def test_355am_validation_member_name_outranks_settings_context(self):
        detail = resolve_input_plausibility_detail(
            value_redacted="settingsObject.usernameTooShort",
            field_context="",
            value_visibility="opaque",
            input_source_class="variable_input",
            input_channel="ui_text_entry",
        )
        self.assertEqual(detail["input_plausibility"], "validation_or_edge_case_input")


if __name__ == "__main__":
    unittest.main()
