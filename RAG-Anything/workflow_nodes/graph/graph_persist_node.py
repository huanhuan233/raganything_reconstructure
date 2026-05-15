"""graph.persist：将 graph.merge 输出真正持久化到图后端。"""

from __future__ import annotations

from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult


class GraphPersistNode(BaseNode):
    """图谱持久化节点（不做 merge，仅做存储）。"""

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="graph.persist",
            display_name="图谱持久化",
            category="knowledge_graph",
            description="将 graph.merge 输出的 entities/relations/components 持久化到图后端。",
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
                        {"label": "networkx", "value": "networkx"},
                        {"label": "local_jsonl", "value": "local_jsonl"},
                    ],
                ),
                NodeConfigField(
                    name="workspace",
                    label="Workspace",
                    type="string",
                    required=False,
                    default="",
                ),
                NodeConfigField(
                    name="create_if_missing",
                    label="Create If Missing",
                    type="boolean",
                    required=False,
                    default=True,
                ),
                NodeConfigField(
                    name="persist_components",
                    label="Persist Components",
                    type="boolean",
                    required=False,
                    default=False,
                ),
            ],
            input_schema={
                "type": "object",
                "description": "必须包含 graph={entities, relations, connected_components}",
            },
            output_schema={
                "type": "object",
                "description": "透传输入并附加 graph_persist_summary / storage_refs",
            },
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        if not isinstance(input_data, dict):
            return NodeResult(success=False, error="graph.persist 期望输入为 dict")
        graph = input_data.get("graph")
        if not isinstance(graph, dict):
            return NodeResult(success=False, error="graph.persist requires graph")

        cfg = dict(self.config or {})
        selected_knowledge = input_data.get("selected_knowledge")
        selected = selected_knowledge if isinstance(selected_knowledge, dict) else {}

        backend = str(
            cfg.get("graph_backend")
            or selected.get("graph_backend")
            or "neo4j"
        ).strip().lower()
        workspace = str(
            cfg.get("workspace")
            or selected.get("graph_workspace")
            or selected.get("workspace")
            or context.workspace
            or ""
        ).strip()
        create_if_missing = bool(cfg.get("create_if_missing", True))
        persist_components = bool(cfg.get("persist_components", False))

        adapter = context.adapters.get("lightrag_graph_persist")
        if adapter is None:
            return NodeResult(success=False, error="graph.persist missing adapter: lightrag_graph_persist")

        context.log(
            f"[GraphPersistNode] backend={backend} workspace={workspace or '(default)'} "
            f"persist_components={persist_components}"
        )
        try:
            persisted = await adapter.persist_graph(
                graph,
                graph_backend=backend,
                workspace=workspace,
                create_if_missing=create_if_missing,
                persist_components=persist_components,
            )
        except Exception as exc:  # noqa: BLE001
            return NodeResult(success=False, error=f"graph.persist failed: {exc}")

        out = dict(input_data)
        out["graph_persist_summary"] = persisted.get("graph_persist_summary", {})
        out["storage_refs"] = persisted.get("storage_refs", [])
        if persisted.get("warnings"):
            out["warnings"] = list(persisted.get("warnings") or [])
        return NodeResult(success=True, data=out, metadata={"node": "graph.persist"})
