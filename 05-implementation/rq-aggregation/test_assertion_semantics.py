#!/usr/bin/env python3
"""Unit tests for RQ5-C verification_intent mapping (Milestone 1)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from classify import ALL_ASSERTION_ORACLE_CATEGORIES
from assertion_semantics import (
    classify_verification_intent,
    classify_verification_intent_detail,
    ORACLE_TO_VERIFICATION_INTENT,
    VERIFICATION_INTENT_LABELS,
    map_verification_intent,
)


class TestVerificationIntent(unittest.TestCase):
    def test_known_oracles(self):
        self.assertEqual(map_verification_intent("visibility_oracle"), "element_presence")
        self.assertEqual(map_verification_intent("api_state_oracle"), "api_or_data_contract")

    def test_specific_generic_patterns_map_to_coarse_intents(self):
        cases = [
            ("generic_assertion", "toHaveValue", "await expect(input).toHaveValue('x')", "value_or_attribute_correctness"),
            ("generic_assertion", "toHaveAttribute", "await expect(input).toHaveAttribute('aria-label', 'Search')", "accessibility_compliance"),
            ("generic_assertion", "toHaveCSS", "await expect(button).toHaveCSS('color', 'red')", "style_or_visual_state"),
            ("generic_assertion", "toHaveClass", "await expect(button).toHaveClass('active')", "style_or_visual_state"),
            ("generic_assertion", "should", 'cy.get("button").should("have.class", "active")', "style_or_visual_state"),
            ("generic_assertion", "should", 'cy.get("button").should("be.visible")', "element_presence"),
            ("generic_assertion", "should", 'cy.get(".toast").should("not.exist")', "element_presence"),
            ("generic_assertion", "toBeEnabled", "await expect(button).toBeEnabled()", "interactive_state"),
            ("generic_assertion", "toBeFocused", "await expect(input).toBeFocused()", "interactive_state"),
            ("generic_assertion", "toHaveURL", "await expect(page).toHaveURL('/home')", "navigation_outcome"),
            ("generic_assertion", "toHaveText", "await expect(page.locator('h1')).toHaveText('Home')", "content_correctness"),
            ("generic_assertion", "status", "expect(response.status).toBe(200)", "network_contract"),
            ("generic_assertion", "should", "expect(spy).not.toHaveBeenCalled()", "api_or_data_contract"),
            ("generic_assertion", "should", "expect(requestSpy).not.toHaveBeenCalled()", "network_contract"),
            ("generic_assertion", "toHaveBeenCalledTimes", "expect(spy).toHaveBeenCalledTimes(2)", "interactive_state"),
            ("generic_assertion", "body", "expect(result.body).toEqual({ ok: true })", "api_or_data_contract"),
            ("generic_assertion", "toBeEmpty", "expect(page.locator('#field-title')).toBeEmpty()", "value_or_attribute_correctness"),
            ("generic_assertion", "toBeTruthy", "expect(csrfToken).toBeTruthy()", "value_or_attribute_correctness"),
            ("generic_assertion", "toHaveCount", "expect(page.locator('#json-setting-editor')).toHaveCount(1)", "collection_size"),
            ("generic_assertion", "toHaveAccessibleName", "expect(lastTileE2eIcon).toHaveAccessibleName('Home')", "accessibility_compliance"),
            ("generic_assertion", "toHaveAccessibleErrorMessage", "expect(input).toHaveAccessibleErrorMessage('Required')", "accessibility_compliance"),
            ("generic_assertion", "toHaveRole", "expect(button).toHaveRole('button')", "accessibility_compliance"),
            ("generic_assertion", "toHaveNoViolations", "expect(page).toHaveNoViolations()", "accessibility_compliance"),
            ("generic_assertion", "toMatchAriaSnapshot", "expect(displaySettings.expandedSection).toMatchAriaSnapshot()", "accessibility_compliance"),
            ("generic_assertion", "toMatchScreenshot", "expect(roomListHeader).toMatchScreenshot('x.png')", "visual_regression"),
            ("url_navigation_oracle", "toMatchScreenshot", 'expect(dialog.getByRole("region", { name: "Map" })).toMatchScreenshot("location-pin.png")', "visual_regression"),
            ("generic_assertion", "closeTo", "expect(image.width()).to.closeTo(480, 2)", "style_or_visual_state"),
            ("generic_assertion", "ok", "t.expect(page.cloudProviders.exists).ok()", "element_presence"),
            ("generic_assertion", "toHaveTitle", "expect(page).toHaveTitle(/CopilotKit Travel/i)", "content_correctness"),
            ("generic_assertion", "greaterThan", "expect(Number($cellData)).to.be.greaterThan(0)", "value_or_attribute_correctness"),
            ("generic_assertion", "lt", "expect(diffPercent).to.be.lt(0.02)", "value_or_attribute_correctness"),
            ("generic_assertion", "toBeAttached", "expect(page.locator('.x')).not.toBeAttached()", "element_presence"),
            ("generic_assertion", "toBeInViewport", "expect(thirdCell).not.toBeInViewport({ ratio: 1 / 100 })", "element_presence"),
            ("generic_assertion", "toHaveReceivedEventTimes", "expect(ionChangeSpy).toHaveReceivedEventTimes(1)", "interactive_state"),
            ("generic_assertion", "toHaveCustomState", "expect(element).toHaveCustomState('required')", "value_or_attribute_correctness"),
            ("generic_assertion", "should", "cy.wrap(null).should(() => { expect(value).to.be.closeTo(1, 0.1); })", "value_or_attribute_correctness"),
            ("generic_assertion", "should", "cy.get('#x').should(($el) => { expect($el[0].style.color).to.not.be.empty; })", "style_or_visual_state"),
            ("generic_assertion", "should", "cy.get('@spy').should((spy) => { expect(spy).to.have.been.calledWith('x'); })", "api_or_data_contract"),
            ("generic_assertion", "expect(mockSetFilters).toHaveBeenCalledWith", "expect(mockSetFilters).toHaveBeenCalledWith({ x: 1 })", "api_or_data_contract"),
            ("generic_assertion", "expect(rect.left).to.be.at.least", "expect(rect.left).to.be.at.least(0)", "value_or_attribute_correctness"),
            ("generic_assertion", "expect(rect.right).to.be.at.most", "expect(rect.right).to.be.at.most(100)", "value_or_attribute_correctness"),
            ("generic_assertion", "assert.isEqual", "assert.isEqual(actual, expected)", "value_or_attribute_correctness"),
            ("generic_assertion", "expect(documentTextField?.fieldMeta).toMatchObject", "expect(documentTextField?.fieldMeta).toMatchObject({ required: true })", "value_or_attribute_correctness"),
            ("generic_assertion", "expect(event).to.be.instanceOf", "expect(event).to.be.instanceOf(CustomEvent)", "value_or_attribute_correctness"),
            ("generic_assertion", "expect(parsedNumbers).to.satisfy", "expect(parsedNumbers).to.satisfy(isSorted)", "value_or_attribute_correctness"),
            ("generic_assertion", "should", "cy.get('#x').should(($el) => { const actual = $el.attr('data-x'); })", "value_or_attribute_correctness"),
            ("generic_assertion", "expect(text).to.not.have.string", "expect(text).to.not.have.string('error')", "content_correctness"),
            ("generic_assertion", "assert.isAtMost", "assert.isAtMost(actual, 10)", "value_or_attribute_correctness"),
            ("generic_assertion", "expect(firstTab).toHaveId", "expect(firstTab).toHaveId('tab-1')", "value_or_attribute_correctness"),
            ("generic_assertion", "expect(blockTextInput).toBeEditable", "expect(blockTextInput).toBeEditable()", "interactive_state"),
            ("generic_assertion", "should", "cy.get('#sidebarItem').should(beUnread)", "value_or_attribute_correctness"),
            ("generic_assertion", "expect(() => action()).to.throw", "expect(() => action()).to.throw()", "value_or_attribute_correctness"),
        ]
        for category, name, raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(classify_verification_intent(category, name, raw), expected)

    def test_extracted_matcher_surface_maps_from_ast(self):
        cases = [
            ("toBeDisplayed", "element_presence"),
            ("toBeExisting", "element_presence"),
            ("toBeClickable", "interactive_state"),
            ("toBeSelected", "interactive_state"),
            ("toHaveAttr", "value_or_attribute_correctness"),
            ("toHaveElementClass", "style_or_visual_state"),
            ("toMatchObject", "value_or_attribute_correctness"),
            ("toMatchScreenshot", "visual_regression"),
            ("toThrow", "value_or_attribute_correctness"),
            ("toHaveAccessibleDescription", "accessibility_compliance"),
            ("toHaveAccessibleErrorMessage", "accessibility_compliance"),
            ("toHaveRole", "accessibility_compliance"),
            ("toMatchAriaSnapshot", "accessibility_compliance"),
            ("lengthOf", "collection_size"),
            ("property", "value_or_attribute_correctness"),
            ("below", "value_or_attribute_correctness"),
            ("be.gt", "value_or_attribute_correctness"),
            ("be.closeTo", "value_or_attribute_correctness"),
            ("be.oneOf", "value_or_attribute_correctness"),
            ("approximately", "value_or_attribute_correctness"),
            ("have.data", "value_or_attribute_correctness"),
            ("have.html", "content_correctness"),
            ("have.been.calledOnceWith", "api_or_data_contract"),
            ("have.been.calledBefore", "api_or_data_contract"),
            ("have.been.not.called", "api_or_data_contract"),
            ("not.been.called", "api_or_data_contract"),
            ("toHaveNoViolations", "accessibility_compliance"),
            ("deep.include", "value_or_attribute_correctness"),
            ("be.greaterThan", "value_or_attribute_correctness"),
            ("be.at.least", "value_or_attribute_correctness"),
            ("be.at.most", "value_or_attribute_correctness"),
            ("be.a", "value_or_attribute_correctness"),
            ("be.an", "value_or_attribute_correctness"),
            ("be.instanceOf", "value_or_attribute_correctness"),
            ("satisfy", "value_or_attribute_correctness"),
            ("have.focused", "interactive_state"),
            ("toHaveReceivedEventTimes", "interactive_state"),
            ("empty", "value_or_attribute_correctness"),
            ("true", "value_or_attribute_correctness"),
            ("false", "value_or_attribute_correctness"),
            ("null", "value_or_attribute_correctness"),
            ("undefined", "value_or_attribute_correctness"),
        ]
        for matcher, expected in cases:
            with self.subTest(matcher=matcher):
                detail = classify_verification_intent_detail(
                    "generic_assertion",
                    matcher,
                    f"expect(subject).{matcher}()",
                    {
                        "assertion_matcher": matcher,
                        "assertion_subject_kind": "unknown",
                    },
                )
                self.assertEqual(detail["verification_intent"], expected)
                self.assertNotEqual(detail["verification_intent"], "unspecified")

    def test_ast_matcher_preferred_over_lexical_raw_text(self):
        detail = classify_verification_intent_detail(
            "generic_assertion",
            "expect",
            "await expect(input).toHaveValue('x')",
            {"assertion_matcher": "toHaveValue", "assertion_subject_kind": "locator"},
        )
        self.assertEqual(detail["verification_intent"], "value_or_attribute_correctness")
        self.assertEqual(detail["verification_intent_evidence_basis"], "ast_assertion_matcher")
        self.assertEqual(detail["verification_intent_confidence"], "high")

    def test_accessibility_matcher_uses_matcher_evidence_before_lexical_context(self):
        detail = classify_verification_intent_detail(
            "generic_assertion",
            "expect",
            "await expect(button).toHaveAccessibleName('Save')",
            {"assertion_matcher": "toHaveAccessibleName", "assertion_subject_kind": "locator"},
        )
        self.assertEqual(detail["verification_intent"], "accessibility_compliance")
        self.assertEqual(detail["verification_intent_evidence_basis"], "ast_assertion_matcher")

    def test_locator_identifier_name_heuristic_is_not_reported_as_strong_ast_subject(self):
        detail = classify_verification_intent_detail(
            "generic_assertion",
            "expect",
            "await expect(locator).toBeVisible()",
            {
                "assertion_matcher": "toBeVisible",
                "assertion_subject_kind": "locator",
                "assertion_subject_basis_ast": "ast_subject_identifier_name_heuristic",
            },
        )
        self.assertEqual(detail["verification_intent"], "element_presence")
        self.assertNotEqual(
            detail["verification_intent_evidence_basis"],
            "ast_assertion_subject_and_matcher",
        )

    def test_ast_subject_identifies_network_contract(self):
        detail = classify_verification_intent_detail(
            "generic_assertion",
            "expect",
            "expect(response.status()).toBe(200)",
            {
                "assertion_matcher": "toBe",
                "assertion_subject_kind": "response",
                "assertion_subject_basis_ast": "ast_response_wait_call",
            },
        )
        self.assertEqual(detail["verification_intent"], "network_contract")
        self.assertEqual(detail["verification_intent_evidence_basis"], "ast_assertion_subject")

    def test_api_subject_overrides_generic_equality_matcher(self):
        detail = classify_verification_intent_detail(
            "generic_assertion",
            "expect",
            "expect(api.getUser()).eq({ id: 1 })",
            {
                "assertion_matcher": "eq",
                "assertion_subject_kind": "api",
                "assertion_subject_basis_ast": "ast_api_call",
            },
        )
        self.assertEqual(detail["verification_intent"], "api_or_data_contract")
        self.assertEqual(detail["verification_intent_evidence_basis"], "ast_assertion_subject")

    def test_url_oracle_overrides_ambiguous_content_matcher(self):
        detail = classify_verification_intent_detail(
            "url_navigation_oracle",
            "expect",
            "expect(page.url()).toContain('/dashboard')",
            {
                "assertion_matcher": "toContain",
                "assertion_subject_kind": "page",
                "assertion_subject_basis_ast": "ast_page_call",
            },
        )
        self.assertEqual(detail["verification_intent"], "navigation_outcome")
        self.assertEqual(
            detail["verification_intent_evidence_basis"],
            "ast_assertion_subject",
        )

    def test_url_oracle_without_strong_subject_stays_lexical_fallback(self):
        detail = classify_verification_intent_detail(
            "url_navigation_oracle",
            "expect",
            "expect(currentUrl).toContain('/dashboard')",
            {
                "assertion_matcher": "toContain",
                "assertion_subject_kind": "unknown",
                "assertion_subject_basis_ast": "",
            },
        )
        self.assertEqual(detail["verification_intent"], "navigation_outcome")
        self.assertEqual(
            detail["verification_intent_evidence_basis"],
            "lexical_navigation_context",
        )

    def test_latest_rq5c_audited_semantic_boundary_tails(self):
        cases = [
            (
                "generic_assertion",
                "expect",
                "await expect(locator).toHaveAccessibleName('Save')",
                {
                    "assertion_matcher": "toHaveAccessibleName",
                    "assertion_subject_semantic_role_ast": "text_payload",
                },
                "accessibility_compliance",
            ),
            (
                "generic_assertion",
                "should",
                "cy.url().should('contain', '/dashboard')",
                {
                    "assertion_matcher": "contain",
                    "assertion_subject_semantic_role_ast": "api_object_contract",
                },
                "navigation_outcome",
            ),
            (
                "generic_assertion",
                "expect",
                "expect(await getCssClasses(bullet3)).toBe('bullet')",
                {
                    "assertion_matcher": "toBe",
                    "assertion_subject_semantic_role_ast": "scalar_property",
                    "assertion_subject_path_ast": "getCssClasses(bullet3)",
                },
                "style_or_visual_state",
            ),
            (
                "generic_assertion",
                "expect",
                "expect(status.componentDidLoad).toHaveBeenCalledTimes(1)",
                {
                    "assertion_matcher": "toHaveBeenCalledTimes",
                    "assertion_subject_semantic_role_ast": "network_status",
                    "assertion_subject_path_ast": "status.componentDidLoad",
                },
                "interactive_state",
            ),
            (
                "generic_assertion",
                "expect",
                "await t.expect(getNodes().count).eql(3)",
                {
                    "assertion_matcher": "eql",
                    "assertion_subject_semantic_role_ast": "element_presence",
                    "assertion_subject_path_ast": "getNodes().count",
                },
                "collection_size",
            ),
        ]
        for category, name, raw, feature, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(
                    classify_verification_intent_detail(category, name, raw, feature)["verification_intent"],
                    expected,
                )

    def test_ast_callback_hint_preferred_over_raw_text_fallback(self):
        detail = classify_verification_intent_detail(
            "generic_assertion",
            "should",
            "cy.get('li').should(($li) => { expect($li).to.have.length(2); })",
            {
                "assertion_matcher": "should",
                "assertion_subject_kind": "locator",
                "assertion_subject_basis_ast": "ast_cypress_subject_chain",
                "assertion_callback_intent_hint_ast": "collection_size",
                "assertion_callback_intent_basis_ast": "ast_callback_nested_assertion",
                "assertion_callback_nested_assertion_count": 1,
            },
        )
        self.assertEqual(detail["verification_intent"], "collection_size")
        self.assertEqual(detail["verification_intent_evidence_basis"], "ast_callback_nested_assertion")
        self.assertEqual(detail["verification_intent_confidence"], "medium")

    def test_audited_verification_intent_context_patches(self):
        cases = [
            (
                "generic_assertion",
                "expect",
                "expect(errors.filter((error) => error.message === 'File does not exist')).toEqual([])",
                {"assertion_matcher": "toEqual", "assertion_subject_kind": "unknown"},
                "collection_size",
            ),
            (
                "generic_assertion",
                "expect",
                "expect(res.status).to.equal(201)",
                {"assertion_semantic_matcher_ast": "equal", "assertion_subject_kind": "unknown"},
                "network_contract",
            ),
            (
                "generic_assertion",
                "expect",
                "expect(status).toBeGreaterThanOrEqual(200)",
                {"assertion_matcher": "toBeGreaterThanOrEqual", "assertion_subject_kind": "unknown"},
                "value_or_attribute_correctness",
            ),
            (
                "generic_assertion",
                "expect",
                "expect(iframeSrc).toMatch(app.urlPattern)",
                {"assertion_matcher": "toMatch", "assertion_subject_kind": "unknown"},
                "navigation_outcome",
            ),
            (
                "generic_assertion",
                "expect",
                'expect(dialog.getByRole("region", { name: "Map" })).toMatchScreenshot("map.png")',
                {"assertion_matcher": "toMatchScreenshot", "assertion_subject_kind": "locator"},
                "visual_regression",
            ),
            (
                "generic_assertion",
                "expect",
                "expect(displaySettings.expandedSection).toMatchAriaSnapshot()",
                {"assertion_matcher": "toMatchAriaSnapshot", "assertion_subject_kind": "locator"},
                "accessibility_compliance",
            ),
            (
                "generic_assertion",
                "should",
                "cy.get('#test').find('svg').should(($svg) => { expect($svg).to.have.length(2); expect($svg).to.not.contain('Syntax error'); })",
                {
                    "assertion_matcher": "should",
                    "assertion_subject_kind": "locator",
                    "assertion_subject_basis_ast": "ast_cypress_subject_chain",
                },
                "collection_size",
            ),
            (
                "generic_assertion",
                "and",
                "cy.findAllByTestId('postView').last().should('have.attr', 'id').and('not.include', ':')",
                {
                    "assertion_matcher": "and",
                    "assertion_semantic_matcher_ast": "not.include",
                    "assertion_subject_kind": "unknown",
                },
                "value_or_attribute_correctness",
            ),
            (
                "generic_assertion",
                "toContain",
                "expect(requestedImagePath).toContain('crest')",
                {"assertion_matcher": "toContain", "assertion_subject_kind": "unknown"},
                "network_contract",
            ),
            (
                "url_navigation_oracle",
                "should",
                "cy.url().should('endWith', `/stackscripts/${intercept.response?.body.id}`)",
                {
                    "assertion_matcher": "should",
                    "assertion_semantic_matcher_ast": "endWith",
                    "assertion_subject_kind": "page",
                    "assertion_subject_basis_ast": "ast_cypress_subject_chain",
                },
                "navigation_outcome",
            ),
            (
                "generic_assertion",
                "should",
                "cy.get('@clickStub').should((stub) => { const event = stub.firstCall.args[0]; expect(event).to.be.instanceOf(CustomEvent); expect(event.detail.tab).to.exist; })",
                {
                    "assertion_matcher": "should",
                    "assertion_subject_kind": "locator",
                    "assertion_subject_basis_ast": "ast_cypress_subject_chain",
                },
                "api_or_data_contract",
            ),
            (
                "generic_assertion",
                "toBe",
                "expect(await element.evaluate((el) => el.labels[1].textContent)).toBe('Label 2')",
                {"assertion_matcher": "toBe", "assertion_subject_kind": "unknown"},
                "content_correctness",
            ),
            (
                "generic_assertion",
                "toBeGreaterThanOrEqual",
                "expect(scrollHeight4).toBeGreaterThanOrEqual(1358)",
                {"assertion_matcher": "toBeGreaterThanOrEqual", "assertion_subject_kind": "unknown"},
                "style_or_visual_state",
            ),
            (
                "generic_assertion",
                "include",
                "expect(g).to.include(`from:'${formatDateForUrl(START_TIME)}'`)",
                {"assertion_matcher": "include", "assertion_subject_kind": "unknown"},
                "navigation_outcome",
            ),
            (
                "generic_assertion",
                "expect(violations.length).toEqual",
                "expect(violations.length).toEqual(0)",
                {
                    "assertion_matcher": "toEqual",
                    "assertion_subject_kind": "unknown",
                    "assertion_subject_path_json": '["violations", "length"]',
                },
                "collection_size",
            ),
            (
                "generic_assertion",
                "cy.get('.cvat-player-filename-wrapper').should",
                "cy.get('.cvat-player-filename-wrapper').should('contain', `${imageFileName}.png`)",
                {
                    "assertion_matcher": "should",
                    "assertion_semantic_matcher_ast": "contain",
                    "assertion_subject_kind": "locator",
                    "assertion_subject_basis_ast": "ast_cypress_subject_chain",
                },
                "content_correctness",
            ),
            (
                "generic_assertion",
                "expect(JSON.stringify(shortcut[0].args)).toBe",
                "expect(JSON.stringify(shortcut[0].args)).toBe(JSON.stringify(args))",
                {
                    "assertion_matcher": "toBe",
                    "assertion_subject_kind": "unknown",
                    "assertion_subject_path_json": '["JSON", "stringify"]',
                },
                "value_or_attribute_correctness",
            ),
            (
                "generic_assertion",
                "expect(interception.request.body.filters).to.have.length",
                "expect(interception.request.body.filters).to.have.length(5)",
                {
                    "assertion_matcher": "length",
                    "assertion_subject_kind": "network",
                    "assertion_subject_basis_ast": "ast_subject_property_path",
                    "assertion_subject_path_json": '["interception", "request", "body", "filters"]',
                },
                "network_contract",
            ),
            (
                "generic_assertion",
                "expect(el).to.have.value",
                "expect(el).to.have.value('abc')",
                {
                    "assertion_matcher": "value",
                    "assertion_subject_kind": "unknown",
                },
                "value_or_attribute_correctness",
            ),
            (
                "generic_assertion",
                "cy.wait('@postExecute').should",
                "cy.wait('@postExecute').should(({ response }) => { expect(response.body.data).to.eq('ok') })",
                {
                    "assertion_matcher": "should",
                    "assertion_subject_kind": "locator",
                    "assertion_subject_basis_ast": "ast_cypress_subject_chain",
                    "assertion_callback_intent_hint_ast": "api_or_data_contract",
                    "assertion_callback_intent_basis_ast": "ast_callback_nested_assertion",
                    "assertion_callback_nested_assertion_count": 1,
                },
                "network_contract",
            ),
            (
                "generic_assertion",
                "expect(tokenApiRequest.postDataJSON()[grant_type]).toBe",
                'expect(tokenApiRequest.postDataJSON()["grant_type"]).toBe("authorization_code")',
                {
                    "assertion_matcher": "toBe",
                    "assertion_subject_kind": "unknown",
                    "assertion_subject_path_json": '["tokenApiRequest", "postDataJSON", "grant_type"]',
                },
                "network_contract",
            ),
            (
                "generic_assertion",
                "expect(response.status).to.be.oneOf",
                "expect(response.status).to.be.oneOf([200, 201, 204])",
                {
                    "assertion_matcher": "oneOf",
                    "assertion_subject_kind": "unknown",
                    "assertion_subject_path_json": '["response", "status"]',
                },
                "network_contract",
            ),
            (
                "generic_assertion",
                "expect(idNew).to.exist",
                "expect(idNew).to.exist.and.not.to.be.equal(this.idOld)",
                {
                    "assertion_matcher": "exist",
                    "assertion_subject_kind": "unknown",
                    "assertion_subject_path_json": '["idNew"]',
                },
                "value_or_attribute_correctness",
            ),
            (
                "generic_assertion",
                "expect($title).to.have.attr",
                "expect($title).to.have.attr('font-size', '5rem')",
                {
                    "assertion_matcher": "attr",
                    "assertion_subject_kind": "element",
                    "assertion_subject_basis_ast": "ast_subject_property_path",
                    "assertion_subject_path_json": '["$title"]',
                },
                "style_or_visual_state",
            ),
            (
                "generic_assertion",
                "expect(result.path).not.toContain",
                "expect(result!.path).not.toContain('/sign/')",
                {
                    "assertion_matcher": "toContain",
                    "assertion_subject_kind": "unknown",
                    "assertion_subject_path_json": '["result", "path"]',
                },
                "navigation_outcome",
            ),
            (
                "generic_assertion",
                "expect(isUploadEnabled).to.equal",
                "expect(isUploadEnabled).to.equal(true)",
                {
                    "assertion_matcher": "equal",
                    "assertion_subject_kind": "unknown",
                    "assertion_subject_path_json": '["isUploadEnabled"]',
                },
                "api_or_data_contract",
            ),
            (
                "generic_assertion",
                "expect(result.totalFocusableElements).toBeLessThanOrEqual",
                "expect(result.totalFocusableElements).toBeLessThanOrEqual(maxFocusableElements)",
                {
                    "assertion_matcher": "toBeLessThanOrEqual",
                    "assertion_subject_kind": "unknown",
                    "assertion_subject_path_json": '["result", "totalFocusableElements"]',
                },
                "accessibility_compliance",
            ),
            (
                "element_state_oracle",
                "expect(isUploadEnabled).to.equal",
                "expect(isUploadEnabled, isUploadEnabled ? '' : 'Should have Plugin upload enabled').to.equal(true)",
                {
                    "assertion_matcher": "equal",
                    "assertion_subject_kind": "unknown",
                },
                "api_or_data_contract",
            ),
            (
                "network_response_oracle",
                "cy.wait('@updateLayout').its('response.body.responseMeta.status').should",
                'cy.wait("@updateLayout").its("response.body.responseMeta.status").should("eq", 200)',
                {
                    "assertion_matcher": "should",
                    "assertion_semantic_matcher_ast": "eq",
                    "assertion_subject_kind": "unknown",
                },
                "network_contract",
            ),
            (
                "generic_assertion",
                "expect(async () => checkFocusIndicators()).toPass",
                "expect(async () => { const result = await checkFocusIndicators(options); expect(result.totalFocusableElements).toBeGreaterThan(0); }).toPass()",
                {
                    "assertion_matcher": "toPass",
                    "assertion_subject_kind": "unknown",
                },
                "accessibility_compliance",
            ),
        ]
        for category, name, raw, feature, expected in cases:
            with self.subTest(raw=raw):
                detail = classify_verification_intent_detail(category, name, raw, feature)
                self.assertEqual(detail["verification_intent"], expected)

    def test_latest_audit_rq5c_subject_matcher_routing(self):
        cases = [
            (
                "generic_assertion",
                "expect(taskProgress).toBeVisible",
                "expect(taskProgress).toBeVisible()",
                {
                    "assertion_matcher": "toBeVisible",
                    "assertion_subject_kind": "unknown",
                    "assertion_subject_path_json": '["taskProgress"]',
                },
                "element_presence",
            ),
            (
                "generic_assertion",
                "cy.get('.saving').should",
                "cy.get('.saving').should('be.visible')",
                {
                    "assertion_matcher": "should",
                    "assertion_semantic_matcher_ast": "be.visible",
                    "assertion_subject_kind": "locator",
                    "assertion_subject_basis_ast": "ast_cypress_subject_chain",
                },
                "element_presence",
            ),
            (
                "generic_assertion",
                "expect(updateResponse.status).to.equal",
                "expect(updateResponse.status).to.equal(201)",
                {
                    "assertion_matcher": "equal",
                    "assertion_subject_kind": "unknown",
                    "assertion_subject_path_json": '["updateResponse", "status"]',
                },
                "network_contract",
            ),
            (
                "generic_assertion",
                "expect(res.ok()).toBeFalsy",
                "expect(res.ok()).toBeFalsy()",
                {
                    "assertion_matcher": "toBeFalsy",
                    "assertion_subject_kind": "unknown",
                    "assertion_subject_path_json": '["res", "ok"]',
                },
                "network_contract",
            ),
            (
                "generic_assertion",
                "expect(requestedPage).toEqual",
                'expect(requestedPage).toEqual("https://example.org/account")',
                {
                    "assertion_matcher": "toEqual",
                    "assertion_subject_kind": "unknown",
                    "assertion_subject_path_json": '["requestedPage"]',
                },
                "navigation_outcome",
            ),
            (
                "generic_assertion",
                "expect(getEventSummary(events).counter).toBe",
                "expect(getEventSummary(events).counter).toBe(2)",
                {
                    "assertion_matcher": "toBe",
                    "assertion_subject_kind": "unknown",
                    "assertion_subject_path_json": '["getEventSummary", "counter"]',
                },
                "interactive_state",
            ),
            (
                "generic_assertion",
                "expect(fontSize).toBe",
                'expect(await button.evaluate((el) => getComputedStyle(el).fontSize)).toBe("14px")',
                {
                    "assertion_matcher": "toBe",
                    "assertion_subject_kind": "unknown",
                    "assertion_subject_path_json": '["button", "style", "fontSize"]',
                },
                "style_or_visual_state",
            ),
            (
                "generic_assertion",
                "expect(json.title).toBe",
                'expect(json.title).toBe("Welcome")',
                {
                    "assertion_matcher": "toBe",
                    "assertion_subject_kind": "unknown",
                    "assertion_subject_path_json": '["json", "title"]',
                },
                "content_correctness",
            ),
            (
                "generic_assertion",
                "expect(result).to.include.members",
                "expect(result).to.include.members([0, 2])",
                {
                    "assertion_matcher": "members",
                    "assertion_semantic_matcher_ast": "include.members",
                    "assertion_subject_kind": "unknown",
                    "assertion_subject_path_json": '["result"]',
                },
                "api_or_data_contract",
            ),
            (
                "generic_assertion",
                "expect(page.screenshot()).toMatchSnapshot",
                "expect(await page.screenshot()).toMatchSnapshot('home.png')",
                {
                    "assertion_matcher": "toMatchSnapshot",
                    "assertion_subject_kind": "unknown",
                    "assertion_subject_path_json": '["page", "screenshot"]',
                },
                "visual_regression",
            ),
            (
                "generic_assertion",
                "cy.get('[name=title]').should",
                "cy.get('[name=title]').should(($el) => { expect($el).to.have.value('Test title'); })",
                {
                    "assertion_matcher": "should",
                    "assertion_subject_kind": "locator",
                    "assertion_subject_basis_ast": "ast_cypress_subject_chain",
                    "assertion_callback_intent_hint_ast": "content_correctness",
                    "assertion_callback_intent_basis_ast": "ast_callback_nested_assertion",
                    "assertion_callback_nested_assertion_count": 1,
                    "assertion_callback_nested_matchers_json": '["have.value"]',
                },
                "value_or_attribute_correctness",
            ),
        ]
        for category, name, raw, feature, expected in cases:
            with self.subTest(raw=raw):
                detail = classify_verification_intent_detail(category, name, raw, feature)
                self.assertEqual(detail["verification_intent"], expected)

    def test_355am_current_matcher_precedence_and_scalar_tail(self):
        cases = [
            (
                "generic_assertion",
                "and",
                "cy.get('label').first().scrollIntoView().should('be.visible').and('contain', element.display_name)",
                {
                    "assertion_matcher": "and",
                    "assertion_semantic_matcher_ast": "contain",
                    "assertion_subject_semantic_role_ast": "text_content_payload",
                    "assertion_subject_kind": "locator",
                },
                "content_correctness",
            ),
            (
                "generic_assertion",
                "and",
                "cy.findByText(text).scrollIntoView().should('be.visible').and('have.attr', 'href').and('include', link)",
                {
                    "assertion_matcher": "and",
                    "assertion_semantic_matcher_ast": "include",
                    "assertion_subject_semantic_role_ast": "text_content_payload",
                    "assertion_subject_kind": "locator",
                },
                "navigation_outcome",
            ),
            (
                "generic_assertion",
                "should",
                "cy.get('@toolbar').should('have.prop', 'promptDescription', 'Generated text').should('have.prop', 'currentVersion', 0)",
                {
                    "assertion_matcher": "should",
                    "assertion_semantic_matcher_ast": "have.prop",
                    "assertion_subject_semantic_role_ast": "text_content_payload",
                    "assertion_subject_kind": "unknown",
                },
                "value_or_attribute_correctness",
            ),
            (
                "generic_assertion",
                "expect",
                "expect(new Date(timestamp as number)).to.deep.equal(new Date(Date.now()))",
                {
                    "assertion_matcher": "equal",
                    "assertion_subject_kind": "unknown",
                    "assertion_subject_path_json": '["timestamp"]',
                },
                "value_or_attribute_correctness",
            ),
            (
                "generic_assertion",
                "expect",
                "expect(numberValue).toEqual(10)",
                {
                    "assertion_matcher": "toEqual",
                    "assertion_subject_kind": "unknown",
                    "assertion_subject_path_json": '["numberValue"]',
                },
                "value_or_attribute_correctness",
            ),
            (
                "generic_assertion",
                "expect",
                "expect(typeof intercept.response?.body.data.body[5].varchar_column).to.be.equal('object')",
                {
                    "assertion_matcher": "equal",
                    "assertion_subject_semantic_role_ast": "network_payload",
                    "assertion_subject_kind": "unknown",
                    "assertion_subject_path_json": '["intercept", "response", "body", "data", "body", "varchar_column"]',
                },
                "network_contract",
            ),
            (
                "generic_assertion",
                "expect",
                "expect(clickCount).toBe(1)",
                {
                    "assertion_matcher": "toBe",
                    "assertion_subject_kind": "unknown",
                    "assertion_subject_path_json": '["clickCount"]',
                },
                "interactive_state",
            ),
        ]
        for category, name, raw, feature, expected in cases:
            with self.subTest(raw=raw):
                detail = classify_verification_intent_detail(category, name, raw, feature)
                self.assertEqual(detail["verification_intent"], expected)

    def test_latest_audit_matcherless_lexical_fallbacks(self):
        cases = [
            (
                "expect(result).to.include.members",
                "expect(result).to.include.members([0, 2])",
                "api_or_data_contract",
            ),
            (
                "expect(await page.screenshot()).toMatchSnapshot",
                "expect(await page.screenshot({ animations: 'disabled' })).toMatchSnapshot('home.png')",
                "visual_regression",
            ),
            (
                "expect(submission.multiselect_options).to.include.members",
                "expect(submission.multiselect_options).to.include.members(['opt1', 'opt3'])",
                "api_or_data_contract",
            ),
            (
                "cy.gridInstance().invoke('getCheckedRowKeys').should",
                "cy.gridInstance().invoke('getCheckedRowKeys').should((result) => { expect(result).to.include.members([0, 2]); })",
                "api_or_data_contract",
            ),
        ]
        for name, raw, expected in cases:
            with self.subTest(raw=raw):
                feature = {}
                if "should((result)" in raw:
                    feature = {
                        "assertion_matcher": "should",
                        "assertion_callback_intent_hint_ast": "value_or_attribute_correctness",
                        "assertion_callback_intent_basis_ast": "ast_callback_nested_assertion",
                        "assertion_callback_nested_matchers_json": '["include"]',
                    }
                detail = classify_verification_intent_detail("generic_assertion", name, raw, feature)
                self.assertEqual(detail["verification_intent"], expected)

    def test_subject_name_heuristic_is_not_ast_subject_evidence(self):
        detail = classify_verification_intent_detail(
            "generic_assertion",
            "expectStatusLabel",
            "expect(responseLabel).toBe('OK')",
            {
                "assertion_matcher": "toBe",
                "assertion_subject_kind": "response",
                "assertion_subject_basis_ast": "ast_subject_identifier_name_heuristic",
            },
        )
        self.assertEqual(detail["verification_intent"], "api_or_data_contract")
        self.assertEqual(detail["verification_intent_evidence_basis"], "subject_name_heuristic_fallback")
        self.assertEqual(detail["verification_intent_confidence"], "medium")

    def test_api_subject_name_heuristic_network_context_is_not_ast_subject_evidence(self):
        detail = classify_verification_intent_detail(
            "generic_assertion",
            "expectApiResponse",
            "expect(apiResponse).toEqual(result)",
            {
                "assertion_matcher": "toEqual",
                "assertion_subject_kind": "api",
                "assertion_subject_basis_ast": "ast_subject_identifier_name_heuristic",
            },
        )
        self.assertEqual(detail["verification_intent"], "api_or_data_contract")
        self.assertEqual(detail["verification_intent_evidence_basis"], "subject_name_heuristic_fallback")

    def test_response_wait_ast_subject_remains_network_contract(self):
        detail = classify_verification_intent_detail(
            "generic_assertion",
            "expectStatus",
            "expect(response.status()).toBe(200)",
            {
                "assertion_matcher": "toBe",
                "assertion_subject_kind": "response",
                "assertion_subject_basis_ast": "ast_response_wait_call",
            },
        )
        self.assertEqual(detail["verification_intent"], "network_contract")

    def test_response_ok_truthiness_is_api_contract_when_subject_is_heuristic(self):
        detail = classify_verification_intent_detail(
            "generic_assertion",
            "expect(res.ok()).toBeTruthy",
            "expect(res.ok()).toBeTruthy()",
            {
                "assertion_matcher": "toBeTruthy",
                "assertion_subject_kind": "response",
                "assertion_subject_basis_ast": "ast_subject_identifier_name_heuristic",
            },
        )
        self.assertEqual(detail["verification_intent"], "api_or_data_contract")
        self.assertEqual(detail["verification_intent_evidence_basis"], "lexical_response_ok_contract_context")

    def test_api_boolean_subject_path_is_api_contract(self):
        detail = classify_verification_intent_detail(
            "generic_assertion",
            "expect(result.gotResponse).toBeTruthy",
            "expect(result.gotResponse).toBeTruthy()",
            {
                "assertion_matcher": "toBeTruthy",
                "assertion_subject_kind": "unknown",
                "assertion_subject_path_json": '["result", "gotResponse"]',
            },
        )
        self.assertEqual(detail["verification_intent"], "api_or_data_contract")
        self.assertEqual(detail["verification_intent_evidence_basis"], "ast_assertion_subject_path")

    def test_specific_semantic_matcher_precedes_weaker_subject_hints(self):
        cases = [
            (
                "be.visible",
                "element_presence",
                '["node", "textContent"]',
                "cy.get('#x').should('be.visible')",
            ),
            (
                "be.enabled",
                "interactive_state",
                '["button", "className"]',
                "cy.get('#x').should('be.enabled')",
            ),
            (
                "be.disabled",
                "interactive_state",
                '["button", "style"]',
                "cy.get('#x').should('be.disabled')",
            ),
            (
                "have.value",
                "value_or_attribute_correctness",
                '["input", "disabled"]',
                "cy.get('#x').should('have.value', 'abc')",
            ),
        ]
        for matcher, expected, subject_path, raw in cases:
            with self.subTest(matcher=matcher):
                detail = classify_verification_intent_detail(
                    "generic_assertion",
                    "should",
                    raw,
                    {
                        "assertion_matcher": "should",
                        "assertion_semantic_matcher_ast": matcher,
                        "assertion_subject_kind": "locator",
                        "assertion_subject_basis_ast": "ast_cypress_subject_chain",
                        "assertion_subject_path_json": subject_path,
                    },
                )
                self.assertEqual(detail["verification_intent"], expected)
                self.assertEqual(detail["verification_intent_evidence_basis"], "ast_assertion_semantic_matcher")

    def test_generic_property_names_do_not_trigger_collection_size(self):
        detail = classify_verification_intent_detail(
            "generic_assertion",
            "expect(surveyResult.country).toEqual",
            "expect(surveyResult.country).toEqual('US')",
            {
                "assertion_matcher": "toEqual",
                "assertion_subject_kind": "unknown",
                "assertion_subject_path_json": '["surveyResult", "country"]',
            },
        )
        self.assertEqual(detail["verification_intent"], "value_or_attribute_correctness")

    def test_network_alias_payload_subject_remains_network_contract(self):
        detail = classify_verification_intent_detail(
            "generic_assertion",
            "cy.wait('@save').its('response.body').should",
            "cy.wait('@save').its('response.body').should('deep.equal', expectedBody)",
            {
                "assertion_matcher": "should",
                "assertion_semantic_matcher_ast": "deep.equal",
                "assertion_subject_kind": "network",
                "assertion_subject_basis_ast": "ast_response_wait_call",
                "assertion_subject_path_json": '["interception", "response", "body"]',
            },
        )
        self.assertEqual(detail["verification_intent"], "network_contract")

    def test_spy_payload_and_call_count_route_to_distinct_intents(self):
        payload_detail = classify_verification_intent_detail(
            "generic_assertion",
            "expect(mockSetFilters).toHaveBeenCalledWith",
            "expect(mockSetFilters).toHaveBeenCalledWith({ country: 'US' })",
            {
                "assertion_matcher": "toHaveBeenCalledWith",
                "assertion_subject_kind": "unknown",
            },
        )
        self.assertEqual(payload_detail["verification_intent"], "api_or_data_contract")

        count_detail = classify_verification_intent_detail(
            "generic_assertion",
            "expect(mockSetFilters).toHaveBeenCalledTimes",
            "expect(mockSetFilters).toHaveBeenCalledTimes(2)",
            {
                "assertion_matcher": "toHaveBeenCalledTimes",
                "assertion_subject_kind": "unknown",
            },
        )
        self.assertEqual(count_detail["verification_intent"], "interactive_state")

    def test_presence_property_context_is_not_reported_as_ast_evidence(self):
        detail = classify_verification_intent_detail(
            "generic_assertion",
            "expect(node.isPresent()).notOk",
            "expect(node.isPresent()).notOk()",
            {
                "assertion_matcher": "notOk",
                "assertion_subject_kind": "unknown",
            },
        )
        self.assertEqual(detail["verification_intent"], "element_presence")
        self.assertEqual(detail["verification_intent_evidence_basis"], "lexical_presence_property_context")

    def test_navigation_context_overrides_ambiguous_api_status(self):
        detail = classify_verification_intent_detail(
            "generic_assertion",
            "should",
            "cy.request(link.prop('href')).its('status').should('eq', 200)",
            {
                "assertion_matcher": "should",
                "assertion_semantic_matcher_ast": "eq",
                "assertion_subject_kind": "api",
                "assertion_subject_basis_ast": "ast_api_call",
            },
        )
        self.assertEqual(detail["verification_intent"], "network_contract")

    def test_latest_corpus_rq5c_subject_precedence_regressions(self):
        cases = [
            (
                "expect(res1.response).to.have.property",
                'expect(res1.response).to.have.property("statusCode", 200)',
                {
                    "assertion_matcher": "property",
                    "assertion_subject_kind": "unknown",
                    "assertion_subject_path_json": '["res1", "response"]',
                },
                "network_contract",
            ),
            (
                "expect(interception?.response?.statusCode).to.equal",
                "expect(interception?.response?.statusCode).to.equal(200)",
                {
                    "assertion_matcher": "equal",
                    "assertion_subject_kind": "unknown",
                    "assertion_subject_path_json": '["interception", "response", "statusCode"]',
                },
                "network_contract",
            ),
            (
                "expect(userRes.status).to.equal",
                "expect(userRes.status).to.equal(201)",
                {
                    "assertion_matcher": "equal",
                    "assertion_subject_kind": "unknown",
                },
                "network_contract",
            ),
            (
                "cy.get('@notifySpy').should",
                "cy.get('@notifySpy').should('be.called')",
                {
                    "assertion_matcher": "should",
                    "assertion_semantic_matcher_ast": "be.called",
                    "assertion_subject_kind": "locator",
                    "assertion_subject_text_ast": "@notifySpy",
                },
                "interactive_state",
            ),
            (
                "cy.get('@notifySpy1').should",
                "cy.get('@notifySpy1').should('not.be.called')",
                {
                    "assertion_matcher": "should",
                    "assertion_semantic_matcher_ast": "not.be.called",
                    "assertion_subject_kind": "locator",
                    "assertion_subject_text_ast": "@notifySpy1",
                },
                "interactive_state",
            ),
            (
                "cy.get('@notifySpy').should",
                "cy.get('@notifySpy').should('have.been.calledWithMatch',\n            otherChannel.display_name, {body, tag: body, requireInteraction: false, silent: false})",
                {
                    "assertion_matcher": "should",
                    "assertion_semantic_matcher_ast": "have.been.calledWithMatch",
                    "assertion_subject_kind": "locator",
                    "assertion_subject_text_ast": "@notifySpy",
                },
                "content_correctness",
            ),
            (
                "cy.get('.post-message__text').findByText(message).should",
                "cy.get('.post-message__text').findByText(message).should('have.css', 'color', 'rgba(63, 67, 80, 0.75)')",
                {
                    "assertion_matcher": "should",
                    "assertion_semantic_matcher_ast": "have.css",
                    "assertion_subject_kind": "locator",
                    "assertion_subject_basis_ast": "ast_cypress_subject_chain",
                },
                "style_or_visual_state",
            ),
            (
                "expect(detailButtonIcon.first()).toHaveCSS",
                'expect(detailButtonIcon.first()).toHaveCSS("opacity", "0")',
                {
                    "assertion_matcher": "toHaveCSS",
                    "assertion_subject_kind": "unknown",
                    "assertion_subject_path_json": '["detailButtonIcon", "first"]',
                },
                "style_or_visual_state",
            ),
            (
                "cy.get(tag).should.and",
                'cy.get(tag).should("have.css", "min-width", "150px").and(($el) => { const borderRadius = $el.css("border-radius"); expect(borderRadius).to.match(/^(0px|4px)$/); })',
                {
                    "assertion_matcher": "and",
                    "assertion_subject_kind": "locator",
                    "assertion_subject_basis_ast": "ast_cypress_subject_chain",
                    "assertion_callback_intent_hint_ast": "value_or_attribute_correctness",
                    "assertion_callback_intent_basis_ast": "ast_callback_nested_assertion",
                    "assertion_callback_nested_assertion_count": 1,
                    "assertion_callback_nested_matchers_json": '["match"]',
                },
                "style_or_visual_state",
            ),
        ]
        for name, raw, feature, expected in cases:
            with self.subTest(raw=raw):
                detail = classify_verification_intent_detail("generic_assertion", name, raw, feature)
                self.assertEqual(detail["verification_intent"], expected)

    def test_common_equality_semantic_matchers_do_not_collapse_to_unspecified(self):
        for matcher in ("eq", "equal", "eql", "be.true", "match"):
            with self.subTest(matcher=matcher):
                detail = classify_verification_intent_detail(
                    "generic_assertion",
                    "should",
                    f'cy.get("x").should("{matcher}", "x")',
                    {
                        "assertion_matcher": "should",
                        "assertion_semantic_matcher_ast": matcher,
                        "assertion_subject_kind": "locator",
                        "assertion_subject_basis_ast": "ast_cypress_subject_chain",
                    },
                )
                self.assertNotEqual(detail["verification_intent"], "unspecified")
                self.assertIn(
                    detail["verification_intent_evidence_basis"],
                    (
                        "ast_assertion_semantic_matcher",
                        "ast_assertion_matcher",
                        "ast_assertion_subject_and_matcher",
                    ),
                )

    def test_cypress_semantic_matcher_argument_drives_intent(self):
        cases = [
            ("have.class", "style_or_visual_state"),
            ("not.have.class", "style_or_visual_state"),
            ("have.value", "value_or_attribute_correctness"),
            ("not.have.value", "value_or_attribute_correctness"),
            ("have.length", "collection_size"),
            ("not.have.length", "collection_size"),
            ("have.lengthOf", "collection_size"),
            ("have.attr", "value_or_attribute_correctness"),
            ("not.have.attr", "value_or_attribute_correctness"),
            ("have.data", "value_or_attribute_correctness"),
            ("have.html", "content_correctness"),
            ("have.property", "value_or_attribute_correctness"),
            ("contain.text", "content_correctness"),
            ("not.contain.text", "content_correctness"),
            ("include.text", "content_correctness"),
            ("not.include.text", "content_correctness"),
            ("be.visible", "element_presence"),
            ("not.be.visible", "element_presence"),
            ("be.not.visible", "element_presence"),
            ("not.exist", "element_presence"),
            ("not.be.enabled", "interactive_state"),
            ("be.equal", "value_or_attribute_correctness"),
            ("be.eql", "value_or_attribute_correctness"),
            ("be.gt", "value_or_attribute_correctness"),
            ("be.closeTo", "value_or_attribute_correctness"),
            ("be.oneOf", "value_or_attribute_correctness"),
            ("be.selected", "interactive_state"),
            ("not.be.exist", "element_presence"),
            ("have.been.calledTwice", "interactive_state"),
            ("have.been.calledThrice", "interactive_state"),
            ("have.been.calledOnceWith", "api_or_data_contract"),
            ("be.calledWithMatch", "api_or_data_contract"),
            ("be.calledWithExactly", "api_or_data_contract"),
            ("have.a.prop", "value_or_attribute_correctness"),
            ("have.any.keys", "value_or_attribute_correctness"),
            ("haveOwnProperty", "value_or_attribute_correctness"),
            ("have.deep.property", "value_or_attribute_correctness"),
            ("have.sameColumnData", "value_or_attribute_correctness"),
            ("attr", "value_or_attribute_correctness"),
            ("not.have.a.property", "value_or_attribute_correctness"),
            ("not.have", "value_or_attribute_correctness"),
            ("not.have.descendants", "element_presence"),
            ("toBeInstanceOf", "value_or_attribute_correctness"),
            ("toBeCloseTo", "value_or_attribute_correctness"),
            ("isBoolean", "value_or_attribute_correctness"),
            ("be.most", "value_or_attribute_correctness"),
            ("toHaveId", "value_or_attribute_correctness"),
            ("have.been.calledAfter", "api_or_data_contract"),
            ("eqls", "value_or_attribute_correctness"),
        ]
        for matcher, expected in cases:
            with self.subTest(matcher=matcher):
                detail = classify_verification_intent_detail(
                    "generic_assertion",
                    "should",
                    f'cy.get("x").should("{matcher}")',
                    {
                        "assertion_matcher": "should",
                        "assertion_semantic_matcher_ast": matcher,
                        "assertion_subject_kind": "locator",
                    },
                )
                self.assertEqual(detail["verification_intent"], expected)
                self.assertEqual(
                    detail["verification_intent_evidence_basis"],
                    "ast_assertion_semantic_matcher",
                )

    def test_lexical_fallback_is_explicit_when_chain_metadata_missing(self):
        detail = classify_verification_intent_detail(
            "generic_assertion",
            "toHaveClass",
            "await expect(button).toHaveClass('active')",
        )
        self.assertEqual(detail["verification_intent"], "style_or_visual_state")
        self.assertEqual(detail["verification_intent_evidence_basis"], "lexical_fallback")

    def test_latest_review_network_contract_precedence(self):
        cases = [
            (
                "cy.request body",
                "should",
                "cy.request(`${baseUrl}/${DemoPath.Time}`).its('body').should('include.match', /<h1.*>\\s+Time/)",
                {
                    "assertion_matcher": "should",
                    "assertion_semantic_matcher_ast": "include.match",
                    "assertion_subject_kind": "api",
                    "assertion_subject_basis_ast": "ast_api_call",
                },
                "network_contract",
            ),
            (
                "bare status",
                "toBeGreaterThanOrEqual",
                "expect(status).toBeGreaterThanOrEqual(200)",
                {
                    "assertion_matcher": "toBeGreaterThanOrEqual",
                    "assertion_subject_kind": "unknown",
                    "assertion_subject_path_json": '["status"]',
                },
                "value_or_attribute_correctness",
            ),
            (
                "response meta status",
                "eq",
                "expect(response.body.responseMeta.status).to.eq(201)",
                {
                    "assertion_matcher": "eq",
                    "assertion_subject_kind": "unknown",
                    "assertion_subject_path_json": '["response", "body", "responseMeta", "status"]',
                },
                "network_contract",
            ),
        ]
        for _label, name, raw, feature, expected in cases:
            with self.subTest(raw=raw):
                detail = classify_verification_intent_detail("generic_assertion", name, raw, feature)
                self.assertEqual(detail["verification_intent"], expected)

    def test_latest_review_event_and_interactive_state_precedence(self):
        cases = [
            (
                "expect((await getEventSummary(link, 'blur')).counter).toBe(0)",
                {
                    "assertion_matcher": "toBe",
                    "assertion_subject_kind": "unknown",
                    "assertion_subject_path_json": '["getEventSummary", "counter"]',
                },
            ),
            (
                "cy.get(\"@changeSpy\").should('have.callCount', 0)",
                {
                    "assertion_matcher": "should",
                    "assertion_semantic_matcher_ast": "have.callCount",
                    "assertion_subject_kind": "locator",
                    "assertion_subject_text_ast": "@changeSpy",
                },
            ),
            (
                "expect((stub as any).args.slice(-1)[0][0].detail.previouslySelectedRows[0].id).to.equal(\"firstRowSingleSelect\")",
                {
                    "assertion_matcher": "equal",
                    "assertion_subject_kind": "unknown",
                    "assertion_subject_path_json": '["stub", "args", "detail", "previouslySelectedRows", "id"]',
                },
            ),
            (
                "expect(await getProperty<boolean>(child, 'disabledParent')).toBeFalsy()",
                {
                    "assertion_matcher": "toBeFalsy",
                    "assertion_subject_kind": "unknown",
                    "assertion_subject_path_json": '["disabledParent"]',
                },
            ),
            (
                "ui.button.findByTitle('Take Snapshot').should('be.visible').should('be.enabled')",
                {
                    "assertion_matcher": "should",
                    "assertion_semantic_matcher_ast": "be.enabled",
                    "assertion_subject_kind": "unknown",
                },
            ),
        ]
        for raw, feature in cases:
            with self.subTest(raw=raw):
                detail = classify_verification_intent_detail("generic_assertion", "should", raw, feature)
                self.assertEqual(detail["verification_intent"], "interactive_state")

    def test_latest_review_presence_and_contract_boundaries(self):
        cases = [
            (
                "cy.getElementByTestId('collapsibleNavAppLink-objects').should('exist')",
                {"assertion_matcher": "should", "assertion_subject_kind": "unknown"},
                "element_presence",
            ),
            (
                'this.GetElement(selector, "exist", timeout).eq(index).scrollIntoView().should(visibility == true ? "be.visible" : "not.be.visible")',
                {"assertion_matcher": "should", "assertion_subject_kind": "unknown"},
                "element_presence",
            ),
            (
                "t.expect(t.ctx.usa.getNode('California').isPresent()).notOk()",
                {"assertion_matcher": "notOk", "assertion_subject_kind": "unknown"},
                "element_presence",
            ),
            (
                "expect(page).toBeInstanceOf(JupyterLabPage)",
                {"assertion_matcher": "toBeInstanceOf", "assertion_subject_kind": "unknown"},
                "api_or_data_contract",
            ),
            (
                "expect(result.error).toBeUndefined()",
                {"assertion_matcher": "toBeUndefined", "assertion_subject_kind": "unknown", "assertion_subject_path_json": '["result", "error"]'},
                "api_or_data_contract",
            ),
            (
                "expect(minmaxRowCount).toBeGreaterThanOrEqual(1)",
                {"assertion_matcher": "toBeGreaterThanOrEqual", "assertion_subject_kind": "unknown", "assertion_subject_path_json": '["minmaxRowCount"]'},
                "collection_size",
            ),
            (
                "assert.isAbove(Number($canvasShape.eq(-1).attr('fill-opacity')), Number($canvasShape.eq(0).attr('fill-opacity')))",
                {"assertion_matcher": "isAbove", "assertion_subject_kind": "unknown"},
                "style_or_visual_state",
            ),
            (
                "cy.get('@notifySpy2').should('have.been.calledWithMatch', `Reply`, (args: {body: string}) => { expect(args.body).to.equal(message); return true; })",
                {"assertion_matcher": "should", "assertion_subject_kind": "locator"},
                "content_correctness",
            ),
        ]
        for raw, feature, expected in cases:
            with self.subTest(raw=raw):
                detail = classify_verification_intent_detail("generic_assertion", "expect", raw, feature)
                self.assertEqual(detail["verification_intent"], expected)

    def test_structured_subject_semantic_role_precedes_generic_matchers(self):
        cases = [
            (
                "expect(variantTextDiv).toContainText('no variant')",
                {"assertion_matcher": "toContainText", "assertion_subject_semantic_role_ast": "text_content_payload"},
                "content_correctness",
            ),
            (
                "expect(selectAll).toBeAttached()",
                {"assertion_matcher": "toBeAttached", "assertion_subject_semantic_role_ast": "element_presence"},
                "element_presence",
            ),
            (
                "expect(status, statusMessage).to.equal(httpStatus)",
                {"assertion_matcher": "equal", "assertion_subject_semantic_role_ast": "network_status"},
                "network_contract",
            ),
            (
                "expect(await getProperty<boolean>(child, 'disabled')).toBeFalsy()",
                {"assertion_matcher": "toBeFalsy", "assertion_subject_semantic_role_ast": "ui_control_state"},
                "interactive_state",
            ),
            (
                "expect(deleteCounter).to.be.equal(1)",
                {"assertion_matcher": "equal", "assertion_subject_semantic_role_ast": "ui_event_counter"},
                "interactive_state",
            ),
            (
                "expect(heightAtTop).toBeCloseTo(heightAtBottom, 1)",
                {"assertion_matcher": "toBeCloseTo", "assertion_subject_semantic_role_ast": "style_layout_property"},
                "style_or_visual_state",
            ),
            (
                "expect(surveyResult.image[0].name).toBe('stub.txt')",
                {"assertion_matcher": "toBe", "assertion_subject_semantic_role_ast": "scalar_property"},
                "value_or_attribute_correctness",
            ),
            (
                "expect(page).toBeInstanceOf(JupyterLabPage)",
                {"assertion_matcher": "toBeInstanceOf", "assertion_subject_semantic_role_ast": "api_object_contract"},
                "api_or_data_contract",
            ),
            (
                "expect(rows.length).toBe(2)",
                {"assertion_matcher": "toBe", "assertion_subject_semantic_role_ast": "collection_size"},
                "collection_size",
            ),
            (
                "expect(await page.screenshot()).toMatchSnapshot('page.png')",
                {"assertion_matcher": "toMatchSnapshot", "assertion_subject_semantic_role_ast": "visual_snapshot_api"},
                "visual_regression",
            ),
        ]
        for raw, feature, expected in cases:
            with self.subTest(raw=raw):
                detail = classify_verification_intent_detail("generic_assertion", "expect", raw, feature)
                self.assertEqual(detail["verification_intent"], expected)
                self.assertEqual(detail["verification_intent_evidence_basis"], "ast_assertion_subject_semantic_role")

    def test_reviewed_rq5c_subject_boundary_cases_override_weak_semantic_roles(self):
        cases = [
            (
                "expect(await getElementStyle(prevIndicator, 'visibility')).toBe('visible')",
                {},
                "style_or_visual_state",
            ),
            (
                "expect(await pluginCheckbox.isDisabled()).toEqual(true)",
                {},
                "interactive_state",
            ),
            (
                "t.expect(getAllByText(FIXTURE_SEND_AMOUNT, { exact: false }).exists).ok()",
                {"assertion_subject_semantic_role_ast": "scalar_property"},
                "element_presence",
            ),
            (
                "t.expect(page.selected.exists).ok()",
                {
                    "assertion_matcher": "ok",
                    "assertion_subject_text_ast": "t.expect(page.selected.exists).ok()",
                    "assertion_subject_path_json": '["t","expect","ok"]',
                    "assertion_subject_semantic_role_ast": "ui_control_state",
                },
                "element_presence",
            ),
            (
                "expect(status).toBeGreaterThanOrEqual(200)",
                {
                    "assertion_matcher": "toBeGreaterThanOrEqual",
                    "assertion_subject_text_ast": "status",
                    "assertion_subject_path_json": '["status"]',
                    "assertion_subject_semantic_role_ast": "scalar_property",
                },
                "network_contract",
            ),
            (
                "cy.location().should((loc) => { expect(loc.href).to.eq(loc.origin + '/applications'); })",
                {"assertion_subject_semantic_role_ast": "scalar_property"},
                "navigation_outcome",
            ),
            (
                'expect(ariaSelectedText).to.be.oneOf([null, undefined, ""])',
                {},
                "interactive_state",
            ),
        ]
        for raw, feature, expected in cases:
            with self.subTest(raw=raw):
                detail = classify_verification_intent_detail("generic_assertion", "expect", raw, feature)
                self.assertEqual(detail["verification_intent"], expected)

    def test_codebook_decision_tree_boundaries_and_path_column(self):
        cases = [
            (
                "expect(status).toBe('healthy')",
                {"assertion_matcher": "toBe", "assertion_subject_path_json": '["status"]'},
                "value_or_attribute_correctness",
                "scalar_property_or_attribute",
            ),
            (
                "expect(response.status).toBe(200)",
                {"assertion_matcher": "toBe", "assertion_subject_path_json": '["response", "status"]'},
                "network_contract",
                "network_request_response_contract",
            ),
            (
                "expect(result.error).toBeUndefined()",
                {"assertion_matcher": "toBeUndefined", "assertion_subject_path_json": '["result", "error"]'},
                "api_or_data_contract",
                "api_object_or_result_contract",
            ),
            (
                "expect(computedTitleField).toHaveValue('Test Title')",
                {"assertion_matcher": "toHaveValue"},
                "value_or_attribute_correctness",
                "scalar_property_or_attribute",
            ),
            (
                "expect(typeof violation.selector).toBe('string')",
                {"assertion_matcher": "toBe", "assertion_subject_path_json": '["violation", "selector"]'},
                "api_or_data_contract",
                "api_object_or_result_contract",
            ),
            (
                "expect(await page.screenshot()).toMatchSnapshot('page.png')",
                {"assertion_matcher": "toMatchSnapshot"},
                "visual_regression",
                "visual_snapshot_api",
            ),
            (
                "cy.get('@changeSpy').should('have.callCount', 0)",
                {"assertion_matcher": "should", "assertion_semantic_matcher_ast": "have.callCount", "assertion_subject_text_ast": "@changeSpy"},
                "interactive_state",
                "interactive_state_or_event_counter",
            ),
            (
                "expect(requestPayload.group_by).to.have.ordered.members(['cpu', 'state'])",
                {
                    "assertion_matcher": "members",
                    "assertion_semantic_matcher_ast": "have.ordered.members",
                    "assertion_subject_path_json": '["requestPayload", "group_by"]',
                },
                "api_or_data_contract",
                "api_object_or_result_contract",
            ),
            (
                "expect(xhr.request.body.root_pass).to.be.a('string')",
                {
                    "assertion_matcher": "be.a",
                    "assertion_subject_path_json": '["xhr", "request", "body", "root_pass"]',
                },
                "network_contract",
                "network_request_response_contract",
            ),
            (
                "ui.button.findByTitle('Save Changes').should('be.visible').should('be.enabled')",
                {
                    "assertion_matcher": "should",
                    "assertion_semantic_matcher_ast": "be.enabled",
                    "assertion_subject_kind": "locator",
                },
                "interactive_state",
                "interactive_state_or_event_counter",
            ),
            (
                "cy.get('[class*=\"visible-overflow-button\"]').should('be.visible').should('have.css', 'justify-content', 'end')",
                {
                    "assertion_matcher": "should",
                    "assertion_semantic_matcher_ast": "have.css",
                    "assertion_subject_kind": "locator",
                },
                "style_or_visual_state",
                "style_layout_css",
            ),
            (
                "expect(await builder.isDashboardDialogVisible()).toBe(false)",
                {"assertion_matcher": "toBe", "assertion_subject_path_json": '["builder", "isDashboardDialogVisible"]'},
                "element_presence",
                "element_presence",
            ),
            (
                "expect(await pm.dashboardPanelTime.isPanelTimeEnabled()).toBe(true)",
                {"assertion_matcher": "toBe", "assertion_subject_path_json": '["pm", "dashboardPanelTime", "isPanelTimeEnabled"]'},
                "interactive_state",
                "interactive_state_or_event_counter",
            ),
            (
                "expect(href).toContain('%25')",
                {"assertion_matcher": "toContain", "assertion_subject_path_json": '["href"]'},
                "navigation_outcome",
                "navigation_location",
            ),
            (
                "cy.get('.tiptap').should('contain.html', '<ul><li><p><br class=\"ProseMirror-trailingBreak\"></p></li></ul>')",
                {"assertion_matcher": "should", "assertion_semantic_matcher_ast": "contain.html"},
                "content_correctness",
                "user_facing_text_content",
            ),
            (
                "expect(_satellite?.track).to.be.a('function')",
                {"assertion_matcher": "be.a", "assertion_subject_path_json": '["_satellite", "track"]'},
                "api_or_data_contract",
                "api_object_or_result_contract",
            ),
            (
                "expect(interception.request.body.filters).to.have.length(3)",
                {
                    "assertion_matcher": "have.length",
                    "assertion_semantic_matcher_ast": "have.length",
                    "assertion_subject_semantic_role_ast": "network_payload",
                    "assertion_subject_path_json": '["interception", "request", "body", "filters"]',
                },
                "network_contract",
                "network_request_response_contract",
            ),
            (
                "expect(currentUrl).toContain('org_identifier=_meta')",
                {
                    "assertion_matcher": "toContain",
                    "assertion_subject_semantic_role_ast": "navigation_location",
                    "assertion_subject_path_json": '["currentUrl"]',
                },
                "navigation_outcome",
                "navigation_location",
            ),
            (
                "cy.get('.tiptap').find('pre>code.language-css').should('have.length', 1)",
                {
                    "assertion_matcher": "should",
                    "assertion_semantic_matcher_ast": "have.length",
                    "assertion_subject_semantic_role_ast": "style_layout_property",
                },
                "style_or_visual_state",
                "style_layout_css",
            ),
            (
                "cy.get('.tiptap').should('have.text', 'green serif').and('have.attr', 'style', 'font-family: serif')",
                {
                    "assertion_matcher": "and",
                    "assertion_semantic_matcher_ast": "have.attr",
                    "assertion_subject_semantic_role_ast": "style_layout_property",
                },
                "style_or_visual_state",
                "style_layout_css",
            ),
            (
                "expect(nodePools[0]).to.be.an('object')",
                {
                    "assertion_matcher": "be.an",
                    "assertion_semantic_matcher_ast": "be.an",
                    "assertion_subject_semantic_role_ast": "api_object_contract",
                },
                "api_or_data_contract",
                "api_object_or_result_contract",
            ),
            (
                "cy.get('[aria-labelledby=\"start-date\"]').should('have.value', date)",
                {
                    "assertion_matcher": "should",
                    "assertion_semantic_matcher_ast": "have.value",
                    "assertion_subject_path_json": '["aria-labelledby", "start-date"]',
                },
                "value_or_attribute_correctness",
                "scalar_property_or_attribute",
            ),
        ]
        for raw, feature, expected, expected_path in cases:
            with self.subTest(raw=raw):
                detail = classify_verification_intent_detail("generic_assertion", "expect", raw, feature)
                self.assertEqual(detail["verification_intent"], expected)
                self.assertEqual(detail["verification_intent_codebook_path"], expected_path)

    def test_mini_v7_remaining_rq5c_boundaries(self):
        cases = [
            (
                "ui.button.findByAttribute('aria-label', 'Group By Dashboard Metrics').should('be.visible').first()",
                {
                    "assertion_matcher": "should",
                    "assertion_semantic_matcher_ast": "be.visible",
                    "assertion_subject_semantic_role_ast": "api_object_contract",
                    "assertion_subject_path_json": '["aria-label", "Group By Dashboard Metrics"]',
                },
                "element_presence",
                "element_presence",
            ),
            (
                "expect(async () => { await expect(page.locator('.export-preview')).toBeVisible() }).toPass()",
                {
                    "assertion_matcher": "toPass",
                    "assertion_semantic_matcher_ast": "toPass",
                    "assertion_callback_intent_hint_ast": "element_presence",
                    "assertion_callback_intent_basis_ast": "ast_callback_nested_assertion",
                    "assertion_callback_nested_matchers_json": '["toBeVisible"]',
                    "assertion_callback_nested_assertion_count": "1",
                },
                "element_presence",
                "callback_element_presence",
            ),
            (
                "expect(result2.actualCount).toBeGreaterThanOrEqual(1)",
                {
                    "assertion_matcher": "toBeGreaterThanOrEqual",
                    "assertion_subject_semantic_role_ast": "scalar_property",
                    "assertion_subject_path_json": '["result2", "actualCount"]',
                    "assertion_subject_text_ast": "result2.actualCount",
                },
                "collection_size",
                "true_collection_cardinality",
            ),
            (
                "expect(page.url()).toMatch(/\\/versions/)",
                {
                    "assertion_matcher": "toMatch",
                    "assertion_subject_semantic_role_ast": "api_object_contract",
                    "assertion_subject_text_ast": "page.url()",
                    "assertion_subject_path_json": '["page", "url"]',
                },
                "navigation_outcome",
                "navigation_location",
            ),
            (
                "expect(status).toBe(200)",
                {
                    "assertion_matcher": "toBe",
                    "assertion_subject_semantic_role_ast": "scalar_property",
                    "assertion_subject_path_json": '["status"]',
                    "assertion_subject_text_ast": "status",
                },
                "network_contract",
                "network_request_response_contract",
            ),
            (
                "expect(status).toBe('healthy')",
                {
                    "assertion_matcher": "toBe",
                    "assertion_subject_semantic_role_ast": "scalar_property",
                    "assertion_subject_path_json": '["status"]',
                    "assertion_subject_text_ast": "status",
                },
                "value_or_attribute_correctness",
                "scalar_property_or_attribute",
            ),
            (
                "expect(colorResult.colorFound).toBe(true)",
                {
                    "assertion_matcher": "toBe",
                    "assertion_subject_semantic_role_ast": "scalar_property",
                    "assertion_subject_path_json": '["colorResult", "colorFound"]',
                    "assertion_subject_text_ast": "colorResult.colorFound",
                },
                "style_or_visual_state",
                "style_layout_css",
            ),
            (
                "expect(initialCount).to.be.greaterThan(0)",
                {
                    "assertion_matcher": "greaterThan",
                    "assertion_subject_semantic_role_ast": "scalar_property",
                    "assertion_subject_path_json": '["expect", "to", "be", "greaterThan"]',
                    "assertion_subject_text_ast": "expect(initialCount).to.be.greaterThan(0)",
                },
                "collection_size",
                "true_collection_cardinality",
            ),
            (
                "cy.get('.tiptap').type('### Headline').find('h3').should('contain', 'Headline')",
                {
                    "assertion_matcher": "should",
                    "assertion_semantic_matcher_ast": "contain",
                    "assertion_subject_kind": "locator",
                    "assertion_subject_semantic_role_ast": "scalar_property",
                    "assertion_subject_path_json": '["cy", "get", "type", "find", "should"]',
                    "assertion_subject_text_ast": "cy.get('.tiptap').type('### Headline').find('h3').should('contain', 'Headline')",
                },
                "content_correctness",
                "text_payload_context",
            ),
            (
                "expect(payload.stack_type).to.eq(stackType)",
                {
                    "assertion_matcher": "eq",
                    "assertion_subject_semantic_role_ast": "api_object_contract",
                    "assertion_subject_path_json": '["expect", "to", "eq"]',
                    "assertion_subject_text_ast": "expect(payload.stack_type).to.eq(stackType)",
                },
                "value_or_attribute_correctness",
                "scalar_property_or_attribute",
            ),
        ]
        for raw, feature, expected, expected_path in cases:
            with self.subTest(raw=raw):
                detail = classify_verification_intent_detail("generic_assertion", "expect", raw, feature)
                self.assertEqual(detail["verification_intent"], expected)
                self.assertEqual(detail["verification_intent_codebook_path"], expected_path)

    def test_408pm_tail_verification_intent_boundaries(self):
        cases = [
            (
                "expect(requestPayload['public']).to.equal(null)",
                {
                    "assertion_matcher": "equal",
                    "assertion_subject_path_json": '["requestPayload", "public"]',
                    "assertion_subject_text_ast": "requestPayload['public']",
                },
                "api_or_data_contract",
                "api_object_or_result_contract",
            ),
            (
                "expect(['degraded', 'critical']).toContain(status)",
                {
                    "assertion_matcher": "toContain",
                    "assertion_subject_path_json": '["status"]',
                    "assertion_subject_text_ast": "status",
                },
                "value_or_attribute_correctness",
                "scalar_property_or_attribute",
            ),
            (
                "expect(error.reason).to.eq(createLinodeErrorMsg)",
                {
                    "assertion_matcher": "eq",
                    "assertion_subject_path_json": '["error", "reason"]',
                    "assertion_subject_text_ast": "error.reason",
                },
                "content_correctness",
                "user_facing_text_content",
            ),
            (
                "cy.get('.tiptap span').should('have.length', 1).and('have.text', 'blue serif').and('have.attr', 'style', 'color: blue')",
                {
                    "assertion_matcher": "and",
                    "assertion_semantic_matcher_ast": "have.text",
                    "assertion_subject_semantic_role_ast": "style_layout_property",
                    "assertion_subject_text_ast": "cy.get('.tiptap span').and('have.text', 'blue serif')",
                },
                "content_correctness",
                "user_facing_text_content",
            ),
            (
                "expect(legendCount).toBeGreaterThan(0)",
                {
                    "assertion_matcher": "toBeGreaterThan",
                    "assertion_subject_path_json": '["legendCount"]',
                    "assertion_subject_text_ast": "legendCount",
                },
                "collection_size",
                "true_collection_cardinality",
            ),
            (
                "expect(alert_channels).to.be.an('array')",
                {
                    "assertion_matcher": "be.an",
                    "assertion_semantic_matcher_ast": "be.an",
                    "assertion_subject_path_json": '["alert_channels"]',
                    "assertion_subject_text_ast": "alert_channels",
                },
                "api_or_data_contract",
                "api_object_or_result_contract",
            ),
            (
                "expect(matchedRequests.length).toBeLessThanOrEqual(allowedNumberOfRequests)",
                {
                    "assertion_matcher": "toBeLessThanOrEqual",
                    "assertion_subject_path_json": '["matchedRequests", "length"]',
                    "assertion_subject_text_ast": "matchedRequests.length",
                },
                "network_contract",
                "network_request_response_contract",
            ),
            (
                "expect(result.totalFocusableElements).toBeLessThanOrEqual(maxFocusableElements)",
                {
                    "assertion_matcher": "toBeLessThanOrEqual",
                    "assertion_subject_path_json": '["result", "totalFocusableElements"]',
                    "assertion_subject_text_ast": "result.totalFocusableElements",
                },
                "accessibility_compliance",
                "accessibility_structure",
            ),
            (
                "expect(() => { expect(result.totalFocusableElements).toBeLessThanOrEqual(maxFocusableElements) }).toPass()",
                {
                    "assertion_matcher": "toPass",
                    "assertion_semantic_matcher_ast": "toPass",
                    "assertion_callback_intent_hint_ast": "api_or_data_contract",
                    "assertion_callback_intent_basis_ast": "ast_callback_nested_assertion",
                    "assertion_subject_path_json": '["result", "totalFocusableElements"]',
                    "assertion_subject_text_ast": "result.totalFocusableElements",
                },
                "accessibility_compliance",
                "accessibility_structure",
            ),
            (
                "expect(typeof data.bestcar).toBe('undefined')",
                {
                    "assertion_matcher": "toBe",
                    "assertion_subject_path_json": '["typeof", "data", "bestcar"]',
                    "assertion_subject_text_ast": "typeof data.bestcar",
                },
                "api_or_data_contract",
                "api_object_or_result_contract",
            ),
        ]
        for raw, feature, expected, expected_path in cases:
            with self.subTest(raw=raw):
                detail = classify_verification_intent_detail("generic_assertion", "expect", raw, feature)
                self.assertEqual(detail["verification_intent"], expected)
                self.assertEqual(detail["verification_intent_codebook_path"], expected_path)

    def test_949pm_tail_style_accessibility_and_event_boundaries(self):
        cases = [
            (
                'expect(classes).includes("hidden-header")',
                {
                    "assertion_matcher": "includes",
                    "assertion_subject_text_ast": "classes",
                    "assertion_subject_path_json": '["classes"]',
                },
                "style_or_visual_state",
                "style_layout_css",
            ),
            (
                "expect(['scroll', 'auto']).toContain(metrics.overflowX)",
                {
                    "assertion_matcher": "toContain",
                    "assertion_subject_text_ast": "metrics.overflowX",
                    "assertion_subject_path_json": '["metrics", "overflowX"]',
                },
                "style_or_visual_state",
                "style_layout_css",
            ),
            (
                "expect(contentBottom).to.be.at.most(footerTop)",
                {
                    "assertion_matcher": "at.most",
                    "assertion_subject_text_ast": "contentBottom",
                    "assertion_subject_path_json": '["contentBottom"]',
                },
                "style_or_visual_state",
                "style_layout_css",
            ),
            (
                "cy.get('@calheader').find('[data-ui5-cal-header-btn-month]').should('have.attr', 'aria-label')",
                {
                    "assertion_matcher": "should",
                    "assertion_semantic_matcher_ast": "have.attr",
                    "assertion_subject_text_ast": "cy.get('@calheader').find('[data-ui5-cal-header-btn-month]')",
                    "assertion_subject_path_json": '["aria-label"]',
                },
                "accessibility_compliance",
                "accessibility_structure",
            ),
            (
                "expect(page.getByRole('button', { name: translations.buttons['no-thanks'] })).toHaveAttribute('aria-pressed', 'true')",
                {
                    "assertion_matcher": "toHaveAttribute",
                    "assertion_subject_kind": "locator",
                    "assertion_subject_path_json": '["aria-pressed"]',
                },
                "accessibility_compliance",
                "accessibility_structure",
            ),
            (
                "cy.get('@onClick').should('have.been.calledTwice')",
                {
                    "assertion_matcher": "should",
                    "assertion_semantic_matcher_ast": "have.been.calledTwice",
                    "assertion_subject_text_ast": "@onClick",
                    "assertion_subject_path_json": '["@onClick"]',
                },
                "interactive_state",
                "interactive_state_or_event_counter",
            ),
            (
                'cy.wrap(effectiveSelectedTabs.length).should("eq", 1, "Only 1 tab is effectively selected")',
                {
                    "assertion_matcher": "should",
                    "assertion_semantic_matcher_ast": "eq",
                    "assertion_subject_semantic_role_ast": "ui_control_state",
                    "assertion_subject_text_ast": "effectiveSelectedTabs.length",
                    "assertion_subject_path_json": '["effectiveSelectedTabs", "length"]',
                },
                "interactive_state",
                "interactive_state_or_event_counter",
            ),
        ]
        for raw, feature, expected, expected_path in cases:
            with self.subTest(raw=raw):
                detail = classify_verification_intent_detail("generic_assertion", "expect", raw, feature)
                self.assertEqual(detail["verification_intent"], expected)
                self.assertEqual(detail["verification_intent_codebook_path"], expected_path)

    def test_unknown_oracle(self):
        self.assertEqual(map_verification_intent("made_up_oracle"), "unspecified")

    def test_all_classify_assertion_categories_have_mapping(self):
        for category in ALL_ASSERTION_ORACLE_CATEGORIES:
            self.assertIn(category, ORACLE_TO_VERIFICATION_INTENT)

    def test_taxonomy_json_matches_python(self):
        path = Path(__file__).resolve().parent / "rq5_verification_intent_taxonomy.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["oracle_to_verification_intent"], ORACLE_TO_VERIFICATION_INTENT)
        self.assertEqual(
            set(data["verification_intent_labels"]),
            set(VERIFICATION_INTENT_LABELS),
        )
        self.assertIn("ast_assertion_semantic_matcher", data["verification_intent_evidence_basis"])
        self.assertIn("ast_assertion_subject_semantic_role", data["verification_intent_evidence_basis"])
        self.assertIn("ast_callback_nested_assertion", data["verification_intent_evidence_basis"])
        self.assertIn("subject_name_heuristic_fallback", data["verification_intent_evidence_basis"])
        self.assertIn("ast_cypress_should_argument", data["assertion_semantic_matcher_basis_ast"])
        self.assertIn("ast_subject_identifier_name_heuristic", data["assertion_subject_basis_ast"])


if __name__ == "__main__":
    unittest.main()
