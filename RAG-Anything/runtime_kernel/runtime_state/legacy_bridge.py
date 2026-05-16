"""Legacy input/output 兼容桥。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from runtime_kernel.graph.workflow_schema import WorkflowSchema

if TYPE_CHECKING:
    from runtime_kernel.execution_context.execution_context import ExecutionContext


def _parents(schema: WorkflowSchema, node_id: str) -> list[str]:
    return [a for a, b in schema.edges if b == node_id]


def resolve_legacy_input(
    *,
    context: "ExecutionContext",
    node_id: str,
    fallback_input: Any = None,
) -> Any:
    """
    为未完全 Runtime 化的节点提供输入兜底。

    优先级：
    1) 调用方显式传入 fallback_input
    2) context.execution_metadata["legacy_node_inputs"][node_id]
    3) default_legacy_input（run 入口输入）
    """
    if fallback_input is not None:
        return fallback_input
    legacy_inputs = context.execution_metadata.get("legacy_node_inputs", {})
    if isinstance(legacy_inputs, dict) and node_id in legacy_inputs:
        return legacy_inputs[node_id]
    return context.execution_metadata.get("default_legacy_input")


def build_legacy_inputs_from_schema(
    *,
    schema: WorkflowSchema,
    context: "ExecutionContext",
    initial_input: Any,
) -> dict[str, Any]:
    """
    基于 DAG 边构造 legacy 输入映射，避免 Runner 直接传 parent_result.data。
    """
    out: dict[str, Any] = {}
    for nid in schema.node_ids():
        parents = _parents(schema, nid)
        if not parents:
            if isinstance(initial_input, dict) and nid in initial_input:
                out[nid] = initial_input[nid]
            else:
                out[nid] = initial_input
            continue
        if len(parents) == 1:
            out[nid] = context.get_node_output_data(parents[0])
            continue
        merged: dict[str, Any] = {}
        for pid in sorted(parents):
            merged[pid] = context.get_node_output_data(pid)
        out[nid] = merged
    return out
