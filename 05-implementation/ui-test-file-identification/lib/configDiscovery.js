"use strict";

const fs = require("fs");
const path = require("path");
const fg = require("fast-glob");

const { toPosix, uniq } = require("./utils");

/**
 * Strip glob wildcards to a directory prefix (legacy fallback).
 */
function deriveDirFromGlob(raw) {
  if (!raw) return "";
  let s = String(raw).trim().replace(/^['"`]/, "").replace(/['"`]$/, "");
  s = s.replace(/\\/g, "/");
  if (s.startsWith("!")) return "";
  const wildcard = s.search(/[*{[]/);
  if (wildcard >= 0) s = s.slice(0, wildcard);
  if (/\.(ts|tsx|js|jsx|mjs|cjs)$/i.test(s)) s = path.posix.dirname(s);
  s = s.replace(/\/+$/, "");
  if (!s || s === ".") return "";
  return s;
}

const FG_IGNORE = ["**/node_modules/**", "**/.git/**", "**/dist/**", "**/build/**"];

function isInside(parent, child) {
  const rel = path.relative(parent, child);
  return rel === "" || (!rel.startsWith("..") && !path.isAbsolute(rel));
}

/** Safe prefix check for repo-relative posix paths (segment-wise, not string prefix). */
function isPosixPathInside(parentRel, childRel) {
  const parent = String(parentRel || "").replace(/\\/g, "/");
  const child = String(childRel || "").replace(/\\/g, "/");
  if (!parent || parent === ".") return true;
  if (child === parent) return true;
  const pParts = parent.split("/").filter(Boolean);
  const cParts = child.split("/").filter(Boolean);
  if (cParts.length < pParts.length) return false;
  for (let i = 0; i < pParts.length; i++) {
    if (cParts[i] !== pParts[i]) return false;
  }
  return true;
}

/**
 * Resolve glob patterns relative to a config file directory; return repo-relative parent dirs.
 */
function dirsFromGlobPatterns(repoPath, configDir, patterns, { maxDirs = 48 } = {}) {
  const dirs = new Set();
  const repoAbs = path.resolve(repoPath);
  const configAbs = path.resolve(configDir);
  const normalized = (patterns || [])
    .map((p) => String(p || "").trim())
    .filter(Boolean)
    .filter((p) => !p.startsWith("!"))
    .flatMap((p) => {
      const d = deriveDirFromGlob(p);
      return d ? [d] : [];
    });

  for (const pat of patterns || []) {
    const p = String(pat || "").trim();
    if (!p || p.startsWith("!") || !/[*{[]/.test(p)) continue;
    try {
      const matches = fg.sync(p, {
        cwd: configAbs,
        onlyFiles: true,
        absolute: false,
        suppressErrors: true,
        ignore: FG_IGNORE,
      });
      for (const m of matches.slice(0, 200)) {
        const absDir = path.dirname(path.join(configAbs, m));
        if (!isInside(repoAbs, absDir)) continue;
        const relDir = toPosix(path.relative(repoAbs, absDir));
        if (relDir && relDir !== ".") dirs.add(relDir);
        if (dirs.size >= maxDirs) break;
      }
    } catch (_) {
      /* ignore bad globs */
    }
    if (dirs.size >= maxDirs) break;
  }

  for (const d of normalized) {
    const absDir = path.resolve(configAbs, d);
    if (!isInside(repoAbs, absDir)) continue;
    const relDir = toPosix(path.relative(repoAbs, absDir));
    if (relDir && relDir !== ".") dirs.add(relDir);
  }
  return [...dirs];
}

function splitTopLevelArgs(argText) {
  const args = [];
  let current = "";
  let quote = null;
  let depth = 0;

  for (let i = 0; i < argText.length; i++) {
    const ch = argText[i];
    const prev = i > 0 ? argText[i - 1] : "";

    if (quote) {
      current += ch;
      if (ch === quote && prev !== "\\") quote = null;
      continue;
    }

    if (ch === "'" || ch === '"' || ch === "`") {
      quote = ch;
      current += ch;
      continue;
    }

    if (ch === "(" || ch === "[" || ch === "{") depth++;
    if (ch === ")" || ch === "]" || ch === "}") depth--;

    if (ch === "," && depth === 0) {
      args.push(current.trim());
      current = "";
    } else {
      current += ch;
    }
  }

  if (current.trim()) args.push(current.trim());
  return args;
}

function stripQuotes(raw) {
  if (!raw) return "";
  let s = String(raw).trim();
  if (
    (s.startsWith("'") && s.endsWith("'")) ||
    (s.startsWith('"') && s.endsWith('"')) ||
    (s.startsWith("`") && s.endsWith("`") && !s.includes("${"))
  ) {
    return s.slice(1, -1);
  }
  return "";
}

function collectSimpleConfigConstants(text) {
  const constants = {};
  const stringConstRe = /\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(['"`])([^'"`${}]+)\2\s*;?/g;
  let m;
  while ((m = stringConstRe.exec(text)) !== null) {
    constants[m[1]] = [m[3]];
  }
  const arrayConstRe = /\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*\[([\s\S]{0,3000}?)\]\s*;?/g;
  while ((m = arrayConstRe.exec(text)) !== null) {
    const values = [];
    const stringRe = /['"`]([^'"`${}]+)['"`]/g;
    let sm;
    while ((sm = stringRe.exec(m[2])) !== null) {
      values.push(sm[1]);
    }
    if (values.length > 0) constants[m[1]] = values;
  }
  const pathConstRe =
    /\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:path\.)?(?:join|resolve)\s*\(([^)]{0,1000})\)\s*;?/g;
  while ((m = pathConstRe.exec(text)) !== null) {
    const resolved = resolveSimplePathJoinExpression(m[2]);
    if (resolved.length > 0) constants[m[1]] = resolved;
  }
  return constants;
}

function resolveSimplePathJoinExpression(argText) {
  const parts = splitTopLevelArgs(argText)
    .map((arg) => arg.trim())
    .filter((arg) => arg && arg !== "__dirname" && arg !== "__filename" && arg !== "process.cwd()")
    .map(stripQuotes)
    .filter(Boolean);
  if (parts.length === 0) return [];
  return [parts.join("/")];
}

function resolveConfigExpression(expr, constants) {
  const out = [];
  const e = String(expr || "").trim().replace(/,$/, "").trim();
  const quoted = stripQuotes(e);
  if (quoted) return [quoted];
  if (/^[A-Za-z_$][\w$]*$/.test(e) && constants[e]) {
    return constants[e];
  }
  if (e.startsWith("[") && e.endsWith("]")) {
    const body = e.slice(1, -1);
    for (const item of splitTopLevelArgs(body)) {
      out.push(...resolveConfigExpression(item, constants));
    }
    return out;
  }
  const pathJoinMatch = e.match(/(?:path\.)?(?:join|resolve)\s*\(([\s\S]{0,1000})\)/);
  if (pathJoinMatch) {
    return resolveSimplePathJoinExpression(pathJoinMatch[1]);
  }
  return out;
}

module.exports = {
  deriveDirFromGlob,
  dirsFromGlobPatterns,
  isInside,
  isPosixPathInside,
  splitTopLevelArgs,
  stripQuotes,
  collectSimpleConfigConstants,
  resolveSimplePathJoinExpression,
  resolveConfigExpression,
};
