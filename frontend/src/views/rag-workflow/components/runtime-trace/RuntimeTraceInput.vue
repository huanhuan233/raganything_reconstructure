<script setup lang="ts">
import { computed } from 'vue';
import type { RuntimeTraceNodeDetail } from './RuntimeTraceTypes';

const props = defineProps<{
  detail: RuntimeTraceNodeDetail | null;
}>();

const prettyInput = computed(() => {
  if (!props.detail) return '';
  try {
    return JSON.stringify(props.detail.input ?? props.detail.input_preview ?? {}, null, 2);
  } catch {
    return String(props.detail.input ?? props.detail.input_preview ?? '');
  }
});

const prettyConfig = computed(() => {
  if (!props.detail) return '';
  try {
    return JSON.stringify(props.detail.config ?? {}, null, 2);
  } catch {
    return String(props.detail.config ?? '');
  }
});
</script>

<template>
  <div class="trace-tab-block">
    <div v-if="!detail" class="trace-empty">请选择节点</div>
    <template v-else>
      <div class="trace-kv"><strong>节点类型：</strong>{{ detail.node_type || '-' }}</div>
      <div class="trace-kv"><strong>状态：</strong>{{ detail.status || '-' }}</div>
      <div class="trace-kv"><strong>耗时：</strong>{{ detail.duration_ms ?? '-' }} ms</div>
      <div class="trace-title">配置 JSON</div>
      <pre class="trace-pre">{{ prettyConfig }}</pre>
      <div class="trace-title">输入 JSON</div>
      <pre class="trace-pre">{{ prettyInput }}</pre>
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

.trace-kv {
  font-size: 12px;
  color: #334155;
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
  max-height: 220px;
  overflow: auto;
}
</style>

