<script setup lang="ts">
import { Icon } from '@iconify/vue';
import type { RagRunHistoryDetail, RagRunHistorySummary } from '@/types/ragWorkflow';
import type { RunStatus } from '../composables/useWorkflowRun';
import RuntimeTracePanel from './runtime-trace/RuntimeTracePanel.vue';
import type { RuntimeTraceState, RuntimeTraceTabKey } from './runtime-trace/RuntimeTraceTypes';
import WorkflowJsonFields from './WorkflowJsonFields.vue';
import WorkflowRunResult from './WorkflowRunResult.vue';
import WorkflowRunRecords from './WorkflowRunRecords.vue';

const props = withDefaults(
  defineProps<{
    lastRunRaw: string;
    runErrorMsg: string;
    runStatus: RunStatus;
    answerSnippet: string;
    activeNodeId?: string | null;
    nodeTitleMap?: Record<string, string>;
    runHistoryList: RagRunHistorySummary[];
    runHistoryLoading: boolean;
    runDetailLoading: boolean;
    runDetailFull: RagRunHistoryDetail | null;
    prettyJson: (v: unknown) => string;
    /** Trace 面板上传导入的 JSON：与列表详情的 ``runDetailFull`` 互为回退数据源 */
    traceImportFallback?: Record<string, unknown> | null;
    traceState?: RuntimeTraceState;
    traceOrderedNodes?: RuntimeTraceState['nodes'];
  }>(),
  {
    traceState: undefined,
    traceOrderedNodes: () => [],
    traceImportFallback: null
  }
);

const workflowPreviewModel = defineModel<string>('workflowPreview', { required: true });
const inputDataJsonModel = defineModel<string>('inputDataJson', { required: true });

const filterRunsByCurrentWorkflow = defineModel<boolean>('filterRunsByCurrentWorkflow', { default: true });
const runDetailVisibleModel = defineModel<boolean>('runDetailVisible', { default: false });
const dockOpen = defineModel<boolean>('dockOpen', { default: false });
const dockTab = defineModel<'json' | 'run' | 'node_output' | 'history'>('dockTab', { default: 'json' });

const fallbackTraceState: RuntimeTraceState = {
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

const emit = defineEmits<{
  'refresh-run-history': [];
  'open-run-detail': [row: RagRunHistorySummary];
  'delete-run-record': [runId: string];
  'trace-update-width': [width: number];
  'trace-update-collapsed': [collapsed: boolean];
  'trace-select-node': [nodeId: string];
  'trace-select-tab': [tab: RuntimeTraceTabKey];
  'trace-refresh': [];
  'trace-toggle-auto-scroll': [enabled: boolean];
  'trace-import-json': [payload: unknown];
}>();

function toggleSameTab(tab: 'json' | 'run' | 'node_output' | 'history') {
  if (dockOpen.value && dockTab.value === tab) {
    dockOpen.value = false;
    return;
  }
  dockTab.value = tab;
  dockOpen.value = true;
}
</script>

<template>
  <div class="rag-wf-dock-icons" aria-label="辅助工具">
    <ElTooltip content="Workflow JSON" placement="bottom">
      <button
        type="button"
        class="rag-wf-dock-icon-btn"
        :class="{ 'is-on': dockOpen && dockTab === 'json' }"
        @click="toggleSameTab('json')"
      >
        <Icon icon="mdi:code-json" class="rag-wf-dock-ico" />
      </button>
    </ElTooltip>
    <ElTooltip content="运行结果" placement="bottom">
      <button
        type="button"
        class="rag-wf-dock-icon-btn"
        :class="{ 'is-on': dockOpen && dockTab === 'run' }"
        @click="toggleSameTab('run')"
      >
        <Icon icon="mdi:text-box-check-outline" class="rag-wf-dock-ico" />
      </button>
    </ElTooltip>
    <ElTooltip content="运行记录" placement="bottom">
      <button
        type="button"
        class="rag-wf-dock-icon-btn"
        :class="{ 'is-on': dockOpen && dockTab === 'history' }"
        @click="toggleSameTab('history')"
      >
        <Icon icon="mdi:format-list-bulleted" class="rag-wf-dock-ico" />
      </button>
    </ElTooltip>
    <ElTooltip content="节点输出" placement="bottom">
      <button
        type="button"
        class="rag-wf-dock-icon-btn"
        :class="{ 'is-on': dockOpen && dockTab === 'node_output' }"
        @click="toggleSameTab('node_output')"
      >
        <Icon icon="mdi:view-list-outline" class="rag-wf-dock-ico" />
      </button>
    </ElTooltip>
  </div>

  <ElDrawer
    v-model="dockOpen"
    direction="rtl"
    :size="420"
    append-to-body
    class="rag-wf-context-drawer"
    modal-class="rag-wf-drawer-light-mask"
    body-class="rag-wf-context-drawer-body"
    :close-on-click-modal="true"
  >
    <template #header>
      <div class="rag-wf-context-drawer-head">
        <div class="rag-wf-context-tabs">
          <button type="button" class="rag-wf-context-tab" :class="{ on: dockTab === 'json' }" @click="dockTab = 'json'">
            JSON
          </button>
          <button type="button" class="rag-wf-context-tab" :class="{ on: dockTab === 'run' }" @click="dockTab = 'run'">
            运行结果
          </button>
          <button type="button" class="rag-wf-context-tab" :class="{ on: dockTab === 'node_output' }" @click="dockTab = 'node_output'">
            节点输出
          </button>
          <button type="button" class="rag-wf-context-tab" :class="{ on: dockTab === 'history' }" @click="dockTab = 'history'">
            运行记录
          </button>
        </div>
      </div>
    </template>

    <div class="rag-wf-context-body">
      <div v-show="dockTab === 'json'" class="rag-wf-context-panel">
        <WorkflowJsonFields v-model:workflow-preview="workflowPreviewModel" v-model:input-data-json="inputDataJsonModel" />
      </div>
      <div v-show="dockTab === 'run'" class="rag-wf-context-panel">
        <RuntimeTracePanel
          embedded
          :state="props.traceState || fallbackTraceState"
          :ordered-nodes="props.traceOrderedNodes || []"
          :run-detail="runDetailFull"
          :import-fallback-record="props.traceImportFallback"
          @update-width="emit('trace-update-width', $event)"
          @update-collapsed="emit('trace-update-collapsed', $event)"
          @select-node="emit('trace-select-node', $event)"
          @select-tab="emit('trace-select-tab', $event)"
          @refresh="emit('trace-refresh')"
          @toggle-auto-scroll="emit('trace-toggle-auto-scroll', $event)"
          @import-json="emit('trace-import-json', $event)"
        />
      </div>
      <div v-show="dockTab === 'node_output'" class="rag-wf-context-panel">
        <WorkflowRunResult
          mode="dock"
          :last-run-raw="lastRunRaw"
          :run-error-msg="runErrorMsg"
          :run-status="runStatus"
          :answer-snippet="answerSnippet"
          :preferred-node-id="activeNodeId"
          :node-title-map="nodeTitleMap || {}"
        />
      </div>
      <div v-show="dockTab === 'history'" class="rag-wf-context-panel">
        <WorkflowRunRecords
          mode="dock"
          v-model:filter-runs-by-current-workflow="filterRunsByCurrentWorkflow"
          v-model:run-detail-visible="runDetailVisibleModel"
          :run-history-list="runHistoryList"
          :run-history-loading="runHistoryLoading"
          :run-detail-loading="runDetailLoading"
          :run-detail-full="runDetailFull"
          :pretty-json="prettyJson"
          @refresh-list="emit('refresh-run-history')"
          @open-detail="row => emit('open-run-detail', row)"
          @delete-record="id => emit('delete-run-record', id)"
        />
      </div>
    </div>
  </ElDrawer>
</template>

<style scoped lang="scss">
.rag-wf-dock-icon-btn {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  border: 1px solid rgb(226 232 240 / 90%);
  background: rgb(255 255 255 / 96%);
  color: #64748b;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 14px rgb(15 23 42 / 5%);
  transition:
    border-color 0.12s,
    color 0.12s,
    box-shadow 0.12s;
}

.rag-wf-dock-icon-btn:hover {
  color: #2563eb;
  border-color: rgb(147 197 253 / 45%);
  background: #eef4ff;
}

.rag-wf-dock-icon-btn.is-on {
  color: #1d4ed8;
  border-color: rgb(147 197 253 / 70%);
  box-shadow: 0 6px 16px rgb(37 99 235 / 8%);
}

.rag-wf-dock-ico {
  font-size: 20px;
}

</style>
