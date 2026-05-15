"""可编排节点抽象基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeMetadata
from runtime_kernel.entities.node_result import NodeResult


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

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.node_id!r}, type={self.node_type!r})"
