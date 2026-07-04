"use strict";

/** Dedupe key for helper_edges rows (matches review gate spec). */
function helperEdgeDedupeKey(edge) {
  const resolved =
    edge.resolved === true ? "1" : edge.resolved === false ? "0" : String(edge.resolved ?? "");
  return [
    edge.repo || "",
    edge.test_id || "",
    edge.hook_instance_key || "",
    edge.from || "",
    edge.to || "",
    edge.target_file || "",
    edge.helper_callsite_id || "",
    edge.helper_target_node_id || "",
    edge.depth ?? "",
    resolved,
  ].join("|");
}

module.exports = { helperEdgeDedupeKey };
