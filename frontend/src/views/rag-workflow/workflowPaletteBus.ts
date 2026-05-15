import type { RagWfEdgeInsertPayload } from './injectionKeys';

/** 边上中点「+」：与原 RagWfEdgeInsertPayload 一致 */
export type WorkflowPaletteFromEdge = { paletteSource: 'edge' } & RagWfEdgeInsertPayload;

/** 节点出口旁「+」：从指定节点拉出一条线到新节点 */
export type WorkflowPaletteFromHandle = {
  paletteSource: 'handle';
  sourceNodeId: string;
  anchorClientX: number;
  anchorClientY: number;
};

export type WorkflowPaletteOpenRequest = WorkflowPaletteFromEdge | WorkflowPaletteFromHandle;

type Handler = (p: WorkflowPaletteOpenRequest) => void;

let handler: Handler | null = null;

/** WorkflowCanvas：挂载注册，Unmount 清空（避免 EdgeLabelRenderer Teleport / 自定义节点挂载链导致 inject 失效） */
export function setWorkflowPaletteHandler(h: Handler | null) {
  handler = h;
}

export function requestWorkflowPalette(p: WorkflowPaletteOpenRequest) {
  handler?.(p);
}
