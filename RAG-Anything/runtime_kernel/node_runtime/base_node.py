"""可编排节点抽象基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from runtime_kernel.entities.node_output import NodeOutput
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeMetadata
from runtime_kernel.entities.node_result import NodeResult
from runtime_kernel.runtime_state.legacy_bridge import resolve_legacy_input


class BaseNode(ABC):
    """
    工作流中的最小计算单元，与前端画布上的「节点」一一对应。

    子类实现 ``run``；输入输出通过 ``NodeResult.data`` 在 DAG 边上传递。
    """

    def __init__(self, node_id: str, node_type: str, config: Dict[str, Any]) -> None:
        self.node_id: str = node_id
        self.node_type: str = node_type
        self.config: Dict[str, Any] = dict(config)

    @classmethod
    def metadata(cls) -> NodeMetadata:
        """节点在节点库中的展示名、分组与配置表单 schema；``node_type`` 由注册表写入。"""
        return NodeMetadata(
            node_type="",
            display_name=cls.__name__,
            category="other",
            description="",
            implementation_status="real",
            is_placeholder=False,
            config_fields=[],
            input_schema=None,
            output_schema=None,
        )

    @abstractmethod
    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        """执行节点逻辑；**不得**在此阻塞除 await 外的长耗时同步 IO（后续可迁到 worker）。"""

    def read_inputs_from_context(self, context: ExecutionContext, input_data: Any = None) -> Any:
        """节点执行前读取上下文；默认走 legacy bridge。"""
        return resolve_legacy_input(
            context=context,
            node_id=self.node_id,
            fallback_input=input_data,
        )

    async def process(self, context: ExecutionContext, prepared_inputs: Any) -> NodeResult:
        """核心处理逻辑；默认代理到 run。"""
        return await self.run(prepared_inputs, context)

    def build_node_output(self, result: NodeResult, context: ExecutionContext) -> NodeOutput:
        """将 NodeResult 映射为标准化 NodeOutput。"""
        metadata = dict(result.metadata or {})
        return NodeOutput(
            content_refs=[],
            metadata=metadata,
            state_changes={},
            trace_events=[],
        )

    def write_outputs_to_context(self, context: ExecutionContext, result: NodeResult, node_output: NodeOutput) -> None:
        """节点执行后写回上下文。"""
        context.set_node_output(self.node_id, result.data, node_output)

    def emit_runtime_events(self, context: ExecutionContext, result: NodeResult, node_output: NodeOutput) -> None:
        """节点执行后发出事件（基础事件）。"""
        context.emit_event(
            "node_output_written",
            {
                "node_id": self.node_id,
                "node_type": self.node_type,
                "success": bool(result.success),
            },
        )
        for event in node_output.trace_events:
            if isinstance(event, dict) and event:
                event_type = str(event.get("event_type") or "node_custom_event")
                payload = {k: v for k, v in event.items() if k != "event_type"}
                context.emit_event(event_type, payload)

    # backward-compatible aliases
    def read_from_context(self, context: ExecutionContext, input_data: Any) -> Any:
        return self.read_inputs_from_context(context, input_data)

    def write_to_context(self, context: ExecutionContext, result: NodeResult, node_output: NodeOutput) -> None:
        self.write_outputs_to_context(context, result, node_output)

    def emit_events(self, context: ExecutionContext, result: NodeResult, node_output: NodeOutput) -> None:
        self.emit_runtime_events(context, result, node_output)

    async def execute(self, context: ExecutionContext, input_data: Any = None) -> NodeResult:
        """统一节点生命周期：read context -> process -> write context -> emit events。"""
        prepared_input = self.read_inputs_from_context(context, input_data)
        result = await self.process(context, prepared_input)
        node_output = self.build_node_output(result, context)
        self.write_outputs_to_context(context, result, node_output)
        self.emit_runtime_events(context, result, node_output)
        return result

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.node_id!r}, type={self.node_type!r})"
