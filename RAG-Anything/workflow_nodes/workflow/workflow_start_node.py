"""工作流开始节点。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeMetadata
from runtime_kernel.entities.node_result import NodeResult


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class WorkflowStartNode(BaseNode):
    """工作流入口：透传输入并记录起始时间。"""

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="",
            display_name="开始",
            category="workflow",
            description="工作流入口节点",
            implementation_status="real",
            is_placeholder=False,
            config_fields=[],
            input_schema=None,
            output_schema=None,
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        started_at = _utc_iso()
        context.log(f"[WorkflowStartNode] started_at={started_at}")
        return NodeResult(success=True, data=input_data, metadata={"started_at": started_at})
