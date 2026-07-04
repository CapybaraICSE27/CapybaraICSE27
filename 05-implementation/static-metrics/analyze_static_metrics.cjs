#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const { Project } = require("ts-morph");
const { toPosix } = require("../test-feature-extraction/lib/shared/utils");
const { computeComplexityMetrics } = require("./lib/complexityUtils");
const {
  computeHookMetricsRow,
  attachHookAggregatesToTest,
} = require("./lib/hookMetrics");

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i++) {
    const cur = argv[i];
    if (!cur.startsWith("--")) continue;
    const key = cur.slice(2);
    const next = argv[i + 1];
    if (!next || next.startsWith("--")) args[key] = true;
    else {
      args[key] = next;
      i++;
    }
  }
  return args;
}

function isExecutableTestCase(tc) {
  if (tc.record_type && tc.record_type !== "test_case") return false;
  if (tc.test_declaration_type === "bdd_step") return false;
  return Boolean(tc.test_id);
}

function metricsForTest(sfResult, tc) {
  const base = {
    repo: tc.repo,
    test_id: tc.test_id,
    framework: tc.framework || "",
    file_path: tc.file_path || "",
    test_name: tc.test_name || "",
    phase1_confidence: tc.phase1_confidence || "",
    source_confidence: tc.source_confidence || "",
    callback_start_line: tc.callback_start_line ?? null,
    callback_end_line: tc.callback_end_line ?? null,
    expected_commit: expectedCommit,
    analyzed_commit: analyzedCommit,
  };

  const start = tc.callback_start_line;
  const end = tc.callback_end_line;

  const emptyBody = () => ({
    test_body_loc: 0,
    test_body_ncloc: 0,
    test_body_statement_count: 0,
    test_body_call_count: 0,
    test_body_cyclomatic_basic: 0,
    test_body_cyclomatic_extended: 0,
    test_body_branch_count: 0,
    test_body_loop_count: 0,
    test_body_switch_case_count: 0,
    test_body_conditional_expression_count: 0,
    test_body_logical_condition_count: 0,
    test_body_try_catch_count: 0,
    test_body_max_nesting_depth: 0,
  });

  if (start == null || end == null || start <= 0 || end <= 0 || end < start) {
    return { ...base, metrics_status: "missing_callback_range", ...emptyBody() };
  }

  if (!sfResult || sfResult.status === "missing_source_file") {
    return { ...base, metrics_status: "missing_source_file", ...emptyBody() };
  }

  if (sfResult.status === "parse_or_add_error") {
    return {
      ...base,
      metrics_status: "parse_or_add_error",
      metrics_error: sfResult.error || "addSourceFileAtPath failed",
      ...emptyBody(),
    };
  }

  const sourceFile = sfResult.sourceFile;
  if (!sourceFile) {
    return { ...base, metrics_status: "missing_source_file", ...emptyBody() };
  }

  try {
    const metrics = computeComplexityMetrics(sourceFile, start, end);
    return { ...base, metrics_status: "ok", ...metrics };
  } catch (err) {
    return {
      ...base,
      metrics_status: "parse_error",
      metrics_error: String(err && err.message ? err.message : err),
      ...emptyBody(),
    };
  }
}

function mergeHookIntoTest(row, tc, hookRowByKey) {
  const hookAgg = attachHookAggregatesToTest(tc, hookRowByKey);
  return { ...row, ...hookAgg };
}

const args = parseArgs(process.argv);
const repoPath = path.resolve(args["repo-path"] || "");
const manifestPath = path.resolve(args.manifest || "");
const outputPath = args.output ? path.resolve(args.output) : null;
const precomputedHooksPath = args["precomputed-hooks"]
  ? path.resolve(args["precomputed-hooks"])
  : null;

if (!repoPath || !fs.existsSync(repoPath) || !manifestPath || !fs.existsSync(manifestPath)) {
  console.error(
    "Usage: node analyze_static_metrics.cjs --repo-path <path> --manifest <tests.json> [--output <file.json>] [--precomputed-hooks <hooks.json>]"
  );
  process.exit(2);
}

const payload = JSON.parse(fs.readFileSync(manifestPath, "utf-8"));
const tests = (payload.tests || []).filter(isExecutableTestCase);
const hookManifest = payload.hooks || [];
const expectedCommit = payload.expected_commit || null;
const analyzedCommit = payload.analyzed_commit || null;

const project = new Project({
  compilerOptions: { allowJs: true, checkJs: false },
  skipAddingFilesFromTsConfig: true,
});

const fileCache = new Map();

function getSourceFile(relPath) {
  const key = toPosix(relPath);
  if (fileCache.has(key)) return fileCache.get(key);
  const abs = path.join(repoPath, key);
  if (!fs.existsSync(abs)) {
    const miss = { status: "missing_source_file", sourceFile: null };
    fileCache.set(key, miss);
    return miss;
  }
  try {
    const sf = project.addSourceFileAtPath(abs);
    const ok = { status: "ok", sourceFile: sf };
    fileCache.set(key, ok);
    return ok;
  } catch (err) {
    const fail = {
      status: "parse_or_add_error",
      sourceFile: null,
      error: String(err && err.message ? err.message : err),
    };
    fileCache.set(key, fail);
    return fail;
  }
}

/** hook_lookup_key -> metrics row */
const hookRowByKey = new Map();
const hookRowsDedup = new Map();

function loadPrecomputedHooks(filePath) {
  const raw = JSON.parse(fs.readFileSync(filePath, "utf-8"));
  const list = Array.isArray(raw) ? raw : raw.hooks || [];
  for (const row of list) {
    const lk = String(row.hook_lookup_key || row.hook_instance_key || "");
    if (!lk || hookRowsDedup.has(lk)) continue;
    hookRowsDedup.set(lk, row);
    hookRowByKey.set(lk, row);
  }
}

if (precomputedHooksPath) {
  if (!fs.existsSync(precomputedHooksPath)) {
    console.error(`Missing --precomputed-hooks file: ${precomputedHooksPath}`);
    process.exit(2);
  }
  loadPrecomputedHooks(precomputedHooksPath);
} else {
  for (const h of hookManifest) {
    const lk = String(h.hook_lookup_key || h.hook_instance_key || "");
    if (!lk || hookRowsDedup.has(lk)) continue;
    const k = String(h.hook_instance_key || "");
    const fp = String(h.file_path || "");
    let hint = fp;
    if (!hint && !k.startsWith("support:")) {
      hint = String(h.fallback_test_file_path || "").replace(/\\/g, "/");
    }
    const computed = computeHookMetricsRow(repoPath, k, hint, getSourceFile, project);
    const row = {
      ...computed,
      hook_lookup_key: lk,
      hook_instance_key: computed.hook_instance_key || k,
    };
    hookRowsDedup.set(lk, row);
    hookRowByKey.set(lk, row);
  }
}

const hookDetailList = [...hookRowsDedup.values()];

const rows = [];
for (const tc of tests) {
  const sf = getSourceFile(tc.file_path);
  const row = mergeHookIntoTest(metricsForTest(sf, tc), tc, hookRowByKey);
  rows.push(row);
}

const out = {
  payload_version: payload.payload_version || 4,
  repo: payload.repo || "",
  expected_commit: payload.expected_commit || null,
  analyzed_commit: payload.analyzed_commit || null,
  cache_fingerprint: payload.cache_fingerprint || null,
  hooks: hookDetailList,
  metrics: rows,
};
if (outputPath) {
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, JSON.stringify(out), "utf-8");
} else {
  process.stdout.write(JSON.stringify(out));
}
