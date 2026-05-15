"""工作流结束节点。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeMetadata
from runtime_kernel.entities.node_result import NodeResult


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class WorkflowEndNode(BaseNode):
    """工作流结束：汇总上游并输出 final_output。"""

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="",
            display_name="结束",
            category="workflow",
            description="工作流结束节点",
            implementation_status="real",
            is_placeholder=False,
            config_fields=[],
            input_schema=None,
            output_schema=None,
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        ended_at = _utc_iso()
        if isinstance(input_data, dict):
            data = {"final_output": input_data, "summary": {"keys": sorted(list(input_data.keys()))}}
        else:
            data = {"final_output": input_data}
        context.log(f"[WorkflowEndNode] ended_at={ended_at}")
        return NodeResult(success=True, data=data, metadata={"ended_at": ended_at})
