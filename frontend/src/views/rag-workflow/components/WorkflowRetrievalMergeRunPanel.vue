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
const summary = computed(() => asRecord(data.value.merge_summary));

const unifiedAll = computed(() => {
  const r = data.value.unified_results;
  return Array.isArray(r) ? r : [];
});

const unifiedView = computed(() => unifiedAll.value.slice(0, 20).map(x => asRecord(x)));

const sourceDistLine = computed(() => {
  const d = asRecord(summary.value.source_distribution);
  const pairs = Object.entries(d);
  if (!pairs.length) return '—';
  return pairs.map(([k, n]) => `${k}:${n}`).join(' · ');
});

function sourceLine(row: Record<string, unknown>): string {
  const s = row.sources;
  if (!Array.isArray(s)) return '—';
  return s.map(x => String(x)).join('/');
}

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
  <div class="rag-wf-merge-panel">
    <div class="rag-wf-merge-card">
      <div class="rag-wf-merge-cap">merge_summary</div>
      <div class="rag-wf-merge-grid">
        <div class="rag-wf-merge-kv"><span class="k">total_input</span><span class="v">{{ summary.total_input ?? 0 }}</span></div>
        <div class="rag-wf-merge-kv"><span class="k">total_output</span><span class="v">{{ summary.total_output ?? 0 }}</span></div>
        <div class="rag-wf-merge-kv"><span class="k">deduplicated</span><span class="v">{{ summary.deduplicated ?? 0 }}</span></div>
        <div class="rag-wf-merge-kv"><span class="k">fusion_strategy</span><span class="v">{{ summary.fusion_strategy ?? 'max_score' }}</span></div>
        <div class="rag-wf-merge-kv rag-wf-merge-kv--full">
          <span class="k">source_distribution</span>
          <span class="v v--wrap">{{ sourceDistLine }}</span>
        </div>
      </div>
    </div>

    <div class="rag-wf-merge-card">
      <div class="rag-wf-merge-cap">unified_results（前 20 条）</div>
      <ElTable v-if="unifiedView.length" :data="unifiedView" size="small" stripe border class="rag-wf-merge-table" max-height="280">
        <ElTableColumn prop="result_id" label="result_id" min-width="120" show-overflow-tooltip />
        <ElTableColumn label="sources" width="130">
          <template #default="{ row }">
            <span class="rag-wf-merge-cell">{{ sourceLine(row as Record<string, unknown>) }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="score" width="100" align="right">
          <template #default="{ row }">
            <span class="rag-wf-merge-cell">{{ scoreText((row as Record<string, unknown>).score) }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="text" min-width="240">
          <template #default="{ row }">
            <span class="rag-wf-merge-cell">{{ textPreview((row as Record<string, unknown>).text) }}</span>
          </template>
        </ElTableColumn>
      </ElTable>
      <div v-else class="rag-wf-merge-empty">无 unified_results</div>
    </div>

    <ElCollapse v-model="rawDataOpen" class="rag-wf-merge-raw-collapse">
      <ElCollapseItem title="原始 data JSON" name="raw">
        <ElScrollbar max-height="220px">
          <pre class="rag-wf-merge-json-pre">{{ formatJson(result.data) }}</pre>
        </ElScrollbar>
      </ElCollapseItem>
    </ElCollapse>
  </div>
</template>

<style scoped lang="scss">
.rag-wf-merge-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.rag-wf-merge-card {
  padding: 10px;
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  background: #fff;
}

.rag-wf-merge-cap {
  font-size: 11px;
  font-weight: 600;
  color: #9ca3af;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  margin-bottom: 8px;
}

.rag-wf-merge-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 12px;
}

.rag-wf-merge-kv {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;

  &--full {
    grid-column: 1 / -1;
  }

  .k {
    font-size: 11px;
    color: #94a3b8;
    font-family: ui-monospace, Menlo, Monaco, Consolas, monospace;
  }

  .v {
    font-size: 13px;
    color: #0f172a;
    font-weight: 600;

    &--wrap {
      font-weight: 500;
      white-space: pre-wrap;
      word-break: break-word;
    }
  }
}

.rag-wf-merge-table {
  width: 100%;
}

.rag-wf-merge-cell {
  font-size: 12px;
  color: #334155;
}

.rag-wf-merge-empty {
  font-size: 12px;
  color: #94a3b8;
  padding: 8px 0;
}

.rag-wf-merge-raw-collapse {
  border: none;
}

.rag-wf-merge-raw-collapse :deep(.el-collapse-item__header) {
  height: auto;
  min-height: 36px;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  padding: 0 4px;
  background: transparent;
}

.rag-wf-merge-raw-collapse :deep(.el-collapse-item__wrap) {
  border: none;
}

.rag-wf-merge-raw-collapse :deep(.el-collapse-item__content) {
  padding: 6px 0 0;
}

.rag-wf-merge-json-pre {
  margin: 0;
  font-size: 11px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: Menlo, Monaco, Consolas, 'Courier New', monospace;
}
</style>
