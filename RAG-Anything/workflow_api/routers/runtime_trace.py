"""运行时追踪接口（快照 + SSE + 节点详情）。"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from .. import run_store
from ..runtime_trace import service as trace_service
from ..schemas import RuntimeTraceNodeDetail, RuntimeTraceSnapshot

router = APIRouter(tags=["runtime-trace"])


@router.get("/runtime-trace/{run_id}", response_model=RuntimeTraceSnapshot)
async def get_runtime_trace(run_id: str) -> RuntimeTraceSnapshot:
    try:
        rid = run_store.validate_run_id(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    snap = await asyncio.to_thread(trace_service.get_snapshot, rid)
    if snap is None:
        raise HTTPException(status_code=404, detail="运行追踪不存在")
    return RuntimeTraceSnapshot.model_validate(snap)


@router.get("/runtime-trace/{run_id}/nodes/{node_id}", response_model=RuntimeTraceNodeDetail)
async def get_runtime_trace_node_detail(run_id: str, node_id: str) -> RuntimeTraceNodeDetail:
    try:
        rid = run_store.validate_run_id(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    detail = await asyncio.to_thread(trace_service.get_node_detail, rid, node_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="节点追踪不存在")
    return RuntimeTraceNodeDetail.model_validate(detail)


@router.get("/runtime-trace/{run_id}/stream")
async def stream_runtime_trace(run_id: str) -> StreamingResponse:
    try:
        run_store.validate_run_id(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return StreamingResponse(
        trace_service.stream(run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

