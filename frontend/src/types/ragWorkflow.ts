/**
 * backend_runtime / backend_api（FastAPI）工作流载荷类型，
 * 与 ``WorkflowSchema`` + ``WorkflowRunResponse`` JSON 对齐。
 */

/** 节点 config 表单项（与 backend NodeConfigField 对齐） */
export interface RagNodeConfigField {
  name: string;
  label: string;
  type: string;
  required?: boolean;
  advanced?: boolean;
  default?: unknown;
  options?: unknown[] | null;
  placeholder?: string | null;
  description?: string | null;
}

/** GET /api/nodes 单项 */
export type RagNodeImplementationStatus = 'real' | 'partial' | 'placeholder';

export interface RagNodeMetadata {
  node_type: string;
  display_name: string;
  category: string;
  description: string;
  implementation_status: RagNodeImplementationStatus;
  is_placeholder: boolean;
  config_fields: RagNodeConfigField[];
  input_schema?: Record<string, unknown> | null;
  output_schema?: Record<string, unknown> | null;
}

/** GET /api/nodes */
export interface RagNodeTypesResponse {
  nodes: RagNodeMetadata[];
  /** 与 nodes[].node_type 一致，升序；兼容旧客户端 */
  node_types: string[];
}

/** 提交给后端单步节点描述（等价于 pydantic WorkflowNodeSpec，字段 id） */
export interface RagWorkflowSubmitNode {
  id: string;
  type: string;
  config: Record<string, unknown>;
}

/** POST /api/workflows/run 请求体 */
export interface RagWorkflowRunPayload {
  workflow_id: string;
  nodes: RagWorkflowSubmitNode[];
  edges: [string, string][];
  entry_node_ids: string[];
  /** 入口初始数据（任意 JSON）；常作为首节点 upstream */
  input_data: unknown | null;
  /** 可选：客户端预生成 run_id，便于实时追踪提前订阅 */
  run_id?: string;
}

/** 单次节点执行快照（等价 SerializedNodeResult） */
export interface RagSerializedNodeResult {
  success: boolean;
  data: unknown;
  error: string | null;
  metadata: Record<string, unknown>;
}

/** GET /api/workflows 列表项 */
export interface RagWorkflowSummary {
  workflow_id: string;
  name: string;
  description?: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface RagWorkflowListResponse {
  workflows: RagWorkflowSummary[];
}

export interface RagWorkflowTemplateSummary {
  template_id: string;
  name: string;
  description: string;
}

/** POST /api/workflows/save 与 GET /api/workflows/{id} 文档体 */
export interface RagWorkflowStoredDocument {
  workflow_id: string;
  name: string;
  description?: string;
  nodes: RagWorkflowStoredNode[];
  edges: [string, string][];
  entry_node_ids: string[];
  input_data: unknown | null;
  created_at: string;
  updated_at: string;
}

/** 保存的节点（含画布字段时带 position / label） */
export interface RagWorkflowStoredNode extends Record<string, unknown> {
  id: string;
  type: string;
  config: Record<string, unknown>;
}

/** POST /api/workflows/save 请求 */
export interface RagWorkflowSavePayload {
  workflow_id: string;
  name: string;
  description: string;
  nodes: RagWorkflowStoredNode[];
  edges: [string, string][];
  entry_node_ids: string[];
  input_data: unknown | null;
}

/** POST /api/workflows/run 响应 */
export interface RagWorkflowRunResult {
  success: boolean;
  workflow_id: string;
  run_id: string;
  error: string | null;
  failed_node_id: string | null;
  node_results: Record<string, RagSerializedNodeResult>;
  logs: string[];
  running?: boolean;
  phase?: string;
  current_node_id?: string | null;
}

/** GET /api/workflows/runs 列表项 */
export interface RagRunHistorySummary {
  run_id: string;
  workflow_id: string;
  workflow_name?: string;
  success: boolean;
  duration_ms?: number | null;
  started_at?: string | null;
  finished_at?: string | null;
  failed_node_id?: string | null;
  error?: string | null;
}

export interface RagRunHistoryListResponse {
  runs: RagRunHistorySummary[];
}

/** GET /api/workflows/runs/{run_id} */
export interface RagRunHistoryDetail {
  run_id: string;
  workflow_id: string;
  workflow_name?: string;
  success: boolean;
  running?: boolean;
  phase?: string;
  current_node_id?: string | null;
  duration_ms?: number | null;
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
  failed_node_id?: string | null;
  node_results: Record<string, unknown>;
  logs: unknown[];
  request_snapshot?: unknown;
  trace_nodes?: Record<string, unknown>;
  trace_timeline?: Array<Record<string, unknown>>;
}

export type RagRuntimeTraceNodeStatus = 'pending' | 'running' | 'success' | 'error' | 'skipped';

export interface RagRuntimeTraceNodeState {
  node_id: string;
  node_name: string;
  node_type: string;
  status: RagRuntimeTraceNodeStatus;
  start_time?: string | null;
  end_time?: string | null;
  duration_ms?: number | null;
  error?: string | null;
  summary?: Record<string, unknown>;
  input_preview?: unknown;
  output_preview?: unknown;
}

export interface RagRuntimeTraceSnapshot {
  run_id: string;
  workflow_id: string;
  workflow_name?: string;
  running: boolean;
  phase?: string;
  success?: boolean;
  error?: string | null;
  failed_node_id?: string | null;
  current_node_id?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  duration_ms?: number | null;
  node_states: RagRuntimeTraceNodeState[];
  timeline?: Array<Record<string, unknown>>;
}

export interface RagRuntimeTraceNodeDetail {
  run_id: string;
  node_id: string;
  node_name: string;
  node_type: string;
  status: string;
  start_time?: string | null;
  end_time?: string | null;
  duration_ms?: number | null;
  error?: string | null;
  summary?: Record<string, unknown>;
  input_preview?: unknown;
  output_preview?: unknown;
  input?: unknown;
  output?: unknown;
  metadata?: Record<string, unknown>;
  config?: Record<string, unknown>;
}

export interface RagRuntimeTraceEvent {
  run_id: string;
  seq: number;
  ts: string;
  event_type: string;
  payload: Record<string, unknown>;
}

/**
 * Vue Flow 节点 ``data`` 载荷（与画布节点 id 分离；后端 id 使用 node.id）
 */
export interface RagFlowNodeData extends Record<string, unknown> {
  /** 画布展示标题 */
  label: string;
  /** backend_runtime 注册的 node_type */
  nodeType: string;
  /** 该步配置，提交为 WorkflowSchema.nodes[].config */
  config: Record<string, unknown>;
  /** 画布 UI：占位节点；不出现在 POST save/run 节点的扁平字段内，仅存于画布 data */
  isPlaceholder?: boolean;
  /** 画布 UI：实现状态，驱动 badge（real / partial / placeholder） */
  implementationStatus?: RagNodeImplementationStatus;
}
