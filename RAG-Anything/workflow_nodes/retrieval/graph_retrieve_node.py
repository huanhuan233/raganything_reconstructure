"""图谱检索节点：关键词 -> 图谱候选结果（最小闭环）。"""

from __future__ import annotations

import json
from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult
from runtime_kernel.runtime_state.content_access import ContentAccess
from runtime_kernel.runtime_state.variable_access import VariableAccess


class GraphRetrieveNode(BaseNode):
    """通过 adapters/lightrag 调用 LightRAG 图检索相关能力。"""

    @staticmethod
    def _as_dict(v: Any) -> dict[str, Any]:
        return v if isinstance(v, dict) else {}

    @staticmethod
    def _parse_keywords(v: Any) -> list[str]:
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            try:
                obj = json.loads(s)
                if isinstance(obj, list):
                    return [str(x).strip() for x in obj if str(x).strip()]
            except Exception:  # noqa: BLE001
                pass
            return [x.strip() for x in s.split(",") if x.strip()]
        return []

    @staticmethod
    def _as_bool(v: Any, default: bool = False) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return bool(v)
        if isinstance(v, str):
            s = v.strip().lower()
            if s in {"1", "true", "yes", "y", "on"}:
                return True
            if s in {"0", "false", "no", "n", "off"}:
                return False
        return default

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="",
            display_name="图谱检索",
            category="retrieval",
            description="通过关键词从图谱检索实体/关系候选。",
            implementation_status="partial",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(
                    name="implementation_mode",
                    label="实现方式",
                    type="select",
                    required=False,
                    default="minimal",
                    options=["minimal", "lightrag_context"],
                ),
                NodeConfigField(name="top_k", label="返回数量", type="number", required=False, default=20),
                NodeConfigField(
                    name="graph_backend",
                    label="图后端",
                    type="select",
                    required=False,
                    default="auto",
                    options=["auto", "neo4j", "networkx"],
                ),
                NodeConfigField(
                    name="workspace",
                    label="图空间",
                    type="string",
                    required=False,
                    default="",
                    description="默认从 knowledge.select 输出 selected_knowledge.graph_workspace 读取。",
                ),
                NodeConfigField(
                    name="strict_mode",
                    label="严格模式",
                    type="boolean",
                    required=False,
                    default=False,
                    description="开启后禁用 workspace 未命中后的全图重试，以及关键词未命中时的样本兜底。",
                    advanced=True,
                ),
                NodeConfigField(
                    name="query",
                    label="覆盖用户问题",
                    type="string",
                    required=False,
                    default="",
                    advanced=True,
                ),
                NodeConfigField(
                    name="high_level_keywords",
                    label="覆盖高层关键词",
                    type="json",
                    required=False,
                    default=[],
                    advanced=True,
                ),
                NodeConfigField(
                    name="low_level_keywords",
                    label="覆盖低层关键词",
                    type="json",
                    required=False,
                    default=[],
                    advanced=True,
                ),
            ],
            input_schema={"type": "object", "description": "query + keywords + selected_knowledge"},
            output_schema={"type": "object", "description": "graph_results + graph_summary"},
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        payload = dict(input_data) if isinstance(input_data, dict) else {}
        query_from_pool = VariableAccess.get_query(context, default="")
        top_k_from_pool = VariableAccess.get_top_k(context, default=20)
        query = str(
            self.config.get("query")
            or query_from_pool
            or payload.get("query")
            or payload.get("query_text")
            or ""
        ).strip()
        if not query:
            return NodeResult(success=False, error="graph.retrieve requires query", data=payload)

        cfg_high = self._parse_keywords(self.config.get("high_level_keywords"))
        cfg_low = self._parse_keywords(self.config.get("low_level_keywords"))
        in_high = self._parse_keywords(payload.get("high_level_keywords"))
        in_low = self._parse_keywords(payload.get("low_level_keywords"))
        high = cfg_high or in_high
        low = cfg_low or in_low

        selected = self._as_dict(
            context.variable_pool.get("selected_knowledge")
            or payload.get("selected_knowledge")
        )
        selected_backend = str(selected.get("graph_backend") or "").strip().lower()
        selected_ws = str(selected.get("graph_workspace") or selected.get("workspace") or "").strip()
        cfg_backend = str(self.config.get("graph_backend") or "auto").strip().lower() or "auto"
        backend = selected_backend if cfg_backend == "auto" and selected_backend else cfg_backend
        if backend in ("", "auto"):
            backend = "neo4j"
        workspace = str(self.config.get("workspace") or selected_ws or "").strip()
        impl_mode = str(self.config.get("implementation_mode") or "minimal").strip().lower()
        top_k = max(1, int(self.config.get("top_k") or top_k_from_pool or 20))
        strict_mode = self._as_bool(self.config.get("strict_mode"), default=False)

        adapter = context.adapters.get("lightrag_graph_retrieve")
        if adapter is None:
            return NodeResult(
                success=False,
                error="graph.retrieve requires lightrag_graph_retrieve adapter",
                data=payload,
            )

        out_data = dict(payload)
        warnings: list[str] = []
        try:
            retrieved = await adapter.retrieve_graph(
                high_level_keywords=high,
                low_level_keywords=low,
                query=query,
                top_k=top_k,
                workspace=workspace or None,
                graph_backend=backend,
                mode=impl_mode,
                strict_mode=strict_mode,
            )
            graph_results = retrieved.get("graph_results") if isinstance(retrieved, dict) else []
            graph_summary = retrieved.get("graph_summary") if isinstance(retrieved, dict) else {}
            if not isinstance(graph_results, list):
                graph_results = []
            if not isinstance(graph_summary, dict):
                graph_summary = {}
            warnings = retrieved.get("warnings") if isinstance(retrieved, dict) and isinstance(retrieved.get("warnings"), list) else []
            graph_summary = {
                "total": int(graph_summary.get("total") or len(graph_results)),
                "entity_count": int(graph_summary.get("entity_count") or 0),
                "relation_count": int(graph_summary.get("relation_count") or 0),
                "backend": str(graph_summary.get("backend") or backend),
                "workspace": str(graph_summary.get("workspace") or workspace),
                "source_algorithm": str(graph_summary.get("source_algorithm") or "lightrag.graph.retrieve.minimal"),
                "adapter_path": str(
                    graph_summary.get("adapter_path")
                    or "adapters.lightrag.graph_retrieve_adapter.GraphRetrieveAdapter"
                ),
                "used_original_algorithm": bool(graph_summary.get("used_original_algorithm", False)),
                "strict_mode": bool(graph_summary.get("strict_mode", strict_mode)),
                "warnings": [str(x) for x in warnings],
            }
            out_data["graph_results"] = graph_results[:top_k]
            out_data["graph_summary"] = graph_summary
            ContentAccess.set_retrieval_results(context, self.node_id, out_data["graph_results"])
            context.log(
                f"[GraphRetrieveNode] mode={impl_mode} backend={backend} workspace={workspace or '-'} "
                f"high={len(high)} low={len(low)} total={graph_summary['total']}"
            )
        except Exception as exc:  # noqa: BLE001
            return NodeResult(success=False, error=f"graph.retrieve failed: {exc}", data=payload)

        return NodeResult(
            success=True,
            data=out_data,
            metadata={"node": "graph.retrieve", "implementation_mode": impl_mode},
        )
