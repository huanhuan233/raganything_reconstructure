<script setup lang="ts">
import { computed, onMounted, reactive, ref, toRaw, watch } from 'vue';
import { useDebounceFn } from '@vueuse/core';
import {
  fetchEmbeddingDimHint,
  fetchMilvusCollections,
  type MilvusCollectionRow
} from '@/service/api/ragStorage';
import { buildStorageStrategyPreview } from '../utils/storageStrategyPreview';

const props = defineProps<{
  vectorStorage: Record<string, unknown>;
}>();

const emit = defineEmits<{
  'patch-field': [name: string, value: unknown];
}>();

const defaultVector = () => ({
  backend: 'milvus',
  mode: 'existing',
  collection: '',
  dimension: 0,
  metric_type: 'COSINE',
  index_type: 'IVF_FLAT',
  auto_create_index: true,
  create_if_missing: false,
  milvus_batch_size: 50
});

const milvusLoading = ref(false);
const milvusError = ref('');
const dimHintLoading = ref(false);
const dimHint = ref(0);

const milvusRows = ref<MilvusCollectionRow[]>([]);

const v = reactive<Record<string, unknown>>({ ...defaultVector(), ...props.vectorStorage });

watch(
  () => props.vectorStorage,
  nv => {
    Object.assign(v, { ...defaultVector(), ...nv });
  },
  { deep: true }
);

const strategyPreviewJson = computed(() => {
  try {
    return JSON.stringify(buildStorageStrategyPreview(toRaw(v)), null, 2);
  } catch {
    return '{}';
  }
});

const vectorNewMode = computed({
  get: () => v.mode === 'create',
  set: (on: boolean) => {
    v.mode = on ? 'create' : 'existing';
    v.create_if_missing = on;
    pushVector();
  }
});

const debouncedPushVector = useDebounceFn(() => {
  const dim = Number(v.dimension);
  const batchRaw = Number(v.milvus_batch_size);
  const batch = Number.isFinite(batchRaw) && batchRaw >= 1 ? Math.floor(batchRaw) : 50;
  emit('patch-field', 'vector_storage', {
    ...toRaw(v),
    dimension: dim > 0 ? dim : 0,
    milvus_batch_size: batch
  });
}, 200);

function pushVector() {
  void debouncedPushVector();
}

async function loadMilvus() {
  milvusLoading.value = true;
  milvusError.value = '';
  try {
    const res = await fetchMilvusCollections();
    if (!res?.success) {
      milvusError.value = res?.error || '无法连接 Milvus，请检查后端 .env 和服务状态';
      milvusRows.value = [];
      return;
    }
    milvusRows.value = Array.isArray(res.data) ? res.data : [];
  } catch (e: unknown) {
    milvusError.value = e instanceof Error ? e.message : '无法连接 Milvus，请检查后端 .env 和服务状态';
    milvusRows.value = [];
  } finally {
    milvusLoading.value = false;
  }
}

async function loadDim() {
  dimHintLoading.value = true;
  try {
    const res = await fetchEmbeddingDimHint();
    const d = res?.data?.dimension;
    dimHint.value = typeof d === 'number' && d > 0 ? d : 0;
    if (dimHint.value > 0 && (!Number(v.dimension) || Number(v.dimension) <= 0)) {
      v.dimension = dimHint.value;
      pushVector();
    }
  } catch {
    dimHint.value = 0;
  } finally {
    dimHintLoading.value = false;
  }
}

onMounted(() => {
  void loadMilvus();
  void loadDim();
});

const milvusOptions = computed(() => milvusRows.value.map(r => ({ label: `${r.name} (${r.num_entities ?? 0})`, value: r.name })));
</script>

<template>
  <div class="rag-wf-storage-ui">
    <div class="rag-wf-storage-ui-actions">
      <ElButton size="small" :loading="milvusLoading || dimHintLoading" @click="() => { void loadMilvus(); void loadDim(); }">
        刷新 Milvus 列表
      </ElButton>
    </div>
    <ElAlert
      title="Docker / 混合部署提示"
      type="info"
      :closable="false"
      show-icon
      class="rag-wf-storage-net-tip"
    >
      若 .env 里 <code>MILVUS_URI</code> 使用 <code>host.docker.internal</code>，在<strong>宿主机</strong>运行的 backend_api
      往往解析不到。请在 <code>RAG-Anything/.env</code> 增加 <code>MILVUS_STORAGE_URI</code>（例如
      <code>http://127.0.0.1:19530</code> 或实际映射端口），可选 <code>MILVUS_STORAGE_DB_NAME</code>。修改后重启 API 再点「刷新」。
    </ElAlert>

    <div class="rag-wf-storage-card">
      <div class="rag-wf-storage-card-title">向量库（Milvus）</div>
      <ElAlert v-if="milvusError" type="error" :closable="false" show-icon class="rag-wf-storage-alert" :title="milvusError" />
      <div class="rag-wf-storage-row">
        <span class="rag-wf-storage-label">已有 collection</span>
        <ElSelect
          v-model="v.collection"
          class="rag-wf-storage-select"
          filterable
          clearable
          placeholder="选择 collection"
          :loading="milvusLoading"
          :disabled="Boolean(vectorNewMode)"
          @change="pushVector"
        >
          <ElOption v-for="opt in milvusOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
        </ElSelect>
      </div>
      <div class="rag-wf-storage-row rag-wf-storage-row--switch">
        <span class="rag-wf-storage-label">新建向量库</span>
        <ElSwitch v-model="vectorNewMode" />
      </div>
      <div v-if="vectorNewMode" class="rag-wf-storage-row">
        <span class="rag-wf-storage-label">新建 collection 名称</span>
        <ElInput v-model="v.collection" placeholder="例如 new_rag_collection" @change="pushVector" />
      </div>
      <div class="rag-wf-storage-row">
        <span class="rag-wf-storage-label">向量维度</span>
        <div class="rag-wf-storage-dim">
          <ElInputNumber v-model="v.dimension" :min="0" :max="16384" :step="1" :controls="true" @change="pushVector" />
          <span v-if="dimHintLoading" class="rag-wf-storage-hint">读取中…</span>
          <span v-else-if="dimHint > 0" class="rag-wf-storage-hint">来自 .env EMBEDDING_DIM：{{ dimHint }}</span>
          <span v-else class="rag-wf-storage-hint">未配置 EMBEDDING_DIM 时请手动填写</span>
        </div>
      </div>
      <div class="rag-wf-storage-row rag-wf-storage-row--switch">
        <span class="rag-wf-storage-label">自动创建索引</span>
        <ElSwitch v-model="v.auto_create_index" @change="pushVector" />
      </div>
      <div class="rag-wf-storage-row">
        <span class="rag-wf-storage-label">Metric Type</span>
        <ElSelect v-model="v.metric_type" class="rag-wf-storage-select" @change="pushVector">
          <ElOption label="COSINE" value="COSINE" />
          <ElOption label="L2" value="L2" />
          <ElOption label="IP" value="IP" />
        </ElSelect>
      </div>
      <div class="rag-wf-storage-row">
        <span class="rag-wf-storage-label">Index Type</span>
        <ElSelect v-model="v.index_type" class="rag-wf-storage-select" @change="pushVector">
          <ElOption label="IVF_FLAT" value="IVF_FLAT" />
          <ElOption label="HNSW" value="HNSW" />
        </ElSelect>
      </div>
      <div class="rag-wf-storage-row">
        <span class="rag-wf-storage-label">Milvus 批量写入条数</span>
        <div class="rag-wf-storage-dim">
          <ElInputNumber
            v-model="v.milvus_batch_size"
            :min="1"
            :max="2048"
            :step="1"
            :controls="true"
            @change="pushVector"
          />
          <span class="rag-wf-storage-hint">每条 embedding 记录一批 upsert；默认 50，增大可减少服务端 flush 次数。</span>
        </div>
      </div>
    </div>

    <div class="rag-wf-storage-card rag-wf-storage-card--adv">
      <div class="rag-wf-storage-card-title">高级：生成的 storage_strategy（只读）</div>
      <p class="rag-wf-storage-adv-desc">运行时将自动追加各 pipeline 的 local_jsonl 兜底；此处为 Milvus 步骤预览。</p>
      <ElInput :model-value="strategyPreviewJson" type="textarea" readonly :autosize="{ minRows: 6, maxRows: 14 }" class="rag-wf-storage-preview mono" />
    </div>
  </div>
</template>

<style scoped lang="scss">
.rag-wf-storage-ui {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 12px;
}

.rag-wf-storage-ui-actions {
  display: flex;
  justify-content: flex-end;
}

.rag-wf-storage-net-tip {
  font-size: 12px;
  line-height: 1.55;
  color: #475569;

  :deep(.el-alert__title) {
    font-size: 12px;
    font-weight: 600;
  }

  code {
    font-size: 11px;
    padding: 1px 4px;
    border-radius: 4px;
    background: #f1f5f9;
  }
}

.rag-wf-storage-card {
  padding: 12px;
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  background: #fafafa;
}

.rag-wf-storage-card--adv {
  background: #fff;
}

.rag-wf-storage-card-title {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 10px;
}

.rag-wf-storage-alert {
  margin-bottom: 10px;
}

.rag-wf-storage-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 10px;

  &--switch {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
  }
}

.rag-wf-storage-label {
  font-size: 12px;
  color: #64748b;
}

.rag-wf-storage-select {
  width: 100%;
}

.rag-wf-storage-dim {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.rag-wf-storage-hint {
  font-size: 11px;
  color: #94a3b8;
}

.rag-wf-storage-adv-desc {
  font-size: 11px;
  color: #94a3b8;
  margin: 0 0 8px;
  line-height: 1.45;
}

.rag-wf-storage-preview :deep(.el-textarea__inner) {
  font-family: ui-monospace, Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
  color: #475569;
  background: #f8fafc;
}

.mono {
  font-family: ui-monospace, Menlo, Monaco, Consolas, monospace;
}
</style>
