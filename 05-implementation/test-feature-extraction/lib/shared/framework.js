"use strict";

const { UI_IMPORT_MODULES } = require("./patterns");
const { uniq, parseFrameworkList } = require("./utils");

function detectFrameworksFromImports(imports) {
  const frameworks = [];
  for (const [fw, modules] of Object.entries(UI_IMPORT_MODULES)) {
    if (imports.some((m) => modules.some((p) => m === p || m.startsWith(p + "/")))) {
      frameworks.push(fw);
    }
  }
  return uniq(frameworks);
}

function getImportModules(sourceFile) {
  const imports = [];
  for (const d of sourceFile.getImportDeclarations()) {
    imports.push(d.getModuleSpecifierValue());
  }
  return uniq(imports);
}

function resolveFrameworkForFile(manifestRow, imports) {
  const fromManifest = parseFrameworkList(manifestRow.file_detected_frameworks || manifestRow.detected_frameworks);
  const fromImports = detectFrameworksFromImports(imports);
  const local = parseFrameworkList(manifestRow.local_framework_context);
  const repo = parseFrameworkList(manifestRow.repo_framework_context);

  let primary = fromManifest[0] || fromImports[0] || local[0] || "Unknown";

  // Disambiguate Playwright vs Puppeteer on page.* APIs
  if (primary === "Puppeteer" && (fromImports.includes("@playwright/test") || local.includes("Playwright"))) {
    primary = "Playwright";
  }
  if (primary === "Playwright" && fromImports.some((m) => m === "puppeteer" || m === "puppeteer-core") && !fromImports.includes("@playwright/test")) {
    if (local.includes("Puppeteer") || fromManifest.includes("Puppeteer")) primary = "Puppeteer";
  }

  // WebDriverIO: require context
  const contexts = uniq([...repo, ...local, ...fromManifest, ...fromImports]);
  return { primary, contexts };
}

function isWebDriverIOContext(contexts) {
  return contexts.some((c) => c === "WebDriverIO");
}

module.exports = {
  detectFrameworksFromImports,
  getImportModules,
  resolveFrameworkForFile,
  isWebDriverIOContext,
};
