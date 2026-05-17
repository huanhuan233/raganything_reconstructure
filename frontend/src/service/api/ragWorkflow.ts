/** RAG 工作流后端（FastAPI `backend_api`）HTTP 封装。 */

import json5 from 'json5';
import type {
  RagNodeTypesResponse,
  RagRunHistoryDetail,
  RagRunHistoryListResponse,
  RagRuntimeTraceNodeDetail,
  RagRuntimeTraceSnapshot,
  RagWorkflowSourceUploadResult,
  RagWorkflowListResponse,
  RagWorkflowRunPayload,
  RagWorkflowRunResult,
  RagWorkflowSavePayload,
  RagWorkflowStoredDocument,
  RagWorkflowTemplateSummary
} from '@/types/ragWorkflow';
import { ragWorkflowRequest } from '../request';

/** 拉取可编排节点类型（对应 ``GET /api/nodes``）。 */
export function fetchRagNodeTypes() {
  return ragWorkflowRequest<RagNodeTypesResponse>({
    url: '/api/nodes',
    method: 'get',
    // 首屏可能与超大运行记录恢复并行；后端若被同步 JSON 短暂阻塞，避免 30s 误判失败
    timeout: 0
  });
}

/** 执行 DAG（``POST /api/workflows/run``）。 */
export function fetchRagWorkflowRun(payload: RagWorkflowRunPayload) {
  return ragWorkflowRequest<RagWorkflowRunResult>({
    url: '/api/workflows/run',
    method: 'post',
    data: payload,
    // 等待后端完成，不因前端超时提前失败（仅以后端真实结果为准）
    timeout: 0
  });
}

/** 上传本地源文件并返回可用 source_path。 */
export async function uploadRagWorkflowSource(file: File) {
  const form = new FormData();
  form.append('file', file);
  const path = '/api/workflows/upload-source';
  let url = path;
  if (import.meta.env.DEV) {
    url = `/proxy-rag${path}`;
  } else {
    let ragBase = '';
    try {
      const raw = String(import.meta.env.VITE_OTHER_SERVICE_BASE_URL || '{}');
      const parsed = json5.parse(raw) as { rag?: string };
      ragBase = String(parsed.rag || '');
    } catch {
      ragBase = '';
    }
    const base = ragBase || String(import.meta.env.VITE_SERVICE_BASE_URL || '');
    url = `${base}${path}`;
  }
  const resp = await fetch(url, {
    method: 'POST',
    body: form
  });
  if (!resp.ok) {
    let detail = '';
    try {
      const err = (await resp.json()) as { detail?: unknown };
      if (typeof err?.detail === 'string') detail = err.detail;
      else if (err?.detail !== undefined) detail = JSON.stringify(err.detail);
    } catch {
      detail = '';
    }
    throw new Error(detail || `上传失败(${resp.status})`);
  }
  return (await resp.json()) as RagWorkflowSourceUploadResult;
}

/** 保存画布到服务端 ``POST /api/workflows/save``。 */
export function fetchRagWorkflowSave(payload: RagWorkflowSavePayload) {
  return ragWorkflowRequest<RagWorkflowStoredDocument>({
    url: '/api/workflows/save',
    method: 'post',
    data: payload,
    timeout: 60000
  });
}

/** 已保存工作流列表 ``GET /api/workflows``。 */
export function fetchRagWorkflowList() {
  return ragWorkflowRequest<RagWorkflowListResponse>({ url: '/api/workflows', method: 'get', timeout: 30000 });
}

/** 读取单个工作流 ``GET /api/workflows/{workflow_id}``。 */
export function fetchRagWorkflowGet(workflowId: string) {
  return ragWorkflowRequest<RagWorkflowStoredDocument>({
    url: `/api/workflows/${encodeURIComponent(workflowId)}`,
    method: 'get',
    timeout: 30000
  });
}

/** 删除工作流 ``DELETE /api/workflows/{workflow_id}``。 */
export function fetchRagWorkflowDelete(workflowId: string) {
  return ragWorkflowRequest<void>({
    url: `/api/workflows/${encodeURIComponent(workflowId)}`,
    method: 'delete'
  });
}

/** 默认模板列表 ``GET /api/workflows/templates``。 */
export function fetchRagWorkflowTemplates() {
  return ragWorkflowRequest<RagWorkflowTemplateSummary[]>({
    url: '/api/workflows/templates',
    method: 'get',
    timeout: 30000
  });
}

/** 默认模板详情 ``GET /api/workflows/templates/{template_id}``。 */
export function fetchRagWorkflowTemplateGet(templateId: string) {
  return ragWorkflowRequest<RagWorkflowStoredDocument>({
    url: `/api/workflows/templates/${encodeURIComponent(templateId)}`,
    method: 'get',
    timeout: 30000
  });
}

/** 运行记录列表 ``GET /api/workflows/runs`` */
export function fetchRagWorkflowRuns(workflowId?: string) {
  return ragWorkflowRequest<RagRunHistoryListResponse>({
    url: '/api/workflows/runs',
    method: 'get',
    params: workflowId?.trim() ? { workflow_id: workflowId.trim() } : {}
  });
}

/** 单次运行详情 ``GET /api/workflows/runs/{run_id}`` */
export function fetchRagWorkflowRunDetail(runId: string) {
  return ragWorkflowRequest<RagRunHistoryDetail>({
    url: `/api/workflows/runs/${encodeURIComponent(runId)}`,
    method: 'get',
    timeout: 0
  });
}

/** 删除运行记录 ``DELETE /api/workflows/runs/{run_id}`` */
export function fetchRagWorkflowRunDelete(runId: string) {
  return ragWorkflowRequest<void>({
    url: `/api/workflows/runs/${encodeURIComponent(runId)}`,
    method: 'delete'
  });
}

/** 运行时追踪快照 ``GET /api/runtime-trace/{run_id}`` */
export function fetchRagRuntimeTrace(runId: string) {
  return ragWorkflowRequest<RagRuntimeTraceSnapshot>({
    url: `/api/runtime-trace/${encodeURIComponent(runId)}`,
    method: 'get'
  });
}

/** 运行时追踪节点详情 ``GET /api/runtime-trace/{run_id}/nodes/{node_id}`` */
export function fetchRagRuntimeTraceNodeDetail(runId: string, nodeId: string) {
  return ragWorkflowRequest<RagRuntimeTraceNodeDetail>({
    url: `/api/runtime-trace/${encodeURIComponent(runId)}/nodes/${encodeURIComponent(nodeId)}`,
    method: 'get'
  });
}

/** 运行时追踪 SSE 地址 ``GET /api/runtime-trace/{run_id}/stream`` */
export function getRagRuntimeTraceStreamUrl(runId: string) {
  const path = `/api/runtime-trace/${encodeURIComponent(runId)}/stream`;
  if (import.meta.env.DEV) {
    return `/proxy-rag${path}`;
  }
  let ragBase = '';
  try {
    const raw = String(import.meta.env.VITE_OTHER_SERVICE_BASE_URL || '{}');
    const parsed = json5.parse(raw) as { rag?: string };
    ragBase = String(parsed.rag || '');
  } catch {
    ragBase = '';
  }
  const base = ragBase || String(import.meta.env.VITE_SERVICE_BASE_URL || '');
  return `${base}${path}`;
}
