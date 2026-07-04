"use strict";

const { SyntaxKind, Node } = require("ts-morph");
const { escapeRegExp, uniq } = require("./utils");
const { GROUP_OR_HOOK_PATTERNS, BDD_IMPORT_MODULE_PREFIXES } = require("./patterns");

function collectTestLikeIdentifiers(sourceFile) {
  const testNames = new Set(["test", "it"]);
  const groupNames = new Set(["describe"]);
  const playwrightTestNames = new Set();

  for (const d of sourceFile.getImportDeclarations()) {
    const moduleName = d.getModuleSpecifierValue();
    if (moduleName === "@playwright/test") {
      for (const ni of d.getNamedImports()) {
        const name = ni.getName();
        const alias = ni.getAliasNode()?.getText() || name;
        if (name === "test") {
          testNames.add(alias);
          playwrightTestNames.add(alias);
        }
      }
    }
  }

  let changed = true;
  while (changed) {
    changed = false;
    for (const vd of sourceFile.getDescendantsOfKind(SyntaxKind.VariableDeclaration)) {
      const nameNode = vd.getNameNode();
      if (!Node.isIdentifier(nameNode)) continue;
      const init = vd.getInitializer();
      if (!init) continue;
      const localName = nameNode.getText();
      const initText = init.getText();
      if (playwrightTestNames.has(initText) && !playwrightTestNames.has(localName)) {
        testNames.add(localName);
        playwrightTestNames.add(localName);
        changed = true;
        continue;
      }
      const extendMatch = initText.match(/^([A-Za-z_$][\w$]*)\.extend\s*\(/);
      if (extendMatch && playwrightTestNames.has(extendMatch[1]) && !playwrightTestNames.has(localName)) {
        testNames.add(localName);
        playwrightTestNames.add(localName);
        changed = true;
      }
    }
  }

  return { testNames: [...testNames], groupNames: [...groupNames], playwrightTestNames: [...playwrightTestNames] };
}

function isTestCaseDeclarationExpr(expr, testNames) {
  for (const name of testNames) {
    // Playwright/Cypress helper calls — not standalone test cases.
    if (
      new RegExp(
        `^${escapeRegExp(name)}\\.(step|info|use|extend|describe|beforeEach|afterEach|beforeAll|afterAll)\\b`
      ).test(expr)
    ) {
      return { match: false };
    }
    if (new RegExp(`^${escapeRegExp(name)}\\.(slow|serial|parallel)$`).test(expr)) {
      return { match: false };
    }
    if (expr === name) return { match: true, status: "normal", declType: name };
    const only = new RegExp(`^${escapeRegExp(name)}\\.only$`);
    const skip = new RegExp(`^${escapeRegExp(name)}\\.(skip|fixme)$`);
    const each = new RegExp(`^${escapeRegExp(name)}\\.each\\s*\\(`);
    if (only.test(expr)) return { match: true, status: "only", declType: `${name}.only` };
    if (skip.test(expr)) return { match: true, status: "skip", declType: `${name}.skip` };
    if (each.test(expr)) return { match: true, status: "normal", declType: `${name}.each`, parameterized: true };
  }
  return { match: false };
}

function matchChainedFixtureOrTestHook(expr) {
  const text = String(expr || "");
  const fixtureHook = text.match(
    /(?:^fixture(?:\([^)]*\))?|\.fixture(?:\([^)]*\))?)\.(beforeEach|afterEach|beforeAll|afterAll|before|after)$/
  );
  if (fixtureHook) {
    return { hook: fixtureHook[1], hook_owner_kind: "fixture" };
  }
  const testHook = text.match(/(?:^|\.)test\.(before|after|beforeEach|afterEach|beforeAll|afterAll)$/);
  if (testHook) {
    return { hook: testHook[1], hook_owner_kind: "test" };
  }
  return null;
}

function isGroupOrHookExpr(expr, testNames, groupNames) {
  const chainedHook = matchChainedFixtureOrTestHook(expr);
  if (chainedHook) {
    return { kind: "hook", hook: chainedHook.hook, expr, hook_owner_kind: chainedHook.hook_owner_kind };
  }
  if (/^fixture\.(beforeEach|afterEach|beforeAll|afterAll|before|after)$/.test(expr)) {
    const hook = expr.split(".").pop();
    return { kind: "hook", hook, expr, hook_owner_kind: "fixture" };
  }
  if (/^test\.(before|after)$/.test(expr)) {
    const hook = expr.split(".").pop();
    return { kind: "hook", hook, expr, hook_owner_kind: "test" };
  }
  if (/^fixture$/.test(expr)) {
    return { kind: "fixture", expr };
  }
  for (const name of groupNames) {
    if (expr === name || new RegExp(`^${escapeRegExp(name)}\\.(only|skip|each)$`).test(expr)) {
      return { kind: "describe", expr };
    }
    if (new RegExp(`^${escapeRegExp(name)}\\.each\\s*\\(`).test(expr)) {
      return { kind: "describe", expr };
    }
  }
  for (const name of testNames) {
    if (new RegExp(`^${escapeRegExp(name)}\\.describe`).test(expr)) return { kind: "describe", expr };
    if (new RegExp(`^${escapeRegExp(name)}\\.(beforeEach|afterEach|beforeAll|afterAll)$`).test(expr)) {
      const hook = expr.split(".").pop();
      return { kind: "hook", hook, expr, hook_owner_kind: "test" };
    }
  }
  if (GROUP_OR_HOOK_PATTERNS.some((re) => re.test(expr))) {
    if (/^(test\.)?(beforeEach|afterEach|beforeAll|afterAll)$/.test(expr)) {
      const hook = expr.split(".").pop() || expr;
      const hook_owner_kind = /^test\./.test(expr) ? "test" : "global";
      return { kind: "hook", hook, expr, hook_owner_kind };
    }
    if (/^before$/.test(expr) || /^after$/.test(expr)) {
      return { kind: "hook", hook: expr, expr, hook_owner_kind: "global" };
    }
    if (/^describe/.test(expr) || /^test\.describe/.test(expr)) {
      return { kind: "describe", expr };
    }
  }
  return null;
}

function collectBddStepIdentifiers(sourceFile) {
  const names = new Set(["Given", "When", "Then", "And", "But"]);
  for (const d of sourceFile.getImportDeclarations()) {
    const moduleName = d.getModuleSpecifierValue();
    if (!BDD_IMPORT_MODULE_PREFIXES.some((p) => moduleName === p || moduleName.startsWith(p + "/"))) continue;
    for (const ni of d.getNamedImports()) {
      const name = ni.getName();
      const alias = ni.getAliasNode()?.getText() || name;
      if (["Given", "When", "Then", "And", "But", "defineStep"].includes(name)) names.add(alias);
    }
  }
  return [...names];
}

function isBddStepExpr(expr, bddNames) {
  return bddNames.includes(expr);
}

function getCallbackArgFromCall(call) {
  const args = call.getArguments();
  for (let i = args.length - 1; i >= 0; i--) {
    const a = args[i];
    if (Node.isArrowFunction(a) || Node.isFunctionExpression(a)) return a;
  }
  return null;
}

/**
 * @returns {string|null|undefined} title text, null when title is a dynamic template, "" if none
 */
function extractTestTitle(call) {
  const args = call.getArguments();
  for (const a of args) {
    if (Node.isStringLiteral(a) || Node.isNoSubstitutionTemplateLiteral(a)) {
      return a.getLiteralText?.() ?? a.getText().replace(/^['"`]|['"`]$/g, "");
    }
    if (Node.isTemplateExpression(a)) {
      if (a.getTemplateSpans().length > 0) return null;
      const head = a.getHead();
      return head.getLiteralText?.() ?? head.getText().replace(/^['"`]|['"`]$/g, "");
    }
  }
  return "";
}

const { extractPlaywrightFixtures } = require("./playwrightFixtureProvenance");

module.exports = {
  collectTestLikeIdentifiers,
  isTestCaseDeclarationExpr,
  isGroupOrHookExpr,
  collectBddStepIdentifiers,
  isBddStepExpr,
  getCallbackArgFromCall,
  extractTestTitle,
  extractPlaywrightFixtures,
  matchChainedFixtureOrTestHook,
};
