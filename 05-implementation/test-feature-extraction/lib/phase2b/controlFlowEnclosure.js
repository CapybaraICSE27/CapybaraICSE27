"use strict";

/**
 * RQ4-B: AST-derived control-flow enclosure for UI actions (Milestone 3).
 * Tracks loop/branch nesting during test-body and hook traversal.
 */

const { SyntaxKind, Node } = require("ts-morph");
const { getCallName } = require("./astPatternExtractor");

const CALLBACK_ITER_METHODS = new Set([
  "forEach", "map", "filter", "some", "every", "find", "flatMap", "reduce", "findIndex", "each",
]);

const LOOP_KINDS = new Set([
  SyntaxKind.ForStatement,
  SyntaxKind.ForOfStatement,
  SyntaxKind.ForInStatement,
  SyntaxKind.WhileStatement,
  SyntaxKind.DoStatement,
]);

function createControlFlowStack() {
  return {
    loopDepth: 0,
    branchDepth: 0,
    loopStack: [],
    branchStack: [],
  };
}

function isCallbackIterationCall(node) {
  if (!Node.isCallExpression(node)) return false;
  const name = getCallName(node);
  if (!CALLBACK_ITER_METHODS.has(name)) return false;
  const args = node.getArguments();
  if (!args.length) return false;
  const first = args[0];
  return Node.isArrowFunction(first) || Node.isFunctionExpression(first);
}

function enterCallbackIterationLoop(stack) {
  if (!stack) return;
  stack.loopDepth += 1;
  stack.loopStack.push({ kind: "callback_iteration", method: "" });
}

function exitCallbackIterationLoop(stack) {
  if (!stack) return;
  if (stack.loopDepth > 0) stack.loopDepth -= 1;
  if (stack.loopStack.length) stack.loopStack.pop();
}

function callbackIterationArg(node) {
  if (!isCallbackIterationCall(node)) return null;
  return node.getArguments()[0] || null;
}

function forEachChildRespectingCallbackIteration(node, stack, visitChild) {
  const cbArg = callbackIterationArg(node);
  if (!cbArg) {
    node.forEachChild(visitChild);
    return;
  }
  const callbackMethod = getCallName(node) || "";
  node.forEachChild((child) => {
    const appliesLoop = child === cbArg || nodeContainsDescendant(child, cbArg);
    if (appliesLoop) {
      enterCallbackIterationLoop(stack);
      if (stack?.loopStack?.length) {
        stack.loopStack[stack.loopStack.length - 1].method = callbackMethod;
        stack.loopStack[stack.loopStack.length - 1].node = node;
      }
    }
    try {
      visitChild(child);
    } finally {
      if (appliesLoop) exitCallbackIterationLoop(stack);
    }
  });
}

function enterControlFlowNode(stack, node) {
  if (!node || !stack) return;
  const kind = node.getKind();
  if (LOOP_KINDS.has(kind)) {
    stack.loopDepth += 1;
    stack.loopStack.push({ kind, node });
    return;
  }
  if (Node.isIfStatement(node)) {
    stack.branchDepth += 1;
    stack.branchStack.push({ kind: "if", node });
    return;
  }
  if (Node.isSwitchStatement(node)) {
    stack.branchDepth += 1;
    stack.branchStack.push({ kind: "switch", node });
    return;
  }
  if (Node.isConditionalExpression(node)) {
    stack.branchDepth += 1;
    stack.branchStack.push({ kind: "conditional", node });
    return;
  }
  if (Node.isTryStatement(node)) {
    stack.branchDepth += 1;
    stack.branchStack.push({ kind: "try_catch", node });
  }
}

function exitControlFlowNode(stack, node) {
  if (!node || !stack) return;
  const kind = node.getKind();
  if (LOOP_KINDS.has(kind)) {
    if (stack.loopDepth > 0) stack.loopDepth -= 1;
    if (stack.loopStack.length) stack.loopStack.pop();
    return;
  }
  if (
    Node.isIfStatement(node) ||
    Node.isSwitchStatement(node) ||
    Node.isConditionalExpression(node) ||
    Node.isTryStatement(node)
  ) {
    if (stack.branchDepth > 0) stack.branchDepth -= 1;
    if (stack.branchStack.length) stack.branchStack.pop();
  }
}

function nodeContainsDescendant(ancestor, target) {
  if (!ancestor || !target || ancestor === target) return false;
  let found = false;
  ancestor.forEachDescendant((d) => {
    if (d === target) found = true;
  });
  return found;
}

function resolveBranchArm(callNode, branchEntry) {
  if (!branchEntry || !callNode) return "";
  const { kind, node } = branchEntry;
  if (kind === "if") {
    const thenStmt = node.getThenStatement();
    const elseStmt = node.getElseStatement();
    if (thenStmt && nodeContainsDescendant(thenStmt, callNode)) return "then";
    if (elseStmt && nodeContainsDescendant(elseStmt, callNode)) return "else";
    return "";
  }
  if (kind === "switch") {
    return "case";
  }
  if (kind === "try_catch") {
    const tryBlock = node.getTryBlock();
    const catchClause = node.getCatchClause();
    const finallyBlock = node.getFinallyBlock();
    if (tryBlock && nodeContainsDescendant(tryBlock, callNode)) return "try";
    if (catchClause && nodeContainsDescendant(catchClause, callNode)) return "catch";
    if (finallyBlock && nodeContainsDescendant(finallyBlock, callNode)) return "finally";
    return "";
  }
  if (kind === "conditional") {
    const whenTrue = node.getWhenTrue();
    const whenFalse = node.getWhenFalse();
    if (whenTrue && nodeContainsDescendant(whenTrue, callNode)) return "then";
    if (whenFalse && nodeContainsDescendant(whenFalse, callNode)) return "else";
    return "";
  }
  return "";
}

function callbackReceiverExpression(loopEntry) {
  const node = loopEntry?.node;
  if (!node || !Node.isCallExpression(node)) return "";
  const expr = node.getExpression();
  if (Node.isPropertyAccessExpression(expr)) {
    return expr.getExpression().getText().slice(0, 500);
  }
  return "";
}

function ancestorChainSummary(stack) {
  const entries = [];
  for (const loop of stack?.loopStack || []) {
    const kind = loop.kind === "callback_iteration"
      ? `callback_iteration:${loop.method || ""}`
      : SyntaxKind[loop.kind] || String(loop.kind || "");
    entries.push(`loop:${kind}`);
  }
  for (const branch of stack?.branchStack || []) {
    entries.push(`branch:${branch.kind || ""}`);
  }
  return entries.filter(Boolean).join(">");
}

function cloneControlFlowStack(stack) {
  if (!stack) return createControlFlowStack();
  return {
    loopDepth: stack.loopDepth || 0,
    branchDepth: stack.branchDepth || 0,
    loopStack: [...(stack.loopStack || [])],
    branchStack: [...(stack.branchStack || [])],
  };
}

function findEnclosingFunctionBody(callExpr) {
  if (!callExpr) return null;
  let p = callExpr;
  while (p) {
    if (Node.isArrowFunction(p)) {
      const body = p.getBody();
      return Node.isBlock(body) ? body : p;
    }
    if (Node.isFunctionExpression(p) || Node.isFunctionDeclaration(p)) {
      return p.getBody();
    }
    p = p.getParent();
  }
  return null;
}

function captureControlFlowStackAtNode(root, targetNode, initialStack) {
  if (!root || !targetNode) {
    return initialStack ? cloneControlFlowStack(initialStack) : createControlFlowStack();
  }
  const stack = initialStack ? cloneControlFlowStack(initialStack) : createControlFlowStack();
  let captured = null;

  function walk(node) {
    if (!node || captured) return;
    if (node === targetNode) {
      captured = cloneControlFlowStack(stack);
      return;
    }
    enterControlFlowNode(stack, node);
    try {
      forEachChildRespectingCallbackIteration(node, stack, walk);
    } finally {
      exitControlFlowNode(stack, node);
    }
  }

  walk(root);
  return captured || (initialStack ? cloneControlFlowStack(initialStack) : createControlFlowStack());
}

function clippedNodeText(node, maxLen = 1500) {
  if (!node) return { text: "", truncated: false };
  try {
    const text = node.getText();
    if (text.length <= maxLen) return { text, truncated: false };
    return { text: text.slice(0, maxLen), truncated: true };
  } catch (_) {
    return { text: "", truncated: false };
  }
}

function nearestEvidenceNode(topLoop, topBranch) {
  const candidates = [topLoop?.node || null, topBranch?.node || null].filter(Boolean);
  if (!candidates.length) return null;
  candidates.sort((a, b) => {
    try {
      return b.getStart() - a.getStart();
    } catch (_) {
      return 0;
    }
  });
  return candidates[0];
}

function snapshotControlFlowEnclosure(stack, callNode) {
  const loopDepth = stack?.loopDepth || 0;
  const branchDepth = stack?.branchDepth || 0;
  let enclosure = "none";
  if (loopDepth > 0 && branchDepth > 0) enclosure = "loop_and_branch";
  else if (loopDepth > 0) enclosure = "loop";
  else if (branchDepth > 0) enclosure = "branch";

  const topBranch = stack?.branchStack?.length
    ? stack.branchStack[stack.branchStack.length - 1]
    : null;
  const topLoop = stack?.loopStack?.length
    ? stack.loopStack[stack.loopStack.length - 1]
    : null;
  const branchKind = topBranch?.kind || "";
  const branchArm = resolveBranchArm(callNode, topBranch);
  const evidenceNode = nearestEvidenceNode(topLoop, topBranch);
  const loopKind = topLoop?.kind === "callback_iteration"
    ? "callback_iteration"
    : topLoop?.kind
      ? SyntaxKind[topLoop.kind] || String(topLoop.kind)
      : "";
  const snippet = clippedNodeText(evidenceNode, 1500);

  return {
    control_flow_enclosure: enclosure,
    control_flow_loop_depth: loopDepth,
    control_flow_branch_depth: branchDepth,
    control_flow_branch_kind: branchKind,
    control_flow_branch_arm: branchArm,
    control_flow_parent_kind: branchKind || loopKind,
    control_flow_parent_line: evidenceNode ? evidenceNode.getStartLineNumber() : "",
    control_flow_parent_start_offset: evidenceNode ? evidenceNode.getStart() : "",
    control_flow_parent_end_offset: evidenceNode ? evidenceNode.getEnd() : "",
    control_flow_callback_method: topLoop?.method || "",
    control_flow_callback_receiver: callbackReceiverExpression(topLoop),
    control_flow_ancestor_chain: ancestorChainSummary(stack),
    enclosing_control_flow_snippet: snippet.text,
    enclosing_control_flow_snippet_truncated: snippet.truncated,
  };
}

module.exports = {
  createControlFlowStack,
  cloneControlFlowStack,
  enterControlFlowNode,
  exitControlFlowNode,
  enterCallbackIterationLoop,
  exitCallbackIterationLoop,
  isCallbackIterationCall,
  forEachChildRespectingCallbackIteration,
  snapshotControlFlowEnclosure,
  findEnclosingFunctionBody,
  captureControlFlowStackAtNode,
};
