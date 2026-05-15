"""文档状态更新占位节点（源码阶段映射）。"""

from __future__ import annotations

from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeMetadata
from runtime_kernel.entities.node_result import NodeResult


class DocStatusUpdateNode(BaseNode):
    """映射文档状态流转阶段，不直接调用真实实现。"""

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="",
            display_name="文档状态更新",
            category="document",
            description="文档状态更新占位，对应 doc_status 的 PENDING/PROCESSING/PROCESSED/FAILED。",
            implementation_status="placeholder",
            is_placeholder=True,
            config_fields=[],
            input_schema=None,
            output_schema=None,
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        context.log(f"[DocStatusUpdateNode] 占位透传 node_id={self.node_id}")
        return NodeResult(
            success=True,
            data=input_data,
            metadata={
                "planned_source_file": "raganything document status pipeline",
                "planned_source_function": "doc_status state transitions",
                "planned_behavior": "在入库生命周期中更新文档状态并同步失败/完成标记。",
            },
        )
