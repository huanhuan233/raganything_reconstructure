"""工作流执行期共享上下文（Runtime 全局状态中心）。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from runtime_kernel.entities.node_output import NodeOutput
from runtime_kernel.runtime_state.content_pool import ContentPool
from runtime_kernel.runtime_state.execution_state import ExecutionState
from runtime_kernel.runtime_state.graph_state import GraphState
from runtime_kernel.runtime_state.node_state import NodeState
from runtime_kernel.runtime_state.runtime_registry import RuntimeRegistry
from runtime_kernel.runtime_state.state_types import CONTENT_BUCKETS
from runtime_kernel.runtime_state.variable_pool import VariablePool

_logger = logging.getLogger("backend_runtime.execution")


@dataclass
class ExecutionContext:
    """
    统一承载 Runtime 状态：

    - ``variable_pool``：运行参数与 flags；
    - ``content_pool``：内容生命周期产物；
    - ``runtime_state`` / ``graph_state``：执行状态与 DAG 状态；
    - ``node_outputs`` / ``trace_events``：标准化节点输出与事件；
    - ``scheduler_state`` / ``execution_metadata``：为后续调度与 tracing 预留。
    """

    workflow_id: str
    run_id: str
    workspace: str = ""
    adapters: dict[str, Any] = field(default_factory=dict)
    shared_data: dict[str, Any] = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)

    variable_pool: VariablePool = field(default_factory=VariablePool)
    content_pool: ContentPool = field(default_factory=ContentPool)
    runtime_state: ExecutionState | None = None
    graph_state: GraphState = field(default_factory=GraphState)
    node_outputs: dict[str, NodeOutput] = field(default_factory=dict)
    trace_events: list[dict[str, Any]] = field(default_factory=list)
    scheduler_state: dict[str, Any] = field(default_factory=dict)
    execution_metadata: dict[str, Any] = field(default_factory=dict)
    runtime_registry: RuntimeRegistry = field(default_factory=RuntimeRegistry)
    raw_node_outputs: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.runtime_state is None:
            self.runtime_state = ExecutionState(
                workflow_id=self.workflow_id,
                run_id=self.run_id,
                scheduler_state=self.scheduler_state,
                execution_metadata=self.execution_metadata,
            )
        else:
            self.scheduler_state = self.runtime_state.scheduler_state
            self.execution_metadata = self.runtime_state.execution_metadata
        self.variable_pool.set("workflow_id", self.workflow_id)
        self.variable_pool.set("run_id", self.run_id)
        if self.workspace:
            self.variable_pool.set("workspace", self.workspace)

    def log(self, message: str) -> None:
        """追加一条日志。"""
        self.logs.append(message)
        try:
            _logger.info(
                "[workflow_id=%s run_id=%s] %s",
                self.workflow_id,
                self.run_id,
                message,
            )
        except Exception:  # noqa: BLE001
            pass

    def register_node_state(self, node_id: str, node_type: str) -> NodeState:
        assert self.runtime_state is not None
        state = self.runtime_state.node_states.get(node_id)
        if state is None:
            state = NodeState(node_id=node_id, node_type=node_type)
            self.runtime_state.node_states[node_id] = state
        return state

    def set_node_output(self, node_id: str, result_data: Any, output: NodeOutput | None = None) -> NodeOutput:
        out = output or NodeOutput()
        self.node_outputs[node_id] = out
        self.raw_node_outputs[node_id] = result_data
        self.shared_data[f"node_output:{node_id}"] = result_data
        self._sync_content_pool(result_data)
        return out

    def get_node_output_data(self, node_id: str, default: Any = None) -> Any:
        return self.raw_node_outputs.get(node_id, default)

    def emit_event(self, event_type: str, payload: dict[str, Any]) -> None:
        event = {"event_type": str(event_type), "run_id": self.run_id, "workflow_id": self.workflow_id, **dict(payload)}
        self.trace_events.append(event)

    def _sync_content_pool(self, result_data: Any) -> None:
        if not isinstance(result_data, dict):
            return
        for bucket in CONTENT_BUCKETS:
            if bucket in result_data:
                self.content_pool.put(bucket, result_data.get(bucket))
