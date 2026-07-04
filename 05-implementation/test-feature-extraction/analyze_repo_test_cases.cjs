#!/usr/bin/env node
/**
 * Phase 2 per-repo test-case feature extractor.
 */
"use strict";

const fs = require("fs");
const path = require("path");
const { Project } = require("ts-morph");
const { extractTestCasesFromFile } = require("./lib/phase2a/testCaseExtractor");
const { extractDirectFeatures } = require("./lib/phase2b/directFeatureExtractor");
const { expandHelpersForRepo } = require("./lib/phase2c/helperExpander");
const { loadSupportFilesForProject } = require("./lib/phase2c/supportFileLoader");
const { loadPlaywrightGlobalSetupFiles } = require("./lib/phase2c/playwrightGlobalSetup");
const { attachHookFeaturesToExpanded } = require("./lib/phase2c/expandedOutput");
const {
  collectGlobalSupportHooks,
  applyGlobalSupportHooksToTestCases,
  reconcileGlobalSupportHookFeatures,
  extractGlobalSupportHookFeatures,
} = require("./lib/phase2c/globalSupportHooks");
const { toPosix } = require("./lib/shared/utils");
const { writePerRepoResult, loadPerRepoResult } = require("./lib/shared/repoOutputWriter");
const { buildInputDataRegistry, summarizeRegistryMetrics } = require("./lib/phase2c/inputDataRegistry");
const { linkInputProvenance } = require("./lib/phase2c/inputProvenanceLinker");

function commitsMatch(actual, target) {
  actual = String(actual || "").trim();
  target = String(target || "").trim();
  if (!target || target === "HEAD") return true;
  if (!actual) return false;
  if (actual === target) return true;
  if (target.length >= 7 && actual.length >= 7) {
    return actual.slice(0, 7).toLowerCase() === target.slice(0, 7).toLowerCase();
  }
  return actual.startsWith(target) || target.startsWith(actual);
}

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i++) {
    const cur = argv[i];
    if (!cur.startsWith("--")) continue;
    const key = cur.slice(2);
    const next = argv[i + 1];
    if (!next || next.startsWith("--")) {
      args[key] = true;
    } else {
      args[key] = next;
      i++;
    }
  }
  return args;
}

const args = parseArgs(process.argv);
const repoPath = path.resolve(args["repo-path"] || "");
const repo = args.repo || path.basename(repoPath);
const repoUrl = args["repo-url"] || `https://github.com/${repo}`;
const commit = args.commit || "HEAD";
const outputPath = args.output ? path.resolve(args.output) : null;
const subphase = String(args.subphase || "2ab").toLowerCase();
const maxHelperDepth = parseInt(args["max-helper-depth"] || "2", 10);
const maxHelperFiles = parseInt(args["max-helper-files"] || "20", 10);
const reuseFromPath = args["reuse-from"] ? path.resolve(args["reuse-from"]) : null;

let manifest = [];
if (args.manifest) {
  manifest = JSON.parse(fs.readFileSync(path.resolve(args.manifest), "utf-8"));
}

let reused = null;
if (reuseFromPath && fs.existsSync(reuseFromPath)) {
  try {
    reused = loadPerRepoResult(reuseFromPath);
  } catch (_) {
    reused = null;
  }
}

if (!repoPath || !fs.existsSync(repoPath)) {
  console.error(
    "Usage: node analyze_repo_test_cases.cjs --repo-path <path> --repo owner/name --manifest <json> [--subphase 2a|2b|2ab|2c] [--output file]"
  );
  process.exit(2);
}

const run2a = ["2a", "2b", "2ab", "2c", "all"].includes(subphase);
const run2b = ["2b", "2ab", "2c", "all"].includes(subphase);
const run2c = ["2c", "all"].includes(subphase);

const repoMeta = { repo, repo_url: repoUrl, commit, file_url: "" };
const project = new Project({
  compilerOptions: { allowJs: true, checkJs: false },
  skipAddingFilesFromTsConfig: true,
});

const testCases = reused && Array.isArray(reused.test_cases) ? [...reused.test_cases] : [];
const bddStepDefinitions =
  reused && Array.isArray(reused.bdd_step_definitions) ? [...reused.bdd_step_definitions] : [];
let featuresDirect = reused && Array.isArray(reused.features_direct) ? [...reused.features_direct] : [];
const parseErrors = [];

let skip2a2b = Boolean(reused && subphase === "2c" && testCases.length && featuresDirect.length);
  if (skip2a2b) {
  const cachedCommit = reused.analyzed_commit || reused.commit || "";
  if (!commitsMatch(commit, cachedCommit)) {
    skip2a2b = false;
    testCases.length = 0;
    bddStepDefinitions.length = 0;
    featuresDirect.length = 0;
  }
}

loadSupportFilesForProject(project, repoPath);
loadPlaywrightGlobalSetupFiles(project, repoPath);
const globalSupportHooks = collectGlobalSupportHooks(project, repoPath);

for (const row of manifest) {
  const rel = toPosix(row.file_path);
  const abs = path.join(repoPath, rel);
  if (!fs.existsSync(abs)) {
    parseErrors.push({ file_path: rel, error: "file_not_found" });
    continue;
  }
  let sf;
  try {
    sf = project.addSourceFileAtPath(abs);
  } catch (e) {
    parseErrors.push({ file_path: rel, error: String(e.message || e) });
    continue;
  }

  if (run2a && !skip2a2b) {
    const extracted = extractTestCasesFromFile(sf, row, repoMeta);
    if (!extracted || !Array.isArray(extracted.testCases)) {
      throw new Error(
        `extractTestCasesFromFile must return { testCases, bddStepDefinitions }; got ${typeof extracted}`
      );
    }
    testCases.push(...extracted.testCases);
    bddStepDefinitions.push(...(extracted.bddStepDefinitions || []));
  }
}

applyGlobalSupportHooksToTestCases(testCases, globalSupportHooks);

if ((run2b || run2c) && !skip2a2b) {
  const manifestByFile = new Map(manifest.map((r) => [toPosix(r.file_path), r]));
  for (const row of manifest) {
    const rel = toPosix(row.file_path);
    const abs = path.join(repoPath, rel);
    const sf = project.getSourceFile(abs);
    if (!sf) continue;
    const feats = extractDirectFeatures(sf, testCases, row, repoMeta);
    featuresDirect.push(...feats);
  }
  const globalFeats = extractGlobalSupportHookFeatures(globalSupportHooks, repoMeta);
  featuresDirect.push(...globalFeats);
} else if (skip2a2b) {
  reconcileGlobalSupportHookFeatures(featuresDirect, globalSupportHooks);
  if (globalSupportHooks.length) {
    const globalFeats = extractGlobalSupportHookFeatures(globalSupportHooks, repoMeta);
    const existingKeys = new Set(
      featuresDirect.filter((f) => f.is_shared_hook_feature).map((f) => f.hook_instance_key)
    );
    for (const f of globalFeats) {
      if (!existingKeys.has(f.hook_instance_key)) featuresDirect.push(f);
    }
  }
}

let featuresExpanded = [];
let helperEdges = [];
let unresolvedCalls = [];

if (run2c) {
  const manifestByFile = new Map(manifest.map((r) => [toPosix(r.file_path), r]));
  const expanded = expandHelpersForRepo({
    project,
    repoPath,
    testCases,
    directFeatures: featuresDirect,
    manifestByFile,
    repoMeta,
    globalSupportHooks,
    maxDepth: maxHelperDepth,
    maxHelperFiles,
  });
  featuresExpanded = attachHookFeaturesToExpanded(
    expanded.expandedFeatures,
    featuresDirect,
    testCases,
    expanded.hookExpandedByKey
  );
  helperEdges = expanded.helperEdges;
  unresolvedCalls = expanded.unresolvedCalls;
} else if (run2b) {
  featuresExpanded = attachHookFeaturesToExpanded([], featuresDirect, testCases);
}

let rq2RegistryMetrics = null;
if (run2b || run2c) {
  const inputRegistry = buildInputDataRegistry(repoPath, project, featuresDirect, featuresExpanded);
  rq2RegistryMetrics = summarizeRegistryMetrics(inputRegistry);
  featuresDirect = linkInputProvenance(featuresDirect, inputRegistry, project, repoPath);
  featuresExpanded = linkInputProvenance(featuresExpanded, inputRegistry, project, repoPath);
}

const uniqueHookKeys = new Set(
  featuresDirect.filter((f) => f.is_shared_hook_feature && f.hook_instance_key).map((f) => f.hook_instance_key)
);

const summary = {
  repo,
  commit,
  subphases_run: [run2a && "2a", run2b && "2b", run2c && "2c"].filter(Boolean),
  reused_from_2ab: Boolean(skip2a2b),
  global_support_hooks: globalSupportHooks.length,
  unique_hook_feature_instances: uniqueHookKeys.size,
  test_case_count: testCases.length,
  bdd_step_definition_count: bddStepDefinitions.length,
  features_direct_count: featuresDirect.length,
  features_expanded_count: featuresExpanded.length,
  helper_edges_count: helperEdges.length,
  unresolved_calls_count: unresolvedCalls.length,
  tests_with_direct_ui_actions: testCases.filter((t) => t.has_direct_ui_actions).length,
  tests_with_hook_ui_actions: testCases.filter((t) => t.has_hook_ui_actions).length,
  tests_with_helper_expanded_ui_actions: testCases.filter((t) => t.has_helper_expanded_ui_actions).length,
  tests_with_expanded_ui_actions: testCases.filter((t) => t.has_expanded_ui_actions).length,
  medium_confidence_test_cases: testCases.filter((t) => t.phase1_confidence === "medium").length,
  parse_errors: parseErrors.length,
  unresolved_rate:
    helperEdges.length > 0
      ? unresolvedCalls.length / (helperEdges.length + unresolvedCalls.length)
      : 0,
  rq2_registry: rq2RegistryMetrics,
};

let analyzedCommit = commit;
try {
  const { execSync } = require("child_process");
  analyzedCommit = execSync("git rev-parse HEAD", { cwd: repoPath, encoding: "utf-8" }).trim();
} catch (_) {
  /* keep manifest commit */
}

const result = {
  repo,
  repo_url: repoUrl,
  commit,
  analyzed_commit: analyzedCommit,
  commit_pin_match: commitsMatch(analyzedCommit, commit),
  subphases_run: summary.subphases_run,
  test_cases: testCases,
  bdd_step_definitions: bddStepDefinitions,
  features_direct: featuresDirect,
  features_expanded: featuresExpanded,
  helper_edges: helperEdges,
  unresolved_calls: unresolvedCalls,
  parse_errors: parseErrors,
  summary,
};

if (outputPath) {
  writePerRepoResult(outputPath, result);
} else {
  const stdoutPayload = {
    ...result,
    _note: "Full arrays omitted on stdout; use --output for complete split_v1 artifacts",
    counts: {
      test_cases: testCases.length,
      features_direct: featuresDirect.length,
      features_expanded: featuresExpanded.length,
      helper_edges: helperEdges.length,
      unresolved_calls: unresolvedCalls.length,
    },
  };
  delete stdoutPayload.test_cases;
  delete stdoutPayload.bdd_step_definitions;
  delete stdoutPayload.features_direct;
  delete stdoutPayload.features_expanded;
  delete stdoutPayload.helper_edges;
  delete stdoutPayload.unresolved_calls;
  process.stdout.write(JSON.stringify(stdoutPayload));
}
