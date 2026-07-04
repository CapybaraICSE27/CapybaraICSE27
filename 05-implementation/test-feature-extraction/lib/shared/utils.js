"use strict";

const crypto = require("crypto");
const { Node } = require("ts-morph");

function toPosix(p) {
  return String(p || "").split(/[\\/]/).join("/");
}

function uniq(arr) {
  return [...new Set(arr)].filter(Boolean);
}

function escapeRegExp(s) {
  return String(s).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function stableTestId(parts) {
  const payload = parts.map((p) => (Array.isArray(p) ? p.join(">") : String(p ?? ""))).join("|");
  return crypto.createHash("sha256").update(payload).digest("hex").slice(0, 32);
}

function getLineRange(node) {
  if (!node) return { start_line: null, end_line: null };
  const start = node.getStartLineNumber();
  const end = node.getEndLineNumber();
  return { start_line: start, end_line: end };
}

/**
 * Line range of executable callback body (not title/template on the same line as `async () =>`).
 * Uses first statement line inside a block body, or the expression body for concise arrows.
 */
function getCallbackBodyRange(callback) {
  if (!callback) return { start_line: null, end_line: null };
  if (Node.isArrowFunction(callback) || Node.isFunctionExpression(callback)) {
    const body = callback.getBody();
    if (!body) return getLineRange(callback);
    if (Node.isBlock(body)) {
      const statements = body.getStatements();
      if (statements.length > 0) {
        return {
          start_line: statements[0].getStartLineNumber(),
          end_line: body.getEndLineNumber(),
        };
      }
      return getLineRange(body);
    }
    return getLineRange(body);
  }
  return getLineRange(callback);
}

function getRawSnippet(node, maxLen = 500) {
  if (!node) return "";
  try {
    const text = node.getText();
    if (text.length <= maxLen) return text;
    return text.slice(0, maxLen) + "...";
  } catch (_) {
    return "";
  }
}

function parseFrameworkList(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value.filter(Boolean);
  return String(value)
    .split(/[;|]/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function primaryFramework(manifestRow) {
  const fromFile = parseFrameworkList(manifestRow.file_detected_frameworks || manifestRow.detected_frameworks);
  if (fromFile.length) return fromFile[0];
  const local = parseFrameworkList(manifestRow.local_framework_context);
  if (local.length) return local[0];
  return "Unknown";
}

module.exports = {
  toPosix,
  uniq,
  escapeRegExp,
  stableTestId,
  getLineRange,
  getCallbackBodyRange,
  getRawSnippet,
  parseFrameworkList,
  primaryFramework,
};
