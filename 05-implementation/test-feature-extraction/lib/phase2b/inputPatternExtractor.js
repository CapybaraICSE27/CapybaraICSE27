"use strict";

/**
 * AST-derived RQ2 input fields (source facts, visibility, field context).
 * Plausibility is resolved in Python (input_plausibility.py).
 */

const path = require("path");
const { Node } = require("ts-morph");
const { TEXT_ENTRY_VALUE_ARG, TEXT_ENTRY_METHODS } = require("../shared/patterns");
const {
  getCallReceiverText,
  isPageReceiverText,
  resolveTextEntryValueArgIndex,
  PAGE_SELECTOR_FIRST_METHODS,
} = require("../shared/textEntryValueArg");
const { findLocatorSubCall, getCallName, getOutermostCall } = require("./astPatternExtractor");

const UPLOAD_METHODS = new Set(["setInputFiles", "setFilesToUpload", "selectFile"]);
const SELECTION_METHODS = new Set(["selectOption", "select"]);
const GENERATOR_ROOTS = new Set(["faker", "chance"]);
const GENERATOR_FUNCTIONS = new Set(["faker", "chance", "uuid", "nanoid", "randomUUID", "generate"]);

function getFirstStringArg(call) {
  const args = call.getArguments();
  if (!args.length) return null;
  const a0 = args[0];
  if (Node.isStringLiteral(a0)) return a0.getLiteralText();
  if (Node.isNoSubstitutionTemplateLiteral(a0)) return a0.getLiteralText();
  return null;
}

function redactValue(raw, maxLen = 120) {
  if (!raw) return "";
  const one = String(raw).replace(/\s+/g, " ").trim();
  if (one.length <= maxLen) return one;
  return `${one.slice(0, maxLen)}…`;
}

function classifyValueKind(valueNode, rawValue) {
  if (valueNode) {
    if (Node.isStringLiteral(valueNode)) return "string_literal";
    if (Node.isNoSubstitutionTemplateLiteral(valueNode)) return "string_literal";
    if (Node.isTemplateExpression(valueNode)) return "template_literal";
    if (Node.isNumericLiteral(valueNode)) return "numeric_literal";
    if (Node.isTrueLiteral(valueNode) || Node.isFalseLiteral(valueNode)) return "boolean_literal";
    if (Node.isIdentifier(valueNode)) return "identifier";
    if (Node.isPropertyAccessExpression(valueNode) || Node.isElementAccessExpression(valueNode)) {
      return "member_expression";
    }
    if (Node.isBinaryExpression(valueNode)) return "binary_expression";
    if (Node.isConditionalExpression?.(valueNode)) return "conditional_expression";
    if (Node.isCallExpression(valueNode)) return "call_expression";
    if (Node.isArrayLiteralExpression(valueNode)) return "array_literal";
    if (Node.isObjectLiteralExpression(valueNode)) return "object_literal";
  }
  const raw = (rawValue || "").trim();
  if (/^['"`].*['"`]$/.test(raw)) return "string_literal";
  if (/^[A-Za-z_$][\w$.]*$/.test(raw)) return "identifier";
  return "unknown";
}

function classifyValueVisibility(valueKind, rawValue, provenance) {
  if (provenance) return "visible";
  if (valueKind === "string_literal" || valueKind === "numeric_literal" || valueKind === "boolean_literal") {
    return "visible";
  }
  if (valueKind === "array_literal" || valueKind === "object_literal") return "visible";
  if (valueKind === "template_literal") return "partially_visible";
  if (valueKind === "identifier" || valueKind === "member_expression" || valueKind === "call_expression") {
    return "opaque";
  }
  if (rawValue && /^['"`]/.test(rawValue.trim())) return "visible";
  return "unknown";
}

function inlineProvenanceFields(valueNode, valueKind, inputSource) {
  if (!valueNode) return {};

  const offsets = {
    input_value_start_offset_ast: valueNode.getStart(),
    input_value_end_offset_ast: valueNode.getEnd(),
  };

  if (
    valueKind === "string_literal" ||
    valueKind === "numeric_literal" ||
    valueKind === "boolean_literal"
  ) {
    return {
      ...offsets,
      input_origin_kind_ast: "inline_literal",
      input_origin_confidence_ast: "high",
      input_provenance_ast: `inline_literal:${valueKind}`,
      input_provenance_family_ast: "inline_literal",
      input_provenance_confidence: "high",
    };
  }

  if (valueKind === "array_literal") {
    return {
      ...offsets,
      input_origin_kind_ast: "inline_array",
      input_origin_confidence_ast: "high",
      input_provenance_ast: "inline_array:array_literal",
      input_provenance_family_ast: "inline_array",
      input_provenance_confidence: "high",
    };
  }

  if (valueKind === "object_literal") {
    return {
      ...offsets,
      input_origin_kind_ast: "inline_object",
      input_origin_confidence_ast: "high",
      input_provenance_ast: "inline_object:object_literal",
      input_provenance_family_ast: "inline_object",
      input_provenance_confidence: "high",
    };
  }

  if (inputSource === "environment_input") {
    return {
      ...offsets,
      input_origin_kind_ast: "environment_value",
      input_origin_confidence_ast: "high",
      input_provenance_ast: "environment:env_expression",
      input_provenance_family_ast: "environment",
      input_provenance_confidence: "high",
    };
  }

  if (inputSource === "generated_input") {
    return {
      ...offsets,
      input_origin_kind_ast: "generated_call",
      input_origin_confidence_ast: "high",
      input_provenance_ast: "generated:factory_or_generator",
      input_provenance_family_ast: "generated",
      input_provenance_confidence: "high",
    };
  }

  return offsets;
}

function expressionNameParts(expr) {
  if (!expr) return [];
  if (Node.isIdentifier(expr)) return [expr.getText()];
  if (Node.isThisExpression?.(expr)) return ["this"];
  if (Node.isPropertyAccessExpression(expr)) {
    return [...expressionNameParts(expr.getExpression()), expr.getName()];
  }
  if (Node.isElementAccessExpression?.(expr)) {
    return expressionNameParts(expr.getExpression());
  }
  if (Node.isCallExpression(expr)) return expressionNameParts(expr.getExpression());
  return [];
}

function expressionCompactText(expr) {
  try {
    return expr?.getText?.().replace(/\s+/g, "") || "";
  } catch (_) {
    return "";
  }
}

function isEnvironmentExpression(expr) {
  const parts = expressionNameParts(expr);
  if (parts[0] === "Cypress" && parts[1] === "env") return true;
  if (parts[0] === "Deno" && parts[1] === "env") return true;
  if (parts[0] === "process" && parts[1] === "env") return true;
  const compact = expressionCompactText(expr);
  return compact.startsWith("import.meta.env");
}

function classifyCallInputSource(call) {
  const callee = call.getExpression();
  const parts = expressionNameParts(callee);
  const root = parts[0] || "";
  const terminal = parts[parts.length - 1] || "";
  if (isEnvironmentExpression(callee)) return "environment_input";
  if (
    GENERATOR_ROOTS.has(root) ||
    GENERATOR_FUNCTIONS.has(terminal) ||
    (root === "crypto" && terminal === "randomUUID") ||
    (root === "Math" && terminal === "random")
  ) {
    return "generated_input";
  }
  if (terminal === "fixture") return "fixture_file_input";
  if (/^readFile(?:Sync)?$/i.test(terminal)) return "external_file_input";
  return "variable_input";
}

function classifyInputSourceFromValueNode(valueNode, rawValue) {
  const text = (rawValue || "").trim();
  const lower = text.toLowerCase();
  const kind = classifyValueKind(valueNode, rawValue);

  if (valueNode) {
    if (Node.isCallExpression(valueNode)) return classifyCallInputSource(valueNode);
    if (
      Node.isPropertyAccessExpression(valueNode) ||
      Node.isElementAccessExpression?.(valueNode)
    ) {
      return isEnvironmentExpression(valueNode) ? "environment_input" : "variable_input";
    }
  }

  if (
    kind === "string_literal" ||
    kind === "numeric_literal" ||
    kind === "boolean_literal" ||
    kind === "array_literal" ||
    kind === "object_literal"
  ) {
    return "literal_input";
  }
  if (kind === "template_literal" || kind === "identifier" || kind === "member_expression") {
    return "variable_input";
  }
  if (kind === "binary_expression" || kind === "conditional_expression") return "variable_input";

  if (/faker|random|chance|uuid|nanoid|generate/i.test(lower)) return "generated_input";
  if (/\b(Cypress\.env|process\.env|Deno\.env)\b/.test(text)) return "environment_input";

  if (kind === "call_expression") return "variable_input";
  if (/^['"`]/.test(text)) return "literal_input";
  if (/^[A-Za-z_$][\w$.]*$/.test(text)) return "variable_input";
  return "unknown_input";
}

function inputChannelForMethod(method) {
  if (!method) return "unknown";
  if (UPLOAD_METHODS.has(method)) return "ui_file_upload";
  if (SELECTION_METHODS.has(method)) return "ui_selection";
  if (method === "realPress") return "keyboard_input";
  if (method === "press" || method === "keyboard") return "keyboard_entry";
  if (TEXT_ENTRY_METHODS.has(method)) return "ui_text_entry";
  return "unknown";
}

function normalizeSelectorContext(literal, basis) {
  if (!literal) return "";
  let s = literal.trim();
  if (s.startsWith("#")) {
    s = s.slice(1).replace(/^input[_-]?/i, "").replace(/^field[_-]?/i, "");
  }
  if (s.startsWith("[") && s.includes("data-testid")) {
    const m = s.match(/data-testid=['"]([^'"]+)['"]/i);
    if (m) s = m[1];
  }
  if (s.startsWith(".")) s = s.slice(1);
  s = s.replace(/[_-]+/g, " ").trim();
  if (/^[a-z][a-zA-Z0-9]*$/.test(s) && /[A-Z]/.test(s.slice(1))) {
    s = s.replace(/([a-z])([A-Z])/g, "$1 $2");
  }
  return s.slice(0, 120);
}

function extractFieldContextFromChain(call) {
  const loc = findLocatorSubCall(call);
  if (!loc) return { field_context_ast: "", field_context_basis_ast: "" };

  const args = loc.call.getArguments();
  const firstArg = args.length ? args[0] : null;
  const literal = getFirstStringArg(loc.call) || "";
  const firstArgText = firstArg ? extractRawValueFromNode(firstArg) : "";
  const api = loc.apiName || "";
  const basis = api || "locator";
  const normalized = normalizeSelectorContext(literal || firstArgText, basis);

  if (/getByLabel|findByLabel/i.test(api)) {
    return { field_context_ast: literal || normalized || firstArgText, field_context_basis_ast: "getByLabel" };
  }
  if (/getByPlaceholder|findByPlaceholder/i.test(api)) {
    return { field_context_ast: literal || normalized || firstArgText, field_context_basis_ast: "getByPlaceholder" };
  }
  if (/getByRole|findByRole/i.test(api)) {
    return { field_context_ast: literal || normalized || firstArgText, field_context_basis_ast: "getByRole" };
  }
  if (/getByTestId|findByTestId|getByDataCy/i.test(api)) {
    return { field_context_ast: normalized || literal || firstArgText, field_context_basis_ast: "getByTestId" };
  }
  if (/getByText|findByText|contains/i.test(api)) {
    return { field_context_ast: literal || normalized || firstArgText, field_context_basis_ast: "getByText" };
  }
  if (api === "get" || api === "find" || api === "$" || api === "Selector") {
    return { field_context_ast: normalized || literal || firstArgText, field_context_basis_ast: basis };
  }
  if (literal || firstArgText) return { field_context_ast: normalized || literal || firstArgText, field_context_basis_ast: basis };
  return { field_context_ast: "", field_context_basis_ast: basis };
}

function targetContextFromChain(call) {
  const loc = findLocatorSubCall(call);
  if (!loc) return { input_target_context_ast: "", input_target_context_basis_ast: "" };
  const args = loc.call.getArguments();
  const firstArg = args.length ? args[0] : null;
  const literal = getFirstStringArg(loc.call) || "";
  const raw = firstArg ? extractRawValueFromNode(firstArg) : "";
  const normalized = normalizeSelectorContext(literal || raw, loc.apiName || "locator");
  return {
    input_target_context_ast: raw || literal || normalized,
    input_target_context_normalized_ast: normalized || literal || raw,
    input_target_context_basis_ast: loc.apiName || "locator",
  };
}

function classifyTargetRole(context, method, channel) {
  const text = `${context || ""} ${method || ""} ${channel || ""}`;
  if (UPLOAD_METHODS.has(method) || /input\[type\s*=\s*['"]file|upload|dropzone|fileinput/i.test(text)) {
    return "file_upload_field";
  }
  if (/(?:client[_-]?id|client[_-]?secret|secret|password|passwd|credential|oauth|token|csrf|api[_-]?key)/i.test(text)) {
    return "credential_or_config_field";
  }
  if (/(?:api|endpoint|resource|resourceurl|datasource|pagination|base[_-]?url|url|uri|host|path|route|webhook)/i.test(text)) {
    return "endpoint_or_resource_config_field";
  }
  if (/(?:search|name|username|email|phone|message|comment|title|label|description|room|team|channel|project|dataset|widget|task|note|segment|subnet|ipv4|address)/i.test(text)) {
    return "domain_text_field";
  }
  if (channel === "ui_selection") return "domain_selection_field";
  if (channel === "keyboard_input" || channel === "keyboard_entry") return "keyboard_control_target";
  return "unknown";
}

function classifyEndpointConstruction(valueNode, rawValue, targetRole) {
  const raw = rawValue || "";
  if (Node.isNewExpression?.(valueNode) && /URL\b/.test(valueNode.getExpression?.().getText?.() || "")) {
    return "url_constructor";
  }
  if (Node.isCallExpression(valueNode) && /\bURL\b|toString|resolve|join/.test(valueNode.getExpression().getText())) {
    return "url_constructor_or_path_builder";
  }
  if (Node.isBinaryExpression(valueNode) && /\b(?:url|uri|path|endpoint|parameters?|params|paginationUrl|prevUrl|nextUrl|resourceUrl|baseUrl)\b/i.test(raw)) {
    return "url_parameter_concatenation";
  }
  if (targetRole === "endpoint_or_resource_config_field" && /\b(?:url|uri|path|endpoint|parameters?|params|datasourceName|resource|paginationUrl|prevUrl|nextUrl|resourceUrl|baseUrl)\b/i.test(raw)) {
    return "resource_config_identifier";
  }
  return "";
}

function looksLikeSelectorLiteral(text) {
  const s = (text || "").trim();
  if (!s) return false;
  return (
    /^input\[/i.test(s) ||
    /^[\[#.]/.test(s) ||
    /type\s*=/.test(s) ||
    /^role=/.test(s) ||
    /^text=/.test(s)
  );
}

function resolveUploadValueArgIndex(callNode, method) {
  if (method === "selectFile" || method === "setFilesToUpload") return 0;
  if (method !== "setInputFiles") return TEXT_ENTRY_VALUE_ARG[method] ?? 0;

  const args = callNode.getArguments();
  if (args.length <= 1) return 0;

  const expr = callNode.getExpression();
  if (Node.isPropertyAccessExpression(expr)) {
    const recv = expr.getExpression();
    const recvText = recv.getText();
    if (Node.isIdentifier(recv) && recv.getText() === "page") return 1;
    if (recvText === "this.page") return 1;
  }

  const firstArgText = extractRawValueFromNode(args[0]);
  if (looksLikeSelectorLiteral(firstArgText)) return 1;

  return 0;
}

function resolveTextEntryMethod(callNode, terminal) {
  if (!terminal || !TEXT_ENTRY_METHODS.has(terminal)) return null;
  return {
    method: terminal,
    valueArgIndex: UPLOAD_METHODS.has(terminal)
      ? resolveUploadValueArgIndex(callNode, terminal)
      : resolveTextEntryValueArgIndex(callNode, terminal),
  };
}

function extractRawValueFromNode(valueNode) {
  if (!valueNode) return "";
  try {
    if (Node.isStringLiteral(valueNode) || Node.isNoSubstitutionTemplateLiteral(valueNode)) {
      return valueNode.getLiteralText?.() ?? valueNode.getText();
    }
    if (Node.isTemplateExpression(valueNode) && valueNode.getTemplateSpans().length === 0) {
      const head = valueNode.getHead();
      return head.getLiteralText?.() ?? head.getText();
    }
    return valueNode.getText();
  } catch (_) {
    return "";
  }
}

function extractTextEntryInputFacts(callNode, terminal) {
  const entry = resolveTextEntryMethod(callNode, terminal);
  if (!entry) return null;

  const args = callNode.getArguments();
  if (args.length <= entry.valueArgIndex) return null;

  const valueNode = args[entry.valueArgIndex];
  const rawValue = extractRawValueFromNode(valueNode);
  const valueKind = classifyValueKind(valueNode, rawValue);
  const inputSource =
    UPLOAD_METHODS.has(entry.method) ? "file_upload_input" : classifyInputSourceFromValueNode(valueNode, rawValue);
  const visibility = classifyValueVisibility(valueKind, rawValue, "");
  let fieldCtx = extractFieldContextFromChain(getOutermostCall(callNode) || callNode);
  const targetCtx = targetContextFromChain(getOutermostCall(callNode) || callNode);
  const targetRole = classifyTargetRole(
    `${fieldCtx.field_context_ast || ""} ${targetCtx.input_target_context_ast || ""} ${targetCtx.input_target_context_normalized_ast || ""}`,
    entry.method,
    inputChannelForMethod(entry.method),
  );
  const endpointConstruction = classifyEndpointConstruction(valueNode, rawValue, targetRole);

  if (UPLOAD_METHODS.has(entry.method) && entry.valueArgIndex === 1 && args[0]) {
    const selectorRaw = extractRawValueFromNode(args[0]);
    if (selectorRaw && !fieldCtx.field_context_ast) {
      fieldCtx = {
        field_context_ast: normalizeSelectorContext(selectorRaw, "setInputFiles"),
        field_context_basis_ast: "setInputFiles_selector",
      };
    }
  }

  if (
    entry.valueArgIndex === 1 &&
    args[0] &&
    PAGE_SELECTOR_FIRST_METHODS.has(entry.method) &&
    isPageReceiverText(getCallReceiverText(callNode))
  ) {
    const selectorRaw = extractRawValueFromNode(args[0]);
    if (selectorRaw && !fieldCtx.field_context_ast) {
      fieldCtx = {
        field_context_ast: normalizeSelectorContext(selectorRaw, entry.method),
        field_context_basis_ast: `${entry.method}_selector`,
      };
    }
  }

  return {
    method: entry.method,
    input_source: inputSource,
    input_source_ast: inputSource,
    input_value_kind_ast: valueKind,
    input_value_expression_kind_ast: valueKind,
    input_value_redacted: redactValue(rawValue),
    input_channel_ast: inputChannelForMethod(entry.method),
    value_visibility_ast: visibility,
    raw_value: rawValue.slice(0, 500),
    value_summary: redactValue(rawValue),
    ...fieldCtx,
    ...targetCtx,
    input_target_role_ast: targetRole,
    input_target_role_basis_ast: targetRole === "unknown" ? "" : "ast_locator_target_context",
    input_endpoint_construction_ast: endpointConstruction,
    input_endpoint_construction_basis_ast: endpointConstruction ? "ast_value_expression_and_target_role" : "",
    input_evidence_basis_ast: "ast_value_argument",
    input_source_confidence_ast: inputSource === "unknown_input" ? "low" : "high",
    ...inlineProvenanceFields(valueNode, valueKind, inputSource),
  };
}

function extractLoadSiteFacts(callNode) {
  const api = getCallName(callNode);
  if (!api) return null;

  const expr = callNode.getExpression();
  let recv = "";
  if (Node.isPropertyAccessExpression(expr)) recv = expr.getExpression().getText();

  const isCyFixture = recv === "cy" && api === "fixture";
  const isCyReadFile = recv === "cy" && api === "readFile";
  const isFsRead =
    /^(fs|fsPromises|node:fs)$/.test(recv.split(".")[0]) &&
    (api === "readFileSync" || api === "readFile");

  const isCyIntercept = recv === "cy" && api === "intercept";
  if (isCyIntercept) {
    for (const arg of callNode.getArguments()) {
      if (!Node.isObjectLiteralExpression(arg)) continue;
      for (const prop of arg.getProperties()) {
        if (prop.getName?.() !== "fixture") continue;
        const init = prop.getInitializer?.();
        if (!init || !Node.isStringLiteral(init)) continue;
        const pathLiteral = init.getLiteralText();
        return {
          input_source_ast: "network_mock_payload_input",
          input_load_path_ast: pathLiteral,
          input_load_format_ast: path.extname(pathLiteral).toLowerCase().replace(/^\./, "") || "unknown",
          input_channel_ast: "load_site",
          value_visibility_ast: "visible",
          input_value_redacted: pathLiteral,
          field_context_ast: "",
          field_context_basis_ast: "",
          input_evidence_basis_ast: "ast_intercept_fixture",
          input_source_confidence_ast: "high",
          is_load_site: true,
          is_network_mock: true,
        };
      }
    }
  }

  if (!isCyFixture && !isCyReadFile && !isFsRead) return null;

  const pathLiteral = getFirstStringArg(callNode) || "";
  let inputSource = "external_file_input";
  if (isCyFixture) inputSource = "fixture_file_input";

  const ext = pathLiteral ? path.extname(pathLiteral).toLowerCase().replace(/^\./, "") : "";

  return {
    input_source_ast: inputSource,
    input_load_path_ast: pathLiteral,
    input_load_format_ast: ext || "unknown",
    input_channel_ast: "load_site",
    value_visibility_ast: pathLiteral ? "visible" : "unknown",
    input_value_redacted: pathLiteral,
    field_context_ast: "",
    field_context_basis_ast: "",
    input_evidence_basis_ast: "ast_load_site",
    input_source_confidence_ast: pathLiteral ? "high" : "medium",
    is_load_site: true,
  };
}

function attachInputPatternFields(node, featureType, callNode, terminal) {
  const out = {};
  const call = callNode || (Node.isCallExpression(node) ? node : null);
  if (!call) return out;

  if (featureType === "input") {
    const load = extractLoadSiteFacts(call);
    if (load) {
      Object.assign(out, load);
      return out;
    }
  }

  if (featureType === "input" || featureType === "ui_action") {
    const facts = extractTextEntryInputFacts(call, terminal);
    if (facts) {
      Object.assign(out, facts);
      out.input_source = facts.input_source_ast;
    }
  }

  if (featureType === "input" && !out.input_source_ast) {
    const load = extractLoadSiteFacts(call);
    if (load) Object.assign(out, load);
  }

  return out;
}

module.exports = {
  attachInputPatternFields,
  extractTextEntryInputFacts,
  extractLoadSiteFacts,
  classifyInputSourceFromValueNode,
  classifyValueKind,
  classifyValueVisibility,
  inputChannelForMethod,
  extractFieldContextFromChain,
  redactValue,
  resolveUploadValueArgIndex,
};
