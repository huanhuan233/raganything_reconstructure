"""Runtime Trace 服务：事件发布、SSE 订阅、快照与节点详情读取。"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Deque, Dict, List

from .. import run_store

_MAX_HISTORY = 300
_HEARTBEAT_SECONDS = 10

_subscribers: Dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)
_histories: Dict[str, Deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=_MAX_HISTORY))
_seq: Dict[str, int] = defaultdict(int)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _to_json_safe(value: Any, *, max_chars: int = 8000) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value if len(value) <= max_chars else value[:max_chars]
    if isinstance(value, list):
        return [_to_json_safe(x, max_chars=max_chars) for x in value[:200]]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        n = 0
        for k, v in value.items():
            out[str(k)] = _to_json_safe(v, max_chars=max_chars)
            n += 1
            if n >= 200:
                break
        return out
    return str(value)


def publish_event(
    *,
    run_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """发布一条 runtime trace 事件到内存队列与历史缓存。"""
    _seq[run_id] += 1
    evt = {
        "seq": _seq[run_id],
        "ts": _utc_iso(),
        "run_id": run_id,
        "event_type": event_type,
        "payload": _to_json_safe(payload),
    }
    _histories[run_id].append(evt)
    dead: list[asyncio.Queue[dict[str, Any]]] = []
    for q in _subscribers.get(run_id, set()):
        try:
            q.put_nowait(evt)
        except Exception:  # noqa: BLE001
            dead.append(q)
    for q in dead:
        _subscribers[run_id].discard(q)
    return evt


def subscribe(run_id: str) -> asyncio.Queue[dict[str, Any]]:
    q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=200)
    _subscribers[run_id].add(q)
    return q


def unsubscribe(run_id: str, q: asyncio.Queue[dict[str, Any]]) -> None:
    _subscribers[run_id].discard(q)


def list_history(run_id: str) -> list[dict[str, Any]]:
    return list(_histories.get(run_id, []))


def _build_node_states_from_record(record: dict[str, Any]) -> list[dict[str, Any]]:
    request_snapshot = record.get("request_snapshot")
    req_nodes = (request_snapshot or {}).get("nodes") if isinstance(request_snapshot, dict) else None
    node_results = record.get("node_results") if isinstance(record.get("node_results"), dict) else {}
    trace_nodes = record.get("trace_nodes") if isinstance(record.get("trace_nodes"), dict) else {}
    current_node_id = str(record.get("current_node_id") or "")
    running = bool(record.get("running"))
    failed_node_id = str(record.get("failed_node_id") or "")

    states: list[dict[str, Any]] = []
    seen: set[str] = set()

    if isinstance(req_nodes, list):
        for one in req_nodes:
            if not isinstance(one, dict):
                continue
            node_id = str(one.get("id") or "").strip()
            if not node_id:
                continue
            seen.add(node_id)
            node_type = str(one.get("type") or "").strip()
            node_name = str(one.get("label") or node_id)
            result = node_results.get(node_id)
            trace = trace_nodes.get(node_id) if isinstance(trace_nodes.get(node_id), dict) else {}
            status = "pending"
            error = None
            if isinstance(trace, dict) and trace.get("status"):
                status = str(trace.get("status"))
            elif isinstance(result, dict):
                status = "success" if bool(result.get("success")) else "error"
                error = result.get("error")
            if running and current_node_id and node_id == current_node_id:
                status = "running"
            if failed_node_id and node_id == failed_node_id:
                status = "error"
                if isinstance(result, dict):
                    error = result.get("error")
            states.append(
                {
                    "node_id": node_id,
                    "node_name": node_name,
                    "node_type": node_type,
                    "status": status,
                    "start_time": trace.get("start_time"),
                    "end_time": trace.get("end_time"),
                    "duration_ms": trace.get("duration_ms"),
                    "error": error or trace.get("error"),
                    "summary": trace.get("summary") if isinstance(trace.get("summary"), dict) else {},
                    "input_preview": trace.get("input_preview"),
                    "output_preview": trace.get("output_preview"),
                }
            )

    for node_id, result in node_results.items():
        if node_id in seen:
            continue
        if not isinstance(result, dict):
            continue
        trace = trace_nodes.get(node_id) if isinstance(trace_nodes.get(node_id), dict) else {}
        states.append(
            {
                "node_id": node_id,
                "node_name": node_id,
                "node_type": str((trace or {}).get("node_type") or ""),
                "status": "success" if bool(result.get("success")) else "error",
                "start_time": trace.get("start_time"),
                "end_time": trace.get("end_time"),
                "duration_ms": trace.get("duration_ms"),
                "error": result.get("error") or trace.get("error"),
                "summary": trace.get("summary") if isinstance(trace.get("summary"), dict) else {},
                "input_preview": trace.get("input_preview"),
                "output_preview": trace.get("output_preview"),
            }
        )
    return states


def get_snapshot(run_id: str) -> dict[str, Any] | None:
    record = run_store.load_record(run_id)
    if not isinstance(record, dict):
        return None
    return {
        "run_id": run_id,
        "workflow_id": str(record.get("workflow_id") or ""),
        "workflow_name": str(record.get("workflow_name") or ""),
        "running": bool(record.get("running")),
        "phase": str(record.get("phase") or ("completed" if bool(record.get("success")) else "failed")),
        "success": bool(record.get("success")),
        "error": record.get("error"),
        "failed_node_id": record.get("failed_node_id"),
        "current_node_id": record.get("current_node_id"),
        "started_at": record.get("started_at"),
        "finished_at": record.get("finished_at"),
        "duration_ms": record.get("duration_ms"),
        "node_states": _build_node_states_from_record(record),
        "timeline": list(record.get("trace_timeline") or []),
    }


def get_node_detail(run_id: str, node_id: str) -> dict[str, Any] | None:
    record = run_store.load_record(run_id)
    if not isinstance(record, dict):
        return None
    node_results = record.get("node_results") if isinstance(record.get("node_results"), dict) else {}
    trace_nodes = record.get("trace_nodes") if isinstance(record.get("trace_nodes"), dict) else {}
    request_snapshot = record.get("request_snapshot") if isinstance(record.get("request_snapshot"), dict) else {}
    nodes = request_snapshot.get("nodes") if isinstance(request_snapshot.get("nodes"), list) else []
    node_spec = None
    for one in nodes:
        if isinstance(one, dict) and str(one.get("id")) == node_id:
            node_spec = one
            break
    result = node_results.get(node_id) if isinstance(node_results.get(node_id), dict) else {}
    trace = trace_nodes.get(node_id) if isinstance(trace_nodes.get(node_id), dict) else {}
    if not node_spec and not result and not trace:
        return None
    return {
        "run_id": run_id,
        "node_id": node_id,
        "node_name": str((node_spec or {}).get("label") or node_id),
        "node_type": str((node_spec or {}).get("type") or (trace or {}).get("node_type") or ""),
        "status": str(trace.get("status") or ("success" if bool(result.get("success", False)) else "pending")),
        "start_time": trace.get("start_time"),
        "end_time": trace.get("end_time"),
        "duration_ms": trace.get("duration_ms"),
        "error": trace.get("error") or result.get("error"),
        "summary": trace.get("summary") if isinstance(trace.get("summary"), dict) else {},
        "input_preview": trace.get("input_preview"),
        "output_preview": trace.get("output_preview"),
        "input": trace.get("input"),
        "output": result.get("data"),
        "metadata": result.get("metadata") if isinstance(result.get("metadata"), dict) else {},
        "config": (node_spec or {}).get("config") if isinstance((node_spec or {}).get("config"), dict) else {},
    }


def _format_sse(event: dict[str, Any], *, event_name: str = "trace") -> str:
    payload = json.dumps(event, ensure_ascii=False)
    return f"event: {event_name}\nid: {event.get('seq', '')}\ndata: {payload}\n\n"


async def stream(run_id: str) -> AsyncIterator[str]:
    """SSE 流：先发历史，再发增量事件。"""
    q = subscribe(run_id)
    try:
        for evt in list_history(run_id):
            yield _format_sse(evt)
        snapshot = get_snapshot(run_id)
        if snapshot is not None:
            yield _format_sse({"run_id": run_id, "event_type": "snapshot", "payload": snapshot}, event_name="snapshot")
        while True:
            try:
                evt = await asyncio.wait_for(q.get(), timeout=_HEARTBEAT_SECONDS)
                yield _format_sse(evt)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
                snap = get_snapshot(run_id)
                if isinstance(snap, dict) and not bool(snap.get("running")):
                    break
    finally:
        unsubscribe(run_id, q)

