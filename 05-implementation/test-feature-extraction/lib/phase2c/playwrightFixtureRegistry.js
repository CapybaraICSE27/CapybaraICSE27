"use strict";

const path = require("path");
const { Node, SyntaxKind } = require("ts-morph");
const { PLAYWRIGHT_BUILTIN_FIXTURES } = require("../shared/playwrightFixtureProvenance");
const { buildImportMap, resolveImport, isSkippedPath } = require("./importResolver");

function propertyName(prop) {
  try {
    const node = prop.getNameNode?.();
    if (node && (Node.isStringLiteral(node) || Node.isNoSubstitutionTemplateLiteral(node))) {
      return node.getLiteralText();
    }
  } catch (_) {
    /* ignore */
  }
  try {
    return prop.getName?.() || "";
  } catch (_) {
    return "";
  }
}

function unwrapFixtureInitializer(node) {
  if (!node) return { callback: null, auto: false };
  if (Node.isArrowFunction(node) || Node.isFunctionExpression(node)) {
    return { callback: node, auto: false };
  }
  if (Node.isArrayLiteralExpression(node)) {
    const elements = node.getElements();
    const callback = elements.find((el) => Node.isArrowFunction(el) || Node.isFunctionExpression(el)) || null;
    const auto = elements.some((el) => {
      if (!Node.isObjectLiteralExpression(el)) return false;
      return el.getProperties().some((p) => {
        if (!Node.isPropertyAssignment(p)) return false;
        if (propertyName(p) !== "auto") return false;
        return p.getInitializer()?.getText() === "true";
      });
    });
    return { callback, auto };
  }
  return { callback: null, auto: false };
}

function fixtureFromProperty(prop, sourceFilePath) {
  const name = propertyName(prop);
  if (!name || PLAYWRIGHT_BUILTIN_FIXTURES.has(name)) return null;

  if (Node.isMethodDeclaration(prop)) {
    return {
      name,
      callback: prop,
      auto: false,
      file: sourceFilePath,
    };
  }

  if (!Node.isPropertyAssignment(prop)) return null;
  const { callback, auto } = unwrapFixtureInitializer(prop.getInitializer());
  if (!callback) return null;
  return {
    name,
    callback,
    auto,
    file: sourceFilePath,
  };
}

function extractFixtureDefinitions(sourceFile) {
  const fixtures = [];
  if (!sourceFile) return fixtures;
  const sourceFilePath = sourceFile.getFilePath();
  for (const call of sourceFile.getDescendantsOfKind(SyntaxKind.CallExpression)) {
    let expr = "";
    try {
      expr = call.getExpression().getText();
    } catch (_) {
      continue;
    }
    if (!/\.extend\b/.test(expr)) continue;
    const arg0 = call.getArguments()[0];
    if (!arg0 || !Node.isObjectLiteralExpression(arg0)) continue;
    for (const prop of arg0.getProperties()) {
      const fixture = fixtureFromProperty(prop, sourceFilePath);
      if (fixture) fixtures.push(fixture);
    }
  }
  return fixtures;
}

function addResolvedImportFile(files, project, repoPath, fromFile, entry, tsconfigCache) {
  if (!entry || !entry.spec) return;
  const spec = entry.spec;
  if (!spec.startsWith(".") && !spec.startsWith("~/") && !spec.startsWith("@/")) return;
  const resolved = resolveImport(fromFile, spec, repoPath, tsconfigCache);
  if (!resolved || isSkippedPath(resolved, repoPath)) return;
  if (files.has(resolved)) return;
  try {
    files.set(resolved, project.getSourceFile(resolved) || project.addSourceFileAtPath(resolved));
  } catch (_) {
    /* ignore unreadable imports */
  }
}

function candidateFixtureFiles(project, repoPath, sourceFile, importMap, tsconfigCache, testIdentifier = "") {
  const files = new Map();
  files.set(sourceFile.getFilePath(), sourceFile);
  const fromFile = sourceFile.getFilePath();

  if (testIdentifier && importMap.has(testIdentifier)) {
    addResolvedImportFile(files, project, repoPath, fromFile, importMap.get(testIdentifier), tsconfigCache);
  }

  return [...files.values()].filter(Boolean);
}

function buildPlaywrightFixtureRegistry({ project, repoPath, sourceFile, importMap, tsconfigCache, testIdentifier = "" }) {
  const registry = new Map();
  for (const sf of candidateFixtureFiles(project, repoPath, sourceFile, importMap, tsconfigCache, testIdentifier)) {
    for (const fixture of extractFixtureDefinitions(sf)) {
      if (!registry.has(fixture.name)) registry.set(fixture.name, []);
      registry.get(fixture.name).push(fixture);
    }
  }
  return registry;
}

function fixtureSourceKind(fixture) {
  return fixture?.auto ? "playwright_auto_fixture" : "playwright_fixture";
}

function fixtureTargetFile(fixture, repoPath) {
  if (!fixture?.file) return "";
  return path.relative(repoPath, fixture.file).replace(/\\/g, "/");
}

module.exports = {
  buildPlaywrightFixtureRegistry,
  extractFixtureDefinitions,
  fixtureSourceKind,
  fixtureTargetFile,
};
