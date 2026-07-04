"use strict";

/**
 * Nested describe paths from callback line ranges (AST-aligned containment).
 */
class DescribeStack {
  constructor() {
    /** @type {{ title: string, callbackStart: number, callbackEnd: number, suiteStatus: string, eachRows?: number, eachDynamic?: boolean, order: number }[]} */
    this.suites = [];
  }

  registerSuite(title, callbackStart, callbackEnd, options = {}) {
    const { suiteStatus = "normal", eachMeta = null } = options;
    const entry = {
      title: title || "suite",
      callbackStart: callbackStart || 0,
      callbackEnd: callbackEnd || Number.MAX_SAFE_INTEGER,
      suiteStatus,
      order: this.suites.length,
    };
    if (eachMeta && eachMeta.rows > 1) {
      entry.eachRows = eachMeta.rows;
      entry.eachDynamic = Boolean(eachMeta.dynamic);
    }
    this.suites.push(entry);
  }

  registerDescribe(title, callbackStart, callbackEnd, eachMeta = null) {
    this.registerSuite(title, callbackStart, callbackEnd, { suiteStatus: "normal", eachMeta });
  }

  registerSkippedDescribe(title, callbackStart, callbackEnd) {
    this.registerSuite(title, callbackStart, callbackEnd, { suiteStatus: "skip" });
  }

  registerOnlyDescribe(title, callbackStart, callbackEnd, eachMeta = null) {
    this.registerSuite(title, callbackStart, callbackEnd, { suiteStatus: "only", eachMeta });
  }

  /**
   * Outermost-to-innermost suite objects whose callback contains `line`.
   */
  getSuitesChainAtLine(line) {
    const matching = this.suites.filter(
      (s) => line >= s.callbackStart && line <= s.callbackEnd
    );
    if (!matching.length) return [];

    matching.sort(
      (a, b) =>
        a.callbackStart - b.callbackStart ||
        b.callbackEnd - a.callbackEnd ||
        a.callbackEnd - a.callbackStart - (b.callbackEnd - b.callbackStart)
    );

    const anchor = matching.reduce((best, s) => {
      const span = s.callbackEnd - s.callbackStart;
      const bestSpan = best.callbackEnd - best.callbackStart;
      if (span < bestSpan) return s;
      if (span === bestSpan && (s.order ?? 0) > (best.order ?? 0)) return s;
      return best;
    }, matching[0]);

    const nested = matching.filter(
      (s) =>
        s.callbackStart <= anchor.callbackStart &&
        s.callbackEnd >= anchor.callbackEnd
    );

    nested.sort(
      (a, b) =>
        a.callbackStart - b.callbackStart ||
        b.callbackEnd - a.callbackEnd
    );

    const chain = [];
    for (const s of nested) {
      if (!chain.length) {
        chain.push(s);
        continue;
      }
      const prev = chain[chain.length - 1];
      if (s.callbackStart >= prev.callbackStart && s.callbackEnd <= prev.callbackEnd) {
        if (s.callbackStart > prev.callbackStart || s.callbackEnd < prev.callbackEnd) {
          chain.push(s);
        }
      }
    }
    return chain;
  }

  getPathAtLine(line) {
    return this.getSuitesChainAtLine(line).map((s) => s.title);
  }

  /** skip > only > normal when nested suites disagree. */
  getSuiteStatusAtLine(line) {
    const chain = this.getSuitesChainAtLine(line);
    if (chain.some((s) => s.suiteStatus === "skip")) return "skip";
    if (chain.some((s) => s.suiteStatus === "only")) return "only";
    return "normal";
  }

  /** Innermost-to-outermost describe.each factors active at `line`. */
  getEachFactorsAtLine(line) {
    return this.getSuitesChainAtLine(line)
      .filter((s) => s.eachRows > 1)
      .map((s) => ({ rows: s.eachRows, dynamic: Boolean(s.eachDynamic), type: "describe.each" }));
  }
}

/**
 * Cartesian row count and per-factor row index for nested describe.each / test.each.
 */
function combineParameterizationFactors(factors) {
  if (!factors.length) {
    return { totalRows: 1, dynamic: false, types: [] };
  }
  const totalRows = factors.reduce((p, f) => p * f.rows, 1);
  const dynamic = factors.some((f) => f.dynamic);
  const types = factors.map((f) => f.type).filter(Boolean);
  return { totalRows, dynamic, types };
}

function decodeFlatRowIndex(factors, flatIdx) {
  const indices = [];
  let remaining = flatIdx;
  for (let i = factors.length - 1; i >= 0; i--) {
    indices[i] = remaining % factors[i].rows;
    remaining = Math.floor(remaining / factors[i].rows);
  }
  return indices;
}

/**
 * Cap describe range when there is no callback (avoid spanning to EOF).
 */
function nextSuiteBoundaryLine(line, allCalls, testNames, groupNames, fileEndLine) {
  for (const call of allCalls) {
    const callLine = call.getStartLineNumber();
    if (callLine <= line) continue;
    let expr = "";
    try {
      expr = call.getExpression().getText();
    } catch (_) {
      continue;
    }
    const { isGroupOrHookExpr, isTestCaseDeclarationExpr } = require("../shared/identifiers");
    const groupInfo = groupNames && testNames ? isGroupOrHookExpr(expr, testNames, groupNames) : null;
    if (groupInfo && (groupInfo.kind === "describe" || groupInfo.kind === "hook")) return callLine - 1;
    if (testNames && isTestCaseDeclarationExpr(expr, testNames).match) {
      return callLine - 1;
    }
  }
  return fileEndLine;
}

function isInsideTestEachCall(call) {
  let node = call.getParent();
  while (node) {
    if (node.getKind && node.getKind() === require("ts-morph").SyntaxKind.CallExpression) {
      try {
        const expr = node.getExpression().getText();
        // Suppress row-template tests inside test.each, but not tests inside describe.each suites.
        if (/\.each\s*\(/.test(expr) && !/(^|\.)(describe)\.each\b/.test(expr)) {
          return true;
        }
      } catch (_) {
        /* ignore */
      }
    }
    node = node.getParent();
  }
  return false;
}

module.exports = {
  DescribeStack,
  combineParameterizationFactors,
  decodeFlatRowIndex,
  isInsideTestEachCall,
  nextSuiteBoundaryLine,
};
