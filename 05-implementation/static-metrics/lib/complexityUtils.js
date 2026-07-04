"use strict";

const { SyntaxKind } = require("ts-morph");
const { sliceLines, physicalLoc, countNcloc } = require("./nclocUtils");

const LOOP_KINDS = new Set([
  SyntaxKind.ForStatement,
  SyntaxKind.ForInStatement,
  SyntaxKind.ForOfStatement,
  SyntaxKind.WhileStatement,
  SyntaxKind.DoStatement,
]);

const NESTING_KINDS = new Set([
  SyntaxKind.IfStatement,
  SyntaxKind.ForStatement,
  SyntaxKind.ForInStatement,
  SyntaxKind.ForOfStatement,
  SyntaxKind.WhileStatement,
  SyntaxKind.DoStatement,
  SyntaxKind.SwitchStatement,
  SyntaxKind.TryStatement,
  SyntaxKind.Block,
  SyntaxKind.CatchClause,
]);

const STATEMENT_KINDS = new Set([
  SyntaxKind.ExpressionStatement,
  SyntaxKind.ReturnStatement,
  SyntaxKind.ThrowStatement,
  SyntaxKind.IfStatement,
  SyntaxKind.ForStatement,
  SyntaxKind.ForInStatement,
  SyntaxKind.ForOfStatement,
  SyntaxKind.WhileStatement,
  SyntaxKind.DoStatement,
  SyntaxKind.SwitchStatement,
  SyntaxKind.TryStatement,
  SyntaxKind.VariableStatement,
  SyntaxKind.BreakStatement,
  SyntaxKind.ContinueStatement,
  SyntaxKind.EmptyStatement,
  SyntaxKind.DebuggerStatement,
]);

function nodeStartInRange(node, startLine, endLine) {
  const line = node.getStartLineNumber();
  return line >= startLine && line <= endLine;
}

function computeMaxNestingDepth(sourceFile, startLine, endLine) {
  let maxDepth = 0;

  function walk(node, depth) {
    if (!nodeStartInRange(node, startLine, endLine)) {
      for (const child of node.getChildren()) walk(child, depth);
      return;
    }
    const kind = node.getKind();
    const nextDepth = NESTING_KINDS.has(kind) ? depth + 1 : depth;
    if (NESTING_KINDS.has(kind)) {
      maxDepth = Math.max(maxDepth, nextDepth);
    }
    for (const child of node.getChildren()) walk(child, nextDepth);
  }

  walk(sourceFile, 0);
  return maxDepth;
}

function computeComplexityMetrics(sourceFile, startLine, endLine) {
  let branchCount = 0;
  let loopCount = 0;
  let switchCaseCount = 0;
  let conditionalExprCount = 0;
  let tryCatchCount = 0;
  let logicalCondCount = 0;
  let statementCount = 0;
  let callCount = 0;

  for (const node of sourceFile.getDescendants()) {
    if (!nodeStartInRange(node, startLine, endLine)) continue;
    const kind = node.getKind();

    if (kind === SyntaxKind.IfStatement) branchCount += 1;
    if (LOOP_KINDS.has(kind)) loopCount += 1;
    if (kind === SyntaxKind.CaseClause || kind === SyntaxKind.DefaultClause) switchCaseCount += 1;
    if (kind === SyntaxKind.ConditionalExpression) conditionalExprCount += 1;
    if (kind === SyntaxKind.CatchClause) tryCatchCount += 1;
    if (STATEMENT_KINDS.has(kind)) statementCount += 1;
    if (kind === SyntaxKind.CallExpression) callCount += 1;

    if (kind === SyntaxKind.BinaryExpression) {
      const op = node.getOperatorToken().getKind();
      if (op === SyntaxKind.AmpersandAmpersandToken || op === SyntaxKind.BarBarToken) {
        logicalCondCount += 1;
      }
    }
  }

  const cyclomaticBasic =
    1 + branchCount + loopCount + switchCaseCount + conditionalExprCount + tryCatchCount;
  const cyclomaticExtended = cyclomaticBasic + logicalCondCount;
  const maxNesting = computeMaxNestingDepth(sourceFile, startLine, endLine);

  const fullText = sourceFile.getFullText();
  const slice = sliceLines(fullText, startLine, endLine);

  return {
    test_body_loc: physicalLoc(startLine, endLine),
    test_body_ncloc: countNcloc(slice),
    test_body_statement_count: statementCount,
    test_body_call_count: callCount,
    test_body_cyclomatic_basic: cyclomaticBasic,
    test_body_cyclomatic_extended: cyclomaticExtended,
    test_body_branch_count: branchCount,
    test_body_loop_count: loopCount,
    test_body_switch_case_count: switchCaseCount,
    test_body_conditional_expression_count: conditionalExprCount,
    test_body_logical_condition_count: logicalCondCount,
    test_body_try_catch_count: tryCatchCount,
    test_body_max_nesting_depth: maxNesting,
  };
}

module.exports = {
  computeComplexityMetrics,
};
