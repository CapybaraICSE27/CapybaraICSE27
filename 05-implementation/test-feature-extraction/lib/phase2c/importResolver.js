"use strict";

const fs = require("fs");
const path = require("path");
const { SyntaxKind, Node } = require("ts-morph");
const { IGNORE_DIR_NAMES } = require("../shared/patterns");
const { toPosix } = require("../shared/utils");

function loadTsconfigPaths(repoPath) {
  const pathsMap = {};
  let baseUrl = repoPath;
  const candidates = [];

  function walkConfigs(dir, depth) {
    if (depth > 4) return;
    let entries = [];
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch (_) {
      return;
    }
    for (const ent of entries) {
      if (ent.isFile() && /^tsconfig.*\.json$/i.test(ent.name)) {
        candidates.push(path.join(dir, ent.name));
      }
      if (ent.isDirectory() && !IGNORE_DIR_NAMES.has(ent.name) && depth < 3) {
        walkConfigs(path.join(dir, ent.name), depth + 1);
      }
    }
  }
  walkConfigs(repoPath, 0);
  if (!candidates.includes(path.join(repoPath, "tsconfig.json"))) {
    candidates.unshift(path.join(repoPath, "tsconfig.json"), path.join(repoPath, "jsconfig.json"));
  }

  for (const full of candidates) {
    if (!fs.existsSync(full)) continue;
    try {
      const raw = JSON.parse(fs.readFileSync(full, "utf-8"));
      const compiler = raw.compilerOptions || raw;
      const cfgDir = path.dirname(full);
      const bu = compiler.baseUrl
        ? path.resolve(cfgDir, compiler.baseUrl)
        : cfgDir;
      if (compiler.paths) {
        for (const [alias, targets] of Object.entries(compiler.paths)) {
          const key = alias.replace(/\*$/, "");
          pathsMap[key] = (targets || []).map((t) => path.resolve(bu, t.replace(/\*$/, "")));
        }
      }
    } catch (_) {
      /* ignore */
    }
  }
  return { pathsMap, baseUrl };
}

function isSkippedPath(absPath, repoPath = null) {
  let pathForParts = absPath;
  if (repoPath) {
    const rel = path.relative(path.resolve(repoPath), path.resolve(absPath));
    if (rel && !rel.startsWith("..") && !path.isAbsolute(rel)) {
      pathForParts = rel;
    }
  }
  const parts = pathForParts.split(/[\\/]/);
  return parts.some((p) => IGNORE_DIR_NAMES.has(p));
}

function isImplementationSourceFile(filePath) {
  if (!filePath) return false;
  if (/\.d\.ts$/i.test(filePath)) return false;
  return true;
}

function tryResolveFile(basePath) {
  const exts = ["", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"];
  for (const ext of exts) {
    const candidate = basePath + ext;
    if (fs.existsSync(candidate) && fs.statSync(candidate).isFile() && isImplementationSourceFile(candidate)) {
      return candidate;
    }
  }
  const parsed = path.parse(basePath);
  const sourceAlternatesByRuntimeExt = {
    ".js": [".ts", ".tsx", ".jsx", ".mjs", ".cjs"],
    ".jsx": [".tsx", ".ts", ".js"],
    ".mjs": [".mts", ".ts", ".js"],
    ".cjs": [".cts", ".ts", ".js"],
  };
  const alternates = sourceAlternatesByRuntimeExt[parsed.ext.toLowerCase()] || [];
  for (const ext of alternates) {
    const candidate = path.join(parsed.dir, parsed.name + ext);
    if (fs.existsSync(candidate) && fs.statSync(candidate).isFile() && isImplementationSourceFile(candidate)) {
      return candidate;
    }
  }
  for (const ext of [".ts", ".tsx", ".js", ".jsx"]) {
    const idx = path.join(basePath, "index" + ext);
    if (fs.existsSync(idx) && isImplementationSourceFile(idx)) return idx;
  }
  return null;
}

function resolveRelativeImport(fromFile, specifier, repoPath = null) {
  const fromDir = path.dirname(fromFile);
  const resolved = path.resolve(fromDir, specifier);
  if (isSkippedPath(resolved, repoPath)) return null;
  return tryResolveFile(resolved);
}

function resolveAliasImport(specifier, pathsMap, repoPath) {
  if (specifier.startsWith("~/")) {
    const rest = specifier.slice(2);
    const direct = tryResolveFile(path.join(repoPath, rest));
    if (direct) return direct;
  }

  const entries = Object.entries(pathsMap).sort((a, b) => b[0].length - a[0].length);
  for (const [alias, targets] of entries) {
    if (specifier === alias || specifier.startsWith(alias + "/")) {
      const rest = specifier.slice(alias.length).replace(/^\//, "");
      for (const target of targets) {
        const candidate = path.join(target, rest);
        const file = tryResolveFile(candidate);
        if (file) return file;
      }
    }
  }
  return null;
}

function expandWorkspacePattern(repoPath, pattern) {
  const roots = [];
  const raw = String(pattern).replace(/^\.\//, "");
  if (!raw) return roots;

  if (!raw.includes("*")) {
    const abs = path.join(repoPath, raw);
    if (fs.existsSync(abs)) roots.push(abs);
    return roots;
  }

  const starIdx = raw.indexOf("*");
  const base = raw.slice(0, starIdx).replace(/\/$/, "");
  const baseDir = path.join(repoPath, base);
  if (!fs.existsSync(baseDir)) return roots;
  let entries = [];
  try {
    entries = fs.readdirSync(baseDir, { withFileTypes: true });
  } catch (_) {
    return roots;
  }
  for (const ent of entries) {
    if (!ent.isDirectory()) continue;
    const abs = path.join(baseDir, ent.name);
    const pkgJson = path.join(abs, "package.json");
    if (fs.existsSync(pkgJson)) roots.push(abs);
  }
  return roots;
}

function loadWorkspaceRootsFromPackageJson(repoPath) {
  const roots = [];
  const pkgPath = path.join(repoPath, "package.json");
  if (!fs.existsSync(pkgPath)) return roots;
  try {
    const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf-8"));
    const workspaces = pkg.workspaces;
    const patterns = Array.isArray(workspaces)
      ? workspaces
      : workspaces && Array.isArray(workspaces.packages)
        ? workspaces.packages
        : [];
    for (const pattern of patterns) {
      for (const abs of expandWorkspacePattern(repoPath, pattern)) {
        if (!roots.includes(abs)) roots.push(abs);
      }
    }
  } catch (_) {
    /* ignore */
  }
  return roots;
}

function resolvePackageImport(specifier, repoPath, pathsMap) {
  const alias = resolveAliasImport(specifier, pathsMap, repoPath);
  if (alias && isImplementationSourceFile(alias)) return alias;
  if (!specifier.startsWith("@")) return null;

  const parts = specifier.split("/");
  const pkgRoot = parts.length >= 2 ? `${parts[0]}/${parts[1]}` : specifier;
  const sub = parts.length > 2 ? parts.slice(2).join("/") : "";
  const pkgSlug = pkgRoot.replace(/^@/, "").replace(/\//g, "-");

  const scopedFolder = parts.length >= 2 ? `${parts[0]}/${parts[1]}` : pkgRoot;
  const workspaceRoots = [];
  for (const wsRoot of loadWorkspaceRootsFromPackageJson(repoPath)) {
    workspaceRoots.push(wsRoot);
    if (sub) {
      workspaceRoots.push(path.join(wsRoot, sub));
      workspaceRoots.push(path.join(wsRoot, "src", sub));
      workspaceRoots.push(path.join(wsRoot, "lib", sub));
    }
    const baseName = path.basename(wsRoot);
    if (parts.length >= 2 && (baseName === parts[1] || baseName === pkgSlug)) {
      workspaceRoots.push(path.join(wsRoot, pkgRoot));
    }
  }
  for (const ws of ["packages", "libs", "modules", "apps"]) {
    workspaceRoots.push(path.join(repoPath, ws, pkgRoot));
    workspaceRoots.push(path.join(repoPath, ws, scopedFolder));
    workspaceRoots.push(path.join(repoPath, ws, pkgSlug));
    if (parts.length >= 2) {
      workspaceRoots.push(path.join(repoPath, ws, parts[0], parts[1]));
      workspaceRoots.push(path.join(repoPath, ws, parts[1]));
    }
    if (sub) {
      workspaceRoots.push(path.join(repoPath, ws, pkgSlug, sub));
      workspaceRoots.push(path.join(repoPath, ws, parts[1], sub));
    }
  }

  for (const base of workspaceRoots) {
    const target = sub ? path.join(base, sub) : base;
    const file = tryResolveFile(target);
    if (file && !isSkippedPath(file, repoPath)) return file;
  }

  if (alias) return null;

  const nm = path.join(repoPath, "node_modules", pkgRoot);
  const file = tryResolveFile(nm);
  if (file && file.includes("node_modules") && !isSkippedPath(file, repoPath) && isImplementationSourceFile(file)) {
    return file;
  }
  return null;
}

function resolveImport(fromFile, specifier, repoPath, tsconfigCache) {
  if (!specifier || specifier.startsWith("node:")) return null;

  if (specifier.startsWith(".")) {
    return resolveRelativeImport(fromFile, specifier, repoPath);
  }

  const { pathsMap } = tsconfigCache || loadTsconfigPaths(repoPath);

  if (specifier.startsWith("~/") || specifier.startsWith("/")) {
    return resolveAliasImport(specifier, pathsMap, repoPath);
  }

  if (specifier.startsWith("@")) {
    return resolvePackageImport(specifier, repoPath, pathsMap);
  }

  return null;
}

const importCallableCache = new Map();

function clearImportCallableCache() {
  importCallableCache.clear();
}

function findCommonJsExport(sf, symbolName, sourceFilePath) {
  for (const stmt of sf.getStatements()) {
    if (!Node.isExpressionStatement(stmt)) continue;
    const expr = stmt.getExpression();
    if (!Node.isBinaryExpression(expr)) continue;
    const left = expr.getLeft().getText();
    const right = expr.getRight();
    const match =
      left === `module.exports.${symbolName}` ||
      left === `exports.${symbolName}` ||
      (left === "module.exports" && symbolName === "default");
    if (!match) continue;
    if (Node.isArrowFunction(right) || Node.isFunctionExpression(right)) {
      return { kind: "function", node: right, file: sourceFilePath };
    }
    if (Node.isIdentifier(right)) {
      const local = findLocalExportedSymbol(sf, right.getText(), sourceFilePath);
      if (local) return local;
    }
  }
  return null;
}

function findLocalExportedSymbol(sf, symbolName, sourceFilePath) {
  for (const fn of sf.getFunctions()) {
    if (fn.getName() === symbolName && (fn.isExported() || fn.isDefaultExport())) {
      return { kind: "function", node: fn, file: sourceFilePath };
    }
  }
  for (const vd of sf.getVariableDeclarations()) {
    if (vd.getName() === symbolName) {
      const stmt = vd.getVariableStatement();
      if (stmt && (stmt.isExported() || stmt.hasExportKeyword())) {
        return { kind: "variable", node: vd, file: sourceFilePath };
      }
    }
  }
  for (const cls of sf.getClasses()) {
    if (cls.getName() === symbolName && cls.isExported()) {
      return { kind: "class", node: cls, file: sourceFilePath };
    }
  }
  const cjs = findCommonJsExport(sf, symbolName, sourceFilePath);
  if (cjs) return cjs;
  return null;
}

function getDefaultExportSymbol(sf, sourceFilePath) {
  for (const fn of sf.getFunctions()) {
    if (fn.isDefaultExport()) return { kind: "function", node: fn, file: sourceFilePath };
  }
  for (const cls of sf.getClasses()) {
    if (cls.isDefaultExport()) return { kind: "class", node: cls, file: sourceFilePath };
  }
  for (const vd of sf.getVariableDeclarations()) {
    const stmt = vd.getVariableStatement();
    if (stmt && stmt.isDefaultExport()) {
      return { kind: "variable", node: vd, file: sourceFilePath };
    }
  }
  for (const exp of sf.getExportAssignments()) {
    const expr = exp.getExpression();
    if (Node.isArrowFunction(expr) || Node.isFunctionExpression(expr)) {
      return { kind: "function", node: expr, file: sourceFilePath };
    }
    if (Node.isIdentifier(expr)) {
      const local = findLocalExportedSymbol(sf, expr.getText(), sourceFilePath);
      if (local) return local;
    }
  }
  return null;
}

function isCallableSymbol(sym) {
  if (!sym) return false;
  if (sym.kind === "function") return true;
  if (sym.kind === "variable") {
    const init = sym.node.getInitializer?.();
    if (init && (Node.isArrowFunction(init) || Node.isFunctionExpression(init))) return true;
  }
  return false;
}

function callableFromDeclaration(decl, fallbackFile, kindHint = "helper_function", basis = "exact_symbol") {
  if (!decl) return null;
  const file = decl.getSourceFile?.().getFilePath?.() || fallbackFile;
  if (!file || isSkippedPath(file) || !isImplementationSourceFile(file)) return null;

  if (Node.isFunctionDeclaration(decl) || Node.isFunctionExpression(decl) || Node.isArrowFunction(decl)) {
    return {
      target: decl,
      file,
      kind: kindHint,
      expansion_evidence_basis: basis,
      expansion_confidence: "high",
    };
  }

  if (Node.isMethodDeclaration(decl)) {
    return {
      target: decl,
      file,
      kind: "page_object_method",
      expansion_evidence_basis: basis === "exact_symbol" ? "class_method_type" : basis,
      expansion_confidence: "high",
    };
  }

  if (Node.isVariableDeclaration(decl)) {
    const init = decl.getInitializer();
    if (Node.isArrowFunction(init) || Node.isFunctionExpression(init)) {
      return {
        target: init,
        file,
        kind: kindHint,
        expansion_evidence_basis: basis,
        expansion_confidence: "high",
      };
    }
  }

  return null;
}

function symbolCandidates(symbol) {
  const out = [];
  if (!symbol) return out;
  out.push(symbol);
  try {
    const aliased = symbol.getAliasedSymbol?.();
    if (aliased && aliased !== symbol) out.push(aliased);
  } catch (_) {
    /* ignore */
  }
  return out;
}

function resolveSymbolTargetFromCall(callExpr, fromFile) {
  if (!callExpr || !Node.isCallExpression(callExpr)) return null;
  let expr;
  try {
    expr = callExpr.getExpression();
  } catch (_) {
    return null;
  }

  const symbols = [];
  try {
    const sym = expr.getSymbol?.();
    if (sym) symbols.push(sym);
  } catch (_) {
    /* ignore */
  }
  try {
    const typeSym = expr.getType?.().getSymbol?.();
    if (typeSym) symbols.push(typeSym);
  } catch (_) {
    /* ignore */
  }

  for (const sym of symbols) {
    for (const candidate of symbolCandidates(sym)) {
      for (const decl of candidate.getDeclarations?.() || []) {
        const isMethod = Node.isPropertyAccessExpression(expr);
        const resolved = callableFromDeclaration(
          decl,
          fromFile,
          isMethod ? "page_object" : "helper_function",
          isMethod ? "class_method_type" : "exact_symbol"
        );
        if (resolved) return resolved;
      }
    }
  }
  return null;
}

function followExportStar(sourceFilePath, symbolName, project, repoPath, tsconfigCache, depth = 0) {
  if (depth > 3) return null;
  let sf;
  try {
    sf = project.getSourceFile(sourceFilePath) || project.addSourceFileAtPath(sourceFilePath);
  } catch (_) {
    return null;
  }
  if (!sf) return null;

  for (const ed of sf.getExportDeclarations()) {
    const isExportStar =
      typeof ed.isExportEverything === "function"
        ? ed.isExportEverything()
        : ed.getNamedExports().length === 0 &&
          !ed.getNamespaceExport() &&
          ed.getModuleSpecifier() != null;
    if (!isExportStar) continue;
    const spec = ed.getModuleSpecifierValue();
    if (!spec) continue;
    const resolved = resolveImport(sourceFilePath, spec, repoPath, tsconfigCache);
    if (!resolved) continue;
    const inner = findExportedSymbol(resolved, symbolName, project, repoPath, tsconfigCache, depth + 1, false);
    if (inner) return inner;
  }
  return null;
}

function followReExport(sourceFilePath, symbolName, project, repoPath, tsconfigCache, depth = 0, preferDefault = false) {
  if (depth > 3) return null;
  let sf;
  try {
    sf = project.getSourceFile(sourceFilePath) || project.addSourceFileAtPath(sourceFilePath);
  } catch (_) {
    return null;
  }
  if (!sf) return null;

  for (const ed of sf.getExportDeclarations()) {
    const spec = ed.getModuleSpecifierValue();
    if (!spec) {
      for (const ne of ed.getNamedExports()) {
        const exported = ne.getName();
        const alias = ne.getAliasNode()?.getText();
        if (exported !== symbolName && alias !== symbolName) continue;
        const lookup = exported === symbolName ? exported : alias;
        const local = findLocalExportedSymbol(sf, lookup, sourceFilePath);
        if (local) return local;
      }
      continue;
    }
    const resolved = resolveImport(sourceFilePath, spec, repoPath, tsconfigCache);
    if (!resolved) continue;
    const inner = findExportedSymbol(resolved, symbolName, project, repoPath, tsconfigCache, depth + 1, preferDefault);
    if (inner) return inner;
  }
  return null;
}

function findExportedSymbol(sourceFilePath, symbolName, project, repoPath, tsconfigCache, depth = 0, preferDefault = false) {
  let sf;
  try {
    sf = project.getSourceFile(sourceFilePath) || project.addSourceFileAtPath(sourceFilePath);
  } catch (_) {
    return null;
  }
  if (!sf) return null;

  if (preferDefault) {
    const def = getDefaultExportSymbol(sf, sourceFilePath);
    if (def) return def;
    return null;
  }

  if (!symbolName || symbolName === "default") {
    return getDefaultExportSymbol(sf, sourceFilePath);
  }

  for (const fn of sf.getFunctions()) {
    if (fn.getName() === symbolName && (fn.isExported() || fn.isDefaultExport())) {
      return { kind: "function", node: fn, file: sourceFilePath };
    }
  }
  for (const vd of sf.getVariableDeclarations()) {
    if (vd.getName() === symbolName) {
      const stmt = vd.getVariableStatement();
      if (stmt && (stmt.isExported() || stmt.hasExportKeyword())) {
        return { kind: "variable", node: vd, file: sourceFilePath };
      }
    }
  }
  for (const cls of sf.getClasses()) {
    if (cls.getName() === symbolName && cls.isExported()) {
      return { kind: "class", node: cls, file: sourceFilePath };
    }
  }

  const star = followExportStar(sourceFilePath, symbolName, project, repoPath, tsconfigCache, depth);
  if (star) return star;

  const re = followReExport(sourceFilePath, symbolName, project, repoPath, tsconfigCache, depth, false);
  if (re) return re;

  return null;
}

function resolveNamespaceMember(objName, memberName, fromFile, importMap, repoPath, tsconfigCache, project) {
  const entry = importMap.get(objName);
  if (!entry || !entry.isNamespace) return null;
  const resolvedPath = resolveImport(fromFile, entry.spec, repoPath, tsconfigCache);
  if (!resolvedPath) return null;
  const sym = findExportedSymbol(resolvedPath, memberName, project, repoPath, tsconfigCache, 0, false);
  if (!sym || !isCallableSymbol(sym)) return null;
  const body = sym.kind === "function" ? sym.node : sym.node.getInitializer?.();
  if (!body && sym.kind !== "function") return null;
  const target = sym.kind === "function" ? sym.node : body;
  if (!target) return null;
  return {
    target,
    file: resolvedPath,
    kind: "imported_helper",
    expansion_evidence_basis: "namespace_import",
    expansion_confidence: "high",
  };
}

function isImportCallable(localName, fromFile, importMap, repoPath, tsconfigCache, project) {
  const cacheKey = `${fromFile}|${localName}`;
  if (importCallableCache.has(cacheKey)) return importCallableCache.get(cacheKey);

  const entry = importMap.get(localName);
  let result = false;
  if (entry && !entry.isNamespace) {
    const spec = entry.spec;
    if (spec) {
      const resolvedPath = resolveImport(fromFile, spec, repoPath, tsconfigCache);
      if (resolvedPath) {
        const sym = findExportedSymbol(resolvedPath, localName, project, repoPath, tsconfigCache, 0, entry.isDefault);
        result = isCallableSymbol(sym);
      }
    }
  }
  importCallableCache.set(cacheKey, result);
  return result;
}

function isNamespaceMemberCallable(objName, memberName, fromFile, importMap, repoPath, tsconfigCache, project) {
  const cacheKey = `${fromFile}|${objName}.${memberName}`;
  if (importCallableCache.has(cacheKey)) return importCallableCache.get(cacheKey);
  const result = Boolean(
    resolveNamespaceMember(objName, memberName, fromFile, importMap, repoPath, tsconfigCache, project)
  );
  importCallableCache.set(cacheKey, result);
  return result;
}

function unwrapExpression(node) {
  let cur = node;
  while (cur && Node.isParenthesizedExpression(cur)) {
    cur = cur.getExpression();
  }
  return cur;
}

function hasClassMemberAccess(node) {
  return Boolean(
    node &&
      typeof node.getMethods === "function" &&
      typeof node.getProperties === "function"
  );
}

function findClassMethod(classNode, methodName) {
  if (!hasClassMemberAccess(classNode)) return null;
  for (const m of classNode.getMethods()) {
    if (m.getName() === methodName) return m;
  }
  for (const prop of classNode.getProperties()) {
    const init = prop.getInitializer();
    if (prop.getName() === methodName && init && (Node.isArrowFunction(init) || Node.isFunctionExpression(init))) {
      return init;
    }
  }
  return null;
}

function findEnclosingClass(node) {
  let cur = node.getParent();
  while (cur) {
    if (Node.isClassDeclaration(cur)) return cur;
    cur = cur.getParent();
  }
  return null;
}

function resolveClassByName(className, fromFile, importMap, repoPath, tsconfigCache, project) {
  const specEntry = importMap.get(className);
  const spec = specEntry && typeof specEntry === "object" ? specEntry.spec : specEntry;
  const preferDefault = specEntry && typeof specEntry === "object" ? specEntry.isDefault : false;

  if (spec) {
    const resolvedPath = resolveImport(fromFile, spec, repoPath, tsconfigCache);
    if (!resolvedPath) return null;
    const sym = findExportedSymbol(resolvedPath, className, project, repoPath, tsconfigCache, 0, preferDefault);
    if (sym && sym.kind === "class") return sym.node;
    return null;
  }

  const sf = project.getSourceFile(fromFile);
  if (sf) {
    for (const cls of sf.getClasses()) {
      if (cls.getName() === className) return cls;
    }
  }
  return null;
}

function resolveClassFileForName(className, fromFile, importMap, repoPath, tsconfigCache) {
  const specEntry = importMap.get(className);
  const spec = specEntry && typeof specEntry === "object" ? specEntry.spec : specEntry;
  if (!spec) return fromFile;
  return resolveImport(fromFile, spec, repoPath, tsconfigCache) || fromFile;
}

function resolveConstructedClassForIdentifier(objName, fromFile, importMap, repoPath, tsconfigCache, project) {
  const sf = project.getSourceFile(fromFile);
  if (!sf) return null;
  for (const vd of sf.getDescendantsOfKind(SyntaxKind.VariableDeclaration)) {
    if (vd.getName() !== objName) continue;
    let init = unwrapExpression(vd.getInitializer());
    if (!init) continue;
    if (Node.isAwaitExpression(init)) init = unwrapExpression(init.getExpression());
    if (!Node.isNewExpression(init)) continue;
    const ctor = unwrapExpression(init.getExpression());
    if (!Node.isIdentifier(ctor)) continue;
    const className = ctor.getText();
    const cls = resolveClassByName(className, fromFile, importMap, repoPath, tsconfigCache, project);
    if (!cls) continue;
    return {
      classNode: cls,
      file: resolveClassFileForName(className, fromFile, importMap, repoPath, tsconfigCache),
    };
  }
  return null;
}

function resolveReceiverClassName(obj) {
  let node = unwrapExpression(obj);
  if (Node.isAwaitExpression(node)) {
    node = unwrapExpression(node.getExpression());
  }
  if (Node.isIdentifier(node)) return { className: node.getText(), resolveFileHint: null };
  if (Node.isNewExpression(node)) {
    const inner = unwrapExpression(node.getExpression());
    if (Node.isIdentifier(inner)) return { className: inner.getText(), resolveFileHint: null };
  }
  if (Node.isCallExpression(node)) {
    const inner = unwrapExpression(node.getExpression());
    if (Node.isIdentifier(inner)) return { className: inner.getText(), resolveFileHint: null };
    if (Node.isPropertyAccessExpression(inner)) {
      return { className: inner.getName(), resolveFileHint: inner.getExpression().getText() };
    }
  }
  if (Node.isPropertyAccessExpression(node)) {
    return { className: node.getName(), resolveFileHint: null };
  }
  return { className: "", resolveFileHint: null };
}

function resolveMethodCall(callExpr, importMap, fromFile, repoPath, tsconfigCache, project) {
  const expr = callExpr.getExpression();
  if (!Node.isPropertyAccessExpression(expr)) return null;

  const methodName = expr.getName();
  const obj = unwrapExpression(expr.getExpression());

  if (Node.isIdentifier(obj) && obj.getText() === "this") {
    const cls = findEnclosingClass(callExpr);
    if (cls) {
      const method = findClassMethod(cls, methodName);
      if (method) {
        return {
          target: method,
          file: fromFile,
          kind: "page_object_method",
          expansion_evidence_basis: "class_method_type",
          expansion_confidence: "high",
        };
      }
    }
    return null;
  }

  if (Node.isIdentifier(obj)) {
    const objName = obj.getText();
    const specEntry = importMap.get(objName);
    const spec = specEntry && typeof specEntry === "object" ? specEntry.spec : specEntry;
    const preferDefault = specEntry && typeof specEntry === "object" ? specEntry.isDefault : false;

    if (!spec) {
      const sf = project.getSourceFile(fromFile);
      if (sf) {
        for (const cls of sf.getClasses()) {
          if (cls.getName() === objName) {
            const method = findClassMethod(cls, methodName);
            if (method) {
              return {
                target: method,
                file: fromFile,
                kind: "page_object_method",
                expansion_evidence_basis: "class_method_type",
                expansion_confidence: "high",
              };
            }
          }
        }
      }
      const constructed = resolveConstructedClassForIdentifier(
        objName,
        fromFile,
        importMap,
        repoPath,
        tsconfigCache,
        project
      );
      if (constructed) {
        const method = findClassMethod(constructed.classNode, methodName);
        if (method) {
          return {
            target: method,
            file: constructed.file,
            kind: "page_object_method",
            expansion_evidence_basis: "constructed_class_method",
            expansion_confidence: "high",
          };
        }
      }
      return null;
    }

    const resolvedPath = resolveImport(fromFile, spec, repoPath, tsconfigCache);
    if (!resolvedPath) return null;
    const sym = findExportedSymbol(resolvedPath, objName, project, repoPath, tsconfigCache, 0, preferDefault);
    if (!sym || sym.kind !== "class") return null;
    const method = findClassMethod(sym.node, methodName);
    if (!method) return null;
    return {
      target: method,
      file: resolvedPath,
      kind: "page_object_method",
      expansion_evidence_basis: "class_method_type",
      expansion_confidence: "high",
    };
  }

  if (
    Node.isNewExpression(obj) ||
    Node.isCallExpression(obj) ||
    Node.isPropertyAccessExpression(obj) ||
    Node.isAwaitExpression(obj)
  ) {
    const receiver = Node.isAwaitExpression(obj) ? unwrapExpression(obj.getExpression()) : obj;
    const { className } = resolveReceiverClassName(receiver);
    let resolveFile = fromFile;
    if (className) {
      const cls = resolveClassByName(className, fromFile, importMap, repoPath, tsconfigCache, project);
      if (cls) {
        const method = findClassMethod(cls, methodName);
        if (method) {
          const specEntry = importMap.get(className);
          if (specEntry?.spec) {
            const rp = resolveImport(fromFile, specEntry.spec, repoPath, tsconfigCache);
            if (rp) resolveFile = rp;
          }
          return {
            target: method,
            file: resolveFile,
            kind: "page_object_method",
            expansion_evidence_basis: "class_method_type",
            expansion_confidence: "high",
          };
        }
      }
    }
  }

  return null;
}

function buildImportMap(sourceFile) {
  const map = new Map();
  for (const d of sourceFile.getImportDeclarations()) {
    const spec = d.getModuleSpecifierValue();
    for (const ni of d.getNamedImports()) {
      const imported = ni.getName();
      const local = ni.getAliasNode()?.getText() || imported;
      map.set(local, { spec, isDefault: false, isNamespace: false });
    }
    const defaultImport = d.getDefaultImport();
    if (defaultImport) {
      map.set(defaultImport.getText(), { spec, isDefault: true, isNamespace: false });
    }
    const namespaceImport = d.getNamespaceImport();
    if (namespaceImport) {
      map.set(namespaceImport.getText(), { spec, isDefault: false, isNamespace: true });
    }
  }
  return map;
}

module.exports = {
  loadTsconfigPaths,
  resolveImport,
  findExportedSymbol,
  findClassMethod,
  resolveMethodCall,
  resolveSymbolTargetFromCall,
  resolveNamespaceMember,
  isImportCallable,
  isNamespaceMemberCallable,
  isCallableSymbol,
  buildImportMap,
  tryResolveFile,
  isSkippedPath,
  getDefaultExportSymbol,
  clearImportCallableCache,
};
