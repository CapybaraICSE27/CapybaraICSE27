"use strict";

const path = require("path");
const { Node } = require("ts-morph");
const {
  loadTsconfigPaths,
  resolveImport,
  findExportedSymbol,
  resolveMethodCall,
  resolveSymbolTargetFromCall,
  resolveNamespaceMember,
  isImportCallable,
  isNamespaceMemberCallable,
  buildImportMap,
  isSkippedPath,
  isCallableSymbol,
  clearImportCallableCache,
} = require("./importResolver");
const {
  buildCustomCommandRegistry,
  resolveCypressRegistryCall,
  resolveCypressTaskCall,
  hasStructuredCypressTaskHandlerEvidence,
} = require("./customCommandRegistry");
const { buildHookFeaturesByKey, testHasHookUi, expandedFeatureDedupeKey } = require("./expandedOutput");
const { buildHookCallbackIndex, expandHookCustomCommandsForRepo } = require("./hookExpansion");
const { walkNodeForFeatures } = require("../phase2b/directFeatureExtractor");
const { buildPageSymbolOrigins } = require("../phase2b/pageSymbolOrigins");
const { scanFunctionBodyPhaseHints } = require("../phase2b/setupTeardownPatternExtractor");
const { extractLocatorInfo } = require("../phase2b/astPatternExtractor");
const {
  buildPlaywrightFixtureRegistry,
  fixtureSourceKind,
  fixtureTargetFile,
} = require("./playwrightFixtureRegistry");
const {
  captureControlFlowStackAtNode,
  findEnclosingFunctionBody,
} = require("../phase2b/controlFlowEnclosure");
const {
  CYPRESS_DIRECT_UI,
  CYPRESS_CONTROL,
  CYPRESS_BUILTIN,
  CYPRESS_BROWSER_CONTEXT,
  CYPRESS_TEST_UTILITY,
  CYPRESS_SUBJECT_CONTROL,
  isCypressLocatorQueryCommand,
} = require("../shared/patterns");
const { toPosix } = require("../shared/utils");
const { getCallbackArgFromCall } = require("../shared/identifiers");
const { helperEdgeDedupeKey } = require("./helperEdgeUtils");
const {
  isFrameworkChainOrUtilityCall,
  isPageObjectBuiltinUiCall,
  shouldReportUnresolved,
} = require("./helperCallFilters");

const ASSERTION_CHAIN_METHODS = new Set([
  "toBe", "toEqual", "toStrictEqual", "toBeVisible", "toBeHidden", "toBeTruthy", "toBeFalsy",
  "toContain", "toHaveLength", "toHaveText", "toHaveURL", "toHaveAttribute", "toHaveValue",
  "toHaveScreenshot", "toMatch", "toThrow", "toBeGreaterThan", "toBeLessThan", "toBeNull",
  "toBeUndefined", "toBeDefined", "toBeChecked", "toBeDisabled", "toBeEnabled", "toBeEmpty",
  "resolves", "rejects",
]);

function getCalleeName(callExpr) {
  const expr = callExpr.getExpression();
  if (Node.isIdentifier(expr)) return expr.getText();
  if (Node.isPropertyAccessExpression(expr)) return expr.getName();
  return expr.getText();
}

function rootIdentifierFromExpression(expr) {
  let cur = expr;
  while (cur && Node.isPropertyAccessExpression(cur)) {
    cur = cur.getExpression();
  }
  return Node.isIdentifier(cur) ? cur.getText() : "";
}

function getFunctionBodyFromSymbol(symbol) {
  if (!symbol) return null;
  if (symbol.kind === "function") return symbol.node;
  if (symbol.kind === "variable") {
    const init = symbol.node.getInitializer();
    if (Node.isArrowFunction(init) || Node.isFunctionExpression(init)) return init;
  }
  if (symbol.kind === "method") return symbol.node;
  return null;
}

const SKIP_CALLEE_NAMES = new Set([
  "expect", "describe", "it", "test", "console", "JSON", "Object", "Array", "Math",
  "Promise", "Date", "Set", "Map", "require", "parseInt", "parseFloat", "isNaN",
  "setTimeout", "clearTimeout", "setInterval", "clearInterval", "fetch", "Boolean",
  "Number", "String", "RegExp", "Error", "Buffer", "process",
]);

function isAssertionChainCall(name, exprText) {
  if (ASSERTION_CHAIN_METHODS.has(name)) return true;
  if (/^to[A-Z]/.test(name) && /\)\s*\./.test(exprText)) return true;
  return false;
}

function isBuiltinCyCommand(cmd) {
  if (!cmd) return false;
  return (
    CYPRESS_DIRECT_UI.has(cmd) ||
    CYPRESS_CONTROL.has(cmd) ||
    CYPRESS_BUILTIN.has(cmd) ||
    CYPRESS_BROWSER_CONTEXT.has(cmd) ||
    CYPRESS_TEST_UTILITY.has(cmd) ||
    CYPRESS_SUBJECT_CONTROL.has(cmd) ||
    isCypressLocatorQueryCommand(cmd) ||
    cmd === "should" ||
    cmd === "and"
  );
}

function isCypressCustomCommandExpr(exprText, name) {
  if (!/^cy\./.test(exprText)) return false;
  const cmd = name || exprText.replace(/^cy\./, "").split("(")[0].split(".")[0];
  return !isBuiltinCyCommand(cmd);
}

function shouldExpandCall(name, exprText) {
  const info = { name, exprText, isMethod: /\./.test(exprText) };
  if (isFrameworkChainOrUtilityCall(info)) return false;
  if (isPageObjectBuiltinUiCall(info)) return false;
  if (!name || SKIP_CALLEE_NAMES.has(name)) return false;
  if (isAssertionChainCall(name, exprText)) return false;
  if (isCypressCustomCommandExpr(exprText, name)) return true;
  if (/^(page|cy|browser|t|locator|frame|dialog|Selector|expect)$/i.test(name)) return false;
  if (/^(goto|click|fill|type|visit|get|should|wait)$/i.test(name)) return false;
  if (/^[a-z]/.test(name) && /^(page|cy|browser)\./.test(exprText)) return false;
  return true;
}

function collectHelperCallsInNode(node, { allowMethods = false } = {}) {
  const calls = [];
  node.forEachDescendant((desc) => {
    if (!Node.isCallExpression(desc)) return;
    const name = getCalleeName(desc);
    let exprText = "";
    try {
      exprText = desc.getExpression().getText();
    } catch (_) {
      exprText = name;
    }
    const isMethod = Node.isPropertyAccessExpression(desc.getExpression());
    if (!shouldExpandCall(name, exprText)) return;
    if (isMethod && !allowMethods) return;
    calls.push({ call: desc, name, line: desc.getStartLineNumber(), isMethod, exprText });
  });
  return calls;
}

function collectImportedHelperNames(importMap, fromFile, repoPath, tsconfigCache, project) {
  const names = new Set();
  for (const [local, entry] of importMap.entries()) {
    if (entry.isNamespace) continue;
    const spec = entry.spec;
    if (spec && (spec.startsWith(".") || spec.startsWith("~/") || spec.startsWith("@/"))) {
      if (isImportCallable(local, fromFile, importMap, repoPath, tsconfigCache, project)) {
        names.add(local);
      }
    }
  }
  return names;
}

function shouldSeedCall(callInfo, helperNames, importMap, registry, fromFile, repoPath, tsconfigCache, project) {
  const { name, isMethod, exprText } = callInfo;
  if (isFrameworkChainOrUtilityCall(callInfo)) return false;
  if (isPageObjectBuiltinUiCall(callInfo)) return false;
  if (registry.has(name)) return true;
  if (helperNames.has(name)) return true;
  if (importMap.has(name) && isImportCallable(name, fromFile, importMap, repoPath, tsconfigCache, project)) {
    return true;
  }
  if (isMethod && isAssertionChainCall(name, exprText)) return false;
  if (isMethod) {
    const objText = exprText.split(".")[0];
    if (/^(page|cy|browser|t|locator|expect)$/i.test(objText)) return false;
    if (importMap.has(objText) && importMap.get(objText).isNamespace) {
      return isNamespaceMemberCallable(objText, name, fromFile, importMap, repoPath, tsconfigCache, project);
    }
    if (importMap.has(objText) && isImportCallable(objText, fromFile, importMap, repoPath, tsconfigCache, project)) {
      return true;
    }
    if (callInfo.call) {
      const methodResolved = resolveMethodCall(
        callInfo.call,
        importMap,
        fromFile,
        repoPath,
        tsconfigCache,
        project
      );
      if (methodResolved) return true;
    }
    if (/^[A-Z][A-Za-z0-9]*(Page|Screen|PO|Helper)$/.test(objText)) return true;
  }
  return false;
}

function queueKey(item) {
  const start = item.callExpr ? item.callExpr.getStart() : 0;
  const end = item.callExpr ? item.callExpr.getEnd() : 0;
  return `${item.fromFile}|${start || item.line}|${end}|${item.callName}`;
}

function nodeId(node, file, repoPath) {
  if (!node || !file) return "";
  const rel = toPosix(path.relative(repoPath, file));
  let start = 0;
  let end = 0;
  try {
    start = node.getStart();
    end = node.getEnd();
  } catch (_) {
    /* ignore */
  }
  return `${rel}:${start}:${end}`;
}

function callsiteId(callExpr, fromFile, repoPath, line = 0, name = "") {
  if (callExpr) return nodeId(callExpr, fromFile, repoPath);
  const rel = toPosix(path.relative(repoPath, fromFile));
  return `${rel}:${line || 0}:0:${name || ""}`;
}

function resolvedEvidence(resolved, fallbackBasis = "heuristic_name") {
  return {
    helper_expansion_evidence_basis: resolved?.expansion_evidence_basis || fallbackBasis,
    helper_expansion_confidence: resolved?.expansion_confidence || (fallbackBasis === "heuristic_name" ? "low" : "medium"),
  };
}

function taskNameFromFeature(feature) {
  try {
    const literals = JSON.parse(feature.literal_args_json || "[]");
    return literals.length ? String(literals[0]) : "";
  } catch (_) {
    return "";
  }
}

function cypressCommandKeyFromFeature(feature, registry) {
  let parts = [];
  try {
    const chain = JSON.parse(feature.callee_chain_json || "[]");
    if (Array.isArray(chain) && chain[0] === "cy" && chain.length > 1) {
      parts = chain.slice(1).map((part) => String(part || ""));
    }
  } catch (_) {
    parts = [];
  }
  if (!parts.length) {
    const m = String(feature.name || feature.raw_code || "").match(/\bcy\.([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)/);
    if (m) parts = m[1].split(".");
  }
  for (let len = parts.length; len >= 1; len -= 1) {
    const key = parts.slice(0, len).join(".");
    if (registry.has(key)) return key;
  }
  return "";
}

function summarizeResolvedSelectorBody(bodyNode, framework = "Cypress") {
  if (!bodyNode) return null;
  let best = null;
  bodyNode.forEachDescendant((node) => {
    if (best || !Node.isCallExpression(node)) return;
    const loc = extractLocatorInfo(node, framework, { pageSymbolOrigins: new Map() });
    if (!loc) return;
    const channel = loc.selector_channel_ast || loc.selector_literal_kind_ast || "";
    const strategy = loc.locator_strategy_ast || "";
    if (!channel || channel === "unknown" || !strategy || strategy === "unknown") return;
    best = {
      channel,
      strategy,
      selectorLiteral: loc.selector_literal_ast || "",
      basis: "resolved_helper_body_locator",
    };
  });
  return best;
}

function attachResolvedSelectorSummary(feature, summary, helperName) {
  if (!feature || !summary) return;
  feature.resolved_selector_channel_ast = summary.channel;
  feature.resolved_selector_strategy_ast = summary.strategy;
  feature.resolved_selector_evidence_basis_ast = summary.basis;
  feature.resolved_selector_helper_name_ast = helperName || "";
  if (summary.selectorLiteral) {
    feature.resolved_selector_literal_ast = String(summary.selectorLiteral).slice(0, 200);
  }
}

function expandHelpersForRepo({
  project,
  repoPath,
  testCases,
  directFeatures,
  manifestByFile,
  repoMeta,
  globalSupportHooks,
  maxDepth,
  maxHelperFiles,
}) {
  clearImportCallableCache();
  const tsconfigCache = loadTsconfigPaths(repoPath);
  const registry = buildCustomCommandRegistry(project, repoPath);
  const hookByKey = buildHookFeaturesByKey(directFeatures);
  const testFilePaths = [...new Set(testCases.map((tc) => tc.file_path).filter(Boolean))];
  const hookCallbackIndex = buildHookCallbackIndex(
    project,
    repoPath,
    globalSupportHooks || [],
    testFilePaths
  );
  const expandedFeatures = [];
  const expandedSeen = new Set();
  const helperEdges = [];
  const edgeSeen = new Set();
  const unresolvedCalls = [];
  const selectorSummaryByRegistryKey = new Map();

  function pushHelperEdge(edge) {
    const key = helperEdgeDedupeKey(edge);
    if (edgeSeen.has(key)) return;
    edgeSeen.add(key);
    helperEdges.push(edge);
  }

  function pushExpandedFeature(f) {
    const key = expandedFeatureDedupeKey(f);
    if (expandedSeen.has(key)) return;
    expandedSeen.add(key);
    expandedFeatures.push(f);
  }

  const directByTest = new Map();
  for (const f of directFeatures) {
    if (f.is_shared_hook_feature || !f.test_id) continue;
    const key = `${f.repo || repoMeta.repo}::${f.test_id}`;
    if (!directByTest.has(key)) directByTest.set(key, []);
    directByTest.get(key).push(f);
  }

  function isUnresolvedCyCustom(callExpr) {
    if (!callExpr || !Node.isCallExpression(callExpr)) return false;
    try {
      let expr = callExpr.getExpression();
      if (!Node.isPropertyAccessExpression(expr)) return false;
      while (Node.isPropertyAccessExpression(expr)) {
        expr = expr.getExpression();
      }
      return expr.getText() === "cy";
    } catch (_) {
      return false;
    }
  }

  function resolveCall(fromFile, callName, importMap, callExpr) {
    if (callExpr) {
      const cyResolved = resolveCypressRegistryCall(callExpr, registry);
      if (cyResolved) return cyResolved;
      const symbolResolved = resolveSymbolTargetFromCall(callExpr, fromFile);
      if (symbolResolved) return symbolResolved;
    }
    if (registry.has(callName)) {
      const reg = registry.get(callName);
      return {
        target: reg.node,
        file: reg.file,
        kind: reg.kind,
        command_role_ast: reg.command_role_ast || "",
        command_role_basis_ast: reg.command_role_basis_ast || "",
        command_role_confidence_ast: reg.command_role_confidence_ast || "",
        expansion_evidence_basis: "cypress_registry",
        expansion_confidence: "high",
      };
    }

    if (callExpr && Node.isPropertyAccessExpression(callExpr.getExpression())) {
      const pa = callExpr.getExpression();
      const obj = pa.getExpression();
      if (Node.isIdentifier(obj)) {
        const ns = resolveNamespaceMember(
          obj.getText(),
          pa.getName(),
          fromFile,
          importMap,
          repoPath,
          tsconfigCache,
          project
        );
        if (ns) return ns;
      }
      const methodRes = resolveMethodCall(callExpr, importMap, fromFile, repoPath, tsconfigCache, project);
      if (methodRes) return methodRes;
    }

    const sf = project.getSourceFile(fromFile);
    if (sf) {
      for (const fn of sf.getFunctions()) {
        if (fn.getName() === callName) {
          return {
            target: fn,
            file: fromFile,
            kind: "helper_function",
            expansion_evidence_basis: "exact_symbol",
            expansion_confidence: "high",
          };
        }
      }
      for (const vd of sf.getVariableDeclarations()) {
        if (vd.getName() === callName) {
          const init = vd.getInitializer();
          if (Node.isArrowFunction(init) || Node.isFunctionExpression(init)) {
            return {
              target: init,
              file: fromFile,
              kind: "helper_function",
              expansion_evidence_basis: "exact_symbol",
              expansion_confidence: "high",
            };
          }
        }
      }
    }

    const entry = importMap.get(callName);
    const spec = entry && typeof entry === "object" ? entry.spec : entry;
    const preferDefault = entry && typeof entry === "object" ? entry.isDefault : false;
    if (!spec) return { unresolved: "import_not_resolved" };
    const resolvedPath = resolveImport(fromFile, spec, repoPath, tsconfigCache);
    if (!resolvedPath) return { unresolved: "import_not_resolved", spec };
    if (isSkippedPath(resolvedPath, repoPath)) return { unresolved: "external_package", spec };

    const sym = findExportedSymbol(resolvedPath, callName, project, repoPath, tsconfigCache, 0, preferDefault);
    if (!sym) return { unresolved: "import_not_resolved", spec, resolvedPath: toPosix(path.relative(repoPath, resolvedPath)) };
    if (sym.kind === "class") {
      return { unresolved: "class_whole_body_skipped", spec, resolvedPath: toPosix(path.relative(repoPath, resolvedPath)) };
    }
    if (!isCallableSymbol(sym)) {
      return { unresolved: "not_callable_export", spec, resolvedPath: toPosix(path.relative(repoPath, resolvedPath)) };
    }
    const body = getFunctionBodyFromSymbol(sym);
    if (!body) return { unresolved: "import_not_resolved", spec, resolvedPath: toPosix(path.relative(repoPath, resolvedPath)) };
    return {
      target: body,
      file: resolvedPath,
      kind: "imported_helper",
      expansion_evidence_basis: "exact_symbol",
      expansion_confidence: "high",
    };
  }

  const hookExpandedByKey = expandHookCustomCommandsForRepo({
    project,
    repoPath,
    repoMeta,
    hookByKey,
    hookCallbackIndex,
    registry,
    tsconfigCache,
    maxDepth,
    maxHelperFiles,
    frameworkDefault: "Cypress",
    resolveCall,
    isUnresolvedCyCustom,
    collectHelperCallsInNode,
    shouldSeedCall,
    isCypressCustomCommandExpr,
    collectImportedHelperNames,
    pushHelperEdge,
    pushUnresolved: (row) => unresolvedCalls.push(row),
  });

  for (const testCase of testCases) {
    const absFile = path.join(repoPath, testCase.file_path);
    let sf;
    try {
      sf = project.getSourceFile(absFile) || project.addSourceFileAtPath(absFile);
    } catch (_) {
      continue;
    }
    const manifestRow = manifestByFile.get(testCase.file_path) || {};
    const importMap = buildImportMap(sf);
    const framework = testCase.framework;
    const contexts = (manifestRow.repo_framework_context || "").split(/[;|]/).filter(Boolean);
    let declarationCall = null;
    let testIdentifier = "";
    if (testCase.declaration_line) {
      declarationCall = sf
        .getDescendantsOfKind(require("ts-morph").SyntaxKind.CallExpression)
        .find((c) => c.getStartLineNumber() === testCase.declaration_line);
      if (declarationCall) {
        testIdentifier = rootIdentifierFromExpression(declarationCall.getExpression());
      }
    }
    const fixtureRegistry = buildPlaywrightFixtureRegistry({
      project,
      repoPath,
      sourceFile: sf,
      importMap,
      tsconfigCache,
      testIdentifier,
    });

    const testKey = `${repoMeta.repo}::${testCase.test_id}`;
    const directHelpers = directByTest.get(testKey) || [];
    const helperNames = new Set([
      ...collectImportedHelperNames(importMap, absFile, repoPath, tsconfigCache, project),
    ]);
    for (const f of directHelpers) {
      const m = String(f.name || "").match(/([A-Za-z_$][\w$]*)$/);
      const name = m ? m[1] : "";
      if (!name) continue;
      if (f.feature_type === "custom_command_call" || registry.has(name)) {
        helperNames.add(name);
        continue;
      }
      if (f.feature_type === "helper_call") {
        if (
          isImportCallable(name, absFile, importMap, repoPath, tsconfigCache, project) ||
          registry.has(name)
        ) {
          helperNames.add(name);
        }
      }
    }

    const testBodyCalls = [];
    let expectedCb = null;
    if (declarationCall) {
      expectedCb = getCallbackArgFromCall(declarationCall);
    }

    if (expectedCb) {
      testBodyCalls.push(...collectHelperCallsInNode(expectedCb, { allowMethods: true }));
    } else {
      for (const fn of sf.getDescendants()) {
        if (!Node.isArrowFunction(fn) && !Node.isFunctionExpression(fn)) continue;
        const start = fn.getStartLineNumber();
        const tcStart = testCase.callback_start_line ?? testCase.start_line;
        const tcEnd = testCase.callback_end_line ?? testCase.end_line;
        if (start < tcStart - 2 || start > tcEnd + 2) continue;
        testBodyCalls.push(...collectHelperCallsInNode(fn, { allowMethods: true }));
      }
    }

    const seedCalls = testBodyCalls.filter((c) =>
      shouldSeedCall(c, helperNames, importMap, registry, absFile, repoPath, tsconfigCache, project)
    );

    const seededNames = new Set(seedCalls.map((c) => c.name));
    for (const f of directHelpers) {
      if (f.feature_type !== "custom_command_call") continue;
      const m = String(f.name || "").match(/([A-Za-z_$][\w$]*)$/);
      const cmdName = m ? m[1] : "";
      if (!cmdName || seededNames.has(cmdName)) continue;
      seededNames.add(cmdName);
      let callExpr = null;
      try {
        callExpr = sf
          .getDescendantsOfKind(require("ts-morph").SyntaxKind.CallExpression)
          .find((c) => c.getStartLineNumber() === f.line);
      } catch (_) {
        /* ignore */
      }
      seedCalls.push({
        call: callExpr,
        name: cmdName,
        line: f.line || 0,
        isMethod: true,
        exprText: callExpr ? callExpr.getExpression().getText() : `cy.${cmdName}`,
      });
    }

    const testBodyRoot = expectedCb || null;

    const fixturesUsed = new Set(
      Array.isArray(testCase.fixtures_used)
        ? testCase.fixtures_used
        : String(testCase.fixtures_used || "")
            .split(/[;|]/)
            .map((s) => s.trim())
            .filter(Boolean)
    );
    for (const fixtureDefs of fixtureRegistry.values()) {
      for (const fixture of fixtureDefs) {
        if (!fixture.auto && !fixturesUsed.has(fixture.name)) continue;
        const fixtureSf =
          project.getSourceFile(fixture.file) ||
          (() => {
            try {
              return project.addSourceFileAtPath(fixture.file);
            } catch (_) {
              return null;
            }
          })();
        const fixtureImportMap = fixtureSf ? buildImportMap(fixtureSf) : new Map();
        const fixtureKind = fixtureSourceKind(fixture);
        const fixtureNodeId = nodeId(fixture.callback, fixture.file, repoPath);
        const fixtureRelFile = fixtureTargetFile(fixture, repoPath);
        const fixtureProvenanceMap = new Map([
          [
            fixture.name,
            {
              declaredBy: "test.extend",
              scope: fixture.auto ? "auto" : "test",
            },
          ],
        ]);
        const fixtureCtx = {
          repo: repoMeta.repo,
          test_id: testCase.test_id,
          file_path: testCase.file_path,
          phase1_confidence: testCase.phase1_confidence,
          framework,
          contexts,
          source_kind: fixtureKind,
          helper_name: fixture.name,
          helper_depth: 1,
          importMap: fixtureImportMap,
          astCtx: {
            pageSymbolOrigins: fixtureSf ? buildPageSymbolOrigins(fixtureSf) : new Map(),
            fixtureProvenanceMap,
          },
          context_node: fixture.callback,
        };
        const fixtureFeats = [];
        walkNodeForFeatures(fixture.callback, fixtureCtx, fixtureFeats);
        for (const f of fixtureFeats) {
          pushExpandedFeature({
            ...f,
            source_kind: fixtureKind,
            helper_name: fixture.name,
            helper_depth: 1,
            helper_resolution_kind: fixtureKind,
            helper_resolution_status: "resolved",
            helper_expansion_evidence_basis: "playwright_test_extend_fixture",
            helper_expansion_confidence: "high",
            helper_target_node_id: fixtureNodeId,
            target_file: fixtureRelFile,
            fixture_param_name: fixture.name,
            fixture_declared_by: "test.extend",
            fixture_scope: fixture.auto ? "auto" : "test",
            fixture_auto: Boolean(fixture.auto),
            fixture_target_file: fixtureRelFile,
            fixture_resolution_status: "resolved",
            attached_from_fixture: true,
          });
        }
      }
    }

    const queue = seedCalls.map((c) => {
      const callRoot =
        testBodyRoot ||
        (c.call && findEnclosingFunctionBody(c.call)) ||
        null;
      return {
        callName: c.name,
        callExpr: c.call,
        from: "test_body",
        depth: 1,
        fromFile: absFile,
        line: c.line,
        helper_chain: [c.name],
        helper_node_chain: [],
        inheritedCfStack: c.call
          ? captureControlFlowStackAtNode(callRoot || sf, c.call, null)
          : null,
      };
    });

    const visitedFiles = new Set();
    const queued = new Set();
    let helperFilesUsed = 0;

    while (queue.length > 0) {
      const item = queue.shift();
      const qk = queueKey(item);
      if (queued.has(qk)) continue;
      queued.add(qk);

      if (item.depth > maxDepth) {
        const helperCallsiteId = callsiteId(item.callExpr, item.fromFile, repoPath, item.line, item.callName);
        if (shouldReportUnresolved(item, item.callExpr)) {
          unresolvedCalls.push({
            repo: repoMeta.repo,
            test_id: testCase.test_id,
            call: item.callName,
            source_file: testCase.file_path,
            line: item.line,
            reason: "max_depth_exceeded",
            helper_callsite_id: helperCallsiteId,
            helper_expansion_evidence_basis: "unresolved",
            helper_expansion_confidence: "low",
          });
        }
        continue;
      }

      const fromSf = project.getSourceFile(item.fromFile);
      const fileImportMap = fromSf ? buildImportMap(fromSf) : importMap;
      const resolved = resolveCall(item.fromFile, item.callName, fileImportMap, item.callExpr);

      if (!resolved || resolved.unresolved) {
        const helperCallsiteId = callsiteId(item.callExpr, item.fromFile, repoPath, item.line, item.callName);
        let reason = resolved?.unresolved || "import_not_resolved";
        if (isUnresolvedCyCustom(item.callExpr)) {
          reason = "cypress_command_not_resolved";
        }
        if (shouldReportUnresolved(item, item.callExpr)) {
          unresolvedCalls.push({
            repo: repoMeta.repo,
            test_id: testCase.test_id,
            call: item.callName,
            source_file: testCase.file_path,
            line: item.line,
            reason,
            helper_callsite_id: helperCallsiteId,
            helper_expansion_evidence_basis: "unresolved",
            helper_expansion_confidence: "low",
          });
        }
        pushHelperEdge({
          repo: repoMeta.repo,
          test_id: testCase.test_id,
          from: item.from,
          to: item.callName,
          target_file: resolved?.resolvedPath || "",
          resolved: false,
          depth: item.depth,
          helper_callsite_id: helperCallsiteId,
          helper_expansion_evidence_basis: "unresolved",
          helper_expansion_confidence: "low",
        });
        continue;
      }

      const helperTargetNodeId = nodeId(resolved.target, resolved.file, repoPath);
      const helperCallsiteId = callsiteId(item.callExpr, item.fromFile, repoPath, item.line, item.callName);
      const helperNodeChain = item.helper_node_chain || [];
      if (helperTargetNodeId && helperNodeChain.includes(helperTargetNodeId)) {
        if (shouldReportUnresolved(item, item.callExpr)) {
          unresolvedCalls.push({
            repo: repoMeta.repo,
            test_id: testCase.test_id,
            call: item.callName,
            source_file: testCase.file_path,
            line: item.line,
            reason: "helper_cycle_detected",
            helper_callsite_id: helperCallsiteId,
            helper_target_node_id: helperTargetNodeId,
          });
        }
        continue;
      }
      const nextHelperNodeChain = helperTargetNodeId
        ? [...helperNodeChain, helperTargetNodeId]
        : helperNodeChain;
      const evidence = resolvedEvidence(resolved);

      if (helperFilesUsed >= maxHelperFiles) {
        if (shouldReportUnresolved(item, item.callExpr)) {
          unresolvedCalls.push({
            repo: repoMeta.repo,
            test_id: testCase.test_id,
            call: item.callName,
            source_file: testCase.file_path,
            line: item.line,
            reason: "max_files_exceeded",
            helper_callsite_id: helperCallsiteId,
            helper_target_node_id: helperTargetNodeId,
          });
        }
        continue;
      }

      if (!visitedFiles.has(resolved.file)) {
        visitedFiles.add(resolved.file);
        helperFilesUsed += 1;
      }

      const helperSf =
        project.getSourceFile(resolved.file) ||
        (() => {
          try {
            return project.addSourceFileAtPath(resolved.file);
          } catch (_) {
            return null;
          }
        })();
      const pageSymbolOrigins = helperSf ? buildPageSymbolOrigins(helperSf) : new Map();

      const ctx = {
        repo: repoMeta.repo,
        test_id: testCase.test_id,
        file_path: testCase.file_path,
        phase1_confidence: testCase.phase1_confidence,
        framework,
        contexts,
        source_kind: "test_body",
        helper_name: item.callName,
        helper_depth: item.depth,
        importMap: fileImportMap,
        astCtx: { pageSymbolOrigins, fixtureProvenanceMap: new Map() },
        initialCfStack: item.inheritedCfStack || null,
      };

      const body = resolved.target;
      ctx.context_node = body;
      const selectorSummary = summarizeResolvedSelectorBody(body, framework);
      const feats = [];
      walkNodeForFeatures(body, ctx, feats);
      const bodyPhases = scanFunctionBodyPhaseHints(body);
      let helperBodyPhaseHint = "";
      if (bodyPhases.hasSetup && bodyPhases.hasTeardown) helperBodyPhaseHint = "setup_and_teardown";
      else if (bodyPhases.hasTeardown) helperBodyPhaseHint = "teardown";
      else if (bodyPhases.hasSetup) helperBodyPhaseHint = "setup";

      for (const f of feats) {
        const outFeature = {
          ...f,
          source_kind: resolved.kind,
          helper_name: item.callName,
          helper_depth: item.depth,
          helper_call_line: item.line,
          helper_call_start_offset: item.callExpr ? item.callExpr.getStart() : 0,
          helper_call_end_offset: item.callExpr ? item.callExpr.getEnd() : 0,
          helper_callsite_id: helperCallsiteId,
          helper_target_node_id: helperTargetNodeId,
          helper_resolution_kind: resolved.kind,
          ...evidence,
          target_file: toPosix(path.relative(repoPath, resolved.file)),
          helper_resolution_status: "resolved",
        };
        attachResolvedSelectorSummary(outFeature, selectorSummary, item.callName);
        pushExpandedFeature({
          ...outFeature,
        });
      }

      const edge = {
        repo: repoMeta.repo,
        test_id: testCase.test_id,
        from: item.from,
        to: item.callName,
        target_file: toPosix(path.relative(repoPath, resolved.file)),
        resolved: true,
        depth: item.depth,
        call_line: item.line,
        call_start_offset: item.callExpr ? item.callExpr.getStart() : 0,
        call_end_offset: item.callExpr ? item.callExpr.getEnd() : 0,
        helper_callsite_id: helperCallsiteId,
        helper_target_node_id: helperTargetNodeId,
        helper_resolution_kind: resolved.kind,
        ...evidence,
        helper_body_phase_hint_ast: helperBodyPhaseHint,
      };
      attachResolvedSelectorSummary(edge, selectorSummary, item.callName);
      pushHelperEdge(edge);

      if (item.depth < maxDepth) {
        const nested = collectHelperCallsInNode(body, { allowMethods: true });
        for (const n of nested) {
          if (
            !shouldSeedCall(n, helperNames, fileImportMap, registry, resolved.file, repoPath, tsconfigCache, project)
          ) {
            continue;
          }
          queue.push({
            callName: n.name,
            callExpr: n.call,
            from: item.callName,
            depth: item.depth + 1,
            fromFile: resolved.file,
            line: n.line,
            helper_chain: [...item.helper_chain, n.name],
            helper_node_chain: nextHelperNodeChain,
            inheritedCfStack: captureControlFlowStackAtNode(
              body,
              n.call,
              item.inheritedCfStack || null
            ),
          });
        }
      }
    }

    const hasExpandedFromHelpers = expandedFeatures.some(
      (f) => f.test_id === testCase.test_id && f.feature_type === "ui_action" && (f.helper_depth || 0) > 0
    );
    const hasHookUi = testHasHookUi(testCase, hookByKey, hookExpandedByKey);
    testCase.has_hook_ui_actions = hasHookUi;
    testCase.has_helper_expanded_ui_actions = hasExpandedFromHelpers;
    testCase.has_expanded_ui_actions = hasExpandedFromHelpers || hasHookUi;
  }

  function enrichCypressCommandRoles(features, registry) {
    for (const f of features) {
      if (f.feature_type !== "custom_command_call") continue;
      const name = String(f.name || "");
      if (!name.startsWith("cy.")) continue;
      const cmd = name.slice(3);
      const reg = registry.get(cmd);
      if (reg && reg.command_role_ast) {
        f.cypress_command_role_ast = reg.command_role_ast;
        f.cypress_command_role_basis_ast = reg.command_role_basis_ast || "";
        f.cypress_command_role_confidence_ast = reg.command_role_confidence_ast || "";
      }
    }
  }

  function enrichCypressTaskRoles(features, registry) {
    for (const f of features) {
      const name = String(f.name || "");
      let isTask = name === "cy.task";
      if (!isTask) {
        try {
          const chain = JSON.parse(f.callee_chain_json || "[]");
          isTask = Array.isArray(chain) && chain[0] === "cy" && chain[chain.length - 1] === "task";
        } catch (_) {
          isTask = false;
        }
      }
      if (!isTask) continue;
      const taskName = taskNameFromFeature(f);
      const resolved = resolveCypressTaskCall(taskName, registry);
      if (!resolved) continue;
      f.cypress_task_name_ast = taskName;
      f.cypress_task_role_ast = resolved.task_role_ast || "";
      f.cypress_task_role_basis_ast = resolved.task_role_basis_ast || "";
      f.cypress_task_role_confidence_ast = resolved.task_role_confidence_ast || "";
      f.cypress_task_handler_file = resolved.file ? toPosix(path.relative(repoPath, resolved.file)) : "";
      f.cypress_task_handler_node_id = nodeId(resolved.target, resolved.file, repoPath);
      if (
        hasStructuredCypressTaskHandlerEvidence(resolved) &&
        (resolved.task_role_ast === "test_data_setup" || resolved.task_role_ast === "setup_or_state_flow")
      ) {
        f.framework_api_category = "backend_task";
        f.framework_api_category_basis_ast = "ast_cypress_task_handler";
      }
    }
  }

  function selectorSummaryForRegistryKey(key) {
    if (!key || !registry.has(key)) return null;
    if (selectorSummaryByRegistryKey.has(key)) return selectorSummaryByRegistryKey.get(key);
    const reg = registry.get(key);
    const summary = summarizeResolvedSelectorBody(reg.node, "Cypress");
    selectorSummaryByRegistryKey.set(key, summary);
    return summary;
  }

  function enrichResolvedSelectorFields(features, registry) {
    for (const f of features) {
      if (f.resolved_selector_channel_ast) continue;
      const key = cypressCommandKeyFromFeature(f, registry);
      if (!key) continue;
      const summary = selectorSummaryForRegistryKey(key);
      if (!summary) continue;
      attachResolvedSelectorSummary(f, summary, key);
    }
  }

  enrichCypressCommandRoles(directFeatures, registry);
  enrichCypressCommandRoles(expandedFeatures, registry);
  enrichCypressTaskRoles(directFeatures, registry);
  enrichCypressTaskRoles(expandedFeatures, registry);
  enrichResolvedSelectorFields(directFeatures, registry);
  enrichResolvedSelectorFields(expandedFeatures, registry);

  return { expandedFeatures, helperEdges, unresolvedCalls, hookByKey, hookExpandedByKey };
}

module.exports = { expandHelpersForRepo };
