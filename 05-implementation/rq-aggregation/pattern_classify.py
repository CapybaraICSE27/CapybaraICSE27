"""
Framework-neutral pattern classifiers for RQ3 (locator / workflow / sync).

Normalized categories are framework-agnostic. ``raw_framework_api`` and
``framework`` preserve audit evidence. Locator robustness uses
documentation-aligned *signals*, not ground-truth quality judgments.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

# --- Normalized locator strategy (framework-neutral) ---
LOCATOR_STRATEGIES = (
    "role_or_accessibility",
    "label_or_form_affordance",
    "test_id_or_data_contract",
    "text_content",
    "placeholder_or_alt_title",
    "css_selector",
    "xpath_selector",
    "framework_selector_object",
    "webdriver_by_strategy",
    "custom_locator_helper",
    "page_object_mediated",
    "unknown",
)

LOCATOR_COMPOSITIONS = (
    "direct_chain",
    "standalone_locator_query",
    "stored_locator",
    "chained_refinement",
    "positional_refinement",
    "parameterized_locator",
    "page_object_mediated",
    "helper_mediated",
    "custom_command_mediated",
    "unknown",
)

ROBUSTNESS_SIGNALS = (
    "user_facing_accessibility_signal",
    "stable_test_contract_signal",
    "readable_text_signal",
    "implementation_coupled_signal",
    "positional_or_structural_signal",
    "opaque_or_unresolved_signal",
    "mixed_signal",
)

EVIDENCE_BASIS = (
    "ast_call_chain",
    "ast_selector_argument",
    "resolved_helper_body_locator",
    "regex_fallback",
    "source_metadata",
    "unresolved",
)

SELECTOR_LITERAL_KINDS = (
    "role",
    "label",
    "placeholder",
    "alt",
    "title",
    "test_id",
    "data_attribute",
    "id",
    "class",
    "css_compound",
    "css_structural",
    "xpath",
    "text",
    "regex_text",
    "variable",
    "cypress_alias_reference",
    "unknown",
)

# --- Workflow ---
ABSTRACTION_KINDS = (
    "inline_test_body",
    "page_object_model",
    "framework_page_instance",
    "page_object",
    "screenplay_or_task_object",
    "domain_helper",
    "cypress_custom_command",
    "playwright_fixture",
    "testcafe_page_model",
    "webdriverio_page_object",
    "selenium_page_object",
    "nightwatch_page_object",
    "bdd_step_definition",
    "playwright_test_step",
    "hook_setup_flow",  # setup/control-flow abstraction; not limited to before/after hooks
    "unresolved_helper",
    "unknown",
)

INTERACTION_OWNERSHIP = (
    "direct_in_test",
    "helper_expanded",
    "page_object_method",
    "custom_command_body",
    "hook_attached",
    "fixture_attached",
    "fixture_callback",
    "unresolved",
)

REUSE_SCOPE = (
    "one_off_local_helper",
    "file_local_helper",
    "repo_shared_helper",
    "page_object_library",
    "framework_extension",
    "playwright_fixture_scope",
    "unknown",
)

WORKFLOW_ARCHETYPES = (
    "inline_direct",
    "page_object_centric",
    "page_object_centric_unresolved",
    "helper_mediated",
    "framework_extension_centric",
    "hook_or_fixture_centric",
    "bdd_step_centric",
    "structured_step_centric",
    "layered",
    "unresolved_thin_wrapper",
    "mixed_or_unclear",
)

# --- Sync ---
SYNC_PATTERNS = (
    "fixed_delay",
    "element_state_wait",
    "navigation_or_load_wait",
    "network_wait",
    "predicate_or_custom_condition",
    "event_wait",
    "assertion_retry_wait",
    "unresolved_custom_wait",
)

# Framework-neutral → API detectors (first match wins within framework block)
SYNC_EVIDENCE_BASIS = (
    "ast_call",
    "ast_array_literal",
    "ast_assertion_call",
    "ast_assertion_callback",
    "ast_assertion_matcher",
    "ast_assertion_semantic_matcher",
    "ast_binary_numeric_expression",
    "ast_expression_unresolved",
    "ast_numeric_literal",
    "ast_string_literal",
    "ast_symbol_name_heuristic",
    "ast_wait_api",
    "regex_fallback",
)

FRAMEWORK_LOCATOR_API: Dict[str, Tuple[Tuple[str, str], ...]] = {
    "Playwright": (
        (r"\bgetbyrole\b", "role_or_accessibility"),
        (r"\bgetbylabel\b|\bgetbyarialabel\b", "label_or_form_affordance"),
        (r"\bgetbytestid\b", "test_id_or_data_contract"),
        (r"\bgetbydatacy\b", "test_id_or_data_contract"),
        (r"\bgetbytext\b", "text_content"),
        (r"\bgetbyplaceholder\b", "placeholder_or_alt_title"),
        (r"\bgetbyalttext\b", "placeholder_or_alt_title"),
        (r"\bgetbytitle\b", "placeholder_or_alt_title"),
        (r"\bgetbycls\b", "css_selector"),
        (r"\bpage\.locator\s*\(", "framework_selector_object"),
        (r"\blocator\s*\(", "framework_selector_object"),
        (r"xpath\s*=", "xpath_selector"),
    ),
    "Cypress": (
        (r"\bfindbyrole\b|\bgetbyrole\b", "role_or_accessibility"),
        (r"\bfindbylabeltext\b|\bfindbylabel\b|\bgetbylabel\b|\bgetbyarialabel\b|\bfindbyarialabel\b", "label_or_form_affordance"),
        (r"\bfindbyattribute\s*\(\s*['\"](?:aria-label|label)['\"]", "label_or_form_affordance"),
        (r"\bfindbytestid\b|\bgetbytestid\b|\bgetbydatacy\b|\bgetbysel(?:like)?\b|\bfindbysel(?:like)?\b|\bdatacy\b|\bdata-cy\b|\bdata-testid\b", "test_id_or_data_contract"),
        (r"\bfindbyplaceholdertext\b|\bgetbyplaceholder\b", "placeholder_or_alt_title"),
        (r"\bcy\.contains\b|\bfindbytext\b|\bgetbytext\b", "text_content"),
        (r"\bgetbycls\b", "css_selector"),
        (r"\bcy\.xpath\b|\bxpath\b", "xpath_selector"),
        (r"\bcy\.get\s*\(", "css_selector"),
    ),
    "Puppeteer": (
        (r"\bpage\.locator\s*\(", "framework_selector_object"),
        (r"\blocator\s*\(", "framework_selector_object"),
        (r"\$\s*x\s*\(|\bxpath\b", "xpath_selector"),
        (r"\$\s*\(\s*['\"]", "css_selector"),
        (r"\bwaitforselector\b", "css_selector"),
    ),
    "TestCafe": (
        (r"\bselector\s*\(", "framework_selector_object"),
        (r"\bwithtext\b|\bwithattribute\b", "text_content"),
    ),
    "WebDriverIO": (
        (r"\bby\.(id|css|xpath|name|linktext|partiallinktext|classname|tagname)\b", "webdriver_by_strategy"),
        (r"\$\s*\(", "css_selector"),
        (r"\$\$\s*\(", "css_selector"),
    ),
    "Selenium": (
        (r"\bby\.(id|css|xpath|name|linktext|partiallinktext|classname|tagname)\b", "webdriver_by_strategy"),
    ),
    "Nightwatch": (
        (r"\bby\.(id|css|xpath|name|linktext|partiallinktext|classname|tagname)\b", "webdriver_by_strategy"),
        (r"\$\s*\(", "css_selector"),
    ),
}

# Chained refinement: filter/nth/first/etc. — not a bare page.locator() call.
_CHAINED_REFINEMENT_RE = re.compile(
    r"\.(nth|first|last|eq|filter|and|or)\s*\(|"
    r"\.filter\s*\(|\.nth\s*\(|>>\s*(?:locator|getby|text)",
    re.IGNORECASE,
)
_POSITIONAL_REFINEMENT_RE = re.compile(
    r"\.(nth|first|last|eq)\s*\(|:nth-|>>\s*",
    re.IGNORECASE,
)
_STORED_LOCATOR_RE = re.compile(
    r"\b(const|let|var)\s+\w+\s*=\s*.*(locator|getby|selector|cy\.get|\$\s*\()",
    re.IGNORECASE,
)
_SELECTOR_ARG_RE = re.compile(
    r"(?:page\.locator|(?:^|[.\s])locator|cy\.get(?:\s*<[^>]+>)?|cy\.find|\$\s*)\s*\(\s*"
    r"(['\"])(.*?)\1",
    re.IGNORECASE | re.DOTALL,
)

# Native Playwright/Puppeteer Page APIs — not POM component methods.
_FRAMEWORK_PAGE_NATIVE_METHODS = frozenset({
    "goto", "locator", "context", "newpage", "close", "bringtofront", "reload",
    "goback", "goforward", "setcontent", "waitforurl", "waitforloadstate",
    "waitforevent", "waitfortimeout", "waitforselector", "waitforfunction",
    "getbyrole", "getbytext", "getbylabel", "getbyplaceholder", "getbytestid",
    "getbyalttext", "getbytitle", "frame", "frames", "keyboard", "mouse",
    "touchscreen", "route", "unroute", "on", "off", "evaluate", "addinitscript",
})

_STANDALONE_QUERY_RE = re.compile(
    r"^(?:cy\.get(?:\s*<[^>]+>)?|cy\.find|page\.locator|\$\s*\(|browser\.\$\s*\()",
    re.IGNORECASE,
)

_NON_LOCATOR_UI_ACTION_RE = re.compile(
    r"\b(page|context)\.(keyboard|mouse|evaluate|evaluatehandle|addscripttag|addinitscript)\b"
    r"|\bcy\.mount\b"
    r"|\bbrowser\.(execute|performactions)\b",
    re.I,
)

_LOCATOR_API_HINT_RE = re.compile(
    r"\b(getby\w+|findby\w+|locator\s*\(|cy\.get\s*\(|cy\.contains\s*\("
    r"|\$\(|selector\s*\(|by\.\w+)",
    re.I,
)

_AST_LOCATOR_API_TO_STRATEGY = {
    "getByRole": "role_or_accessibility",
    "findByRole": "role_or_accessibility",
    "getByLabel": "label_or_form_affordance",
    "findByLabel": "label_or_form_affordance",
    "findByLabelText": "label_or_form_affordance",
    "getByPlaceholder": "placeholder_or_alt_title",
    "findByPlaceholderText": "placeholder_or_alt_title",
    "getByAltText": "placeholder_or_alt_title",
    "getByTitle": "placeholder_or_alt_title",
    "getByText": "text_content",
    "findByText": "text_content",
    "getByTestId": "test_id_or_data_contract",
    "findByTestId": "test_id_or_data_contract",
    "getByDataCy": "test_id_or_data_contract",
    "getByCls": "css_selector",
    "findByAttribute": "css_selector",
    "contains": "text_content",
    "locator": "css_selector",
    "get": "css_selector",
}


def lacks_locator_subexpression(name: str, raw: str, framework: str) -> bool:
    text = _s(name, raw)
    if _NON_LOCATOR_UI_ACTION_RE.search(text):
        return True
    if _match_framework_api(framework, text):
        return False
    return not bool(_LOCATOR_API_HINT_RE.search(raw or name or ""))


def _s(name: str, raw: str) -> str:
    return f"{name} {raw}".lower()


def _page_like_root(root: str) -> bool:
    if not root:
        return False
    return bool(
        re.match(r"^[A-Z][A-Za-z0-9]*(?:Page|Screen|PO|PageObject)$", root)
        or re.match(r"^[a-z][a-zA-Z0-9]*(?:Page|Screen|PO|PageObject)$", root)
    )


def is_page_like_helper_function(name: str) -> bool:
    """Direct helper calls like waitForDashboardPage(page), not xPage.method()."""
    root = (name or "").split(".")[0]
    if "." in (name or ""):
        return False
    return bool(
        re.match(r"^(waitFor|visit|moveTo|goTo|navigateTo|open)[A-Za-z0-9]*Page$", root, re.I)
    )


def is_page_object_name(name: str) -> bool:
    """True for Page/Screen/PO-like callee roots (model or framework instance)."""
    if is_page_like_helper_function(name):
        return False
    return _page_like_root((name or "").split(".")[0])


def is_framework_page_native_method(method: str) -> bool:
    m = (method or "").lower()
    if m in _FRAMEWORK_PAGE_NATIVE_METHODS:
        return True
    return m.startswith("getby") or m.startswith("findby")


def infer_page_workflow_abstraction(
    name: str,
    raw: str,
    framework: str,
    *,
    feature: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Distinguish Page Object Model abstractions from Playwright Page variables (userPage).
    """
    if feature:
        origin = (feature.get("page_symbol_origin_ast") or "").strip()
        if origin in ("page_object_model", "framework_page_instance"):
            return origin
    if is_page_like_helper_function(name):
        return None
    root = (name or "").split(".")[0]
    if not _page_like_root(root):
        return None
    parts = (name or "").split(".")
    method = parts[1] if len(parts) > 1 else ""

    if re.match(r"^[A-Z]", root):
        return _page_object_kind(framework)

    # lower-camel *Page: nested components -> POM; bare native Page API -> instance
    if len(parts) >= 3:
        return _page_object_kind(framework)
    if len(parts) == 2 and not is_framework_page_native_method(method):
        return _page_object_kind(framework)
    if len(parts) == 2 and is_framework_page_native_method(method):
        return "framework_page_instance"
    return _page_object_kind(framework)


def is_screenplay_or_task(name: str) -> bool:
    root = (name or "").split(".")[0]
    return bool(root) and (
        root.endswith("Task") or root.endswith("Actor") or root.endswith("Flow")
    )


def extract_raw_framework_api(name: str, raw: str) -> str:
    """Best-effort API substring for audit."""
    text = raw or name or ""
    m = re.search(
        r"(page|cy|browser|t|\$)\s*\.[\w$.]+|"
        r"(getBy\w+|findBy\w+|Selector|By\.\w+)",
        text,
        re.IGNORECASE,
    )
    if m:
        return m.group(0)
    return (name or "").split(".")[0] or ""


def _match_framework_api(framework: str, text: str) -> Optional[str]:
    fw = framework or ""
    patterns = FRAMEWORK_LOCATOR_API.get(fw, ())
    for pat, strategy in patterns:
        if re.search(pat, text, re.IGNORECASE):
            return strategy
    # Cross-framework fallbacks
    if re.search(r"\bgetbyrole\b|\bfindbyrole(?:extended)?\b", text, re.IGNORECASE):
        return "role_or_accessibility"
    if re.search(r"\bgetbytestid\b|\bgetbysel(?:like)?\b|\bfindbysel(?:like)?\b|\bdata-cy\b|\bdata-testid\b|\bdatacy\b", text, re.IGNORECASE):
        return "test_id_or_data_contract"
    if re.search(r"\bgetbylabel\b|\bgetbyarialabel\b|\bfindbyarialabel\b|\bgetbyplaceholder\b", text, re.IGNORECASE):
        return "label_or_form_affordance"
    if re.search(r"\bgetbytext\b|\bcy\.contains\b", text, re.IGNORECASE):
        return "text_content"
    if re.search(r"\bgetelementbytestid\b|\bfindbytestid\b", text, re.IGNORECASE):
        return "test_id_or_data_contract"
    if re.search(
        r"\bfindbytitle\b|\bgetbytitle\b|\bfindbyalttext\b|\bgetbyalttext\b|"
        r"\bfindbyplaceholder\b|\bgetbyplaceholder\b",
        text,
        re.IGNORECASE,
    ):
        return "placeholder_or_alt_title"
    if re.search(r"\bxpath\b|xpath\s*=", text, re.IGNORECASE):
        return "xpath_selector"
    if re.search(r"\bselector\s*\(", text, re.IGNORECASE):
        return "framework_selector_object"
    if re.search(r"\bby\.\w+", text, re.IGNORECASE):
        return "webdriver_by_strategy"
    if re.search(r"\bcy\.get(?:\s*<[^>]+>)?\s*\(|\$\s*\(|page\.locator\s*\(", text, re.IGNORECASE):
        return "css_selector"
    return None


def extract_selector_argument(raw: str) -> Optional[str]:
    """Extract first quoted selector/locator argument when present."""
    text = raw or ""
    m = _SELECTOR_ARG_RE.search(text)
    if m:
        return m.group(2)
    m0 = re.search(r"\(\s*`([^`]+)`", text, re.I | re.DOTALL)
    if m0:
        return m0.group(1)
    m1 = re.search(r"\(\s*([A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*)\s*(?:,|\))", text, re.I | re.DOTALL)
    if m1:
        return m1.group(1)
    m2 = re.search(r"selector\s*\(\s*(['\"])(.*?)\1", text, re.I | re.DOTALL)
    if m2:
        return m2.group(2)
    return None


def selector_channel_from_api(name: str, raw: str, normalized_strategy: str = "") -> str:
    text = f"{name or ''} {raw or ''}"
    compact = re.sub(r"\s+", "", text).lower()
    if re.search(r"\b(?:getbylabel|findbylabel|findbylabeltext|getbyarialabel|findbyarialabel)\b", text, re.I):
        return "label"
    if re.search(r"\b(?:getbytitle|findbytitle)\b", text, re.I):
        return "title"
    if re.search(r"\b(?:getbyplaceholder|findbyplaceholder|findbyplaceholdertext)\b", text, re.I):
        return "placeholder"
    if re.search(r"\b(?:getbyrole|findbyrole(?:extended)?)\b", text, re.I):
        return "role"
    if re.search(r"\b(?:getbytestid|findbytestid|getbydatacy|getbysel(?:like)?|findbysel(?:like)?|getelementbytestid)\b", text, re.I):
        return "test_id"
    if re.search(r"\b(?:getbytext|findbytext)\b|\bcy\.contains\s*\(", text, re.I):
        return "text"
    if "xpath(" in compact or re.search(r"\bxpath\s*=", text, re.I):
        return "xpath"
    if normalized_strategy == "text_content":
        return "text"
    if normalized_strategy == "role_or_accessibility":
        return "role"
    if normalized_strategy == "test_id_or_data_contract":
        return "test_id"
    if normalized_strategy == "label_or_form_affordance":
        return "label"
    if normalized_strategy == "placeholder_or_alt_title":
        return "placeholder"
    if normalized_strategy == "xpath_selector":
        return "xpath"
    return ""


def selector_value_origin_from_raw(raw: str) -> str:
    text = raw or ""
    m = re.search(r"\(\s*([^)]+?)\s*(?:,|\))", text, re.DOTALL)
    if not m:
        return ""
    arg = m.group(1).strip()
    if re.match(r"^[rubf]?(['\"`])", arg):
        return "inline_literal"
    if re.match(r"^[A-Za-z_$][A-Za-z0-9_$]*\.[A-Za-z0-9_$.]+$", arg):
        return "member_path"
    if re.match(r"^[A-Za-z_$][A-Za-z0-9_$]*$", arg):
        return "variable"
    if "${" in arg or any(op in arg for op in ("+", "?", ":", "(", ")")):
        return "computed"
    return ""


def infer_selector_literal_kind(raw: str, normalized_strategy: str = "") -> str:
    """Classify selector literal from argument string when possible, not whole call."""
    channel = selector_channel_from_api("", raw, normalized_strategy)
    if channel:
        if channel == "placeholder" and re.search(r"\b(?:getbytitle|findbytitle)\b", raw or "", re.I):
            return "title"
        return channel
    arg = extract_selector_argument(raw)
    r = (arg if arg is not None else "").strip()
    if not r and normalized_strategy:
        # API-only locators (getByText) — no separate literal
        if normalized_strategy == "text_content":
            return "text"
        if normalized_strategy == "role_or_accessibility":
            return "role"
        if normalized_strategy == "test_id_or_data_contract":
            return "test_id"
        return "unknown"
    if not r:
        return "unknown"

    rl = r.lower()
    if rl.startswith("@"):
        return "cypress_alias_reference"
    if rl.startswith("role=") or rl.startswith("role:"):
        return "role"
    if rl.startswith("text=") or rl.startswith("text:"):
        return "text"
    if rl.startswith("xpath=") or rl.startswith("//") or rl.startswith("(//"):
        return "xpath"
    if re.search(r"\[\s*(?:aria-label|aria-labelledby|label)\b", r, re.I):
        return "label"
    if re.search(r"\[\s*placeholder\b", r, re.I):
        return "placeholder"
    if re.search(r"\[\s*title\b", r, re.I):
        return "title"
    if re.search(r"\[\s*alt\b", r, re.I):
        return "alt"
    if re.search(r"data-(?:testid|test-id|test|cy|qa|pw|test-subj)|datacy", r, re.I):
        return "test_id"
    if re.search(r"data-[a-z0-9_-]+", r, re.I):
        return "data_attribute"
    if r.startswith("#") or re.match(r"^#[\w-]+$", r):
        return "id"
    if re.search(r"(?:^|[\s>+~])\.[A-Za-z0-9_-]+", r):
        return "class"
    if r.startswith(".") and " " not in r and ">" not in r:
        return "class"
    if re.match(r"^[A-Za-z][A-Za-z0-9_-]*$", r) and normalized_strategy in {
        "css_selector",
        "framework_selector_object",
    }:
        return "css_structural"
    if re.match(r"^\[[A-Za-z_][\w:.-]*(?:[~|^$*]?=.*)?\]$", r):
        return "css_compound"
    if re.search(r">\s*[\w.#\[]|:\w+-child|\bnth-", r, re.I):
        return "css_structural"
    if re.search(r"[\s>+~]", r):
        return "css_compound"
    if re.match(r"^/.+/$", r):
        return "regex_text"
    if re.search(r"^\$\{", r) or re.match(r"^[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*$", r):
        return "variable"
    # Unquoted simple selectors
    if re.match(r"^#[\w-]+$", r):
        return "id"
    if re.match(r"^\.[\w-]+", r):
        return "class"
    return "unknown"


def strategy_from_selector_channel(selector_literal_kind: str) -> str:
    kind = (selector_literal_kind or "").strip().lower()
    if kind in {"test_id"}:
        return "test_id_or_data_contract"
    if kind == "role":
        return "role_or_accessibility"
    if kind == "label":
        return "label_or_form_affordance"
    if kind in {"placeholder", "title", "alt"}:
        return "placeholder_or_alt_title"
    if kind in {"text", "regex_text"}:
        return "text_content"
    if kind == "xpath":
        return "xpath_selector"
    if kind in {"class", "id", "css_structural", "css_compound", "data_attribute"}:
        return "css_selector"
    return ""


def reconcile_locator_strategy_with_selector_channel(
    strategy: str,
    selector_literal_kind: str,
) -> str:
    channel_strategy = strategy_from_selector_channel(selector_literal_kind)
    if not channel_strategy:
        return strategy
    if strategy in {
        "unknown",
        "framework_selector_object",
        "custom_locator_helper",
        "css_selector",
    }:
        return channel_strategy
    return strategy


def strategy_to_robustness_signal(
    strategy: str,
    framework: str,
    selector_literal_kind: str,
    *,
    opaque: bool = False,
) -> str:
    if opaque or strategy in ("unknown", "page_object_mediated", "custom_locator_helper"):
        if strategy == "unknown":
            return "opaque_or_unresolved_signal"
        return "opaque_or_unresolved_signal"
    if strategy == "role_or_accessibility":
        return "user_facing_accessibility_signal"
    if strategy in ("label_or_form_affordance", "placeholder_or_alt_title"):
        return "user_facing_accessibility_signal"
    if strategy == "test_id_or_data_contract":
        return "stable_test_contract_signal"
    if strategy == "text_content":
        return "readable_text_signal"
    if strategy in ("css_selector", "framework_selector_object"):
        if selector_literal_kind in ("xpath",):
            return "positional_or_structural_signal"
        if selector_literal_kind in ("text", "regex_text"):
            return "readable_text_signal"
        if selector_literal_kind in ("css_structural", "css_compound", "class", "id"):
            return "implementation_coupled_signal"
        if selector_literal_kind in ("role", "test_id", "data_attribute", "label"):
            return "stable_test_contract_signal"
        if framework == "Cypress" and selector_literal_kind in ("data_attribute", "test_id"):
            return "stable_test_contract_signal"
        return "implementation_coupled_signal"
    if strategy == "xpath_selector":
        return "positional_or_structural_signal"
    if strategy == "webdriver_by_strategy":
        if "xpath" in (selector_literal_kind or ""):
            return "positional_or_structural_signal"
        if selector_literal_kind in ("id", "test_id", "data_attribute"):
            return "stable_test_contract_signal"
        return "implementation_coupled_signal"
    return "mixed_signal"


def infer_locator_composition(
    name: str,
    raw: str,
    source_kind: str,
    helper_depth: int,
    feature_type: str,
) -> str:
    sk = (source_kind or "").lower()
    if "page_object" in sk or feature_type == "page_object_ctor" or is_page_object_name(name):
        return "page_object_mediated"
    if sk == "cypress_command" or feature_type == "custom_command_call":
        return "custom_command_mediated"
    if helper_depth > 0 or sk in ("imported_helper", "helper_function"):
        return "helper_mediated"
    text = _s(name, raw)
    if _STANDALONE_QUERY_RE.search(name or raw or "") and not re.search(
        r"\.(click|fill|type|press|check|select|hover|dblclick|tap)\s*\(", text
    ):
        return "standalone_locator_query"
    if _STORED_LOCATOR_RE.search(raw or ""):
        return "stored_locator"
    if _POSITIONAL_REFINEMENT_RE.search(raw or ""):
        return "positional_refinement"
    if _CHAINED_REFINEMENT_RE.search(raw or ""):
        return "chained_refinement"
    if re.search(r"\$\{|[\w]+\s*\)\s*\.(click|fill|type)", raw or ""):
        return "parameterized_locator"
    if re.search(r"\.(click|fill|type|press|hover|check|select)\s*\(", raw or ""):
        return "direct_chain"
    return "unknown"


def resolve_locator_pattern(
    name: str,
    raw: str,
    framework: str,
    source_kind: str,
    helper_depth: int,
    feature_type: str,
    ui_action_category: str,
    feature: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Prefer AST fields from Phase 2B when present; otherwise regex fallback.
    Returns canonical locator fields plus audit companions.
    """
    inferred = classify_locator_from_ui_action(
        name, raw, framework, source_kind, helper_depth, feature_type, ui_action_category
    )
    inferred_strategy = inferred.get("normalized_strategy", "unknown")
    inferred_channel = selector_channel_from_api(name, raw, inferred_strategy) or inferred.get("selector_literal_kind", "")
    inferred_origin = selector_value_origin_from_raw(raw)
    result = {
        **inferred,
        "locator_strategy": inferred_strategy,
        "locator_strategy_inferred": inferred_strategy,
        "locator_composition_inferred": inferred.get("locator_composition", ""),
        "selector_literal_kind_inferred": inferred.get("selector_literal_kind", ""),
        "selector_literal_kind": inferred_channel or inferred.get("selector_literal_kind", ""),
        "selector_channel": inferred_channel,
        "selector_value_origin": inferred_origin,
        "locator_evidence_basis": inferred.get("evidence_basis", "regex_fallback"),
        "locator_composition_evidence_basis": _locator_composition_basis_from_inferred(
            inferred
        ),
    }

    if not feature:
        return result

    resolved_strategy = (feature.get("resolved_selector_strategy_ast") or "").strip()
    if resolved_strategy and resolved_strategy != "unknown":
        basis = (
            feature.get("resolved_selector_evidence_basis_ast")
            or "resolved_helper_body_locator"
        )
        resolved_channel = (feature.get("resolved_selector_channel_ast") or "").strip()
        composition = (
            (feature.get("locator_composition_ast") or "").strip()
            or inferred.get("locator_composition")
            or "helper_mediated"
        )
        result.update(
            {
                "locator_present": True,
                "normalized_strategy": resolved_strategy,
                "locator_strategy": resolved_strategy,
                "locator_strategy_inferred": inferred_strategy,
                "locator_composition": composition,
                "locator_composition_evidence_basis": result[
                    "locator_composition_evidence_basis"
                ],
                "selector_literal_kind": resolved_channel
                or feature.get("selector_literal_kind_ast")
                or inferred_channel
                or inferred.get("selector_literal_kind"),
                "selector_channel": resolved_channel
                or feature.get("selector_channel_ast")
                or inferred_channel
                or inferred.get("selector_literal_kind"),
                "selector_value_origin": feature.get("selector_value_origin_ast")
                or inferred_origin,
                "has_positional_refinement": bool(
                    feature.get("has_positional_refinement_ast")
                ),
                "has_chained_refinement": bool(feature.get("has_chained_refinement_ast")),
                "locator_evidence_basis": basis,
                "evidence_basis": basis,
                "confidence": feature.get("ast_confidence") or inferred.get("confidence"),
            }
        )
        result["robustness_signal"] = strategy_to_robustness_signal(
            resolved_strategy,
            framework,
            result.get("selector_literal_kind", "unknown"),
            opaque=composition in ("page_object_mediated", "helper_mediated"),
        )
        return result

    ast_strategy = (feature.get("locator_strategy_ast") or "").strip()
    if not ast_strategy:
        return result

    use_ast = ast_strategy != "unknown" or inferred_strategy == "unknown"
    if not use_ast:
        return result

    basis = "ast_call_chain" if feature.get("callee_chain_json") else "ast_selector_argument"
    ast_composition = (feature.get("locator_composition_ast") or "").strip()
    composition = ast_composition or inferred.get("locator_composition")
    composition_basis = "ast_call_chain" if ast_composition else result[
        "locator_composition_evidence_basis"
    ]
    chosen_strategy = ast_strategy if ast_strategy != "unknown" else inferred_strategy
    origin = (feature.get("page_symbol_origin_ast") or "").strip()
    if origin == "framework_page_instance" and chosen_strategy == "page_object_mediated":
        api = (feature.get("locator_api_ast") or "").strip()
        chosen_strategy = _AST_LOCATOR_API_TO_STRATEGY.get(api, inferred_strategy)
        if chosen_strategy == "page_object_mediated" and inferred_strategy != "unknown":
            chosen_strategy = inferred_strategy
        if composition == "page_object_mediated":
            composition = inferred.get("locator_composition") or "direct_chain"
            composition_basis = result["locator_composition_evidence_basis"]
    locator_present = bool(inferred.get("locator_present"))
    if locator_present and chosen_strategy == "unknown" and composition in (
        "unknown",
        "helper_mediated",
    ):
        locator_present = False
    result.update(
        {
            "locator_present": locator_present,
            "normalized_strategy": chosen_strategy,
            "locator_strategy": chosen_strategy,
            "locator_strategy_inferred": inferred_strategy,
            "locator_composition": composition,
            "locator_composition_evidence_basis": composition_basis,
            "selector_literal_kind": feature.get("selector_literal_kind_ast")
            or inferred_channel
            or inferred.get("selector_literal_kind"),
            "selector_channel": feature.get("selector_channel_ast")
            or feature.get("selector_literal_kind_ast")
            or inferred_channel
            or inferred.get("selector_literal_kind"),
            "selector_value_origin": feature.get("selector_value_origin_ast") or inferred_origin,
            "has_positional_refinement": bool(
                feature.get("has_positional_refinement_ast")
            ),
            "has_chained_refinement": bool(feature.get("has_chained_refinement_ast")),
            "locator_evidence_basis": basis,
            "evidence_basis": basis,
            "confidence": feature.get("ast_confidence") or inferred.get("confidence"),
        }
    )
    result["robustness_signal"] = strategy_to_robustness_signal(
        chosen_strategy,
        framework,
        result.get("selector_literal_kind", "unknown"),
        opaque=composition in ("page_object_mediated", "helper_mediated"),
    )
    return result


def locator_ast_audit_mismatch_type(
    ast_strategy: str,
    inferred_strategy: str,
    composition_ast: str,
    composition_inferred: str,
    selector_kind_ast: str,
    selector_kind_inferred: str,
    ast_confidence: str,
) -> str:
    """Semicolon-separated mismatch tags, or ``match`` when AST and regex agree."""
    tags: List[str] = []
    if ast_strategy != inferred_strategy:
        tags.append("strategy")
    if composition_ast and composition_inferred and composition_ast != composition_inferred:
        tags.append("composition")
    if (
        selector_kind_ast
        and selector_kind_inferred
        and selector_kind_ast != selector_kind_inferred
    ):
        tags.append("selector_literal_kind")
    if (ast_confidence or "").strip().lower() == "low":
        tags.append("low_confidence")
    return "match" if not tags else ";".join(tags)


def _locator_composition_basis_from_inferred(inferred: Dict[str, Any]) -> str:
    composition = (inferred.get("locator_composition") or "").strip()
    if composition in {
        "page_object_mediated",
        "custom_command_mediated",
        "helper_mediated",
    }:
        return "source_metadata"
    if composition == "unknown":
        return "unresolved"
    return "regex_fallback"


def sync_target_for_pattern(pattern: str) -> str:
    return {
        "element_state_wait": "element",
        "navigation_or_load_wait": "navigation",
        "network_wait": "network",
        "predicate_or_custom_condition": "predicate",
        "event_wait": "event",
        "assertion_retry_wait": "assertion",
        "fixed_delay": "time",
        "unresolved_custom_wait": "",
    }.get(pattern, "")


def sync_flags_for_pattern(pattern: str) -> Dict[str, bool]:
    """Boolean sync flags aligned with canonical sync_pattern."""
    return {
        "is_fixed_delay": pattern == "fixed_delay",
        "is_condition_based": pattern
        in {
            "element_state_wait",
            "navigation_or_load_wait",
            "predicate_or_custom_condition",
            "event_wait",
        },
        "is_network_based": pattern == "network_wait",
        "is_assertion_retry": pattern == "assertion_retry_wait",
    }


def _wait_call_arg(text: str) -> str:
    m = re.search(
        r"(?:\bwaitfortimeout|(?:\bcy|\bt|\.)\.?wait|pause)\s*\(",
        text or "",
        re.I,
    )
    if not m:
        return ""
    start = m.end()
    chars: List[str] = []
    depth = 0
    quote = ""
    escaped = False
    for ch in (text or "")[start:]:
        if quote:
            chars.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = ""
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            chars.append(ch)
            continue
        if ch in "([{":
            depth += 1
            chars.append(ch)
            continue
        if ch in ")]}":
            if depth == 0:
                break
            depth -= 1
            chars.append(ch)
            continue
        if ch == "," and depth == 0:
            break
        chars.append(ch)
    return "".join(chars).strip()


def _is_network_alias_wait_arg(arg: str) -> bool:
    a = (arg or "").strip()
    return bool(
        re.match(r"^['\"]@", a)
        or re.match(r"^`@", a)
        or re.match(r"^\[\s*['\"]@", a)
        or re.match(r"^\[\s*`@", a)
        or (a.startswith("[") and "@" in a)
        or (a.startswith("[") and re.search(r"\.\.\.\s*\w*aliases?\b", a, re.I))
        or re.search(r"\.fill\s*\(\s*['\"]@", a)
        or re.search(r"\b(?:\w*aliases|aliasArray\w*|aliasList\w*|waitAlias\w*|interceptAlias\w*|routeWait\w*)\b", a, re.I)
    )


def _network_alias_arg_kind(arg: str) -> str:
    a = (arg or "").strip()
    if re.match(r"^\[", a) or re.search(r"\.fill\s*\(\s*['\"]@", a):
        return "alias_array"
    if re.match(r"^['\"]@", a):
        return "alias_literal"
    if re.match(r"^`@", a):
        return "alias_expression"
    if re.search(r"\b(?:\w*aliases|aliasArray\w*|aliasList\w*|waitAlias\w*|interceptAlias\w*|routeWait\w*)\b", a, re.I):
        return "alias_expression"
    return ""


def _is_literal_ms_wait_arg(arg: str) -> bool:
    return bool(re.match(r"^\d+(?:\.\d+)?\b", (arg or "").strip()))


def _looks_like_time_wait_arg(arg: str) -> bool:
    a = (arg or "").strip()
    if not a or _is_network_alias_wait_arg(a) or re.match(r"^['\"]", a):
        return False
    if _is_literal_ms_wait_arg(a):
        return True
    if re.match(r"^[A-Z_][A-Z0-9_.]*$", a):
        return True
    if re.search(
        r"(timeout|delay|wait|ms|msec|millis|milliseconds|sec|duration|interval|retry|sleep|pause|throttle|debounce)",
        a,
        re.I,
    ):
        return True
    if re.search(r"(?:\d+\s*[+*\/-]|[+*\/-]\s*\d+)", a):
        return True
    return False


def resolve_wait_pattern(
    name: str,
    raw: str,
    framework: str,
    feature_type: str,
    feature: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    regex = classify_sync_pattern(name, raw, framework, feature_type)
    ast_wait = (feature.get("wait_subtype_ast") or "").strip() if feature else ""
    ast_arg_kind = (feature.get("wait_arg_kind_ast") or "").strip() if feature else ""
    ast_basis = (feature.get("wait_evidence_basis_ast") or "").strip() if feature else ""
    if not ast_wait:
        regex["sync_evidence_basis"] = "regex_fallback"
        return regex

    regex_pattern = regex.get("sync_pattern", "unresolved_custom_wait")
    use_ast = ast_wait != "unresolved_custom_wait" or regex_pattern == "unresolved_custom_wait"
    if not use_ast:
        regex["sync_evidence_basis"] = "regex_fallback"
        return regex

    pattern = ast_wait
    if pattern in ("fixed_delay_literal", "fixed_delay_expression"):
        pattern = "fixed_delay"
    regex = {
        **regex,
        "sync_pattern": pattern,
        "sync_target": sync_target_for_pattern(pattern),
        "sync_evidence_basis": ast_basis or "ast_call",
        "sync_arg_kind": _sync_arg_kind_from_ast(ast_wait, ast_arg_kind) or regex.get("sync_arg_kind", ""),
        **sync_flags_for_pattern(pattern),
    }
    return regex


def classify_locator_from_ui_action(
    name: str,
    raw: str,
    framework: str,
    source_kind: str,
    helper_depth: int,
    feature_type: str,
    ui_action_category: str,
) -> Dict[str, Any]:
    """
  Classify locator evidence on every ui_action (locator-on-all-actions).
  Returns dict with normalized fields; locator_present=False when no locator evidence.
  """
    text = _s(name, raw)
    composition = infer_locator_composition(name, raw, source_kind, helper_depth, feature_type)

    if composition != "page_object_mediated" and lacks_locator_subexpression(name, raw, framework):
        return {
            "locator_present": False,
            "raw_framework_api": extract_raw_framework_api(name, raw),
            "normalized_strategy": "unknown",
            "locator_composition": composition,
            "robustness_signal": "opaque_or_unresolved_signal",
            "evidence_basis": "unresolved",
            "selector_literal_kind": "unknown",
            "selector_depth": 0,
            "has_positional_refinement": False,
            "has_text_filter": False,
            "has_testid_signal": False,
            "confidence": "low",
        }

    concrete_strategy = _match_framework_api(framework, text)

    if composition == "page_object_mediated":
        strategy = "page_object_mediated"
        evidence = "source_metadata"
        confidence = "medium"
    elif composition in ("helper_mediated", "custom_command_mediated"):
        strategy = concrete_strategy or "custom_locator_helper"
        evidence = "regex_fallback" if concrete_strategy else "source_metadata"
        confidence = "medium" if concrete_strategy else "low"
    else:
        strategy = concrete_strategy or "unknown"
        evidence = "regex_fallback" if strategy != "unknown" else "unresolved"
        confidence = "high" if strategy != "unknown" else "low"

    # Action chains: locator often only in raw_code, not in terminal name
    if strategy == "unknown" and ui_action_category in (
        "click",
        "text_input",
        "selection",
        "hover",
        "keyboard_input",
        "locator_query",
    ):
        strategy = _match_framework_api(framework, text) or strategy
        if strategy != "unknown":
            evidence = "regex_fallback"

    locator_present = strategy != "unknown" or composition not in (
        "unknown",
        "direct_chain",
        "standalone_locator_query",
    )
    if ui_action_category == "navigation" and strategy == "unknown":
        locator_present = False

    literal_kind = (
        infer_selector_literal_kind(raw, strategy) if locator_present else "unknown"
    )
    reconciled_strategy = reconcile_locator_strategy_with_selector_channel(strategy, literal_kind)
    if reconciled_strategy != strategy:
        strategy = reconciled_strategy
        if evidence in {"source_metadata", "unresolved"}:
            evidence = "selector_channel_inference"
        confidence = "medium" if confidence == "low" else confidence
        locator_present = True
    opaque = composition in ("helper_mediated", "page_object_mediated") and strategy in (
        "custom_locator_helper",
        "page_object_mediated",
    )
    robustness = strategy_to_robustness_signal(
        strategy, framework, literal_kind, opaque=opaque
    )

    selector_depth = len(re.findall(r"\.(filter|nth|first|last|eq|and|or)\s*\(", raw or "", re.I))
    has_positional = bool(_POSITIONAL_REFINEMENT_RE.search(raw or ""))
    has_text_filter = bool(re.search(r"contains|withtext|filter\s*\(", text))
    has_testid_signal = bool(
        re.search(r"testid|data-cy|data-testid|datacy", text, re.I)
    )

    return {
        "locator_present": locator_present,
        "raw_framework_api": extract_raw_framework_api(name, raw),
        "normalized_strategy": strategy,
        "locator_composition": composition,
        "robustness_signal": robustness,
        "evidence_basis": evidence,
        "selector_literal_kind": literal_kind,
        "selector_depth": selector_depth,
        "has_positional_refinement": has_positional,
        "has_text_filter": has_text_filter,
        "has_testid_signal": has_testid_signal,
        "confidence": confidence,
    }


def classify_sync_pattern(
    name: str,
    raw: str,
    framework: str,
    feature_type: str,
) -> Dict[str, Any]:
    original_text = f"{name} {raw}"
    text = _s(name, raw)
    wait_arg = _wait_call_arg(original_text)
    sync_pattern = "unresolved_custom_wait"
    sync_target = ""
    is_fixed = False
    is_condition = False
    is_network = False
    is_assertion_retry = False
    confidence = "medium"
    sync_arg_kind = _sync_arg_kind_from_raw(name, raw)

    if feature_type == "assertion":
        if re.search(r"\.topass\s*\(", text):
            if "expect(" in text and re.search(
                r"\.\s*to(?:bevisible|behidden|beattached|bedetached|beenabled|bedisabled|bechecked|befocused|havecount|havetext|containtext)\s*\(",
                text,
            ):
                sync_pattern = "assertion_retry_wait"
                sync_target = "assertion"
                is_assertion_retry = True
                return _sync_result(sync_pattern, sync_target, is_fixed, is_condition, is_network, is_assertion_retry, confidence, "")
            sync_pattern = "predicate_or_custom_condition"
            sync_target = "predicate"
            is_condition = True
            return _sync_result(sync_pattern, sync_target, is_fixed, is_condition, is_network, is_assertion_retry, confidence, "")
        if re.search(r"\bto(bevisible|behidden|beattached|bedetached|beenabled|bedisabled|bechecked|befocused)\s*\(", text):
            sync_pattern = "element_state_wait"
            sync_target = "element"
            is_condition = True
            return _sync_result(sync_pattern, sync_target, is_fixed, is_condition, is_network, is_assertion_retry, confidence, "")
        if is_retryable_ui_assertion(name, raw):
            sync_pattern = "assertion_retry_wait"
            is_assertion_retry = True
        return _sync_result(sync_pattern, sync_target, is_fixed, is_condition, is_network, is_assertion_retry, confidence, "")

    if wait_arg and _is_network_alias_wait_arg(wait_arg):
        sync_pattern = "network_wait"
        is_network = True
        sync_target = "network"
    elif wait_arg and _looks_like_time_wait_arg(wait_arg):
        sync_pattern = "fixed_delay"
        is_fixed = True
        confidence = "medium"
    elif (
        re.search(r"\bwaitfortimeout\s*\(\s*\d", text)
        or re.search(r"(?:\bcy|\bt|\.)\.?wait\s*\(\s*\d", text)
        or re.search(r"\.(?:pause)\s*\(\s*\d", text)
    ):
        sync_pattern = "fixed_delay"
        is_fixed = True
    elif re.search(r"\bwaitfortimeout\s*\([^'\"@\d\s]", text):
        sync_pattern = "fixed_delay"
        is_fixed = True
        confidence = "medium"
    elif re.search(r"\bpause\s*\(\s*\d|thread\.sleep", text):
        sync_pattern = "fixed_delay"
        is_fixed = True
    elif re.search(
        r"waitforselector|waitfordisplayed|waitforvisible|waitforclickable|waitforelement|\.waitfor\s*\(",
        text,
    ):
        sync_pattern = "element_state_wait"
        is_condition = True
        sync_target = "element"
    elif re.search(r"tobvisible|should\s*\(\s*['\"]be\.visible", text):
        sync_pattern = "element_state_wait"
        is_condition = True
    elif re.search(r"waitforurl|waitfornavigation|waitforloadstate", text):
        sync_pattern = "navigation_or_load_wait"
        is_condition = True
        sync_target = "navigation"
    elif re.search(r"waitforresponse|waitforrequest|intercept|waitfornetworkidle", text):
        sync_pattern = "network_wait"
        is_network = True
        sync_target = "network"
    elif re.search(r"waitforevent", text):
        sync_pattern = "event_wait"
        is_condition = True
    elif re.search(r"waitforfunction|waituntil|waituntil\s*\(", text):
        sync_pattern = "predicate_or_custom_condition"
        is_condition = True
    elif wait_arg:
        sync_pattern = "unresolved_custom_wait"
        confidence = "low"
    elif re.search(r"\bwait\b", text):
        sync_pattern = "unresolved_custom_wait"
        confidence = "low"
    else:
        sync_pattern = "unresolved_custom_wait"
        confidence = "low"

    if sync_pattern != "fixed_delay" and not (
        sync_pattern == "network_wait" and sync_arg_kind.startswith("alias_")
    ):
        sync_arg_kind = ""
    return _sync_result(sync_pattern, sync_target, is_fixed, is_condition, is_network, is_assertion_retry, confidence, sync_arg_kind)


def _sync_arg_kind_from_ast(wait_subtype: str, wait_arg_kind: str) -> str:
    if wait_subtype == "network_wait" or wait_arg_kind in (
        "network_alias",
        "network_alias_array",
        "network_alias_expression",
    ):
        if wait_arg_kind == "network_alias_array":
            return "alias_array"
        if wait_arg_kind == "network_alias":
            return "alias_literal"
        return "alias_expression"
    if wait_subtype == "fixed_delay_literal" or wait_arg_kind == "fixed_ms":
        return "literal_ms"
    if wait_subtype == "fixed_delay_expression" or wait_arg_kind in (
        "timeout_constant",
        "time_expression",
        "expression",
    ):
        return "constant_or_expression"
    return ""


def _sync_arg_kind_from_raw(name: str, raw: str) -> str:
    text = f"{name} {raw}"
    arg = _wait_call_arg(text)
    if arg and _is_network_alias_wait_arg(arg):
        return _network_alias_arg_kind(arg)
    if arg and _is_literal_ms_wait_arg(arg):
        return "literal_ms"
    if arg and _looks_like_time_wait_arg(arg):
        return "constant_or_expression"
    return ""


def _sync_result(
    sync_pattern: str,
    sync_target: str,
    is_fixed: bool,
    is_condition: bool,
    is_network: bool,
    is_assertion_retry: bool,
    confidence: str,
    sync_arg_kind: str = "",
) -> Dict[str, Any]:
    if not sync_target:
        sync_target = sync_target_for_pattern(sync_pattern)
    return {
        "sync_pattern": sync_pattern,
        "sync_target": sync_target,
        "is_fixed_delay": is_fixed,
        "is_condition_based": is_condition,
        "is_network_based": is_network,
        "is_assertion_retry": is_assertion_retry,
        "is_framework_auto_wait_inferred": False,
        "sync_arg_kind": sync_arg_kind,
        "confidence": confidence,
    }


def sync_placement(source_kind: str, attached_hook: bool, helper_depth: int) -> str:
    if attached_hook or (source_kind or "").lower() in (
        "before",
        "after",
        "beforeeach",
        "aftereach",
        "beforeall",
        "afterall",
    ):
        return "hook"
    if helper_depth > 0 or (source_kind or "").lower() in ("imported_helper", "helper_function"):
        return "helper"
    if (source_kind or "").lower() == "cypress_command":
        return "custom_command"
    return "test_body"


_WORKFLOW_AST_ABSTRACTION = {
    "page_object": "page_object_model",
    "page_object_model": "page_object_model",
    "framework_page_instance": "framework_page_instance",
    "cypress_custom_command": "cypress_custom_command",
    "domain_helper": "domain_helper",
    "playwright_fixture": "playwright_fixture",
}

PAGE_OBJECT_MODEL_KINDS = frozenset({
    "page_object_model",  # AST / general PO signal
    "page_object",  # framework-normalized label (Playwright/Cypress/Puppeteer)
    "webdriverio_page_object",
    "selenium_page_object",
    "nightwatch_page_object",
    "testcafe_page_model",
})

PAGE_OBJECT_ABSTRACTION_KINDS = PAGE_OBJECT_MODEL_KINDS

# Backward-compatible alias
_PAGE_OBJECT_ABSTRACTIONS = PAGE_OBJECT_MODEL_KINDS


def is_page_object_model_abstraction(abstraction: str) -> bool:
    return (abstraction or "") in PAGE_OBJECT_MODEL_KINDS


def is_page_object_abstraction(abstraction: str) -> bool:
    """POM abstractions only (excludes framework_page_instance)."""
    return is_page_object_model_abstraction(abstraction)


_CYPRESS_UI_ACTION_RE = re.compile(
    r"\.(?:click|type|visit|get|contains|find|fill|select|check|trigger|mount|dblclick)\s*\(",
    re.I,
)
_CYPRESS_NESTED_SETUP_RE = re.compile(
    r"\bcy\.\w+\([^)]*\)(?:\.\w+\([^)]*\))*\.\s*wait\s*\(",
    re.I,
)
_CYPRESS_SETUP_CMD_NAME_RE = re.compile(
    r"^(ui(?:Save|Add|Remove|Delete|Reset|Clear|Load|Post|Open|Close)|postMessage|api[A-Z]|seed|reset|setup|init)",
    re.I,
)

_PO_SETUP_METHOD_RE = re.compile(
    r"\.(?:goto|navigate|login|logout|open|reset|seed|setup|init|prepare|visit|load|authenticate|waitFor|constructor)\s*\(",
    re.I,
)
_PO_UI_METHOD_RE = re.compile(
    r"\.(?:click|dblclick|fill|type|press|clear|check|uncheck|hover|select|tap|focus|blur|submit|"
    r"getByRole|getByText|getByLabel|getByTestId|getByPlaceholder|locator|get|contains|find)\s*\(",
    re.I,
)
_PO_AMBIGUOUS_UI_METHOD_RE = re.compile(
    r"\.(?:submit|save|confirm|cancel|delete|edit|add|remove|send|apply|close|toggle|expand|collapse)\s*\(",
    re.I,
)


def infer_cypress_fallback_abstraction(name: str, raw: str) -> Optional[str]:
    """Reclassify nested Cypress setup/API chains away from cypress_custom_command."""
    text = _s(name, raw)
    cmd = (name or "").split(".")[-1]
    if _CYPRESS_SETUP_CMD_NAME_RE.match(cmd) and not _CYPRESS_UI_ACTION_RE.search(text):
        return "domain_helper"
    if _CYPRESS_NESTED_SETUP_RE.search(text) and not _CYPRESS_UI_ACTION_RE.search(text):
        return "domain_helper"
    if re.search(r"\bcy\.(task|fixture|request|session)\b", text):
        return "hook_setup_flow"
    return None


def is_page_object_setup_or_utility_call(
    feature_type: str,
    name: str,
    raw: str,
) -> bool:
    """True when a page-object call is setup/utility rather than a UI interaction."""
    ft = (feature_type or "").lower()
    if ft == "ui_action":
        return False
    if ft == "page_object_ctor":
        return True
    if ft in ("setup", "wait_synchronization", "network_mock", "browser_context_control", "control"):
        return True
    if ft == "helper_call":
        text = f"{name} {raw}"
        if _PO_UI_METHOD_RE.search(text) or _PO_AMBIGUOUS_UI_METHOD_RE.search(text):
            return False
        if _PO_SETUP_METHOD_RE.search(text):
            return True
        return True
    return False


def _workflow_ownership_reuse_for_abstraction(abstraction: str) -> Dict[str, str]:
    if abstraction in PAGE_OBJECT_MODEL_KINDS:
        return {
            "interaction_ownership": "page_object_method",
            "reuse_scope": "page_object_library",
        }
    if abstraction == "cypress_custom_command":
        return {
            "interaction_ownership": "custom_command_body",
            "reuse_scope": "framework_extension",
        }
    if abstraction == "playwright_fixture":
        return {
            "interaction_ownership": "fixture_callback",
            "reuse_scope": "playwright_fixture_scope",
        }
    if abstraction == "domain_helper":
        return {
            "interaction_ownership": "helper_expanded",
            "reuse_scope": "file_local_helper",
        }
    return {}


def resolve_workflow_pattern(
    name: str,
    raw: str,
    framework: str,
    source_kind: str,
    helper_depth: int,
    feature_type: str,
    target_file: str,
    resolved: Optional[bool],
    *,
    feature: Optional[Dict[str, Any]] = None,
    attached_hook: bool = False,
) -> Dict[str, Any]:
    """Prefer AST workflow_kind_ast from Phase 2B when present; else regex/name heuristics."""
    result = classify_workflow_from_feature(
        name,
        raw,
        framework,
        source_kind,
        helper_depth,
        feature_type,
        target_file,
        resolved,
        attached_hook=attached_hook,
    )
    if not feature:
        return result

    fixture_param = (feature.get("fixture_param_name") or "").strip()
    cypress_role = (feature.get("cypress_command_role_ast") or "").strip()
    ast_kind = (feature.get("workflow_kind_ast") or "").strip()
    if fixture_param or ast_kind == "playwright_fixture":
        ownership_reuse = _workflow_ownership_reuse_for_abstraction("playwright_fixture")
        return {
            **result,
            "abstraction_kind": "playwright_fixture",
            "confidence": feature.get("ast_confidence") or result.get("confidence"),
            "workflow_evidence_basis": (
                feature.get("workflow_kind_basis_ast") or "ast_playwright_fixture_param"
            ),
            **ownership_reuse,
        }

    if cypress_role == "session_setup" or cypress_role == "test_data_setup":
        return {
            **result,
            "abstraction_kind": "hook_setup_flow",
            "confidence": feature.get("ast_confidence") or "high",
            "workflow_evidence_basis": (
                feature.get("cypress_command_role_basis_ast")
                or "legacy_cypress_command_role"
            ),
            **_workflow_ownership_reuse_for_abstraction("hook_setup_flow"),
        }
    if cypress_role == "locator_helper":
        return {
            **result,
            "abstraction_kind": "domain_helper",
            "confidence": feature.get("ast_confidence") or "high",
            "workflow_evidence_basis": (
                feature.get("cypress_command_role_basis_ast")
                or "legacy_cypress_command_role"
            ),
            **_workflow_ownership_reuse_for_abstraction("domain_helper"),
        }
    if cypress_role == "utility":
        return {
            **result,
            "abstraction_kind": "domain_helper",
            "confidence": feature.get("ast_confidence") or "medium",
            "workflow_evidence_basis": (
                feature.get("cypress_command_role_basis_ast")
                or "legacy_cypress_command_role"
            ),
            **_workflow_ownership_reuse_for_abstraction("domain_helper"),
        }
    if cypress_role == "workflow_abstraction":
        return {
            **result,
            "abstraction_kind": "cypress_custom_command",
            "confidence": feature.get("ast_confidence") or "high",
            "workflow_evidence_basis": (
                feature.get("cypress_command_role_basis_ast")
                or "legacy_cypress_command_role"
            ),
            **_workflow_ownership_reuse_for_abstraction("cypress_custom_command"),
        }

    if not ast_kind:
        return result

    abstraction = _WORKFLOW_AST_ABSTRACTION.get(ast_kind, ast_kind)
    if abstraction == "cypress_custom_command" and not feature.get("workflow_kind_basis_ast"):
        fb = infer_cypress_fallback_abstraction(name, raw)
        if fb:
            abstraction = fb
    if abstraction in ("page_object", "page_object_model"):
        abstraction = _page_object_kind(framework)

    conf = feature.get("ast_confidence") or result.get("confidence")
    ownership_reuse = _workflow_ownership_reuse_for_abstraction(abstraction)
    return {
        **result,
        "abstraction_kind": abstraction,
        "confidence": conf,
        "workflow_evidence_basis": feature.get("workflow_kind_basis_ast")
        or "ast_workflow_kind",
        **ownership_reuse,
    }


def classify_workflow_from_feature(
    name: str,
    raw: str,
    framework: str,
    source_kind: str,
    helper_depth: int,
    feature_type: str,
    target_file: str,
    resolved: Optional[bool],
    *,
    attached_hook: bool = False,
) -> Dict[str, Any]:
    sk = (source_kind or "").lower()
    ft = (feature_type or "").lower()
    tf = (target_file or "").lower()

    abstraction = "unknown"
    evidence_basis = "feature_metadata_fallback"
    if resolved is False:
        abstraction = "unresolved_helper"
        evidence_basis = "resolution_status"
    elif ft == "bdd_step" or "step_definition" in sk:
        abstraction = "bdd_step_definition"
        evidence_basis = "source_kind"
    elif ft == "page_object_ctor" or "page_object" in sk:
        abstraction = _page_object_kind(framework)
        evidence_basis = "source_kind"
    elif is_screenplay_or_task(name):
        abstraction = "screenplay_or_task_object"
        evidence_basis = "callee_name_heuristic"
    elif ft == "custom_command_call" or sk == "cypress_command":
        abstraction = infer_cypress_fallback_abstraction(name, raw) or "cypress_custom_command"
        evidence_basis = "regex_fallback" if abstraction != "cypress_custom_command" else "feature_type"
    elif ft == "helper_call":
        po_kind = infer_page_workflow_abstraction(name, raw, framework)
        if po_kind:
            abstraction = po_kind
            evidence_basis = "callee_name_heuristic"
        else:
            abstraction = "domain_helper"
            evidence_basis = "feature_type"
    elif ft == "test_step":
        abstraction = "playwright_test_step"
        evidence_basis = "feature_type"
    elif ft == "ui_action" and helper_depth > 0:
        po_kind = infer_page_workflow_abstraction(name, raw, framework)
        if "page_object" in sk and po_kind:
            abstraction = po_kind
            evidence_basis = "callee_name_heuristic"
        elif "page_object" in sk:
            abstraction = _page_object_kind(framework)
            evidence_basis = "source_kind"
        elif sk in ("imported_helper", "helper_function"):
            abstraction = "domain_helper"
            evidence_basis = "source_kind"
        else:
            abstraction = "domain_helper"
            evidence_basis = "helper_depth"
    elif sk in ("before", "after", "beforeeach", "aftereach", "beforeall", "afterall") or "hook" in sk:
        abstraction = "hook_setup_flow"
        evidence_basis = "source_kind"
    elif helper_depth == 0 and ft in ("ui_action", "assertion", "input"):
        abstraction = "inline_test_body"
        evidence_basis = "feature_type"

    ownership = "direct_in_test"
    if resolved is False:
        ownership = "unresolved"
    elif abstraction in PAGE_OBJECT_MODEL_KINDS or "page_object" in sk:
        ownership = "page_object_method"
    elif abstraction == "framework_page_instance":
        ownership = "direct_in_test"
    elif sk == "cypress_command" or ft == "custom_command_call":
        ownership = "custom_command_body"
    elif attached_hook or attached_hook_from_sk(sk):
        ownership = "hook_attached"
    elif helper_depth > 0 or sk in ("imported_helper", "helper_function"):
        ownership = "helper_expanded"
    elif abstraction == "playwright_fixture":
        ownership = "fixture_attached"

    reuse = "unknown"
    if abstraction in PAGE_OBJECT_MODEL_KINDS:
        reuse = "page_object_library"
    elif abstraction == "framework_page_instance":
        reuse = "unknown"
    elif abstraction == "cypress_custom_command":
        reuse = "framework_extension"
    elif tf and ("/helpers/" in tf or "/support/" in tf or "/commands/" in tf):
        reuse = "repo_shared_helper" if "shared" in tf or "common" in tf else "file_local_helper"
    elif abstraction == "domain_helper" and tf:
        reuse = "file_local_helper"

    return {
        "abstraction_kind": abstraction,
        "interaction_ownership": ownership,
        "reuse_scope": reuse,
        "confidence": "high" if abstraction != "unknown" else "low",
        "workflow_evidence_basis": evidence_basis,
    }


def attached_hook_from_sk(sk: str) -> bool:
    return sk in ("before", "after", "beforeeach", "aftereach", "beforeall", "afterall")


def _page_object_kind(framework: str) -> str:
    mapping = {
        "Playwright": "page_object",
        "Cypress": "page_object",
        "TestCafe": "testcafe_page_model",
        "WebDriverIO": "webdriverio_page_object",
        "Selenium": "selenium_page_object",
        "Nightwatch": "nightwatch_page_object",
        "Puppeteer": "page_object",
    }
    return mapping.get(framework or "", "page_object")


def is_assertion_retry_sync_feature(
    name: str,
    raw: str,
    feature: Optional[Dict[str, Any]] = None,
) -> bool:
    """Retryable UI assertion via regex and/or Phase 2B AST wait_subtype_ast."""
    if feature:
        ast_wait = (feature.get("wait_subtype_ast") or "").strip()
        ast_basis = (feature.get("wait_evidence_basis_ast") or "").strip()
        if ast_wait or ast_basis:
            return ast_wait == "assertion_retry_wait"
    if is_retryable_ui_assertion(name, raw):
        return True
    return False


def is_retryable_ui_assertion(name: str, raw: str) -> bool:
    """Web-first / retryable UI assertions only — not value equality checks."""
    text = _s(name, raw)
    if re.search(r"\.(?:should|and)\s*\(\s*['\"]", text):
        return True
    if re.search(
        r"\.(?:should|and)\s*\(\s*(?:async\s*)?(?:function\b|\(?\s*[A-Za-z_$][\w$,\s]*\)?\s*=>)",
        text,
    ):
        return True
    retry_markers = (
        r"tobevisible|tobehidden|tocontaintext|tohavetext|tohaveurl|tohaveattribute",
        r"should\s*\(\s*['\"]be\.visible",
        r"should\s*\(\s*['\"]contain",
        r"should\s*\(\s*['\"]have\.",
        r"waitfordisplayed|waitforelementvisible",
        r"expect\s*\([^)]+\)\.tobedisplayed",
    )
    if not re.search(r"\b(expect|should|t\.expect)\b", text):
        return False
    if re.search(r"toequal|tobe\s*\(|\.equal\s*\(", text) and not re.search(
        r"visible|hidden|text|url|displayed|contain", text
    ):
        return False
    return any(re.search(p, text) for p in retry_markers)


def classify_auto_retry_capabilities(name: str, raw: str, framework: str) -> Dict[str, bool]:
    """
    Split action auto-wait from retryable query semantics.
    Does not emit sync events.
    """
    text = _s(name, raw)
    auto_wait = False
    retryable_query = False
    if framework == "Playwright" and re.search(
        r"\b(page\.|locator\.)[^;]*(click|fill|type|press|check)\s*\(", text
    ):
        auto_wait = True
    if framework == "TestCafe" and re.search(r"\bt\.(click|type|hover)\b", text):
        auto_wait = True
    if framework == "WebDriverIO" and re.search(r"\$\([^)]+\)\.(click|setvalue)\b", text):
        auto_wait = True
    if framework == "Cypress":
        if re.search(r"\bcy\.(click|type|check|select)\b", text):
            auto_wait = True
        if re.search(r"\bcy\.(get|contains|find)\b", text):
            retryable_query = True
    return {"auto_wait_capable": auto_wait, "retryable_query": retryable_query}


def is_auto_wait_capable_ui_action(name: str, raw: str, framework: str) -> bool:
    """Backward-compatible wrapper."""
    return classify_auto_retry_capabilities(name, raw, framework)["auto_wait_capable"]


def infer_workflow_archetype(
    *,
    ui_action_count: int,
    test_body_ui: int,
    hook_ui: int,
    helper_ui: int,
    po_ui: int,
    cypress_cmd_ui: int,
    page_object_signal: bool,
    helper_call_count: int,
    unresolved_helper_calls: int,
    expanded_ui_count: int,
    bdd_step_definition_count: int = 0,
    playwright_test_step_count: int = 0,
    page_object_call_count: int = 0,
) -> str:
    return infer_workflow_archetype_detail(
        ui_action_count=ui_action_count,
        test_body_ui=test_body_ui,
        hook_ui=hook_ui,
        helper_ui=helper_ui,
        po_ui=po_ui,
        cypress_cmd_ui=cypress_cmd_ui,
        page_object_signal=page_object_signal,
        helper_call_count=helper_call_count,
        unresolved_helper_calls=unresolved_helper_calls,
        expanded_ui_count=expanded_ui_count,
        bdd_step_definition_count=bdd_step_definition_count,
        playwright_test_step_count=playwright_test_step_count,
        page_object_call_count=page_object_call_count,
    )["workflow_archetype"]


def infer_workflow_archetype_detail(
    *,
    ui_action_count: int,
    test_body_ui: int,
    hook_ui: int,
    helper_ui: int,
    po_ui: int,
    cypress_cmd_ui: int,
    page_object_signal: bool,
    helper_call_count: int,
    unresolved_helper_calls: int,
    expanded_ui_count: int,
    bdd_step_definition_count: int = 0,
    playwright_test_step_count: int = 0,
    page_object_call_count: int = 0,
) -> Dict[str, Any]:
    source_counts = {
        "hook_ui": max(0, int(hook_ui or 0)),
        "cypress_command_ui": max(0, int(cypress_cmd_ui or 0)),
        "page_object_ui": max(0, int(po_ui or 0)),
        "helper_ui": max(0, int(helper_ui or 0)),
        "structured_step": max(0, int(playwright_test_step_count or 0)),
        "bdd_step": max(0, int(bdd_step_definition_count or 0)),
        "test_body_ui": max(0, int(test_body_ui or 0)),
        "unresolved_helper_calls": max(0, int(unresolved_helper_calls or 0)),
    }
    total = max(
        int(ui_action_count or 0),
        sum(source_counts[k] for k in ("hook_ui", "cypress_command_ui", "page_object_ui", "helper_ui", "test_body_ui")),
        0,
    )

    def share(source: str) -> float:
        return round(source_counts.get(source, 0) / total, 6) if total else 0.0

    positive = {k: v for k, v in source_counts.items() if v > 0}
    source_priority = {
        "hook_ui": 0,
        "cypress_command_ui": 1,
        "page_object_ui": 2,
        "helper_ui": 3,
        "structured_step": 4,
        "bdd_step": 5,
        "test_body_ui": 6,
        "unresolved_helper_calls": 7,
    }
    top_two = [
        {"source": key, "count": int(value), "share": share(key)}
        for key, value in sorted(
            positive.items(),
            key=lambda item: (-int(item[1]), source_priority.get(item[0], 99), item[0]),
        )[:2]
    ]
    dominant_source = top_two[0]["source"] if top_two else ""
    dominant_share = float(top_two[0]["share"]) if top_two else 0.0
    second_share = float(top_two[1]["share"]) if len(top_two) > 1 else 0.0

    def result(label: str, basis: str) -> Dict[str, Any]:
        return {
            "workflow_archetype": label,
            "workflow_source_count_json": json.dumps(source_counts, sort_keys=True),
            "dominant_workflow_source": dominant_source,
            "workflow_dominant_source": dominant_source,
            "dominant_workflow_source_share": dominant_share,
            "workflow_dominant_source_share": dominant_share,
            "top_two_workflow_sources": top_two,
            "workflow_top_two_sources_json": json.dumps(top_two, sort_keys=True),
            "workflow_archetype_basis": basis,
        }

    if total == 0:
        return result("mixed_or_unclear", "no_ui_workflow_evidence")

    direct_plus_po = source_counts["test_body_ui"] + source_counts["page_object_ui"]
    if (
        source_counts["unresolved_helper_calls"] > 0
        and source_counts["unresolved_helper_calls"] > max(expanded_ui_count, source_counts["helper_ui"] + source_counts["cypress_command_ui"])
        and source_counts["unresolved_helper_calls"] >= max(source_counts["test_body_ui"], source_counts["page_object_ui"])
    ):
        return result("unresolved_thin_wrapper", "unresolved_dominates_expanded_evidence")

    if share("hook_ui") >= 0.5 or (source_counts["hook_ui"] > 0 and source_counts["hook_ui"] >= direct_plus_po):
        return result("hook_or_fixture_centric", "dominant_source:hook_ui")

    if source_counts["cypress_command_ui"] > 0 and (
        share("cypress_command_ui") >= 0.5
        or source_counts["cypress_command_ui"] >= direct_plus_po
    ):
        return result("framework_extension_centric", "dominant_source:cypress_command_ui")

    if source_counts["page_object_ui"] > 0 and (
        share("page_object_ui") >= 0.5
        or source_counts["page_object_ui"] >= source_counts["test_body_ui"] + source_counts["helper_ui"]
    ):
        return result("page_object_centric", "dominant_source:page_object_ui")

    if source_counts["helper_ui"] > 0 and (
        share("helper_ui") >= 0.5
        or source_counts["helper_ui"] >= direct_plus_po
    ):
        return result("helper_mediated", "dominant_source:helper_ui")

    if source_counts["structured_step"] > 0 and share("structured_step") >= 0.5:
        return result("structured_step_centric", "dominant_source:structured_step")

    if source_counts["bdd_step"] > 0 and share("bdd_step") >= 0.5:
        return result("bdd_step_centric", "dominant_source:bdd_step")

    if (
        page_object_call_count >= 2
        and share("page_object_ui") < 0.15
        and page_object_signal
    ):
        return result("page_object_centric_unresolved", "page_object_calls_unresolved")

    if dominant_share < 0.5 and second_share >= 0.25:
        return result("layered", f"layered_top:{dominant_source};second_share:{second_share}")

    if source_counts["test_body_ui"] > 0:
        return result("inline_direct", "dominant_source:test_body_ui")

    if page_object_signal or page_object_call_count >= 2:
        return result("page_object_centric", "page_object_signal_fallback")

    if helper_call_count > 0:
        return result("helper_mediated", "helper_call_fallback")

    return result("mixed_or_unclear", "insufficient_workflow_evidence")


def _legacy_infer_workflow_archetype(
    *,
    ui_action_count: int,
    test_body_ui: int,
    hook_ui: int,
    helper_ui: int,
    po_ui: int,
    cypress_cmd_ui: int,
    page_object_signal: bool,
    helper_call_count: int,
    unresolved_helper_calls: int,
    expanded_ui_count: int,
    bdd_step_definition_count: int = 0,
    playwright_test_step_count: int = 0,
    page_object_call_count: int = 0,
) -> str:
    if ui_action_count == 0:
        return "mixed_or_unclear"

    def share(part: int) -> float:
        capped = min(part, ui_action_count)
        return capped / ui_action_count if ui_action_count else 0.0

    if share(hook_ui) >= 0.5:
        return "hook_or_fixture_centric"

    if bdd_step_definition_count > 0 and bdd_step_definition_count >= max(1, ui_action_count * 0.3):
        return "bdd_step_centric"

    if playwright_test_step_count > 0 and playwright_test_step_count >= max(1, ui_action_count * 0.3):
        return "structured_step_centric"

    if helper_call_count >= 3 and expanded_ui_count < helper_call_count and unresolved_helper_calls > 0:
        return "unresolved_thin_wrapper"

    if (
        page_object_call_count >= 2
        and share(po_ui) < 0.15
        and page_object_signal
    ):
        return "page_object_centric_unresolved"

    if share(test_body_ui) >= 0.8 and max(share(helper_ui), share(po_ui), share(cypress_cmd_ui), share(hook_ui)) <= 0.25:
        return "inline_direct"

    if share(cypress_cmd_ui) >= 0.5:
        return "framework_extension_centric"
    if share(helper_ui) >= 0.55:
        return "helper_mediated"
    if share(po_ui) >= 0.5:
        return "page_object_centric"

    total_layered = sum(1 for x in (test_body_ui, hook_ui, helper_ui, po_ui, cypress_cmd_ui) if x > 0)
    if total_layered >= 3:
        return "layered"

    if share(po_ui) >= 0.3 or (page_object_signal and share(helper_ui + po_ui) >= 0.5):
        return "page_object_centric"
    if page_object_call_count >= 2 and page_object_signal:
        return "page_object_centric"
    if share(cypress_cmd_ui) >= 0.4:
        return "framework_extension_centric"
    if share(helper_ui) >= 0.5:
        return "helper_mediated"
    if share(test_body_ui) >= 0.7 and helper_call_count == 0:
        return "inline_direct"
    if total_layered >= 2:
        return "layered"
    return "mixed_or_unclear"


def positive_resilience_signals(robustness_signal: str) -> bool:
    return robustness_signal in (
        "user_facing_accessibility_signal",
        "stable_test_contract_signal",
        "readable_text_signal",
    )


def implementation_coupled_signal(robustness_signal: str) -> bool:
    return robustness_signal in (
        "implementation_coupled_signal",
        "positional_or_structural_signal",
    )
