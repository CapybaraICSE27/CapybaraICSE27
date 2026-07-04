"use strict";

const fs = require("fs");
const path = require("path");
const { SyntaxKind, Node } = require("ts-morph");

const CONFIG_NAMES = [
  "playwright.config.ts",
  "playwright.config.js",
  "playwright.config.mjs",
  "playwright.config.cjs",
];

function addPathLiteral(paths, node) {
  if (!node) return;
  if (Node.isStringLiteral(node) || Node.isNoSubstitutionTemplateLiteral(node)) {
    const raw = node.getLiteralText?.() ?? node.getText().replace(/^['"`]|['"`]$/g, "");
    if (raw) paths.add(raw);
    return;
  }
  if (Node.isCallExpression(node)) {
    const expr = node.getExpression().getText();
    if (/^require\s*$/.test(expr) || expr === "require") {
      const arg = node.getArguments()[0];
      if (arg && (Node.isStringLiteral(arg) || Node.isNoSubstitutionTemplateLiteral(arg))) {
        addPathLiteral(paths, arg);
      }
      return;
    }
    if (/defineConfig$/.test(expr) || expr.endsWith(".defineConfig")) {
      const arg = node.getArguments()[0];
      if (arg && Node.isObjectLiteralExpression(arg)) {
        collectFromObjectLiteral(paths, arg);
      }
    }
  }
}

function collectFromObjectLiteral(paths, obj) {
  for (const prop of obj.getProperties()) {
    if (!Node.isPropertyAssignment(prop)) continue;
    if (prop.getName() !== "globalSetup" && prop.getName() !== "globalTeardown") continue;
    const init = prop.getInitializer();
    if (!init) continue;
    if (Node.isArrayLiteralExpression(init)) {
      for (const el of init.getElements()) addPathLiteral(paths, el);
    } else {
      addPathLiteral(paths, init);
    }
  }
}

function extractGlobalSetupPaths(sourceFile, repoPath) {
  const paths = new Set();
  for (const prop of sourceFile.getDescendantsOfKind(SyntaxKind.PropertyAssignment)) {
    if (prop.getName() !== "globalSetup" && prop.getName() !== "globalTeardown") continue;
    const init = prop.getInitializer();
    if (!init) continue;
    if (Node.isArrayLiteralExpression(init)) {
      for (const el of init.getElements()) addPathLiteral(paths, el);
    } else {
      addPathLiteral(paths, init);
    }
  }
  for (const call of sourceFile.getDescendantsOfKind(SyntaxKind.CallExpression)) {
    const expr = call.getExpression().getText();
    if (/defineConfig$/.test(expr) || expr.endsWith(".defineConfig")) {
      const arg = call.getArguments()[0];
      if (arg && Node.isObjectLiteralExpression(arg)) {
        collectFromObjectLiteral(paths, arg);
      }
    }
  }
  for (const exp of sourceFile.getExportAssignments()) {
    const expr = exp.getExpression();
    if (expr && Node.isObjectLiteralExpression(expr)) {
      collectFromObjectLiteral(paths, expr);
    }
    if (expr && Node.isCallExpression(expr)) {
      addPathLiteral(paths, expr);
    }
  }
  const resolved = [];
  for (const rel of paths) {
    const abs = path.resolve(repoPath, rel);
    if (fs.existsSync(abs) && fs.statSync(abs).isFile()) {
      resolved.push(abs);
    }
  }
  return resolved;
}

/**
 * Load Playwright config and any globalSetup script into the ts-morph project.
 */
function loadPlaywrightGlobalSetupFiles(project, repoPath) {
  let added = 0;
  for (const name of CONFIG_NAMES) {
    const configPath = path.join(repoPath, name);
    if (!fs.existsSync(configPath)) continue;
    let sf;
    try {
      sf = project.getSourceFile(configPath) || project.addSourceFileAtPath(configPath);
    } catch (_) {
      continue;
    }
    for (const setupPath of extractGlobalSetupPaths(sf, repoPath)) {
      try {
        if (!project.getSourceFile(setupPath)) {
          project.addSourceFileAtPath(setupPath);
          added += 1;
        }
      } catch (_) {
        /* ignore parse errors */
      }
    }
  }
  return added;
}

module.exports = { loadPlaywrightGlobalSetupFiles, extractGlobalSetupPaths };
