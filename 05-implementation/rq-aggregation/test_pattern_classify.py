#!/usr/bin/env python3
"""Tests for RQ3 pattern classifiers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pattern_classify import (
    classify_auto_retry_capabilities,
    classify_locator_from_ui_action,
    classify_sync_pattern,
    classify_workflow_from_feature,
    resolve_workflow_pattern,
    infer_workflow_archetype,
    infer_workflow_archetype_detail,
    is_assertion_retry_sync_feature,
    is_page_object_setup_or_utility_call,
    is_retryable_ui_assertion,
    positive_resilience_signals,
    resolve_locator_pattern,
    resolve_wait_pattern,
    sync_flags_for_pattern,
    sync_target_for_pattern,
    locator_ast_audit_mismatch_type,
)


class TestLocatorPatterns(unittest.TestCase):
    def test_playwright_getbyrole_in_click_chain(self):
        r = classify_locator_from_ui_action(
            "click",
            "await page.getByRole('button', { name: 'Save' }).click()",
            "Playwright",
            "test_body",
            0,
            "ui_action",
            "click",
        )
        self.assertTrue(r["locator_present"])
        self.assertEqual(r["normalized_strategy"], "role_or_accessibility")
        self.assertEqual(r["locator_composition"], "direct_chain")
        self.assertFalse(r["has_positional_refinement"])

    def test_page_locator_submit_is_direct_chain(self):
        r = classify_locator_from_ui_action(
            "click",
            "await page.locator('#submit').click()",
            "Playwright",
            "test_body",
            0,
            "ui_action",
            "click",
        )
        self.assertEqual(r["locator_composition"], "direct_chain")
        self.assertFalse(r["has_positional_refinement"])
        self.assertEqual(r["selector_literal_kind"], "id")
        self.assertEqual(r["normalized_strategy"], "css_selector")

    def test_page_locator_text_submit(self):
        r = classify_locator_from_ui_action(
            "click",
            "await page.locator('text=Submit').click()",
            "Playwright",
            "test_body",
            0,
            "ui_action",
            "click",
        )
        self.assertEqual(r["selector_literal_kind"], "text")
        self.assertEqual(r["robustness_signal"], "readable_text_signal")

    def test_page_locator_xpath(self):
        r = classify_locator_from_ui_action(
            "click",
            "await page.locator('xpath=//button').click()",
            "Playwright",
            "test_body",
            0,
            "ui_action",
            "click",
        )
        self.assertEqual(r["selector_literal_kind"], "xpath")
        self.assertEqual(r["robustness_signal"], "positional_or_structural_signal")

    def test_cypress_datacy(self):
        r = classify_locator_from_ui_action(
            "cy.get",
            "cy.get('[data-cy=submit]').click()",
            "Cypress",
            "test_body",
            0,
            "ui_action",
            "click",
        )
        self.assertEqual(r["normalized_strategy"], "test_id_or_data_contract")
        self.assertTrue(positive_resilience_signals(r["robustness_signal"]))

    def test_page_object_mediated(self):
        r = classify_locator_from_ui_action(
            "loginPage.submit",
            "await loginPage.submit()",
            "Playwright",
            "test_body",
            0,
            "ui_action",
            "click",
        )
        self.assertEqual(r["normalized_strategy"], "page_object_mediated")
        self.assertEqual(r["locator_composition"], "page_object_mediated")

    def test_page_keyboard_not_locator_event(self):
        r = classify_locator_from_ui_action(
            "page.keyboard.press",
            "await page.keyboard.press('Enter')",
            "Playwright",
            "imported_helper",
            1,
            "ui_action",
            "keyboard_input",
        )
        self.assertFalse(r["locator_present"])

    def test_page_evaluate_not_locator_event(self):
        r = classify_locator_from_ui_action(
            "page.evaluate",
            "await page.evaluate(() => navigator.clipboard.readText())",
            "Playwright",
            "imported_helper",
            1,
            "ui_action",
            "click",
        )
        self.assertFalse(r["locator_present"])

    def test_framework_page_instance_ast_not_page_object_mediated(self):
        r = resolve_locator_pattern(
            "userPage.getByLabel",
            "await userPage.getByLabel('Username').fill(username)",
            "Playwright",
            "test_body",
            0,
            "ui_action",
            "text_input",
            feature={
                "locator_strategy_ast": "label_or_form_affordance",
                "locator_composition_ast": "direct_chain",
                "locator_api_ast": "getByLabel",
                "page_symbol_origin_ast": "framework_page_instance",
            },
        )
        self.assertTrue(r["locator_present"])
        self.assertEqual(r["normalized_strategy"], "label_or_form_affordance")
        self.assertNotEqual(r["normalized_strategy"], "page_object_mediated")

    def test_wait_for_page_helper_not_page_object_workflow(self):
        r = resolve_workflow_pattern(
            "waitForDashboardPage",
            "await waitForDashboardPage(page)",
            "Playwright",
            "test_body",
            0,
            "helper_call",
            "",
            True,
        )
        self.assertNotIn(r["abstraction_kind"], ("page_object", "page_object_model"))

    def test_getbytext_not_class_literal(self):
        r = classify_locator_from_ui_action(
            "getByText",
            "page.getByText('Submit')",
            "Playwright",
            "test_body",
            0,
            "ui_action",
            "locator_query",
        )
        self.assertEqual(r["normalized_strategy"], "text_content")
        self.assertIn(r["selector_literal_kind"], ("text", "unknown"))

    def test_getbydatacy(self):
        r = classify_locator_from_ui_action(
            "getByDataCy",
            "page.getByDataCy('submit-btn').click()",
            "Playwright",
            "test_body",
            0,
            "ui_action",
            "click",
        )
        self.assertEqual(r["normalized_strategy"], "test_id_or_data_contract")

    def test_findbyattribute_aria_label(self):
        r = classify_locator_from_ui_action(
            "findByAttribute",
            "findByAttribute('aria-label', 'Save').click()",
            "Cypress",
            "test_body",
            0,
            "ui_action",
            "click",
        )
        self.assertEqual(r["normalized_strategy"], "label_or_form_affordance")

    def test_findbyplaceholdertext(self):
        r = classify_locator_from_ui_action(
            "findByPlaceholderText",
            "findByPlaceholderText('Email').type('a@b.c')",
            "Cypress",
            "test_body",
            0,
            "ui_action",
            "text_input",
        )
        self.assertEqual(r["normalized_strategy"], "placeholder_or_alt_title")

    def test_getbycls(self):
        r = classify_locator_from_ui_action(
            "getByCls",
            "getByCls('btn-primary').click()",
            "Cypress",
            "test_body",
            0,
            "ui_action",
            "click",
        )
        self.assertEqual(r["normalized_strategy"], "css_selector")

    def test_locator_strategy_uses_underlying_selector_channel(self):
        cases = [
            (
                "Playwright",
                "page.locator",
                "page.locator('.step-nav.app-header__step-nav .step-nav__last')",
                "css_selector",
                "class",
            ),
            (
                "Playwright",
                "page.locator",
                "page.locator('[data-test-frame-uid]')",
                "test_id_or_data_contract",
                "test_id",
            ),
            (
                "Cypress",
                "cy.getBySelLike",
                'cy.getBySelLike("transaction-item").first().click({ force: true })',
                "test_id_or_data_contract",
                "test_id",
            ),
            (
                "Cypress",
                "cy.getBySelLike",
                "cy.getBySelLike(feed.tab).click()",
                "test_id_or_data_contract",
                "test_id",
            ),
            (
                "Playwright",
                "getByAriaLabel",
                "getByAriaLabel(page, `Hide ${data.accounts[1].name}`).click()",
                "label_or_form_affordance",
                "label",
            ),
            (
                "Cypress",
                "ui.button.findByTitle",
                "ui.button.findByTitle(ip).should('be.visible')",
                "placeholder_or_alt_title",
                "title",
            ),
            (
                "Playwright",
                "page.locator",
                'page.locator(\'textarea, [placeholder*="message"]\')',
                "placeholder_or_alt_title",
                "placeholder",
            ),
        ]
        for framework, name, raw, expected_strategy, expected_selector in cases:
            with self.subTest(raw=raw):
                r = classify_locator_from_ui_action(
                    name,
                    raw,
                    framework,
                    "test_body",
                    0,
                    "ui_action",
                    "click",
                )
                self.assertEqual(r["normalized_strategy"], expected_strategy)
                self.assertEqual(r["selector_literal_kind"], expected_selector)

    def test_audited_selector_literal_kind_tail_cases(self):
        cases = [
            (
                "Playwright",
                "tagbox2.locator",
                'await tagbox2.locator(".sv-list").evaluate((el) => el.scrollTop)',
                "class",
            ),
            (
                "Cypress",
                "cy.get",
                'cy.get("[ui5-textarea]").type("x")',
                "css_compound",
            ),
            (
                "Cypress",
                "cy.get",
                'cy.get("body").click()',
                "css_structural",
            ),
            (
                "Cypress",
                "cy.get",
                "cy.get(welcomePage.firstName).type('Ada')",
                "variable",
            ),
            (
                "Cypress",
                "findByRoleExtended",
                "findByRoleExtended('button', { name: 'Save' }).click()",
                "role",
            ),
            (
                "Cypress",
                "getElementByTestId",
                "getElementByTestId('submit').click()",
                "test_id",
            ),
        ]
        for framework, name, raw, expected in cases:
            with self.subTest(raw=raw):
                r = classify_locator_from_ui_action(
                    name,
                    raw,
                    framework,
                    "test_body",
                    0,
                    "ui_action",
                    "click",
                )
                self.assertEqual(r["selector_literal_kind"], expected)

    def test_named_test_id_helpers_remain_data_contract_strategy(self):
        r = classify_locator_from_ui_action(
            "cy.getElementByTestId('metricsPageTab-query').click",
            "cy.getElementByTestId('metricsPageTab-query').click()",
            "Cypress",
            "test_body",
            0,
            "ui_action",
            "click",
        )
        self.assertEqual(r["normalized_strategy"], "test_id_or_data_contract")
        self.assertEqual(r["selector_literal_kind"], "test_id")

    def test_codebook_v7_selector_literal_kind_uses_dominant_channel(self):
        cases = [
            (
                "Playwright",
                "page.locator",
                'await page.locator(".doc-controls__popup .popup-button").click()',
                "class",
            ),
            (
                "Playwright",
                "page.locator",
                'await page.locator(".tiptap table tr").click()',
                "class",
            ),
            (
                "Playwright",
                "page.locator",
                'await page.locator(".nav-toggler >> visible=true").click()',
                "class",
            ),
            (
                "Playwright",
                "page.locator",
                'await page.locator("[data-test-subj=discoverQueryHits]").click()',
                "test_id",
            ),
            (
                "Playwright",
                "page.locator",
                'await page.locator("[data-foo=bar]").click()',
                "data_attribute",
            ),
            (
                "Cypress",
                "cy.get",
                "cy.get('@linodeApiV4Request.all')",
                "cypress_alias_reference",
            ),
        ]
        for framework, name, raw, expected in cases:
            with self.subTest(raw=raw):
                r = classify_locator_from_ui_action(
                    name,
                    raw,
                    framework,
                    "test_body",
                    0,
                    "ui_action",
                    "click",
                )
                self.assertEqual(r["selector_literal_kind"], expected)


class TestSyncPatterns(unittest.TestCase):
    def test_cy_wait_timeout_constant(self):
        r = resolve_wait_pattern(
            "cy.wait",
            "cy.get('.x').wait(TIMEOUTS.HALF_SEC)",
            "Cypress",
            "wait_synchronization",
            feature={
                "wait_subtype_ast": "fixed_delay_expression",
                "wait_evidence_basis_ast": "ast_symbol_name_heuristic",
            },
        )
        self.assertEqual(r["sync_pattern"], "fixed_delay")
        self.assertEqual(r["sync_arg_kind"], "constant_or_expression")
        self.assertEqual(r["sync_evidence_basis"], "ast_symbol_name_heuristic")

    def test_fixed_delay_cy(self):
        r = classify_sync_pattern("cy.wait", "cy.wait(1000)", "Cypress", "wait_synchronization")
        self.assertEqual(r["sync_pattern"], "fixed_delay")
        self.assertEqual(r["sync_arg_kind"], "literal_ms")

    def test_waitfortimeout_expression(self):
        r = classify_sync_pattern(
            "page.waitForTimeout",
            "await page.waitForTimeout(config.defaultTimeout)",
            "Playwright",
            "wait_synchronization",
        )
        self.assertEqual(r["sync_pattern"], "fixed_delay")

    def test_topass_with_nested_retryable_expect_is_assertion_retry(self):
        r = classify_sync_pattern(
            "expect.toPass",
            "await expect(async () => { await expect(page.locator('.ready')).toBeVisible(); }).toPass()",
            "Playwright",
            "assertion",
        )
        self.assertEqual(r["sync_pattern"], "assertion_retry_wait")
        self.assertTrue(r["is_assertion_retry"])

    def test_chained_wait_literal(self):
        r = classify_sync_pattern(
            "wait",
            "cy.get('.toast').wait(1000)",
            "Cypress",
            "wait_synchronization",
        )
        self.assertEqual(r["sync_pattern"], "fixed_delay")
        self.assertEqual(r["sync_arg_kind"], "literal_ms")

    def test_cy_wait_variable_expression(self):
        r = classify_sync_pattern("cy.wait", "cy.wait(waitTime)", "Cypress", "wait_synchronization")
        self.assertEqual(r["sync_pattern"], "fixed_delay")
        self.assertEqual(r["sync_arg_kind"], "constant_or_expression")
        self.assertEqual(r["confidence"], "medium")

    def test_cy_wait_ambiguous_identifier_is_unresolved(self):
        r = classify_sync_pattern("cy.wait", "cy.wait(alias)", "Cypress", "wait_synchronization")
        self.assertEqual(r["sync_pattern"], "unresolved_custom_wait")
        self.assertEqual(r["sync_arg_kind"], "")
        self.assertEqual(r["confidence"], "low")

    def test_cy_wait_alias_network(self):
        r = classify_sync_pattern("cy.wait", "cy.wait('@getUsers')", "Cypress", "wait_synchronization")
        self.assertEqual(r["sync_pattern"], "network_wait")
        self.assertTrue(r["is_network_based"])
        self.assertEqual(r["sync_arg_kind"], "alias_literal")

    def test_cy_wait_alias_array_network(self):
        r = classify_sync_pattern(
            "cy.wait",
            "cy.wait(['@getUsers', '@getPosts'])",
            "Cypress",
            "wait_synchronization",
        )
        self.assertEqual(r["sync_pattern"], "network_wait")

    def test_navigation_wait(self):
        r = classify_sync_pattern(
            "page.waitForURL",
            "await page.waitForURL('**/home')",
            "Playwright",
            "wait_synchronization",
        )
        self.assertEqual(r["sync_pattern"], "navigation_or_load_wait")

    def test_retryable_assertion_tobevisible(self):
        self.assertTrue(
            is_retryable_ui_assertion("expect", "await expect(locator).toBeVisible()")
        )
        r = classify_sync_pattern(
            "expect",
            "await expect(locator).toBeVisible()",
            "Playwright",
            "assertion",
        )
        self.assertEqual(r["sync_pattern"], "element_state_wait")

    def test_non_retryable_assertion_equal(self):
        self.assertFalse(is_retryable_ui_assertion("expect", "expect(x).toEqual(1)"))
        r = classify_sync_pattern("expect", "expect(x).toEqual(1)", "Playwright", "assertion")
        self.assertNotEqual(r["sync_pattern"], "assertion_retry_wait")


class TestWorkflowPatterns(unittest.TestCase):
    def test_cypress_custom_command(self):
        r = classify_workflow_from_feature(
            "cy.login",
            "cy.login()",
            "Cypress",
            "test_body",
            0,
            "custom_command_call",
            "cypress/support/commands.ts",
            True,
        )
        self.assertEqual(r["abstraction_kind"], "cypress_custom_command")

    def test_unresolved_helper(self):
        r = classify_workflow_from_feature(
            "setupUser",
            "",
            "Playwright",
            "",
            1,
            "helper_call",
            "",
            False,
        )
        self.assertEqual(r["abstraction_kind"], "unresolved_helper")

    def test_helper_expanded_ui_action(self):
        r = classify_workflow_from_feature(
            "click",
            "await btn.click()",
            "Playwright",
            "imported_helper",
            1,
            "ui_action",
            "helpers/ui.ts",
            True,
        )
        self.assertEqual(r["abstraction_kind"], "domain_helper")
        self.assertEqual(r["interaction_ownership"], "helper_expanded")

    def test_page_object_source_kind(self):
        r = classify_workflow_from_feature(
            "click",
            "await this.submit()",
            "Playwright",
            "page_object",
            1,
            "ui_action",
            "pages/LoginPage.ts",
            True,
        )
        self.assertEqual(r["abstraction_kind"], "page_object")

    def test_playwright_test_step_not_bdd(self):
        r = classify_workflow_from_feature(
            "test.step",
            "await test.step('login', async () => {})",
            "Playwright",
            "test_body",
            0,
            "test_step",
            "",
            True,
        )
        self.assertEqual(r["abstraction_kind"], "playwright_test_step")


class TestAutoRetryCapabilities(unittest.TestCase):
    def test_cypress_get_is_retryable_query_not_auto_wait(self):
        caps = classify_auto_retry_capabilities("cy.get", "cy.get('[data-cy=x]')", "Cypress")
        self.assertFalse(caps["auto_wait_capable"])
        self.assertTrue(caps["retryable_query"])

    def test_playwright_click_auto_wait(self):
        caps = classify_auto_retry_capabilities(
            "click",
            "await page.getByRole('button').click()",
            "Playwright",
        )
        self.assertTrue(caps["auto_wait_capable"])
        self.assertFalse(caps["retryable_query"])


class TestAstPreference(unittest.TestCase):
    def test_ast_unknown_does_not_override_useful_regex(self):
        r = resolve_locator_pattern(
            "click",
            "await page.getByRole('button').click()",
            "Playwright",
            "test_body",
            0,
            "ui_action",
            "click",
            feature={
                "locator_strategy_ast": "unknown",
                "ast_confidence": "low",
            },
        )
        self.assertEqual(r["locator_strategy"], "role_or_accessibility")
        self.assertNotIn(
            r.get("locator_evidence_basis"),
            ("ast_call_chain", "ast_selector_argument"),
        )
        self.assertEqual(r["locator_evidence_basis"], "regex_fallback")

    def test_locator_fallback_evidence_labels_are_taxonomy_labels(self):
        regex_locator = resolve_locator_pattern(
            "click",
            "await page.getByRole('button').click()",
            "Playwright",
            "test_body",
            0,
            "ui_action",
            "click",
        )
        self.assertEqual(regex_locator["locator_evidence_basis"], "regex_fallback")

        source_metadata_locator = resolve_locator_pattern(
            "loginPage.submit",
            "await loginPage.submit()",
            "Playwright",
            "page_object",
            0,
            "ui_action",
            "click",
        )
        self.assertEqual(source_metadata_locator["locator_evidence_basis"], "source_metadata")

        no_locator = resolve_locator_pattern(
            "page.goto",
            "await page.goto('/home')",
            "Playwright",
            "test_body",
            0,
            "ui_action",
            "navigation",
        )
        self.assertFalse(no_locator["locator_present"])
        self.assertEqual(no_locator["locator_evidence_basis"], "unresolved")

    def test_prefers_ast_strategy(self):
        r = resolve_locator_pattern(
            "click",
            "await page.getByRole('button').click()",
            "Playwright",
            "test_body",
            0,
            "ui_action",
            "click",
            feature={
                "locator_strategy_ast": "role_or_accessibility",
                "locator_composition_ast": "direct_chain",
                "callee_chain_json": '["page","getByRole","click"]',
                "ast_confidence": "high",
            },
        )
        self.assertEqual(r["locator_strategy"], "role_or_accessibility")
        self.assertEqual(r["locator_evidence_basis"], "ast_call_chain")
        self.assertEqual(r["evidence_basis"], "ast_call_chain")


class TestWaitAstPreference(unittest.TestCase):
    def test_ast_unresolved_does_not_override_specific_regex(self):
        r = resolve_wait_pattern(
            "page.waitForURL",
            "await page.waitForURL('**/home')",
            "Playwright",
            "wait_synchronization",
            feature={"wait_subtype_ast": "unresolved_custom_wait"},
        )
        self.assertEqual(r["sync_pattern"], "navigation_or_load_wait")
        self.assertEqual(r["sync_evidence_basis"], "regex_fallback")

    def test_browser_waituntil_regex_is_predicate(self):
        r = classify_sync_pattern(
            "browser.waitUntil",
            "await browser.waitUntil(() => true)",
            "WebDriverIO",
            "wait_synchronization",
        )
        self.assertEqual(r["sync_pattern"], "predicate_or_custom_condition")
        self.assertEqual(r["sync_target"], "predicate")

    def test_ast_override_updates_sync_target(self):
        r = resolve_wait_pattern(
            "browser.waitUntil",
            "await browser.waitUntil(() => document.readyState === 'complete')",
            "WebDriverIO",
            "wait_synchronization",
            feature={"wait_subtype_ast": "predicate_or_custom_condition"},
        )
        self.assertEqual(r["sync_target"], "predicate")

    def test_ast_binary_numeric_wait_basis_is_preserved(self):
        r = resolve_wait_pattern(
            "cy.wait",
            "cy.wait(500 * retries)",
            "Cypress",
            "wait_synchronization",
            feature={
                "wait_subtype_ast": "fixed_delay_expression",
                "wait_arg_kind_ast": "time_expression",
                "wait_evidence_basis_ast": "ast_binary_numeric_expression",
            },
        )
        self.assertEqual(r["sync_pattern"], "fixed_delay")
        self.assertEqual(r["sync_evidence_basis"], "ast_binary_numeric_expression")

    def test_dynamic_template_alias_wait_is_network_wait(self):
        r = resolve_wait_pattern(
            "cy.wait",
            "cy.wait(`@${as}`)",
            "Cypress",
            "wait_synchronization",
            {},
        )
        self.assertEqual(r["sync_pattern"], "network_wait")
        self.assertEqual(r["sync_arg_kind"], "alias_expression")

    def test_spread_alias_array_wait_is_network_wait(self):
        r = resolve_wait_pattern(
            "cy.wait",
            "cy.wait([...enableBackupAliases, '@updateAccountSettings'])",
            "Cypress",
            "wait_synchronization",
            {
                "wait_subtype_ast": "unresolved_custom_wait",
                "wait_arg_kind_ast": "array_expression",
                "wait_evidence_basis_ast": "ast_array_literal",
            },
        )
        self.assertEqual(r["sync_pattern"], "network_wait")
        self.assertEqual(r["sync_arg_kind"], "alias_array")
        self.assertEqual(r["sync_evidence_basis"], "regex_fallback")

    def test_throttle_constant_wait_is_fixed_delay_expression(self):
        r = resolve_wait_pattern(
            "cy.wait",
            "cy.wait(RESIZE_THROTTLE_RATE)",
            "Cypress",
            "wait_synchronization",
            {
                "wait_subtype_ast": "unresolved_custom_wait",
                "wait_arg_kind_ast": "expression",
                "wait_evidence_basis_ast": "ast_expression_unresolved",
            },
        )
        self.assertEqual(r["sync_pattern"], "fixed_delay")
        self.assertEqual(r["sync_arg_kind"], "constant_or_expression")

    def test_ast_override_updates_sync_flags(self):
        r = resolve_wait_pattern(
            "cy.wait",
            "cy.wait(500)",
            "Cypress",
            "wait_synchronization",
            feature={"wait_subtype_ast": "network_wait"},
        )
        self.assertEqual(r["sync_pattern"], "network_wait")
        self.assertTrue(r["is_network_based"])
        self.assertFalse(r["is_fixed_delay"])

    def test_sync_flags_for_pattern(self):
        flags = sync_flags_for_pattern("predicate_or_custom_condition")
        self.assertTrue(flags["is_condition_based"])
        self.assertFalse(flags["is_network_based"])

    def test_sync_target_for_pattern(self):
        self.assertEqual(sync_target_for_pattern("network_wait"), "network")

    def test_cypress_should_eq_is_retryable_assertion_sync(self):
        raw = "cy.get('.count').should('eq', 2)"
        self.assertTrue(is_assertion_retry_sync_feature("should", raw, {}))
        r = resolve_wait_pattern("should", raw, "Cypress", "assertion", {})
        self.assertEqual(r["sync_pattern"], "assertion_retry_wait")
        self.assertEqual(r["sync_evidence_basis"], "regex_fallback")

    def test_cypress_should_callback_is_retryable_assertion_sync(self):
        raw = "cy.get('.count').should(($el) => { expect($el).to.have.length(2) })"
        self.assertTrue(is_assertion_retry_sync_feature("should", raw, {}))


class TestLocatorAuditMismatch(unittest.TestCase):
    def test_composition_only_mismatch(self):
        t = locator_ast_audit_mismatch_type(
            "css_selector",
            "css_selector",
            "direct_chain",
            "chained_refinement",
            "id",
            "id",
            "high",
        )
        self.assertEqual(t, "composition")


class TestWorkflowAstPreference(unittest.TestCase):
    def test_prefers_workflow_kind_ast(self):
        r = resolve_workflow_pattern(
            "loginPage.submit",
            "await loginPage.submit()",
            "Playwright",
            "test_body",
            0,
            "helper_call",
            "",
            None,
            feature={"workflow_kind_ast": "page_object", "ast_confidence": "high"},
        )
        self.assertEqual(r["abstraction_kind"], "page_object")
        self.assertEqual(r["interaction_ownership"], "page_object_method")
        self.assertEqual(r["reuse_scope"], "page_object_library")

    def test_domain_helper_ast_ownership(self):
        r = resolve_workflow_pattern(
            "setupUser",
            "await setupUser()",
            "Playwright",
            "test_body",
            0,
            "helper_call",
            "",
            None,
            feature={"workflow_kind_ast": "domain_helper", "ast_confidence": "medium"},
        )
        self.assertEqual(r["abstraction_kind"], "domain_helper")
        self.assertEqual(r["interaction_ownership"], "helper_expanded")


class TestAssertionRetrySync(unittest.TestCase):
    def test_ast_only_assertion_retry(self):
        self.assertFalse(
            is_retryable_ui_assertion("expect", "await expect(locator).toBeEnabled()")
        )
        self.assertTrue(
            is_assertion_retry_sync_feature(
                "expect",
                "await expect(locator).toBeEnabled()",
                {"wait_subtype_ast": "assertion_retry_wait"},
            )
        )


class TestWorkflowPageSplit(unittest.TestCase):
    def test_user_page_is_framework_instance(self):
        r = classify_workflow_from_feature(
            "userPage.getByRole",
            "await userPage.getByRole('button')",
            "Playwright",
            "test_body",
            0,
            "helper_call",
            "",
            None,
        )
        self.assertEqual(r["abstraction_kind"], "framework_page_instance")

    def test_channels_page_nested_is_pom(self):
        r = classify_workflow_from_feature(
            "channelsPage.searchBox.searchInput.fill",
            "await channelsPage.searchBox.searchInput.fill('x')",
            "Playwright",
            "test_body",
            0,
            "helper_call",
            "",
            None,
        )
        self.assertIn(r["abstraction_kind"], ("page_object", "page_object_model"))

    def test_no_playwright_fixture_on_username(self):
        r = classify_workflow_from_feature(
            "username.replace",
            "username.replace('@', '')",
            "Playwright",
            "test_body",
            0,
            "helper_call",
            "",
            None,
        )
        self.assertNotEqual(r["abstraction_kind"], "playwright_fixture")

    def test_playwright_fixture_requires_provenance(self):
        r = resolve_workflow_pattern(
            "authenticatedPage.goto",
            "await authenticatedPage.goto('/home')",
            "Playwright",
            "test_body",
            0,
            "helper_call",
            "",
            None,
            feature={
                "workflow_kind_ast": "playwright_fixture",
                "fixture_param_name": "authenticatedPage",
                "fixture_declared_by": "test.extend",
            },
        )
        self.assertEqual(r["abstraction_kind"], "playwright_fixture")

    def test_page_symbol_origin_framework_instance(self):
        r = resolve_workflow_pattern(
            "userPage.getByRole",
            "await userPage.getByRole('button').click()",
            "Playwright",
            "test_body",
            0,
            "helper_call",
            "",
            None,
            feature={
                "workflow_kind_ast": "framework_page_instance",
                "page_symbol_origin_ast": "framework_page_instance",
            },
        )
        self.assertEqual(r["abstraction_kind"], "framework_page_instance")

    def test_cypress_command_role_session_setup(self):
        r = resolve_workflow_pattern(
            "cy.login",
            "cy.login()",
            "Cypress",
            "test_body",
            0,
            "custom_command_call",
            "",
            None,
            feature={
                "cypress_command_role_ast": "session_setup",
                "cypress_command_role_basis_ast": "ast_cypress_session_call",
            },
        )
        self.assertEqual(r["abstraction_kind"], "hook_setup_flow")
        self.assertEqual(r["workflow_evidence_basis"], "ast_cypress_session_call")

    def test_cypress_command_role_utility(self):
        r = resolve_workflow_pattern(
            "cy.logDebug",
            "cy.logDebug()",
            "Cypress",
            "test_body",
            0,
            "custom_command_call",
            "",
            None,
            feature={
                "cypress_command_role_ast": "utility",
                "cypress_command_role_basis_ast": "ast_cypress_ui_action_call",
            },
        )
        self.assertEqual(r["abstraction_kind"], "domain_helper")
        self.assertNotEqual(r["abstraction_kind"], "cypress_custom_command")
        self.assertEqual(r["workflow_evidence_basis"], "ast_cypress_ui_action_call")

    def test_cypress_nested_setup_fallback_without_ast_basis(self):
        r = resolve_workflow_pattern(
            "cy.uiSave",
            "cy.uiSave().wait(TIMEOUTS.HALF_SEC)",
            "Cypress",
            "test_body",
            0,
            "custom_command_call",
            "",
            None,
            feature={"workflow_kind_ast": "cypress_custom_command"},
        )
        self.assertEqual(r["abstraction_kind"], "domain_helper")

    def test_cypress_custom_command_ast_basis_not_overridden_by_raw_chain(self):
        r = resolve_workflow_pattern(
            "cy.uiSave",
            "cy.uiSave().wait(TIMEOUTS.HALF_SEC)",
            "Cypress",
            "test_body",
            0,
            "custom_command_call",
            "",
            None,
            feature={
                "workflow_kind_ast": "cypress_custom_command",
                "workflow_kind_basis_ast": "ast_cypress_custom_command_call",
            },
        )
        self.assertEqual(r["abstraction_kind"], "cypress_custom_command")
        self.assertEqual(r["workflow_evidence_basis"], "ast_cypress_custom_command_call")

    def test_cypress_setup_cmd_name_fallback(self):
        r = classify_workflow_from_feature(
            "cy.postMessageFromFile",
            "cy.postMessageFromFile('msg.json')",
            "Cypress",
            "test_body",
            0,
            "custom_command_call",
            "",
            None,
        )
        self.assertEqual(r["abstraction_kind"], "domain_helper")


class TestLocatorComposition(unittest.TestCase):
    def test_standalone_cy_get(self):
        r = classify_locator_from_ui_action(
            "cy.get",
            "cy.get('.tiptap')",
            "Cypress",
            "test_body",
            0,
            "ui_action",
            "locator_query",
        )
        self.assertEqual(r["locator_composition"], "standalone_locator_query")

    def test_locator_composition_basis_separate_from_ast_strategy(self):
        r = resolve_locator_pattern(
            "cy.get",
            "cy.get('.item').eq(0).click()",
            "Cypress",
            "test_body",
            0,
            "ui_action",
            "click",
            {
                "locator_strategy_ast": "css_selector",
                "locator_composition_ast": "",
                "selector_literal_kind_ast": "class",
                "ast_confidence": "high",
            },
        )
        self.assertEqual(r["locator_evidence_basis"], "ast_selector_argument")
        self.assertEqual(r["locator_composition_evidence_basis"], "regex_fallback")

    def test_structured_selector_channel_and_origin_are_preserved(self):
        r = resolve_locator_pattern(
            "cy.xpath",
            "cy.xpath(widgetsPage.textCenterAlign).click()",
            "Cypress",
            "test_body",
            0,
            "ui_action",
            "click",
            {
                "locator_strategy_ast": "xpath_selector",
                "locator_composition_ast": "direct_chain",
                "selector_literal_kind_ast": "xpath",
                "selector_channel_ast": "xpath",
                "selector_value_origin_ast": "member_path",
                "ast_confidence": "high",
            },
        )
        self.assertEqual(r["selector_literal_kind"], "xpath")
        self.assertEqual(r["selector_channel"], "xpath")
        self.assertEqual(r["selector_value_origin"], "member_path")

    def test_resolved_helper_selector_channel_overrides_wrapper_category(self):
        r = resolve_locator_pattern(
            "cy.getElementByTestId",
            "cy.getElementByTestId('discoverNewButton').click()",
            "Cypress",
            "test_body",
            0,
            "ui_action",
            "click",
            {
                "resolved_selector_channel_ast": "test_id",
                "resolved_selector_strategy_ast": "test_id_or_data_contract",
                "resolved_selector_evidence_basis_ast": "resolved_helper_body_locator",
                "resolved_selector_helper_name_ast": "getElementByTestId",
                "ast_confidence": "high",
            },
        )
        self.assertEqual(r["locator_strategy"], "test_id_or_data_contract")
        self.assertEqual(r["selector_literal_kind"], "test_id")
        self.assertEqual(r["selector_channel"], "test_id")
        self.assertEqual(r["locator_evidence_basis"], "resolved_helper_body_locator")

    def test_selector_channel_fallback_uses_api_semantics_without_ast_fields(self):
        cases = [
            ("findByTitle", "ui.dialog\n       .findByTitle(`Delete StackScript ${stackScripts[0].label}?`)", "title", ""),
            ("getByPlaceholder", 'page.getByPlaceholder("Type a message")', "placeholder", "inline_literal"),
            ("cy.findByLabelText", "cy.findByLabelText('Bucket')", "label", "inline_literal"),
            ("cy.xpath", "cy.xpath(widgetsPage.textCenterAlign).click()", "xpath", "member_path"),
            ("cy.get", "cy.get(welcomePage.continueButton)", "variable", "member_path"),
        ]
        for name, raw, expected_channel, expected_origin in cases:
            with self.subTest(raw=raw):
                r = resolve_locator_pattern(
                    name,
                    raw,
                    "Cypress",
                    "test_body",
                    0,
                    "ui_action",
                    "click",
                    {},
                )
                self.assertEqual(r["selector_literal_kind"], expected_channel)
                self.assertEqual(r["selector_channel"], expected_channel)
                if expected_origin:
                    self.assertEqual(r["selector_value_origin"], expected_origin)


class TestAssertionRetryAstPreference(unittest.TestCase):
    def test_ast_wait_metadata_blocks_regex_retry_fallback(self):
        raw = "cy.get('#x').should('eq', 'y')"
        self.assertFalse(
            is_assertion_retry_sync_feature(
                "should",
                raw,
                {
                    "wait_subtype_ast": "",
                    "wait_evidence_basis_ast": "ast_expression_unresolved",
                },
            )
        )

    def test_to_pass_and_element_state_assertions_are_not_generic_retry_waits(self):
        predicate = classify_sync_pattern(
            "expect",
            "expect(async () => { await expect(page.locator('.x')).toBeVisible() }).toPass({ timeout: POLL_TOPASS_TIMEOUT })",
            "Playwright",
            "assertion",
        )
        self.assertEqual(predicate["sync_pattern"], "assertion_retry_wait")
        self.assertEqual(predicate["sync_target"], "assertion")

        element = classify_sync_pattern(
            "expect",
            "expect(firstCard).toBeVisible()",
            "Playwright",
            "assertion",
        )
        self.assertEqual(element["sync_pattern"], "element_state_wait")
        self.assertEqual(element["sync_target"], "element")

    def test_terminal_chained_wait_constant_wins_over_prior_should(self):
        r = classify_sync_pattern(
            "wait",
            "cy.get('input').should('be.visible').type('Town').wait(TIMEOUTS.HALF_SEC)",
            "Cypress",
            "wait",
        )
        self.assertEqual(r["sync_pattern"], "fixed_delay")
        self.assertEqual(r["sync_arg_kind"], "constant_or_expression")


class TestWorkflowArchetype(unittest.TestCase):
    def test_page_object_centric_unresolved(self):
        a = infer_workflow_archetype(
            ui_action_count=4,
            test_body_ui=4,
            hook_ui=0,
            helper_ui=0,
            po_ui=0,
            cypress_cmd_ui=0,
            page_object_signal=True,
            helper_call_count=2,
            unresolved_helper_calls=0,
            expanded_ui_count=0,
            page_object_call_count=3,
        )
        self.assertEqual(a, "page_object_centric_unresolved")

    def test_inline_direct(self):
        a = infer_workflow_archetype(
            ui_action_count=10,
            test_body_ui=9,
            hook_ui=0,
            helper_ui=0,
            po_ui=0,
            cypress_cmd_ui=0,
            page_object_signal=False,
            helper_call_count=0,
            unresolved_helper_calls=0,
            expanded_ui_count=0,
        )
        self.assertEqual(a, "inline_direct")

    def test_structured_step_centric(self):
        a = infer_workflow_archetype(
            ui_action_count=4,
            test_body_ui=4,
            hook_ui=0,
            helper_ui=0,
            po_ui=0,
            cypress_cmd_ui=0,
            page_object_signal=False,
            helper_call_count=0,
            unresolved_helper_calls=0,
            expanded_ui_count=0,
            playwright_test_step_count=3,
        )
        self.assertEqual(a, "structured_step_centric")

    def test_hook_or_fixture_dominance_takes_precedence_over_other_archetypes(self):
        cases = [
            dict(ui_action_count=10, test_body_ui=2, hook_ui=7, helper_ui=1, po_ui=0, cypress_cmd_ui=0, playwright_test_step_count=4),
            dict(ui_action_count=10, test_body_ui=1, hook_ui=6, helper_ui=0, po_ui=0, cypress_cmd_ui=3, helper_call_count=4, unresolved_helper_calls=3),
            dict(ui_action_count=12, test_body_ui=2, hook_ui=7, helper_ui=2, po_ui=1, cypress_cmd_ui=0),
        ]
        for case in cases:
            with self.subTest(case=case):
                a = infer_workflow_archetype(
                    page_object_signal=False,
                    helper_call_count=case.pop("helper_call_count", 0),
                    unresolved_helper_calls=case.pop("unresolved_helper_calls", 0),
                    expanded_ui_count=case.get("helper_ui", 0),
                    **case,
                )
                self.assertEqual(a, "hook_or_fixture_centric")

    def test_helper_dominance_takes_precedence_over_page_object_signal(self):
        a = infer_workflow_archetype(
            ui_action_count=10,
            test_body_ui=1,
            hook_ui=0,
            helper_ui=7,
            po_ui=2,
            cypress_cmd_ui=0,
            page_object_signal=True,
            helper_call_count=4,
            unresolved_helper_calls=0,
            expanded_ui_count=7,
            page_object_call_count=2,
        )
        self.assertEqual(a, "helper_mediated")

    def test_custom_command_dominance_takes_precedence_over_page_object_signal(self):
        a = infer_workflow_archetype(
            ui_action_count=10,
            test_body_ui=1,
            hook_ui=0,
            helper_ui=1,
            po_ui=2,
            cypress_cmd_ui=6,
            page_object_signal=True,
            helper_call_count=1,
            unresolved_helper_calls=0,
            expanded_ui_count=7,
            page_object_call_count=2,
        )
        self.assertEqual(a, "framework_extension_centric")

    def test_high_direct_share_is_inline_even_with_minor_helper_calls(self):
        a = infer_workflow_archetype(
            ui_action_count=12,
            test_body_ui=10,
            hook_ui=0,
            helper_ui=1,
            po_ui=1,
            cypress_cmd_ui=0,
            page_object_signal=False,
            helper_call_count=1,
            unresolved_helper_calls=0,
            expanded_ui_count=1,
        )
        self.assertEqual(a, "inline_direct")

    def test_unresolved_thin_wrapper(self):
        a = infer_workflow_archetype(
            ui_action_count=2,
            test_body_ui=2,
            hook_ui=0,
            helper_ui=0,
            po_ui=0,
            cypress_cmd_ui=0,
            page_object_signal=False,
            helper_call_count=5,
            unresolved_helper_calls=3,
            expanded_ui_count=0,
        )
        self.assertEqual(a, "unresolved_thin_wrapper")

    def test_weighted_source_dominance_detail_exposes_basis(self):
        detail = infer_workflow_archetype_detail(
            ui_action_count=10,
            test_body_ui=3,
            hook_ui=0,
            helper_ui=2,
            po_ui=0,
            cypress_cmd_ui=5,
            page_object_signal=True,
            helper_call_count=2,
            unresolved_helper_calls=0,
            expanded_ui_count=7,
            page_object_call_count=2,
        )
        self.assertEqual(detail["workflow_archetype"], "framework_extension_centric")
        self.assertEqual(detail["dominant_workflow_source"], "cypress_command_ui")
        self.assertAlmostEqual(detail["dominant_workflow_source_share"], 0.5)
        self.assertIn("dominant_source", detail["workflow_archetype_basis"])

    def test_layered_requires_material_second_source(self):
        detail = infer_workflow_archetype_detail(
            ui_action_count=10,
            test_body_ui=4,
            hook_ui=0,
            helper_ui=3,
            po_ui=3,
            cypress_cmd_ui=0,
            page_object_signal=True,
            helper_call_count=3,
            unresolved_helper_calls=0,
            expanded_ui_count=6,
            page_object_call_count=3,
        )
        self.assertEqual(detail["workflow_archetype"], "layered")
        self.assertEqual(detail["dominant_workflow_source"], "test_body_ui")
        self.assertEqual(detail["top_two_workflow_sources"][1]["source"], "page_object_ui")

    def test_unresolved_wrapper_detail_only_when_unresolved_dominates_expanded(self):
        detail = infer_workflow_archetype_detail(
            ui_action_count=4,
            test_body_ui=4,
            hook_ui=0,
            helper_ui=0,
            po_ui=0,
            cypress_cmd_ui=0,
            page_object_signal=False,
            helper_call_count=6,
            unresolved_helper_calls=5,
            expanded_ui_count=0,
        )
        self.assertEqual(detail["workflow_archetype"], "unresolved_thin_wrapper")
        self.assertIn("unresolved_dominates", detail["workflow_archetype_basis"])


if __name__ == "__main__":
    unittest.main()
