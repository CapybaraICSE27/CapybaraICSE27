"use strict";

const { SyntaxKind, Node } = require("ts-morph");
const {
  collectTestLikeIdentifiers,
  isTestCaseDeclarationExpr,
  isGroupOrHookExpr,
  collectBddStepIdentifiers,
  isBddStepExpr,
  getCallbackArgFromCall,
  extractTestTitle,
  extractPlaywrightFixtures,
} = require("../shared/identifiers");
const { stableTestId, getLineRange, getCallbackBodyRange } = require("../shared/utils");
const { resolveFrameworkForFile, getImportModules } = require("../shared/framework");
const {
  DescribeStack,
  combineParameterizationFactors,
  decodeFlatRowIndex,
  isInsideTestEachCall,
  nextSuiteBoundaryLine,
} = require("../shared/describeStack");

function extractDescribeTitle(call) {
  const args = call.getArguments();
  if (!args.length) return "";
  const first = args[0];
  if (Node.isStringLiteral(first) || Node.isNoSubstitutionTemplateLiteral(first)) {
    return first.getLiteralText?.() ?? first.getText().replace(/^['"`]|['"`]$/g, "");
  }
  return "";
}

/** CallExpression whose first argument is the .each row table (handles curried test.each(table)(title, fn)). */
function resolveEachTableCall(call) {
  const callee = call.getExpression();
  if (callee.getKind() === SyntaxKind.CallExpression) {
    const innerText = callee.getText();
    if (/\.each\s*\(/.test(innerText)) return callee;
  }
  const calleeText = callee.getText();
  if (/\.each\b/.test(calleeText)) return call;
  return null;
}

function unwrapEachTableNode(node) {
  let cur = node;
  for (let depth = 0; depth < 8 && cur; depth++) {
    if (Node.isArrayLiteralExpression(cur)) return cur;
    if (Node.isParenthesizedExpression(cur)) {
      cur = cur.getExpression();
      continue;
    }
    if (Node.isAsExpression(cur)) {
      cur = cur.getExpression();
      continue;
    }
    if (typeof Node.isSatisfiesExpression === "function" && Node.isSatisfiesExpression(cur)) {
      cur = cur.getExpression();
      continue;
    }
    if (cur.getKind?.() === SyntaxKind.SatisfiesExpression) {
      cur = cur.getExpression();
      continue;
    }
    break;
  }
  return null;
}

function rowsFromArrayLiteral(arr) {
  const els = arr.getElements();
  return { rows: els.length > 0 ? els.length : 1, dynamic: false };
}

function resolveIdentifierToArrayLiteral(identifier, sourceFile) {
  if (!Node.isIdentifier(identifier) || !sourceFile) return null;
  const symbol = identifier.getSymbol();
  if (!symbol) return null;
  for (const decl of symbol.getDeclarations()) {
    if (decl.getSourceFile() !== sourceFile) continue;
    if (Node.isVariableDeclaration(decl)) {
      const arr = unwrapEachTableNode(decl.getInitializer());
      if (arr) return arr;
    }
  }
  return null;
}

/** Static row count from .each table arg (literal, satisfies/as wrap, or same-file const array). */
function countRowsFromTableArg(tableArg, sourceFile) {
  if (!tableArg) return null;
  const direct = unwrapEachTableNode(tableArg);
  if (direct) return rowsFromArrayLiteral(direct);
  if (Node.isIdentifier(tableArg)) {
    const resolved = resolveIdentifierToArrayLiteral(tableArg, sourceFile);
    if (resolved) return rowsFromArrayLiteral(resolved);
  }
  return null;
}

function countEachRows(call, sourceFile = null) {
  const eachCall = resolveEachTableCall(call) || call;
  const table = eachCall.getArguments()[0];
  if (!table) return { rows: 1, dynamic: true };

  const staticRows = countRowsFromTableArg(table, sourceFile);
  if (staticRows) return staticRows;

  if (Node.isTemplateExpression(table) || Node.isCallExpression(table)) {
    return { rows: 1, dynamic: true };
  }
  if (Node.isIdentifier(table)) {
    return { rows: 1, dynamic: true };
  }
  return { rows: 1, dynamic: true };
}

function resolveTestTitle(call, line, bdd, expr) {
  const title = extractTestTitle(call);
  if (title) return title;
  if (title === null) return `dynamic_title@${line}`;
  if (bdd) return `${expr} step`;
  return `anonymous@${line}`;
}

function bddStepIsInsideStandardTest(call, allCalls, testNames) {
  const line = call.getStartLineNumber();
  for (const other of allCalls) {
    let expr = "";
    try {
      expr = other.getExpression().getText();
    } catch (_) {
      continue;
    }
    if (!isTestCaseDeclarationExpr(expr, testNames).match) continue;
    const cb = getCallbackArgFromCall(other);
    if (!cb) continue;
    if (line >= cb.getStartLineNumber() && line <= cb.getEndLineNumber()) return true;
  }
  return false;
}

function buildParameterizationType(factorTypes) {
  if (!factorTypes.length) return "";
  const hasDescribe = factorTypes.includes("describe.each");
  const hasTest = factorTypes.includes("test.each");
  if (hasDescribe && hasTest) return "describe.each+test.each";
  if (hasDescribe) return "describe.each";
  if (hasTest) return "test.each";
  return "each";
}

function pushTestCaseRecord(testCases, record) {
  testCases.push({
    record_type: "test_case",
    hook_instance_keys: [],
    has_direct_ui_actions: false,
    has_direct_assertions: false,
    has_expanded_ui_actions: false,
    extraction_empty: false,
    ...record,
  });
}

function pushBddStepRecord(bddStepDefinitions, record) {
  bddStepDefinitions.push({
    record_type: "bdd_step_definition",
    suite_status: "normal",
    hook_instance_keys: [],
    ...record,
  });
}

function isGlobalSetupTeardownFile(filePath) {
  const base = (filePath || "").replace(/\\/g, "/").split("/").pop() || "";
  return /^global[-_]?(setup|teardown)\.(ts|js|mjs|cjs)$/i.test(base);
}

function extractTestCasesFromFile(sourceFile, manifestRow, repoMeta) {
  const filePath = manifestRow.file_path;
  if (isGlobalSetupTeardownFile(filePath)) {
    return { testCases: [], bddStepDefinitions: [] };
  }

  const imports = getImportModules(sourceFile);
  const { primary: framework } = resolveFrameworkForFile(manifestRow, imports);
  const { testNames, groupNames } = collectTestLikeIdentifiers(sourceFile);
  const bddNames = collectBddStepIdentifiers(sourceFile);
  const phase1Confidence = manifestRow.confidence || "high";

  const testCases = [];
  const bddStepDefinitions = [];
  const describeStack = new DescribeStack();
  const seenEachOuter = new Set();
  const fileEndLine = sourceFile.getEndLineNumber();

  const allCalls = sourceFile
    .getDescendantsOfKind(SyntaxKind.CallExpression)
    .sort((a, b) => a.getStartLineNumber() - b.getStartLineNumber());

  for (const call of allCalls) {
    const line = call.getStartLineNumber();

    let expr = "";
    try {
      expr = call.getExpression().getText();
    } catch (_) {
      continue;
    }

    const groupInfo = isGroupOrHookExpr(expr, testNames, groupNames);
    if (groupInfo && groupInfo.kind === "describe") {
      const parent = call.getParent();
      if (
        /\.each\s*\(/.test(expr) &&
        parent &&
        parent.getKind() === SyntaxKind.CallExpression &&
        parent.getExpression() === call
      ) {
        // Curried describe.each(table)(title, fn) — register on the outer call only.
        continue;
      }

      let title = extractDescribeTitle(call) || `describe@${line}`;
      let cb = getCallbackArgFromCall(call);
      let eachMeta = null;

      const eachTableCall = resolveEachTableCall(call);
      if (eachTableCall && /describe\.each\b/.test(eachTableCall.getText())) {
        eachMeta = countEachRows(eachTableCall, sourceFile);
      } else if (/\.each\s*\(/.test(expr)) {
        eachMeta = countEachRows(call, sourceFile);
        if (!cb) {
          const outer = call.getParent();
          if (outer && outer.getKind() === SyntaxKind.CallExpression && outer.getExpression() === call) {
            cb = getCallbackArgFromCall(outer);
            const parentTitle = extractDescribeTitle(outer);
            if (parentTitle) title = parentTitle;
          }
        }
      }

      const cbStart = cb ? cb.getStartLineNumber() : line;
      const cbEnd = cb
        ? cb.getEndLineNumber()
        : nextSuiteBoundaryLine(line, allCalls, testNames, groupNames, fileEndLine);

      if (/\.(skip|fixme)\b/.test(expr)) {
        describeStack.registerSkippedDescribe(title, cbStart, cbEnd);
        continue;
      }

      if (/\.only\b/.test(expr)) {
        describeStack.registerOnlyDescribe(title, cbStart, cbEnd, eachMeta);
        continue;
      }

      describeStack.registerDescribe(title, cbStart, cbEnd, eachMeta);
      continue;
    }

    if (groupInfo && groupInfo.kind === "fixture") {
      continue;
    }

    const testInfo = isTestCaseDeclarationExpr(expr, testNames);
    const bdd = isBddStepExpr(expr, bddNames);

    if (!testInfo.match && !bdd) continue;

    if (bdd && bddStepIsInsideStandardTest(call, allCalls, testNames)) {
      continue;
    }

    if (testInfo.parameterized || /\.each\s*\(/.test(expr)) {
      if (isInsideTestEachCall(call) && !/\.each\s*\(/.test(expr)) {
        continue;
      }
      const eachKey = `${line}:${expr}`;
      if (/\.each\s*\(/.test(expr)) {
        if (seenEachOuter.has(eachKey)) continue;
        seenEachOuter.add(eachKey);
      }
    } else if (isInsideTestEachCall(call)) {
      continue;
    }

    const callback = getCallbackArgFromCall(call);
    // Runtime annotations (test.skip(cond, "msg"), test.slow(), etc.) are not test declarations.
    if (testInfo.match && !callback) {
      continue;
    }

    const describe_path = describeStack.getPathAtLine(line);
    const callRange = getLineRange(call);
    const cbRange = callback ? getCallbackBodyRange(callback) : callRange;

    const baseName = resolveTestTitle(call, line, bdd, expr);

    const suite_status = describeStack.getSuiteStatusAtLine(line);
    let test_status = testInfo.match ? testInfo.status : "normal";
    if (suite_status === "skip" && test_status === "normal") {
      test_status = "skip";
    } else if (suite_status === "only" && test_status === "normal") {
      test_status = "only";
    }

    const testIsEach = Boolean(testInfo.parameterized || (/\.each\s*\(/.test(expr) && testInfo.match));
    const fixtures_used = extractPlaywrightFixtures(callback);
    const source_confidence = callback ? "high" : "medium";

    const paramFactors = [...describeStack.getEachFactorsAtLine(line)];
    if (testIsEach) {
      const eachTableCall = resolveEachTableCall(call);
      if (eachTableCall) {
        const eachInfo = countEachRows(eachTableCall, sourceFile);
        paramFactors.push({
          rows: eachInfo.rows,
          dynamic: eachInfo.dynamic,
          type: "test.each",
        });
      }
    }

    const { totalRows, dynamic, types } = combineParameterizationFactors(paramFactors);
    const is_parameterized = totalRows > 1 || paramFactors.length > 0;
    const parameterization_type = buildParameterizationType(types);
    const rowCount = totalRows;

    if (bdd) {
      pushBddStepRecord(bddStepDefinitions, {
        repo: repoMeta.repo,
        repo_url: repoMeta.repo_url,
        commit: manifestRow.commit || repoMeta.commit,
        file_path: filePath,
        file_url: manifestRow.file_url || repoMeta.file_url,
        framework,
        phase1_confidence: phase1Confidence,
        test_id: stableTestId([repoMeta.repo, filePath, describe_path, baseName, line, "bdd"]),
        test_name: baseName,
        test_status: "normal",
        start_line: callRange.start_line,
        end_line: callRange.end_line,
        callback_start_line: callback ? cbRange.start_line : null,
        callback_end_line: callback ? cbRange.end_line : null,
        declaration_line: line,
        describe_path,
        test_declaration_type: "bdd_step",
        is_parameterized: false,
        parameterization_type: "",
        parameter_row_index: null,
        parameter_row_count: null,
        parameterization_dynamic: false,
        parameterization_note: "",
        parameterization_scope: "",
        fixtures_used,
        source_confidence,
      });
      continue;
    }

    for (let rowIdx = 0; rowIdx < rowCount; rowIdx++) {
      const rowSuffix = rowCount > 1 ? ` [row ${rowIdx + 1}/${rowCount}]` : "";
      const test_name = baseName + rowSuffix;
      const factorIndices = paramFactors.length ? decodeFlatRowIndex(paramFactors, rowIdx) : [];

      const test_id = stableTestId([
        repoMeta.repo,
        filePath,
        describe_path,
        test_name,
        callRange.start_line,
        rowIdx,
        factorIndices.join(","),
      ]);

      pushTestCaseRecord(testCases, {
        repo: repoMeta.repo,
        repo_url: repoMeta.repo_url,
        commit: manifestRow.commit || repoMeta.commit,
        file_path: filePath,
        file_url: manifestRow.file_url || repoMeta.file_url,
        framework,
        phase1_confidence: phase1Confidence,
        test_id,
        test_name,
        test_status,
        suite_status,
        start_line: callRange.start_line,
        end_line: callRange.end_line,
        callback_start_line: callback ? cbRange.start_line : null,
        callback_end_line: callback ? cbRange.end_line : null,
        declaration_line: line,
        describe_path,
        test_declaration_type: testInfo.declType || expr,
        is_parameterized,
        parameterization_type,
        parameter_row_index: rowCount > 1 ? rowIdx : null,
        parameter_row_count: rowCount > 1 ? rowCount : null,
        parameterization_dynamic: dynamic,
        parameterization_note:
          rowCount > 1
            ? dynamic
              ? "shared_callback_body_dynamic_table"
              : paramFactors.some((f) => f.type === "describe.each")
                ? "describe_each_row_expansion"
                : "shared_callback_body"
            : "",
        parameterization_scope:
          rowCount > 1
            ? paramFactors.some((f) => f.type === "describe.each")
              ? "describe_each_rows"
              : "shared_ast_all_rows"
            : "",
        fixtures_used,
        source_confidence,
      });
    }
  }

  const isTestCafeFile = framework === "TestCafe" || /testcafe/i.test(String(manifestRow.repo_framework_context || ""));

  for (const call of allCalls) {
    if (!isTestCafeFile) break;

    let expr = "";
    try {
      expr = call.getExpression().getText();
    } catch (_) {
      continue;
    }
    if (!/\.test\s*$/.test(expr)) continue;
    if (call.getExpression().getKind() !== SyntaxKind.PropertyAccessExpression) continue;
    let chainText = "";
    try {
      chainText = call.getExpression().getExpression().getText();
    } catch (_) {
      continue;
    }
    if (!/fixture/i.test(chainText) && !/fixture/i.test(expr)) continue;

    const line = call.getStartLineNumber();
    const callback = getCallbackArgFromCall(call);
    if (!callback) continue;
    const callRange = getLineRange(call);
    const cbRange = getCallbackBodyRange(callback);
    const test_name = extractTestTitle(call) || `testcafe@${line}`;
    const test_id = stableTestId([repoMeta.repo, filePath, [], test_name, callRange.start_line]);
    if (testCases.some((t) => t.test_id === test_id)) continue;

    pushTestCaseRecord(testCases, {
      repo: repoMeta.repo,
      repo_url: repoMeta.repo_url,
      commit: manifestRow.commit || repoMeta.commit,
      file_path: filePath,
      file_url: manifestRow.file_url || repoMeta.file_url,
      framework: framework === "Unknown" ? "TestCafe" : framework,
      phase1_confidence: phase1Confidence,
      test_id,
      test_name,
      test_status: "normal",
      suite_status: "normal",
      start_line: callRange.start_line,
      end_line: callRange.end_line,
      callback_start_line: cbRange.start_line,
      callback_end_line: cbRange.end_line,
      declaration_line: line,
      describe_path: [],
      test_declaration_type: "testcafe_fixture_test",
      is_parameterized: false,
      parameterization_type: "",
      parameter_row_index: null,
      parameter_row_count: null,
      parameterization_dynamic: false,
      parameterization_note: "",
      parameterization_scope: "",
      fixtures_used: [],
      source_confidence: "high",
    });
  }

  return { testCases, bddStepDefinitions };
}

module.exports = {
  extractTestCasesFromFile,
  countEachRows,
  resolveEachTableCall,
  unwrapEachTableNode,
  countRowsFromTableArg,
};
