"""Workflow-integrated LLM semantic correction for hard RQ labels.

The deterministic extractor remains primary. This module only handles selected
high-risk rows and always records deterministic, LLM, final, and basis fields.
"""

from __future__ import annotations

import json
import http.client
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request
import concurrent.futures
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO

from llm_semantic_cache import LlmSemanticCache, build_input_hash


LLM_SEMANTIC_PROMPT_VERSION = "rq-semantic-v13-determinate-labels"

ALLOWED_LABELS: Dict[str, List[str]] = {
    "rq2": [
        "domain_plausible_input",
        "placeholder_or_dummy_input",
        "validation_or_edge_case_input",
    ],
    "rq3_workflow": [
        "inline_direct",
        "helper_mediated",
        "page_object_centric",
        "framework_extension_centric",
        "hook_or_fixture_centric",
        "structured_step_centric",
        "layered",
    ],
    "rq5c": [
        "element_presence",
        "content_correctness",
        "value_or_attribute_correctness",
        "interactive_state",
        "style_or_visual_state",
        "navigation_outcome",
        "network_contract",
        "api_or_data_contract",
        "visual_regression",
        "accessibility_compliance",
        "collection_size",
    ],
}

ABANDONED_LABEL_NORMALIZATION: Dict[str, Dict[str, str]] = {
    "rq2": {
        "technical_or_control_input": "not_observable",
        "technical_or_configuration_or_control_input": "not_observable",
        "indeterminate_or_insufficient_evidence": "not_observable",
    },
    "rq3_workflow": {
        "page_object_centric_unresolved": "",
        "bdd_step_centric": "structured_step_centric",
        "unresolved_thin_wrapper": "",
        "mixed_or_unclear": "",
    },
    "rq5c": {
        "unspecified": "",
    },
}

RQ2_DETERMINATE_PAPER_LABELS = frozenset(
    {
        "domain_plausible_input",
        "placeholder_or_dummy_input",
        "validation_or_edge_case_input",
    }
)

TAXONOMY_DEFINITIONS: Dict[str, Dict[str, str]] = {
    "rq2": {
        "domain_plausible_input": "A realistic user/domain value for a visible UI consumer; variables, member paths, and env values can be domain-plausible when target or member semantics are meaningful.",
        "placeholder_or_dummy_input": "A clear dummy, lorem, sample, hello/filler, generic test-room, or intentionally fake value. Do not use solely because an identifier contains test/mock/input/value.",
        "validation_or_edge_case_input": "A malformed, boundary, invalid, empty, URL/resource-construction, or edge-case input.",
        "abstain": "Use abstain for keyboard/control tokens, technical configuration values, or insufficient evidence instead of assigning a determinate input-plausibility label.",
    },
    "rq3_workflow": {
        "inline_direct": "Most workflow actions are directly in the test body.",
        "helper_mediated": "Domain helper functions dominate workflow actions.",
        "page_object_centric": "Page-object methods or models dominate workflow actions.",
        "framework_extension_centric": "Custom framework commands/extensions dominate workflow actions.",
        "hook_or_fixture_centric": "Hook or fixture setup dominates workflow actions.",
        "structured_step_centric": "Structured step blocks dominate the workflow.",
        "layered": "Multiple abstraction layers materially contribute.",
        "abstain": "Use abstain when workflow evidence is missing or insufficient instead of assigning an uncertainty category.",
    },
    "rq5c": {
        "element_presence": "Element existence, visibility, attachment, or viewport presence.",
        "content_correctness": "Textual content, title, subject, message, or notification body correctness.",
        "value_or_attribute_correctness": "Scalar value, field, property, or attribute correctness.",
        "interactive_state": "Enabled/disabled/checked/focused/selected state, event counters, or UI callback state.",
        "style_or_visual_state": "CSS, class, layout, color, size, opacity, or style-property correctness.",
        "navigation_outcome": "URL, path, location, route, or navigation target correctness.",
        "network_contract": "HTTP request/response/status/header/body/interception contract. Bare status variables are not network unless HTTP provenance is visible.",
        "api_or_data_contract": "Object shape, type, schema, structured payload, result.error, callback argument, or API/data contract; not every scalar object property.",
        "visual_regression": "Screenshot or image snapshot regression.",
        "accessibility_compliance": "ARIA snapshot, accessible name, role, or semantic accessibility structure.",
        "collection_size": "True DOM/list/array cardinality assertions.",
        "abstain": "Use abstain when no reliable verification-intent category can be assigned.",
    },
}

FEW_SHOT_EXAMPLES: Dict[str, List[Dict[str, str]]] = {
    "rq2": [
        {
            "evidence": "agHelper.GetNClick(table._filterInputValue).type('i') or cy.get(publish.inputValue).type('bind')",
            "label": "domain_plausible_input",
            "rationale": "Meaningful filter/input-value helper targets provide enough UI context for plausible domain text.",
        },
        {
            "evidence": "page.keyboard.type(html`<h1>Foo</h1><p>Hello world</p>`)",
            "label": "placeholder_or_dummy_input",
            "rationale": "Targetless HTML/template keyboard filler with Foo/Hello sample content is filler data.",
        },
        {
            "evidence": "page.setInputFiles(fileInput, path.resolve(dirname, 'duck.glb'))",
            "label": "domain_plausible_input",
            "rationale": "Ordinary upload API values and file path variables are plausible file inputs.",
        },
        {
            "evidence": "cy.get('#input_address').type('testaddress') with address target context",
            "label": "domain_plausible_input",
            "rationale": "The visible address target gives domain semantics even though the literal contains test.",
        },
        {
            "evidence": "page.getByPlaceholder(/search/i).fill(faker.string.alphanumeric(10))",
            "label": "domain_plausible_input",
            "rationale": "Search fields often accept arbitrary generated search terms; visible target semantics make the generated value plausible.",
        },
        {
            "evidence": "setInputFiles([path.resolve(dirname, './image.png'), path.resolve(dirname, './2mb.jpg'), path.resolve(dirname, './small.png')])",
            "label": "domain_plausible_input",
            "rationale": "A normal file-upload path list is a plausible upload input; comments alone do not make it an edge case.",
        },
        {
            "evidence": "cy.focused().type(newAccountData['tax_id'])",
            "label": "domain_plausible_input",
            "rationale": "A meaningful member path such as tax_id can supply domain semantics even when the focused input target is implicit.",
        },
        {
            "evidence": "page.keyboard.type('test') with no focused/target context",
            "label": "placeholder_or_dummy_input",
            "rationale": "A targetless keyboard type of a generic test literal is filler/dummy evidence.",
        },
        {
            "evidence": "cy.get('.tiptap').type('`$foobar`')",
            "label": "domain_plausible_input",
            "rationale": "A meaningful editor target can make markdown/code-like text plausible domain content.",
        },
        {
            "evidence": "cy.findByTestId('TeamSettings.SiteNameinput').type(siteName) or cy.get('#channel_settings_header_textbox').type(text)",
            "label": "domain_plausible_input",
            "rationale": "Some settings panels contain user-facing site/channel text fields; site name and channel header text are domain content, not endpoint/config control values.",
        },
        {
            "evidence": "cy.get(searchInput).type(settingsObject.usernameTooShort)",
            "label": "validation_or_edge_case_input",
            "rationale": "Explicit invalid/boundary member names such as tooShort are validation/edge-case values.",
        },
    ],
    "rq3_workflow": [
        {
            "evidence": "dominant_workflow_source=helper_mediated with helper score far above page object score",
            "label": "helper_mediated",
            "rationale": "Dominant expanded helper evidence should determine the test-level archetype.",
        },
        {
            "evidence": "direct test-body actions dominate and no helper/page-object layer contributes material evidence",
            "label": "inline_direct",
            "rationale": "Workflow is expressed in the test body.",
        },
        {
            "evidence": "cypress_command_ui/custom_command_calls are the strongest source even with minor helper/test-body evidence",
            "label": "framework_extension_centric",
            "rationale": "Custom framework command dominance should not be diluted into layered.",
        },
        {
            "evidence": "test_body_ui is strongest but helper, hook, and custom-command layers also materially contribute",
            "label": "layered",
            "rationale": "Material secondary layers make the workflow layered rather than purely inline.",
        },
    ],
    "rq5c": [
        {
            "evidence": "expect(status).toBe('healthy')",
            "label": "value_or_attribute_correctness",
            "rationale": "Bare status is a scalar value unless HTTP/request/response provenance is visible.",
        },
        {
            "evidence": "expect(response.status).toBe(200)",
            "label": "network_contract",
            "rationale": "The subject is an HTTP response status.",
        },
        {
            "evidence": "expect(result.error).toBeUndefined()",
            "label": "api_or_data_contract",
            "rationale": "Result error fields are structured result/data contract checks.",
        },
        {
            "evidence": "expect(computedTitleField).toHaveValue('Test Title')",
            "label": "value_or_attribute_correctness",
            "rationale": "Value matchers on fields are value/attribute correctness checks.",
        },
        {
            "evidence": "expect(typeof violation.selector).toBe('string')",
            "label": "api_or_data_contract",
            "rationale": "Type checks on structured violation payload fields verify object/data contract.",
        },
        {
            "evidence": "toHaveAccessibleName('Save')",
            "label": "accessibility_compliance",
            "rationale": "Accessible-name assertions are accessibility checks, not plain content checks.",
        },
        {
            "evidence": "cy.url().should('contain', '/dashboard')",
            "label": "navigation_outcome",
            "rationale": "URL/path assertions verify navigation outcome.",
        },
        {
            "evidence": "expect(await getCssClasses(node)).toBe('bullet')",
            "label": "style_or_visual_state",
            "rationale": "CSS class/style helper evidence verifies visual state.",
        },
        {
            "evidence": "expect(addon).not.toBeNull() where subject is an element handle or extracted element",
            "label": "element_presence",
            "rationale": "Null checks on element-like subjects verify presence.",
        },
        {
            "evidence": "expect(stub).to.have.been.callCount(4)",
            "label": "interactive_state",
            "rationale": "Spy/stub call counts verify callback/event interaction state, not collection cardinality.",
        },
        {
            "evidence": "expect(typeof limits.singleChannelGuestCount).toBe('number')",
            "label": "api_or_data_contract",
            "rationale": "A count-like property name is still an API/object contract unless the assertion counts a DOM/list/array collection.",
        },
        {
            "evidence": "expect(result.totalFocusableElements).toBeLessThanOrEqual(maxFocusableElements)",
            "label": "accessibility_compliance",
            "rationale": "Focusable-element counts are accessibility-surface semantics, not generic API object contracts.",
        },
        {
            "evidence": "expect(requestPayload['public']).to.equal(null)",
            "label": "api_or_data_contract",
            "rationale": "A requestPayload object field equality is a structured payload/data contract unless HTTP status/header/body metadata is the asserted subject.",
        },
        {
            "evidence": "expect(['degraded', 'critical']).toContain(status)",
            "label": "value_or_attribute_correctness",
            "rationale": "Enum membership for a scalar status variable is value/attribute correctness, not text content.",
        },
        {
            "evidence": "expect(error.reason).to.eq(createLinodeErrorMsg)",
            "label": "content_correctness",
            "rationale": "Reason/message fields compared to message text are user-facing content checks.",
        },
        {
            "evidence": "expect(matchedRequests.length).toBeLessThanOrEqual(allowedNumberOfRequests)",
            "label": "network_contract",
            "rationale": "The cardinality being checked is network request behavior.",
        },
        {
            "evidence": "cy.get('label').should('be.visible').and('contain', element.display_name)",
            "label": "content_correctness",
            "rationale": "For a chained assertion row, the current contain matcher checks label text even if an earlier matcher checked visibility.",
        },
        {
            "evidence": "cy.findByText(text).should('be.visible').and('have.attr', 'href').and('include', link)",
            "label": "navigation_outcome",
            "rationale": "href/link attribute assertions verify navigation target, not element visibility or generic text.",
        },
        {
            "evidence": "expect(numberValue).toEqual(10) or expect(new Date(timestamp)).to.deep.equal(...)",
            "label": "value_or_attribute_correctness",
            "rationale": "Numeric/date scalar equality is value correctness unless the subject is a true collection cardinality.",
        },
        {
            "evidence": "expect(clickCount).toBe(1)",
            "label": "interactive_state",
            "rationale": "Event/click counters verify interaction state.",
        },
    ],
}

CLASSIFICATION_GUIDELINES: Dict[str, List[str]] = {
    "rq2": [
        "Classify the input event/value itself using both value and consumer context.",
        "Abstain when both value and target/member context lack useful semantics.",
        "Do not promote a bare visible literal to domain_plausible_input without useful target/member/editor context. Weak targetless literals such as abc, log, test Mandatory, or a bare email should abstain.",
        "Visible text-entry literals are domain_plausible_input when the target/member/editor context gives meaningful semantics, unless they are explicit filler/dummy, invalid/boundary/empty, endpoint/config/path construction, or keyboard/control input.",
        "Opaque generated/faker values are not non-domain merely because they are generated. With a meaningful visible field such as search/name/address/amount they may be domain_plausible_input; with opaque target context, abstain.",
        "Meaningful member/identifier names such as zone.domain, mockFormFields.useCase, monitorUrl, entityTag, slug, prefix, query, username, and notes are domain-plausible when typed into UI text inputs even if the concrete value is opaque.",
        "Use domain_plausible_input when the visible literal, member path, or target/value combination is specific enough for a reviewer to see realistic user-domain data, including option-like values such as colors in selectors.",
        "Use placeholder_or_dummy_input only for explicit filler/dummy/sample/lorem/hello/test-room/editor-foobar values.",
        "Use validation_or_edge_case_input for invalid/boundary/malformed values and explicit preservation/boundary probes. For endpoint/resource/config UI fields, abstain unless the value itself is explicitly malformed or boundary-oriented. Ordinary upload API paths are domain_plausible_input; exceed-limit/invalid upload probes are validation_or_edge_case_input.",
        "For endpoint/resource/datasource/base URL/route/port/method/frame/column configuration fields, abstain even when the target is visible and the value is a plausible-looking URL or identifier.",
        "Meaningful helper/member targets such as filterInput, inputValue, replyTextBox, promptInput, toneSelect, serialNumberInput, modelNumberInput, dosage form, and editor fields can make short literals or member paths domain_plausible_input.",
        "For explicit text-editing/control-token sequences in input calls, single page.keyboard.press key presses, pure realPress/key navigation with no typed value, and config/control fields, abstain instead of assigning a determinate label.",
        "For second-pass RQ2 adjudication triggers, assign a determinate label only when receiver/member names, target context, upload/editor/focus context, and value shape provide concrete evidence.",
        "For single page.keyboard.press key presses, abstain unless nearby focus/editor/target context proves the key is semantic text entry.",
    ],
    "rq3_workflow": [
        "Classify from workflow evidence scores and dominant_workflow_source. The deterministic label is only a candidate and may be wrong.",
        "helper_ui/helper_calls dominance maps to helper_mediated unless unresolved helper evidence is the actual dominant signal.",
        "cypress_command/custom_command dominance maps to framework_extension_centric.",
        "hook_ui/fixture dominance maps to hook_or_fixture_centric.",
        "test_body_ui dominance maps to inline_direct when helper/page-object/custom/hook evidence is not materially comparable.",
        "Use layered when two or more abstraction layers materially contribute and no single source clearly dominates.",
        "Abstain when workflow evidence is missing or genuinely insufficient; use layered only when two or more concrete abstraction layers materially contribute.",
    ],
    "rq5c": [
        "Classify by the current assertion subject plus the current matcher. The deterministic label is only a candidate and may be wrong.",
        "When the raw chain contains several assertions, use assertion_semantic_matcher_ast/assertion_matcher for this row; do not let an earlier be.visible/exist token override a current have.css/be.enabled/have.attr assertion.",
        "exist, not.exist, be.visible, toBeVisible, not.toBeNull on element-like subjects, attachment, and viewport checks map to element_presence.",
        "cy.url, location, pathname, href, currentUrl, route/path assertions map to navigation_outcome.",
        "HTTP request/response/status/header/body/interception assertions map to network_contract. Bare status is scalar unless HTTP provenance exists.",
        "callCount/calledOnce/stub/spy/event counters, component lifecycle counters, enabled/disabled/checked/focused, and UI event payload checks map to interactive_state.",
        "CSS/class/style/layout/color/font/opacity/padding/width/height and getCssClasses/getElementStyle checks map to style_or_visual_state.",
        "toHaveValue/have.value/toHaveAttribute/have.attr/value/property scalar checks map to value_or_attribute_correctness unless a stronger network, navigation, style, or interactive role applies.",
        "typeof/object shape/type/schema/result.error/API result fields map to api_or_data_contract. Count-like property names are not collection_size unless the assertion is true array/list/DOM cardinality.",
        "LLM correction must not abstain on generic truthiness/equality when deterministic scalar/value is the least-wrong codebook label.",
        "Visual regression requires screenshot or snapshot assertion APIs, not button text containing Snapshot.",
        "Accessible name/ARIA/accessibility snapshot/focusable-surface assertions map to accessibility_compliance.",
    ],
}

RQ_COLUMNS = {
    "rq2": {
        "label": "input_plausibility",
        "deterministic": "input_plausibility_deterministic",
        "llm": "input_plausibility_llm",
        "final": "input_plausibility_final",
        "basis": "input_plausibility_final_basis",
        "trigger": "input_plausibility_llm_trigger_reason",
    },
    "rq3_workflow": {
        "label": "workflow_archetype",
        "deterministic": "workflow_archetype_deterministic",
        "llm": "workflow_archetype_llm",
        "final": "workflow_archetype_final",
        "basis": "workflow_archetype_final_basis",
        "trigger": "workflow_archetype_llm_trigger_reason",
    },
    "rq5c": {
        "label": "verification_intent",
        "deterministic": "verification_intent_deterministic",
        "llm": "verification_intent_llm",
        "final": "verification_intent_final",
        "basis": "verification_intent_final_basis",
        "trigger": "verification_intent_llm_trigger_reason",
    },
}

GENERATED_EVIDENCE_FIELDS = {"llm_model", "llm_prompt_version", "llm_input_hash"}
for _cols in RQ_COLUMNS.values():
    GENERATED_EVIDENCE_FIELDS.update(
        {
            _cols["deterministic"],
            _cols["llm"],
            f"{_cols['llm']}_confidence",
            f"{_cols['llm']}_rationale",
            f"{_cols['llm']}_codebook_step",
            _cols["final"],
            _cols["basis"],
            _cols["trigger"],
        }
    )
GENERATED_EVIDENCE_FIELDS.update(
    {
        "input_plausibility_pre_adjudication_final",
        "input_plausibility_adjudication_label",
        "input_plausibility_adjudication_confidence",
        "input_plausibility_adjudication_trigger_reason",
        "input_plausibility_adjudication_codebook_step",
        "input_plausibility_adjudication_rationale",
    }
)


@dataclass
class LlmSemanticDecision:
    label: str
    confidence: str
    abstain: bool
    evidence_fields: List[str]
    short_rationale: str
    codebook_step: str = ""


def load_openai_api_key_from_env_file(env_file: Optional[Path]) -> str:
    """Load OPENAI_API_KEY from process env or an untracked .env.local file.

    The process environment wins. The key is never logged by this helper.
    """
    current = os.environ.get("OPENAI_API_KEY", "").strip()
    if current:
        return current
    if not env_file:
        return ""
    path = Path(env_file)
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        if name.strip() != "OPENAI_API_KEY":
            continue
        key = value.strip().strip("'\"")
        if key:
            os.environ["OPENAI_API_KEY"] = key
            return key
    return ""


def _lower_join(*values: Any) -> str:
    return " ".join(str(v or "") for v in values).lower()


def _normalize_abandoned_label(rq: str, label: Any) -> str:
    normalized = str(label or "").strip()
    return ABANDONED_LABEL_NORMALIZATION.get(rq, {}).get(normalized, normalized)


def _paper_label_for_rq2_final(label: Any) -> str:
    normalized = _normalize_abandoned_label("rq2", label)
    return normalized if normalized in RQ2_DETERMINATE_PAPER_LABELS else ""


def _normalize_structured_fields_for_llm(rq: str, row: Dict[str, Any]) -> Dict[str, Any]:
    cols = RQ_COLUMNS[rq]
    out = dict(row)
    if cols["label"] in out:
        out[cols["label"]] = _normalize_abandoned_label(rq, out.get(cols["label"]))
    if rq == "rq2":
        out["input_plausibility_paper_label"] = _paper_label_for_rq2_final(
            out.get("input_plausibility_final") or out.get("input_plausibility")
        )
    return out


def _workflow_expected_from_dominant_source(row: Dict[str, Any]) -> str:
    source = str(row.get("dominant_workflow_source") or "").strip().lower()
    source_map = {
        "helper_mediated": "helper_mediated",
        "domain_helper": "helper_mediated",
        "helper_calls": "helper_mediated",
        "page_object": "page_object_centric",
        "page_object_centric": "page_object_centric",
        "page_object_calls": "page_object_centric",
        "framework_extension": "framework_extension_centric",
        "cypress_custom_command": "framework_extension_centric",
        "custom_command_calls": "framework_extension_centric",
        "hook": "hook_or_fixture_centric",
        "fixture": "hook_or_fixture_centric",
        "test_body": "inline_direct",
        "inline": "inline_direct",
        "bdd_step": "structured_step_centric",
        "structured_step": "structured_step_centric",
        "helper_ui": "helper_mediated",
        "page_object_ui": "page_object_centric",
        "cypress_command_ui": "framework_extension_centric",
        "hook_ui": "hook_or_fixture_centric",
        "test_body_ui": "inline_direct",
    }
    if source in source_map:
        return source_map[source]
    try:
        scores = json.loads(str(row.get("workflow_evidence_score_json") or "{}"))
    except json.JSONDecodeError:
        scores = {}
    if not isinstance(scores, dict) or not scores:
        return ""
    labels = {
        "helper_mediated",
        "page_object_centric",
        "framework_extension_centric",
        "hook_or_fixture_centric",
        "inline_direct",
        "structured_step_centric",
    }
    numeric_scores: Dict[str, float] = {}
    for key, value in scores.items():
        if not isinstance(value, (int, float)):
            continue
        raw_key = str(key)
        mapped_key = source_map.get(raw_key, raw_key)
        if mapped_key not in labels:
            continue
        numeric_scores[mapped_key] = numeric_scores.get(mapped_key, 0.0) + float(value)
    if not numeric_scores:
        return ""
    top = max(numeric_scores, key=numeric_scores.get)
    runner_up = max((v for k, v in numeric_scores.items() if k != top), default=0.0)
    if numeric_scores[top] >= max(2.0, runner_up * 1.5):
        return top
    return ""


def should_trigger_llm_correction(rq: str, row: Dict[str, Any]) -> str:
    if rq == "rq2":
        target = str(row.get("input_target_role_ast") or "").strip().lower()
        source = str(row.get("input_source_class") or "").strip().lower()
        expr = str(row.get("input_value_expression_kind_ast") or "").strip().lower()
        label = str(row.get("input_plausibility") or "").strip()
        confidence = str(row.get("input_plausibility_confidence") or "").strip().lower()
        value = _lower_join(row.get("value_summary"), row.get("raw_code"))
        field = _lower_join(
            row.get("field_context"),
            row.get("input_target_context_ast"),
            row.get("input_consumer_context_ast"),
        )
        channel = str(row.get("input_channel") or "").strip().lower()
        upload_consumer = str(row.get("input_upload_consumer_ast") or "").strip().lower()
        weak_literals = {"", "abc", "asdf", "log", "hello", "test", "test mandatory", "sample", "dummy"}
        pure_control_value = _is_pure_cypress_control_value(row.get("value_summary"))
        has_control_token = _has_cypress_control_token(value)
        if upload_consumer or source == "file_upload_input":
            if any(k in value for k in ("path.resolve", "path.join", "dirname", "filepath", "imagepath", "validimagepath", ".glb", ".png", ".jpg", ".mp4")):
                return "rq2_path_or_file_construction_edge_conflict"
        if (
            any(k in value for k in ("realpress", "keyboard.type", "keyboard.press"))
            or (channel in {"keyboard_entry", "keyboard_input"} and not pure_control_value)
        ):
            return "rq2_keyboard_control_observability_boundary"
        if source == "generated_input" and any(k in value for k in ("faker.", "random", "alphanumeric", "uuid")):
            if target not in {"", "unknown"} or any(k in field for k in ("search", "message", "name", "address", "title", "label")):
                return "rq2_generated_value_visible_domain_context"
        stripped_value = str(row.get("value_summary") or "").strip().strip("'\"").lower()
        if stripped_value in {"hello", "testaddress", "testcanceladdress"}:
            return "rq2_literal_domain_dummy_observability_boundary"
        if target in {"", "unknown"} and (expr in {"member_expression", "identifier"} or source in {"generated_input", "environment_input", "variable_input"}):
            if label in {
                "not_observable",
                "unclear",
                "technical_or_control_input",
                "placeholder_or_dummy_input",
                "validation_or_edge_case_input",
            } or confidence in {"low", ""}:
                return "rq2_unknown_target_opaque_or_member_value"
        if target in {"", "unknown"} and label in {
            "domain_plausible_input",
            "placeholder_or_dummy_input",
            "technical_or_control_input",
            "validation_or_edge_case_input",
            "unclear",
        }:
            if label == "technical_or_control_input" and confidence == "high" and pure_control_value:
                return ""
            if confidence in {"high", "medium", "low", ""} and (
                stripped_value in weak_literals
                or label in {
                    "placeholder_or_dummy_input",
                    "validation_or_edge_case_input",
                }
            ):
                return "rq2_weak_literal_unknown_target_not_observable_candidate"
        if source == "file_upload_input" and label == "validation_or_edge_case_input":
            return "rq2_upload_edge_conflict"
        if label == "placeholder_or_dummy_input" and any(k in field for k in ("name", "title", "label", "search", "task")):
            return "rq2_dummy_word_domain_context_conflict"
        if has_control_token and "{" in value and "}" in value and ".type" in value and not pure_control_value:
            return "rq2_keyboard_token_chain_ambiguity"
        risky_label = label in {
            "not_observable",
            "unclear",
            "placeholder_or_dummy_input",
            "validation_or_edge_case_input",
            "technical_or_control_input",
        }
        has_semantic_context = (
            target not in {"", "unknown"}
            or any(k in field for k in ("search", "user", "name", "title", "label", "message", "address", "email", "phone", "password"))
            or expr in {"member_expression", "identifier"}
            or source in {"generated_input", "environment_input", "variable_input", "api_seed_input"}
        )
        if any(k in value for k in (".type(", ".fill(")) and risky_label and has_semantic_context:
            return "rq2_visible_text_input_semantic_boundary"
        if any(k in value for k in (".type(", ".fill(")) and risky_label:
            if any(k in value for k in ("'", '"')) and not pure_control_value:
                return "rq2_visible_literal_unknown_target_boundary"
        return ""
    if rq == "rq3_workflow":
        label = str(row.get("workflow_archetype") or "").strip()
        dominant_expected = _workflow_expected_from_dominant_source(row)
        if dominant_expected and label and dominant_expected != label:
            return "rq3_workflow_dominant_evidence_label_conflict"
        if label in {"layered", "mixed_or_unclear", "unresolved_thin_wrapper"}:
            return "rq3_workflow_ambiguous_archetype"
        if not str(row.get("dominant_workflow_source") or "").strip() and label not in {"inline_direct", ""}:
            return "rq3_workflow_missing_dominant_evidence"
        return ""
    if rq == "rq5c":
        basis = str(row.get("verification_intent_evidence_basis") or "").strip().lower()
        role = str(row.get("assertion_subject_semantic_role_ast") or "").strip()
        raw = str(row.get("raw_code") or "").lower()
        matcher = str(row.get("matcher") or row.get("assertion_matcher") or "").lower()
        text = _lower_join(raw, matcher, row.get("assertion_subject_path_ast"), row.get("assertion_subject_semantic_role_ast"))
        current_matcher = _lower_join(
            row.get("assertion_semantic_matcher_ast"),
            row.get("matcher"),
            row.get("assertion_matcher"),
        ).replace(" ", "")
        label = str(row.get("verification_intent") or "")
        if any(k in text for k in ("requestpayload", "xhr.request.body", "request.body", "response.body", "interception")):
            if label != "network_contract":
                return "rq5c_network_payload_semantic_conflict"
        if any(k in current_matcher for k in ("have.css", "havecss", "tohavecss", "css", "have.class", "haveclass", "tohaveclass")):
            if label != "style_or_visual_state":
                return "rq5c_style_current_matcher_semantic_conflict"
        if any(k in current_matcher for k in ("be.enabled", "beenabled", "tobeenabled", "be.disabled", "bedisabled", "tobedisabled")):
            if label != "interactive_state":
                return "rq5c_interactive_current_matcher_semantic_conflict"
        if any(k in text for k in ("tohaveaccessiblename", "tomatchariasnapshot", "accessible name", "accessible description")):
            if label != "accessibility_compliance":
                return "rq5c_accessibility_matcher_semantic_conflict"
        if any(k in text for k in ("cy.url", "cy.location", "currenturl", "location.pathname", "loc.href", "window.location")):
            if label != "navigation_outcome":
                return "rq5c_navigation_subject_semantic_conflict"
        if any(k in text for k in ("be.visible", "not.exist", "should(\"exist", "should('exist", "tobevisible", "tobenull", "not.tobenull", "not tobenull")):
            if label != "element_presence":
                return "rq5c_presence_matcher_semantic_conflict"
        if ".count" in text or "getnodes().count" in text:
            if label != "collection_size":
                return "rq5c_collection_count_semantic_conflict"
        if any(k in text for k in ("tohavevalue", "have.value", "value correctness")):
            if label != "value_or_attribute_correctness":
                return "rq5c_value_matcher_semantic_conflict"
        if any(k in text for k in ("getcssclasses", "classlist", "classname", "fill-opacity", "padding", "css", "style", "layout")):
            if label != "style_or_visual_state":
                return "rq5c_style_subject_semantic_conflict"
        if any(k in text for k in ("componentdidload", "componentdidrender", "event counter", "callcount", "calledonce", "changespy")):
            if label not in {"interactive_state", "api_or_data_contract"}:
                return "rq5c_interactive_event_semantic_conflict"
            if label == "network_contract":
                return "rq5c_interactive_event_semantic_conflict"
        if basis.startswith("lexical") or not role:
            return "rq5c_lexical_or_missing_subject_role"
        if role in {"scalar_property", "api_object_contract", "text_content_payload"} and any(
            k in raw for k in (".exists", "cy.location", "loc.href", "isdisabled", "getelementstyle")
        ):
            return "rq5c_conflicting_subject_matcher_role"
        if "callback" in basis or "=> " in raw:
            return "rq5c_callback_subject_ambiguity"
        return ""
    return ""


def should_trigger_rq2_indeterminate_adjudication(row: Dict[str, Any]) -> str:
    """Return a second-pass trigger for broad RQ2 semantic-risk families.

    This is intentionally category-based, not tied to reviewed row IDs. The
    adjudicator is only for labels that are likely too conservative after the
    first deterministic/LLM pass, especially paper-facing indeterminate rows.
    """
    final_label = str(row.get("input_plausibility_final") or row.get("input_plausibility") or "").strip()
    paper_label = str(row.get("input_plausibility_paper_label") or "").strip()
    if paper_label not in RQ2_DETERMINATE_PAPER_LABELS:
        paper_label = ""
    if not paper_label:
        paper_label = _paper_label_for_rq2_final(final_label)
    source = str(row.get("input_source_class") or "").strip().lower()
    channel = str(row.get("input_channel") or "").strip().lower()
    visibility = str(row.get("value_visibility") or "").strip().lower()
    expr = str(row.get("input_value_expression_kind_ast") or "").strip().lower()
    target_role = str(row.get("input_target_role_ast") or "").strip().lower()
    raw = _lower_join(row.get("raw_code"), row.get("value_summary"), row.get("name"))
    value_text = str(row.get("value_summary") or "").strip()
    context = _lower_join(
        row.get("field_context"),
        row.get("input_target_context_ast"),
        row.get("input_consumer_context_ast"),
        row.get("input_target_context_normalized_ast"),
        row.get("field_path"),
        row.get("external_file_path"),
    )

    if final_label == "validation_or_edge_case_input" and (
        any(token in raw for token in ("port", "8080", "endpoint", "resourceurl", "datasource", "domain", "bucket", "remote-file"))
        or any(token in context for token in ("port", "endpoint", "resource", "datasource", "config", "remote file"))
    ):
        return "rq2_validation_config_or_domain_boundary_adjudication"

    if paper_label:
        return ""

    if not raw.strip() and not context.strip():
        return ""

    if "realpress" in raw and ".type(" not in raw:
        return ""

    if "page.keyboard.press" in raw or "keyboard.press" in raw:
        if any(token in context for token in ("editor", "input", "textbox", "field", "search", "name", "title")):
            return "rq2_indeterminate_keyboard_focused_text_adjudication"
        return ""

    if (
        (
            source in {"variable_input", "environment_input", "generated_input", "api_seed_input", "file_upload_input"}
            and (value_text or context.strip() or channel in {"ui_text_entry", "ui_selection", "ui_file_upload"})
        )
        or expr in {"identifier", "member_expression", "call_expression"}
        or "." in value_text
    ):
        if target_role not in {"technical_control_field"}:
            return "rq2_indeterminate_opaque_member_or_receiver_adjudication"

    if (
        visibility in {"visible", "partially_visible"}
        and channel in {"ui_text_entry", "ui_selection", "ui_file_upload", "keyboard_entry", "keyboard_input"}
    ):
        return "rq2_indeterminate_visible_or_contextual_value_adjudication"

    if any(token in raw for token in ("focused().type", "cy.focused", "keyboard.type", ".type(", ".fill(", ".setinputfiles", ".selectfile")):
        return "rq2_indeterminate_visible_or_contextual_value_adjudication"

    if any(token in raw for token in ("path.resolve", "path.join", "validimagepath", ".png", ".jpg", ".jpeg", ".gif", ".mp4", ".glb")):
        return "rq2_indeterminate_upload_or_file_value_adjudication"

    return ""


def build_llm_semantic_request(
    *,
    rq: str,
    row: Dict[str, Any],
    trigger_reason: str,
) -> Dict[str, Any]:
    cols = RQ_COLUMNS[rq]
    llm_row = _normalize_structured_fields_for_llm(rq, row)
    excluded_prefixes = ("manual_",)
    excluded_exact = {
        "sample_origin",
        "review_reason",
        "needs_review",
    }
    structured_fields = {
        key: llm_row.get(key, "")
        for key in sorted(llm_row)
        if key not in {"OPENAI_API_KEY"}
        and "api_key" not in key.lower()
        and not key.lower().startswith(excluded_prefixes)
        and key.lower() not in excluded_exact
        and not key.lower().endswith("_should_be")
        and key not in GENERATED_EVIDENCE_FIELDS
    }
    snippet = str(row.get("test_body_context_snippet") or row.get("event_snippet") or row.get("raw_code") or "")[:1500]
    return {
        "prompt_version": LLM_SEMANTIC_PROMPT_VERSION,
        "task": "classify one row according to the provided RQ taxonomy",
        "rq": rq,
        "allowed_labels": ALLOWED_LABELS[rq],
        "deterministic_label": _normalize_abandoned_label(rq, row.get(cols["label"], "")),
        "deterministic_evidence_basis": row.get("input_evidence_basis")
        or row.get("workflow_archetype_basis")
        or row.get("verification_intent_evidence_basis")
        or "",
        "trigger_reason": trigger_reason,
        "structured_fields": structured_fields,
        "source_snippet": snippet,
        "required_output_schema": {
            "label": "one allowed label or abstain",
            "confidence": "high|medium|low",
            "abstain": True,
            "evidence_fields": [],
            "short_rationale": "",
            "codebook_step": "decision-tree step used",
        },
    }


def build_llm_instruction_block(rq: str) -> Dict[str, Any]:
    return {
        "prompt_version": LLM_SEMANTIC_PROMPT_VERSION,
        "task": "classify empirical software-engineering extraction rows",
        "rq": rq,
        "allowed_labels": ALLOWED_LABELS[rq],
        "taxonomy_definitions": TAXONOMY_DEFINITIONS[rq],
        "classification_guidelines": CLASSIFICATION_GUIDELINES.get(rq, []),
        "few_shot_examples": FEW_SHOT_EXAMPLES.get(rq, []),
        "required_output_contract": {
            "label": "one allowed label or abstain",
            "confidence": "high|medium|low",
            "abstain": True,
            "evidence_fields": [],
            "short_rationale": "",
            "codebook_step": "short decision-tree/codebook branch name",
        },
    }


def build_llm_semantic_batch_request(
    *,
    rq: str,
    items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build a compact same-RQ batch prompt from per-row requests.

    Each item must contain a stable row_id and a request returned by
    build_llm_semantic_request. Taxonomy, guidelines, and few-shot examples are
    carried once at the batch level so API overhead does not scale linearly with
    row count.
    """
    batch_items: List[Dict[str, Any]] = []
    for item in items:
        row_id = str(item.get("row_id") or "")
        request = item.get("request") or {}
        batch_items.append({
            "row_id": row_id,
            "deterministic_label": request.get("deterministic_label", ""),
            "deterministic_evidence_basis": request.get("deterministic_evidence_basis", ""),
            "trigger_reason": request.get("trigger_reason", ""),
            "structured_fields": request.get("structured_fields", {}),
            "source_snippet": request.get("source_snippet", ""),
        })
    return {
        "prompt_version": LLM_SEMANTIC_PROMPT_VERSION,
        "task": "classify multiple rows according to the provided RQ taxonomy",
        "rq": rq,
        "allowed_labels": ALLOWED_LABELS[rq],
        "instruction_block": build_llm_instruction_block(rq),
        "items": batch_items,
        "required_output_schema": {
            "items": [
                {
                    "row_id": "must match one input row_id",
                    "label": "one allowed label or abstain",
                    "confidence": "high|medium|low",
                    "abstain": True,
                    "evidence_fields": [],
                    "short_rationale": "",
                    "codebook_step": "decision-tree step used",
                }
            ]
        },
    }


def _decision_from_payload(payload: Dict[str, Any], allowed: List[str]) -> LlmSemanticDecision:
    label = str(payload.get("label") or "").strip()
    confidence = str(payload.get("confidence") or "low").strip().lower()
    abstain = bool(payload.get("abstain")) or label not in allowed
    evidence = payload.get("evidence_fields")
    if not isinstance(evidence, list):
        evidence = []
    return LlmSemanticDecision(
        label=label if label in allowed else "",
        confidence=confidence if confidence in {"high", "medium", "low"} else "low",
        abstain=abstain,
        evidence_fields=[str(x) for x in evidence],
        short_rationale=str(payload.get("short_rationale") or "")[:500],
        codebook_step=str(payload.get("codebook_step") or "")[:120],
    )


def apply_llm_semantic_decision(
    rq: str,
    row: Dict[str, Any],
    decision: LlmSemanticDecision,
    trigger_reason: str,
) -> Dict[str, Any]:
    cols = RQ_COLUMNS[rq]
    raw_deterministic = str(row.get(cols["label"]) or "")
    deterministic = _normalize_abandoned_label(rq, raw_deterministic)
    out = dict(row)
    out[cols["deterministic"]] = deterministic
    decision_label = _normalize_abandoned_label(rq, decision.label)
    decision_abstains = decision.abstain or not decision_label or decision_label not in ALLOWED_LABELS[rq]
    out[cols["llm"]] = "" if decision_abstains else decision_label
    out[cols["trigger"]] = trigger_reason
    guarded = _normalize_abandoned_label(rq, _guarded_final_label(rq, row, trigger_reason))
    llm_is_promotable = (
        not decision_abstains
        and decision.confidence != "low"
        and decision_label in ALLOWED_LABELS[rq]
    )
    if guarded and not (llm_is_promotable and decision_label == guarded):
        out[cols["final"]] = guarded
        out[cols["basis"]] = "deterministic_llm_guard"
        out[cols["label"]] = guarded
        out[f"{cols['llm']}_confidence"] = decision.confidence
        out[f"{cols['llm']}_rationale"] = decision.short_rationale
        out[f"{cols['llm']}_codebook_step"] = decision.codebook_step
        return _with_rq2_paper_label(rq, out)
    if not llm_is_promotable:
        out[cols["final"]] = deterministic
        out[cols["basis"]] = "deterministic"
    else:
        out[cols["final"]] = decision_label
        out[cols["basis"]] = "llm_semantic_correction"
        out[cols["label"]] = decision_label
    out[f"{cols['llm']}_confidence"] = decision.confidence
    out[f"{cols['llm']}_rationale"] = decision.short_rationale
    out[f"{cols['llm']}_codebook_step"] = decision.codebook_step
    return _with_rq2_paper_label(rq, out)


def apply_rq2_indeterminate_adjudication_decision(
    row: Dict[str, Any],
    decision: LlmSemanticDecision,
    trigger_reason: str,
) -> Dict[str, Any]:
    """Apply the second-pass RQ2 adjudication without overwriting first-pass evidence."""
    out = dict(row)
    pre_final = _normalize_abandoned_label(
        "rq2",
        out.get("input_plausibility_final") or out.get("input_plausibility") or "",
    )
    out["input_plausibility_pre_adjudication_final"] = pre_final
    decision_label = _normalize_abandoned_label("rq2", decision.label)
    decision_abstains = decision.abstain or not decision_label or decision_label not in ALLOWED_LABELS["rq2"]
    out["input_plausibility_adjudication_label"] = "" if decision_abstains else decision_label
    out["input_plausibility_adjudication_confidence"] = decision.confidence
    out["input_plausibility_adjudication_trigger_reason"] = trigger_reason
    out["input_plausibility_adjudication_codebook_step"] = decision.codebook_step
    out["input_plausibility_adjudication_rationale"] = decision.short_rationale

    guarded = _normalize_abandoned_label("rq2", _guarded_rq2_adjudication_label(out, trigger_reason))
    if guarded:
        out["input_plausibility_final"] = guarded
        out["input_plausibility_final_basis"] = "deterministic_llm_guard"
        out["input_plausibility"] = guarded
        return _with_rq2_paper_label("rq2", out)

    promotable = (
        not decision_abstains
        and decision.confidence in {"high", "medium"}
        and decision_label in ALLOWED_LABELS["rq2"]
        and bool(decision.evidence_fields)
    )
    if promotable:
        out["input_plausibility_final"] = decision_label
        out["input_plausibility_final_basis"] = "llm_indeterminate_adjudication"
        out["input_plausibility"] = decision_label
    else:
        out["input_plausibility_final"] = pre_final
        out.setdefault("input_plausibility_final_basis", "deterministic")
    return _with_rq2_paper_label("rq2", out)


def _guarded_rq2_adjudication_label(row: Dict[str, Any], trigger_reason: str) -> str:
    raw = _lower_join(row.get("raw_code"), row.get("value_summary"))
    context = _lower_join(
        row.get("field_context"),
        row.get("input_target_context_ast"),
        row.get("input_consumer_context_ast"),
        row.get("input_target_context_normalized_ast"),
    )
    value_text = str(row.get("value_summary") or "").strip().strip("'\"`")
    channel = str(row.get("input_channel") or "").strip().lower()
    target_role = str(row.get("input_target_role_ast") or "").strip().lower()
    source = str(row.get("input_source_class") or "").strip().lower()
    expr = str(row.get("input_value_expression_kind_ast") or "").strip().lower()
    if _rq2_keyboard_control_context(raw, context, value_text):
        return "technical_or_control_input"
    if _rq2_numeric_config_control_context(raw, context, value_text):
        return "technical_or_control_input"
    if _rq2_config_or_control_context(raw, context):
        return "technical_or_control_input"
    if _rq2_domain_target_context(raw, context, target_role, channel, source, expr, value_text):
        return "domain_plausible_input"
    if _rq2_meaningful_visible_text_literal(raw, context, value_text, channel, target_role):
        return "domain_plausible_input"
    if "page.keyboard.press" in raw or "keyboard.press" in raw:
        if not any(token in context for token in ("editor", "input", "textbox", "field", "search", "name", "title")):
            return "technical_or_control_input"
    if "realpress" in raw and ".type(" not in raw:
        return "technical_or_control_input"
    if trigger_reason == "rq2_validation_config_or_domain_boundary_adjudication":
        if any(token in raw for token in ("8080", "port", "endpoint", "resourceurl", "datasource", "remote-file")):
            return "technical_or_control_input"
    return ""


def apply_guarded_semantic_columns(
    rq: str,
    row: Dict[str, Any],
    *,
    trigger_reason: str,
    guarded_label: str,
) -> Dict[str, Any]:
    cols = RQ_COLUMNS[rq]
    guarded_label = _normalize_abandoned_label(rq, guarded_label)
    out = apply_deterministic_semantic_columns(rq, row, trigger_reason)
    out[cols["final"]] = guarded_label
    out[cols["basis"]] = "deterministic_llm_guard"
    out[cols["label"]] = guarded_label
    return _with_rq2_paper_label(rq, out)


def _guarded_final_label(rq: str, row: Dict[str, Any], trigger_reason: str) -> str:
    if rq == "rq3_workflow" and trigger_reason == "rq3_workflow_dominant_evidence_label_conflict":
        return _workflow_expected_from_dominant_source(row)
    if rq == "rq5c":
        deterministic = str(row.get("verification_intent") or row.get("verification_intent_deterministic") or "")
        subject_role = _lower_join(row.get("assertion_subject_semantic_role_ast"))
        subject_path = _lower_join(row.get("assertion_subject_path_json"), row.get("assertion_subject_text_ast"))
        current_matcher = _lower_join(
            row.get("assertion_semantic_matcher_ast"),
            row.get("matcher"),
            row.get("assertion_matcher"),
        ).replace(" ", "")
        raw = _lower_join(row.get("raw_code"), row.get("matcher"), row.get("assertion_matcher"))
        strong_guard = {
            "accessibility_compliance": (
                any(token in subject_role for token in ("accessibility", "accessible", "aria"))
                or any(token in subject_path for token in ("accessible", "accessibility", "a11y", "aria", "focusable", "tabindex"))
                or any(token in raw for token in ("accessible", "accessibility", "a11y", "aria", "focusable", "tabindex"))
            ),
            "style_or_visual_state": (
                "style_layout_property" in subject_role
                or any(token in current_matcher for token in ("have.css", "havecss", "tohavecss", "css"))
                or any(token in raw for token in ("language-css", "have.css", "computedstyle", "font-", "fontfamily", "fill-opacity", "opacity", "class="))
            ),
            "network_contract": (
                subject_role in {"network_status", "network_payload"}
                or any(token in subject_path for token in ("interception", "request", "response", "statuscode", "headers", "body"))
                or any(token in raw for token in ("cy.request", "cy.wait('@", "interception.", ".request.", ".response.", "statuscode"))
            ),
            "navigation_outcome": (
                "navigation_location" in subject_role
                or any(token in subject_path for token in ("currenturl", "location", "pathname", "href", "url"))
                or any(token in raw for token in ("cy.url", "currenturl", "window.location", "location.", "pathname", "href"))
            ),
            "interactive_state": (
                subject_role in {"ui_control_state", "ui_event_counter"}
                or any(
                    token in current_matcher
                    for token in ("be.enabled", "beenabled", "tobeenabled", "be.disabled", "bedisabled", "tobedisabled", "have.callcount", "callcount")
                )
                or any(token in raw for token in ("callcount", "clickcount", "eventcount", "calledonce", "changespy", "clickspy", "blurspy", "stub", "data-qa-toggle"))
            ),
            "api_or_data_contract": (
                "api_object_contract" in subject_role
                or "requestpayload" in subject_path
                or "typeof" in subject_path
                or any(token in current_matcher for token in ("tobeinstanceof", "instanceof", "be.an", "bean", "be.a", "bea"))
                and any(token in raw for token in ("'object'", '"object"', "result.", "nodepools", "typeof"))
            ),
        }
        if deterministic in strong_guard and strong_guard[deterministic]:
            return deterministic
        if deterministic == "value_or_attribute_correctness" and any(
            token in current_matcher
            for token in (
                "have.value",
                "havevalue",
                "tohavevalue",
                "have.attr",
                "haveattr",
                "tohaveattribute",
                "tohaveattr",
            )
        ):
            return deterministic
        if any(token in current_matcher for token in ("have.css", "havecss", "tohavecss", "css")):
            return "style_or_visual_state"
        if any(token in current_matcher for token in ("have.text", "havetext", "tohavetext", "containtext", "tocontaintext")):
            return "content_correctness"
        if any(token in current_matcher for token in ("be.enabled", "beenabled", "tobeenabled", "be.disabled", "bedisabled", "tobedisabled")):
            return "interactive_state"
        if trigger_reason == "rq5c_presence_matcher_semantic_conflict" and any(
            token in raw
            for token in (
                "be.visible",
                "toBeVisible".lower(),
                "should('exist",
                'should("exist',
                "not.exist",
            )
        ):
            if deterministic in strong_guard and strong_guard[deterministic]:
                return deterministic
            return "element_presence"
        if any(token in raw for token in ("callcount", "clickcount", "eventcount", "calledonce", "changespy", "stub")):
            return "interactive_state"
        if "matchedrequests" in subject_path or "matchedrequests" in raw:
            return "network_contract"
        return ""
    if rq != "rq2":
        return ""

    raw = _lower_join(row.get("raw_code"), row.get("value_summary"))
    context = _lower_join(
        row.get("field_context"),
        row.get("input_target_context_ast"),
        row.get("input_consumer_context_ast"),
        row.get("input_target_role_ast"),
    )
    value_text = str(row.get("value_summary") or "").strip().strip("'\"`")
    channel = str(row.get("input_channel") or "").strip().lower()
    source = str(row.get("input_source_class") or "").strip().lower()
    expr = str(row.get("input_value_expression_kind_ast") or "").strip().lower()
    target_role = str(row.get("input_target_role_ast") or "").strip().lower()

    if _rq2_keyboard_control_context(raw, context, value_text):
        return "technical_or_control_input"

    if trigger_reason == "rq2_path_or_file_construction_edge_conflict" or any(
        token in raw
        for token in (
            "setinputfiles",
            "selectfile",
            "path.join",
            "path.resolve",
            "dirname",
            "input[type=\"file\"]",
            "input[type='file']",
        )
    ):
        signal_raw = re.sub(r"//[^\r\n]*", "", raw)
        if any(
            token in signal_raw
            for token in (
                "exceed-limit",
                "exceed_limit",
                "over-limit",
                "over_limit",
                "too-large",
                "too_large",
                "invalid",
                "malformed",
                "wrongpath",
                "badpath",
                "limit-test",
            )
        ):
            return "validation_or_edge_case_input"
        if str(row.get("input_plausibility") or "").strip() == "validation_or_edge_case_input":
            return "domain_plausible_input"
        return ""

    if ".fill('')" in raw or '.fill("")' in raw:
        return ""

    if _rq2_config_or_control_context(raw, context):
        return "technical_or_control_input"

    if _rq2_clear_dummy_literal(value_text) and not _rq2_strong_domain_target(context, target_role):
        return "placeholder_or_dummy_input"

    if _rq2_numeric_config_control_context(raw, context, value_text):
        return "technical_or_control_input"

    if any(token in raw for token in ("ipv4", ".cvc", "\"cvc\"", "'cvc'", "type(image)", ".type(image)")):
        return "domain_plausible_input"

    if any(token in raw for token in ("tax_id", "taxid")):
        return "domain_plausible_input"

    if "paginationurl" in raw and "parsespecialcharsequences" in raw:
        return "domain_plausible_input"

    if "field-prefix" in raw and "test-prefix" in raw:
        return "domain_plausible_input"

    if "homepage" in raw and "http" in raw:
        return "validation_or_edge_case_input"

    if "realpress" in raw and ".type(" not in raw:
        return "technical_or_control_input"

    if "page.keyboard.press" in raw or "keyboard.press" in raw:
        return "technical_or_control_input"

    if "page.keyboard.type" in raw:
        if "options." in raw or "celexpression" in raw:
            return "technical_or_control_input"
        if ("html`" in raw or "<h1" in raw or "<pre" in raw or "<p" in raw) and re.search(
            r"\b(?:foo|foobar|hello\s+world|lorem|ipsum|dummy|sample)\b",
            raw,
            re.I,
        ):
            return "placeholder_or_dummy_input"
        if "tiptap" in raw or "editor" in context:
            return "domain_plausible_input"
        if _rq2_clear_dummy_literal(value_text):
            return "placeholder_or_dummy_input"
        return "domain_plausible_input"

    if _rq2_domain_target_context(raw, context, target_role, channel, source, expr, value_text):
        return "domain_plausible_input"

    if _rq2_meaningful_visible_text_literal(raw, context, value_text, channel, target_role):
        return "domain_plausible_input"

    has_control_token = _has_cypress_control_token(raw)
    type_count = raw.count(".type(")
    if has_control_token and type_count > 1:
        return "technical_or_control_input"
    if has_control_token and type_count <= 1:
        return ""

    if "faker.string.alphanumeric" in raw and "search" in raw:
        return "domain_plausible_input"

    if any(token in raw for token in ("testaddress", "testcanceladdress")) and "address" in raw:
        return "domain_plausible_input"

    if "treeselectfilterinput" in raw and any(token in raw for token in ("\"blue\"", "'blue'")):
        return "domain_plausible_input"

    weak_literals = (
        "'abc'",
        '"abc"',
        "'bar'",
        '"bar"',
        "'log'",
        '"log"',
        "'before'",
        '"before"',
        '"clear"',
        "'clear'",
        "'test mandatory'",
        '"test mandatory"',
    )
    if any(token in raw for token in weak_literals) and (
        not context.strip() or "unknown" in context or "generic" in context
    ):
        return ""

    return ""


def _rq2_clear_dummy_literal(value_text: str) -> bool:
    normalized = value_text.strip().strip("'\"`").lower()
    if not normalized:
        return False
    if normalized in {"abc", "def", "asdf", "test", "test room", "hello", "hello world", "val1", "val2", "foo", "foobar"}:
        return True
    if re.fullmatch(r"val\d+", normalized):
        return True
    if re.fullmatch(r"item\d+", normalized):
        return True
    return any(token in normalized for token in ("lorem", "dummy", "sample"))


def _rq2_config_or_control_context(raw: str, context: str) -> bool:
    combined = f"{raw} {context}"
    return bool(
        re.search(
            r"(?:"
            r"apiwidget|api[-_ ]?widget|endpoint|resource[-_ ]?url|resourceurl|resource[-_ ]?config|"
            r"datasource|data[-_ ]?source|base[-_ ]?url|baseurl|select[-_ ]?route|route|"
            r"pagination|webhook|remote[-_ ]?file|object[-_ ]?storage[-_ ]?endpoint|"
            r"port|config(?:uration)?|setting|dashboard[-_ ]?variable|methodselect|method[-_ ]?select|"
            r"start[-_ ]?frame|stop[-_ ]?frame|overlap[-_ ]?size|table[-_ ]?modal[-_ ]?columns|"
            r"modal[-_ ]?columns"
            r")",
            combined,
            re.I,
        )
        and not re.search(r"\b(?:invalid|malformed|expired|too[-_ ]?(?:long|short|large)|exceed|boundary)\b", combined, re.I)
        and not re.search(r"\b(?:upload|setinputfiles|selectfile|file input|profile|patient|instruction|reply|comment|description|search|filter)\b", combined, re.I)
    )


def _rq2_keyboard_control_context(raw: str, context: str, value_text: str = "") -> bool:
    combined = f"{raw} {context}"
    return (
        _has_cypress_control_token(value_text)
        or "keyboard_control_target" in combined
        or "page.keyboard.press" in combined
        or "keyboard.press" in combined
        or "input:press:" in combined
        or re.search(r"\.press\s*\(", combined, re.I) is not None
    )


def _rq2_strong_domain_target(context: str, target_role: str) -> bool:
    if target_role in {"domain_text_field", "domain_selection_field", "credential_or_config_field"}:
        return True
    return any(token in context for token in ("title", "name", "label", "search", "address", "email", "phone", "password"))


def _rq2_unknown_numeric_max_context(raw: str, context: str, value_text: str) -> bool:
    if not re.fullmatch(r"\d+(?:\.\d+)?", value_text.strip()):
        return False
    combined = f"{raw} {context}"
    return bool(
        re.search(r"(?:symbolmax|symbolmaximum|maxinput|maximuminput|mininput|minimuminput)", combined, re.I)
        and not re.search(r"\b(?:port|age|amount|quantity|count|row|item)\b", combined, re.I)
    )


def _rq2_numeric_config_control_context(raw: str, context: str, value_text: str) -> bool:
    """Recognize numeric UI config/control values without treating them as edge cases."""
    if not re.fullmatch(r"\d+(?:\.\d+)?", value_text.strip()):
        return False
    combined = f"{raw} {context}"
    if re.search(r"\b(?:invalid|malformed|expired|too[-_ ]?(?:long|short|large)|exceed|boundary)\b", combined, re.I):
        return False
    return bool(
        re.search(
            r"(?:symbol[-_ ]?(?:min|max)|symbol(?:min|max)input|dashboard[-_ ]?config|config[-_ ]?(?:map|symbol)|"
            r"(?:min|max)(?:imum)?input|fixedinput|thresholdinput|limitinput|port[-_ ]?\d*)",
            combined,
            re.I,
        )
    )


def _rq2_meaningful_visible_text_literal(
    raw: str,
    context: str,
    value_text: str,
    channel: str,
    target_role: str,
) -> bool:
    """Treat visible text-entry literals as domain values when they are not filler or edge/config inputs."""
    normalized = value_text.strip().strip("'\"`").lower()
    if not normalized:
        return False
    if target_role in {"credential_or_config_field"}:
        return False
    if channel and channel not in {"ui_text_entry", "text_entry", "keyboard_entry"}:
        return False
    if not any(token in raw for token in (".fill(", ".type(", "keyboard.type")):
        return False
    if "keyboard.press" in raw or "realpress" in raw:
        return False
    if _rq2_clear_dummy_literal(normalized):
        return False
    if normalized.startswith("test "):
        return False
    useful_context = context.strip() and not re.fullmatch(r"(?:unknown|generic|none|null|ui_text_entry|\s)+", context.strip())
    if useful_context:
        return False
    if re.fullmatch(r"\d+(?:\.\d+)?", normalized):
        return False
    if "@" in normalized and not _rq2_strong_domain_target(context, target_role):
        return False
    if re.search(r"(?:https?://|/|\\\\|\\.png\\b|\\.jpg\\b|\\.jpeg\\b|\\.gif\\b|\\.pdf\\b|\\.json\\b)", normalized, re.I):
        return False
    if re.search(
        r"\b(?:invalid|malformed|expired|should[-_ ]?preserve|preserve|too[-_ ]?(?:long|short|large)|"
        r"exceed|boundary|limit[-_ ]?test)\b",
        normalized,
        re.I,
    ):
        return False
    if len(normalized) < 4:
        return False
    return bool(re.search(r"[a-z]", normalized, re.I))


def _rq2_domain_target_context(
    raw: str,
    context: str,
    target_role: str,
    channel: str,
    source: str,
    expr: str,
    value_text: str,
) -> bool:
    if _rq2_clear_dummy_literal(value_text):
        return False
    if _rq2_config_or_control_context(raw, context):
        return False
    if _rq2_strong_domain_target(context, target_role):
        return True
    if channel == "ui_selection" and value_text:
        return True
    if any(token in raw for token in ("cy.focused().type", "focused().type")) and value_text:
        return True
    if any(token in context for token in ("title", "name", "label", "search", "filterinput", "inputvalue", "replytextbox", "promptinput", "toneselect", "serialnumber", "modelnumber", "dosage form", "prefix", "weight", "lat", "lon", "operator", "enabled blocks")):
        return True
    if any(token in raw for token in ("filterinput", "replytextbox", "promptinput", "inputvalue", "toneselect", "serialnumberinput", "modelnumberinput", "weightinput", "latinput", "loninput", "longfield", "inputlocator", "valueinput", "valuefield", "textinput", "blocktextfield")):
        return True
    if (
        source in {"variable_input", "environment_input", "generated_input", "api_seed_input"}
        or expr in {"identifier", "member_expression"}
    ) and channel == "ui_text_entry" and any(token in raw for token in (".type(", ".fill(", "keyboard.type")):
        return True
    if re.search(r"\b[0-9a-f]{2,4}(?::[0-9a-f]{2,4}){3,}\b", raw, re.I):
        return True
    return False


def _has_cypress_control_token(raw: str) -> bool:
    compact = raw.replace(" ", "").replace("_", "").lower()
    tokens = (
        "{enter}",
        "{tab}",
        "{esc}",
        "{escape}",
        "{leftarrow}",
        "{rightarrow}",
        "{uparrow}",
        "{downarrow}",
        "{selectall}",
        "{movetostart}",
        "{movetoend}",
        "{del}",
        "{backspace}",
        "{ctrl}",
        "{control}",
        "{meta}",
        "{cmd}",
        "{shift}",
        "{alt}",
        "{option}",
    )
    return any(token in compact for token in tokens)


def _is_pure_cypress_control_value(value: object) -> bool:
    compact = str(value or "").strip().strip("'\"").replace(" ", "").replace("_", "").lower()
    if not compact:
        return False
    tokens = (
        "{enter}",
        "{tab}",
        "{esc}",
        "{escape}",
        "{leftarrow}",
        "{rightarrow}",
        "{uparrow}",
        "{downarrow}",
        "{selectall}",
        "{movetostart}",
        "{movetoend}",
        "{del}",
        "{delete}",
        "{backspace}",
        "{ctrl}",
        "{control}",
        "{meta}",
        "{cmd}",
        "{shift}",
        "{alt}",
        "{option}",
    )
    remainder = compact
    for token in tokens:
        remainder = remainder.replace(token, "")
    for delimiter in ("+", ",", ";"):
        remainder = remainder.replace(delimiter, "")
    return remainder == ""


def apply_deterministic_semantic_columns(rq: str, row: Dict[str, Any], trigger_reason: str = "") -> Dict[str, Any]:
    cols = RQ_COLUMNS[rq]
    deterministic = _normalize_abandoned_label(rq, row.get(cols["label"]) or "")
    out = dict(row)
    if not str(out.get(cols["deterministic"]) or ""):
        out[cols["deterministic"]] = deterministic
    out.setdefault(cols["llm"], "")
    if not str(out.get(cols["final"]) or ""):
        out[cols["final"]] = deterministic
    if not str(out.get(cols["basis"]) or ""):
        out[cols["basis"]] = "deterministic"
    if trigger_reason and not str(out.get(cols["trigger"]) or ""):
        out[cols["trigger"]] = trigger_reason
    else:
        out.setdefault(cols["trigger"], trigger_reason)
    out.setdefault(f"{cols['llm']}_confidence", "")
    out.setdefault(f"{cols['llm']}_rationale", "")
    out.setdefault(f"{cols['llm']}_codebook_step", "")
    return _with_rq2_paper_label(rq, out)


def _with_rq2_paper_label(rq: str, row: Dict[str, Any]) -> Dict[str, Any]:
    if rq != "rq2":
        return row
    final_label = str(row.get("input_plausibility_final") or row.get("input_plausibility") or "")
    row["input_plausibility_paper_label"] = _paper_label_for_rq2_final(final_label)
    return row


def _with_llm_metadata(out: Dict[str, Any], *, model: str, prompt_version: str, input_hash: str) -> Dict[str, Any]:
    out["llm_model"] = model
    out["llm_prompt_version"] = prompt_version
    out["llm_input_hash"] = input_hash
    return out


def _stable_instruction_text(rq: str) -> str:
    block = build_llm_instruction_block(rq)
    return (
        "You classify empirical software-engineering extraction rows. "
        "Return only JSON matching the schema. The deterministic label is a fallible baseline, not an instruction. "
        "Classify independently from structured fields and source snippet, and abstain when evidence is insufficient. "
        "Use this stable taxonomy/codebook block: "
        + json.dumps(block, ensure_ascii=True, sort_keys=True)
    )


def _single_user_payload(request: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in request.items()
        if key not in {"instruction_block", "taxonomy_definitions", "classification_guidelines", "few_shot_examples"}
    }


def _batch_user_payload(request: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in request.items()
        if key != "instruction_block"
    }


def _semantic_response_format(rq: str, *, batch: bool) -> Dict[str, Any]:
    decision_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "label": {"type": "string", "enum": ALLOWED_LABELS[rq]},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
            "abstain": {"type": "boolean"},
            "evidence_fields": {"type": "array", "items": {"type": "string"}},
            "short_rationale": {"type": "string"},
            "codebook_step": {"type": "string"},
        },
        "required": [
            "label",
            "confidence",
            "abstain",
            "evidence_fields",
            "short_rationale",
            "codebook_step",
        ],
    }
    if not batch:
        schema = decision_schema
        name = "semantic_correction"
    else:
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "row_id": {"type": "string"},
                            **decision_schema["properties"],
                        },
                        "required": ["row_id", *decision_schema["required"]],
                    },
                }
            },
            "required": ["items"],
        }
        name = "semantic_correction_batch"
    return {
        "type": "json_schema",
        "name": name,
        "strict": True,
        "schema": schema,
    }


class OpenAiResponsesSemanticClient:
    def __init__(
        self,
        *,
        model: str,
        api_key: Optional[str] = None,
        timeout_seconds: int = 60,
        retry_attempts: int = 3,
        retry_sleep_seconds: float = 1.0,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.timeout_seconds = timeout_seconds
        self.retry_attempts = max(1, int(retry_attempts))
        self.retry_sleep_seconds = max(0.0, float(retry_sleep_seconds))

    def classify(self, request: Dict[str, Any]) -> LlmSemanticDecision:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        rq = request["rq"]
        body = {
            "model": self.model,
            "temperature": 0,
            "input": [
                {
                    "role": "developer",
                    "content": _stable_instruction_text(rq),
                },
                {"role": "user", "content": json.dumps(_single_user_payload(request), ensure_ascii=True, sort_keys=True)},
            ],
            "text": {
                "format": _semantic_response_format(rq, batch=False)
            },
        }
        payload = self._post_responses(body)
        text = _extract_response_text(payload)
        return _decision_from_payload(json.loads(text), ALLOWED_LABELS[rq])

    def classify_batch(self, rq: str, request: Dict[str, Any]) -> Dict[str, LlmSemanticDecision]:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        body = {
            "model": self.model,
            "temperature": 0,
            "input": [
                {
                    "role": "developer",
                    "content": _stable_instruction_text(rq),
                },
                {"role": "user", "content": json.dumps(_batch_user_payload(request), ensure_ascii=True, sort_keys=True)},
            ],
            "text": {
                "format": _semantic_response_format(rq, batch=True)
            },
        }
        payload = self._post_responses(body)
        text = _extract_response_text(payload)
        raw = json.loads(text)
        out: Dict[str, LlmSemanticDecision] = {}
        for item in raw.get("items") or []:
            if not isinstance(item, dict):
                continue
            row_id = str(item.get("row_id") or "")
            if not row_id:
                continue
            out[row_id] = _decision_from_payload(item, ALLOWED_LABELS[rq])
        return out

    def _post_responses(self, body: Dict[str, Any]) -> Dict[str, Any]:
        http_req = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        last_exc: Optional[BaseException] = None
        for attempt in range(self.retry_attempts):
            try:
                with urllib.request.urlopen(http_req, timeout=self.timeout_seconds) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                last_exc = exc
                if exc.code not in {429, 500, 502, 503, 504} or attempt == self.retry_attempts - 1:
                    raise RuntimeError(f"OpenAI semantic correction request failed: {exc}") from exc
                self._sleep_before_retry(attempt)
            except (urllib.error.URLError, socket.timeout, TimeoutError, http.client.HTTPException) as exc:
                last_exc = exc
                if attempt == self.retry_attempts - 1:
                    raise RuntimeError(f"OpenAI semantic correction request failed: {exc}") from exc
                self._sleep_before_retry(attempt)
            except json.JSONDecodeError as exc:
                last_exc = exc
                if attempt == self.retry_attempts - 1:
                    raise RuntimeError(f"OpenAI semantic correction request failed: {exc}") from exc
                self._sleep_before_retry(attempt)
        raise RuntimeError(f"OpenAI semantic correction request failed: {last_exc}")

    def _sleep_before_retry(self, attempt: int) -> None:
        if self.retry_sleep_seconds:
            time.sleep(min(30.0, self.retry_sleep_seconds * (2 ** max(0, attempt))))


def _extract_response_text(payload: Dict[str, Any]) -> str:
    if "output_text" in payload:
        return str(payload["output_text"])
    for item in payload.get("output", []) or []:
        for content in item.get("content", []) or []:
            if content.get("type") in {"output_text", "text"}:
                return str(content.get("text") or "")
    raise RuntimeError("OpenAI response did not contain output text")


class LlmSemanticCorrector:
    def __init__(
        self,
        *,
        enabled: bool,
        model: str,
        cache: LlmSemanticCache,
        dry_run: bool = False,
        max_rows: int = 0,
        fail_closed: bool = False,
        cache_only: bool = False,
        client: Optional[OpenAiResponsesSemanticClient] = None,
        prompt_version: str = LLM_SEMANTIC_PROMPT_VERSION,
        batch_size: int = 32,
        max_concurrent_requests: int = 1,
        client_timeout_seconds: int = 60,
        client_retry_attempts: int = 3,
        client_retry_sleep_seconds: float = 1.0,
        progress_interval: int = 100,
        progress_stream: Optional[TextIO] = None,
    ) -> None:
        self.enabled = enabled
        self.model = model
        self.cache = cache
        self.dry_run = dry_run
        self.max_rows = max_rows
        self.fail_closed = fail_closed
        self.cache_only = cache_only
        self.client = client or OpenAiResponsesSemanticClient(
            model=model,
            timeout_seconds=client_timeout_seconds,
            retry_attempts=client_retry_attempts,
            retry_sleep_seconds=client_retry_sleep_seconds,
        )
        self.prompt_version = prompt_version
        self.batch_size = max(1, int(batch_size or 1))
        self.max_concurrent_requests = max(1, int(max_concurrent_requests or 1))
        self.progress_interval = max(1, int(progress_interval or 1))
        self.progress_stream = progress_stream
        self.rows_corrected = 0
        self.rows_triggered = 0
        self.rows_cache_hits = 0
        self.rows_api_calls = 0
        self.api_batches = 0
        self.rows_dry_run_or_limited = 0
        self.rows_failed_open = 0
        self.rows_seen = 0
        self.rows_guarded = 0
        self.rows_cache_only_misses = 0

    def correct(self, rq: str, row: Dict[str, Any]) -> Dict[str, Any]:
        return self.correct_many(rq, [row])[0]

    def correct_many(self, rq: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        self.rows_seen += len(rows)
        results: List[Optional[Dict[str, Any]]] = [None for _ in rows]
        pending: List[Dict[str, Any]] = []
        call_triggered = 0
        call_cache_hits = 0
        call_deterministic = 0
        call_guarded = 0
        call_dry_or_limited = 0

        for idx, row in enumerate(rows):
            trigger = should_trigger_llm_correction(rq, row)
            if not trigger:
                call_deterministic += 1
                results[idx] = apply_deterministic_semantic_columns(rq, row)
                continue

            self.rows_triggered += 1
            call_triggered += 1
            request = build_llm_semantic_request(rq=rq, row=row, trigger_reason=trigger)
            input_hash = build_input_hash(request)
            guarded = _guarded_final_label(rq, row, trigger)
            if guarded:
                self.rows_guarded += 1
                self.rows_corrected += 1
                call_guarded += 1
                results[idx] = _with_llm_metadata(
                    apply_guarded_semantic_columns(
                        rq,
                        row,
                        trigger_reason=trigger,
                        guarded_label=guarded,
                    ),
                    model=self.model,
                    prompt_version=self.prompt_version,
                    input_hash=input_hash,
                )
                continue
            if (
                not self.enabled
                or self.dry_run
                or (self.max_rows and self.rows_api_calls >= self.max_rows)
            ):
                self.rows_dry_run_or_limited += 1
                call_dry_or_limited += 1
                results[idx] = _with_llm_metadata(
                    apply_deterministic_semantic_columns(rq, row, trigger),
                    model=self.model,
                    prompt_version=self.prompt_version,
                    input_hash=input_hash,
                )
                continue

            cached = self.cache.get(model=self.model, prompt_version=self.prompt_version, input_hash=input_hash)
            if cached is not None:
                try:
                    decision = _decision_from_payload(cached, ALLOWED_LABELS[rq])
                    self.rows_cache_hits += 1
                    call_cache_hits += 1
                    self.rows_corrected += 1
                    out = apply_llm_semantic_decision(rq, row, decision, trigger)
                    results[idx] = _with_llm_metadata(
                        out,
                        model=self.model,
                        prompt_version=self.prompt_version,
                        input_hash=input_hash,
                    )
                    continue
                except Exception:
                    pass

            if self.cache_only:
                self.rows_cache_only_misses += 1
                if self.fail_closed:
                    raise RuntimeError(
                        f"LLM cache-only miss for {rq} row input_hash={input_hash}"
                    )
                self.rows_dry_run_or_limited += 1
                call_dry_or_limited += 1
                results[idx] = _with_llm_metadata(
                    apply_deterministic_semantic_columns(rq, row, trigger),
                    model=self.model,
                    prompt_version=self.prompt_version,
                    input_hash=input_hash,
                )
                continue

            pending.append({
                "idx": idx,
                "row": row,
                "trigger": trigger,
                "request": request,
                "input_hash": input_hash,
            })

        total_pending = len(pending)
        self._log_scan(
            rq,
            rows=len(rows),
            triggered=call_triggered,
            cache_hits=call_cache_hits,
            deterministic=call_deterministic,
            guarded=call_guarded,
            dry_or_limited=call_dry_or_limited,
            pending=total_pending,
        )
        if total_pending:
            self._log_progress(rq, processed=0, total=total_pending, phase="start")
        processed_pending = 0
        api_work: List[List[Dict[str, Any]]] = []
        scheduled_api_rows = 0
        for start in range(0, total_pending, self.batch_size):
            original_batch = pending[start:start + self.batch_size]
            batch = original_batch
            limited_batch: List[Dict[str, Any]] = []
            if self.max_rows:
                remaining_api_rows = self.max_rows - self.rows_api_calls - scheduled_api_rows
                if remaining_api_rows <= 0:
                    for item in original_batch:
                        self.rows_dry_run_or_limited += 1
                        results[item["idx"]] = _with_llm_metadata(
                            apply_deterministic_semantic_columns(rq, item["row"], item["trigger"]),
                            model=self.model,
                            prompt_version=self.prompt_version,
                            input_hash=item["input_hash"],
                        )
                    processed_pending += len(batch)
                    self._log_progress(rq, processed=processed_pending, total=total_pending, phase="limited")
                    continue
                batch = original_batch[:remaining_api_rows]
                limited_batch = original_batch[remaining_api_rows:]

            if batch:
                api_work.append(batch)
                scheduled_api_rows += len(batch)
            for item in limited_batch:
                self.rows_dry_run_or_limited += 1
                results[item["idx"]] = _with_llm_metadata(
                    apply_deterministic_semantic_columns(rq, item["row"], item["trigger"]),
                    model=self.model,
                    prompt_version=self.prompt_version,
                    input_hash=item["input_hash"],
                )
            processed_pending += len(limited_batch)
            if limited_batch:
                self._log_progress(rq, processed=processed_pending, total=total_pending, phase="limited")

        if api_work and self.max_concurrent_requests <= 1:
            for batch in api_work:
                processed_pending = self._process_api_batch(
                    rq,
                    batch=batch,
                    results=results,
                    processed_pending=processed_pending,
                    total_pending=total_pending,
                )
        elif api_work:
            max_workers = min(self.max_concurrent_requests, len(api_work))
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
                future_to_batch = {
                    pool.submit(self._classify_pending_batch, rq, batch): batch
                    for batch in api_work
                }
                for future in concurrent.futures.as_completed(future_to_batch):
                    batch = future_to_batch[future]
                    processed_pending = self._process_api_batch_result(
                        rq,
                        batch=batch,
                        results=results,
                        future=future,
                        processed_pending=processed_pending,
                        total_pending=total_pending,
                    )

        final_results = [
            result if result is not None else apply_deterministic_semantic_columns(rq, rows[idx])
            for idx, result in enumerate(results)
        ]
        if rq == "rq2":
            final_results = self._run_rq2_indeterminate_adjudication(final_results)
        return final_results

    def _run_rq2_indeterminate_adjudication(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Optional[Dict[str, Any]]] = [dict(row) for row in rows]
        pending: List[Dict[str, Any]] = []

        for idx, row in enumerate(rows):
            trigger = should_trigger_rq2_indeterminate_adjudication(row)
            if not trigger:
                continue
            request_row = dict(row)
            request_row.setdefault("input_plausibility_pre_adjudication_final", row.get("input_plausibility_final") or row.get("input_plausibility") or "")
            request = build_llm_semantic_request(rq="rq2", row=request_row, trigger_reason=trigger)
            input_hash = build_input_hash(request)
            guarded = _guarded_rq2_adjudication_label(request_row, trigger)
            if guarded:
                self.rows_guarded += 1
                self.rows_corrected += 1
                results[idx] = _with_llm_metadata(
                    apply_rq2_indeterminate_adjudication_decision(
                        request_row,
                        LlmSemanticDecision(
                            label=guarded,
                            confidence="high",
                            abstain=False,
                            evidence_fields=["deterministic_guard"],
                            short_rationale="Deterministic guard applies before second-pass adjudication.",
                            codebook_step="deterministic_guard",
                        ),
                        trigger,
                    ),
                    model=self.model,
                    prompt_version=self.prompt_version,
                    input_hash=input_hash,
                )
                continue
            if (
                not self.enabled
                or self.dry_run
                or (self.max_rows and self.rows_api_calls >= self.max_rows)
            ):
                self.rows_dry_run_or_limited += 1
                out = dict(request_row)
                out["input_plausibility_pre_adjudication_final"] = str(
                    out.get("input_plausibility_final") or out.get("input_plausibility") or ""
                )
                out["input_plausibility_adjudication_trigger_reason"] = trigger
                results[idx] = _with_llm_metadata(
                    out,
                    model=self.model,
                    prompt_version=self.prompt_version,
                    input_hash=input_hash,
                )
                continue

            cached = self.cache.get(model=self.model, prompt_version=self.prompt_version, input_hash=input_hash)
            if cached is not None:
                try:
                    decision = _decision_from_payload(cached, ALLOWED_LABELS["rq2"])
                    self.rows_cache_hits += 1
                    self.rows_corrected += 1
                    results[idx] = _with_llm_metadata(
                        apply_rq2_indeterminate_adjudication_decision(request_row, decision, trigger),
                        model=self.model,
                        prompt_version=self.prompt_version,
                        input_hash=input_hash,
                    )
                    continue
                except Exception:
                    pass

            if self.cache_only:
                self.rows_cache_only_misses += 1
                if self.fail_closed:
                    raise RuntimeError(
                        f"LLM cache-only miss for rq2-adjudication row input_hash={input_hash}"
                    )
                self.rows_dry_run_or_limited += 1
                out = dict(request_row)
                out["input_plausibility_pre_adjudication_final"] = str(
                    out.get("input_plausibility_final") or out.get("input_plausibility") or ""
                )
                out["input_plausibility_adjudication_trigger_reason"] = trigger
                results[idx] = _with_llm_metadata(
                    out,
                    model=self.model,
                    prompt_version=self.prompt_version,
                    input_hash=input_hash,
                )
                continue

            pending.append({
                "idx": idx,
                "row": request_row,
                "trigger": trigger,
                "request": request,
                "input_hash": input_hash,
            })

        total_pending = len(pending)
        if total_pending:
            self._log_progress("rq2-adjudication", processed=0, total=total_pending, phase="start")

        api_work: List[List[Dict[str, Any]]] = []
        scheduled_api_rows = 0
        processed_pending = 0
        for start in range(0, total_pending, self.batch_size):
            original_batch = pending[start:start + self.batch_size]
            batch = original_batch
            limited_batch: List[Dict[str, Any]] = []
            if self.max_rows:
                remaining_api_rows = self.max_rows - self.rows_api_calls - scheduled_api_rows
                if remaining_api_rows <= 0:
                    limited_batch = original_batch
                    batch = []
                else:
                    batch = original_batch[:remaining_api_rows]
                    limited_batch = original_batch[remaining_api_rows:]
            if batch:
                api_work.append(batch)
                scheduled_api_rows += len(batch)
            for item in limited_batch:
                self.rows_dry_run_or_limited += 1
                out = dict(item["row"])
                out["input_plausibility_pre_adjudication_final"] = str(
                    out.get("input_plausibility_final") or out.get("input_plausibility") or ""
                )
                out["input_plausibility_adjudication_trigger_reason"] = item["trigger"]
                results[item["idx"]] = _with_llm_metadata(
                    out,
                    model=self.model,
                    prompt_version=self.prompt_version,
                    input_hash=item["input_hash"],
                )
                processed_pending += 1
            if limited_batch:
                self._log_progress("rq2-adjudication", processed=processed_pending, total=total_pending, phase="limited")

        if api_work and self.max_concurrent_requests <= 1:
            for batch in api_work:
                processed_pending = self._process_rq2_adjudication_batch(
                    batch=batch,
                    results=results,
                    processed_pending=processed_pending,
                    total_pending=total_pending,
                )
        elif api_work:
            max_workers = min(self.max_concurrent_requests, len(api_work))
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
                future_to_batch = {
                    pool.submit(self._classify_pending_batch, "rq2", batch): batch
                    for batch in api_work
                }
                for future in concurrent.futures.as_completed(future_to_batch):
                    batch = future_to_batch[future]
                    processed_pending = self._process_rq2_adjudication_batch_result(
                        batch=batch,
                        results=results,
                        future=future,
                        processed_pending=processed_pending,
                        total_pending=total_pending,
                    )

        return [result if result is not None else dict(rows[idx]) for idx, result in enumerate(results)]

    def _process_rq2_adjudication_batch(
        self,
        *,
        batch: List[Dict[str, Any]],
        results: List[Optional[Dict[str, Any]]],
        processed_pending: int,
        total_pending: int,
    ) -> int:
        try:
            decisions = self._classify_pending_batch("rq2", batch)
            self._apply_rq2_adjudication_decisions(batch=batch, results=results, decisions=decisions)
        except Exception:
            self._handle_rq2_adjudication_failure(batch=batch, results=results)
        processed_pending += len(batch)
        self._log_progress("rq2-adjudication", processed=processed_pending, total=total_pending, phase="batch")
        return processed_pending

    def _process_rq2_adjudication_batch_result(
        self,
        *,
        batch: List[Dict[str, Any]],
        results: List[Optional[Dict[str, Any]]],
        future: concurrent.futures.Future,
        processed_pending: int,
        total_pending: int,
    ) -> int:
        try:
            decisions = future.result()
            self._apply_rq2_adjudication_decisions(batch=batch, results=results, decisions=decisions)
        except Exception:
            self._handle_rq2_adjudication_failure(batch=batch, results=results)
        processed_pending += len(batch)
        self._log_progress("rq2-adjudication", processed=processed_pending, total=total_pending, phase="batch")
        return processed_pending

    def _apply_rq2_adjudication_decisions(
        self,
        *,
        batch: List[Dict[str, Any]],
        results: List[Optional[Dict[str, Any]]],
        decisions: Dict[str, LlmSemanticDecision],
    ) -> None:
        self.api_batches += 1
        self.rows_api_calls += len(batch)
        for i, item in enumerate(batch):
            row_id = f"r{i}"
            decision = decisions.get(row_id) or LlmSemanticDecision(
                label="",
                confidence="low",
                abstain=True,
                evidence_fields=[],
                short_rationale="LLM batch response omitted this row.",
            )
            self.cache.put(
                model=self.model,
                prompt_version=self.prompt_version,
                input_hash=item["input_hash"],
                payload=asdict(decision),
            )
            self.rows_corrected += 1
            results[item["idx"]] = _with_llm_metadata(
                apply_rq2_indeterminate_adjudication_decision(item["row"], decision, item["trigger"]),
                model=self.model,
                prompt_version=self.prompt_version,
                input_hash=item["input_hash"],
            )

    def _handle_rq2_adjudication_failure(
        self,
        *,
        batch: List[Dict[str, Any]],
        results: List[Optional[Dict[str, Any]]],
    ) -> None:
        if self.fail_closed:
            raise
        self.rows_failed_open += len(batch)
        for item in batch:
            out = dict(item["row"])
            out["input_plausibility_pre_adjudication_final"] = str(
                out.get("input_plausibility_final") or out.get("input_plausibility") or ""
            )
            out["input_plausibility_adjudication_trigger_reason"] = item["trigger"]
            results[item["idx"]] = _with_llm_metadata(
                out,
                model=self.model,
                prompt_version=self.prompt_version,
                input_hash=item["input_hash"],
            )

    def _classify_pending_batch(self, rq: str, batch: List[Dict[str, Any]]) -> Dict[str, LlmSemanticDecision]:
        batch_items = [
            {"row_id": f"r{i}", "request": item["request"]}
            for i, item in enumerate(batch)
        ]
        batch_request = build_llm_semantic_batch_request(rq=rq, items=batch_items)
        return self.client.classify_batch(rq, batch_request)

    def _process_api_batch(
        self,
        rq: str,
        *,
        batch: List[Dict[str, Any]],
        results: List[Optional[Dict[str, Any]]],
        processed_pending: int,
        total_pending: int,
    ) -> int:
        try:
            decisions = self._classify_pending_batch(rq, batch)
            self._apply_api_batch_decisions(rq, batch=batch, results=results, decisions=decisions)
        except Exception:
            self._handle_api_batch_failure(rq, batch=batch, results=results)
        processed_pending += len(batch)
        self._log_progress(rq, processed=processed_pending, total=total_pending, phase="batch")
        return processed_pending

    def _process_api_batch_result(
        self,
        rq: str,
        *,
        batch: List[Dict[str, Any]],
        results: List[Optional[Dict[str, Any]]],
        future: concurrent.futures.Future,
        processed_pending: int,
        total_pending: int,
    ) -> int:
        try:
            decisions = future.result()
            self._apply_api_batch_decisions(rq, batch=batch, results=results, decisions=decisions)
        except Exception:
            self._handle_api_batch_failure(rq, batch=batch, results=results)
        processed_pending += len(batch)
        self._log_progress(rq, processed=processed_pending, total=total_pending, phase="batch")
        return processed_pending

    def _apply_api_batch_decisions(
        self,
        rq: str,
        *,
        batch: List[Dict[str, Any]],
        results: List[Optional[Dict[str, Any]]],
        decisions: Dict[str, LlmSemanticDecision],
    ) -> None:
        self.api_batches += 1
        self.rows_api_calls += len(batch)
        for i, item in enumerate(batch):
            row_id = f"r{i}"
            decision = decisions.get(row_id) or LlmSemanticDecision(
                label="",
                confidence="low",
                abstain=True,
                evidence_fields=[],
                short_rationale="LLM batch response omitted this row.",
            )
            self.cache.put(
                model=self.model,
                prompt_version=self.prompt_version,
                input_hash=item["input_hash"],
                payload=asdict(decision),
            )
            self.rows_corrected += 1
            out = apply_llm_semantic_decision(rq, item["row"], decision, item["trigger"])
            results[item["idx"]] = _with_llm_metadata(
                out,
                model=self.model,
                prompt_version=self.prompt_version,
                input_hash=item["input_hash"],
            )

    def _handle_api_batch_failure(
        self,
        rq: str,
        *,
        batch: List[Dict[str, Any]],
        results: List[Optional[Dict[str, Any]]],
    ) -> None:
        if self.fail_closed:
            raise
        self.rows_failed_open += len(batch)
        for item in batch:
            results[item["idx"]] = _with_llm_metadata(
                apply_deterministic_semantic_columns(rq, item["row"], item["trigger"]),
                model=self.model,
                prompt_version=self.prompt_version,
                input_hash=item["input_hash"],
            )

    def _log_scan(
        self,
        rq: str,
        *,
        rows: int,
        triggered: int,
        cache_hits: int,
        deterministic: int,
        guarded: int,
        dry_or_limited: int,
        pending: int,
    ) -> None:
        if self.progress_stream is None:
            return
        print(
            (
                f"LLM semantic correction {rq}: scan rows={rows} triggered={triggered} "
                f"deterministic={deterministic} guarded={guarded} cache_hits={cache_hits} pending_api={pending} "
                f"dry_or_limited={dry_or_limited} "
                f"batch_size={self.batch_size} concurrency={self.max_concurrent_requests}"
            ),
            file=self.progress_stream,
        )
        try:
            self.progress_stream.flush()
        except Exception:
            pass

    def _log_progress(self, rq: str, *, processed: int, total: int, phase: str) -> None:
        if self.progress_stream is None:
            return
        interval = self.progress_interval
        if phase == "limited":
            interval = max(self.progress_interval, 500)
        previous = max(0, processed - self.batch_size)
        if processed not in {0, total} and processed // interval == previous // interval:
            return
        remaining = max(0, total - processed)
        print(
            (
                f"LLM semantic correction {rq}: phase={phase} "
                f"processed={processed}/{total} remaining={remaining} "
                f"batch_size={self.batch_size} concurrency={self.max_concurrent_requests} api_batches={self.api_batches} "
                f"api_rows={self.rows_api_calls} cache_hits={self.rows_cache_hits} "
                f"guarded={self.rows_guarded} dry_or_limited={self.rows_dry_run_or_limited} "
                f"failed_open={self.rows_failed_open}"
            ),
            file=self.progress_stream,
        )
        try:
            self.progress_stream.flush()
        except Exception:
            pass
