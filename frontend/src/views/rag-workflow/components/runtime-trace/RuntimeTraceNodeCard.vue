<script setup lang="ts">
import { computed } from 'vue';
import type { RuntimeTraceNodeState } from './RuntimeTraceTypes';

const props = defineProps<{
  node: RuntimeTraceNodeState;
  selected?: boolean;
  current?: boolean;
}>();

const emit = defineEmits<{
  select: [nodeId: string];
}>();

const statusClass = computed(() => `status-${props.node.status || 'pending'}`);
const durationText = computed(() => {
  const d = props.node.duration_ms;
  return typeof d === 'number' && d >= 0 ? `${d}ms` : '--';
});
const statusIcon = computed(() => {
  switch (props.node.status) {
    case 'running':
      return '⏳';
    case 'success':
      return '✔';
    case 'error':
      return '✖';
    case 'skipped':
      return '⏭';
    default:
      return '•';
  }
});
</script>

<template>
  <button
    type="button"
    class="trace-node-card"
    :class="[statusClass, { selected: !!selected, current: !!current }]"
    @click="emit('select', node.node_id)"
  >
    <div class="trace-node-card__head">
      <span class="trace-node-card__icon">{{ statusIcon }}</span>
      <span class="trace-node-card__name">{{ node.node_name || node.node_id }}</span>
      <span class="trace-node-card__dur">{{ durationText }}</span>
    </div>
    <div class="trace-node-card__sub">{{ node.node_type || node.node_id }}</div>
  </button>
</template>

<style scoped lang="scss">
.trace-node-card {
  width: 100%;
  text-align: left;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #fff;
  padding: 8px 10px;
  cursor: pointer;
  transition: border-color 0.12s ease, box-shadow 0.12s ease;
}

.trace-node-card:hover {
  border-color: #cbd5e1;
}

.trace-node-card.selected {
  border-color: #60a5fa;
  box-shadow: 0 0 0 2px rgb(59 130 246 / 12%);
}

.trace-node-card.current {
  box-shadow: 0 0 0 2px rgb(37 99 235 / 16%);
}

.trace-node-card__head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.trace-node-card__icon {
  width: 18px;
  text-align: center;
  flex-shrink: 0;
}

.trace-node-card__name {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trace-node-card__dur {
  font-size: 12px;
  color: #64748b;
  flex-shrink: 0;
}

.trace-node-card__sub {
  margin-top: 4px;
  font-size: 11px;
  color: #64748b;
  font-family: ui-monospace, Menlo, Monaco, Consolas, monospace;
  word-break: break-all;
}

.trace-node-card.status-running {
  border-color: #93c5fd;
  background: #eff6ff;
}

.trace-node-card.status-success {
  border-color: #bbf7d0;
  background: #f0fdf4;
}

.trace-node-card.status-error {
  border-color: #fecaca;
  background: #fef2f2;
}

.trace-node-card.status-skipped {
  border-color: #e5e7eb;
  background: #f8fafc;
}
</style>

