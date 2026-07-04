"use strict";

/**
 * Broader variable-origin tracking (API/hook/factory/alias/object), beyond static files.
 */

const path = require("path");
const { Node, SyntaxKind } = require("ts-morph");
const { toPosix } = require("../shared/utils");

const KEYBOARD_LITERALS = new Set([
  "enter", "escape", "esc", "tab", "backspace", "delete", "k", "up", "down", "left", "right",
  "home", "end", "pageup", "pagedown", "space", "shift", "ctrl", "alt", "meta",
]);
const GENERIC_VAR_NAMES = new Set([
  "value", "body", "data", "item", "result", "response", "text", "input", "str", "val",
  "name", "email", "password", "user", "token", "id", "key", "msg", "message", "content",
]);
const API_LIKE_FUNCTIONS = new Set([
  "makeClient", "createUser", "apiCreate", "getUser", "postUser",
  "createRandomUser", "generateUser", "setupUser", "createNewUser",
]);
const GENERATOR_ROOTS = new Set(["faker", "chance", "uuid", "nanoid"]);
const GENERATOR_TERMINALS = new Set(["randomUUID", "nanoid", "uuid"]);

function originBinding(opts) {
  return {
    originKind: opts.originKind,
    sourceClass: opts.sourceClass,
    evidence: (opts.evidence || "").slice(0, 200),
    line: opts.line || "",
    file: opts.file || "",
    confidence: opts.confidence || "medium",
    entry: opts.entry || null,
    fieldPath: opts.fieldPath || "",
    basis: opts.basis || "",
    components: opts.components || null,
  };
}

function setOriginBinding(bindings, name, binding) {
  if (!name || !binding) return;
  bindings.set(name, binding);
}

function mergeOriginBindings(into, from) {
  for (const [k, v] of from.entries()) {
    if (!into.has(k)) into.set(k, v);
  }
  return into;
}

function memberChainFromNode(node) {
  const parts = [];
  let cur = node;
  while (cur) {
    if (Node.isIdentifier(cur)) {
      parts.unshift(cur.getText());
      break;
    }
    if (Node.isPropertyAccessExpression(cur)) {
      parts.unshift(cur.getName());
      cur = cur.getExpression();
      continue;
    }
    if (Node.isElementAccessExpression(cur)) {
      const arg = cur.getArgumentExpression();
      if (arg && Node.isNumericLiteral(arg)) parts.unshift(String(arg.getLiteralValue()));
      else if (arg && Node.isStringLiteral(arg)) parts.unshift(arg.getLiteralText());
      else parts.unshift("[]");
      cur = cur.getExpression();
      continue;
    }
    break;
  }
  return parts;
}

function calleePartsFromExpression(expr) {
  if (!expr) return [];
  if (Node.isIdentifier(expr)) return [expr.getText()];
  if (Node.isPropertyAccessExpression(expr)) {
    return [...calleePartsFromExpression(expr.getExpression()), expr.getName()];
  }
  if (Node.isCallExpression(expr)) return calleePartsFromExpression(expr.getExpression());
  return [];
}

function callCalleeParts(call) {
  if (!call || !Node.isCallExpression(call)) return [];
  return calleePartsFromExpression(call.getExpression());
}

function callTerminal(call) {
  const parts = callCalleeParts(call);
  return parts[parts.length - 1] || "";
}

function callReceiverExpression(call) {
  if (!call || !Node.isCallExpression(call)) return null;
  const expr = call.getExpression();
  if (!Node.isPropertyAccessExpression(expr)) return null;
  return expr.getExpression();
}

function normalizeMemberText(raw) {
  let s = (raw || "").trim();
  if (s.startsWith("this.")) s = s.slice(5);
  return s;
}

function rootIdentifierNode(node) {
  let cur = node;
  while (cur) {
    if (Node.isIdentifier(cur)) return cur;
    if (Node.isPropertyAccessExpression(cur) || Node.isElementAccessExpression(cur)) {
      cur = cur.getExpression();
      continue;
    }
    return null;
  }
  return null;
}

function parameterDeclarationLine(identifierNode) {
  if (!identifierNode || !Node.isIdentifier(identifierNode)) return 0;
  const symbol = identifierNode.getSymbol?.();
  const decls = symbol?.getDeclarations?.() || [];
  for (const decl of decls) {
    if (Node.isParameterDeclaration(decl)) {
      return decl.getStartLineNumber?.() || identifierNode.getStartLineNumber?.() || 0;
    }
  }
  return 0;
}

function bindingAllowedForExpressionNode(node, origin) {
  const root = rootIdentifierNode(node);
  const paramLine = parameterDeclarationLine(root);
  if (!paramLine) return true;
  const originLine = Number(origin?.line || 0);
  // Callback parameter bindings are collected from the enclosing fixture/test.each/API
  // call at roughly the same line as the parameter. Older import/support bindings
  // with the same name should not pierce the parameter's lexical shadow.
  return Boolean(originLine && originLine >= paramLine - 1);
}

function apiCallBasis(call) {
  if (!call || !Node.isCallExpression(call)) return "";
  const parts = calleePartsFromExpression(call.getExpression());
  const root = parts[0] || "";
  const terminal = parts[parts.length - 1] || "";
  if (root === "cy" && terminal === "request") return "ast_cypress_request_call";
  if (root === "cy" && terminal.startsWith("api")) return "ast_callee_name_heuristic";
  if (API_LIKE_FUNCTIONS.has(terminal)) return "ast_callee_name_heuristic";
  return "";
}

function isFactoryBuildCall(call) {
  if (!call || !Node.isCallExpression(call)) return false;
  const parts = calleePartsFromExpression(call.getExpression());
  const root = parts[0] || "";
  const terminal = parts[parts.length - 1] || "";
  return (
    terminal === "build" ||
    root === "Factory" ||
    root === "factory" ||
    root.endsWith("Factory") ||
    parts.some((part) => part === "Factory" || part === "factory")
  );
}

function isGeneratorCall(call) {
  if (!call || !Node.isCallExpression(call)) return false;
  const parts = calleePartsFromExpression(call.getExpression());
  const root = parts[0] || "";
  const terminal = parts[parts.length - 1] || "";
  return (
    GENERATOR_ROOTS.has(root) ||
    GENERATOR_TERMINALS.has(terminal) ||
    (root === "Math" && terminal === "random") ||
    (root === "crypto" && terminal === "randomUUID")
  );
}

function isEnvironmentCall(call) {
  if (!call || !Node.isCallExpression(call)) return false;
  const parts = calleePartsFromExpression(call.getExpression());
  if (parts[0] === "Cypress" && parts[1] === "env") return true;
  if (parts[0] === "Deno" && parts[1] === "env") return true;
  if (parts[0] === "process" && parts[1] === "env") return true;
  return false;
}

function isEnvironmentMember(node) {
  const parts = memberChainFromNode(node);
  if (parts[0] === "process" && parts[1] === "env") return true;
  if (parts[0] === "Deno" && parts[1] === "env") return true;
  return false;
}

function literalOriginKind(node) {
  if (!node) return "";
  if (Node.isStringLiteral(node) || Node.isNoSubstitutionTemplateLiteral(node)) return "string_literal";
  if (Node.isNumericLiteral(node)) return "numeric_literal";
  if (Node.isTrueLiteral(node) || Node.isFalseLiteral(node)) return "boolean_literal";
  return "";
}

function literalConstantBinding(name, valueNode, line, file) {
  const kind = literalOriginKind(valueNode);
  if (!kind) return null;
  return originBinding({
    originKind: "literal_constant",
    sourceClass: "variable_input",
    evidence: `${name} = ${valueNode.getText().slice(0, 160)}`,
    line,
    file,
    confidence: "high",
    basis: "ast_literal_constant",
    fieldPath: kind,
  });
}

function seedFileBindings(fileBindings, file) {
  const bindings = new Map();
  for (const [name, fb] of fileBindings.entries()) {
    if (!fb?.entry) continue;
    setOriginBinding(
      bindings,
      name,
      originBinding({
        originKind:
          fb.entry.kind === "parameterized_input"
            ? "parameterized_row"
            : fb.entry.kind === "network_mock_payload_input"
              ? "network_mock_payload"
              : "static_file_root",
        sourceClass:
          fb.entry.kind === "parameterized_input"
            ? "parameterized_input"
            : fb.entry.kind === "network_mock_payload_input"
              ? "network_mock_payload_input"
              : "variable_from_external_file",
        evidence: fb.entry.resolved_path || fb.entry.literal_path || "",
        line: fb.line || fb.entry.declared_line,
        file: fb.entry.declared_file || file,
        confidence: fb.confidence || "high",
        entry: fb.entry,
        fieldPath: fb.fieldPath || "",
        basis: "ast_static_file_binding",
      })
    );
  }
  return bindings;
}

function collectObjectAndFactoryBindings(sf, repoPath, bindings) {
  const file = toPosix(path.relative(repoPath, sf.getFilePath()));
  sf.forEachDescendant((node) => {
    if (!Node.isVariableDeclaration(node)) return;
    const name = node.getName();
    const init = node.getInitializer();
    if (!name || !init) return;

    if (Node.isObjectLiteralExpression(init)) {
      setOriginBinding(
        bindings,
        name,
        originBinding({
          originKind: "object_literal",
          sourceClass: "variable_input",
          evidence: `${name} = { ... }`,
          line: node.getStartLineNumber(),
          file,
          confidence: "medium",
          basis: "ast_object_literal",
        })
      );
      return;
    }

    if (Node.isCallExpression(init)) {
      if (isFactoryBuildCall(init)) {
        setOriginBinding(
          bindings,
          name,
          originBinding({
            originKind: "factory_build",
            sourceClass: "generated_input",
            evidence: init.getText().slice(0, 160),
            line: node.getStartLineNumber(),
            file,
            confidence: "high",
            basis: "ast_factory_call",
          })
        );
      } else if (isGeneratorCall(init)) {
        setOriginBinding(
          bindings,
          name,
          originBinding({
            originKind: "generated_call",
            sourceClass: "generated_input",
            evidence: init.getText().slice(0, 160),
            line: node.getStartLineNumber(),
            file,
            confidence: "high",
            basis: "ast_generator_call",
          })
        );
      }
    }
  });
}

function bindAssignmentTarget(name, valueNode, line, file, bindings) {
  if (!name || !valueNode) return;
  const literal = literalConstantBinding(name, valueNode, line, file);
  if (literal) {
    setOriginBinding(bindings, name, literal);
    return;
  }
  if (Node.isIdentifier(valueNode) && bindings.has(valueNode.getText())) {
    const src = bindings.get(valueNode.getText());
    setOriginBinding(bindings, name, {
      ...src,
      evidence: `${name} = ${valueNode.getText()}`,
      line,
      file,
      confidence: src.confidence === "high" ? "high" : "medium",
    });
    return;
  }
  if (Node.isPropertyAccessExpression(valueNode) || Node.isElementAccessExpression(valueNode)) {
    const chain = memberChainFromNode(valueNode);
    if (chain.length >= 2) {
      const root = chain[0];
      const fieldPath = chain.slice(1).join(".");
      const src = bindings.get(root);
      if (src) {
        setOriginBinding(
          bindings,
          name,
          originBinding({
            originKind: src.entry ? "static_file_member" : "member_from_bound_root",
            sourceClass: src.sourceClass,
            evidence: `${name} = ${chain.join(".")}`,
            line,
            file,
            confidence: "high",
            entry: src.entry,
            fieldPath: [src.fieldPath, fieldPath].filter(Boolean).join("."),
            basis: src.basis || "ast_member_binding",
          })
        );
      }
    }
  }
  if (Node.isCallExpression(valueNode)) {
    if (isGeneratorCall(valueNode)) {
      setOriginBinding(
        bindings,
        name,
        originBinding({
          originKind: "generated_call",
          sourceClass: "generated_input",
          evidence: valueNode.getText().slice(0, 160),
          line,
          file,
          confidence: "high",
          basis: "ast_generator_call",
        })
      );
      return;
    }
    if (isEnvironmentCall(valueNode)) {
      setOriginBinding(
        bindings,
        name,
        originBinding({
          originKind: "environment_value",
          sourceClass: "environment_input",
          evidence: valueNode.getText().slice(0, 160),
          line,
          file,
          confidence: "high",
          basis: "ast_environment_call",
        })
      );
      return;
    }
    const basis = apiCallBasis(valueNode);
    if (!basis) return;
    setOriginBinding(
      bindings,
      name,
      originBinding({
        originKind: "api_call_result",
        sourceClass: "api_seed_input",
        evidence: valueNode.getText().slice(0, 160),
        line,
        file,
        confidence: "medium",
        basis,
      })
    );
  }
}

function bindingElementPropertyName(element) {
  const prop = element.getPropertyNameNode?.();
  if (!prop) return element.getName();
  if (Node.isStringLiteral(prop) || Node.isNoSubstitutionTemplateLiteral(prop)) return prop.getLiteralText();
  return prop.getText().replace(/^['"]|['"]$/g, "");
}

function bindObjectPattern(pattern, initializer, line, file, bindings) {
  if (!pattern || !initializer) return;
  for (const element of pattern.getElements()) {
    if (!Node.isBindingElement(element)) continue;
    const nameNode = element.getNameNode();
    if (!Node.isIdentifier(nameNode)) continue;
    const targetName = nameNode.getText();
    const propName = bindingElementPropertyName(element);
    if (!targetName || !propName) continue;

    let origin = null;
    if (
      Node.isIdentifier(initializer) ||
      Node.isPropertyAccessExpression(initializer) ||
      Node.isElementAccessExpression(initializer)
    ) {
      origin = resolveOriginFromRaw(`${initializer.getText()}.${propName}`, bindings);
    } else if (Node.isObjectLiteralExpression(initializer)) {
      origin = originBinding({
        originKind: "object_literal_member",
        sourceClass: "variable_input",
        evidence: `${targetName} from { ${propName}: ... }`,
        line,
        file,
        confidence: "medium",
        basis: "ast_object_literal_destructure",
        fieldPath: propName,
      });
    }
    if (origin) {
      setOriginBinding(bindings, targetName, {
        ...origin,
        evidence: `${targetName} = ${initializer.getText().slice(0, 80)}.${propName}`,
        line,
        file,
      });
    }
  }
}

function bindArrayPattern(pattern, initializer, line, file, bindings) {
  if (!pattern || !initializer) return;
  const elements = pattern.getElements();
  elements.forEach((element, index) => {
    if (!element || !Node.isIdentifier(element)) return;
    let origin = null;
    if (
      Node.isIdentifier(initializer) ||
      Node.isPropertyAccessExpression(initializer) ||
      Node.isElementAccessExpression(initializer)
    ) {
      origin = resolveOriginFromRaw(`${initializer.getText()}.${index}`, bindings);
    }
    if (origin) {
      setOriginBinding(bindings, element.getText(), {
        ...origin,
        evidence: `${element.getText()} = ${initializer.getText().slice(0, 80)}[${index}]`,
        line,
        file,
      });
    }
  });
}

function bindVariableDeclarationOrigin(node, file, bindings) {
  const init = node.getInitializer();
  if (!init) return;
  const nameNode = node.getNameNode?.();
  if (nameNode && Node.isObjectBindingPattern(nameNode)) {
    bindObjectPattern(nameNode, init, node.getStartLineNumber(), file, bindings);
    return;
  }
  if (nameNode && Node.isArrayBindingPattern?.(nameNode)) {
    bindArrayPattern(nameNode, init, node.getStartLineNumber(), file, bindings);
    return;
  }
  bindAssignmentTarget(node.getName(), init, node.getStartLineNumber(), file, bindings);
}

function collectAssignmentOrigins(sf, repoPath, bindings) {
  const file = toPosix(path.relative(repoPath, sf.getFilePath()));
  sf.forEachDescendant((node) => {
    if (Node.isVariableDeclaration(node)) {
      bindVariableDeclarationOrigin(node, file, bindings);
    }
    if (isEqualsAssignment(node)) {
      const left = node.getLeft();
      if (Node.isIdentifier(left)) {
        bindAssignmentTarget(left.getText(), node.getRight(), node.getStartLineNumber(), file, bindings);
      }
      if (Node.isPropertyAccessExpression(left) && left.getExpression().getText() === "this") {
        const prop = left.getName();
        const right = node.getRight();
        if (Node.isIdentifier(right) && bindings.has(right.getText())) {
          const src = bindings.get(right.getText());
          setOriginBinding(bindings, prop, {
            ...src,
            evidence: `this.${prop} = ${right.getText()}`,
            line: node.getStartLineNumber(),
            file,
          });
        }
      }
    }
  });
}

function isEqualsAssignment(node) {
  return Node.isBinaryExpression(node) && node.getOperatorToken().getKind() === SyntaxKind.EqualsToken;
}

function callbackParamNames(param) {
  if (!param) return [];
  const nameNode = typeof param.getNameNode === "function" ? param.getNameNode() : param;
  if (Node.isIdentifier(nameNode)) return [nameNode.getText()];
  if (Node.isObjectBindingPattern(nameNode)) {
    const names = [];
    for (const el of nameNode.getElements()) {
      if (!Node.isBindingElement(el)) continue;
      const elName = el.getNameNode();
      if (Node.isIdentifier(elName)) names.push(elName.getText());
    }
    return names;
  }
  return [];
}

function collectHookApiThenBindings(sf, repoPath, bindings) {
  const file = toPosix(path.relative(repoPath, sf.getFilePath()));
  sf.forEachDescendant((node) => {
    if (!Node.isCallExpression(node)) return;
    if (callTerminal(node) !== "then") return;
    const cb = node.getArguments()[0];
    if (!cb || (!Node.isArrowFunction(cb) && !Node.isFunctionExpression(cb))) return;
    const recv = callReceiverExpression(node);
    const recvText = Node.isCallExpression(recv) ? recv.getText() : node.getExpression().getText();
    const apiBasis = Node.isCallExpression(recv) ? apiCallBasis(recv) : "";
    const isApi = Boolean(apiBasis);
    const paramNames = callbackParamNames(cb.getParameters()[0]);
    if (!paramNames.length) return;

    for (const param of paramNames) {
      if (isApi) {
        setOriginBinding(
          bindings,
          param,
          originBinding({
            originKind: "api_response_callback_param",
            sourceClass: "api_seed_input",
            evidence: recvText.slice(0, 160),
            line: node.getStartLineNumber(),
            file,
            confidence: "medium",
            basis: apiBasis,
          })
        );
      }
    }

    const body = cb.getBody();
    if (!body) return;
    body.forEachDescendant((inner) => {
      if (isEqualsAssignment(inner)) {
        const left = inner.getLeft();
        const right = inner.getRight();
        if (!Node.isIdentifier(left) || !Node.isIdentifier(right)) return;
        if (!paramNames.includes(right.getText())) return;
        setOriginBinding(
          bindings,
          left.getText(),
          originBinding({
            originKind: isApi ? "hook_assigned_api_response" : "hook_assigned_callback_param",
            sourceClass: isApi ? "api_seed_input" : "variable_input",
            evidence: `${left.getText()} = ${right.getText()} in ${recvText.slice(0, 80)}`,
            line: inner.getStartLineNumber(),
            file,
            confidence: isApi ? "high" : "medium",
            basis: isApi ? apiBasis : "ast_callback_param_binding",
          })
        );
      }
    });
  });
}

function collectCypressAliasBindings(sf, repoPath, bindings) {
  const file = toPosix(path.relative(repoPath, sf.getFilePath()));
  sf.forEachDescendant((node) => {
    if (!Node.isCallExpression(node)) return;
    if (callTerminal(node) !== "as") return;
    const aliasArg = node.getArguments()[0];
    if (!aliasArg || !Node.isStringLiteral(aliasArg)) return;
    const alias = aliasArg.getLiteralText();
    const recv = callReceiverExpression(node);
    if (!Node.isCallExpression(recv)) return;
    const wrapParts = callCalleeParts(recv);
    if (wrapParts[wrapParts.length - 1] !== "wrap") return;
    if (wrapParts[0] && wrapParts[0] !== "cy") return;
    const wrapped = recv.getArguments()[0];
    if (Node.isIdentifier(wrapped) && bindings.has(wrapped.getText())) {
      const src = bindings.get(wrapped.getText());
      setOriginBinding(bindings, alias, {
        ...src,
        originKind: "cypress_alias",
        evidence: `cy.wrap(${wrapped.getText()}).as('${alias}')`,
        line: node.getStartLineNumber(),
        file,
        basis: "ast_cypress_alias_binding",
      });
    }
  });
}

function buildOriginBindingsForFile(sf, repoPath, fileBindings) {
  if (!sf) return new Map();
  const file = toPosix(path.relative(repoPath, sf.getFilePath()));
  const bindings = seedFileBindings(fileBindings, file);
  collectObjectAndFactoryBindings(sf, repoPath, bindings);
  collectHookApiThenBindings(sf, repoPath, bindings);
  collectAssignmentOrigins(sf, repoPath, bindings);
  collectCypressAliasBindings(sf, repoPath, bindings);
  return bindings;
}

function buildRepoOriginBindings(project, repoPath, getFileBindingsForPath) {
  const bindings = new Map();
  if (!project) return bindings;
  for (const sf of project.getSourceFiles()) {
    const rel = toPosix(path.relative(repoPath, sf.getFilePath()));
    const fb = getFileBindingsForPath(rel);
    mergeOriginBindings(bindings, buildOriginBindingsForFile(sf, repoPath, fb));
  }
  return bindings;
}

function resolveOriginFromRaw(raw, bindings) {
  const trimmed = normalizeMemberText(raw);
  if (!trimmed) return null;

  if (/^[A-Za-z_$][\w$]*(\.[A-Za-z_$][\w$]*)*$/.test(trimmed)) {
    const parts = trimmed.split(".");
    const root = parts[0];
    const fieldPath = parts.slice(1).join(".");
    const rootBinding = bindings.get(root);
    if (rootBinding) {
      return {
        ...rootBinding,
        fieldPath: [rootBinding.fieldPath, fieldPath].filter(Boolean).join("."),
        originKind: fieldPath ? `${rootBinding.originKind}_member` : rootBinding.originKind,
        confidence: fieldPath ? (rootBinding.confidence === "high" ? "high" : "medium") : rootBinding.confidence,
      };
    }
  }

  if (/^[A-Za-z_$][\w$]*$/.test(trimmed) && bindings.has(trimmed)) {
    return bindings.get(trimmed);
  }
  return null;
}

function provenanceForOrigin(origin) {
  if (!origin) return "";
  if (origin.entry) {
    const prefix =
      origin.entry.kind === "fixture_file_input"
        ? "fixture_file"
        : origin.entry.kind === "network_mock_payload_input"
          ? "fixture_file"
          : "external_file";
    const filePath = origin.entry.resolved_path || origin.entry.literal_path || "";
    return origin.fieldPath ? `${prefix}:${filePath}#${origin.fieldPath}` : `${prefix}:${filePath}`;
  }
  if (origin.originKind === "parameterized_row" || (origin.originKind || "").startsWith("parameterized_row")) {
    return `parameterized_row:test.each#${origin.fieldPath || ""}`;
  }
  if (origin.originKind === "hook_assigned_api_response" || origin.originKind === "api_response_callback_param") {
    return `api_seed:${origin.evidence.slice(0, 80)}`;
  }
  if (origin.originKind === "factory_build" || origin.originKind === "generated_call") {
    return "generated:factory_or_generator";
  }
  if (origin.originKind === "environment_value") {
    return "environment:env_expression";
  }
  if (origin.originKind === "literal_constant") {
    return "inline_literal:local_constant";
  }
  if (origin.originKind === "inline_literal") {
    return `inline_literal:${origin.fieldPath || "literal"}`;
  }
  if (origin.originKind === "inline_array") {
    return "inline_array:array_literal";
  }
  if (origin.originKind === "inline_object" || origin.originKind === "object_literal" || origin.originKind === "object_literal_member") {
    return "inline_object:object_literal";
  }
  if (origin.originKind === "composite_expression") {
    return "composite_expression";
  }
  if (origin.originKind === "cypress_alias" || origin.originKind === "cypress_alias_member") {
    return `alias:${origin.evidence.slice(0, 80)}`;
  }
  return origin.originKind || "";
}

function componentFromOrigin(origin, expressionText = "") {
  if (!origin) return null;
  return {
    originKind: origin.originKind || "",
    sourceClass: origin.sourceClass || "",
    provenance: provenanceForOrigin(origin),
    evidence: (origin.evidence || expressionText || "").slice(0, 160),
    fieldPath: origin.fieldPath || "",
    file: origin.file || "",
    line: origin.line || "",
    confidence: origin.confidence || "medium",
    basis: origin.basis || "",
  };
}

function componentsFromOrigin(origin, expressionText = "") {
  if (!origin) return [];
  if (Array.isArray(origin.components)) return origin.components;
  const component = componentFromOrigin(origin, expressionText);
  return component ? [component] : [];
}

function dedupeComponents(components) {
  const out = [];
  const seen = new Set();
  for (const c of components) {
    if (!c) continue;
    const key = `${c.originKind}|${c.provenance}|${c.evidence}|${c.fieldPath}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(c);
  }
  return out;
}

function confidenceFromComponents(components) {
  if (!components.length) return "low";
  if (components.every((c) => c.confidence === "high")) return "high";
  if (components.some((c) => c.confidence === "low")) return "low";
  return "medium";
}

function sourceClassFromComponents(components) {
  const classes = new Set(components.map((c) => c.sourceClass).filter(Boolean));
  if (classes.has("variable_from_external_file")) return "variable_from_external_file";
  if (classes.has("fixture_file_input")) return "variable_from_external_file";
  if (classes.has("parameterized_input")) return "parameterized_input";
  if (classes.has("api_seed_input")) return "api_seed_input";
  if (classes.has("generated_input")) return "generated_input";
  if (classes.has("environment_input")) return "environment_input";
  return "variable_input";
}

function combineExpressionOrigins(node, origins, basis) {
  const components = dedupeComponents(origins.flatMap((origin) => componentsFromOrigin(origin)));
  if (!components.length) return null;
  if (components.length === 1) return origins.find(Boolean) || null;
  return originBinding({
    originKind: "composite_expression",
    sourceClass: sourceClassFromComponents(components),
    evidence: node.getText().slice(0, 160),
    line: node.getStartLineNumber?.() || "",
    file: "",
    confidence: confidenceFromComponents(components),
    basis,
    components,
  });
}

function inlineStringComponent(text, node, basis) {
  if (!text) return null;
  return originBinding({
    originKind: "inline_literal",
    sourceClass: "literal_input",
    evidence: String(text).slice(0, 160),
    line: node.getStartLineNumber?.() || "",
    confidence: "high",
    basis,
    fieldPath: "string_literal",
  });
}

function inlineLiteralOrigin(node) {
  const kind = literalOriginKind(node);
  if (!kind) return null;
  return originBinding({
    originKind: "inline_literal",
    sourceClass: "literal_input",
    evidence: node.getText().slice(0, 160),
    line: node.getStartLineNumber?.() || "",
    confidence: "high",
    basis: "ast_inline_literal",
    fieldPath: kind,
  });
}

function resolveOriginFromExpression(node, bindings) {
  if (!node) return null;

  const inline = inlineLiteralOrigin(node);
  if (inline) return inline;

  if (Node.isParenthesizedExpression?.(node)) {
    return resolveOriginFromExpression(node.getExpression(), bindings);
  }

  if (Node.isIdentifier(node) || Node.isPropertyAccessExpression(node) || Node.isElementAccessExpression(node)) {
    if (isEnvironmentMember(node)) {
      return originBinding({
        originKind: "environment_value",
        sourceClass: "environment_input",
        evidence: node.getText().slice(0, 160),
        line: node.getStartLineNumber?.() || "",
        confidence: "high",
        basis: "ast_environment_member",
      });
    }
    const origin = resolveOriginFromRaw(node.getText(), bindings);
    if (origin && !bindingAllowedForExpressionNode(node, origin)) return null;
    return origin;
  }

  if (Node.isCallExpression(node)) {
    if (isGeneratorCall(node)) {
      return originBinding({
        originKind: "generated_call",
        sourceClass: "generated_input",
        evidence: node.getText().slice(0, 160),
        line: node.getStartLineNumber?.() || "",
        confidence: "high",
        basis: "ast_generator_call",
      });
    }
    if (isEnvironmentCall(node)) {
      return originBinding({
        originKind: "environment_value",
        sourceClass: "environment_input",
        evidence: node.getText().slice(0, 160),
        line: node.getStartLineNumber?.() || "",
        confidence: "high",
        basis: "ast_environment_call",
      });
    }
    const argOrigins = node.getArguments().map((arg) => resolveOriginFromExpression(arg, bindings)).filter(Boolean);
    return combineExpressionOrigins(node, argOrigins, "ast_call_argument_component_origins");
  }

  if (Node.isTemplateExpression(node)) {
    const origins = [];
    const headText = node.getHead()?.getLiteralText?.() || "";
    const head = inlineStringComponent(headText, node, "ast_template_literal_head");
    if (head) origins.push(head);
    for (const span of node.getTemplateSpans()) {
      origins.push(resolveOriginFromExpression(span.getExpression(), bindings));
      const tailText = span.getLiteral?.()?.getLiteralText?.() || "";
      const tail = inlineStringComponent(tailText, span, "ast_template_literal_tail");
      if (tail) origins.push(tail);
    }
    return combineExpressionOrigins(node, origins.filter(Boolean), "ast_template_expression_components");
  }

  if (Node.isBinaryExpression(node)) {
    return combineExpressionOrigins(
      node,
      [
        resolveOriginFromExpression(node.getLeft(), bindings),
        resolveOriginFromExpression(node.getRight(), bindings),
      ].filter(Boolean),
      "ast_binary_expression_components"
    );
  }

  if (Node.isConditionalExpression?.(node)) {
    return combineExpressionOrigins(
      node,
      [
        resolveOriginFromExpression(node.getWhenTrue(), bindings),
        resolveOriginFromExpression(node.getWhenFalse(), bindings),
      ].filter(Boolean),
      "ast_conditional_expression_branches"
    );
  }

  if (Node.isArrayLiteralExpression(node)) {
    const origins = node.getElements().map((el) => resolveOriginFromExpression(el, bindings)).filter(Boolean);
    if (origins.length) return combineExpressionOrigins(node, origins, "ast_array_literal_components");
    return originBinding({
      originKind: "inline_array",
      sourceClass: "literal_input",
      evidence: node.getText().slice(0, 160),
      line: node.getStartLineNumber?.() || "",
      confidence: "high",
      basis: "ast_inline_array",
    });
  }

  if (Node.isObjectLiteralExpression(node)) {
    const origins = [];
    for (const prop of node.getProperties()) {
      const init = prop.getInitializer?.();
      if (init) origins.push(resolveOriginFromExpression(init, bindings));
    }
    if (origins.some(Boolean)) return combineExpressionOrigins(node, origins.filter(Boolean), "ast_object_literal_components");
    return originBinding({
      originKind: "inline_object",
      sourceClass: "literal_input",
      evidence: node.getText().slice(0, 160),
      line: node.getStartLineNumber?.() || "",
      confidence: "high",
      basis: "ast_inline_object",
    });
  }

  return null;
}

function originHasStaticFileEvidence(origin) {
  if (!origin) return false;
  if (Array.isArray(origin.components)) {
    return origin.components.some((c) =>
      /^(external_file:|fixture_file:|parameterized_row:)/.test(c.provenance || "") ||
      (c.originKind || "").includes("static_file") ||
      (c.originKind || "").startsWith("parameterized_row") ||
      (c.originKind || "").startsWith("network_mock_payload")
    );
  }
  if (origin.entry) return true;
  const kind = origin.originKind || "";
  if (/^(hook_assigned_api|hook_assigned_callback|api_|factory_|object_literal|generated_call|cypress_alias)/.test(kind)) {
    return false;
  }
  if (
    kind.includes("static_file") ||
    kind.startsWith("parameterized_row") ||
    kind.startsWith("network_mock_payload") ||
    kind === "hook_assigned_fixture"
  ) {
    return true;
  }
  return false;
}

function linkHasStaticFileEvidence(link) {
  const prov = link?.input_provenance_ast || "";
  return /^(external_file:|fixture_file:|parameterized_row:)/.test(prov);
}

function computeTrueStaticFileCandidate({ raw, origin, link, fileBindings, sourceClass, valueNode = null }) {
  if (origin) {
    const kind = origin.originKind || "";
    if (/^(hook_assigned_api|hook_assigned_callback|api_|factory_|object_literal|generated_call|cypress_alias)/.test(kind)) {
      return false;
    }
    if (originHasStaticFileEvidence(origin)) return true;
  }
  if (linkHasStaticFileEvidence(link)) return true;
  if (sourceClass === "variable_from_external_file" || sourceClass === "parameterized_input") {
    return true;
  }
  const trimmed = normalizeMemberText(raw || "");
  if (trimmed && fileBindings) {
    const root = trimmed.split(".")[0];
    const binding = fileBindings.get(root);
    if (binding?.entry) {
      if (valueNode && !bindingAllowedForExpressionNode(valueNode, { line: binding.line })) return false;
      return true;
    }
  }
  return false;
}

function isStaticFileCandidate(raw, sourceClass) {
  // Legacy export: identifier shape only; do not use for gate metrics.
  const src = sourceClass || "";
  if (!["variable_input", "unknown_input", "parameterized_input", "variable_from_external_file"].includes(src)) {
    return false;
  }
  const t = normalizeMemberText(raw || "");
  if (!t) return false;
  if (/[`$@]/.test(t)) return false;
  if (/^(faker|Math|random|uuid|nanoid|chance)/i.test(t)) return false;
  if (/Factory|factory|\.build\b/.test(t)) return false;
  if (!/^[A-Za-z_$][\w$]*(\.[A-Za-z_$][\w$]*)*$/.test(t)) return false;
  const root = t.split(".")[0];
  if (KEYBOARD_LITERALS.has(root.toLowerCase())) return false;
  if (GENERIC_VAR_NAMES.has(root.toLowerCase()) && !t.includes(".")) return false;
  return true;
}

function applyOriginFields(feature, origin) {
  if (!origin) return feature;
  const provenance = provenanceForOrigin(origin);
  const out = {
    ...feature,
    input_origin_kind_ast: origin.originKind,
    input_origin_confidence_ast: origin.confidence,
    input_origin_evidence_ast: origin.evidence,
    linked_definition_line: String(origin.line || ""),
    linked_definition_file: origin.file || "",
    is_static_file_candidate_ast: originHasStaticFileEvidence(origin),
    input_provenance_family_ast: origin.originKind || "",
  };

  if (Array.isArray(origin.components)) {
    out.input_provenance_components_json = JSON.stringify(origin.components);
  }

  const variableLike = ["variable_input", "unknown_input"].includes(feature.input_source_ast || "");
  if (origin.sourceClass && (variableLike || !feature.input_source_ast)) {
    out.input_source_ast = origin.sourceClass;
  }

  if (origin.entry) {
    out.input_provenance_ast = provenance;
    out.input_provenance_confidence = origin.confidence;
    out.is_static_file_candidate_ast = true;
  } else if (origin.originKind === "parameterized_row" || (origin.originKind || "").startsWith("parameterized_row")) {
    out.input_provenance_ast = provenance;
    out.is_static_file_candidate_ast = true;
  } else if (origin.originKind === "hook_assigned_api_response" || origin.originKind === "api_response_callback_param") {
    out.input_provenance_ast = provenance;
  } else if (origin.originKind === "factory_build" || origin.originKind === "generated_call") {
    out.input_provenance_ast = provenance;
  } else if (origin.originKind === "environment_value") {
    out.input_provenance_ast = provenance;
  } else if (origin.originKind === "literal_constant" || origin.originKind === "inline_literal") {
    out.input_provenance_ast = provenance;
  } else if (origin.originKind === "inline_array") {
    out.input_provenance_ast = provenance;
  } else if (origin.originKind === "inline_object" || origin.originKind === "object_literal" || origin.originKind === "object_literal_member") {
    out.input_provenance_ast = provenance;
  } else if (origin.originKind === "composite_expression") {
    out.input_provenance_ast = provenance;
  } else if (origin.originKind === "cypress_alias" || origin.originKind === "cypress_alias_member") {
    out.input_provenance_ast = provenance;
    out.is_static_file_candidate_ast = false;
  }

  if (out.input_provenance_ast && !out.input_provenance_confidence) {
    out.input_provenance_confidence = origin.confidence || "medium";
  }

  if (originHasStaticFileEvidence(origin)) {
    out.is_static_file_candidate_ast = true;
  }

  out.input_evidence_basis_ast = origin.basis || "ast_origin_binding";
  return out;
}

module.exports = {
  buildOriginBindingsForFile,
  buildRepoOriginBindings,
  resolveOriginFromExpression,
  resolveOriginFromRaw,
  applyOriginFields,
  bindingAllowedForExpressionNode,
  originHasStaticFileEvidence,
  linkHasStaticFileEvidence,
  computeTrueStaticFileCandidate,
  isStaticFileCandidate,
};
