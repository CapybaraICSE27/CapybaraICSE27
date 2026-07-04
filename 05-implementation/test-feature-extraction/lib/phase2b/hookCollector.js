"use strict";

const { SyntaxKind } = require("ts-morph");
const { isGroupOrHookExpr, getCallbackArgFromCall } = require("../shared/identifiers");
const { getLineRange, getCallbackBodyRange } = require("../shared/utils");
const { DescribeStack, nextSuiteBoundaryLine } = require("../shared/describeStack");
const { countEachRows } = require("../phase2a/testCaseExtractor");

function getCallEndLine(call) {
  const cb = getCallbackArgFromCall(call);
  if (cb) return cb.getEndLineNumber();
  return call.getEndLineNumber();
}

function collectHooks(sourceFile, testNames, groupNames) {
  const hooks = [];
  const describeStack = new DescribeStack();
  const fileEndLine = sourceFile.getEndLineNumber();

  const calls = sourceFile
    .getDescendantsOfKind(SyntaxKind.CallExpression)
    .sort((a, b) => a.getStartLineNumber() - b.getStartLineNumber());

  for (const call of calls) {
    const line = call.getStartLineNumber();

    let expr = "";
    try {
      expr = call.getExpression().getText();
    } catch (_) {
      continue;
    }

    const groupInfo = isGroupOrHookExpr(expr, testNames, groupNames);
    if (!groupInfo) continue;

    if (groupInfo.kind === "fixture") continue;

    if (groupInfo.kind === "describe") {
      const { SyntaxKind: SK } = require("ts-morph");
      const parent = call.getParent();
      if (
        /\.each\s*\(/.test(expr) &&
        parent &&
        parent.getKind() === SK.CallExpression &&
        parent.getExpression() === call
      ) {
        continue;
      }

      let title =
        call.getArguments()[0]?.getLiteralText?.() ||
        call.getArguments()[0]?.getText()?.replace(/^['"`]|['"`]$/g, "") ||
        `describe@${line}`;
      let cb = getCallbackArgFromCall(call);
      let eachMeta = null;
      const callee = call.getExpression();
      const calleeText = callee.getText();
      if (callee.getKind() === SK.CallExpression && /describe\.each\b/.test(calleeText)) {
        eachMeta = countEachRows(callee);
      } else if (/\.each\s*\(/.test(expr)) {
        eachMeta = countEachRows(call);
        if (!cb) {
          const outer = call.getParent();
          if (outer && outer.getKind() === SK.CallExpression && outer.getExpression() === call) {
            cb = getCallbackArgFromCall(outer);
            const parentTitle =
              outer.getArguments()[0]?.getLiteralText?.() ||
              outer.getArguments()[0]?.getText()?.replace(/^['"`]|['"`]$/g, "");
            if (parentTitle) title = parentTitle;
          }
        }
      }
      const cbStart = cb ? cb.getStartLineNumber() : line;
      const cbEnd = cb
        ? cb.getEndLineNumber()
        : nextSuiteBoundaryLine(line, calls, testNames, groupNames, fileEndLine);
      if (/\.(skip|fixme)\b/.test(expr)) {
        describeStack.registerSkippedDescribe(title, cbStart, cbEnd);
        continue;
      }
      if (/\.only\b/.test(expr)) {
        describeStack.registerOnlyDescribe(title, cbStart, cbEnd, eachMeta);
        continue;
      }
      describeStack.registerDescribe(title, cbStart, cbEnd, eachMeta);
      continue;
    }

    if (groupInfo.kind === "hook") {
      const hookName = normalizeHookName(groupInfo.hook || expr);
      const callback = getCallbackArgFromCall(call);
      const range = callback ? getCallbackBodyRange(callback) : getLineRange(call);
      const describe_path = describeStack.getPathAtLine(line);
      hooks.push({
        hookName,
        source_kind: hookName,
        hook_owner_kind: groupInfo.hook_owner_kind || inferHookOwnerKind(expr) || "unknown",
        hook_instance_key: `${line}:${hookName}:${describe_path.join(">")}`,
        describe_path,
        start_line: range.start_line,
        end_line: range.end_line,
        hook_call_line: line,
        callback,
        is_file_level: describe_path.length === 0,
      });
    }
  }

  return hooks;
}

function normalizeHookName(raw) {
  const s = String(raw || "");
  if (/beforeEach/i.test(s)) return "beforeEach";
  if (/afterEach/i.test(s)) return "afterEach";
  if (/beforeAll/i.test(s)) return "beforeAll";
  if (/afterAll/i.test(s)) return "afterAll";
  if (/^before$/i.test(s)) return "before";
  if (/^after$/i.test(s)) return "after";
  return s;
}

function inferHookOwnerKind(expr) {
  const text = String(expr || "");
  if (/^fixture(?:\([^)]*\))?\.|^fixture\./.test(text)) return "fixture";
  if (/^test\./.test(text)) return "test";
  if (/^(before|after|beforeEach|afterEach|beforeAll|afterAll)$/.test(text)) return "global";
  return "unknown";
}

/**
 * Hooks whose describe_path is a prefix of the test's path (nested suite inheritance).
 */
function hooksForTestCase(hooks, testCase) {
  const path = testCase.describe_path || [];
  return hooks.filter((h) => {
    // File-level hooks apply to every test in the same source file (hooks are collected per file).
    if (h.is_file_level) return true;
    if (h.describe_path.length > path.length) return false;
    for (let i = 0; i < h.describe_path.length; i++) {
      if (h.describe_path[i] !== path[i]) return false;
    }
    return true;
  });
}

module.exports = { collectHooks, hooksForTestCase, normalizeHookName, inferHookOwnerKind };
