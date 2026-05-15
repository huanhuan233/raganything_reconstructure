"""工作流执行与本地存储。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Response

from .. import run_store
from .. import workflow_store
from workflow_storage.workflows.default_workflows import (
    get_default_workflow_template,
    list_default_workflow_templates,
)
from ..runtime_service import run_workflow
from ..schemas import (
    ResumeCacheClearResponse,
    WorkflowListResponse,
    WorkflowRunHistoryDetail,
    WorkflowRunHistoryListResponse,
    WorkflowRunHistorySummary,
    WorkflowRunRequest,
    WorkflowRunResponse,
    WorkflowTemplateSummary,
    WorkflowSaveRequest,
    WorkflowStoredDocument,
    WorkflowSummary,
)

router = APIRouter(tags=["workflows"])


@router.post("/workflows/run", response_model=WorkflowRunResponse)
async def run_workflow_endpoint(body: WorkflowRunRequest) -> WorkflowRunResponse:
    """
    提交 DAG 并由 ``WorkflowRunner`` 执行。

    每次调用（成功或 Runner 内失败）都会在 ``storage/runs/{run_id}.json`` 留存记录。
    """
    try:
        return await run_workflow(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/workflows/save", response_model=WorkflowStoredDocument)
def save_workflow_endpoint(body: WorkflowSaveRequest) -> WorkflowStoredDocument:
    """将画布 JSON 保存到 ``backend_api/storage/workflows/{workflow_id}.json``。"""
    try:
        doc = workflow_store.save_document(
            workflow_id=body.workflow_id,
            name=body.name,
            description=body.description,
            nodes=body.nodes,
            edges=body.edges,
            entry_node_ids=body.entry_node_ids,
            input_data=body.input_data,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WorkflowStoredDocument.model_validate(doc)


@router.get("/workflows/runs", response_model=WorkflowRunHistoryListResponse)
def list_run_history(
    workflow_id: Optional[str] = Query(None, description="可选，仅列出该 workflow_id 的运行记录"),
) -> WorkflowRunHistoryListResponse:
    """列出本地保存的运行记录摘要（按 ``started_at`` 降序）。"""
    raw = run_store.list_summaries(workflow_id=workflow_id)
    return WorkflowRunHistoryListResponse(
        runs=[WorkflowRunHistorySummary.model_validate(x) for x in raw]
    )


@router.get("/workflows/runs/{run_id}", response_model=WorkflowRunHistoryDetail)
def get_run_history(run_id: str) -> WorkflowRunHistoryDetail:
    """读取单次运行完整 JSON。"""
    try:
        run_store.validate_run_id(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    doc = run_store.load_record(run_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    return WorkflowRunHistoryDetail.model_validate(doc)


@router.delete("/workflows/runs/{run_id}", status_code=204)
def delete_run_history(run_id: str) -> Response:
    """删除运行记录文件。"""
    try:
        run_store.validate_run_id(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not run_store.delete_record(run_id):
        raise HTTPException(status_code=404, detail="运行记录不存在")
    return Response(status_code=204)


@router.delete("/workflows/resume-cache", response_model=ResumeCacheClearResponse)
def clear_resume_cache(
    cache_key: str = Query(..., description="节点 resume_cache_key；为空时返回 400"),
    scope: str = Query("all", description="清理范围：all / multimodal / embedding"),
) -> ResumeCacheClearResponse:
    """按 resume_cache_key 删除断点缓存文件。"""
    try:
        result = run_store.delete_resume_checkpoints(cache_key=cache_key, scope=scope)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ResumeCacheClearResponse.model_validate(result)


@router.get("/workflows", response_model=WorkflowListResponse)
def list_saved_workflows() -> WorkflowListResponse:
    """列出已保存的工作流摘要（按 ``updated_at`` 降序）。"""
    raw = workflow_store.list_summaries()
    return WorkflowListResponse(
        workflows=[WorkflowSummary.model_validate(x) for x in raw]
    )


@router.get("/workflows/templates", response_model=list[WorkflowTemplateSummary])
def list_workflow_templates() -> list[WorkflowTemplateSummary]:
    """列出默认工作流模板。"""
    raw = list_default_workflow_templates()
    return [WorkflowTemplateSummary.model_validate(x) for x in raw]


@router.get("/workflows/templates/{template_id}", response_model=WorkflowStoredDocument)
def get_workflow_template(template_id: str) -> WorkflowStoredDocument:
    """读取单个默认模板。"""
    try:
        doc = get_default_workflow_template(template_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="模板不存在") from exc
    return WorkflowStoredDocument.model_validate(doc)


@router.get("/workflows/{workflow_id}", response_model=WorkflowStoredDocument)
def get_saved_workflow(workflow_id: str) -> WorkflowStoredDocument:
    """读取单个已保存工作流。"""
    try:
        workflow_store.validate_workflow_id(workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    doc = workflow_store.load_document(workflow_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="工作流不存在")
    return WorkflowStoredDocument.model_validate(doc)


@router.delete("/workflows/{workflow_id}", status_code=204)
def delete_saved_workflow(workflow_id: str) -> Response:
    """删除已保存的工作流文件。"""
    try:
        workflow_store.validate_workflow_id(workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not workflow_store.delete_document(workflow_id):
        raise HTTPException(status_code=404, detail="工作流不存在")
    return Response(status_code=204)
