<script setup lang="ts">
import { computed } from 'vue';
import type { RuntimeTraceNodeDetail } from './RuntimeTraceTypes';

const props = defineProps<{
  detail: RuntimeTraceNodeDetail | null;
}>();

const prettyOutput = computed(() => {
  if (!props.detail) return '';
  try {
    return JSON.stringify(props.detail.output ?? props.detail.output_preview ?? {}, null, 2);
  } catch {
    return String(props.detail.output ?? props.detail.output_preview ?? '');
  }
});

const cards = computed(() => {
  const s = (props.detail?.summary || {}) as Record<string, unknown>;
  const arr: Array<{ label: string; value: unknown }> = [];
  const keys = [
    ['graph_node_count', 'Graph nodes'],
    ['graph_edge_count', 'Graph edges'],
    ['entity_count', 'Entities'],
    ['relation_count', 'Relations'],
    ['constraint_count', 'Constraints'],
    ['processed_count', 'Processed'],
    ['vlm_used_count', 'VLM used'],
    ['embedding_total', 'Embeddings'],
    ['with_vector', 'With vector']
  ] as const;
  for (const [k, label] of keys) {
    if (k in s) arr.push({ label, value: s[k] });
  }
  return arr;
});
</script>

<template>
  <div class="trace-tab-block">
    <div v-if="!detail" class="trace-empty">请选择节点</div>
    <template v-else>
      <div class="trace-metrics">
        <div v-for="item in cards" :key="item.label" class="trace-metric">
          <span class="trace-metric__label">{{ item.label }}</span>
          <span class="trace-metric__value">{{ item.value }}</span>
        </div>
      </div>
      <div class="trace-title">输出 JSON</div>
      <pre class="trace-pre">{{ prettyOutput }}</pre>
    </template>
  </div>
</template>

<style scoped lang="scss">
.trace-tab-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.trace-empty {
  font-size: 12px;
  color: #94a3b8;
}

.trace-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.trace-metric {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 6px 8px;
  background: #fff;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.trace-metric__label {
  font-size: 11px;
  color: #64748b;
}

.trace-metric__value {
  font-size: 13px;
  color: #0f172a;
  font-weight: 600;
}

.trace-title {
  font-size: 12px;
  color: #64748b;
  margin-top: 4px;
}

.trace-pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 11px;
  line-height: 1.5;
  font-family: ui-monospace, Menlo, Monaco, Consolas, monospace;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 8px;
  max-height: 260px;
  overflow: auto;
}
</style>

