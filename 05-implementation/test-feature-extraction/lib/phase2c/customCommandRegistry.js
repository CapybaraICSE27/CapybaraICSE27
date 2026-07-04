"use strict";

const path = require("path");
const fs = require("fs");
const { SyntaxKind, Node } = require("ts-morph");
const { toPosix } = require("../shared/utils");
const { collectTestLikeIdentifiers } = require("../shared/identifiers");
const { discoverSupportRoots } = require("./supportFileLoader");
const { isCypressLocatorQueryCommand } = require("../shared/patterns");

const PLAYWRIGHT_EXTEND_ROOTS = new Set(["test", "base"]);

const CYPRESS_COMMANDS_RE = /Cypress\.Commands\.(add|addAll|overwrite)\b/;
const TASK_SETUP_TOKENS = new Set([
  "cleanup", "create", "database", "db", "delete", "drop", "factory", "fixture",
  "insert", "migrate", "migration", "patch", "remove", "reset", "restore", "seed",
  "server", "start", "stop", "teardown", "truncate", "update", "upsert",
]);
const TASK_DIAGNOSTIC_TOKENS = new Set([
  "debug", "error", "info", "log", "logger", "print", "table", "trace", "warn",
]);
const TASK_BACKEND_CALL_TOKENS = new Set([
  "cleanup", "create", "database", "db", "delete", "drop", "factory", "insert",
  "migrate", "patch", "remove", "reset", "restore", "seed", "truncate", "update", "upsert",
]);

const CYPRESS_TEST_DATA_COMMANDS = new Set(["request", "task", "fixture", "readFile", "writeFile"]);
const CYPRESS_LOCATOR_ONLY_COMMANDS = new Set(["get", "contains", "find"]);
const CYPRESS_UI_ACTION_COMMANDS = new Set([
  "click", "dblclick", "type", "realType", "visit", "fill", "select", "check",
  "uncheck", "trigger", "mount", "clear", "press", "realClick", "realPress",
  "realHover", "hover", "tap",
]);

function isCypressCommandsRegistration(expr) {
  return CYPRESS_COMMANDS_RE.test(expr);
}

function identifierTokens(text) {
  const tokens = [];
  for (const ident of String(text || "").matchAll(/[A-Za-z_$][A-Za-z0-9_$]*/g)) {
    for (const part of ident[0].split(/[_$]+/)) {
      if (!part) continue;
      const pieces = part.match(/[A-Z]+(?=[A-Z][a-z]|$)|[A-Z]?[a-z]+|[0-9]+/g) || [part];
      for (const piece of pieces) tokens.push(piece.toLowerCase());
    }
  }
  return tokens;
}

function literalText(node) {
  if (!node) return "";
  if (Node.isStringLiteral(node) || Node.isNoSubstitutionTemplateLiteral(node)) {
    return node.getLiteralText?.() ?? node.getText().replace(/^['"`]|['"`]$/g, "");
  }
  return "";
}

function propertyNameText(prop) {
  try {
    if (Node.isPropertyAssignment(prop) || Node.isMethodDeclaration(prop) || Node.isShorthandPropertyAssignment(prop)) {
      const nameNode = prop.getNameNode?.();
      if (nameNode && (Node.isStringLiteral(nameNode) || Node.isNoSubstitutionTemplateLiteral(nameNode))) {
        return nameNode.getLiteralText?.() ?? nameNode.getText().replace(/^['"`]|['"`]$/g, "");
      }
      return prop.getName?.() || "";
    }
  } catch (_) {
    /* ignore */
  }
  return "";
}

function callName(call) {
  try {
    const expr = call.getExpression();
    if (Node.isPropertyAccessExpression(expr)) return expr.getName();
    if (Node.isIdentifier(expr)) return expr.getText();
  } catch (_) {
    /* ignore */
  }
  return "";
}

function callReceiverRoot(call) {
  try {
    const expr = call.getExpression();
    if (!Node.isPropertyAccessExpression(expr)) return "";
    let receiver = expr.getExpression();
    while (receiver && Node.isPropertyAccessExpression(receiver)) {
      receiver = receiver.getExpression();
    }
    if (Node.isCallExpression(receiver)) return callReceiverRoot(receiver);
    if (Node.isIdentifier(receiver)) return receiver.getText();
  } catch (_) {
    /* ignore */
  }
  return "";
}

function expressionRoot(expr) {
  let cur = expr;
  try {
    while (cur && Node.isPropertyAccessExpression(cur)) cur = cur.getExpression();
    if (Node.isCallExpression(cur)) return callReceiverRoot(cur);
    if (Node.isIdentifier(cur)) return cur.getText();
  } catch (_) {
    /* ignore */
  }
  return "";
}

function isCypressChainCall(call) {
  const root = callReceiverRoot(call);
  if (root === "cy") return true;
  try {
    const expr = call.getExpression();
    return Node.isIdentifier(expr) && expr.getText() === "cy";
  } catch (_) {
    return false;
  }
}

function isTestingLibraryLocatorName(name) {
  return (
    isCypressLocatorQueryCommand(name) ||
    name.startsWith("findBy") ||
    name.startsWith("findAllBy") ||
    name.startsWith("getBy") ||
    name.startsWith("getAllBy") ||
    name.startsWith("queryBy") ||
    name.startsWith("queryAllBy")
  );
}

function classifyCypressCommandBodyDetail(bodyNode) {
  if (!bodyNode) {
    return {
      command_role_ast: "utility",
      command_role_basis_ast: "ast_body_unavailable",
      command_role_confidence_ast: "low",
    };
  }

  const signals = {
    session: false,
    testData: false,
    locator: false,
    uiAction: false,
    customOnly: false,
  };

  bodyNode.forEachDescendant((node) => {
    if (!Node.isCallExpression(node)) return;
    const name = callName(node);
    if (!name) return;
    const expr = node.getExpression();
    const root = expressionRoot(expr);
    const isCy = isCypressChainCall(node);

    if (isCy && name === "session") signals.session = true;
    if (isCy && CYPRESS_TEST_DATA_COMMANDS.has(name)) signals.testData = true;
    if (isCy && isTestingLibraryLocatorName(name)) signals.locator = true;
    if (isCy && CYPRESS_UI_ACTION_COMMANDS.has(name)) signals.uiAction = true;
    if (!isCy && isTestingLibraryLocatorName(name)) signals.locator = true;
    if (root === "cy" && !signals.session && !signals.testData && !signals.uiAction) {
      if (!CYPRESS_LOCATOR_ONLY_COMMANDS.has(name)) signals.customOnly = true;
    }
  });

  if (signals.session) {
    return {
      command_role_ast: "session_setup",
      command_role_basis_ast: "ast_cypress_session_call",
      command_role_confidence_ast: "high",
    };
  }
  if (signals.testData) {
    return {
      command_role_ast: "test_data_setup",
      command_role_basis_ast: "ast_cypress_data_call",
      command_role_confidence_ast: "high",
    };
  }
  if (signals.uiAction) {
    return {
      command_role_ast: "workflow_abstraction",
      command_role_basis_ast: "ast_cypress_ui_action_call",
      command_role_confidence_ast: "high",
    };
  }
  if (signals.locator) {
    return {
      command_role_ast: "locator_helper",
      command_role_basis_ast: "ast_cypress_locator_query_call",
      command_role_confidence_ast: "high",
    };
  }
  if (signals.customOnly) {
    return {
      command_role_ast: "utility",
      command_role_basis_ast: "ast_cypress_custom_call_only",
      command_role_confidence_ast: "medium",
    };
  }
  return {
    command_role_ast: "utility",
    command_role_basis_ast: "ast_no_cypress_setup_or_ui_call",
    command_role_confidence_ast: "medium",
  };
}

function classifyCypressCommandBody(bodyNode) {
  return classifyCypressCommandBodyDetail(bodyNode).command_role_ast;
}

function classifyCypressTaskHandlerDetail(taskName, bodyNode) {
  const taskTokens = new Set(identifierTokens(taskName));
  const diagnosticName =
    taskTokens.size > 0 && [...taskTokens].every((tok) => TASK_DIAGNOSTIC_TOKENS.has(tok));
  const setupName = [...taskTokens].some((tok) => TASK_SETUP_TOKENS.has(tok));
  let backendCall = false;
  let serverCall = false;
  let sawDiagnosticCall = false;
  let sawNonDiagnosticCall = false;
  let sawCall = false;

  if (bodyNode) {
    bodyNode.forEachDescendant((node) => {
      if (!Node.isCallExpression(node)) return;
      sawCall = true;
      const name = callName(node);
      const nameTokens = identifierTokens(name);
      const receiverTokens = identifierTokens(callReceiverRoot(node));
      const backendTokens = new Set([...nameTokens, ...receiverTokens]);
      if ([...backendTokens].some((tok) => TASK_BACKEND_CALL_TOKENS.has(tok))) backendCall = true;
      if ([...backendTokens].some((tok) => ["server", "start", "stop"].includes(tok))) serverCall = true;
      if (nameTokens.length && nameTokens.every((tok) => TASK_DIAGNOSTIC_TOKENS.has(tok))) {
        sawDiagnosticCall = true;
      } else {
        sawNonDiagnosticCall = true;
      }
    });
  }

  if (diagnosticName && !backendCall && !serverCall && (!sawCall || (sawDiagnosticCall && !sawNonDiagnosticCall))) {
    return {
      task_role_ast: "diagnostic_utility",
      task_role_basis_ast: "ast_task_handler_diagnostic",
      task_role_confidence_ast: "high",
    };
  }
  if (backendCall) {
    return {
      task_role_ast: "test_data_setup",
      task_role_basis_ast: "ast_task_handler_callee",
      task_role_confidence_ast: "high",
    };
  }
  if (serverCall) {
    return {
      task_role_ast: "setup_or_state_flow",
      task_role_basis_ast: "ast_task_handler_callee",
      task_role_confidence_ast: "high",
    };
  }
  if (setupName) {
    return {
      task_role_ast: "test_data_setup",
      task_role_basis_ast: "ast_task_handler_registered_name",
      task_role_confidence_ast: "medium",
    };
  }
  return {
    task_role_ast: "utility",
    task_role_basis_ast: bodyNode ? "ast_task_handler_no_setup_call" : "ast_task_handler_body_unavailable",
    task_role_confidence_ast: bodyNode ? "medium" : "low",
  };
}

function registerCypressCommand(registry, name, body, file) {
  if (!name || !body) return;
  if (
    !Node.isFunctionExpression(body) &&
    !Node.isArrowFunction(body) &&
    !Node.isMethodDeclaration(body) &&
    !Node.isFunctionDeclaration(body)
  ) {
    return;
  }
  const role = classifyCypressCommandBodyDetail(body);
  registry.set(name, { file, node: body, kind: "cypress_command", ...role });
}

function collectCommandsFromObjectLiteral(registry, obj, file, prefix = "") {
  if (!obj || !Node.isObjectLiteralExpression(obj)) return;
  for (const prop of obj.getProperties()) {
    let key = "";
    let body = null;
    if (Node.isPropertyAssignment(prop)) {
      key = prop.getName();
      body = prop.getInitializer();
    } else if (Node.isMethodDeclaration(prop)) {
      key = prop.getName();
      body = prop;
    } else if (Node.isShorthandPropertyAssignment(prop)) {
      key = prop.getName();
      const decl = prop.getSymbol()?.getDeclarations()?.[0];
      if (decl && Node.isVariableDeclaration(decl)) {
        body = decl.getInitializer();
      }
    }
    if (!key || !body) continue;
    if (Node.isArrowFunction(body) || Node.isFunctionExpression(body) || Node.isMethodDeclaration(body)) {
      const fullKey = prefix ? `${prefix}.${key}` : key;
      registerCypressCommand(registry, fullKey, body, file);
      registerCypressCommand(registry, key, body, file);
    }
  }
}

function collectTaskHandlersFromObjectLiteral(taskRegistry, obj, file) {
  collectTaskHandlersFromObjectLiteralInner(taskRegistry, obj, file, new Set());
}

function collectTaskHandlersFromObjectLiteralInner(taskRegistry, obj, file, seen) {
  if (!obj || !Node.isObjectLiteralExpression(obj)) return;
  const objId = `object:${obj.getSourceFile().getFilePath()}:${obj.getStart()}:${obj.getEnd()}`;
  if (seen.has(objId)) return;
  seen.add(objId);
  for (const prop of obj.getProperties()) {
    if (Node.isSpreadAssignment(prop)) {
      const spreadObj = resolveObjectLiteralFromNode(prop.getExpression(), seen);
      if (spreadObj) collectTaskHandlersFromObjectLiteralInner(taskRegistry, spreadObj, file, seen);
      continue;
    }
    const key = propertyNameText(prop);
    if (!key) continue;
    let body = null;
    if (Node.isPropertyAssignment(prop)) {
      body = resolveCallableFromNode(prop.getInitializer());
    } else if (Node.isMethodDeclaration(prop)) {
      body = prop;
    } else if (Node.isShorthandPropertyAssignment(prop)) {
      body = resolveCallableFromNode(prop.getNameNode?.());
      const decl = prop.getSymbol()?.getDeclarations()?.[0];
      if (!body && decl && Node.isVariableDeclaration(decl)) {
        body = resolveCallableFromNode(decl.getInitializer());
      }
    }
    const role = classifyCypressTaskHandlerDetail(key, body);
    taskRegistry.set(key, {
      file,
      node: body,
      kind: "cypress_task",
      task_name: key,
      ...role,
    });
  }
}

function unwrapExpressionNode(node) {
  let cur = node;
  while (cur) {
    const wrapped =
      Node.isParenthesizedExpression(cur) ||
      Node.isAsExpression(cur) ||
      (typeof Node.isTypeAssertion === "function" && Node.isTypeAssertion(cur)) ||
      (typeof Node.isSatisfiesExpression === "function" && Node.isSatisfiesExpression(cur));
    if (!wrapped) return cur;
    cur = cur.getExpression();
  }
  return cur;
}

function resolveCallableFromNode(node) {
  node = unwrapExpressionNode(node);
  if (!node) return null;
  if (Node.isFunctionExpression(node) || Node.isArrowFunction(node) || Node.isMethodDeclaration(node)) {
    return node;
  }
  if (Node.isIdentifier(node)) {
    const symbols = [];
    const symbol = node.getSymbol?.();
    if (symbol) symbols.push(symbol);
    const alias = typeof symbol?.getAliasedSymbol === "function" ? symbol.getAliasedSymbol() : null;
    if (alias && alias !== symbol) symbols.push(alias);
    for (const candidate of symbols) {
      for (const decl of candidate.getDeclarations?.() || []) {
        if (decl && Node.isFunctionDeclaration(decl)) return decl;
        if (decl && Node.isVariableDeclaration(decl)) {
          return resolveCallableFromNode(decl.getInitializer());
        }
      }
    }
    const name = node.getText();
    const sourceFile = node.getSourceFile?.();
    const sameFileVar = sourceFile?.getVariableDeclaration?.(name);
    if (sameFileVar) return resolveCallableFromNode(sameFileVar.getInitializer());
    const sameFileFunction = sourceFile?.getFunction?.(name);
    if (sameFileFunction) return sameFileFunction;
  }
  return null;
}

function resolveObjectLiteralFromNode(node, seen = new Set()) {
  node = unwrapExpressionNode(node);
  if (!node) return null;
  if (Node.isObjectLiteralExpression(node)) return node;
  if (!Node.isIdentifier(node)) return null;

  const symbols = [];
  const symbol = node.getSymbol?.();
  if (symbol) symbols.push(symbol);
  const alias = typeof symbol?.getAliasedSymbol === "function" ? symbol.getAliasedSymbol() : null;
  if (alias && alias !== symbol) symbols.push(alias);

  for (const candidate of symbols) {
    for (const decl of candidate.getDeclarations?.() || []) {
      if (!decl || !Node.isVariableDeclaration(decl)) continue;
      const declId = `decl:${decl.getSourceFile().getFilePath()}:${decl.getStart()}:${decl.getEnd()}`;
      if (seen.has(declId)) continue;
      seen.add(declId);
      const resolved = resolveObjectLiteralFromNode(decl.getInitializer(), seen);
      if (resolved) return resolved;
    }
  }
  return null;
}

function processCypressCommandsCall(registry, call, sf) {
  const args = call.getArguments();
  if (!args.length) return;
  const file = sf.getFilePath();

  if (Node.isObjectLiteralExpression(args[0])) {
    collectCommandsFromObjectLiteral(registry, args[0], file);
    return;
  }

  const nameArg = args[0];
  let cmdName = "";
  if (Node.isStringLiteral(nameArg) || Node.isNoSubstitutionTemplateLiteral(nameArg)) {
    cmdName = nameArg.getLiteralText?.() ?? nameArg.getText().replace(/^['"`]|['"`]$/g, "");
  } else if (Node.isIdentifier(nameArg)) {
    cmdName = nameArg.getText();
  }

  let body = null;
  if (Node.isIdentifier(nameArg)) {
    body = resolveCallableFromNode(nameArg);
  }
  for (const arg of args.slice(1)) {
    if (body) break;
    body = resolveCallableFromNode(arg);
  }

  if (cmdName && body) {
    registerCypressCommand(registry, cmdName, body, file);
  }
}

function processCypressTaskRegistration(taskRegistry, call, sf) {
  const args = call.getArguments();
  if (args.length < 2) return;
  if (literalText(args[0]) !== "task") return;
  const handlers = resolveObjectLiteralFromNode(args[1]);
  if (!handlers) return;
  collectTaskHandlersFromObjectLiteral(taskRegistry, handlers, sf.getFilePath());
}

/**
 * Collect Cypress.Commands.add/addAll/overwrite and Playwright test.extend bodies.
 */
function buildCustomCommandRegistry(project, repoPath) {
  const registry = new Map();
  registry.taskHandlers = new Map();
  const extendRoots = new Set(PLAYWRIGHT_EXTEND_ROOTS);

  for (const root of discoverSupportRoots(repoPath)) {
    try {
      if (!project.getSourceFile(root)) {
        const indexCandidates = ["index.ts", "index.js", "e2e.ts", "e2e.js"].map((n) =>
          path.join(root, n)
        );
        for (const abs of indexCandidates) {
          if (fs.existsSync(abs) && !project.getSourceFile(abs)) {
            project.addSourceFileAtPath(abs);
          }
        }
      }
    } catch (_) {
      /* ignore */
    }
  }

  for (const sf of project.getSourceFiles()) {
    const rel = toPosix(path.relative(repoPath, sf.getFilePath()));
    if (rel.startsWith("..")) continue;

    const { testNames } = collectTestLikeIdentifiers(sf);
    for (const n of testNames) extendRoots.add(n);

    for (const call of sf.getDescendantsOfKind(SyntaxKind.CallExpression)) {
      let expr = "";
      try {
        expr = call.getExpression().getText();
      } catch (_) {
        continue;
      }

      if (isCypressCommandsRegistration(expr)) {
        processCypressCommandsCall(registry, call, sf);
      }

      processCypressTaskRegistration(registry.taskHandlers, call, sf);

      const extendMatch = expr.match(/^([A-Za-z_$][\w$]*)\.extend\s*\(/);
      if (extendMatch && extendRoots.has(extendMatch[1])) {
        const arg = call.getArguments()[0];
        if (!arg || !Node.isObjectLiteralExpression(arg)) continue;
        collectCommandsFromObjectLiteral(registry, arg, sf.getFilePath());
      }
    }

  }

  return registry;
}

/**
 * Resolve cy.* / cy.ns.* custom commands using longest registered chain match.
 */
function resolveCypressRegistryCall(callExpr, registry) {
  if (!callExpr || !Node.isCallExpression(callExpr)) return null;
  let expr = callExpr.getExpression();
  if (!Node.isPropertyAccessExpression(expr)) return null;

  const parts = [];
  while (Node.isPropertyAccessExpression(expr)) {
    parts.unshift(expr.getName());
    expr = expr.getExpression();
  }
  if (expr.getText() !== "cy") return null;

  for (let i = 0; i < parts.length; i++) {
    const key = parts.slice(i).join(".");
    if (registry.has(key)) {
      const reg = registry.get(key);
      return {
        target: reg.node,
        file: reg.file,
        kind: reg.kind,
        command_role_ast: reg.command_role_ast || "",
        command_role_basis_ast: reg.command_role_basis_ast || "",
        command_role_confidence_ast: reg.command_role_confidence_ast || "",
        expansion_evidence_basis: "cypress_registry",
        expansion_confidence: "high",
      };
    }
  }
  return null;
}

function resolveCypressTaskCall(taskName, registry) {
  const handlers = registry?.taskHandlers;
  if (!taskName || !handlers || !handlers.has(taskName)) return null;
  const reg = handlers.get(taskName);
  return {
    target: reg.node,
    file: reg.file,
    kind: reg.kind,
    task_name: reg.task_name || taskName,
    task_role_ast: reg.task_role_ast || "",
    task_role_basis_ast: reg.task_role_basis_ast || "",
    task_role_confidence_ast: reg.task_role_confidence_ast || "",
  };
}

function hasStructuredCypressTaskHandlerEvidence(resolved) {
  const basis = resolved?.task_role_basis_ast || "";
  return (
    basis.startsWith("ast_task_handler_") &&
    ![
      "ast_task_handler_body_unavailable",
      "ast_task_handler_diagnostic",
      "ast_task_handler_no_setup_call",
      "ast_task_handler_registered_name",
    ].includes(basis)
  );
}

module.exports = {
  buildCustomCommandRegistry,
  resolveCypressRegistryCall,
  resolveCypressTaskCall,
  hasStructuredCypressTaskHandlerEvidence,
  classifyCypressCommandBody,
  classifyCypressCommandBodyDetail,
  classifyCypressTaskHandlerDetail,
};
