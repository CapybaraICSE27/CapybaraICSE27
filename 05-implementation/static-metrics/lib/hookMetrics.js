"use strict";

const path = require("path");
const { collectHooks } = require("../../test-feature-extraction/lib/phase2b/hookCollector");
const { collectTestLikeIdentifiers } = require("../../test-feature-extraction/lib/shared/identifiers");
const { getLineRange, toPosix } = require("../../test-feature-extraction/lib/shared/utils");
const { computeComplexityMetrics } = require("./complexityUtils");
const { hookLookupKey, resolveHookCallbackBody } = require("./hookCallbackResolver");

/**
 * Parse support:* hook_instance_key → { rel, innerKey }.
 * Format: support:<relative/path>:<line>:<hookKind>:<describePath...>
 */
function parseSupportHookKey(fullKey) {
  const s = String(fullKey || "");
  if (!s.startsWith("support:")) return null;
  const rest = s.slice("support:".length);
  const m = rest.match(
    /^(.+):(\d+):(beforeEach|afterEach|beforeAll|afterAll|before|after):(.*)$/
  );
  if (!m) return null;
  return {
    rel: m[1].replace(/\\/g, "/"),
    innerKey: `${m[2]}:${m[3]}:${m[4]}`,
  };
}

/** Parse file-local hook key: `<line>:<hookKind>:<describePath>` */
function parseInnerHookKey(innerKey) {
  const s = String(innerKey || "");
  const m = s.match(
    /^(\d+):(beforeEach|afterEach|beforeAll|afterAll|before|after):(.*)$/i
  );
  if (!m) return null;
  return {
    line: parseInt(m[1], 10),
    hookKind: m[2],
    describePath: m[3] || "",
  };
}

function hookKindMatches(hook, expectedKind) {
  const got = String(hook.source_kind || hook.hookName || "").toLowerCase();
  const want = String(expectedKind || "").toLowerCase();
  return got === want;
}

function describePathKey(hook) {
  return (hook.describe_path || []).join(">");
}

function findHookInSourceFile(sourceFile, innerKey) {
  const { testNames, groupNames } = collectTestLikeIdentifiers(sourceFile);
  const hooks = collectHooks(sourceFile, testNames, groupNames);

  const exact = hooks.find((h) => h.hook_instance_key === innerKey);
  if (exact) {
    return { hook: exact, hook_metrics_match_mode: "exact" };
  }

  const parsed = parseInnerHookKey(innerKey);
  if (!parsed) {
    return { hook: null, hook_metrics_match_mode: null };
  }

  const byLineKind = hooks.filter(
    (h) => h.hook_call_line === parsed.line && hookKindMatches(h, parsed.hookKind)
  );
  if (byLineKind.length === 1) {
    return { hook: byLineKind[0], hook_metrics_match_mode: "line_kind_fallback" };
  }
  if (byLineKind.length > 1) {
    const pathMatches = byLineKind.filter(
      (h) => describePathKey(h) === parsed.describePath
    );
    if (pathMatches.length === 1) {
      return { hook: pathMatches[0], hook_metrics_match_mode: "line_kind_describe_fallback" };
    }
    if (!parsed.describePath) {
      const fileLevel = byLineKind.filter(
        (h) => h.is_file_level || describePathKey(h) === ""
      );
      if (fileLevel.length === 1) {
        return { hook: fileLevel[0], hook_metrics_match_mode: "line_kind_file_level_fallback" };
      }
    }
  }

  const byLine = hooks.filter((h) => h.hook_call_line === parsed.line);
  if (byLine.length === 1) {
    return { hook: byLine[0], hook_metrics_match_mode: "line_fallback" };
  }

  return { hook: null, hook_metrics_match_mode: null };
}

/**
 * @param {*} getSourceFile - (rel POSIX path) → { status, sourceFile } | legacy SourceFile | null
 */
function resolveSourceFile(getSourceFile, relFile) {
  const res = getSourceFile(relFile);
  if (res && typeof res === "object" && "status" in res) {
    return res;
  }
  if (!res) {
    return { status: "missing_source_file", sourceFile: null };
  }
  return { status: "ok", sourceFile: res };
}

function relPathFromRepo(repoPath, absolutePath) {
  try {
    const rel = path.relative(path.resolve(repoPath), path.resolve(absolutePath));
    if (rel.startsWith("..")) return toPosix(absolutePath);
    return toPosix(rel);
  } catch (_) {
    return "";
  }
}

/** Source file that owns the resolved hook callback AST node. */
function sourceFileForBody(bodyNode, fallbackSf) {
  try {
    const bodySf = bodyNode?.getSourceFile?.();
    if (bodySf) return bodySf;
  } catch (_) {
    /* ignore */
  }
  return fallbackSf;
}

function computeHookMetricsRow(
  repoPath,
  hookInstanceKey,
  filePathHint,
  getSourceFile,
  project
) {
  const key = String(hookInstanceKey || "");
  let relFile = String(filePathHint || "").replace(/\\/g, "/");
  let innerKey = key;
  const lookupKey = hookLookupKey(relFile, key);

  if (key.startsWith("support:")) {
    const parsed = parseSupportHookKey(key);
    if (!parsed) {
      return {
        hook_lookup_key: lookupKey,
        hook_instance_key: key,
        file_path: relFile,
        hook_metrics_status: "hook_unresolved",
      };
    }
    relFile = parsed.rel;
    innerKey = parsed.innerKey;
  }

  const sfResult = resolveSourceFile(getSourceFile, relFile);
  if (sfResult.status === "parse_or_add_error") {
    return {
      hook_lookup_key: hookLookupKey(relFile, key),
      hook_instance_key: key,
      file_path: relFile,
      hook_metrics_status: "parse_or_add_error",
      hook_metrics_error: sfResult.error || "addSourceFileAtPath failed",
    };
  }
  const sf = sfResult.sourceFile;
  if (!sf) {
    return {
      hook_lookup_key: hookLookupKey(relFile, key),
      hook_instance_key: key,
      file_path: relFile,
      hook_metrics_status: "missing_hook_source_file",
    };
  }

  const found = findHookInSourceFile(sf, innerKey);
  const hook = found.hook;
  if (!hook) {
    return {
      hook_lookup_key: hookLookupKey(relFile, key),
      hook_instance_key: key,
      file_path: relFile,
      hook_metrics_status: "hook_body_not_found",
      hook_metrics_match_mode: found.hook_metrics_match_mode,
    };
  }

  let matchMode = found.hook_metrics_match_mode || "exact";
  let bodyNode = hook.callback;
  if (!bodyNode && project) {
    const resolved = resolveHookCallbackBody(hook, sf, repoPath, project);
    bodyNode = resolved.body;
    if (resolved.hook_metrics_match_mode) {
      matchMode = resolved.hook_metrics_match_mode;
    }
  }

  if (!bodyNode) {
    return {
      hook_lookup_key: hookLookupKey(relFile, key),
      hook_instance_key: key,
      file_path: relFile,
      hook_metrics_status: "hook_body_not_found",
      hook_metrics_match_mode: matchMode,
    };
  }

  const range = getLineRange(bodyNode);
  const startLine = range.start_line;
  const endLine = range.end_line;
  const sourceKind = hook.source_kind || hook.hookName || "";
  const metricsSf = sourceFileForBody(bodyNode, sf);
  const hookBodyFile = relPathFromRepo(repoPath, metricsSf.getFilePath());

  try {
    const m = computeComplexityMetrics(metricsSf, startLine, endLine);
    return {
      hook_lookup_key: hookLookupKey(relFile, key),
      hook_instance_key: key,
      file_path: relFile,
      hook_body_file_path: hookBodyFile || relFile,
      hook_source_kind: sourceKind,
      start_line: startLine,
      end_line: endLine,
      hook_metrics_status: "ok",
      hook_metrics_match_mode: matchMode,
      hook_ncloc: m.test_body_ncloc,
      hook_loc: m.test_body_loc,
      hook_cyclomatic_basic: m.test_body_cyclomatic_basic,
      hook_cyclomatic_extended: m.test_body_cyclomatic_extended,
      hook_branch_count: m.test_body_branch_count,
      hook_loop_count: m.test_body_loop_count,
      hook_max_nesting_depth: m.test_body_max_nesting_depth,
    };
  } catch (err) {
    return {
      hook_lookup_key: hookLookupKey(relFile, key),
      hook_instance_key: key,
      file_path: relFile,
      hook_body_file_path: hookBodyFile || relFile,
      hook_source_kind: sourceKind,
      start_line: startLine,
      end_line: endLine,
      hook_metrics_status: "parse_error",
      hook_metrics_error: String(err && err.message ? err.message : err),
      hook_ncloc: 0,
      hook_loc: 0,
      hook_cyclomatic_basic: 0,
      hook_cyclomatic_extended: 0,
      hook_branch_count: 0,
      hook_loop_count: 0,
      hook_max_nesting_depth: 0,
      hook_metrics_match_mode: matchMode,
    };
  }
}

function isSetupKind(sk) {
  const s = String(sk || "").toLowerCase();
  return s === "before" || s === "beforeeach" || s === "beforeall";
}

function isTeardownKind(sk) {
  const s = String(sk || "").toLowerCase();
  return s === "after" || s === "aftereach" || s === "afterall";
}

/**
 * Aggregate hook_* totals for a test from hook_instance_keys (file-scoped lookup).
 * @param {Map<string, object>} hookRowByKey - hook_lookup_key → metrics row
 */
function attachHookAggregatesToTest(testCase, hookRowByKey) {
  const keys = testCase.hook_instance_keys || [];
  const testFp = testCase.file_path || "";
  const base = {
    hook_count: keys.length,
    before_hook_count: 0,
    before_each_hook_count: 0,
    before_all_hook_count: 0,
    after_hook_count: 0,
    after_each_hook_count: 0,
    after_all_hook_count: 0,
    hook_ncloc_total: 0,
    hook_cyclomatic_basic_total: 0,
    hook_cyclomatic_extended_total: 0,
    setup_hook_ncloc_total: 0,
    teardown_hook_ncloc_total: 0,
    setup_hook_cyclomatic_basic_total: 0,
    teardown_hook_cyclomatic_basic_total: 0,
    setup_hook_cyclomatic_extended_total: 0,
    teardown_hook_cyclomatic_extended_total: 0,
    hook_max_nesting_depth_max: 0,
    hook_metrics_unresolved_count: 0,
  };

  for (const k of keys) {
    const lk = hookLookupKey(testFp, k);
    const row = hookRowByKey.get(lk);
    if (!row || row.hook_metrics_status !== "ok") {
      base.hook_metrics_unresolved_count += 1;
      continue;
    }

    const sk = String(row.hook_source_kind || "");
    const skl = sk.toLowerCase();
    if (skl === "before") base.before_hook_count += 1;
    else if (skl === "beforeeach") base.before_each_hook_count += 1;
    else if (skl === "beforeall") base.before_all_hook_count += 1;
    else if (skl === "after") base.after_hook_count += 1;
    else if (skl === "aftereach") base.after_each_hook_count += 1;
    else if (skl === "afterall") base.after_all_hook_count += 1;

    const ncloc = row.hook_ncloc || 0;
    const cycB = row.hook_cyclomatic_basic || 0;
    const cycE = row.hook_cyclomatic_extended || 0;
    const nest = row.hook_max_nesting_depth || 0;

    base.hook_ncloc_total += ncloc;
    base.hook_cyclomatic_basic_total += cycB;
    base.hook_cyclomatic_extended_total += cycE;
    base.hook_max_nesting_depth_max = Math.max(base.hook_max_nesting_depth_max, nest);

    if (isSetupKind(sk)) {
      base.setup_hook_ncloc_total += ncloc;
      base.setup_hook_cyclomatic_basic_total += cycB;
      base.setup_hook_cyclomatic_extended_total += cycE;
    }
    if (isTeardownKind(sk)) {
      base.teardown_hook_ncloc_total += ncloc;
      base.teardown_hook_cyclomatic_basic_total += cycB;
      base.teardown_hook_cyclomatic_extended_total += cycE;
    }
  }

  return base;
}

module.exports = {
  hookLookupKey,
  parseSupportHookKey,
  parseInnerHookKey,
  findHookInSourceFile,
  computeHookMetricsRow,
  attachHookAggregatesToTest,
  isSetupKind,
  isTeardownKind,
  relPathFromRepo,
  sourceFileForBody,
};
