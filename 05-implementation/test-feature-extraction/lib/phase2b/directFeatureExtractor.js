"use strict";

const { SyntaxKind, Node } = require("ts-morph");
const {
  UI_ACTION_PATTERNS,
  SETUP_PATTERNS,
  INPUT_PATTERNS,
  CYPRESS_DIRECT_UI,
  isCypressLocatorQueryCommand,
  CYPRESS_BUILTIN,
  CYPRESS_TEST_UTILITY,
  CYPRESS_SUBJECT_CONTROL,
  CYPRESS_REAL_UI,
  CYPRESS_CONTROL,
  CYPRESS_BROWSER_CONTEXT,
  TEXT_ENTRY_VALUE_ARG,
  TEXT_ENTRY_METHODS,
  CYPRESS_ASSERT_MATCHER_VALUES,
} = require("../shared/patterns");
const { collectTestLikeIdentifiers } = require("../shared/identifiers");
const { collectHooks, hooksForTestCase } = require("./hookCollector");
const { getRawSnippet } = require("../shared/utils");
const { resolveFrameworkForFile, getImportModules } = require("../shared/framework");
const { buildImportMap } = require("../phase2c/importResolver");
const { getCallbackArgFromCall } = require("../shared/identifiers");
const { attachAstPatternFields } = require("./astPatternExtractor");
const {
  attachInputPatternFields,
  extractTextEntryInputFacts,
  resolveUploadValueArgIndex,
} = require("./inputPatternExtractor");
const { resolveTextEntryValueArgIndex } = require("../shared/textEntryValueArg");
const { buildPlaywrightFixtureProvenanceMap } = require("../shared/playwrightFixtureProvenance");
const { buildPageSymbolOrigins } = require("./pageSymbolOrigins");
const {
  createControlFlowStack,
  cloneControlFlowStack,
  enterControlFlowNode,
  exitControlFlowNode,
  forEachChildRespectingCallbackIteration,
  snapshotControlFlowEnclosure,
  findEnclosingFunctionBody,
} = require("./controlFlowEnclosure");
const { buildActionSignatureJson, inferUiActionCategory } = require("./actionSignatureExtractor");
const { attachSetupTeardownPatternFields } = require("./setupTeardownPatternExtractor");
const { extractAssertionChainFields } = require("./assertionChainExtractor");

const HELPER_CALL_BLOCKLIST = new Set([
  "setTimeout", "clearTimeout", "setInterval", "clearInterval", "setImmediate",
  "console", "JSON", "Object", "Array", "Math", "Date", "Promise", "Error",
  "parseInt", "parseFloat", "isNaN", "Boolean", "Number", "String", "RegExp",
  "require", "import", "fetch", "Buffer", "process", "queueMicrotask",
]);

/** Playwright locator/page interaction methods (terminal callee only). */
const PLAYWRIGHT_LOCATOR_ACTIONS = new Set([
  "click", "dblclick", "fill", "press", "clear", "check", "uncheck", "hover",
  "selectOption", "setInputFiles", "tap", "dispatchEvent", "type",
]);

const PLAYWRIGHT_MOUSE_DRAG_METHODS = new Set(["down", "move", "up"]);
const SCROLL_MUTATION_PROPERTIES = new Set(["scrollTop", "scrollLeft"]);
const SCROLL_CALL_METHODS = new Set(["scroll", "scrollTo", "scrollBy", "scrollIntoView"]);

/** Canvas / graphics context receivers — not page/locator UI. */
const CANVAS_RECEIVER_ROOT_RE =
  /^(ctx|context|canvasContext|canvas|gl|gfx|graphics|renderingContext|chartCtx|chartContext)$/i;

const CANVAS_DRAWING_METHODS = new Set([
  "fill", "stroke", "fillRect", "strokeRect", "clearRect", "arc", "beginPath", "closePath",
  "moveTo", "lineTo", "drawImage", "fillText", "strokeText", "clip", "save", "restore",
  "scale", "rotate", "translate", "transform", "setTransform", "resetTransform",
  "quadraticCurveTo", "bezierCurveTo", "rect", "ellipse",
]);

const NON_UI_TYPE_RECEIVER_ROOT_RE =
  /^(msg|message|consoleMessage|consoleMsg|response|request|event)$/i;
const NON_UI_TYPE_RECEIVER_TYPE_RE =
  /\b(ConsoleMessage|Response|APIResponse|HTTPResponse|Request|HTTPRequest|Event|Message)\b/i;
const UI_TYPE_RECEIVER_TYPE_RE = /\b(Locator|ElementHandle|Page|Frame)\b/i;

const PLAYWRIGHT_WAIT_METHODS = new Set([
  "waitFor", "waitForTimeout", "waitForLoadState", "waitForURL", "waitForResponse",
  "waitForSelector", "waitForFunction", "waitForEvent",
]);

const PUPPETEER_WAIT_METHODS = new Set([
  "waitForSelector", "waitForNavigation", "waitForResponse", "waitForNetworkIdle",
  "waitForFunction",
]);

const API_REQUEST_METHODS = new Set(["get", "post", "put", "patch", "delete", "del"]);

const CYPRESS_BODY_CONTROL_TYPES = {
  wait: "wait_synchronization",
  waitUntil: "wait_synchronization",
  viewport: "browser_context_control",
  clock: "time_control",
  tick: "time_control",
  log: "test_utility",
  wrap: "cypress_subject_control",
  intercept: "network_mock",
  reload: "browser_context_control",
};

function exprMatchesAny(expr, patterns) {
  return patterns.some((re) => re.test(expr));
}

/** True only for hook callbacks (beforeEach, etc.) — not helper/cypress_command expansion. */
function isHookSource(sourceKind) {
  if (!sourceKind || sourceKind === "test_body") return false;
  if (/^(before|after)(Each|All)?$/.test(sourceKind)) return true;
  if (sourceKind === "before" || sourceKind === "after") return true;
  return false;
}

function getInvocationMethod(callNode) {
  try {
    const expr = callNode.getExpression();
    if (Node.isPropertyAccessExpression(expr)) return expr.getName();
    if (Node.isIdentifier(expr)) return expr.getText();
  } catch (_) {
    /* ignore */
  }
  return null;
}

function isAssertionExpr(expr) {
  if (/^expect\s*\(/.test(expr) || /^assert\./.test(expr)) return true;
  if (/\bcy\.(should|and)\b/.test(expr)) return true;
  if (/\bt\.expect\s*\(/.test(expr)) return true;
  if (/\bbrowser\.(assert|expect)\./.test(expr)) return true;
  if (/expect\s*\([^)]*\)\s*\.\s*(contains?|includes?)\s*\(/i.test(expr)) return true;
  if (/expect\s*\([^)]*\)\s*\.\s*to\s*\.\s*(contain|include)\s*\(/i.test(expr)) return true;
  if (/expect\s*\([^)]*\)\s*\.\s*to(Be|Have|Contain)/.test(expr)) return true;
  if (/\.(toBeVisible|toBeHidden|toHaveURL|toHaveText|toContainText|toHaveAttribute|toHaveValue|toHaveScreenshot)\b/.test(expr)) {
    return /^await\s+expect\b/.test(expr) || /^expect\b/.test(expr) || /\)\.to/.test(expr);
  }
  if (/\.(should|and)\s*\(/.test(expr)) return true;
  return false;
}

function helperOracleFields(callNode, terminal, expr) {
  if (String(expr || "").includes(".")) return null;
  const callee = String(terminal || expr || "").split(".").pop();
  if (!callee || HELPER_CALL_BLOCKLIST.has(callee)) return null;
  if (/^(test|it|describe|before|after|beforeEach|afterEach|expect|assert)$/i.test(callee)) {
    return null;
  }

  let helperKind = "";
  if (/snapshot|screenshot/i.test(callee)) {
    helperKind = "snapshot_helper";
  } else if (/^expect[A-Z_]/.test(callee)) {
    helperKind = "expect_helper";
  } else if (/^assert[A-Z_]/.test(callee)) {
    helperKind = "assert_helper";
  } else if (/^verify[A-Z_]/.test(callee)) {
    helperKind = "verify_helper";
  }
  if (!helperKind) return null;

  return {
    source_kind: "helper_oracle",
    assertion_helper_kind_ast: helperKind,
    assertion_helper_detection_basis_ast: "callee_name_heuristic",
    assertion_helper_detection_confidence_ast: "medium",
    assertion_matcher: callee,
    assertion_semantic_matcher_ast: callee,
    assertion_semantic_matcher_basis_ast: "helper_callee_name",
    assertion_framework_context: "helper_oracle",
    assertion_library_syntax: "helper_oracle",
    assertion_framework: "helper_oracle",
  };
}

function isStandaloneCypressContainsImplicitOracle(callNode, terminal, expr) {
  if (terminal !== "contains") return false;
  if (!/^cy(?:\.|$)/.test(String(expr || ""))) return false;

  let parent = callNode.getParent();
  while (parent && (Node.isParenthesizedExpression(parent) || Node.isAwaitExpression(parent))) {
    parent = parent.getParent();
  }
  if (parent && Node.isPropertyAccessExpression(parent) && parent.getExpression() === callNode) {
    return false;
  }
  return true;
}

function implicitContainsOracleFields() {
  return {
    source_kind: "implicit_oracle",
    assertion_helper_kind_ast: "cypress_contains_existence",
    assertion_helper_detection_basis_ast: "ast_standalone_cypress_contains",
    assertion_helper_detection_confidence_ast: "medium",
    assertion_matcher: "contains",
    assertion_semantic_matcher_ast: "contains",
    assertion_semantic_matcher_basis_ast: "implicit_cypress_contains",
    assertion_subject_kind: "locator",
    assertion_subject_basis_ast: "ast_cypress_contains_call",
    assertion_framework_context: "cypress_implicit",
    assertion_library_syntax: "cypress_implicit",
    assertion_framework: "cypress",
  };
}

function pushImplicitOracleCompanion(callNode, ctx, features, terminal, expr) {
  if (!isStandaloneCypressContainsImplicitOracle(callNode, terminal, expr)) return;
  features.push(makeFeature(callNode, expr, "assertion", ctx, implicitContainsOracleFields()));
}

function isCanvasDrawingCall(callNode, terminal) {
  if (!terminal || !CANVAS_DRAWING_METHODS.has(terminal)) return false;
  const recv = getCallReceiverText(callNode).trim();
  const root = recv.split(".")[0];
  return CANVAS_RECEIVER_ROOT_RE.test(root);
}

function receiverTypeText(callNode) {
  try {
    const recv = getCallReceiverNode(callNode);
    return recv?.getType?.()?.getText?.() || "";
  } catch (_) {
    return "";
  }
}

function isNonUiTypeCall(callNode, terminal) {
  if (terminal !== "type") return false;
  const recv = getCallReceiverText(callNode).trim();
  const root = recv.split(".")[0];
  if (NON_UI_TYPE_RECEIVER_ROOT_RE.test(root)) return true;
  const typeText = receiverTypeText(callNode);
  if (!typeText || UI_TYPE_RECEIVER_TYPE_RE.test(typeText)) return false;
  return NON_UI_TYPE_RECEIVER_TYPE_RE.test(typeText);
}

function isLocatorStyleUiAction(callNode, terminal) {
  if (!terminal || !PLAYWRIGHT_LOCATOR_ACTIONS.has(terminal)) return false;
  if (isNonUiTypeCall(callNode, terminal)) return false;
  if (isCanvasDrawingCall(callNode, terminal)) return false;
  return !isArrayPrototypeDataCall(callNode, terminal);
}

function isPlaywrightWaitCall(terminal, framework) {
  if (!terminal || !PLAYWRIGHT_WAIT_METHODS.has(terminal)) return false;
  return framework === "Playwright" || framework === "Unknown";
}

function isPuppeteerWaitCall(terminal, framework) {
  if (!terminal || !PUPPETEER_WAIT_METHODS.has(terminal)) return false;
  return framework === "Puppeteer" || framework === "Unknown";
}

function classifyWaitSynchronization(callNode, terminal, framework, expr, sourceKind) {
  if (!terminal) return null;
  const recv = getCallReceiverText(callNode).trim();

  if (isPlaywrightWaitCall(terminal, framework) || isPuppeteerWaitCall(terminal, framework)) {
    return "wait_synchronization";
  }

  if (terminal === "wait") {
    if (recv === "t" || /\bt\.wait\b/.test(expr) || framework === "TestCafe") {
      return "wait_synchronization";
    }
    if (/\bcy\./.test(expr) || framework === "Cypress") {
      return "wait_synchronization";
    }
  }

  if (terminal === "waitUntil") {
    if (recv === "browser" || /^browser\b/.test(recv) || /\bbrowser\.waitUntil/.test(expr) || framework === "WebDriverIO") {
      return "wait_synchronization";
    }
    if (/\bcy\./.test(expr) || framework === "Cypress") {
      return "wait_synchronization";
    }
  }

  return null;
}

function classifyCypressControl(cmd, sourceKind) {
  if (cmd === "intercept") {
    return isHookSource(sourceKind) ? "setup" : "network_mock";
  }
  if (cmd === "fixture") {
    return "input";
  }
  if (CYPRESS_BODY_CONTROL_TYPES[cmd]) {
    return CYPRESS_BODY_CONTROL_TYPES[cmd];
  }
  if (isHookSource(sourceKind)) return "setup";
  return "control";
}

/** Detect wait/synchronization calls mis-tagged as setup (e.g. hook-attached features). */
function isWaitLikeFeatureText(rawCode, name) {
  const text = `${rawCode || ""} ${name || ""}`.toLowerCase();
  return (
    /\b(page|locator|frame|dialog)\.waitfor\w*\b/.test(text) ||
    /\blocator\.waitfor\b/.test(text) ||
    /\bcy\.wait\b/.test(text) ||
    /\bcy\.waituntil\b/.test(text) ||
    /\bt\.wait\b/.test(text) ||
    /\bbrowser\.waituntil\b/.test(text)
  );
}

function normalizeWaitFeatureType(feature) {
  if (feature?.feature_type === "setup" && isWaitLikeFeatureText(feature.raw_code, feature.name)) {
    return { ...feature, feature_type: "wait_synchronization" };
  }
  return feature;
}

function isCypressRealUi(terminal, expr) {
  if (terminal && CYPRESS_REAL_UI.has(terminal)) return true;
  return /\.(realPress|realClick|realType|realHover|realTouch)\b/.test(expr);
}

function classifyCypressCall(callNode, expr, sourceKind) {
  const terminal = getInvocationMethod(callNode);
  const recv = getCallReceiverText(callNode).trim();
  const isCyRoot = recv === "cy";

  if (terminal === "should" || terminal === "and") return "assertion";
  if (terminal === "wait" || terminal === "waitUntil") {
    return "wait_synchronization";
  }
  if (isCypressRealUi(terminal, expr)) return "ui_action";

  if (terminal && CYPRESS_TEST_UTILITY.has(terminal)) return "cypress_test_utility";
  if (terminal && CYPRESS_SUBJECT_CONTROL.has(terminal)) return "cypress_subject_control";
  if (terminal && CYPRESS_BUILTIN.has(terminal)) return "cypress_builtin";

  const m = expr.match(/\bcy\.([A-Za-z_$][\w$]*)/);
  const cmd = m ? m[1] : "";

  if (isCyRoot) {
    if (CYPRESS_TEST_UTILITY.has(cmd)) return "cypress_test_utility";
    if (CYPRESS_SUBJECT_CONTROL.has(cmd)) return "cypress_subject_control";
    if (CYPRESS_BUILTIN.has(cmd)) return "cypress_builtin";
    if (CYPRESS_BROWSER_CONTEXT.has(cmd)) {
      return isHookSource(sourceKind) ? "setup" : "browser_context_control";
    }
    if (isCypressLocatorQueryCommand(cmd)) return "ui_action";
    if (CYPRESS_CONTROL.has(cmd) || cmd === "intercept") {
      return classifyCypressControl(cmd, sourceKind);
    }
  }

  if (terminal && (CYPRESS_DIRECT_UI.has(terminal) || isCypressLocatorQueryCommand(terminal))) {
    return "ui_action";
  }

  if (CYPRESS_BROWSER_CONTEXT.has(cmd) || (terminal && CYPRESS_BROWSER_CONTEXT.has(terminal))) {
    return isHookSource(sourceKind) ? "setup" : "browser_context_control";
  }
  if (isCyRoot && (CYPRESS_CONTROL.has(cmd) || cmd === "intercept")) {
    return classifyCypressControl(cmd, sourceKind);
  }
  if (cmd === "should" || cmd === "and") return "assertion";

  if (/\bcy\./.test(expr) || (isCyRoot && cmd)) return "custom_command_call";
  return null;
}

function getCallReceiverNode(callNode) {
  try {
    const callee = callNode.getExpression();
    if (Node.isPropertyAccessExpression(callee)) {
      return callee.getExpression();
    }
  } catch (_) {
    /* ignore */
  }
  return null;
}

function getCallReceiverText(callNode) {
  const recv = getCallReceiverNode(callNode);
  return recv ? recv.getText() : "";
}

function isPlaywrightMouseCall(callNode, terminal) {
  if (!terminal || !PLAYWRIGHT_MOUSE_DRAG_METHODS.has(terminal)) return false;
  const recv = getCallReceiverText(callNode).replace(/\s+/g, "");
  return recv === "page.mouse";
}

function enclosingBlock(node) {
  let cur = node.getParent();
  while (cur) {
    if (Node.isBlock(cur) || Node.isSourceFile(cur)) return cur;
    cur = cur.getParent();
  }
  return null;
}

function statementContainsNode(stmt, node) {
  return stmt.getStart() <= node.getStart() && stmt.getEnd() >= node.getEnd();
}

function mouseDragSnippetFromStatements(statements, currentIndex) {
  const startIndex = Math.max(0, currentIndex - 4);
  return statements
    .slice(startIndex, currentIndex + 1)
    .map((stmt) => stmt.getText())
    .join("\n")
    .slice(0, 400);
}

function extractPlaywrightMouseDragFields(callNode, terminal) {
  if (!isPlaywrightMouseCall(callNode, terminal) || terminal !== "up") return null;
  const block = enclosingBlock(callNode);
  if (!block || typeof block.getStatements !== "function") return null;
  const statements = block.getStatements();
  const currentIndex = statements.findIndex((stmt) => statementContainsNode(stmt, callNode));
  if (currentIndex < 0) return null;

  let sawDown = false;
  let sawMoveAfterDown = false;
  for (let idx = Math.max(0, currentIndex - 12); idx < currentIndex; idx += 1) {
    for (const priorCall of statements[idx].getDescendantsOfKind(SyntaxKind.CallExpression)) {
      const priorTerminal = getInvocationMethod(priorCall);
      if (!isPlaywrightMouseCall(priorCall, priorTerminal)) continue;
      if (priorTerminal === "down") {
        sawDown = true;
        sawMoveAfterDown = false;
      } else if (priorTerminal === "move" && sawDown) {
        sawMoveAfterDown = true;
      }
    }
  }
  if (!sawDown || !sawMoveAfterDown) return null;
  return {
    name: "page.mouse.drag",
    raw_code: mouseDragSnippetFromStatements(statements, currentIndex) || getRawSnippet(callNode, 400),
    terminal_action_ast: "drag",
    ui_action_category: "drag_drop",
    ui_action_evidence_basis_ast: "ast_playwright_mouse_down_move_up_sequence",
    action_signature_terminal_ast: "drag",
    action_signature_expr: "page.mouse.drag",
  };
}

function callbackArgForEvaluate(callNode, terminal) {
  if (terminal !== "evaluate") return null;
  const firstArg = callNode.getArguments()[0];
  if (!firstArg) return null;
  if (Node.isArrowFunction(firstArg) || Node.isFunctionExpression(firstArg)) return firstArg;
  return null;
}

function isScrollPropertyWrite(node) {
  if (!Node.isBinaryExpression(node)) return false;
  const op = node.getOperatorToken().getText();
  if (!["=", "+=", "-="].includes(op)) return false;
  const left = node.getLeft();
  return Node.isPropertyAccessExpression(left) && SCROLL_MUTATION_PROPERTIES.has(left.getName());
}

function isScrollCall(node) {
  if (!Node.isCallExpression(node)) return false;
  const expr = node.getExpression();
  return Node.isPropertyAccessExpression(expr) && SCROLL_CALL_METHODS.has(expr.getName());
}

function evaluateCallbackMutatesScroll(callbackNode) {
  let found = false;
  if (isScrollPropertyWrite(callbackNode) || isScrollCall(callbackNode)) return true;
  callbackNode.forEachDescendant((desc) => {
    if (found) return false;
    if (isScrollPropertyWrite(desc) || isScrollCall(desc)) {
      found = true;
      return false;
    }
    return undefined;
  });
  return found;
}

function extractEvaluateScrollFields(callNode, terminal, expr) {
  const callbackNode = callbackArgForEvaluate(callNode, terminal);
  if (!callbackNode || !evaluateCallbackMutatesScroll(callbackNode)) return null;
  return {
    name: `${expr}.scroll`,
    terminal_action_ast: "scroll",
    ui_action_category: "scroll",
    ui_action_evidence_basis_ast: "ast_evaluate_scroll_mutation",
    action_signature_terminal_ast: "scroll",
    action_signature_expr: `${expr}.scroll`,
  };
}

/** `Array(10).fill(0)` / `new Array(n).fill(x)` — JS data, not locator/page fill. */
function isJsArrayDataReceiver(exprNode) {
  if (!exprNode) return false;
  if (Node.isNewExpression(exprNode)) {
    const ex = exprNode.getExpression();
    return Node.isIdentifier(ex) && ex.getText() === "Array";
  }
  if (Node.isCallExpression(exprNode)) {
    const ex = exprNode.getExpression();
    return Node.isIdentifier(ex) && ex.getText() === "Array";
  }
  if (Node.isParenthesizedExpression(exprNode)) {
    return isJsArrayDataReceiver(exprNode.getExpression());
  }
  if (Node.isPropertyAccessExpression(exprNode) && exprNode.getName() === "fill") {
    return isJsArrayDataReceiver(exprNode.getExpression());
  }
  return false;
}

function isArrayPrototypeDataCall(callNode, terminal) {
  if (terminal !== "fill") return false;
  return isJsArrayDataReceiver(getCallReceiverNode(callNode));
}

function valueArgIndexForTextEntry(callNode, method) {
  if (method === "setInputFiles" || method === "setFilesToUpload" || method === "selectFile") {
    return resolveUploadValueArgIndex(callNode, method);
  }
  return resolveTextEntryValueArgIndex(callNode, method);
}

function isAssertionMatcherValue(rawValue) {
  const v = (rawValue || "").trim().replace(/^['"`]|['"`]$/g, "");
  if (!v) return false;
  if (CYPRESS_ASSERT_MATCHER_VALUES.has(v)) return true;
  if (/^(have|be|not|contain|include)\.[a-z][\w.]*/i.test(v)) return true;
  if (/^to(Have|Be|Contain|Equal|Match)/.test(v)) return true;
  return false;
}

/** Block misclassified input rows whose expression is assertion/chaining, not data entry. */
function exprLooksLikeAssertionInput(expr) {
  if (!expr) return false;
  if (isAssertionExpr(expr)) return true;
  if (/\bcy\.(should|and)\s*\(\s*['"`]/.test(expr)) return true;
  if (/\bexpect\s*\([^)]*\)\s*\.\s*to(Have|Be|Contain)/.test(expr)) return true;
  if (/(?:fill|type|setValue|addValue|press)\s*\(\s*['"`](?:have\.|be\.|contain\.|include\.|not\.)/i.test(expr)) {
    return true;
  }
  return false;
}

/** Resolve text-entry only from the current CallExpression callee method (not chain text). */
function resolveTextEntryMethod(callNode, terminal) {
  if (!terminal || !TEXT_ENTRY_METHODS.has(terminal)) return null;
  if (isNonUiTypeCall(callNode, terminal)) return null;
  if (isArrayPrototypeDataCall(callNode, terminal)) return null;
  return {
    method: terminal,
    valueArgIndex: valueArgIndexForTextEntry(callNode, terminal),
  };
}

function shouldEmitTextEntryCompanion(primaryType, terminal) {
  if (!primaryType || primaryType === "input" || primaryType === "assertion") return false;
  return TEXT_ENTRY_METHODS.has(terminal);
}

function classifyPlaywrightControl(expr, sourceKind) {
  if (/\bpage\.(?:route|unroute)\b/.test(expr)) {
    return isHookSource(sourceKind) ? "setup" : "network_mock";
  }
  if (/\bpage\.context\b/.test(expr)) {
    return isHookSource(sourceKind) ? "setup" : "browser_context_control";
  }
  if (/\btest\.step\b/.test(expr)) return "test_step";
  return null;
}

function isNonCypressRequestCall(callNode, terminal, expr, framework) {
  const recv = getCallReceiverText(callNode).replace(/\s+/g, "");
  const cmd = String(terminal || "").toLowerCase();
  if (cmd === "fetch" || /^fetch\s*\(/.test(expr)) return true;
  if (!API_REQUEST_METHODS.has(cmd)) return false;
  if (recv === "request" || recv === "page.request" || /request$/i.test(recv)) return true;
  return framework === "Playwright" && recv === "request";
}

function classifyCall(callNode, expr, framework, contexts, sourceKind) {
  const terminal = getInvocationMethod(callNode);

  if (/\btest\.step\b/.test(expr)) return "test_step";

  const pwControl = classifyPlaywrightControl(expr, sourceKind);
  if (pwControl) return pwControl;

  const waitType = classifyWaitSynchronization(callNode, terminal, framework, expr, sourceKind);
  if (waitType) return waitType;

  if (framework === "Cypress" || /\bcy\./.test(expr)) {
    const cypressType = classifyCypressCall(callNode, expr, sourceKind);
    if (cypressType) return cypressType;
  }

  if (isAssertionExpr(expr)) return "assertion";

  if (isArrayPrototypeDataCall(callNode, terminal)) return null;

  if (isNonCypressRequestCall(callNode, terminal, expr, framework)) return "setup";

  if (
    isLocatorStyleUiAction(callNode, terminal) &&
    !/^expect\s*\(/.test(expr) &&
    !(/\.toBe|\.toHave|\.toContain/.test(expr) && /expect/.test(expr)) &&
    (framework === "Playwright" || framework === "Puppeteer" || framework === "Unknown")
  ) {
    return "ui_action";
  }

  for (const [fw, patterns] of Object.entries(UI_ACTION_PATTERNS)) {
    if (framework !== "Unknown" && fw !== framework) continue;
    if (fw === "WebDriverIO" && !isWebDriverIOContext(contexts) && /\$\s*\(/.test(expr)) continue;
    if (exprMatchesAny(expr, patterns)) return "ui_action";
  }

  if (isHookSource(sourceKind)) {
    for (const patterns of Object.values(SETUP_PATTERNS)) {
      if (exprMatchesAny(expr, patterns)) return "setup";
    }
  }

  if (exprMatchesAny(expr, INPUT_PATTERNS) && !exprLooksLikeAssertionInput(expr)) return "input";

  if (/^new\s+[A-Z][A-Za-z0-9_]*(?:Page|Screen|Component|PO)\b/.test(expr)) return "page_object_ctor";

  return null;
}

function isWebDriverIOContext(contexts) {
  return (contexts || []).some((c) => /webdriverio|wdio/i.test(c));
}

const FRAMEWORK_PAGE_NATIVE = new Set([
  "goto", "locator", "getbyrole", "getbytext", "getbylabel", "getbyplaceholder",
  "getbytestid", "context", "newpage", "close", "waitforevent",
]);

function isFrameworkPageNativeMethod(method) {
  const m = (method || "").toLowerCase();
  return FRAMEWORK_PAGE_NATIVE.has(m) || m.startsWith("getby") || m.startsWith("findby");
}

/** POM-like lower-camel roots (loginPage), not bare userPage.getByRole */
function isLikelyPageObjectInstance(root, fullName) {
  if (!/^[a-z][a-zA-Z0-9]*(?:Page|Screen|PO|PageObject)$/.test(root || "")) return false;
  const parts = (fullName || root).split(".");
  if (parts.length >= 3) return true;
  if (parts.length === 2 && !isFrameworkPageNativeMethod(parts[1])) return true;
  return false;
}

function isFrameworkUtilityRoot(root) {
  return /^(page|cy|browser|t|locator|frame|expect|assert|console|test|describe|it)$/.test(root || "");
}

function isHelperLikeCalleeName(root, fullExpr) {
  if (!root || isFrameworkUtilityRoot(root)) return false;
  if (isLikelyPageObjectInstance(root, fullExpr || root)) return true;
  if (/^[A-Z]/.test(root) && /(Page|Screen|Helper|Utils?|Util|Steps|Actions|Flow|Support|Fixture|PO)$/.test(root)) {
    return true;
  }
  if (/^(_|use)[A-Za-z]/.test(root) && root.length > 3) return true;
  if (/^[a-z][a-zA-Z0-9]{2,}(User|Admin|Account|Session|Auth|Login|Logout|Setup|Teardown)$/.test(root)) {
    return true;
  }
  return false;
}

function isHelperLikeImportSpec(spec) {
  if (!spec || typeof spec !== "string") return false;
  return /(?:^|\/)(?:helpers?|support|commands|steps|actions|flows|fixtures|utils?|page-objects?|pages)(?:\/|$)/i.test(
    spec
  );
}

function isLocalImportSpec(spec) {
  return Boolean(spec && (spec.startsWith(".") || spec.startsWith("~/") || spec.startsWith("@/")));
}

function isLikelyHelperCall(name, expr, importMap) {
  if (!name || HELPER_CALL_BLOCKLIST.has(name)) return false;
  if (/^(page|cy|browser|t|locator|frame|expect|assert|console)$/.test(name)) return false;
  if (/^(describe|it|test|before|after|beforeEach|afterEach)$/.test(name)) return false;
  if (/^(then|catch|finally|map|filter|forEach|reduce|find|some|every)$/.test(name)) return false;
  if (/^to[A-Z]/.test(name)) return false;

  const root = name.split(".")[0];
  if (isHelperLikeCalleeName(root, name)) return true;

  if (importMap && importMap.has(root)) {
    const entry = importMap.get(root);
    const spec = entry && typeof entry === "object" ? entry.spec : entry;
    if (isFrameworkUtilityRoot(root)) return false;
    if (isLocalImportSpec(spec) && (isHelperLikeCalleeName(root, name) || isHelperLikeImportSpec(spec))) {
      return true;
    }
  }

  return false;
}

function isLikelyDirectHelperCall(name, expr, importMap) {
  if (!isLikelyHelperCall(name, expr, importMap)) return false;
  const root = name.split(".")[0];
  if (isHelperLikeCalleeName(root, name)) return true;
  if (importMap && importMap.has(root)) {
    const entry = importMap.get(root);
    const spec = entry && typeof entry === "object" ? entry.spec : entry;
    if (isLocalImportSpec(spec) && (isHelperLikeCalleeName(root, name) || isHelperLikeImportSpec(spec))) {
      return true;
    }
  }
  return false;
}

function clippedTextFromNode(node, maxLen = 1500) {
  if (!node) return { text: "", truncated: false };
  try {
    const text = node.getText();
    if (text.length <= maxLen) return { text, truncated: false };
    return { text: text.slice(0, maxLen), truncated: true };
  } catch (_) {
    return { text: "", truncated: false };
  }
}

function findCallbackOwningCall(fnNode) {
  if (!fnNode) return null;
  let p = fnNode.getParent();
  while (p) {
    if (Node.isCallExpression(p)) {
      try {
        if (p.getArguments().includes(fnNode)) return p;
      } catch (_) {
        return null;
      }
    }
    if (Node.isBlock(p) || Node.isSourceFile(p)) return null;
    p = p.getParent();
  }
  return null;
}

function enclosingFunctionOrCallbackNode(callNode) {
  if (!callNode) return null;
  let p = callNode;
  while (p) {
    if (Node.isArrowFunction(p) || Node.isFunctionExpression(p)) {
      const owningCall = findCallbackOwningCall(p);
      if (owningCall) return owningCall;
      const body = p.getBody();
      return Node.isBlock(body) ? body : p;
    }
    if (Node.isFunctionDeclaration(p)) {
      return p.getBody() || p;
    }
    p = p.getParent();
  }
  return findEnclosingFunctionBody(callNode);
}

function controlFlowSource(ctx, fields) {
  const enclosure = String(fields.control_flow_enclosure || "");
  if (!enclosure || enclosure === "none") return "none";
  const helperDepth = ctx.helper_depth || 0;
  if (helperDepth > 0) {
    const initial = ctx.initialCfStack || {};
    const baseLoop = initial.loopDepth || 0;
    const baseBranch = initial.branchDepth || 0;
    const loopDepth = Number(fields.control_flow_loop_depth || 0);
    const branchDepth = Number(fields.control_flow_branch_depth || 0);
    if ((baseLoop || baseBranch) && loopDepth <= baseLoop && branchDepth <= baseBranch) {
      return "caller_context";
    }
    if (baseLoop || baseBranch) return "helper_body_with_caller_context";
    return "helper_body";
  }
  if (ctx.is_shared_hook_feature || isHookSource(ctx.source_kind)) return "hook_or_fixture";
  return "test_body";
}

const SETUP_TEARDOWN_FEATURE_TYPES = new Set([
  "setup",
  "teardown",
  "browser_context_control",
  "network_mock",
  "time_control",
  "control",
  "helper_call",
  "custom_command_call",
  "cypress_test_utility",
  "page_object_ctor",
  "input",
  "ui_action",
]);

function attachMilestone3Fields(node, featureType, ctx, extra, terminal, expr, fieldContext = {}) {
  if (featureType === "ui_action") {
    const cfFields = snapshotControlFlowEnclosure(ctx.cfStack, node);
    Object.assign(extra, cfFields);
    const actionSnippet = clippedTextFromNode(node, 1500);
    const functionSnippet = clippedTextFromNode(enclosingFunctionOrCallbackNode(node), 1500);
    const contextSnippet = clippedTextFromNode(ctx.context_node || findEnclosingFunctionBody(node), 1500);
    extra.action_snippet = actionSnippet.text;
    extra.enclosing_function_or_callback_snippet = functionSnippet.text;
    extra.test_body_or_helper_context_snippet = contextSnippet.text;
    extra.control_flow_source = controlFlowSource(ctx, cfFields);
    extra.snippet_truncated = Boolean(
      actionSnippet.truncated ||
        functionSnippet.truncated ||
        contextSnippet.truncated ||
        cfFields.enclosing_control_flow_snippet_truncated
    );
    const category = fieldContext.ui_action_category || inferUiActionCategory(terminal, expr);
    extra.ui_action_category = category;
    extra.action_signature_json = buildActionSignatureJson({
      category,
      callNode: node,
      terminalAction:
        fieldContext.action_signature_terminal_ast ||
        fieldContext.terminal_action_ast ||
        extra.terminal_action_ast ||
        terminal,
      locatorStrategy: fieldContext.locator_strategy_ast || extra.locator_strategy_ast || "",
      inputChannel: fieldContext.input_channel_ast || extra.input_channel_ast || "",
      navigationTarget: fieldContext.navigation_target_ast || extra.navigation_target_ast || "",
      sourceKind: ctx.source_kind,
      helperDepth: ctx.helper_depth || 0,
    });
    if (category === "navigation" && extra.navigation_target_ast) {
      extra.navigation_target = extra.navigation_target_ast;
      extra.navigation_target_evidence_basis = "string_literal_arg_ast";
    }
  }

  if (featureType === "assertion") {
    Object.assign(extra, extractAssertionChainFields(node, ctx.file_path, ctx.framework) || {});
  }

  if (SETUP_TEARDOWN_FEATURE_TYPES.has(featureType)) {
    Object.assign(
      extra,
      attachSetupTeardownPatternFields(node, featureType, ctx.source_kind, ctx.framework)
    );
  }
}

function walkNodeForFeatures(node, ctx, features, cfStack) {
  if (!node) return;
  cfStack =
    cfStack ||
    (ctx.initialCfStack ? cloneControlFlowStack(ctx.initialCfStack) : createControlFlowStack());
  ctx.cfStack = cfStack;
  enterControlFlowNode(cfStack, node);

  try {
    if (Node.isCallExpression(node)) {
      let expr = "";
      try {
        expr = node.getExpression().getText();
      } catch (_) {
        return;
      }
      const terminal = getInvocationMethod(node);
      const helperOracle = helperOracleFields(node, terminal, expr);
      const featureType =
        classifyCall(node, expr, ctx.framework, ctx.contexts, ctx.source_kind) ||
        (helperOracle ? "assertion" : null);
      const syntheticUiActionFields =
        extractPlaywrightMouseDragFields(node, terminal) ||
        extractEvaluateScrollFields(node, terminal, expr);
      if (featureType) {
        const astFields = attachAstPatternFields(
          node,
          featureType,
          ctx.framework,
          ctx.importMap,
          ctx.astCtx
        );
        const inputFields = attachInputPatternFields(node, featureType, node, terminal);
        const semanticFields =
          featureType === "ui_action"
            ? syntheticUiActionFields || {}
            : featureType === "assertion" && helperOracle
              ? helperOracle
              : {};
        const effectiveTerminal = semanticFields.terminal_action_ast || terminal;
        const effectiveExpr = semanticFields.action_signature_expr || expr;
        const m3Fields = {};
        attachMilestone3Fields(node, featureType, ctx, m3Fields, effectiveTerminal, effectiveExpr, {
          ...astFields,
          ...inputFields,
          ...semanticFields,
        });
        features.push(
          normalizeWaitFeatureType(
            makeFeature(node, semanticFields.name || expr, featureType, ctx, {
              ...astFields,
              ...inputFields,
              ...m3Fields,
              ...semanticFields,
            })
          )
        );
        const inputMeta = extractTextEntryInputFacts(node, terminal);
        if (inputMeta && shouldEmitTextEntryCompanion(featureType, terminal)) {
          const inputFeat = makeInputFeature(node, expr, ctx, inputMeta);
          if (inputFeat) features.push(inputFeat);
        }
        if (featureType === "ui_action") {
          pushImplicitOracleCompanion(node, ctx, features, terminal, expr);
        }
      } else if (syntheticUiActionFields || isLocatorStyleUiAction(node, terminal)) {
        const astFields = attachAstPatternFields(
          node,
          "ui_action",
          ctx.framework,
          ctx.importMap,
          ctx.astCtx
        );
        const inputFields = attachInputPatternFields(node, "ui_action", node, terminal);
        const semanticFields = syntheticUiActionFields || {};
        const effectiveTerminal = semanticFields.terminal_action_ast || terminal;
        const effectiveExpr = semanticFields.action_signature_expr || expr;
        const m3Fields = {};
        attachMilestone3Fields(node, "ui_action", ctx, m3Fields, effectiveTerminal, effectiveExpr, {
          ...astFields,
          ...inputFields,
          ...semanticFields,
        });
        features.push(
          normalizeWaitFeatureType(
            makeFeature(node, semanticFields.name || expr, "ui_action", ctx, {
              ...astFields,
              ...inputFields,
              ...m3Fields,
              ...semanticFields,
            })
          )
        );
        const inputMeta = extractTextEntryInputFacts(node, terminal);
        if (inputMeta && shouldEmitTextEntryCompanion("ui_action", terminal)) {
          const inputFeat = makeInputFeature(node, expr, ctx, inputMeta);
          if (inputFeat) features.push(inputFeat);
        }
        pushImplicitOracleCompanion(node, ctx, features, terminal, expr);
      } else {
        const name = node.getExpression().getText();
        const root = name.split(".")[0];
        if (isLikelyDirectHelperCall(root, expr, ctx.importMap)) {
          const astFields = attachAstPatternFields(
            node,
            "helper_call",
            ctx.framework,
            ctx.importMap,
            ctx.astCtx
          );
          features.push(
            normalizeWaitFeatureType(
              makeFeature(node, expr, "helper_call", ctx, {
                ...astFields,
                ...(function () {
                  const m3 = {};
                  attachMilestone3Fields(node, "helper_call", ctx, m3, terminal, expr);
                  return m3;
                })(),
              })
            )
          );
        }
      }
    }

    forEachChildRespectingCallbackIteration(node, cfStack, (child) =>
      walkNodeForFeatures(child, ctx, features, cfStack)
    );
  } finally {
    exitControlFlowNode(cfStack, node);
  }
}

function makeFeature(node, name, featureType, ctx, extra = {}) {
  return {
    repo: ctx.repo,
    test_id: ctx.test_id,
    file_path: ctx.file_path,
    phase1_confidence: ctx.phase1_confidence,
    feature_type: featureType,
    source_kind: ctx.source_kind,
    framework: ctx.framework,
    name: name.slice(0, 200),
    raw_code: getRawSnippet(node, 400),
    line: node.getStartLineNumber(),
    source_start_offset: node.getStart(),
    source_end_offset: node.getEnd(),
    confidence: "high",
    hook_instance_key: ctx.hook_instance_key || "",
    hook_owner_kind: ctx.hook_owner_kind || "",
    is_shared_hook_feature: Boolean(ctx.is_shared_hook_feature),
    input_source: "",
    raw_value: "",
    value_summary: "",
    linked_action_line: null,
    ...extra,
  };
}

function makeInputFeature(node, actionExpr, ctx, inputMeta) {
  if (
    isAssertionMatcherValue(inputMeta.raw_value) ||
    isAssertionMatcherValue(inputMeta.value_summary) ||
    exprLooksLikeAssertionInput(actionExpr)
  ) {
    return null;
  }
  const line = node.getStartLineNumber();
  const label = `input:${inputMeta.method}:${inputMeta.value_summary || inputMeta.input_source}`;
  return makeFeature(node, label, "input", ctx, {
    name: label.slice(0, 200),
    input_source: inputMeta.input_source,
    raw_value: inputMeta.raw_value,
    value_summary: inputMeta.value_summary,
    linked_action_line: line,
    raw_code: getRawSnippet(node, 400),
    input_source_ast: inputMeta.input_source_ast || inputMeta.input_source || "",
    input_value_kind_ast: inputMeta.input_value_kind_ast || "",
    input_value_redacted: inputMeta.input_value_redacted || inputMeta.value_summary || "",
    input_channel_ast: inputMeta.input_channel_ast || "",
    field_context_ast: inputMeta.field_context_ast || "",
    field_context_basis_ast: inputMeta.field_context_basis_ast || "",
    input_target_role_ast: inputMeta.input_target_role_ast || "",
    input_target_role_basis_ast: inputMeta.input_target_role_basis_ast || "",
    input_target_context_ast: inputMeta.input_target_context_ast || "",
    input_target_context_normalized_ast: inputMeta.input_target_context_normalized_ast || "",
    input_target_context_basis_ast: inputMeta.input_target_context_basis_ast || "",
    input_value_expression_kind_ast: inputMeta.input_value_expression_kind_ast || "",
    input_endpoint_construction_ast: inputMeta.input_endpoint_construction_ast || "",
    input_endpoint_construction_basis_ast: inputMeta.input_endpoint_construction_basis_ast || "",
    input_value_start_offset_ast: inputMeta.input_value_start_offset_ast || "",
    input_value_end_offset_ast: inputMeta.input_value_end_offset_ast || "",
    input_origin_kind_ast: inputMeta.input_origin_kind_ast || "",
    input_origin_confidence_ast: inputMeta.input_origin_confidence_ast || "",
    input_provenance_ast: inputMeta.input_provenance_ast || "",
    input_provenance_family_ast: inputMeta.input_provenance_family_ast || "",
    input_provenance_confidence: inputMeta.input_provenance_confidence || "",
    input_provenance_components_json: inputMeta.input_provenance_components_json || "",
    value_visibility_ast: inputMeta.value_visibility_ast || "",
    input_evidence_basis_ast: inputMeta.input_evidence_basis_ast || "missing_input_evidence_basis",
    input_source_confidence_ast: inputMeta.input_source_confidence_ast || "",
  });
}

function findTestBodyNode(sourceFile, testCase) {
  const declLine = testCase.declaration_line;
  if (declLine) {
    for (const call of sourceFile.getDescendantsOfKind(SyntaxKind.CallExpression)) {
      if (call.getStartLineNumber() !== declLine) continue;
      const cb = getCallbackArgFromCall(call);
      if (cb) return cb;
    }
  }

  const start = testCase.callback_start_line ?? testCase.start_line;
  const end = testCase.callback_end_line ?? testCase.end_line;
  let best = null;
  let bestDist = Infinity;

  for (const fn of sourceFile.getDescendants()) {
    if (!Node.isArrowFunction(fn) && !Node.isFunctionExpression(fn)) continue;
    const fnStart = fn.getStartLineNumber();
    const fnEnd = fn.getEndLineNumber();
    if (fnStart === start) return fn;
    if (fnStart >= start && fnEnd <= end) {
      const dist = Math.abs(fnStart - start);
      if (dist < bestDist) {
        bestDist = dist;
        best = fn;
      }
    }
  }
  return best;
}

function extractDirectFeatures(sourceFile, testCases, manifestRow, repoMeta) {
  const imports = getImportModules(sourceFile);
  const { primary: framework, contexts } = resolveFrameworkForFile(manifestRow, imports);
  const { testNames, groupNames } = collectTestLikeIdentifiers(sourceFile);
  const hooks = collectHooks(sourceFile, testNames, groupNames);
  const importMap = buildImportMap(sourceFile);
  const allFeatures = [];

  const fileTests = testCases.filter((t) => t.file_path === manifestRow.file_path);
  const hookFeatureCache = new Map();
  const pageSymbolOrigins = buildPageSymbolOrigins(sourceFile);

  for (const testCase of fileTests) {
    const callbackFixtureNames = Array.isArray(testCase.fixtures_used)
      ? testCase.fixtures_used
      : String(testCase.fixtures_used || "")
          .split(";")
          .map((s) => s.trim())
          .filter(Boolean);
    const fixtureProvenanceMap = buildPlaywrightFixtureProvenanceMap(
      sourceFile,
      callbackFixtureNames
    );
    const astCtx = { fixtureProvenanceMap, pageSymbolOrigins };
    const applicableHooks = hooksForTestCase(hooks, testCase);
    const hookKeys = new Set(testCase.hook_instance_keys || []);
    for (const h of applicableHooks) {
      hookKeys.add(h.hook_instance_key);
    }
    testCase.hook_instance_keys = [...hookKeys];

    const testBody = findTestBodyNode(sourceFile, testCase);

    const ctxBase = {
      repo: repoMeta.repo,
      test_id: testCase.test_id,
      file_path: testCase.file_path,
      phase1_confidence: testCase.phase1_confidence,
      framework,
      contexts,
      importMap,
      astCtx,
    };

    const testFeats = [];
    if (testBody) {
      const ctx = { ...ctxBase, source_kind: "test_body", context_node: testBody };
      walkNodeForFeatures(testBody, ctx, testFeats);
      allFeatures.push(...testFeats);
    }

    for (const hook of applicableHooks) {
      if (!hook.callback) continue;
      if (!hookFeatureCache.has(hook.hook_instance_key)) {
        const ctx = {
          ...ctxBase,
          test_id: "",
          source_kind: hook.source_kind,
          hook_instance_key: hook.hook_instance_key,
          hook_owner_kind: hook.hook_owner_kind || "",
          is_shared_hook_feature: true,
          context_node: hook.callback,
          astCtx: { fixtureProvenanceMap: buildPlaywrightFixtureProvenanceMap(sourceFile, []), pageSymbolOrigins },
        };
        const cached = [];
        walkNodeForFeatures(hook.callback, ctx, cached);
        hookFeatureCache.set(hook.hook_instance_key, cached);
      }
      const hookFeats = hookFeatureCache.get(hook.hook_instance_key) || [];
      testFeats.push(...hookFeats);
    }

    const hookUi = testFeats.some((f) => f.is_shared_hook_feature && f.feature_type === "ui_action");
    const bodyUi = testFeats.some((f) => !f.is_shared_hook_feature && f.feature_type === "ui_action");
    const bodyAssert = testFeats.some(
      (f) => !f.is_shared_hook_feature && f.feature_type === "assertion"
    );
    testCase.has_direct_ui_actions = bodyUi;
    testCase.has_direct_assertions = bodyAssert;
    testCase.has_hook_ui_actions = hookUi;
    testCase.has_helper_expanded_ui_actions = false;
    testCase.has_expanded_ui_actions = hookUi;
    testCase.extraction_empty =
      testCase.phase1_confidence === "medium" && !bodyUi && !bodyAssert;
  }

  for (const feats of hookFeatureCache.values()) {
    allFeatures.push(...feats);
  }

  return allFeatures;
}

module.exports = {
  extractDirectFeatures,
  classifyCall,
  classifyCypressCall,
  walkNodeForFeatures,
  isLikelyHelperCall,
  getInvocationMethod,
  isLocatorStyleUiAction,
  resolveTextEntryMethod,
  normalizeWaitFeatureType,
  isWaitLikeFeatureText,
};
