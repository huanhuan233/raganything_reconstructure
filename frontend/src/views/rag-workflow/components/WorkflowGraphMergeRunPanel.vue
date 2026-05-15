<script setup lang="ts">
import { computed } from 'vue';

type NodeResultLike = { data?: unknown; error?: string | null };
const props = defineProps<{ result: NodeResultLike }>();

function asRecord(v: unknown): Record<string, unknown> {
  return v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
}

const dataObj = computed(() => asRecord(props.result.data));
const summary = computed(() => asRecord(dataObj.value.graph_summary));
const graph = computed(() => asRecord(dataObj.value.graph));
const entities = computed(() => {
  const rows = graph.value.entities;
  return Array.isArray(rows) ? (rows.filter(x => x && typeof x === 'object') as Record<string, unknown>[]).slice(0, 20) : [];
});
const relations = computed(() => {
  const rows = graph.value.relations;
  return Array.isArray(rows) ? (rows.filter(x => x && typeof x === 'object') as Record<string, unknown>[]).slice(0, 20) : [];
});
const components = computed(() => {
  const rows = graph.value.connected_components;
  return Array.isArray(rows) ? (rows.filter(x => x && typeof x === 'object') as Record<string, unknown>[]).slice(0, 20) : [];
});
</script>

<template>
  <div class="graph-merge-panel">
    <div class="card">
      <div class="title">GRAPH_SUMMARY</div>
      <div class="kv-grid">
        <div><span>entity_count</span><b>{{ Number(summary.entity_count ?? entities.length) }}</b></div>
        <div><span>relation_count</span><b>{{ Number(summary.relation_count ?? relations.length) }}</b></div>
        <div><span>component_count</span><b>{{ Number(summary.component_count ?? components.length) }}</b></div>
        <div><span>isolated_entity_count</span><b>{{ Number(summary.isolated_entity_count ?? 0) }}</b></div>
        <div><span>merge_engine</span><b>{{ String(summary.merge_engine ?? 'runtime') }}</b></div>
        <div><span>used_original_algorithm</span><b>{{ String(Boolean(summary.used_original_algorithm ?? false)) }}</b></div>
      </div>
    </div>

    <div class="card">
      <div class="title">CONNECTED_COMPONENTS（前 20 条）</div>
      <div v-if="!components.length" class="empty">无 connected_components</div>
      <div v-else class="rows">
        <div class="row row--head">
          <div>component_id</div>
          <div>entity_count</div>
          <div>relation_count</div>
        </div>
        <div v-for="(r, idx) in components" :key="`${idx}-${String(r.component_id ?? '')}`" class="row">
          <div>{{ String(r.component_id ?? '-') }}</div>
          <div>{{ Number(r.entity_count ?? 0) }}</div>
          <div>{{ Number(r.relation_count ?? 0) }}</div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="title">GRAPH_ENTITIES（前 20 条）</div>
      <div v-if="!entities.length" class="empty">无 entities</div>
      <div v-else class="rows">
        <div class="row row--head row--entities">
          <div>canonical_name</div>
          <div>chunk_refs count</div>
        </div>
        <div v-for="(r, idx) in entities" :key="`${idx}-${String(r.canonical_entity_id ?? '')}`" class="row row--entities">
          <div>{{ String(r.canonical_name ?? r.canonical_entity_id ?? '-') }}</div>
          <div>{{ Array.isArray(r.chunk_refs) ? r.chunk_refs.length : 0 }}</div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="title">GRAPH_RELATIONS（前 20 条）</div>
      <div v-if="!relations.length" class="empty">无 relations</div>
      <div v-else class="rows">
        <div class="row row--head row--relations">
          <div>source_entity</div>
          <div>target_entity</div>
          <div>relation_type</div>
        </div>
        <div v-for="(r, idx) in relations" :key="`${idx}-${String(r.canonical_relation_id ?? '')}`" class="row row--relations">
          <div>{{ String(r.source_entity ?? '-') }}</div>
          <div>{{ String(r.target_entity ?? '-') }}</div>
          <div>{{ String(r.relation_type ?? '-') }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.graph-merge-panel { display: flex; flex-direction: column; gap: 10px; }
.card { border: 1px solid #e5e7eb; border-radius: 12px; background: #fff; padding: 10px; }
.title { font-size: 11px; font-weight: 700; color: #9ca3af; margin-bottom: 8px; letter-spacing: .03em; }
.kv-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 8px; font-size: 12px; }
.kv-grid span { color: #94a3b8; display: block; }
.kv-grid b { color: #111827; font-weight: 600; word-break: break-all; }
.rows { display: flex; flex-direction: column; gap: 6px; }
.row { display: grid; grid-template-columns: 1.4fr .8fr .8fr; gap: 8px; font-size: 12px; border-top: 1px solid #f1f5f9; padding-top: 6px; }
.row:first-child { border-top: none; padding-top: 0; }
.row--head { color: #64748b; font-weight: 600; border-bottom: 1px solid #f1f5f9; padding-bottom: 6px; }
.row--entities { grid-template-columns: 1.4fr .8fr; }
.row--relations { grid-template-columns: 1fr 1fr .8fr; }
.empty { font-size: 12px; color: #94a3b8; }
</style>

