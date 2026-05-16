import type {
  RagRuntimeTraceEvent,
  RagRuntimeTraceNodeDetail,
  RagRuntimeTraceNodeState,
  RagRuntimeTraceSnapshot
} from '@/types/ragWorkflow';

export type RuntimeTraceTabKey = 'input' | 'output' | 'detail' | 'observatory' | 'trace';

export type RuntimeTraceNodeStatus = RagRuntimeTraceNodeState['status'];

export interface RuntimeTraceNodeCatalogItem {
  node_id: string;
  node_name: string;
  node_type: string;
}

export interface RuntimeTraceState {
  runId: string;
  workflowId: string;
  running: boolean;
  phase: string;
  currentNodeId: string | null;
  failedNodeId: string | null;
  startedAt: string | null;
  finishedAt: string | null;
  durationMs: number | null;
  error: string | null;
  nodes: RagRuntimeTraceNodeState[];
  timeline: Array<Record<string, unknown>>;
  selectedNodeId: string | null;
  selectedTab: RuntimeTraceTabKey;
  selectedNodeDetail: RagRuntimeTraceNodeDetail | null;
  panelCollapsed: boolean;
  panelWidth: number;
  autoScroll: boolean;
}

export type RuntimeTraceSnapshot = RagRuntimeTraceSnapshot;
export type RuntimeTraceNodeState = RagRuntimeTraceNodeState;
export type RuntimeTraceNodeDetail = RagRuntimeTraceNodeDetail;
export type RuntimeTraceEvent = RagRuntimeTraceEvent;

