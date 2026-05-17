<script setup lang="ts">
import { Icon } from '@iconify/vue';
import { computed, nextTick, onMounted, ref, unref, watch } from 'vue';
import { fetchRagWorkflowTemplateGet, fetchRagWorkflowTemplates } from '@/service/api';
import type { Edge, Node, ViewportTransform, VueFlowStore } from '@vue-flow/core';
import type { RagFlowNodeData, RagNodeMetadata, RagWorkflowStoredDocument, RagWorkflowTemplateSummary } from '@/types/ragWorkflow';
import WorkflowCanvas from './components/WorkflowCanvas.vue';
import WorkflowContextDock from './components/WorkflowContextDock.vue';
import WorkflowHeader from './components/WorkflowHeader.vue';
import WorkflowLoadDialog from './components/WorkflowLoadDialog.vue';
import NodePalette from './components/NodePalette.vue';
import NodeConfigPanel from './components/NodeConfigPanel.vue';
import WorkflowNodeLastRunPeek from './components/WorkflowNodeLastRunPeek.vue';
import WorkflowToolbar from './components/WorkflowToolbar.vue';
import { useRuntimeTraceStore } from './components/runtime-trace/RuntimeTraceStore';
import type { RuntimeTraceTabKey } from './components/runtime-trace/RuntimeTraceTypes';
import { useNodeConfig } from './composables/useNodeConfig';
import { useWorkflowNodes } from './composables/useWorkflowNodes';
import { useWorkflowRun } from './composables/useWorkflowRun';
import { useWorkflowRunRecords } from './composables/useWorkflowRunRecords';
import { useWorkflowStore } from './composables/useWorkflowStore';
import { useWorkflowState } from './composables/useWorkflowState';
import type { RagWfEdgeInsertPayload } from './injectionKeys';
import type { WorkflowPaletteOpenRequest } from './workflowPaletteBus';
import { messageFromAxios } from './utils/apiError';
import { safeParseJson5, stringifyPretty } from './utils/jsonHelper';
import { ensureStoragePersistRemoteResources } from './utils/storagePersistRemote';
import { flowToRunPayload, normalizeRagVueFlowEdges, parseStoredWorkflowDocument } from './utils/workflowTransform';

const canvasWrapRef = ref<HTMLElement | null>(null);

const {
  flowNodes,
  flowEdges,
  selectedNodeId,
  workflowId,
  workflowDisplayName,
  workflowDescription,
  workflowInputJson,
  vfStore,
  zoomPercent,
  workflowPreview,
  onStructureChange: syncWorkflowPreview,
  updateWorkflowPreview
} = useWorkflowState();

const headerStructAt = ref(Date.now());

function onStructureChange() {
  applyUpstreamKnowledgeHints();
  syncWorkflowPreview();
  headerStructAt.value = Date.now();
}

const canvasInteraction = ref<'pan' | 'select'>('pan');

function setCanvasInteractionMode(mode: 'pan' | 'select') {
  canvasInteraction.value = mode;
}

const nodeDrawerTab = ref<'settings' | 'last'>('settings');
const templateDialogVisible = ref(false);
const templateLoading = ref(false);
const templateApplying = ref(false);
const templateCatalog = ref<RagWorkflowTemplateSummary[]>([]);
const selectedTemplateId = ref('');

const nodePickerVisible = ref(false);
const nodePickerPos = ref({ x: 56, y: 56 });
/** 从边上「+」拆边，或从节点出口「+」追加下游 */
const paletteWorkflowCtx = ref<
  | { mode: 'edge'; payload: RagWfEdgeInsertPayload }
  | { mode: 'handle'; sourceNodeId: string }
  | null
>(null);
const filterRunsByCurrentWorkflow = ref(true);

const runtimeTrace = useRuntimeTraceStore();
const traceState = runtimeTrace.state;
const orderedTraceNodes = runtimeTrace.orderedNodes;

const traceObsImportFallback = computed(() =>
  runtimeTrace.lastImportedRunRecord ? unref(runtimeTrace.lastImportedRunRecord) : null
);
const dockOpen = ref(false);
const dockTab = ref<'json' | 'run' | 'node_output' | 'history'>('json');

const LAST_RUN_ID_KEY_PREFIX = 'ragwf:last-run-id:';

function traceRunStorageKey(workflowIdText: string): string {
  const wid = workflowIdText.trim() || '__all__';
  return `${LAST_RUN_ID_KEY_PREFIX}${wid}`;
}

function saveLastRunIdForWorkflow(workflowIdText: string, runId: string) {
  try {
    if (!runId.trim()) return;
    localStorage.setItem(traceRunStorageKey(workflowIdText), runId.trim());
  } catch {
    // ignore storage errors
  }
}

function loadLastRunIdForWorkflow(workflowIdText: string): string {
  try {
    return String(localStorage.getItem(traceRunStorageKey(workflowIdText)) || '').trim();
  } catch {
    return '';
  }
}

function closeWorkflowNodePicker() {
  paletteWorkflowCtx.value = null;
  nodePickerVisible.value = false;
}

const {
  runHistoryList,
  runHistoryLoading,
  runDetailVisible,
  runDetailLoading,
  runDetailFull,
  prettyJson,
  refreshRunHistory,
  openRunDetail,
  deleteRunRecord
} = useWorkflowRunRecords({
  workflowId,
  filterByCurrentWorkflow: filterRunsByCurrentWorkflow
});

const {
  runLoading,
  lastRunRaw,
  runErrorMsg,
  runStatus,
  runWorkflow,
  syncRunStateFromServer,
  runAnswerSnippet
} = useWorkflowRun({
  refreshRunHistory
});

const headerStatusLine = computed(() => {
  const t = new Date(headerStructAt.value);
  const p = (n: number) => String(n).padStart(2, '0');
  const timeStr = `${p(t.getHours())}:${p(t.getMinutes())}:${p(t.getSeconds())}`;
  if (runStatus.value === 'running') {
    return `运行中 · ${timeStr}`;
  }
  return `自动保存 ${timeStr} · 已就绪`;
});

const workflowGlobalQuery = computed<string>({
  get() {
    const parsed = safeParseJson5(workflowInputJson.value);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return '';
    const q = (parsed as Record<string, unknown>).query;
    return typeof q === 'string' ? q : '';
  },
  set(v: string) {
    const parsed = safeParseJson5(workflowInputJson.value);
    const next =
      parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? { ...(parsed as Record<string, unknown>) } : {};
    const q = String(v ?? '');
    if (q.trim()) next.query = q;
    else delete next.query;
    workflowInputJson.value = `${stringifyPretty(next)}\n`;
  }
});

const runNodeTitleMap = computed<Record<string, string>>(() => {
  const m: Record<string, string> = {};
  for (const n of flowNodes.value) {
    const id = String(n.id);
    const data = (n.data ?? {}) as Record<string, unknown>;
    const label = typeof data.label === 'string' && data.label.trim() ? data.label.trim() : id;
    const nodeType = typeof data.nodeType === 'string' && data.nodeType.trim() ? data.nodeType.trim() : '';
    m[id] = nodeType ? `${label}（${nodeType}）` : label;
  }
  return m;
});

const traceNodeCatalog = computed(() =>
  flowNodes.value.map(n => {
    const data = (n.data ?? {}) as Record<string, unknown>;
    const label = typeof data.label === 'string' && data.label.trim() ? data.label.trim() : String(n.id);
    const nodeType = typeof data.nodeType === 'string' ? data.nodeType : '';
    return {
      node_id: String(n.id),
      node_name: label,
      node_type: nodeType
    };
  })
);

const {
  paletteCatalog,
  paletteLoading,
  fetchNodeTypes,
  addNodeFromMeta,
  insertNodeOnEdge,
  addNodeLinkedFromSource,
  connectNodes
} = useWorkflowNodes({
  flowNodes,
  flowEdges,
  onStructureChange,
  closeNodePicker: closeWorkflowNodePicker
});

const {
  labelDraft,
  configDraft,
  selectedNode,
  selectedNodeMeta,
  hasConfigSchema,
  localSchemaConfig,
  patchSchemaField,
  applyConfigDraftNow,
  onNodeSelected,
  clearSelectionDrafts,
  resetDraftsAfterClearCanvas
} = useNodeConfig({
  flowNodes,
  selectedNodeId,
  paletteCatalog,
  onStructureChange
});

const drawerNodeType = computed(
  () => (selectedNode.value?.data as RagFlowNodeData | undefined)?.nodeType ?? ''
);

const drawerNodeLabel = computed(() => {
  const n = selectedNode.value;
  if (!n?.data) return '节点配置';
  const d = n.data as RagFlowNodeData;
  return String(d.label ?? n.id ?? '节点');
});

const drawerNodeIco = computed(() => {
  const t = drawerNodeType.value.trim();
  if (t.includes('.')) {
    const last = t.split('.').pop() ?? t;
    return last.slice(0, 2).toUpperCase();
  }
  return (t || '?').slice(0, 2).toUpperCase() || '?';
});

type UpstreamKnowledgeHint = {
  knowledge_id?: string;
  vector_backend?: string;
};

function getUpstreamNodeByType(nodeId: string, nodeType: string): Node | null {
  const targetId = String(nodeId);
  for (const e of flowEdges.value) {
    if (String(e.target) !== targetId) continue;
    const srcId = String(e.source);
    const src = flowNodes.value.find(n => String(n.id) === srcId);
    if (!src) continue;
    const d = (src.data ?? {}) as RagFlowNodeData;
    if (String(d.nodeType || '') === nodeType) return src;
  }
  return null;
}

const DEFAULT_ROUTE_PIPELINES = ['text_pipeline', 'table_pipeline', 'vision_pipeline', 'equation_pipeline', 'discard_pipeline'] as const;

function getUpstreamContentRouteNodes(nodeId: string): Node[] {
  const targetId = String(nodeId);
  const out: Node[] = [];
  for (const e of flowEdges.value) {
    if (String(e.target) !== targetId) continue;
    const src = flowNodes.value.find(n => String(n.id) === String(e.source));
    if (!src) continue;
    const d = (src.data ?? {}) as RagFlowNodeData;
    if (String(d.nodeType || '') === 'content.route') out.push(src);
  }
  return out;
}

function routeMappingKeysFromConfig(node: Node): string[] {
  const d = (node.data ?? {}) as RagFlowNodeData;
  const cfg = (d.config ?? {}) as Record<string, unknown>;
  const rm = cfg.route_mapping;
  if (rm && typeof rm === 'object' && !Array.isArray(rm)) return Object.keys(rm as Record<string, unknown>);
  return [];
}

function routeKeysFromLastRun(nodeId: string): string[] {
  if (!lastRunRaw.value?.trim()) return [];
  try {
    const obj = JSON.parse(lastRunRaw.value) as Record<string, unknown>;
    const nr = (obj.node_results ?? {}) as Record<string, unknown>;
    const one = (nr[nodeId] ?? {}) as Record<string, unknown>;
    const data = (one.data ?? {}) as Record<string, unknown>;
    const routes = data.routes;
    if (routes && typeof routes === 'object' && !Array.isArray(routes)) return Object.keys(routes as Record<string, unknown>);
  } catch {
    return [];
  }
  return [];
}

const knowledgeSelectPipelineCandidates = computed(() => {
  const n = selectedNode.value;
  if (!n) return [...DEFAULT_ROUTE_PIPELINES];
  const d = (n.data ?? {}) as RagFlowNodeData;
  if (String(d.nodeType || '') !== 'knowledge.select') return [...DEFAULT_ROUTE_PIPELINES];
  const out: string[] = [];
  for (const routeNode of getUpstreamContentRouteNodes(String(n.id))) {
    for (const k of routeMappingKeysFromConfig(routeNode)) {
      if (k && !out.includes(k)) out.push(k);
    }
  }
  if (out.length) return out;
  for (const routeNode of flowNodes.value) {
    const rd = (routeNode.data ?? {}) as RagFlowNodeData;
    if (String(rd.nodeType || '') !== 'content.route') continue;
    for (const k of routeKeysFromLastRun(String(routeNode.id))) {
      if (k && !out.includes(k)) out.push(k);
    }
  }
  if (out.length) return out;
  return [...DEFAULT_ROUTE_PIPELINES];
});

function applyUpstreamKnowledgeHints() {
  let changed = false;
  const nextNodes = flowNodes.value.map(n => {
    const d = (n.data ?? {}) as RagFlowNodeData & { upstreamKnowledgeHint?: UpstreamKnowledgeHint };
    const nt = String(d.nodeType || '');
    if (nt !== 'vector.retrieve') {
      if (d.upstreamKnowledgeHint) {
        changed = true;
        const cleaned = { ...(d as Record<string, unknown>) };
        delete cleaned.upstreamKnowledgeHint;
        return { ...n, data: cleaned as RagFlowNodeData };
      }
      return n;
    }
    const upstream = getUpstreamNodeByType(String(n.id), 'knowledge.select');
    const ucfg = ((upstream?.data as RagFlowNodeData | undefined)?.config ?? {}) as Record<string, unknown>;
    const hint: UpstreamKnowledgeHint = {
      knowledge_id: String(ucfg.knowledge_id || '').trim(),
      vector_backend: String(ucfg.vector_backend || '').trim().toLowerCase()
    };
    const old = d.upstreamKnowledgeHint ?? {};
    if ((old.knowledge_id || '') === (hint.knowledge_id || '') && (old.vector_backend || '') === (hint.vector_backend || '')) {
      return n;
    }
    changed = true;
    return { ...n, data: { ...(d as Record<string, unknown>), upstreamKnowledgeHint: hint } as RagFlowNodeData };
  });
  if (changed) flowNodes.value = nextNodes;
}

function applyLoadedDocument(doc: RagWorkflowStoredDocument) {
  const parsed = parseStoredWorkflowDocument(doc, paletteCatalog.value);
  workflowId.value = parsed.workflowId;
  workflowDisplayName.value = parsed.workflowDisplayName;
  workflowDescription.value = parsed.workflowDescription;
  workflowInputJson.value = parsed.inputJsonText;
  flowNodes.value = parsed.flowNodes;
  flowEdges.value = normalizeRagVueFlowEdges(parsed.flowEdges);
  selectedNodeId.value = null;
  clearSelectionDrafts();
  resetDraftsAfterClearCanvas();
  nextTick(() => {
    onStructureChange();
    nextTick(() => fitViewSafe());
  });
}

function layoutFlowNodesHorizontally(nodes: Node[], edges: Edge[]): Node[] {
  if (!nodes.length) return [];
  const idSet = new Set(nodes.map(n => String(n.id)));
  const indeg = new Map<string, number>();
  const out = new Map<string, string[]>();
  for (const id of idSet) {
    indeg.set(id, 0);
    out.set(id, []);
  }
  for (const e of edges) {
    const s = String(e.source);
    const t = String(e.target);
    if (!idSet.has(s) || !idSet.has(t)) continue;
    indeg.set(t, (indeg.get(t) ?? 0) + 1);
    out.get(s)?.push(t);
  }
  const queue: string[] = [];
  for (const id of idSet) {
    if ((indeg.get(id) ?? 0) === 0) queue.push(id);
  }
  const level = new Map<string, number>();
  for (const id of queue) level.set(id, 0);
  while (queue.length) {
    const cur = queue.shift() as string;
    const curLv = level.get(cur) ?? 0;
    for (const nxt of out.get(cur) ?? []) {
      if ((level.get(nxt) ?? 0) < curLv + 1) level.set(nxt, curLv + 1);
      indeg.set(nxt, (indeg.get(nxt) ?? 1) - 1);
      if ((indeg.get(nxt) ?? 0) === 0) queue.push(nxt);
    }
  }
  let fallbackLv = 0;
  for (const id of idSet) {
    if (!level.has(id)) {
      level.set(id, fallbackLv++);
    }
  }
  const byLv = new Map<number, string[]>();
  for (const [id, lv] of level.entries()) {
    if (!byLv.has(lv)) byLv.set(lv, []);
    byLv.get(lv)?.push(id);
  }
  const mapNode = new Map<string, Node>(nodes.map(n => [String(n.id), n]));
  const nextNodes: Node[] = [];
  const x0 = 80;
  const y0 = 100;
  const dx = 280;
  const dy = 130;
  const lvSorted = [...byLv.keys()].sort((a, b) => a - b);
  for (const lv of lvSorted) {
    const ids = byLv.get(lv) ?? [];
    ids.sort();
    ids.forEach((id, idx) => {
      const n = mapNode.get(id);
      if (!n) return;
      nextNodes.push({
        ...n,
        position: { x: x0 + lv * dx, y: y0 + idx * dy }
      });
    });
  }
  return nextNodes.length ? nextNodes : nodes;
}

function applyTemplateDocument(doc: RagWorkflowStoredDocument) {
  const parsed = parseStoredWorkflowDocument(doc, paletteCatalog.value);
  const normalizedEdges = normalizeRagVueFlowEdges(parsed.flowEdges);
  const laidNodes = layoutFlowNodesHorizontally(parsed.flowNodes as Node[], normalizedEdges as Edge[]);
  workflowId.value = parsed.workflowId;
  workflowDisplayName.value = parsed.workflowDisplayName;
  workflowDescription.value = parsed.workflowDescription;
  workflowInputJson.value = parsed.inputJsonText;
  flowNodes.value = laidNodes;
  flowEdges.value = normalizedEdges;
  selectedNodeId.value = null;
  clearSelectionDrafts();
  resetDraftsAfterClearCanvas();
  nextTick(() => {
    onStructureChange();
    nextTick(() => fitViewSafe());
  });
}

async function openTemplateDialog() {
  templateDialogVisible.value = true;
  selectedTemplateId.value = '';
  templateLoading.value = true;
  try {
    const res = await fetchRagWorkflowTemplates();
    templateCatalog.value = [...res];
    if (templateCatalog.value.length) {
      selectedTemplateId.value = templateCatalog.value[0].template_id;
    }
  } catch (e) {
    window.$message?.error(messageFromAxios(e));
  } finally {
    templateLoading.value = false;
  }
}

async function applyTemplateSelection() {
  const templateId = selectedTemplateId.value.trim();
  if (!templateId) {
    window.$message?.warning('请先选择模板');
    return;
  }
  templateApplying.value = true;
  try {
    if (!paletteCatalog.value.length) {
      await fetchNodeTypes();
    }
    const doc = await fetchRagWorkflowTemplateGet(templateId);
    applyTemplateDocument(doc);
    templateDialogVisible.value = false;
    window.$message?.success('模板已创建到画布');
  } catch (e) {
    const msg = messageFromAxios(e);
    window.$message?.error(msg.includes('timeout') ? `子模板加载失败：${msg}（请确认 backend_api 已启动）` : `子模板加载失败：${msg}`);
  } finally {
    templateApplying.value = false;
  }
}

const {
  saveLoading,
  loadDialogVisible,
  loadListLoading,
  savedWorkflowList,
  saveWorkflow,
  listSavedWorkflows,
  openLoadDialog,
  loadWorkflowByIdent,
  deleteSavedWorkflowCurrent
} = useWorkflowStore({
  flowNodes,
  flowEdges,
  workflowId,
  workflowDisplayName,
  workflowDescription,
  workflowInputJson,
  applyLoadedDocument
});

function openNodePicker(anchor?: HTMLElement | null) {
  paletteWorkflowCtx.value = null;
  nodePickerVisible.value = true;
  if (anchor) {
    const r = anchor.getBoundingClientRect();
    const wrap = canvasWrapRef.value?.getBoundingClientRect();
    if (wrap) {
      nodePickerPos.value = {
        x: r.left - wrap.left + r.width + 8,
        y: r.top - wrap.top
      };
    }
  } else {
    nodePickerPos.value = { x: 56, y: 56 };
  }
}

function onVfInit(store: VueFlowStore) {
  vfStore.value = store;
  zoomPercent.value = Math.round(unref(store.viewport).zoom * 100);
}

function onViewportChange(vp: ViewportTransform) {
  zoomPercent.value = Math.round(vp.zoom * 100);
}

function fitViewSafe() {
  vfStore.value?.fitView({ padding: 0.2, duration: 200 });
}

function resetViewport() {
  vfStore.value?.setViewport({ x: 0, y: 0, zoom: 1 }, { duration: 200 });
}

function zoomStep(delta: number) {
  const vf = vfStore.value;
  if (!vf) return;
  const z = unref(vf.viewport).zoom ?? 1;
  const next = Math.min(1.8, Math.max(0.4, z + delta));
  vf.zoomTo(next, { duration: 150 });
}

function onPaneClickOuter() {
  closeWorkflowNodePicker();
}

function onNodeDeleteRequest(nodeId: string) {
  const id = String(nodeId);
  closeWorkflowNodePicker();
  flowNodes.value = (flowNodes.value as typeof flowNodes.value).filter(n => String(n.id) !== id);
  flowEdges.value = (flowEdges.value as typeof flowEdges.value).filter(
    e => String(e.source) !== id && String(e.target) !== id
  );
  if (selectedNodeId.value === id) {
    selectedNodeId.value = null;
    clearSelectionDrafts();
  }
  onStructureChange();
}

function onWorkflowPaletteRequest(p: WorkflowPaletteOpenRequest) {
  if (p.paletteSource === 'edge') {
    paletteWorkflowCtx.value = {
      mode: 'edge',
      payload: {
        edgeId: p.edgeId,
        source: p.source,
        target: p.target,
        flowMidX: p.flowMidX,
        flowMidY: p.flowMidY,
        anchorClientX: p.anchorClientX,
        anchorClientY: p.anchorClientY
      }
    };
  } else {
    paletteWorkflowCtx.value = { mode: 'handle', sourceNodeId: p.sourceNodeId };
  }
  const wrap = canvasWrapRef.value?.getBoundingClientRect();
  const ax = p.anchorClientX;
  const ay = p.anchorClientY;
  if (wrap) {
    nodePickerPos.value = {
      x: ax - wrap.left + 10,
      y: ay - wrap.top - 14
    };
  }
  nodePickerVisible.value = true;
}

function handlePaletteAddNode(meta: RagNodeMetadata) {
  const ctx = paletteWorkflowCtx.value;
  if (!ctx) {
    addNodeFromMeta(meta);
    return;
  }
  if (ctx.mode === 'edge') {
    const h = ctx.payload;
    insertNodeOnEdge(
      {
        edgeId: h.edgeId,
        source: h.source,
        target: h.target,
        flowMidX: h.flowMidX,
        flowMidY: h.flowMidY
      },
      meta
    );
    return;
  }
  addNodeLinkedFromSource(ctx.sourceNodeId, meta);
}

function onNodePanelMore(cmd: string) {
  if (cmd === 'keys') moreHintHotkeys();
}

function clearCanvas() {
  flowNodes.value = [];
  flowEdges.value = [];
  selectedNodeId.value = null;
  clearSelectionDrafts();
  resetDraftsAfterClearCanvas();
  onStructureChange();
}

function closeNodeConfigDrawer() {
  selectedNodeId.value = null;
  clearSelectionDrafts();
}

function applyRuntimeNodeStats(runRes: unknown) {
  if (!runRes || typeof runRes !== 'object') return;
  const nr = (runRes as { node_results?: Record<string, unknown> }).node_results;
  if (!nr || typeof nr !== 'object') return;
  flowNodes.value = flowNodes.value.map(n => {
    const id = String(n.id);
    const one = nr[id] as { data?: Record<string, unknown> } | undefined;
    const data = (one?.data ?? {}) as Record<string, unknown>;
    const ps = (data.process_summary ?? {}) as Record<string, unknown>;
    const rs = (data.route_summary ?? {}) as Record<string, unknown>;
    const es = (data.embedding_summary ?? {}) as Record<string, unknown>;
    const processedCount = ps.processed_count;
    const groupDistribution = rs.group_distribution;
    const totalRecords = es.total_records;
    const withVector = es.with_vector;
    const withoutVector = es.without_vector;
    const hasProcessed = typeof processedCount === 'number';
    const hasGroupDist = groupDistribution && typeof groupDistribution === 'object';
    const hasEmbeddingStats =
      typeof totalRecords === 'number' || typeof withVector === 'number' || typeof withoutVector === 'number';
    const ssum = (data.storage_summary ?? {}) as Record<string, unknown>;
    const bySt = (ssum.by_status ?? {}) as Record<string, unknown>;
    const hasStorageStats =
      typeof ssum.total_records === 'number' ||
      typeof ssum.refs_total === 'number' ||
      typeof bySt.stored === 'number' ||
      typeof bySt.skipped === 'number' ||
      typeof bySt.failed === 'number';
    const msum = (data.merge_summary ?? {}) as Record<string, unknown>;
    const mdist = (msum.source_distribution ?? {}) as Record<string, unknown>;
    const hasMergeStats =
      typeof msum.total_input === 'number' ||
      typeof msum.total_output === 'number' ||
      typeof msum.deduplicated === 'number' ||
      Object.keys(mdist).length > 0;
    const csum = (data.context_summary ?? {}) as Record<string, unknown>;
    const hasContextStats =
      typeof csum.input_results === 'number' ||
      typeof csum.used_results === 'number' ||
      typeof csum.context_chars === 'number' ||
      typeof csum.max_context_chars === 'number' ||
      typeof data.context_str === 'string';
    const rrsum = (data.rerank_summary ?? {}) as Record<string, unknown>;
    const hasRerankStats =
      typeof rrsum.input_count === 'number' ||
      typeof rrsum.output_count === 'number' ||
      typeof rrsum.rerank_engine === 'string' ||
      typeof rrsum.rerank_model === 'string' ||
      Array.isArray(data.reranked_results);
    const rsum = (data.retrieve_summary ?? {}) as Record<string, unknown>;
    const rdist = (rsum.backend_distribution ?? {}) as Record<string, unknown>;
    const rwarns = rsum.warnings;
    const rrows = data.vector_results;
    const hasRetrieveStats =
      typeof rsum.total === 'number' ||
      (rdist && typeof rdist === 'object' && Object.keys(rdist).length > 0) ||
      Array.isArray(rwarns) ||
      Array.isArray(rrows);
    const gsum = (data.generation_summary ?? {}) as Record<string, unknown>;
    const hasGenerationStats =
      typeof gsum.prompt_chars === 'number' ||
      typeof gsum.context_chars === 'number' ||
      typeof gsum.answer_chars === 'number' ||
      typeof gsum.model === 'string' ||
      typeof gsum.used_llm === 'boolean' ||
      typeof data.answer === 'string' ||
      typeof data.prompt === 'string';
    const ksum = (data.keyword_summary ?? {}) as Record<string, unknown>;
    const grsum = (data.graph_summary ?? {}) as Record<string, unknown>;
    const ggraph = (data.graph ?? {}) as Record<string, unknown>;
    const hasKeywordStats =
      typeof ksum.total === 'number' ||
      typeof ksum.high_level_count === 'number' ||
      typeof ksum.low_level_count === 'number' ||
      typeof ksum.mode === 'string' ||
      Array.isArray(data.keywords) ||
      Array.isArray(data.high_level_keywords) ||
      Array.isArray(data.low_level_keywords);
    const hasGraphStats =
      typeof grsum.total === 'number' ||
      typeof grsum.entity_count === 'number' ||
      typeof grsum.relation_count === 'number' ||
      typeof grsum.backend === 'string' ||
      typeof grsum.workspace === 'string' ||
      Array.isArray(data.graph_results);
    const hasGraphMergeStats =
      typeof grsum.component_count === 'number' ||
      typeof grsum.isolated_entity_count === 'number' ||
      typeof grsum.merge_strategy === 'string' ||
      Array.isArray(ggraph.entities) ||
      Array.isArray(ggraph.relations) ||
      Array.isArray(ggraph.connected_components);
    const chsum = (data.chunk_summary ?? {}) as Record<string, unknown>;
    const hasChunkStats =
      typeof chsum.total_chunks === 'number' ||
      typeof chsum.input_items === 'number' ||
      (chsum.pipeline_distribution && typeof chsum.pipeline_distribution === 'object') ||
      (chsum.type_distribution && typeof chsum.type_distribution === 'object') ||
      Array.isArray(data.chunks);
    const ersum = (data.entity_relation_summary ?? {}) as Record<string, unknown>;
    const hasEntityRelationStats =
      typeof ersum.entity_count === 'number' ||
      typeof ersum.relation_count === 'number' ||
      Array.isArray(data.entities) ||
      Array.isArray(data.relations);
    const emsum = (data.entity_merge_summary ?? {}) as Record<string, unknown>;
    const hasEntityMergeStats =
      typeof emsum.input_entities === 'number' ||
      typeof emsum.merged_entities === 'number' ||
      typeof emsum.merged_groups === 'number' ||
      Array.isArray(data.merged_entities);
    const rmsum = ((data.relation_merge_summary ?? data.relation_merge) ?? {}) as Record<string, unknown>;
    const hasRelationMergeStats =
      typeof rmsum.input_relations === 'number' ||
      typeof rmsum.merged_relations === 'number' ||
      typeof rmsum.merged_groups === 'number' ||
      typeof rmsum.merge_strategy === 'string' ||
      Array.isArray(data.merged_relations);
    const gpsum = (data.graph_persist_summary ?? {}) as Record<string, unknown>;
    const hasGraphPersistStats =
      typeof gpsum.entity_persisted === 'number' ||
      typeof gpsum.relation_persisted === 'number' ||
      typeof gpsum.component_persisted === 'number' ||
      typeof gpsum.graph_backend === 'string' ||
      Array.isArray(data.storage_refs);
    if (
      !hasProcessed &&
      !hasGroupDist &&
      !hasEmbeddingStats &&
      !hasStorageStats &&
      !hasRetrieveStats &&
      !hasMergeStats &&
      !hasRerankStats &&
      !hasContextStats &&
      !hasGenerationStats &&
      !hasKeywordStats &&
      !hasGraphStats &&
      !hasGraphMergeStats &&
      !hasChunkStats &&
      !hasEntityRelationStats &&
      !hasEntityMergeStats &&
      !hasRelationMergeStats &&
      !hasGraphPersistStats
    )
      return n;
    return {
      ...n,
      data: {
        ...(n.data ?? {}),
        ...(hasProcessed ? { runtimeProcessedCount: processedCount } : {}),
        ...(hasGroupDist ? { runtimeGroupDistribution: groupDistribution } : {}),
        ...(hasEmbeddingStats
          ? {
              runtimeEmbeddingSummary: {
                total_records: totalRecords,
                with_vector: withVector,
                without_vector: withoutVector
              }
            }
          : {}),
        ...(hasStorageStats
          ? {
              runtimeStorageSummary: {
                total_records: ssum.total_records,
                refs_total: ssum.refs_total,
                stored: Number(bySt.stored ?? 0),
                skipped: Number(bySt.skipped ?? 0),
                failed: Number(bySt.failed ?? 0)
              }
            }
          : {}),
        ...(hasRetrieveStats
          ? {
              runtimeRetrieveSummary: {
                total: typeof rsum.total === 'number' ? Number(rsum.total) : undefined,
                backend_distribution: rdist && typeof rdist === 'object' ? rdist : {},
                warnings_count: Array.isArray(rwarns) ? rwarns.length : 0,
                rows_count: Array.isArray(rrows) ? rrows.length : 0
              }
            }
          : {}),
        ...(hasMergeStats
          ? {
              runtimeMergeSummary: {
                total_input: typeof msum.total_input === 'number' ? Number(msum.total_input) : undefined,
                total_output: typeof msum.total_output === 'number' ? Number(msum.total_output) : undefined,
                deduplicated: typeof msum.deduplicated === 'number' ? Number(msum.deduplicated) : undefined,
                source_distribution: mdist,
                fusion_strategy: typeof msum.fusion_strategy === 'string' ? msum.fusion_strategy : undefined
              }
            }
          : {}),
        ...(hasRerankStats
          ? {
              runtimeRerankSummary: {
                input_count: typeof rrsum.input_count === 'number' ? Number(rrsum.input_count) : undefined,
                output_count:
                  typeof rrsum.output_count === 'number'
                    ? Number(rrsum.output_count)
                    : Array.isArray(data.reranked_results)
                      ? data.reranked_results.length
                      : undefined,
                rerank_engine: typeof rrsum.rerank_engine === 'string' ? rrsum.rerank_engine : undefined,
                rerank_model: typeof rrsum.rerank_model === 'string' ? rrsum.rerank_model : undefined,
                source_algorithm: typeof rrsum.source_algorithm === 'string' ? rrsum.source_algorithm : undefined
              }
            }
          : {}),
        ...(hasContextStats
          ? {
              runtimeContextSummary: {
                input_results: typeof csum.input_results === 'number' ? Number(csum.input_results) : undefined,
                used_results: typeof csum.used_results === 'number' ? Number(csum.used_results) : undefined,
                context_chars: typeof csum.context_chars === 'number' ? Number(csum.context_chars) : undefined,
                max_context_chars: typeof csum.max_context_chars === 'number' ? Number(csum.max_context_chars) : undefined
              }
            }
          : {}),
        ...(hasGenerationStats
          ? {
              runtimeGenerationSummary: {
                used_llm: typeof gsum.used_llm === 'boolean' ? gsum.used_llm : undefined,
                model: typeof gsum.model === 'string' ? gsum.model : undefined,
                prompt_chars: typeof gsum.prompt_chars === 'number' ? Number(gsum.prompt_chars) : undefined,
                context_chars: typeof gsum.context_chars === 'number' ? Number(gsum.context_chars) : undefined,
                answer_chars: typeof gsum.answer_chars === 'number' ? Number(gsum.answer_chars) : undefined
              }
            }
          : {}),
        ...(hasKeywordStats
          ? {
              runtimeKeywordSummary: {
                total:
                  typeof ksum.total === 'number'
                    ? Number(ksum.total)
                    : Array.isArray(data.keywords)
                      ? data.keywords.length
                      : undefined,
                high_level_count:
                  typeof ksum.high_level_count === 'number'
                    ? Number(ksum.high_level_count)
                    : Array.isArray(data.high_level_keywords)
                      ? data.high_level_keywords.length
                      : undefined,
                low_level_count:
                  typeof ksum.low_level_count === 'number'
                    ? Number(ksum.low_level_count)
                    : Array.isArray(data.low_level_keywords)
                      ? data.low_level_keywords.length
                      : undefined,
                mode: typeof ksum.mode === 'string' ? ksum.mode : typeof data.keyword_mode === 'string' ? data.keyword_mode : undefined
              }
            }
          : {}),
        ...(hasGraphStats
          ? {
              runtimeGraphSummary: {
                total: typeof grsum.total === 'number' ? Number(grsum.total) : Array.isArray(data.graph_results) ? data.graph_results.length : undefined,
                entity_count: typeof grsum.entity_count === 'number' ? Number(grsum.entity_count) : undefined,
                relation_count: typeof grsum.relation_count === 'number' ? Number(grsum.relation_count) : undefined,
                backend: typeof grsum.backend === 'string' ? grsum.backend : undefined,
                workspace: typeof grsum.workspace === 'string' ? grsum.workspace : undefined,
                source_algorithm: typeof grsum.source_algorithm === 'string' ? grsum.source_algorithm : undefined
              }
            }
          : {}),
        ...(hasGraphMergeStats
          ? {
              runtimeGraphMergeSummary: {
                entity_count:
                  typeof grsum.entity_count === 'number'
                    ? Number(grsum.entity_count)
                    : Array.isArray(ggraph.entities)
                      ? ggraph.entities.length
                      : undefined,
                relation_count:
                  typeof grsum.relation_count === 'number'
                    ? Number(grsum.relation_count)
                    : Array.isArray(ggraph.relations)
                      ? ggraph.relations.length
                      : undefined,
                component_count:
                  typeof grsum.component_count === 'number'
                    ? Number(grsum.component_count)
                    : Array.isArray(ggraph.connected_components)
                      ? ggraph.connected_components.length
                      : undefined,
                isolated_entity_count:
                  typeof grsum.isolated_entity_count === 'number'
                    ? Number(grsum.isolated_entity_count)
                    : undefined,
                merge_strategy: typeof grsum.merge_strategy === 'string' ? grsum.merge_strategy : undefined,
                merge_engine: typeof grsum.merge_engine === 'string' ? grsum.merge_engine : undefined
              }
            }
          : {}),
        ...(hasChunkStats
          ? {
              runtimeChunkSummary: {
                input_items: typeof chsum.input_items === 'number' ? Number(chsum.input_items) : undefined,
                total_chunks: typeof chsum.total_chunks === 'number' ? Number(chsum.total_chunks) : Array.isArray(data.chunks) ? data.chunks.length : undefined,
                pipeline_distribution:
                  chsum.pipeline_distribution && typeof chsum.pipeline_distribution === 'object' ? chsum.pipeline_distribution : {},
                type_distribution:
                  chsum.type_distribution && typeof chsum.type_distribution === 'object' ? chsum.type_distribution : {},
                source_algorithm: typeof chsum.source_algorithm === 'string' ? chsum.source_algorithm : undefined
              }
            }
          : {}),
        ...(hasEntityRelationStats
          ? {
              runtimeEntityRelationSummary: {
                entity_count:
                  typeof ersum.entity_count === 'number'
                    ? Number(ersum.entity_count)
                    : Array.isArray(data.entities)
                      ? data.entities.length
                      : undefined,
                relation_count:
                  typeof ersum.relation_count === 'number'
                    ? Number(ersum.relation_count)
                    : Array.isArray(data.relations)
                      ? data.relations.length
                      : undefined,
                source_algorithm:
                  typeof ersum.source_algorithm === 'string' ? ersum.source_algorithm : undefined
              }
            }
          : {}),
        ...(hasEntityMergeStats
          ? {
              runtimeEntityMergeSummary: {
                input_entities:
                  typeof emsum.input_entities === 'number' ? Number(emsum.input_entities) : undefined,
                merged_entities:
                  typeof emsum.merged_entities === 'number'
                    ? Number(emsum.merged_entities)
                    : Array.isArray(data.merged_entities)
                      ? data.merged_entities.length
                      : undefined,
                merged_groups:
                  typeof emsum.merged_groups === 'number' ? Number(emsum.merged_groups) : undefined,
                merge_strategy:
                  typeof emsum.merge_strategy === 'string' ? emsum.merge_strategy : undefined,
                merge_engine:
                  typeof emsum.merge_engine === 'string' ? emsum.merge_engine : undefined
              }
            }
          : {}),
        ...(hasRelationMergeStats
          ? {
              runtimeRelationMergeSummary: {
                input_relations:
                  typeof rmsum.input_relations === 'number' ? Number(rmsum.input_relations) : undefined,
                merged_relations:
                  typeof rmsum.merged_relations === 'number'
                    ? Number(rmsum.merged_relations)
                    : Array.isArray(data.merged_relations)
                      ? data.merged_relations.length
                      : undefined,
                merged_groups:
                  typeof rmsum.merged_groups === 'number' ? Number(rmsum.merged_groups) : undefined,
                merge_strategy:
                  typeof rmsum.merge_strategy === 'string' ? rmsum.merge_strategy : undefined,
                merge_engine:
                  typeof rmsum.merge_engine === 'string' ? rmsum.merge_engine : undefined
              }
            }
          : {}),
        ...(hasGraphPersistStats
          ? {
              runtimeGraphPersistSummary: {
                graph_backend: typeof gpsum.graph_backend === 'string' ? gpsum.graph_backend : undefined,
                workspace: typeof gpsum.workspace === 'string' ? gpsum.workspace : undefined,
                entity_persisted:
                  typeof gpsum.entity_persisted === 'number' ? Number(gpsum.entity_persisted) : undefined,
                relation_persisted:
                  typeof gpsum.relation_persisted === 'number' ? Number(gpsum.relation_persisted) : undefined,
                component_persisted:
                  typeof gpsum.component_persisted === 'number' ? Number(gpsum.component_persisted) : undefined
              }
            }
          : {})
      }
    };
  });
}

async function onSaveWorkflow() {
  try {
    await ensureStoragePersistRemoteResources(flowNodes.value);
  } catch (e: unknown) {
    window.$message?.error(e instanceof Error ? e.message : String(e));
    return;
  }
  await saveWorkflow();
}

function createRunIdHex16(): string {
  const g = globalThis.crypto;
  if (g?.getRandomValues) {
    const arr = new Uint8Array(8);
    g.getRandomValues(arr);
    return Array.from(arr)
      .map(x => x.toString(16).padStart(2, '0'))
      .join('');
  }
  const fallback = Math.random().toString(16).replace('.', '') + Date.now().toString(16);
  return fallback.slice(0, 16).padEnd(16, '0');
}

function onTraceSelectNode(nodeId: string) {
  runtimeTrace.selectNode(nodeId);
  selectedNodeId.value = nodeId;
}

function onTraceSelectTab(tab: RuntimeTraceTabKey) {
  traceState.selectedTab = tab;
}

function syncImportedRunToHistory(payload: unknown) {
  if (!payload || typeof payload !== 'object') return;
  const rec = payload as Record<string, unknown>;
  const runId = String(rec.run_id || '').trim();
  if (!runId) return;

  const summary = {
    run_id: runId,
    workflow_id: String(rec.workflow_id || workflowId.value || ''),
    workflow_name: String(rec.workflow_name || workflowDisplayName.value || ''),
    success: Boolean(rec.success),
    duration_ms: typeof rec.duration_ms === 'number' ? Number(rec.duration_ms) : null,
    started_at: rec.started_at ? String(rec.started_at) : null,
    finished_at: rec.finished_at ? String(rec.finished_at) : null,
    failed_node_id: rec.failed_node_id ? String(rec.failed_node_id) : null,
    error: rec.error ? String(rec.error) : null
  };

  const others = runHistoryList.value.filter(one => String(one.run_id || '') !== runId);
  runHistoryList.value = [summary, ...others];
}

function onTraceImportJson(payload: unknown) {
  const ok = runtimeTrace.importRunJson(payload);
  if (!ok) {
    window.$message?.error('导入失败：请上传包含 run_id 的运行记录 JSON');
    return;
  }
  if (payload && typeof payload === 'object') {
    try {
      lastRunRaw.value = stringifyPretty(payload);
      const p = payload as Record<string, unknown>;
      runStatus.value = Boolean(p.success) ? 'success' : p.running ? 'running' : 'error';
      runErrorMsg.value = p.error ? String(p.error) : '';
    } catch {
      // ignore
    }
  }
  dockTab.value = 'run';
  dockOpen.value = true;
  if (traceState.runId) {
    saveLastRunIdForWorkflow(workflowId.value, traceState.runId);
  }
  syncImportedRunToHistory(payload);
  const preferredNodeId =
    traceState.currentNodeId ||
    traceState.nodes.find(n => n.status !== 'pending')?.node_id ||
    traceState.nodes[0]?.node_id ||
    null;
  if (preferredNodeId) {
    runtimeTrace.selectNode(preferredNodeId);
  }
  window.$message?.success(`已导入运行记录：${traceState.runId}`);
}

async function handleRunWorkflow() {
  try {
    await ensureStoragePersistRemoteResources(flowNodes.value);
  } catch (e: unknown) {
    window.$message?.error(e instanceof Error ? e.message : String(e));
    return;
  }
  const runId = createRunIdHex16();
  dockTab.value = 'run';
  dockOpen.value = true;
  runtimeTrace.stopTracking();
  runtimeTrace.clear();
  runtimeTrace.setNodeCatalog(traceNodeCatalog.value);
  await runtimeTrace.startTracking(runId, traceNodeCatalog.value);
  traceState.selectedNodeId = traceNodeCatalog.value[0]?.node_id ?? null;
  const res = await runWorkflow(
    {
      ...flowToRunPayload(flowNodes.value, flowEdges.value, workflowId.value.trim(), workflowInputJson.value),
      run_id: runId
    },
    workflowInputJson.value,
    runId
  );
  const finalRunId = String(res?.run_id || runId).trim();
  if (finalRunId) {
    saveLastRunIdForWorkflow(workflowId.value, finalRunId);
  }
  const detail = finalRunId ? await syncRunStateFromServer(finalRunId) : null;
  const statsSource = detail ?? res;
  if (statsSource) {
    applyRuntimeNodeStats(statsSource);
  }
  if (detail && !detail.running) {
    runtimeTrace.importRunJson(detail as unknown as Record<string, unknown>);
  } else if (finalRunId) {
    await runtimeTrace.refreshSnapshot();
    if (detail?.running) {
      await runtimeTrace.startTracking(finalRunId, traceNodeCatalog.value);
    }
  }
}

async function restoreLatestRunTrace() {
  const rememberedRunId = loadLastRunIdForWorkflow(workflowId.value);
  const latestRunId = String(runHistoryList.value[0]?.run_id || '').trim();
  const candidateRunIds = [rememberedRunId, latestRunId].filter((id, idx, arr) => !!id && arr.indexOf(id) === idx);
  if (!candidateRunIds.length) return;

  runtimeTrace.stopTracking();
  runtimeTrace.clear();
  runtimeTrace.setNodeCatalog(traceNodeCatalog.value);

  let restored = false;
  for (const rid of candidateRunIds) {
    const runDetail = await syncRunStateFromServer(rid);
    if (!runDetail) continue;
    saveLastRunIdForWorkflow(workflowId.value, rid);
    const asRecord = runDetail as unknown as Record<string, unknown>;
    if (runDetail.running) {
      runtimeTrace.importRunJson(asRecord);
      await runtimeTrace.startTracking(rid, traceNodeCatalog.value);
      await runtimeTrace.refreshSnapshot();
    } else {
      runtimeTrace.importRunJson(asRecord);
    }
    restored = true;
    break;
  }
  if (!restored) return;

  // 刷新进入页面时默认选中当前运行节点；无运行节点则选第一条非 pending 节点。
  const preferredNodeId =
    traceState.currentNodeId ||
    traceState.nodes.find(n => n.status !== 'pending')?.node_id ||
    traceState.nodes[0]?.node_id ||
    null;
  if (preferredNodeId) {
    runtimeTrace.selectNode(preferredNodeId);
  }
}

function moreHintHotkeys() {
  window.$message?.info('Delete / Backspace：删除选中节点或边；拖拽连线：连接节点');
}

onMounted(() => {
  flowNodes.value = flowNodes.value.map(n => ({
    ...n,
    type: n.type === 'default' ? 'ragWf' : n.type
  })) as typeof flowNodes.value;
  flowEdges.value = normalizeRagVueFlowEdges(flowEdges.value);
  void (async () => {
    await fetchNodeTypes();
    updateWorkflowPreview();
    await refreshRunHistory();
    await restoreLatestRunTrace();
  })();
});

watch(selectedNodeId, () => {
  nodeDrawerTab.value = 'settings';
  if (selectedNodeId.value) {
    runtimeTrace.selectNode(String(selectedNodeId.value));
  }
});

watch(
  flowNodes,
  () => {
    runtimeTrace.setNodeCatalog(traceNodeCatalog.value);
    const id = selectedNodeId.value;
    if (!id) return;
    if (!flowNodes.value.some(n => String(n.id) === id)) {
      selectedNodeId.value = null;
      clearSelectionDrafts();
    }
  },
  { deep: true }
);

onMounted(() => {
  runtimeTrace.setNodeCatalog(traceNodeCatalog.value);
});
</script>

<template>
  <div
    class="rag-wf-page min-h-0 min-w-0 w-full flex-1 overflow-hidden"
    :class="{ 'rag-wf-page--node-panel-open': !!(selectedNodeId && selectedNode) }"
  >
    <WorkflowHeader
      v-model:workflow-id="workflowId"
      v-model:workflow-name="workflowDisplayName"
      v-model:description="workflowDescription"
      :save-loading="saveLoading"
      :load-list-loading="loadListLoading"
      :status-line="headerStatusLine"
      :run-loading="runLoading"
      @save="onSaveWorkflow"
      @open-load="openLoadDialog"
      @delete-workflow="deleteSavedWorkflowCurrent"
      @new-workflow="openTemplateDialog"
      @refresh-palette="fetchNodeTypes"
      @clear-canvas="clearCanvas"
      @run="handleRunWorkflow"
    />

    <div class="rag-wf-global-querybar">
      <span class="rag-wf-global-querybar__label">用户问题 query</span>
      <ElInput
        v-model="workflowGlobalQuery"
        class="rag-wf-global-querybar__input"
        placeholder="在这里填写一次用户问题；节点默认使用全局 query，高级设置可覆盖"
        clearable
      />
    </div>

    <div class="rag-wf-stage">
      <div class="rag-wf-stage-layout">
        <main ref="canvasWrapRef" class="rag-wf-canvas-wrap" @click.self="onPaneClickOuter">
          <WorkflowCanvas
            v-model:nodes="flowNodes"
            v-model:edges="flowEdges"
            :interaction-mode="canvasInteraction"
            @init="onVfInit"
            @viewport-change="onViewportChange"
            @node-click="onNodeSelected"
            @pane-click="onPaneClickOuter"
            @connect="connectNodes"
            @structure-change="onStructureChange"
            @workflow-palette-request="onWorkflowPaletteRequest"
            @node-delete-request="onNodeDeleteRequest"
          />

          <WorkflowToolbar
            :interaction-mode="canvasInteraction"
            @open-picker="anchor => openNodePicker(anchor)"
            @set-mode="setCanvasInteractionMode"
            @fit-view="fitViewSafe"
            @reset-view="resetViewport"
            @hotkeys="moreHintHotkeys"
          />

          <NodePalette
            :visible="nodePickerVisible"
            :position="nodePickerPos"
            :loading="paletteLoading"
            :catalog="paletteCatalog"
            @close="closeWorkflowNodePicker"
            @add-node="handlePaletteAddNode"
          />

          <div class="rag-wf-capsule rag-wf-capsule--stats">
            <span>节点 {{ flowNodes.length }}</span>
            <span class="rag-wf-capsule-dot">·</span>
            <span>边 {{ flowEdges.length }}</span>
          </div>

          <div class="rag-wf-capsule rag-wf-capsule--zoom">
            <button type="button" class="rag-wf-capsule-zoom-btn" @click="zoomStep(-0.1)">−</button>
            <span class="rag-wf-capsule-zoom-val">{{ zoomPercent }}%</span>
            <button type="button" class="rag-wf-capsule-zoom-btn" @click="zoomStep(0.1)">+</button>
          </div>

          <div class="rag-wf-capsule rag-wf-capsule--run" :class="`tone-${runStatus}`">
            <template v-if="runStatus === 'running'">运行中…</template>
            <template v-else-if="runStatus === 'success'">上次运行 · 成功</template>
            <template v-else-if="runStatus === 'error'">上次运行 · 失败</template>
            <template v-else>就绪</template>
          </div>

          <WorkflowContextDock
            v-model:workflow-preview="workflowPreview"
            v-model:input-data-json="workflowInputJson"
            v-model:filter-runs-by-current-workflow="filterRunsByCurrentWorkflow"
            v-model:run-detail-visible="runDetailVisible"
            v-model:dock-open="dockOpen"
            v-model:dock-tab="dockTab"
            :last-run-raw="lastRunRaw"
            :run-error-msg="runErrorMsg"
            :run-status="runStatus"
            :answer-snippet="runAnswerSnippet(lastRunRaw)"
            :active-node-id="selectedNodeId ? String(selectedNodeId) : null"
            :node-title-map="runNodeTitleMap"
            :run-history-list="runHistoryList"
            :run-history-loading="runHistoryLoading"
            :run-detail-loading="runDetailLoading"
            :run-detail-full="runDetailFull"
            :trace-import-fallback="traceObsImportFallback"
            :pretty-json="prettyJson"
            :trace-state="traceState"
            :trace-ordered-nodes="orderedTraceNodes"
            @refresh-run-history="refreshRunHistory"
            @open-run-detail="openRunDetail"
            @delete-run-record="deleteRunRecord"
            @trace-update-width="runtimeTrace.setPanelWidth"
            @trace-update-collapsed="runtimeTrace.setCollapsed"
            @trace-select-node="onTraceSelectNode"
            @trace-select-tab="onTraceSelectTab"
            @trace-refresh="runtimeTrace.refreshSnapshot"
            @trace-toggle-auto-scroll="runtimeTrace.toggleAutoScroll"
            @trace-import-json="onTraceImportJson"
          />

          <Transition name="rag-wf-node-config-panel">
            <aside
              v-if="selectedNode && selectedNodeId"
              :key="String(selectedNodeId)"
              class="node-config-panel rag-wf-node-config-shell"
              aria-label="节点配置"
            >
              <header class="node-config-panel__header">
                <div class="node-config-panel__identity">
                  <div class="node-config-panel__icon" aria-hidden="true">{{ drawerNodeIco }}</div>
                  <div class="node-config-panel__titles">
                    <div class="node-config-panel__title">{{ drawerNodeLabel }}</div>
                    <div class="node-config-panel__type">{{ drawerNodeType || '—' }}</div>
                  </div>
                </div>
                <div class="node-config-panel__actions">
                  <ElTooltip content="运行完整工作流（等同于顶部测试运行）" placement="bottom">
                    <ElButton
                      circle
                      type="primary"
                      size="small"
                      class="node-config-panel__act-btn"
                      :loading="runLoading"
                      @click="handleRunWorkflow()"
                    >
                      <Icon icon="mdi:play" class="node-config-panel__act-ico" />
                    </ElButton>
                  </ElTooltip>
                  <ElDropdown trigger="click" @command="onNodePanelMore">
                    <ElButton circle size="small" class="node-config-panel__act-btn node-config-panel__act-btn--plain">
                      <Icon icon="mdi:dots-horizontal" class="node-config-panel__act-ico" />
                    </ElButton>
                    <template #dropdown>
                      <ElDropdownMenu>
                        <ElDropdownItem command="keys">
                          <span>快捷键说明</span>
                        </ElDropdownItem>
                      </ElDropdownMenu>
                    </template>
                  </ElDropdown>
                  <button type="button" class="node-config-panel__close" title="关闭" @click="closeNodeConfigDrawer()">
                    <Icon icon="mdi:close" class="node-config-panel__close-ico" />
                  </button>
                </div>
              </header>
              <div class="node-config-panel__tabs-host">
                <ElTabs v-model="nodeDrawerTab" class="rag-wf-node-panel-tabs">
                  <ElTabPane label="设置" name="settings">
                    <NodeConfigPanel
                      suppress-internal-head
                      v-model:global-query="workflowGlobalQuery"
                      v-model:label-draft="labelDraft"
                      v-model:config-draft="configDraft"
                      :selected-node="selectedNode"
                      :selected-node-meta="selectedNodeMeta"
                      :has-config-schema="hasConfigSchema"
                      :local-schema-config="localSchemaConfig"
                      :knowledge-pipeline-candidates="knowledgeSelectPipelineCandidates"
                      @patch-field="patchSchemaField"
                      @apply-json-config="applyConfigDraftNow"
                    />
                  </ElTabPane>
                  <ElTabPane label="上次运行" name="last">
                    <WorkflowNodeLastRunPeek :last-run-raw="lastRunRaw" :node-id="String(selectedNode.id)" />
                  </ElTabPane>
                </ElTabs>
              </div>
            </aside>
          </Transition>
        </main>

      </div>
    </div>

    <WorkflowLoadDialog
      v-model:visible="loadDialogVisible"
      :saved-workflow-list="savedWorkflowList"
      :load-list-loading="loadListLoading"
      @refresh="listSavedWorkflows"
      @load="loadWorkflowByIdent"
    />

    <ElDialog v-model="templateDialogVisible" title="新建工作流" width="540px" destroy-on-close append-to-body>
      <ElSkeleton v-if="templateLoading" :rows="4" animated />
      <div v-else class="rag-wf-template-list">
        <ElRadioGroup v-model="selectedTemplateId" class="rag-wf-template-radio">
          <ElRadio
            v-for="t in templateCatalog"
            :key="t.template_id"
            :label="t.template_id"
            size="large"
            border
            class="rag-wf-template-item"
          >
            <div class="rag-wf-template-item-title">{{ t.name }}</div>
            <div class="rag-wf-template-item-desc">{{ t.description }}</div>
          </ElRadio>
        </ElRadioGroup>
      </div>
      <template #footer>
        <ElButton @click="templateDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="templateApplying" @click="applyTemplateSelection">创建</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style lang="scss">
@import './styles/index.scss';
</style>
