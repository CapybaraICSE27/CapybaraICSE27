"""Per-test incremental aggregation for Phase 2D (streaming-safe)."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, TextIO, Tuple

from classify import (
    classify_assertion,
    classify_interaction,
    classify_setup,
    infer_locator_strategy,
    is_rq1_environment_feature,
    map_input_source,
)
from input_classify import input_ast_audit_mismatch_type, resolve_input_pattern
from input_plausibility import format_value_for_display, format_upload_display_value, map_input_plausibility_paper_label
from rq2_review_queue import (
    RQ2_REVIEW_QUEUE_FIELDS,
    build_review_row,
    should_enqueue_review,
)
from pattern_classify import (
    classify_auto_retry_capabilities,
    classify_sync_pattern,
    implementation_coupled_signal,
    infer_workflow_archetype,
    infer_workflow_archetype_detail,
    is_assertion_retry_sync_feature,
    is_page_object_model_abstraction,
    is_page_object_setup_or_utility_call,
    locator_ast_audit_mismatch_type,
    positive_resilience_signals,
    resolve_locator_pattern,
    resolve_wait_pattern,
    resolve_workflow_pattern,
    sync_placement,
)
from feature_merge import feature_dedupe_key, helper_edge_dedupe_key
from static_metrics_join import (
    StaticMetricsLoadResult,
    build_static_metrics_by_test_rows,
    join_summary,
    merge_static_fields,
)
from stream_io import test_key
from assertion_metrics import build_assertion_density_fields
from assertion_semantics import classify_verification_intent_detail
from llm_semantic_categorizer import (
    LlmSemanticCorrector,
    apply_deterministic_semantic_columns,
    should_trigger_rq2_indeterminate_adjudication,
    should_trigger_llm_correction,
)
from interaction_sequence_metrics import (
    compute_dual_scope_sequence_metrics,
    normalize_action_signature,
    resolve_navigation_target_fields,
)
from interaction_control_flow_metrics import (
    build_control_flow_fields,
    compute_dual_scope_control_flow_metrics,
)
from assertion_chain_metrics import build_assertion_chain_fields
from setup_teardown_intent import (
    build_intent_candidate,
    resolve_test_intent_units,
    summarize_rq1_intent_by_test,
    summarize_rq1_intent_corpus,
    match_resolved_helper_wrapper,
)
from rq1_intent_review_queue import (
    RQ1_INTENT_REVIEW_QUEUE_FIELDS,
    build_intent_review_row,
)

HOOK_SOURCE_KINDS = frozenset({
    "before",
    "after",
    "beforeEach",
    "afterEach",
    "beforeAll",
    "afterAll",
})


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def bool_text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    s = str(value or "").strip().lower()
    return "true" if s in {"1", "true", "yes", "y"} else "false"


def ui_action_category_from_feature(feature: Dict[str, Any], name: str, raw: str) -> str:
    structured = str(feature.get("ui_action_category") or "").strip().lower()
    if structured and structured != "unknown_action":
        return structured
    terminal = str(feature.get("terminal_action_ast") or "").strip()
    if terminal:
        inferred = classify_interaction(terminal, raw)
        if inferred != "unknown_action":
            return inferred
    return classify_interaction(name, raw)


@dataclass
class TestAgg:
    repo: str
    test_id: str
    phase1_confidence: str = ""
    framework: str = ""
    describe_depth: int = 0
    is_parameterized: bool = False
    parameterization_type: str = ""
    parameter_row_count: int = 0
    fixtures_used: str = ""

    rq1_categories: Counter = field(default_factory=Counter)
    rq2_categories: Counter = field(default_factory=Counter)
    rq2_plausibility_counts: Counter = field(default_factory=Counter)
    rq2_action_input_context_by_line: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    rq4_categories: Counter = field(default_factory=Counter)
    rq5_categories: Counter = field(default_factory=Counter)
    rq5_verification_intent_counts: Counter = field(default_factory=Counter)
    ui_action_sequence_events: List[Dict[str, Any]] = field(default_factory=list)
    test_body_ui_action_sequence_events: List[Dict[str, Any]] = field(default_factory=list)
    ui_action_control_flow_events: List[Dict[str, Any]] = field(default_factory=list)
    test_body_ui_action_control_flow_events: List[Dict[str, Any]] = field(default_factory=list)
    rq5_assertion_chain_events: List[Dict[str, Any]] = field(default_factory=list)
    resolved_helper_seeds: Set[Tuple[int, str, int, int]] = field(default_factory=set)
    helper_body_phase_by_seed: Dict[Tuple[int, str, int, int], str] = field(default_factory=dict)
    ui_action_sequence_ingest_index: int = 0

    uses_helper: bool = False
    uses_imported_helper: bool = False
    uses_page_object: bool = False
    uses_cypress_command: bool = False
    uses_fixture: bool = False
    helper_call_count: int = 0
    custom_command_call_count: int = 0
    cypress_command_expanded_feature_count: int = 0
    wait_sync_count: int = 0
    locator_strategies: Counter = field(default_factory=Counter)
    helper_edge_count: int = 0

    rq1_count: int = 0
    rq2_count: int = 0
    rq4_count: int = 0
    rq5_count: int = 0

    test_body_ui_action_lines: List[int] = field(default_factory=list)
    test_body_ui_action_count: int = 0
    hook_ui_action_count: int = 0
    helper_ui_action_count: int = 0
    cypress_command_ui_action_count: int = 0
    navigation_count: int = 0

    test_body_assertion_lines: List[int] = field(default_factory=list)
    test_body_assertion_count: int = 0
    direct_assertion_count: int = 0
    hook_assertion_count: int = 0
    helper_assertion_count: int = 0

    has_direct_ui_actions: bool = False
    has_hook_ui_actions: bool = False
    has_helper_expanded_ui_actions: bool = False

    # RQ3 pattern summaries
    locator_strategy_norm: Counter = field(default_factory=Counter)
    locator_composition_counts: Counter = field(default_factory=Counter)
    robustness_signal_counts: Counter = field(default_factory=Counter)
    locator_event_count: int = 0
    locator_bearing_ui_action_count: int = 0
    sync_pattern_counts: Counter = field(default_factory=Counter)
    fixed_delay_sync_count: int = 0
    condition_based_sync_count: int = 0
    network_sync_count: int = 0
    assertion_retry_sync_count: int = 0
    auto_wait_capable_action_count: int = 0
    retryable_query_count: int = 0
    abstraction_kind_counts: Counter = field(default_factory=Counter)
    workflow_layer_counts: Counter = field(default_factory=Counter)
    page_object_ui_action_count: int = 0
    page_object_ui_call_count: int = 0
    page_object_setup_or_utility_call_count: int = 0
    page_object_call_count: int = 0
    page_object_signal_present: bool = False
    unresolved_helper_call_count: int = 0
    bdd_step_definition_count: int = 0
    playwright_test_step_count: int = 0
    workflow_event_count: int = 0
    rq3_locator_ui_action_rows: int = 0
    ast_regex_locator_mismatches: int = 0
    ast_locator_low_confidence_rows: int = 0
    ast_locator_audit_nonmatch_rows: int = 0

    rq1_intent_candidates: List[Dict[str, Any]] = field(default_factory=list)
    first_non_navigation_ui_line: Optional[int] = None


class CsvEventSink:
    """Append event rows to CSV without holding them in memory."""

    def __init__(self, path: Path, fieldnames: List[str]) -> None:
        self.path = path
        self.fieldnames = fieldnames
        self._file: Optional[TextIO] = None
        self._writer: Optional[csv.DictWriter] = None
        self.count = 0

    def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("w", encoding="utf-8", errors="replace", newline="")
        self._writer = csv.DictWriter(self._file, fieldnames=self.fieldnames, extrasaction="ignore")
        self._writer.writeheader()

    def write(self, row: Dict[str, Any]) -> None:
        if self._writer is None:
            self.open()
        assert self._writer is not None
        self._writer.writerow({k: row.get(k, "") for k in self.fieldnames})
        self.count += 1

    def ensure_created(self) -> None:
        if self._writer is None:
            self.open()

    def close(self) -> None:
        if self._file:
            self._file.close()
            self._file = None
            self._writer = None


class Aggregator:
    RQ2_COMPANION_INPUT_CONTEXT_FIELDS = [
        "input_target_role_ast",
        "input_target_role_basis_ast",
        "input_target_context_ast",
        "input_target_context_normalized_ast",
        "input_target_context_basis_ast",
        "input_value_expression_kind_ast",
        "input_endpoint_construction_ast",
        "input_endpoint_construction_basis_ast",
    ]

    RQ1_FIELDS = [
        "repo", "test_id", "framework", "phase1_confidence", "category", "feature_type",
        "name", "source_kind", "helper_depth", "attached_from_hook",
    ]
    RQ1_INTENT_EVENT_FIELDS = [
        "repo", "test_id", "framework", "phase1_confidence",
        "file_path", "source_start_offset", "source_end_offset",
        "line", "name", "raw_code", "feature_type", "source_kind",
        "hook_instance_key", "wrapper_only",
        "helper_depth", "attached_from_hook",
        "inventory_category", "phase", "scope", "primary_intent",
        "primary_intent_evidence_basis", "operation_kind", "operation_kind_evidence_basis",
        "confidence", "needs_review", "review_reason",
        "uncertain_reason", "fallback_used", "structured_evidence_available",
        "helper_resolution_status", "child_setup_unit_count",
        "child_intent_counts_json", "dominant_child_intent", "mixed_intent_score",
        "provenance_basis", "eligibility_basis", "partial_coverage_note",
    ]
    RQ2_FIELDS = [
        "repo", "test_id", "framework", "phase1_confidence",
        "input_source_class", "input_source_inferred", "input_generation_class",
        "input_plausibility", "input_plausibility_confidence",
        "input_plausibility_paper_label",
        "input_plausibility_codebook_path",
        "input_plausibility_deterministic", "input_plausibility_llm",
        "input_plausibility_final", "input_plausibility_final_basis",
        "input_plausibility_llm_trigger_reason",
        "input_plausibility_llm_confidence", "input_plausibility_llm_rationale",
        "input_plausibility_llm_codebook_step",
        "input_plausibility_pre_adjudication_final",
        "input_plausibility_adjudication_label",
        "input_plausibility_adjudication_confidence",
        "input_plausibility_adjudication_trigger_reason",
        "input_plausibility_adjudication_codebook_step",
        "input_plausibility_adjudication_rationale",
        "llm_model", "llm_prompt_version", "llm_input_hash",
        "value_visibility", "input_channel",
        "input_provenance", "input_provenance_family", "input_provenance_components_json",
        "external_file_path", "field_path", "field_context",
        "input_target_role_ast", "input_target_role_basis_ast",
        "input_target_context_ast", "input_target_context_normalized_ast",
        "input_target_context_basis_ast", "input_value_expression_kind_ast",
        "input_endpoint_construction_ast", "input_endpoint_construction_basis_ast",
        "input_evidence_basis", "input_source_confidence", "needs_review", "rq2_unit",
        "rq2_value_bearing_input", "rq2_value_exclusion_reason", "rq2_value_bearing_basis",
        "input_origin_kind", "input_origin_confidence", "input_origin_evidence",
        "linked_definition_line", "linked_definition_file", "is_static_file_candidate",
        "category", "input_source", "value_summary", "name", "raw_code",
        "helper_depth", "attached_from_hook", "line",
    ]
    RQ2_AST_INPUT_AUDIT_FIELDS = [
        "repo", "test_id", "framework", "line", "name", "raw_code",
        "input_source_ast", "input_source_inferred", "mismatch_type",
        "input_plausibility", "input_plausibility_paper_label", "input_plausibility_codebook_path", "value_visibility_ast",
        "input_target_role_ast", "input_target_context_ast",
        "input_value_expression_kind_ast", "input_endpoint_construction_ast",
    ]
    RQ4_FIELDS = [
        "repo", "test_id", "framework", "phase1_confidence", "category", "name",
        "source_file", "file_path", "source_kind", "helper_depth", "attached_from_hook",
        "hook_instance_key", "line",
        "raw_code", "source_start_offset", "source_end_offset",
        "feature_type", "action_signature", "action_signature_v2",
        "ui_action_category", "terminal_action_ast", "callee_chain_json",
        "locator_strategy_ast", "input_channel_ast",
        "sequence_index", "navigation_target", "navigation_target_evidence_basis",
        "control_flow_enclosure", "control_flow_loop_depth", "control_flow_branch_depth",
        "control_flow_branch_kind", "control_flow_branch_arm", "control_flow_source",
        "enclosing_control_flow_snippet", "control_flow_parent_kind",
        "control_flow_parent_line", "control_flow_parent_start_offset",
        "control_flow_parent_end_offset",
        "control_flow_callback_method", "control_flow_callback_receiver",
        "control_flow_ancestor_chain",
        "action_snippet", "enclosing_function_or_callback_snippet",
        "test_body_or_helper_context_snippet", "snippet_truncated",
        "action_signature_json",
    ]
    RQ5_FIELDS = [
        "repo", "test_id", "framework", "phase1_confidence", "category", "name",
        "source_kind", "assertion_source", "helper_depth", "attached_from_hook", "line",
        "raw_code", "assertion_chain_raw_code",
        "assertion_chain_raw_code_length", "assertion_chain_raw_code_truncated",
        "assertion_execution_scope", "assertion_provenance", "verification_intent",
        "verification_intent_deterministic", "verification_intent_llm",
        "verification_intent_final", "verification_intent_final_basis",
        "verification_intent_llm_trigger_reason",
        "verification_intent_llm_confidence", "verification_intent_llm_rationale",
        "verification_intent_llm_codebook_step",
        "llm_model", "llm_prompt_version", "llm_input_hash",
        "verification_intent_evidence_basis", "verification_intent_confidence",
        "verification_intent_matched_signal", "verification_intent_codebook_path",
        "assertion_framework_context", "assertion_library_syntax", "assertion_framework",
        "assertion_chain_root_id", "assertion_chain_index", "assertion_chain_length",
        "chain_matcher_sequence_json", "non_assertion_chain_methods_json",
        "assertion_matcher", "assertion_semantic_matcher_ast",
        "assertion_semantic_matcher_basis_ast", "assertion_subject_kind",
        "assertion_subject_basis_ast",
        "assertion_subject_root_ast", "assertion_subject_path_json",
        "assertion_subject_text_ast",
        "assertion_subject_semantic_role_ast", "assertion_subject_semantic_role_basis_ast",
        "assertion_callback_intent_hint_ast", "assertion_callback_intent_basis_ast",
        "assertion_callback_intent_hints_json", "assertion_callback_nested_assertion_count",
        "assertion_callback_nested_matchers_json", "assertion_callback_subject_properties_json",
        "assertion_callback_literal_args_json",
        "is_soft_assertion", "is_negated_assertion", "promise_modifier",
        "chai_modifier_deep", "assertion_modifiers_json",
        "is_grouped_assertion", "assertion_group_kind",
    ]
    RQ3_LOCATOR_FIELDS = [
        "repo", "test_id", "framework", "phase1_confidence", "source_kind", "line", "name",
        "raw_code", "ui_action_category", "locator_present", "raw_framework_api",
        "normalized_strategy", "locator_composition", "robustness_signal", "evidence_basis",
        "selector_literal_kind", "selector_depth", "has_positional_refinement",
        "selector_channel", "selector_value_origin",
        "selector_channel_ast", "selector_value_origin_ast", "selector_channel_basis",
        "has_chained_refinement", "has_text_filter",
        "has_testid_signal", "helper_depth", "attached_from_hook", "confidence",
        "locator_strategy_inferred", "locator_evidence_basis",
        "locator_composition_evidence_basis",
    ]
    RQ3_SYNC_FIELDS = [
        "repo", "test_id", "framework", "phase1_confidence", "source_kind", "line", "name",
        "raw_code", "sync_pattern", "sync_target", "sync_placement", "is_fixed_delay",
        "sync_arg_kind",
        "sync_call_kind_ast", "sync_arg_kind_ast",
        "is_condition_based", "is_network_based", "is_assertion_retry",
        "is_framework_auto_wait_inferred", "helper_depth", "attached_from_hook", "confidence",
        "sync_evidence_basis",
    ]
    RQ3_WORKFLOW_FIELDS = [
        "repo", "test_id", "framework", "phase1_confidence", "source_kind", "line", "name",
        "raw_code", "abstraction_kind", "interaction_ownership", "reuse_scope", "helper_depth",
        "helper_target_file", "resolved", "attached_from_hook", "expanded_ui_action_count",
        "confidence", "workflow_evidence_basis",
    ]
    RQ3_AST_LOCATOR_AUDIT_FIELDS = [
        "repo",
        "test_id",
        "framework",
        "line",
        "raw_code",
        "locator_strategy_ast",
        "locator_strategy_inferred",
        "locator_composition_ast",
        "locator_composition_inferred",
        "selector_literal_kind_ast",
        "selector_literal_kind_inferred",
        "selector_channel_ast",
        "selector_value_origin_ast",
        "ast_confidence",
        "mismatch_type",
    ]

    def __init__(
        self,
        test_cases: Dict[str, Dict[str, Any]],
        output_dir: Path,
        *,
        static_metrics_by_key: Optional[Dict[str, Dict[str, Any]]] = None,
        static_metrics_load: Optional[StaticMetricsLoadResult] = None,
        llm_corrector: Optional[LlmSemanticCorrector] = None,
    ) -> None:
        self.test_cases = test_cases
        self.output_dir = output_dir
        self.static_metrics_by_key = static_metrics_by_key
        self.static_metrics_load = static_metrics_load
        self.llm_corrector = llm_corrector
        self.by_key: Dict[str, TestAgg] = {}
        self.global_seen: Set[str] = set()
        self.seen_helper_edges: Set[str] = set()
        self.rq3_ast_provenance: Dict[str, int] = {
            "ui_action_rows": 0,
            "locator_rows_with_ast_strategy": 0,
            "locator_rows_with_ast_call_chain": 0,
            "wait_rows_with_ast_subtype": 0,
            "assertion_rows_with_ast_retry": 0,
            "workflow_rows_with_ast_kind": 0,
            "workflow_rows_with_fixture_provenance": 0,
            "workflow_rows_with_page_symbol_origin": 0,
            "ui_rows_with_action_signature_json": 0,
            "ui_rows_with_control_flow_field_present": 0,
            "ui_rows_with_control_flow_enclosure_non_none": 0,
            "assertion_rows_with_chain_fields": 0,
            "features_with_framework_api_category": 0,
        }

        self.rq1_sink = CsvEventSink(output_dir / "rq1_environment_control_events.csv", self.RQ1_FIELDS)
        self.rq2_sink = CsvEventSink(output_dir / "rq2_input_events.csv", self.RQ2_FIELDS)
        self.rq2_ast_input_audit_sink = CsvEventSink(
            output_dir / "rq2_ast_vs_regex_input_audit.csv",
            self.RQ2_AST_INPUT_AUDIT_FIELDS,
        )
        self.rq4_sink = CsvEventSink(output_dir / "rq4_interaction_events.csv", self.RQ4_FIELDS)
        self.rq5_sink = CsvEventSink(output_dir / "rq5_assertion_events.csv", self.RQ5_FIELDS)
        self.rq3_locator_sink = CsvEventSink(
            output_dir / "rq3_locator_pattern_events.csv", self.RQ3_LOCATOR_FIELDS
        )
        self.rq3_sync_sink = CsvEventSink(
            output_dir / "rq3_sync_pattern_events.csv", self.RQ3_SYNC_FIELDS
        )
        self.rq3_workflow_sink = CsvEventSink(
            output_dir / "rq3_workflow_pattern_events.csv", self.RQ3_WORKFLOW_FIELDS
        )
        self.rq3_ast_locator_audit_sink = CsvEventSink(
            output_dir / "rq3_ast_vs_regex_locator_audit.csv",
            self.RQ3_AST_LOCATOR_AUDIT_FIELDS,
        )
        self.rq2_review_rows: List[Dict[str, Any]] = []
        self.rq1_intent_review_rows: List[Dict[str, Any]] = []
        self._rq1_intent_event_rows: List[Dict[str, Any]] = []
        self._semantic_event_buffers: List[
            Tuple[str, Dict[str, Any], CsvEventSink, Callable[[Dict[str, Any]], None]]
        ] = []
        self.event_sinks = [
            self.rq1_sink,
            self.rq2_sink,
            self.rq2_ast_input_audit_sink,
            self.rq4_sink,
            self.rq5_sink,
            self.rq3_locator_sink,
            self.rq3_sync_sink,
            self.rq3_workflow_sink,
            self.rq3_ast_locator_audit_sink,
        ]

        for _key, tc in test_cases.items():
            path = tc.get("describe_path") or []
            if isinstance(path, str):
                depth = len([p for p in path.split(">") if p.strip()])
            else:
                depth = len(path)
            repo = str(tc.get("repo") or "").strip()
            test_id = str(tc.get("test_id") or "").strip()
            canonical_key = test_key(repo, test_id)
            self.by_key[canonical_key] = TestAgg(
                repo=repo,
                test_id=test_id,
                phase1_confidence=str(tc.get("phase1_confidence") or ""),
                framework=str(tc.get("framework") or ""),
                describe_depth=depth,
                is_parameterized=bool(tc.get("is_parameterized")),
                parameterization_type=str(tc.get("parameterization_type") or ""),
                parameter_row_count=int(tc.get("parameter_row_count") or 0),
                fixtures_used=";".join(tc.get("fixtures_used") or [])
                if isinstance(tc.get("fixtures_used"), list)
                else str(tc.get("fixtures_used") or ""),
                has_direct_ui_actions=bool(tc.get("has_direct_ui_actions")),
                has_hook_ui_actions=bool(tc.get("has_hook_ui_actions")),
                has_helper_expanded_ui_actions=bool(tc.get("has_helper_expanded_ui_actions")),
            )

    def _apply_semantic_correction(self, rq: str, row: Dict[str, Any]) -> Dict[str, Any]:
        if self.llm_corrector is not None:
            return self.llm_corrector.correct(rq, row)
        return apply_deterministic_semantic_columns(rq, row)

    def _apply_semantic_corrections(self, rq: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self.llm_corrector is not None:
            return self.llm_corrector.correct_many(rq, rows)
        return [apply_deterministic_semantic_columns(rq, row) for row in rows]

    def _write_or_buffer_semantic_event(
        self,
        rq: str,
        row: Dict[str, Any],
        sink: CsvEventSink,
        on_write: Callable[[Dict[str, Any]], None],
    ) -> None:
        trigger = should_trigger_llm_correction(rq, row)
        adjudication_trigger = ""
        if rq == "rq2":
            adjudication_trigger = should_trigger_rq2_indeterminate_adjudication(row)
        if self.llm_corrector is not None and (trigger or adjudication_trigger):
            if self.llm_corrector.enabled or self.llm_corrector.dry_run:
                self._semantic_event_buffers.append((rq, row, sink, on_write))
                return
            corrected = self.llm_corrector.correct(rq, row)
        else:
            corrected = apply_deterministic_semantic_columns(rq, row)
        sink.write(corrected)
        on_write(corrected)

    def _flush_semantic_event_buffers(self) -> None:
        if not self._semantic_event_buffers:
            return
        by_rq: Dict[str, List[Tuple[Dict[str, Any], CsvEventSink, Callable[[Dict[str, Any]], None]]]] = {}
        for rq, row, sink, on_write in self._semantic_event_buffers:
            by_rq.setdefault(rq, []).append((row, sink, on_write))
        self._semantic_event_buffers = []
        for rq, items in by_rq.items():
            corrected_rows = self._apply_semantic_corrections(rq, [row for row, _sink, _on_write in items])
            for corrected, (_row, sink, on_write) in zip(corrected_rows, items):
                sink.write(corrected)
                on_write(corrected)

    def _agg(self, repo: str, test_id: str) -> Optional[TestAgg]:
        return self.by_key.get(test_key(repo, test_id))

    def _base_event_fields(self, agg: TestAgg, repo: str, test_id: str) -> Dict[str, Any]:
        return {
            "repo": repo,
            "test_id": test_id,
            "framework": agg.framework,
            "phase1_confidence": agg.phase1_confidence,
        }

    def _track_rq3_ast_provenance(self, f: Dict[str, Any], feature_type: str) -> None:
        ft = (feature_type or "").lower()
        p = self.rq3_ast_provenance
        if ft == "ui_action":
            p["ui_action_rows"] += 1
            if (f.get("locator_strategy_ast") or "").strip():
                p["locator_rows_with_ast_strategy"] += 1
            chain = f.get("callee_chain_json") or ""
            if chain and chain not in ("[]", ""):
                p["locator_rows_with_ast_call_chain"] += 1
            if (f.get("action_signature_json") or "").strip():
                p["ui_rows_with_action_signature_json"] += 1
            enclosure = (f.get("control_flow_enclosure") or "").strip()
            if enclosure:
                p["ui_rows_with_control_flow_field_present"] += 1
            if enclosure and enclosure != "none":
                p["ui_rows_with_control_flow_enclosure_non_none"] += 1
        if ft == "wait_synchronization":
            if (f.get("wait_subtype_ast") or "").strip():
                p["wait_rows_with_ast_subtype"] += 1
        if ft == "assertion":
            if (f.get("wait_subtype_ast") or "").strip() == "assertion_retry_wait":
                p["assertion_rows_with_ast_retry"] += 1
            if (f.get("assertion_chain_root_id") or "").strip():
                p["assertion_rows_with_chain_fields"] += 1
        if ft in ("helper_call", "page_object_ctor", "custom_command_call", "test_step", "ui_action"):
            if (f.get("workflow_kind_ast") or "").strip():
                p["workflow_rows_with_ast_kind"] += 1
            if (f.get("fixture_param_name") or "").strip():
                p["workflow_rows_with_fixture_provenance"] += 1
            if (f.get("page_symbol_origin_ast") or "").strip():
                p["workflow_rows_with_page_symbol_origin"] += 1
        if (f.get("framework_api_category") or "").strip():
            p["features_with_framework_api_category"] += 1

    def _apply_page_object_workflow_signals(
        self,
        agg: TestAgg,
        wf: Dict[str, Any],
        *,
        count_call: bool = False,
        feature_type: str = "",
        name: str = "",
        raw: str = "",
    ) -> None:
        """
        Update page-object flags from resolved workflow abstraction (AST-aware).

        count_call: increment page-object call counters only for helper_call /
        page_object_ctor rows (not expanded ui_action inside PO bodies).
        """
        if is_page_object_model_abstraction(wf.get("abstraction_kind", "")):
            if count_call:
                if is_page_object_setup_or_utility_call(feature_type, name, raw):
                    agg.page_object_setup_or_utility_call_count += 1
                else:
                    agg.page_object_call_count += 1
                    agg.page_object_ui_call_count += 1
            agg.page_object_signal_present = True
            agg.uses_page_object = True

    def ingest_feature(self, f: Dict[str, Any]) -> None:
        repo = str(f.get("repo") or "").strip()
        tid = str(f.get("test_id") or "").strip()
        if not repo or not tid:
            return
        dk = feature_dedupe_key(repo, tid, f)
        if dk in self.global_seen:
            return
        self.global_seen.add(dk)

        agg = self._agg(repo, tid)
        if agg is None:
            return

        ft = str(f.get("feature_type") or "")
        sk = str(f.get("source_kind") or "")
        depth = safe_int(f.get("helper_depth"))
        line = safe_int(f.get("line"))
        attached_hook = bool(f.get("attached_from_hook"))
        name = str(f.get("name") or "")
        raw = str(f.get("raw_code") or "")

        if ft == "ui_action" and line:
            companion_context = {
                field: f.get(field)
                for field in self.RQ2_COMPANION_INPUT_CONTEXT_FIELDS
                if f.get(field)
            }
            if companion_context:
                agg.rq2_action_input_context_by_line[line] = companion_context

        if ft == "input":
            action_line = safe_int(f.get("linked_action_line")) or line
            companion_context = agg.rq2_action_input_context_by_line.get(action_line, {})
            if companion_context:
                enriched = dict(f)
                for field, value in companion_context.items():
                    if value and not enriched.get(field):
                        enriched[field] = value
                f = enriched

        if ft == "helper_call" or depth > 0:
            agg.uses_helper = True
            if ft == "helper_call":
                agg.helper_call_count += 1
        if sk in ("imported_helper", "helper_function") or "helper" in sk:
            agg.uses_imported_helper = True
        if ft == "page_object_ctor" or "page_object" in sk.lower() or re_page_object(name):
            agg.uses_page_object = True
            agg.page_object_signal_present = True
        if ft == "test_step":
            agg.playwright_test_step_count += 1
        if ft == "bdd_step":
            agg.bdd_step_definition_count += 1
        if ft == "custom_command_call":
            agg.uses_cypress_command = True
            agg.custom_command_call_count += 1
        if sk == "cypress_command":
            agg.uses_cypress_command = True
            agg.cypress_command_expanded_feature_count += 1
        if ft == "wait_synchronization":
            self._track_rq3_ast_provenance(f, ft)
            agg.wait_sync_count += 1
            sync_info = resolve_wait_pattern(name, raw, agg.framework, ft, f)
            placement = sync_placement(sk, attached_hook, depth)
            self.rq3_sync_sink.write({
                **self._base_event_fields(agg, repo, tid),
                "source_kind": sk,
                "line": line,
                "name": name,
                "raw_code": raw[:500] if raw else "",
                "sync_placement": placement,
                **sync_info,
                "sync_call_kind_ast": str(
                    f.get("sync_call_kind_ast")
                    or f.get("wait_call_kind_ast")
                    or (
                        "predicate"
                        if sync_info.get("sync_pattern") == "predicate_or_custom_condition"
                        else "assertion"
                        if sync_info.get("sync_pattern") == "assertion_retry_wait"
                        else "wait_api"
                    )
                ),
                "sync_arg_kind_ast": str(
                    f.get("sync_arg_kind_ast")
                    or f.get("wait_arg_kind_ast")
                    or sync_info.get("sync_arg_kind")
                    or ""
                ),
                "helper_depth": depth,
                "attached_from_hook": attached_hook,
            })
            sp = sync_info["sync_pattern"]
            agg.sync_pattern_counts[sp] += 1
            if sync_info["is_fixed_delay"]:
                agg.fixed_delay_sync_count += 1
            if sync_info["is_condition_based"]:
                agg.condition_based_sync_count += 1
            if sync_info["is_network_based"]:
                agg.network_sync_count += 1
            if sync_info["is_assertion_retry"]:
                agg.assertion_retry_sync_count += 1
        if agg.fixtures_used or (f.get("fixture_param_name") or "").strip():
            agg.uses_fixture = True

        if ft in ("helper_call", "page_object_ctor", "custom_command_call", "test_step"):
            self._track_rq3_ast_provenance(f, ft)
            wf = resolve_workflow_pattern(
                name,
                raw,
                agg.framework,
                sk,
                depth,
                ft,
                str(f.get("target_file") or ""),
                None,
                feature=f,
                attached_hook=attached_hook,
            )
            self._apply_page_object_workflow_signals(
                agg,
                wf,
                count_call=ft in ("helper_call", "page_object_ctor"),
                feature_type=ft,
                name=name,
                raw=raw,
            )
            self._write_workflow_event(agg, repo, tid, f, wf, line, sk, depth, attached_hook)

        if is_rq1_environment_feature(f):
            cat = classify_setup(name, raw, sk, ft)
            self.rq1_sink.write({
                **self._base_event_fields(agg, repo, tid),
                "category": cat,
                "feature_type": ft,
                "name": name,
                "source_kind": sk,
                "helper_depth": depth,
                "attached_from_hook": attached_hook,
            })
            agg.rq1_categories[cat] += 1
            agg.rq1_count += 1

        intent_feature = {
            **f,
            "repo": repo,
            "test_id": tid,
            "framework": agg.framework,
            "phase1_confidence": agg.phase1_confidence,
            "feature_type": ft,
            "source_kind": sk,
            "name": name,
            "raw_code": raw,
            "line": line,
            "helper_depth": depth,
            "attached_from_hook": attached_hook,
        }
        if ft == "helper_call" and depth == 0 and sk == "test_body" and line:
            matched = match_resolved_helper_wrapper(
                agg.resolved_helper_seeds,
                line,
                name,
                start=int(f.get("source_start_offset") or 0),
                end=int(f.get("source_end_offset") or 0),
            )
            if matched:
                intent_feature["wrapper_only"] = True
                intent_feature["matched_helper_call_line"] = matched[0]
                intent_feature["matched_helper_call_start_offset"] = matched[2]
                intent_feature["matched_helper_call_end_offset"] = matched[3]
                intent_feature["helper_call_line"] = matched[0]
                intent_feature["helper_call_start_offset"] = matched[2]
                intent_feature["helper_call_end_offset"] = matched[3]
                if not int(intent_feature.get("source_start_offset") or 0):
                    intent_feature["source_start_offset"] = matched[2]
                if not int(intent_feature.get("source_end_offset") or 0):
                    intent_feature["source_end_offset"] = matched[3]
                body_phase = agg.helper_body_phase_by_seed.get(matched, "")
                if body_phase:
                    intent_feature["helper_body_phase_hint_ast"] = body_phase
        intent_cand = build_intent_candidate(intent_feature)
        if intent_cand:
            agg.rq1_intent_candidates.append(intent_cand)

        if ft == "input":
            inp = resolve_input_pattern(
                name,
                raw,
                f,
                is_parameterized_test=agg.is_parameterized,
            )
            if inp.get("rq2_unit") == "load_site":
                return
            if inp.get("exclude_from_rq2_consumer_events"):
                return
            cat = inp["input_source_class"]
            inf_cat = inp["input_source_inferred"]
            ast_src = (f.get("input_source_ast") or "").strip()
            mismatch = "match"
            if ast_src:
                mismatch = input_ast_audit_mismatch_type(
                    ast_src,
                    inf_cat,
                    str(f.get("input_source_confidence_ast") or ""),
                )
                self.rq2_ast_input_audit_sink.write({
                    **self._base_event_fields(agg, repo, tid),
                    "line": line,
                    "name": name,
                    "raw_code": raw[:500] if raw else "",
                    "input_source_ast": ast_src,
                    "input_source_inferred": inf_cat,
                    "mismatch_type": mismatch,
                    "input_plausibility": inp.get("input_plausibility", ""),
                    "input_plausibility_paper_label": inp.get("input_plausibility_paper_label", ""),
                    "input_plausibility_codebook_path": inp.get("input_plausibility_codebook_path", ""),
                    "value_visibility_ast": f.get("value_visibility_ast") or "",
                    "input_target_role_ast": f.get("input_target_role_ast") or "",
                    "input_target_context_ast": f.get("input_target_context_ast") or "",
                    "input_value_expression_kind_ast": f.get("input_value_expression_kind_ast") or "",
                    "input_endpoint_construction_ast": f.get("input_endpoint_construction_ast") or "",
                })
            raw_value = f.get("value_summary", "") or f.get("input_value_redacted", "")
            if inp.get("input_source_class") == "file_upload_input":
                value_summary = format_upload_display_value(raw_value)
            else:
                value_summary = format_value_for_display(raw_value)
            if should_enqueue_review(inp, f, ast_mismatch=mismatch):
                self.rq2_review_rows.append(
                    build_review_row(
                        self._base_event_fields(agg, repo, tid),
                        {**inp, "value_summary": value_summary},
                        name=name,
                        raw_code=raw,
                        line=line,
                        feature=f,
                        ast_mismatch=mismatch,
                    )
                )
            rq2_row = {
                **self._base_event_fields(agg, repo, tid),
                **inp,
                "category": cat,
                "input_source": f.get("input_source", "") or ast_src,
                "value_summary": value_summary,
                "input_target_role_ast": str(f.get("input_target_role_ast") or ""),
                "input_target_role_basis_ast": str(f.get("input_target_role_basis_ast") or ""),
                "input_target_context_ast": str(f.get("input_target_context_ast") or ""),
                "input_target_context_normalized_ast": str(f.get("input_target_context_normalized_ast") or ""),
                "input_target_context_basis_ast": str(f.get("input_target_context_basis_ast") or ""),
                "input_value_expression_kind_ast": str(f.get("input_value_expression_kind_ast") or ""),
                "input_endpoint_construction_ast": str(f.get("input_endpoint_construction_ast") or ""),
                "input_endpoint_construction_basis_ast": str(f.get("input_endpoint_construction_basis_ast") or ""),
                "name": name,
                "raw_code": raw[:500] if raw else "",
                "helper_depth": depth,
                "attached_from_hook": attached_hook,
                "line": line,
            }
            def after_rq2_write(corrected_row: Dict[str, Any]) -> None:
                agg.rq2_categories[cat] += 1
                if not corrected_row.get("input_plausibility_paper_label"):
                    corrected_row["input_plausibility_paper_label"] = map_input_plausibility_paper_label(
                        str(corrected_row.get("input_plausibility") or "")
                    )
                agg.rq2_plausibility_counts[corrected_row.get("input_plausibility", "")] += 1
                agg.rq2_count += 1

            self._write_or_buffer_semantic_event("rq2", rq2_row, self.rq2_sink, after_rq2_write)

        if ft == "ui_action":
            self._track_rq3_ast_provenance(f, ft)
            cat = ui_action_category_from_feature(f, name, raw)
            loc = infer_locator_strategy(name, raw, cat)
            if loc:
                agg.locator_strategies[loc] += 1

            loc_pat = resolve_locator_pattern(
                name, raw, agg.framework, sk, depth, ft, cat, f
            )
            ast_s = (f.get("locator_strategy_ast") or "").strip()
            inf_s = loc_pat.get("locator_strategy_inferred", "")
            comp_ast = str(f.get("locator_composition_ast") or "")
            comp_inf = loc_pat.get("locator_composition_inferred", "")
            sel_ast = str(f.get("selector_literal_kind_ast") or "")
            sel_inf = loc_pat.get("selector_literal_kind_inferred", "")
            ast_conf = str(f.get("ast_confidence") or "")
            if ast_s:
                mismatch_type = locator_ast_audit_mismatch_type(
                    ast_s, inf_s, comp_ast, comp_inf, sel_ast, sel_inf, ast_conf
                )
                self.rq3_ast_locator_audit_sink.write({
                    **self._base_event_fields(agg, repo, tid),
                    "line": line,
                    "raw_code": raw[:400] if raw else "",
                    "locator_strategy_ast": ast_s,
                    "locator_strategy_inferred": inf_s,
                    "locator_composition_ast": comp_ast,
                    "locator_composition_inferred": comp_inf,
                    "selector_literal_kind_ast": sel_ast,
                    "selector_literal_kind_inferred": sel_inf,
                    "selector_channel_ast": str(f.get("selector_channel_ast") or ""),
                    "selector_value_origin_ast": str(f.get("selector_value_origin_ast") or ""),
                    "ast_confidence": ast_conf,
                    "mismatch_type": mismatch_type,
                })
                if mismatch_type != "match":
                    agg.ast_locator_audit_nonmatch_rows += 1
                    tags = set(mismatch_type.split(";"))
                    if tags & {"strategy", "composition", "selector_literal_kind"}:
                        agg.ast_regex_locator_mismatches += 1
                    if "low_confidence" in tags:
                        agg.ast_locator_low_confidence_rows += 1
            if loc_pat.get("locator_present"):
                agg.locator_event_count += 1
                agg.locator_bearing_ui_action_count += 1
                agg.locator_strategy_norm[loc_pat["locator_strategy"]] += 1
                agg.locator_composition_counts[loc_pat["locator_composition"]] += 1
                agg.robustness_signal_counts[loc_pat["robustness_signal"]] += 1
            if (
                loc_pat.get("locator_composition") == "page_object_mediated"
                or "page_object" in sk.lower()
            ):
                agg.page_object_ui_action_count += 1
                agg.page_object_ui_call_count += 1

            agg.rq3_locator_ui_action_rows += 1
            if loc_pat.get("locator_present"):
                selector_channel_ast = str(f.get("selector_channel_ast") or loc_pat.get("selector_channel") or "")
                selector_value_origin_ast = str(
                    f.get("selector_value_origin_ast") or loc_pat.get("selector_value_origin") or ""
                )
                selector_channel_basis = (
                    "ast_selector_channel"
                    if f.get("selector_channel_ast") or f.get("selector_value_origin_ast")
                    else str(
                        loc_pat.get("selector_channel_basis")
                        or loc_pat.get("locator_evidence_basis")
                        or loc_pat.get("evidence_basis")
                        or ""
                    )
                )
                self.rq3_locator_sink.write({
                    **self._base_event_fields(agg, repo, tid),
                    "source_kind": sk,
                    "line": line,
                    "name": name,
                    "raw_code": raw[:500] if raw else "",
                    "ui_action_category": cat,
                    **loc_pat,
                    "selector_channel_ast": selector_channel_ast,
                    "selector_value_origin_ast": selector_value_origin_ast,
                    "selector_channel_basis": selector_channel_basis,
                    "helper_depth": depth,
                    "attached_from_hook": attached_hook,
                })

            retry_caps = classify_auto_retry_capabilities(name, raw, agg.framework)
            if retry_caps["auto_wait_capable"]:
                agg.auto_wait_capable_action_count += 1
            if retry_caps["retryable_query"]:
                agg.retryable_query_count += 1

            seq_index = agg.ui_action_sequence_ingest_index
            nav_target = ""
            nav_target_basis = ""
            if cat == "navigation":
                nav_target = str(f.get("navigation_target_ast") or "").strip()
                if nav_target:
                    nav_target_basis = "string_literal_arg_ast"
                else:
                    nav_target, nav_target_basis = resolve_navigation_target_fields(raw, name)

            cf_enclosure = str(f.get("control_flow_enclosure") or "")
            action_sig_json = str(f.get("action_signature_json") or "")
            action_sig = normalize_action_signature(cat, name)
            event_file = str(f.get("target_file") or f.get("file_path") or "")

            self.rq4_sink.write({
                **self._base_event_fields(agg, repo, tid),
                "category": cat,
                "name": name,
                "source_file": event_file,
                "file_path": event_file,
                "source_kind": sk,
                "helper_depth": depth,
                "attached_from_hook": attached_hook,
                "hook_instance_key": str(f.get("hook_instance_key") or ""),
                "line": line,
                "raw_code": raw[:500] if raw else "",
                "source_start_offset": int(f.get("source_start_offset") or 0),
                "source_end_offset": int(f.get("source_end_offset") or 0),
                "feature_type": str(f.get("feature_type") or "ui_action"),
                "action_signature": action_sig,
                "action_signature_v2": action_sig_json,
                "ui_action_category": cat,
                "terminal_action_ast": str(f.get("terminal_action_ast") or ""),
                "callee_chain_json": str(f.get("callee_chain_json") or ""),
                "locator_strategy_ast": str(f.get("locator_strategy_ast") or ""),
                "input_channel_ast": str(f.get("input_channel_ast") or ""),
                "sequence_index": seq_index,
                "navigation_target": nav_target,
                "navigation_target_evidence_basis": nav_target_basis,
                "control_flow_enclosure": cf_enclosure,
                "control_flow_loop_depth": int(f.get("control_flow_loop_depth") or 0),
                "control_flow_branch_depth": int(f.get("control_flow_branch_depth") or 0),
                "control_flow_branch_kind": str(f.get("control_flow_branch_kind") or ""),
                "control_flow_branch_arm": str(f.get("control_flow_branch_arm") or ""),
                "control_flow_source": str(f.get("control_flow_source") or ""),
                "enclosing_control_flow_snippet": str(f.get("enclosing_control_flow_snippet") or "")[:1500],
                "control_flow_parent_kind": str(f.get("control_flow_parent_kind") or ""),
                "control_flow_parent_line": str(f.get("control_flow_parent_line") or ""),
                "control_flow_parent_start_offset": str(f.get("control_flow_parent_start_offset") or ""),
                "control_flow_parent_end_offset": str(f.get("control_flow_parent_end_offset") or ""),
                "control_flow_callback_method": str(f.get("control_flow_callback_method") or ""),
                "control_flow_callback_receiver": str(f.get("control_flow_callback_receiver") or "")[:500],
                "control_flow_ancestor_chain": str(f.get("control_flow_ancestor_chain") or ""),
                "action_snippet": str(f.get("action_snippet") or raw or "")[:1500],
                "enclosing_function_or_callback_snippet": str(
                    f.get("enclosing_function_or_callback_snippet") or ""
                )[:1500],
                "test_body_or_helper_context_snippet": str(
                    f.get("test_body_or_helper_context_snippet") or ""
                )[:1500],
                "snippet_truncated": bool_text(
                    f.get("snippet_truncated") or f.get("enclosing_control_flow_snippet_truncated")
                ),
                "action_signature_json": action_sig_json,
            })
            agg.rq4_categories[cat] += 1
            agg.rq4_count += 1
            ui_bucket = ui_action_bucket(sk, attached_hook, depth)
            seq_event: Dict[str, Any] = {
                "line": line,
                "category": cat,
                "name": name,
                "_ingest_index": seq_index,
                "action_signature_json": action_sig_json,
            }
            agg.ui_action_control_flow_events.append({
                "category": cat,
                "control_flow_enclosure": cf_enclosure or "none",
                "control_flow_loop_depth": int(f.get("control_flow_loop_depth") or 0),
                "control_flow_branch_depth": int(f.get("control_flow_branch_depth") or 0),
                "control_flow_branch_kind": str(f.get("control_flow_branch_kind") or ""),
                "control_flow_branch_arm": str(f.get("control_flow_branch_arm") or ""),
                "helper_depth": depth,
            })
            if ui_bucket == "test_body":
                agg.test_body_ui_action_control_flow_events.append(
                    agg.ui_action_control_flow_events[-1]
                )
            agg.ui_action_sequence_ingest_index += 1
            if cat == "navigation":
                seq_event["raw_code"] = raw[:300] if raw else ""
                seq_event["navigation_target"] = nav_target
                seq_event["navigation_target_evidence_basis"] = nav_target_basis
            agg.ui_action_sequence_events.append(seq_event)
            if ui_bucket == "test_body":
                agg.test_body_ui_action_sequence_events.append(seq_event)
            agg.workflow_layer_counts[ui_bucket] += 1
            if ui_bucket == "test_body":
                agg.test_body_ui_action_count += 1
                if line:
                    agg.test_body_ui_action_lines.append(line)
                if cat != "navigation" and line > 0:
                    if (
                        agg.first_non_navigation_ui_line is None
                        or line < agg.first_non_navigation_ui_line
                    ):
                        agg.first_non_navigation_ui_line = line
            elif ui_bucket == "hook":
                agg.hook_ui_action_count += 1
            elif ui_bucket == "helper":
                agg.helper_ui_action_count += 1
            elif ui_bucket == "cypress_command":
                agg.cypress_command_ui_action_count += 1
            if cat == "navigation":
                agg.navigation_count += 1

            wf = resolve_workflow_pattern(
                name,
                raw,
                agg.framework,
                sk,
                depth,
                ft,
                str(f.get("target_file") or ""),
                True,
                feature=f,
                attached_hook=attached_hook,
            )
            self._apply_page_object_workflow_signals(agg, wf, count_call=False)
            if depth > 0 or sk in (
                "imported_helper",
                "helper_function",
                "page_object",
                "cypress_command",
            ):
                self._write_workflow_event(agg, repo, tid, f, wf, line, sk, depth, attached_hook)

        if ft == "assertion":
            self._track_rq3_ast_provenance(f, ft)
            cat = classify_assertion(name, raw)
            verification_intent_info = classify_verification_intent_detail(cat, name, raw, f)
            verification_intent = verification_intent_info["verification_intent"]
            source_bucket = assertion_source_bucket(sk, depth, attached_hook)
            exec_scope = assertion_execution_scope(sk, attached_hook, depth)
            provenance = assertion_provenance(sk, depth, attached_hook)
            chain_raw = str(f.get("assertion_chain_raw_code") or "")
            try:
                chain_raw_length = int(f.get("assertion_chain_raw_code_length") or len(chain_raw))
            except (TypeError, ValueError):
                chain_raw_length = len(chain_raw)
            trunc_value = str(f.get("assertion_chain_raw_code_truncated") or "").strip().lower()
            chain_truncated = chain_raw_length > 1500 or trunc_value in ("1", "true", "yes")
            rq5_row = {
                **self._base_event_fields(agg, repo, tid),
                "category": cat,
                "name": name,
                "source_kind": sk,
                "assertion_source": source_bucket,
                "helper_depth": depth,
                "attached_from_hook": attached_hook,
                "line": line,
                "raw_code": raw[:500] if raw else "",
                "assertion_chain_raw_code": chain_raw[:1500],
                "assertion_chain_raw_code_length": chain_raw_length,
                "assertion_chain_raw_code_truncated": 1 if chain_truncated else 0,
                "assertion_execution_scope": exec_scope,
                "assertion_provenance": provenance,
                "verification_intent": verification_intent,
                "verification_intent_evidence_basis": verification_intent_info.get(
                    "verification_intent_evidence_basis", ""
                ),
                "verification_intent_confidence": verification_intent_info.get(
                    "verification_intent_confidence", ""
                ),
                "verification_intent_matched_signal": verification_intent_info.get(
                    "verification_intent_matched_signal", ""
                ),
                "verification_intent_codebook_path": verification_intent_info.get(
                    "verification_intent_codebook_path", ""
                ),
                "assertion_chain_root_id": str(f.get("assertion_chain_root_id") or ""),
                "assertion_chain_index": int(f.get("assertion_chain_index") or 0),
                "assertion_chain_length": int(f.get("assertion_chain_length") or 0),
                "chain_matcher_sequence_json": str(f.get("chain_matcher_sequence_json") or ""),
                "non_assertion_chain_methods_json": str(f.get("non_assertion_chain_methods_json") or ""),
                "assertion_matcher": str(f.get("assertion_matcher") or ""),
                "assertion_semantic_matcher_ast": str(f.get("assertion_semantic_matcher_ast") or ""),
                "assertion_semantic_matcher_basis_ast": str(
                    f.get("assertion_semantic_matcher_basis_ast") or ""
                ),
                "assertion_subject_kind": str(f.get("assertion_subject_kind") or ""),
                "assertion_subject_basis_ast": str(f.get("assertion_subject_basis_ast") or ""),
                "assertion_subject_root_ast": str(f.get("assertion_subject_root_ast") or ""),
                "assertion_subject_path_json": str(f.get("assertion_subject_path_json") or ""),
                "assertion_subject_text_ast": str(f.get("assertion_subject_text_ast") or ""),
                "assertion_subject_semantic_role_ast": str(f.get("assertion_subject_semantic_role_ast") or ""),
                "assertion_subject_semantic_role_basis_ast": str(
                    f.get("assertion_subject_semantic_role_basis_ast") or ""
                ),
                "assertion_callback_intent_hint_ast": str(
                    f.get("assertion_callback_intent_hint_ast") or ""
                ),
                "assertion_callback_intent_basis_ast": str(
                    f.get("assertion_callback_intent_basis_ast") or ""
                ),
                "assertion_callback_intent_hints_json": str(
                    f.get("assertion_callback_intent_hints_json") or ""
                ),
                "assertion_callback_nested_assertion_count": int(
                    f.get("assertion_callback_nested_assertion_count") or 0
                ),
                "assertion_callback_nested_matchers_json": str(
                    f.get("assertion_callback_nested_matchers_json") or ""
                ),
                "assertion_callback_subject_properties_json": str(
                    f.get("assertion_callback_subject_properties_json") or ""
                ),
                "assertion_callback_literal_args_json": str(
                    f.get("assertion_callback_literal_args_json") or ""
                ),
                "assertion_framework_context": str(f.get("assertion_framework_context") or ""),
                "assertion_library_syntax": str(
                    f.get("assertion_library_syntax") or f.get("assertion_framework") or ""
                ),
                "assertion_framework": str(
                    f.get("assertion_library_syntax") or f.get("assertion_framework") or ""
                ),
                "is_soft_assertion": 1 if f.get("is_soft_assertion") else 0,
                "is_negated_assertion": 1 if f.get("is_negated_assertion") else 0,
                "promise_modifier": str(f.get("promise_modifier") or ""),
                "chai_modifier_deep": 1 if f.get("chai_modifier_deep") else 0,
                "assertion_modifiers_json": str(f.get("assertion_modifiers_json") or ""),
                "is_grouped_assertion": 1 if f.get("is_grouped_assertion") else 0,
                "assertion_group_kind": str(f.get("assertion_group_kind") or ""),
            }
            def after_rq5_write(corrected_row: Dict[str, Any]) -> None:
                corrected_intent = str(corrected_row.get("verification_intent") or verification_intent)
                agg.rq5_assertion_chain_events.append({
                    "assertion_chain_root_id": str(f.get("assertion_chain_root_id") or ""),
                    "assertion_chain_length": int(f.get("assertion_chain_length") or 0),
                    "assertion_matcher": str(f.get("assertion_matcher") or ""),
                    "is_soft_assertion": f.get("is_soft_assertion"),
                    "is_grouped_assertion": f.get("is_grouped_assertion"),
                })
                agg.rq5_categories[cat] += 1
                agg.rq5_verification_intent_counts[corrected_intent] += 1
                agg.rq5_count += 1
                if source_bucket == "hook":
                    agg.hook_assertion_count += 1
                elif source_bucket == "helper":
                    agg.helper_assertion_count += 1
                else:
                    agg.direct_assertion_count += 1
                if is_test_body_source(sk, attached_hook, depth):
                    agg.test_body_assertion_count += 1
                    if line:
                        agg.test_body_assertion_lines.append(line)

            self._write_or_buffer_semantic_event("rq5c", rq5_row, self.rq5_sink, after_rq5_write)

            if is_assertion_retry_sync_feature(name, raw, f):
                sync_info = resolve_wait_pattern(name, raw, agg.framework, "assertion", f)
                placement = sync_placement(sk, attached_hook, depth)
                self.rq3_sync_sink.write({
                    **self._base_event_fields(agg, repo, tid),
                    "source_kind": sk,
                    "line": line,
                    "name": name,
                    "raw_code": raw[:500] if raw else "",
                    "sync_placement": placement,
                    **sync_info,
                    "sync_call_kind_ast": str(
                        f.get("sync_call_kind_ast")
                        or (
                            "predicate"
                            if sync_info.get("sync_pattern") == "predicate_or_custom_condition"
                            else "assertion"
                        )
                    ),
                    "sync_arg_kind_ast": str(
                        f.get("sync_arg_kind_ast")
                        or f.get("wait_arg_kind_ast")
                        or sync_info.get("sync_arg_kind")
                        or ""
                    ),
                    "helper_depth": depth,
                    "attached_from_hook": attached_hook,
                })
                sp = sync_info["sync_pattern"]
                agg.sync_pattern_counts[sp] += 1
                if sync_info["is_assertion_retry"]:
                    agg.assertion_retry_sync_count += 1

    def _write_workflow_event(
        self,
        agg: TestAgg,
        repo: str,
        tid: str,
        f: Dict[str, Any],
        wf: Dict[str, Any],
        line: int,
        sk: str,
        depth: int,
        attached_hook: bool,
    ) -> None:
        agg.workflow_event_count += 1
        agg.abstraction_kind_counts[wf["abstraction_kind"]] += 1
        resolved = f.get("resolved")
        self.rq3_workflow_sink.write({
            **self._base_event_fields(agg, repo, tid),
            "source_kind": sk,
            "line": line,
            "name": str(f.get("name") or ""),
            "raw_code": str(f.get("raw_code") or "")[:500],
            **wf,
            "helper_depth": depth,
            "helper_target_file": str(f.get("target_file") or ""),
            "resolved": resolved if resolved is not None else "",
            "attached_from_hook": attached_hook,
            "expanded_ui_action_count": "",
        })

    def ingest_helper_edge(self, e: Dict[str, Any]) -> None:
        edge_key = helper_edge_dedupe_key(e)
        if edge_key in self.seen_helper_edges:
            return
        self.seen_helper_edges.add(edge_key)

        repo = str(e.get("repo") or "").strip()
        tid = str(e.get("test_id") or "").strip()
        agg = self._agg(repo, tid)
        if agg:
            agg.helper_edge_count += 1
            if e.get("resolved") is True and int(e.get("depth") or 0) == 1:
                call_line = int(e.get("call_line") or 0)
                to_name = str(e.get("to") or "").strip()
                if call_line and to_name:
                    seed = (
                        call_line,
                        to_name,
                        int(e.get("call_start_offset") or 0),
                        int(e.get("call_end_offset") or 0),
                    )
                    agg.resolved_helper_seeds.add(seed)
                    body_phase = str(e.get("helper_body_phase_hint_ast") or "").strip()
                    if body_phase:
                        agg.helper_body_phase_by_seed[seed] = body_phase
            if e.get("resolved") is False:
                agg.unresolved_helper_call_count += 1
                wf = resolve_workflow_pattern(
                    str(e.get("to") or ""),
                    "",
                    agg.framework,
                    "",
                    int(e.get("depth") or 0),
                    "helper_call",
                    str(e.get("target_file") or ""),
                    False,
                )
                self._apply_page_object_workflow_signals(agg, wf, count_call=True)
                self._write_workflow_event(
                    agg,
                    repo,
                    tid,
                    {
                        "name": e.get("to", ""),
                        "raw_code": "",
                        "target_file": e.get("target_file", ""),
                        "resolved": False,
                    },
                    wf,
                    0,
                    "",
                    int(e.get("depth") or 0),
                    False,
                )

    def close_event_sinks(self) -> None:
        self._flush_semantic_event_buffers()
        for sink in self.event_sinks:
            sink.ensure_created()
            sink.close()

    def finalize(self) -> Dict[str, int]:
        """Build per-test summary CSVs; event CSVs already written."""
        import json

        from stream_io import write_csv

        rq1_by_test: List[Dict[str, Any]] = []
        rq2_by_test: List[Dict[str, Any]] = []
        rq3: List[Dict[str, Any]] = []
        rq3_patterns: List[Dict[str, Any]] = []
        rq4_complexity: List[Dict[str, Any]] = []
        rq5_complexity: List[Dict[str, Any]] = []
        rq1_intent_by_test: List[Dict[str, Any]] = []
        rq1_intent_rejected_nav = 0
        rq1_intent_dedupe_dropped = 0
        rq1_intent_lifecycle_window_rejected = 0

        for agg in self.by_key.values():
            has_test_body_ui = agg.test_body_ui_action_count > 0
            has_hook_ui = agg.hook_ui_action_count > 0
            has_helper_ui = (
                agg.helper_ui_action_count > 0 or agg.cypress_command_ui_action_count > 0
            )

            rq1_by_test.append({
                "repo": agg.repo,
                "test_id": agg.test_id,
                "framework": agg.framework,
                "phase1_confidence": agg.phase1_confidence,
                "environment_control_count": agg.rq1_count,
                "category_counts": json.dumps(dict(agg.rq1_categories)),
            })

            rq2_by_test.append({
                "repo": agg.repo,
                "test_id": agg.test_id,
                "framework": agg.framework,
                "phase1_confidence": agg.phase1_confidence,
                "is_parameterized": agg.is_parameterized,
                "parameterization_type": agg.parameterization_type,
                "parameter_row_count": agg.parameter_row_count,
                "input_feature_count": agg.rq2_count,
                "input_category_counts": json.dumps(dict(agg.rq2_categories)),
                "input_plausibility_counts": json.dumps(dict(agg.rq2_plausibility_counts)),
            })

            structure = "flat_test" if agg.describe_depth <= 1 else "nested_describe"
            if agg.is_parameterized and structure == "flat_test":
                structure = "parameterized"

            rq3.append({
                "repo": agg.repo,
                "test_id": agg.test_id,
                "framework": agg.framework,
                "phase1_confidence": agg.phase1_confidence,
                "structure_category": structure,
                "describe_depth": agg.describe_depth,
                "uses_helper": agg.uses_helper,
                "uses_imported_helper": agg.uses_imported_helper,
                "uses_page_object": agg.uses_page_object,
                "uses_cypress_command": agg.uses_cypress_command,
                "uses_fixture": agg.uses_fixture,
                "uses_parameterization": agg.is_parameterized,
                "helper_call_count": agg.helper_call_count,
                "custom_command_call_count": agg.custom_command_call_count,
                "cypress_command_expanded_feature_count": agg.cypress_command_expanded_feature_count,
                "wait_synchronization_count": agg.wait_sync_count,
                "helper_edge_count": agg.helper_edge_count,
                "locator_strategy_counts": json.dumps(dict(agg.locator_strategies)),
                "has_test_body_ui_actions": has_test_body_ui,
                "has_hook_ui_actions": has_hook_ui,
                "has_helper_expanded_ui_actions": has_helper_ui,
            })

            rq3_patterns.append(build_rq3_patterns_by_test_row(agg))

            ui_lines = sorted(agg.test_body_ui_action_lines)
            rq4_row = {
                "repo": agg.repo,
                "test_id": agg.test_id,
                "framework": agg.framework,
                "phase1_confidence": agg.phase1_confidence,
                "ui_action_count": agg.rq4_count,
                "test_body_ui_action_count": agg.test_body_ui_action_count,
                "hook_ui_action_count": agg.hook_ui_action_count,
                "helper_ui_action_count": agg.helper_ui_action_count,
                "cypress_command_ui_action_count": agg.cypress_command_ui_action_count,
                "wait_synchronization_count": agg.wait_sync_count,
                "navigation_count": agg.navigation_count,
                "action_sequence_length": agg.rq4_count,
                "action_type_distribution": json.dumps(dict(agg.rq4_categories)),
                "first_test_body_ui_action_line": ui_lines[0] if ui_lines else "",
                "last_test_body_ui_action_line": ui_lines[-1] if ui_lines else "",
            }
            rq4_row.update(
                compute_dual_scope_sequence_metrics(
                    agg.ui_action_sequence_events,
                    agg.test_body_ui_action_sequence_events,
                )
            )
            rq4_row.update(
                compute_dual_scope_control_flow_metrics(
                    agg.ui_action_control_flow_events,
                    agg.test_body_ui_action_control_flow_events,
                )
            )
            if rq4_row.get("sequence_event_count") != rq4_row.get("action_sequence_length"):
                rq4_row["sequence_event_count_mismatch"] = 1
            else:
                rq4_row["sequence_event_count_mismatch"] = 0
            if self.static_metrics_by_key is not None:
                rq4_row = merge_static_fields(
                    rq4_row,
                    self.static_metrics_by_key.get(test_key(agg.repo, agg.test_id)),
                )
            rq4_complexity.append(rq4_row)

            assert_lines = sorted(agg.test_body_assertion_lines)
            placement = assertion_placement(assert_lines, ui_lines)
            sm_row = (
                self.static_metrics_by_key.get(test_key(agg.repo, agg.test_id))
                if self.static_metrics_by_key is not None
                else None
            )
            rq5_row = {
                "repo": agg.repo,
                "test_id": agg.test_id,
                "framework": agg.framework,
                "phase1_confidence": agg.phase1_confidence,
                "assertion_count": agg.rq5_count,
                "direct_assertion_count": agg.direct_assertion_count,
                "hook_assertion_count": agg.hook_assertion_count,
                "helper_assertion_count": agg.helper_assertion_count,
                "assertion_category_counts": json.dumps(dict(agg.rq5_categories)),
                "assertion_placement_test_body": placement,
                "expanded_assertion_source_pattern": expanded_assertion_source_pattern(agg),
                "first_test_body_assertion_line": assert_lines[0] if assert_lines else "",
                "last_test_body_assertion_line": assert_lines[-1] if assert_lines else "",
            }
            if sm_row is not None:
                rq5_row = merge_static_fields(rq5_row, sm_row)
            rq5_row.update(
                build_assertion_density_fields(
                    assertion_count=agg.rq5_count,
                    test_body_assertion_count=agg.test_body_assertion_count,
                    direct_assertion_count=agg.direct_assertion_count,
                    hook_assertion_count=agg.hook_assertion_count,
                    helper_assertion_count=agg.helper_assertion_count,
                    ui_action_count=agg.rq4_count,
                    test_body_ui_action_count=agg.test_body_ui_action_count,
                    static_row=sm_row,
                )
            )
            rq5_row["test_body_assertion_count"] = agg.test_body_assertion_count
            rq5_row["verification_intent_counts"] = json.dumps(
                dict(agg.rq5_verification_intent_counts)
            )
            rq5_row["unspecified_verification_intent_count"] = int(
                agg.rq5_verification_intent_counts.get("unspecified", 0)
            )
            rq5_row.update(build_assertion_chain_fields(agg.rq5_assertion_chain_events))
            rq5_complexity.append(rq5_row)

            intent_rows, intent_resolve_stats = resolve_test_intent_units(
                agg.rq1_intent_candidates,
                first_non_navigation_ui_line=agg.first_non_navigation_ui_line or 0,
            )
            rq1_intent_rejected_nav += intent_resolve_stats.get("navigation_bootstrap_rejected", 0)
            rq1_intent_dedupe_dropped += intent_resolve_stats.get("intent_rows_deduplicated", 0)
            rq1_intent_lifecycle_window_rejected += intent_resolve_stats.get("lifecycle_window_rejected", 0)
            for row in intent_rows:
                self._rq1_intent_event_rows.append(row)
                if int(row.get("needs_review") or 0):
                    self.rq1_intent_review_rows.append(build_intent_review_row(row))
            rq1_intent_by_test.append({
                "repo": agg.repo,
                "test_id": agg.test_id,
                "framework": agg.framework,
                "phase1_confidence": agg.phase1_confidence,
                **summarize_rq1_intent_by_test(intent_rows),
            })

        out = self.output_dir
        write_csv(out / "rq1_environment_control_by_test.csv", rq1_by_test)
        write_csv(
            out / "rq1_setup_teardown_intent_events.csv",
            self._rq1_intent_event_rows,
            self.RQ1_INTENT_EVENT_FIELDS,
        )
        write_csv(out / "rq1_setup_teardown_intent_by_test.csv", rq1_intent_by_test)
        write_csv(
            out / "rq1_setup_teardown_intent_review_queue.csv",
            self.rq1_intent_review_rows,
            RQ1_INTENT_REVIEW_QUEUE_FIELDS,
        )
        write_csv(out / "rq2_input_by_test.csv", rq2_by_test)
        write_csv(
            out / "rq2_input_semantics_review_queue.csv",
            self.rq2_review_rows,
            RQ2_REVIEW_QUEUE_FIELDS,
        )
        write_csv(out / "rq3_structure_by_test.csv", rq3)
        rq3_patterns = self._apply_semantic_corrections("rq3_workflow", rq3_patterns)
        write_csv(out / "rq3_patterns_by_test.csv", rq3_patterns)
        write_csv(out / "rq3_patterns_by_repo.csv", build_rq3_patterns_by_repo(rq3_patterns))
        from rq3_weighted_summaries import write_weighted_summaries

        write_weighted_summaries(out, self)
        write_csv(out / "rq4_interaction_complexity_by_test.csv", rq4_complexity)
        write_csv(out / "rq5_assertion_complexity_by_test.csv", rq5_complexity)

        static_join_counts: Dict[str, Any] = {}
        if self.static_metrics_by_key is not None:
            static_rows = build_static_metrics_by_test_rows(
                self.test_cases, self.static_metrics_by_key
            )
            write_csv(out / "rq_static_metrics_by_test.csv", static_rows)
            static_join_counts = join_summary(
                self.test_cases,
                self.static_metrics_by_key,
                load_result=self.static_metrics_load,
            )

        # Legacy aliases (copy event files)
        import shutil

        legacy = [
            ("rq1_setup_fixtures_summary.csv", "rq1_environment_control_events.csv"),
            ("rq2_inputs_summary.csv", "rq2_input_events.csv"),
            ("rq3_structure_summary.csv", "rq3_structure_by_test.csv"),
            ("rq4_interactions_summary.csv", "rq4_interaction_events.csv"),
            ("rq5_assertions_summary.csv", "rq5_assertion_events.csv"),
        ]
        for dest, src in legacy:
            sp = out / src
            dp = out / dest
            if sp.exists():
                shutil.copy2(sp, dp)

        result = {
            "rq1_events": self.rq1_sink.count,
            "rq1_setup_teardown_intent_events": len(self._rq1_intent_event_rows),
            "rq1_setup_teardown_intent_review_queue_rows": len(self.rq1_intent_review_rows),
            "rq2_events": self.rq2_sink.count,
            "rq3_locator_events": self.rq3_locator_sink.count,
            "rq3_locator_ui_action_rows": sum(
                a.rq3_locator_ui_action_rows for a in self.by_key.values()
            ),
            "rq3_ast_regex_locator_mismatches": sum(
                a.ast_regex_locator_mismatches for a in self.by_key.values()
            ),
            "rq3_ast_locator_low_confidence_rows": sum(
                a.ast_locator_low_confidence_rows for a in self.by_key.values()
            ),
            "rq3_ast_locator_audit_nonmatch_rows": sum(
                a.ast_locator_audit_nonmatch_rows for a in self.by_key.values()
            ),
            "rq3_ast_locator_audit_rows": self.rq3_ast_locator_audit_sink.count,
            "rq3_sync_events": self.rq3_sync_sink.count,
            "rq3_workflow_events": self.rq3_workflow_sink.count,
            "rq4_events": self.rq4_sink.count,
            "rq5_events": self.rq5_sink.count,
            "tests": len(self.by_key),
            "rq3_ast_enabled": True,
        }
        result.update(self.rq3_ast_provenance)
        result.update(static_join_counts)
        result["milestone1_rq4_sequence"] = _summarize_rq4_sequence_metrics(rq4_complexity)
        result["milestone1_rq5_density"] = _summarize_rq5_density_metrics(rq5_complexity)
        result["unspecified_verification_intent_fraction"] = result["milestone1_rq5_density"].get(
            "unspecified_verification_intent_fraction", ""
        )
        result["milestone2_rq1_intent"] = summarize_rq1_intent_corpus(
            self._rq1_intent_event_rows,
            navigation_bootstrap_rejected=rq1_intent_rejected_nav,
            intent_rows_deduplicated=rq1_intent_dedupe_dropped,
            lifecycle_window_rejected=rq1_intent_lifecycle_window_rejected,
        )
        result["milestone3_rq4_control_flow"] = _summarize_rq4_control_flow_metrics(rq4_complexity)
        result["milestone3_rq5_assertion_chains"] = _summarize_rq5_assertion_chain_metrics(rq5_complexity)
        result["milestone3_action_signature_v2"] = _summarize_action_signature_v2(rq4_complexity)
        return result


def _summarize_rq4_control_flow_metrics(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    with_cf = [
        r for r in rows
        if int(r.get("ui_actions_with_control_flow_enclosure_non_none") or 0) > 0
    ]
    classified_with_cf = [
        r for r in rows
        if int(r.get("classified_user_action_ui_actions_with_control_flow_enclosure_non_none") or 0) > 0
    ]
    loop_tests = sum(int(r.get("loop_driven_action_count") or 0) > 0 for r in rows)
    branch_tests = sum(int(r.get("branch_driven_action_count") or 0) > 0 for r in rows)
    classified_loop_tests = sum(
        int(r.get("classified_user_action_loop_driven_action_count") or 0) > 0 for r in rows
    )
    classified_branch_tests = sum(
        int(r.get("classified_user_action_branch_driven_action_count") or 0) > 0 for r in rows
    )
    cond_fracs = sorted(
        float(r["conditionalized_action_fraction"])
        for r in rows
        if r.get("conditionalized_action_fraction") not in ("", None)
    )
    classified_cond_fracs = sorted(
        float(r["classified_user_action_conditionalized_action_fraction"])
        for r in rows
        if r.get("classified_user_action_conditionalized_action_fraction") not in ("", None)
    )
    return {
        "tests_with_control_flow_tagged_actions": len(with_cf),
        "tests_with_loop_driven_actions": loop_tests,
        "tests_with_branch_driven_actions": branch_tests,
        "median_conditionalized_action_fraction": (
            cond_fracs[len(cond_fracs) // 2] if cond_fracs else ""
        ),
        "total_loop_driven_actions": sum(int(r.get("loop_driven_action_count") or 0) for r in rows),
        "total_branch_driven_actions": sum(int(r.get("branch_driven_action_count") or 0) for r in rows),
        "tests_with_classified_user_action_control_flow_tagged_actions": len(classified_with_cf),
        "tests_with_classified_user_action_loop_driven_actions": classified_loop_tests,
        "tests_with_classified_user_action_branch_driven_actions": classified_branch_tests,
        "median_classified_user_action_conditionalized_action_fraction": (
            classified_cond_fracs[len(classified_cond_fracs) // 2] if classified_cond_fracs else ""
        ),
        "total_classified_user_action_loop_driven_actions": sum(
            int(r.get("classified_user_action_loop_driven_action_count") or 0) for r in rows
        ),
        "total_classified_user_action_branch_driven_actions": sum(
            int(r.get("classified_user_action_branch_driven_action_count") or 0) for r in rows
        ),
    }


def _summarize_rq5_assertion_chain_metrics(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    with_chain = [r for r in rows if int(r.get("assertions_with_chain_fields") or 0) > 0]
    missing = sum(int(r.get("assertions_missing_chain_metadata_count") or 0) for r in rows)
    tagged = sum(int(r.get("assertions_with_chain_fields") or 0) for r in rows)
    chain_fracs = [
        float(r["tagged_chained_assertion_fraction"])
        for r in rows
        if r.get("tagged_chained_assertion_fraction") not in ("", None)
        and float(r["tagged_chained_assertion_fraction"]) > 0
    ]
    return {
        "tests_with_assertion_chain_fields": len(with_chain),
        "total_assertions_with_chain_metadata": tagged,
        "total_assertions_missing_chain_metadata": missing,
        "ast_tagged_chain_metrics_note": (
            "Chained/standalone fractions are among assertions with chain metadata only."
        ),
        "total_chained_assertions": sum(int(r.get("chained_assertion_count") or 0) for r in rows),
        "total_soft_assertions": sum(int(r.get("soft_assertion_count") or 0) for r in rows),
        "max_chain_length_observed": max(
            (int(r.get("max_assertion_chain_length") or 0) for r in rows),
            default=0,
        ),
        "tests_with_chained_assertions": len(chain_fracs),
    }


def _summarize_action_signature_v2(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    v2_tests = [r for r in rows if r.get("sequence_signature_version") == "v2"]
    return {
        "tests_with_action_signature_v2": len(v2_tests),
        "tests_with_v2_signatures_fraction": (
            round(len(v2_tests) / len(rows), 6) if rows else ""
        ),
    }


def _summarize_rq4_sequence_metrics(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    with_ui = [r for r in rows if int(r.get("sequence_event_count") or 0) > 0]
    repeat_vals = [
        float(r["repeat_action_fraction"])
        for r in with_ui
        if r.get("repeat_action_fraction") not in ("", None)
    ]
    repeat_vals_sorted = sorted(repeat_vals)
    user_repeat_vals = [
        float(r["test_body_user_action_repeat_fraction"])
        for r in with_ui
        if r.get("test_body_user_action_repeat_fraction") not in ("", None)
    ]
    user_repeat_vals_sorted = sorted(user_repeat_vals)
    classified_repeat_vals = [
        float(r["classified_user_action_repeat_fraction"])
        for r in with_ui
        if r.get("classified_user_action_repeat_fraction") not in ("", None)
    ]
    classified_repeat_vals_sorted = sorted(classified_repeat_vals)
    test_body_classified_repeat_vals = [
        float(r["test_body_classified_user_action_repeat_fraction"])
        for r in with_ui
        if r.get("test_body_classified_user_action_repeat_fraction") not in ("", None)
    ]
    test_body_classified_repeat_vals_sorted = sorted(test_body_classified_repeat_vals)
    revisit_api = [int(r.get("repeated_navigation_api_count") or 0) for r in with_ui]
    revisit_target = [int(r.get("navigation_target_revisit_count") or 0) for r in with_ui]
    mismatches = sum(int(r.get("sequence_event_count_mismatch") or 0) for r in rows)

    def _percentile(vals: List[float], pct: int) -> Any:
        if not vals:
            return ""
        idx = max(0, min(len(vals) - 1, int(round((pct / 100) * (len(vals) - 1)))))
        return round(vals[idx], 6)

    return {
        "metric_interpretation": {
            "repeat_action_fraction": (
                "Repeated UI-test event signatures (includes locator_query)."
            ),
            "user_action_repeat_fraction": (
                "Repeated user-interaction events excluding locator_query but retaining "
                "synchronization and unknown-action events for backward compatibility."
            ),
            "classified_user_action_repeat_fraction": (
                "Repeated classified user-facing action events excluding locator_query, "
                "wait_synchronization, and unknown_action; preferred paper-facing metric."
            ),
            "primary_scope_for_paper": "test_body_* sequence columns",
            "secondary_scope": (
                "All-layer columns when sequence_all_layers_includes_non_test_body_events=1 "
                "(helper/hook ordering approximate)."
            ),
        },
        "tests_with_sequence_events": len(with_ui),
        "tests_with_repeat_action_fraction_gt_0": sum(1 for v in repeat_vals if v > 0),
        "tests_with_user_action_repeat_fraction_gt_0": sum(1 for v in user_repeat_vals if v > 0),
        "tests_with_classified_user_action_repeat_fraction_gt_0": sum(
            1 for v in classified_repeat_vals if v > 0
        ),
        "tests_with_repeated_navigation_api_gt_0": sum(1 for v in revisit_api if v > 0),
        "tests_with_navigation_target_revisit_gt_0": sum(1 for v in revisit_target if v > 0),
        "mean_repeat_action_fraction": (
            round(sum(repeat_vals) / len(repeat_vals), 6) if repeat_vals else ""
        ),
        "mean_test_body_user_action_repeat_fraction": (
            round(sum(user_repeat_vals) / len(user_repeat_vals), 6) if user_repeat_vals else ""
        ),
        "mean_classified_user_action_repeat_fraction": (
            round(sum(classified_repeat_vals) / len(classified_repeat_vals), 6)
            if classified_repeat_vals
            else ""
        ),
        "mean_test_body_classified_user_action_repeat_fraction": (
            round(sum(test_body_classified_repeat_vals) / len(test_body_classified_repeat_vals), 6)
            if test_body_classified_repeat_vals
            else ""
        ),
        "median_repeat_action_fraction": _percentile(repeat_vals_sorted, 50),
        "median_test_body_user_action_repeat_fraction": _percentile(user_repeat_vals_sorted, 50),
        "median_classified_user_action_repeat_fraction": _percentile(classified_repeat_vals_sorted, 50),
        "median_test_body_classified_user_action_repeat_fraction": _percentile(
            test_body_classified_repeat_vals_sorted,
            50,
        ),
        "p90_repeat_action_fraction": _percentile(repeat_vals_sorted, 90),
        "p90_test_body_user_action_repeat_fraction": _percentile(user_repeat_vals_sorted, 90),
        "p90_classified_user_action_repeat_fraction": _percentile(classified_repeat_vals_sorted, 90),
        "p90_test_body_classified_user_action_repeat_fraction": _percentile(
            test_body_classified_repeat_vals_sorted,
            90,
        ),
        "tests_where_action_sequence_length_ne_sequence_event_count": mismatches,
    }


def _summarize_rq5_density_metrics(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    no_assert = sum(int(r.get("tests_with_no_assertions") or 0) for r in rows)
    only_helper = sum(int(r.get("tests_with_only_helper_assertions") or 0) for r in rows)
    density_all = [
        float(r["assertion_density_all_actions"])
        for r in rows
        if r.get("assertion_density_all_actions") not in ("", None)
    ]
    density_body = [
        float(r["assertion_density_test_body"])
        for r in rows
        if r.get("assertion_density_test_body") not in ("", None)
    ]
    unspecified = sum(int(r.get("unspecified_verification_intent_count") or 0) for r in rows)
    total_assertions = sum(int(r.get("assertion_count") or 0) for r in rows)
    null_all = sum(
        1 for r in rows if r.get("assertion_density_all_actions") in ("", None)
    )
    null_body = sum(
        1 for r in rows if r.get("assertion_density_test_body") in ("", None)
    )
    gt_one = sum(
        1
        for r in rows
        if r.get("assertion_density_all_actions") not in ("", None)
        and float(r["assertion_density_all_actions"]) > 1
    )
    max_density = max(density_all) if density_all else ""

    return {
        "coverage_limitation": (
            "unspecified_verification_intent_fraction reflects upstream assertion "
            "classifier coverage, not mapping errors in Tier-1 taxonomy."
        ),
        "tests_with_no_assertions": no_assert,
        "tests_with_only_helper_assertions": only_helper,
        "tests_with_assertion_density_all_actions": len(density_all),
        "tests_with_assertion_density_test_body": len(density_body),
        "mean_assertion_density_all_actions": (
            round(sum(density_all) / len(density_all), 6) if density_all else ""
        ),
        "mean_assertion_density_test_body": (
            round(sum(density_body) / len(density_body), 6) if density_body else ""
        ),
        "assertions_with_unspecified_verification_intent": unspecified,
        "unspecified_verification_intent_fraction": (
            round(unspecified / total_assertions, 6) if total_assertions else ""
        ),
        "assertion_density_all_actions_null_fraction": (
            round(null_all / len(rows), 6) if rows else ""
        ),
        "assertion_density_test_body_null_fraction": (
            round(null_body / len(rows), 6) if rows else ""
        ),
        "density_gt_1_count": gt_one,
        "max_assertion_density_all_actions": max_density,
    }


def build_rq3_patterns_by_test_row(agg: TestAgg) -> Dict[str, Any]:
    import json

    ui_count = agg.rq4_count
    loc_events = agg.locator_event_count
    robust_pos = sum(
        c for sig, c in agg.robustness_signal_counts.items() if positive_resilience_signals(sig)
    )
    impl_coupled = sum(
        c for sig, c in agg.robustness_signal_counts.items() if implementation_coupled_signal(sig)
    )
    opaque = agg.robustness_signal_counts.get("opaque_or_unresolved_signal", 0)

    dominant_strategy = ""
    if agg.locator_strategy_norm:
        dominant_strategy = agg.locator_strategy_norm.most_common(1)[0][0]

    unresolved_frac = (
        agg.unresolved_helper_call_count / agg.helper_call_count
        if agg.helper_call_count
        else 0.0
    )

    archetype_detail = infer_workflow_archetype_detail(
        ui_action_count=ui_count,
        test_body_ui=agg.test_body_ui_action_count,
        hook_ui=agg.hook_ui_action_count,
        helper_ui=agg.helper_ui_action_count,
        po_ui=agg.page_object_ui_action_count,
        cypress_cmd_ui=agg.cypress_command_ui_action_count,
        page_object_signal=agg.page_object_signal_present or agg.uses_page_object,
        helper_call_count=agg.helper_call_count,
        unresolved_helper_calls=agg.unresolved_helper_call_count,
        expanded_ui_count=agg.helper_ui_action_count + agg.cypress_command_ui_action_count,
        bdd_step_definition_count=agg.bdd_step_definition_count,
        playwright_test_step_count=agg.playwright_test_step_count,
        page_object_call_count=agg.page_object_call_count,
    )
    archetype = archetype_detail["workflow_archetype"]
    workflow_scores = {
        "test_body_ui": agg.test_body_ui_action_count,
        "hook_ui": agg.hook_ui_action_count,
        "helper_ui": agg.helper_ui_action_count,
        "page_object_ui": agg.page_object_ui_action_count,
        "cypress_command_ui": agg.cypress_command_ui_action_count,
        "helper_calls": agg.helper_call_count,
        "page_object_calls": agg.page_object_call_count,
        "unresolved_helper_calls": agg.unresolved_helper_call_count,
        "playwright_test_steps": agg.playwright_test_step_count,
        "bdd_step_definitions": agg.bdd_step_definition_count,
    }
    positive_scores = {k: v for k, v in workflow_scores.items() if int(v or 0) > 0}
    dominant_source = ""
    if positive_scores:
        dominant_source = max(positive_scores.items(), key=lambda item: (int(item[1] or 0), item[0]))[0]
    top_evidence = [
        {"source": key, "count": int(value or 0)}
        for key, value in sorted(positive_scores.items(), key=lambda item: int(item[1] or 0), reverse=True)[:5]
    ]

    return {
        "repo": agg.repo,
        "test_id": agg.test_id,
        "framework": agg.framework,
        "phase1_confidence": agg.phase1_confidence,
        "locator_event_count": loc_events,
        "ui_action_count": ui_count,
        "locator_strategy_counts_json": json.dumps(dict(agg.locator_strategy_norm)),
        "locator_composition_counts_json": json.dumps(dict(agg.locator_composition_counts)),
        "robustness_signal_counts_json": json.dumps(dict(agg.robustness_signal_counts)),
        "dominant_locator_strategy": dominant_strategy,
        "robustness_signal_fraction_among_locator_events": (
            robust_pos / loc_events if loc_events else ""
        ),
        "robustness_signal_action_fraction_among_ui_actions": (
            robust_pos / ui_count if ui_count else ""
        ),
        "implementation_coupled_locator_fraction": (
            impl_coupled / loc_events if loc_events else ""
        ),
        "opaque_locator_fraction": opaque / loc_events if loc_events else "",
        "sync_event_count": sum(agg.sync_pattern_counts.values()),
        "sync_pattern_counts_json": json.dumps(dict(agg.sync_pattern_counts)),
        "fixed_delay_sync_count": agg.fixed_delay_sync_count,
        "condition_based_sync_count": agg.condition_based_sync_count,
        "network_sync_count": agg.network_sync_count,
        "assertion_retry_sync_count": agg.assertion_retry_sync_count,
        "auto_wait_capable_action_count": agg.auto_wait_capable_action_count,
        "retryable_query_count": agg.retryable_query_count,
        "workflow_event_count": agg.workflow_event_count,
        "workflow_layer_counts_json": json.dumps(dict(agg.workflow_layer_counts)),
        "abstraction_kind_counts_json": json.dumps(dict(agg.abstraction_kind_counts)),
        "workflow_archetype": archetype,
        "workflow_evidence_score_json": json.dumps(workflow_scores, sort_keys=True),
        "dominant_workflow_source": str(archetype_detail.get("dominant_workflow_source") or dominant_source),
        "workflow_dominant_source": str(archetype_detail.get("workflow_dominant_source") or dominant_source),
        "dominant_workflow_source_share": archetype_detail.get("dominant_workflow_source_share", ""),
        "workflow_dominant_source_share": archetype_detail.get("workflow_dominant_source_share", ""),
        "workflow_source_count_json": str(archetype_detail.get("workflow_source_count_json") or ""),
        "workflow_top_two_sources_json": str(archetype_detail.get("workflow_top_two_sources_json") or ""),
        "workflow_archetype_basis": str(archetype_detail.get("workflow_archetype_basis") or f"deterministic_score:{dominant_source or 'none'}"),
        "top_workflow_evidence_json": json.dumps(top_evidence),
        "unresolved_workflow_fraction": round(unresolved_frac, 4) if agg.helper_call_count else "",
        "page_object_signal_present": agg.page_object_signal_present or agg.uses_page_object,
        "page_object_expanded_ui_count": agg.page_object_ui_action_count,
        "page_object_ui_call_count": agg.page_object_ui_call_count,
        "page_object_setup_or_utility_call_count": agg.page_object_setup_or_utility_call_count,
        "page_object_call_count": agg.page_object_call_count,
        "direct_only_ui_action_count": agg.test_body_ui_action_count,
        "expanded_ui_action_count": agg.helper_ui_action_count + agg.cypress_command_ui_action_count,
        "hook_ui_action_count": agg.hook_ui_action_count,
        "helper_ui_action_count": agg.helper_ui_action_count,
        "custom_command_ui_action_count": agg.cypress_command_ui_action_count,
        "unresolved_helper_call_count": agg.unresolved_helper_call_count,
        "tests_with_locator": 1 if loc_events > 0 else 0,
        "tests_with_ui_action": 1 if ui_count > 0 else 0,
    }


def build_rq3_patterns_by_repo(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    import json
    from collections import defaultdict

    by_repo: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_repo[str(row.get("repo") or "")].append(row)

    out: List[Dict[str, Any]] = []
    for repo, tests in sorted(by_repo.items()):
        if not repo:
            continue
        n = len(tests)
        strat = Counter()
        arch = Counter()
        sync = Counter()
        robust = Counter()
        ui_total = 0
        loc_total = 0
        tests_with_loc = 0
        tests_with_ui = 0
        for t in tests:
            ui_total += int(t.get("ui_action_count") or 0)
            loc_total += int(t.get("locator_event_count") or 0)
            tests_with_loc += int(t.get("tests_with_locator") or 0)
            tests_with_ui += int(t.get("tests_with_ui_action") or 0)
            arch[str(t.get("workflow_archetype") or "")] += 1
            try:
                for k, v in json.loads(t.get("locator_strategy_counts_json") or "{}").items():
                    strat[k] += int(v)
            except json.JSONDecodeError:
                pass
            try:
                for k, v in json.loads(t.get("sync_pattern_counts_json") or "{}").items():
                    sync[k] += int(v)
            except json.JSONDecodeError:
                pass
            try:
                for k, v in json.loads(t.get("robustness_signal_counts_json") or "{}").items():
                    robust[k] += int(v)
            except json.JSONDecodeError:
                pass
        out.append({
            "repo": repo,
            "test_count": n,
            "tests_with_ui_action": tests_with_ui,
            "tests_with_locator": tests_with_loc,
            "ui_action_count": ui_total,
            "locator_event_count": loc_total,
            "locator_strategy_counts_json": json.dumps(dict(strat)),
            "workflow_archetype_counts_json": json.dumps(dict(arch)),
            "sync_pattern_counts_json": json.dumps(dict(sync)),
            "robustness_signal_counts_json": json.dumps(dict(robust)),
        })
    return out


def re_page_object(name: str) -> bool:
    root = name.split(".")[0] if name else ""
    return bool(root) and (
        root.endswith("Page")
        or root.endswith("Screen")
        or root.endswith("PO")
        or "Page" in root
    )


def assertion_source_bucket(source_kind: str, helper_depth: int, attached_hook: bool) -> str:
    """
    Legacy provenance bucket. Hook scope takes precedence over helper provenance.

    Prefer assertion_execution_scope + assertion_provenance for two-dimensional analysis.
    """
    if attached_hook or source_kind in ("before", "after", "beforeEach", "afterEach", "beforeAll", "afterAll"):
        return "hook"
    if helper_depth > 0 or source_kind in (
        "imported_helper",
        "helper_function",
        "helper_oracle",
        "page_object_method",
        "playwright_fixture",
        "playwright_auto_fixture",
        "cypress_command",
    ):
        return "helper"
    return "direct"


def assertion_execution_scope(source_kind: str, attached_hook: bool, helper_depth: int) -> str:
    """Where the assertion runs: test body vs hook-attached scope."""
    if attached_hook or source_kind in HOOK_SOURCE_KINDS:
        return "hook"
    if is_test_body_source(source_kind, attached_hook, helper_depth):
        return "test_body"
    return "expanded"


def assertion_provenance(source_kind: str, helper_depth: int, attached_hook: bool) -> str:
    """Implementation provenance independent of hook execution scope."""
    if source_kind == "cypress_command":
        return "cypress_command"
    if helper_depth > 0 or source_kind in (
        "imported_helper",
        "helper_function",
        "helper_oracle",
        "page_object_method",
        "playwright_fixture",
        "playwright_auto_fixture",
    ):
        return "helper"
    return "direct"


def is_test_body_source(source_kind: str, attached_hook: bool, depth: int) -> bool:
    if attached_hook:
        return False
    if depth > 0:
        return False
    if source_kind in HOOK_SOURCE_KINDS:
        return False
    if source_kind in (
        "imported_helper",
        "helper_function",
        "helper_oracle",
        "page_object_method",
        "playwright_fixture",
        "playwright_auto_fixture",
        "cypress_command",
    ):
        return False
    return source_kind in ("test_body", "implicit_oracle", "")


def ui_action_bucket(source_kind: str, attached_hook: bool, depth: int) -> str:
    if attached_hook or source_kind in HOOK_SOURCE_KINDS:
        return "hook"
    if source_kind == "cypress_command":
        return "cypress_command"
    if depth > 0 or source_kind in ("imported_helper", "helper_function"):
        return "helper"
    return "test_body"


def expanded_assertion_source_pattern(agg: TestAgg) -> str:
    parts: List[str] = []
    if agg.direct_assertion_count > 0:
        parts.append("direct")
    if agg.hook_assertion_count > 0:
        parts.append("hook")
    if agg.helper_assertion_count > 0:
        parts.append("helper")
    if not parts:
        return "none"
    if len(parts) == 1:
        return f"{parts[0]}_only"
    return "_and_".join(parts)


def assertion_placement(assertion_lines: List[int], ui_lines: List[int]) -> str:
    """Placement using test-body line numbers only (same file scope)."""
    if not assertion_lines:
        return "none"
    if not ui_lines:
        return "assertions_only"
    last_ui = max(ui_lines)
    if all(a > last_ui for a in assertion_lines):
        return "end_only"
    if all(a < min(ui_lines) for a in assertion_lines):
        return "start_only"
    if any(min(ui_lines) < a < max(ui_lines) for a in assertion_lines):
        return "interleaved"
    return "mixed"
