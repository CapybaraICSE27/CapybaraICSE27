"use strict";

/**
 * Link variable/member inputs to external file registry entries (AST scopes, not regex).
 */

const path = require("path");
const { Node, SyntaxKind } = require("ts-morph");
const { toPosix } = require("../shared/utils");
const { buildEntry } = require("./inputDataRegistry");
const { isSupportFilePath } = require("./supportFileLoader");
const {
  buildOriginBindingsForFile,
  buildRepoOriginBindings,
  resolveOriginFromExpression,
  resolveOriginFromRaw,
  applyOriginFields,
  computeTrueStaticFileCandidate,
  bindingAllowedForExpressionNode,
} = require("./inputOriginResolver");

const CONF_RANK = { high: 3, medium: 2, low: 1, none: 0 };
const fileBindingCache = new Map();
const repoWideBindingCache = new Map();

function splitProvenance(provenance) {
  if (!provenance || !provenance.includes(":")) return { file: "", field: "" };
  const body = provenance.replace(/^external_file:/, "").replace(/^fixture_file:/, "").replace(/^parameterized_row:/, "");
  const hash = body.indexOf("#");
  if (hash === -1) return { file: body, field: "" };
  return { file: body.slice(0, hash), field: body.slice(hash + 1) };
}

function formatProvenance(entry, fieldPath) {
  if (entry.kind === "parameterized_input") {
    return fieldPath ? `parameterized_row:test.each#${fieldPath}` : "parameterized_row:test.each";
  }
  const prefix = entry.kind === "fixture_file_input" ? "fixture_file" : "external_file";
  const file = entry.resolved_path || entry.literal_path || entry.raw_path || "";
  if (fieldPath) return `${prefix}:${file}#${fieldPath}`;
  return `${prefix}:${file}`;
}

function registryEntryForPath(registry, literalPath) {
  if (!literalPath) return null;
  const alias = literalPath.replace(/\.[^./\\]+$/, "").split(/[/\\]/).pop();
  return (
    registry.byLiteral.get(`fixture_file_input:${literalPath}`) ||
    registry.byLiteral.get(`external_file_input:${literalPath}`) ||
    registry.byLiteral.get(`network_mock_payload_input:${literalPath}`) ||
    registry.byAlias.get(alias) ||
    null
  );
}

function resolveSourceFile(project, repoPath, filePath) {
  if (!project || !filePath) return null;
  const abs = path.isAbsolute(filePath) ? filePath : path.join(repoPath, filePath);
  return project.getSourceFile(abs) || project.getSourceFile(toPosix(abs)) || null;
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

function extractFixturePathFromCall(call) {
  if (!call || !Node.isCallExpression(call)) return null;
  if (callTerminal(call) !== "fixture") return null;
  const arg = call.getArguments()[0];
  if (!arg || !Node.isStringLiteral(arg)) return null;
  return arg.getLiteralText();
}

function extractReadFilePathFromCall(call) {
  if (!call || !Node.isCallExpression(call)) return null;
  if (!/^readFile(?:Sync)?$/i.test(callTerminal(call))) return null;
  const arg = call.getArguments()[0];
  if (!arg || !Node.isStringLiteral(arg)) return null;
  return arg.getLiteralText();
}

function fixturePathFromObjectLiteral(obj) {
  if (!obj || !Node.isObjectLiteralExpression(obj)) return null;
  for (const prop of obj.getProperties()) {
    const name = prop.getName?.() || "";
    if (name !== "fixture" && name !== "body") continue;
    const init = prop.getInitializer?.();
    if (init && Node.isStringLiteral(init) && name === "fixture") return init.getLiteralText();
  }
  return null;
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

function normalizeMemberText(raw) {
  let s = (raw || "").trim();
  if (s.startsWith("this.")) s = s.slice(5);
  return s;
}

function bindingFromEntry(entry, fieldPath, line, confidence) {
  return { entry, fieldPath: fieldPath || "", line: line || entry.declared_line || "", confidence };
}

function mergeBindings(into, from) {
  for (const [k, v] of from.entries()) {
    if (!into.has(k)) into.set(k, v);
  }
  return into;
}

function setBinding(bindings, name, binding) {
  if (!name || !binding?.entry) return;
  bindings.set(name, binding);
}

function traceMemberBinding(memberText, bindings) {
  const normalized = normalizeMemberText(memberText);
  const parts = normalized.split(".");
  const root = parts[0];
  const fieldPath = parts.slice(1).join(".");
  const bound = bindings.get(root);
  if (!bound?.entry) return null;
  const combined = [bound.fieldPath, fieldPath].filter(Boolean).join(".");
  return bindingFromEntry(
    bound.entry,
    combined,
    bound.line,
    fieldPath ? bound.confidence || "high" : "medium"
  );
}

function bindFromValueNode(name, valueNode, bindings, registry, repoPath, fromFile, line) {
  if (!name || !valueNode) return;

  if (Node.isPropertyAccessExpression(valueNode) || Node.isElementAccessExpression(valueNode)) {
    const chain = memberChainFromNode(valueNode);
    if (chain.length >= 2) {
      const link = traceMemberBinding(chain.join("."), bindings);
      if (link) {
        setBinding(bindings, name, link);
        return;
      }
    }
    if (chain.length === 1) {
      const root = chain[0];
      const aliasEntry = registry.byAlias.get(root);
      if (aliasEntry) setBinding(bindings, name, bindingFromEntry(aliasEntry, "", line, "medium"));
    }
  }

  if (Node.isCallExpression(valueNode)) {
    const fixtureLit = extractFixturePathFromCall(valueNode);
    const readFileLit = extractReadFilePathFromCall(valueNode);
    const lit = fixtureLit || readFileLit;
    if (lit) {
      let entry = registryEntryForPath(registry, lit);
      if (!entry && repoPath) {
        entry = buildEntry(
          repoPath,
          fromFile,
          lit,
          fixtureLit ? "fixture_file_input" : "external_file_input",
          line
        );
      }
      if (entry) setBinding(bindings, name, bindingFromEntry(entry, "", line, "high"));
    }
  }
}

function collectImportBindings(sf, registry, repoPath, bindings) {
  const fromFile = toPosix(path.relative(repoPath, sf.getFilePath()));
  for (const decl of sf.getImportDeclarations()) {
    const spec = decl.getModuleSpecifier().getLiteralText();
    if (!/\.(json|ya?ml|csv)$/i.test(spec)) continue;
    let entry = registryEntryForPath(registry, spec);
    if (!entry) entry = buildEntry(repoPath, fromFile, spec, "external_file_input", decl.getStartLineNumber());
    const def = decl.getDefaultImport()?.getText();
    if (def) setBinding(bindings, def, bindingFromEntry(entry, "", decl.getStartLineNumber(), "high"));
    for (const el of decl.getNamedImports()) {
      setBinding(bindings, el.getName(), bindingFromEntry(entry, el.getName(), decl.getStartLineNumber(), "high"));
    }
  }
}

function collectRequireBindings(sf, registry, repoPath, bindings) {
  const fromFile = toPosix(path.relative(repoPath, sf.getFilePath()));
  sf.forEachDescendant((node) => {
    if (!Node.isVariableDeclaration(node)) return;
    const init = node.getInitializer();
    if (!init || !Node.isCallExpression(init)) return;
    const callee = init.getExpression().getText();
    if (callee !== "require") return;
    const arg = init.getArguments()[0];
    if (!arg || !Node.isStringLiteral(arg)) return;
    const spec = arg.getLiteralText();
    if (!/\.(json|ya?ml|csv)$/i.test(spec)) return;
    let entry = registryEntryForPath(registry, spec);
    if (!entry) entry = buildEntry(repoPath, fromFile, spec, "external_file_input", node.getStartLineNumber());
    setBinding(bindings, node.getName(), bindingFromEntry(entry, "", node.getStartLineNumber(), "high"));
  });
}

function bindThisPropertyFromParam(left, right, paramName, entry, line, bindings) {
  if (!Node.isPropertyAccessExpression(left)) return;
  if (left.getExpression().getText() !== "this") return;
  if (right.getText() !== paramName) return;
  const prop = left.getName();
  if (prop) setBinding(bindings, prop, bindingFromEntry(entry, "", line, "high"));
}

function collectFixtureThenBindings(sf, registry, repoPath, bindings) {
  const fromFile = toPosix(path.relative(repoPath, sf.getFilePath()));
  sf.forEachDescendant((node) => {
    if (!Node.isCallExpression(node)) return;
    if (callTerminal(node) !== "then") return;
    const cb = node.getArguments()[0];
    if (!cb || (!Node.isArrowFunction(cb) && !Node.isFunctionExpression(cb))) return;
    const params = cb.getParameters();
    if (!params.length) return;
    const paramName = params[0].getName();
    const recv = callReceiverExpression(node);
    if (!Node.isCallExpression(recv)) return;
    const lit = extractFixturePathFromCall(recv) || extractReadFilePathFromCall(recv);
    if (!lit || !paramName) return;
    let entry = registryEntryForPath(registry, lit);
    if (!entry) {
      entry = buildEntry(
        repoPath,
        fromFile,
        lit,
        extractFixturePathFromCall(recv) ? "fixture_file_input" : "external_file_input",
        recv.getStartLineNumber()
      );
    }
    setBinding(bindings, paramName, bindingFromEntry(entry, "", recv.getStartLineNumber(), "high"));

    const body = cb.getBody();
    if (!body) return;
    body.forEachDescendant((inner) => {
      if (Node.isVariableDeclaration(inner)) {
        bindFromValueNode(inner.getName(), inner.getInitializer(), bindings, registry, repoPath, fromFile, inner.getStartLineNumber());
      }
      if (Node.isBinaryExpression(inner) && inner.getOperatorToken().getKind() === SyntaxKind.EqualsToken) {
        const left = inner.getLeft();
        const right = inner.getRight();
        bindThisPropertyFromParam(left, right, paramName, entry, inner.getStartLineNumber(), bindings);
        if (Node.isIdentifier(left)) {
          bindFromValueNode(left.getText(), right, bindings, registry, repoPath, fromFile, inner.getStartLineNumber());
        }
      }
    });
  });
}

function collectTestEachBindings(sf, bindings) {
  const paramEntry = {
    kind: "parameterized_input",
    literal_path: "test.each",
    resolved_path: "",
    alias: "test.each",
    declared_line: null,
    declared_file: toPosix(sf.getFilePath?.() || ""),
  };

  sf.forEachDescendant((node) => {
    if (!Node.isCallExpression(node)) return;
    if (callTerminal(node) !== "each") return;

    const tableArg = node.getArguments()[0];
    const keys = new Set();
    if (tableArg && Node.isArrayLiteralExpression(tableArg)) {
      for (const el of tableArg.getElements()) {
        if (Node.isObjectLiteralExpression(el)) {
          for (const prop of el.getProperties()) {
            const k = prop.getName?.();
            if (k) keys.add(k);
          }
        }
      }
    }

    let callback = null;
    if (node.getArguments().length >= 2) callback = node.getArguments()[1];
    const parent = node.getParent();
    if (!callback && parent && Node.isCallExpression(parent)) {
      callback = parent.getArguments()[1] || parent.getArguments()[0];
    }
    if (!callback || (!Node.isArrowFunction(callback) && !Node.isFunctionExpression(callback))) return;

    const params = callback.getParameters();
    if (!params.length) return;
    const paramNode = params[0].getNameNode();
    if (Node.isObjectBindingPattern(paramNode)) {
      for (const el of paramNode.getElements()) {
        const name = el.getName();
        if (name) setBinding(bindings, name, bindingFromEntry(paramEntry, name, node.getStartLineNumber(), "high"));
      }
    } else if (Node.isIdentifier(paramNode) && keys.size) {
      for (const k of keys) {
        setBinding(bindings, k, bindingFromEntry(paramEntry, k, node.getStartLineNumber(), "medium"));
      }
    }
  });
}

function collectAssignmentBindings(sf, registry, repoPath, bindings) {
  const fromFile = toPosix(path.relative(repoPath, sf.getFilePath()));
  sf.forEachDescendant((node) => {
    if (Node.isVariableDeclaration(node)) {
      bindFromValueNode(node.getName(), node.getInitializer(), bindings, registry, repoPath, fromFile, node.getStartLineNumber());
    }
    if (Node.isBinaryExpression(node) && node.getOperatorToken().getKind() === SyntaxKind.EqualsToken) {
      const left = node.getLeft();
      const right = node.getRight();
      if (Node.isIdentifier(left)) {
        bindFromValueNode(left.getText(), right, bindings, registry, repoPath, fromFile, node.getStartLineNumber());
      }
      if (Node.isPropertyAccessExpression(left) && left.getExpression().getText() === "this" && Node.isIdentifier(right)) {
        const paramName = right.getText();
        const bound = bindings.get(paramName);
        if (bound) {
          setBinding(bindings, left.getName(), bindingFromEntry(bound.entry, bound.fieldPath, node.getStartLineNumber(), "high"));
        }
      }
    }
  });
}

function collectFileBindings(sf, registry, repoPath) {
  const bindings = new Map();
  if (!sf || !registry) return bindings;
  collectImportBindings(sf, registry, repoPath, bindings);
  collectRequireBindings(sf, registry, repoPath, bindings);
  collectFixtureThenBindings(sf, registry, repoPath, bindings);
  collectTestEachBindings(sf, bindings);
  collectAssignmentBindings(sf, registry, repoPath, bindings);
  return bindings;
}

function buildFileBindings(project, repoPath, filePath, registry) {
  const cacheKey = `${repoPath}::${filePath}`;
  if (fileBindingCache.has(cacheKey)) return fileBindingCache.get(cacheKey);
  const sf = resolveSourceFile(project, repoPath, filePath);
  const bindings = collectFileBindings(sf, registry, repoPath);
  fileBindingCache.set(cacheKey, bindings);
  return bindings;
}

function buildRepoWideBindings(project, repoPath, registry) {
  const cacheKey = repoPath;
  if (repoWideBindingCache.has(cacheKey)) return repoWideBindingCache.get(cacheKey);

  const bindings = new Map();
  if (!project) {
    repoWideBindingCache.set(cacheKey, bindings);
    return bindings;
  }

  for (const sf of project.getSourceFiles()) {
    const rel = toPosix(path.relative(repoPath, sf.getFilePath()));
    if (!isSupportFilePath(rel)) continue;
    mergeBindings(bindings, collectFileBindings(sf, registry, repoPath));
  }

  repoWideBindingCache.set(cacheKey, bindings);
  return bindings;
}

function buildBindingsForFeature(feature, registry, project, repoPath) {
  const filePath = feature.file_path || feature.target_file || "";
  const local = buildFileBindings(project, repoPath, filePath, registry);
  const support = buildRepoWideBindings(project, repoPath, registry);
  return mergeBindings(new Map(local), support);
}

function linkFromBindings(raw, bindings, registry, valueNode = null) {
  if (!raw) return null;
  const trimmed = normalizeMemberText(raw);

  if (/^[A-Za-z_$][\w$]*(\.[A-Za-z_$][\w$]*)*$/.test(trimmed)) {
    const traced = traceMemberBinding(trimmed, bindings);
    if (traced && valueNode && !bindingAllowedForExpressionNode(valueNode, { line: traced.line })) {
      return null;
    }
    if (traced) {
      const src =
        traced.entry.kind === "parameterized_input"
          ? "parameterized_input"
          : "variable_from_external_file";
      return {
        input_provenance_ast: formatProvenance(traced.entry, traced.fieldPath),
        input_provenance_confidence: traced.confidence,
        linked_load_line: traced.line,
        input_source_ast: src,
        external_file_path: traced.entry.resolved_path || traced.entry.literal_path || "",
        field_path: traced.fieldPath,
      };
    }
    const root = trimmed.split(".")[0];
    const aliasEntry = registry.byAlias.get(root);
    if (aliasEntry && !trimmed.includes(".")) {
      return {
        input_provenance_ast: formatProvenance(aliasEntry, ""),
        input_provenance_confidence: "low",
        linked_load_line: aliasEntry.declared_line || "",
        input_source_ast: "variable_from_external_file",
        external_file_path: aliasEntry.resolved_path || aliasEntry.literal_path,
        field_path: "",
      };
    }
  }

  const rootOnly = /^[A-Za-z_$][\w$]*$/.test(trimmed) ? trimmed : "";
  if (rootOnly && bindings.has(rootOnly)) {
    const b = bindings.get(rootOnly);
    if (valueNode && !bindingAllowedForExpressionNode(valueNode, { line: b.line })) return null;
    const src =
      b.entry.kind === "parameterized_input" ? "parameterized_input" : "variable_from_external_file";
    return {
      input_provenance_ast: formatProvenance(b.entry, b.fieldPath),
      input_provenance_confidence: b.fieldPath ? "high" : "medium",
      linked_load_line: b.line,
      input_source_ast: src,
      external_file_path: b.entry.resolved_path || b.entry.literal_path || "",
      field_path: b.fieldPath,
    };
  }
  return null;
}

function isConsumerInput(feature) {
  if (feature.is_load_site) return false;
  if (feature.input_channel_ast === "load_site") return false;
  if (feature.input_source_ast === "network_mock_payload_input") return false;
  if ((feature.name || "").startsWith("cy.fixture")) return false;
  if ((feature.raw_code || "").trim().match(/^cy\.fixture\s*\(/)) return false;
  if ((feature.raw_code || "").trim().match(/^cy\.intercept\s*\(/)) return false;
  return true;
}

function nodeContainsRange(node, start, end) {
  return node.getStart() <= start && node.getEnd() >= end;
}

function findNodeByExactRange(sourceFile, start, end) {
  if (!sourceFile || !Number.isFinite(start) || !Number.isFinite(end) || end <= start) return null;
  let best = null;
  sourceFile.forEachDescendant((node) => {
    if (node.getStart() === start && node.getEnd() === end) {
      best = node;
      return false;
    }
    if (nodeContainsRange(node, start, end)) {
      if (!best || (node.getEnd() - node.getStart()) < (best.getEnd() - best.getStart())) {
        best = node;
      }
    }
    return undefined;
  });
  return best;
}

function inputValueNodeForFeature(feature, project, repoPath) {
  const filePath = feature.file_path || feature.target_file || "";
  const sf = resolveSourceFile(project, repoPath, filePath);
  if (!sf) return null;
  const start = Number(feature.input_value_start_offset_ast || 0);
  const end = Number(feature.input_value_end_offset_ast || 0);
  return findNodeByExactRange(sf, start, end);
}

function scopedOriginBindingsForFeature(feature, registry, project, repoPath, repoOriginBindings) {
  const scoped = new Map(repoOriginBindings);
  const filePath = feature.file_path || feature.target_file || "";
  const sf = resolveSourceFile(project, repoPath, filePath);
  if (!sf) return scoped;
  const localFileBindings = buildBindingsForFeature(feature, registry, project, repoPath);
  const localOrigins = buildOriginBindingsForFile(sf, repoPath, localFileBindings);
  for (const [name, origin] of localOrigins.entries()) {
    scoped.set(name, origin);
  }
  return scoped;
}

function enrichFeatureWithProvenance(feature, registry, project, repoPath, repoOriginBindings) {
  if (feature.feature_type !== "input") return feature;

  let upgraded = { ...feature };
  if (!isConsumerInput(feature)) {
    upgraded.rq2_unit = "load_site";
    return upgraded;
  }
  upgraded.rq2_unit = "consumer_input";

  const raw = (feature.raw_value || feature.input_value_redacted || "").trim();
  const fileBindings = buildBindingsForFeature(feature, registry, project, repoPath);
  const valueNode = inputValueNodeForFeature(feature, project, repoPath);
  const link = linkFromBindings(raw, fileBindings, registry, valueNode);
  const scopedOriginBindings = scopedOriginBindingsForFeature(feature, registry, project, repoPath, repoOriginBindings);

  if (link) {
    upgraded = {
      ...upgraded,
      input_provenance_ast: link.input_provenance_ast,
      input_provenance_confidence: link.input_provenance_confidence,
      linked_load_line: link.linked_load_line || upgraded.linked_load_line,
      input_evidence_basis_ast: "ast_provenance",
    };
    if ((CONF_RANK[link.input_provenance_confidence] || 0) >= CONF_RANK.medium) {
      upgraded.input_source_ast = link.input_source_ast;
      upgraded.external_file_path = link.external_file_path;
      upgraded.field_path = link.field_path;
      if (link.input_provenance_confidence === "high") {
        upgraded.value_visibility_ast = "partially_visible";
      }
    }
  }

  const origin = valueNode
    ? resolveOriginFromExpression(valueNode, scopedOriginBindings)
    : resolveOriginFromRaw(raw, scopedOriginBindings);
  if (origin) {
    upgraded = applyOriginFields(upgraded, origin);
  }

  upgraded.is_static_file_candidate_ast = computeTrueStaticFileCandidate({
    raw,
    origin: origin || null,
    link: link || null,
    fileBindings,
    sourceClass: upgraded.input_source_ast,
    valueNode,
  });

  return upgraded;
}

function linkInputProvenance(features, registry, project, repoPath) {
  if (!Array.isArray(features) || !registry) return features;
  fileBindingCache.clear();
  repoWideBindingCache.clear();

  const getFileBindingsForPath = (rel) => {
    const sf = resolveSourceFile(project, repoPath, rel);
    return collectFileBindings(sf, registry, repoPath);
  };
  const repoOriginBindings = buildRepoOriginBindings(project, repoPath, getFileBindingsForPath);

  return features.map((f) => enrichFeatureWithProvenance(f, registry, project, repoPath, repoOriginBindings));
}

function clearBindingCache() {
  fileBindingCache.clear();
  repoWideBindingCache.clear();
}

module.exports = {
  linkInputProvenance,
  enrichFeatureWithProvenance,
  formatProvenance,
  splitProvenance,
  isConsumerInput,
  buildBindingsForFeature,
  buildFileBindings,
  buildRepoWideBindings,
  clearBindingCache,
};
