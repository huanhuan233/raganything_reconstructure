<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { Icon } from '@iconify/vue';
import SemanticRuntimePanel from '@/components/runtime/SemanticRuntimePanel.vue';
import RuntimeTimeline from '@/components/runtime/RuntimeTimeline.vue';
import type { RagRunHistoryDetail } from '@/types/ragWorkflow';
import { mergeSemanticObservatoryFromRun } from '@/components/runtime/useSemanticObservatory';
import RuntimeTraceDetail from './RuntimeTraceDetail.vue';
import RuntimeTraceInput from './RuntimeTraceInput.vue';
import RuntimeTraceNodeCard from './RuntimeTraceNodeCard.vue';
import RuntimeTraceOutput from './RuntimeTraceOutput.vue';
import RuntimeTraceTabs from './RuntimeTraceTabs.vue';
import RuntimeTraceTimeline from './RuntimeTraceTimeline.vue';
import type { RuntimeTraceState, RuntimeTraceTabKey } from './RuntimeTraceTypes';

const props = defineProps<{
  state: RuntimeTraceState;
  orderedNodes: RuntimeTraceState['nodes'];
  embedded?: boolean;
  runDetail?: RagRunHistoryDetail | null;
  importFallbackRecord?: Record<string, unknown> | null;
}>();

const observatorySnap = computed(() =>
  mergeSemanticObservatoryFromRun(
    (props.runDetail ?? props.importFallbackRecord ?? null) as RagRunHistoryDetail | null,
    { liveTraceTimeline: props.state.timeline }
  )
);

const semanticTraceTimeline = computed(() => observatorySnap.value?.timeline ?? []);

const emit = defineEmits<{
  'update-width': [width: number];
  'update-collapsed': [collapsed: boolean];
  'select-node': [nodeId: string];
  'select-tab': [tab: RuntimeTraceTabKey];
  refresh: [];
  'toggle-auto-scroll': [enabled: boolean];
  'import-json': [payload: unknown];
}>();

const listRef = ref<HTMLElement | null>(null);
const fileInputRef = ref<HTMLInputElement | null>(null);
const resizing = ref(false);
const dragStartX = ref(0);
const dragStartW = ref(0);

function beginResize(e: MouseEvent) {
  resizing.value = true;
  dragStartX.value = e.clientX;
  dragStartW.value = props.state.panelWidth;
  window.addEventListener('mousemove', onDragResize);
  window.addEventListener('mouseup', stopResize);
}

function onDragResize(e: MouseEvent) {
  if (!resizing.value) return;
  const delta = dragStartX.value - e.clientX;
  emit('update-width', dragStartW.value + delta);
}

function stopResize() {
  if (!resizing.value) return;
  resizing.value = false;
  window.removeEventListener('mousemove', onDragResize);
  window.removeEventListener('mouseup', stopResize);
}

function openJsonUploader() {
  fileInputRef.value?.click();
}

async function onJsonFileChange(e: Event) {
  const input = e.target as HTMLInputElement;
  const f = input.files?.[0];
  if (!f) return;
  try {
    const txt = await f.text();
    const obj = JSON.parse(txt) as unknown;
    emit('import-json', obj);
  } catch {
    window.$message?.error('JSON 文件解析失败');
  } finally {
    input.value = '';
  }
}

onBeforeUnmount(() => {
  stopResize();
});

watch(
  () => props.state.currentNodeId,
  async id => {
    if (!id || !props.state.autoScroll) return;
    await nextTick();
    const el = listRef.value?.querySelector(`[data-node-id="${id}"]`) as HTMLElement | null;
    el?.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }
);

const selectedTab = computed<RuntimeTraceTabKey>({
  get() {
    return props.state.selectedTab;
  },
  set(v) {
    emit('select-tab', v);
  }
});

</script>

<template>
  <aside
    class="runtime-trace-panel"
    :class="{ collapsed: state.panelCollapsed && !embedded, embedded: !!embedded }"
    :style="embedded ? {} : { width: `${state.panelWidth}px` }"
  >
    <div v-if="!embedded" class="runtime-trace-panel__resize" @mousedown.prevent="beginResize"></div>
    <div class="runtime-trace-panel__header">
      <div class="runtime-trace-panel__title">
        Industrial Semantic Trace
        <span v-if="state.running" class="runtime-trace-panel__running">运行中</span>
      </div>
      <div class="runtime-trace-panel__actions">
        <button type="button" class="trace-icon-btn" @click="emit('refresh')">
          <Icon icon="mdi:refresh" />
        </button>
        <button type="button" class="trace-icon-btn" title="上传 run_id.json" @click="openJsonUploader">
          <Icon icon="mdi:upload" />
        </button>
        <button type="button" class="trace-icon-btn" @click="emit('toggle-auto-scroll', !state.autoScroll)">
          <Icon :icon="state.autoScroll ? 'mdi:arrow-down-circle' : 'mdi:arrow-down-circle-outline'" />
        </button>
        <button v-if="!embedded" type="button" class="trace-icon-btn" @click="emit('update-collapsed', !state.panelCollapsed)">
          <Icon :icon="state.panelCollapsed ? 'mdi:chevron-left' : 'mdi:chevron-right'" />
        </button>
      </div>
    </div>

    <template v-if="embedded || !state.panelCollapsed">
      <input
        ref="fileInputRef"
        type="file"
        accept=".json,application/json"
        class="runtime-trace-panel__file-input"
        @change="onJsonFileChange"
      />
      <div class="runtime-trace-panel__meta">
        <span>run_id: {{ state.runId || '-' }}</span>
        <span>phase: {{ state.phase || (state.running ? 'running' : 'idle') }}</span>
      </div>

      <div ref="listRef" class="runtime-trace-panel__list">
        <div
          v-for="node in orderedNodes"
          :key="node.node_id"
          class="runtime-trace-panel__card-wrap"
          :data-node-id="node.node_id"
        >
          <RuntimeTraceNodeCard
            :node="node"
            :selected="state.selectedNodeId === node.node_id"
            :current="state.currentNodeId === node.node_id"
            @select="emit('select-node', $event)"
          />
        </div>
      </div>

      <div class="runtime-trace-panel__detail">
        <RuntimeTraceTabs v-model="selectedTab" />
        <div class="runtime-trace-panel__detail-body">
          <RuntimeTraceInput v-if="selectedTab === 'input'" :detail="state.selectedNodeDetail" />
          <RuntimeTraceOutput v-else-if="selectedTab === 'output'" :detail="state.selectedNodeDetail" />
          <RuntimeTraceDetail v-else-if="selectedTab === 'detail'" :detail="state.selectedNodeDetail" />
          <SemanticRuntimePanel v-else-if="selectedTab === 'observatory'" :snapshot="observatorySnap" />
          <div v-else class="runtime-trace-panel__trace-stack">
            <div class="runtime-trace-panel__trace-subttl">生命周期 Semantic lifecycle</div>
            <RuntimeTimeline :events="semanticTraceTimeline" />
            <div class="runtime-trace-panel__trace-subttl runtime-trace-panel__trace-subttl--muted">节点耗时</div>
            <RuntimeTraceTimeline :nodes="orderedNodes" :timeline="state.timeline" />
          </div>
        </div>
      </div>
    </template>
  </aside>
</template>

<style scoped lang="scss">
.runtime-trace-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  min-width: 320px;
  max-width: 680px;
  height: 100%;
  background: #fff;
  border-left: 1px solid #e5e7eb;
  box-shadow: -8px 0 20px rgb(15 23 42 / 6%);
}

.runtime-trace-panel.collapsed {
  width: 44px !important;
  min-width: 44px;
}

.runtime-trace-panel.embedded {
  width: 100%;
  min-width: 0;
  max-width: none;
  border-left: none;
  box-shadow: none;
  height: 100%;
}

.runtime-trace-panel__resize {
  position: absolute;
  left: -4px;
  top: 0;
  width: 8px;
  height: 100%;
  cursor: col-resize;
  z-index: 2;
}

.runtime-trace-panel__header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 10px 8px 12px;
  border-bottom: 1px solid #eef2f7;
}

.runtime-trace-panel__title {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.runtime-trace-panel__running {
  margin-left: 8px;
  font-size: 11px;
  color: #1d4ed8;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 999px;
  padding: 1px 6px;
}

.runtime-trace-panel__actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.trace-icon-btn {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
  background: #fff;
  color: #64748b;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.runtime-trace-panel__meta {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 12px;
  border-bottom: 1px solid #f1f5f9;
  font-size: 11px;
  color: #64748b;
}

.runtime-trace-panel__list {
  flex: 1 1 auto;
  min-height: 180px;
  overflow: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.runtime-trace-panel__detail {
  flex-shrink: 0;
  border-top: 1px solid #eef2f7;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 42%;
}

.runtime-trace-panel__detail-body {
  min-height: 120px;
  max-height: min(440px, 48vh);
  overflow: auto;
}

.runtime-trace-panel__trace-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.runtime-trace-panel__trace-subttl {
  font-size: 11px;
  font-weight: 700;
  color: #475569;
}

.runtime-trace-panel__trace-subttl--muted {
  font-weight: 600 !important;
  color: #94a3b8 !important;
}

.runtime-trace-panel__file-input {
  display: none;
}
</style>

