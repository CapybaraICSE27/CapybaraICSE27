"use strict";

const UI_IMPORT_MODULES = {
  Playwright: ["@playwright/test", "playwright"],
  Cypress: ["cypress"],
  Selenium: ["selenium-webdriver"],
  WebDriverIO: ["webdriverio", "@wdio/globals", "@wdio/sync"],
  Puppeteer: ["puppeteer", "puppeteer-core"],
  TestCafe: ["testcafe"],
  Nightwatch: ["nightwatch"],
};

const BDD_IMPORT_MODULE_PREFIXES = [
  "@cucumber/cucumber",
  "cucumber",
  "playwright-bdd",
  "@badeball/cypress-cucumber-preprocessor",
  "cypress-cucumber-preprocessor",
];

const GROUP_OR_HOOK_PATTERNS = [
  /^describe$/,
  /^describe\.(only|skip|each)$/,
  /^test\.describe$/,
  /^test\.describe\.(only|skip|serial|parallel|configure)$/,
  /^fixture$/,
  /^test\.beforeEach$/,
  /^test\.afterEach$/,
  /^test\.beforeAll$/,
  /^test\.afterAll$/,
  /^test\.before$/,
  /^test\.after$/,
  /^fixture\.before$/,
  /^fixture\.after$/,
  /^fixture\.beforeEach$/,
  /^fixture\.afterEach$/,
  /^before$/,
  /^beforeEach$/,
  /^afterEach$/,
  /^afterAll$/,
  /^after$/,
];

const UI_ACTION_PATTERNS = {
  Playwright: [
    /^page\.(goto|locator|getByRole|getByText|getByLabel|getByTestId|getByPlaceholder|getByAltText|getByTitle|click|fill|type|press|hover|dragTo|selectOption|setInputFiles|evaluate)$/,
    /^page\..*\.(click|fill|type|press|hover|dragTo|selectOption|setInputFiles|isVisible|textContent|inputValue)$/,
    /^(locator|frame|dialog)\.(click|fill|type|press|hover|dragTo|selectOption|setInputFiles|isVisible|textContent|inputValue)$/,
  ],
  Cypress: [/\bcy\.(visit|get|contains|find|click|type|clear|select|check|uncheck|scrollTo|trigger|mount|findBy\w+|getBy\w+)\b/],
  Selenium: [
    /\bdriver\.(findElement|findElements|navigate|manage|switchTo|executeScript|wait)\b/,
    /\bBy\.(id|name|cssSelector|xpath|linkText|partialLinkText|className|tagName)\b/,
  ],
  WebDriverIO: [
    /\bbrowser\.(url|click|setValue|getUrl|pause|execute|reloadSession|newWindow)\b/,
    /^.*\$\s*\([^)]*\)\.(click|setValue|addValue|getText|waitForDisplayed|isDisplayed)\b/,
  ],
  Puppeteer: [/^page\.(goto|click|type|keyboard|mouse|screenshot|evaluate|select|focus|hover|setViewport)$/],
  TestCafe: [/\bSelector\s*\(/, /\bt\.(click|typeText|selectText|pressKey|navigateTo|hover|drag|setFilesToUpload)\b/],
  Nightwatch: [/\bbrowser\.(url|click|setValue|waitForElementVisible|waitForElementPresent|end|pause)\b/],
};

const SETUP_PATTERNS = {
  Cypress: [/\bcy\.(request|task|fixture|intercept|session|exec|readFile|writeFile)\b/],
  Playwright: [/\bpage\.route\b/, /\bpage\.context\b/],
  generic: [/\bprocess\.env\b/, /\bfetch\s*\(/, /\baxios\./],
};

/** Non–text-entry input sources (fixtures, env, uploads). Text typing uses companion rows. */
const INPUT_PATTERNS = [
  /\bcy\.fixture\s*\(/,
  /\bsetInputFiles\s*\(/,
  /\bsetFilesToUpload\s*\(/,
  /\bprocess\.env\b/,
  /\bcy\.intercept\s*\(/,
];

const ASSERTION_PATTERNS = [
  /\bexpect\s*\(/,
  /\bassert\./,
  /\bcy\.(should|contains)\b/,
  /\.should\b/,
  /\.(toBeVisible|toBeHidden|toHaveURL|toHaveText|toContainText|toHaveAttribute|toHaveValue|toHaveScreenshot|toEqual|toBe|toContain)\b/,
  /\bt\.expect\s*\(/,
  /\bbrowser\.(assert|expect)\./,
];

const CYPRESS_DIRECT_UI = new Set([
  "visit", "get", "contains", "find", "click", "type", "clear", "select",
  "check", "uncheck", "scrollTo", "trigger", "mount",
]);

/** Cypress Testing Library / plugin locator queries — UI query, not custom commands. */
const CYPRESS_LOCATOR_QUERY_RE =
  /^(?:find(?:All)?|get(?:All)?)By[A-Z]\w*|getElementByTestId|xpath|dataCy$/;

function isCypressLocatorQueryCommand(cmd) {
  if (!cmd) return false;
  if (CYPRESS_DIRECT_UI.has(cmd)) return true;
  return CYPRESS_LOCATOR_QUERY_RE.test(cmd);
}

/** Built-in query/state commands — not project custom commands (RQ3). */
const CYPRESS_BUILTIN = new Set([
  "focused", "window", "document", "root", "state", "url", "title",
  "location", "hash", "go", "reload",
]);

/** Chain/async utilities — not UI actions or customs. */
const CYPRESS_TEST_UTILITY = new Set([
  "then", "spy", "stub", "as", "origin",
]);

/** Subject-chain control (aliases, scopes, iteration) — not UI actions. */
const CYPRESS_SUBJECT_CONTROL = new Set([
  "within", "invoke", "its", "each", "wrap",
]);

/** cypress-real-events style terminal methods on chains. */
const CYPRESS_REAL_UI = new Set([
  "realPress", "realClick", "realType", "realHover", "realTouch",
]);

const CYPRESS_CONTROL = new Set([
  "intercept", "request", "wait", "session", "task", "exec", "readFile",
  "writeFile", "fixture", "log", "wrap", "clock", "tick", "reload", "viewport",
]);

/** Cypress cookie/session surface — not custom commands. */
const CYPRESS_BROWSER_CONTEXT = new Set([
  "setCookie", "clearCookie", "clearCookies", "getCookie", "getCookies",
]);

/** Text-entry methods: method -> default index of primary value argument. */
const TEXT_ENTRY_VALUE_ARG = {
  fill: 0,
  type: 0,
  typeText: 1,
  setValue: 0,
  addValue: 0,
  press: 0,
  realType: 0,
  realPress: 0,
  selectOption: 0,
  setInputFiles: 0,
  selectFile: 0,
};

/** Only emit input companions from these CallExpression callee methods. */
const TEXT_ENTRY_METHODS = new Set(Object.keys(TEXT_ENTRY_VALUE_ARG));

/** Cypress assertion matcher strings — never treat as typed input values. */
const CYPRESS_ASSERT_MATCHER_VALUES = new Set([
  "have.value", "have.prop", "have.length", "have.text", "have.class",
  "have.attr", "have.id", "have.css", "have.data", "have.descendants",
  "be.visible", "be.hidden", "be.focused", "be.enabled", "be.disabled",
  "be.checked", "be.selected", "not.exist", "not.be.visible", "not.have.class",
  "contain.text", "contain.value", "include.text", "match", "exist",
]);

const IGNORE_DIR_NAMES = new Set([
  "node_modules", ".git", "dist", "build", "coverage", ".next", ".nuxt",
  ".cache", ".turbo", ".vercel", "vendor", "out", "tmp", "temp",
]);

module.exports = {
  UI_IMPORT_MODULES,
  BDD_IMPORT_MODULE_PREFIXES,
  GROUP_OR_HOOK_PATTERNS,
  UI_ACTION_PATTERNS,
  SETUP_PATTERNS,
  INPUT_PATTERNS,
  ASSERTION_PATTERNS,
  CYPRESS_DIRECT_UI,
  CYPRESS_LOCATOR_QUERY_RE,
  isCypressLocatorQueryCommand,
  CYPRESS_BUILTIN,
  CYPRESS_TEST_UTILITY,
  CYPRESS_SUBJECT_CONTROL,
  CYPRESS_REAL_UI,
  CYPRESS_CONTROL,
  CYPRESS_BROWSER_CONTEXT,
  TEXT_ENTRY_VALUE_ARG,
  TEXT_ENTRY_METHODS,
  CYPRESS_ASSERT_MATCHER_VALUES,
  IGNORE_DIR_NAMES,
};
