"""ontology.graph.persist — 将 OntologyObject 列表写入 Neo4j Runtime Graph（适配器可选）。"""

from __future__ import annotations

import inspect
from typing import Any

from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult
from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.runtime_state.payload_carry import slim_semantic_carry_payload


class OntologyGraphPersistNode(BaseNode):
    adapter_names = ("ontology_graph_runtime", "industrial_semantic_graph")

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="ontology.graph.persist",
            display_name="本体对象图持久化",
            category="ontology_graph_runtime",
            description="写入 (:Part|:Process|…) 运行时标签；需适配器 ontology_graph_runtime（可无则跳过）。",
            implementation_status="partial",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(name="dry_run", label="Dry Run", type="boolean", required=False, default=True),
            ],
            ontology_types=["Part", "Process", "Equipment", "Operation", "Constraint", "State"],
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        incoming = dict(input_data) if isinstance(input_data, dict) else {}
        payload = slim_semantic_carry_payload(incoming)
        objs = payload.get("ontology_objects") or context.content_pool.get("ontology_objects") or []
        if not isinstance(objs, list):
            objs = []

        adapter = None
        for name in self.adapter_names:
            adapter = context.adapters.get(name)
            if adapter is not None:
                break

        dry = bool(self.config.get("dry_run", True))
        if adapter is None:
            payload["ontology_graph_persist_skipped"] = True
            payload["ontology_graph_persist_reason"] = "no adapter ontology_graph_runtime / industrial_semantic_graph"
            return NodeResult(success=True, data=payload)

        op = getattr(adapter, "persist_ontology_objects", None) or getattr(adapter, "persist", None)
        if op is None:
            payload["ontology_graph_persist_skipped"] = True
            payload["ontology_graph_persist_reason"] = "adapter lacks persist_ontology_objects / persist"
            return NodeResult(success=True, data=payload)

        bundle = {"objects": objs, "dry_run": dry, "workspace": context.workspace}
        out = await op(bundle) if inspect.iscoroutinefunction(op) else op(bundle)
        payload["ontology_graph_persist_summary"] = out if isinstance(out, dict) else {"result": str(out)}
        return NodeResult(success=True, data=payload)
