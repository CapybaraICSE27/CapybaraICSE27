"use strict";

const fs = require("fs");
const path = require("path");
const fg = require("fast-glob");
const { IGNORE_DIR_NAMES } = require("../shared/patterns");

const LEGACY_SUPPORT_ROOTS = [
  "test/support",
  "tests/support",
  "e2e/support",
  "playwright/support",
];

const SUPPORT_FILE_BASENAMES = new Set([
  "commands.js",
  "commands.ts",
  "commands.tsx",
  "e2e.js",
  "e2e.ts",
  "component.js",
  "component.ts",
]);

const MAX_SUPPORT_FILES = 200;
const MAX_SUPPORT_ROOTS = 32;
const MAX_REPO_WALK_DEPTH = 12;
const MAX_WALK_DEPTH = 6;

function isTypingsOnlyFile(filePath) {
  return /\.d\.ts$/i.test(filePath);
}

function isSupportTreeRel(rel) {
  const lower = rel.toLowerCase().replace(/\\/g, "/");
  if (/(?:^|\/)cypress\/(?:support|plugins)(?:\/|$)/.test(lower)) return true;
  if (/(?:^|\/)cypress\/[^/]+\/support(?:\/|$)/.test(lower)) return true;
  if (/(?:^|\/)e2e-tests\/cypress\/(?:tests\/)?support(?:\/|$)/.test(lower)) return true;
  return LEGACY_SUPPORT_ROOTS.some((p) => lower === p || lower.startsWith(p + "/"));
}

function isSupportFilePath(rel) {
  const lower = rel.toLowerCase().replace(/\\/g, "/");
  const base = path.basename(lower);
  if (SUPPORT_FILE_BASENAMES.has(base)) return true;
  if (/^playwright\.config\.(ts|js|mjs|cjs)$/.test(base)) return true;
  if (/global[-_]?setup\.(ts|js|mjs|cjs)$/.test(base)) return true;
  return isSupportTreeRel(lower);
}

/**
 * Find all Cypress/Playwright support trees (including monorepo package paths).
 */
function discoverSupportRoots(repoPath, maxRoots = MAX_SUPPORT_ROOTS) {
  const roots = new Set();

  const globHits = fg.sync(
    [
      "**/cypress/support",
      "**/cypress/plugins",
      "**/cypress/*/support",
      "**/playwright/support",
      "**/e2e/support",
      "**/tests/support",
      "**/test/support",
    ],
    {
      cwd: repoPath,
      onlyDirectories: true,
      absolute: true,
      suppressErrors: true,
      ignore: ["**/node_modules/**", "**/.git/**"],
    }
  );
  for (const abs of globHits) {
    roots.add(abs);
    if (roots.size >= maxRoots) break;
  }

  for (const rel of LEGACY_SUPPORT_ROOTS) {
    const abs = path.join(repoPath, rel);
    if (fs.existsSync(abs)) roots.add(abs);
  }

  return [...roots].slice(0, maxRoots);
}

function walkSupportDir(dir, repoPath, depth, out) {
  if (depth > MAX_WALK_DEPTH || out.size >= MAX_SUPPORT_FILES) return;
  let entries = [];
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch (_) {
    return;
  }

  for (const ent of entries) {
    if (out.size >= MAX_SUPPORT_FILES) break;
    const abs = path.join(dir, ent.name);
    const rel = path.relative(repoPath, abs).replace(/\\/g, "/");
    if (rel.startsWith("..")) continue;

    if (ent.isDirectory()) {
      if (IGNORE_DIR_NAMES.has(ent.name)) continue;
      walkSupportDir(abs, repoPath, depth + 1, out);
      continue;
    }

    if (!/\.(js|ts|tsx|mjs|cjs)$/i.test(ent.name)) continue;
    if (isTypingsOnlyFile(abs)) continue;
    out.add(abs);
  }
}

function prioritizeSupportFiles(files) {
  return [...files].sort((a, b) => {
    const score = (p) => {
      const base = path.basename(p).toLowerCase();
      if (base.startsWith("commands")) return 0;
      if (base === "e2e.ts" || base === "e2e.js") return 1;
      if (base.startsWith("index.")) return 2;
      if (/\/api\//i.test(p)) return 3;
      return 4;
    };
    const sa = score(a);
    const sb = score(b);
    if (sa !== sb) return sa - sb;
    return a.localeCompare(b);
  });
}

/**
 * Add Cypress/Playwright support/command files into the ts-morph project.
 */
function loadSupportFilesForProject(project, repoPath) {
  const found = new Set();
  const roots = discoverSupportRoots(repoPath);
  for (const base of roots) {
    if (found.size >= MAX_SUPPORT_FILES) break;
    walkSupportDir(base, repoPath, 0, found);
  }

  let added = 0;
  for (const abs of prioritizeSupportFiles(found)) {
    if (added >= MAX_SUPPORT_FILES) break;
    try {
      if (!project.getSourceFile(abs)) {
        project.addSourceFileAtPath(abs);
        added += 1;
      }
    } catch (_) {
      /* ignore parse errors */
    }
  }
  return added;
}

module.exports = {
  loadSupportFilesForProject,
  discoverSupportRoots,
  isSupportFilePath,
  isSupportTreeRel,
  isTypingsOnlyFile,
};
