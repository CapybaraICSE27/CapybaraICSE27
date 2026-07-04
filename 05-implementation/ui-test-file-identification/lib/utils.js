"use strict";

const fs = require("fs");
const path = require("path");

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

function toPosix(p) {
  return String(p || "").split(path.sep).join("/");
}

function uniq(arr) {
  return [...new Set(arr)].filter(Boolean);
}

function readTextSafely(file, maxChars = 250000) {
  try {
    const text = fs.readFileSync(file, "utf8");
    return text.length > maxChars ? text.slice(0, maxChars) : text;
  } catch (_) {
    return "";
  }
}

function makeFileUrl(repoUrl, commit, relPath) {
  const base = String(repoUrl || "").replace(/\/+$/, "");
  const sha = String(commit || "HEAD");
  return `${base}/blob/${sha}/${relPath.replace(/\\/g, "/")}`;
}

module.exports = {
  parseArgs,
  toPosix,
  uniq,
  readTextSafely,
  makeFileUrl,
};
