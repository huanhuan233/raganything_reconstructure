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

const summary = computed(() => asRecord(data.value.storage_summary));

const refsAll = computed(() => {
  const r = data.value.storage_refs;
  return Array.isArray(r) ? r : [];
});

const refsView = computed(() => refsAll.value.slice(0, 20).map(x => asRecord(x)));

const byStatus = computed(() => asRecord(summary.value.by_status));

const storedN = computed(() => Number(byStatus.value.stored ?? 0));
const skippedN = computed(() => Number(byStatus.value.skipped ?? 0));
const failedN = computed(() => Number(byStatus.value.failed ?? 0));

const backendDistribution = computed(() => {
  const m: Record<string, number> = {};
  for (const r of refsAll.value) {
    const o = asRecord(r);
    const b = String(o.backend ?? 'unknown').trim() || 'unknown';
    m[b] = (m[b] ?? 0) + 1;
  }
  return m;
});

const backendDistLine = computed(() => {
  const pairs = Object.entries(backendDistribution.value);
  if (!pairs.length) return '—';
  return pairs.map(([k, n]) => `${k}: ${n}`).join(' · ');
});

function statusTagType(status: unknown): 'success' | 'warning' | 'danger' | 'info' {
  const s = String(status ?? '').toLowerCase();
  if (s === 'stored') return 'success';
  if (s === 'skipped') return 'warning';
  if (s === 'failed') return 'danger';
  return 'info';
}

function warnErrCell(row: Record<string, unknown>): string {
  const w = row.warning;
  const e = row.error;
  const ws = typeof w === 'string' && w.trim() ? w.trim() : '';
  const es = typeof e === 'string' && e.trim() ? e.trim() : '';
  if (ws && es) return `${ws}\n${es}`;
  return ws || es || '—';
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
  <div class="rag-wf-storage-panel">
    <div class="rag-wf-storage-card">
      <div class="rag-wf-storage-cap">存储摘要</div>
      <div class="rag-wf-storage-grid">
        <div class="rag-wf-storage-kv"><span class="k">total_records</span><span class="v">{{ summary.total_records ?? '—' }}</span></div>
        <div class="rag-wf-storage-kv"><span class="k">stored</span><span class="v v--ok">{{ storedN }}</span></div>
        <div class="rag-wf-storage-kv"><span class="k">skipped</span><span class="v v--skip">{{ skippedN }}</span></div>
        <div class="rag-wf-storage-kv"><span class="k">failed</span><span class="v v--fail">{{ failedN }}</span></div>
        <div class="rag-wf-storage-kv rag-wf-storage-kv--full">
          <span class="k">backend_distribution</span>
          <span class="v v--wrap">{{ backendDistLine }}</span>
        </div>
      </div>
    </div>

    <div class="rag-wf-storage-card">
      <div class="rag-wf-storage-cap">存储引用（前 20 条）</div>
      <ElTable v-if="refsView.length" :data="refsView" size="small" stripe border class="rag-wf-storage-table" max-height="280">
        <ElTableColumn prop="record_id" label="record_id" min-width="120" show-overflow-tooltip />
        <ElTableColumn prop="pipeline" label="pipeline" width="120" show-overflow-tooltip />
        <ElTableColumn prop="backend" label="backend" width="100" show-overflow-tooltip />
        <ElTableColumn prop="target" label="target" min-width="140" show-overflow-tooltip />
        <ElTableColumn label="status" width="96" align="center">
          <template #default="{ row }">
            <ElTag :type="statusTagType(row.status)" size="small" effect="plain">{{ row.status ?? '—' }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="warning / error" min-width="160">
          <template #default="{ row }">
            <span class="rag-wf-storage-warn-cell">{{ warnErrCell(row as Record<string, unknown>) }}</span>
          </template>
        </ElTableColumn>
      </ElTable>
      <div v-else class="rag-wf-storage-empty">无 storage_refs</div>
    </div>

    <ElCollapse v-model="rawDataOpen" class="rag-wf-storage-raw-collapse">
      <ElCollapseItem title="原始 data JSON" name="raw">
        <ElScrollbar max-height="220px">
          <pre class="rag-wf-storage-json-pre">{{ formatJson(result.data) }}</pre>
        </ElScrollbar>
      </ElCollapseItem>
    </ElCollapse>
  </div>
</template>

<style scoped lang="scss">
.rag-wf-storage-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.rag-wf-storage-card {
  padding: 10px;
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  background: #fff;
}

.rag-wf-storage-cap {
  font-size: 11px;
  font-weight: 600;
  color: #9ca3af;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  margin-bottom: 8px;
}

.rag-wf-storage-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 12px;
}

.rag-wf-storage-kv {
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

    &--ok {
      color: #15803d;
    }

    &--skip {
      color: #b45309;
    }

    &--fail {
      color: #b91c1c;
    }
  }
}

.rag-wf-storage-table {
  width: 100%;
}

.rag-wf-storage-warn-cell {
  font-size: 11px;
  line-height: 1.45;
  color: #64748b;
  white-space: pre-wrap;
  word-break: break-word;
}

.rag-wf-storage-empty {
  font-size: 12px;
  color: #94a3b8;
  padding: 8px 0;
}

.rag-wf-storage-raw-collapse {
  border: none;
}

.rag-wf-storage-raw-collapse :deep(.el-collapse-item__header) {
  height: auto;
  min-height: 36px;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  padding: 0 4px;
  background: transparent;
}

.rag-wf-storage-raw-collapse :deep(.el-collapse-item__wrap) {
  border: none;
}

.rag-wf-storage-raw-collapse :deep(.el-collapse-item__content) {
  padding: 6px 0 0;
}

.rag-wf-storage-json-pre {
  margin: 0;
  font-size: 11px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: Menlo, Monaco, Consolas, 'Courier New', monospace;
}
</style>
