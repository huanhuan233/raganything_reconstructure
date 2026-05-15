<script setup lang="ts">
import { computed } from 'vue';
import ConstraintViewer from '../industrial/ConstraintViewer.vue';
import CustomSchemaViewer from '../industrial/CustomSchemaViewer.vue';
import IndustrialGraphViewer from '../industrial/IndustrialGraphViewer.vue';
import ProcessFlowViewer from '../industrial/ProcessFlowViewer.vue';
import TableRelationViewer from '../industrial/TableRelationViewer.vue';
import TitleHierarchyViewer from '../industrial/TitleHierarchyViewer.vue';
import ValidationPanel from '../industrial/ValidationPanel.vue';

const props = defineProps<{
  result: {
    data?: unknown;
  };
}>();

const data = computed<Record<string, unknown>>(() => {
  const d = props.result?.data;
  return d && typeof d === 'object' && !Array.isArray(d) ? (d as Record<string, unknown>) : {};
});

const composite = computed<Record<string, unknown>>(() => {
  const x = data.value.composite_structure;
  return x && typeof x === 'object' && !Array.isArray(x) ? (x as Record<string, unknown>) : {};
});

const industrialGraph = computed<Record<string, unknown>>(() => {
  const g = data.value.industrial_graph;
  return g && typeof g === 'object' && !Array.isArray(g) ? (g as Record<string, unknown>) : {};
});

const persistSummary = computed<Record<string, unknown>>(() => {
  const s = data.value.industrial_graph_persist_summary;
  return s && typeof s === 'object' && !Array.isArray(s) ? (s as Record<string, unknown>) : {};
});
</script>

<template>
  <div class="ik-panel">
    <ElTabs>
      <ElTabPane label="Title Hierarchy">
        <TitleHierarchyViewer :data="(composite.title_hierarchy as Record<string, unknown>) || {}" />
      </ElTabPane>
      <ElTabPane label="Process Flow">
        <ProcessFlowViewer :data="(composite.process_flow as Record<string, unknown>) || {}" />
      </ElTabPane>
      <ElTabPane label="Table Relations">
        <TableRelationViewer :tables="(data.structured_tables as unknown[]) || []" />
      </ElTabPane>
      <ElTabPane label="Constraints">
        <ConstraintViewer :constraints="(data.constraints as unknown[]) || []" />
      </ElTabPane>
      <ElTabPane label="Custom Schema">
        <CustomSchemaViewer :data="(composite.custom_schema as Record<string, unknown>) || {}" />
      </ElTabPane>
      <ElTabPane label="Validation">
        <ValidationPanel :validation="(data.validation as Record<string, unknown>) || {}" />
      </ElTabPane>
      <ElTabPane label="Industrial Graph">
        <IndustrialGraphViewer :graph="industrialGraph" />
      </ElTabPane>
      <ElTabPane v-if="Object.keys(persistSummary).length" label="Persist Summary">
        <pre class="ik-json">{{ JSON.stringify(persistSummary, null, 2) }}</pre>
      </ElTabPane>
    </ElTabs>
  </div>
</template>

<style scoped>
.ik-panel {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.ik-panel :deep(.el-tabs) {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.ik-panel :deep(.el-tabs__header) {
  margin: 0 0 8px;
  flex-shrink: 0;
}

.ik-panel :deep(.el-tabs__content) {
  flex: 1;
  min-height: 0;
}

.ik-panel :deep(.el-tab-pane) {
  height: 320px;
  max-height: 320px;
  overflow-y: auto;
  overflow-x: hidden;
  box-sizing: border-box;
}

.ik-json {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  font-family: ui-monospace, Menlo, Monaco, Consolas, 'Courier New', monospace;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
