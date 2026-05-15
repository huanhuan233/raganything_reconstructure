"""视觉内容回收占位节点（源码阶段映射）。"""

from __future__ import annotations

from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeMetadata
from runtime_kernel.entities.node_result import NodeResult


class VisualRecoverNode(BaseNode):
    """映射 RAG-Anything VLM enhanced query 的视觉内容回收阶段。"""

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="",
            display_name="视觉内容回收",
            category="multimodal",
            description="多模态视觉内容回收占位，对应 image path dereference/base64 处理。",
            implementation_status="placeholder",
            is_placeholder=True,
            config_fields=[],
            input_schema=None,
            output_schema=None,
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        context.log(f"[VisualRecoverNode] 占位透传 node_id={self.node_id}")
        return NodeResult(
            success=True,
            data=input_data,
            metadata={
                "planned_source_file": "raganything query pipeline",
                "planned_source_function": "vlm enhanced query image dereference/base64 stage",
                "planned_behavior": "将检索命中的视觉资源路径解析为可直接送入 VLM 的内容片段。",
            },
        )
