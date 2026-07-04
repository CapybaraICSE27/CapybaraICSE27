"use strict";

const { Node } = require("ts-morph");

const NON_HELPER_CHAIN_METHODS = new Set([
  "first",
  "last",
  "eq",
  "find",
  "filter",
  "contains",
  "focus",
  "blur",
  "parent",
  "children",
  "closest",
  "next",
  "prev",
  "callsFake",
  "returns",
  "resolves",
  "rejects",
  "tag",
  "cls",
  "tab",
  "each",
  "its",
  "as",
  "then",
  "within",
  "root",
  "spread",
  "and",
  "should",
  "click",
  "type",
  "fill",
  "clear",
  "trigger",
  "scrollIntoView",
  "scrollTo",
  "wait",
  "map",
  "invoke",
  "wrap",
  "request",
]);

/** Property / matcher / collection accessors — not custom helpers. */
const NON_HELPER_PROPERTY_CALLS = new Set([
  "value",
  "not",
  "parents",
  "parent",
  "siblings",
  "text",
  "html",
  "attr",
  "data",
  "prop",
  "props",
  "state",
  "style",
  "class",
  "classes",
  "exist",
  "visible",
  "hidden",
  "length",
  "width",
  "height",
  "offset",
  "offsetParent",
  "get",
  "set",
  "has",
  "add",
  "remove",
  "toggle",
  "keys",
  "values",
  "entries",
  "at",
  "nth",
  "eq",
]);

const CANVAS_RECEIVER_ROOT_RE =
  /^(ctx|context|canvasContext|canvas|gl|gfx|graphics|renderingContext|chartCtx|chartContext)$/i;

const PAGE_OBJECT_UI_METHODS = new Set([
  "goto",
  "click",
  "fill",
  "type",
  "press",
  "focus",
  "blur",
  "hover",
  "check",
  "uncheck",
  "selectOption",
  "dblclick",
  "tap",
  "clear",
  "setChecked",
  "isVisible",
  "count",
]);

function receiverRoot(exprText) {
  const t = String(exprText || "").trim();
  const dot = t.indexOf(".");
  return dot === -1 ? t : t.slice(0, dot);
}

function isFrameworkChainOrUtilityCall(callInfo) {
  const { name, exprText, isMethod } = callInfo;
  if (!name || !isMethod || !NON_HELPER_CHAIN_METHODS.has(name)) return false;

  const root = receiverRoot(exprText);
  if (CANVAS_RECEIVER_ROOT_RE.test(root)) {
    return true;
  }
  if (/^(cy|page|browser|t|locator|frame|dialog|expect|sinon|sandbox|stub|spy|chai)$/i.test(root)) {
    return true;
  }
  if (/\)\s*\.\s*(?:first|last|eq|find|filter|contains|focus|blur|parent|children|closest)\b/.test(exprText)) {
    return true;
  }
  if (/^(cy|page|locator|browser)\./.test(exprText) && NON_HELPER_CHAIN_METHODS.has(name)) {
    return true;
  }
  return false;
}

function isPageObjectBuiltinUiCall(callInfo) {
  const { name, exprText, isMethod } = callInfo;
  if (!name || !isMethod || !PAGE_OBJECT_UI_METHODS.has(name)) return false;
  const root = receiverRoot(exprText);
  return /(?:Page|Screen|PO|Helper)$/i.test(root);
}

function callInfoFromItem(item, callExpr) {
  let exprText = item.callName;
  let isMethod = false;
  try {
    if (callExpr && Node.isCallExpression(callExpr)) {
      const ex = callExpr.getExpression();
      isMethod = Node.isPropertyAccessExpression(ex);
      exprText = ex.getText();
    }
  } catch (_) {
    /* ignore */
  }
  return { name: item.callName, exprText, isMethod };
}

function shouldReportUnresolved(item, callExpr) {
  const name = item?.callName || item?.name || "";
  if (name && NON_HELPER_PROPERTY_CALLS.has(name)) {
    return false;
  }
  if (name && NON_HELPER_CHAIN_METHODS.has(name) && !callExpr) {
    return false;
  }
  const info = callInfoFromItem(item, callExpr);
  if (isFrameworkChainOrUtilityCall(info)) return false;
  if (isPageObjectBuiltinUiCall(info)) return false;
  return true;
}

module.exports = {
  NON_HELPER_CHAIN_METHODS,
  NON_HELPER_PROPERTY_CALLS,
  isFrameworkChainOrUtilityCall,
  isPageObjectBuiltinUiCall,
  callInfoFromItem,
  shouldReportUnresolved,
};
