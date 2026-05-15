"""工业约束抽取节点。"""

from __future__ import annotations

from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult


class IndustrialConstraintExtractNode(BaseNode):
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
            node_type="industrial.constraint_extract",
            display_name="工业约束抽取",
            category="constraint_extraction",
            description="规则优先抽取工程约束（Ra、公差、边距等）。",
            implementation_status="partial",
            is_placeholder=False,
            config_fields=[NodeConfigField(name="enable_validation", label="Enable Validation", type="boolean", required=False, default=True)],
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
            return NodeResult(success=False, error="industrial.constraint_extract requires content_list", data=payload)
        payload["content_list"] = content_list
        cfg = {"enable_validation": bool(self.config.get("enable_validation", True))}
        out = await adapter.constraint_extract(mineru_content_list=content_list, config=cfg)
        payload.update(out if isinstance(out, dict) else {})
        return NodeResult(success=True, data=payload, metadata={"node": "industrial.constraint_extract"})
