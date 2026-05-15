<script setup lang="ts">
import { computed } from 'vue';
import IndustrialGraphPersistPanel from './IndustrialGraphPersistPanel.vue';
import StructureParserSelector from './StructureParserSelector.vue';

const props = defineProps<{
  config: Record<string, unknown>;
  nodeType?: string;
}>();
const emit = defineEmits<{
  'patch-field': [name: string, value: unknown];
}>();

const enabledParsers = computed<string[]>({
  get: () => {
    const raw = props.config.enabled_parsers;
    return Array.isArray(raw) ? raw.map(x => String(x)) : ['title_hierarchy', 'process_flow', 'table_structure'];
  },
  set: v => emit('patch-field', 'enabled_parsers', v)
});

const isIndustrialGraphPersist = computed(() => String(props.nodeType ?? '') === 'industrial.graph.persist');
</script>

<template>
  <IndustrialGraphPersistPanel
    v-if="isIndustrialGraphPersist"
    :config="config"
    @patch-field="(name, value) => emit('patch-field', name, value)"
  />
  <div v-else class="ik-config">
    <div class="ik-title">工业节点配置</div>
    <div class="ik-row">
      <div class="ik-label">Parser 选择</div>
      <StructureParserSelector v-model="enabledParsers" />
    </div>
    <div class="ik-grid">
      <div class="ik-switch">
        <span>参数规则开关</span>
        <ElSwitch
          :model-value="Boolean(config.enable_constraint_extract ?? true)"
          @update:model-value="v => emit('patch-field', 'enable_constraint_extract', v)"
        />
      </div>
      <div class="ik-switch">
        <span>LLM 补全开关</span>
        <ElSwitch
          :model-value="Boolean(config.enable_semantic_completion ?? false)"
          @update:model-value="v => emit('patch-field', 'enable_semantic_completion', v)"
        />
      </div>
      <div class="ik-switch">
        <span>表格解析开关</span>
        <ElSwitch
          :model-value="Boolean(config.enable_table_parse ?? true)"
          @update:model-value="v => emit('patch-field', 'enable_table_parse', v)"
        />
      </div>
      <div class="ik-switch">
        <span>Graph 构建开关</span>
        <ElSwitch
          :model-value="Boolean(config.enable_graph_build ?? true)"
          @update:model-value="v => emit('patch-field', 'enable_graph_build', v)"
        />
      </div>
      <div class="ik-switch">
        <span>验证开关</span>
        <ElSwitch
          :model-value="Boolean(config.enable_validation ?? true)"
          @update:model-value="v => emit('patch-field', 'enable_validation', v)"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.ik-config {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 12px;
  background: #fff;
}
.ik-title {
  font-size: 12px;
  color: #475569;
  font-weight: 600;
  margin-bottom: 10px;
}
.ik-row {
  margin-bottom: 12px;
}
.ik-label {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 6px;
}
.ik-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
}
.ik-switch {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #334155;
}
</style>
