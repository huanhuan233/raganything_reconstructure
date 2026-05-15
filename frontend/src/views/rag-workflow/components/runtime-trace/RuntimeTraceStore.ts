import { computed, reactive } from 'vue';
import type {
  RuntimeTraceEvent,
  RuntimeTraceNodeCatalogItem,
  RuntimeTraceNodeState,
  RuntimeTraceState
} from './RuntimeTraceTypes';
import { RuntimeTraceService } from './RuntimeTraceService';

function createInitialState(): RuntimeTraceState {
  return {
    runId: '',
    workflowId: '',
    running: false,
    phase: '',
    currentNodeId: null,
    failedNodeId: null,
    startedAt: null,
    finishedAt: null,
    durationMs: null,
    error: null,
    nodes: [],
    timeline: [],
    selectedNodeId: null,
    selectedTab: 'detail',
    selectedNodeDetail: null,
    panelCollapsed: false,
    panelWidth: 420,
    autoScroll: true
  };
}

export function useRuntimeTraceStore() {
  const state = reactive<RuntimeTraceState>(createInitialState());
  const service = new RuntimeTraceService();
  let importedRunRecord: Record<string, unknown> | null = null;

  function clear() {
    Object.assign(state, createInitialState());
    service.close();
    importedRunRecord = null;
  }

  function setPanelWidth(width: number) {
    state.panelWidth = Math.min(680, Math.max(320, width));
  }

  function setCollapsed(collapsed: boolean) {
    state.panelCollapsed = collapsed;
  }

  function toggleAutoScroll(v: boolean) {
    state.autoScroll = v;
  }

  function upsertNode(partial: Partial<RuntimeTraceNodeState> & { node_id: string }) {
    const idx = state.nodes.findIndex(x => x.node_id === partial.node_id);
    if (idx < 0) {
      state.nodes.push({
        node_id: partial.node_id,
        node_name: partial.node_name || partial.node_id,
        node_type: partial.node_type || '',
        status: partial.status || 'pending',
        start_time: partial.start_time || null,
        end_time: partial.end_time || null,
        duration_ms: partial.duration_ms ?? null,
        error: partial.error || null,
        summary: partial.summary || {},
        input_preview: partial.input_preview,
        output_preview: partial.output_preview
      });
      return;
    }
    state.nodes[idx] = {
      ...state.nodes[idx],
      ...partial
    };
  }

  function setNodeCatalog(catalog: RuntimeTraceNodeCatalogItem[]) {
    const keep = new Map(state.nodes.map(x => [x.node_id, x]));
    state.nodes = catalog.map(one => {
      const old = keep.get(one.node_id);
      return old || {
        node_id: one.node_id,
        node_name: one.node_name || one.node_id,
        node_type: one.node_type || '',
        status: 'pending',
        start_time: null,
        end_time: null,
        duration_ms: null,
        error: null,
        summary: {}
      };
    });
  }

  // eslint-disable-next-line complexity
  function applySnapshot(snapshot: any) {
    if (!snapshot || typeof snapshot !== 'object') return;
    state.runId = String(snapshot.run_id || state.runId || '');
    state.workflowId = String(snapshot.workflow_id || state.workflowId || '');
    state.running = Boolean(snapshot.running);
    state.phase = String(snapshot.phase || '');
    state.currentNodeId = snapshot.current_node_id ? String(snapshot.current_node_id) : null;
    state.failedNodeId = snapshot.failed_node_id ? String(snapshot.failed_node_id) : null;
    state.startedAt = snapshot.started_at ? String(snapshot.started_at) : null;
    state.finishedAt = snapshot.finished_at ? String(snapshot.finished_at) : null;
    state.durationMs = typeof snapshot.duration_ms === 'number' ? snapshot.duration_ms : null;
    state.error = snapshot.error ? String(snapshot.error) : null;
    if (Array.isArray(snapshot.node_states)) {
      const validStates = snapshot.node_states
        .filter((one: unknown) => !!one && typeof one === 'object')
        .map((one: any) => ({ ...one, node_id: String(one.node_id || '') }))
        .filter((one: { node_id: string }) => !!one.node_id);
      validStates.forEach((one: any) => upsertNode(one));
    }
    state.timeline = Array.isArray(snapshot.timeline) ? snapshot.timeline : [];
  }

  function buildNodeDetailFromRecord(record: Record<string, unknown>, nodeId: string) {
    const nodeResults = (record.node_results || {}) as Record<string, any>;
    const traceNodes = (record.trace_nodes || {}) as Record<string, any>;
    const reqNodes = (((record.request_snapshot || {}) as Record<string, any>).nodes || []) as Array<Record<string, any>>;
    const spec = reqNodes.find(one => String(one.id || '') === nodeId) || null;
    const result = (nodeResults[nodeId] || {}) as Record<string, any>;
    const trace = (traceNodes[nodeId] || {}) as Record<string, any>;

    return {
      run_id: String(record.run_id || ''),
      node_id: nodeId,
      node_name: String((spec?.label as string) || (trace.node_name as string) || nodeId),
      node_type: String((spec?.type as string) || (trace.node_type as string) || ''),
      status: String(trace.status || (result.success ? 'success' : 'pending')),
      start_time: trace.start_time || null,
      end_time: trace.end_time || null,
      duration_ms: typeof trace.duration_ms === 'number' ? trace.duration_ms : null,
      error: (trace.error as string) || (result.error as string) || null,
      summary: (trace.summary as Record<string, unknown>) || {},
      input_preview: trace.input_preview,
      output_preview: trace.output_preview,
      input: trace.input,
      output: result.data,
      metadata: (result.metadata as Record<string, unknown>) || {},
      config: (spec?.config as Record<string, unknown>) || {}
    };
  }

  function importRunJson(payload: unknown): boolean {
    if (!payload || typeof payload !== 'object') return false;
    const record = payload as Record<string, unknown>;
    const runId = String(record.run_id || '').trim();
    if (!runId) return false;

    importedRunRecord = record;
    service.close();

    state.runId = runId;
    state.workflowId = String(record.workflow_id || '');
    state.running = Boolean(record.running);
    state.phase = String(record.phase || (state.running ? 'running' : 'completed'));
    state.currentNodeId = record.current_node_id ? String(record.current_node_id) : null;
    state.failedNodeId = record.failed_node_id ? String(record.failed_node_id) : null;
    state.startedAt = record.started_at ? String(record.started_at) : null;
    state.finishedAt = record.finished_at ? String(record.finished_at) : null;
    state.durationMs = typeof record.duration_ms === 'number' ? Number(record.duration_ms) : null;
    state.error = record.error ? String(record.error) : null;
    state.timeline = Array.isArray(record.trace_timeline) ? (record.trace_timeline as Array<Record<string, unknown>>) : [];
    state.selectedNodeDetail = null;

    const nodeResults = (record.node_results || {}) as Record<string, any>;
    const traceNodes = (record.trace_nodes || {}) as Record<string, any>;
    const reqNodes = (((record.request_snapshot || {}) as Record<string, any>).nodes || []) as Array<Record<string, any>>;
    const nodeIds = Array.from(
      new Set([
        ...reqNodes.map(one => String(one.id || '')).filter(Boolean),
        ...Object.keys(nodeResults),
        ...Object.keys(traceNodes)
      ])
    );

    state.nodes = nodeIds.map(nodeId => {
      const spec = reqNodes.find(one => String(one.id || '') === nodeId) || {};
      const result = (nodeResults[nodeId] || {}) as Record<string, any>;
      const trace = (traceNodes[nodeId] || {}) as Record<string, any>;
      const statusFromResult =
        result && typeof result.success === 'boolean'
          ? result.success
            ? 'success'
            : 'error'
          : 'pending';
      return {
        node_id: nodeId,
        node_name: String((spec.label as string) || (trace.node_name as string) || nodeId),
        node_type: String((spec.type as string) || (trace.node_type as string) || ''),
        status: String(trace.status || statusFromResult) as any,
        start_time: trace.start_time || null,
        end_time: trace.end_time || null,
        duration_ms: typeof trace.duration_ms === 'number' ? Number(trace.duration_ms) : null,
        error: (trace.error as string) || (result.error as string) || null,
        summary: (trace.summary as Record<string, unknown>) || {},
        input_preview: trace.input_preview,
        output_preview: trace.output_preview
      };
    });

    return true;
  }

  // eslint-disable-next-line complexity
  function applyEvent(evt: RuntimeTraceEvent) {
    if (!evt || typeof evt !== 'object') return;
    const payload = (evt.payload || {}) as Record<string, unknown>;
    if (evt.event_type === 'run_start') {
      state.running = true;
      state.phase = 'running';
      return;
    }
    if (evt.event_type === 'run_end') {
      state.running = false;
      state.phase = payload.success ? 'completed' : 'failed';
      state.error = payload.error ? String(payload.error) : null;
      state.failedNodeId = payload.failed_node_id ? String(payload.failed_node_id) : null;
      return;
    }
    if (evt.event_type === 'node_start' || evt.event_type === 'node_end' || evt.event_type === 'node_error') {
      const nodeId = String(payload.node_id || '');
      if (!nodeId) return;
      upsertNode({
        node_id: nodeId,
        node_name: String(payload.node_name || nodeId),
        node_type: String(payload.node_type || ''),
        status: String(payload.status || (evt.event_type === 'node_start' ? 'running' : 'success')) as any,
        start_time: payload.start_time ? String(payload.start_time) : undefined,
        end_time: payload.end_time ? String(payload.end_time) : undefined,
        duration_ms: typeof payload.duration_ms === 'number' ? Number(payload.duration_ms) : undefined,
        error: payload.error ? String(payload.error) : undefined,
        summary: (payload.summary || {}) as Record<string, unknown>,
        input_preview: payload.input_preview,
        output_preview: payload.output_preview
      });
      state.currentNodeId = nodeId;
    }
  }

  async function fetchNodeDetail(nodeId: string) {
    if (!state.runId || !nodeId) return;
    if (importedRunRecord) {
      state.selectedNodeDetail = buildNodeDetailFromRecord(importedRunRecord, nodeId) as any;
      return;
    }
    try {
      state.selectedNodeDetail = await service.getNodeDetail(state.runId, nodeId);
    } catch {
      state.selectedNodeDetail = null;
    }
  }

  function selectNode(nodeId: string) {
    state.selectedNodeId = nodeId || null;
    if (!state.selectedNodeId) {
      state.selectedNodeDetail = null;
      return;
    }

    // 当前 run 的 trace 中不存在该节点时，不请求详情，避免无意义 404 噪音。
    const inCurrentTrace = state.nodes.some(one => one.node_id === state.selectedNodeId);
    if (!inCurrentTrace) {
      state.selectedNodeDetail = null;
      return;
    }

    fetchNodeDetail(state.selectedNodeId).catch(() => {
      // ignore
    });
  }

  async function startTracking(runId: string, nodeCatalog: RuntimeTraceNodeCatalogItem[]) {
    if (!runId) return;
    importedRunRecord = null;
    state.runId = runId;
    setNodeCatalog(nodeCatalog);
    service.subscribeSSE(runId, {
      onEvent: applyEvent,
      onSnapshot: applySnapshot
    });
  }

  function stopTracking() {
    service.close();
  }

  async function refreshSnapshot(): Promise<boolean> {
    if (!state.runId) return false;
    try {
      const snap = await service.getSnapshot(state.runId);
      applySnapshot(snap);
      return true;
    } catch {
      // ignore
      return false;
    }
  }

  const orderedNodes = computed(() => {
    const rank: Record<string, number> = { running: 0, error: 1, success: 2, pending: 3, skipped: 4 };
    return [...state.nodes].sort((a, b) => (rank[a.status] ?? 9) - (rank[b.status] ?? 9));
  });

  return {
    state,
    orderedNodes,
    clear,
    setPanelWidth,
    setCollapsed,
    toggleAutoScroll,
    setNodeCatalog,
    applySnapshot,
    applyEvent,
    selectNode,
    fetchNodeDetail,
    importRunJson,
    startTracking,
    stopTracking,
    refreshSnapshot
  };
}

