"use strict";

const path = require("path");
const { collectHooks } = require("../phase2b/hookCollector");
const { collectTestLikeIdentifiers } = require("../shared/identifiers");
const { isSupportFilePath } = require("./supportFileLoader");

function hookRunnerScope(hook) {
  const src = (hook.source_file || "").toLowerCase();
  if (src.includes("cypress/")) return "cypress";
  if (src.includes("playwright/")) return "playwright";
  if (src.includes("vitest")) return "vitest";
  if (src.includes("jest")) return "jest";
  return "other";
}

function testCaseRunnerScope(testCase) {
  const fw = String(testCase.framework || "").trim();
  const fwLower = fw.toLowerCase();
  const fp = String(testCase.file_path || "").toLowerCase();

  if (fw && fwLower !== "unknown") {
    if (fwLower.includes("cypress")) return "cypress";
    if (fwLower.includes("playwright")) return "playwright";
    if (fwLower.includes("vitest")) return "vitest";
    if (fwLower.includes("jest")) return "jest";
    if (fwLower.includes("testcafe")) return "testcafe";
    if (fwLower.includes("webdriver") || fwLower.includes("wdio")) return "webdriverio";
    if (fwLower.includes("selenium")) return "selenium";
    if (fwLower.includes("puppeteer")) return "puppeteer";
    return "other";
  }

  // Path heuristics only when Phase 1 framework is unknown (avoid .spec./.test. → vitest/jest for Playwright).
  if (fp.includes("cypress")) return "cypress";
  if (fp.includes("playwright")) return "playwright";
  if (fp.includes("vitest")) return "vitest";
  if (fp.includes("__tests__") || fp.includes("/jest")) return "jest";
  if (fp.includes("testcafe")) return "testcafe";
  if (fp.includes("wdio") || fp.includes("webdriver")) return "webdriverio";
  return "other";
}

/**
 * Whether a global support hook applies to a given test file (framework + path).
 */
function testMatchesGlobalSupportHook(testCase, hook) {
  const hookScope = hookRunnerScope(hook);
  const testScope = testCaseRunnerScope(testCase);
  if (hookScope === "cypress") return testScope === "cypress";
  if (hookScope === "playwright") return testScope === "playwright";
  if (hookScope === "vitest") return testScope === "vitest" || testScope === "jest";
  if (hookScope === "jest") return testScope === "jest" || testScope === "vitest";

  const src = (hook.source_file || "").toLowerCase();
  const fp = String(testCase.file_path || "").toLowerCase();

  if (src.includes("e2e/support") || src.includes("tests/e2e/support") || src.includes("test/e2e/support")) {
    return (
      fp.includes("e2e") &&
      (fp.includes("spec") ||
        fp.includes("cypress") ||
        fp.includes("playwright") ||
        fp.endsWith(".test.ts") ||
        fp.endsWith(".test.tsx") ||
        fp.endsWith(".spec.ts") ||
        fp.endsWith(".spec.tsx"))
    );
  }
  if (src.includes("tests/support") || src.includes("test/support")) {
    const srcTop = src.split("/")[0];
    return fp.startsWith(`${srcTop}/`) || fp.includes(`/${srcTop}/`);
  }

  const supportTop = src.split("/")[0];
  if (supportTop && supportTop.length > 1) {
    return fp.startsWith(`${supportTop}/`) || fp.includes(`/${supportTop}/`);
  }
  return testScope === "other" && hookScope === "other";
}

/**
 * Collect hooks from Cypress/Playwright support files loaded into the project.
 */
function collectGlobalSupportHooks(project, repoPath) {
  const hooks = [];
  for (const sf of project.getSourceFiles()) {
    const rel = path.relative(repoPath, sf.getFilePath()).replace(/\\/g, "/");
    if (rel.startsWith("..")) continue;
    if (!isSupportFilePath(rel)) continue;

    const { testNames, groupNames } = collectTestLikeIdentifiers(sf);
    const fileHooks = collectHooks(sf, testNames, groupNames);
    for (const h of fileHooks) {
      hooks.push({
        ...h,
        hook_instance_key: `support:${rel}:${h.hook_instance_key}`,
        source_file: rel,
        is_global_support: true,
        runner_scope: hookRunnerScope({ source_file: rel }),
      });
    }
  }
  return hooks;
}

const GLOBAL_SUPPORT_KEY_PREFIX = "support:";

function isGlobalSupportHookKey(key) {
  return String(key || "").startsWith(GLOBAL_SUPPORT_KEY_PREFIX);
}

/**
 * Replace (not accumulate) global support hook keys on test cases.
 * File-local hook keys (no support: prefix) are preserved.
 */
function applyGlobalSupportHooksToTestCases(testCases, globalHooks) {
  for (const tc of testCases) {
    const keys = new Set((tc.hook_instance_keys || []).filter((k) => !isGlobalSupportHookKey(k)));
    for (const h of globalHooks) {
      if (testMatchesGlobalSupportHook(tc, h)) {
        keys.add(h.hook_instance_key);
      }
    }
    tc.hook_instance_keys = [...keys];
  }
}

/** Drop stale support:* shared-hook features before re-adding current global hooks. */
function reconcileGlobalSupportHookFeatures(featuresDirect, globalHooks) {
  const validKeys = new Set(globalHooks.map((h) => h.hook_instance_key));
  let write = 0;
  for (let i = 0; i < featuresDirect.length; i++) {
    const f = featuresDirect[i];
    if (!f.is_shared_hook_feature) {
      featuresDirect[write++] = f;
      continue;
    }
    const key = f.hook_instance_key || "";
    if (!isGlobalSupportHookKey(key) || validKeys.has(key)) {
      featuresDirect[write++] = f;
    }
  }
  featuresDirect.length = write;
}

function extractGlobalSupportHookFeatures(globalHooks, repoMeta) {
  const { walkNodeForFeatures } = require("../phase2b/directFeatureExtractor");
  const all = [];
  for (const h of globalHooks) {
    if (!h.callback) continue;
    const feats = [];
    const fw =
      h.runner_scope === "cypress"
        ? "Cypress"
        : h.runner_scope === "playwright"
          ? "Playwright"
          : h.runner_scope === "vitest"
            ? "Vitest"
            : h.runner_scope === "jest"
              ? "Jest"
              : "Unknown";
    walkNodeForFeatures(h.callback, {
      repo: repoMeta.repo,
      test_id: "",
      file_path: h.source_file || "",
      phase1_confidence: "high",
      framework: fw,
      contexts: [],
      importMap: new Map(),
      source_kind: h.source_kind,
      hook_instance_key: h.hook_instance_key,
      hook_owner_kind: h.hook_owner_kind || "global",
      is_shared_hook_feature: true,
      context_node: h.callback,
    }, feats);
    all.push(...feats);
  }
  return all;
}

module.exports = {
  GLOBAL_SUPPORT_KEY_PREFIX,
  isGlobalSupportHookKey,
  collectGlobalSupportHooks,
  applyGlobalSupportHooksToTestCases,
  reconcileGlobalSupportHookFeatures,
  extractGlobalSupportHookFeatures,
  testMatchesGlobalSupportHook,
  hookRunnerScope,
  testCaseRunnerScope,
};
