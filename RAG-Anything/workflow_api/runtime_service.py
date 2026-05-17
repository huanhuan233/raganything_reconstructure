"""
封装 ``backend_runtime``：`get_default_registry`、`WorkflowRunner`、``ExecutionContext``。
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.graph_engine.workflow_runner import WorkflowRunner
from runtime_kernel.graph.workflow_schema import WorkflowSchema
from runtime_kernel.node_runtime.node_registry import get_default_registry
from runtime_kernel.entities.node_result import NodeResult
from runtime_kernel.runtime_state.payload_slim import strip_visual_heavy_for_export

from .raganything_runtime import build_adapters_for_request
from . import run_store
from .runtime_trace import service as runtime_trace_service
from .schemas import (
    SerializedNodeResult,
    WorkflowRunRequest,
    WorkflowRunResponse,
    workflow_nodes_to_runner_dicts,
)


def get_available_nodes() -> List[Dict[str, Any]]:
    """列出默认 ``NodeRegistry`` 中全部已注册节点的元数据 dict（升序）。"""
    return get_default_registry().list_nodes()


def _key_suggests_vector_field(key: str | None) -> bool:
    if not key:
        return False
    lk = str(key).lower()
    return "vector" in lk or "embedding" in lk


def _is_uniform_number_list(value: list[Any]) -> bool:
    if not value:
        return False
    for x in value:
        if isinstance(x, bool) or not isinstance(x, (int, float)):
            return False
    return True


def _omit_vector_floats_placeholder(dim: int) -> dict[str, Any]:
    return {"_omitted": "vector_floats", "dim": int(dim)}


def strip_vector_floats_for_storage(value: Any, *, key: str | None = None) -> Any:
    """
    去掉大块浮点向量，缩小运行记录 / HTTP 响应体积，避免 UI 渲染巨量数字。

    规则：字段名含 vector/embedding 的数值列表一律省略；其它无名列表仅当长度 >= 192
    且元素全为数字时视为向量省略（常见 embedding 维度均 >= 192）。
    """
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, dict):
        try:
            return {str(k): strip_vector_floats_for_storage(v, key=str(k)) for k, v in value.items()}
        except Exception:  # noqa: BLE001
            return str(value)
    if isinstance(value, list):
        if _is_uniform_number_list(value):
            dim = len(value)
            if _key_suggests_vector_field(key) or dim >= 192:
                return _omit_vector_floats_placeholder(dim)
            return value
        try:
            return [strip_vector_floats_for_storage(x, key=None) for x in value]
        except Exception:  # noqa: BLE001
            return str(value)
    return str(value)


def _should_strip_visual_heavy_for_run_export() -> bool:
    """
    落盘 / HTTP 的 node_results 默认会缩略 routes 等大字段以减小体积。
    若需将完整 data 写入 runs/*.json（例如复制给「自 chunk.split 起跑」的 input_data），在 .env 设：
    WORKFLOW_RUN_STRIP_VISUAL_HEAVY=0
    """
    v = str(os.getenv("WORKFLOW_RUN_STRIP_VISUAL_HEAVY", "1") or "1").strip().lower()
    return v not in {"0", "false", "no", "off"}


def _serialize_node_results(
    raw: Dict[str, NodeResult],
) -> Dict[str, SerializedNodeResult]:
    def _sanitize(value: Any) -> Any:
        """尽量返回 JSON 兼容结构；无法实现时退化为 str。"""
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            try:
                return {str(k): _sanitize(v) for k, v in value.items()}
            except Exception:  # noqa: BLE001
                return str(value)
        if isinstance(value, list):
            try:
                return [_sanitize(x) for x in value]
            except Exception:  # noqa: BLE001
                return str(value)
        return str(value)

    out: Dict[str, SerializedNodeResult] = {}
    for nid, nr in raw.items():
        meta = dict(nr.metadata or {})
        data_stripped = strip_vector_floats_for_storage(nr.data)
        if _should_strip_visual_heavy_for_run_export():
            data_stripped = strip_visual_heavy_for_export(data_stripped)
        out[nid] = SerializedNodeResult(
            success=nr.success,
            data=_sanitize(data_stripped),
            error=nr.error,
            metadata=_sanitize(strip_vector_floats_for_storage(meta)) if isinstance(meta, dict) else {},
        )
    return out


def _edges_as_tuples(edges: List[List[str]]) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    for e in edges:
        if len(e) != 2:
            raise ValueError(f"每条边必须恰好包含两个节点 id，收到: {e!r}")
        pairs.append((str(e[0]), str(e[1])))
    return pairs


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _preview(value: Any, *, max_chars: int = 1600) -> Any:
    value = strip_vector_floats_for_storage(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value if len(value) <= max_chars else value[:max_chars]
    if isinstance(value, list):
        return [_preview(x, max_chars=max_chars) for x in value[:30]]
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for idx, (k, v) in enumerate(value.items()):
            out[str(k)] = _preview(v, max_chars=max_chars)
            if idx >= 29:
                break
        return out
    return str(value)


def _parse_iso(ts: Any) -> datetime | None:
    s = str(ts or "").strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


def _duration_ms(start_ts: str | None, end_ts: str | None) -> int | None:
    sdt = _parse_iso(start_ts)
    edt = _parse_iso(end_ts)
    if sdt is None or edt is None:
        return None
    return max(0, int((edt - sdt).total_seconds() * 1000))


def _node_summary(node_type: str, data: Any, metadata: Any) -> Dict[str, Any]:
    d = data if isinstance(data, dict) else {}
    m = metadata if isinstance(metadata, dict) else {}
    summary: Dict[str, Any] = {}

    if isinstance(d.get("process_summary"), dict):
        ps = d["process_summary"]
        summary["processed_count"] = ps.get("processed_count")
        summary["vlm_used_count"] = ps.get("vlm_used_count")

    if isinstance(d.get("chunk_summary"), dict):
        cs = d["chunk_summary"]
        summary["total_chunks"] = cs.get("total_chunks")
        summary["input_items"] = cs.get("input_items")

    if isinstance(d.get("embedding_summary"), dict):
        es = d["embedding_summary"]
        summary["embedding_total"] = es.get("total_records")
        summary["with_vector"] = es.get("with_vector")
        summary["without_vector"] = es.get("without_vector")

    if isinstance(d.get("entity_relation_summary"), dict):
        er = d["entity_relation_summary"]
        summary["entity_count"] = er.get("entity_count")
        summary["relation_count"] = er.get("relation_count")

    if node_type == "industrial.structure_recognition":
        composite = d.get("composite_structure")
        parser_trace = (composite or {}).get("parser_trace") if isinstance(composite, dict) else []
        summary["parser_count"] = len(parser_trace) if isinstance(parser_trace, list) else 0
        summary["title_parser"] = any(
            isinstance(x, dict) and str(x.get("name", "")).strip() == "title_hierarchy"
            for x in (parser_trace if isinstance(parser_trace, list) else [])
        )
        summary["process_parser"] = any(
            isinstance(x, dict) and str(x.get("name", "")).strip() == "process_flow"
            for x in (parser_trace if isinstance(parser_trace, list) else [])
        )
        summary["table_parser"] = any(
            isinstance(x, dict) and str(x.get("name", "")).strip() == "table_structure"
            for x in (parser_trace if isinstance(parser_trace, list) else [])
        )

    if node_type == "industrial.constraint_extract":
        constraints = d.get("constraints")
        validation = d.get("validation")
        summary["constraint_count"] = len(constraints) if isinstance(constraints, list) else 0
        if isinstance(validation, dict):
            errs = validation.get("errors")
            summary["invalid_constraints"] = len(errs) if isinstance(errs, list) else 0

    if node_type == "industrial.graph_build":
        graph = d.get("graph")
        if isinstance(graph, dict):
            nodes = graph.get("nodes")
            edges = graph.get("edges")
            summary["graph_node_count"] = len(nodes) if isinstance(nodes, list) else 0
            summary["graph_edge_count"] = len(edges) if isinstance(edges, list) else 0
        summary["namespace"] = m.get("namespace")

    if node_type == "industrial.graph.persist":
        ps = d.get("graph_persist_summary")
        if isinstance(ps, dict):
            summary["node_persisted"] = ps.get("node_persisted")
            summary["edge_persisted"] = ps.get("edge_persisted")
            summary["native_labels"] = ps.get("native_labels")
            summary["typed_relationships"] = ps.get("typed_relationships")

    return {k: v for k, v in summary.items() if v is not None}


async def run_workflow(request: WorkflowRunRequest) -> WorkflowRunResponse:
    """
    使用默认注册表与工作流拓扑执行 DAG。

    ``context.adapters``：当 DAG 含 ``raganything.insert``（且配置路径）或
    ``rag.query``（``engine=raganything``）时，惰性注入共享 ``RAGAnythingEngineAdapter``。

    每次返回前将运行结果写入 ``backend_api/storage/runs/{run_id}.json``（失败不影响 HTTP 响应）。
    """
    req_run_id = str(request.run_id or "").strip().lower()
    if req_run_id:
        run_id = run_store.validate_run_id(req_run_id)
    else:
        run_id = uuid.uuid4().hex[:16]
    started_at = _utc_iso()
    t0 = time.perf_counter()
    ctx: ExecutionContext | None = None
    workflow_name = run_store.resolve_workflow_name(request.workflow_id.strip())
    node_type_map: Dict[str, str] = {str(n.node_id): str(n.type) for n in request.nodes}
    trace_nodes: Dict[str, Dict[str, Any]] = {}
    trace_timeline: List[Dict[str, Any]] = []
    try:
        request_snapshot: Dict[str, Any] = request.model_dump(mode="json", by_alias=True)
    except Exception:  # noqa: BLE001
        request_snapshot = {"workflow_id": request.workflow_id}

    def _ensure_trace_node(node_id: str, node_type: str) -> Dict[str, Any]:
        node = trace_nodes.get(node_id)
        if isinstance(node, dict):
            return node
        node_name = node_id
        req_nodes = request_snapshot.get("nodes")
        if isinstance(req_nodes, list):
            for one in req_nodes:
                if not isinstance(one, dict):
                    continue
                if str(one.get("id") or "") == node_id:
                    node_name = str(one.get("label") or node_id)
                    break
        node = {
            "node_id": node_id,
            "node_name": node_name,
            "node_type": node_type,
            "status": "pending",
            "start_time": None,
            "end_time": None,
            "duration_ms": None,
            "error": None,
            "summary": {},
            "input_preview": None,
            "output_preview": None,
            "input": None,
        }
        trace_nodes[node_id] = node
        return node

    def _publish_event(event_type: str, payload: Dict[str, Any]) -> None:
        runtime_trace_service.publish_event(run_id=run_id, event_type=event_type, payload=payload)

    def _save_progress_record(
        *,
        node_results_json: Dict[str, Any],
        success: bool,
        error: str | None,
        failed_node_id: str | None,
        logs: list[str],
        phase: str,
        current_node_id: str | None = None,
    ) -> None:
        """运行中增量落盘；失败不影响主流程。"""
        now = _utc_iso()
        record: Dict[str, Any] = {
            "run_id": run_id,
            "workflow_id": request.workflow_id,
            "workflow_name": workflow_name,
            "success": success,
            "running": phase == "running",
            "phase": phase,
            "current_node_id": current_node_id,
            "started_at": started_at,
            "finished_at": None if phase == "running" else now,
            "duration_ms": int((time.perf_counter() - t0) * 1000),
            "error": error,
            "failed_node_id": failed_node_id,
            "node_results": node_results_json,
            "logs": list(logs),
            "request_snapshot": request_snapshot,
            "trace_nodes": trace_nodes,
            "trace_timeline": trace_timeline,
        }
        try:
            run_store.save_run_record(record)
        except Exception:  # noqa: BLE001
            pass

    resp: WorkflowRunResponse | None = None
    try:
        adapters = await build_adapters_for_request(request)
        ctx = ExecutionContext(
            workflow_id=request.workflow_id,
            run_id=run_id,
            workspace="",
            adapters=adapters,
            shared_data={},
            logs=[],
        )
        _save_progress_record(
            node_results_json={},
            success=False,
            error=None,
            failed_node_id=None,
            logs=list(ctx.logs),
            phase="running",
            current_node_id=None,
        )
        _publish_event(
            "run_start",
            {
                "run_id": run_id,
                "workflow_id": request.workflow_id,
                "started_at": started_at,
            },
        )
        runner = WorkflowRunner(registry=get_default_registry())
        schema = WorkflowSchema(
            workflow_id=request.workflow_id,
            nodes=workflow_nodes_to_runner_dicts(request.nodes),
            edges=_edges_as_tuples(request.edges),
            entry_node_ids=list(request.entry_node_ids),
        )

        async def _on_node_start(nid: str, ntype: str, inp: Any, _partial: Dict[str, NodeResult]) -> None:
            now = _utc_iso()
            node = _ensure_trace_node(nid, ntype)
            node["status"] = "running"
            node["start_time"] = now
            node["end_time"] = None
            node["duration_ms"] = None
            node["error"] = None
            node["input_preview"] = _preview(inp)
            node["input"] = _preview(inp, max_chars=24000)
            _publish_event(
                "node_start",
                {
                    "run_id": run_id,
                    "node_id": nid,
                    "node_name": node.get("node_name"),
                    "node_type": ntype,
                    "status": "running",
                    "start_time": now,
                    "input_preview": node.get("input_preview"),
                },
            )
            nr_json = {
                k: v.model_dump(mode="json")
                for k, v in _serialize_node_results(_partial).items()
            }
            _save_progress_record(
                node_results_json=nr_json,
                success=False,
                error=None,
                failed_node_id=None,
                logs=list(ctx.logs),
                phase="running",
                current_node_id=nid,
            )

        async def _on_node_error(nid: str, ntype: str, err: str, partial: Dict[str, NodeResult]) -> None:
            now = _utc_iso()
            node = _ensure_trace_node(nid, ntype)
            node["status"] = "error"
            node["end_time"] = now
            node["duration_ms"] = _duration_ms(node.get("start_time"), now)
            node["error"] = err
            trace_timeline.append(
                {
                    "node_id": nid,
                    "node_type": ntype,
                    "status": "error",
                    "start_time": node.get("start_time"),
                    "end_time": now,
                    "duration_ms": node.get("duration_ms"),
                }
            )
            _publish_event(
                "node_error",
                {
                    "run_id": run_id,
                    "node_id": nid,
                    "node_name": node.get("node_name"),
                    "node_type": ntype,
                    "status": "error",
                    "start_time": node.get("start_time"),
                    "end_time": now,
                    "duration_ms": node.get("duration_ms"),
                    "error": err,
                },
            )
            nr_json = {
                k: v.model_dump(mode="json")
                for k, v in _serialize_node_results(partial).items()
            }
            _save_progress_record(
                node_results_json=nr_json,
                success=False,
                error=err,
                failed_node_id=nid,
                logs=list(ctx.logs),
                phase="running",
                current_node_id=nid,
            )

        async def _progress(nid: str, _nr: NodeResult, partial: Dict[str, NodeResult]) -> None:
            now = _utc_iso()
            node_type = node_type_map.get(nid, "")
            node = _ensure_trace_node(nid, node_type)
            node["status"] = "success" if _nr.success else "error"
            node["end_time"] = now
            node["duration_ms"] = _duration_ms(node.get("start_time"), now)
            node["error"] = _nr.error
            node["summary"] = _node_summary(node_type, _nr.data, _nr.metadata)
            node["output_preview"] = _preview(_nr.data)
            trace_timeline.append(
                {
                    "node_id": nid,
                    "node_type": node_type,
                    "status": node["status"],
                    "start_time": node.get("start_time"),
                    "end_time": now,
                    "duration_ms": node.get("duration_ms"),
                }
            )
            _publish_event(
                "node_end",
                {
                    "run_id": run_id,
                    "node_id": nid,
                    "node_name": node.get("node_name"),
                    "node_type": node_type,
                    "status": node["status"],
                    "start_time": node.get("start_time"),
                    "end_time": now,
                    "duration_ms": node.get("duration_ms"),
                    "summary": node.get("summary"),
                    "output_preview": node.get("output_preview"),
                    "error": _nr.error,
                },
            )
            nr_json = {k: v.model_dump(mode="json") for k, v in _serialize_node_results(partial).items()}
            _save_progress_record(
                node_results_json=nr_json,
                success=False,
                error=_nr.error if not _nr.success else None,
                failed_node_id=nid if not _nr.success else None,
                logs=list(ctx.logs),
                phase="running",
                current_node_id=nid,
            )

        raw = await runner.run(
            schema,
            ctx,
            initial_input=request.input_data,
            progress_callback=_progress,
            node_start_callback=_on_node_start,
            node_error_callback=_on_node_error,
        )
        node_results = _serialize_node_results(raw.get("node_results") or {})
        resp = WorkflowRunResponse(
            success=bool(raw.get("success")),
            workflow_id=request.workflow_id,
            run_id=run_id,
            error=raw.get("error"),
            failed_node_id=raw.get("failed_node_id"),
            node_results=node_results,
            logs=list(ctx.logs),
        )
    except asyncio.CancelledError:
        _publish_event(
            "run_error",
            {
                "run_id": run_id,
                "workflow_id": request.workflow_id,
                "error": "workflow run cancelled (interrupted)",
            },
        )
        resp = WorkflowRunResponse(
            success=False,
            workflow_id=request.workflow_id,
            run_id=run_id,
            error="workflow run cancelled (interrupted)",
            failed_node_id=None,
            node_results={},
            logs=list(ctx.logs) if ctx is not None else [],
        )
        raise
    except Exception as exc:  # noqa: BLE001
        _publish_event(
            "run_error",
            {
                "run_id": run_id,
                "workflow_id": request.workflow_id,
                "error": str(exc),
            },
        )
        resp = WorkflowRunResponse(
            success=False,
            workflow_id=request.workflow_id,
            run_id=run_id,
            error=str(exc),
            failed_node_id=None,
            node_results={},
            logs=list(ctx.logs) if ctx is not None else [],
        )
    finally:
        if resp is None:
            resp = WorkflowRunResponse(
                success=False,
                workflow_id=request.workflow_id,
                run_id=run_id,
                error="workflow run ended without response (internal)",
                failed_node_id=None,
                node_results={},
                logs=list(ctx.logs) if ctx is not None else [],
            )
        finished_at = _utc_iso()
        duration_ms = int((time.perf_counter() - t0) * 1000)
        nr_json = {k: v.model_dump(mode="json") for k, v in resp.node_results.items()}
        record: Dict[str, Any] = {
            "run_id": resp.run_id,
            "workflow_id": resp.workflow_id,
            "workflow_name": workflow_name,
            "success": resp.success,
            "running": False,
            "phase": "completed" if resp.success else "failed",
            "current_node_id": None,
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": duration_ms,
            "error": resp.error,
            "failed_node_id": resp.failed_node_id,
            "node_results": nr_json,
            "logs": list(resp.logs),
            "request_snapshot": request_snapshot,
            "trace_nodes": trace_nodes,
            "trace_timeline": trace_timeline,
        }
        try:
            run_store.save_run_record(record)
        except Exception:  # noqa: BLE001
            pass
        _publish_event(
            "run_end",
            {
                "run_id": run_id,
                "workflow_id": request.workflow_id,
                "success": resp.success,
                "error": resp.error,
                "failed_node_id": resp.failed_node_id,
                "finished_at": finished_at,
                "duration_ms": duration_ms,
            },
        )

    return resp
