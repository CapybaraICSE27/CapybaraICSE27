"use strict";

/**
 * RQ5-B: AST-derived assertion chain metadata (Milestone 3).
 * One metadata block per semantic matcher call, linked by assertion_chain_root_id.
 */

const { Node } = require("ts-morph");
const { getCallName } = require("./astPatternExtractor");

const CHAIN_MODIFIER_NAMES = new Set(["not", "resolves", "rejects", "deep", "eventually", "soft"]);

const PLAYWRIGHT_MATCHERS = new Set([
  "toBe", "toEqual", "toStrictEqual", "toBeVisible", "toBeHidden",
  "toContain", "toHaveLength", "toHaveCount", "toHaveText", "toContainText",
  "toHaveTitle", "toHaveURL", "toHaveAttribute", "toHaveValue", "toHaveProperty",
  "toHaveJSProperty", "toHaveCSS", "toHaveClass", "toHaveId", "toHaveScreenshot", "toMatch",
  "toMatchObject", "toMatchScreenshot", "toThrow", "toBeAttached", "toBeInViewport",
  "toBeInTheDocument", "toBeChecked", "toBeDisabled", "toBeEnabled", "toBeEditable",
  "toBeFocused", "toBeEmpty", "toBeTruthy", "toBeFalsy", "toBeNull", "toBeUndefined",
  "toBeDefined", "toBeGreaterThan", "toBeGreaterThanOrEqual", "toBeLessThan",
  "toBeLessThanOrEqual", "toHaveBeenCalled", "toHaveBeenCalledWith",
  "toHaveBeenCalledTimes", "toHaveBeenCalledOnce", "toHaveReceivedEvent",
  "toHaveReceivedEventTimes", "toHaveReceivedEventDetail", "toHaveCustomState",
  "toHaveAccessibleName", "toHaveAccessibleDescription", "toHaveAccessibleError",
  "toHaveAccessibleErrorMessage", "toHaveRole", "toHaveNoViolations",
  "toMatchAriaSnapshot", "toPass",
]);

const WEBDRIVERIO_MATCHERS = new Set([
  "toBeDisplayed", "toBeExisting", "toBeClickable", "toBeEnabled", "toBeDisabled",
  "toHaveText", "toHaveValue", "toHaveAttr", "toHaveElementClass", "toBeFocused",
  "toBeSelected", "toBeChecked",
]);

const CHAI_PROPERTY_MATCHERS = new Set([
  "eq", "equal", "eql", "include", "match", "contain", "above", "below",
  "gt", "gte", "lt", "lte", "greaterThan", "lessThan", "closeTo",
  "property", "prop", "value", "length", "lengthOf", "true", "false", "null", "undefined",
  "exist", "exists", "empty", "ok", "called", "calledOnce", "calledTwice",
  "calledThrice", "calledWith", "calledWithMatch", "contains",
]);

const CYPRESS_MATCHERS = new Set(["should", "and"]);

const TESTCAFE_MATCHERS = new Set(["ok", "eql", "contains", "notOk", "notEql", "notContains"]);

const CHAIN_ROOT_NAMES = new Set(["expect", "assert", "get", "contains", "visit"]);

const LOCATOR_SUBJECT_CALLS = new Set([
  "get", "contains", "find", "locator", "selector", "$", "$$",
  "getByRole", "findByRole", "getByLabel", "findByLabel", "findByLabelText",
  "getByPlaceholder", "findByPlaceholderText", "getByAltText", "getByTitle",
  "getByText", "findByText", "getByTestId", "findByTestId", "getByDataCy",
]);
const API_SUBJECT_CALLS = new Set(["request", "fetch", "api", "graphql"]);
const RESPONSE_SUBJECT_CALLS = new Set(["waitForResponse"]);
const PAGE_SUBJECT_CALLS = new Set(["goto", "visit", "url"]);

const CALLBACK_INTENT_PRIORITY = [
  "accessibility_compliance",
  "visual_regression",
  "network_contract",
  "api_or_data_contract",
  "navigation_outcome",
  "collection_size",
  "content_correctness",
  "style_or_visual_state",
  "interactive_state",
  "element_presence",
  "value_or_attribute_correctness",
];

const GENERIC_VALUE_MATCHER_NAMES = new Set([
  "eq", "equal", "eql", "toequal", "tostrictequal", "tobe", "match", "tomatch",
  "include", "contain", "contains", "property", "prop", "tobedefined",
  "tobeundefined", "tobenull", "tobetruthy", "tobefalsy", "true", "false",
  "null", "undefined", "ok", "notok",
]);

function chainRootId(filePath, call) {
  const sf = call.getSourceFile();
  const fp = filePath || sf?.getFilePath?.() || "unknown";
  return `${fp}:${call.getStartLineNumber()}:${call.getStart()}`;
}

function isChainModifierName(name) {
  return CHAIN_MODIFIER_NAMES.has(name);
}

function isSemanticMatcherName(name) {
  if (!name || isChainModifierName(name)) return false;
  return (
    PLAYWRIGHT_MATCHERS.has(name) ||
    WEBDRIVERIO_MATCHERS.has(name) ||
    CHAI_PROPERTY_MATCHERS.has(name) ||
    CYPRESS_MATCHERS.has(name) ||
    TESTCAFE_MATCHERS.has(name)
  );
}

function isChainTraversalName(name) {
  if (!name) return false;
  if (name === "expect" || name === "assert") return true;
  return isSemanticMatcherName(name) || isChainModifierName(name);
}

function normalizeFrameworkHint(frameworkHint) {
  const f = String(frameworkHint || "").toLowerCase();
  if (f.includes("playwright")) return "playwright";
  if (f.includes("cypress")) return "cypress";
  if (f.includes("testcafe")) return "testcafe";
  if (f.includes("nightwatch")) return "nightwatch";
  if (f.includes("webdriverio") || f === "wdio") return "webdriverio";
  if (f.includes("jest")) return "jest";
  if (f.includes("chai")) return "chai";
  return "";
}

/** Walk outward to the topmost semantic matcher call in a property-access chain. */
function findTopmostChainCall(call) {
  let top = call;
  for (let i = 0; i < 20; i++) {
    const parent = top.getParent();
    if (!parent || !Node.isPropertyAccessExpression(parent)) break;
    const gp = parent.getParent();
    if (!gp || !Node.isCallExpression(gp)) break;
    const outerName = getCallName(gp);
    if (isChainTraversalName(outerName)) {
      top = gp;
      continue;
    }
    break;
  }
  return top;
}

function detectAssertionLibrarySyntax(call, text, frameworkHint) {
  const t = text || call.getText();
  if (/\bt\.expect\b/.test(t)) return "testcafe";
  if (/\bcy\.(should|and)\b/.test(t) || /\.(should|and)\s*\(/.test(t)) return "cypress";
  if (/\$\([^)]+\)\.(toBe|toHave)/.test(t)) return "webdriverio";
  if (/\bbrowser\.assert\b/.test(t)) return "nightwatch";
  if (/\bassert\.(?:deep\.)?(?:equal|include|match|property)/.test(t)) return "chai";
  if (/\bexpect\s*\([^)]*\)\.(?:not\.)?(?:toBe|toHave|toEqual|toStrictEqual|toContain)/.test(t)) {
    return "playwright";
  }
  if (/\bexpect\s*\(/.test(t) && /\.to[A-Z]/.test(t)) return "playwright";
  if (/\bexpect\s*\(/.test(t)) return "jest";
  return normalizeFrameworkHint(frameworkHint) || "unknown";
}

function isSoftAssertion(call, text) {
  const t = text || call.getText();
  return /\bexpect\.soft\s*\(/.test(t) || /\.soft\s*\(/.test(t);
}

function semanticMatcherTokens(matcher) {
  const tokens = [];
  let current = "";
  for (const ch of String(matcher || "").toLowerCase()) {
    const code = ch.charCodeAt(0);
    const isAlphaNum =
      (code >= 48 && code <= 57) ||
      (code >= 97 && code <= 122);
    if (isAlphaNum) {
      current += ch;
    } else if (current) {
      tokens.push(current);
      current = "";
    }
  }
  if (current) tokens.push(current);
  return tokens;
}

function normalizedAlnum(value) {
  let out = "";
  for (const ch of String(value || "")) {
    const code = ch.charCodeAt(0);
    const isDigit = code >= 48 && code <= 57;
    const isUpper = code >= 65 && code <= 90;
    const isLower = code >= 97 && code <= 122;
    if (isDigit || isLower) out += ch;
    else if (isUpper) out += ch.toLowerCase();
  }
  return out;
}

function identifierTokens(value) {
  const tokens = [];
  let current = "";
  const push = () => {
    if (current) {
      tokens.push(current.toLowerCase());
      current = "";
    }
  };
  for (const ch of String(value || "")) {
    const code = ch.charCodeAt(0);
    const isDigit = code >= 48 && code <= 57;
    const isUpper = code >= 65 && code <= 90;
    const isLower = code >= 97 && code <= 122;
    if (isUpper) {
      if (current && current[current.length - 1] !== current[current.length - 1].toUpperCase()) {
        push();
      }
      current += ch.toLowerCase();
    } else if (isLower || isDigit) {
      current += ch;
    } else {
      push();
    }
  }
  push();
  return tokens;
}

function addTokens(tokens, value) {
  for (const token of identifierTokens(value)) {
    if (token) tokens.add(token);
  }
  const normalized = normalizedAlnum(value);
  if (normalized) tokens.add(normalized);
}

function semanticMatcherIsNegated(matcher) {
  return semanticMatcherTokens(matcher).includes("not");
}

function detectChainModifiers(text, semanticMatcher = "") {
  const t = text || "";
  let promiseModifier = "";
  if (/\)\.resolves\./.test(t) || /\.resolves\.(?:to|toEqual|toStrictEqual|toBe)/.test(t)) {
    promiseModifier = "resolves";
  } else if (/\)\.rejects\./.test(t) || /\.rejects\.(?:to|toThrow|toEqual)/.test(t)) {
    promiseModifier = "rejects";
  }
  const modifiers = {
    is_negated_assertion: /\.not\.(?:to|toBe|toHave|toEqual|toStrictEqual|toContain)/.test(t)
      || /\bassert\.not\./.test(t)
      || /\.notOk\b/.test(t)
      || /\.notEql\b/.test(t)
      || /\.notContains\b/.test(t)
      || semanticMatcherIsNegated(semanticMatcher),
    promise_modifier: promiseModifier,
    chai_modifier_deep: /\.deep\.(?:equal|eql|include|contain)/.test(t),
  };
  modifiers.assertion_modifiers_json = JSON.stringify({
    negated: modifiers.is_negated_assertion,
    promise: modifiers.promise_modifier,
    deep: modifiers.chai_modifier_deep,
    soft: isSoftAssertion(null, t),
  });
  return modifiers;
}

function detectGroupKind(text) {
  if (/\btest\.step\b/.test(text)) return "test_step";
  if (/\.toPass\s*\(/.test(text)) return "toPass";
  if (/\bwithin\s*\(/.test(text)) return "within";
  if (/\b(?:then|catch)\s*\(\s*(?:async\s*)?\(?/.test(text)) return "callback";
  return "none";
}

function detectGroupKindFromAncestors(callNode, textFallback) {
  if (Node.isCallExpression(callNode) && getCallName(callNode) === "should") {
    const args = callNode.getArguments();
    if (args.length && (Node.isArrowFunction(args[0]) || Node.isFunctionExpression(args[0]))) {
      return "callback";
    }
  }
  let p = callNode.getParent();
  while (p) {
    if (Node.isCallExpression(p)) {
      const name = getCallName(p);
      const t = p.getText();
      if (name === "step" && /\btest\.step\b/.test(t)) return "test_step";
      if (name === "within" || /\b(?:cy\.)?within\b/.test(t)) return "within";
      if (name === "toPass") return "toPass";
      if (name === "should") {
        const args = p.getArguments();
        if (args.length && (Node.isArrowFunction(args[0]) || Node.isFunctionExpression(args[0]))) {
          return "callback";
        }
      }
    }
    p = p.getParent();
  }
  return detectGroupKind(textFallback);
}

function identifierSubjectInfo(name) {
  const n = String(name || "");
  if (!n) return null;
  const low = n.toLowerCase();
  if (["interception", "xhr"].includes(low)) {
    return { kind: "network", basis: "ast_subject_identifier_name_heuristic" };
  }
  if (["response", "res"].includes(low)) {
    return { kind: "response", basis: "ast_subject_identifier_name_heuristic" };
  }
  if (["request", "req"].includes(low)) {
    return { kind: "request", basis: "ast_subject_identifier_name_heuristic" };
  }
  if (["api", "apiresponse", "apiresult", "body", "payload", "headers"].includes(low)) {
    return { kind: "api", basis: "ast_subject_identifier_name_heuristic" };
  }
  if (["locator", "element", "el"].includes(low)) {
    return { kind: "locator", basis: "ast_subject_identifier_name_heuristic" };
  }
  if (low === "page") {
    return { kind: "page", basis: "ast_subject_identifier_name_heuristic" };
  }
  return null;
}

function lowerPath(path) {
  return (path || []).map((part) => String(part || "").toLowerCase()).filter(Boolean);
}

function enrichSubjectInfo(info, expr) {
  const path = expressionSegments(expr).filter(Boolean);
  const low = lowerPath(path);
  const root = path[0] || "";
  let out = { ...(info || { kind: "unknown", basis: "" }) };

  const has = (...names) => names.some((name) => low.includes(name));
  if (
    has("interception", "xhr") ||
    (has("request", "response", "req", "res") && has("body", "status", "headers", "url", "method"))
  ) {
    out = { ...out, kind: "network", basis: "ast_subject_property_path" };
    out.kind = "network";
  } else if (!out.kind || out.kind === "unknown") {
    const byRoot = identifierSubjectInfo(root);
    if (byRoot) out = byRoot;
  }

  return {
    ...out,
    root_identifier_ast: root,
    property_path: path.slice(0, 40),
    subject_text_ast: expr?.getText?.().slice(0, 300) || "",
  };
}

function propertyRootIdentifier(node) {
  let cur = node;
  while (cur && Node.isPropertyAccessExpression(cur)) {
    cur = cur.getExpression();
  }
  return Node.isIdentifier(cur) ? cur.getText() : "";
}

function callReceiverRoot(call) {
  if (!call || !Node.isCallExpression(call)) return "";
  const expr = call.getExpression();
  if (!Node.isPropertyAccessExpression(expr)) return "";
  let recv = expr.getExpression();
  while (recv && Node.isPropertyAccessExpression(recv)) {
    recv = recv.getExpression();
  }
  if (Node.isCallExpression(recv)) return callReceiverRoot(recv);
  return Node.isIdentifier(recv) ? recv.getText() : recv?.getText?.() || "";
}

function callSubjectInfo(call) {
  if (!call || !Node.isCallExpression(call)) return null;
  const name = getCallName(call);
  const root = callReceiverRoot(call);
  if (LOCATOR_SUBJECT_CALLS.has(name)) {
    return { kind: "locator", basis: root === "cy" ? "ast_cypress_subject_chain" : "ast_locator_call" };
  }
  if (RESPONSE_SUBJECT_CALLS.has(name)) return { kind: "response", basis: "ast_response_wait_call" };
  if (API_SUBJECT_CALLS.has(name)) return { kind: "api", basis: root === "cy" ? "ast_cypress_subject_chain" : "ast_api_call" };
  if (PAGE_SUBJECT_CALLS.has(name)) return { kind: "page", basis: root === "cy" ? "ast_cypress_subject_chain" : "ast_page_call" };

  const expr = call.getExpression();
  if (Node.isPropertyAccessExpression(expr)) {
    const recv = expr.getExpression();
    if (Node.isCallExpression(recv)) {
      const recvInfo = callSubjectInfo(recv);
      if (recvInfo) return recvInfo;
    }
    const rootInfo = identifierSubjectInfo(propertyRootIdentifier(expr));
    if (rootInfo) return rootInfo;
  }
  return identifierSubjectInfo(name);
}

function expressionSubjectInfo(expr) {
  if (!expr) return { kind: "unknown", basis: "" };
  if (
    Node.isStringLiteral(expr) ||
    Node.isNoSubstitutionTemplateLiteral(expr) ||
    Node.isNumericLiteral(expr) ||
    expr.getKindName?.() === "TrueKeyword" ||
    expr.getKindName?.() === "FalseKeyword" ||
    expr.getKindName?.() === "NullKeyword"
  ) {
    return { kind: "primitive", basis: "ast_subject_literal" };
  }
  if (Node.isCallExpression(expr)) {
    return callSubjectInfo(expr) || { kind: "unknown", basis: "" };
  }
  if (Node.isPropertyAccessExpression(expr)) {
    const recv = expr.getExpression();
    if (Node.isCallExpression(recv)) {
      const recvInfo = callSubjectInfo(recv);
      if (recvInfo) return recvInfo;
    }
    return identifierSubjectInfo(propertyRootIdentifier(expr)) || { kind: "unknown", basis: "" };
  }
  if (Node.isIdentifier(expr)) {
    return identifierSubjectInfo(expr.getText()) || { kind: "unknown", basis: "" };
  }
  if (Node.isParenthesizedExpression?.(expr)) {
    return expressionSubjectInfo(expr.getExpression());
  }
  return { kind: "unknown", basis: "" };
}

function subjectInfoFromExpression(expr) {
  return enrichSubjectInfo(expressionSubjectInfo(expr), expr);
}

function cypressChainSubjectInfo(topCall) {
  let current = topCall;
  for (let depth = 0; depth < 30; depth++) {
    if (!current || !Node.isCallExpression(current)) break;
    const info = callSubjectInfo(current);
    if (info && info.kind !== "unknown") return enrichSubjectInfo(info, current);
    const expr = current.getExpression();
    if (!Node.isPropertyAccessExpression(expr)) break;
    const recv = expr.getExpression();
    if (Node.isCallExpression(recv)) current = recv;
    else break;
  }
  return enrichSubjectInfo({ kind: "unknown", basis: "" }, topCall);
}

function classifySubjectInfo(visitedCall, rootCall, topCall) {
  const librarySyntax = detectAssertionLibrarySyntax(visitedCall, topCall.getText(), "");
  if (librarySyntax === "cypress") {
    return cypressChainSubjectInfo(topCall);
  }
  const rootName = getCallName(rootCall);
  if (rootName === "expect" || rootName === "assert") {
    const subject = rootCall.getArguments()[0];
    return subjectInfoFromExpression(subject);
  }
  return enrichSubjectInfo(callSubjectInfo(rootCall) || { kind: "unknown", basis: "" }, rootCall);
}

function matcherNameFromCall(current) {
  const name = getCallName(current);
  if (name && isSemanticMatcherName(name)) return name;
  const expr = current.getExpression();
  if (Node.isPropertyAccessExpression(expr)) {
    const prop = expr.getName();
    if (isSemanticMatcherName(prop)) return prop;
  }
  return name || "";
}

function cypressSemanticMatcherFromCall(call) {
  if (!call || !Node.isCallExpression(call)) return "";
  const name = getCallName(call);
  if (!CYPRESS_MATCHERS.has(name)) return "";
  const first = call.getArguments()[0];
  if (!first || !(Node.isStringLiteral(first) || Node.isNoSubstitutionTemplateLiteral(first))) {
    return "";
  }
  return first.getLiteralText?.() ?? "";
}

function collectPlaywrightJestMatchers(startCall) {
  const matchers = [];
  let current = startCall;
  let root = startCall;
  for (let depth = 0; depth < 20; depth++) {
    if (!current || !Node.isCallExpression(current)) break;
    const name = getCallName(current);
    if (name === "expect" || name === "assert") {
      root = current;
      break;
    }
    if (!isChainModifierName(name)) {
      const matcher = matcherNameFromCall(current);
      if (matcher && isSemanticMatcherName(matcher)) {
        matchers.unshift({ call: current, matcher, rootCall: root });
      }
    }
    const expr = current.getExpression();
    if (!Node.isPropertyAccessExpression(expr)) break;
    const recv = expr.getExpression();
    if (Node.isCallExpression(recv)) {
      current = recv;
      if (getCallName(recv) === "expect" || getCallName(recv) === "assert") {
        root = recv;
      }
    } else break;
  }
  return matchers.map((m) => ({ ...m, rootCall: root }));
}

function collectCypressMatchers(startCall) {
  const matchers = [];
  let current = startCall;
  let root = startCall;
  for (let depth = 0; depth < 20; depth++) {
    if (!current || !Node.isCallExpression(current)) break;
    const name = getCallName(current);
    if (CYPRESS_MATCHERS.has(name)) {
      matchers.unshift({ call: current, matcher: name, rootCall: root });
    }
    if (CHAIN_ROOT_NAMES.has(name) || name === "get" || name === "contains") {
      root = current;
    }
    const expr = current.getExpression();
    if (!Node.isPropertyAccessExpression(expr)) break;
    const recv = expr.getExpression();
    if (Node.isCallExpression(recv)) current = recv;
    else break;
  }
  return matchers;
}

function collectTestCafeMatchers(startCall) {
  const matchers = [];
  let current = startCall;
  let root = startCall;
  for (let depth = 0; depth < 20; depth++) {
    if (!current || !Node.isCallExpression(current)) break;
    const name = getCallName(current);
    if (name === "expect") root = current;
    if (TESTCAFE_MATCHERS.has(name)) {
      matchers.unshift({ call: current, matcher: name, rootCall: root });
    }
    const expr = current.getExpression();
    if (!Node.isPropertyAccessExpression(expr)) break;
    const recv = expr.getExpression();
    if (Node.isCallExpression(recv)) current = recv;
    else break;
  }
  return matchers;
}

function collectMatchersFromChain(startCall, frameworkHint) {
  const text = startCall.getText();
  const hinted = normalizeFrameworkHint(frameworkHint);
  if (hinted === "testcafe" || /\bt\.expect\b/.test(text)) return collectTestCafeMatchers(startCall);
  const startName = getCallName(startCall);
  if (
    hinted === "cypress" ||
    CYPRESS_MATCHERS.has(startName) ||
    /\.(should|and)\s*\(/.test(text) ||
    /\bcy\./.test(text)
  ) {
    const cy = collectCypressMatchers(startCall);
    if (cy.length) return cy;
  }
  return collectPlaywrightJestMatchers(startCall);
}

function collectCallChainEntries(topCall) {
  const entries = [];
  let current = topCall;
  for (let depth = 0; depth < 40; depth++) {
    if (!current || !Node.isCallExpression(current)) break;
    entries.push({ call: current, name: getCallName(current) || matcherNameFromCall(current) || "" });
    const expr = current.getExpression();
    if (!Node.isPropertyAccessExpression(expr)) break;
    const recv = expr.getExpression();
    if (Node.isCallExpression(recv)) current = recv;
    else break;
  }
  return entries.reverse();
}

function chainMatcherSequence(matchers) {
  return matchers.map((entry) => {
    const semantic = cypressSemanticMatcherFromCall(entry.call);
    if (semantic && semantic !== entry.matcher) return `${entry.matcher}:${semantic}`;
    return entry.matcher || "";
  }).filter(Boolean);
}

function nonAssertionChainMethods(topCall, matchers) {
  const assertionCalls = new Set(matchers.map((entry) => entry.call));
  const methods = [];
  for (const entry of collectCallChainEntries(topCall)) {
    if (!entry.name || assertionCalls.has(entry.call)) continue;
    if (entry.name === "expect" || entry.name === "assert") continue;
    if (isChainModifierName(entry.name)) continue;
    methods.push(entry.name);
  }
  return methods.slice(0, 80);
}

function expressionSegments(node, depth = 0) {
  if (!node || depth > 30) return [];
  if (Node.isIdentifier(node)) return [node.getText()];
  if (Node.isPropertyAccessExpression(node)) {
    return [...expressionSegments(node.getExpression(), depth + 1), node.getName()];
  }
  if (Node.isElementAccessExpression?.(node)) {
    const arg = node.getArgumentExpression?.();
    const parts = expressionSegments(node.getExpression(), depth + 1);
    if (arg && (Node.isStringLiteral(arg) || Node.isNoSubstitutionTemplateLiteral(arg))) {
      parts.push(arg.getLiteralText?.() || "");
    }
    return parts;
  }
  if (Node.isCallExpression(node)) {
    return expressionSegments(node.getExpression(), depth + 1);
  }
  if (Node.isParenthesizedExpression?.(node)) {
    return expressionSegments(node.getExpression(), depth + 1);
  }
  if (Node.isThisExpression?.(node)) return ["this"];
  return [];
}

function findAssertionRootCallInExpression(node, depth = 0) {
  if (!node || depth > 30) return null;
  if (Node.isCallExpression(node)) {
    const name = getCallName(node);
    if (name === "expect" || name === "assert") return node;
    return findAssertionRootCallInExpression(node.getExpression(), depth + 1);
  }
  if (Node.isPropertyAccessExpression(node)) {
    return findAssertionRootCallInExpression(node.getExpression(), depth + 1);
  }
  if (Node.isElementAccessExpression?.(node)) {
    return findAssertionRootCallInExpression(node.getExpression(), depth + 1);
  }
  if (Node.isParenthesizedExpression?.(node)) {
    return findAssertionRootCallInExpression(node.getExpression(), depth + 1);
  }
  return null;
}

function literalArgValues(call, limit = 4) {
  const values = [];
  for (const arg of call.getArguments()) {
    if (values.length >= limit) break;
    if (Node.isStringLiteral(arg) || Node.isNoSubstitutionTemplateLiteral(arg)) {
      values.push(arg.getLiteralText?.() || "");
    }
  }
  return values;
}

function callbackFunctionArgForAssertion(call) {
  if (!call || !Node.isCallExpression(call)) return null;
  const name = getCallName(call);
  if (!CYPRESS_MATCHERS.has(name)) return null;
  const first = call.getArguments()[0];
  if (first && (Node.isArrowFunction(first) || Node.isFunctionExpression(first))) {
    return first;
  }
  return null;
}

function classifyCallbackIntentFromAst(matcher, subjectSegments, matcherSegments, literalValues) {
  const matcherKey = normalizedAlnum(matcher);
  const tokens = new Set(semanticMatcherTokens(matcher));
  for (const value of [...subjectSegments, ...matcherSegments, ...literalValues]) {
    addTokens(tokens, value);
  }
  const has = (...names) => names.some((name) => tokens.has(name));
  const hasMatcher = (...names) => names.some((name) => matcherKey === normalizedAlnum(name));
  const requestedResource =
    (has("requested", "request") && has("path", "url", "uri", "resource", "image", "src")) ||
    has("requestedimagepath", "requestedurl", "requestedpath", "requestedresource");

  if (hasMatcher("toHaveAccessibleName", "toHaveAccessibleDescription", "toMatchAriaSnapshot", "toHaveRole") ||
      has("aria", "accessible", "accessibility", "role", "accessiblename", "accessibledescription")) {
    return "accessibility_compliance";
  }
  if (hasMatcher("toHaveScreenshot", "toMatchScreenshot", "toMatchSnapshot") ||
      has("screenshot", "snapshot", "visualdiff", "imagematch")) {
    return "visual_regression";
  }
  if (requestedResource || has("interception", "intercept", "xhr", "fetch", "network")) {
    return "network_contract";
  }
  if (has("response", "request", "res", "req", "status", "statuscode", "body", "headers", "payload", "graphql", "api")) {
    return "api_or_data_contract";
  }
  if (hasMatcher("toHaveURL") ||
      has("url", "currenturl", "href", "pathname", "location", "route", "iframesrc", "src")) {
    return "navigation_outcome";
  }
  if (hasMatcher("toHaveLength", "toHaveCount", "toHaveBeenCalledTimes") ||
      has("length", "lengthof", "count", "size", "filter", "items", "array")) {
    return "collection_size";
  }
  if (hasMatcher("toHaveText", "toContainText", "toHaveTitle") ||
      has("text", "textcontent", "innertext", "html", "gethtml", "title", "content")) {
    return "content_correctness";
  }
  if (hasMatcher("toHaveCSS", "toHaveClass") ||
      has("css", "class", "style", "scroll", "scrolltop", "scrollleft", "height", "width", "contentheight",
        "clientheight", "offsetheight", "viewportheight", "boundingbox")) {
    return "style_or_visual_state";
  }
  if (hasMatcher("toBeEnabled", "toBeDisabled", "toBeChecked", "toBeFocused", "toBeEditable", "toBeClickable") ||
      has("enabled", "disabled", "checked", "focused", "editable", "clickable", "selected")) {
    return "interactive_state";
  }
  if (hasMatcher("toBeVisible", "toBeHidden", "toBeAttached", "toBeInViewport", "toBeInTheDocument") ||
      has("visible", "hidden", "exist", "exists", "attached", "viewport", "document")) {
    return "element_presence";
  }
  if (has("value", "attr", "attribute", "property", "prop", "id", "detail", "state", "data", "key")) {
    return "value_or_attribute_correctness";
  }
  if (GENERIC_VALUE_MATCHER_NAMES.has(matcherKey)) {
    return "value_or_attribute_correctness";
  }
  return "";
}

function primaryCallbackIntent(intents) {
  const present = new Set(intents.filter(Boolean));
  for (const intent of CALLBACK_INTENT_PRIORITY) {
    if (present.has(intent)) return intent;
  }
  return "";
}

function callbackAssertionSummary(call, frameworkHint) {
  const callback = callbackFunctionArgForAssertion(call);
  if (!callback) return {};
  const nested = [];
  const seen = new Set();

  const recordNestedAssertion = (desc, matcher) => {
    if (!matcher || !isSemanticMatcherName(matcher)) return;
    const expr = Node.isCallExpression(desc) ? desc.getExpression() : desc;
    const root = findAssertionRootCallInExpression(expr);
    const subject = root ? root.getArguments()[0] : null;
    const subjectSegments = expressionSegments(subject);
    const matcherSegments = expressionSegments(expr);
    const literals = Node.isCallExpression(desc) ? literalArgValues(desc) : [];
    const intent = classifyCallbackIntentFromAst(matcher, subjectSegments, matcherSegments, literals);
    const key = `${desc.getStart()}:${matcher}`;
    if (seen.has(key)) return;
    seen.add(key);
    nested.push({
      matcher,
      intent,
      subject_segments: subjectSegments.slice(0, 12),
      matcher_segments: matcherSegments.slice(0, 12),
      literal_args: literals.slice(0, 4),
    });
  };

  callback.forEachDescendant((desc) => {
    if (Node.isCallExpression(desc)) {
      const matcher = cypressSemanticMatcherFromCall(desc) || matcherNameFromCall(desc);
      recordNestedAssertion(desc, matcher);
      return;
    }
    if (!Node.isPropertyAccessExpression(desc)) return;
    const parent = desc.getParent();
    if (Node.isCallExpression(parent) && parent.getExpression() === desc) return;
    const matcher = desc.getName();
    recordNestedAssertion(desc, matcher);
  });

  if (!nested.length) return {};
  const intents = nested.map((item) => item.intent).filter(Boolean);
  const primary = primaryCallbackIntent(intents);
  const fields = {
    assertion_callback_nested_assertion_count: nested.length,
    assertion_callback_nested_matchers_json: JSON.stringify(nested.map((item) => item.matcher)),
    assertion_callback_subject_properties_json: JSON.stringify(
      [...new Set(nested.flatMap((item) => item.subject_segments || []))].slice(0, 40)
    ),
    assertion_callback_literal_args_json: JSON.stringify(
      [...new Set(nested.flatMap((item) => item.literal_args || []))].slice(0, 40)
    ),
    assertion_callback_intent_hints_json: JSON.stringify([...new Set(intents)]),
  };
  if (primary) {
    fields.assertion_callback_intent_hint_ast = primary;
    fields.assertion_callback_intent_basis_ast = "ast_callback_nested_assertion";
  }
  return fields;
}

function subjectSemanticRoleFromAst(subject, semanticMatcher, matcher, chainText) {
  const path = subject?.property_path || [];
  const text = `${path.join(".")} ${subject?.subject_text_ast || ""} ${semanticMatcher || ""} ${matcher || ""} ${chainText || ""}`;
  const key = normalizedAlnum(`${semanticMatcher || ""} ${matcher || ""}`);
  const has = (...patterns) => patterns.some((pat) => pat.test(text));

  if (
    /to(matchsnapshot|matchscreenshot|havescreenshot)|matchariasnapshot/i.test(semanticMatcher || matcher || "") ||
    /\b(?:screenshot|snapshot)\s*\(/i.test(text)
  ) {
    return { role: "visual_snapshot_api", basis: "ast_assertion_matcher_or_subject" };
  }
  if (
    subject?.kind === "network" ||
    subject?.kind === "response" ||
    subject?.kind === "request" ||
    has(/\b(?:interception|xhr|request|response|req|res|fetch|httpresponse|apiresponse)\b/i)
  ) {
    if (has(/\b(?:status|statuscode|statusmessage)\b/i)) {
      return { role: "network_status", basis: "ast_assertion_subject_path" };
    }
    if (has(/\b(?:headers?|body|payload|postdata|method|url)\b/i)) {
      return { role: "network_payload", basis: "ast_assertion_subject_path" };
    }
  }
  if (/to(beattached|beinviewport|beinthedocument|bevisible|behidden)|(?:^|\\W)(?:exist|exists)(?:\\W|$)/i.test(key)) {
    return { role: "element_presence", basis: "ast_assertion_matcher" };
  }
  if (has(/\b(?:isPresent|toBeAttached|toBeInViewport|toBeInTheDocument)\b/i)) {
    return { role: "element_presence", basis: "ast_assertion_subject_path" };
  }
  if (has(/\b(?:callcount|counter|event|receivedevent|eventsummary|change|blur|click|deletecounter|spy|stub)\b/i)) {
    return { role: "ui_event_counter", basis: "ast_assertion_subject_path" };
  }
  if (
    /to(beenabled|bedisabled|bechecked|befocused|beeditable)|(?:^|\\W)(?:enabled|disabled|checked|focused|selected)(?:\\W|$)/i.test(key) ||
    has(/\b(?:enabled|disabled|checked|focused|selected|typedSignatureEnabled)\b/i)
  ) {
    return { role: "ui_control_state", basis: "ast_assertion_subject_path" };
  }
  if (
    /to(havecss|haveclass)|(?:^|\\W)(?:havecss|haveclass)(?:\\W|$)/i.test(key) ||
    has(/\b(?:css|class|style|height|width|padding|margin|opacity|color|font|rgb|layout|bounding|offset|clientheight|fill-opacity)\b/i)
  ) {
    return { role: "style_layout_property", basis: "ast_assertion_subject_path" };
  }
  if (
    /to(containtext|havetext|havetitle)|(?:^|\\W)(?:contain|contains|include|havehtml)(?:\\W|$)/i.test(key) ||
    has(/\b(?:text|textcontent|innertext|alltextcontents|title|subject|message|label|html|content)\b/i)
  ) {
    return { role: "text_content_payload", basis: "ast_assertion_subject_path" };
  }
  if (/to(havecount|havelength)|(?:^|\\W)(?:length|lengthof|count|size)(?:\\W|$)/i.test(key) || has(/\b(?:length|count|size|rowcount)\b/i)) {
    return { role: "collection_size", basis: "ast_assertion_subject_path" };
  }
  if (/to(beinstanceof|matchobject)|(?:^|\\W)(?:instanceof|deepinclude|havesubset)(?:\\W|$)/i.test(key) || has(/\b(?:result|parseddata|apiresult|payload|schema|object|error|page)\b/i)) {
    return { role: "api_object_contract", basis: "ast_assertion_subject_path" };
  }
  if (path.length || subject?.kind === "primitive") {
    return { role: "scalar_property", basis: "ast_assertion_subject_path" };
  }
  return { role: "", basis: "" };
}

function extractAssertionChainFields(callNode, filePath, frameworkHint) {
  const visitedCall = Node.isCallExpression(callNode) ? callNode : null;
  if (!visitedCall) return null;

  const visitedName = getCallName(visitedCall);
  if (visitedName === "expect" || visitedName === "assert") {
    const parent = visitedCall.getParent();
    if (parent && Node.isPropertyAccessExpression(parent)) {
      const gp = parent.getParent();
      if (gp && Node.isCallExpression(gp) && isChainTraversalName(getCallName(gp))) {
        return null;
      }
    }
  }

  const propMatcher = matcherNameFromCall(visitedCall);
  if (!isSemanticMatcherName(visitedName) && !CYPRESS_MATCHERS.has(visitedName)) {
    if (!propMatcher || !isSemanticMatcherName(propMatcher)) return null;
  }

  const topCall = findTopmostChainCall(visitedCall);
  const matchers = collectMatchersFromChain(topCall, frameworkHint);
  if (!matchers.length) return null;

  const idx = matchers.findIndex((m) => m.call === visitedCall);
  if (idx < 0) return null;

  const entry = matchers[idx];
  const rootCall = entry.rootCall || matchers[0].rootCall || visitedCall;
  const chainText = topCall.getText();
  const semanticMatcher = cypressSemanticMatcherFromCall(visitedCall);
  const groupKind = detectGroupKindFromAncestors(visitedCall, chainText);
  const chainMods = detectChainModifiers(chainText, semanticMatcher);
  const librarySyntax = detectAssertionLibrarySyntax(visitedCall, chainText, frameworkHint);
  const frameworkContext = normalizeFrameworkHint(frameworkHint) || "unknown";
  const subject = classifySubjectInfo(visitedCall, rootCall, topCall);
  const callbackSummary = callbackAssertionSummary(visitedCall, frameworkHint);
  const matcherSequence = chainMatcherSequence(matchers);
  const nonAssertionMethods = nonAssertionChainMethods(topCall, matchers);
  const semanticRole = subjectSemanticRoleFromAst(subject, semanticMatcher, entry.matcher || visitedName || "", chainText);

  return {
    assertion_chain_root_id: chainRootId(filePath, rootCall),
    assertion_chain_index: idx,
    assertion_chain_length: matchers.length,
    assertion_matcher: entry.matcher || visitedName || "",
    assertion_semantic_matcher_ast: semanticMatcher,
    assertion_semantic_matcher_basis_ast: semanticMatcher ? "ast_cypress_should_argument" : "",
    assertion_subject_kind: subject.kind,
    assertion_subject_basis_ast: subject.basis,
    assertion_subject_root_ast: subject.root_identifier_ast || "",
    assertion_subject_path_json: JSON.stringify(subject.property_path || []),
    assertion_subject_text_ast: subject.subject_text_ast || "",
    assertion_subject_semantic_role_ast: semanticRole.role,
    assertion_subject_semantic_role_basis_ast: semanticRole.basis,
    chain_matcher_sequence_json: JSON.stringify(matcherSequence),
    non_assertion_chain_methods_json: JSON.stringify(nonAssertionMethods),
    assertion_framework_context: frameworkContext,
    assertion_library_syntax: librarySyntax,
    assertion_framework: frameworkContext,
    is_soft_assertion: isSoftAssertion(visitedCall, chainText),
    is_negated_assertion: chainMods.is_negated_assertion,
    promise_modifier: chainMods.promise_modifier,
    chai_modifier_deep: chainMods.chai_modifier_deep,
    assertion_modifiers_json: chainMods.assertion_modifiers_json,
    is_grouped_assertion: groupKind !== "none",
    assertion_group_kind: groupKind,
    assertion_chain_raw_code: chainText.slice(0, 1500),
    assertion_chain_raw_code_length: chainText.length,
    assertion_chain_raw_code_truncated: chainText.length > 1500,
    ...callbackSummary,
  };
}

module.exports = {
  extractAssertionChainFields,
  collectMatchersFromChain,
  findTopmostChainCall,
  detectAssertionLibrarySyntax,
  detectAssertionFramework: detectAssertionLibrarySyntax,
  isSemanticMatcherName,
  isChainModifierName,
  semanticMatcherIsNegated,
};
