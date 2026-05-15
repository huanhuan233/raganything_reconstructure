<script setup lang="ts">
import { computed, ref } from 'vue';

type NodeResultLike = {
  success?: boolean;
  data?: unknown;
  error?: string | null;
  metadata?: unknown;
};

const props = defineProps<{
  result: NodeResultLike;
}>();

const rawDataOpen = ref<string[]>([]);

function asRecord(v: unknown): Record<string, unknown> {
  return v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
}

const data = computed(() => asRecord(props.result.data));
const summary = computed(() => asRecord(data.value.graph_persist_summary));

const refsAll = computed(() => (Array.isArray(data.value.storage_refs) ? data.value.storage_refs : []));
const refsView = computed(() => refsAll.value.slice(0, 20).map(x => asRecord(x)));

function formatJson(v: unknown): string {
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}
</script>

<template>
  <div class="rag-wf-graph-persist-panel">
    <div class="rag-wf-graph-persist-card">
      <div class="rag-wf-graph-persist-cap">graph_persist_summary</div>
      <div class="rag-wf-graph-persist-grid">
        <div class="rag-wf-graph-persist-kv"><span class="k">graph_backend</span><span class="v">{{ summary.graph_backend ?? '—' }}</span></div>
        <div class="rag-wf-graph-persist-kv"><span class="k">workspace</span><span class="v">{{ summary.workspace ?? '—' }}</span></div>
        <div class="rag-wf-graph-persist-kv"><span class="k">entity_persisted</span><span class="v">{{ summary.entity_persisted ?? 0 }}</span></div>
        <div class="rag-wf-graph-persist-kv"><span class="k">relation_persisted</span><span class="v">{{ summary.relation_persisted ?? 0 }}</span></div>
        <div class="rag-wf-graph-persist-kv"><span class="k">component_persisted</span><span class="v">{{ summary.component_persisted ?? 0 }}</span></div>
      </div>
    </div>

    <div class="rag-wf-graph-persist-card">
      <div class="rag-wf-graph-persist-cap">storage_refs（前 20 条）</div>
      <ElTable v-if="refsView.length" :data="refsView" size="small" stripe border class="rag-wf-graph-persist-table" max-height="280">
        <ElTableColumn prop="record_type" label="record_type" width="100" show-overflow-tooltip />
        <ElTableColumn prop="entity_id" label="entity_id" min-width="120" show-overflow-tooltip />
        <ElTableColumn prop="relation_id" label="relation_id" min-width="120" show-overflow-tooltip />
        <ElTableColumn prop="backend" label="backend" width="110" show-overflow-tooltip />
        <ElTableColumn prop="workspace" label="workspace" min-width="120" show-overflow-tooltip />
        <ElTableColumn prop="status" label="status" width="90" show-overflow-tooltip />
      </ElTable>
      <div v-else class="rag-wf-graph-persist-empty">无 storage_refs</div>
    </div>

    <ElCollapse v-model="rawDataOpen" class="rag-wf-graph-persist-raw-collapse">
      <ElCollapseItem title="原始 data JSON" name="raw">
        <ElScrollbar max-height="220px">
          <pre class="rag-wf-graph-persist-json-pre">{{ formatJson(result.data) }}</pre>
        </ElScrollbar>
      </ElCollapseItem>
    </ElCollapse>
  </div>
</template>

<style scoped lang="scss">
.rag-wf-graph-persist-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.rag-wf-graph-persist-card {
  padding: 10px;
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  background: #fff;
}

.rag-wf-graph-persist-cap {
  font-size: 11px;
  font-weight: 600;
  color: #9ca3af;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  margin-bottom: 8px;
}

.rag-wf-graph-persist-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 12px;
}

.rag-wf-graph-persist-kv {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;

  .k {
    font-size: 11px;
    color: #94a3b8;
    font-family: ui-monospace, Menlo, Monaco, Consolas, monospace;
  }

  .v {
    font-size: 13px;
    color: #0f172a;
    font-weight: 600;
  }
}

.rag-wf-graph-persist-table {
  width: 100%;
}

.rag-wf-graph-persist-empty {
  font-size: 12px;
  color: #94a3b8;
  padding: 8px 0;
}

.rag-wf-graph-persist-raw-collapse {
  border: none;
}

.rag-wf-graph-persist-raw-collapse :deep(.el-collapse-item__header) {
  height: auto;
  min-height: 36px;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  padding: 0 4px;
  background: transparent;
}

.rag-wf-graph-persist-raw-collapse :deep(.el-collapse-item__wrap) {
  border: none;
}

.rag-wf-graph-persist-raw-collapse :deep(.el-collapse-item__content) {
  padding: 6px 0 0;
}

.rag-wf-graph-persist-json-pre {
  margin: 0;
  font-size: 11px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: Menlo, Monaco, Consolas, 'Courier New', monospace;
}
</style>
