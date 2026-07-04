"use strict";

/**
 * RQ1 AST gap enrichment (Milestone 3).
 * Inline setup/cleanup, navigation bootstrap literals, mixed helper body hints.
 */

const { Node } = require("ts-morph");
const { getCallName, getOutermostCall, extractCallChainFromCall } = require("./astPatternExtractor");
const { extractNavigationTargetAst } = require("./actionSignatureExtractor");

const AUTH_APIS = new Set(["session", "login", "logout", "task"]);
const DATA_APIS = new Set(["request", "fixture", "task"]);
const NETWORK_APIS = new Set(["intercept", "route"]);
const CLEANUP_RE =
  /\b(cleanup|teardown|clear|reset|delete|restore|close|logout|remove|destroy|drop)\b/i;
const SETUP_RE = /\b(setup|seed|prepare|initialize|create|insert|mock|stub|login|auth)\b/i;
const TIME_DEVICE_APIS = new Set(["clock", "tick", "viewport", "geolocation"]);
const UI_INTERACTION_CMDS = new Set([
  "click", "dblclick", "tap", "fill", "type", "press", "check", "uncheck", "hover",
  "clear", "select", "selectoption", "setinputfiles", "selectfile",
  "getbyrole", "getbytext", "getbylabel", "getbytestid", "locator", "get",
]);

function stripStringLiterals(text) {
  return String(text || "")
    .replace(/'(?:\\.|[^'\\])*'/g, "''")
    .replace(/"(?:\\.|[^"\\])*"/g, '""')
    .replace(/`(?:\\.|[^`\\])*`/g, "``");
}

function textForIntentScan(call, terminal, text) {
  const cmd = (terminal || getCallName(call) || "").toLowerCase();
  if (UI_INTERACTION_CMDS.has(cmd)) return cmd;
  return stripStringLiterals(text);
}

const HOOK_SOURCE_MAP = {
  before: "before",
  beforeEach: "beforeEach",
  beforeAll: "beforeAll",
  after: "after",
  afterEach: "afterEach",
  afterAll: "afterAll",
};

const NAV_METHODS = new Set(["goto", "visit", "url", "navigateTo", "navigate", "open"]);

const SETUP_API_CATEGORIES = new Set([
  "auth_session",
  "network_mock",
  "test_data_api",
  "test_data_fixture",
  "backend_task",
  "time_device_emulation",
  "setup_utility",
]);
const STRUCTURED_FRAMEWORK_API_BASES = new Set([
  "ast_known_framework_api",
  "ast_nested_framework_api",
]);

function bestPhaseBasis(bases) {
  const clean = (bases || []).filter(Boolean);
  if (!clean.length) return "";
  const structured = clean.find((basis) => STRUCTURED_FRAMEWORK_API_BASES.has(basis));
  return structured || clean[0];
}

function combinedPhaseBasis(phases, hint) {
  if (!phases || !hint) return "";
  if (hint === "setup") return phases.setupBasis || "";
  if (hint === "teardown") return phases.teardownBasis || "";
  if (hint !== "setup_and_teardown") return "";
  const bases = [phases.setupBasis, phases.teardownBasis].filter(Boolean);
  if (!bases.length) return "";
  if (bases.every((basis) => STRUCTURED_FRAMEWORK_API_BASES.has(basis))) {
    return new Set(bases).size === 1 ? bases[0] : "mixed_structured_framework_api";
  }
  if (bases.some((basis) => STRUCTURED_FRAMEWORK_API_BASES.has(basis))) {
    return "mixed_ast_and_heuristic";
  }
  return bases[0];
}

function inferStatementPhaseHint(category) {
  if (category === "cleanup") return "teardown";
  if (SETUP_API_CATEGORIES.has(category)) return "setup";
  return "";
}

function firstStringLiterals(call, limit = 3) {
  if (!call || !Node.isCallExpression(call)) return [];
  const out = [];
  for (const arg of call.getArguments()) {
    if (Node.isStringLiteral(arg) || Node.isNoSubstitutionTemplateLiteral(arg)) {
      out.push(arg.getLiteralText());
      if (out.length >= limit) break;
    }
  }
  return out;
}

function normalizedHttpMethod(value) {
  const method = String(value || "").trim().replace(/^['"`]|['"`]$/g, "").toLowerCase();
  if (method === "del") return "delete";
  if (["get", "post", "put", "patch", "delete", "head", "options"].includes(method)) {
    return method;
  }
  return "";
}

function expressionTextValue(node) {
  if (!node) return "";
  if (Node.isStringLiteral(node) || Node.isNoSubstitutionTemplateLiteral(node)) {
    return node.getLiteralText?.() ?? node.getText().replace(/^['"`]|['"`]$/g, "");
  }
  if (Node.isTemplateExpression(node)) return node.getText();
  return node.getText();
}

function objectPropertyByName(objectNode, names) {
  if (!objectNode || !Node.isObjectLiteralExpression(objectNode)) return null;
  const wanted = new Set(names.map((name) => String(name).toLowerCase()));
  for (const prop of objectNode.getProperties()) {
    if (!Node.isPropertyAssignment(prop) && !Node.isShorthandPropertyAssignment(prop)) continue;
    const nameNode = prop.getNameNode?.();
    const rawName =
      nameNode && (Node.isStringLiteral(nameNode) || Node.isNoSubstitutionTemplateLiteral(nameNode))
        ? nameNode.getLiteralText()
        : prop.getName?.();
    if (!wanted.has(String(rawName || "").toLowerCase())) continue;
    if (Node.isShorthandPropertyAssignment(prop)) return prop.getNameNode?.() || null;
    return prop.getInitializer?.() || null;
  }
  return null;
}

function objectHasAnyProperty(objectNode, names) {
  return Boolean(objectPropertyByName(objectNode, names));
}

function isRequestLikeCall(chain, terminal) {
  const root = (chain[0] || "").toLowerCase();
  const cmd = String(terminal || "").toLowerCase();
  if (root === "cy" && cmd === "request") return true;
  if (root === "page" && cmd === "request") return true;
  if (["request", "apirequestcontext"].includes(root) && ["get", "post", "put", "patch", "delete", "del", "fetch"].includes(cmd)) {
    return true;
  }
  if (["get", "post", "put", "patch", "delete", "del"].includes(cmd) && /request/i.test(root)) {
    return true;
  }
  if (cmd === "fetch" || root === "fetch") return true;
  return false;
}

function classifyRequestTargetDomain(method, target, hasBody) {
  const text = String(target || "").toLowerCase();
  if (!text) return "unknown";
  if (/\b(?:config|settings?|preferences?|feature[-_]?flags?)\b/.test(text)) return "config";
  if (/\b(?:login|logout|signin|signout|session|token|auth|oauth|saml)\b/.test(text)) return "auth";
  if (
    /\/api\/|\/graphql\b|\/v\d+\//.test(text) ||
    /\b(?:users?|teams?|channels?|projects?|issues?|items?|records?|workspaces?|apps?|applications?|fixtures?)\b/.test(text) ||
    hasBody ||
    ["post", "put", "patch", "delete"].includes(method)
  ) {
    return "backend_data";
  }
  return "unknown";
}

function requestMethodFromArgs(call, chain, terminal) {
  const args = call.getArguments();
  const cmd = String(terminal || "").toLowerCase();
  const cmdMethod = normalizedHttpMethod(cmd);
  if (cmdMethod && !(chain[0] === "cy" && cmd === "request")) return cmdMethod;
  const first = args[0];
  if (first && Node.isObjectLiteralExpression(first)) {
    const methodNode = objectPropertyByName(first, ["method"]);
    return normalizedHttpMethod(expressionTextValue(methodNode)) || "get";
  }
  const firstLiteral = first ? expressionTextValue(first) : "";
  const positionalMethod = normalizedHttpMethod(firstLiteral);
  if (positionalMethod) return positionalMethod;
  const second = args[1];
  if (second && Node.isObjectLiteralExpression(second)) {
    const methodNode = objectPropertyByName(second, ["method"]);
    const method = normalizedHttpMethod(expressionTextValue(methodNode));
    if (method) return method;
  }
  return cmd === "request" || cmd === "fetch" ? "get" : cmdMethod;
}

function requestTargetFromArgs(call, method) {
  const args = call.getArguments();
  const first = args[0];
  if (first && Node.isObjectLiteralExpression(first)) {
    const targetNode = objectPropertyByName(first, ["url", "uri", "path", "endpoint"]);
    return expressionTextValue(targetNode);
  }
  const firstText = first ? expressionTextValue(first) : "";
  if (normalizedHttpMethod(firstText) && args[1]) {
    return expressionTextValue(args[1]);
  }
  return firstText;
}

function requestHasBodyFromArgs(call) {
  const args = call.getArguments();
  const first = args[0];
  if (first && Node.isObjectLiteralExpression(first)) {
    return objectHasAnyProperty(first, ["body", "data", "payload", "json"]);
  }
  const firstText = first ? expressionTextValue(first) : "";
  if (normalizedHttpMethod(firstText)) {
    if (args[2]) return true;
    const options = args[1];
    return options && Node.isObjectLiteralExpression(options)
      ? objectHasAnyProperty(options, ["body", "data", "payload", "json"])
      : false;
  }
  const second = args[1];
  if (second && Node.isObjectLiteralExpression(second)) {
    return objectHasAnyProperty(second, ["body", "data", "payload", "json"]);
  }
  return false;
}

function extractRequestAstDetail(call, chain, terminal) {
  if (!call || !Node.isCallExpression(call) || !isRequestLikeCall(chain, terminal)) return null;
  const args = call.getArguments();
  const method = requestMethodFromArgs(call, chain, terminal);
  const target = requestTargetFromArgs(call, method);
  const hasBody = Boolean(requestHasBodyFromArgs(call));
  const first = args[0];
  const basis = first && Node.isObjectLiteralExpression(first)
    ? "ast_object_argument"
    : "ast_positional_arguments";
  return {
    method,
    target,
    hasBody,
    domain: classifyRequestTargetDomain(method, target, hasBody),
    basis,
  };
}

function frameworkCommandLiteralPhaseHint(call, chain, terminal) {
  if (!call || !Node.isCallExpression(call)) return "";
  const root = (chain[0] || "").toLowerCase();
  if (root !== "cy" || terminal !== "task") return "";
  const first = call.getArguments()[0];
  if (!first || !(Node.isStringLiteral(first) || Node.isNoSubstitutionTemplateLiteral(first))) {
    return "";
  }
  const command = first.getLiteralText();
  const setup = SETUP_RE.test(command);
  const teardown = CLEANUP_RE.test(command);
  if (setup && teardown) return "setup_and_teardown";
  if (teardown) return "teardown";
  if (setup) return "setup";
  return "";
}

function findNestedFrameworkApiDetail(call) {
  if (!call || !Node.isCallExpression(call)) return null;
  let found = null;
  call.forEachDescendant((n) => {
    if (found || !Node.isCallExpression(n)) return;
    const nestedChain = extractCallChainFromCall(n);
    const nestedTerminal = getCallName(n) || "";
    const nested = classifyFrameworkApiCategoryDetail(
      nestedChain,
      nestedTerminal,
      "",
      null,
      { skipNestedScan: true, skipTextFallback: true },
    );
    if (nested.category !== "unknown") {
      found = {
        category: nested.category,
        basis: "ast_nested_framework_api",
      };
    }
  });
  return found;
}

function classifyFrameworkApiCategoryDetail(chain, terminal, text, callNode = null, options = {}) {
  const cmd = terminal || chain[chain.length - 1] || "";
  const scanText = textForIntentScan(null, cmd, text);
  const strippedText = stripStringLiterals(text);
  const low = scanText.toLowerCase();
  const root = (chain[0] || "").split(".")[0];
  const rootLow = root.toLowerCase();
  const cmdLow = cmd.toLowerCase();
  const detail = (category, basis = "ast_known_framework_api") => ({ category, basis });

  if (rootLow === "cy") {
    if (cmd === "session") return detail("auth_session");
    if (cmd === "intercept") return detail("network_mock");
    if (cmd === "request") return detail("test_data_api");
    if (cmd === "task") return detail("backend_task");
    if (cmd === "fixture") return detail("test_data_fixture");
    if (TIME_DEVICE_APIS.has(cmd)) return detail("time_device_emulation");
    if (cmd === "visit") return detail("navigation");
    if (!UI_INTERACTION_CMDS.has(cmdLow) && (CLEANUP_RE.test(cmd) || CLEANUP_RE.test(low))) {
      return detail("cleanup", "callee_name_heuristic");
    }
  }

  if ((rootLow === "page" || rootLow === "browsercontext") && cmdLow === "route") {
    return detail("network_mock");
  }
  if (cmdLow === "storagestate" || cmdLow === "storage_state") {
    return detail("auth_session");
  }
  if (rootLow === "page" && cmdLow === "request") {
    return detail("test_data_api");
  }
  if (NAV_METHODS.has(cmd.toLowerCase()) || cmd === "goto" || cmd === "visit") return detail("navigation");

  if (!options.skipNestedScan) {
    const nested = findNestedFrameworkApiDetail(callNode);
    if (nested) return nested;
  }

  if (options.skipTextFallback) return detail("unknown", "");

  if (/\bcy\.session\b/.test(strippedText)) return detail("auth_session", "call_text_framework_api");
  if (/\bcy\.intercept\b/.test(strippedText)) return detail("network_mock", "call_text_framework_api");
  if (/\bcy\.request\b/.test(strippedText)) return detail("test_data_api", "call_text_framework_api");
  if (/\bcy\.task\b/.test(strippedText)) return detail("backend_task", "call_text_framework_api");
  if (/\bcy\.fixture\b/.test(strippedText)) return detail("test_data_fixture", "call_text_framework_api");
  if (/\bpage\.route\b/.test(strippedText) || /\bbrowsercontext\.route\b/.test(strippedText)) {
    return detail("network_mock", "call_text_framework_api");
  }
  if (/\bstoragestate\b/i.test(strippedText) || /\bstorage_state\b/i.test(strippedText)) {
    return detail("auth_session", "call_text_framework_api");
  }
  if (/\bapirequestcontext\b/i.test(strippedText) || /\bpage\.request\b/.test(strippedText)) {
    return detail("test_data_api", "call_text_framework_api");
  }

  if (!UI_INTERACTION_CMDS.has(cmdLow) && (CLEANUP_RE.test(cmd) || CLEANUP_RE.test(low))) {
    return detail("cleanup", "callee_name_heuristic");
  }
  if (!UI_INTERACTION_CMDS.has(cmdLow) && (SETUP_RE.test(cmd) || SETUP_RE.test(low))) {
    return detail("setup_utility", "callee_name_heuristic");
  }

  return detail("unknown", "");
}

function classifyFrameworkApiCategory(chain, terminal, text, callNode = null) {
  return classifyFrameworkApiCategoryDetail(chain, terminal, text, callNode).category;
}

function classifyStateMutationKind(category, text, terminal = "") {
  const low = stripStringLiterals(text).toLowerCase();
  if (category === "auth_session") return "session";
  if (category === "network_mock") return "network";
  if (category === "test_data_api" || category === "test_data_fixture") return "data";
  if (category === "backend_task") return "backend";
  if (category === "navigation") return "navigation";
  if (category === "cleanup") return "cleanup";
  if (category === "time_device_emulation") return "environment";
  if (UI_INTERACTION_CMDS.has(String(terminal || "").toLowerCase())) return "unknown";
  if (CLEANUP_RE.test(low)) return "cleanup";
  if (SETUP_RE.test(low)) return "setup";
  return "unknown";
}

function classifyTargetResourceKind(category) {
  switch (category) {
    case "auth_session":
      return "auth";
    case "network_mock":
      return "network";
    case "test_data_api":
    case "test_data_fixture":
    case "backend_task":
      return "data";
    case "navigation":
      return "route";
    case "cleanup":
      return "state";
    case "time_device_emulation":
      return "browser_environment";
    default:
      return "unknown";
  }
}

function scanFunctionBodyPhaseHints(bodyNode) {
  if (!bodyNode) {
    return { hasSetup: false, hasTeardown: false, setupBasis: "", teardownBasis: "" };
  }
  let hasSetup = false;
  let hasTeardown = false;
  const setupBases = [];
  const teardownBases = [];
  const addSetup = (basis) => {
    hasSetup = true;
    setupBases.push(basis || "callee_name_heuristic");
  };
  const addTeardown = (basis) => {
    hasTeardown = true;
    teardownBases.push(basis || "callee_name_heuristic");
  };
  bodyNode.forEachDescendant((n) => {
    if (!Node.isCallExpression(n)) return;
    const text = n.getText();
    const name = getCallName(n);
    const chain = extractCallChainFromCall(n);
    const api = classifyFrameworkApiCategoryDetail(chain, name, text, n);
    const cat = api.category;
    if (cat === "cleanup") addTeardown(api.basis);
    if (cat !== "unknown" && cat !== "cleanup" && cat !== "navigation") addSetup(api.basis);
    const frameworkCommandPhase = frameworkCommandLiteralPhaseHint(n, chain, name);
    if (frameworkCommandPhase === "setup_and_teardown") {
      addSetup("ast_task_literal_heuristic");
      addTeardown("ast_task_literal_heuristic");
    } else if (frameworkCommandPhase === "setup") {
      addSetup("ast_task_literal_heuristic");
    } else if (frameworkCommandPhase === "teardown") {
      addTeardown("ast_task_literal_heuristic");
    }
    const scanText = textForIntentScan(n, name, text);
    const nameLow = (name || "").toLowerCase();
    const isUiInteraction = UI_INTERACTION_CMDS.has(nameLow);
    if (!isUiInteraction && (CLEANUP_RE.test(name) || CLEANUP_RE.test(scanText))) {
      addTeardown("callee_name_heuristic");
    }
    if (!isUiInteraction && (SETUP_RE.test(name) || SETUP_RE.test(scanText) || NETWORK_APIS.has(name))) {
      addSetup("callee_name_heuristic");
    }
  });
  return {
    hasSetup,
    hasTeardown,
    setupBasis: bestPhaseBasis(setupBases),
    teardownBasis: bestPhaseBasis(teardownBases),
  };
}

function attachSetupTeardownPatternFields(node, featureType, sourceKind, framework) {
  const call = Node.isCallExpression(node) ? node : getOutermostCall(node);
  if (!call) return {};

  const chain = extractCallChainFromCall(call);
  const terminal = getCallName(call) || "";
  const text = call.getText();
  const literals = firstStringLiterals(call);
  const hookType = HOOK_SOURCE_MAP[sourceKind] || "";

  const frameworkApi = classifyFrameworkApiCategoryDetail(chain, terminal, text, call);
  const frameworkApiCategory = frameworkApi.category;
  const stateMutationKind = classifyStateMutationKind(frameworkApiCategory, text, terminal);
  const targetResourceKind = classifyTargetResourceKind(frameworkApiCategory);
  const requestAst = extractRequestAstDetail(call, chain, terminal);

  const out = {
    lifecycle_scope_hint: hookType || sourceKind || "",
    hook_type: hookType,
    callee_chain_json: JSON.stringify(chain),
    framework_api_category: frameworkApiCategory,
    framework_api_category_basis_ast: frameworkApi.basis,
    literal_args_json: JSON.stringify(literals),
    state_mutation_kind: stateMutationKind,
    target_resource_kind: targetResourceKind,
    source_start_offset: call.getStart(),
    source_end_offset: call.getEnd(),
  };

  if (requestAst) {
    out.request_method_ast = requestAst.method;
    out.request_target_url_ast = String(requestAst.target || "").slice(0, 300);
    out.request_has_body_ast = requestAst.hasBody;
    out.request_target_domain_ast = requestAst.domain;
    out.request_evidence_basis_ast = requestAst.basis;
  }

  const statementPhaseHint = inferStatementPhaseHint(frameworkApiCategory);
  if (statementPhaseHint) {
    out.statement_phase_hint_ast = statementPhaseHint;
    out.statement_phase_hint_basis_ast = frameworkApi.basis;
  }

  if (featureType === "helper_call" || featureType === "custom_command_call") {
    const body = resolveInlineFunctionBody(call);
    if (body) {
      out.helper_resolution_status = "inline_body";
      const phases = scanFunctionBodyPhaseHints(body);
      if (phases.hasSetup && phases.hasTeardown) {
        out.helper_body_phase_hint_ast = "setup_and_teardown";
      } else if (phases.hasTeardown) {
        out.helper_body_phase_hint_ast = "teardown";
      } else if (phases.hasSetup) {
        out.helper_body_phase_hint_ast = "setup";
      }
      if (out.helper_body_phase_hint_ast) {
        out.helper_body_phase_hint_basis_ast = combinedPhaseBasis(
          phases,
          out.helper_body_phase_hint_ast,
        );
      }
    } else {
      out.helper_resolution_status = "unresolved";
    }
  }

  const navTarget = extractNavigationTargetAst(call, terminal);
  if (navTarget) {
    out.navigation_target_ast = navTarget;
    out.navigation_target_evidence_basis_ast = "string_literal_arg";
  }

  if (frameworkApiCategory === "navigation" && (sourceKind === "test_body" || !hookType)) {
    out.navigation_bootstrap_candidate_ast = 1;
  }

  return out;
}

function resolveInlineFunctionBody(call) {
  const expr = call.getExpression();
  if (Node.isIdentifier(expr)) {
    const decl = expr.getSymbol()?.getDeclarations()?.[0];
    if (decl && Node.isFunctionDeclaration(decl)) return decl;
    if (decl && Node.isVariableDeclaration(decl)) {
      const init = decl.getInitializer();
      if (Node.isArrowFunction(init) || Node.isFunctionExpression(init)) return init;
    }
  }
  return null;
}

module.exports = {
  attachSetupTeardownPatternFields,
  classifyFrameworkApiCategory,
  classifyFrameworkApiCategoryDetail,
  scanFunctionBodyPhaseHints,
};
