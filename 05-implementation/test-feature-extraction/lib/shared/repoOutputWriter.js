"use strict";

const fs = require("fs");
const path = require("path");

const SPLIT_FORMAT = "split_v1";

function writeJsonl(filePath, rows) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  const fd = fs.openSync(filePath, "w");
  try {
    for (const row of rows || []) {
      fs.writeSync(fd, `${JSON.stringify(row)}\n`, "utf-8");
    }
  } finally {
    fs.closeSync(fd);
  }
}

function readJsonl(filePath) {
  if (!fs.existsSync(filePath)) return [];
  const text = fs.readFileSync(filePath, "utf-8");
  const rows = [];
  for (const line of text.split("\n")) {
    if (line.trim()) rows.push(JSON.parse(line));
  }
  return rows;
}

function sidecarPath(outputJsonPath, suffix) {
  const dir = path.dirname(outputJsonPath);
  const stem = path.basename(outputJsonPath, ".json");
  return path.join(dir, `${stem}.${suffix}.jsonl`);
}

/**
 * Persist per-repo results without a single giant JSON.stringify.
 * Index file: {repo}.json (metadata + summary + counts).
 * Sidecars: {repo}.test_cases.jsonl, {repo}.features_expanded.jsonl, etc.
 */
function writePerRepoResult(outputJsonPath, result) {
  fs.mkdirSync(path.dirname(outputJsonPath), { recursive: true });

  const arrays = {
    test_cases: result.test_cases || [],
    bdd_step_definitions: result.bdd_step_definitions || [],
    features_direct: result.features_direct || [],
    features_expanded: result.features_expanded || [],
    helper_edges: result.helper_edges || [],
    unresolved_calls: result.unresolved_calls || [],
  };

  for (const [suffix, rows] of Object.entries(arrays)) {
    writeJsonl(sidecarPath(outputJsonPath, suffix), rows);
  }

  const index = {
    repo: result.repo,
    repo_url: result.repo_url,
    commit: result.commit,
    analyzed_commit: result.analyzed_commit,
    commit_pin_match: result.commit_pin_match,
    subphases_run: result.subphases_run,
    storage_format: SPLIT_FORMAT,
    summary: result.summary,
    parse_errors: result.parse_errors || [],
    counts: {
      test_cases: arrays.test_cases.length,
      bdd_step_definitions: arrays.bdd_step_definitions.length,
      features_direct: arrays.features_direct.length,
      features_expanded: arrays.features_expanded.length,
      helper_edges: arrays.helper_edges.length,
      unresolved_calls: arrays.unresolved_calls.length,
    },
  };

  fs.writeFileSync(outputJsonPath, JSON.stringify(index, null, 2), "utf-8");
}

/**
 * Load per-repo cache (split_v1 sidecars or legacy monolithic JSON).
 */
function loadPerRepoResult(inputPath) {
  const raw = JSON.parse(fs.readFileSync(inputPath, "utf-8"));
  if (raw.storage_format !== SPLIT_FORMAT) {
    return raw;
  }

  const loaded = { ...raw };
  for (const suffix of [
    "test_cases",
    "bdd_step_definitions",
    "features_direct",
    "features_expanded",
    "helper_edges",
    "unresolved_calls",
  ]) {
    loaded[suffix] = readJsonl(sidecarPath(inputPath, suffix));
  }
  return loaded;
}

function splitSidecarsExist(outputJsonPath) {
  if (!fs.existsSync(outputJsonPath)) return false;
  try {
    const raw = JSON.parse(fs.readFileSync(outputJsonPath, "utf-8"));
    if (raw.storage_format !== SPLIT_FORMAT) return true;
    return fs.existsSync(sidecarPath(outputJsonPath, "test_cases"));
  } catch (_) {
    return false;
  }
}

module.exports = {
  SPLIT_FORMAT,
  writePerRepoResult,
  loadPerRepoResult,
  splitSidecarsExist,
  sidecarPath,
  writeJsonl,
  readJsonl,
};
