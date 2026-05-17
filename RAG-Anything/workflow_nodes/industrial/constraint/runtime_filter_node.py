"""constraint.runtime.filter — 解释性运行时约束过滤（Runtime Rule Engine）。"""

from __future__ import annotations

from typing import Any

from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult
from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.runtime_state.runtime_constraint import RuntimeConstraintEngine
from runtime_kernel.runtime_state.payload_carry import slim_semantic_carry_payload

from .constraint_engine_bridge import coerce_constraint_records


class IndustrialConstraintRuntimeFilterNode(BaseNode):
    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="constraint.runtime.filter",
            display_name="工业运行时约束过滤",
            category="industrial_semantic_runtime",
            description="ExplainableFiltering：产出 valid_objects / rejected_objects / constraint_explanations。",
            implementation_status="real",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(name="explain_all", label="Explain All", type="boolean", required=False, default=False),
            ],
            semantic_inputs=["ontology_objects", "constraints"],
            semantic_outputs=["industrial_filtered", "constraint_explanations"],
            ontology_types=["Part", "Process", "Operation"],
            constraint_dependencies=["constraints"],
            runtime_state_dependencies=["ontology_state", "constraint_state", "runtime_constraints"],
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        base = dict(input_data) if isinstance(input_data, dict) else {}

        objs = base.get("ontology_objects") or context.content_pool.get("ontology_objects") or []
        if not isinstance(objs, list):
            objs = []

        cands_raw: list[Any] = list(objs)
        cand_proc = base.get("candidate_plan") or base.get("candidate_process_plan")
        if isinstance(cand_proc, list):
            cands_raw.extend([p for p in cand_proc if isinstance(p, dict)])

        cands_dump: list[dict[str, Any]] = []
        for c in cands_raw:
            if hasattr(c, "model_dump"):
                cands_dump.append(c.model_dump(mode="python"))
            elif isinstance(c, dict):
                cands_dump.append(dict(c))

        con_raw = base.get("constraints") or context.content_pool.get("constraints") or []
        if not isinstance(con_raw, list):
            con_raw = []
        merged_rules_src = [*con_raw, *(context.runtime_constraints or [])]

        rules = coerce_constraint_records(merged_rules_src)
        engine = RuntimeConstraintEngine()
        explain_all = bool(self.config.get("explain_all", False))
        valid, rejected, explanations = engine.filter(
            constraints=rules,
            candidates=cands_dump,
            explain_all=explain_all,
        )

        for r in rejected:
            context.constraint_state.log_rejection(
                {
                    "reason": "constraint_runtime_filter",
                    "object_id": r.get("object_id"),
                    "node_id": self.node_id,
                }
            )

        digest = engine.explain(explanations)
        filt_block = {"valid_objects": valid, "rejected_objects": rejected}

        payload = slim_semantic_carry_payload(base)

        retrieval = base.get("candidate_retrieval_results")
        if retrieval is not None:
            filt_retrieval = retrieval if isinstance(retrieval, list) else []
            payload["candidate_retrieval_results_filtered"] = [x for x in filt_retrieval if isinstance(x, dict)]

        payload["valid_objects"] = valid
        payload["rejected_objects"] = rejected
        payload["constraint_explanations"] = explanations
        payload["explanation_digest_zh"] = digest

        context.content_pool.put("industrial_filtered", filt_block)
        payload["industrial_filtered"] = filt_block

        context.emit_event(
            "constraint_filter_completed",
            {
                "node_id": self.node_id,
                "valid": len(valid),
                "rejected": len(rejected),
            },
        )
        trig = [{"constraint_id": e.get("constraint_id"), "satisfied": e.get("satisfied")} for e in explanations][:20]
        context.emit_event("constraint_triggered", {"records": trig})
        if rejected:
            context.emit_event(
                "constraint_rejected",
                {
                    "node_id": self.node_id,
                    "digest_preview": digest[:400],
                    "count": len(rejected),
                    "sample_ids": [r.get("object_id") for r in rejected][:10],
                },
            )

        return NodeResult(
            success=True,
            data=payload,
            metadata={"valid_count": len(valid), "rejected_count": len(rejected)},
        )

    def build_node_output(self, result: NodeResult, context: ExecutionContext):
        out = super().build_node_output(result, context)
        meta = dict(result.metadata or {})
        out.trace_events.append({"event_type": "constraint_filtered", **meta})
        return out
