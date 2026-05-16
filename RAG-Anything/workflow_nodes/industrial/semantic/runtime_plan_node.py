"""semantic.runtime.plan — SemanticExecutionPlan IR（DAG + 对象 + 约束链）。"""

from __future__ import annotations

from typing import Any

from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult
from runtime_kernel.node_runtime.base_node import BaseNode

from ..models.semantic_execution_plan import SemanticDependency, SemanticExecutionPlan


def _ontology_type_lowercase(o: dict) -> str:
    ot = o.get("ontology_type")
    return str(getattr(ot, "value", ot) or "").lower()


class IndustrialSemanticRuntimePlanNode(BaseNode):
    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="semantic.runtime.plan",
            display_name="语义运行时执行计划 IR",
            category="industrial_semantic_runtime",
            description="融合本体对象 / 约束 / runtime_state → SemanticExecutionPlan。",
            implementation_status="real",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(
                    name="use_dag_topo",
                    label="Use DAG Topo From Metadata",
                    type="boolean",
                    required=False,
                    default=False,
                    description="若 execution_metadata['dag_topo_order'] 存在则纳入 plan",
                ),
            ],
            semantic_inputs=["ontology_objects", "constraints"],
            semantic_outputs=["semantic_plan", "semantic_runtime_state"],
            runtime_state_dependencies=["ontology_state", "constraint_state"],
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        payload = dict(input_data) if isinstance(input_data, dict) else {}

        objs = payload.get("ontology_objects") or context.content_pool.get("ontology_objects") or []
        cons = payload.get("constraints") or context.content_pool.get("constraints") or []
        filt = payload.get("industrial_filtered") or context.content_pool.get("industrial_filtered") or {}

        valid_only = filt.get("valid_objects") if isinstance(filt, dict) else None
        if isinstance(valid_only, list) and valid_only:
            work_objs = valid_only
        elif isinstance(objs, list):
            work_objs = [dict(o) if isinstance(o, dict) else o.model_dump(mode="python") for o in objs if o]
        else:
            work_objs = []

        object_ids = [str(o.get("object_id")) for o in work_objs if isinstance(o, dict) and o.get("object_id")]

        wf_order: list[str] = []
        if bool(self.config.get("use_dag_topo", False)):
            topo = context.execution_metadata.get("dag_topo_order")
            if isinstance(topo, list):
                wf_order = [str(x) for x in topo]

        deps: list[SemanticDependency] = []
        proc_ids = sorted(
            str(o["object_id"])
            for o in work_objs
            if isinstance(o, dict) and o.get("object_id") and _ontology_type_lowercase(o) == "process"
        )
        prev: str | None = None
        for pid in proc_ids:
            if prev:
                deps.append(SemanticDependency(subject=prev, predicate="DEPENDS_ON", obj=pid))
            prev = pid

        constraint_ids: list[str] = []
        if isinstance(cons, list):
            for c in cons:
                if isinstance(c, dict) and c.get("constraint_id"):
                    constraint_ids.append(str(c["constraint_id"]))

        legality: list[str] = []
        for c in cons or []:
            if not isinstance(c, dict):
                continue
            preds = (c.get("predicates") or {}) if isinstance(c.get("predicates"), dict) else {}
            before = preds.get("requires_ordering_before")
            if before:
                legality.append(f"序约束存根：{before} （需在 Transition 校验中闭环）")

        exec_order_proc = sorted(
            str(o["object_id"])
            for o in work_objs
            if isinstance(o, dict) and o.get("object_id") and _ontology_type_lowercase(o) == "process"
        )
        execution_order = exec_order_proc or wf_order or object_ids

        plan = SemanticExecutionPlan(
            workflow_node_order=list(wf_order),
            ontology_object_ids=list(object_ids),
            semantic_dependencies=list(deps),
            constraint_chain_refs=constraint_ids,
            execution_order=execution_order,
            runtime_legality_notes=list(legality),
            state_ordering_hints=sorted({d.obj for d in deps}),
        )

        dumped = plan.model_dump(mode="python")
        context.semantic_plan = dumped
        context.semantic_runtime_state.phase = "planned"
        context.semantic_runtime_state.plan_id = plan.plan_id
        context.semantic_runtime_state.dependency_edges = [(d.subject, d.predicate, d.obj) for d in deps]
        context.semantic_runtime_state.legality_issues = list(legality)

        payload["semantic_plan"] = dumped
        context.emit_event(
            "semantic_plan_generated",
            {"node_id": self.node_id, "plan_id": plan.plan_id, "stages": len(execution_order)},
        )

        return NodeResult(success=True, data=payload, metadata={"plan_id": plan.plan_id})
