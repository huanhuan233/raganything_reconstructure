<script setup lang="ts">
import { computed } from 'vue';
import type { RuntimeTraceNodeDetail } from './RuntimeTraceTypes';

const props = defineProps<{
  detail: RuntimeTraceNodeDetail | null;
}>();

const detailRows = computed(() => {
  const d = props.detail;
  if (!d) return [];
  const s = (d.summary || {}) as Record<string, unknown>;
  const rows: Array<{ label: string; value: unknown }> = [];
  const push = (label: string, key: string) => {
    if (key in s) rows.push({ label, value: s[key] });
  };

  // 通用摘要
  push('Section detected', 'section_detected');
  push('Constraint extracted', 'constraint_count');
  push('ProcessStep extracted', 'process_step_count');
  push('Graph nodes persisted', 'node_persisted');
  push('Graph edges persisted', 'edge_persisted');
  push('Regex hits', 'regex_hits');
  push('Parser count', 'parser_count');
  push('Invalid constraints', 'invalid_constraints');

  // 工业节点专项
  if (d.node_type === 'industrial.structure_recognition') {
    push('title_hierarchy parser', 'title_parser');
    push('process_flow parser', 'process_parser');
    push('table_structure parser', 'table_parser');
  }
  if (d.node_type === 'industrial.graph_build') {
    push('Graph node count', 'graph_node_count');
    push('Graph edge count', 'graph_edge_count');
    push('Namespace', 'namespace');
  }
  if (d.node_type === 'industrial.graph.persist') {
    push('Neo4j native labels', 'native_labels');
    push('Typed relationships', 'typed_relationships');
    push('Relationship count', 'edge_persisted');
  }
  return rows;
});
</script>

<template>
  <div class="trace-detail">
    <div v-if="!detail" class="trace-empty">请选择节点</div>
    <template v-else>
      <div class="trace-head">
        <div><strong>节点：</strong>{{ detail.node_name }}</div>
        <div><strong>类型：</strong>{{ detail.node_type }}</div>
      </div>
      <div class="trace-grid">
        <div v-for="row in detailRows" :key="row.label" class="trace-row">
          <span class="trace-row__label">{{ row.label }}</span>
          <span class="trace-row__value">{{ row.value }}</span>
        </div>
      </div>
      <div v-if="detail.error" class="trace-error"><strong>Error:</strong> {{ detail.error }}</div>
    </template>
  </div>
</template>

<style scoped lang="scss">
.trace-detail {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.trace-empty {
  font-size: 12px;
  color: #94a3b8;
}

.trace-head {
  font-size: 12px;
  color: #334155;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.trace-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 6px;
}

.trace-row {
  border: 1px solid #e5e7eb;
  background: #fff;
  border-radius: 8px;
  padding: 6px 8px;
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.trace-row__label {
  color: #64748b;
  font-size: 12px;
}

.trace-row__value {
  color: #0f172a;
  font-size: 12px;
  font-weight: 600;
  text-align: right;
  word-break: break-all;
}

.trace-error {
  font-size: 12px;
  color: #b91c1c;
  border: 1px solid #fecaca;
  background: #fef2f2;
  border-radius: 8px;
  padding: 8px;
}
</style>

