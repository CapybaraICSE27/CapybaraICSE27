"""RQ1 setup/teardown semantic intent layer (Milestone 2)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from classify import (
    classify_setup,
    is_navigation_call,
)
from rq1_provenance_mapper import (
    GENERIC_HELPER_NAME_RE,
    HOOK_SOURCE_KINDS,
    SETUP_ELIGIBLE_FEATURE_TYPES,
    map_provenance_hints,
    provenance_basis_labels,
)

TAXONOMY_PATH = Path(__file__).resolve().parent / "rq1_setup_teardown_taxonomy.json"

PHASES = frozenset({"setup", "teardown", "setup_and_teardown", "unclear"})
SCOPES = frozenset({
    "global_or_project",
    "suite_or_fixture",
    "per_test_hook",
    "helper_or_framework_extension",
    "inline_test_body",
    "unclear",
})
PRIMARY_INTENTS = frozenset({
    "navigation_bootstrap",
    "auth_session_state",
    "browser_context_or_client_state",
    "test_data_or_backend_state",
    "network_mock_or_spy",
    "server_or_external_environment",
    "time_device_permission_emulation",
    "cleanup_restore_state",
    "generic_setup_teardown_utility",
    "unclear",
})
CONFIDENCE_LEVELS = frozenset({"high", "medium", "low"})
OPERATION_KINDS = frozenset({"cleanup_restore", "other_setup_teardown"})
OPERATION_KIND_EVIDENCE_BASES = frozenset({
    "ast_framework_api_category",
    "ast_callee_name_heuristic",
    "ast_literal_argument_context",
    "inventory_category:feature_type",
    "resolved_helper_child_intents",
    "lexical_cleanup",
    "primary_intent_cleanup",
    "not_cleanup_restore",
})
PRIMARY_INTENT_EVIDENCE_BASES = frozenset({
    "ast_framework_api_category",
    "ast_cypress_command_role",
    "ast_cypress_task_handler",
    "ast_callee_name_heuristic",
    "ast_literal_argument_context",
    "ast_request_target_domain",
    "heuristic_cypress_command_role",
    "input_source_class",
    "resolved_helper_child_intents",
    "lexical_framework_api_category",
    "inventory_category:feature_type",
    "inventory_category:source_kind",
    "inventory_category:lexical_fallback",
    "lexical_navigation_call",
    "lexical_static_file_load",
    "lexical_wait_sleep",
    "lexical_network_mock",
    "lexical_backend_data_setup",
    "lexical_auth_session",
    "lexical_inline_data_setup",
    "lexical_server_environment",
    "lexical_time_device_permission",
    "lexical_cleanup",
    "lexical_cookie_storage",
    "lexical_generic_helper_name",
    "unresolved",
})
UNCERTAIN_REASONS = frozenset({
    "helper_body_unavailable",
    "generic_helper_name",
    "mixed_intents",
    "missing_framework_mapping",
    "weak_lexical_signal",
    "conflicting_evidence",
    "not_enough_context",
    "review_snippet_truncated",
    "true_semantic_ambiguity",
})

_TEARDOWN_SOURCE_KINDS = frozenset({"after", "afterEach", "afterAll"})
_SETUP_SOURCE_KINDS = frozenset({"before", "beforeEach", "beforeAll"})
_SUITE_HOOK_SOURCE_KINDS = frozenset({"before", "after", "beforeAll", "afterAll"})
_PER_TEST_HOOK_SOURCE_KINDS = frozenset({"beforeEach", "afterEach"})
_HELPER_IMPLEMENTATION_SOURCE_KINDS = frozenset({"imported_helper", "helper_function", "cypress_command"})

_STATIC_FILE_INPUT_CLASSES = frozenset({
    "fixture_file_input",
    "external_file_input",
    "variable_from_external_file",
})
_INLINE_DATA_SETUP_RE = re.compile(
    r"\b(cy\.(request|task|fixture)|page\.request|fetch\s*\(|axios\.)",
    re.IGNORECASE,
)
_SERVER_ENV_RE = re.compile(
    r"\b(cy\.exec|startserver|stopserver|webdriverio.*service|elasticsearch|opensearch|"
    r"docker|container|serviceworker|mockserver|testserver)\b",
    re.IGNORECASE,
)
_SERVER_ENV_CAMEL_RE = re.compile(
    r"(?:elasticSearch|openSearch|startServer|stopServer|mockServer|testServer|serviceWorker)",
    re.IGNORECASE,
)
_GENERIC_NAME_RE = re.compile(
    rf"\b({'|'.join(GENERIC_HELPER_NAME_RE)})\b",
    re.IGNORECASE,
)
_CLEANUP_RE = re.compile(r"\b(cleanup|teardown|clear|reset|delete|drop|restore|close|remove|logout)\b", re.IGNORECASE)
_AUTH_RE = re.compile(
    r"(session|login|logout|auth|authenticate|storagestate|signin|signout|signup|"
    r"visitwithlogin|apilogin|loginfromapi|userole|token|bearer|authorization|basic\s+auth)",
    re.IGNORECASE,
)
_INTERCEPT_UTILITY_RE = re.compile(r"\b(intercept|page\.route|browsercontext\.route)\b", re.IGNORECASE)
_LOGGER_ASSERT_REPORT_RE = re.compile(
    r"^\s*(?:"
    r"console\.\w+|logger\.\w+|testlogger\.\w+|(?:cy\.)?log|"
    r"(?:assert|expect|report|count|print|debug)[A-Za-z0-9_$]*"
    r")\s*(?:\.|$|\()",
    re.IGNORECASE,
)
_DIRECT_STATEFUL_SETUP_API_RE = re.compile(
    r"\b("
    r"cy\.(?:session|request|task|fixture|intercept|setcookie|clearcookies?|getcookie)|"
    r"page\.(?:route|request|goto)|browsercontext\.route|"
    r"(?:localstorage|sessionstorage)\.setitem|storageState\s*\(|"
    r"(?:t\.)?useRole\s*\("
    r")",
    re.IGNORECASE,
)
_STATEFUL_SETUP_API_RE = re.compile(
    r"\b(cy\.(?:session|request|task|fixture|intercept|setcookie|clearcookies?)|"
    r"page\.(?:route|request|context|goto)|browsercontext\.route|"
    r"localstorage|sessionstorage|storagestate|"
    r"(?:api|db|database)(?:create|update|patch|delete|seed|reset|cleanup|task)[A-Z_a-z0-9]*"
    r"|(?:api|db|database)\.(?:create|update|patch|delete|seed|reset|cleanup|task)"
    r")\b",
    re.IGNORECASE,
)
_BACKEND_FRAMEWORK_CALL_RE = re.compile(
    r"\b(?:cy\.)?(?:request|task)\s*\(",
    re.IGNORECASE,
)
_AUTH_API_NAME_RE = re.compile(
    r"\b(?:cy\.)?(?:api|ui)?(?:login|logout|signin|signout|signup|authenticate|auth|session)"
    r"[A-Z_a-z0-9$]*\b",
    re.IGNORECASE,
)
_AUTH_FLOW_CONTEXT_RE = re.compile(
    r"(?:^|[^a-z0-9])(?:authenticate|login|logout|signin|signout|session|csrf|xsrf|oauth|saml|token|magiclink|invite|verify)(?:$|[^a-z0-9])",
    re.IGNORECASE,
)
_TOKENIZED_AUTH_NAVIGATION_RE = re.compile(
    r"\b(?:page\.goto|cy\.visit)\s*\([^)]*(?:/sign/|/signin/|/invite/|/verify/|/reset-password/|/magic)[^)]*(?:token|\$\{)",
    re.IGNORECASE,
)
_VISUAL_AUDIT_HELPER_RE = re.compile(
    r"\b(compareScreenshot|expectScreenshot|assertScreenshot|matchScreenshot|"
    r"toHaveScreenshot|takeScreenshot|screenshot|snapshot)\b",
    re.IGNORECASE,
)
_EVENT_LISTENER_HELPER_RE = re.compile(
    r"\b(addEventListener|removeEventListener|dispatchEvent|fireEvent|emitEvent)\b",
    re.IGNORECASE,
)
_VERIFICATION_HELPER_NAME_RE = re.compile(r"^(?:verify|validate|assert|expect|check)[A-Z_]", re.IGNORECASE)
_ORDINARY_WORKFLOW_HELPER_RE = re.compile(
    r"\b(open|goto|goTo|navigate|visit|click|select|fill|type|drag|drop|hover|"
    r"edit|submit|save|scroll|toggle|expand|collapse|upload|download|render)\w*",
    re.IGNORECASE,
)
_IDENTIFIER_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_CAMEL_TOKEN_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z]|$)|[A-Z]?[a-z]+|[0-9]+")
_BACKEND_ACTION_TOKENS = frozenset({
    "activate",
    "archive",
    "create",
    "deactivate",
    "update",
    "patch",
    "delete",
    "seed",
    "reset",
    "insert",
    "upsert",
    "truncate",
    "factory",
    "task",
    "unarchive",
    "verify",
})
_READ_ONLY_TASK_TOKENS = frozenset({
    "find",
    "get",
    "list",
    "load",
    "lookup",
    "query",
    "read",
    "select",
})
_BACKEND_MARKER_TOKENS = frozenset({
    "api",
    "backend",
    "database",
    "db",
    "graphql",
    "mongo",
    "mongodb",
    "orm",
    "prisma",
    "redis",
    "sequelize",
    "server",
    "sql",
})
_BACKEND_ENTITY_TOKENS = frozenset({
    "account",
    "accounts",
    "cart",
    "carts",
    "channel",
    "channels",
    "comment",
    "comments",
    "customer",
    "customers",
    "data",
    "entity",
    "entities",
    "fixture",
    "fixtures",
    "file",
    "files",
    "issue",
    "issues",
    "item",
    "items",
    "order",
    "orders",
    "org",
    "orgs",
    "organization",
    "organizations",
    "permission",
    "permissions",
    "post",
    "posts",
    "product",
    "products",
    "project",
    "projects",
    "repo",
    "repos",
    "repository",
    "repositories",
    "record",
    "records",
    "role",
    "roles",
    "tenant",
    "tenants",
    "team",
    "teams",
    "todo",
    "todos",
    "bot",
    "bots",
    "user",
    "users",
    "workspace",
    "workspaces",
})
_UI_OBJECT_TOKENS = frozenset({
    "button",
    "component",
    "components",
    "dialog",
    "element",
    "form",
    "locator",
    "modal",
    "page",
    "pages",
    "screen",
    "screens",
    "tab",
    "view",
    "views",
})
_EXPLICIT_NETWORK_MOCK_RE = re.compile(
    r"\b(cy\.intercept|page\.route|browsercontext\.route|route\.fulfill|"
    r"requestmock|browser\.mock|nock|msw|requestlogger)\b",
    re.IGNORECASE,
)
_NETWORK_MOCK_RE = re.compile(
    r"\b(intercept|route|fulfill|mock|stub|spy|callsfake|nock|msw|requestlogger)\b",
    re.IGNORECASE,
)
_NETWORK_CONTEXT_TOKENS = frozenset({
    "api",
    "fetch",
    "fulfill",
    "http",
    "intercept",
    "msw",
    "network",
    "nock",
    "request",
    "requestlogger",
    "requestmock",
    "response",
    "route",
    "xhr",
})
_NETWORK_MOCK_CLEANUP_TERMINALS = frozenset({
    "cleanall",
    "clearallmocks",
    "clearroutes",
    "mockclear",
    "mockreset",
    "mockrestore",
    "resetallmocks",
    "resethandlers",
    "restoreallmocks",
    "unroute",
    "unrouteall",
})
_NETWORK_MOCK_CLEANUP_CONTEXTS = frozenset({
    "browsercontext",
    "context",
    "jest",
    "mock",
    "mocks",
    "nock",
    "page",
    "server",
    "sinon",
    "spy",
    "stub",
    "vi",
    "worker",
})
_WAIT_SLEEP_ONLY_RE = re.compile(
    r"^\s*(?:await\s+)?(?:"
    r"cy\.(?:wait|waituntil)|page\.(?:waitfortimeout|waitforselector|waitforevent)|locator\.waitfor|"
    r"t\.wait|browser\.(?:pause|waituntil)|"
    r"wait|waituntil|waitforselector|waitforevent|sleep|delay|pause|settimeout"
    r")\s*\(",
    re.IGNORECASE,
)
_CYPRESS_QUERY_THEN_WRAPPER_RE = re.compile(
    r"^\s*(?:cy\.)?(?:url|location|title)\s*\([^)]*\)\s*\.then\s*\(",
    re.IGNORECASE,
)
_LOCATOR_QUERY_ONLY_RE = re.compile(
    r"\b(?:"
    r"(?:page|locator|frame|iframe|canvas|dialog|modal|[^.\s]+page)\."
    r"(?:locator|getbyrole|getbytext|getbylabel|getbyplaceholder|getbytestid|getbytitle|getbyalttext)\s*\("
    r"|(?:cy\.)?get\s*\([^)]*\)\s*\.shadow\s*\("
    r"|(?:cy\.)?get\s*\([^)]*\)\s*\.(?:eq|first|last|find|filter|children|parent|parents|siblings|next|prev)\s*\("
    r"|\.shadow\s*\("
    r"|\.locator\s*\([^)]*\)\s*\.waitfor\s*\("
    r"|\.waitfor\s*\(\s*\{[^}]*\bstate\s*:"
    r")",
    re.IGNORECASE,
)
_LOAD_STATE_WAIT_RE = re.compile(r"\bwaitforloadstate\s*\(", re.IGNORECASE)
_BARE_CONTEXT_ACCESS_RE = re.compile(
    r"^\s*(?:await\s+)?(?:page|browser|context|[^.\s]+page)\.context\s*\(\s*\)\s*$",
    re.IGNORECASE,
)
_READ_ONLY_CONTEXT_QUERY_RE = re.compile(
    r"^\s*(?:await\s+)?(?:page|browser|context|[^.\s]+page)\.context\s*\(\s*\)\."
    r"(?:(?:cookies|storageState)\s*\(\s*\)|waitForEvent\s*\([^)]*\))\s*$",
    re.IGNORECASE,
)
_COOKIE_TEST_DATA_RE = re.compile(
    r"\bsetcookie\s*\([^)]*(?:seed|fixture|testdata|test_data|mock|dataset)",
    re.IGNORECASE,
)
_UTILITY_CHAIN_ONLY_RE = re.compile(
    r"\b(?:cy\.)?(?:then|wrap|as|log|debug|print|screenshot|snapshot|stub|spy)\s*\("
    r"|\.then\s*\(|\.as\s*\(",
    re.IGNORECASE,
)
_AUTH_COOKIE_CONTEXT_RE = re.compile(
    r"\b(?:getcookie|setcookie|cookie|cookies)\b[^;\n]*(?:token|session|auth|login|userid|csrf|xsrf|jwt|bearer|mmuserid|mmcsrf)",
    re.IGNORECASE,
)
_DOM_MUTATION_UTILITY_RE = re.compile(
    r"\b(?:document\.createelement|createelement|setattribute|appendchild|innerhtml)\b",
    re.IGNORECASE,
)
_UI_CLEAR_OR_FOCUS_CHAIN_RE = re.compile(
    r"\b(?:cy\.)?get\s*\([^)]*\)[^;\n]*(?:\.clear\s*\(|\.focus\s*\()",
    re.IGNORECASE,
)
_ASSERTION_OR_REPORTING_TEXT_RE = re.compile(
    r"\b(expect|assert|should|report|requestcount|console\.|logger\.|testlogger\.)\b",
    re.IGNORECASE,
)
_TIME_DEVICE_PERMISSION_RE = re.compile(
    r"\b(grantpermissions?|setpermissions?|permissions?|geolocation|viewport|timezone|locale|clock|tick)\b",
    re.IGNORECASE,
)
_COOKIE_STORAGE_RE = re.compile(r"\b(getcookie|setcookie|addcookies?|clearcookies?|localstorage|sessionstorage|storagestate)\b", re.IGNORECASE)

_INTENT_CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}

_API_CATEGORY_TO_INTENT = {
    "auth_session": "auth_session_state",
    "network_mock": "network_mock_or_spy",
    "test_data_api": "test_data_or_backend_state",
    "test_data_fixture": "test_data_or_backend_state",
    "backend_task": "test_data_or_backend_state",
    "navigation": "navigation_bootstrap",
    "cleanup": "cleanup_restore_state",
    "time_device_emulation": "time_device_permission_emulation",
    "browser_context_control": "browser_context_or_client_state",
    "setup_utility": "generic_setup_teardown_utility",
}

_DATA_DOMAIN_API_CATEGORIES = frozenset({"test_data_api", "test_data_fixture", "backend_task"})
_COOKIE_CLEANUP_TERMINALS = frozenset({
    "clearcookie",
    "clearcookies",
    "deletecookie",
    "deletecookies",
    "clearlocalstorage",
})
_MUTATING_REQUEST_METHODS = frozenset({"post", "put", "patch", "delete", "del"})
_CLEANUP_REQUEST_METHODS = frozenset({"delete", "del"})
_AST_CYPRESS_STATEFUL_METHODS = frozenset({
    "session",
    "request",
    "task",
    "fixture",
    "intercept",
    "setcookie",
    "getcookie",
    "clearcookie",
    "clearcookies",
    "clearlocalstorage",
})
_AST_PAGE_STATEFUL_METHODS = frozenset({"route", "request", "goto"})
_AST_BROWSER_CONTEXT_METHODS = frozenset({"route", "newcdpsession", "storageState".lower()})
_AST_STORAGE_OBJECTS = frozenset({"localstorage", "sessionstorage"})
_AST_STORAGE_MUTATION_METHODS = frozenset({"setitem", "removeitem", "clear"})
_AST_STORAGE_CLEANUP_METHODS = frozenset({"removeitem", "clear"})
_AST_LOCATOR_QUERY_METHODS = frozenset({
    "get",
    "locator",
    "getbyrole",
    "getbytext",
    "getbylabel",
    "getbyplaceholder",
    "getbytestid",
    "getbytitle",
    "getbyalttext",
    "shadow",
    "eq",
    "first",
    "last",
    "find",
    "filter",
    "children",
    "parent",
    "parents",
    "siblings",
    "next",
    "prev",
    "waitfor",
})
_AST_UI_ACTION_METHODS = frozenset({
    "click",
    "dblclick",
    "type",
    "fill",
    "press",
    "select",
    "selectoption",
    "check",
    "uncheck",
    "hover",
    "drag",
    "dragto",
    "trigger",
    "clear",
    "focus",
})
_AST_UTILITY_METHODS = frozenset({
    "then",
    "wrap",
    "as",
    "log",
    "debug",
    "print",
    "screenshot",
    "snapshot",
    "stub",
    "spy",
})
_AST_DOM_MUTATION_METHODS = frozenset({
    "createelement",
    "setattribute",
    "appendchild",
})
_AST_AUTH_FRAGMENTS = frozenset({
    "auth",
    "authenticate",
    "authorization",
    "bearer",
    "csrf",
    "jwt",
    "login",
    "logout",
    "mmcsrf",
    "mmuserid",
    "session",
    "signin",
    "signout",
    "token",
    "userid",
    "xsrf",
})
_AST_BACKEND_ACTION_FRAGMENTS = frozenset({
    "activate",
    "archive",
    "cleanup",
    "create",
    "delete",
    "drop",
    "factory",
    "insert",
    "patch",
    "remove",
    "reset",
    "restore",
    "seed",
    "task",
    "truncate",
    "unarchive",
    "update",
    "upsert",
    "verify",
})
_AST_CLEANUP_ACTION_FRAGMENTS = frozenset({
    "cleanup",
    "clear",
    "close",
    "delete",
    "drop",
    "remove",
    "reset",
    "restore",
    "teardown",
    "truncate",
})
_AST_BACKEND_MUTATION_FRAGMENTS = frozenset({
    "activate",
    "archive",
    "create",
    "deactivate",
    "factory",
    "insert",
    "patch",
    "promote",
    "seed",
    "task",
    "unarchive",
    "update",
    "upsert",
    "verify",
})
_AST_TEST_DATA_LITERAL_FRAGMENTS = frozenset({
    "dataset",
    "fixture",
    "mock",
    "seed",
    "testdata",
    "test_data",
})
_AST_TIME_DEVICE_FRAGMENTS = frozenset({
    "clock",
    "geolocation",
    "locale",
    "permission",
    "permissions",
    "timezone",
    "tick",
    "viewport",
})

_STRUCTURED_SETUP_API_CATEGORIES = frozenset({
    "auth_session",
    "network_mock",
    "test_data_api",
    "test_data_fixture",
    "backend_task",
    "time_device_emulation",
    "browser_context_control",
    "cleanup",
})
_STRUCTURED_NAVIGATION_API_CATEGORIES = frozenset({"navigation"})
_STRUCTURED_PHASE_HINT_BASES = frozenset({
    "ast_known_framework_api",
    "ast_nested_framework_api",
    "mixed_structured_framework_api",
})
_TRUSTED_HELPER_EXPANSION_BASES = frozenset({
    "class_method_type",
    "cypress_registry",
    "exact_symbol",
    "namespace_import",
})
_CYPRESS_TASK_DIAGNOSTIC_COMMANDS = frozenset({
    "debug",
    "error",
    "info",
    "log",
    "logger",
    "print",
    "table",
    "trace",
    "warn",
})
_AST_READ_ONLY_TERMINALS = frozenset({
    "browser",
    "browsername",
    "browsertype",
    "cookies",
    "getcookie",
    "getcookies",
    "getlocalstorage",
    "getsessionstorage",
    "name",
    "title",
    "url",
})
_AST_RUNTIME_LIFECYCLE_TERMINALS = frozenset({
    "useeffect",
    "useisomorphiclayouteffect",
    "uselayouteffect",
    "usememo",
})
_AST_WAIT_TERMINALS = frozenset({
    "delay",
    "pause",
    "sleep",
    "wait",
    "waitfor",
    "waitforevent",
    "waitforfunction",
    "waitforloadstate",
    "waitforrequest",
    "waitforresponse",
    "waitforselector",
    "waitfortimeout",
    "waituntil",
})
_AST_VALUE_CONSTRUCTION_ROOTS = frozenset({
    "buffer",
    "string",
    "textdecoder",
    "textencoder",
    "url",
    "urlsearchparams",
})
_AST_VALUE_CONSTRUCTION_TERMINALS = frozenset({
    "encode",
    "encodeuri",
    "encodeuricomponent",
    "from",
    "parse",
    "stringify",
    "tobuffer",
    "tojson",
    "tostring",
})


def load_taxonomy() -> Dict[str, Any]:
    return json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))


def _s(feature: Dict[str, Any], key: str) -> str:
    return str(feature.get(key) or "").strip()


def _line(feature: Dict[str, Any]) -> int:
    try:
        return int(feature.get("line") or 0)
    except (TypeError, ValueError):
        return 0


def _json_list_field(feature: Dict[str, Any], key: str) -> List[str]:
    value = feature.get(key)
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item).strip() for item in parsed if str(item).strip()]


def _callee_chain(feature: Dict[str, Any]) -> Tuple[str, ...]:
    return tuple(item.lower() for item in _json_list_field(feature, "callee_chain_json"))


def _literal_args(feature: Dict[str, Any]) -> Tuple[str, ...]:
    return tuple(item.lower() for item in _json_list_field(feature, "literal_args_json"))


def _has_structured_callee_chain(feature: Dict[str, Any]) -> bool:
    return bool(_callee_chain(feature))


def _has_lifecycle_callsite_context(feature: Dict[str, Any]) -> bool:
    sk = _s(feature, "source_kind")
    depth = int(feature.get("helper_depth") or 0)
    return bool(
        sk in HOOK_SOURCE_KINDS
        or (sk == "test_body" and depth == 0)
        or feature.get("attached_from_hook")
        or _s(feature, "hook_instance_key")
    )


def _trusted_helper_expansion_evidence(feature: Dict[str, Any]) -> bool:
    basis = _s(feature, "helper_expansion_evidence_basis")
    if not basis:
        return True
    return basis in _TRUSTED_HELPER_EXPANSION_BASES


def _has_structured_helper_setup_signal(feature: Dict[str, Any]) -> bool:
    api_cat = _s(feature, "framework_api_category")
    if api_cat and api_cat not in {"unknown", "navigation"} and _framework_api_category_is_structured(feature):
        return True
    role = _s(feature, "cypress_command_role_ast")
    if role in ("session_setup", "test_data_setup", "setup_or_state_flow") and _cypress_command_role_is_structured(feature):
        return True
    structured_intent, _ = _structured_chain_primary_intent(feature)
    if structured_intent and structured_intent != "navigation_bootstrap":
        return True
    if int(feature.get("child_setup_unit_count") or 0) > 0 and _helper_child_intent_is_trusted(feature, feature):
        return True
    return bool(
        _trusted_helper_expansion_evidence(feature) and
        _helper_body_phase_hint(feature, feature)
        and _phase_hint_basis_is_structured(_s(feature, "helper_body_phase_hint_basis_ast"))
    )


def _structured_framework_category(feature: Dict[str, Any]) -> str:
    if _is_read_only_ast_call(feature) or _is_runtime_lifecycle_call(feature):
        return ""
    api_cat = _s(feature, "framework_api_category")
    if api_cat == "backend_task" and _is_cypress_task_call(feature) and not _is_setup_cypress_task(feature):
        return ""
    if (
        api_cat
        and api_cat != "unknown"
        and _framework_api_category_is_structured(feature)
    ):
        return api_cat
    return _exact_known_framework_api_category(feature)


def _has_structured_framework_setup_category(feature: Dict[str, Any]) -> bool:
    return _structured_framework_category(feature) in _STRUCTURED_SETUP_API_CATEGORIES


def _has_structured_navigation_category(feature: Dict[str, Any]) -> bool:
    return _structured_framework_category(feature) in _STRUCTURED_NAVIGATION_API_CATEGORIES


def _has_structured_phase_hint(feature: Dict[str, Any], key: str, basis_key: str) -> bool:
    return bool(_s(feature, key) and _s(feature, basis_key) in _STRUCTURED_PHASE_HINT_BASES)


def _has_structured_helper_body_phase_signal(feature: Dict[str, Any]) -> bool:
    return _trusted_helper_expansion_evidence(feature) and _has_structured_phase_hint(
        feature,
        "helper_body_phase_hint_ast",
        "helper_body_phase_hint_basis_ast",
    )


def _has_structured_statement_phase_signal(feature: Dict[str, Any]) -> bool:
    return _has_structured_phase_hint(
        feature,
        "statement_phase_hint_ast",
        "statement_phase_hint_basis_ast",
    )


def _has_structured_cypress_role_signal(feature: Dict[str, Any]) -> bool:
    role = _s(feature, "cypress_command_role_ast")
    return (
        role in ("session_setup", "test_data_setup", "setup_or_state_flow")
        and _cypress_command_role_is_structured(feature)
    )


def _has_trusted_child_setup_signal(feature: Dict[str, Any]) -> bool:
    return (
        int(feature.get("child_setup_unit_count") or 0) > 0
        and _helper_child_intent_is_trusted(feature, feature)
    )


def _normalized_ast_call_name(feature: Dict[str, Any]) -> str:
    name = _s(feature, "name").lower()
    return name.replace("()", "")


def _is_cypress_task_call(feature: Dict[str, Any]) -> bool:
    chain = _callee_chain(feature)
    if chain and chain[0] == "cy" and chain[-1] == "task":
        return True
    return _normalized_ast_call_name(feature) == "cy.task"


def _cypress_task_command_literal(feature: Dict[str, Any]) -> str:
    literals = _json_list_field(feature, "literal_args_json")
    if literals:
        return literals[0]
    raw = _s(feature, "raw_code")
    match = re.search(r"\bcy\.task\s*\(\s*(['\"])(.*?)\1", raw, re.IGNORECASE)
    return match.group(2) if match else ""


def _is_diagnostic_cypress_task(feature: Dict[str, Any]) -> bool:
    if not _is_cypress_task_call(feature):
        return False
    command = _cypress_task_command_literal(feature).strip().lower()
    if not command:
        return False
    tokens = set(_identifier_tokens(command))
    return command in _CYPRESS_TASK_DIAGNOSTIC_COMMANDS or bool(
        tokens and tokens <= _CYPRESS_TASK_DIAGNOSTIC_COMMANDS
    )


def _is_read_only_cypress_task(feature: Dict[str, Any]) -> bool:
    task_text = f"{_s(feature, 'name')} {_s(feature, 'raw_code')}"
    if not (_is_cypress_task_call(feature) or re.search(r"\bcy\.task\s*\(", task_text, re.I)):
        return False
    if _cypress_task_role_is_structured(feature):
        return False
    command = _cypress_task_command_literal(feature).strip()
    if not command:
        return False
    tokens = set(_identifier_tokens(command))
    if tokens & (_BACKEND_ACTION_TOKENS | _AST_CLEANUP_ACTION_FRAGMENTS | _AST_BACKEND_MUTATION_FRAGMENTS):
        return False
    return bool(tokens & _READ_ONLY_TASK_TOKENS)


def _is_setup_cypress_task(feature: Dict[str, Any]) -> bool:
    if not _is_cypress_task_call(feature) or _is_diagnostic_cypress_task(feature):
        return False
    return _cypress_task_role_is_structured(feature)


def _is_read_only_ast_call(feature: Dict[str, Any]) -> bool:
    chain = _callee_chain(feature)
    terminal = chain[-1] if chain else _normalized_ast_call_name(feature).rsplit(".", 1)[-1]
    if terminal in _AST_READ_ONLY_TERMINALS:
        return True
    if len(chain) >= 2 and chain[-2:] in {
        ("browsertype", "name"),
        ("context", "browser"),
    }:
        return True
    return False


def _is_runtime_lifecycle_call(feature: Dict[str, Any]) -> bool:
    chain = _callee_chain(feature)
    terminal = chain[-1] if chain else _normalized_ast_call_name(feature).rsplit(".", 1)[-1]
    return terminal in _AST_RUNTIME_LIFECYCLE_TERMINALS


def _is_wait_synchronization_feature(feature: Dict[str, Any], name: str, raw: str) -> bool:
    if _s(feature, "feature_type").lower() == "wait_synchronization":
        return True
    chain = _callee_chain(feature)
    terminal = chain[-1] if chain else _normalized_ast_call_name(feature).rsplit(".", 1)[-1]
    if terminal in _AST_WAIT_TERMINALS:
        return True
    return _is_wait_or_load_state_only_text(name, raw)


def _is_direct_cypress_fixture_load(feature: Dict[str, Any]) -> bool:
    chain = _callee_chain(feature)
    if chain and chain[0] == "cy" and "fixture" in chain:
        return True
    return _normalized_ast_call_name(feature) == "cy.fixture"


def _is_fixture_only_load(feature: Dict[str, Any]) -> bool:
    src = _input_source_class(feature)
    api_cat = _s(feature, "framework_api_category")
    if api_cat in {"network_mock", "test_data_api", "backend_task", "auth_session", "cleanup"}:
        return False
    if _has_trusted_child_setup_signal(feature):
        return False
    return bool(src == "fixture_file_input" or api_cat == "test_data_fixture" or _is_direct_cypress_fixture_load(feature))


def _is_value_construction_utility(feature: Dict[str, Any], name: str, raw: str) -> bool:
    chain = _callee_chain(feature)
    if chain:
        first = chain[0]
        terminal = chain[-1]
        if first in _AST_VALUE_CONSTRUCTION_ROOTS and terminal in _AST_VALUE_CONSTRUCTION_TERMINALS:
            return True
        if len(chain) >= 2 and chain[-2:] in {("buffer", "from"), ("json", "parse"), ("json", "stringify")}:
            return True
        return False
    compact_name = _normalized_ast_call_name(feature)
    if compact_name.startswith("buffer.from") or compact_name.startswith("json.parse") or compact_name.startswith("json.stringify"):
        return True
    return False


def _exact_known_framework_api_category(feature: Dict[str, Any]) -> str:
    """Known framework API from AST call shape/name, not free-text scanning."""
    chain = _callee_chain(feature)
    if chain:
        first = chain[0]
        terminal = chain[-1]
        chain_tuple = tuple(chain)
        if first == "cy":
            if terminal == "intercept":
                return "network_mock"
            if terminal == "session":
                return "auth_session"
            if terminal == "request":
                return "test_data_api"
            if terminal == "task":
                if not _is_setup_cypress_task(feature):
                    return ""
                return "backend_task"
            if terminal == "fixture":
                return ""
            if terminal in {"clock", "tick", "viewport"}:
                return "time_device_emulation"
            if terminal in {"clearcookie", "clearcookies", "clearlocalstorage"}:
                return "cleanup"
            if terminal == "setcookie":
                return "browser_context_control"
            if terminal == "visit":
                return "navigation"
        if first in {"context", "browsercontext", "page", "browser", "t", "testcontroller"}:
            if terminal in _COOKIE_CLEANUP_TERMINALS:
                return "cleanup"
        if first in {"page", "browsercontext", "context"} and terminal == "route":
            return "network_mock"
        if first == "route" and terminal == "fulfill":
            return "network_mock"
        if first in {"page", "apirequestcontext"} and terminal == "request":
            return "test_data_api"
        if terminal == "storagestate" and (
            first in {"page", "browsercontext", "context"} or "context" in chain_tuple
        ):
            return "auth_session"
        if terminal in _AST_STORAGE_MUTATION_METHODS and any(part in _AST_STORAGE_OBJECTS for part in chain_tuple):
            return "browser_context_control"
        if terminal == "userole" and first in {"t", "testcontroller"}:
            return "auth_session"
        if first == "page" and terminal == "goto":
            return "navigation"

    name = _normalized_ast_call_name(feature)
    exact = {
        "cy.intercept": "network_mock",
        "page.route": "network_mock",
        "browsercontext.route": "network_mock",
        "context.route": "network_mock",
        "route.fulfill": "network_mock",
        "browser.mock": "network_mock",
        "cy.session": "auth_session",
        "page.context.storagestate": "auth_session",
        "browsercontext.storagestate": "auth_session",
        "context.storagestate": "auth_session",
        "cy.request": "test_data_api",
        "page.request": "test_data_api",
        "cy.task": "backend_task" if _is_setup_cypress_task(feature) else "",
        "cy.fixture": "",
        "cy.clock": "time_device_emulation",
        "cy.tick": "time_device_emulation",
        "cy.viewport": "time_device_emulation",
        "cy.clearcookie": "cleanup",
        "cy.clearcookies": "cleanup",
        "cy.clearlocalstorage": "cleanup",
        "context.clearcookies": "cleanup",
        "browsercontext.clearcookies": "cleanup",
        "page.deletecookie": "cleanup",
        "browser.deletecookies": "cleanup",
        "t.deletecookies": "cleanup",
        "cy.setcookie": "browser_context_control",
        "localstorage.setitem": "browser_context_control",
        "sessionstorage.setitem": "browser_context_control",
        "localstorage.removeitem": "browser_context_control",
        "sessionstorage.removeitem": "browser_context_control",
        "localstorage.clear": "browser_context_control",
        "sessionstorage.clear": "browser_context_control",
        "t.userole": "auth_session",
        "page.goto": "navigation",
        "cy.visit": "navigation",
    }
    return exact.get(name, "")


def _structured_known_api_eligibility_basis(feature: Dict[str, Any]) -> str:
    """Positive RQ1 evidence from structured AST/call-graph fields only.

    Deliberately excludes helper-name, arbitrary callee-fragment, and raw-code
    regex matches. Exact framework API categories are allowed because they come
    from parsed AST callee chains emitted by Phase 2B.
    """
    api_cat = _structured_framework_category(feature)
    if api_cat in _STRUCTURED_SETUP_API_CATEGORIES:
        return f"framework_api_category:{api_cat}"
    if _has_structured_cypress_role_signal(feature):
        return f"cypress_command_role:{_s(feature, 'cypress_command_role_ast')}"
    if _cypress_task_role_is_structured(feature):
        return f"cypress_task_role:{_s(feature, 'cypress_task_role_ast')}"
    if _has_structured_statement_phase_signal(feature):
        return "statement_phase_hint_ast"
    if _has_structured_helper_body_phase_signal(feature):
        return "helper_body_phase_hint"
    if _has_trusted_child_setup_signal(feature):
        return "resolved_helper_child_intents"
    return ""


def _terminal_callee(feature: Dict[str, Any]) -> str:
    chain = _callee_chain(feature)
    return chain[-1] if chain else ""


def _chain_has_fragment(chain: Tuple[str, ...], fragments: frozenset[str]) -> bool:
    return any(fragment in part for part in chain for fragment in fragments)


def _literal_args_have_fragment(feature: Dict[str, Any], fragments: frozenset[str]) -> bool:
    return any(fragment in arg for arg in _literal_args(feature) for fragment in fragments)


def _structured_terminal_or_name_has_fragment(feature: Dict[str, Any], fragments: frozenset[str]) -> bool:
    chain = _callee_chain(feature)
    if chain:
        return any(fragment in chain[-1] for fragment in fragments)
    # Name is the AST-emitted call surface; use it only as a fallback when the
    # upstream extractor did not provide enough callee-chain detail.
    compact_name = _normalized_ast_call_name(feature).lower()
    return any(fragment in compact_name for fragment in fragments)


def _request_method_from_text(text: str) -> str:
    m = re.search(r"\bmethod\s*:\s*['\"]?\s*([a-z]+)", text or "", re.IGNORECASE)
    if m:
        return m.group(1).lower()
    m = re.search(r"\bcy\.request\s*\(\s*['\"]\s*(GET|POST|PUT|PATCH|DELETE|DEL)\b", text or "", re.IGNORECASE)
    if m:
        return m.group(1).lower()
    m = re.search(r"\b(?:fetch|axios\.(?:request|post|put|patch|delete|get)|request)\s*\([^)]*\bmethod\s*:\s*['\"]?\s*([a-z]+)", text or "", re.IGNORECASE)
    if m:
        return m.group(1).lower()
    m = re.search(r"\b(?:page\.)?request\.(get|post|put|patch|delete|del)\s*\(", text or "", re.IGNORECASE)
    if m:
        return m.group(1).lower()
    m = re.search(r"\baxios\.(post|put|patch|delete|get)\s*\(", text or "", re.IGNORECASE)
    if m:
        return m.group(1).lower()
    return ""


def _request_target_text(text: str) -> str:
    """Return URL/path-like request target expressions, excluding header/body context."""
    raw = text or ""
    chunks: List[str] = []
    for match in re.finditer(r"\b(?:url|uri|path|endpoint)\s*:\s*([^,\n\r}]+)", raw, re.IGNORECASE):
        chunks.append(match.group(1))
    for match in re.finditer(
        r"\bcy\.request\s*\(\s*(['\"])\s*(?:GET|POST|PUT|PATCH|DELETE|DEL)\s*\1\s*,\s*([^,\n\r)]+)",
        raw,
        re.IGNORECASE,
    ):
        chunks.append(match.group(2))
    for match in re.finditer(r"\b(?:fetch|request)\s*\(\s*([^,\n\r)]+)", raw, re.IGNORECASE):
        chunks.append(match.group(1))
    for match in re.finditer(
        r"\b(?:page\.)?request\.(?:get|post|put|patch|delete|del)\s*\(\s*([^,\n\r)]+)",
        raw,
        re.IGNORECASE,
    ):
        chunks.append(match.group(1))
    for match in re.finditer(
        r"\baxios\.(?:request|get|post|put|patch|delete)\s*\(\s*([^,\n\r)]+)",
        raw,
        re.IGNORECASE,
    ):
        chunks.append(match.group(1))
    return " ".join(chunks).lower()


def _request_target_is_auth_operation(text: str, api_name: str = "") -> bool:
    if api_name and _AUTH_API_NAME_RE.search(api_name):
        return True
    target = _request_target_text(text)
    if not target:
        return False
    return bool(
        _AUTH_FLOW_CONTEXT_RE.search(target)
        or re.search(r"(?:^|[^a-z0-9])token(?:$|[^a-z0-9])", target, re.IGNORECASE)
        or any(fragment in target for fragment in _AST_AUTH_FRAGMENTS)
    )


def _request_text_has_body_payload(text: str) -> bool:
    return bool(
        re.search(r"\b(?:body|data|payload|json)\s*:", text or "", re.IGNORECASE)
        or re.search(r"\bjson\.stringify\s*\(", text or "", re.IGNORECASE)
        or re.search(r"\b(?:post|put|patch)\s*\([^)]*,", text or "", re.IGNORECASE)
    )


def _request_text_is_auth_flow(text: str, api_name: str = "") -> bool:
    lowered = text or ""
    if api_name and _AUTH_API_NAME_RE.search(api_name):
        return True
    if _AUTH_FLOW_CONTEXT_RE.search(lowered):
        return True
    return False


def _request_text_is_auth_operation(text: str, api_name: str = "") -> bool:
    if api_name and _AUTH_API_NAME_RE.search(api_name):
        return True
    return bool(
        re.search(
            r"(?:^|[^a-z0-9])(?:authenticate|login|logout|signin|signout|session|csrf|xsrf|oauth|saml|magiclink|invite|verify)(?:$|[^a-z0-9])",
            text or "",
            re.I,
        )
        or re.search(r"(?:^|[^a-z0-9])token(?:$|[^a-z0-9])", text or "", re.I)
    )


def _request_api_surface_name(feature: Dict[str, Any]) -> str:
    name = _s(feature, "name").lower()
    return re.split(r"[\s(]", name, maxsplit=1)[0]


def _is_request_like_call_text(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:cy\.(?:request|task)|page\.request|fetch\s*\(|axios\.|request\s*\(|"
            r"(?:page\.)?request\.(?:get|post|put|patch|delete|del)\s*\()",
            text or "",
            re.I,
        )
    )


def _is_read_only_request_feature(feature: Dict[str, Any]) -> bool:
    text = f"{_s(feature, 'name')} {_s(feature, 'raw_code')} {' '.join(_literal_args(feature))}".lower()
    if not _is_request_like_call_text(text):
        return False
    name = _normalized_ast_call_name(feature)
    chain = _callee_chain(feature)
    direct_surface = (
        name in {"cy.request", "page.request", "fetch", "request"}
        or name.startswith(("cy.request", "page.request", "fetch(", "request("))
        or bool(chain and "request" in chain[:2])
    )
    if not direct_surface:
        return False
    method = _request_method_from_text(text)
    if method in _MUTATING_REQUEST_METHODS:
        return False
    if _request_text_has_body_payload(text):
        return False
    if _request_text_is_auth_flow(text, _request_api_surface_name(feature)):
        return False
    return True


def _request_text_intent(feature: Dict[str, Any]) -> Tuple[str, str]:
    """Intent override for request-like APIs until Phase 2B emits method/url fields."""
    text = f"{_s(feature, 'name')} {_s(feature, 'raw_code')} {' '.join(_literal_args(feature))}".lower()
    if not text.strip():
        return "", ""
    if _s(feature, "feature_type").lower() == "assertion":
        return "", ""
    if not _is_request_like_call_text(text):
        return "", ""
    method = _request_method_from_text(text)
    api_surface = _request_api_surface_name(feature)
    auth_context = _request_text_is_auth_flow(text, api_surface)
    cleanup_context = bool(
        method in _CLEANUP_REQUEST_METHODS
        or re.search(r"\b(?:delete|drop|reset|cleanup|teardown|restore|remove)\b", text, re.I)
    )
    if method in _MUTATING_REQUEST_METHODS or cleanup_context:
        return "test_data_or_backend_state", "lexical_backend_data_setup"
    if auth_context:
        return "auth_session_state", "lexical_auth_session"
    return "", ""


def _field_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return False


def _request_ast_intent(feature: Dict[str, Any]) -> Tuple[str, str]:
    """Route real request calls by structured Phase 2C method/target fields."""
    method = _s(feature, "request_method_ast").lower()
    domain = _s(feature, "request_target_domain_ast").lower()
    has_body = _field_truthy(feature.get("request_has_body_ast"))
    if not (method or domain or "request_has_body_ast" in feature):
        return "", ""

    basis = "ast_request_target_domain"
    if domain in {"backend_data", "config", "test_data", "entity_data"}:
        return "test_data_or_backend_state", basis
    if method in _MUTATING_REQUEST_METHODS or has_body:
        return "test_data_or_backend_state", basis
    if domain == "auth":
        return "auth_session_state", basis
    return "", ""


def _literal_args_have_auth_target(feature: Dict[str, Any]) -> bool:
    return _literal_args_have_fragment(feature, _AST_AUTH_FRAGMENTS)


def _call_argument_context_text(feature: Dict[str, Any]) -> str:
    parts = list(_literal_args(feature))
    raw = _s(feature, "raw_code")
    for match in re.finditer(r"\(([^()]*)\)", raw):
        parts.append(match.group(1))
    return " ".join(parts).lower()


def _cleanup_target_has_auth_evidence(feature: Dict[str, Any]) -> bool:
    if _literal_args_have_auth_target(feature):
        return True
    target = _call_argument_context_text(feature)
    return bool(
        _AUTH_FLOW_CONTEXT_RE.search(target)
        or re.search(r"(?:^|[^a-z0-9])token(?:$|[^a-z0-9])", target, re.IGNORECASE)
        or any(fragment in target for fragment in _AST_AUTH_FRAGMENTS)
    )


def _structured_cleanup_target_primary_intent(
    feature: Dict[str, Any],
    hints: Dict[str, Any],
) -> Tuple[str, str]:
    """Resolve cleanup-like operations to the state domain they modify.

    This is deliberately limited to structured fields emitted by Phase 2:
    exact framework API category, AST callee chain, literal arguments, and
    trusted helper-child intent summaries. Ambiguous cleanup stays residual.
    """
    merged = {**feature, **hints}
    api_cat = _structured_framework_category(merged)
    chain = _callee_chain(merged)
    terminal = chain[-1] if chain else _normalized_ast_call_name(merged).split(".")[-1]

    child_intent = _s(merged, "dominant_child_intent")
    if (
        child_intent in {
            "auth_session_state",
            "browser_context_or_client_state",
            "test_data_or_backend_state",
            "server_or_external_environment",
        }
        and int(merged.get("child_setup_unit_count") or 0) > 0
        and _helper_child_intent_is_trusted(merged, merged)
        and not _is_mixed_child_intent(merged)
    ):
        return child_intent, "resolved_helper_child_intents"

    if api_cat == "auth_session":
        return "auth_session_state", "ast_framework_api_category"
    if api_cat in _DATA_DOMAIN_API_CATEGORIES:
        return "test_data_or_backend_state", "ast_framework_api_category"

    if terminal in _COOKIE_CLEANUP_TERMINALS or (
        terminal in _AST_STORAGE_MUTATION_METHODS and any(part in _AST_STORAGE_OBJECTS for part in chain)
    ):
        return "browser_context_or_client_state", "ast_callee_name_heuristic"
    if terminal.startswith(("api", "db", "database")) and any(
        fragment in terminal for fragment in _AST_CLEANUP_ACTION_FRAGMENTS
    ):
        return "test_data_or_backend_state", "ast_callee_name_heuristic"

    if api_cat == "browser_context_control":
        return "browser_context_or_client_state", "ast_framework_api_category"
    if api_cat == "cleanup" and _s(merged, "feature_type").lower() == "browser_context_control":
        return "browser_context_or_client_state", "inventory_category:feature_type"
    return "", ""


def classify_operation_kind_detail(
    feature: Dict[str, Any],
    hints: Dict[str, Any],
    *,
    primary_intent: str = "",
    primary_intent_basis: str = "",
) -> Tuple[str, str]:
    """Return the action kind independently from the target-domain intent.

    Primary intent answers which state domain is manipulated. This field keeps
    reset/cleanup semantics available for paper claims such as setup-vs-teardown
    placement even when cleanup targets auth, browser context, or backend data.
    """
    if primary_intent == "cleanup_restore_state":
        return "cleanup_restore", primary_intent_basis or "primary_intent_cleanup"

    merged = {**feature, **hints}
    api_cat = _structured_framework_category(merged)
    if api_cat == "cleanup":
        return "cleanup_restore", "ast_framework_api_category"

    chain = _callee_chain(merged)
    terminal = chain[-1] if chain else _normalized_ast_call_name(merged).split(".")[-1]
    if primary_intent == "network_mock_or_spy":
        if _is_network_mock_cleanup_operation(merged, terminal, chain):
            return "cleanup_restore", "ast_callee_name_heuristic"
        return "other_setup_teardown", "not_cleanup_restore"
    if terminal in _COOKIE_CLEANUP_TERMINALS:
        return "cleanup_restore", "ast_callee_name_heuristic"
    if terminal in _AST_STORAGE_CLEANUP_METHODS and any(part in _AST_STORAGE_OBJECTS for part in chain):
        return "cleanup_restore", "ast_callee_name_heuristic"
    if _structured_terminal_or_name_has_fragment(merged, _AST_CLEANUP_ACTION_FRAGMENTS):
        return "cleanup_restore", "ast_callee_name_heuristic"

    request_intent, request_basis = _request_text_intent(merged)
    if request_intent == "cleanup_restore_state":
        return "cleanup_restore", request_basis

    text = f"{_s(feature, 'name')} {_s(feature, 'raw_code')}"
    if _has_strong_cleanup_api(text) or _CLEANUP_RE.search(text):
        return "cleanup_restore", "lexical_cleanup"

    return "other_setup_teardown", "not_cleanup_restore"


def _is_network_mock_cleanup_operation(
    feature: Dict[str, Any],
    terminal: str,
    chain: Tuple[str, ...],
) -> bool:
    """Recognize cleanup of mock infrastructure without treating mocked DELETE routes as cleanup."""
    parts = chain or tuple(part for part in _normalized_ast_call_name(feature).split(".") if part)
    if terminal in _NETWORK_MOCK_CLEANUP_TERMINALS:
        return True
    if terminal in {"clear", "reset", "restore"}:
        return bool(set(parts[:-1]) & _NETWORK_MOCK_CLEANUP_CONTEXTS)
    return False


def _tokenized_auth_navigation_text(name: str, raw: str) -> bool:
    text = f"{name} {raw}"
    return bool(_TOKENIZED_AUTH_NAVIGATION_RE.search(text))


def _inline_wrapper_child_intent_signal(feature: Dict[str, Any]) -> Tuple[str, str]:
    ft = _s(feature, "feature_type").lower()
    if ft not in {"cypress_test_utility", "custom_command_call", "helper_call", "setup"}:
        return "", ""
    original_text = f"{_s(feature, 'name')} {_s(feature, 'raw_code')}"
    text = original_text.lower()
    if ".then" not in text and "=>" not in text and "function" not in text:
        return "", ""
    tokens = set(_identifier_tokens(original_text))
    if _EXPLICIT_NETWORK_MOCK_RE.search(text) or (
        "mock" in tokens and tokens & {"api", "event", "events", "polling", "request", "response", "server"}
    ):
        return "network_mock_or_spy", "lexical_network_mock"
    if _request_text_intent(feature)[0] == "cleanup_restore_state":
        return "cleanup_restore_state", "lexical_cleanup"
    if (
        "postmessageas" in text
        or "headlesscreate" in text
        or (tokens & _AST_BACKEND_MUTATION_FRAGMENTS and tokens & {"api", "client", "db", "message", "post", "task"})
        or re.search(r"\bcy\.(?:request|task)\s*\([^)]*\b(?:post|put|patch|create|seed|promote)\b", text, re.I)
    ):
        return "test_data_or_backend_state", "lexical_backend_data_setup"
    return "", ""


def _is_lodash_times_iteration(feature: Dict[str, Any]) -> bool:
    chain = _callee_chain(feature)
    if chain and len(chain) >= 2 and chain[-1] == "times" and ("_" in chain or "cypress" in chain):
        return True
    text = f"{_s(feature, 'name')} {_s(feature, 'raw_code')}".lower()
    return "cypress._.times" in text or "cypress._[\"times\"]" in text or "cypress._['times']" in text


def _is_headless_backend_creation_call(feature: Dict[str, Any]) -> bool:
    text = f"{_s(feature, 'name')} {_s(feature, 'raw_code')}".lower()
    return "headlesscreate" in text


def _is_direct_time_device_operation(feature: Dict[str, Any]) -> bool:
    chain = _callee_chain(feature)
    if len(chain) >= 2:
        if chain[0] == "cy" and chain[1] in {"clock", "tick", "viewport"}:
            return True
        if chain[0] in {"page", "context", "browsercontext", "browser"} and chain[1] in {
            "setviewport",
            "setviewportsize",
            "grantpermissions",
            "clearpermissions",
            "setgeolocation",
        }:
            return True
    call_name = _normalized_ast_call_name(feature)
    return bool(
        call_name.startswith(("cy.clock", "cy.tick", "cy.viewport"))
        or call_name.startswith(
            (
                "page.setviewport",
                "page.setviewportsize",
                "context.grantpermissions",
                "context.clearpermissions",
                "context.setgeolocation",
                "browsercontext.grantpermissions",
                "browsercontext.clearpermissions",
                "browsercontext.setgeolocation",
            )
        )
    )


def _structured_chain_primary_intent(feature: Dict[str, Any]) -> Tuple[str, str]:
    chain = _callee_chain(feature)
    if not chain:
        if _s(feature, "feature_type").lower() not in {
            "browser_context_control",
            "custom_command_call",
            "cypress_test_utility",
            "network_mock",
            "setup",
            "teardown",
        }:
            return "", ""
        if _structured_terminal_or_name_has_fragment(feature, _AST_CLEANUP_ACTION_FRAGMENTS):
            return "cleanup_restore_state", "ast_callee_name_heuristic"
        if _structured_terminal_or_name_has_fragment(feature, _AST_AUTH_FRAGMENTS):
            return "auth_session_state", "ast_callee_name_heuristic"
        if _structured_terminal_or_name_has_fragment(feature, _AST_BACKEND_MUTATION_FRAGMENTS):
            return "test_data_or_backend_state", "ast_callee_name_heuristic"
        return "", ""
    terminal = chain[-1]
    first = chain[0]
    chain_set = set(chain)

    if first == "cy" and terminal in {"intercept"}:
        return "network_mock_or_spy", "ast_callee_name_heuristic"
    if first in {"page", "browsercontext", "context", "route"} and terminal == "route":
        return "network_mock_or_spy", "ast_callee_name_heuristic"
    if terminal in {"requestmock", "mock", "nock"}:
        return "network_mock_or_spy", "ast_callee_name_heuristic"
    if _is_network_mock_cleanup_operation(feature, terminal, chain):
        return "network_mock_or_spy", "ast_callee_name_heuristic"

    if first == "cy" and terminal in {"session"}:
        return "auth_session_state", "ast_callee_name_heuristic"
    if terminal == "userole" or (first == "t" and terminal == "userole"):
        return "auth_session_state", "ast_callee_name_heuristic"
    if terminal == "storagestate":
        return "auth_session_state", "ast_callee_name_heuristic"
    if terminal in {"getcookie", "setcookie"}:
        if terminal == "getcookie":
            return "", ""
        return "browser_context_or_client_state", "ast_callee_name_heuristic"
    if terminal in _AST_STORAGE_MUTATION_METHODS and any(part in _AST_STORAGE_OBJECTS for part in chain):
        return "browser_context_or_client_state", "ast_callee_name_heuristic"

    if terminal in {"clearcookie", "clearcookies", "clearlocalstorage"}:
        return "cleanup_restore_state", "ast_callee_name_heuristic"
    if terminal == "newcdpsession" or "cdpsession" in terminal:
        return "browser_context_or_client_state", "ast_callee_name_heuristic"
    if _is_headless_backend_creation_call(feature):
        return "test_data_or_backend_state", "lexical_backend_data_setup"

    if terminal in {"request", "task"} and ("cy" in chain_set or "page" in chain_set):
        request_intent, request_basis = _request_text_intent(feature)
        if request_intent:
            return request_intent, request_basis
        return "test_data_or_backend_state", "ast_callee_name_heuristic"
    if first == "cy" and terminal == "fixture":
        return "test_data_or_backend_state", "ast_callee_name_heuristic"
    if terminal.startswith(("api", "db", "database")):
        if any(fragment in terminal for fragment in _AST_CLEANUP_ACTION_FRAGMENTS):
            return "cleanup_restore_state", "ast_callee_name_heuristic"
        if any(fragment in terminal for fragment in _AST_AUTH_FRAGMENTS):
            return "auth_session_state", "ast_callee_name_heuristic"
        if any(fragment in terminal for fragment in _AST_BACKEND_MUTATION_FRAGMENTS):
            return "test_data_or_backend_state", "ast_callee_name_heuristic"
    if _structured_terminal_or_name_has_fragment(feature, _AST_CLEANUP_ACTION_FRAGMENTS):
        return "cleanup_restore_state", "ast_callee_name_heuristic"
    if _structured_terminal_or_name_has_fragment(feature, _AST_AUTH_FRAGMENTS):
        return "auth_session_state", "ast_callee_name_heuristic"
    if _structured_terminal_or_name_has_fragment(feature, _AST_BACKEND_MUTATION_FRAGMENTS):
        return "test_data_or_backend_state", "ast_callee_name_heuristic"

    if any(fragment in terminal for fragment in _AST_TIME_DEVICE_FRAGMENTS):
        return "time_device_permission_emulation", "ast_callee_name_heuristic"
    if first == "page" and terminal == "goto":
        if _tokenized_auth_navigation_text(_s(feature, "name"), _s(feature, "raw_code")):
            return "auth_session_state", "lexical_auth_session"
        return "navigation_bootstrap", "ast_callee_name_heuristic"
    return "", ""


def is_eligible_setup_teardown_unit(feature: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Return (eligible, eligibility_basis).

    Semantic units are a subset of lifecycle-relevant features; ordinary workflow
    UI actions and assertions are excluded unless navigation-bootstrap candidates.
    """
    ft = _s(feature, "feature_type").lower()
    sk = _s(feature, "source_kind")
    name = _s(feature, "name")
    raw = _s(feature, "raw_code")
    depth = int(feature.get("helper_depth") or 0)
    text = f"{name} {raw}"

    if _is_wait_synchronization_feature(feature, name, raw):
        return False, "excluded_wait_sleep_only"

    if _is_fixture_only_load(feature):
        return False, "excluded_fixture_only_load"

    if _is_value_construction_utility(feature, name, raw):
        return False, "excluded_value_construction_utility"

    if _is_ui_clear_or_focus_chain(name, raw, feature):
        return False, "excluded_ui_focus_clear_chain"

    if _is_logger_only_call(name, raw):
        return False, "excluded_logger_only"

    if _is_visual_audit_helper_call(name, raw):
        return False, "excluded_visual_audit_helper"

    if _is_event_listener_helper_call(name, raw):
        return False, "excluded_event_listener_helper"

    if _is_bare_context_access(name, raw):
        return False, "excluded_bare_context_access"
    if _is_read_only_context_query(name, raw):
        return False, "excluded_read_only_context_query"
    if _is_read_only_ast_call(feature):
        return False, "excluded_read_only_inspection"
    if _is_runtime_lifecycle_call(feature):
        return False, "excluded_runtime_lifecycle_code"
    if _is_diagnostic_cypress_task(feature):
        return False, "excluded_diagnostic_cypress_task"
    if _is_read_only_cypress_task(feature):
        return False, "excluded_read_only_cypress_task"
    if _is_cypress_query_then_wrapper(name, raw):
        return False, "excluded_cypress_query_then_wrapper"

    if _is_locator_query_only_call(feature, name, raw):
        return False, "excluded_locator_query_only"

    if ft == "assertion":
        return False, "excluded_assertion"

    if _is_read_only_request_feature(feature):
        return False, "excluded_read_only_request"

    request_intent, _ = _request_text_intent(feature)
    if request_intent and ft != "helper_call":
        return True, "lexical_request_method_or_auth_context"

    if ft == "ui_action":
        if (
            sk in _HELPER_IMPLEMENTATION_SOURCE_KINDS
            and not _has_lifecycle_callsite_context(feature)
            and (feature.get("navigation_bootstrap_candidate_ast") or _has_structured_navigation_category(feature))
        ):
            return False, "excluded_helper_navigation_without_lifecycle_context"
        if feature.get("navigation_bootstrap_candidate_ast") or _has_structured_navigation_category(feature):
            return True, "navigation_bootstrap_ast"
        return False, "excluded_ordinary_ui_action"

    if ft == "input":
        if not _is_input_load_site(feature):
            return False, "excluded_input_consumer"
        src = _input_source_class(feature)
        if src in _STATIC_FILE_INPUT_CLASSES:
            return True, f"input_source_class:{src}"
        return False, "excluded_unstructured_input_load_site"

    if ft in SETUP_ELIGIBLE_FEATURE_TYPES:
        basis = _structured_known_api_eligibility_basis(feature)
        if basis:
            return True, basis
        return False, f"excluded_unstructured_feature_type:{ft}"

    if ft == "control":
        basis = _structured_known_api_eligibility_basis(feature)
        if basis:
            return True, basis
        return False, "excluded_utility_control"

    if _is_cypress_utility_only_without_state(feature, name, raw):
        return False, "excluded_cypress_utility_only"

    structured_basis = _structured_known_api_eligibility_basis(feature)
    if structured_basis and ft not in ("helper_call", "custom_command_call", "cypress_test_utility"):
        return True, structured_basis

    if (
        ft in ("helper_call", "custom_command_call")
        and sk in _HELPER_IMPLEMENTATION_SOURCE_KINDS
        and not _has_lifecycle_callsite_context(feature)
    ):
        return False, "excluded_helper_implementation_without_lifecycle_context"

    if ft in ("helper_call", "custom_command_call") and _is_ordinary_workflow_helper_without_setup_signal(feature, name, raw):
        return False, "excluded_ordinary_workflow_helper"

    if ft == "helper_call" and _is_verification_helper_without_setup_signal(feature, name, raw):
        return False, "excluded_verification_helper"

    if sk in HOOK_SOURCE_KINDS:
        basis = _structured_known_api_eligibility_basis(feature)
        if not basis:
            return False, "excluded_hook_utility_without_setup_signal"
        return True, f"hook_source_kind:{sk}:{basis}"

    if ft == "page_object_ctor":
        basis = _structured_known_api_eligibility_basis(feature)
        if basis:
            return True, basis
        return False, "excluded_page_object_ctor_without_structured_setup_signal"

    structured_intent, structured_basis = _structured_chain_primary_intent(feature)
    if ft == "cypress_test_utility" and _structured_known_api_eligibility_basis(feature):
        return True, "cypress_test_utility_intercept"

    if ft == "custom_command_call":
        if (
            sk == "test_body"
            and not _has_direct_stateful_setup_signal(feature, name, raw, allow_cypress_role=False)
            and not _helper_wrapper_has_body_phase_signal(feature)
        ):
            return False, "excluded_test_body_custom_command_without_direct_setup_signal"
        basis = _structured_known_api_eligibility_basis(feature)
        if basis:
            return True, basis
        if (
            structured_intent
            and structured_intent != "navigation_bootstrap"
            and structured_basis != "ast_callee_name_heuristic"
            and not (
                sk == "test_body"
                and structured_basis == "ast_callee_name_heuristic"
                and _terminal_callee(feature).startswith(("api", "db", "database"))
            )
        ):
            return True, structured_basis

    if ft == "helper_call" and depth == 0 and sk == "test_body":
        if not _helper_wrapper_has_body_phase_signal(feature) and not _has_direct_stateful_setup_signal(
            feature,
            name,
            raw,
            allow_cypress_role=False,
        ):
            return False, "excluded_test_body_helper_without_direct_setup_signal"
        basis = _structured_known_api_eligibility_basis(feature)
        if basis:
            return True, basis

    return False, "not_eligible"


def _input_source_class(feature: Dict[str, Any]) -> str:
    for key in ("input_source_class", "input_source_ast"):
        val = _s(feature, key).lower()
        if val:
            return val
    return ""


def _input_load_site_evidence_is_structured(feature: Dict[str, Any]) -> bool:
    return bool(
        bool(feature.get("is_load_site"))
        or _s(feature, "rq2_unit").lower() == "load_site"
        or _s(feature, "input_channel_ast").lower() == "load_site"
        or _s(feature, "input_load_path_ast")
    )


def _has_server_environment_text(name: str, raw: str) -> bool:
    text = f"{name} {raw}"
    return bool(_SERVER_ENV_RE.search(text) or _SERVER_ENV_CAMEL_RE.search(text))


def _is_logger_only_call(name: str, raw: str) -> bool:
    text = f"{name} {raw}".strip()
    request_intent, _ = _request_text_intent({"name": name, "raw_code": raw})
    if request_intent:
        return False
    if _STATEFUL_SETUP_API_RE.search(raw or ""):
        return False
    return bool(
        _LOGGER_ASSERT_REPORT_RE.search(text)
        or _LOGGER_ASSERT_REPORT_RE.search(raw or "")
        or _LOGGER_ASSERT_REPORT_RE.search(name or "")
    )


def _is_locator_query_only_call(feature: Dict[str, Any], name: str, raw: str) -> bool:
    """Exclude locator/query plumbing that has no setup side effect."""
    ft = _s(feature, "feature_type").lower()
    if ft in SETUP_ELIGIBLE_FEATURE_TYPES or ft in {"network_mock", "browser_context_control", "time_control"}:
        return False
    terminal_action = _s(feature, "terminal_action_ast").lower()
    ui_action_category = _s(feature, "ui_action_category").lower()
    chain = _callee_chain(feature)
    if chain:
        if terminal_action or any(method in chain for method in _AST_UI_ACTION_METHODS):
            return False
        if ui_action_category == "locator_query":
            return True
        return bool(set(chain) & _AST_LOCATOR_QUERY_METHODS)
    if ui_action_category == "locator_query" and not terminal_action:
        return True
    text = f"{name} {raw}".strip()
    if not _LOCATOR_QUERY_ONLY_RE.search(text):
        return False
    if re.search(r"\.(?:click|dblclick|type|fill|press|select|check|uncheck|hover|drag|trigger)\s*\(", text, re.I):
        return False
    if (
        _EXPLICIT_NETWORK_MOCK_RE.search(text)
        or _STATEFUL_SETUP_API_RE.search(text)
        or _COOKIE_STORAGE_RE.search(text)
        or _is_backend_data_setup_text(name, raw)
    ):
        return False
    return True


def _is_cypress_utility_only_without_state(feature: Dict[str, Any], name: str, raw: str) -> bool:
    ft = _s(feature, "feature_type").lower()
    if ft not in {"cypress_test_utility", "cypress_subject_control", "cypress_builtin", "control"}:
        return False
    if _has_direct_stateful_setup_signal(feature, name, raw):
        return False
    chain = _callee_chain(feature)
    if chain:
        return chain[-1] in _AST_UTILITY_METHODS
    text = f"{name} {raw}".strip()
    if (
        _STATEFUL_SETUP_API_RE.search(text)
        or _EXPLICIT_NETWORK_MOCK_RE.search(text)
        or _AUTH_RE.search(text)
        or _AUTH_API_NAME_RE.search(text)
        or _is_backend_data_setup_text(name, raw)
        or _has_time_device_permission_text(name, raw)
        or _COOKIE_STORAGE_RE.search(text)
    ):
        return False
    if _is_wait_sleep_only(text):
        return True
    return bool(_UTILITY_CHAIN_ONLY_RE.search(text) or _ASSERTION_OR_REPORTING_TEXT_RE.search(text))


def _test_body_helper_requires_direct_setup_signal(feature: Dict[str, Any]) -> bool:
    return (
        _s(feature, "feature_type").lower() == "helper_call"
        and _s(feature, "source_kind") == "test_body"
        and int(feature.get("helper_depth") or 0) == 0
        and not bool(feature.get("attached_from_hook"))
    )


def _has_direct_stateful_setup_signal(
    feature: Dict[str, Any],
    name: str,
    raw: str,
    *,
    allow_cypress_role: bool = True,
) -> bool:
    text = f"{name} {raw}"
    api_cat = _s(feature, "framework_api_category")
    if (
        api_cat in _API_CATEGORY_TO_INTENT
        and api_cat != "navigation"
        and _framework_api_category_is_structured(feature)
    ):
        return True
    role = _s(feature, "cypress_command_role_ast")
    if (
        allow_cypress_role
        and role in ("session_setup", "test_data_setup", "setup_or_state_flow")
        and _cypress_command_role_is_structured(feature)
    ):
        return True
    structured_intent, _ = _structured_chain_primary_intent(feature)
    if structured_intent and structured_intent not in {"generic_setup_teardown_utility", "navigation_bootstrap"}:
        if (
            not allow_cypress_role
            and _s(feature, "feature_type").lower() == "custom_command_call"
            and _s(feature, "source_kind") == "test_body"
            and _terminal_callee(feature).startswith(("api", "db", "database"))
        ):
            return structured_intent == "auth_session_state"
        return True
    if _has_structured_callee_chain(feature):
        return False
    if (
        not allow_cypress_role
        and _s(feature, "feature_type").lower() == "custom_command_call"
        and _s(feature, "source_kind") == "test_body"
    ):
        return bool(_AUTH_API_NAME_RE.search(text))
    if _s(feature, "source_kind") in HOOK_SOURCE_KINDS and _AUTH_API_NAME_RE.search(text):
        return True
    return bool(
        _DIRECT_STATEFUL_SETUP_API_RE.search(text)
        or _EXPLICIT_NETWORK_MOCK_RE.search(text)
        or _BACKEND_FRAMEWORK_CALL_RE.search(text)
        or re.search(r"\bcy\.(?:api|db|database)[A-Z_a-z0-9$]*\s*\(", text, re.IGNORECASE)
    )


def _helper_wrapper_has_body_phase_signal(feature: Dict[str, Any]) -> bool:
    return bool(feature.get("wrapper_only")) and bool(_s(feature, "helper_body_phase_hint_ast"))


def _is_dom_mutation_utility_without_state(name: str, raw: str, feature: Dict[str, Any] | None = None) -> bool:
    if feature:
        chain = _callee_chain(feature)
        if chain and chain[-1] in _AST_DOM_MUTATION_METHODS:
            structured_intent, _ = _structured_chain_primary_intent(feature)
            return not structured_intent
        if chain:
            return False
    text = f"{name} {raw}"
    if not _DOM_MUTATION_UTILITY_RE.search(text):
        return False
    return not (
        _DIRECT_STATEFUL_SETUP_API_RE.search(text)
        or _EXPLICIT_NETWORK_MOCK_RE.search(text)
        or _COOKIE_STORAGE_RE.search(text)
        or _AUTH_COOKIE_CONTEXT_RE.search(text)
        or re.search(r"\b(?:localstorage|sessionstorage)\.setitem\b", text, re.IGNORECASE)
    )


def _is_ui_clear_or_focus_chain(name: str, raw: str, feature: Dict[str, Any] | None = None) -> bool:
    if feature:
        chain = _callee_chain(feature)
        if chain:
            terminal = chain[-1]
            if terminal not in {"clear", "focus"}:
                return False
            if "cy" in chain and "get" in chain:
                structured_intent, _ = _structured_chain_primary_intent(feature)
                return not structured_intent
            return False
    text = f"{name} {raw}"
    if not _UI_CLEAR_OR_FOCUS_CHAIN_RE.search(text):
        return False
    return not (
        _COOKIE_STORAGE_RE.search(text)
        or _AUTH_COOKIE_CONTEXT_RE.search(text)
        or _DIRECT_STATEFUL_SETUP_API_RE.search(text)
    )


def _is_wait_sleep_only(text: str) -> bool:
    compact = (text or "").strip().lower()
    return bool(_WAIT_SLEEP_ONLY_RE.search(compact))


def _is_bare_context_access(name: str, raw: str) -> bool:
    return bool(
        _BARE_CONTEXT_ACCESS_RE.search((name or "").strip())
        or _BARE_CONTEXT_ACCESS_RE.search((raw or "").strip())
    )


def _is_read_only_context_query(name: str, raw: str) -> bool:
    return bool(
        _READ_ONLY_CONTEXT_QUERY_RE.search((name or "").strip())
        or _READ_ONLY_CONTEXT_QUERY_RE.search((raw or "").strip())
    )


def _is_cypress_query_then_wrapper(name: str, raw: str) -> bool:
    return bool(
        _CYPRESS_QUERY_THEN_WRAPPER_RE.search((name or "").strip())
        or _CYPRESS_QUERY_THEN_WRAPPER_RE.search((raw or "").strip())
    )


def _has_cleanup_api(text: str) -> bool:
    compact = (text or "").lower()
    return bool(
        re.search(
            r"\b(clearcookies?|clearlocalstorage|delete|drop|reset|cleanup|teardown|close|restore|remove|logout)\b"
            r"|(?:api|db|database)?(?:delete|drop|reset|cleanup|teardown|restore|remove)[A-Z_a-z0-9]*",
            compact,
        )
    )


def _has_strong_cleanup_api(text: str) -> bool:
    compact = (text or "").lower()
    return bool(
        re.search(
            r"\b(clearcookies?|clearlocalstorage|drop|cleanup|teardown|close|restore|remove|logout)\b",
            compact,
        )
        or re.search(r"\b(?:api|db|database)?delete[A-Z_a-z0-9]*(?:channel|team|repo|repository|project)\b", text or "", re.I)
    )


def _is_input_load_site(feature: Dict[str, Any]) -> bool:
    """True only for static file load APIs, not UI text-entry consumers."""
    if _is_file_upload_consumer(feature):
        return False
    return _input_load_site_evidence_is_structured(feature)


def _is_file_upload_consumer(feature: Dict[str, Any]) -> bool:
    text = f"{_s(feature, 'name')} {_s(feature, 'raw_code')}"
    channel = _s(feature, "input_channel_ast").lower() or _s(feature, "input_channel").lower()
    return bool(
        channel in ("ui_file_upload", "file_upload")
        or re.search(r"\b(selectfile|setinputfiles)\s*(?:\(|:)", text, re.I)
        or re.search(r"\binput\s*:\s*(?:selectfile|setinputfiles)\b", text, re.I)
    )


def _identifier_tokens(text: str) -> List[str]:
    tokens: List[str] = []
    for ident in _IDENTIFIER_RE.findall(text or ""):
        for part in re.split(r"[_$]+", ident):
            if not part:
                continue
            split = _CAMEL_TOKEN_RE.findall(part)
            tokens.extend((tok or part).lower() for tok in (split or [part]))
    return tokens


def _has_generic_setup_helper_name(name: str) -> bool:
    if _GENERIC_NAME_RE.search(name or ""):
        return True
    return bool(set(_identifier_tokens(name or "")) & set(GENERIC_HELPER_NAME_RE))


def _looks_like_ui_page_object_name(name_tokens: List[str]) -> bool:
    if not name_tokens:
        return False
    if name_tokens[-1] in _UI_OBJECT_TOKENS:
        return True
    return bool(set(name_tokens) & _UI_OBJECT_TOKENS and "pageobject" in "".join(name_tokens))


def _is_backend_data_setup_text(name: str, raw: str) -> bool:
    """Token-aware backend/data setup detection with page-object false-positive guards."""
    text = f"{name} {raw}".strip()
    if _BACKEND_FRAMEWORK_CALL_RE.search(text):
        return True

    name_tokens = _identifier_tokens(name)
    tokens = name_tokens + _identifier_tokens(raw)
    token_set = set(tokens)
    if not token_set or not (token_set & _BACKEND_ACTION_TOKENS):
        return False

    if _DOM_MUTATION_UTILITY_RE.search(text) and not (token_set & _BACKEND_MARKER_TOKENS):
        return False
    if _looks_like_ui_page_object_name(name_tokens):
        return False
    if token_set & _BACKEND_MARKER_TOKENS:
        return True
    if "headless" in token_set:
        return True
    if token_set & _BACKEND_ENTITY_TOKENS:
        return True
    return False


def _is_network_mock_or_spy_text(name: str, raw: str) -> bool:
    text = f"{name} {raw}".strip()
    if _EXPLICIT_NETWORK_MOCK_RE.search(text):
        return True
    tokens = set(_identifier_tokens(text))
    if tokens & {"intercept", "route", "fulfill", "nock", "msw", "requestlogger", "requestmock"}:
        return True
    if tokens & {"mock", "stub", "spy", "callsfake"} and tokens & _NETWORK_CONTEXT_TOKENS:
        return True
    return False


def _is_test_data_cookie_text(name: str, raw: str) -> bool:
    return bool(_COOKIE_TEST_DATA_RE.search(f"{name} {raw}"))


def _is_wait_or_load_state_only_text(name: str, raw: str) -> bool:
    return bool(
        _is_wait_sleep_only(name)
        or _is_wait_sleep_only(raw)
        or _LOAD_STATE_WAIT_RE.search(name or "")
        or _LOAD_STATE_WAIT_RE.search(raw or "")
    )


def _has_time_device_permission_text(name: str, raw: str) -> bool:
    text = f"{name} {raw}"
    if _TIME_DEVICE_PERMISSION_RE.search(text):
        return True
    tokens = set(_identifier_tokens(text))
    if tokens & {"goto", "go", "navigate", "navigation", "visit", "open"} and not (
        tokens & {"clock", "geolocation", "locale", "timezone", "viewport"}
    ):
        return False
    return bool(
        tokens
        & {
            "clock",
            "geolocation",
            "locale",
            "permission",
            "permissions",
            "timezone",
            "tick",
            "viewport",
            "viewportwidth",
            "viewportheight",
        }
    )


def _helper_seed_name(name: str) -> str:
    text = (name or "").strip()
    if not text:
        return ""
    if "." in text:
        return text.rsplit(".", 1)[-1]
    match = re.search(r"([A-Za-z_$][\w$]*)$", text)
    return match.group(1) if match else text


HelperSeedKey = Tuple[int, str, int, int]


def helper_wrapper_seed_key(
    line: int,
    name: str,
    *,
    start: int = 0,
    end: int = 0,
) -> HelperSeedKey:
    return (line, _helper_seed_name(name), int(start or 0), int(end or 0))


def _int_feature_field(feature: Dict[str, Any], *keys: str) -> int:
    for key in keys:
        try:
            value = int(feature.get(key) or 0)
        except (TypeError, ValueError):
            value = 0
        if value:
            return value
    return 0


def _helper_child_seed_key(feature: Dict[str, Any]) -> Optional[HelperSeedKey]:
    line = _int_feature_field(feature, "helper_call_line", "call_line")
    name = _s(feature, "helper_name")
    if not line or not name:
        return None
    return helper_wrapper_seed_key(
        line,
        name,
        start=_int_feature_field(feature, "helper_call_start_offset", "call_start_offset"),
        end=_int_feature_field(feature, "helper_call_end_offset", "call_end_offset"),
    )


def _is_visual_audit_helper_call(name: str, raw: str) -> bool:
    text = f"{name} {raw}".strip()
    if not _VISUAL_AUDIT_HELPER_RE.search(text):
        return False
    return not (
        _STATEFUL_SETUP_API_RE.search(raw or "")
        or _AUTH_RE.search(text)
        or _is_backend_data_setup_text(name, raw)
    )


def _is_event_listener_helper_call(name: str, raw: str) -> bool:
    text = f"{name} {raw}".strip()
    return bool(_EVENT_LISTENER_HELPER_RE.search(text))


def _helper_has_setup_signal(feature: Dict[str, Any], name: str, raw: str) -> bool:
    text = f"{name} {raw}"
    api_cat = _s(feature, "framework_api_category")
    if (
        api_cat
        and api_cat not in {"unknown", "navigation"}
        and _framework_api_category_is_structured(feature)
    ):
        return True
    role = _s(feature, "cypress_command_role_ast")
    if role in ("session_setup", "test_data_setup", "setup_or_state_flow") and _cypress_command_role_is_structured(feature):
        return True
    structured_intent, _ = _structured_chain_primary_intent(feature)
    if structured_intent and structured_intent != "navigation_bootstrap":
        return True
    if _has_structured_callee_chain(feature):
        return False
    if _s(feature, "navigation_bootstrap_candidate_ast"):
        return True
    if _is_navigation_helper_text(name, raw) and _s(feature, "source_kind") in HOOK_SOURCE_KINDS:
        return True
    if int(feature.get("child_setup_unit_count") or 0) > 0 and _helper_child_intent_is_trusted(feature, feature):
        return True
    if bool(feature.get("wrapper_only")) and _s(feature, "helper_body_phase_hint_ast"):
        return True
    return bool(
        _EXPLICIT_NETWORK_MOCK_RE.search(text)
        or _AUTH_RE.search(text)
        or _is_backend_data_setup_text(name, raw)
        or _INLINE_DATA_SETUP_RE.search(raw)
        or _has_server_environment_text(name, raw)
        or _has_time_device_permission_text(name, raw)
        or _COOKIE_STORAGE_RE.search(text)
    )


def _is_ordinary_workflow_helper_without_setup_signal(
    feature: Dict[str, Any],
    name: str,
    raw: str,
) -> bool:
    if _helper_has_setup_signal(feature, name, raw):
        return False
    return bool(_ORDINARY_WORKFLOW_HELPER_RE.search(name or ""))


def _is_verification_helper_without_setup_signal(
    feature: Dict[str, Any],
    name: str,
    raw: str,
) -> bool:
    text = f"{name} {raw}"
    api_cat = _s(feature, "framework_api_category")
    role = _s(feature, "cypress_command_role_ast")
    if (
        (api_cat and api_cat != "unknown")
        or role in ("session_setup", "test_data_setup", "setup_or_state_flow")
        or _EXPLICIT_NETWORK_MOCK_RE.search(text)
        or _AUTH_RE.search(text)
        or _AUTH_API_NAME_RE.search(text)
        or _is_backend_data_setup_text(name, raw)
        or _INLINE_DATA_SETUP_RE.search(raw)
        or _has_server_environment_text(name, raw)
        or _has_time_device_permission_text(name, raw)
        or _COOKIE_STORAGE_RE.search(text)
    ):
        return False
    return bool(_VERIFICATION_HELPER_NAME_RE.search(name or ""))


def _helper_wrapper_call_seed_key(feature: Dict[str, Any]) -> Optional[HelperSeedKey]:
    line = _int_feature_field(feature, "matched_helper_call_line", "helper_call_line") or _line(feature)
    name = _s(feature, "name")
    if not line or not name:
        return None
    return helper_wrapper_seed_key(
        line,
        name,
        start=_int_feature_field(
            feature,
            "matched_helper_call_start_offset",
            "helper_call_start_offset",
            "source_start_offset",
        ),
        end=_int_feature_field(
            feature,
            "matched_helper_call_end_offset",
            "helper_call_end_offset",
            "source_end_offset",
        ),
    )


def match_resolved_helper_wrapper(
    seeds: set[HelperSeedKey],
    line: int,
    name: str,
    *,
    start: int = 0,
    end: int = 0,
) -> Optional[HelperSeedKey]:
    """Match a direct helper call to a resolved expansion seed (offset-aware)."""
    seed_name = _helper_seed_name(name)
    if not line or not seed_name:
        return None
    start_i, end_i = int(start or 0), int(end or 0)
    line_candidates = [s for s in seeds if s[0] == line and s[1] == seed_name]
    if not line_candidates:
        return None
    if start_i and end_i:
        for seed in line_candidates:
            if seed[2] == start_i and seed[3] == end_i:
                return seed
        return None
    if len(line_candidates) == 1:
        return line_candidates[0]
    return None


def _helper_body_phase_hint(feature: Dict[str, Any], hints: Dict[str, Any]) -> str:
    return hints.get("helper_body_phase_hint_ast") or _s(feature, "helper_body_phase_hint_ast")


def _statement_phase_hint(feature: Dict[str, Any], hints: Dict[str, Any]) -> str:
    return hints.get("statement_phase_hint_ast") or _s(feature, "statement_phase_hint_ast")


def classify_phase(feature: Dict[str, Any], hints: Dict[str, Any]) -> str:
    ft = _s(feature, "feature_type").lower()
    wrapper_only = bool(feature.get("wrapper_only"))
    body_hint = _helper_body_phase_hint(feature, hints)

    if wrapper_only and ft == "helper_call":
        if body_hint == "setup_and_teardown":
            return "setup_and_teardown"
        if body_hint == "teardown":
            return "teardown"
        if body_hint == "setup":
            return "setup"

    sk = _s(feature, "source_kind")
    inv = hints.get("inventory_category") or ""
    if sk in _TEARDOWN_SOURCE_KINDS or ft == "teardown" or inv == "teardown_cleanup":
        return "teardown"
    if sk in _SETUP_SOURCE_KINDS or ft == "setup" or inv == "hook_setup":
        return "setup"

    stmt_hint = _statement_phase_hint(feature, hints)
    if stmt_hint == "setup_and_teardown":
        return "setup_and_teardown"
    if stmt_hint == "teardown":
        return "teardown"
    if stmt_hint == "setup":
        return "setup"

    role = hints.get("cypress_command_role_ast") or _s(feature, "cypress_command_role_ast")
    if role in ("session_setup", "test_data_setup", "setup_or_state_flow"):
        return "setup"

    ft = _s(feature, "feature_type").lower()
    if ft == "input" and _is_input_load_site(feature):
        return "setup"

    name = _s(feature, "name")
    raw = _s(feature, "raw_code")
    text = f"{name} {raw}".lower()

    if _is_wait_sleep_only(text) and not _has_cleanup_api(text):
        return "setup"
    if _CLEANUP_RE.search(text) and not _AUTH_RE.search(text):
        return "teardown"
    if inv in ("auth_session_setup", "api_seed_setup", "database_seed_setup", "browser_context_setup"):
        return "setup"
    if inv in ("network_mock", "browser_context_control", "time_control", "framework_fixture"):
        return "setup"
    if ft in ("helper_call", "custom_command_call") and sk in ("test_body", "imported_helper", "helper_function", "cypress_command"):
        if (
            _AUTH_RE.search(text)
            or _AUTH_API_NAME_RE.search(text)
            or _is_backend_data_setup_text(name, raw)
            or _has_server_environment_text(name, raw)
            or _has_time_device_permission_text(name, raw)
            or _has_generic_setup_helper_name(name)
        ):
            return "setup"
    if ft == "control" and _CLEANUP_RE.search(text):
        return "teardown"
    if ft == "control":
        return "setup"
    return "unclear"


def classify_scope(feature: Dict[str, Any], hints: Dict[str, Any]) -> str:
    sk = _s(feature, "source_kind")
    depth = int(feature.get("helper_depth") or 0)
    ft = _s(feature, "feature_type").lower()
    hook_owner = _s(feature, "hook_owner_kind") or hints.get("hook_owner_kind") or ""

    if hook_owner == "fixture" and sk in ("before", "after", "beforeAll", "afterAll"):
        return "suite_or_fixture"
    if hook_owner == "test" and sk in ("before", "after", "beforeEach", "afterEach"):
        return "per_test_hook"
    if hook_owner == "global" and sk in _SUITE_HOOK_SOURCE_KINDS:
        return "suite_or_fixture"
    if not hook_owner and sk in _SUITE_HOOK_SOURCE_KINDS:
        return "suite_or_fixture"
    if sk in _PER_TEST_HOOK_SOURCE_KINDS:
        return "per_test_hook"
    if sk in _SUITE_HOOK_SOURCE_KINDS:
        return "suite_or_fixture"
    if sk == "test_body" and depth == 0:
        return "inline_test_body"
    if sk == "cypress_command" or ft == "cypress_command":
        return "helper_or_framework_extension"
    if ft == "custom_command_call":
        if sk == "test_body" and depth == 0:
            return "inline_test_body"
        return "helper_or_framework_extension"
    if (
        ft == "helper_call"
        and (depth > 0 or sk in ("imported_helper", "helper_function"))
    ):
        return "helper_or_framework_extension"
    if hints.get("is_support_hook"):
        return "global_or_project"
    if hints.get("cypress_command_role_ast"):
        return "helper_or_framework_extension"
    if hints.get("fixture_param_name") or hints.get("workflow_kind_ast") == "playwright_fixture":
        scope = hints.get("fixture_scope") or ""
        if scope in ("worker", "project", "global"):
            return "global_or_project"
        return "helper_or_framework_extension"
    if (
        depth > 0
        or sk in ("imported_helper", "helper_function", "cypress_command")
    ):
        return "helper_or_framework_extension"
    return "unclear"


def classify_primary_intent(
    feature: Dict[str, Any],
    hints: Dict[str, Any],
    *,
    eligibility_basis: str = "",
) -> str:
    return classify_primary_intent_detail(
        feature,
        hints,
        eligibility_basis=eligibility_basis,
    )[0]


def classify_primary_intent_detail(
    feature: Dict[str, Any],
    hints: Dict[str, Any],
    *,
    eligibility_basis: str = "",
) -> Tuple[str, str]:
    """Return (primary_intent, evidence_basis), with lexical fallbacks explicit."""
    name = _s(feature, "name")
    raw = _s(feature, "raw_code")
    text = f"{name} {raw}".lower()
    api_cat = hints.get("framework_api_category") or _s(feature, "framework_api_category")

    if _tokenized_auth_navigation_text(name, raw):
        return "navigation_bootstrap", "lexical_navigation_call"

    if (
        eligibility_basis == "navigation_bootstrap_ast"
        and api_cat == "navigation"
    ):
        return (
            "navigation_bootstrap",
            "ast_framework_api_category"
            if _framework_api_category_is_structured(hints)
            else "lexical_navigation_call",
        )

    if (
        eligibility_basis == "navigation_bootstrap_candidate"
        and not (_AUTH_RE.search(text) or _AUTH_API_NAME_RE.search(text))
    ):
        return "navigation_bootstrap", "lexical_navigation_call"

    if eligibility_basis.startswith("input_source_class:") or eligibility_basis in (
        "fixture_file_input",
        "external_file_input_lexical",
        "input_load_site",
    ):
        if eligibility_basis == "external_file_input_lexical":
            return "test_data_or_backend_state", "lexical_static_file_load"
        return "test_data_or_backend_state", "input_source_class"

    child_intent = _s(feature, "dominant_child_intent")
    if (
        child_intent in PRIMARY_INTENTS
        and int(feature.get("child_setup_unit_count") or 0) > 0
        and _helper_child_intent_is_trusted(feature, hints)
    ):
        if _is_mixed_child_intent(feature):
            return "generic_setup_teardown_utility", "resolved_helper_child_intents"
        return child_intent, "resolved_helper_child_intents"

    if _is_wait_or_load_state_only_text(name, raw) and not _is_backend_data_setup_text(name, raw):
        return "generic_setup_teardown_utility", "lexical_wait_sleep"

    structured_intent, structured_basis = _structured_primary_intent_signal(feature, hints)
    if structured_intent:
        return structured_intent, structured_basis

    if _EXPLICIT_NETWORK_MOCK_RE.search(text):
        if api_cat == "network_mock":
            return (
                "network_mock_or_spy",
                "ast_framework_api_category"
                if _framework_api_category_is_structured(hints)
                else "lexical_framework_api_category",
            )
        return "network_mock_or_spy", "lexical_network_mock"

    role = hints.get("cypress_command_role_ast") or ""
    if role == "session_setup":
        return "auth_session_state", _cypress_command_role_primary_basis(hints)
    if (
        _AUTH_RE.search(text)
        or _AUTH_API_NAME_RE.search(text)
        or "cy.session" in text
        or "storagestate" in text
        or "localstorage" in text and re.search(r"(token|session|auth|login)", text)
        or "sessionstorage" in text and re.search(r"(token|session|auth|login)", text)
        or "setcookie" in text and re.search(r"(token|session|auth|login)", text)
    ):
        return "auth_session_state", "lexical_auth_session"
    if _is_navigation_helper_text(name, raw) and _s(feature, "source_kind") in HOOK_SOURCE_KINDS:
        return "navigation_bootstrap", "lexical_navigation_call"

    if _plain_helper_body_unavailable_without_structured_intent(feature, hints):
        return "generic_setup_teardown_utility", "lexical_generic_helper_name"
    if _opaque_helper_without_structured_intent(feature, hints):
        return "generic_setup_teardown_utility", "lexical_generic_helper_name"
    if role == "test_data_setup":
        return "test_data_or_backend_state", _cypress_command_role_primary_basis(hints)
    request_intent, request_basis = _request_text_intent(feature)
    if request_intent:
        return request_intent, request_basis
    if _is_backend_data_setup_text(name, raw) or _is_test_data_cookie_text(name, raw):
        return "test_data_or_backend_state", "lexical_backend_data_setup"
    if _has_server_environment_text(name, raw):
        return "server_or_external_environment", "lexical_server_environment"
    if _has_time_device_permission_text(name, raw):
        return "time_device_permission_emulation", "lexical_time_device_permission"

    api_cat = hints.get("framework_api_category") or _s(feature, "framework_api_category")
    if api_cat == "network_mock":
        basis = (
            "ast_framework_api_category"
            if _framework_api_category_is_structured(hints)
            else "lexical_framework_api_category"
        )
        return "network_mock_or_spy", basis
    if api_cat == "cleanup":
        basis = (
            "ast_framework_api_category"
            if _framework_api_category_is_structured(hints)
            else "lexical_framework_api_category"
        )
        return "cleanup_restore_state", basis
    if _is_ui_clear_or_focus_chain(name, raw, feature):
        return "generic_setup_teardown_utility", "lexical_generic_helper_name"
    if _has_strong_cleanup_api(f"{name} {raw}") and not (
        _AUTH_API_NAME_RE.search(text)
        and not re.search(r"\b(?:delete|drop|reset|cleanup|teardown|restore|remove)\b", text, re.I)
    ):
        return "cleanup_restore_state", "lexical_cleanup"

    if api_cat in _API_CATEGORY_TO_INTENT:
        mapped = _API_CATEGORY_TO_INTENT[api_cat]
        if mapped != "navigation_bootstrap" or eligibility_basis in (
            "navigation_bootstrap_candidate",
            "navigation_bootstrap_ast",
        ):
            basis = (
                "ast_framework_api_category"
                if _framework_api_category_is_structured(hints)
                else "lexical_framework_api_category"
            )
            return mapped, basis

    if _is_network_mock_or_spy_text(name, raw):
        return "network_mock_or_spy", "lexical_network_mock"

    if _INLINE_DATA_SETUP_RE.search(text):
        return "test_data_or_backend_state", "lexical_inline_data_setup"
    if _COOKIE_STORAGE_RE.search(text):
        if _AUTH_RE.search(text) or _AUTH_COOKIE_CONTEXT_RE.search(text):
            return "auth_session_state", "lexical_auth_session"
        if _CLEANUP_RE.search(text):
            return "cleanup_restore_state", "lexical_cleanup"
        return "browser_context_or_client_state", "lexical_cookie_storage"
    if _CLEANUP_RE.search(text):
        return "cleanup_restore_state", "lexical_cleanup"

    if (
        _s(feature, "feature_type").lower() in {"custom_command_call", "setup", "browser_context_control"}
        and _s(feature, "source_kind") == "cypress_command"
        and not _has_direct_stateful_setup_signal(feature, name, raw)
    ):
        return "generic_setup_teardown_utility", "lexical_generic_helper_name"

    if (
        _s(feature, "feature_type").lower() == "setup"
        and _s(feature, "source_kind") in _TEARDOWN_SOURCE_KINDS
        and not _has_direct_stateful_setup_signal(feature, name, raw)
    ):
        return "generic_setup_teardown_utility", "lexical_generic_helper_name"

    inv = hints.get("inventory_category") or ""
    taxonomy = load_taxonomy()
    hint_map = taxonomy.get("inventory_category_to_primary_intent_hint") or {}
    if inv in hint_map and hint_map[inv] != "unclear":
        inv_basis = hints.get("inventory_category_basis") or "lexical_fallback"
        return hint_map[inv], f"inventory_category:{inv_basis}"

    if _has_generic_setup_helper_name(name):
        return "generic_setup_teardown_utility", "lexical_generic_helper_name"
    return "unclear", "unresolved"


def classify_confidence(
    feature: Dict[str, Any],
    hints: Dict[str, Any],
    primary_intent: str,
    eligibility_basis: str,
    primary_intent_basis: str = "",
) -> str:
    if primary_intent_basis and _primary_intent_basis_is_fallback(primary_intent_basis):
        return "low" if primary_intent in ("generic_setup_teardown_utility", "unclear") else "medium"

    role = hints.get("cypress_command_role_ast") or ""
    inv = hints.get("inventory_category") or ""
    ft = _s(feature, "feature_type").lower()

    if eligibility_basis == "navigation_bootstrap_candidate":
        return "medium"
    if role in ("session_setup", "test_data_setup"):
        return "high" if _cypress_command_role_is_structured(hints) else "medium"
    if (feature.get("dominant_child_intent") or "") and int(feature.get("child_setup_unit_count") or 0) > 0:
        return "low" if _is_mixed_child_intent(feature) else "medium"
    if primary_intent == "generic_setup_teardown_utility":
        return "low"
    if primary_intent == "unclear":
        return "low"
    if ft in ("network_mock", "browser_context_control", "time_control", "setup", "teardown"):
        return "high"
    if inv in (
        "network_mock",
        "browser_context_control",
        "time_control",
        "auth_session_setup",
        "api_seed_setup",
        "database_seed_setup",
        "teardown_cleanup",
    ):
        return "high"
    ast_conf = (hints.get("ast_confidence") or "").lower()
    if ast_conf == "high":
        return "medium"
    return "medium"


def intent_review_reasons(
    feature: Dict[str, Any],
    hints: Dict[str, Any],
    *,
    primary_intent: str,
    confidence: str,
    eligibility_basis: str,
    primary_intent_basis: str = "",
    navigation_bootstrap_rejected: bool = False,
) -> List[str]:
    reasons: List[str] = []
    name = _s(feature, "name")

    if confidence == "low":
        reasons.append("low_confidence")
    if primary_intent == "unclear":
        reasons.append("weak_lexical_signal")
    if _primary_intent_basis_is_fallback(primary_intent_basis) and "weak_lexical_signal" not in reasons:
        reasons.append("weak_lexical_signal")
    if primary_intent == "generic_setup_teardown_utility":
        if _is_mixed_child_intent(feature):
            reasons.append("mixed_intents")
        else:
            reasons.append("generic_helper_name")
    role = hints.get("cypress_command_role_ast") or _s(feature, "cypress_command_role_ast")
    structured_cypress_role = (
        role in ("session_setup", "test_data_setup", "setup_or_state_flow")
        and _cypress_command_role_is_structured(hints)
    )
    if hints.get("helper_resolution_status") in ("unresolved", "missing_body"):
        if not structured_cypress_role:
            reasons.append("helper_body_unavailable")
    if navigation_bootstrap_rejected:
        reasons.append("partial_coverage_m3")
    if eligibility_basis == "navigation_bootstrap_candidate" and primary_intent != "navigation_bootstrap":
        reasons.append("partial_coverage_m3")
    if not hints.get("cypress_command_role_ast") and _s(feature, "framework") == "Cypress" and _s(feature, "feature_type") == "custom_command_call":
        reasons.append("framework_mapping_unclear")
    if _has_generic_setup_helper_name(name) and primary_intent not in ("generic_setup_teardown_utility", "unclear"):
        pass
    elif _has_generic_setup_helper_name(name):
        if "generic_helper_name" not in reasons:
            reasons.append("generic_helper_name")
    return reasons


def _is_mixed_child_intent(feature: Dict[str, Any]) -> bool:
    try:
        return float(feature.get("mixed_intent_score") or 0) >= 0.34
    except (TypeError, ValueError):
        return False


def _helper_child_intent_is_trusted(feature: Dict[str, Any], hints: Dict[str, Any]) -> bool:
    status = (hints.get("helper_resolution_status") or _s(feature, "helper_resolution_status")).strip().lower()
    if status in {"unresolved", "missing_body", "body_unavailable", "unavailable"}:
        return False
    if status in {"resolved", "inline_body", "expanded", "inlined"}:
        return _trusted_helper_expansion_evidence(feature)
    if (
        _helper_body_phase_hint(feature, hints)
        and _phase_hint_basis_is_structured(hints.get("helper_body_phase_hint_basis_ast") or "")
    ):
        return True
    if _int_feature_field(
        feature,
        "matched_helper_call_start_offset",
        "helper_call_start_offset",
        "call_start_offset",
    ):
        return True
    return not status


def _plain_helper_body_unavailable_without_structured_intent(
    feature: Dict[str, Any],
    hints: Dict[str, Any],
) -> bool:
    if _s(feature, "feature_type").lower() != "helper_call":
        return False
    status = (hints.get("helper_resolution_status") or _s(feature, "helper_resolution_status")).strip().lower()
    if status not in {"unresolved", "missing_body", "body_unavailable", "unavailable"}:
        return False
    api_cat = hints.get("framework_api_category") or _s(feature, "framework_api_category")
    if api_cat and _framework_api_category_is_structured(hints):
        return False
    if _cypress_command_role_is_structured(hints):
        return False
    return True


def _opaque_helper_without_structured_intent(
    feature: Dict[str, Any],
    hints: Dict[str, Any],
) -> bool:
    if _s(feature, "feature_type").lower() != "helper_call":
        return False
    if _has_direct_stateful_setup_signal(feature, _s(feature, "name"), _s(feature, "raw_code")):
        return False
    if _framework_api_category_is_structured(hints) or _cypress_command_role_is_structured(hints):
        return False
    if int(feature.get("child_setup_unit_count") or 0) > 0 and _helper_child_intent_is_trusted(feature, hints):
        return False
    if _helper_body_phase_hint(feature, hints) and _phase_hint_basis_is_structured(
        hints.get("helper_body_phase_hint_basis_ast") or ""
    ):
        return False
    return _s(feature, "source_kind") in {
        "before",
        "beforeEach",
        "beforeAll",
        "after",
        "afterEach",
        "afterAll",
        "imported_helper",
        "helper_function",
    }


def _structured_primary_intent_signal(
    feature: Dict[str, Any],
    hints: Dict[str, Any],
) -> Tuple[str, str]:
    api_cat = _structured_framework_category({**feature, **hints})
    role = hints.get("cypress_command_role_ast") or _s(feature, "cypress_command_role_ast")
    if role == "session_setup" and _cypress_command_role_is_structured(hints):
        return "auth_session_state", "ast_cypress_command_role"
    if api_cat == "network_mock":
        text = f"{_s(feature, 'name')} {_s(feature, 'raw_code')}"
        if (
            _s(feature, "feature_type").lower() != "network_mock"
            and _is_backend_data_setup_text(_s(feature, "name"), _s(feature, "raw_code"))
            and not _EXPLICIT_NETWORK_MOCK_RE.search(text)
        ):
            return "test_data_or_backend_state", "lexical_backend_data_setup"
        return "network_mock_or_spy", "ast_framework_api_category"

    request_ast_intent, request_ast_basis = _request_ast_intent(feature)
    if request_ast_intent:
        return request_ast_intent, request_ast_basis

    request_intent, request_basis = _request_text_intent(feature)
    if request_intent == "auth_session_state":
        return request_intent, request_basis

    cleanup_target_intent, cleanup_target_basis = _structured_cleanup_target_primary_intent(feature, hints)
    if cleanup_target_intent:
        return cleanup_target_intent, cleanup_target_basis

    if request_intent:
        return request_intent, request_basis
    intent, basis = _structured_chain_primary_intent(feature)
    if intent and intent != "navigation_bootstrap":
        return intent, basis
    inline_child_intent, inline_child_basis = _inline_wrapper_child_intent_signal(feature)
    if inline_child_intent and (
        not api_cat
        or api_cat in {"setup_utility"}
        or not _framework_api_category_is_structured(hints)
    ):
        return inline_child_intent, inline_child_basis
    if api_cat == "time_device_emulation":
        if _is_direct_time_device_operation(feature):
            return "time_device_permission_emulation", "ast_framework_api_category"
        if _is_lodash_times_iteration(feature):
            tokens = set(_identifier_tokens(f"{_s(feature, 'name')} {_s(feature, 'raw_code')}"))
            if tokens & _AST_BACKEND_MUTATION_FRAGMENTS:
                return "test_data_or_backend_state", "lexical_backend_data_setup"
            return "generic_setup_teardown_utility", "lexical_generic_helper_name"
        return "", ""
    if api_cat in _API_CATEGORY_TO_INTENT:
        return _API_CATEGORY_TO_INTENT[api_cat], "ast_framework_api_category"

    if role == "test_data_setup" and _cypress_command_role_is_structured(hints):
        return "test_data_or_backend_state", "ast_cypress_command_role"
    if role == "setup_or_state_flow" and _cypress_command_role_is_structured(hints):
        return "generic_setup_teardown_utility", "ast_cypress_command_role"

    task_role = hints.get("cypress_task_role_ast") or _s(feature, "cypress_task_role_ast")
    if task_role == "test_data_setup" and _cypress_task_role_is_structured(hints):
        return "test_data_or_backend_state", "ast_cypress_task_handler"
    if task_role == "setup_or_state_flow" and _cypress_task_role_is_structured(hints):
        return "server_or_external_environment", "ast_cypress_task_handler"

    return "", ""


def _is_navigation_helper_text(name: str, raw: str) -> bool:
    text = f"{name} {raw}"
    tokens = set(_identifier_tokens(text))
    return bool(tokens & {"goto", "go", "navigate", "navigation", "visit", "open"} or is_navigation_call(name, raw))


def _structured_evidence_available(feature: Dict[str, Any], hints: Dict[str, Any]) -> bool:
    if _cypress_command_role_is_structured(hints):
        return True
    if _cypress_task_role_is_structured(hints):
        return True
    if hints.get("workflow_kind_ast") and _workflow_kind_is_structured(hints):
        return True
    if hints.get("fixture_param_name"):
        return True
    if hints.get("statement_phase_hint_ast") and _phase_hint_basis_is_structured(
        hints.get("statement_phase_hint_basis_ast") or ""
    ):
        return True
    if hints.get("helper_body_phase_hint_ast") and _phase_hint_basis_is_structured(
        hints.get("helper_body_phase_hint_basis_ast") or ""
    ):
        return True
    if _structured_framework_category({**feature, **hints}):
        return True
    if int(feature.get("child_setup_unit_count") or 0) > 0 and _helper_child_intent_is_trusted(feature, hints):
        return True
    return False


def _framework_api_category_is_structured(hints: Dict[str, Any]) -> bool:
    basis = (hints.get("framework_api_category_basis_ast") or "").strip()
    return basis in {"ast_known_framework_api", "ast_nested_framework_api", "ast_cypress_task_handler"}


def _phase_hint_basis_is_structured(basis: str) -> bool:
    return (basis or "").strip() in {
        "ast_known_framework_api",
        "ast_nested_framework_api",
        "mixed_structured_framework_api",
    }


def _workflow_kind_is_structured(hints: Dict[str, Any]) -> bool:
    basis = (hints.get("workflow_kind_basis_ast") or "").strip()
    return bool(basis) and not basis.endswith("_heuristic")


def _cypress_command_role_is_structured(hints: Dict[str, Any]) -> bool:
    basis = (hints.get("cypress_command_role_basis_ast") or "").strip()
    return basis.startswith("ast_") and basis not in {
        "ast_body_unavailable",
        "ast_no_cypress_setup_or_ui_call",
    }


def _cypress_task_role_is_structured(hints: Dict[str, Any]) -> bool:
    role = (hints.get("cypress_task_role_ast") or "").strip()
    basis = (hints.get("cypress_task_role_basis_ast") or "").strip()
    return (
        role in {"test_data_setup", "setup_or_state_flow"}
        and basis.startswith("ast_task_handler_")
        and basis not in {
            "ast_task_handler_body_unavailable",
            "ast_task_handler_diagnostic",
            "ast_task_handler_no_setup_call",
            "ast_task_handler_registered_name",
        }
    )


def _cypress_command_role_primary_basis(hints: Dict[str, Any]) -> str:
    return (
        "ast_cypress_command_role"
        if _cypress_command_role_is_structured(hints)
        else "heuristic_cypress_command_role"
    )


def _primary_intent_basis_is_fallback(primary_intent_basis: str) -> bool:
    basis = (primary_intent_basis or "").strip()
    return (
        not basis
        or basis == "unresolved"
        or basis.startswith("heuristic_")
        or basis.startswith("lexical_")
        or basis.endswith("_heuristic")
        or basis == "inventory_category:lexical_fallback"
    )


def _fallback_used(
    feature: Dict[str, Any],
    hints: Dict[str, Any],
    eligibility_basis: str,
    primary_intent_basis: str = "",
) -> int:
    if primary_intent_basis:
        return 1 if _primary_intent_basis_is_fallback(primary_intent_basis) else 0
    if eligibility_basis in (
        "navigation_bootstrap_ast",
        "navigation_bootstrap_accepted",
    ):
        return 0
    if _structured_evidence_available(feature, hints):
        return 0
    return 1


def _uncertain_reason(
    feature: Dict[str, Any],
    reasons: List[str],
    *,
    primary_intent: str,
) -> str:
    mapped: List[str] = []
    for reason in reasons:
        if reason == "low_confidence":
            continue
        if reason == "framework_mapping_unclear":
            mapped.append("missing_framework_mapping")
        elif reason == "partial_coverage_m3":
            mapped.append("not_enough_context")
        elif reason in UNCERTAIN_REASONS:
            mapped.append(reason)
    if _is_mixed_child_intent(feature):
        mapped.append("mixed_intents")
    if primary_intent == "unclear" and not mapped:
        mapped.append("not_enough_context")
    if _s(feature, "raw_code") and len(_s(feature, "raw_code")) > 500:
        mapped.append("review_snippet_truncated")
    seen = []
    for reason in mapped:
        if reason in UNCERTAIN_REASONS and reason not in seen:
            seen.append(reason)
    return "|".join(seen)


def _child_summary_fields(feature: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "child_setup_unit_count": int(feature.get("child_setup_unit_count") or 0),
        "child_intent_counts_json": _s(feature, "child_intent_counts_json"),
        "dominant_child_intent": _s(feature, "dominant_child_intent"),
        "mixed_intent_score": feature.get("mixed_intent_score") or "",
    }


def annotate_helper_child_intent_summaries(candidates: List[Dict[str, Any]]) -> None:
    """Attach resolved helper/custom-command child intent summaries to wrapper candidates."""
    by_seed: Dict[HelperSeedKey, Counter] = {}
    totals_by_seed: Counter = Counter()
    by_name: Dict[str, Counter] = {}
    totals_by_name: Counter = Counter()
    wrapper_name_counts: Counter = Counter()

    for cand in candidates:
        if not cand:
            continue
        feature = cand["feature"]
        ft = _s(feature, "feature_type").lower()
        if ft not in ("helper_call", "custom_command_call"):
            continue
        helper_name = _helper_seed_name(_s(feature, "name"))
        if helper_name:
            wrapper_name_counts[helper_name] += 1

    for cand in candidates:
        if not cand:
            continue
        feature = cand["feature"]
        helper_name = _helper_seed_name(_s(feature, "helper_name"))
        if not helper_name:
            continue
        if int(feature.get("helper_depth") or 0) <= 0 and _s(feature, "source_kind") != "cypress_command":
            continue
        primary = classify_primary_intent(
            feature,
            cand["provenance_hints"],
            eligibility_basis=cand["eligibility_basis"],
        )
        seed = _helper_child_seed_key(feature)
        if seed:
            by_seed.setdefault(seed, Counter())[primary] += 1
            totals_by_seed[seed] += 1
        by_name.setdefault(helper_name, Counter())[primary] += 1
        totals_by_name[helper_name] += 1

    for cand in candidates:
        if not cand:
            continue
        feature = cand["feature"]
        ft = _s(feature, "feature_type").lower()
        if ft not in ("helper_call", "custom_command_call"):
            continue
        helper_name = _helper_seed_name(_s(feature, "name"))
        seed = _helper_wrapper_call_seed_key(feature)
        counts = by_seed.get(seed) if seed else None
        total = totals_by_seed[seed] if seed and counts else 0
        if not counts and wrapper_name_counts[helper_name] == 1:
            counts = by_name.get(helper_name)
            total = totals_by_name[helper_name] if counts else 0
        if not counts:
            continue
        dominant, dominant_count = counts.most_common(1)[0]
        mixed_score = round(1 - (dominant_count / total), 6) if total else 0
        feature["child_setup_unit_count"] = total
        feature["child_intent_counts_json"] = json.dumps(dict(counts), sort_keys=True)
        feature["dominant_child_intent"] = dominant
        feature["mixed_intent_score"] = mixed_score
        feature["structured_evidence_available"] = 1


def should_enqueue_intent_review(reasons: List[str]) -> bool:
    actionable = {r for r in reasons if r != "not_applicable"}
    return bool(actionable)


def build_intent_candidate(feature: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    eligible, basis = is_eligible_setup_teardown_unit(feature)
    if not eligible:
        return None
    hints = map_provenance_hints(feature)
    return {
        "feature": dict(feature),
        "eligibility_basis": basis,
        "provenance_hints": hints,
        "line": _line(feature),
    }


def _prior_setup_blocks_nav(resolved: List[Dict[str, Any]], nav_cand: Dict[str, Any]) -> bool:
    """Return True when prior setup should block navigation bootstrap for this candidate."""
    nav_feature = nav_cand["feature"]
    nav_hook_key = _s(nav_feature, "hook_instance_key")
    nav_line = nav_cand["line"]
    for row in resolved:
        phase = row.get("phase")
        if phase not in ("setup", "setup_and_teardown"):
            continue
        prior_line = int(row.get("line") or 0)
        if prior_line >= nav_line:
            continue
        prior_hook_key = _s(row, "hook_instance_key")
        if nav_hook_key and prior_hook_key and nav_hook_key == prior_hook_key:
            continue
        return True
    return False


def _candidate_callsite_line(feature: Dict[str, Any], fallback_line: int) -> int:
    """Prefer the test-body helper callsite over helper implementation body lines."""
    for key in (
        "matched_helper_call_line",
        "helper_call_line",
        "call_line",
        "line",
    ):
        value = _int_feature_field(feature, key)
        if value:
            return value
    return int(fallback_line or 0)


def _candidate_has_lifecycle_anchor(feature: Dict[str, Any]) -> bool:
    sk = _s(feature, "source_kind")
    return bool(
        sk in HOOK_SOURCE_KINDS
        or feature.get("attached_from_hook")
        or _s(feature, "hook_instance_key")
    )


def _candidate_within_setup_window(
    cand: Dict[str, Any],
    *,
    first_non_navigation_ui_line: int,
) -> bool:
    """Conservative lifecycle placement gate for inline/helper-expanded rows.

    Hook-attached rows are already lifecycle anchored. Test-body rows and helper
    implementation rows reached from a test-body call are setup/teardown units
    only when their callsite appears before the first non-navigation UI action.
    This avoids classifying stateful API calls inside the exercised workflow as
    setup just because the callee is known.
    """
    feature = cand["feature"]
    if _candidate_has_lifecycle_anchor(feature):
        return True
    if not first_non_navigation_ui_line:
        return True
    anchor = _candidate_callsite_line(feature, cand.get("line") or 0)
    if not anchor:
        return False
    return anchor <= first_non_navigation_ui_line


def _intent_row_rank(row: Dict[str, Any]) -> tuple:
    intent = row.get("primary_intent") or ""
    conf = row.get("confidence") or ""
    intent_rank = 0 if intent == "unclear" else 1
    conf_rank = _INTENT_CONFIDENCE_RANK.get(conf, 0)
    return (intent_rank, conf_rank, int(row.get("line") or 0))


def _intent_dedupe_key(row: Dict[str, Any]) -> tuple:
    start = int(row.get("source_start_offset") or 0)
    end = int(row.get("source_end_offset") or 0)
    fp = row.get("file_path") or ""
    if fp and start and end:
        return (
            row.get("repo") or "",
            row.get("test_id") or "",
            fp,
            start,
            end,
        )
    return (
        row.get("repo") or "",
        row.get("test_id") or "",
        int(row.get("line") or 0),
        row.get("name") or "",
    )


def dedupe_intent_rows(rows: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], int]:
    """Collapse duplicate semantic rows for the same call site (offsets preferred)."""
    best: Dict[tuple, Dict[str, Any]] = {}
    dropped = 0
    for row in rows:
        key = _intent_dedupe_key(row)
        existing = best.get(key)
        if existing is None:
            best[key] = row
        elif _intent_row_rank(row) > _intent_row_rank(existing):
            best[key] = row
            dropped += 1
        else:
            dropped += 1
    out = list(best.values())
    out.sort(key=lambda r: (int(r.get("line") or 0), r.get("name") or ""))
    return out, dropped


def resolve_test_intent_units(
    candidates: List[Dict[str, Any]],
    *,
    first_non_navigation_ui_line: int = 0,
) -> tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Classify all eligible units for one test; apply navigation bootstrap heuristic."""
    candidates = [c for c in candidates if c]
    annotate_helper_child_intent_summaries(candidates)
    nav_candidates = [
        c for c in candidates
        if c["eligibility_basis"] in ("navigation_bootstrap_candidate", "navigation_bootstrap_ast")
    ]
    pre_window_other_candidates = [
        c for c in candidates
        if c["eligibility_basis"] not in ("navigation_bootstrap_candidate", "navigation_bootstrap_ast")
    ]
    lifecycle_window_rejected = 0
    other_candidates: List[Dict[str, Any]] = []
    for cand in pre_window_other_candidates:
        if _candidate_within_setup_window(
            cand,
            first_non_navigation_ui_line=first_non_navigation_ui_line,
        ):
            other_candidates.append(cand)
        else:
            lifecycle_window_rejected += 1
    nav_candidates.sort(key=lambda c: (c["line"], _s(c["feature"], "name")))
    other_candidates.sort(key=lambda c: (c["line"], _s(c["feature"], "name")))

    resolved: List[Dict[str, Any]] = []
    for cand in other_candidates:
        resolved.append(_classify_candidate(cand, navigation_bootstrap_rejected=False))

    rejected_nav_count = 0
    bootstrap_accepted = False
    for idx, cand in enumerate(nav_candidates):
        line = cand["line"]
        rejected = False
        include = False
        if bootstrap_accepted:
            rejected = True
        elif _prior_setup_blocks_nav(resolved, cand):
            rejected = True
        elif idx == 0 and (first_non_navigation_ui_line == 0 or line <= first_non_navigation_ui_line):
            include = True
        elif line < first_non_navigation_ui_line and first_non_navigation_ui_line > 0:
            include = True
        else:
            rejected = True

        if include:
            row = _classify_candidate(cand, navigation_bootstrap_rejected=False)
            if row.get("primary_intent") != "navigation_bootstrap":
                row["phase"] = "setup"
                resolved.append(row)
                continue
            nav_basis = (
                "ast_framework_api_category"
                if cand["eligibility_basis"] == "navigation_bootstrap_ast"
                else "lexical_navigation_call"
            )
            row["primary_intent"] = "navigation_bootstrap"
            row["primary_intent_evidence_basis"] = nav_basis
            row["phase"] = "setup"
            row["confidence"] = "medium"
            row["eligibility_basis"] = "navigation_bootstrap_accepted"
            row["fallback_used"] = 1 if _primary_intent_basis_is_fallback(nav_basis) else 0
            reasons = intent_review_reasons(
                cand["feature"],
                cand["provenance_hints"],
                primary_intent="navigation_bootstrap",
                confidence="medium",
                eligibility_basis="navigation_bootstrap_candidate",
                primary_intent_basis=nav_basis,
            )
            row["review_reason"] = "|".join(reasons) if reasons else ""
            row["uncertain_reason"] = _uncertain_reason(
                cand["feature"],
                reasons,
                primary_intent="navigation_bootstrap",
            )
            row["needs_review"] = 1 if should_enqueue_intent_review(reasons) else 0
            resolved.append(row)
            bootstrap_accepted = True
        elif rejected:
            rejected_nav_count += 1

    resolved.sort(key=lambda r: (int(r.get("line") or 0), r.get("name") or ""))
    deduped, dedupe_dropped = dedupe_intent_rows(resolved)
    stats = {
        "navigation_bootstrap_rejected": rejected_nav_count,
        "intent_rows_deduplicated": dedupe_dropped,
        "lifecycle_window_rejected": lifecycle_window_rejected,
    }
    return deduped, stats


def _classify_candidate(cand: Dict[str, Any], *, navigation_bootstrap_rejected: bool) -> Dict[str, Any]:
    feature = cand["feature"]
    hints = cand["provenance_hints"]
    basis = cand["eligibility_basis"]
    phase = classify_phase(feature, hints)
    scope = classify_scope(feature, hints)
    primary, primary_basis = classify_primary_intent_detail(feature, hints, eligibility_basis=basis)
    operation_kind, operation_kind_basis = classify_operation_kind_detail(
        feature,
        hints,
        primary_intent=primary,
        primary_intent_basis=primary_basis,
    )
    confidence = classify_confidence(feature, hints, primary, basis, primary_basis)
    reasons = intent_review_reasons(
        feature,
        hints,
        primary_intent=primary,
        confidence=confidence,
        eligibility_basis=basis,
        primary_intent_basis=primary_basis,
        navigation_bootstrap_rejected=navigation_bootstrap_rejected,
    )
    needs_review = should_enqueue_intent_review(reasons)
    structured = _structured_evidence_available(feature, hints)
    fallback = _fallback_used(feature, hints, basis, primary_basis)
    child_fields = _child_summary_fields(feature)
    inv = hints.get("inventory_category") or classify_setup(
        _s(feature, "name"), _s(feature, "raw_code"), _s(feature, "source_kind"), _s(feature, "feature_type")
    )
    return {
        "repo": _s(feature, "repo"),
        "test_id": _s(feature, "test_id"),
        "framework": _s(feature, "framework"),
        "phase1_confidence": _s(feature, "phase1_confidence"),
        "file_path": _s(feature, "file_path"),
        "source_start_offset": int(feature.get("source_start_offset") or 0),
        "source_end_offset": int(feature.get("source_end_offset") or 0),
        "line": _line(feature),
        "name": _s(feature, "name"),
        "raw_code": (_s(feature, "raw_code")[:500]),
        "feature_type": _s(feature, "feature_type"),
        "source_kind": _s(feature, "source_kind"),
        "helper_depth": int(feature.get("helper_depth") or 0),
        "attached_from_hook": bool(feature.get("attached_from_hook")),
        "inventory_category": inv,
        "phase": phase,
        "scope": scope,
        "primary_intent": primary,
        "primary_intent_evidence_basis": primary_basis,
        "operation_kind": operation_kind,
        "operation_kind_evidence_basis": operation_kind_basis,
        "confidence": confidence,
        "needs_review": 1 if needs_review else 0,
        "review_reason": "|".join(reasons) if reasons else "",
        "uncertain_reason": _uncertain_reason(
            feature,
            reasons,
            primary_intent=primary,
        ),
        "fallback_used": fallback,
        "structured_evidence_available": 1 if structured else 0,
        "helper_resolution_status": hints.get("helper_resolution_status") or _s(feature, "helper_resolution_status"),
        **child_fields,
        "provenance_basis": "|".join(provenance_basis_labels(hints)),
        "eligibility_basis": basis,
        "partial_coverage_note": "",
        "hook_instance_key": _s(feature, "hook_instance_key"),
        "wrapper_only": 1 if feature.get("wrapper_only") else 0,
    }


def paper_facing_intent_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Exclude wrapper-only helper calls when expansion succeeded (Option B policy)."""
    return [r for r in rows if not int(r.get("wrapper_only") or 0)]


def summarize_rq1_intent_by_test(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    from collections import Counter

    paper_rows = paper_facing_intent_rows(rows)
    wrapper_count = sum(int(r.get("wrapper_only") or 0) for r in rows)
    phase_c = Counter(r.get("phase") or "" for r in paper_rows)
    scope_c = Counter(r.get("scope") or "" for r in paper_rows)
    intent_c = Counter(r.get("primary_intent") or "" for r in paper_rows)
    operation_kind_c = Counter(
        r.get("operation_kind")
        or ("cleanup_restore" if r.get("primary_intent") == "cleanup_restore_state" else "other_setup_teardown")
        for r in paper_rows
    )
    conf_c = Counter(r.get("confidence") or "" for r in paper_rows)
    non_unclear = [r for r in paper_rows if r.get("primary_intent") != "unclear"]
    high_non_unclear = [r for r in non_unclear if r.get("confidence") == "high"]
    inline_count = sum(1 for r in paper_rows if r.get("scope") == "inline_test_body")
    hook_count = sum(1 for r in paper_rows if r.get("scope") == "per_test_hook")
    helper_count = sum(1 for r in paper_rows if r.get("scope") == "helper_or_framework_extension")
    return {
        "setup_teardown_intent_unit_count": len(paper_rows),
        "wrapper_call_count": wrapper_count,
        "body_statement_count": len(paper_rows),
        "paper_facing_unit_count": len(paper_rows),
        "intent_unit_count_including_wrappers": len(rows),
        "setup_unit_count": phase_c.get("setup", 0),
        "teardown_unit_count": phase_c.get("teardown", 0),
        "setup_and_teardown_unit_count": phase_c.get("setup_and_teardown", 0),
        "inline_setup_teardown_count": inline_count,
        "hook_setup_teardown_count": hook_count,
        "helper_setup_teardown_count": helper_count,
        "phase_counts_json": json.dumps(dict(phase_c)),
        "scope_counts_json": json.dumps(dict(scope_c)),
        "primary_intent_counts_json": json.dumps(dict(intent_c)),
        "operation_kind_counts_json": json.dumps(dict(operation_kind_c)),
        "cleanup_restore_operation_count": operation_kind_c.get("cleanup_restore", 0),
        "confidence_counts_json": json.dumps(dict(conf_c)),
        "needs_review_count": sum(int(r.get("needs_review") or 0) for r in paper_rows),
        "high_confidence_count": conf_c.get("high", 0),
        "unclear_primary_intent_count": intent_c.get("unclear", 0),
        "navigation_bootstrap_count": intent_c.get("navigation_bootstrap", 0),
        "high_confidence_non_unclear_count": len(high_non_unclear),
    }


def summarize_rq1_intent_corpus(
    all_rows: List[Dict[str, Any]],
    *,
    navigation_bootstrap_rejected: int = 0,
    intent_rows_deduplicated: int = 0,
    lifecycle_window_rejected: int = 0,
) -> Dict[str, Any]:
    from collections import Counter

    taxonomy = load_taxonomy()
    paper_rows = paper_facing_intent_rows(all_rows)
    total = len(paper_rows)
    wrapper_count = sum(int(r.get("wrapper_only") or 0) for r in all_rows)
    needs_review = sum(int(r.get("needs_review") or 0) for r in paper_rows)
    non_unclear = [r for r in paper_rows if r.get("primary_intent") != "unclear"]
    high_non_unclear = [r for r in non_unclear if r.get("confidence") == "high"]
    intent_c = Counter(r.get("primary_intent") or "" for r in paper_rows)
    nav_rejected = sum(
        1 for r in all_rows if "partial_coverage_m3" in (r.get("review_reason") or "")
    )
    return {
        "partial_coverage_note": taxonomy.get("partial_coverage_note", ""),
        "intent_event_rows": total,
        "wrapper_call_count": wrapper_count,
        "body_statement_count": total,
        "paper_facing_unit_count": total,
        "intent_unit_count_including_wrappers": len(all_rows),
        "tests_with_intent_units": len({(r.get("repo"), r.get("test_id")) for r in paper_rows}),
        "needs_review_rows": needs_review,
        "needs_review_fraction": round(needs_review / total, 6) if total else "",
        "primary_intent_distribution": dict(intent_c.most_common()),
        "high_confidence_non_unclear_fraction": (
            round(len(high_non_unclear) / len(non_unclear), 6) if non_unclear else ""
        ),
        "unclear_primary_intent_fraction": (
            round(intent_c.get("unclear", 0) / total, 6) if total else ""
        ),
        "navigation_bootstrap_count": intent_c.get("navigation_bootstrap", 0),
        "navigation_bootstrap_rejected": navigation_bootstrap_rejected,
        "intent_rows_deduplicated": intent_rows_deduplicated,
        "lifecycle_window_rejected": lifecycle_window_rejected,
        "partial_coverage_m3_flag_rows": nav_rejected,
    }
