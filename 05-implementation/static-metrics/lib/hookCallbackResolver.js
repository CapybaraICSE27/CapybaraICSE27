"use strict";

const path = require("path");
const { SyntaxKind, Node } = require("ts-morph");
const { getCallbackArgFromCall } = require("../../test-feature-extraction/lib/shared/identifiers");
const {
  buildImportMap,
  resolveImport,
  findExportedSymbol,
  isCallableSymbol,
} = require("../../test-feature-extraction/lib/phase2c/importResolver");
const { loadTsconfigPaths } = require("../../test-feature-extraction/lib/phase2c/importResolver");
const { toPosix } = require("../../test-feature-extraction/lib/shared/utils");

function hookLookupKey(testFilePath, hookInstanceKey) {
  const k = String(hookInstanceKey || "");
  if (k.startsWith("support:")) return k;
  const fp = toPosix(String(testFilePath || ""));
  return fp ? `${fp}::${k}` : k;
}

let tsconfigCacheByRepo = new Map();

function getTsconfigCache(repoPath) {
  const key = path.resolve(repoPath);
  if (!tsconfigCacheByRepo.has(key)) {
    tsconfigCacheByRepo.set(key, loadTsconfigPaths(key));
  }
  return tsconfigCacheByRepo.get(key);
}

function clearTsconfigCacheForTests() {
  tsconfigCacheByRepo = new Map();
}

function findHookCallAtLine(sourceFile, line, hookKind) {
  const want = String(hookKind || "").toLowerCase();
  for (const call of sourceFile.getDescendantsOfKind(SyntaxKind.CallExpression)) {
    if (call.getStartLineNumber() !== line) continue;
    try {
      const expr = call.getExpression().getText().toLowerCase();
      if (expr.includes(want)) return call;
    } catch (_) {
      /* ignore */
    }
  }
  return null;
}

function referenceNameFromArg(arg) {
  if (!arg) return null;
  if (Node.isIdentifier(arg)) return arg.getText();
  if (Node.isPropertyAccessExpression(arg)) return arg.getName();
  return null;
}

function findLocalCallable(sourceFile, name) {
  for (const fn of sourceFile.getFunctions()) {
    if (fn.getName() === name) {
      return { kind: "function", node: fn };
    }
  }
  for (const vd of sourceFile.getVariableDeclarations()) {
    if (vd.getName() !== name) continue;
    const init = vd.getInitializer();
    if (init && (Node.isArrowFunction(init) || Node.isFunctionExpression(init))) {
      return { kind: "variable", node: vd };
    }
  }
  return null;
}

function unwrapReturnedHookBody(init, sourceFile) {
  if (!init) return null;
  if (Node.isArrowFunction(init) || Node.isFunctionExpression(init)) {
    return init;
  }
  if (!Node.isCallExpression(init)) return null;

  let callee = init.getExpression();
  let refName = null;
  if (Node.isIdentifier(callee)) {
    refName = callee.getText();
  } else if (Node.isPropertyAccessExpression(callee)) {
    refName = callee.getName();
  }
  if (!refName) return null;

  const local = findLocalCallable(sourceFile, refName);
  const factory = bodyNodeFromSymbol(local);
  if (!factory || !Node.isArrowFunction(factory)) return null;

  const inner = factory.getBody();
  if (Node.isArrowFunction(inner) || Node.isFunctionExpression(inner)) {
    return inner;
  }
  if (Node.isBlock(inner)) return factory;
  return null;
}

function bodyNodeFromSymbol(sym, sourceFile = null) {
  if (!sym) return null;
  if (sym.kind === "function") {
    const n = sym.node;
    if (
      Node.isFunctionDeclaration(n) ||
      Node.isFunctionExpression(n) ||
      Node.isArrowFunction(n)
    ) {
      return n;
    }
  }
  if (sym.kind === "variable") {
    const init = sym.node.getInitializer?.();
    if (init && (Node.isArrowFunction(init) || Node.isFunctionExpression(init))) {
      return init;
    }
    if (init && sourceFile) {
      return unwrapReturnedHookBody(init, sourceFile);
    }
  }
  return null;
}

function resolveImportPath(absFile, spec, repoPath, tsconfigCache) {
  const direct = resolveImport(absFile, spec, repoPath, tsconfigCache);
  if (direct) return direct;
  const altExts = [".mts", ".mjs", ".ts", ".js", ".tsx", ".jsx"];
  const m = String(spec || "").match(/^(.+)(\.[^./]+)$/);
  if (!m) return null;
  const base = m[1];
  for (const ext of altExts) {
    if (ext === m[2]) continue;
    const alt = resolveImport(absFile, base + ext, repoPath, tsconfigCache);
    if (alt) return alt;
  }
  return null;
}

function resolveImportedCallable(name, sourceFile, absFile, repoPath, project) {
  const importMap = buildImportMap(sourceFile);
  const entry = importMap.get(name);
  if (!entry || entry.isNamespace) return null;

  const tsconfigCache = getTsconfigCache(repoPath);
  const resolvedPath = resolveImportPath(absFile, entry.spec, repoPath, tsconfigCache);
  if (!resolvedPath) return null;

  const exportName = entry.isDefault ? "default" : name;
  const sym = findExportedSymbol(
    resolvedPath,
    exportName,
    project,
    repoPath,
    tsconfigCache,
    0,
    entry.isDefault
  );
  if (!sym) return null;

  let sf;
  try {
    sf = project.getSourceFile(resolvedPath) || project.addSourceFileAtPath(resolvedPath);
  } catch (_) {
    sf = null;
  }
  const body = bodyNodeFromSymbol(sym, sf);
  if (body) return body;
  return isCallableSymbol(sym) ? bodyNodeFromSymbol(sym, sf) : null;
}

/**
 * Resolve hook callback body: inline callback, same-file function, or imported helper.
 */
function resolveHookCallbackBody(hook, sourceFile, repoPath, project) {
  if (hook.callback) {
    return { body: hook.callback, hook_metrics_match_mode: hook.metrics_match_mode || "exact" };
  }

  const line = hook.hook_call_line;
  const parsedKind = hook.source_kind || hook.hookName || "";
  const call = findHookCallAtLine(sourceFile, line, parsedKind);
  if (!call) {
    return { body: null, hook_metrics_match_mode: null };
  }

  const inline = getCallbackArgFromCall(call);
  if (inline) {
    return { body: inline, hook_metrics_match_mode: "inline_at_call" };
  }

  const args = call.getArguments();
  const refName = referenceNameFromArg(args[0]);
  if (!refName) {
    return { body: null, hook_metrics_match_mode: null };
  }

  const local = findLocalCallable(sourceFile, refName);
  const localBody = bodyNodeFromSymbol(local, sourceFile);
  if (localBody) {
    return { body: localBody, hook_metrics_match_mode: "reference_local" };
  }

  const absFile = sourceFile.getFilePath();
  const importedBody = resolveImportedCallable(
    refName,
    sourceFile,
    absFile,
    repoPath,
    project
  );
  if (importedBody) {
    return { body: importedBody, hook_metrics_match_mode: "reference_import" };
  }

  return { body: null, hook_metrics_match_mode: "reference_unresolved" };
}

module.exports = {
  hookLookupKey,
  findHookCallAtLine,
  resolveHookCallbackBody,
  getTsconfigCache,
  clearTsconfigCacheForTests,
};
