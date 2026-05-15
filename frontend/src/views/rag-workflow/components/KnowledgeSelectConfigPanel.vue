<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import {
  fetchKnowledgeDiscover,
  type KnowledgeDiscoverGraphBackend,
  type KnowledgeDiscoverResponse,
  type KnowledgeDiscoverVectorBackend
} from '@/service/api/ragStorage';

const props = defineProps<{
  config: Record<string, unknown>;
  pipelineCandidates: string[];
}>();

const emit = defineEmits<{
  'patch-field': [name: string, value: unknown];
}>();

const loading = ref(false);
const discover = ref<KnowledgeDiscoverResponse>({
  vector_backends: [],
  graph_backends: []
});
const discoverError = ref('');

function strVal(name: string): string {
  return String(props.config[name] || '').trim();
}

function patch(name: string, value: unknown): void {
  emit('patch-field', name, value);
}

function backendCollections(backend: string): string[] {
  const one = discover.value.vector_backends.find(x => x.backend === backend);
  return Array.isArray(one?.collections) ? one!.collections : [];
}

function backendWorkspaces(backend: string): string[] {
  const one = discover.value.graph_backends.find(x => x.backend === backend);
  return Array.isArray(one?.workspaces) ? one!.workspaces : [];
}

function backendLabels(backend: string): string[] {
  const one = discover.value.graph_backends.find(x => x.backend === backend);
  return Array.isArray(one?.labels) ? (one!.labels as string[]) : [];
}

const vectorBackends = computed(() => {
  const rows = discover.value.vector_backends.map(x => x.backend).filter(Boolean);
  const cur = strVal('vector_backend').toLowerCase();
  if (cur && !rows.includes(cur)) rows.push(cur);
  return rows;
});

const graphBackends = computed(() => {
  const rows = discover.value.graph_backends.map(x => x.backend).filter(Boolean);
  if (!rows.includes('none')) rows.push('none');
  const cur = strVal('graph_backend').toLowerCase();
  if (cur && !rows.includes(cur)) rows.push(cur);
  return rows;
});

const activeCollections = computed(() => {
  const b = strVal('vector_backend').toLowerCase();
  return backendCollections(b);
});

const collectionMode = computed(() => {
  const m = strVal('collection_mode').toLowerCase();
  return m === 'by_pipeline' ? 'by_pipeline' : 'unified';
});

const activeWorkspaces = computed(() => {
  const b = strVal('graph_backend').toLowerCase();
  return b === 'neo4j' ? backendWorkspaces('neo4j') : [];
});
const activeNeoLabels = computed(() => backendLabels('neo4j'));

const activeWarnings = computed(() => {
  const v = strVal('vector_backend').toLowerCase();
  const g = strVal('graph_backend').toLowerCase();
  const vv = discover.value.vector_backends.find(x => x.backend === v)?.warnings || [];
  const gw = discover.value.graph_backends.find(x => x.backend === g)?.warnings || [];
  return [...vv, ...gw].filter(Boolean);
});

function syncLocalJsonlPaths(): void {
  if (strVal('vector_backend').toLowerCase() !== 'local_jsonl') return;
  const m: Record<string, string> = {};
  if (collectionMode.value === 'unified') {
    const c = strVal('collection');
    if (c) m.text_pipeline = c;
  } else {
    const pm = pipelineCollectionMap.value;
    for (const [k, v] of Object.entries(pm)) {
      if (v) m[k] = v;
    }
  }
  patch('local_jsonl_paths', m);
}

function asPipelineMap(v: unknown): Record<string, string> {
  if (!v || typeof v !== 'object' || Array.isArray(v)) return {};
  const out: Record<string, string> = {};
  for (const [k, one] of Object.entries(v as Record<string, unknown>)) {
    const kk = String(k || '').trim();
    const vv = String(one || '').trim();
    if (kk && vv) out[kk] = vv;
  }
  return out;
}

const pipelineCollectionMap = computed(() => asPipelineMap(props.config.pipeline_collections));

const visiblePipelines = computed(() => {
  const rows = props.pipelineCandidates.map(x => String(x || '').trim()).filter(Boolean);
  const cur = Object.keys(pipelineCollectionMap.value);
  for (const one of cur) if (!rows.includes(one)) rows.push(one);
  return rows;
});

function patchPipelineCollection(pipeline: string, value: string): void {
  const pm = { ...pipelineCollectionMap.value };
  const vv = String(value || '').trim();
  if (vv) pm[pipeline] = vv;
  else delete pm[pipeline];
  patch('pipeline_collections', pm);
  // legacy 兼容字段同步（仅三类）
  if (pipeline === 'text_pipeline') patch('text_collection', vv || '');
  if (pipeline === 'table_pipeline') patch('table_collection', vv || '');
  if (pipeline === 'vision_pipeline') patch('vision_collection', vv || '');
  syncLocalJsonlPaths();
}

function maybeAutoFillByKnowledgeId(): void {
  const kid = strVal('knowledge_id');
  if (!kid) return;
  const k = kid.toLowerCase();

  if (!strVal('vector_backend')) {
    const hit = discover.value.vector_backends.find(one => one.collections.some(c => c.toLowerCase().includes(k)));
    if (hit?.backend) patch('vector_backend', hit.backend);
  }
  if (!strVal('graph_backend')) {
    const neoHit = backendWorkspaces('neo4j').some(w => w.toLowerCase().includes(k));
    patch('graph_backend', neoHit ? 'neo4j' : 'none');
  }

  const vback = strVal('vector_backend').toLowerCase();
  const cols = backendCollections(vback);
  if (cols.length && collectionMode.value === 'unified') {
    if (!strVal('collection')) {
      const hit = cols.find(c => c.toLowerCase().includes(k)) || cols[0];
      patch('collection', hit);
    }
  }

  if (strVal('graph_backend').toLowerCase() === 'neo4j' && !strVal('workspace')) {
    const ws = backendWorkspaces('neo4j');
    const hit = ws.find(w => w.toLowerCase().includes(k)) || '';
    if (hit) patch('workspace', hit);
  }
}

function onVectorBackendChange(v: string): void {
  const b = String(v || '').trim().toLowerCase();
  patch('vector_backend', b);
  const cols = backendCollections(b);
  if (collectionMode.value === 'unified') {
    if (cols.length) {
      const c = strVal('collection');
      if (!c || !cols.includes(c)) patch('collection', cols[0]);
    } else {
      patch('collection', '');
    }
  } else {
    const pm = { ...pipelineCollectionMap.value };
    for (const p of visiblePipelines.value) {
      const cur = pm[p];
      if (!cur || !cols.includes(cur)) pm[p] = cols[0] || '';
    }
    patch('pipeline_collections', pm);
  }
  syncLocalJsonlPaths();
}

function onGraphBackendChange(v: string): void {
  const b = String(v || '').trim().toLowerCase() || 'none';
  patch('graph_backend', b);
  if (b === 'none') {
    patch('workspace', '');
  } else if (b === 'neo4j') {
    const ws = backendWorkspaces('neo4j');
    const cur = strVal('workspace');
    if ((!cur || !ws.includes(cur)) && ws.length) patch('workspace', ws[0]);
  }
}

function onCollectionModeChange(v: string): void {
  const mode = String(v || '').trim().toLowerCase() === 'by_pipeline' ? 'by_pipeline' : 'unified';
  patch('collection_mode', mode);
  const cols = activeCollections.value;
  if (mode === 'unified') {
    const c = strVal('collection');
    if ((!c || !cols.includes(c)) && cols.length) patch('collection', cols[0]);
  } else {
    const pm = { ...pipelineCollectionMap.value };
    for (const p of visiblePipelines.value) {
      if (!pm[p] && cols.length) pm[p] = cols[0];
    }
    patch('pipeline_collections', pm);
  }
  syncLocalJsonlPaths();
}

async function loadDiscover(): Promise<void> {
  loading.value = true;
  discoverError.value = '';
  try {
    const res = await fetchKnowledgeDiscover();
    discover.value = {
      vector_backends: Array.isArray(res?.vector_backends) ? (res.vector_backends as KnowledgeDiscoverVectorBackend[]) : [],
      graph_backends: Array.isArray(res?.graph_backends) ? (res.graph_backends as KnowledgeDiscoverGraphBackend[]) : []
    };
    maybeAutoFillByKnowledgeId();
  } catch (e) {
    discoverError.value = e instanceof Error ? e.message : '知识库自动发现失败';
    discover.value = { vector_backends: [], graph_backends: [] };
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  if (!strVal('collection_mode')) patch('collection_mode', 'unified');
  void loadDiscover();
});
</script>

<template>
  <div class="ks-panel">
    <div class="ks-head">
      <ElButton size="small" :loading="loading" @click="() => void loadDiscover()">刷新可用知识库资源</ElButton>
    </div>
    <ElAlert v-if="discoverError" type="error" :closable="false" show-icon :title="discoverError" />
    <ElAlert
      v-for="(w, idx) in activeWarnings"
      :key="`kw-${idx}`"
      type="warning"
      :closable="false"
      show-icon
      :title="String(w)"
    />

    <div class="ks-row">
      <span class="ks-label">知识库标识（可选）</span>
      <ElInput
        :model-value="strVal('knowledge_id')"
        placeholder="可选，例如 kb_project_a；为空时自动根据 collection/workspace 生成"
        @update:model-value="v => patch('knowledge_id', v)"
      />
    </div>

    <div class="ks-row">
      <span class="ks-label">Collection模式</span>
      <ElSelect :model-value="collectionMode" @update:model-value="onCollectionModeChange">
        <ElOption label="unified" value="unified" />
        <ElOption label="by_pipeline" value="by_pipeline" />
      </ElSelect>
    </div>

    <div class="ks-row">
      <span class="ks-label">向量后端</span>
      <ElSelect :model-value="strVal('vector_backend')" placeholder="选择向量后端" filterable @update:model-value="onVectorBackendChange">
        <ElOption v-for="b in vectorBackends" :key="b" :label="b" :value="b" />
      </ElSelect>
    </div>

    <div class="ks-row">
      <span class="ks-label">图后端</span>
      <ElSelect :model-value="strVal('graph_backend')" placeholder="选择图后端" filterable @update:model-value="onGraphBackendChange">
        <ElOption v-for="b in graphBackends" :key="b" :label="b" :value="b" />
      </ElSelect>
    </div>

    <div v-if="collectionMode === 'unified'" class="ks-row">
      <span class="ks-label">collection</span>
      <ElSelect
        :model-value="strVal('collection')"
        :placeholder="activeCollections.length ? '选择统一 collection' : '暂无可用 collection'"
        filterable
        clearable
        @update:model-value="v => { patch('collection', v || ''); syncLocalJsonlPaths(); }"
      >
        <ElOption v-for="c in activeCollections" :key="`u-${c}`" :label="c" :value="c" />
      </ElSelect>
    </div>

    <div v-else class="ks-row">
      <span class="ks-label">按 pipeline 配置 collection</span>
      <div v-for="p in visiblePipelines" :key="`p-${p}`" class="ks-row ks-pipeline-row">
        <span class="ks-sub-label">{{ p }} collection</span>
        <ElSelect
          :model-value="pipelineCollectionMap[p] || ''"
          :placeholder="activeCollections.length ? `选择 ${p} collection` : '暂无可用 collection'"
          filterable
          clearable
          @update:model-value="v => patchPipelineCollection(p, String(v || ''))"
        >
          <ElOption v-for="c in activeCollections" :key="`${p}-${c}`" :label="c" :value="c" />
        </ElSelect>
      </div>
    </div>

    <div v-if="strVal('graph_backend').toLowerCase() === 'neo4j'" class="ks-row">
      <span class="ks-label">Neo4j workspace</span>
      <ElSelect
        :model-value="strVal('workspace')"
        placeholder="选择 workspace"
        filterable
        clearable
        @update:model-value="v => patch('workspace', v || '')"
      >
        <ElOption v-for="w in activeWorkspaces" :key="`w-${w}`" :label="w" :value="w" />
      </ElSelect>
      <span v-if="!activeWorkspaces.length && activeNeoLabels.length" class="ks-tip"
        >检测到 Neo4j 图数据，但未发现 workspace 属性，将使用默认图。</span
      >
      <span v-if="!activeWorkspaces.length && !activeNeoLabels.length" class="ks-tip"
        >未发现 Neo4j 图空间，请先写入图数据或检查连接配置。</span
      >
    </div>

    <div v-else-if="strVal('graph_backend').toLowerCase() === 'networkx'" class="ks-row">
      <span class="ks-label">workspace</span>
      <ElInput :model-value="strVal('workspace')" placeholder="可选：本地 workspace 名称" @update:model-value="v => patch('workspace', v)" />
    </div>
  </div>
</template>

<style scoped lang="scss">
.ks-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.ks-head {
  display: flex;
  justify-content: flex-end;
}
.ks-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.ks-label {
  font-size: 12px;
  color: #64748b;
}
.ks-sub-label {
  font-size: 12px;
  color: #64748b;
}
.ks-pipeline-row {
  padding: 8px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
}
.ks-tip {
  font-size: 11px;
  color: #94a3b8;
}
</style>

