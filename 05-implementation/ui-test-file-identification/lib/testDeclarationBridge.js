"use strict";

/**
 * Reuse Phase 2 AST utilities for test/BDD declaration detection (avoid duplicating logic).
 */
const path = require("path");
const phase2Shared = path.join(
  __dirname,
  "..",
  "..",
  "test-feature-extraction",
  "lib",
  "shared"
);

const {
  collectTestLikeIdentifiers,
  isTestCaseDeclarationExpr,
  isGroupOrHookExpr,
  getCallbackArgFromCall,
  collectBddStepIdentifiers,
  isBddStepExpr,
} = require(path.join(phase2Shared, "identifiers"));

const { extractPlaywrightCallbackFixtureNames } = require(path.join(
  phase2Shared,
  "playwrightFixtureProvenance"
));

const { SyntaxKind, Node } = require("ts-morph");

function collectPlaywrightFixtureParamsFromTestCalls(sourceFile, playwrightTestNames) {
  const { testNames } = collectTestLikeIdentifiers(sourceFile);
  const fixtures = new Set();
  for (const call of sourceFile.getDescendantsOfKind(SyntaxKind.CallExpression)) {
    let expr = "";
    try {
      expr = call.getExpression().getText();
    } catch (_) {
      continue;
    }
    let matched = false;
    for (const name of playwrightTestNames) {
      if (expr === name || expr.startsWith(`${name}.`)) {
        matched = true;
        break;
      }
    }
    if (!matched && !isTestCaseDeclarationExpr(expr, testNames)) continue;
    const cb = getCallbackArgFromCall(call);
    for (const f of extractPlaywrightCallbackFixtureNames(cb)) fixtures.add(f);
  }
  return [...fixtures];
}

module.exports = {
  collectTestLikeIdentifiers,
  isTestCaseDeclarationExpr,
  isGroupOrHookExpr,
  getCallbackArgFromCall,
  collectBddStepIdentifiers,
  isBddStepExpr,
  collectPlaywrightFixtureParamsFromTestCalls,
};
