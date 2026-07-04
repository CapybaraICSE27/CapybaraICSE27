"use strict";

const { SyntaxKind, Node } = require("ts-morph");
const { uniq } = require("./utils");

const PLAYWRIGHT_BUILTIN_FIXTURES = new Set([
  "page",
  "context",
  "browser",
  "request",
  "baseURL",
]);

/**
 * Custom fixture parameter names from test('...', async ({ page, authenticatedPage }) => ...).
 */
function extractPlaywrightCallbackFixtureNames(callback) {
  if (!callback) return [];
  const params = callback.getParameters();
  if (!params.length) return [];
  const paramNode = params[0].getNameNode();
  const names = [];
  if (Node.isObjectBindingPattern(paramNode)) {
    for (const el of paramNode.getElements()) {
      const name = el.getName();
      if (name && !PLAYWRIGHT_BUILTIN_FIXTURES.has(name)) {
        names.push(name);
      }
    }
  }
  return uniq(names);
}

/**
 * Fixture keys declared via test.extend({ authenticatedPage: async ({ page }, use) => ... }).
 */
function extractPlaywrightExtendFixtureNames(sourceFile) {
  const names = [];
  if (!sourceFile) return names;
  for (const call of sourceFile.getDescendantsOfKind(SyntaxKind.CallExpression)) {
    let expr = "";
    try {
      expr = call.getExpression().getText();
    } catch (_) {
      continue;
    }
    if (!/\.extend\s*\(/.test(expr)) continue;
    const root = expr.split(".")[0];
    if (!/^(test|base)$/i.test(root) && !/test$/i.test(expr.split(".")[0])) {
      // allow aliased test identifiers (e.g. pwTest.extend)
      if (!/test$/i.test(root) && root !== "base") continue;
    }
    const arg0 = call.getArguments()[0];
    if (!arg0 || !Node.isObjectLiteralExpression(arg0)) continue;
    for (const prop of arg0.getProperties()) {
      if (Node.isPropertyAssignment(prop) || Node.isMethodDeclaration(prop)) {
        const key = prop.getName();
        if (key && !PLAYWRIGHT_BUILTIN_FIXTURES.has(key)) names.push(key);
      }
    }
  }
  return uniq(names);
}

/**
 * Map fixture name -> { declaredBy, scope } for provenance fields on features.
 */
function buildPlaywrightFixtureProvenanceMap(sourceFile, callbackFixtureNames) {
  const map = new Map();
  for (const name of extractPlaywrightExtendFixtureNames(sourceFile)) {
    map.set(name, { declaredBy: "test.extend", scope: "file" });
  }
  for (const name of callbackFixtureNames || []) {
    if (!map.has(name)) {
      map.set(name, { declaredBy: "test_callback", scope: "test" });
    }
  }
  return map;
}

function extractPlaywrightFixtures(callback) {
  return extractPlaywrightCallbackFixtureNames(callback);
}

module.exports = {
  PLAYWRIGHT_BUILTIN_FIXTURES,
  extractPlaywrightCallbackFixtureNames,
  extractPlaywrightExtendFixtureNames,
  buildPlaywrightFixtureProvenanceMap,
  extractPlaywrightFixtures,
};
