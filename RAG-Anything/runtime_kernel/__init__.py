"""运行时核心：上下文、节点抽象、注册表、工作流模式与执行器。"""

from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.graph.workflow_schema import WorkflowSchema
from runtime_kernel.graph_engine.workflow_runner import WorkflowRunner
from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.node_runtime.node_registry import NodeRegistry, get_default_registry
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata, metadata_as_dict, with_node_type
from runtime_kernel.entities.node_output import NodeOutput
from runtime_kernel.entities.node_result import NodeResult
from runtime_kernel.runtime_state import (
    ContentPool,
    ExecutionState,
    GraphState,
    NodePhase,
    NodeState,
    RuntimeRegistry,
    VariablePool,
)

__all__ = [
    "BaseNode",
    "ExecutionContext",
    "NodeResult",
    "NodeOutput",
    "NodeConfigField",
    "NodeMetadata",
    "metadata_as_dict",
    "with_node_type",
    "NodeRegistry",
    "get_default_registry",
    "WorkflowSchema",
    "WorkflowRunner",
    "VariablePool",
    "ContentPool",
    "ExecutionState",
    "GraphState",
    "NodeState",
    "NodePhase",
    "RuntimeRegistry",
]
