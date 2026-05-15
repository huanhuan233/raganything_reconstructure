"""最简单的 DAG 顺序执行器（拓扑序、无并行）。"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Awaitable, Callable, Dict, List, Optional

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.node_runtime.node_registry import NodeRegistry, get_default_registry
from runtime_kernel.entities.node_result import NodeResult
from runtime_kernel.graph.workflow_schema import WorkflowSchema


class WorkflowRunner:
    """
    按有向无环图拓扑序依次执行节点；任一步失败则中止并返回聚合错误信息。

    多条入边时，将各父节点 ``NodeResult.data`` 合并为
    ``{"<parent_id>": data}`` 传入子节点（若父节点唯一且 data 为 dict，亦可被下游直接解构）。
    """

    def __init__(self, registry: Optional[NodeRegistry] = None) -> None:
        self._registry = registry or get_default_registry()

    def _topological_order(self, schema: WorkflowSchema) -> List[str]:
        ids = schema.node_ids()
        id_set = set(ids)
        for a, b in schema.edges:
            if a not in id_set or b not in id_set:
                raise ValueError(f"边 ({a}, {b}) 引用了未知节点 id")

        indeg: Dict[str, int] = {i: 0 for i in ids}
        adj: Dict[str, List[str]] = defaultdict(list)
        for a, b in schema.edges:
            adj[a].append(b)
            indeg[b] += 1

        # 初始入队：入度为 0 的节点（确定性：按 id 排序）
        zero = [n for n in sorted(ids) if indeg[n] == 0]
        if not zero:
            raise ValueError("图中无入度为 0 的节点，可能存在环或空图")

        q = deque()
        for n in zero:
            q.append(n)

        order: List[str] = []
        while q:
            u = q.popleft()
            order.append(u)
            for v in sorted(adj[u]):
                indeg[v] -= 1
                if indeg[v] == 0:
                    q.append(v)

        if len(order) != len(ids):
            raise ValueError("图中存在环或无法拓扑排序的连通分支")

        return order

    def _parents(self, schema: WorkflowSchema, node_id: str) -> List[str]:
        return [a for a, b in schema.edges if b == node_id]

    def _build_input(
        self,
        node_id: str,
        schema: WorkflowSchema,
        results_by_id: Dict[str, NodeResult],
        initial_input: Any,
    ) -> Any:
        parents = self._parents(schema, node_id)
        if not parents:
            if isinstance(initial_input, dict) and node_id in initial_input:
                return initial_input[node_id]
            return initial_input
        if len(parents) == 1:
            pid = parents[0]
            prev = results_by_id[pid]
            return prev.data
        merged: Dict[str, Any] = {}
        for pid in sorted(parents):
            merged[pid] = results_by_id[pid].data
        return merged

    async def run(
        self,
        schema: WorkflowSchema,
        context: ExecutionContext,
        *,
        initial_input: Any = None,
        progress_callback: Callable[[str, NodeResult, Dict[str, NodeResult]], Awaitable[None] | None] | None = None,
        node_start_callback: Callable[[str, str, Any, Dict[str, NodeResult]], Awaitable[None] | None] | None = None,
        node_error_callback: Callable[[str, str, str, Dict[str, NodeResult]], Awaitable[None] | None] | None = None,
    ) -> Dict[str, Any]:
        """
        执行整个工作流。

        Returns:
            包含 ``success``、``node_results``（node_id -> NodeResult）、``error``（可选）。
        """
        node_by_id: Dict[str, Dict[str, Any]] = {}
        for spec in schema.nodes:
            node_by_id[str(spec["id"])] = spec

        order = self._topological_order(schema)
        results_by_id: Dict[str, NodeResult] = {}
        context.log(f"workflow {schema.workflow_id} 拓扑序: {order}")

        for nid in order:
            spec = node_by_id[nid]
            ntype = str(spec["type"])
            cfg = dict(spec.get("config") or {})
            try:
                node: BaseNode = self._registry.create_node(ntype, nid, cfg)
            except KeyError:
                if node_error_callback is not None:
                    try:
                        maybe = node_error_callback(nid, ntype, f"未注册的节点类型: {ntype}", dict(results_by_id))
                        if hasattr(maybe, "__await__"):
                            await maybe
                    except Exception:  # noqa: BLE001
                        pass
                return {
                    "success": False,
                    "error": f"未注册的节点类型: {ntype}",
                    "failed_node_id": nid,
                    "node_results": results_by_id,
                }

            inp = self._build_input(nid, schema, results_by_id, initial_input)
            context.log(f"执行节点 {nid} ({ntype})")
            if node_start_callback is not None:
                try:
                    maybe = node_start_callback(nid, ntype, inp, dict(results_by_id))
                    if hasattr(maybe, "__await__"):
                        await maybe
                except Exception:  # noqa: BLE001
                    pass
            try:
                result = await node.run(inp, context)
            except Exception as exc:  # noqa: BLE001 — 骨架捕获便于返回
                err = str(exc)
                context.log(f"节点 {nid} 异常: {err}")
                if node_error_callback is not None:
                    try:
                        maybe = node_error_callback(nid, ntype, err, dict(results_by_id))
                        if hasattr(maybe, "__await__"):
                            await maybe
                    except Exception:  # noqa: BLE001
                        pass
                return {
                    "success": False,
                    "error": err,
                    "failed_node_id": nid,
                    "node_results": results_by_id,
                }

            results_by_id[nid] = result
            if progress_callback is not None:
                try:
                    maybe = progress_callback(nid, result, dict(results_by_id))
                    if hasattr(maybe, "__await__"):
                        await maybe
                except Exception:  # noqa: BLE001
                    # 进度回调异常不应影响主执行流程。
                    pass
            if not result.success:
                context.log(f"节点 {nid} 返回 success=False: {result.error}")
                return {
                    "success": False,
                    "error": result.error or "节点失败",
                    "failed_node_id": nid,
                    "node_results": results_by_id,
                }

        return {"success": True, "node_results": results_by_id, "error": None}
