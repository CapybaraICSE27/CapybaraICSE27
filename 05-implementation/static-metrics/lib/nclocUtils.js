"use strict";

/**
 * Line-based LOC / NCLOC for a source slice (1-indexed inclusive line range).
 * NCLOC uses the `sloc` package (TypeScript lexer rules) for citable, maintained counting.
 */

const sloc = require("sloc");

function sliceLines(fullText, startLine, endLine) {
  const lines = fullText.split(/\r?\n/);
  const start = Math.max(1, startLine);
  const end = Math.min(lines.length, endLine);
  if (start > end || start > lines.length) return "";
  return lines.slice(start - 1, end).join("\n");
}

function physicalLoc(startLine, endLine) {
  if (!startLine || !endLine || endLine < startLine) return 0;
  return endLine - startLine + 1;
}

/**
 * Non-comment lines of code (NCLOC) — `sloc` "source" line count.
 * @see https://github.com/slangner/sloc (MIT; Markus Kohlhase)
 */
function countNcloc(text) {
  if (!text) return 0;
  return sloc(text, "ts").source;
}

/**
 * Legacy helper retained for diff/audit scripts comparing line classifiers.
 */
function lineHasNclocCode(line, state) {
  let i = 0;
  let hasCode = false;

  while (i < line.length) {
    const c = line[i];
    const next = line[i + 1];

    if (state.inBlockComment) {
      if (c === "*" && next === "/") {
        state.inBlockComment = false;
        i += 2;
        continue;
      }
      i += 1;
      continue;
    }

    if (state.inLineComment) {
      break;
    }

    if (state.stringQuote) {
      if (c === "\\") {
        i += 2;
        continue;
      }
      if (c === state.stringQuote) {
        state.stringQuote = null;
      }
      i += 1;
      continue;
    }

    if (c === "/" && next === "*") {
      state.inBlockComment = true;
      i += 2;
      continue;
    }
    if (c === "/" && next === "/") {
      state.inLineComment = true;
      i += 2;
      continue;
    }
    if (c === "'" || c === '"' || c === "`") {
      state.stringQuote = c;
      i += 1;
      continue;
    }
    if (!/\s/.test(c)) {
      hasCode = true;
    }
    i += 1;
  }

  state.inLineComment = false;
  return hasCode;
}

module.exports = {
  sliceLines,
  physicalLoc,
  countNcloc,
  lineHasNclocCode,
};
