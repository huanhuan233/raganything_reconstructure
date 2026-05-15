/**
 * 工作流视图层类型：与后端契约一致的类型从全局 `ragWorkflow` 再导出，
 * 并补充画布侧别名便于组件引用。
 */

import type { RagFlowNodeData, RagNodeMetadata } from '@/types/ragWorkflow';

export type {
  RagFlowNodeData,
  RagNodeConfigField,
  RagNodeMetadata,
  RagRunHistoryDetail,
  RagRunHistorySummary,
  RagWorkflowRunPayload,
  RagWorkflowRunResult,
  RagWorkflowSavePayload,
  RagWorkflowStoredDocument,
  RagWorkflowSummary,
  RagWorkflowStoredNode
} from '@/types/ragWorkflow';

/** 画布节点 ``data`` */
export type FlowNodeData = RagFlowNodeData;

export interface PaletteGroup {
  key: string;
  title: string;
  items: RagNodeMetadata[];
}
