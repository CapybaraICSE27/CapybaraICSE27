#!/usr/bin/env python3
"""Unit tests for RQ1 setup/teardown intent resolver (Milestone 2)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from setup_teardown_intent import (
    build_intent_candidate,
    classify_scope,
    dedupe_intent_rows,
    is_eligible_setup_teardown_unit,
    map_provenance_hints,
    match_resolved_helper_wrapper,
    paper_facing_intent_rows,
    resolve_test_intent_units,
    summarize_rq1_intent_by_test,
)


class TestEligibility(unittest.TestCase):
    def test_excludes_ordinary_click(self):
        f = {
            "feature_type": "ui_action",
            "source_kind": "test_body",
            "name": "page.click",
            "raw_code": "await page.click('#x')",
        }
        ok, basis = is_eligible_setup_teardown_unit(f)
        self.assertFalse(ok)

    def test_navigation_is_candidate_only(self):
        f = {
            "feature_type": "ui_action",
            "source_kind": "test_body",
            "name": "page.goto",
            "raw_code": "await page.goto('/')",
            "line": 5,
        }
        ok, basis = is_eligible_setup_teardown_unit(f)
        self.assertTrue(ok)
        self.assertEqual(basis, "navigation_bootstrap_ast")

    def test_cy_intercept_eligible(self):
        f = {
            "feature_type": "network_mock",
            "source_kind": "beforeEach",
            "name": "cy.intercept",
            "raw_code": "cy.intercept('GET', '/api/x')",
        }
        ok, _ = is_eligible_setup_teardown_unit(f)
        self.assertTrue(ok)

    def test_common_false_positive_patterns_are_excluded(self):
        cases = [
            ("helper_call", "test_body", "cy.log", 'cy.log("delete user")'),
            ("helper_call", "beforeEach", "console.log", 'console.log("cleanup")'),
            ("helper_call", "afterEach", "logger.info", 'logger.info("reset database")'),
            ("assertion", "test_body", "assertHTML", "assertHTML(markup)"),
            ("helper_call", "test_body", "reportRequestCount", "reportRequestCount()"),
            ("ui_action", "test_body", "page.fill", 'page.fill("#email", data.email)'),
            ("ui_action", "test_body", "cy.get('#submit').click", 'cy.get("#submit").click()'),
            ("ui_action", "test_body", "page.locator('button').press", 'page.locator("button").press("Enter")'),
            ("helper_call", "test_body", "someWorkflowHelper", "someWorkflowHelper()"),
            ("cypress_test_utility", "test_body", "cy.wrap", "cy.wrap(subject)"),
            ("cypress_test_utility", "test_body", "cy.then", "cy.then(() => {})"),
            ("cypress_test_utility", "test_body", "cy.as", 'cy.as("subject")'),
            ("wait_synchronization", "beforeEach", "cy.wait", "cy.wait(1000)"),
            ("wait_synchronization", "beforeEach", "agHelper.Sleep", "agHelper.Sleep(2000)"),
            ("wait_synchronization", "beforeEach", "browser.pause", "browser.pause(500)"),
            ("wait_synchronization", "beforeEach", "t.wait", "t.wait(1000)"),
        ]
        for feature_type, source_kind, name, raw in cases:
            with self.subTest(raw=raw):
                cand = build_intent_candidate({
                    "repo": "r",
                    "test_id": "t",
                    "framework": "Cypress",
                    "feature_type": feature_type,
                    "source_kind": source_kind,
                    "name": name,
                    "raw_code": raw,
                    "line": 3,
                })
                self.assertIsNone(cand)

    def test_manual_audit_leakage_patterns_are_excluded(self):
        cases = [
            {
                "feature_type": "setup",
                "source_kind": "beforeEach",
                "name": "cy.task",
                "raw_code": "cy.task('log', message)",
                "callee_chain_json": '["cy", "task"]',
                "literal_args_json": '["log"]',
            },
            {
                "feature_type": "browser_context_control",
                "source_kind": "beforeEach",
                "name": "cy.getCookies",
                "raw_code": "cy.getCookies()",
                "callee_chain_json": '["cy", "getCookies"]',
            },
            {
                "feature_type": "setup",
                "source_kind": "beforeEach",
                "name": "page.context.browser.browserType.name",
                "raw_code": "page.context().browser()?.browserType().name()",
                "callee_chain_json": '["page", "context", "browser", "browserType", "name"]',
            },
            {
                "feature_type": "setup",
                "source_kind": "beforeEach",
                "name": "Buffer.from.toString",
                "raw_code": "Buffer.from(value).toString('base64')",
                "callee_chain_json": '["Buffer", "from", "toString"]',
            },
            {
                "feature_type": "setup",
                "source_kind": "beforeEach",
                "name": "page.waitForResponse",
                "raw_code": "await page.waitForResponse('/api/status')",
                "callee_chain_json": '["page", "waitForResponse"]',
            },
            {
                "feature_type": "wait_synchronization",
                "source_kind": "beforeEach",
                "name": "locator.waitFor",
                "raw_code": "await locator.waitFor({ state: 'visible' })",
                "callee_chain_json": '["locator", "waitFor"]',
            },
            {
                "feature_type": "setup",
                "source_kind": "beforeEach",
                "name": "useIsomorphicLayoutEffect",
                "raw_code": "useIsomorphicLayoutEffect(() => {}, [])",
                "callee_chain_json": '["useIsomorphicLayoutEffect"]',
            },
            {
                "feature_type": "custom_command_call",
                "source_kind": "beforeEach",
                "name": "cy.get.clear.focus",
                "raw_code": "cy.get('#time').should('be.visible').first().clear().focus()",
                "callee_chain_json": '["cy", "get", "should", "first", "clear", "focus"]',
            },
            {
                "feature_type": "assertion",
                "source_kind": "beforeEach",
                "name": "expect",
                "raw_code": "expect(setupResult).to.equal(true)",
            },
        ]
        for feature in cases:
            with self.subTest(raw=feature["raw_code"]):
                cand = build_intent_candidate({
                    "repo": "r",
                    "test_id": "t",
                    "framework": "Cypress",
                    "line": 3,
                    **feature,
                })
                self.assertIsNone(cand)

    def test_false_positive_families_are_hard_rejected_before_structured_hints(self):
        cases = [
            (
                "waits_with_framework_category",
                {
                    "feature_type": "setup",
                    "source_kind": "beforeEach",
                    "name": "page.waitForResponse",
                    "raw_code": "await page.waitForResponse('/api/status')",
                    "callee_chain_json": '["page", "waitForResponse"]',
                    "framework_api_category": "network_mock",
                    "framework_api_category_basis_ast": "ast_known_framework_api",
                },
            ),
            (
                "logging_task_without_literal_metadata",
                {
                    "feature_type": "setup",
                    "source_kind": "beforeEach",
                    "name": "cy.task",
                    "raw_code": "cy.task('log', message)",
                    "callee_chain_json": '["cy", "task"]',
                    "framework_api_category": "backend_task",
                    "framework_api_category_basis_ast": "ast_cypress_task_handler",
                    "cypress_task_role_ast": "test_data_setup",
                    "cypress_task_role_basis_ast": "ast_task_handler_callee",
                },
            ),
            (
                "focus_chain_with_helper_phase_hint",
                {
                    "feature_type": "custom_command_call",
                    "source_kind": "beforeEach",
                    "name": "cy.get.clear.focus",
                    "raw_code": "cy.get('#time').should('be.visible').first().clear().focus()",
                    "callee_chain_json": '["cy", "get", "should", "first", "clear", "focus"]',
                    "helper_body_phase_hint_ast": "setup",
                    "helper_body_phase_hint_basis_ast": "ast_nested_framework_api",
                    "helper_expansion_evidence_basis": "exact_symbol",
                },
            ),
            (
                "value_construction_with_statement_hint",
                {
                    "feature_type": "setup",
                    "source_kind": "beforeEach",
                    "name": "Buffer.from.toString",
                    "raw_code": "Buffer.from(value).toString('base64')",
                    "callee_chain_json": '["Buffer", "from", "toString"]',
                    "statement_phase_hint_ast": "setup",
                    "statement_phase_hint_basis_ast": "ast_known_framework_api",
                },
            ),
            (
                "direct_cypress_fixture_load",
                {
                    "feature_type": "setup",
                    "source_kind": "beforeEach",
                    "name": "cy.fixture",
                    "raw_code": "cy.fixture('users.json')",
                    "callee_chain_json": '["cy", "fixture"]',
                    "framework_api_category": "test_data_fixture",
                    "framework_api_category_basis_ast": "ast_known_framework_api",
                },
            ),
            (
                "fixture_input_load_site",
                {
                    "feature_type": "input",
                    "source_kind": "beforeEach",
                    "name": "cy.fixture",
                    "raw_code": "cy.fixture('users.json')",
                    "callee_chain_json": '["cy", "fixture"]',
                    "input_source_class": "fixture_file_input",
                    "input_channel_ast": "load_site",
                    "is_load_site": 1,
                },
            ),
            (
                "runtime_lifecycle_with_framework_category",
                {
                    "feature_type": "setup",
                    "source_kind": "beforeEach",
                    "name": "useIsomorphicLayoutEffect",
                    "raw_code": "useIsomorphicLayoutEffect(() => {}, [])",
                    "callee_chain_json": '["useIsomorphicLayoutEffect"]',
                    "framework_api_category": "browser_context_control",
                    "framework_api_category_basis_ast": "ast_known_framework_api",
                },
            ),
        ]
        for label, feature in cases:
            with self.subTest(label=label):
                cand = build_intent_candidate({
                    "repo": "r",
                    "test_id": "t",
                    "framework": "Cypress",
                    "line": 3,
                    **feature,
                })
                self.assertIsNone(cand)

    def test_page_object_ctor_name_alone_is_not_rq1_eligible(self):
        ok, basis = is_eligible_setup_teardown_unit({
            "feature_type": "page_object_ctor",
            "source_kind": "test_body",
            "name": "new SettingsPage",
            "raw_code": "const settings = new SettingsPage(page)",
        })
        self.assertFalse(ok)
        self.assertEqual(basis, "excluded_page_object_ctor_without_structured_setup_signal")

    def test_common_rq1_precedence_and_scope_patterns(self):
        cases = [
            (
                {
                    "feature_type": "network_mock",
                    "source_kind": "beforeEach",
                    "name": "cy.intercept",
                    "raw_code": 'cy.intercept("/logout")',
                    "callee_chain_json": '["cy", "intercept"]',
                },
                "network_mock_or_spy",
                "per_test_hook",
            ),
            (
                {
                    "feature_type": "setup",
                    "source_kind": "beforeEach",
                    "name": "browser.mock",
                    "raw_code": 'browser.mock("/token")',
                    "callee_chain_json": '["browser", "mock"]',
                },
                "network_mock_or_spy",
                "per_test_hook",
            ),
            (
                {
                    "feature_type": "custom_command_call",
                    "source_kind": "before",
                    "name": "cy.apiDeleteTeam",
                    "raw_code": "cy.apiDeleteTeam(team.id)",
                    "callee_chain_json": '["cy", "apiDeleteTeam"]',
                },
                "test_data_or_backend_state",
                "suite_or_fixture",
            ),
            (
                {
                    "feature_type": "browser_context_control",
                    "source_kind": "beforeEach",
                    "name": "localStorage.setItem",
                    "raw_code": 'localStorage.setItem("token", token)',
                    "callee_chain_json": '["localStorage", "setItem"]',
                    "literal_args_json": '["token"]',
                },
                "browser_context_or_client_state",
                "per_test_hook",
            ),
            (
                {
                    "feature_type": "browser_context_control",
                    "source_kind": "beforeEach",
                    "name": "cy.clearCookies",
                    "raw_code": "cy.clearCookies()",
                    "callee_chain_json": '["cy", "clearCookies"]',
                    "statement_phase_hint_ast": "teardown",
                },
                "browser_context_or_client_state",
                "per_test_hook",
            ),
        ]
        for feature, expected_intent, expected_scope in cases:
            with self.subTest(raw=feature["raw_code"]):
                if feature["name"].startswith("cy.api"):
                    feature = {
                        **feature,
                        "cypress_command_role_ast": "test_data_setup",
                        "cypress_command_role_basis_ast": "ast_cypress_data_call",
                    }
                cand = build_intent_candidate({
                    "repo": "r",
                    "test_id": "t",
                    "framework": "Cypress",
                    "line": 3,
                    **feature,
                })
                self.assertIsNotNone(cand)
                rows, _ = resolve_test_intent_units([cand])
                self.assertEqual(rows[0]["primary_intent"], expected_intent)
                self.assertEqual(rows[0]["scope"], expected_scope)

    def test_cypress_test_utility_intercept_eligible(self):
        f = {
            "feature_type": "cypress_test_utility",
            "source_kind": "test_body",
            "name": "cy.intercept",
            "raw_code": "cy.intercept('POST', '/api/save', { fixture: 'x.json' })",
        }
        ok, basis = is_eligible_setup_teardown_unit(f)
        self.assertTrue(ok)
        self.assertEqual(basis, "cypress_test_utility_intercept")

    def _control(self, raw_code: str, **extra) -> dict:
        return {
            "feature_type": "control",
            "source_kind": "test_body",
            "name": raw_code.split("(")[0].strip(),
            "raw_code": raw_code,
            **extra,
        }

    def test_cypress_utility_controls_not_eligible(self):
        for raw in ('cy.wrap(foo)', 'cy.then(() => {})', 'cy.as("x")'):
            with self.subTest(raw=raw):
                ok, basis = is_eligible_setup_teardown_unit(self._control(raw))
                self.assertFalse(ok, raw)
                self.assertEqual(basis, "excluded_utility_control")

    def test_unknown_framework_api_category_does_not_make_control_eligible(self):
        ok, basis = is_eligible_setup_teardown_unit(
            self._control(
                "cy.wrap(foo)",
                framework_api_category="unknown",
                framework_api_category_basis_ast="",
            )
        )
        self.assertFalse(ok)
        self.assertEqual(basis, "excluded_utility_control")

    def test_cypress_environment_controls_eligible(self):
        cases = (
            ("cy.clearCookies()", "framework_api_category:cleanup", {}),
            (
                'cy.task("resetDb")',
                "framework_api_category:backend_task",
                {
                    "callee_chain_json": '["cy", "task"]',
                    "literal_args_json": '["resetDb"]',
                    "framework_api_category": "backend_task",
                    "framework_api_category_basis_ast": "ast_cypress_task_handler",
                    "cypress_task_role_ast": "test_data_setup",
                    "cypress_task_role_basis_ast": "ast_task_handler_callee",
                },
            ),
            ('cy.session("user", () => {})', "framework_api_category:auth_session", {}),
        )
        for raw, expected_basis, extra in cases:
            with self.subTest(raw=raw):
                ok, basis = is_eligible_setup_teardown_unit(self._control(raw, **extra))
                self.assertTrue(ok, raw)
                self.assertEqual(basis, expected_basis)

    def test_unknown_cypress_task_not_eligible_without_task_role(self):
        ok, basis = is_eligible_setup_teardown_unit(self._control(
            'cy.task("noop")',
            callee_chain_json='["cy", "task"]',
            literal_args_json='["noop"]',
        ))
        self.assertFalse(ok)
        self.assertEqual(basis, "excluded_utility_control")

    def test_cypress_task_name_without_registry_evidence_not_eligible(self):
        ok, basis = is_eligible_setup_teardown_unit(self._control(
            'cy.task("resetDb")',
            callee_chain_json='["cy", "task"]',
            literal_args_json='["resetDb"]',
        ))
        self.assertFalse(ok)
        self.assertEqual(basis, "excluded_utility_control")

    def test_logger_only_rows_not_eligible_even_in_hooks(self):
        for raw in (
            'cy.log("cleanup done")',
            'console.log("reset database")',
            'logger.info("Deleting user")',
            'assertHTML("ready")',
            'expectSetupBanner()',
            'reportCleanup()',
            'countUsers()',
            'printDebugState()',
            'debugSession()',
        ):
            with self.subTest(raw=raw):
                ok, basis = is_eligible_setup_teardown_unit({
                    "feature_type": "control",
                    "source_kind": "beforeEach",
                    "name": raw.split("(")[0],
                    "raw_code": raw,
                })
                self.assertFalse(ok)
                self.assertEqual(basis, "excluded_logger_only")

    def test_reporting_wrapper_with_stateful_body_remains_eligible(self):
        ok, basis = is_eligible_setup_teardown_unit({
            "feature_type": "helper_call",
            "source_kind": "beforeEach",
            "name": "reportSeed",
            "raw_code": "function reportSeed() { cy.request('POST', '/seed') }",
            "helper_body_phase_hint_ast": "setup",
            "helper_body_phase_hint_basis_ast": "ast_nested_framework_api",
        })
        self.assertTrue(ok)
        self.assertTrue(basis.startswith("hook_source_kind"))


class TestIntentReviewReasons(unittest.TestCase):
    def test_structured_cypress_role_suppresses_helper_body_unavailable(self):
        from setup_teardown_intent import intent_review_reasons

        feature = {
            "feature_type": "custom_command_call",
            "framework": "Cypress",
            "name": "cy.session",
            "raw_code": 'cy.session("user", () => {})',
            "cypress_command_role_ast": "session_setup",
            "cypress_command_role_basis_ast": "ast_cypress_session_call",
            "helper_resolution_status": "unresolved",
        }
        hints = map_provenance_hints(feature)
        reasons = intent_review_reasons(
            feature,
            hints,
            primary_intent="session_or_auth_setup",
            confidence="high",
            eligibility_basis="cypress_command_role:session_setup",
        )
        self.assertNotIn("helper_body_unavailable", reasons)

    def test_legacy_cypress_role_still_flags_body_unavailable(self):
        from setup_teardown_intent import intent_review_reasons

        feature = {
            "feature_type": "custom_command_call",
            "framework": "Cypress",
            "name": "cy.login",
            "raw_code": "cy.login()",
            "cypress_command_role_ast": "session_setup",
            "helper_resolution_status": "unresolved",
        }
        hints = map_provenance_hints(feature)
        reasons = intent_review_reasons(
            feature,
            hints,
            primary_intent="session_or_auth_setup",
            confidence="medium",
            eligibility_basis="cypress_command_role:session_setup",
            primary_intent_basis="heuristic_cypress_command_role",
        )
        self.assertIn("helper_body_unavailable", reasons)

    def test_unstructured_helper_still_flags_body_unavailable(self):
        from setup_teardown_intent import intent_review_reasons

        feature = {
            "feature_type": "helper_call",
            "name": "seedUsers",
            "raw_code": "seedUsers()",
            "helper_resolution_status": "unresolved",
        }
        hints = map_provenance_hints(feature)
        reasons = intent_review_reasons(
            feature,
            hints,
            primary_intent="generic_setup_teardown_utility",
            confidence="low",
            eligibility_basis="generic_helper_name",
        )
        self.assertIn("helper_body_unavailable", reasons)


class TestNavigationBootstrap(unittest.TestCase):
    def test_first_goto_before_click_is_bootstrap(self):
        nav = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Playwright",
            "feature_type": "ui_action",
            "source_kind": "test_body",
            "name": "page.goto",
            "raw_code": "await page.goto('/login')",
            "line": 10,
        })
        self.assertIsNotNone(nav)
        rows, _ = resolve_test_intent_units([nav], first_non_navigation_ui_line=12)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["primary_intent"], "navigation_bootstrap")
        self.assertEqual(rows[0]["phase"], "setup")

    def test_mid_test_goto_excluded(self):
        nav = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Playwright",
            "feature_type": "ui_action",
            "source_kind": "test_body",
            "name": "page.goto",
            "raw_code": "await page.goto('/settings')",
            "line": 20,
        })
        rows, stats = resolve_test_intent_units([nav], first_non_navigation_ui_line=15)
        self.assertEqual(len(rows), 0)
        self.assertEqual(stats["navigation_bootstrap_rejected"], 1)

    def test_only_first_goto_before_click_is_bootstrap(self):
        nav1 = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Playwright",
            "feature_type": "ui_action",
            "source_kind": "test_body",
            "name": "page.goto",
            "raw_code": "await page.goto('/login')",
            "line": 10,
        })
        nav2 = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Playwright",
            "feature_type": "ui_action",
            "source_kind": "test_body",
            "name": "page.goto",
            "raw_code": "await page.goto('/home')",
            "line": 11,
        })
        rows, stats = resolve_test_intent_units(
            [nav1, nav2], first_non_navigation_ui_line=15
        )
        bootstrap = [r for r in rows if r["primary_intent"] == "navigation_bootstrap"]
        self.assertEqual(len(bootstrap), 1)
        self.assertEqual(bootstrap[0]["line"], 10)
        self.assertEqual(stats["navigation_bootstrap_rejected"], 1)

    def test_unclear_prior_setup_blocks_bootstrap(self):
        setup_unclear = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Playwright",
            "feature_type": "setup",
            "source_kind": "test_body",
            "name": "unknownSetup",
            "raw_code": "await unknownSetup()",
            "line": 3,
        })
        nav = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Playwright",
            "feature_type": "ui_action",
            "source_kind": "test_body",
            "name": "page.goto",
            "raw_code": "await page.goto('/')",
            "line": 10,
        })
        rows, stats = resolve_test_intent_units(
            [setup_unclear, nav], first_non_navigation_ui_line=15
        )
        self.assertIsNone(setup_unclear)
        self.assertEqual(rows[0]["primary_intent"], "navigation_bootstrap")
        self.assertEqual(stats["navigation_bootstrap_rejected"], 0)

    def test_ast_navigation_bootstrap_eligibility(self):
        nav = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Playwright",
            "feature_type": "ui_action",
            "source_kind": "test_body",
            "name": "page.goto",
            "raw_code": "await page.goto('/dashboard')",
            "line": 5,
            "navigation_bootstrap_candidate_ast": 1,
            "framework_api_category": "navigation",
            "navigation_target_ast": "/dashboard",
        })
        self.assertIsNotNone(nav)
        self.assertEqual(nav["eligibility_basis"], "navigation_bootstrap_ast")
        rows, _ = resolve_test_intent_units([nav], first_non_navigation_ui_line=10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["primary_intent"], "navigation_bootstrap")

    def test_helper_body_phase_on_wrapper_only(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "helper_call",
            "source_kind": "test_body",
            "name": "resetAndSeed",
            "raw_code": "resetAndSeed()",
            "line": 4,
            "wrapper_only": True,
            "helper_body_phase_hint_ast": "setup_and_teardown",
            "helper_body_phase_hint_basis_ast": "ast_nested_framework_api",
        })
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["phase"], "setup_and_teardown")
        self.assertEqual(rows[0]["wrapper_only"], 1)

    def test_structured_helper_body_phase_counts_as_structured(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "helper_call",
            "source_kind": "test_body",
            "name": "seedViaApi",
            "raw_code": "seedViaApi()",
            "line": 4,
            "wrapper_only": True,
            "helper_body_phase_hint_ast": "setup",
            "helper_body_phase_hint_basis_ast": "ast_known_framework_api",
        })
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["phase"], "setup")
        self.assertEqual(rows[0]["structured_evidence_available"], 1)

    def test_heuristic_helper_body_phase_is_not_structured(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "helper_call",
            "source_kind": "test_body",
            "name": "cleanupWrapper",
            "raw_code": "cleanupWrapper()",
            "line": 4,
            "wrapper_only": True,
            "helper_body_phase_hint_ast": "teardown",
            "helper_body_phase_hint_basis_ast": "callee_name_heuristic",
        })
        self.assertIsNone(cand)

    def test_workflow_name_heuristic_is_not_structured_rq1_evidence(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Playwright",
            "feature_type": "helper_call",
            "source_kind": "beforeEach",
            "name": "setupUser",
            "raw_code": "setupUser()",
            "line": 4,
            "workflow_kind_ast": "domain_helper",
            "workflow_kind_basis_ast": "ast_helper_name_heuristic",
        })
        self.assertIsNone(cand)

    def test_statement_phase_not_mixed_body(self):
        wrapper = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "helper_call",
            "source_kind": "test_body",
            "name": "resetAndSeed",
            "raw_code": "resetAndSeed()",
            "line": 4,
            "wrapper_only": True,
            "helper_body_phase_hint_ast": "setup_and_teardown",
        })
        body_stmt = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "network_mock",
            "source_kind": "imported_helper",
            "name": "cy.request",
            "raw_code": "cy.request('POST', '/seed')",
            "line": 6,
            "helper_depth": 1,
            "statement_phase_hint_ast": "setup",
            "framework_api_category": "test_data_api",
        })
        rows, _ = resolve_test_intent_units([wrapper, body_stmt])
        body_row = next(r for r in rows if r["name"] == "cy.request")
        self.assertEqual(body_row["phase"], "setup")
        self.assertNotEqual(body_row["phase"], "setup_and_teardown")

    def test_goto_after_setup_intercept_excluded(self):
        intercept = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "network_mock",
            "source_kind": "beforeEach",
            "name": "cy.intercept",
            "raw_code": "cy.intercept('GET', '/api')",
            "line": 5,
        })
        nav = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Playwright",
            "feature_type": "ui_action",
            "source_kind": "test_body",
            "name": "page.goto",
            "raw_code": "await page.goto('/')",
            "line": 10,
        })
        rows, _ = resolve_test_intent_units([intercept, nav], first_non_navigation_ui_line=15)
        intents = [r["primary_intent"] for r in rows]
        self.assertIn("network_mock_or_spy", intents)
        self.assertNotIn("navigation_bootstrap", intents)

    def test_hook_visit_after_intercept_in_same_hook_allowed(self):
        hook_key = "repo/file.ts:beforeEach:10"
        intercept = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "network_mock",
            "source_kind": "beforeEach",
            "name": "cy.intercept",
            "raw_code": "cy.intercept('GET', '/api')",
            "line": 5,
            "hook_instance_key": hook_key,
            "source_start_offset": 100,
            "source_end_offset": 140,
        })
        visit = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "ui_action",
            "source_kind": "beforeEach",
            "name": "cy.visit",
            "raw_code": "cy.visit('/')",
            "line": 6,
            "hook_instance_key": hook_key,
            "navigation_bootstrap_candidate_ast": 1,
            "framework_api_category": "navigation",
            "source_start_offset": 150,
            "source_end_offset": 170,
        })
        rows, _ = resolve_test_intent_units([intercept, visit], first_non_navigation_ui_line=20)
        intents = [r["primary_intent"] for r in rows]
        self.assertIn("navigation_bootstrap", intents)

    def test_different_hook_instances_block_nav_bootstrap(self):
        intercept = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "network_mock",
            "source_kind": "beforeEach",
            "name": "cy.intercept",
            "raw_code": "cy.intercept('GET', '/api')",
            "line": 5,
            "hook_instance_key": "file.ts:beforeEach:10",
        })
        visit = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "ui_action",
            "source_kind": "beforeEach",
            "name": "cy.visit",
            "raw_code": "cy.visit('/')",
            "line": 6,
            "hook_instance_key": "file.ts:beforeEach:40",
            "navigation_bootstrap_candidate_ast": 1,
            "framework_api_category": "navigation",
        })
        rows, stats = resolve_test_intent_units([intercept, visit], first_non_navigation_ui_line=20)
        self.assertNotIn("navigation_bootstrap", [r["primary_intent"] for r in rows])
        self.assertEqual(stats["navigation_bootstrap_rejected"], 1)

    def test_setup_and_teardown_blocks_nav_bootstrap(self):
        mixed = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "helper_call",
            "source_kind": "test_body",
            "name": "resetAndSeed",
            "raw_code": "resetAndSeed()",
            "line": 3,
            "wrapper_only": True,
            "helper_body_phase_hint_ast": "setup_and_teardown",
            "helper_body_phase_hint_basis_ast": "ast_nested_framework_api",
        })
        nav = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Playwright",
            "feature_type": "ui_action",
            "source_kind": "test_body",
            "name": "page.goto",
            "raw_code": "await page.goto('/')",
            "line": 10,
        })
        rows, stats = resolve_test_intent_units([mixed, nav], first_non_navigation_ui_line=15)
        self.assertNotIn("navigation_bootstrap", [r["primary_intent"] for r in rows])
        self.assertEqual(stats["navigation_bootstrap_rejected"], 1)

    def test_cypress_command_role_maps_to_setup_phase(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "custom_command_call",
            "source_kind": "beforeEach",
            "name": "cy.seedData",
            "raw_code": "cy.seedData()",
            "line": 2,
            "cypress_command_role_ast": "test_data_setup",
            "cypress_command_role_basis_ast": "ast_cypress_request_call",
        })
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["phase"], "setup")


class TestPrimaryIntent(unittest.TestCase):
    def test_session_setup_role(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "custom_command_call",
            "source_kind": "beforeEach",
            "name": "cy.login",
            "raw_code": "cy.login()",
            "line": 3,
            "cypress_command_role_ast": "session_setup",
            "cypress_command_role_basis_ast": "ast_cypress_session_call",
        })
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["primary_intent"], "auth_session_state")
        self.assertEqual(rows[0]["confidence"], "high")

    def test_known_auth_apis_map_to_auth_session(self):
        cases = [
            (
                "setup",
                "page.context.storageState",
                "await page.context().storageState({ path })",
                "beforeEach",
                '["page", "context", "storageState"]',
                "[]",
            ),
            ("setup", "t.useRole", "await t.useRole(admin)", "beforeEach", '["t", "useRole"]', "[]"),
            (
                "browser_context_control",
                "localStorage.setItem",
                "localStorage.setItem('token', token)",
                "beforeEach",
                '["localStorage", "setItem"]',
                '["token"]',
            ),
        ]
        expected_by_raw = {
            "localStorage.setItem('token', token)": "browser_context_or_client_state",
        }
        for ft, name, raw, source_kind, chain, literals in cases:
            with self.subTest(raw=raw):
                cand = build_intent_candidate({
                    "repo": "r",
                    "test_id": "t",
                    "framework": "Cypress",
                    "feature_type": ft,
                    "source_kind": source_kind,
                    "name": name,
                    "raw_code": raw,
                    "callee_chain_json": chain,
                    "literal_args_json": literals,
                    "line": 3,
                })
                self.assertIsNotNone(cand)
                rows, _ = resolve_test_intent_units([cand])
                self.assertEqual(rows[0]["primary_intent"], expected_by_raw.get(raw, "auth_session_state"))

    def test_auth_names_without_resolved_body_are_not_rq1_eligible(self):
        cases = [
            ("helper_call", "apiLogin", "await apiLogin(user)", "beforeEach"),
            ("custom_command_call", "cy.apiLogin", "cy.apiLogin(user)", "test_body"),
            ("custom_command_call", "cy.visitWithLogin", "cy.visitWithLogin('/home')", "beforeEach"),
            ("helper_call", "ShowPage.logout", "ShowPage.logout()", "beforeEach"),
            ("setup", "setAuthHeader", 'headers: { Authorization: `Bearer ${token}` }', "beforeEach"),
        ]
        for ft, name, raw, source_kind in cases:
            with self.subTest(raw=raw):
                cand = build_intent_candidate({
                    "repo": "r",
                    "test_id": "t",
                    "framework": "Cypress",
                    "feature_type": ft,
                    "source_kind": source_kind,
                    "name": name,
                    "raw_code": raw,
                    "line": 3,
                })
                self.assertIsNone(cand)

    def test_hook_navigation_helper_name_without_resolved_body_is_not_rq1(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "helper_call",
            "source_kind": "before",
            "name": "AppSidebar.navigate",
            "raw_code": "AppSidebar.navigate(AppSidebarButton.Editor)",
            "line": 30,
        })
        self.assertIsNone(cand)

    def test_helper_implementation_navigation_without_lifecycle_context_is_not_rq1(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Playwright",
            "feature_type": "ui_action",
            "source_kind": "imported_helper",
            "name": "page.goto",
            "raw_code": "await page.goto('/admin')",
            "navigation_bootstrap_candidate_ast": 1,
            "line": 24,
        })
        self.assertIsNone(cand)

    def test_helper_implementation_lexical_helper_name_is_not_rq1(self):
        for name, raw, source_kind in (
            ("seedUser", "seedUser()", "imported_helper"),
            ("headerAuth", "headerAuth()", "imported_helper"),
            ("cy.apiDeactivateUser", "cy.apiDeactivateUser(user.id)", "cypress_command"),
            ("cy.apiLogin", "cy.apiLogin(user)", "cypress_command"),
        ):
            with self.subTest(name=name):
                cand = build_intent_candidate({
                    "repo": "r",
                    "test_id": "t",
                    "framework": "Cypress",
                    "feature_type": "custom_command_call" if name.startswith("cy.") else "helper_call",
                    "source_kind": source_kind,
                    "name": name,
                    "raw_code": raw,
                    "line": 30,
                })
                self.assertIsNone(cand)

    def test_helper_implementation_custom_command_role_without_lifecycle_context_is_not_rq1(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "custom_command_call",
            "source_kind": "cypress_command",
            "name": "cy.oktaGetUser",
            "raw_code": "cy.oktaGetUser(user.email)",
            "cypress_command_role_ast": "test_data_setup",
            "cypress_command_role_basis_ast": "ast_cypress_data_call",
            "line": 226,
        })
        self.assertIsNone(cand)

    def test_login_navigation_alone_remains_navigation_bootstrap(self):
        nav = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Playwright",
            "feature_type": "ui_action",
            "source_kind": "test_body",
            "name": "page.goto",
            "raw_code": "await page.goto('/login')",
            "line": 2,
        })
        rows, _ = resolve_test_intent_units([nav], first_non_navigation_ui_line=10)
        self.assertEqual(rows[0]["primary_intent"], "navigation_bootstrap")

    def test_custom_api_create_maps_to_backend_data_not_network_mock(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "custom_command_call",
            "source_kind": "beforeEach",
            "name": "cy.headlessCreateTask",
            "raw_code": "cy.headlessCreateTask({ title: 'x' })",
            "line": 3,
            "cypress_command_role_ast": "test_data_setup",
            "cypress_command_role_basis_ast": "ast_cypress_data_call",
        })
        self.assertIsNotNone(cand)
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["primary_intent"], "test_data_or_backend_state")

    def test_network_mock_and_backend_data_precedence(self):
        cases = [
            ("network_mock", "cy.intercept", "cy.intercept('POST', '/api/createUser')", "network_mock_or_spy"),
            ("network_mock", "cy.intercept", "cy.intercept('GET', '/logout')", "network_mock_or_spy"),
            ("setup", "page.route", "await page.route('/login', route => route.fulfill())", "network_mock_or_spy"),
            ("setup", "route.fulfill", "await route.fulfill({ json: user })", "network_mock_or_spy"),
            ("custom_command_call", "cy.apiDeleteUser", "cy.apiDeleteUser(id)", "test_data_or_backend_state"),
            ("custom_command_call", "cy.dbSeedUser", "cy.dbSeedUser()", "test_data_or_backend_state"),
            ("custom_command_call", "cy.mockSeedDb", "cy.mockSeedDb()", "test_data_or_backend_state"),
            ("setup", "cy.task", "cy.task('resetDb')", "test_data_or_backend_state"),
        ]
        for ft, name, raw, expected in cases:
            with self.subTest(raw=raw):
                feature = {
                    "repo": "r",
                    "test_id": "t",
                    "framework": "Cypress",
                    "feature_type": ft,
                    "source_kind": "beforeEach",
                    "name": name,
                    "raw_code": raw,
                    "line": 3,
                }
                if ft == "custom_command_call":
                    feature.update({
                        "cypress_command_role_ast": "test_data_setup",
                        "cypress_command_role_basis_ast": "ast_cypress_data_call",
                    })
                if name == "cy.task":
                    feature.update({
                        "callee_chain_json": '["cy", "task"]',
                        "literal_args_json": '["resetDb"]',
                        "framework_api_category": "backend_task",
                        "framework_api_category_basis_ast": "ast_cypress_task_handler",
                        "cypress_task_role_ast": "test_data_setup",
                        "cypress_task_role_basis_ast": "ast_task_handler_callee",
                    })
                cand = build_intent_candidate(feature)
                self.assertIsNotNone(cand)
                rows, _ = resolve_test_intent_units([cand])
                self.assertEqual(rows[0]["primary_intent"], expected)

    def test_audited_rq1_targeted_intent_fixes(self):
        cases = [
            (
                "custom_command_call",
                "beforeEach",
                "cy.headlessCreateTask",
                "cy.headlessCreateTask({ title: 'x' })",
                "test_data_or_backend_state",
                "per_test_hook",
            ),
            (
                "custom_command_call",
                "afterEach",
                "cy.apiDeleteTeam",
                "cy.apiDeleteTeam(team.id)",
                "test_data_or_backend_state",
                "per_test_hook",
            ),
            (
                "custom_command_call",
                "beforeEach",
                "cy.apiPatchMe",
                "cy.apiPatchMe({ timezone: 'UTC' })",
                "test_data_or_backend_state",
                "per_test_hook",
            ),
            (
                "custom_command_call",
                "afterEach",
                "cy.LogOut",
                "cy.LogOut()",
                "auth_session_state",
                "per_test_hook",
            ),
            (
                "browser_context_control",
                "beforeEach",
                "cy.setCookie",
                'cy.setCookie("plasmic_seed", "1")',
                "browser_context_or_client_state",
                "per_test_hook",
            ),
        ]
        for ft, source_kind, name, raw, expected_intent, expected_scope in cases:
            with self.subTest(raw=raw):
                feature = {
                    "repo": "r",
                    "test_id": "t",
                    "framework": "Cypress",
                    "feature_type": ft,
                    "source_kind": source_kind,
                    "name": name,
                    "raw_code": raw,
                    "line": 3,
                }
                if ft == "custom_command_call":
                    feature.update({
                        "cypress_command_role_ast": (
                            "session_setup" if "logout" in name.lower() else "test_data_setup"
                        ),
                        "cypress_command_role_basis_ast": "ast_cypress_data_call",
                    })
                if name == "cy.setCookie":
                    feature.update({
                        "callee_chain_json": '["cy", "setCookie"]',
                        "literal_args_json": '["plasmic_seed", "1"]',
                    })
                cand = build_intent_candidate(feature)
                self.assertIsNotNone(cand)
                rows, _ = resolve_test_intent_units([cand])
                self.assertEqual(rows[0]["primary_intent"], expected_intent)
                self.assertEqual(rows[0]["scope"], expected_scope)

    def test_audited_rq1_intent_precedence_uses_structured_api_semantics(self):
        cases = [
            (
                {
                    "feature_type": "custom_command_call",
                    "source_kind": "beforeEach",
                    "name": "cy.apiLogin",
                    "raw_code": "cy.apiLogin(this.mainUser)",
                    "callee_chain_json": '["cy", "apiLogin"]',
                    "cypress_command_role_ast": "test_data_setup",
                    "cypress_command_role_basis_ast": "ast_cypress_data_call",
                },
                "auth_session_state",
            ),
            (
                {
                    "feature_type": "custom_command_call",
                    "source_kind": "beforeEach",
                    "name": "cy.apiAccessToken",
                    "raw_code": "cy.apiAccessToken(botUserId, 'Create token')",
                    "callee_chain_json": '["cy", "apiAccessToken"]',
                    "cypress_command_role_ast": "test_data_setup",
                    "cypress_command_role_basis_ast": "ast_cypress_data_call",
                },
                "auth_session_state",
            ),
            (
                {
                    "feature_type": "setup",
                    "source_kind": "beforeEach",
                    "name": "cy.request",
                    "raw_code": 'cy.request({ url: "/api/v1/auth/login", method: "POST", body: { email, password } })',
                    "callee_chain_json": '["cy", "request"]',
                    "framework_api_category": "test_data_api",
                    "framework_api_category_basis_ast": "ast_known_framework_api",
                },
                "test_data_or_backend_state",
            ),
            (
                {
                    "feature_type": "setup",
                    "source_kind": "afterEach",
                    "name": "cy.request",
                    "raw_code": 'cy.request({ method: "DELETE", url: "api/v1/workspaces/" + workspaceId })',
                    "callee_chain_json": '["cy", "request"]',
                    "framework_api_category": "test_data_api",
                    "framework_api_category_basis_ast": "ast_known_framework_api",
                },
                "test_data_or_backend_state",
            ),
            (
                {
                    "feature_type": "setup",
                    "source_kind": "beforeEach",
                    "name": "cy.headlessCreateTask",
                    "raw_code": "cy.headlessCreateTask({ title: 'x' })",
                    "callee_chain_json": '["cy", "headlessCreateTask"]',
                    "framework_api_category": "network_mock",
                    "framework_api_category_basis_ast": "ast_known_framework_api",
                },
                "test_data_or_backend_state",
            ),
            (
                {
                    "feature_type": "setup",
                    "source_kind": "beforeEach",
                    "name": "Cypress._.times",
                    "raw_code": "Cypress._.times(15, () => cy.request('/api/v1/users'))",
                    "callee_chain_json": '["Cypress", "_", "times"]',
                    "framework_api_category": "test_data_api",
                    "framework_api_category_basis_ast": "ast_known_framework_api",
                },
                "test_data_or_backend_state",
            ),
        ]
        for feature, expected_intent in cases:
            with self.subTest(raw=feature["raw_code"]):
                cand = build_intent_candidate({
                    "repo": "r",
                    "test_id": "t",
                    "framework": "Cypress",
                    "line": 3,
                    **feature,
                })
                self.assertIsNotNone(cand)
                rows, _ = resolve_test_intent_units([cand])
                self.assertEqual(rows[0]["primary_intent"], expected_intent)

    def test_latest_audit_rq1_intent_and_eligibility_regressions(self):
        intent_cases = [
            (
                {
                    "framework": "Playwright",
                    "feature_type": "setup",
                    "source_kind": "beforeAll",
                    "name": "page.evaluate",
                    "raw_code": """await page.evaluate(async ({ baseUrl, org, authorization, destinationPayload }) => {
                        await fetch(`${baseUrl}/api/${org}/alerts/destinations`, {
                            method: "POST",
                            headers: { Authorization: authorization },
                            body: JSON.stringify(destinationPayload)
                        });
                    })""",
                    "callee_chain_json": '["page", "evaluate", "fetch"]',
                    "framework_api_category": "test_data_api",
                    "framework_api_category_basis_ast": "ast_nested_framework_api",
                },
                "test_data_or_backend_state",
            ),
            (
                {
                    "framework": "Playwright",
                    "feature_type": "ui_action",
                    "source_kind": "test_body",
                    "name": "page.goto",
                    "raw_code": "await page.goto(`/sign/${recipient.token}`)",
                    "callee_chain_json": '["page", "goto"]',
                    "framework_api_category": "navigation",
                    "framework_api_category_basis_ast": "ast_known_framework_api",
                    "navigation_bootstrap_candidate_ast": True,
                },
                "navigation_bootstrap",
            ),
            (
                {
                    "framework": "Cypress",
                    "feature_type": "cypress_test_utility",
                    "source_kind": "beforeEach",
                    "name": "cy.clock.then",
                    "raw_code": "cy.clock().then((clock) => { mockGetEventsPolling(); clock.tick(2000); })",
                    "callee_chain_json": '["cy", "clock", "then"]',
                    "framework_api_category": "time_device_emulation",
                    "framework_api_category_basis_ast": "ast_nested_framework_api",
                },
                "time_device_permission_emulation",
            ),
            (
                {
                    "framework": "Cypress",
                    "feature_type": "cypress_test_utility",
                    "source_kind": "beforeEach",
                    "name": "cy.makeClient.then",
                    "raw_code": "cy.makeClient().then((client) => { Cypress._.times(3, () => cy.postMessageAs(client, channelId)); })",
                    "callee_chain_json": '["cy", "makeClient", "then"]',
                    "framework_api_category": "test_data_api",
                    "framework_api_category_basis_ast": "ast_nested_framework_api",
                },
                "test_data_or_backend_state",
            ),
        ]
        for feature, expected_intent in intent_cases:
            with self.subTest(raw=feature["raw_code"]):
                cand = build_intent_candidate({
                    "repo": "r",
                    "test_id": "t",
                    "line": 3,
                    **feature,
                })
                self.assertIsNotNone(cand)
                rows, _ = resolve_test_intent_units([cand], first_non_navigation_ui_line=20)
                self.assertEqual(rows[0]["primary_intent"], expected_intent)

        excluded_cases = [
            {
                "framework": "Cypress",
                "feature_type": "setup",
                "source_kind": "beforeEach",
                "name": "cy.request",
                "raw_code": "cy.request({ url: `/api/teams/${teamId}/channels` }).then((res) => res.body.channels)",
                "callee_chain_json": '["cy", "request", "then"]',
                "framework_api_category": "test_data_api",
                "framework_api_category_basis_ast": "ast_nested_framework_api",
            },
            {
                "framework": "Cypress",
                "feature_type": "setup",
                "source_kind": "beforeEach",
                "name": "cy.task",
                "raw_code": "cy.task('dbGetUser', userId).then((user) => user.email)",
                "callee_chain_json": '["cy", "task", "then"]',
                "literal_args_json": '["dbGetUser"]',
                "framework_api_category": "backend_task",
                "framework_api_category_basis_ast": "ast_known_framework_api",
            },
            {
                "framework": "Playwright",
                "feature_type": "assertion",
                "source_kind": "beforeEach",
                "name": "expect(route.request().headers()[\"Authorization\"]).toBeDefined",
                "raw_code": "expect(route.request().headers()[\"Authorization\"]).toBeDefined()",
                "callee_chain_json": '["expect", "toBeDefined"]',
                "framework_api_category": "test_data_api",
                "framework_api_category_basis_ast": "ast_nested_framework_api",
            },
        ]
        for feature in excluded_cases:
            with self.subTest(raw=feature["raw_code"]):
                cand = build_intent_candidate({
                    "repo": "r",
                    "test_id": "t",
                    "line": 3,
                    **feature,
                })
                self.assertIsNone(cand)

    def test_corpus_shape_read_only_task_wrappers_and_admin_post_routing(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "cypress_test_utility",
            "source_kind": "cypress_command",
            "name": "cy.task('dbGetUser', {dbConfig, params}).then",
            "raw_code": "cy.task('dbGetUser', {dbConfig, params}).then(({user}) => cy.wrap({user}))",
            "framework_api_category": "test_data_api",
            "framework_api_category_basis_ast": "ast_nested_framework_api",
            "line": 3,
        })
        self.assertIsNone(cand)

        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "setup",
            "source_kind": "before",
            "name": "cy.task",
            "raw_code": """cy.task('keycloakRequest', {
                baseUrl: `${keycloakBaseUrl}/auth/admin/realms`,
                method: 'POST',
                data: realm,
                headers: { Authorization: `Bearer ${accessToken}` },
            })""",
            "callee_chain_json": '["cy", "task"]',
            "framework_api_category": "backend_task",
            "framework_api_category_basis_ast": "ast_nested_framework_api",
            "line": 3,
        })
        self.assertIsNotNone(cand)
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["primary_intent"], "test_data_or_backend_state")

        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "cypress_test_utility",
            "source_kind": "cypress_command",
            "name": "cy.task('keycloakRequest', { baseUrl: `${keycloakBaseUrl}/auth/admin/realms`, method: 'POST'",
            "raw_code": """cy.task('keycloakRequest', {
                baseUrl: `${keycloakBaseUrl}/auth/admin/realms`,
                method: 'POST',
                data: realm,
                headers: { Authorization: `Bearer ${accessToken}` },
            }).then((response) => expect(response.status).to.equal(201))""",
            "framework_api_category": "backend_task",
            "framework_api_category_basis_ast": "ast_nested_framework_api",
            "statement_phase_hint_ast": "setup",
            "statement_phase_hint_basis_ast": "ast_nested_framework_api",
            "line": 3,
        })
        self.assertIsNotNone(cand)
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["primary_intent"], "test_data_or_backend_state")

    def test_audited_rq1_corpus_shapes_without_callee_chain_use_specific_intent(self):
        cases = [
            (
                {
                    "feature_type": "cypress_test_utility",
                    "source_kind": "cypress_command",
                    "name": 'cy.request({ method: "DELETE", url: "api/v1/applications/" + appId }).then',
                    "raw_code": 'cy.request({ method: "DELETE", url: "api/v1/applications/" + appId }).then((response) => {})',
                    "framework_api_category": "test_data_api",
                    "framework_api_category_basis_ast": "ast_nested_framework_api",
                },
                "test_data_or_backend_state",
            ),
            (
                {
                    "feature_type": "cypress_test_utility",
                    "source_kind": "cypress_command",
                    "name": """cy.request({
      method: "DELETE",
      url: "api/v1/applications/" + appId,
      failOnStatusCode: false,
      headers: {
        "X-Requested-By": "Appsmith",
      },
    }).then""",
                    "raw_code": """cy.request({
      method: "DELETE",
      url: "api/v1/applications/" + appId,
      failOnStatusCode: false,
      headers: {
        "X-Requested-By": "Appsmith",
      },
    }).then((response) => {
      cy.log(response.body);
      cy.log(response.status);
    })""",
                },
                "test_data_or_backend_state",
            ),
            (
                {
                    "feature_type": "cypress_test_utility",
                    "source_kind": "before",
                    "name": "cy.headlessCreateTask({ name: taskName, source_storage: { location: 'local' } })",
                    "raw_code": "cy.headlessCreateTask({ name: taskName, source_storage: { location: 'local' } })",
                    "callee_chain_json": '["cy", "headlessCreateTask", "source_storage"]',
                    "framework_api_category": "network_mock",
                    "framework_api_category_basis_ast": "ast_nested_framework_api",
                },
                "test_data_or_backend_state",
            ),
            (
                {
                    "feature_type": "cypress_test_utility",
                    "source_kind": "test_body",
                    "name": "cy.makeClient().then",
                    "raw_code": "cy.makeClient().then((client) => { Cypress._.times(15, () => client.createPost()) })",
                    "framework_api_category": "time_device_emulation",
                    "framework_api_category_basis_ast": "ast_nested_framework_api",
                },
                "test_data_or_backend_state",
            ),
        ]
        for feature, expected_intent in cases:
            with self.subTest(raw=feature["raw_code"]):
                cand = build_intent_candidate({
                    "repo": "r",
                    "test_id": "t",
                    "framework": "Cypress",
                    "line": 3,
                    **feature,
                })
                self.assertIsNotNone(cand)
                rows, _ = resolve_test_intent_units([cand])
                self.assertEqual(rows[0]["primary_intent"], expected_intent)

    def test_locator_shadow_and_logger_only_rows_are_not_rq1_eligible(self):
        cases = [
            (
                "locator",
                "beforeEach",
                "user2Page.locator",
                "user2Page.locator('.payload__modal-container')",
            ),
            (
                "wait_synchronization",
                "beforeEach",
                "getStudioFrame(page).locator.waitFor",
                "getStudioFrame(page).locator('.x').waitFor({ timeout: 60000, state: 'attached' })",
            ),
            (
                "wait_synchronization",
                "afterAll",
                "cleanupPage.waitForLoadState",
                "await cleanupPage.waitForLoadState('networkidle')",
            ),
            (
                "wait_synchronization",
                "afterEach",
                "page.getByText('Are you sure you want to delete the dashboard?').waitFor",
                "page.getByText('Are you sure you want to delete the dashboard?').waitFor({ state: 'visible' })",
            ),
            (
                "wait_synchronization",
                "beforeEach",
                "page.waitForSelector",
                "page.waitForSelector('[data-test=\"login-user-id\"]', { timeout: 10000 })",
            ),
            (
                "cypress_subject_control",
                "beforeEach",
                "cy.get('[ui5-tokenizer]').shadow",
                'cy.get("[ui5-tokenizer]").shadow()',
            ),
            (
                "helper_call",
                "afterEach",
                "testLogger.warn",
                'testLogger.warn("Cleanup failed", error)',
            ),
        ]
        for ft, source_kind, name, raw in cases:
            with self.subTest(raw=raw):
                cand = build_intent_candidate({
                    "repo": "r",
                    "test_id": "t",
                    "framework": "Playwright",
                    "feature_type": ft,
                    "source_kind": source_kind,
                    "name": name,
                    "raw_code": raw,
                    "line": 3,
                })
                self.assertIsNone(cand)

    def test_bare_context_access_is_not_rq1_eligible(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Playwright",
            "feature_type": "setup",
            "source_kind": "beforeEach",
            "name": "page.context",
            "raw_code": "page.context()",
            "line": 3,
        })
        self.assertIsNone(cand)

    def test_cypress_query_then_wrapper_is_not_own_rq1_unit(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "cypress_test_utility",
            "source_kind": "before",
            "name": "cy.url().then",
            "raw_code": "cy.url().then((url) => { if (url.includes('setup')) { cy.SignupFromAPI(); } })",
            "line": 3,
        })
        self.assertIsNone(cand)

    def test_read_only_context_query_is_not_rq1_eligible(self):
        for name, raw in (
            ("page.context().cookies", "page.context().cookies()"),
            ("page.context().storageState", "page.context().storageState()"),
            ("page.context().waitForEvent", "page.context().waitForEvent('page')"),
        ):
            with self.subTest(raw=raw):
                cand = build_intent_candidate({
                    "repo": "r",
                    "test_id": "t",
                    "framework": "Playwright",
                    "feature_type": "browser_context_control",
                    "source_kind": "test_body",
                    "name": name,
                    "raw_code": raw,
                    "line": 3,
                })
                self.assertIsNone(cand)

    def test_verification_named_helper_is_not_setup_from_name_only(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Playwright",
            "feature_type": "helper_call",
            "source_kind": "test_body",
            "name": "verifyTabsSetup",
            "raw_code": "verifyTabsSetup()",
            "line": 3,
        })
        self.assertIsNone(cand)

    def test_support_before_hook_uses_suite_scope(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "setup",
            "source_kind": "before",
            "name": "cy.task",
            "raw_code": "cy.task('seed database')",
            "callee_chain_json": '["cy", "task"]',
            "literal_args_json": '["seed database"]',
            "hook_instance_key": "support:hooks.ts:10:before:",
            "framework_api_category": "backend_task",
            "framework_api_category_basis_ast": "ast_cypress_task_handler",
            "cypress_task_role_ast": "test_data_setup",
            "cypress_task_role_basis_ast": "ast_task_handler_callee",
            "line": 3,
        })
        self.assertIsNotNone(cand)
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["scope"], "suite_or_fixture")

    def test_cypress_task_registered_name_only_is_not_eligible(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "setup",
            "source_kind": "beforeEach",
            "name": "cy.task",
            "raw_code": "cy.task('seed database')",
            "callee_chain_json": '["cy", "task"]',
            "literal_args_json": '["seed database"]',
            "framework_api_category": "backend_task",
            "framework_api_category_basis_ast": "ast_cypress_task_handler",
            "cypress_task_role_ast": "test_data_setup",
            "cypress_task_role_basis_ast": "ast_task_handler_registered_name",
            "line": 3,
        })
        self.assertIsNone(cand)

    def test_untrusted_helper_child_intent_falls_back_to_generic(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "helper_call",
            "source_kind": "beforeEach",
            "name": "setupCustomProfileAttributeValues",
            "raw_code": "setupCustomProfileAttributeValues(userClient)",
            "helper_resolution_status": "unresolved",
            "child_setup_unit_count": 2,
            "dominant_child_intent": "test_data_or_backend_state",
            "child_intent_counts_json": '{"test_data_or_backend_state": 2}',
            "line": 3,
        })
        self.assertIsNone(cand)

    def test_inline_body_child_intent_drives_hook_helper(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "helper_call",
            "source_kind": "before",
            "name": "sysadminSetup",
            "raw_code": "sysadminSetup(response.user)",
            "helper_resolution_status": "inline_body",
            "child_setup_unit_count": 11,
            "dominant_child_intent": "test_data_or_backend_state",
            "child_intent_counts_json": '{"test_data_or_backend_state": 11}',
            "line": 116,
        })
        self.assertIsNotNone(cand)
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["phase"], "setup")
        self.assertEqual(rows[0]["scope"], "suite_or_fixture")
        self.assertEqual(rows[0]["primary_intent"], "test_data_or_backend_state")
        self.assertEqual(rows[0]["primary_intent_evidence_basis"], "resolved_helper_child_intents")

    def test_generic_stub_without_structured_state_is_not_rq1(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "setup",
            "source_kind": "before",
            "name": "cy.stub",
            "raw_code": 'cy.stub(internals, "search").callsFake(() => results)',
            "line": 3,
        })
        self.assertIsNone(cand)

    def test_resolved_helper_child_intent_drives_wrapper(self):
        wrapper = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "helper_call",
            "source_kind": "test_body",
            "name": "setupUser",
            "raw_code": "setupUser()",
            "line": 4,
            "wrapper_only": True,
            "helper_body_phase_hint_ast": "setup",
            "helper_body_phase_hint_basis_ast": "ast_known_framework_api",
        })
        child = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "setup",
            "source_kind": "imported_helper",
            "helper_name": "setupUser",
            "helper_depth": 1,
            "name": "cy.request",
            "raw_code": "cy.request('POST', '/users')",
            "line": 8,
            "framework_api_category": "test_data_api",
            "framework_api_category_basis_ast": "ast_known_framework_api",
        })
        rows, _ = resolve_test_intent_units([wrapper, child])
        row = next(r for r in rows if r["name"] == "setupUser")
        self.assertEqual(row["primary_intent"], "test_data_or_backend_state")
        self.assertEqual(row["child_setup_unit_count"], 1)
        self.assertEqual(row["dominant_child_intent"], "test_data_or_backend_state")
        self.assertEqual(row["fallback_used"], 0)

    def test_resolved_helper_child_intent_uses_call_site_seed(self):
        wrappers = [
            build_intent_candidate({
                "repo": "r",
                "test_id": "t",
                "framework": "Cypress",
                "feature_type": "helper_call",
                "source_kind": "test_body",
                "name": "setupUser",
                "raw_code": "setupUser()",
                "line": 4,
                "source_start_offset": 100,
                "source_end_offset": 112,
                "wrapper_only": True,
                "helper_body_phase_hint_ast": "setup",
                "helper_body_phase_hint_basis_ast": "ast_known_framework_api",
            }),
            build_intent_candidate({
                "repo": "r",
                "test_id": "t",
                "framework": "Cypress",
                "feature_type": "helper_call",
                "source_kind": "test_body",
                "name": "setupUser",
                "raw_code": "setupUser()",
                "line": 6,
                "source_start_offset": 150,
                "source_end_offset": 162,
                "wrapper_only": True,
                "helper_body_phase_hint_ast": "setup",
                "helper_body_phase_hint_basis_ast": "ast_known_framework_api",
            }),
        ]
        child = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "setup",
            "source_kind": "imported_helper",
            "helper_name": "setupUser",
            "helper_call_line": 6,
            "helper_call_start_offset": 150,
            "helper_call_end_offset": 162,
            "helper_depth": 1,
            "name": "cy.request",
            "raw_code": "cy.request('POST', '/users')",
            "line": 8,
            "framework_api_category": "test_data_api",
            "framework_api_category_basis_ast": "ast_known_framework_api",
        })
        rows, _ = resolve_test_intent_units([*wrappers, child])
        first = next(r for r in rows if r["name"] == "setupUser" and r["line"] == 4)
        second = next(r for r in rows if r["name"] == "setupUser" and r["line"] == 6)
        self.assertEqual(first["child_setup_unit_count"], 0)
        self.assertEqual(second["child_setup_unit_count"], 1)
        self.assertEqual(second["primary_intent"], "test_data_or_backend_state")

    def test_resolved_helper_child_intent_uses_matched_seed_without_source_offsets(self):
        wrappers = [
            build_intent_candidate({
                "repo": "r",
                "test_id": "t",
                "framework": "Cypress",
                "feature_type": "helper_call",
                "source_kind": "test_body",
                "name": "setupUser",
                "raw_code": "setupUser()",
                "line": 4,
                "wrapper_only": True,
                "helper_body_phase_hint_ast": "setup",
                "helper_body_phase_hint_basis_ast": "ast_known_framework_api",
            }),
            build_intent_candidate({
                "repo": "r",
                "test_id": "t",
                "framework": "Cypress",
                "feature_type": "helper_call",
                "source_kind": "test_body",
                "name": "setupUser",
                "raw_code": "setupUser()",
                "line": 6,
                "wrapper_only": True,
                "helper_body_phase_hint_ast": "setup",
                "helper_body_phase_hint_basis_ast": "ast_known_framework_api",
                "matched_helper_call_line": 6,
                "matched_helper_call_start_offset": 150,
                "matched_helper_call_end_offset": 162,
            }),
        ]
        child = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "setup",
            "source_kind": "imported_helper",
            "helper_name": "setupUser",
            "helper_call_line": 6,
            "helper_call_start_offset": 150,
            "helper_call_end_offset": 162,
            "helper_depth": 1,
            "name": "cy.request",
            "raw_code": "cy.request('POST', '/users')",
            "line": 8,
            "framework_api_category": "test_data_api",
            "framework_api_category_basis_ast": "ast_known_framework_api",
        })
        rows, _ = resolve_test_intent_units([*wrappers, child])
        first = next(r for r in rows if r["name"] == "setupUser" and r["line"] == 4)
        second = next(r for r in rows if r["name"] == "setupUser" and r["line"] == 6)
        self.assertEqual(first["child_setup_unit_count"], 0)
        self.assertEqual(second["child_setup_unit_count"], 1)
        self.assertEqual(second["primary_intent"], "test_data_or_backend_state")

    def test_duplicate_helper_names_without_call_seed_do_not_overattach(self):
        wrappers = [
            build_intent_candidate({
                "repo": "r",
                "test_id": "t",
                "framework": "Cypress",
                "feature_type": "helper_call",
                "source_kind": "test_body",
                "name": "setupUser",
                "raw_code": "setupUser()",
                "line": 4,
                "wrapper_only": True,
                "helper_body_phase_hint_ast": "setup",
                "helper_body_phase_hint_basis_ast": "ast_known_framework_api",
            }),
            build_intent_candidate({
                "repo": "r",
                "test_id": "t",
                "framework": "Cypress",
                "feature_type": "helper_call",
                "source_kind": "test_body",
                "name": "setupUser",
                "raw_code": "setupUser()",
                "line": 6,
                "wrapper_only": True,
                "helper_body_phase_hint_ast": "setup",
                "helper_body_phase_hint_basis_ast": "ast_known_framework_api",
            }),
        ]
        child = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "setup",
            "source_kind": "imported_helper",
            "helper_name": "setupUser",
            "helper_depth": 1,
            "name": "cy.request",
            "raw_code": "cy.request('POST', '/users')",
            "line": 8,
            "framework_api_category": "test_data_api",
            "framework_api_category_basis_ast": "ast_known_framework_api",
        })
        rows, _ = resolve_test_intent_units([*wrappers, child])
        wrapper_rows = [r for r in rows if r["name"] == "setupUser"]
        self.assertEqual(len(wrapper_rows), 2)
        self.assertTrue(all(r["child_setup_unit_count"] == 0 for r in wrapper_rows))

    def test_mixed_helper_child_intents_are_reviewed(self):
        wrapper = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "helper_call",
            "source_kind": "test_body",
            "name": "setupWorld",
            "raw_code": "setupWorld()",
            "line": 4,
            "wrapper_only": True,
            "helper_body_phase_hint_ast": "setup",
            "helper_body_phase_hint_basis_ast": "ast_nested_framework_api",
        })
        data_child = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "setup",
            "source_kind": "imported_helper",
            "helper_name": "setupWorld",
            "helper_depth": 1,
            "name": "cy.request",
            "raw_code": "cy.request('POST', '/seed')",
            "line": 8,
            "framework_api_category": "test_data_api",
        })
        mock_child = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "network_mock",
            "source_kind": "imported_helper",
            "helper_name": "setupWorld",
            "helper_depth": 1,
            "name": "cy.intercept",
            "raw_code": "cy.intercept('/api')",
            "line": 9,
            "framework_api_category": "network_mock",
        })
        rows, _ = resolve_test_intent_units([wrapper, data_child, mock_child])
        row = next(r for r in rows if r["name"] == "setupWorld")
        self.assertEqual(row["primary_intent"], "generic_setup_teardown_utility")
        self.assertEqual(row["needs_review"], 1)
        self.assertIn("mixed_intents", row["review_reason"])
        self.assertIn("mixed_intents", row["uncertain_reason"])

    def test_wait_only_is_not_rq1_eligible(self):
        for raw in ("cy.wait(1000)", "await page.waitForTimeout(500)", "sleep(200)"):
            with self.subTest(raw=raw):
                cand = build_intent_candidate({
                    "repo": "r",
                    "test_id": "t",
                    "framework": "Cypress",
                    "feature_type": "setup",
                    "source_kind": "beforeEach",
                    "name": raw.split("(")[0],
                    "raw_code": raw,
                    "line": 3,
                })
                self.assertIsNone(cand)

    def test_hook_scope_wins_over_custom_command_call_scope(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "custom_command_call",
            "source_kind": "before",
            "name": "cy.apiDeactivateTestBots",
            "raw_code": "cy.apiDeactivateTestBots()",
            "cypress_command_role_ast": "test_data_setup",
            "cypress_command_role_basis_ast": "ast_cypress_data_call",
            "line": 3,
        })
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["scope"], "suite_or_fixture")
        self.assertEqual(rows[0]["primary_intent"], "test_data_or_backend_state")

    def test_opaque_auth_helper_call_in_test_body_is_not_rq1_eligible(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Playwright",
            "feature_type": "helper_call",
            "source_kind": "test_body",
            "name": "apiSignin",
            "raw_code": "apiSignin({ page, email: user.email, redirectPath: '/home' })",
            "line": 3,
        })
        self.assertIsNone(cand)

    def test_direct_test_body_custom_api_name_is_not_enough_for_rq1(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "custom_command_call",
            "source_kind": "test_body",
            "name": "cy.apiCreateUser",
            "raw_code": "cy.apiCreateUser({ email })",
            "line": 3,
        })
        self.assertIsNone(cand)

    def test_ast_callee_chain_custom_api_name_is_not_enough_without_call_graph(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "custom_command_call",
            "source_kind": "beforeEach",
            "name": "opaque",
            "raw_code": "opaque()",
            "callee_chain_json": '["cy", "apiCreateUser"]',
            "line": 3,
        })
        self.assertIsNone(cand)

    def test_plain_helper_in_suite_hook_without_resolved_body_is_not_rq1(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "helper_call",
            "source_kind": "before",
            "name": "enableElasticSearch",
            "raw_code": "enableElasticSearch()",
            "line": 3,
        })
        self.assertIsNone(cand)

    def test_hook_context_utility_without_setup_signal_is_not_rq1_eligible(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "cypress_builtin",
            "source_kind": "before",
            "name": "RapidMode.url",
            "raw_code": "RapidMode.url()",
            "line": 3,
        })
        self.assertIsNone(cand)

    def test_hook_context_stub_without_state_is_not_rq1_eligible(self):
        for raw in ("cy.stub()", 'cy.stub(internals, "search")'):
            with self.subTest(raw=raw):
                cand = build_intent_candidate({
                    "repo": "r",
                    "test_id": "t",
                    "framework": "Cypress",
                    "feature_type": "cypress_test_utility",
                    "source_kind": "beforeEach",
                    "name": raw.split("(")[0],
                    "raw_code": raw,
                    "line": 3,
                })
                self.assertIsNone(cand)

    def test_cypress_locator_query_with_token_selector_is_not_auth_setup(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "custom_command_call",
            "source_kind": "test_body",
            "name": 'cy.get("[ui5-token]").eq',
            "raw_code": 'cy.get("[ui5-token]").eq(0)',
            "line": 3,
        })
        self.assertIsNone(cand)

    def test_ast_callee_chain_locator_query_with_token_selector_is_not_auth_setup(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "custom_command_call",
            "source_kind": "test_body",
            "name": "opaque",
            "raw_code": "opaque()",
            "callee_chain_json": '["cy", "get", "eq"]',
            "ui_action_category": "locator_query",
            "line": 3,
        })
        self.assertIsNone(cand)

    def test_hook_context_client_state_signal_remains_rq1_eligible(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "cypress_test_utility",
            "source_kind": "before",
            "name": "cy.window().then",
            "raw_code": 'cy.window().then((window) => { window.localStorage.setItem("flag", "1"); })',
            "framework_api_category": "browser_context_control",
            "framework_api_category_basis_ast": "ast_nested_framework_api",
            "line": 3,
        })
        self.assertIsNotNone(cand)
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["scope"], "suite_or_fixture")
        self.assertEqual(rows[0]["primary_intent"], "browser_context_or_client_state")

    def test_hook_dom_script_injection_without_state_api_is_not_backend_setup(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "cypress_test_utility",
            "source_kind": "before",
            "name": "cy.window().then",
            "raw_code": (
                'cy.window().then(($el) => { const scriptElement = document.createElement("script"); '
                'scriptElement.setAttribute("data-ui5-config", "true"); '
                "scriptElement.innerHTML = JSON.stringify(configurationObject); })"
            ),
            "line": 3,
        })
        self.assertIsNone(cand)

    def test_cypress_utility_reporting_row_is_not_rq1_eligible(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "cypress_test_utility",
            "source_kind": "afterEach",
            "name": "cy.get('@requests.all').then",
            "raw_code": "cy.get('@requests.all').then((calls) => { cy.log(`${calls.length} requests`); expect(calls).to.have.length(1); })",
            "line": 3,
        })
        self.assertIsNone(cand)

    def test_cypress_subject_spy_listener_is_not_rq1_eligible(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "cypress_subject_control",
            "source_kind": "beforeEach",
            "name": "cy.get('[ui5-multi-combobox]').invoke",
            "raw_code": "cy.get('[ui5-multi-combobox]').invoke('on', 'selection-change', cy.spy().as('selectionChangeSpy'))",
            "line": 3,
        })
        self.assertIsNone(cand)

    def test_ui_clear_focus_chain_in_hook_is_not_rq1_eligible(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "custom_command_call",
            "source_kind": "beforeEach",
            "name": "cy.get('#time [contenteditable]').clear.focus",
            "raw_code": "cy.get('#time [contenteditable]').should('be.visible').first().clear().focus()",
            "line": 3,
        })
        self.assertIsNone(cand)

    def test_ast_callee_chain_ui_clear_focus_is_not_rq1_eligible(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "custom_command_call",
            "source_kind": "beforeEach",
            "name": "opaque",
            "raw_code": "opaque()",
            "callee_chain_json": '["cy", "get", "clear", "focus"]',
            "line": 3,
        })
        self.assertIsNone(cand)

    def test_backend_api_delete_maps_to_backend_data_intent(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "custom_command_call",
            "source_kind": "before",
            "name": "cy.apiDeleteChannel",
            "raw_code": "cy.apiDeleteChannel(channel.id)",
            "cypress_command_role_ast": "test_data_setup",
            "cypress_command_role_basis_ast": "ast_cypress_data_call",
            "line": 3,
        })
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["scope"], "suite_or_fixture")
        self.assertEqual(rows[0]["primary_intent"], "test_data_or_backend_state")

    def test_api_verify_user_hook_command_is_backend_data_setup(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "custom_command_call",
            "source_kind": "before",
            "name": "cy.apiVerifyUserEmailById",
            "raw_code": "cy.apiVerifyUserEmailById(user.id)",
            "cypress_command_role_ast": "test_data_setup",
            "cypress_command_role_basis_ast": "ast_cypress_data_call",
            "line": 3,
        })
        self.assertIsNotNone(cand)
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["scope"], "suite_or_fixture")
        self.assertEqual(rows[0]["primary_intent"], "test_data_or_backend_state")

    def test_test_body_helper_child_navigation_does_not_rescue_opaque_auth_name(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Playwright",
            "feature_type": "helper_call",
            "source_kind": "test_body",
            "name": "apiSignin",
            "raw_code": "apiSignin({ page, redirectPath: '/documents' })",
            "line": 3,
            "child_setup_unit_count": 2,
            "dominant_child_intent": "navigation_bootstrap",
            "child_intent_counts_json": '{"navigation_bootstrap": 2}',
        })
        self.assertIsNone(cand)

    def test_cleanup_in_before_hook_is_setup_phase_browser_context_intent(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "browser_context_control",
            "source_kind": "beforeEach",
            "name": "cy.clearCookies",
            "raw_code": "cy.clearCookies()",
            "line": 3,
            "framework_api_category": "cleanup",
            "statement_phase_hint_ast": "teardown",
        })
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["phase"], "setup")
        self.assertEqual(rows[0]["primary_intent"], "browser_context_or_client_state")

    def test_read_only_cookie_getter_is_not_rq1_eligible(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "setup",
            "source_kind": "beforeEach",
            "name": "opaque",
            "raw_code": "opaque()",
            "callee_chain_json": '["cy", "getCookie"]',
            "literal_args_json": '["MMCSRF"]',
            "line": 3,
        })
        self.assertIsNone(cand)

    def test_cleanup_in_after_hook_is_teardown_phase_browser_context_intent(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "browser_context_control",
            "source_kind": "afterEach",
            "name": "cy.clearCookies",
            "raw_code": "cy.clearCookies()",
            "line": 3,
            "framework_api_category": "cleanup",
            "statement_phase_hint_ast": "teardown",
        })
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["phase"], "teardown")
        self.assertEqual(rows[0]["primary_intent"], "browser_context_or_client_state")

    def test_auth_cookie_cleanup_uses_browser_context_target_domain(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Playwright",
            "feature_type": "browser_context_control",
            "source_kind": "afterEach",
            "name": "context.clearCookies",
            "raw_code": "await context.clearCookies({ name: 'auth_token' })",
            "callee_chain_json": '["context", "clearCookies"]',
            "literal_args_json": '["auth_token"]',
            "framework_api_category": "cleanup",
            "framework_api_category_basis_ast": "ast_known_framework_api",
            "statement_phase_hint_ast": "teardown",
            "line": 3,
        })
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["phase"], "teardown")
        self.assertEqual(rows[0]["primary_intent"], "browser_context_or_client_state")
        self.assertEqual(rows[0]["primary_intent_evidence_basis"], "ast_callee_name_heuristic")
        self.assertEqual(rows[0]["operation_kind"], "cleanup_restore")
        self.assertEqual(rows[0]["operation_kind_evidence_basis"], "ast_framework_api_category")

    def test_structured_api_delete_cleanup_targets_backend_data_domain(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Playwright",
            "feature_type": "setup",
            "source_kind": "afterEach",
            "name": "request.delete",
            "raw_code": "await request.delete('/api/projects/123')",
            "callee_chain_json": '["request", "delete"]',
            "literal_args_json": '["/api/projects/123"]',
            "framework_api_category": "test_data_api",
            "framework_api_category_basis_ast": "ast_known_framework_api",
            "statement_phase_hint_ast": "teardown",
            "line": 3,
        })
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["phase"], "teardown")
        self.assertEqual(rows[0]["primary_intent"], "test_data_or_backend_state")
        self.assertEqual(rows[0]["primary_intent_evidence_basis"], "ast_framework_api_category")
        self.assertEqual(rows[0]["operation_kind"], "cleanup_restore")
        self.assertEqual(rows[0]["operation_kind_evidence_basis"], "ast_callee_name_heuristic")

    def test_cypress_delete_request_targets_backend_data_domain(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "setup",
            "source_kind": "afterEach",
            "name": "cy.request",
            "raw_code": "cy.request({ url: '/api/v4/channels/' + channelId, method: 'DELETE' })",
            "callee_chain_json": '["cy", "request"]',
            "framework_api_category": "test_data_api",
            "framework_api_category_basis_ast": "ast_known_framework_api",
            "statement_phase_hint_ast": "teardown",
            "line": 3,
        })
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["primary_intent"], "test_data_or_backend_state")
        self.assertEqual(rows[0]["operation_kind"], "cleanup_restore")

    def test_structured_request_ast_fields_route_by_target_domain(self):
        cases = [
            (
                {
                    "name": "cy.request",
                    "raw_code": "cy.request({ url: '/api/v4/channels/' + channelId, method: 'DELETE' })",
                    "callee_chain_json": '["cy", "request"]',
                    "request_method_ast": "delete",
                    "request_target_domain_ast": "backend_data",
                    "request_has_body_ast": False,
                    "request_evidence_basis_ast": "ast_object_argument",
                },
                "test_data_or_backend_state",
                "ast_request_target_domain",
            ),
            (
                {
                    "name": "cy.request",
                    "raw_code": "cy.request({ url: '/api/v4/config', method: 'PUT', body: config })",
                    "callee_chain_json": '["cy", "request"]',
                    "request_method_ast": "put",
                    "request_target_domain_ast": "config",
                    "request_has_body_ast": True,
                    "request_evidence_basis_ast": "ast_object_argument",
                },
                "test_data_or_backend_state",
                "ast_request_target_domain",
            ),
            (
                {
                    "name": "request.post",
                    "raw_code": "await request.post('/api/v4/users/login', { data: credentials })",
                    "callee_chain_json": '["request", "post"]',
                    "request_method_ast": "post",
                    "request_target_domain_ast": "auth",
                    "request_has_body_ast": True,
                    "request_evidence_basis_ast": "ast_positional_arguments",
                },
                "test_data_or_backend_state",
                "ast_request_target_domain",
            ),
        ]
        for request_fields, expected_intent, expected_basis in cases:
            with self.subTest(raw=request_fields["raw_code"]):
                cand = build_intent_candidate({
                    "repo": "r",
                    "test_id": "t",
                    "framework": "Cypress",
                    "feature_type": "setup",
                    "source_kind": "beforeEach",
                    "framework_api_category": "test_data_api",
                    "framework_api_category_basis_ast": "ast_known_framework_api",
                    "line": 3,
                    **request_fields,
                })
                rows, _ = resolve_test_intent_units([cand])
                self.assertEqual(rows[0]["primary_intent"], expected_intent)
                self.assertEqual(rows[0]["primary_intent_evidence_basis"], expected_basis)

    def test_nested_fetch_delete_targets_backend_data_domain(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Playwright",
            "feature_type": "setup",
            "source_kind": "afterEach",
            "name": "cleanupPage.evaluate",
            "raw_code": (
                "cleanupPage.evaluate(async ({ orgId, pipelineId }) => { "
                "await fetch(`/api/${orgId}/pipelines/${pipelineId}`, { method: 'DELETE' }); "
                "}, { orgId, pipelineId: testPipelineId }).catch(() => {})"
            ),
            "callee_chain_json": '["cleanupPage", "evaluate"]',
            "statement_phase_hint_ast": "teardown",
            "line": 3,
        })
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["primary_intent"], "test_data_or_backend_state")
        self.assertEqual(rows[0]["operation_kind"], "cleanup_restore")

    def test_request_with_csrf_cookie_header_targets_backend_mutation(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "setup",
            "source_kind": "beforeEach",
            "name": "cy.getCookie('MMCSRF').then",
            "raw_code": (
                "cy.getCookie('MMCSRF').then((csrfCookie) => { "
                "const headers = {'X-CSRF-Token': csrfCookie.value}; "
                "return cy.request({ url: '/api/v4/config', method: 'PUT', body: config, headers }); "
                "})"
            ),
            "callee_chain_json": '["cy", "getCookie", "then"]',
            "statement_phase_hint_ast": "setup",
            "line": 3,
        })
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["primary_intent"], "test_data_or_backend_state")

    def test_auth_cookie_and_storage_cleanup_targets_browser_context_domain(self):
        cases = [
            ("cy.clearCookie", 'cy.clearCookie("SESSION")', '["cy", "clearCookie"]'),
            ("cy.clearCookie", "cy.clearCookie('accessTokenPayload')", '["cy", "clearCookie"]'),
            ("cy.clearLocalStorage", "cy.clearLocalStorage('token')", '["cy", "clearLocalStorage"]'),
            (
                "page.context().clearCookies",
                "page.context().clearCookies({ name: 'jwt_access_token' })",
                '["page", "context", "clearCookies"]',
            ),
        ]
        for name, raw, chain in cases:
            with self.subTest(raw=raw):
                cand = build_intent_candidate({
                    "repo": "r",
                    "test_id": "t",
                    "framework": "Cypress",
                    "feature_type": "browser_context_control",
                    "source_kind": "afterEach",
                    "name": name,
                    "raw_code": raw,
                    "callee_chain_json": chain,
                    "framework_api_category": "cleanup",
                    "framework_api_category_basis_ast": "ast_known_framework_api",
                    "statement_phase_hint_ast": "teardown",
                    "line": 3,
                })
                rows, _ = resolve_test_intent_units([cand])
                self.assertEqual(rows[0]["primary_intent"], "browser_context_or_client_state")
                self.assertEqual(rows[0]["operation_kind"], "cleanup_restore")

    def test_generic_cookie_and_storage_cleanup_targets_browser_context_domain(self):
        cases = [
            ("cy.clearCookies", "cy.clearCookies()", '["cy", "clearCookies"]'),
            ("cy.clearLocalStorage", "cy.clearLocalStorage()", '["cy", "clearLocalStorage"]'),
        ]
        for name, raw, chain in cases:
            with self.subTest(raw=raw):
                cand = build_intent_candidate({
                    "repo": "r",
                    "test_id": "t",
                    "framework": "Cypress",
                    "feature_type": "browser_context_control",
                    "source_kind": "afterEach",
                    "name": name,
                    "raw_code": raw,
                    "callee_chain_json": chain,
                    "framework_api_category": "cleanup",
                    "framework_api_category_basis_ast": "ast_known_framework_api",
                    "statement_phase_hint_ast": "teardown",
                    "line": 3,
                })
                rows, _ = resolve_test_intent_units([cand])
                self.assertEqual(rows[0]["primary_intent"], "browser_context_or_client_state")
                self.assertEqual(rows[0]["operation_kind"], "cleanup_restore")

    def test_mutating_login_request_targets_backend_data_not_auth_context(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "setup",
            "source_kind": "beforeEach",
            "name": "cy.request",
            "raw_code": (
                "cy.request({ url: '/api/v4/users/login', method: 'POST', "
                "body: { login_id: user.username, password: user.password, token } })"
            ),
            "callee_chain_json": '["cy", "request"]',
            "statement_phase_hint_ast": "setup",
            "line": 3,
        })
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["primary_intent"], "test_data_or_backend_state")

    def test_tokenized_navigation_remains_navigation_bootstrap(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Playwright",
            "feature_type": "ui_action",
            "source_kind": "test_body",
            "name": "page.goto",
            "raw_code": "page.goto(`/sign/${token}`)",
            "callee_chain_json": '["page", "goto"]',
            "framework_api_category": "navigation",
            "framework_api_category_basis_ast": "ast_known_framework_api",
            "navigation_bootstrap_candidate_ast": True,
            "line": 3,
        })
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["primary_intent"], "navigation_bootstrap")

    def test_route_fulfill_wrapper_remains_network_mock_not_backend_data(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Playwright",
            "feature_type": "setup",
            "source_kind": "beforeEach",
            "name": "page.route",
            "raw_code": (
                "page.route('**/api/status', async (route) => { "
                "const response = await route.fetch(); "
                "const json = await response.json(); "
                "delete json.updateInfo; "
                "await route.fulfill({ json }); "
                "})"
            ),
            "callee_chain_json": '["page", "route"]',
            "framework_api_category": "network_mock",
            "framework_api_category_basis_ast": "ast_known_framework_api",
            "statement_phase_hint_ast": "setup",
            "line": 3,
        })
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["primary_intent"], "network_mock_or_spy")

    def test_clock_wrapper_prefers_direct_time_operation_over_nested_polling_mock(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "cypress_test_utility",
            "source_kind": "test_body",
            "name": "cy.clock(Date.now()).then",
            "raw_code": (
                "cy.clock(Date.now()).then((clock) => { "
                "mockGetEventsPolling(mockEvents, mockNowTimestamp).as('getEventsPoll'); "
                "clock.tick(2000); "
                "})"
            ),
            "callee_chain_json": '["cy", "clock", "then"]',
            "framework_api_category": "time_device_emulation",
            "framework_api_category_basis_ast": "ast_nested_framework_api",
            "statement_phase_hint_ast": "setup",
            "line": 3,
        })
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["primary_intent"], "time_device_permission_emulation")

    def test_signup_wrapper_with_nested_clock_remains_auth_flow(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "cypress_test_utility",
            "source_kind": "test_body",
            "name": "cy.signup({ user }).then",
            "raw_code": (
                "cy.signup({ user: userParams, redirect: routeBase }).then(() => { "
                "cy.clock(Date.parse('2042/05/03')); "
                "cy.get('[data-cy=details]').should('be.visible'); "
                "})"
            ),
            "callee_chain_json": '["cy", "signup", "then"]',
            "framework_api_category": "time_device_emulation",
            "framework_api_category_basis_ast": "ast_nested_framework_api",
            "statement_phase_hint_ast": "setup",
            "line": 3,
        })
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["primary_intent"], "auth_session_state")

    def test_create_issue_wrapper_with_viewport_reads_remains_backend_data(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "cypress_test_utility",
            "source_kind": "test_body",
            "name": "cy.createIssueFromControlButton(createIssueRectangle).then",
            "raw_code": (
                "cy.createIssueFromControlButton(createIssueRectangle).then(() => { "
                "const viewportHeight = Cypress.config('viewportHeight'); "
                "const viewportWidth = Cypress.config('viewportWidth'); "
                "waitForResize(); "
                "})"
            ),
            "callee_chain_json": '["cy", "createIssueFromControlButton", "then"]',
            "framework_api_category": "time_device_emulation",
            "framework_api_category_basis_ast": "ast_nested_framework_api",
            "statement_phase_hint_ast": "setup",
            "line": 3,
        })
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["primary_intent"], "test_data_or_backend_state")

    def test_intercept_delete_route_is_not_cleanup_operation(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "network_mock",
            "source_kind": "beforeEach",
            "name": "cy.intercept",
            "raw_code": "cy.intercept('DELETE', '/api/projects/*')",
            "callee_chain_json": '["cy", "intercept"]',
            "literal_args_json": '["DELETE", "/api/projects/*"]',
            "framework_api_category": "network_mock",
            "framework_api_category_basis_ast": "ast_known_framework_api",
            "statement_phase_hint_ast": "setup",
            "line": 3,
        })
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["primary_intent"], "network_mock_or_spy")
        self.assertEqual(rows[0]["operation_kind"], "other_setup_teardown")
        self.assertEqual(rows[0]["operation_kind_evidence_basis"], "not_cleanup_restore")

    def test_network_mock_reset_api_is_cleanup_operation(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Playwright",
            "feature_type": "network_mock",
            "source_kind": "afterEach",
            "name": "server.resetHandlers",
            "raw_code": "server.resetHandlers()",
            "callee_chain_json": '["server", "resetHandlers"]',
            "framework_api_category": "network_mock",
            "framework_api_category_basis_ast": "ast_known_framework_api",
            "statement_phase_hint_ast": "teardown",
            "line": 3,
        })
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["primary_intent"], "network_mock_or_spy")
        self.assertEqual(rows[0]["operation_kind"], "cleanup_restore")
        self.assertEqual(rows[0]["operation_kind_evidence_basis"], "ast_callee_name_heuristic")

    def test_opaque_cleanup_helper_remains_residual_cleanup(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Playwright",
            "feature_type": "setup",
            "source_kind": "afterEach",
            "name": "cleanupEverything",
            "raw_code": "cleanupEverything()",
            "callee_chain_json": '["cleanupEverything"]',
            "framework_api_category": "cleanup",
            "framework_api_category_basis_ast": "ast_known_framework_api",
            "statement_phase_hint_ast": "teardown",
            "line": 3,
        })
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["phase"], "teardown")
        self.assertEqual(rows[0]["primary_intent"], "cleanup_restore_state")
        self.assertEqual(rows[0]["operation_kind"], "cleanup_restore")

    def test_create_page_name_does_not_imply_setup_eligibility(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Playwright",
            "feature_type": "setup",
            "source_kind": "beforeEach",
            "name": "createPage",
            "raw_code": "await createPage()",
            "line": 3,
        })
        self.assertIsNone(cand)

    def test_bare_seed_helper_names_without_direct_api_evidence_are_not_rq1(self):
        for ft, name, raw in (
            ("helper_call", "seedUsers", "seedUsers()"),
            ("helper_call", "createUser", "createUser()"),
        ):
            with self.subTest(name=name):
                cand = build_intent_candidate({
                    "repo": "r",
                    "test_id": "t",
                    "framework": "Cypress",
                    "feature_type": ft,
                    "source_kind": "beforeEach",
                    "name": name,
                    "raw_code": raw,
                    "line": 3,
                })
                self.assertIsNone(cand)

        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "custom_command_call",
            "source_kind": "beforeEach",
            "name": "cy.seedUsers",
            "raw_code": "cy.seedUsers()",
            "line": 3,
        })
        self.assertIsNone(cand)

    def test_direct_api_seed_command_in_test_body_is_not_setup_by_name_only(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "custom_command_call",
            "source_kind": "test_body",
            "name": "cy.apiCreateUser",
            "raw_code": "cy.apiCreateUser({ email })",
            "line": 3,
        })
        self.assertIsNone(cand)

    def test_structured_framework_api_category_is_not_rq1_fallback(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "network_mock",
            "source_kind": "beforeEach",
            "name": "cy.intercept",
            "raw_code": "cy.intercept('/api')",
            "line": 3,
            "framework_api_category": "network_mock",
            "framework_api_category_basis_ast": "ast_known_framework_api",
        })
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["primary_intent"], "network_mock_or_spy")
        self.assertEqual(rows[0]["primary_intent_evidence_basis"], "ast_framework_api_category")
        self.assertEqual(rows[0]["fallback_used"], 0)
        self.assertEqual(rows[0]["needs_review"], 0)

    def test_framework_api_category_name_heuristic_is_not_rq1_eligible(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Playwright",
            "feature_type": "helper_call",
            "source_kind": "beforeEach",
            "name": "cleanupData",
            "raw_code": "cleanupData()",
            "line": 3,
            "framework_api_category": "cleanup",
            "framework_api_category_basis_ast": "callee_name_heuristic",
        })
        self.assertIsNone(cand)

    def test_framework_api_category_call_text_is_not_rq1_eligible(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "setup",
            "source_kind": "beforeEach",
            "name": "helper",
            "raw_code": "helper(() => cy.intercept('/api'))",
            "line": 3,
            "framework_api_category": "network_mock",
            "framework_api_category_basis_ast": "call_text_framework_api",
        })
        self.assertIsNone(cand)

    def test_nested_framework_api_category_is_structured(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "setup",
            "source_kind": "beforeEach",
            "name": "helper",
            "raw_code": "helper(() => cy.intercept('/api'))",
            "line": 3,
            "framework_api_category": "network_mock",
            "framework_api_category_basis_ast": "ast_nested_framework_api",
        })
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["primary_intent"], "network_mock_or_spy")
        self.assertEqual(rows[0]["primary_intent_evidence_basis"], "ast_framework_api_category")
        self.assertEqual(rows[0]["fallback_used"], 0)
        self.assertEqual(rows[0]["structured_evidence_available"], 1)
        self.assertEqual(rows[0]["needs_review"], 0)

    def test_database_page_name_does_not_imply_setup_eligibility(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Playwright",
            "feature_type": "setup",
            "source_kind": "beforeEach",
            "name": "createDatabasePage",
            "raw_code": "await createDatabasePage()",
            "line": 3,
        })
        self.assertIsNone(cand)


class TestDedupe(unittest.TestCase):
    def test_dedupe_same_line_intercept(self):
        mock = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "network_mock",
            "source_kind": "beforeEach",
            "name": "cy.intercept",
            "raw_code": "cy.intercept('GET', '/api')",
            "line": 5,
            "file_path": "cypress/e2e/x.cy.ts",
            "source_start_offset": 100,
            "source_end_offset": 140,
        })
        utility = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "cypress_test_utility",
            "source_kind": "beforeEach",
            "name": "cy.intercept",
            "raw_code": "cy.intercept('GET', '/api')",
            "line": 5,
            "file_path": "cypress/e2e/x.cy.ts",
            "source_start_offset": 100,
            "source_end_offset": 140,
        })
        rows, stats = resolve_test_intent_units([mock, utility])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["primary_intent"], "network_mock_or_spy")
        self.assertEqual(stats["intent_rows_deduplicated"], 1)

    def test_dedupe_preserves_distinct_same_line_calls(self):
        first = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "network_mock",
            "source_kind": "beforeEach",
            "name": "cy.intercept",
            "raw_code": "cy.intercept('GET', '/api/a')",
            "line": 5,
            "file_path": "cypress/e2e/x.cy.ts",
            "source_start_offset": 100,
            "source_end_offset": 140,
        })
        second = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "network_mock",
            "source_kind": "beforeEach",
            "name": "cy.intercept",
            "raw_code": "cy.intercept('GET', '/api/b')",
            "line": 5,
            "file_path": "cypress/e2e/x.cy.ts",
            "source_start_offset": 150,
            "source_end_offset": 190,
        })
        rows, stats = resolve_test_intent_units([first, second])
        self.assertEqual(len(rows), 2)
        self.assertEqual(stats["intent_rows_deduplicated"], 0)

    def test_dedupe_helper_prefers_non_unclear(self):
        rows_in = [
            {
                "repo": "r",
                "test_id": "t",
                "line": 7,
                "name": "cy.intercept",
                "primary_intent": "unclear",
                "confidence": "low",
            },
            {
                "repo": "r",
                "test_id": "t",
                "line": 7,
                "name": "cy.intercept",
                "primary_intent": "network_mock_or_spy",
                "confidence": "high",
            },
        ]
        out, dropped = dedupe_intent_rows(rows_in)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["primary_intent"], "network_mock_or_spy")
        self.assertEqual(dropped, 1)

    def test_wrapper_only_excluded_from_paper_facing_summary(self):
        rows = [
            {"wrapper_only": 1, "phase": "setup_and_teardown", "primary_intent": "generic_setup_teardown_utility", "operation_kind": "cleanup_restore", "scope": "inline_test_body", "confidence": "low", "needs_review": 1},
            {"wrapper_only": 0, "phase": "setup", "primary_intent": "network_mock_or_spy", "operation_kind": "cleanup_restore", "scope": "helper_or_framework_extension", "confidence": "high", "needs_review": 0},
        ]
        summary = summarize_rq1_intent_by_test(rows)
        self.assertEqual(summary["wrapper_call_count"], 1)
        self.assertEqual(summary["setup_teardown_intent_unit_count"], 1)
        self.assertEqual(summary["paper_facing_unit_count"], 1)
        self.assertEqual(json.loads(summary["operation_kind_counts_json"]), {"cleanup_restore": 1})
        self.assertEqual(summary["cleanup_restore_operation_count"], 1)
        self.assertEqual(len(paper_facing_intent_rows(rows)), 1)


class TestScope(unittest.TestCase):
    def test_before_is_suite_or_fixture(self):
        feature = {"source_kind": "before", "framework": "Cypress", "feature_type": "setup", "helper_depth": 0}
        self.assertEqual(classify_scope(feature, map_provenance_hints(feature)), "suite_or_fixture")

    def test_before_each_is_per_test_hook(self):
        feature = {"source_kind": "beforeEach", "framework": "Cypress", "feature_type": "setup", "helper_depth": 0}
        self.assertEqual(classify_scope(feature, map_provenance_hints(feature)), "per_test_hook")

    def test_testcafe_test_before_is_per_test_hook(self):
        feature = {
            "source_kind": "before",
            "framework": "TestCafe",
            "feature_type": "setup",
            "helper_depth": 0,
            "hook_owner_kind": "test",
        }
        self.assertEqual(classify_scope(feature, map_provenance_hints(feature)), "per_test_hook")

    def test_testcafe_fixture_before_is_suite_or_fixture(self):
        feature = {
            "source_kind": "before",
            "framework": "TestCafe",
            "feature_type": "setup",
            "helper_depth": 0,
            "hook_owner_kind": "fixture",
        }
        self.assertEqual(classify_scope(feature, map_provenance_hints(feature)), "suite_or_fixture")

    def test_helper_and_framework_extension_scopes(self):
        cases = [
            ({"source_kind": "cypress_command", "feature_type": "cypress_command"}, "helper_or_framework_extension"),
            ({"source_kind": "imported_helper", "feature_type": "helper_call"}, "helper_or_framework_extension"),
            ({"source_kind": "helper_function", "feature_type": "helper_call"}, "helper_or_framework_extension"),
            ({"source_kind": "test_body", "feature_type": "helper_call"}, "inline_test_body"),
            ({"source_kind": "test_body", "feature_type": "custom_command_call"}, "inline_test_body"),
        ]
        for feature, expected in cases:
            feature = {**feature, "framework": "Cypress", "helper_depth": 0}
            with self.subTest(feature=feature):
                self.assertEqual(classify_scope(feature, map_provenance_hints(feature)), expected)

    def test_global_owner_suite_hook_scope_is_suite_or_fixture_without_support_provenance(self):
        feature = {
            "source_kind": "beforeAll",
            "framework": "Playwright",
            "feature_type": "setup",
            "helper_depth": 0,
            "hook_owner_kind": "global",
        }
        self.assertEqual(classify_scope(feature, map_provenance_hints(feature)), "suite_or_fixture")


class TestInputEligibility(unittest.TestCase):
    def test_external_file_input_class_eligible(self):
        f = {
            "feature_type": "input",
            "source_kind": "test_body",
            "name": "cy.readFile",
            "raw_code": "cy.readFile('data/users.json')",
            "input_source_class": "external_file_input",
            "input_channel_ast": "load_site",
        }
        ok, basis = is_eligible_setup_teardown_unit(f)
        self.assertTrue(ok)
        self.assertEqual(basis, "input_source_class:external_file_input")

    def test_fixture_only_load_is_not_rq1_setup(self):
        cases = [
            {
                "feature_type": "input",
                "source_kind": "beforeEach",
                "name": "cy.fixture",
                "raw_code": "cy.fixture('users.json')",
                "callee_chain_json": '["cy", "fixture"]',
                "input_source_class": "fixture_file_input",
                "input_channel_ast": "load_site",
                "is_load_site": 1,
            },
            {
                "feature_type": "setup",
                "source_kind": "beforeEach",
                "name": "cy.fixture",
                "raw_code": "cy.fixture('users.json')",
                "callee_chain_json": '["cy", "fixture"]',
                "framework_api_category": "test_data_fixture",
                "framework_api_category_basis_ast": "ast_known_framework_api",
            },
        ]
        for feature in cases:
            with self.subTest(feature_type=feature["feature_type"]):
                ok, basis = is_eligible_setup_teardown_unit(feature)
                self.assertFalse(ok)
                self.assertEqual(basis, "excluded_fixture_only_load")

    def test_raw_file_load_call_without_rq2_load_site_metadata_is_not_eligible(self):
        f = {
            "feature_type": "input",
            "source_kind": "test_body",
            "name": "cy.readFile",
            "raw_code": "cy.readFile('data/users.json')",
            "input_source_class": "external_file_input",
        }
        ok, basis = is_eligible_setup_teardown_unit(f)
        self.assertFalse(ok)
        self.assertEqual(basis, "excluded_input_consumer")

    def test_input_consumer_from_fixture_not_eligible(self):
        cases = (
            {
                "feature_type": "input",
                "source_kind": "test_body",
                "name": "page.fill",
                "raw_code": 'await page.fill("#email", data.email)',
                "input_source_class": "variable_from_external_file",
                "input_channel_ast": "dom_text_entry",
            },
            {
                "feature_type": "input",
                "source_kind": "test_body",
                "name": "cy.get(...).type",
                "raw_code": 'cy.get("#email").type(data.email)',
                "input_source_class": "variable_from_external_file",
            },
            {
                "feature_type": "input",
                "source_kind": "test_body",
                "name": "selectOption",
                "raw_code": "selectOption(data.role)",
                "input_source_class": "variable_from_external_file",
            },
        )
        for f in cases:
            with self.subTest(raw=f["raw_code"]):
                ok, basis = is_eligible_setup_teardown_unit(f)
                self.assertFalse(ok)
                self.assertEqual(basis, "excluded_input_consumer")

    def test_resolves_test_data_intent_and_setup_phase(self):
        cand = build_intent_candidate({
            "repo": "r",
            "test_id": "t",
            "framework": "Cypress",
            "feature_type": "input",
            "source_kind": "test_body",
            "name": "cy.readFile",
            "raw_code": "cy.readFile('data/users.json')",
            "input_source_class": "external_file_input",
            "input_channel_ast": "load_site",
            "line": 4,
        })
        rows, _ = resolve_test_intent_units([cand])
        self.assertEqual(rows[0]["primary_intent"], "test_data_or_backend_state")
        self.assertEqual(rows[0]["phase"], "setup")
        self.assertEqual(rows[0]["needs_review"], 0)


class TestHelperWrapperMatch(unittest.TestCase):
    def test_offset_match_required_for_same_line_repeated_calls(self):
        seeds = {
            (10, "setupUser", 100, 120),
            (10, "setupUser", 200, 220),
        }
        self.assertIsNotNone(
            match_resolved_helper_wrapper(seeds, 10, "setupUser", start=100, end=120)
        )
        self.assertIsNone(
            match_resolved_helper_wrapper(seeds, 10, "setupUser", start=150, end=170)
        )
        self.assertIsNone(match_resolved_helper_wrapper(seeds, 10, "setupUser"))


if __name__ == "__main__":
    unittest.main()
