"""industrial.graph.persist：工业原生图谱持久化节点。"""

from __future__ import annotations

from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult


class IndustrialGraphPersistNode(BaseNode):
    """将 industrial_graph 以原生 Label / Typed Relationship 写入图后端。"""

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="industrial.graph.persist",
            display_name="工业图谱持久化",
            category="industrial_graph",
            description="原生工业图谱落库（Document/Section/ProcessStep/Constraint 等 Label）。",
            implementation_status="partial",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(
                    name="graph_backend",
                    label="Graph Backend",
                    type="select",
                    required=False,
                    default="neo4j",
                    options=[
                        {"label": "neo4j", "value": "neo4j"},
                    ],
                    description="当前默认支持 neo4j，后续可扩展。",
                ),
                NodeConfigField(
                    name="enable_native_labels",
                    label="Enable Native Labels",
                    type="boolean",
                    required=False,
                    default=True,
                ),
                NodeConfigField(
                    name="enable_typed_relationships",
                    label="Enable Typed Relationships",
                    type="boolean",
                    required=False,
                    default=True,
                ),
                NodeConfigField(
                    name="namespace",
                    label="Namespace",
                    type="string",
                    required=False,
                    default="industrial_default",
                ),
                NodeConfigField(
                    name="validation",
                    label="Validation",
                    type="boolean",
                    required=False,
                    default=True,
                ),
                NodeConfigField(
                    name="batch_size",
                    label="Batch Size",
                    type="number",
                    required=False,
                    default=100,
                ),
                NodeConfigField(
                    name="dry_run",
                    label="Dry Run",
                    type="boolean",
                    required=False,
                    default=False,
                ),
                NodeConfigField(
                    name="create_if_missing",
                    label="Create If Missing",
                    type="boolean",
                    required=False,
                    default=True,
                ),
            ],
            input_schema={"type": "object", "description": "requires industrial_graph={nodes,edges}"},
            output_schema={"type": "object", "description": "附加 industrial_graph_persist_summary / storage_refs"},
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        if not isinstance(input_data, dict):
            return NodeResult(success=False, error="industrial.graph.persist expects dict input")
        payload = dict(input_data)
        graph = payload.get("industrial_graph")
        if not isinstance(graph, dict):
            return NodeResult(success=False, error="industrial.graph.persist requires industrial_graph", data=payload)

        adapter = context.adapters.get("industrial_graph_persist")
        if adapter is None:
            return NodeResult(success=False, error="industrial.graph.persist missing adapter: industrial_graph_persist", data=payload)

        cfg = dict(self.config or {})
        backend = str(cfg.get("graph_backend") or "neo4j").strip().lower() or "neo4j"
        namespace = str(cfg.get("namespace") or "").strip() or "industrial_default"
        enable_native_labels = bool(cfg.get("enable_native_labels", True))
        enable_typed_relationships = bool(cfg.get("enable_typed_relationships", True))
        validation = bool(cfg.get("validation", True))
        dry_run = bool(cfg.get("dry_run", False))
        batch_size = int(cfg.get("batch_size") or 100)
        create_if_missing = bool(cfg.get("create_if_missing", True))

        context.log(
            "[IndustrialGraphPersistNode] "
            f"backend={backend} namespace={namespace} native_labels={enable_native_labels} "
            f"typed_relationships={enable_typed_relationships} validation={validation} dry_run={dry_run}"
        )
        try:
            persisted = await adapter.persist_graph(
                graph,
                graph_backend=backend,
                namespace=namespace,
                enable_native_labels=enable_native_labels,
                enable_typed_relationships=enable_typed_relationships,
                validation=validation,
                batch_size=batch_size,
                dry_run=dry_run,
                create_if_missing=create_if_missing,
            )
        except Exception as exc:  # noqa: BLE001
            return NodeResult(success=False, error=f"industrial.graph.persist failed: {exc}", data=payload)

        if not bool(persisted.get("success", False)):
            return NodeResult(
                success=False,
                error="industrial.graph.persist validation failed",
                data={**payload, "industrial_graph_persist_errors": persisted.get("errors", [])},
            )

        out = dict(payload)
        out["industrial_graph_persist_summary"] = persisted.get("industrial_graph_persist_summary", {})
        out["storage_refs"] = persisted.get("storage_refs", [])
        warnings = list(persisted.get("warnings", []))
        if warnings:
            out["warnings"] = list(out.get("warnings", [])) + warnings
        return NodeResult(success=True, data=out, metadata={"node": "industrial.graph.persist"})

