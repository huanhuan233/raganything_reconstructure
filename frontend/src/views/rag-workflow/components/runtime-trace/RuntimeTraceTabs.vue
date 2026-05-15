<script setup lang="ts">
import type { RuntimeTraceTabKey } from './RuntimeTraceTypes';

const modelValue = defineModel<RuntimeTraceTabKey>({ required: true });

const tabs: Array<{ key: RuntimeTraceTabKey; label: string }> = [
  { key: 'input', label: '输入' },
  { key: 'output', label: '输出' },
  { key: 'detail', label: '详情' },
  { key: 'trace', label: 'Trace' }
];
</script>

<template>
  <div class="trace-tabs">
    <button
      v-for="tab in tabs"
      :key="tab.key"
      type="button"
      class="trace-tabs__btn"
      :class="{ active: modelValue === tab.key }"
      @click="modelValue = tab.key"
    >
      {{ tab.label }}
    </button>
  </div>
</template>

<style scoped lang="scss">
.trace-tabs {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.trace-tabs__btn {
  border: 1px solid #e5e7eb;
  background: #f8fafc;
  color: #475569;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
}

.trace-tabs__btn.active {
  border-color: #93c5fd;
  background: #eff6ff;
  color: #1d4ed8;
}
</style>

