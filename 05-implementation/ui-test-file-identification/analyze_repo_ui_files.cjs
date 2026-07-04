#!/usr/bin/env node
/**
 * Phase 1 UI Test File Inventory Analyzer - v15
 *
 * This analyzer scans one local JavaScript/TypeScript repository and identifies
 * browser-driven UI test files with evidence and confidence.
 *
 * Main capabilities:
 *  - Detects Playwright, Cypress, Selenium, WebDriverIO, Puppeteer, TestCafe, and Nightwatch tests.
 *  - Separates UI interaction evidence from assertions, synchronization, network/dependency control, and custom commands.
 *  - Separates file-specific framework evidence from local and repository-level framework context.
 *  - Handles Playwright aliases/custom fixtures and Playwright browser fixture parameters.
 *  - Uses safe static handling for dynamic config: fallback path patterns, simple partial evaluation, and package-script parsing.
 *  - Detects BDD-style step-definition files using Given/When/Then when BDD context is present.
  - Separates regular test files from setup/helper/support files and filters template files.
  - Uses stricter medium-confidence rules to reduce non-UI/unit-test false positives.
  - Requires file/context-specific Selenium evidence to avoid driver.get(...) false positives.
  - Anchors Playwright/Puppeteer page-action detection to actual call expressions to avoid object-property false positives.
  - Does not count browser/context lifecycle calls as direct UI actions by themselves.
  - Does not count cy.viewport(...) as a direct UI action by itself.
  - Avoids WebDriverIO false positives from standalone $/$$ selector calls.
  - Separates root-level template/ and templates/ paths from the main inventory.
  - Keeps Puppeteer labels only with explicit file evidence or Puppeteer-only local context.
  - Labels Cypress custom-command files as Cypress when local Cypress context exists.
  - Avoids treating API/response custom commands like cy.ResponseCheck as UI-like Cypress commands.
 *
 * Dependency:
 *   npm install ts-morph
 */

const fs = require("fs");
const path = require("path");
const { Project, SyntaxKind, Node } = require("ts-morph");
const { parseArgs, toPosix, uniq, readTextSafely, makeFileUrl } = require("./lib/utils");
const {
  deriveDirFromGlob,
  dirsFromGlobPatterns,
  isInside,
  isPosixPathInside,
  splitTopLevelArgs,
  stripQuotes,
  collectSimpleConfigConstants,
  resolveSimplePathJoinExpression,
  resolveConfigExpression,
} = require("./lib/configDiscovery");
const {
  collectTestLikeIdentifiers,
  isTestCaseDeclarationExpr,
  isGroupOrHookExpr,
  getCallbackArgFromCall,
  collectBddStepIdentifiers,
  isBddStepExpr,
  collectPlaywrightFixtureParamsFromTestCalls,
} = require("./lib/testDeclarationBridge");

const SOURCE_EXTS = new Set([".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"]);
const IGNORE_DIR_NAMES = new Set([
  "node_modules", ".git", "dist", "build", "coverage", ".next", ".nuxt",
  ".cache", ".turbo", ".vercel", "vendor", "out", "tmp", "temp",
  ".yarn", ".pnpm-store"
]);

const TEST_LIKE_RE = /(\.|-|_)(spec|test|e2e|cy)\.(ts|tsx|js|jsx|mjs|cjs)$/i;
const TEST_DIR_PARTS = new Set([
  "test", "tests", "__tests__", "e2e", "integration", "spec", "specs",
  "playwright", "cypress", "wdio", "webdriverio", "nightwatch", "testcafe"
]);

const CONFIG_FILE_RE = /^(playwright\.config|cypress\.config|wdio\.conf|nightwatch\.conf|testcafe\.config|jest\.config|vitest\.config|vite\.config|package\.json|tsconfig|jsconfig)/i;

const UI_IMPORT_MODULES = {
  Playwright: ["@playwright/test", "playwright"],
  Cypress: ["cypress"],
  Selenium: ["selenium-webdriver"],
  WebDriverIO: ["webdriverio", "@wdio/globals", "@wdio/sync"],
  Puppeteer: ["puppeteer", "puppeteer-core"],
  TestCafe: ["testcafe"],
  Nightwatch: ["nightwatch"],
};

const PACKAGE_DEP_TO_FRAMEWORK = {
  "@playwright/test": "Playwright",
  "playwright": "Playwright",
  "cypress": "Cypress",
  "selenium-webdriver": "Selenium",
  "webdriverio": "WebDriverIO",
  "@wdio/globals": "WebDriverIO",
  "@wdio/sync": "WebDriverIO",
  "puppeteer": "Puppeteer",
  "puppeteer-core": "Puppeteer",
  "testcafe": "TestCafe",
  "nightwatch": "Nightwatch",
};

const BDD_PACKAGE_NAMES = new Set([
  "@cucumber/cucumber",
  "cucumber",
  "cucumber-js",
  "playwright-bdd",
  "@badeball/cypress-cucumber-preprocessor",
  "cypress-cucumber-preprocessor",
  "@cucumber/gherkin",
]);

const BDD_IMPORT_MODULE_PREFIXES = [
  "@cucumber/cucumber",
  "cucumber",
  "playwright-bdd",
  "@badeball/cypress-cucumber-preprocessor",
  "cypress-cucumber-preprocessor",
];

const CONFIG_NAME_TO_FRAMEWORK = [
  [/playwright\.config/i, "Playwright"],
  [/cypress\.config/i, "Cypress"],
  [/wdio\.conf/i, "WebDriverIO"],
  [/nightwatch\.conf/i, "Nightwatch"],
  [/testcafe\.config/i, "TestCafe"],
];

const GROUP_OR_HOOK_PATTERNS = [
  /^describe$/,
  /^describe\.(only|skip|each)$/,
  /^test\.describe$/,
  /^test\.describe\.(only|skip|serial|parallel|configure)$/,
  /^fixture$/,
  /^test\.beforeEach$/,
  /^test\.afterEach$/,
  /^beforeEach$/,
  /^afterEach$/,
  /^beforeAll$/,
  /^afterAll$/,
];

const UI_ACTION_PATTERNS = {
  Playwright: [
    // Match the call expression itself, not arbitrary nested property access
    // inside an assertion argument such as expect(obj.page.type).toBe(...).
    //
    // Browser/context lifecycle calls such as browser.newContext(),
    // browser.newPage(), context.newPage(), and browser.close() are intentionally
    // not counted as direct UI actions. They may support UI tests, but by
    // themselves they do not prove that the file performs UI interaction.
    /^page\.(goto|locator|getByRole|getByText|getByLabel|getByTestId|getByPlaceholder|getByAltText|getByTitle|click|fill|type|press|hover|dragTo|selectOption|setInputFiles|waitForLoadState|waitForURL|waitForResponse|waitForSelector|waitForTimeout|evaluate)$/,
    /^page\..*\.(click|fill|type|press|hover|dragTo|selectOption|setInputFiles|waitFor|isVisible|textContent|inputValue)$/,
    /^(locator|frame|dialog)\.(click|fill|type|press|hover|dragTo|selectOption|setInputFiles|waitFor|isVisible|textContent|inputValue)$/,
  ],
  Cypress: [
    // Direct UI/browser interaction and element-location commands only.
    // cy.viewport(...) is treated as browser configuration/control evidence,
    // not as direct UI interaction by itself.
    /\bcy\.(visit|get|contains|find|click|type|clear|select|check|uncheck|scrollTo|trigger|mount)\b/,
  ],
  Selenium: [
    // Avoid treating arbitrary configuration objects named `driver` as Selenium.
    // `driver.get(...)` alone is not enough; framework/import context is required
    // by normalizeFrameworkAmbiguity before Selenium is kept.
    /\bdriver\.(findElement|findElements|navigate|manage|switchTo|executeScript|wait)\b/,
    /\bBy\.(id|name|cssSelector|xpath|linkText|partialLinkText|className|tagName)\b/,
    /^.*\.findElement\(.*\)\.(click|sendKeys|clear|submit|getText|isDisplayed|isEnabled)\b/,
  ],
  WebDriverIO: [
    // Do not count standalone $ / $$ as WebDriverIO evidence. Many unit/parser
    // tests use $ as jQuery/Cheerio-style selector helpers. Count only clearer
    // WebDriverIO browser commands or chained element actions.
    /\bbrowser\.(url|click|setValue|getUrl|waitUntil|pause|execute|reloadSession|newWindow)\b/,
    /^.*\$\s*\([^)]*\)\.(click|setValue|addValue|getText|waitForDisplayed|isDisplayed)\b/,
    /^.*\$\$\s*\([^)]*\)\.(map|forEach|filter|length)\b/,
  ],
  Puppeteer: [
    // puppeteer.launch/connect are framework evidence, but browser.newPage/close
    // alone is lifecycle evidence, not direct UI interaction.
    /^puppeteer\.(launch|connect)$/,
    /^page\.(goto|click|type|keyboard|mouse|waitForSelector|waitForNavigation|waitForResponse|screenshot|evaluate|select|focus|hover|setViewport)$/,
  ],
  TestCafe: [
    /\bSelector\s*\(/,
    /\bt\.(click|typeText|selectText|pressKey|navigateTo|hover|drag|setFilesToUpload|wait)\b/,
  ],
  Nightwatch: [
    /\bbrowser\.(url|click|setValue|waitForElementVisible|waitForElementPresent|end|pause)\b/,
  ],
};


const CYPRESS_DIRECT_UI_COMMANDS = new Set([
  "visit", "get", "contains", "find", "click", "type", "clear", "select",
  "check", "uncheck", "scrollTo", "trigger", "mount",
]);

const CYPRESS_CONTROL_COMMANDS = new Set([
  "intercept", "request", "wait", "session", "task", "exec", "readFile",
  "writeFile", "fixture", "log", "wrap", "clock", "tick", "reload", "viewport",
  "clearCookies", "setCookie", "getCookie", "getCookies", "screenshot",
]);

const CYPRESS_ASSERTION_COMMANDS = new Set([
  "should", "and",
]);

function getCypressCommandName(expr) {
  const match = String(expr || "").match(/\bcy\.([A-Za-z_$][\w$]*)\b/);
  return match ? match[1] : "";
}

function isUiLikeCypressCustomCommand(command) {
  const c = String(command || "");
  // Common Testing Library and selector helper names:
  // cy.findByRole, cy.findAllByText, cy.getBySel, cy.dataCy, etc.
  if (/^(findBy|findAllBy|getBy|getAllBy|queryBy|queryAllBy)/.test(c)) return true;
  if (/^(dataCy|getBySel|getByTestId|getByRole|getByText|getByLabel|getByLabelText|getByPlaceholder|getByPlaceholderText)$/.test(c)) return true;

  // Explicitly UI-only custom commands.
  if (/^(loginViaUi|logoutViaUi)$/i.test(c)) return true;

  // UI-oriented action verbs are considered UI-like only when they start the
  // command name. This avoids API/server-side helpers such as ResponseCheck,
  // ResponseStatusCheck, and CreationOfUniqueAPIcheck being treated as UI.
  if (/^(click|type|select|hover|focus|blur|scroll|drag|drop|submit|open|close|navigate|visit|mount)([A-Z_$]|$)/i.test(c)) return true;

  // check/uncheck are very ambiguous in API tests. Keep only clear UI-control
  // forms rather than any custom command containing "check".
  if (/^(check|uncheck)(Box|Checkbox|Radio|Toggle|Input|Form|Option|Field)?([A-Z_$]|$)/i.test(c)) return true;

  return false;
}

function collectCypressEvidence(calls) {
  const directUiCalls = [];
  const controlCalls = [];
  const uiLikeCustomCommandCalls = [];
  const nonUiCustomCommandCalls = [];

  for (const expr of calls) {
    const command = getCypressCommandName(expr);
    if (!command) continue;

    if (CYPRESS_DIRECT_UI_COMMANDS.has(command)) {
      directUiCalls.push(expr);
    } else if (CYPRESS_CONTROL_COMMANDS.has(command)) {
      controlCalls.push(expr);
    } else if (!CYPRESS_ASSERTION_COMMANDS.has(command)) {
      if (isUiLikeCypressCustomCommand(command)) {
        uiLikeCustomCommandCalls.push(expr);
      } else {
        nonUiCustomCommandCalls.push(expr);
      }
    }
  }

  return {
    directUiCalls: uniq(directUiCalls).slice(0, 50),
    controlCalls: uniq(controlCalls).slice(0, 50),
    uiLikeCustomCommandCalls: uniq(uiLikeCustomCommandCalls).slice(0, 50),
    nonUiCustomCommandCalls: uniq(nonUiCustomCommandCalls).slice(0, 50),
    // Backward-compatible combined list.
    customCommandCalls: uniq([...uiLikeCustomCommandCalls, ...nonUiCustomCommandCalls]).slice(0, 50),
  };
}

const ASSERTION_PATTERNS = [
  /\bexpect\s*\(/,
  /\bassert\./,
  /\bshould\./,
  /\.should\b/,
  /\.(toBeVisible|toBeHidden|toHaveURL|toHaveText|toContainText|toHaveAttribute|toHaveValue|toHaveScreenshot|toEqual|toBe|toContain)\b/,
  /\bt\.expect\s*\(/,
  /\bbrowser\.assert\./,
  /\bbrowser\.expect\./,
];

function walkFiles(root) {
  const files = [];
  const stack = [root];

  while (stack.length > 0) {
    const current = stack.pop();
    let entries = [];
    try {
      entries = fs.readdirSync(current, { withFileTypes: true });
    } catch (_) {
      continue;
    }

    for (const entry of entries) {
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) {
        if (!IGNORE_DIR_NAMES.has(entry.name)) stack.push(full);
      } else if (entry.isFile()) {
        files.push(full);
      }
    }
  }
  return files;
}

function getConfigFiles(allFiles, root) {
  return allFiles
    .filter((f) => CONFIG_FILE_RE.test(path.basename(f)))
    .map((f) => toPosix(path.relative(root, f)))
    .sort();
}

function detectRepoFrameworkContext(allFiles, root, configFiles) {
  const frameworks = new Set();

  for (const rel of configFiles) {
    for (const [re, fw] of CONFIG_NAME_TO_FRAMEWORK) {
      if (re.test(path.basename(rel))) frameworks.add(fw);
    }
  }

  for (const file of allFiles) {
    if (path.basename(file) !== "package.json") continue;
    let pkg;
    try {
      pkg = JSON.parse(fs.readFileSync(file, "utf8"));
    } catch (_) {
      continue;
    }

    const depGroups = [
      pkg.dependencies || {},
      pkg.devDependencies || {},
      pkg.peerDependencies || {},
      pkg.optionalDependencies || {},
    ];
    for (const deps of depGroups) {
      for (const depName of Object.keys(deps)) {
        if (PACKAGE_DEP_TO_FRAMEWORK[depName]) {
          frameworks.add(PACKAGE_DEP_TO_FRAMEWORK[depName]);
        }
      }
    }

    const scripts = pkg.scripts || {};
    for (const script of Object.values(scripts)) {
      const s = String(script).toLowerCase();
      if (s.includes("playwright")) frameworks.add("Playwright");
      if (s.includes("cypress")) frameworks.add("Cypress");
      if (s.includes("wdio") || s.includes("webdriverio")) frameworks.add("WebDriverIO");
      if (s.includes("nightwatch")) frameworks.add("Nightwatch");
      if (s.includes("testcafe")) frameworks.add("TestCafe");
      if (s.includes("puppeteer")) frameworks.add("Puppeteer");
    }
  }

  return [...frameworks].sort();
}

function frameworksFromPackageJsonFile(file) {
  let pkg;
  try {
    pkg = JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (_) {
    return [];
  }

  const frameworks = new Set();
  const depGroups = [
    pkg.dependencies || {},
    pkg.devDependencies || {},
    pkg.peerDependencies || {},
    pkg.optionalDependencies || {},
  ];

  for (const deps of depGroups) {
    for (const depName of Object.keys(deps)) {
      if (PACKAGE_DEP_TO_FRAMEWORK[depName]) {
        frameworks.add(PACKAGE_DEP_TO_FRAMEWORK[depName]);
      }
    }
  }

  const scripts = pkg.scripts || {};
  for (const script of Object.values(scripts)) {
    const s = String(script).toLowerCase();
    if (s.includes("playwright")) frameworks.add("Playwright");
    if (s.includes("cypress")) frameworks.add("Cypress");
    if (s.includes("wdio") || s.includes("webdriverio")) frameworks.add("WebDriverIO");
    if (s.includes("nightwatch")) frameworks.add("Nightwatch");
    if (s.includes("testcafe")) frameworks.add("TestCafe");
    if (s.includes("puppeteer")) frameworks.add("Puppeteer");
  }

  return [...frameworks].sort();
}

function buildPackageFrameworkContext(allFiles) {
  const map = new Map();
  for (const file of allFiles) {
    if (path.basename(file) !== "package.json") continue;
    const frameworks = frameworksFromPackageJsonFile(file);
    if (frameworks.length > 0) {
      map.set(path.dirname(file), frameworks);
    }
  }
  return map;
}

function nearestPackageFrameworkContext(filePath, root, packageFrameworkContext) {
  const frameworks = new Set();
  let dir = path.dirname(filePath);
  const normalizedRoot = path.resolve(root);

  while (isInside(normalizedRoot, dir)) {
    const local = packageFrameworkContext.get(dir);
    if (local) {
      for (const fw of local) frameworks.add(fw);
      break; // nearest package.json should dominate
    }
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }

  return [...frameworks].sort();
}

function fileConfigFrameworkContext(filePath, root, configFiles) {
  const frameworks = new Set();
  const relFile = toPosix(path.relative(root, filePath));
  const fileParts = relFile.split("/");

  for (const relConfig of configFiles) {
    const configDir = path.posix.dirname(relConfig);
    const configBase = path.basename(relConfig);
    const sameTree = isPosixPathInside(configDir, relFile);
    if (!sameTree) continue;
    for (const [re, fw] of CONFIG_NAME_TO_FRAMEWORK) {
      if (re.test(configBase)) frameworks.add(fw);
    }
  }

  // Path-specific clues are intentionally local to the file.
  if (fileParts.includes("cypress") || relFile.endsWith(".cy.ts") || relFile.endsWith(".cy.tsx") || relFile.endsWith(".cy.js") || relFile.endsWith(".cy.jsx")) {
    frameworks.add("Cypress");
  }
  if (fileParts.includes("playwright")) frameworks.add("Playwright");
  if (fileParts.includes("wdio") || fileParts.includes("webdriverio")) frameworks.add("WebDriverIO");
  if (fileParts.includes("nightwatch")) frameworks.add("Nightwatch");
  if (fileParts.includes("testcafe")) frameworks.add("TestCafe");

  return [...frameworks].sort();
}

function fileLocalFrameworkContext(filePath, root, configFiles, packageFrameworkContext) {
  return uniq([
    ...nearestPackageFrameworkContext(filePath, root, packageFrameworkContext),
    ...fileConfigFrameworkContext(filePath, root, configFiles),
  ]).sort();
}

function bddContextsFromPackageJsonFile(file) {
  let pkg;
  try {
    pkg = JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (_) {
    return [];
  }

  const contexts = new Set();
  const depGroups = [
    pkg.dependencies || {},
    pkg.devDependencies || {},
    pkg.peerDependencies || {},
    pkg.optionalDependencies || {},
  ];

  for (const deps of depGroups) {
    for (const depName of Object.keys(deps)) {
      if (BDD_PACKAGE_NAMES.has(depName)) contexts.add(depName);
    }
  }

  const scripts = pkg.scripts || {};
  for (const script of Object.values(scripts)) {
    const s = String(script).toLowerCase();
    if (s.includes("cucumber")) contexts.add("cucumber_script");
    if (s.includes("bdd")) contexts.add("bdd_script");
  }

  return [...contexts].sort();
}

function detectRepoBddContext(allFiles) {
  const contexts = new Set();
  for (const file of allFiles) {
    if (path.basename(file) !== "package.json") continue;
    for (const c of bddContextsFromPackageJsonFile(file)) contexts.add(c);
  }
  return [...contexts].sort();
}

function buildPackageBddContext(allFiles) {
  const map = new Map();
  for (const file of allFiles) {
    if (path.basename(file) !== "package.json") continue;
    const contexts = bddContextsFromPackageJsonFile(file);
    if (contexts.length > 0) {
      map.set(path.dirname(file), contexts);
    }
  }
  return map;
}

function nearestPackageBddContext(filePath, root, packageBddContext) {
  const contexts = new Set();
  let dir = path.dirname(filePath);
  const normalizedRoot = path.resolve(root);

  while (isInside(normalizedRoot, dir)) {
    const local = packageBddContext.get(dir);
    if (local) {
      for (const c of local) contexts.add(c);
      break;
    }
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }

  return [...contexts].sort();
}

function fileLocalBddContext(filePath, root, packageBddContext) {
  return nearestPackageBddContext(filePath, root, packageBddContext);
}

function extractConfigCandidateDirs(allFiles, root) {
  const dirs = new Set();
  const sources = [];
  const rootAbs = path.resolve(root);

  for (const file of allFiles) {
    const base = path.basename(file);
    if (!CONFIG_FILE_RE.test(base)) continue;

    const text = readTextSafely(file);
    if (!text) continue;

    const configDir = path.dirname(file);
    const constants = collectSimpleConfigConstants(text);

    function addCandidate(raw, sourceKind) {
      const values = Array.isArray(raw) ? raw : [raw];
      for (const value of values) {
        const s = String(value || "");
        if (/[*{[]/.test(s)) {
          for (const relDir of dirsFromGlobPatterns(root, configDir, [s])) {
            const abs = path.resolve(rootAbs, relDir);
            if (isInside(rootAbs, abs) && fs.existsSync(abs)) {
              dirs.add(abs);
              sources.push({
                source_kind: sourceKind + "_fastglob",
                source_file: toPosix(path.relative(root, file)),
                raw_value: value,
                candidate_dir: toPosix(path.relative(root, abs)),
              });
            }
          }
          continue;
        }
        const d = deriveDirFromGlob(value);
        if (!d) continue;
        const abs = path.resolve(configDir, d);
        if (isInside(rootAbs, abs) && fs.existsSync(abs)) {
          dirs.add(abs);
          sources.push({
            source_kind: sourceKind,
            source_file: toPosix(path.relative(root, file)),
            raw_value: value,
            candidate_dir: toPosix(path.relative(root, abs)),
          });
        }
      }
    }

    // Layer 1: literal config values.
    const singleValueRe = /\b(testDir|specPattern|component\.?specPattern|specs|src_folders)\b\s*[:=]\s*(['"`][^'"`]+['"`])/g;
    let m;
    while ((m = singleValueRe.exec(text)) !== null) {
      addCandidate(resolveConfigExpression(m[2], constants), "literal_config_value");
    }

    const arrayRe = /\b(testMatch|specPattern|component\.?specPattern|specs|src_folders)\b\s*[:=]\s*\[([\s\S]{0,3000}?)\]/g;
    while ((m = arrayRe.exec(text)) !== null) {
      const body = m[2];
      for (const item of splitTopLevelArgs(body)) {
        addCandidate(resolveConfigExpression(item, constants), "literal_config_array");
      }
    }

    // Layer 2: lightweight static partial evaluation.
    // Handles testDir: e2eDir, specs: specs, specs, and testDir: path.join(...)
    const exprRe = /\b(testDir|specPattern|component\.?specPattern|specs|src_folders|testMatch)\b\s*[:=]\s*([^,\n\r}]+|\[[\s\S]{0,3000}?\])/g;
    while ((m = exprRe.exec(text)) !== null) {
      const values = resolveConfigExpression(m[2], constants);
      if (values.length > 0) addCandidate(values, "partial_eval_config_expr");
    }

    // Shorthand property: const specs = [...]; export const config = { specs, }
    const shorthandRe = /\b(testDir|specPattern|componentSpecPattern|specs|src_folders|testMatch)\s*(?:,|})/g;
    while ((m = shorthandRe.exec(text)) !== null) {
      const key = m[1];
      if (constants[key]) addCandidate(constants[key], "partial_eval_shorthand_config");
    }
  }

  return {
    dirs: [...dirs].filter((d) => isInside(rootAbs, d) && fs.existsSync(d)),
    sources,
  };
}

function extractPackageScriptCandidateDirs(allFiles, root) {
  const dirs = new Set();
  const sources = [];
  const rootAbs = path.resolve(root);

  function addCandidate(raw, sourceFile, scriptName) {
    const d = deriveDirFromGlob(raw);
    if (!d) return;
    const packageDir = path.dirname(sourceFile);
    const abs = path.resolve(packageDir, d);
    if (isInside(rootAbs, abs) && fs.existsSync(abs)) {
      dirs.add(abs);
      sources.push({
        source_kind: "package_script",
        source_file: toPosix(path.relative(root, sourceFile)),
        script_name: scriptName,
        raw_value: raw,
        candidate_dir: toPosix(path.relative(root, abs)),
      });
    }
  }

  function extractPathLikeTokens(script) {
    const values = new Set();
    const s = String(script || "");

    // --spec cypress/e2e/**/*.cy.ts
    const specRe = /--(?:spec|grep|config-file|project)\s+['"]?([^'"\s]+)['"]?/g;
    let m;
    while ((m = specRe.exec(s)) !== null) values.add(m[1]);

    // Quoted paths/globs.
    const quotedRe = /['"]([^'"]*(?:e2e|test|tests|spec|cypress|playwright|wdio|nightwatch|testcafe)[^'"]*)['"]/gi;
    while ((m = quotedRe.exec(s)) !== null) values.add(m[1]);

    // Unquoted path-like tokens.
    const tokenRe = /(?:^|\s)([^\s;&|]+(?:\/|\\)[^\s;&|]*(?:e2e|test|tests|spec|cypress|playwright|wdio|nightwatch|testcafe)[^\s;&|]*)/gi;
    while ((m = tokenRe.exec(s)) !== null) {
      const token = m[1].replace(/^['"]|['"]$/g, "");
      if (!token.startsWith("-")) values.add(token);
    }

    // Framework-specific defaults when scripts mention framework but no explicit path.
    const lower = s.toLowerCase();
    if (lower.includes("cypress")) values.add("cypress");
    if (lower.includes("playwright")) values.add("playwright");
    if (lower.includes("wdio") || lower.includes("webdriverio")) values.add("wdio");
    if (lower.includes("nightwatch")) values.add("nightwatch");
    if (lower.includes("testcafe")) values.add("testcafe");

    return [...values];
  }

  for (const file of allFiles) {
    if (path.basename(file) !== "package.json") continue;

    let pkg;
    try {
      pkg = JSON.parse(fs.readFileSync(file, "utf8"));
    } catch (_) {
      continue;
    }

    const scripts = pkg.scripts || {};
    for (const [scriptName, script] of Object.entries(scripts)) {
      const lowerName = String(scriptName).toLowerCase();
      const lowerScript = String(script).toLowerCase();
      const isRelevant =
        /e2e|ui|browser|playwright|cypress|wdio|webdriver|nightwatch|testcafe|puppeteer/.test(lowerName) ||
        /playwright|cypress|wdio|webdriverio|nightwatch|testcafe|puppeteer/.test(lowerScript);

      if (!isRelevant) continue;

      for (const raw of extractPathLikeTokens(script)) {
        addCandidate(raw, file, scriptName);
      }
    }
  }

  return {
    dirs: [...dirs].filter((d) => isInside(rootAbs, d) && fs.existsSync(d)),
    sources,
  };
}

function isCandidateTestFile(absPath, root, configCandidateDirs) {
  const rel = toPosix(path.relative(root, absPath));
  const ext = path.extname(absPath);
  if (!SOURCE_EXTS.has(ext)) return false;

  const base = path.basename(absPath);
  if (TEST_LIKE_RE.test(base)) return true;

  const parts = rel.split("/");
  if (parts.some((p) => TEST_DIR_PARTS.has(p.toLowerCase()))) {
    return true;
  }

  if (configCandidateDirs.some((d) => isInside(d, absPath))) {
    return true;
  }

  return false;
}

function getImportModules(sourceFile) {
  const imports = [];
  for (const d of sourceFile.getImportDeclarations()) {
    imports.push(d.getModuleSpecifierValue());
  }

  for (const call of sourceFile.getDescendantsOfKind(SyntaxKind.CallExpression)) {
    const expr = call.getExpression().getText();
    if (expr === "require") {
      const firstArg = call.getArguments()[0];
      if (firstArg && firstArg.getKindName && firstArg.getKindName() === "StringLiteral") {
        imports.push(firstArg.getLiteralText());
      }
    }
  }
  return uniq(imports);
}

function detectFrameworksFromImports(imports) {
  const frameworks = [];
  for (const [fw, modules] of Object.entries(UI_IMPORT_MODULES)) {
    if (imports.some((m) => modules.some((prefix) => m === prefix || m.startsWith(prefix + "/")))) {
      frameworks.push(fw);
    }
  }
  return uniq(frameworks);
}

function exprMatchesAny(expr, patterns) {
  return patterns.some((re) => re.test(expr));
}


function detectBddContextsFromImports(imports) {
  const contexts = [];
  for (const imp of imports) {
    if (BDD_IMPORT_MODULE_PREFIXES.some((prefix) => imp === prefix || imp.startsWith(prefix + "/"))) {
      contexts.push(imp);
    }
  }
  return uniq(contexts);
}

function collectEvidence(sourceFile) {
  const imports = getImportModules(sourceFile);
  const frameworksFromImports = detectFrameworksFromImports(imports);
  const bddContextsFromImports = detectBddContextsFromImports(imports);
  const { testNames, groupNames, playwrightTestNames } = collectTestLikeIdentifiers(sourceFile);
  const bddStepNames = collectBddStepIdentifiers(sourceFile);

  const calls = sourceFile.getDescendantsOfKind(SyntaxKind.CallExpression).map((call) => {
    try {
      return call.getExpression().getText();
    } catch (_) {
      return "";
    }
  }).filter(Boolean);

  const testCaseDeclarations = [];
  const groupOrHookDeclarations = [];
  const bddStepDeclarations = [];

  for (const expr of calls) {
    if (isTestCaseDeclarationExpr(expr, testNames)) {
      testCaseDeclarations.push(expr);
    } else if (isBddStepExpr(expr, bddStepNames)) {
      bddStepDeclarations.push(expr);
    } else if (isGroupOrHookExpr(expr, testNames, groupNames)) {
      groupOrHookDeclarations.push(expr);
    }
  }

  const playwrightFixtureParams = collectPlaywrightFixtureParamsFromTestCalls(sourceFile, playwrightTestNames);

  const uiActionEvidence = {};
  const frameworksFromUiActions = [];

  for (const [fw, patterns] of Object.entries(UI_ACTION_PATTERNS)) {
    const matched = calls.filter((expr) => exprMatchesAny(expr, patterns));
    if (matched.length > 0) {
      frameworksFromUiActions.push(fw);
      uiActionEvidence[fw] = uniq(matched).slice(0, 50);
    }
  }

  const cypressEvidence = collectCypressEvidence(calls);
  const assertionCalls = uniq(calls.filter((expr) => ASSERTION_PATTERNS.some((re) => re.test(expr)))).slice(0, 50);
  const fileDetectedFrameworks = uniq([...frameworksFromImports, ...frameworksFromUiActions]);

  return {
    imports,
    frameworksFromImports,
    frameworksFromUiActions: uniq(frameworksFromUiActions),
    fileDetectedFrameworks,
    bddContextsFromImports,
    testCaseDeclarations: uniq(testCaseDeclarations),
    groupOrHookDeclarations: uniq(groupOrHookDeclarations),
    bddStepDeclarations: uniq(bddStepDeclarations),
    playwrightFixtureParams,
    uiActionsByFramework: uiActionEvidence,
    cypressDirectUiCalls: cypressEvidence.directUiCalls,
    cypressControlCalls: cypressEvidence.controlCalls,
    cypressUiLikeCustomCommandCalls: cypressEvidence.uiLikeCustomCommandCalls,
    cypressNonUiCustomCommandCalls: cypressEvidence.nonUiCustomCommandCalls,
    cypressCustomCommandCalls: cypressEvidence.customCommandCalls,
    assertionCalls,
    allCallCount: calls.length,
  };
}

function flattenUiActions(uiActionsByFramework) {
  const out = [];
  for (const [fw, calls] of Object.entries(uiActionsByFramework || {})) {
    for (const c of calls) out.push(`${fw}:${c}`);
  }
  return uniq(out);
}

function flattenCypressCustomCommands(evidence) {
  return uniq((evidence.cypressCustomCommandCalls || []).map((c) => `CypressCustom:${c}`));
}

function flattenCypressUiLikeCustomCommands(evidence) {
  return uniq((evidence.cypressUiLikeCustomCommandCalls || []).map((c) => `CypressUiLikeCustom:${c}`));
}

function flattenCypressNonUiCustomCommands(evidence) {
  return uniq((evidence.cypressNonUiCustomCommandCalls || []).map((c) => `CypressNonUiCustom:${c}`));
}

function flattenCypressControlCalls(evidence) {
  return uniq((evidence.cypressControlCalls || []).map((c) => `CypressControl:${c}`));
}

function hasFramework(frameworks, name) {
  return Array.isArray(frameworks) && frameworks.includes(name);
}

function normalizeFrameworkAmbiguity(evidence, localFrameworkContext) {
  // Playwright and Puppeteer share page.goto/page.click/page.waitForSelector-like APIs.
  // To avoid falsely labeling Playwright files as Puppeteer, resolve the ambiguity
  // using file imports first, then local package/config/path context.
  const importedPlaywright = hasFramework(evidence.frameworksFromImports, "Playwright");
  const importedPuppeteer = hasFramework(evidence.frameworksFromImports, "Puppeteer");
  const localPlaywright = hasFramework(localFrameworkContext, "Playwright");
  const localPuppeteer = hasFramework(localFrameworkContext, "Puppeteer");

  const removeFramework = (fw) => {
    evidence.frameworksFromUiActions = (evidence.frameworksFromUiActions || []).filter((x) => x !== fw);
    evidence.fileDetectedFrameworks = (evidence.fileDetectedFrameworks || []).filter((x) => x !== fw);
    if (evidence.uiActionsByFramework) delete evidence.uiActionsByFramework[fw];
  };

  const puppeteerActionEvidence = (evidence.uiActionsByFramework && evidence.uiActionsByFramework.Puppeteer) || [];
  const explicitPuppeteerFileEvidence =
    importedPuppeteer ||
    puppeteerActionEvidence.some((expr) => /^puppeteer\.(launch|connect)$/.test(expr));

  const playwrightActionEvidence = (evidence.uiActionsByFramework && evidence.uiActionsByFramework.Playwright) || [];
  const hasPlaywrightSpecificFileEvidence =
    importedPlaywright ||
    (evidence.playwrightFixtureParams || []).length > 0 ||
    playwrightActionEvidence.some((expr) =>
      /^page\.(locator|getByRole|getByText|getByLabel|getByTestId|getByPlaceholder|getByAltText|getByTitle|waitForLoadState|waitForURL|waitForResponse)$/.test(expr)
    );

  // File-level imports are strongest.
  if (importedPlaywright && !importedPuppeteer) {
    removeFramework("Puppeteer");
  } else if (importedPuppeteer && !importedPlaywright && !hasPlaywrightSpecificFileEvidence) {
    removeFramework("Playwright");
  } else {
    // Playwright and Puppeteer share generic page.* APIs such as page.goto(...)
    // and page.evaluate(...). Do not keep Puppeteer just because generic page.*
    // calls matched. Keep Puppeteer only with explicit file-level Puppeteer
    // evidence, or when the local context is Puppeteer-only.
    const localContextIsPuppeteerOnly = localPuppeteer && !localPlaywright && !importedPlaywright;
    if (!explicitPuppeteerFileEvidence && !localContextIsPuppeteerOnly) {
      removeFramework("Puppeteer");
    }

    // Conversely, if the local context is Playwright-only and the file has no
    // Playwright-specific evidence, do not infer Puppeteer from shared APIs.
    if (localPlaywright && !localPuppeteer && !importedPuppeteer) {
      removeFramework("Puppeteer");
    }

    // If the file has clear Playwright-specific evidence and no explicit
    // Puppeteer evidence, it should be Playwright, not Playwright;Puppeteer.
    if (hasPlaywrightSpecificFileEvidence && !explicitPuppeteerFileEvidence) {
      removeFramework("Puppeteer");
    }

    // In a Puppeteer-only local context, remove Playwright when there is no
    // Playwright-specific file evidence. This preserves real Puppeteer files
    // that use page.goto/page.evaluate without imports.
    if (localPuppeteer && !localPlaywright && !hasPlaywrightSpecificFileEvidence) {
      removeFramework("Playwright");
    }
  }

  // Selenium is also ambiguous because many non-UI objects are named `driver`
  // and expose `driver.get(...)`. Only keep Selenium if there is file-specific
  // Selenium import evidence or local Selenium/WebDriver context. Stronger
  // Selenium-specific calls such as By.cssSelector/findElement are still not
  // enough by themselves in backend/unit-test files without framework context.
  const importedSelenium = hasFramework(evidence.frameworksFromImports, "Selenium");
  const localSelenium = hasFramework(localFrameworkContext, "Selenium");
  if (!importedSelenium && !localSelenium) {
    removeFramework("Selenium");
  }

  // WebDriverIO is ambiguous because $/$$ and even browser-like helpers can
  // appear in non-WebDriverIO tests. Only keep WebDriverIO if the file imports
  // WebDriverIO/@wdio or the local package/config/path context indicates it.
  const importedWebDriverIO = hasFramework(evidence.frameworksFromImports, "WebDriverIO");
  const localWebDriverIO = hasFramework(localFrameworkContext, "WebDriverIO");
  if (!importedWebDriverIO && !localWebDriverIO) {
    removeFramework("WebDriverIO");
  }

  evidence.frameworksFromUiActions = uniq(evidence.frameworksFromUiActions || []);
  evidence.fileDetectedFrameworks = uniq(evidence.fileDetectedFrameworks || []);
  return evidence;
}

function classifyFileRole(relPath, evidence) {
  const rel = String(relPath || "").replace(/\\/g, "/");
  const lower = rel.toLowerCase();
  const base = path.posix.basename(lower);

  // Template files are not developer-written test instances and should not be
  // counted in the main inventory.
  if (
    lower === "template" ||
    lower === "templates" ||
    lower.startsWith("template/") ||
    lower.startsWith("templates/") ||
    lower.includes("/templates/") ||
    lower.includes("/template/") ||
    lower.includes("/scripts/templates/") ||
    base.includes("componentname") ||
    base.includes("__template__") ||
    base.includes(".template.")
  ) {
    return "template_file";
  }

  // Setup projects may contain real browser actions, but their role is
  // environment/session setup rather than ordinary test cases.
  if (
    lower.includes("/setup/") ||
    base.includes(".setup.") ||
    base === "setup.ts" ||
    base === "setup.js" ||
    base === "setup.mjs" ||
    base === "setup.cjs" ||
    base.includes("global-setup") ||
    base.includes("global.setup") ||
    base.includes("auth.setup") ||
    base.includes("storage-state") ||
    base.includes("storagestate")
  ) {
    return "setup_file";
  }

  // Support/helper files are separated if their path/name suggests they are
  // shared infrastructure rather than an actual test file. A .spec/.test/.cy/.e2e
  // file remains a test_file unless it was already caught by setup/template rules.
  if (!TEST_LIKE_RE.test(base)) {
    if (
      lower.includes("/support/") ||
      lower.includes("/helpers/") ||
      lower.includes("/helper/") ||
      lower.includes("/utils/") ||
      lower.includes("/commands/") ||
      lower.includes("/fixtures/") ||
      base.includes("helper") ||
      base === "utils.ts" ||
      base === "utils.js" ||
      base === "util.ts" ||
      base === "util.js" ||
      base.includes("commands") ||
      base.includes("fixture")
    ) {
      return "helper_file";
    }
  }

  if ((evidence.testCaseDeclarations || []).length > 0 || (evidence.bddStepDeclarations || []).length > 0) {
    return "test_file";
  }

  return "unclear";
}


function pathLooksStrongForUiTesting(relPath) {
  const relLower = relPath.toLowerCase();
  return (
    relLower.includes("cypress/") ||
    relLower.includes("playwright/") ||
    relLower.includes("/e2e/") ||
    relLower.includes("\\e2e\\") ||
    relLower.includes("/wdio/") ||
    relLower.includes("/nightwatch/") ||
    relLower.endsWith(".cy.ts") ||
    relLower.endsWith(".cy.tsx") ||
    relLower.endsWith(".cy.js") ||
    relLower.endsWith(".cy.jsx") ||
    relLower.endsWith(".e2e.ts") ||
    relLower.endsWith(".e2e.js")
  );
}

function inferFrameworksForFile(evidence, repoFrameworkContext, relPath) {
  const fileFrameworks = new Set(evidence.fileDetectedFrameworks);
  const pathStrong = pathLooksStrongForUiTesting(relPath);

  const hasCypressEvidence =
    (evidence.cypressDirectUiCalls || []).length > 0 ||
    (evidence.cypressUiLikeCustomCommandCalls || []).length > 0 ||
    (evidence.cypressNonUiCustomCommandCalls || []).length > 0 ||
    (evidence.cypressControlCalls || []).length > 0 ||
    (evidence.cypressCustomCommandCalls || []).length > 0;

  // Cypress custom commands may not produce file_detected_frameworks because
  // they are deliberately separated from direct UI actions. If local context or
  // path evidence says this is Cypress, keep the framework label so Phase 2 can
  // route the file correctly.
  if (hasCypressEvidence && (repoFrameworkContext.includes("Cypress") || pathStrong)) {
    fileFrameworks.add("Cypress");
  }

  // If the file has Playwright fixture params and repo/import context supports Playwright,
  // infer Playwright for this file.
  if (
    evidence.playwrightFixtureParams.length > 0 &&
    (evidence.frameworksFromImports.includes("Playwright") || repoFrameworkContext.includes("Playwright"))
  ) {
    fileFrameworks.add("Playwright");
  }

  // If no file-specific framework was detected, infer a single repo-level framework only when
  // context is unambiguous and the path is strong.
  if (fileFrameworks.size === 0 && repoFrameworkContext.length === 1 && pathStrong) {
    fileFrameworks.add(repoFrameworkContext[0]);
  }

  return [...fileFrameworks].sort();
}

function classifyFile(evidence, relPath, localFrameworkContext, localBddContext) {
  const hasTestCaseDecl = evidence.testCaseDeclarations.length > 0;
  const hasBddStepDecl = evidence.bddStepDeclarations.length > 0;
  const uiActions = flattenUiActions(evidence.uiActionsByFramework);
  const hasUiActions = uiActions.length > 0;
  const hasAssertions = evidence.assertionCalls.length > 0;
  const hasFileFrameworkImport = evidence.frameworksFromImports.length > 0;
  const hasFileSpecificFrameworkEvidence =
    hasFileFrameworkImport ||
    (evidence.frameworksFromUiActions || []).length > 0 ||
    (evidence.bddContextsFromImports || []).length > 0;
  const hasPlaywrightFixtureParams = evidence.playwrightFixtureParams.length > 0;
  const hasCypressUiLikeCustomCommands = (evidence.cypressUiLikeCustomCommandCalls || []).length > 0;
  const hasCypressNonUiCustomCommands = (evidence.cypressNonUiCustomCommandCalls || []).length > 0;
  const hasCypressCustomCommands = (evidence.cypressCustomCommandCalls || []).length > 0;
  const hasCypressControlCalls = (evidence.cypressControlCalls || []).length > 0;
  const hasBddContext = (evidence.bddContextsFromImports || []).length > 0 || (localBddContext || []).length > 0;
  const pathStrong = pathLooksStrongForUiTesting(relPath);
  const inferredFrameworks = inferFrameworksForFile(evidence, localFrameworkContext, relPath);
  const hasFrameworkEvidence = inferredFrameworks.length > 0 || hasFileFrameworkImport;

  if (!hasTestCaseDecl && !(hasBddStepDecl && hasBddContext)) {
    return { confidence: "none", reason: "no executable test-case declaration or BDD step-definition declaration" };
  }

  const isBddStyle = !hasTestCaseDecl && hasBddStepDecl && hasBddContext;
  const hasPuppeteer = inferredFrameworks.includes("Puppeteer") || evidence.fileDetectedFrameworks.includes("Puppeteer");

  if (hasPuppeteer) {
    if (hasUiActions && hasAssertions && (hasFileFrameworkImport || pathStrong || isBddStyle)) {
      return { confidence: "high", reason: "Puppeteer test/BDD step with UI actions and assertion/path/import evidence" };
    }
    if (hasUiActions && hasAssertions) {
      return { confidence: "medium", reason: "Puppeteer test/BDD step with UI actions and assertions" };
    }
    return { confidence: "low", reason: "Puppeteer evidence without enough oracle/path evidence; possible automation script" };
  }

  if (hasUiActions && hasFrameworkEvidence) {
    return { confidence: "high", reason: isBddStyle ? "BDD step definition with direct UI actions and framework evidence" : "executable test case with direct UI actions and framework evidence" };
  }

  if (hasUiActions && pathStrong) {
    return { confidence: "high", reason: isBddStyle ? "BDD step definition with direct UI actions in strong UI-test path" : "executable test case with direct UI actions in strong UI-test path" };
  }

  if (hasUiActions) {
    return { confidence: "medium", reason: isBddStyle ? "BDD step definition with direct UI actions but weak framework/path evidence" : "executable test case with direct UI actions but weak framework/path evidence" };
  }

  // UI-like Cypress custom commands can wrap real UI interactions, but they are still
  // weaker than direct cy.visit/cy.get/cy.click evidence.
  if (hasCypressUiLikeCustomCommands && (localFrameworkContext || []).includes("Cypress")) {
    if (pathStrong || hasAssertions || hasFileSpecificFrameworkEvidence) {
      return { confidence: "medium", reason: "Cypress test uses UI-like custom commands; UI actions may be hidden in custom command implementation" };
    }
    return { confidence: "low", reason: "Cypress UI-like custom commands without direct UI actions; needs custom-command review" };
  }

  // Non-UI Cypress custom/control commands are not enough for medium confidence.
  if ((hasCypressNonUiCustomCommands || hasCypressControlCalls || hasCypressCustomCommands) && (localFrameworkContext || []).includes("Cypress")) {
    return { confidence: "low", reason: "Cypress custom/control commands without direct UI actions; possible API/setup/non-UI test" };
  }

  // Playwright fixture parameters only count if the file itself imports/defines
  // a Playwright test function. Local repo context alone is not enough because
  // ordinary unit tests may use a parameter named `context`.
  if (hasPlaywrightFixtureParams && hasFileFrameworkImport && evidence.frameworksFromImports.includes("Playwright")) {
    return { confidence: "medium", reason: "Playwright test uses browser fixture parameters; UI actions may be in helpers" };
  }

  if (isBddStyle && hasFileSpecificFrameworkEvidence) {
    return { confidence: "medium", reason: "BDD step definition with file-specific browser framework context; UI actions may be in helpers" };
  }

  // Stricter rule: if there is no direct UI action and no file-specific
  // framework evidence, do not place the file in the high/medium inventory.
  if (!hasUiActions && !hasFileSpecificFrameworkEvidence) {
    if (hasFrameworkEvidence && (pathStrong || hasAssertions || hasCypressControlCalls)) {
      return { confidence: "low", reason: "only local/repo framework context without direct UI actions or file-specific framework evidence" };
    }
    return { confidence: "none", reason: "insufficient file-specific UI-test evidence" };
  }

  if (hasFrameworkEvidence && pathStrong && hasAssertions) {
    return { confidence: "low", reason: "framework/path/assertion evidence but no direct UI actions; needs helper review" };
  }

  if (hasFrameworkEvidence && (hasAssertions || pathStrong || hasCypressControlCalls)) {
    return { confidence: "low", reason: "weak framework evidence without direct UI actions; needs manual/helper review" };
  }

  return { confidence: "none", reason: "insufficient UI-test evidence" };
}

function analyzeRepo(options = {}) {
  const rawRepoPath = options.repoPath || options["repo-path"];
  if (!rawRepoPath) {
    throw new Error("analyzeRepo requires options.repoPath");
  }
  const repoPath = path.resolve(rawRepoPath);
  if (!fs.existsSync(repoPath)) {
    throw new Error(`repoPath does not exist: ${repoPath}`);
  }
  const repo = options.repo || path.basename(repoPath);
  const repoUrl = options.repoUrl || options["repo-url"] || `https://github.com/${repo}`;
  const commit = options.commit || "HEAD";
  const includeLowConfidence = Boolean(
    options.includeLowConfidence ?? options["include-low-confidence"]
  );

  const allFiles = walkFiles(repoPath);
  const configFiles = getConfigFiles(allFiles, repoPath);
  const repoFrameworkContext = detectRepoFrameworkContext(allFiles, repoPath, configFiles);
  const repoBddContext = detectRepoBddContext(allFiles);
  const packageFrameworkContext = buildPackageFrameworkContext(allFiles);
  const packageBddContext = buildPackageBddContext(allFiles);
  const configCandidateResult = extractConfigCandidateDirs(allFiles, repoPath);
  const scriptCandidateResult = extractPackageScriptCandidateDirs(allFiles, repoPath);
  const configCandidateDirs = configCandidateResult.dirs;
  const scriptCandidateDirs = scriptCandidateResult.dirs;
  const candidateDirs = uniq([...configCandidateDirs, ...scriptCandidateDirs]);
  const candidates = allFiles.filter((f) => isCandidateTestFile(f, repoPath, candidateDirs));

  const project = new Project({
    compilerOptions: {
      allowJs: true,
      checkJs: false,
      jsx: 4,
      skipLibCheck: true,
      noResolve: true,
    },
    skipAddingFilesFromTsConfig: true,
    useInMemoryFileSystem: false,
  });

  const uiTestFiles = [];
  const supportOrSetupFiles = [];
  const templateFiles = [];
  const lowConfidenceCandidates = [];
  const rejectedCandidateFiles = [];
  let parseErrors = 0;

  for (const file of candidates) {
    const relPath = toPosix(path.relative(repoPath, file));
    const localFrameworkContext = fileLocalFrameworkContext(file, repoPath, configFiles, packageFrameworkContext);
    const localBddContext = fileLocalBddContext(file, repoPath, packageBddContext);
    let sourceFile;
    try {
      sourceFile = project.addSourceFileAtPath(file);
    } catch (err) {
      parseErrors++;
      rejectedCandidateFiles.push({
        file_path: relPath,
        reason: "parse_error",
        error: String(err).slice(0, 300),
      });
      continue;
    }

    let evidence;
    try {
      evidence = collectEvidence(sourceFile);
    } catch (err) {
      parseErrors++;
      rejectedCandidateFiles.push({
        file_path: relPath,
        reason: "analysis_error",
        error: String(err).slice(0, 300),
      });
      try { sourceFile.forget(); } catch (_) {}
      continue;
    }

    evidence = normalizeFrameworkAmbiguity(evidence, localFrameworkContext);
    const fileRole = classifyFileRole(relPath, evidence);
    const classification = classifyFile(evidence, relPath, localFrameworkContext, localBddContext);
    const uiActions = flattenUiActions(evidence.uiActionsByFramework);
    const inferredFrameworks = inferFrameworksForFile(evidence, localFrameworkContext, relPath);

    const record = {
      repo,
      repo_url: repoUrl,
      commit,
      file_path: relPath,
      file_url: makeFileUrl(repoUrl, commit, relPath),
      language: path.extname(file).replace(".", ""),
      detected_frameworks: inferredFrameworks,
      file_detected_frameworks: evidence.fileDetectedFrameworks,
      repo_framework_context: repoFrameworkContext,
      local_framework_context: localFrameworkContext,
      repo_bdd_context: repoBddContext,
      local_bdd_context: localBddContext,
      file_role: fileRole,
      confidence: classification.confidence,
      classification_reason: classification.reason,
      test_case_declaration_count: evidence.testCaseDeclarations.length,
      group_or_hook_declaration_count: evidence.groupOrHookDeclarations.length,
      bdd_step_declaration_count: evidence.bddStepDeclarations.length,
      ui_action_count: uiActions.length,
      cypress_custom_command_count: (evidence.cypressCustomCommandCalls || []).length,
      cypress_ui_like_custom_command_count: (evidence.cypressUiLikeCustomCommandCalls || []).length,
      cypress_non_ui_custom_command_count: (evidence.cypressNonUiCustomCommandCalls || []).length,
      cypress_control_call_count: (evidence.cypressControlCalls || []).length,
      assertion_call_count: evidence.assertionCalls.length,
      evidence: {
        imports: evidence.imports.filter((m) =>
          Object.values(UI_IMPORT_MODULES).flat().some((prefix) => m === prefix || m.startsWith(prefix + "/"))
        ).slice(0, 30),
        test_case_declarations: evidence.testCaseDeclarations.slice(0, 30),
        group_or_hook_declarations: evidence.groupOrHookDeclarations.slice(0, 30),
        bdd_step_declarations: evidence.bddStepDeclarations.slice(0, 30),
        bdd_contexts_from_imports: evidence.bddContextsFromImports,
        playwright_fixture_params: evidence.playwrightFixtureParams,
        ui_actions: uiActions.slice(0, 60),
        cypress_direct_ui_calls: evidence.cypressDirectUiCalls || [],
        cypress_custom_commands: evidence.cypressCustomCommandCalls || [],
        cypress_ui_like_custom_commands: evidence.cypressUiLikeCustomCommandCalls || [],
        cypress_non_ui_custom_commands: evidence.cypressNonUiCustomCommandCalls || [],
        cypress_control_calls: evidence.cypressControlCalls || [],
        assertion_calls: evidence.assertionCalls.slice(0, 30),
        file_detected_frameworks: evidence.fileDetectedFrameworks,
        repo_framework_context: repoFrameworkContext,
        local_framework_context: localFrameworkContext,
        repo_bdd_context: repoBddContext,
        local_bdd_context: localBddContext,
      },
    };

    if (fileRole === "template_file") {
      templateFiles.push(record);
    } else if (classification.confidence === "high" || classification.confidence === "medium") {
      if (fileRole === "test_file") {
        uiTestFiles.push(record);
      } else if (fileRole === "setup_file" || fileRole === "helper_file") {
        supportOrSetupFiles.push(record);
      } else {
        // Unknown role but strong UI-test evidence. Keep it visible as low-confidence
        // for manual validation rather than mixing it into the main inventory.
        lowConfidenceCandidates.push(record);
      }
    } else if (classification.confidence === "low") {
      lowConfidenceCandidates.push(record);
      if (includeLowConfidence && fileRole === "test_file") uiTestFiles.push(record);
    } else {
      rejectedCandidateFiles.push({
        file_path: relPath,
        reason: classification.reason,
        file_role: fileRole,
        test_case_declaration_count: evidence.testCaseDeclarations.length,
        group_or_hook_declaration_count: evidence.groupOrHookDeclarations.length,
        bdd_step_declaration_count: evidence.bddStepDeclarations.length,
        file_detected_frameworks: evidence.fileDetectedFrameworks,
        repo_framework_context: repoFrameworkContext,
        local_framework_context: localFrameworkContext,
        repo_bdd_context: repoBddContext,
        local_bdd_context: localBddContext,
        ui_action_count: uiActions.length,
        cypress_custom_command_count: (evidence.cypressCustomCommandCalls || []).length,
        cypress_ui_like_custom_command_count: (evidence.cypressUiLikeCustomCommandCalls || []).length,
        cypress_non_ui_custom_command_count: (evidence.cypressNonUiCustomCommandCalls || []).length,
        cypress_control_call_count: (evidence.cypressControlCalls || []).length,
        assertion_call_count: evidence.assertionCalls.length,
      });
    }

    try { sourceFile.forget(); } catch (_) {}
  }

  const summary = {
    repo,
    repo_url: repoUrl,
    commit,
    total_files_scanned: allFiles.length,
    candidate_test_files: candidates.length,
    detected_ui_test_files: uiTestFiles.length,
    support_or_setup_files: supportOrSetupFiles.length,
    template_files: templateFiles.length,
    low_confidence_candidates: lowConfidenceCandidates.length,
    parse_errors: parseErrors,
    config_files: configFiles,
    repo_framework_context: repoFrameworkContext,
    repo_bdd_context: repoBddContext,
    config_candidate_dirs: configCandidateDirs.map((d) => toPosix(path.relative(repoPath, d))),
    package_script_candidate_dirs: scriptCandidateDirs.map((d) => toPosix(path.relative(repoPath, d))),
    candidate_dir_sources: [...configCandidateResult.sources, ...scriptCandidateResult.sources],
    framework_distribution: uiTestFiles.reduce((acc, f) => {
      for (const fw of f.detected_frameworks || []) acc[fw] = (acc[fw] || 0) + 1;
      return acc;
    }, {}),
    confidence_distribution: uiTestFiles.reduce((acc, f) => {
      acc[f.confidence] = (acc[f.confidence] || 0) + 1;
      return acc;
    }, {}),
  };

  return {
    repo,
    repo_url: repoUrl,
    commit,
    summary,
    config_files: configFiles,
    repo_framework_context: repoFrameworkContext,
    ui_test_files: uiTestFiles,
    support_or_setup_files: supportOrSetupFiles,
    template_files: templateFiles,
    low_confidence_candidates: lowConfidenceCandidates,
    rejected_candidate_files: rejectedCandidateFiles.slice(0, 500),
  };
}

if (require.main === module) {
  const args = parseArgs(process.argv);
  const rawRepoPath = args["repo-path"];
  const outputPath = args["output"] ? path.resolve(args["output"]) : null;

  if (!rawRepoPath || !fs.existsSync(path.resolve(rawRepoPath))) {
    console.error(
      "Usage: node analyze_repo_ui_files.cjs --repo-path <path> --repo owner/name [--repo-url url] [--commit sha] [--output file] [--include-low-confidence]"
    );
    process.exit(2);
  }

  const result = analyzeRepo({
    repoPath: rawRepoPath,
    repo: args["repo"],
    repoUrl: args["repo-url"],
    commit: args["commit"],
    includeLowConfidence: args["include-low-confidence"],
  });

  if (outputPath) {
    fs.mkdirSync(path.dirname(outputPath), { recursive: true });
    fs.writeFileSync(outputPath, JSON.stringify(result, null, 2), "utf8");
  } else {
    process.stdout.write(JSON.stringify(result, null, 2));
  }
}

module.exports = { analyzeRepo };
