"use strict";

const { normalizeWaitFeatureType } = require("../phase2b/directFeatureExtractor");

/**
 * Attach shared hook features to per-test expanded output (for downstream tools).
 */function buildHookFeaturesByKey(directFeatures) {
  const hookByKey = new Map();
  for (const f of directFeatures) {
    if (!f.is_shared_hook_feature || !f.hook_instance_key) continue;
    if (!hookByKey.has(f.hook_instance_key)) hookByKey.set(f.hook_instance_key, []);
    hookByKey.get(f.hook_instance_key).push(f);
  }
  return hookByKey;
}

function hookAttachDedupeKey(tid, hookKey, f) {
  return expandedFeatureDedupeKey({ ...f, test_id: tid, hook_instance_key: hookKey });
}

function expandedFeatureDedupeKey(f) {
  return [
    f.test_id || "",
    f.hook_instance_key || "",
    f.helper_depth || 0,
    f.line,
    f.feature_type,
    f.name,
    f.target_file || "",
    f.attached_from_hook ? "hook" : "",
  ].join("|");
}

function seedSeenFromExpanded(seen, expandedFeatures) {
  for (const f of expandedFeatures) {
    if (!f.attached_from_hook || !f.test_id) continue;
    const key = f.hook_instance_key || "";
    seen.add(hookAttachDedupeKey(f.test_id, key, f));
  }
}

function hookExpansionWasAttempted(key, hookExpandedByKey) {
  const bucket = hookExpandedByKey && hookExpandedByKey.get(key);
  if (!bucket) return false;
  return Boolean(
    (bucket.features && bucket.features.length > 0) ||
      (bucket.unresolved && bucket.unresolved.length > 0)
  );
}

function attachHookFeaturesToExpanded(
  expandedFeatures,
  directFeatures,
  testCases,
  hookExpandedByKey
) {
  const hookByKey = buildHookFeaturesByKey(directFeatures);
  const out = [...expandedFeatures];
  const seen = new Set();
  seedSeenFromExpanded(seen, expandedFeatures);

  for (const tc of testCases) {
    const tid = tc.test_id;
    if (!tid) continue;
    for (const key of tc.hook_instance_keys || []) {
      const skipShallowCustom = hookExpansionWasAttempted(key, hookExpandedByKey);
      for (const f of hookByKey.get(key) || []) {
        if (skipShallowCustom && f.feature_type === "custom_command_call") continue;
        const dedupe = hookAttachDedupeKey(tid, key, f);
        if (seen.has(dedupe)) continue;
        seen.add(dedupe);
        out.push(
          normalizeWaitFeatureType({
            ...f,
            test_id: tid,
            helper_depth: f.helper_depth || 0,
            attached_from_hook: true,
            is_shared_hook_feature: false,
          })
        );
      }
      const expanded = hookExpandedByKey && hookExpandedByKey.get(key);
      if (!expanded || !expanded.features) continue;
      for (const f of expanded.features) {
        const dedupe = hookAttachDedupeKey(tid, key, f);
        if (seen.has(dedupe)) continue;
        seen.add(dedupe);
        out.push(
          normalizeWaitFeatureType({
            ...f,
            test_id: tid,
            helper_depth: f.helper_depth || 0,
            attached_from_hook: true,
            is_shared_hook_feature: false,
            hook_instance_key: key,
          })
        );
      }
    }
  }
  return out;
}

function testHasHookUi(testCase, hookByKey, hookExpandedByKey) {
  return (testCase.hook_instance_keys || []).some((key) => {
    const expanded = hookExpandedByKey && hookExpandedByKey.get(key);
    if (expanded && (expanded.features || []).some((f) => f.feature_type === "ui_action")) {
      return true;
    }
    return (hookByKey.get(key) || []).some((f) => f.feature_type === "ui_action");
  });
}

module.exports = {
  buildHookFeaturesByKey,
  hookAttachDedupeKey,
  expandedFeatureDedupeKey,
  seedSeenFromExpanded,
  attachHookFeaturesToExpanded,
  testHasHookUi,
};
