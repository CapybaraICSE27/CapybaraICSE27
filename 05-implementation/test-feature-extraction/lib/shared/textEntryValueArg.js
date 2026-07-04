"use strict";

const { Node } = require("ts-morph");
const { TEXT_ENTRY_VALUE_ARG } = require("./patterns");

/** Playwright Page APIs pass selector first, value second. Locator APIs pass value at index 0. */
const PAGE_SELECTOR_FIRST_METHODS = new Set(["fill", "type", "press", "selectOption"]);

function getCallReceiverText(callNode) {
  try {
    const callee = callNode.getExpression();
    if (Node.isPropertyAccessExpression(callee)) {
      return callee.getExpression().getText();
    }
  } catch (_) {
    /* ignore */
  }
  return "";
}

function isPageReceiverText(recvText) {
  const t = (recvText || "").trim();
  return t === "page" || t === "this.page";
}

function resolveTextEntryValueArgIndex(callNode, method) {
  const defaultIdx = TEXT_ENTRY_VALUE_ARG[method] ?? 0;
  if (PAGE_SELECTOR_FIRST_METHODS.has(method) && isPageReceiverText(getCallReceiverText(callNode))) {
    return 1;
  }
  return defaultIdx;
}

module.exports = {
  PAGE_SELECTOR_FIRST_METHODS,
  getCallReceiverText,
  isPageReceiverText,
  resolveTextEntryValueArgIndex,
};
