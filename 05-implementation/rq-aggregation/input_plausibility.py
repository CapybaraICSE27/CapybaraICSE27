"""RQ2 input plausibility resolver (separate from source/provenance)."""

from __future__ import annotations

import re
from typing import Dict, Tuple

INPUT_PLAUSIBILITY_LABELS = (
    "domain_plausible_input",
    "placeholder_or_dummy_input",
    "validation_or_edge_case_input",
    "technical_or_control_input",
    "not_observable",
    "unclear",
)

INPUT_PLAUSIBILITY_PAPER_LABELS = (
    "domain_plausible_input",
    "placeholder_or_dummy_input",
    "validation_or_edge_case_input",
    "technical_or_configuration_or_control_input",
    "indeterminate_or_insufficient_evidence",
)

_PLACEHOLDER_TOKENS = frozenset({
    "asdf", "asd", "foo", "bar", "baz", "abcd", "lorem", "ipsum", "dummy", "testing",
    "placeholder", "sample", "example", "xxx", "yyy", "qwerty", "temp", "tmp",
    "test123", "123456", "password1", "changeme",
})
_WEAK_CONTEXTLESS_LITERALS = frozenset({"abc", "log", "test mandatory", "bar", "before", "clear"})
_OPTION_LIKE_VALUES = frozenset({"red", "blue", "green", "black", "white", "yellow", "purple", "orange", "gray", "grey"})

_TECHNICAL_TOKENS = frozenset({
    "token", "bearer", "authorization", "apikey", "api_key", "secret", "localhost",
    "true", "false", "null", "undefined", "status", "mock", "stub", "header",
})

_AMBIGUOUS_VISIBLE = frozenset({"admin", "default", "sample", "user", "guest", "demo", "name"})

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_URL_RE = re.compile(r"^https?://", re.I)
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)
_DATE_RE = re.compile(
    r"^(\d{1,4}[-/]\d{1,2}[-/]\d{1,4}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})$"
)
_IP_OR_CIDR_RE = re.compile(
    r"^(\d{1,3}\.){3}\d{1,3}(/\d{1,2})?$|^(?=.*:)[0-9a-f:]+$",
    re.I,
)
_KEYBOARD_SPECIAL_RE = re.compile(
    r"^(\{[a-z0-9+\-]+\}|Control\+[a-zA-Z]|Meta\+[a-zA-Z]|Alt\+[a-zA-Z]|Shift\+[a-zA-Z]|"
    r"Arrow(?:Up|Down|Left|Right)|Enter|Escape|Tab|Backspace|Delete|Home|End|"
    r"PageUp|PageDown|Space|Insert|F\d{1,2})$",
    re.I,
)
_CYPRESS_KEY_RE = re.compile(r"^\{[a-z0-9+\-]+\}$", re.I)
_CYPRESS_CHORD_SEQ_RE = re.compile(r"^(\{[a-z0-9+\-]+\})+$", re.I)
_CYPRESS_CHORD_INLINE_RE = re.compile(
    r"\{(ctrl|shift|alt|meta|cmd|option|selectall|backspace|downarrow|uparrow|leftarrow|rightarrow|enter|esc)\}",
    re.I,
)
_FILE_PATH_EXT_RE = re.compile(
    r"\.(pdf|png|jpe?g|gif|webp|svg|avif|mov|mp4|avi|mkv|json|csv|txt|md|markdown|xml|yaml|yml|zip|docx?|xlsx?|pptx?|html|htm|wav|mp3|webm|heic)$",
    re.I,
)
_GENERATED_DOMAIN_MEMBER_RE = re.compile(
    r"\b(fullName|displayName|taskName|username|userName|newUser|user|email|title|label|name|summary|description|message|comment|address|city|company|organization|ipv4|ssh_key|sshKey|domain|publicInfo|useCase|numberOfEntities|monitorUrl|entityTag|slug|prefix|query|upload|color|bgColor|backgroundColor|bannerBgColor)\b",
    re.I,
)
_GENERATED_TECHNICAL_MEMBER_RE = re.compile(
    r"\b(stopFrame|chunkSize|labelColor|hexColor|hex|port|status|config|token|uuid|index|offset|limit|frame|size|buffer|enabled|disabled)\b",
    re.I,
)
_GENERATED_RANDOM_TEMPLATE_RE = re.compile(
    r"\$\{?(randomIp|randomNumber|randomUUID|randomString|faker|uuid|nanoid)\(",
    re.I,
)
_LOREM_GENERATOR_RE = re.compile(r"\b(?:faker\.)?lorem(?:\.|\b)|\bipsum\b", re.I)
_TEST_TITLE_RE = re.compile(r"^test\s+(?:title|name|user|client|sample|fixture)\b", re.I)
_INVALID_EDGE_MEMBER_RE = re.compile(
    r"\b(?:invalid[a-z0-9_]*|malformed[a-z0-9_]*|expired[a-z0-9_]*|wrong[a-z0-9_]*|bad[a-z0-9_]*|empty[a-z0-9_]*|missing[a-z0-9_]*|nonMatching[a-z0-9_]*|noMatch[a-z0-9_]*|notFound[a-z0-9_]*|tooShort|tooLong|error|edge)\b",
    re.I,
)
_ENDPOINT_CONSTRUCTION_RE = re.compile(
    r"\b(?:new\s+URL|URL\s*\(|process\.env\.[A-Za-z0-9_]*(?:URL|URI|HOST|API|LOCATION|ENDPOINT)|"
    r"(?:endpoint|apiLocation|baseUrl|path)\b)",
    re.I,
)
_DOMAIN_VARIABLE_MEMBER_RE = re.compile(
    r"\b(?:username|userName|password|email|phone|display[_-]?name|fullName|shortName|"
    r"widgetName|ylabel|xLabel|label|title|summary|description|message|comment|organization|"
    r"team|channel|room|workspace|project|dataset|dataSet|table|credential|credentials|searchTerm|taskName|tax_id|taxId|ipv4|ssh_key|sshKey|newUser|domain|publicInfo|useCase|numberOfEntities|monitorUrl|entityTag|slug|prefix|query|color|bgColor|backgroundColor|attribute|attributes)\b",
    re.I,
)
_EDITOR_FILLER_RE = re.compile(r"""^\s*(?:[*+\->])\s*["'`]*foobar["'`]*\s*$|^\s*["']hello["']\s*$""", re.I)
_UPLOAD_FILENAME_RE = re.compile(r"""fileName\s*:\s*(['"])([^'"]+)\1""", re.I)
_UPLOAD_MIMETYPE_RE = re.compile(r"""mimeType\s*:\s*(['"])([^'"]+)\1""", re.I)
_API_SEED_DOMAIN_MEMBER_RE = re.compile(
    r"\b(email|username|userName|password|display_name|displayName|fullName|taskName|"
    r"channelName|channel\.display_name|teamName|team\.display_name|teamDisplayName|"
    r"memberName|groupName|roomName|boardName|title|label|name)\b",
    re.I,
)
_XSS_EDGE_RE = re.compile(r"(<script|javascript:|onerror=|'\s*or\s*'1'|DROP\s+TABLE)", re.I)
_TEST_PREFIX_RE = re.compile(r"^test[a-z0-9_\-]*$", re.I)
_IDENTIFIER_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_CAMEL_TOKEN_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z]|$)|[A-Z]?[a-z]+|[0-9]+")


def _field_suggests_email(field_context: str) -> bool:
    f = (field_context or "").lower()
    return any(k in f for k in ("email", "e-mail", "mail", "@"))


def _field_suggests_password(field_context: str) -> bool:
    f = (field_context or "").lower()
    return any(k in f for k in ("password", "passwd", "pass", "pwd"))


def _field_suggests_url(field_context: str) -> bool:
    f = (field_context or "").lower()
    return any(k in f for k in ("url", "link", "website", "href"))


def _field_suggests_phone(field_context: str) -> bool:
    f = (field_context or "").lower()
    return any(k in f for k in ("phone", "mobile", "tel"))


def _field_suggests_date(field_context: str) -> bool:
    f = (field_context or "").lower()
    return any(k in f for k in ("date", "dob", "birth", "day", "month", "year"))


def _field_suggests_name(field_context: str) -> bool:
    f = (field_context or "").lower()
    return any(k in f for k in ("name", "display", "title", "label", "username", "user name"))


def _field_suggests_message(field_context: str) -> bool:
    f = (field_context or "").lower()
    return any(k in f for k in ("message", "comment", "body", "text", "description", "content", "post", "search"))


def _field_suggests_address(field_context: str) -> bool:
    f = (field_context or "").lower()
    return any(k in f for k in ("address", "city", "street", "zip", "postal", "state", "country", "vpc", "region"))


def _field_suggests_domain_value(field_context: str) -> bool:
    return (
        _field_suggests_email(field_context)
        or _field_suggests_password(field_context)
        or _field_suggests_phone(field_context)
        or _field_suggests_date(field_context)
        or _field_suggests_name(field_context)
        or _field_suggests_message(field_context)
        or _field_suggests_address(field_context)
        or any(
            k in (field_context or "").lower()
            for k in (
                "answer",
                "channel",
                "code",
                "clientid",
                "clientsecret",
                "client_id",
                "client_secret",
                "credential",
                "credentials",
                "dataset",
                "file",
                "mfa",
                "otp",
                "oauth",
                "organization",
                "patient",
                "plugin",
                "room",
                "search",
                "secret",
                "signature",
                "slug",
                "task",
                "team",
                "tiptap",
                "editor",
                "prosemirror",
                "widget",
                "select dropdown",
                "dropdown",
                "attribute values",
            )
        )
    )


def _field_suggests_user_facing_setting_text(field_context: str) -> bool:
    f = field_context or ""
    return bool(
        re.search(
            r"(?:"
            r"TeamSettings\.SiteNameinput|channel[_-]?settings[_-]?header[_-]?textbox|"
            r"\b(?:site|team|channel)\b[\s\S]{0,40}\b(?:name|header|display|text|textbox)\b|"
            r"\b(?:name|header|display|text|textbox)\b[\s\S]{0,40}\b(?:site|team|channel)\b"
            r")",
            f,
            re.I,
        )
    )


def _field_suggests_config_or_control(field_context: str) -> bool:
    f = field_context or ""
    if _field_suggests_user_facing_setting_text(f):
        return False
    return bool(
        re.search(
            r"(?:"
            r"apiwidget|api[-_ ]?widget|endpoint|resource[-_ ]?url|resourceurl|resource[-_ ]?config|"
            r"datasource|data[-_ ]?source|base[-_ ]?url|baseurl|select[-_ ]?route|route|"
            r"pagination|webhook|remote[-_ ]?file|object[-_ ]?storage[-_ ]?endpoint|"
            r"port|config(?:uration)?|setting|constant|dashboard[-_ ]?variable|variable[-_ ]?constant|"
            r"bug[-_ ]?tracker|manifest\.jsonl|ant\s+input\s+number|numberofpoints|"
            r"methodselect|method[-_ ]?select|start[-_ ]?frame|stop[-_ ]?frame|overlap[-_ ]?size|"
            r"table[-_ ]?modal[-_ ]?columns|modal[-_ ]?columns|#startframe|#overlapsize"
            r")",
            f,
            re.I,
        )
    )


def _field_suggests_editor_content(field_context: str) -> bool:
    f = (field_context or "").lower()
    return any(k in f for k in ("tiptap", "editor", "prosemirror", "contenteditable"))


def _field_suggests_preservation_edge(field_context: str, value: str) -> bool:
    f = (field_context or "").lower()
    v = (value or "").lower()
    return ("prefix" in f or "preserve" in f) and "preserve" in v


def _field_suggests_keyboard_press_control(field_context: str) -> bool:
    f = (field_context or "").lower()
    return (
        "keyboard_control_target" in f
        or "page.keyboard.press" in f
        or "keyboard.press" in f
        or "input:press:" in f
        or re.search(r"\.press\s*\(", f) is not None
    )


def _is_cypress_chord_value(val: str) -> bool:
    if _CYPRESS_CHORD_SEQ_RE.match(val):
        return True
    if _CYPRESS_CHORD_INLINE_RE.search(val):
        return True
    if "${" in val and "}" in val and any(k in val.lower() for k in ("modifierkey", "selectall", "arrow", "enter")):
        return True
    return False


def _contains_keyboard_or_control_token(val: str) -> bool:
    text = val or ""
    if _is_cypress_chord_value(text):
        return True
    if re.search(r"\{(?:left|right|up|down)arrow\}\s*\.repeat\s*\(", text, re.I):
        return True
    if re.search(r"\{(?:enter|esc|selectall|backspace|del|delete|tab|ctrl|control|meta|cmd|shift|alt)[^}]*\}", text, re.I):
        return True
    return False


def _is_keyboard_or_control_value(val: str, input_channel: str) -> bool:
    if _is_cypress_chord_value(val):
        return True
    if _KEYBOARD_SPECIAL_RE.match(val):
        return True
    if _CYPRESS_KEY_RE.match(val):
        return True
    if _is_keyboard_key_array_literal(val, input_channel):
        return True
    if val in {"@", "~", "/"}:
        return True
    return False


def _is_keyboard_key_array_literal(val: str, input_channel: str) -> bool:
    if input_channel not in {"keyboard_entry", "keyboard_input"}:
        return False
    text = (val or "").strip()
    if not (text.startswith("[") and text.endswith("]")):
        return False
    tokens = [token.lower() for token in re.findall(r"['\"]([^'\"]+)['\"]", text)]
    if not tokens:
        return False
    known_keys = {
        "shift",
        "tab",
        "alt",
        "option",
        "meta",
        "cmd",
        "command",
        "control",
        "ctrl",
        "enter",
        "escape",
        "esc",
        "backspace",
        "delete",
        "arrowleft",
        "arrowright",
        "arrowup",
        "arrowdown",
        "left",
        "right",
        "up",
        "down",
        "home",
        "end",
        "pageup",
        "pagedown",
    }
    return all(token.replace(" ", "").replace("_", "").replace("-", "") in known_keys for token in tokens)


def _is_conditional_keyboard_or_control_expression(val: str) -> bool:
    if "?" not in (val or "") or ":" not in (val or ""):
        return False
    quoted = re.findall(r"""(['"])(.*?)\1""", val or "")
    if not quoted:
        return False
    return all(_is_keyboard_or_control_value(text, "") for _, text in quoted)


def _looks_like_natural_language(val: str) -> bool:
    words = val.split()
    if len(words) < 2:
        return False
    alpha_words = [w for w in words if re.search(r"[A-Za-z]{2,}", w)]
    return len(alpha_words) >= 2


def parse_upload_object_metadata(raw: str) -> Dict[str, str]:
    text = raw or ""
    file_name = ""
    mime = ""
    m = _UPLOAD_FILENAME_RE.search(text)
    if m:
        file_name = m.group(2)
    m = _UPLOAD_MIMETYPE_RE.search(text)
    if m:
        mime = m.group(2)
    return {"fileName": file_name, "mimeType": mime}


def upload_object_has_visible_metadata(raw: str) -> bool:
    meta = parse_upload_object_metadata(raw)
    return bool(meta["fileName"] or meta["mimeType"])


def resolve_upload_visibility(raw: str, current_visibility: str) -> str:
    if current_visibility in ("visible", "partially_visible"):
        return current_visibility
    if upload_object_has_visible_metadata(raw):
        return "partially_visible"
    return current_visibility


def format_upload_display_value(raw: str) -> str:
    meta = parse_upload_object_metadata(raw)
    if meta["fileName"] or meta["mimeType"]:
        parts = []
        if meta["fileName"]:
            parts.append(f"fileName={meta['fileName']}")
        if meta["mimeType"]:
            parts.append(f"mimeType={meta['mimeType']}")
        return "; ".join(parts)
    return format_value_for_display(raw)


def _is_generated_random_template(val: str) -> bool:
    return bool(_GENERATED_RANDOM_TEMPLATE_RE.search(val or ""))


def _looks_like_placeholder_or_dummy_expression(val: str) -> bool:
    text = (val or "").strip().strip("'\"")
    low = text.lower()
    return bool(
        _LOREM_GENERATOR_RE.search(text)
        or low in _PLACEHOLDER_TOKENS
        or low == "hello"
        or re.fullmatch(r"item\d+", low)
        or _EDITOR_FILLER_RE.search(text)
        or low.startswith("lorem")
        or _TEST_TITLE_RE.search(text)
    )


def _looks_like_explicit_placeholder_or_dummy(val: str) -> bool:
    text = (val or "").strip().strip("'\"")
    return bool(
        _LOREM_GENERATOR_RE.search(text)
        or _EDITOR_FILLER_RE.search((val or "").strip())
        or re.fullmatch(r"item\d+", text, re.I)
        or re.search(r"\b(?:dummy|sample|placeholder|lorem|ipsum)\b", text, re.I)
        or text.lower() == "hello"
        or re.search(r"^test\s+(?:room|college|user|client|sample|fixture|title|name)\b", text, re.I)
    )


def _strip_js_line_comments(text: str) -> str:
    return re.sub(r"//[^\r\n]*", "", text or "")


def _is_editor_control_literal(val: str, field_context: str) -> bool:
    text = (val or "").strip().strip("'\"`")
    if not _field_suggests_editor_content(field_context):
        return False
    return text in {"---", "***", "___", "```"}


def _looks_like_invalid_or_edge_expression(val: str) -> bool:
    if _INVALID_EDGE_MEMBER_RE.search(val or "") or _XSS_EDGE_RE.search(val or ""):
        return True
    tokens = _identifier_tokens(val or "")
    return bool(
        tokens
        & {
            "invalid",
            "malformed",
            "expired",
            "wrong",
            "bad",
            "empty",
            "missing",
            "non",
            "matching",
            "nomatch",
            "notfound",
            "too",
            "short",
            "long",
            "error",
            "edge",
        }
    ) and bool(tokens & {"invalid", "malformed", "expired", "wrong", "bad", "empty", "missing", "nomatch", "notfound", "error", "edge"} or {"too", "short"}.issubset(tokens) or {"too", "long"}.issubset(tokens) or {"non", "matching"}.issubset(tokens))


def _looks_like_html_template_filler(val: str) -> bool:
    text = val or ""
    if not re.search(r"(?:html`|<[a-z][\s>])", text, re.I):
        return False
    return bool(re.search(r"\b(?:foo|foobar|hello\s+world|lorem|ipsum|dummy|sample)\b", text, re.I))


def _looks_like_endpoint_construction(val: str) -> bool:
    text = val or ""
    if not _ENDPOINT_CONSTRUCTION_RE.search(text):
        return False
    return bool(
        re.search(r"\b(?:URL|URI|HOST|API|LOCATION|ENDPOINT|baseUrl|endpoint|path)\b", text)
        or re.search(r"""['"][^'"]*/[^'"]*['"]""", text)
    )


def _field_suggests_endpoint_or_resource_config(field_context: str) -> bool:
    f = field_context or ""
    return bool(
        _field_suggests_config_or_control(f)
        or
        re.search(
            r"\b(?:api|endpoint|resource|datasource|pagination|baseurl|base_url|uri|host|path|webhook)\b",
            f,
            re.I,
        )
        or re.search(r"(?:editResourceUrl|apiPagination|resourceUrl|datasourceEditor\.url|#url|\\[data-test=['\"]url)", f, re.I)
    )


def _looks_like_endpoint_value_for_field(val: str, field_context: str) -> bool:
    text = val or ""
    if _looks_like_endpoint_construction(text):
        return True
    if not _field_suggests_endpoint_or_resource_config(field_context):
        return False
    if re.search(r"\b(?:profile|display|patient|instruction|message|comment|description|search|filter|reply|prompt|email|password|username)\b", field_context or "", re.I):
        return False
    return bool(
        re.search(r"\b(?:url|uri|path|route|endpoint|parameters?|params|baseUrl|paginationUrl|prevUrl|nextUrl|resourceUrl|datasource|datasourceName|resourceName|endpointName|apiName|startFrame|stopFrame|overlapSize|columns|method)\b", text, re.I)
        or re.search(r"\b(?:url_parameter_concatenation|resource_config_identifier|url_constructor|endpoint_or_resource_config_field)\b", field_context, re.I)
        or "+" in text
        or "/" in text
        or bool(re.match(r"^[A-Za-z_$][A-Za-z0-9_$.]*$", text.strip().strip("'\"")))
    )


def _field_suggests_meaningful_member_target(field_context: str) -> bool:
    f = field_context or ""
    if _field_suggests_config_or_control(f):
        return False
    return bool(
        re.search(
            r"(?:filterInput|filter[-_ ]?input|replyTextBox|reply[-_ ]?text[-_ ]?box|promptInput|"
            r"prompt[-_ ]?input|inputValue|input[-_ ]?value|toneSelect|tone[-_ ]?select|"
            r"serialNumberInput|serial[-_ ]?number|modelNumberInput|model[-_ ]?number|"
            r"dosage[-_ ]?form|searchInput|search[-_ ]?input|textBox|textbox|editor|tiptap|"
            r"select[-_ ]?dropdown|dropdown|attribute[-_ ]?values?|attributes?[-_ ]?values?)",
            f,
            re.I,
        )
    )


def _field_suggests_style_option(field_context: str) -> bool:
    f = (field_context or "").lower()
    return any(k in f for k in ("color", "font", "style", "theme", "fill", "background", "border"))


def _field_suggests_file_upload(field_context: str) -> bool:
    return bool(
        re.search(
            r"\b(?:file|upload|image|video|audio|avatar|plugin|document|fileinput|setinputfiles|selectfile|dropzone)\b",
            field_context or "",
            re.I,
        )
        or re.search(r"input\[type\s*=\s*['\"]file", field_context or "", re.I)
    )


def _visible_domain_value_from_context(
    value_redacted: str,
    field_context: str,
    input_source_class: str,
    input_channel: str,
) -> bool:
    if input_channel not in {"ui_text_entry", "text_entry", "keyboard_entry", "ui_selection", ""}:
        return False
    text = f"{value_redacted} {field_context}"
    if _field_suggests_domain_value(field_context) and (
        input_source_class in {
            "api_seed_input",
            "environment_input",
            "external_file_input",
            "fixture_file_input",
            "unknown_input",
            "variable_from_external_file",
            "variable_input",
        }
        or _DOMAIN_VARIABLE_MEMBER_RE.search(text)
    ):
        return True
    return bool(
        input_source_class in {"api_seed_input", "external_file_input", "variable_from_external_file"}
        and (_DOMAIN_VARIABLE_MEMBER_RE.search(text) or _api_seed_text_suggests_domain(value_redacted, field_context))
    )


def map_input_plausibility_paper_label(label: str) -> str:
    """Map detailed RQ2 plausibility labels to the paper-facing merged codebook."""
    normalized = (label or "").strip()
    if normalized == "technical_or_control_input":
        return "technical_or_configuration_or_control_input"
    if normalized in {"not_observable", "unclear", ""}:
        return "indeterminate_or_insufficient_evidence"
    if normalized in INPUT_PLAUSIBILITY_PAPER_LABELS:
        return normalized
    return "indeterminate_or_insufficient_evidence"


def _identifier_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for ident in _IDENTIFIER_RE.findall(text or ""):
        for part in re.split(r"[_$.-]+", ident):
            if not part:
                continue
            split = _CAMEL_TOKEN_RE.findall(part)
            tokens.update((tok or part).lower() for tok in (split or [part]))
    return tokens


def _api_seed_text_suggests_domain(value_redacted: str, field_context: str) -> bool:
    if _API_SEED_DOMAIN_MEMBER_RE.search(f"{value_redacted} {field_context}"):
        return True
    tokens = _identifier_tokens(f"{value_redacted} {field_context}")
    return bool(
        tokens
        & {
            "board",
            "channel",
            "display",
            "email",
            "full",
            "group",
            "label",
            "member",
            "room",
            "team",
            "title",
            "username",
        }
    )


def _resolve_api_seed_plausibility(value_redacted: str, field_context: str) -> Tuple[str, str, bool]:
    """
    API-seeded setup data typed into UI fields.

    Default: technical_or_control_input (test harness state).
    When member/field context suggests a domain-facing field, allow domain_plausible_input
    with review because the concrete value is usually opaque.
    """
    text = f"{value_redacted} {field_context}"
    if _field_suggests_domain_value(field_context) and re.search(r"\b(?:token|code|otp|mfa|credential|password|username|email)\b", text, re.I):
        return "domain_plausible_input", "medium", True
    if _generated_member_suggests_domain(value_redacted, field_context):
        return "domain_plausible_input", "medium", True
    if _api_seed_text_suggests_domain(value_redacted, field_context) and (
        _field_suggests_email(field_context)
        or _field_suggests_password(field_context)
        or _field_suggests_name(field_context)
        or _field_suggests_message(field_context)
    ):
        return "domain_plausible_input", "medium", True
    if _api_seed_text_suggests_domain(value_redacted, field_context):
        return "domain_plausible_input", "medium", True
    return "technical_or_control_input", "medium", False


def _upload_expression_has_visible_file_hint(text: str) -> bool:
    lowered = text or ""
    if _looks_like_visible_upload_path(lowered.strip().strip("'\"")):
        return True
    for quoted in re.findall(r"""['"]([^'"]+)['"]""", lowered):
        if _looks_like_visible_upload_path(quoted):
            return True
    return bool(
        re.search(r"\b(path\.(?:resolve|join)|getSampleFilePath|fixturePath|filePath|imagePath|jsonPath|csvPath)\b", lowered)
        and re.search(r"\.(?:pdf|png|jpe?g|gif|webp|svg|avif|json|csv|txt|md|xml|ya?ml|zip|docx?|xlsx?|html?)\b", lowered, re.I)
    )


def _upload_variable_name_has_file_hint(text: str) -> bool:
    compact = re.sub(r"[^A-Za-z0-9_$]+", " ", text or "")
    return bool(
        re.search(
            r"\b(?:test|sample|new|fixture)?(?:image|csv|json|video|audio|avatar|upload|file|document|pdf|plugin)\w*paths?\b",
            compact,
            re.I,
        )
        or re.search(r"\b(?:csv|json|image|video|avatar|fixture|plugin)paths?\b", compact, re.I)
        or re.search(r"\b(?:videoPaths|validImagePath|testPluginPath)\b", text or "", re.I)
    )


def _resolve_upload_plausibility(
    raw_val: str, val: str, value_visibility: str, field_context: str = ""
) -> Tuple[str, str, bool] | None:
    signal_text = _strip_js_line_comments(f"{raw_val} {val}")
    if re.search(r"\b(?:invalid\w*path|malformed\w*path|expired\w*path|wrong\w*path|bad\w*path|exceed(?:ed|s)?[-_ ]?limit|too[-_ ]?large|over[-_ ]?limit)\b", signal_text, re.I):
        return "validation_or_edge_case_input", "medium", True
    if upload_object_has_visible_metadata(raw_val):
        return "domain_plausible_input", "medium", False
    if re.search(r"\bfileName\b", raw_val or "", re.I) and re.search(
        r"\b(?:mimeType|buffer|contents?)\b", raw_val or "", re.I
    ):
        return "domain_plausible_input", "medium", True
    if _looks_like_visible_upload_path(val):
        return "domain_plausible_input", "medium", False
    if _upload_expression_has_visible_file_hint(f"{raw_val} {val}"):
        return "domain_plausible_input", "medium", False
    if _upload_variable_name_has_file_hint(f"{raw_val} {val}"):
        return "domain_plausible_input", "medium", True
    if _field_suggests_file_upload(field_context) and re.search(r"[A-Za-z_$][A-Za-z0-9_$.]*", f"{raw_val} {val}"):
        return "domain_plausible_input", "medium", True
    if val.startswith(("{", "[", "path.", "Cypress.", "new Uint8Array")):
        return "technical_or_control_input", "medium", False
    if value_visibility in ("opaque", "unknown"):
        return "not_observable", "medium", False
    return None


def format_value_for_display(value: str | None) -> str:
    """Human-readable value for audit CSVs (empty strings are explicit)."""
    if value is None:
        return "<EMPTY_STRING>"
    text = str(value)
    if text.lower() in ("nan", "none", "null"):
        return "<EMPTY_STRING>"
    if text in ('""', "''"):
        return "<EMPTY_STRING>"
    if text == "":
        return "<EMPTY_STRING>"
    if text.isspace():
        return "<WHITESPACE_ONLY>"
    return text


def _looks_like_visible_upload_path(val: str) -> bool:
    if not val or val.isspace():
        return False
    if val.startswith(("{", "[", "path.", "Cypress.Buffer", "new Uint8Array")):
        return False
    cleaned = val.split("?")[0].split("#")[0]
    if _FILE_PATH_EXT_RE.search(cleaned):
        return True
    if ("/" in cleaned or "\\" in cleaned) and re.search(r"[A-Za-z0-9]", cleaned):
        return True
    return False


def _generated_member_suggests_domain(value_redacted: str, field_context: str) -> bool:
    text = f"{value_redacted} {field_context}"
    if _GENERATED_DOMAIN_MEMBER_RE.search(text):
        return True
    tokens = _identifier_tokens(text)
    return bool("color" in tokens and (tokens & {"banner", "bg", "background"}))


def _generated_member_suggests_technical(value_redacted: str, field_context: str) -> bool:
    text = f"{value_redacted} {field_context}"
    return bool(_GENERATED_TECHNICAL_MEMBER_RE.search(text))


def _resolve_generated_opaque_plausibility(
    value_redacted: str, field_context: str
) -> Tuple[str, str, bool]:
    if _looks_like_placeholder_or_dummy_expression(value_redacted):
        return "placeholder_or_dummy_input", "medium", True
    if _is_generated_random_template(value_redacted):
        return "technical_or_control_input", "medium", False
    if _generated_member_suggests_domain(value_redacted, field_context):
        return "domain_plausible_input", "medium", True
    if _generated_member_suggests_technical(value_redacted, field_context):
        return "technical_or_control_input", "medium", False
    return "technical_or_control_input", "medium", False


def _resolve_input_plausibility_tuple(
    *,
    value_redacted: str,
    field_context: str,
    value_visibility: str,
    input_source_class: str,
    input_channel: str = "",
) -> Tuple[str, str, bool]:
    """Return (input_plausibility, confidence, needs_review)."""
    raw_val = value_redacted or ""
    if str(field_context or "").strip().lower() in {"none", "null"}:
        field_context = ""
    stripped_val = raw_val.strip().strip("'\"")
    low_val = stripped_val.lower()
    if _field_suggests_keyboard_press_control(field_context):
        return "technical_or_control_input", "high", False
    if input_channel in {"keyboard_press", "key_press"}:
        return "technical_or_control_input", "high", False
    if not (field_context or "").strip() and _looks_like_html_template_filler(raw_val):
        return "placeholder_or_dummy_input", "medium", False
    if input_channel in {"keyboard_entry", "keyboard_input"} and not (field_context or "").strip():
        if _looks_like_html_template_filler(raw_val):
            return "placeholder_or_dummy_input", "medium", False
        if low_val in {"test", "hello", "hello world", "example", "sample"}:
            return "placeholder_or_dummy_input", "medium", False
        if not stripped_val or low_val in {"none", "null"}:
            return "technical_or_control_input", "high", False
    if _field_suggests_preservation_edge(field_context, raw_val):
        return "validation_or_edge_case_input", "high", False
    if _field_suggests_config_or_control(field_context) and re.match(r"^[0-9]+$", stripped_val):
        return "technical_or_control_input", "high", False
    if input_source_class == "file_upload_input":
        upload = _resolve_upload_plausibility(raw_val, stripped_val, value_visibility, field_context)
        if upload:
            return upload
    if (
        input_source_class == "literal_input"
        and value_visibility in {"visible", "partially_visible"}
        and not (field_context or "").strip()
        and (low_val in _WEAK_CONTEXTLESS_LITERALS or _EMAIL_RE.match(stripped_val))
    ):
        return "unclear", "medium", True
    if _is_conditional_keyboard_or_control_expression(raw_val):
        return "technical_or_control_input", "medium", False
    if _is_keyboard_or_control_value(raw_val.strip().strip("'\""), input_channel):
        return "technical_or_control_input", "high", False
    if _contains_keyboard_or_control_token(raw_val):
        return "technical_or_control_input", "medium", False
    if _looks_like_invalid_or_edge_expression(raw_val):
        return "validation_or_edge_case_input", "medium", True
    if input_source_class != "file_upload_input" and _looks_like_endpoint_value_for_field(raw_val, field_context):
        return "technical_or_control_input", "medium", False
    if _looks_like_explicit_placeholder_or_dummy(raw_val):
        confidence = "high" if value_visibility == "visible" else "medium"
        return "placeholder_or_dummy_input", confidence, value_visibility != "visible"
    if _field_suggests_meaningful_member_target(field_context) and re.search(r"[A-Za-z0-9]", raw_val):
        return "domain_plausible_input", "medium", input_source_class not in {"literal_input"}
    if _is_editor_control_literal(raw_val, field_context):
        return "technical_or_control_input", "high", False
    if _field_suggests_style_option(field_context) and raw_val.strip().strip("'\"").lower() in _OPTION_LIKE_VALUES:
        return "domain_plausible_input", "medium", False
    if (
        input_source_class in {"generated_input", "variable_input", "unknown_input"}
        and _field_suggests_domain_value(field_context)
        and re.match(r"^[A-Za-z_$][A-Za-z0-9_$.]*$", raw_val.strip().strip("'\""))
        and not _looks_like_explicit_placeholder_or_dummy(raw_val)
    ):
        return "domain_plausible_input", "medium", True
    if _looks_like_placeholder_or_dummy_expression(raw_val) and not (
        (input_source_class == "api_seed_input" and _api_seed_text_suggests_domain(raw_val, field_context))
        or (
            input_source_class in {"variable_input", "unknown_input", "generated_input", "variable_from_external_file"}
            and _field_suggests_domain_value(field_context)
            and re.match(r"^[A-Za-z_$][A-Za-z0-9_$.]*$", raw_val.strip().strip("'\""))
        )
    ):
        confidence = "high" if value_visibility == "visible" else "medium"
        return "placeholder_or_dummy_input", confidence, value_visibility != "visible"
    if raw_val.strip() in {"", '""', "''"} and value_visibility in {"visible", "partially_visible"}:
        return "validation_or_edge_case_input", "high", False
    if (
        input_source_class == "literal_input"
        and value_visibility in {"visible", "partially_visible"}
        and _field_suggests_editor_content(field_context)
        and re.search(r"[A-Za-z0-9_$]", raw_val)
    ):
        return "domain_plausible_input", "medium", False
    if _visible_domain_value_from_context(raw_val, field_context, input_source_class, input_channel):
        return "domain_plausible_input", "medium", True
    if (
        input_channel in {"ui_text_entry", "text_entry", "keyboard_entry", ""}
        and input_source_class in {"variable_input", "unknown_input", "generated_input", "variable_from_external_file", "api_seed_input"}
        and (_DOMAIN_VARIABLE_MEMBER_RE.search(raw_val) or _generated_member_suggests_domain(raw_val, field_context))
        and not _looks_like_invalid_or_edge_expression(raw_val)
        and not _generated_member_suggests_technical(raw_val, field_context)
    ):
        return "domain_plausible_input", "medium", True
    if value_visibility in ("opaque", "unknown") or input_source_class in (
        "variable_input",
        "unknown_input",
    ):
        if input_source_class == "file_upload_input":
            upload = _resolve_upload_plausibility(raw_val, raw_val.strip().strip("'\""), value_visibility)
            if upload:
                return upload
        if input_source_class == "generated_input":
            return _resolve_generated_opaque_plausibility(raw_val, field_context)
        if input_source_class == "environment_input":
            if _visible_domain_value_from_context(raw_val, field_context, input_source_class, input_channel):
                return "domain_plausible_input", "medium", True
            return "technical_or_control_input", "medium", False
        if input_source_class == "api_seed_input":
            return _resolve_api_seed_plausibility(raw_val, field_context)
        if input_source_class in ("fixture_file_input", "external_file_input", "variable_from_external_file"):
            if _visible_domain_value_from_context(raw_val, field_context, input_source_class, input_channel):
                return "domain_plausible_input", "medium", True
            return "not_observable", "medium", False
        if _visible_domain_value_from_context(raw_val, field_context, input_source_class, input_channel):
            return "domain_plausible_input", "medium", True
        return "not_observable", "high", False

    val = raw_val.strip().strip("'\"")
    low = val.lower()

    if input_source_class == "file_upload_input":
        upload = _resolve_upload_plausibility(raw_val, val, value_visibility, field_context)
        if upload:
            return upload

    if _is_keyboard_or_control_value(val, input_channel):
        return "technical_or_control_input", "high", False

    if val == "" or val in ('""', "''") or val.isspace():
        return "validation_or_edge_case_input", "high", False

    if _XSS_EDGE_RE.search(val) or low in {"null", "undefined", "nan"}:
        return "validation_or_edge_case_input", "high", False

    if _IP_OR_CIDR_RE.match(val):
        return "technical_or_control_input", "high", False

    if low in _TECHNICAL_TOKENS or input_source_class == "environment_input":
        return "technical_or_control_input", "high", False

    if _looks_like_placeholder_or_dummy_expression(val):
        return "placeholder_or_dummy_input", "high", False

    if val.endswith(":") and len(val) <= 8:
        return "technical_or_control_input", "medium", False

    if _EMAIL_RE.match(val) and _field_suggests_email(field_context):
        return "domain_plausible_input", "high", False
    if _EMAIL_RE.match(val):
        return "domain_plausible_input", "medium", True

    if _URL_RE.match(val) and _field_suggests_url(field_context):
        return "domain_plausible_input", "high", False
    if _URL_RE.match(val):
        return "domain_plausible_input", "medium", True

    if _DATE_RE.match(val) and _field_suggests_date(field_context):
        return "domain_plausible_input", "high", False
    if _DATE_RE.match(val):
        return "domain_plausible_input", "medium", True

    if _UUID_RE.match(val):
        return "technical_or_control_input", "medium", False

    if low.isdigit():
        if len(low) <= 3:
            return "validation_or_edge_case_input", "medium", False
        if _field_suggests_phone(field_context):
            return "domain_plausible_input", "medium", True
        return "unclear", "low", True

    if low in _AMBIGUOUS_VISIBLE or low in {"123456", "test-user", "testuser"}:
        return "unclear", "low", True

    if input_source_class == "generated_input":
        if _is_generated_random_template(val) or _is_generated_random_template(raw_val):
            return "technical_or_control_input", "medium", False
        if _generated_member_suggests_domain(val, field_context) or _generated_member_suggests_domain(
            raw_val, field_context
        ):
            return "domain_plausible_input", "medium", True
        if _field_suggests_email(field_context) or _field_suggests_phone(field_context):
            return "domain_plausible_input", "medium", True
        if _generated_member_suggests_technical(val, field_context) or _generated_member_suggests_technical(
            raw_val, field_context
        ):
            return "technical_or_control_input", "medium", False
        return "placeholder_or_dummy_input", "medium", True

    if _field_suggests_password(field_context) and len(val) >= 6:
        return "domain_plausible_input", "medium", True

    if _field_suggests_name(field_context) and re.match(r"^[A-Z][a-zA-Z]+(\s+[A-Z][a-zA-Z]+)*$", val):
        return "domain_plausible_input", "medium", False

    if _field_suggests_address(field_context) and len(val) >= 2:
        if re.match(r"^[A-Za-z0-9][A-Za-z0-9 _\-./]{1,}$", val):
            return "domain_plausible_input", "medium", False

    if _field_suggests_message(field_context) and _looks_like_natural_language(val):
        return "domain_plausible_input", "medium", False

    if _looks_like_natural_language(val):
        return "domain_plausible_input", "medium", True

    if len(val) >= 4 and re.match(r"^[A-Za-z][A-Za-z0-9 _\-./]{2,}$", val):
        if _field_suggests_message(field_context) or _field_suggests_name(field_context):
            return "domain_plausible_input", "medium", True
        return "unclear", "medium", True

    if (
        input_source_class == "literal_input"
        and value_visibility in {"visible", "partially_visible"}
        and input_channel in {"ui_text_entry", "text_entry", "keyboard_entry", ""}
        and len(val) >= 2
        and re.search(r"[A-Za-z0-9]", val)
    ):
        return "domain_plausible_input", "medium", True

    return "unclear", "low", True


def _infer_input_plausibility_codebook_path(
    *,
    value_redacted: str,
    field_context: str,
    value_visibility: str,
    input_source_class: str,
    input_channel: str = "",
    label: str,
) -> str:
    raw_val = value_redacted or ""
    val = raw_val.strip().strip("'\"")
    if input_source_class == "file_upload_input":
        if label == "validation_or_edge_case_input":
            return "upload_consumer_edge_or_invalid_path"
        if label == "domain_plausible_input":
            return "upload_consumer_domain_path"
    if _field_suggests_keyboard_press_control(field_context):
        return "keyboard_or_control_token"
    if _contains_keyboard_or_control_token(raw_val) or _is_keyboard_or_control_value(val, input_channel):
        return "keyboard_or_control_token"
    if _looks_like_endpoint_value_for_field(raw_val, field_context):
        return "endpoint_resource_config_value"
    if label == "placeholder_or_dummy_input":
        return "explicit_placeholder_dummy_or_filler"
    if label == "domain_plausible_input" and _field_suggests_domain_value(field_context):
        return "visible_domain_target_context"
    if label == "domain_plausible_input" and _DOMAIN_VARIABLE_MEMBER_RE.search(f"{raw_val} {field_context}"):
        return "domain_member_path_context"
    if label == "validation_or_edge_case_input":
        return "invalid_boundary_or_empty_value"
    if label == "technical_or_control_input":
        return "technical_harness_or_control_value"
    if label == "not_observable":
        return "insufficient_value_and_target_semantics"
    return "fallback_unclear"


def resolve_input_plausibility_detail(
    *,
    value_redacted: str,
    field_context: str,
    value_visibility: str,
    input_source_class: str,
    input_channel: str = "",
) -> Dict[str, str | bool]:
    """Return label plus confidence/review and the codebook decision path."""
    label, confidence, needs_review = _resolve_input_plausibility_tuple(
        value_redacted=value_redacted,
        field_context=field_context,
        value_visibility=value_visibility,
        input_source_class=input_source_class,
        input_channel=input_channel,
    )
    return {
        "input_plausibility": label,
        "input_plausibility_confidence": confidence,
        "input_plausibility_paper_label": map_input_plausibility_paper_label(label),
        "needs_review": needs_review,
        "input_plausibility_codebook_path": _infer_input_plausibility_codebook_path(
            value_redacted=value_redacted,
            field_context=field_context,
            value_visibility=value_visibility,
            input_source_class=input_source_class,
            input_channel=input_channel,
            label=label,
        ),
    }


def resolve_input_plausibility(
    *,
    value_redacted: str,
    field_context: str,
    value_visibility: str,
    input_source_class: str,
    input_channel: str = "",
) -> Tuple[str, str, bool]:
    """Return (input_plausibility, confidence, needs_review)."""
    detail = resolve_input_plausibility_detail(
        value_redacted=value_redacted,
        field_context=field_context,
        value_visibility=value_visibility,
        input_source_class=input_source_class,
        input_channel=input_channel,
    )
    return (
        str(detail["input_plausibility"]),
        str(detail["input_plausibility_confidence"]),
        bool(detail["needs_review"]),
    )
