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
const summary = computed(() => asRecord(data.value.rerank_summary));
const rows = computed(() => {
  const v = data.value.reranked_results;
  return Array.isArray(v) ? v.map(one => asRecord(one)).slice(0, 20) : [];
});

function scoreText(v: unknown): string {
  const n = Number(v);
  return Number.isFinite(n) ? n.toFixed(4) : '0.0000';
}

function textPreview(v: unknown): string {
  const s = String(v ?? '').replace(/\s+/g, ' ').trim();
  if (!s) return '—';
  return s.length > 120 ? `${s.slice(0, 117)}...` : s;
}

function formatJson(v: unknown): string {
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}
</script>

<template>
  <div class="rag-wf-rerank-panel">
    <div class="rag-wf-rerank-card">
      <div class="rag-wf-rerank-cap">rerank_summary</div>
      <div class="rag-wf-rerank-grid">
        <div class="rag-wf-rerank-kv"><span class="k">input_count</span><span class="v">{{ summary.input_count ?? 0 }}</span></div>
        <div class="rag-wf-rerank-kv"><span class="k">output_count</span><span class="v">{{ summary.output_count ?? 0 }}</span></div>
        <div class="rag-wf-rerank-kv"><span class="k">rerank_engine</span><span class="v">{{ summary.rerank_engine ?? 'runtime' }}</span></div>
        <div class="rag-wf-rerank-kv"><span class="k">rerank_model</span><span class="v">{{ summary.rerank_model ?? 'none' }}</span></div>
      </div>
    </div>

    <div class="rag-wf-rerank-card">
      <div class="rag-wf-rerank-cap">top reranked_results（前 20 条）</div>
      <ElTable v-if="rows.length" :data="rows" size="small" stripe border class="rag-wf-rerank-table" max-height="280">
        <ElTableColumn prop="source_type" label="source" width="96" />
        <ElTableColumn prop="modality" label="modality" width="96" />
        <ElTableColumn label="before" width="90" align="right">
          <template #default="{ row }">
            <span class="rag-wf-rerank-cell">{{ scoreText((row as Record<string, unknown>).score) }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="after" width="90" align="right">
          <template #default="{ row }">
            <span class="rag-wf-rerank-cell">{{ scoreText((row as Record<string, unknown>).rerank_score) }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="content" min-width="260">
          <template #default="{ row }">
            <span class="rag-wf-rerank-cell">{{ textPreview((row as Record<string, unknown>).content) }}</span>
          </template>
        </ElTableColumn>
      </ElTable>
      <div v-else class="rag-wf-rerank-empty">无 reranked_results</div>
    </div>

    <ElCollapse v-model="rawDataOpen" class="rag-wf-rerank-raw-collapse">
      <ElCollapseItem title="原始 data JSON" name="raw">
        <ElScrollbar max-height="220px">
          <pre class="rag-wf-rerank-json-pre">{{ formatJson(result.data) }}</pre>
        </ElScrollbar>
      </ElCollapseItem>
    </ElCollapse>
  </div>
</template>

<style scoped lang="scss">
.rag-wf-rerank-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.rag-wf-rerank-card {
  padding: 10px;
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  background: #fff;
}
.rag-wf-rerank-cap {
  font-size: 11px;
  font-weight: 600;
  color: #9ca3af;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  margin-bottom: 8px;
}
.rag-wf-rerank-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 12px;
}
.rag-wf-rerank-kv {
  display: flex;
  flex-direction: column;
  gap: 2px;
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
.rag-wf-rerank-cell {
  font-size: 12px;
  color: #334155;
}
.rag-wf-rerank-empty {
  font-size: 12px;
  color: #94a3b8;
  padding: 8px 0;
}
.rag-wf-rerank-raw-collapse {
  border: none;
}
.rag-wf-rerank-raw-collapse :deep(.el-collapse-item__header) {
  height: auto;
  min-height: 36px;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  padding: 0 4px;
  background: transparent;
}
.rag-wf-rerank-raw-collapse :deep(.el-collapse-item__wrap) {
  border: none;
}
.rag-wf-rerank-raw-collapse :deep(.el-collapse-item__content) {
  padding: 6px 0 0;
}
.rag-wf-rerank-json-pre {
  margin: 0;
  font-size: 11px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: Menlo, Monaco, Consolas, 'Courier New', monospace;
}
</style>
