type Handler = (nodeId: string) => void;

let handler: Handler | null = null;

/** WorkflowCanvas 挂载时注册，Unmount 清空（与自定义节点内事件上报一致） */
export function setWorkflowNodeDeleteHandler(h: Handler | null) {
  handler = h;
}

export function requestDeleteWorkflowNode(nodeId: string) {
  handler?.(nodeId);
}
