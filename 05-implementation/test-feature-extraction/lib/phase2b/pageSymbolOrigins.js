"use strict";

const { SyntaxKind, Node } = require("ts-morph");

const POM_CTOR_RE = /\bnew\s+[A-Z][A-Za-z0-9]*(?:Page|Screen|PO|PageObject)\s*\(/;
const FRAMEWORK_NEW_PAGE_RE = /\b(?:context|browser)\s*\.\s*newPage\s*\(|\bnewPage\s*\(/;

/**
 * Lightweight symbol-origin map: variable name -> page_object_model | framework_page_instance.
 */
function buildPageSymbolOrigins(sourceFile) {
  const origins = new Map();
  if (!sourceFile) return origins;

  for (const vd of sourceFile.getDescendantsOfKind(SyntaxKind.VariableDeclaration)) {
    const name = vd.getName();
    if (!name || typeof name !== "string") continue;
    const init = vd.getInitializer();
    const initText = init ? init.getText() : "";
    if (FRAMEWORK_NEW_PAGE_RE.test(initText)) {
      origins.set(name, "framework_page_instance");
      continue;
    }
    if (POM_CTOR_RE.test(initText)) {
      origins.set(name, "page_object_model");
    }
  }

  for (const imp of sourceFile.getImportDeclarations()) {
    const spec = imp.getModuleSpecifierValue() || "";
    if (!/pages?\/|page-?objects?|pom\b/i.test(spec)) continue;
    for (const ni of imp.getNamedImports()) {
      const alias = ni.getAliasNode()?.getText() || ni.getName();
      if (alias && /^[A-Z]/.test(alias)) {
        origins.set(alias, "page_object_model");
      }
    }
  }

  return origins;
}

module.exports = { buildPageSymbolOrigins, POM_CTOR_RE, FRAMEWORK_NEW_PAGE_RE };
