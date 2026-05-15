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
const summary = computed(() => asRecord(data.value.context_summary));
const contextStr = computed(() => String(data.value.context_str ?? ''));

const blocksAll = computed(() => {
  const rows = data.value.context_blocks;
  return Array.isArray(rows) ? rows : [];
});

const blocksView = computed(() => blocksAll.value.slice(0, 20).map(x => asRecord(x)));

function scoreText(v: unknown): string {
  const n = Number(v);
  return Number.isFinite(n) ? n.toFixed(4) : '0.0000';
}

function textPreview(v: unknown): string {
  const s = String(v ?? '').replace(/\s+/g, ' ').trim();
  if (!s) return '—';
  return s.length > 120 ? `${s.slice(0, 117)}...` : s;
}

async function copyContextStr() {
  const text = contextStr.value;
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    window.$message?.success('已复制 context_str');
  } catch {
    window.$message?.warning('复制失败，请手动复制');
  }
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
  <div class="rag-wf-context-panel">
    <div class="rag-wf-context-card">
      <div class="rag-wf-context-cap">context_summary</div>
      <div class="rag-wf-context-grid">
        <div class="rag-wf-context-kv"><span class="k">input_results</span><span class="v">{{ summary.input_results ?? 0 }}</span></div>
        <div class="rag-wf-context-kv"><span class="k">used_results</span><span class="v">{{ summary.used_results ?? 0 }}</span></div>
        <div class="rag-wf-context-kv"><span class="k">context_chars</span><span class="v">{{ summary.context_chars ?? 0 }}</span></div>
        <div class="rag-wf-context-kv"><span class="k">max_context_chars</span><span class="v">{{ summary.max_context_chars ?? 0 }}</span></div>
      </div>
    </div>

    <div class="rag-wf-context-card">
      <div class="rag-wf-context-cap rag-wf-context-cap--row">
        <span>context_str</span>
        <ElButton size="small" text type="primary" @click="copyContextStr">复制</ElButton>
      </div>
      <ElInput
        :model-value="contextStr"
        type="textarea"
        readonly
        :autosize="{ minRows: 5, maxRows: 12 }"
        class="rag-wf-context-textarea"
      />
    </div>

    <div class="rag-wf-context-card">
      <div class="rag-wf-context-cap">context_blocks（前 20 条）</div>
      <ElTable v-if="blocksView.length" :data="blocksView" size="small" stripe border class="rag-wf-context-table" max-height="280">
        <ElTableColumn prop="result_id" label="result_id" min-width="120" show-overflow-tooltip />
        <ElTableColumn prop="source" label="source" width="110" show-overflow-tooltip />
        <ElTableColumn label="score" width="100" align="right">
          <template #default="{ row }">
            <span class="rag-wf-context-cell">{{ scoreText((row as Record<string, unknown>).score) }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="text" min-width="260">
          <template #default="{ row }">
            <span class="rag-wf-context-cell">{{ textPreview((row as Record<string, unknown>).text) }}</span>
          </template>
        </ElTableColumn>
      </ElTable>
      <div v-else class="rag-wf-context-empty">无 context_blocks</div>
    </div>

    <ElCollapse v-model="rawDataOpen" class="rag-wf-context-raw-collapse">
      <ElCollapseItem title="原始 data JSON" name="raw">
        <ElScrollbar max-height="220px">
          <pre class="rag-wf-context-json-pre">{{ formatJson(result.data) }}</pre>
        </ElScrollbar>
      </ElCollapseItem>
    </ElCollapse>
  </div>
</template>

<style scoped lang="scss">
.rag-wf-context-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.rag-wf-context-card {
  padding: 10px;
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  background: #fff;
}

.rag-wf-context-cap {
  font-size: 11px;
  font-weight: 600;
  color: #9ca3af;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  margin-bottom: 8px;

  &--row {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
}

.rag-wf-context-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 12px;
}

.rag-wf-context-kv {
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

.rag-wf-context-textarea :deep(.el-textarea__inner) {
  font-family: Menlo, Monaco, Consolas, 'Courier New', monospace;
  font-size: 11px;
  line-height: 1.45;
}

.rag-wf-context-table {
  width: 100%;
}

.rag-wf-context-cell {
  font-size: 12px;
  color: #334155;
}

.rag-wf-context-empty {
  font-size: 12px;
  color: #94a3b8;
  padding: 8px 0;
}

.rag-wf-context-raw-collapse {
  border: none;
}

.rag-wf-context-raw-collapse :deep(.el-collapse-item__header) {
  height: auto;
  min-height: 36px;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  padding: 0 4px;
  background: transparent;
}

.rag-wf-context-raw-collapse :deep(.el-collapse-item__wrap) {
  border: none;
}

.rag-wf-context-raw-collapse :deep(.el-collapse-item__content) {
  padding: 6px 0 0;
}

.rag-wf-context-json-pre {
  margin: 0;
  font-size: 11px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: Menlo, Monaco, Consolas, 'Courier New', monospace;
}
</style>
