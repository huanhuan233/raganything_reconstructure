"""semantic.relation.persist — 将 SemanticRelation / plan 语义边写入 Neo4j（适配器可选）。"""

from __future__ import annotations

import inspect
from typing import Any

from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult
from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.runtime_state.payload_carry import slim_semantic_carry_payload


class SemanticRelationPersistNode(BaseNode):
    adapter_names = ("ontology_graph_runtime", "industrial_semantic_graph")

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="semantic.relation.persist",
            display_name="语义关系持久化",
            category="ontology_graph_runtime",
            description="USES / DEPENDS_ON 等运行时关系写入图库。",
            implementation_status="partial",
            is_placeholder=False,
            config_fields=[NodeConfigField(name="dry_run", label="Dry Run", type="boolean", required=False, default=True)],
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        incoming = dict(input_data) if isinstance(input_data, dict) else {}
        payload = slim_semantic_carry_payload(incoming)
        edges_raw = payload.get("semantic_relations") or payload.get("relations")

        plan = payload.get("semantic_plan") or context.semantic_plan
        deps: list[dict[str, str]] = []
        if isinstance(plan, dict):
            for d in plan.get("semantic_dependencies") or []:
                if isinstance(d, dict) and {"subject", "predicate", "obj"} <= set(d):
                    deps.append({"subject_id": str(d["subject"]), "predicate": str(d["predicate"]), "object_id": str(d["obj"])})

        if isinstance(edges_raw, list):
            for e in edges_raw:
                if isinstance(e, dict) and {"subject_id", "predicate", "object_id"} <= set(e.keys()):
                    deps.append(
                        {
                            "subject_id": str(e["subject_id"]),
                            "predicate": str(e["predicate"]),
                            "object_id": str(e["object_id"]),
                        }
                    )

        adapter = next((context.adapters.get(n) for n in self.adapter_names if context.adapters.get(n)), None)
        dry = bool(self.config.get("dry_run", True))
        if adapter is None:
            payload["semantic_relation_persist_skipped"] = True
            payload["semantic_relation_persist_reason"] = "no adapter"
            payload["semantic_relations_preview"] = deps
            return NodeResult(success=True, data=payload)

        fn = getattr(adapter, "persist_semantic_relations", None) or getattr(adapter, "persist_relations", None)
        if fn is None:
            payload["semantic_relation_persist_skipped"] = True
            payload["semantic_relation_preview"] = deps
            return NodeResult(success=True, data=payload)

        bundle = {"edges": deps, "dry_run": dry, "workspace": context.workspace}
        out = await fn(bundle) if inspect.iscoroutinefunction(fn) else fn(bundle)
        payload["semantic_relation_persist_summary"] = out if isinstance(out, dict) else {}
        return NodeResult(success=True, data=payload)
