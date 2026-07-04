"use strict";

const fs = require("fs");
const path = require("path");
const fg = require("fast-glob");
const { Node } = require("ts-morph");
const { toPosix } = require("../shared/utils");
const { loadTsconfigPaths, resolveImport } = require("./importResolver");

const FIXTURE_GLOBS = [
  "**/fixtures/**/*.{json,yml,yaml,csv}",
  "**/cypress/fixtures/**/*.{json,yml,yaml,csv}",
  "**/e2e/fixtures/**/*.{json,yml,yaml,csv}",
];

const MAX_PARSE_BYTES = 65536;

function fileFormat(filePath) {
  const ext = path.extname(filePath || "").toLowerCase().replace(/^\./, "");
  if (ext === "yml") return "yaml";
  return ext || "unknown";
}

function isInsideRepo(repoPath, candidate) {
  const rel = path.relative(repoPath, candidate);
  return rel && !rel.startsWith("..") && !path.isAbsolute(rel);
}

function tryParseJson(filePath) {
  try {
    const buf = fs.readFileSync(filePath);
    if (buf.length > MAX_PARSE_BYTES) return { parse_status: "partial", top_keys: [] };
    const data = JSON.parse(buf.toString("utf-8"));
    if (data && typeof data === "object" && !Array.isArray(data)) {
      return { parse_status: "ok", top_keys: Object.keys(data).slice(0, 50) };
    }
    if (Array.isArray(data) && data.length && typeof data[0] === "object") {
      return { parse_status: "ok", top_keys: Object.keys(data[0]).slice(0, 50) };
    }
    return { parse_status: "ok", top_keys: [] };
  } catch (_) {
    return { parse_status: "error", top_keys: [] };
  }
}

function tryParseYaml(filePath) {
  try {
    const yaml = require("yaml");
    const buf = fs.readFileSync(filePath);
    if (buf.length > MAX_PARSE_BYTES) return { parse_status: "partial", top_keys: [] };
    const data = yaml.parse(buf.toString("utf-8"));
    if (data && typeof data === "object" && !Array.isArray(data)) {
      return { parse_status: "ok", top_keys: Object.keys(data).slice(0, 50) };
    }
    return { parse_status: "ok", top_keys: [] };
  } catch (_) {
    return { parse_status: "skipped", top_keys: [] };
  }
}

function tryParseCsvHeaders(filePath) {
  try {
    const text = fs.readFileSync(filePath, "utf-8").slice(0, 4096);
    const firstLine = text.split(/\r?\n/)[0] || "";
    const headers = firstLine.split(",").map((h) => h.trim().replace(/^["']|["']$/g, ""));
    return { parse_status: headers.length ? "ok" : "partial", top_keys: headers.slice(0, 50) };
  } catch (_) {
    return { parse_status: "error", top_keys: [] };
  }
}

function parseFileMetadata(absPath) {
  const fmt = fileFormat(absPath);
  if (fmt === "json") return tryParseJson(absPath);
  if (fmt === "yaml") return tryParseYaml(absPath);
  if (fmt === "csv") return tryParseCsvHeaders(absPath);
  return { parse_status: "skipped", top_keys: [] };
}

function resolveStaticPath(repoPath, fromFile, literalPath) {
  if (!literalPath || !literalPath.trim()) return { resolved_path: "", parse_status: "skipped" };
  const lit = literalPath.trim();
  if (/^https?:\/\//i.test(lit) || /\$\{|`|\+/.test(lit)) {
    return { resolved_path: "", parse_status: "skipped" };
  }

  const fromDir = fromFile ? path.dirname(fromFile) : repoPath;
  const candidates = [];

  if (lit.startsWith(".") || lit.startsWith("/")) {
    candidates.push(path.resolve(fromDir, lit.replace(/^\//, "")));
  } else {
    candidates.push(path.resolve(fromDir, lit));
    candidates.push(path.join(repoPath, lit));
    candidates.push(path.join(repoPath, "cypress", "fixtures", lit));
    candidates.push(path.join(repoPath, "fixtures", lit));
    if (!/\.[a-z0-9]+$/i.test(lit)) {
      for (const ext of [".json", ".yaml", ".yml", ".csv"]) {
        candidates.push(path.join(repoPath, "cypress", "fixtures", `${lit}${ext}`));
        candidates.push(path.join(repoPath, "fixtures", `${lit}${ext}`));
      }
    }
  }

  for (const c of candidates) {
    const abs = path.normalize(c);
    if (fs.existsSync(abs) && fs.statSync(abs).isFile() && isInsideRepo(repoPath, abs)) {
      return { resolved_path: toPosix(path.relative(repoPath, abs)), parse_status: "ok" };
    }
  }

  return { resolved_path: lit, parse_status: "partial" };
}

function registerLoadSite(registry, entry) {
  if (!entry || !entry.literal_path) return;
  const key = `${entry.kind}:${entry.literal_path}`;
  if (!registry.byLiteral.has(key)) registry.byLiteral.set(key, entry);
  if (entry.alias) registry.byAlias.set(entry.alias, entry);
  if (entry.resolved_path) registry.byResolved.set(entry.resolved_path, entry);
}

function buildEntry(repoPath, fromFile, literalPath, kind, line) {
  const absFrom = fromFile ? path.join(repoPath, fromFile) : repoPath;
  const { resolved_path, parse_status: resolveStatus } = resolveStaticPath(repoPath, absFrom, literalPath);
  let parseMeta = { parse_status: resolveStatus, top_keys: [] };
  if (resolved_path && resolveStatus === "ok") {
    const abs = path.join(repoPath, resolved_path);
    if (fs.existsSync(abs)) parseMeta = parseFileMetadata(abs);
  }
  const alias = path.basename(literalPath, path.extname(literalPath));
  return {
    kind,
    literal_path: literalPath,
    resolved_path,
    format: fileFormat(resolved_path || literalPath),
    alias,
    declared_line: line || null,
    declared_file: fromFile || "",
    parse_status: parseMeta.parse_status,
    top_keys: parseMeta.top_keys,
  };
}

function collectFromFeatures(features, repoPath, registry) {
  for (const f of features) {
    const lit = f.input_load_path_ast || "";
    const fromFile = f.file_path || f.target_file || "";
    if (!lit && f.raw_code && /\bcy\.fixture\s*\(/.test(f.raw_code)) {
      const m = f.raw_code.match(/fixture\s*\(\s*['"]([^'"]+)['"]/);
      if (m) registerLoadSite(registry, buildEntry(repoPath, fromFile, m[1], "fixture_file_input", f.line));
    }
    if (lit) registerLoadSite(registry, buildEntry(repoPath, fromFile, lit, f.input_source_ast || "external_file_input", f.line));
  }
}

function collectFromSourceFiles(project, repoPath, registry) {
  for (const sf of project.getSourceFiles()) {
    const filePath = toPosix(path.relative(repoPath, sf.getFilePath()));
    for (const decl of sf.getImportDeclarations()) {
      const spec = decl.getModuleSpecifier().getLiteralText();
      if (!/\.(json|ya?ml|csv)$/i.test(spec)) continue;
      registerLoadSite(
        registry,
        buildEntry(repoPath, filePath, spec, "external_file_input", decl.getStartLineNumber())
      );
    }
    sf.forEachDescendant((node) => {
      if (!Node.isCallExpression(node)) return;
      const expr = node.getExpression().getText();
      if (!/\.intercept\b|route\s*\(|\.fulfill\b/.test(expr)) return;
      for (const arg of node.getArguments()) {
        const lit = fixturePathFromObjectLiteral(arg);
        if (lit) {
          registerLoadSite(
            registry,
            buildEntry(repoPath, filePath, lit, "network_mock_payload_input", node.getStartLineNumber())
          );
        }
      }
    });
  }
}

function fixturePathFromObjectLiteral(obj) {
  if (!obj || !Node.isObjectLiteralExpression(obj)) return null;
  for (const prop of obj.getProperties()) {
    const name = prop.getName?.() || "";
    if (name !== "fixture") continue;
    const init = prop.getInitializer?.();
    if (init && Node.isStringLiteral(init)) return init.getLiteralText();
  }
  return null;
}

function discoverFixtureFiles(repoPath, registry) {
  for (const pattern of FIXTURE_GLOBS) {
    const matches = fg.sync(pattern, {
      cwd: repoPath,
      absolute: true,
      onlyFiles: true,
      suppressErrors: true,
    });
    for (const abs of matches.slice(0, 500)) {
      if (!isInsideRepo(repoPath, abs)) continue;
      const rel = toPosix(path.relative(repoPath, abs));
      if (registry.byResolved.has(rel)) continue;
      const meta = parseFileMetadata(abs);
      registry.byResolved.set(rel, {
        kind: "fixture_file_input",
        literal_path: path.basename(abs),
        resolved_path: rel,
        format: fileFormat(abs),
        alias: path.basename(abs, path.extname(abs)),
        declared_line: null,
        declared_file: "",
        parse_status: meta.parse_status,
        top_keys: meta.top_keys,
      });
    }
  }
}

function buildInputDataRegistry(repoPath, project, featuresDirect, featuresExpanded) {
  const registry = { byLiteral: new Map(), byAlias: new Map(), byResolved: new Map() };
  collectFromFeatures(featuresDirect || [], repoPath, registry);
  collectFromFeatures(featuresExpanded || [], repoPath, registry);
  if (project) collectFromSourceFiles(project, repoPath, registry);
  discoverFixtureFiles(repoPath, registry);
  return registry;
}

function summarizeRegistryMetrics(registry) {
  const entries = [];
  const seen = new Set();
  for (const map of [registry.byLiteral, registry.byResolved]) {
    for (const entry of map.values()) {
      const key = `${entry.kind}:${entry.literal_path}:${entry.resolved_path}`;
      if (seen.has(key)) continue;
      seen.add(key);
      entries.push(entry);
    }
  }

  const loadSites = entries.filter((e) => e.declared_line || e.declared_file);
  const staticPaths = entries.filter((e) => e.literal_path);
  const resolved = entries.filter((e) => e.resolved_path && e.parse_status !== "skipped");
  const parseOk = entries.filter((e) => e.parse_status === "ok");
  const parsePartial = entries.filter((e) => e.parse_status === "partial");
  const parseError = entries.filter((e) => e.parse_status === "error");

  const denom = staticPaths.length || entries.length;
  return {
    rq2_registry_load_sites: loadSites.length,
    rq2_registry_static_paths: staticPaths.length,
    rq2_registry_resolved_paths: resolved.length,
    rq2_registry_parse_ok: parseOk.length,
    rq2_registry_parse_partial: parsePartial.length,
    rq2_registry_parse_error: parseError.length,
    rq2_registry_resolution_rate: denom ? resolved.length / denom : 0,
    rq2_registry_entries: entries.length,
  };
}

module.exports = {
  buildInputDataRegistry,
  summarizeRegistryMetrics,
  resolveStaticPath,
  fileFormat,
  parseFileMetadata,
  buildEntry,
};
