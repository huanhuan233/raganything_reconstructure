<script setup lang="ts">
import { computed, ref } from 'vue';
import {
  fetchKnowledgeDiscover,
  fetchNeo4jGraphPartitionEnsure,
  type KnowledgeDiscoverGraphBackend,
  type KnowledgeDiscoverResponse
} from '@/service/api/ragStorage';

const props = defineProps<{
  config: Record<string, unknown>;
}>();
const emit = defineEmits<{
  'patch-field': [name: string, value: unknown];
}>();

const loading = ref(false);
const creating = ref(false);
const discoverError = ref('');
const discover = ref<KnowledgeDiscoverResponse>({
  vector_backends: [],
  graph_backends: []
});

const namespaceValue = computed(() => String(props.config.namespace ?? 'industrial_default').trim() || 'industrial_default');
const batchSizeValue = computed(() => Number(props.config.batch_size ?? 100));
const graphBackendValue = computed(() => String(props.config.graph_backend ?? 'neo4j').trim().toLowerCase() || 'neo4j');
const graphBackendOptions = computed(() => {
  const rows = discover.value.graph_backends.map(one => String(one.backend || '').trim().toLowerCase()).filter(Boolean);
  const uniq = Array.from(new Set(rows));
  if (!uniq.includes('neo4j')) uniq.unshift('neo4j');
  if (!uniq.includes(graphBackendValue.value)) uniq.push(graphBackendValue.value);
  return uniq;
});
const neo4jWorkspaces = computed(() => {
  const row = discover.value.graph_backends.find(x => String(x.backend || '').trim().toLowerCase() === 'neo4j');
  return Array.isArray(row?.workspaces) ? row!.workspaces.map(x => String(x || '').trim()).filter(Boolean) : [];
});
const activeWarnings = computed(() => {
  const backend = graphBackendValue.value;
  const row = discover.value.graph_backends.find(x => String(x.backend || '').trim().toLowerCase() === backend);
  return Array.isArray(row?.warnings) ? row!.warnings.map(x => String(x || '')).filter(Boolean) : [];
});

function patch(name: string, value: unknown): void {
  emit('patch-field', name, value);
}

async function loadDiscover(): Promise<void> {
  loading.value = true;
  discoverError.value = '';
  try {
    const res = await fetchKnowledgeDiscover();
    discover.value = {
      vector_backends: Array.isArray(res?.vector_backends) ? res.vector_backends : [],
      graph_backends: Array.isArray(res?.graph_backends) ? (res.graph_backends as KnowledgeDiscoverGraphBackend[]) : []
    };
  } catch (e) {
    discoverError.value = e instanceof Error ? e.message : '图分区自动发现失败';
    discover.value = { vector_backends: [], graph_backends: [] };
  } finally {
    loading.value = false;
  }
}

async function ensurePartition(): Promise<void> {
  const backend = graphBackendValue.value;
  const namespace = namespaceValue.value;
  if (backend !== 'neo4j') {
    window.$message?.warning('当前仅 neo4j 支持预创建图分区');
    return;
  }
  if (!namespace) {
    window.$message?.warning('请先输入 Namespace');
    return;
  }
  creating.value = true;
  try {
    await fetchNeo4jGraphPartitionEnsure({
      database: 'neo4j',
      partition: namespace,
      auto_create_constraints: true
    });
    window.$message?.success(`图分区已就绪：${namespace}`);
    await loadDiscover();
    patch('namespace', namespace);
  } catch (e) {
    window.$message?.error(e instanceof Error ? e.message : '图分区创建失败');
  } finally {
    creating.value = false;
  }
}

</script>

<template>
  <div class="igp-config">
    <div class="igp-head">
      <div class="igp-title">工业图谱持久化配置</div>
      <ElButton size="small" :loading="loading" @click="() => void loadDiscover()">刷新图分区</ElButton>
    </div>
    <ElAlert v-if="discoverError" type="error" :closable="false" show-icon :title="discoverError" />
    <ElAlert
      v-for="(w, idx) in activeWarnings"
      :key="`igp-w-${idx}`"
      type="warning"
      :closable="false"
      show-icon
      :title="String(w)"
    />
    <div class="igp-grid">
      <div class="igp-field">
        <div class="igp-label">graph_backend</div>
        <ElSelect
          :model-value="graphBackendValue"
          filterable
          @update:model-value="v => patch('graph_backend', String(v || 'neo4j').trim().toLowerCase())"
        >
          <ElOption v-for="b in graphBackendOptions" :key="`igp-b-${b}`" :label="b" :value="b" />
        </ElSelect>
      </div>
      <div class="igp-row">
        <span>enable_native_labels</span>
        <ElSwitch
          :model-value="Boolean(config.enable_native_labels ?? true)"
          @update:model-value="v => emit('patch-field', 'enable_native_labels', v)"
        />
      </div>
      <div class="igp-row">
        <span>enable_typed_relationships</span>
        <ElSwitch
          :model-value="Boolean(config.enable_typed_relationships ?? true)"
          @update:model-value="v => emit('patch-field', 'enable_typed_relationships', v)"
        />
      </div>
      <div class="igp-field">
        <div class="igp-label">namespace</div>
        <ElSelect
          :model-value="namespaceValue"
          filterable
          allow-create
          default-first-option
          clearable
          placeholder="选择或输入 namespace"
          @update:model-value="v => patch('namespace', String(v || '').trim())"
        >
          <ElOption v-for="w in neo4jWorkspaces" :key="`igp-ws-${w}`" :label="w" :value="w" />
        </ElSelect>
      </div>
      <div class="igp-actions">
        <ElButton
          size="small"
          type="primary"
          plain
          :loading="creating"
          @click="() => void ensurePartition()"
        >
          新建图分区
        </ElButton>
        <span class="igp-tip">可直接输入新 namespace，运行时自动作为图分区落库。</span>
      </div>
      <div class="igp-row">
        <span>validation</span>
        <ElSwitch
          :model-value="Boolean(config.validation ?? true)"
          @update:model-value="v => emit('patch-field', 'validation', v)"
        />
      </div>
      <div class="igp-field">
        <div class="igp-label">batch_size</div>
        <ElInputNumber
          :model-value="batchSizeValue"
          :min="1"
          :max="5000"
          controls-position="right"
          @update:model-value="v => emit('patch-field', 'batch_size', Number(v || 100))"
        />
      </div>
      <div class="igp-row">
        <span>dry_run</span>
        <ElSwitch
          :model-value="Boolean(config.dry_run ?? false)"
          @update:model-value="v => emit('patch-field', 'dry_run', v)"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.igp-config {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 12px;
  background: #fff;
}

.igp-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}

.igp-title {
  font-size: 12px;
  color: #475569;
  font-weight: 600;
}

.igp-grid {
  display: grid;
  gap: 10px;
}

.igp-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: #334155;
}

.igp-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.igp-label {
  font-size: 12px;
  color: #64748b;
}

.igp-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.igp-tip {
  font-size: 11px;
  color: #94a3b8;
}
</style>

