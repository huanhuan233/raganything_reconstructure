import { nanoid } from '@sa/utils';
import type { Edge, Node } from '@vue-flow/core';
import type {
  RagFlowNodeData,
  RagNodeImplementationStatus,
  RagNodeMetadata,
  RagWorkflowRunPayload,
  RagWorkflowSavePayload,
  RagWorkflowStoredDocument
} from '@/types/ragWorkflow';
import { isrSemanticFieldsFromMeta } from '@/components/runtime/isrPalette';
import { safeParseJson5 } from './jsonHelper';

type SkinnyEdge = { source?: string; target?: string };
type SkinnyNode = { id?: string; data?: RagFlowNodeData };

function sanitizeNodeConfig(nodeType: string, config: Record<string, unknown>): Record<string, unknown> {
  const out = { ...config };
  // 兼容历史草稿：此前曾短暂引入 workflow.start.question，现已下线。
  if (nodeType === 'workflow.start') {
    delete out.question;
  }
  return out;
}

function resolveImplementationStatus(metaCatalog: RagNodeMetadata | undefined): RagNodeImplementationStatus {
  if (!metaCatalog) return 'real';
  return metaCatalog.implementation_status ?? (metaCatalog.is_placeholder ? 'placeholder' : 'real');
}

export function computeEntryNodeIds(nodes: SkinnyNode[], edges: SkinnyEdge[]): string[] {
  const targetIds = new Set(edges.map(e => String(e.target)));
  return nodes.filter(n => !targetIds.has(String(n.id))).map(n => String(n.id));
}

/** 画布 → ``POST /workflows/run`` 载荷 */
export function flowToRunPayload(
  nodes: Node[],
  edges: Edge[],
  workflowIdTrimmed: string,
  inputJsonText: string,
  fallbackWorkflowId = 'ui-dag'
): RagWorkflowRunPayload {
  const skinnyEdges = edges as unknown as SkinnyEdge[];
  const skinnyNodes = nodes as unknown as SkinnyNode[];

  const submitNodes = skinnyNodes.map(n => {
    const d = (n.data ?? {}) as RagFlowNodeData;
    const nodeType = String(d.nodeType ?? '');
    return {
      id: String(n.id),
      type: nodeType,
      config: sanitizeNodeConfig(nodeType, { ...(d.config ?? {}) })
    };
  });

  const ee: [string, string][] = skinnyEdges.map(e => [String(e.source), String(e.target)]);

  return {
    workflow_id: workflowIdTrimmed || fallbackWorkflowId,
    nodes: submitNodes,
    edges: ee,
    entry_node_ids: computeEntryNodeIds(skinnyNodes, skinnyEdges),
    input_data: safeParseJson5(inputJsonText)
  };
}

/** 画布 → ``POST /workflows/save`` 载荷（节点含 ``position`` / ``label``） */
export function flowToSavePayload(
  nodes: Node[],
  edges: Edge[],
  workflowIdTrimmed: string,
  workflowDisplayNameTrimmed: string,
  workflowDescriptionTrimmed: string,
  inputJsonText: string,
  fallbackWorkflowId = 'ui-dag'
): RagWorkflowSavePayload {
  const base = flowToRunPayload(nodes, edges, workflowIdTrimmed, inputJsonText, fallbackWorkflowId);
  const skinnyNodes = nodes as unknown as (SkinnyNode & {
    position?: { x: number; y: number };
    label?: string;
  })[];

  const enriched = skinnyNodes.map(n => {
    const d = (n.data ?? {}) as RagFlowNodeData;
    const nodeType = String(d.nodeType ?? '');
    const pos = (n as { position?: { x: number; y: number } }).position ?? { x: 80, y: 80 };
    const nl = (n as { label?: string }).label;
    return {
      id: String(n.id),
      type: nodeType,
      config: sanitizeNodeConfig(nodeType, { ...(d.config ?? {}) }),
      position: { x: pos.x, y: pos.y },
      label: String(nl ?? d.label ?? d.nodeType ?? '')
    };
  });

  const wid = base.workflow_id;
  return {
    workflow_id: wid,
    name: workflowDisplayNameTrimmed || wid,
    description: workflowDescriptionTrimmed,
    nodes: enriched,
    edges: base.edges,
    entry_node_ids: base.entry_node_ids,
    input_data: base.input_data
  };
}

export function normalizeRagVueFlowEdges(edges: Edge[]): Edge[] {
  return edges.map(e => {
    const c = e.class;
    const className =
      typeof c === 'string' && c.trim() !== ''
        ? c
        : Array.isArray(c) && c.length
          ? c.join(' ')
          : 'rag-wf-insert-bezier';
    return { ...e, type: 'ragWfInsert', class: className } as Edge;
  });
}

export function edgePairsToFlowEdges(pairs: unknown): Edge[] {
  if (!Array.isArray(pairs)) return [];
  const out: Edge[] = [];
  pairs.forEach((pair, i) => {
    if (!Array.isArray(pair) || pair.length < 2) return;
    const source = String(pair[0]);
    const target = String(pair[1]);
    out.push({
      id: `e_${source}_${target}_${i}`,
      source,
      target,
      type: 'ragWfInsert',
      class: 'rag-wf-insert-bezier'
    } as Edge);
  });
  return out;
}

/** 服务端保存的文档 → Vue Flow nodes */
export function storedNodesToFlowNodes(rawNodes: unknown[], paletteCatalog: RagNodeMetadata[]): Node[] {
  return rawNodes.map((raw, index) =>
    storedRecordToFlowNode(raw as Record<string, unknown>, index, paletteCatalog)
  ) as Node[];
}

export function storedRecordToFlowNode(
  raw: Record<string, unknown>,
  index: number,
  paletteCatalog: RagNodeMetadata[]
): Node {
  const id = String(raw.id ?? `wf_${nanoid(8)}`);
  const nodeType = String(raw.type ?? '');
  const config =
    raw.config && typeof raw.config === 'object' && !Array.isArray(raw.config)
      ? sanitizeNodeConfig(
          nodeType,
          ({ ...(raw.config as Record<string, unknown>) } as Record<string, unknown>)
        )
      : {};
  const metaCatalog = paletteCatalog.find(m => m.node_type === nodeType);
  let label = typeof raw.label === 'string' ? raw.label : '';
  if (!label) {
    label = metaCatalog?.display_name ?? nodeType;
  }
  let x = 80 + ((index * 88) % 520);
  let y = 80 + ((index * 64) % 360);
  const pos = raw.position;
  if (pos && typeof pos === 'object' && !Array.isArray(pos)) {
    const p = pos as Record<string, unknown>;
    if (typeof p.x === 'number') x = p.x;
    if (typeof p.y === 'number') y = p.y;
  }
  const data: RagFlowNodeData = {
    label,
    nodeType,
    config,
    isPlaceholder: Boolean(metaCatalog?.is_placeholder),
    implementationStatus: resolveImplementationStatus(metaCatalog),
    ...isrSemanticFieldsFromMeta(metaCatalog)
  };
  return {
    id,
    type: 'ragWf',
    position: { x, y },
    draggable: true,
    connectable: true,
    selectable: true,
    label,
    data
  } as Node;
}

/** 服务端文档应用到画布返回值（调用方赋值给 ``flowNodes`` / ``flowEdges`` / 表单） */
export function parseStoredWorkflowDocument(doc: RagWorkflowStoredDocument, paletteCatalog: RagNodeMetadata[]) {
  const rawNodes = Array.isArray(doc.nodes) ? doc.nodes : [];
  const flowNodes = storedNodesToFlowNodes(rawNodes, paletteCatalog);
  const flowEdges = edgePairsToFlowEdges(doc.edges);
  return {
    workflowId: doc.workflow_id,
    workflowDisplayName: doc.name || doc.workflow_id,
    workflowDescription: doc.description ?? '',
    inputJsonText: `${JSON.stringify(doc.input_data ?? {}, null, 2)}\n`,
    flowNodes,
    flowEdges
  };
}
