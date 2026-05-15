"""工业流程抽取节点。"""

from __future__ import annotations

from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeMetadata
from runtime_kernel.entities.node_result import NodeResult


class IndustrialProcessExtractNode(BaseNode):
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
            node_type="industrial.process_extract",
            display_name="工业流程抽取",
            category="process_knowledge",
            description="抽取 Process Flow Graph（before/next_step）。",
            implementation_status="partial",
            is_placeholder=False,
            config_fields=[],
            input_schema={"type": "object"},
            output_schema={"type": "object"},
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
            return NodeResult(success=False, error="industrial.process_extract requires content_list", data=payload)
        payload["content_list"] = content_list
        out = await adapter.process_extract(mineru_content_list=content_list, config={})
        payload.update(out if isinstance(out, dict) else {})
        return NodeResult(success=True, data=payload, metadata={"node": "industrial.process_extract"})
