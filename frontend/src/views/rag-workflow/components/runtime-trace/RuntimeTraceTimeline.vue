<script setup lang="ts">
import { computed } from 'vue';
import type { RuntimeTraceNodeState } from './RuntimeTraceTypes';

const props = defineProps<{
  nodes: RuntimeTraceNodeState[];
  timeline?: Array<Record<string, unknown>>;
}>();

const rows = computed(() => {
  const base = props.nodes
    .filter(n => typeof n.duration_ms === 'number' && (n.duration_ms || 0) >= 0)
    .map(n => ({ node_id: n.node_id, name: n.node_name || n.node_id, duration_ms: Number(n.duration_ms || 0) }));
  return base;
});

const maxDuration = computed(() => {
  const vals = rows.value.map(x => x.duration_ms);
  return vals.length ? Math.max(...vals, 1) : 1;
});

function widthPercent(ms: number) {
  return Math.max(4, Math.round((ms / maxDuration.value) * 100));
}
</script>

<template>
  <div class="trace-timeline">
    <div v-if="!rows.length" class="trace-empty">暂无时间轴数据</div>
    <div v-for="row in rows" :key="row.node_id" class="trace-line">
      <div class="trace-line__name">{{ row.name }}</div>
      <div class="trace-line__bar-wrap">
        <div class="trace-line__bar" :style="{ width: `${widthPercent(row.duration_ms)}%` }"></div>
      </div>
      <div class="trace-line__ms">{{ row.duration_ms }}ms</div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.trace-timeline {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.trace-empty {
  font-size: 12px;
  color: #94a3b8;
}

.trace-line {
  display: grid;
  grid-template-columns: 1fr 1.5fr auto;
  align-items: center;
  gap: 8px;
}

.trace-line__name {
  font-size: 12px;
  color: #334155;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trace-line__bar-wrap {
  height: 10px;
  border-radius: 999px;
  background: #e2e8f0;
  overflow: hidden;
}

.trace-line__bar {
  height: 100%;
  background: linear-gradient(90deg, #93c5fd, #3b82f6);
}

.trace-line__ms {
  font-size: 11px;
  color: #64748b;
  font-variant-numeric: tabular-nums;
}
</style>

