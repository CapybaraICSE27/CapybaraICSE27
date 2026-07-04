"use strict";

const path = require("path");
const { SyntaxKind, Node } = require("ts-morph");
const { collectHooks } = require("../phase2b/hookCollector");
const { collectTestLikeIdentifiers } = require("../shared/identifiers");
const { buildImportMap } = require("./importResolver");
const { walkNodeForFeatures } = require("../phase2b/directFeatureExtractor");
const { buildPageSymbolOrigins } = require("../phase2b/pageSymbolOrigins");
const { scanFunctionBodyPhaseHints } = require("../phase2b/setupTeardownPatternExtractor");
const { captureControlFlowStackAtNode } = require("../phase2b/controlFlowEnclosure");
const { expandedFeatureDedupeKey } = require("./expandedOutput");
const { toPosix } = require("../shared/utils");
const { helperEdgeDedupeKey } = require("./helperEdgeUtils");
const { shouldReportUnresolved } = require("./helperCallFilters");

/**
 * Index hook_instance_key -> { callback, source_file (abs), source_kind }.
 */
function buildHookCallbackIndex(project, repoPath, globalSupportHooks, testFilePaths) {
  const index = new Map();

  for (const h of globalSupportHooks || []) {
    if (!h.hook_instance_key || !h.callback) continue;
    const abs = h.source_file
      ? path.isAbsolute(h.source_file)
        ? h.source_file
        : path.join(repoPath, h.source_file)
      : "";
    index.set(h.hook_instance_key, {
      callback: h.callback,
      source_file: abs,
      source_kind: h.source_kind || h.hookName || "beforeEach",
      hook_owner_kind: h.hook_owner_kind || "",
      rel_file: h.source_file || "",
    });
  }

  const seenAbs = new Set();
  for (const rel of testFilePaths) {
    const abs = path.join(repoPath, rel);
    if (seenAbs.has(abs)) continue;
    seenAbs.add(abs);
    let sf;
    try {
      sf = project.getSourceFile(abs) || project.addSourceFileAtPath(abs);
    } catch (_) {
      continue;
    }
    const { testNames, groupNames } = collectTestLikeIdentifiers(sf);
    for (const h of collectHooks(sf, testNames, groupNames)) {
      if (!h.hook_instance_key || !h.callback) continue;
      index.set(h.hook_instance_key, {
        callback: h.callback,
        source_file: abs,
        source_kind: h.source_kind || h.hookName || "beforeEach",
        hook_owner_kind: h.hook_owner_kind || "",
        rel_file: toPosix(path.relative(repoPath, abs)),
      });
    }
  }

  return index;
}

function findCallAtLine(sf, line) {
  if (!sf || !line) return null;
  try {
    return (
      sf
        .getDescendantsOfKind(SyntaxKind.CallExpression)
        .find((c) => c.getStartLineNumber() === line) || null
    );
  } catch (_) {
    return null;
  }
}

function calleeNameFromFeature(f) {
  const m = String(f.name || "").match(/([A-Za-z_$][\w$]*)$/);
  return m ? m[1] : "";
}

function nodeId(node, file, repoPath) {
  if (!node || !file) return "";
  const rel = toPosix(path.relative(repoPath, file));
  let start = 0;
  let end = 0;
  try {
    start = node.getStart();
    end = node.getEnd();
  } catch (_) {
    /* ignore */
  }
  return `${rel}:${start}:${end}`;
}

function callsiteId(callExpr, fromFile, repoPath, line = 0, name = "") {
  if (callExpr) return nodeId(callExpr, fromFile, repoPath);
  const rel = toPosix(path.relative(repoPath, fromFile));
  return `${rel}:${line || 0}:0:${name || ""}`;
}

function resolvedEvidence(resolved, fallbackBasis = "heuristic_name") {
  return {
    helper_expansion_evidence_basis: resolved?.expansion_evidence_basis || fallbackBasis,
    helper_expansion_confidence: resolved?.expansion_confidence || (fallbackBasis === "heuristic_name" ? "low" : "medium"),
  };
}

function buildHookSeeds(
  hookFeats,
  callback,
  sf,
  {
    registry,
    collectHelperCallsInNode,
    isCypressCustomCommandExpr,
    shouldSeedHookCall,
    helperNames,
    importMap,
    absFile,
    repoPath,
    tsconfigCache,
    project,
    shouldSeedCall,
  }
) {
  const seeds = [];
  const seen = new Set();

  function addSeed(callExpr, name, line, exprText) {
    const key = `${line}|${name}|${exprText}`;
    if (seen.has(key)) return;
    seen.add(key);
    seeds.push({
      call: callExpr,
      name,
      line: line || 0,
      isMethod: true,
      exprText: exprText || `cy.${name}`,
    });
  }

  if (callback) {
    for (const c of collectHelperCallsInNode(callback, { allowMethods: true })) {
      if (
        shouldSeedHookCall(
          c,
          registry,
          helperNames,
          importMap,
          absFile,
          repoPath,
          tsconfigCache,
          project,
          shouldSeedCall,
          isCypressCustomCommandExpr
        )
      ) {
        addSeed(c.call, c.name, c.line, c.exprText);
      }
    }
  }

  for (const f of hookFeats) {
    if (f.feature_type !== "custom_command_call" && f.feature_type !== "helper_call") continue;
    const cmdName = calleeNameFromFeature(f);
    if (!cmdName) continue;
    const callExpr = findCallAtLine(sf, f.line);
    addSeed(
      callExpr,
      cmdName,
      f.line || 0,
      callExpr ? callExpr.getExpression().getText() : String(f.name || cmdName)
    );
  }

  return seeds;
}

function shouldSeedHookCall(
  callInfo,
  registry,
  helperNames,
  importMap,
  fromFile,
  repoPath,
  tsconfigCache,
  project,
  shouldSeedCall,
  isCypressCustomCommandExpr
) {
  if (registry.has(callInfo.name)) return true;
  if (helperNames.has(callInfo.name)) return true;
  if (isCypressCustomCommandExpr(callInfo.exprText, callInfo.name)) return true;
  return shouldSeedCall(
    callInfo,
    helperNames,
    importMap,
    registry,
    fromFile,
    repoPath,
    tsconfigCache,
    project
  );
}

/**
 * Expand Cypress custom commands in shared hooks once per hook_instance_key.
 * Returns Map<hookKey, { features: Feature[], unresolved: Unresolved[] }>.
 */
function expandHookCustomCommandsForRepo({
  project,
  repoPath,
  repoMeta,
  hookByKey,
  hookCallbackIndex,
  registry,
  tsconfigCache,
  maxDepth,
  maxHelperFiles,
  frameworkDefault,
  resolveCall,
  isUnresolvedCyCustom,
  collectHelperCallsInNode,
  shouldSeedCall,
  isCypressCustomCommandExpr,
  collectImportedHelperNames,
  pushHelperEdge,
  pushUnresolved,
}) {
  const hookExpandedByKey = new Map();
  const hookEdgeSeen = new Set();
  const hookExpandedSeen = new Set();

  function pushHookExpanded(f) {
    const key = expandedFeatureDedupeKey(f);
    if (hookExpandedSeen.has(key)) return;
    hookExpandedSeen.add(key);
    const hookKey = f.hook_instance_key;
    if (!hookExpandedByKey.has(hookKey)) {
      hookExpandedByKey.set(hookKey, { features: [], unresolved: [] });
    }
    hookExpandedByKey.get(hookKey).features.push(f);
  }

  function pushHookUnresolved(hookKey, row) {
    if (!hookExpandedByKey.has(hookKey)) {
      hookExpandedByKey.set(hookKey, { features: [], unresolved: [] });
    }
    const bucket = hookExpandedByKey.get(hookKey).unresolved;
    const dedupe = `${row.call}|${row.line}|${row.reason}`;
    if (bucket.some((u) => `${u.call}|${u.line}|${u.reason}` === dedupe)) return;
    bucket.push(row);
    pushUnresolved(row);
  }

  function pushHookEdge(edge) {
    const key = helperEdgeDedupeKey(edge);
    if (hookEdgeSeen.has(key)) return;
    hookEdgeSeen.add(key);
    pushHelperEdge(edge);
  }

  for (const [hookKey, hookFeats] of hookByKey) {
    const meta = hookCallbackIndex.get(hookKey);
    if (!meta?.callback && !hookFeats.some((f) => f.feature_type === "custom_command_call" || f.feature_type === "helper_call")) {
      continue;
    }

    const relFile =
      meta?.rel_file ||
      toPosix(String(hookFeats[0]?.file_path || "").replace(/\\/g, "/"));
    const absFile = meta?.source_file || (relFile ? path.join(repoPath, relFile) : "");
    if (!absFile) continue;

    let sf;
    try {
      sf = project.getSourceFile(absFile) || project.addSourceFileAtPath(absFile);
    } catch (_) {
      continue;
    }

    const sourceKind = meta?.source_kind || hookFeats[0]?.source_kind || "beforeEach";
    const hookOwnerKind = meta?.hook_owner_kind || hookFeats[0]?.hook_owner_kind || "";
    const framework = hookFeats[0]?.framework || frameworkDefault || "Cypress";
    const importMap = buildImportMap(sf);
    const helperNames = new Set([
      ...collectImportedHelperNames(importMap, absFile, repoPath, tsconfigCache, project),
    ]);
    for (const f of hookFeats) {
      const n = calleeNameFromFeature(f);
      if (n && (f.feature_type === "custom_command_call" || registry.has(n))) {
        helperNames.add(n);
      }
    }

    const seeds = buildHookSeeds(hookFeats, meta?.callback, sf, {
      registry,
      collectHelperCallsInNode,
      isCypressCustomCommandExpr,
      shouldSeedHookCall,
      helperNames,
      importMap,
      absFile,
      repoPath,
      tsconfigCache,
      project,
      shouldSeedCall,
    });
    if (!seeds.length) continue;

    const hookCfRoot = meta?.callback || sf;
    const queue = seeds.map((c) => ({
      callName: c.name,
      callExpr: c.call,
      from: "hook",
      depth: 1,
      fromFile: absFile,
      line: c.line,
      helper_chain: [c.name],
      helper_node_chain: [],
      inheritedCfStack: c.call ? captureControlFlowStackAtNode(hookCfRoot, c.call, null) : null,
    }));

    const visitedFiles = new Set();
    const queued = new Set();
    let helperFilesUsed = 0;

    while (queue.length > 0) {
      const item = queue.shift();
      const start = item.callExpr ? item.callExpr.getStart() : 0;
      const end = item.callExpr ? item.callExpr.getEnd() : 0;
      const qk = `${hookKey}|${item.fromFile}|${start || item.line}|${end}|${item.callName}`;
      if (queued.has(qk)) continue;
      queued.add(qk);

      if (item.depth > maxDepth) {
        const helperCallsiteId = callsiteId(item.callExpr, item.fromFile, repoPath, item.line, item.callName);
        if (shouldReportUnresolved(item, item.callExpr)) {
          pushHookUnresolved(hookKey, {
            repo: repoMeta.repo,
            test_id: "",
            hook_instance_key: hookKey,
            call: item.callName,
            source_file: relFile,
            line: item.line,
            reason: "max_depth_exceeded",
            expansion_scope: "hook",
            helper_callsite_id: helperCallsiteId,
            helper_expansion_evidence_basis: "unresolved",
            helper_expansion_confidence: "low",
          });
        }
        continue;
      }

      const fromSf = project.getSourceFile(item.fromFile);
      const fileImportMap = fromSf ? buildImportMap(fromSf) : importMap;
      const resolved = resolveCall(item.fromFile, item.callName, fileImportMap, item.callExpr);

      if (!resolved || resolved.unresolved) {
        const helperCallsiteId = callsiteId(item.callExpr, item.fromFile, repoPath, item.line, item.callName);
        let reason = resolved?.unresolved || "import_not_resolved";
        if (isUnresolvedCyCustom(item.callExpr)) {
          reason = "cypress_command_not_resolved";
        }
        if (shouldReportUnresolved(item, item.callExpr)) {
          pushHookUnresolved(hookKey, {
            repo: repoMeta.repo,
            test_id: "",
            hook_instance_key: hookKey,
            call: item.callName,
            source_file: relFile,
            line: item.line,
            reason,
            expansion_scope: "hook",
            helper_callsite_id: helperCallsiteId,
            helper_expansion_evidence_basis: "unresolved",
            helper_expansion_confidence: "low",
          });
        }
        pushHookEdge({
          repo: repoMeta.repo,
          test_id: "",
          hook_instance_key: hookKey,
          from: item.from,
          to: item.callName,
          target_file: resolved?.resolvedPath || "",
          resolved: false,
          depth: item.depth,
          helper_callsite_id: helperCallsiteId,
          helper_expansion_evidence_basis: "unresolved",
          helper_expansion_confidence: "low",
        });
        continue;
      }

      const helperTargetNodeId = nodeId(resolved.target, resolved.file, repoPath);
      const helperCallsiteId = callsiteId(item.callExpr, item.fromFile, repoPath, item.line, item.callName);
      const helperNodeChain = item.helper_node_chain || [];
      if (helperTargetNodeId && helperNodeChain.includes(helperTargetNodeId)) {
        if (shouldReportUnresolved(item, item.callExpr)) {
          pushHookUnresolved(hookKey, {
            repo: repoMeta.repo,
            test_id: "",
            hook_instance_key: hookKey,
            call: item.callName,
            source_file: relFile,
            line: item.line,
            reason: "helper_cycle_detected",
            expansion_scope: "hook",
            helper_callsite_id: helperCallsiteId,
            helper_target_node_id: helperTargetNodeId,
            helper_expansion_evidence_basis: "unresolved",
            helper_expansion_confidence: "low",
          });
        }
        continue;
      }
      const nextHelperNodeChain = helperTargetNodeId
        ? [...helperNodeChain, helperTargetNodeId]
        : helperNodeChain;
      const evidence = resolvedEvidence(resolved);

      if (helperFilesUsed >= maxHelperFiles) {
        if (shouldReportUnresolved(item, item.callExpr)) {
          pushHookUnresolved(hookKey, {
          repo: repoMeta.repo,
          test_id: "",
          hook_instance_key: hookKey,
          call: item.callName,
          source_file: relFile,
          line: item.line,
          reason: "max_files_exceeded",
          expansion_scope: "hook",
          helper_callsite_id: helperCallsiteId,
          helper_target_node_id: helperTargetNodeId,
          helper_expansion_evidence_basis: "unresolved",
          helper_expansion_confidence: "low",
          });
        }
        continue;
      }

      if (!visitedFiles.has(resolved.file)) {
        visitedFiles.add(resolved.file);
        helperFilesUsed += 1;
      }

      pushHookEdge({
        repo: repoMeta.repo,
        test_id: "",
        hook_instance_key: hookKey,
        from: item.from,
        to: item.callName,
        target_file: toPosix(path.relative(repoPath, resolved.file)),
        resolved: true,
        depth: item.depth,
        helper_callsite_id: helperCallsiteId,
        helper_target_node_id: helperTargetNodeId,
        helper_resolution_kind: resolved.kind,
        ...evidence,
      });

      const helperSf =
        project.getSourceFile(resolved.file) ||
        (() => {
          try {
            return project.addSourceFileAtPath(resolved.file);
          } catch (_) {
            return null;
          }
        })();
      const pageSymbolOrigins = helperSf ? buildPageSymbolOrigins(helperSf) : new Map();

      const ctx = {
        repo: repoMeta.repo,
        test_id: "",
        file_path: relFile,
        phase1_confidence: "high",
        framework,
        contexts: [],
        source_kind: sourceKind,
        hook_instance_key: hookKey,
        hook_owner_kind: hookOwnerKind,
        is_shared_hook_feature: true,
        helper_name: item.callName,
        helper_depth: item.depth,
        importMap: fileImportMap,
        astCtx: { pageSymbolOrigins, fixtureProvenanceMap: new Map() },
        initialCfStack: item.inheritedCfStack || null,
      };

      const body = resolved.target;
      ctx.context_node = body;
      const feats = [];
      walkNodeForFeatures(body, ctx, feats);
      const bodyPhases = scanFunctionBodyPhaseHints(body);
      for (const f of feats) {
        pushHookExpanded({
          ...f,
          source_kind: resolved.kind === "cypress_command" ? "cypress_command" : f.source_kind,
          helper_name: item.callName,
          helper_depth: item.depth,
          helper_call_line: item.line,
          helper_call_start_offset: item.callExpr ? item.callExpr.getStart() : 0,
          helper_call_end_offset: item.callExpr ? item.callExpr.getEnd() : 0,
          helper_callsite_id: helperCallsiteId,
          helper_target_node_id: helperTargetNodeId,
          helper_resolution_kind: resolved.kind,
          ...evidence,
          target_file: toPosix(path.relative(repoPath, resolved.file)),
          hook_instance_key: hookKey,
          hook_owner_kind: hookOwnerKind,
          is_shared_hook_feature: true,
          helper_resolution_status: "resolved",
        });
      }

      if (item.depth < maxDepth) {
        const nested = collectHelperCallsInNode(body, { allowMethods: true });
        for (const n of nested) {
          if (item.helper_chain.includes(n.name)) continue;
          if (
            !shouldSeedHookCall(
              n,
              registry,
              helperNames,
              fileImportMap,
              resolved.file,
              repoPath,
              tsconfigCache,
              project,
              shouldSeedCall,
              isCypressCustomCommandExpr
            )
          ) {
            continue;
          }
          queue.push({
            callName: n.name,
            callExpr: n.call,
            from: item.callName,
            depth: item.depth + 1,
            fromFile: resolved.file,
            line: n.line,
            helper_chain: [...item.helper_chain, n.name],
            helper_node_chain: nextHelperNodeChain,
            inheritedCfStack: captureControlFlowStackAtNode(
              body,
              n.call,
              item.inheritedCfStack || null
            ),
          });
        }
      }
    }
  }

  return hookExpandedByKey;
}

module.exports = {
  buildHookCallbackIndex,
  expandHookCustomCommandsForRepo,
};
