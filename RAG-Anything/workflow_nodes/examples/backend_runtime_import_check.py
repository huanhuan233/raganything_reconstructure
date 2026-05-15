"""
验证 Runtime Kernel 与 Workflow Nodes 的基础可编排能力。
"""

from __future__ import annotations

import asyncio
from typing import Any

from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.graph.workflow_schema import WorkflowSchema
from runtime_kernel.graph_engine.workflow_runner import WorkflowRunner
from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.node_runtime.node_registry import NodeRegistry
from runtime_kernel.entities.node_result import NodeResult


class CheckEchoNode(BaseNode):
    async def run(self, input_data: Any, _ctx: ExecutionContext) -> NodeResult:
        tag = str(self.config.get("tag", ""))
        return NodeResult(success=True, data={"tag": tag, "received": input_data}, metadata={})


async def main() -> None:
    reg = NodeRegistry()
    reg.register("check.echo", CheckEchoNode)

    schema = WorkflowSchema(
        workflow_id="import_check_dag",
        nodes=[
            {"id": "n1", "type": "check.echo", "config": {"tag": "first"}},
            {"id": "n2", "type": "check.echo", "config": {"tag": "second"}},
        ],
        edges=[("n1", "n2")],
        entry_node_ids=["n1"],
    )
    ctx = ExecutionContext(workflow_id=schema.workflow_id, run_id="check-1")
    result = await WorkflowRunner(registry=reg).run(schema, ctx, initial_input={"seed": True})
    print("RESULT:", "OK" if result.get("success") else "FAILED")


if __name__ == "__main__":
    asyncio.run(main())
