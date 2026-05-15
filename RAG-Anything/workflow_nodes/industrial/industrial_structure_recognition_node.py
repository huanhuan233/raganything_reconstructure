"""工业结构识别节点。"""

from __future__ import annotations

from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult


class IndustrialStructureRecognitionNode(BaseNode):
    @staticmethod
    def _flatten_routes(payload: dict[str, Any]) -> list[dict[str, Any]]:
        routes = payload.get("routes")
        if not isinstance(routes, dict):
            return []
        out: list[dict[str, Any]] = []
        for _, items in routes.items():
            if not isinstance(items, list):
                continue
            for one in items:
                if isinstance(one, dict):
                    out.append(dict(one))
        return out

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="industrial.structure_recognition",
            display_name="工业结构识别",
            category="industrial_parsing",
            description="基于 NormalizedLayoutBlocks 的多结构并行识别。",
            implementation_status="partial",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(
                    name="enabled_parsers",
                    label="Enabled Parsers",
                    type="multiselect",
                    required=False,
                    default=["title_hierarchy", "process_flow", "table_structure"],
                    options=["title_hierarchy", "process_flow", "table_structure", "form_structure", "custom_schema"],
                ),
                NodeConfigField(name="enable_validation", label="Enable Validation", type="boolean", required=False, default=True),
                NodeConfigField(name="enable_semantic_completion", label="Enable Semantic Completion", type="boolean", required=False, default=False),
            ],
            input_schema={"type": "object", "description": "requires mineru content_list"},
            output_schema={"type": "object", "description": "CompositeStructureResult"},
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        payload = dict(input_data) if isinstance(input_data, dict) else {}
        adapter = context.adapters.get("industrial_knowledge")
        if adapter is None:
            return NodeResult(success=False, error="industrial_knowledge adapter not found", data=payload)
        content_list = payload.get("content_list")
        if not isinstance(content_list, list):
            content_list = payload.get("mineru_content_list")
        if not isinstance(content_list, list):
            content_list = self._flatten_routes(payload)
        if not isinstance(content_list, list):
            return NodeResult(success=False, error="industrial.structure_recognition requires content_list", data=payload)
        # 供后续工业节点复用，避免 content.route 仅输出 routes 时再次缺失
        payload["content_list"] = content_list
        cfg = {
            "structure": {"enabled_parsers": list(self.config.get("enabled_parsers") or ["title_hierarchy", "process_flow", "table_structure"])},
            "enable_validation": bool(self.config.get("enable_validation", True)),
            "enable_semantic_completion": bool(self.config.get("enable_semantic_completion", False)),
        }
        out = await adapter.structure_recognition(mineru_content_list=content_list, config=cfg)
        payload.update(out if isinstance(out, dict) else {})
        return NodeResult(success=True, data=payload, metadata={"node": "industrial.structure_recognition"})
