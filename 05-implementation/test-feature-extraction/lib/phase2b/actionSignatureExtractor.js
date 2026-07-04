"use strict";

/**
 * RQ4 action_signature_json v2 (Milestone 3).
 * Structured signature for sequence repetition metrics.
 */

const { Node } = require("ts-morph");
const { getCallName, getOutermostCall } = require("./astPatternExtractor");

const NAV_METHODS = new Set([
  "goto", "visit", "url", "navigateTo", "navigate", "open", "loadUrl",
]);

function firstStringLiteralArg(call) {
  if (!call || !Node.isCallExpression(call)) return "";
  for (const arg of call.getArguments()) {
    if (Node.isStringLiteral(arg) || Node.isNoSubstitutionTemplateLiteral(arg)) {
      return arg.getLiteralText();
    }
  }
  return "";
}

function extractNavigationTargetAst(call, terminal) {
  const t = (terminal || getCallName(call) || "").toLowerCase();
  if (!NAV_METHODS.has(t)) return "";
  return firstStringLiteralArg(call);
}

function inferUiActionCategory(terminal, rawCode) {
  const t = (terminal || "").toLowerCase();
  if (NAV_METHODS.has(t)) return "navigation";
  if (["click", "dblclick", "tap", "check", "uncheck"].includes(t)) return "click";
  if (["fill", "type", "setvalue", "addvalue", "typetext", "clear"].includes(t)) {
    return "text_input";
  }
  if (["press", "keyboard", "keydown", "keyup"].includes(t)) return "keyboard_input";
  if (["hover", "moveto"].includes(t)) return "hover";
  if (["select", "selectoption"].includes(t)) return "selection";
  if (["drag", "dragto", "draganddrop"].includes(t)) return "drag_drop";
  if (["setinputfiles", "uploadfile", "selectfile"].includes(t)) return "file_upload";
  if (["scroll", "scrollintoview", "scrollto", "scrollby"].includes(t)) return "scroll";
  if (["wait", "waitfor", "waituntil", "waitfortimeout", "waitforselector"].includes(t)) {
    return "wait_synchronization";
  }
  if (["screenshot", "snapshot"].includes(t)) return "visual_action";
  if (["get", "locator", "getbyrole", "getbytext", "contains", "find", "queryselector"].includes(t)) {
    return "locator_query";
  }
  return "unknown_action";
}

function resolveSourceLayer(sourceKind, helperDepth) {
  if ((helperDepth || 0) > 0) return "helper_expanded";
  if (sourceKind === "test_body") return "test_body";
  if (/before|after|hook|fixture/i.test(sourceKind || "")) return "hook_or_fixture";
  return sourceKind || "unknown";
}

function buildActionSignatureJson({
  category,
  callNode,
  terminalAction,
  locatorStrategy,
  inputChannel,
  navigationTarget,
  sourceKind,
  helperDepth,
}) {
  const call = callNode ? getOutermostCall(callNode) : null;
  const terminal = terminalAction || (call ? getCallName(call) : "");
  let navTarget = navigationTarget || "";
  if (!navTarget && call && (category || "").toLowerCase() === "navigation") {
    navTarget = extractNavigationTargetAst(call, terminal);
  }

  const payload = {
    v: 2,
    category: (category || "unknown_action").toLowerCase(),
    terminal_action: terminal || "",
    locator_strategy: locatorStrategy || "",
    input_channel: inputChannel || "",
    navigation_target: navTarget || "",
    source_layer: resolveSourceLayer(sourceKind, helperDepth),
  };

  return JSON.stringify(payload);
}

module.exports = {
  buildActionSignatureJson,
  extractNavigationTargetAst,
  resolveSourceLayer,
  inferUiActionCategory,
};
