"""Rule-based category classifiers for RQ1-RQ5."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional


def classify_setup(name: str, raw: str, source_kind: str = "", feature_type: str = "") -> str:
    s = f"{name} {raw}".lower()
    sk = (source_kind or "").lower()
    ft = (feature_type or "").lower()

    if ft == "network_mock" or "intercept" in s or "page.route" in s or "cy.intercept" in s:
        return "network_mock"
    if ft == "browser_context_control" or "viewport" in s or "setcookie" in s or "clearcookie" in s:
        return "browser_context_control"
    if ft == "time_control" or "cy.clock" in s or ".clock(" in s:
        return "time_control"
    if "fixture" in s and ("cy." in s or "fixture(" in s):
        return "framework_fixture"

    if re.search(r"\bafter(?:each|all)?\b", s) or sk in ("after", "aftereach", "afterall"):
        return "teardown_cleanup"
    if re.search(r"\bbefore(?:each|all)?\b", s) or sk in ("before", "beforeeach", "beforeall"):
        return "hook_setup"

    if "cy.request" in s or "fetch(" in s or "axios" in s:
        return "api_seed_setup"
    if "database" in s or "db." in s or "sequelize" in s:
        return "database_seed_setup"
    if "login" in s or "session" in s or "auth" in s:
        return "auth_session_setup"
    if "newcontext" in s or re.search(r"\bbrowser\.(url|newWindow)", s):
        return "browser_context_setup"
    if "teardown" in s or "cleanup" in s:
        return "teardown_cleanup"
    if "helper" in s:
        return "helper_setup"
    if ft in ("setup", "teardown"):
        return "hook_setup" if ft == "setup" else "teardown_cleanup"
    return "unknown_setup"


def map_input_source(input_source: str, name: str = "", raw: str = "") -> str:
    src = (input_source or "").strip().lower()
    mapping = {
        "literal_input": "literal_input",
        "variable_input": "variable_input",
        "generated_input": "generated_input",
        "fixture_file_input": "fixture_file_input",
        "external_file_input": "external_file_input",
        "environment_input": "environment_input",
        "file_upload_input": "file_upload_input",
        "parameterized_input": "parameterized_input",
        "variable_from_external_file": "variable_from_external_file",
        "unknown": "unknown_input",
        "unknown_input": "unknown_input",
    }
    if src in mapping:
        return mapping[src]
    return classify_input(name, raw)


def classify_input(name: str, raw: str) -> str:
    s = f"{name} {raw}".lower()
    if "cy.fixture" in s or re.search(r"\bfixture\s*\(\s*['\"]", s):
        return "fixture_file_input"
    if "process.env" in s or "cypress.env" in s:
        return "environment_input"
    if "cy.intercept" in s or "route(" in s:
        return "network_mock_payload_input"
    if "setinputfiles" in s or "upload" in s or "setfilestoupload" in s:
        return "file_upload_input"
    if "each(" in s or "parameterized" in s:
        return "parameterized_input"
    if re.search(r"['\"][^'\"]+['\"]", raw) and any(x in s for x in ("fill", "type", "setvalue")):
        return "literal_input"
    if "random" in s or "faker" in s:
        return "generated_input"
    if re.search(r"\b[A-Za-z_$][\w$.]*\b", raw) and not re.search(r"^['\"]", raw.strip()):
        return "variable_input"
    if "request" in s or "seed" in s:
        return "api_seed_input"
    return "unknown_input"


# Navigation = explicit page-load / URL navigation calls — not URL oracles (toHaveURL, waitForURL).
_NAV_URL_ORACLE_RE = re.compile(r"\b(tohaveurl|waitforurl)\b", re.IGNORECASE)
_NAV_CALL_RE = re.compile(
    r"""
    \.goto\s*\( |
    \bcy\.visit\s*\( |
    \bpage\.goto\s*\( |
    \bnavigateto\s*\( |
    \bbrowser\.url\s*\(
    """,
    re.IGNORECASE | re.VERBOSE,
)


def is_navigation_call(name: str, raw: str) -> bool:
    """True for goto/visit/browser.url-style calls; false for URL oracles and identifier substrings."""
    s = f"{name} {raw}"
    if _NAV_URL_ORACLE_RE.search(s):
        return False
    return _NAV_CALL_RE.search(s) is not None


def classify_interaction(name: str, raw: str) -> str:
    if is_navigation_call(name, raw):
        return "navigation"
    s = f"{name} {raw}".lower()
    if "getby" in s or "locator" in s or "cy.get" in s or "selector(" in s or "findby" in s:
        return "locator_query"
    if "click" in s:
        return "click"
    if "fill" in s or "type" in s or "setvalue" in s or "typetext" in s:
        return "text_input"
    if "press" in s or "keyboard" in s:
        return "keyboard_input"
    if "select" in s:
        return "selection"
    if "hover" in s:
        return "hover"
    if "drag" in s:
        return "drag_drop"
    if "upload" in s or "setinputfiles" in s:
        return "file_upload"
    if "scroll" in s:
        return "scroll"
    if "wait" in s:
        return "wait_synchronization"
    if "screenshot" in s:
        return "visual_action"
    return "unknown_action"


def classify_assertion(name: str, raw: str) -> str:
    s = f"{name} {raw}".lower()

    # Explicit matcher names (before broad heuristics).
    if (
        "tobevisible" in s
        or "tobehidden" in s
        or "tobenotvisible" in s
        or "nottobevisible" in s
    ):
        return "visibility_oracle"

    # TestCafe selector existence checks.
    if re.search(r"\.exists\s*\.\s*(?:not\s*\.\s*)?(?:ok|notok|not\.ok)\b", s):
        return "visibility_oracle"

    if "tohavevalue" in s or "tohavevalues" in s:
        return "element_state_oracle"

    if "tobenull" in s or "tobeundefined" in s or "tobenan" in s:
        return "element_state_oracle"

    if re.search(r"\.href\b", s) and re.search(
        r"\b(?:to\.eq|to\.equal|\.eq\s*\(|should\s*\(\s*['\"]eq|expect\s*\([^)]*\.href)",
        s,
    ):
        return "url_navigation_oracle"

    if re.search(r"\b(visible|hidden)\b", s):
        return "visibility_oracle"
    if "tohavetext" in s or "contain" in s or "gettext" in s:
        return "text_content_oracle"
    if "haveurl" in s or re.search(r"\burl\b", s):
        return "url_navigation_oracle"
    if "tohaveattribute" in s or "disabled" in s or "enabled" in s:
        return "element_state_oracle"
    if "length" in s or "count" in s:
        return "count_or_length_oracle"
    if "snapshot" in s or "screenshot" in s:
        return "visual_snapshot_oracle"
    if "accessibility" in s or "a11y" in s:
        return "accessibility_oracle"
    if "response" in s or "intercept" in s:
        return "network_response_oracle"
    if "request" in s:
        return "api_state_oracle"
    return "generic_assertion"


ALL_ASSERTION_ORACLE_CATEGORIES: frozenset[str] = frozenset({
    "visibility_oracle",
    "text_content_oracle",
    "url_navigation_oracle",
    "element_state_oracle",
    "count_or_length_oracle",
    "visual_snapshot_oracle",
    "accessibility_oracle",
    "network_response_oracle",
    "api_state_oracle",
    "generic_assertion",
})


def is_locator_query_action(name: str, raw: str, interaction_category: str | None = None) -> bool:
    if interaction_category == "locator_query":
        return True
    s = f"{name} {raw}".lower()
    locator_markers = (
        "getbyrole",
        "getbytext",
        "getbylabel",
        "getbytestid",
        "getbyplaceholder",
        "getbyalt",
        "getbytitle",
        "cy.get",
        "cy.contains",
        "cy.find",
        "cy.xpath",
        "cy.datacy",
        "page.locator",
        "page.getby",
        "selector(",
        "findby",
        "findallby",
        "datacy",
        "locator(",
    )
    return any(m in s for m in locator_markers)


def infer_locator_strategy(
    name: str,
    raw: str,
    interaction_category: str | None = None,
) -> Optional[str]:
    """Infer locator strategy only for locator/query UI actions (avoids css inflation)."""
    if not is_locator_query_action(name, raw, interaction_category):
        return None
    s = f"{name} {raw}".lower()
    if "getbyrole" in s:
        return "role"
    if "getbytestid" in s or "datacy" in s:
        return "testid"
    if "getbytext" in s or "cy.contains" in s or "contains" in s:
        return "text"
    if "getbylabel" in s:
        return "label"
    if "getbyplaceholder" in s:
        return "placeholder"
    if "xpath" in s or "cy.xpath" in s:
        return "xpath"
    if "page.locator" in s or "locator(" in s:
        return "playwright_locator"
    if "selector(" in s:
        return "testcafe_selector"
    if re.search(r"\bcy\.get\s*\(", s):
        return "css"
    if re.search(r"#[\w-]+", raw):
        return "css"
    return "other_locator"


RQ1_ENVIRONMENT_TYPES = frozenset({
    "setup",
    "teardown",
    "network_mock",
    "browser_context_control",
    "time_control",
})

# Conservative patterns for generic `control` features (environment/session/state only).
RQ1_CONTROL_ENV_PATTERNS = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bcookies?\b",
        r"\baddcookies?\b",
        r"\blocalstorage\b",
        r"\bsessionstorage\b",
        r"\bstoragestate\b",
        r"\bsetcookie\b",
        r"\bclearcookies?\b",
        r"\bcy\.task\s*\(",
        r"\bgrantpermissions?\b",
        r"\bviewport\s*\(",
        r"\bsetviewport\b",
        r"\bnewcontext\b",
        r"\baddinitscript\b",
        r"\bpage\.route\b",
        r"\bcy\.intercept\b",
        r"\bintercept\s*\(",
        r"\broute\s*\([^)]*mock",
        r"\bnetworkmock\b",
        r"\bmock\b",
        r"\b(database|sequelize|prisma|mongodb)\b",
        r"\bdb\.\w+",
        r"\b(seed|cleanup|reset).{0,40}\b(db|database)\b",
        r"\bcy\.session\b",
        r"\bcy\.task\s*\(\s*['\"]?(seed|db|database|reset|cleanup|auth)",
        r"\bcy\.request\s*\(",
        r"\bpage\.request\s*\(",
        r"\bfetch\s*\([^)]*(seed|auth|login|session)",
        r"\b(login|logout|authenticate|signin|signout)\s*\(",
        r"\b(auth|session).{0,20}\b(setup|seed|reset|clear)\b",
        r"\bclear(local|session)storage\b",
        r"\bresetbrowsercontext\b",
    )
)

# Cypress subject/utility controls that must not count as RQ1 environment control.
RQ1_CONTROL_EXCLUDE_PATTERNS = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bcy\.wrap\s*\(",
        r"\bcy\.within\s*\(",
        r"\bcy\.then\s*\(",
        r"\bcy\.as\s*\(",
        r"\bcy\.log\s*\(",
        r"\bcy\.focused\s*\(",
        r"\bcy\.root\s*\(",
    )
)


def is_rq1_control_environment(name: str, raw: str) -> bool:
    s = f"{name} {raw}"
    if any(p.search(s) for p in RQ1_CONTROL_EXCLUDE_PATTERNS):
        return False
    return any(p.search(s) for p in RQ1_CONTROL_ENV_PATTERNS)


def is_rq1_environment_feature(f: Dict[str, Any]) -> bool:
    ft = str(f.get("feature_type") or "").lower()
    name = str(f.get("name") or "")
    raw = str(f.get("raw_code") or "")

    if ft in RQ1_ENVIRONMENT_TYPES:
        return True

    if ft == "input":
        s = f"{name} {raw}".lower()
        if "fixture" in s:
            return True

    if ft == "control":
        return is_rq1_control_environment(name, raw)

    return False
