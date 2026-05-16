"""constraint.relation.persist — 约束链与实体关联写入 Neo4j（适配器可选）。"""

from __future__ import annotations

import inspect
from typing import Any

from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult
from runtime_kernel.node_runtime.base_node import BaseNode


class ConstraintRelationPersistNode(BaseNode):
    adapter_names = ("ontology_graph_runtime", "industrial_semantic_graph")

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="constraint.relation.persist",
            display_name="约束关系持久化",
            category="ontology_graph_runtime",
            description="CONSTRAINED_BY / FORBIDS 等约束图边（最小封装）。",
            implementation_status="partial",
            is_placeholder=False,
            config_fields=[NodeConfigField(name="dry_run", label="Dry Run", type="boolean", required=False, default=True)],
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        payload = dict(input_data) if isinstance(input_data, dict) else {}
        constraints = payload.get("constraints") or context.content_pool.get("constraints") or []
        targets = payload.get("ontology_objects") or context.content_pool.get("ontology_objects") or []

        adapter = next((context.adapters.get(n) for n in self.adapter_names if context.adapters.get(n)), None)
        dry = bool(self.config.get("dry_run", True))

        snapshot = {
            "constraints": constraints if isinstance(constraints, list) else [],
            "targets": targets if isinstance(targets, list) else [],
        }
        payload["constraint_relation_snapshot"] = snapshot

        if adapter is None:
            payload["constraint_relation_persist_skipped"] = True
            payload["constraint_relation_persist_reason"] = "no adapter"
            return NodeResult(success=True, data=payload)

        fn = getattr(adapter, "persist_constraint_relations", None) or getattr(adapter, "persist_constraints", None)
        if fn is None:
            payload["constraint_relation_persist_skipped"] = True
            return NodeResult(success=True, data=payload)

        bundle = dict(snapshot)
        bundle.update({"dry_run": dry, "workspace": context.workspace})
        out = await fn(bundle) if inspect.iscoroutinefunction(fn) else fn(bundle)
        payload["constraint_relation_persist_summary"] = out if isinstance(out, dict) else {}
        return NodeResult(success=True, data=payload)
