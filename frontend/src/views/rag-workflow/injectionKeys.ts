/** Edge 中点「+」拆边插入时的拓扑上下文（经 workflowPaletteBus 上传，避免 Teleport 打断 provide/inject） */
export type RagWfEdgeInsertPayload = {
  edgeId: string;
  source: string;
  target: string;
  flowMidX: number;
  flowMidY: number;
  anchorClientX: number;
  anchorClientY: number;
};
