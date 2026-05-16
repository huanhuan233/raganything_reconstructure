import type { Connection, Edge, Node } from '@vue-flow/core';
import { addEdge } from '@vue-flow/core';
import { ref, type Ref } from 'vue';
import { nanoid } from '@sa/utils';
import { fetchRagNodeTypes } from '@/service/api';
import { isrSemanticFieldsFromMeta } from '@/components/runtime/isrPalette';
import type { RagFlowNodeData, RagNodeImplementationStatus, RagNodeMetadata } from '@/types/ragWorkflow';
import type { RagWfEdgeInsertPayload } from '../injectionKeys';

const SNAP_GRID = 14;
/** ragWfFlowNode.vue 卡片约 210×88，居中落在边中点上 */
const NODE_VIS_W = 210;
const NODE_VIS_H = 88;
/** 出口旁「+」：新节点相对源节点的水平间距（与卡片宽 + 留白） */
const OUT_HANDLE_GAP_X = NODE_VIS_W + 30;

function snapFlow(n: number): number {
  return Math.round(n / SNAP_GRID) * SNAP_GRID;
}

function tagInsertEdge(edge: Edge): Edge {
  const cls =
    typeof edge.class === 'string' && edge.class.trim() !== ''
      ? edge.class
      : 'rag-wf-insert-bezier';
  if (edge.type === 'ragWfInsert' && edge.class === cls) return edge;
  return { ...edge, type: 'ragWfInsert', class: cls };
}

function resolveImplementationStatus(meta: RagNodeMetadata): RagNodeImplementationStatus {
  return meta.implementation_status ?? (meta.is_placeholder ? 'placeholder' : 'real');
}

export function useWorkflowNodes(options: {
  flowNodes: Ref<Node[]>;
  flowEdges: Ref<Edge[]>;
  onStructureChange: () => void;
  closeNodePicker?: () => void;
}) {
  const { flowNodes, flowEdges, onStructureChange, closeNodePicker } = options;

  const paletteCatalog = ref<RagNodeMetadata[]>([]);
  const paletteLoading = ref(false);
  let spawnOffset = 0;

  async function fetchNodeTypes() {
    paletteLoading.value = true;
    try {
      const res = await fetchRagNodeTypes();
      const raw = res as unknown as
        | { nodes?: unknown; data?: { nodes?: unknown }; result?: { nodes?: unknown } }
        | unknown[];
      const maybeNodes = Array.isArray(raw)
        ? raw
        : raw?.nodes ??
          raw?.data?.nodes ??
          raw?.result?.nodes ??
          [];
      const nodes = Array.isArray(maybeNodes) ? maybeNodes : [];
      paletteCatalog.value = nodes as RagNodeMetadata[];
      if (!paletteCatalog.value.length) {
        window.$message?.warning?.('节点库为空：未解析到节点元数据');
      }
    } catch (e) {
      paletteCatalog.value = [];
      const msg = e instanceof Error ? e.message : String(e);
      window.$message?.error?.(`加载节点库失败：${msg}`);
    } finally {
      paletteLoading.value = false;
    }
  }

  function addNodeFromMeta(meta: RagNodeMetadata) {
    const id = `wf_${nanoid(8)}`;
    spawnOffset += 1;
    const x = 80 + ((spawnOffset * 88) % 520);
    const y = 80 + ((spawnOffset * 64) % 360);

    const data: RagFlowNodeData = {
      label: meta.display_name,
      nodeType: meta.node_type,
      config: {},
      isPlaceholder: Boolean(meta.is_placeholder),
      implementationStatus: resolveImplementationStatus(meta),
      ...isrSemanticFieldsFromMeta(meta)
    };

    const vfNode: Node = {
      id,
      type: 'ragWf',
      position: { x, y },
      draggable: true,
      connectable: true,
      selectable: true,
      label: data.label,
      data
    };

    flowNodes.value = [...(flowNodes.value as Node[]), vfNode];
    closeNodePicker?.();
    onStructureChange();
  }

  function connectNodes(c: Connection) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const next = addEdge(c, flowEdges.value as any) as Edge[];
    flowEdges.value = next.map(e => tagInsertEdge(e));
    onStructureChange();
  }

  /**
   * A→B 上插入 C：删原边，增 C 于中点居中，再加 A→C、C→B（payload 仅存 flow 拓扑相关字段）。
   */
  function insertNodeOnEdge(
    ctx: Omit<RagWfEdgeInsertPayload, 'anchorClientX' | 'anchorClientY'>,
    meta: RagNodeMetadata
  ) {
    const id = `wf_${nanoid(8)}`;
    const { edgeId, source, target, flowMidX, flowMidY } = ctx;

    const data: RagFlowNodeData = {
      label: meta.display_name,
      nodeType: meta.node_type,
      config: {},
      isPlaceholder: Boolean(meta.is_placeholder),
      implementationStatus: resolveImplementationStatus(meta),
      ...isrSemanticFieldsFromMeta(meta)
    };

    const position = {
      x: snapFlow(flowMidX - NODE_VIS_W / 2),
      y: snapFlow(flowMidY - NODE_VIS_H / 2)
    };

    const vfNode: Node = {
      id,
      type: 'ragWf',
      position,
      draggable: true,
      connectable: true,
      selectable: true,
      label: data.label,
      data
    };

    const rest = flowEdges.value.filter(e => e.id !== edgeId).map(e => tagInsertEdge(e));

    const suf = nanoid(4);
    rest.push(
      {
        id: `e_${source}_${id}_${suf}_i`,
        source,
        target: id,
        type: 'ragWfInsert',
        class: 'rag-wf-insert-bezier'
      } as Edge,
      {
        id: `e_${id}_${target}_${suf}_o`,
        source: id,
        target,
        type: 'ragWfInsert',
        class: 'rag-wf-insert-bezier'
      } as Edge
    );

    flowNodes.value = [...(flowNodes.value as Node[]), vfNode];
    flowEdges.value = rest;
    closeNodePicker?.();
    onStructureChange();
  }

  /** 源节点右侧出口旁追加：新建节点并连线 source → new */
  function addNodeLinkedFromSource(sourceNodeId: string, meta: RagNodeMetadata) {
    const nodes = flowNodes.value as Node[];
    const src = nodes.find(n => String(n.id) === String(sourceNodeId));
    if (!src) {
      window.$message?.warning?.('找不到源节点');
      closeNodePicker?.();
      return;
    }

    const id = `wf_${nanoid(8)}`;

    const data: RagFlowNodeData = {
      label: meta.display_name,
      nodeType: meta.node_type,
      config: {},
      isPlaceholder: Boolean(meta.is_placeholder),
      implementationStatus: resolveImplementationStatus(meta),
      ...isrSemanticFieldsFromMeta(meta)
    };

    const position = {
      x: snapFlow(src.position.x + OUT_HANDLE_GAP_X),
      y: snapFlow(src.position.y)
    };

    const vfNode: Node = {
      id,
      type: 'ragWf',
      position,
      draggable: true,
      connectable: true,
      selectable: true,
      label: data.label,
      data
    };

    const suf = nanoid(4);
    const nextEdge = {
      id: `e_${sourceNodeId}_${id}_${suf}`,
      source: String(sourceNodeId),
      target: id,
      type: 'ragWfInsert',
      class: 'rag-wf-insert-bezier'
    } as Edge;

    flowNodes.value = [...nodes, vfNode];
    flowEdges.value = [...(flowEdges.value as Edge[]).map(e => tagInsertEdge(e)), nextEdge];
    closeNodePicker?.();
    onStructureChange();
  }

  return {
    paletteCatalog,
    paletteLoading,
    fetchNodeTypes,
    addNodeFromMeta,
    insertNodeOnEdge,
    addNodeLinkedFromSource,
    connectNodes
  };
}
