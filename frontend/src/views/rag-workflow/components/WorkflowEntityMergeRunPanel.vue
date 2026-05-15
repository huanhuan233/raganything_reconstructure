<script setup lang="ts">
import { computed } from 'vue';

type NodeResultLike = { data?: unknown; error?: string | null };
const props = defineProps<{ result: NodeResultLike }>();

function asRecord(v: unknown): Record<string, unknown> {
  return v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
}
const dataObj = computed(() => asRecord(props.result.data));
const summary = computed(() => asRecord(dataObj.value.entity_merge_summary));
const mergedEntities = computed(() => {
  const rows = dataObj.value.merged_entities;
  return Array.isArray(rows) ? (rows.filter(x => x && typeof x === 'object') as Record<string, unknown>[]).slice(0, 20) : [];
});
const mergeMap = computed(() => asRecord(dataObj.value.entity_merge_map));
</script>

<template>
  <div class="entity-merge-panel">
    <div class="card">
      <div class="title">ENTITY_MERGE_SUMMARY</div>
      <div class="kv-grid">
        <div><span>input_entities</span><b>{{ Number(summary.input_entities ?? 0) }}</b></div>
        <div><span>merged_entities</span><b>{{ Number(summary.merged_entities ?? mergedEntities.length) }}</b></div>
        <div><span>merged_groups</span><b>{{ Number(summary.merged_groups ?? 0) }}</b></div>
        <div><span>merge_strategy</span><b>{{ String(summary.merge_strategy ?? '-') }}</b></div>
        <div><span>merge_engine</span><b>{{ String(summary.merge_engine ?? 'runtime') }}</b></div>
        <div><span>use_llm_summary_on_merge</span><b>{{ String(Boolean(summary.use_llm_summary_on_merge ?? false)) }}</b></div>
        <div><span>used_original_algorithm</span><b>{{ String(Boolean(summary.used_original_algorithm ?? false)) }}</b></div>
      </div>
    </div>

    <div class="card">
      <div class="title">MERGED_ENTITIES（前 20 条）</div>
      <div v-if="!mergedEntities.length" class="empty">无 merged_entities</div>
      <div v-else class="rows">
        <div class="row row--head">
          <div>canonical_name</div>
          <div>entity_type</div>
          <div>merged_from count</div>
        </div>
        <div v-for="(r, idx) in mergedEntities" :key="`${idx}-${String(r.canonical_entity_id ?? '')}`" class="row">
          <div>{{ String(r.canonical_name ?? '-') }}</div>
          <div>{{ String(r.entity_type ?? '-') }}</div>
          <div>{{ Array.isArray(r.merged_from) ? r.merged_from.length : 0 }}</div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="title">ENTITY_MERGE_MAP（预览）</div>
      <pre class="json-pre">{{ JSON.stringify(mergeMap, null, 2) }}</pre>
    </div>
  </div>
</template>

<style scoped lang="scss">
.entity-merge-panel { display: flex; flex-direction: column; gap: 10px; }
.card { border: 1px solid #e5e7eb; border-radius: 12px; background: #fff; padding: 10px; }
.title { font-size: 11px; font-weight: 700; color: #9ca3af; margin-bottom: 8px; letter-spacing: .03em; }
.kv-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 8px; font-size: 12px; }
.kv-grid span { color: #94a3b8; display: block; }
.kv-grid b { color: #111827; font-weight: 600; word-break: break-all; }
.rows { display: flex; flex-direction: column; gap: 6px; }
.row { display: grid; grid-template-columns: 1.2fr .8fr .8fr; gap: 8px; font-size: 12px; border-top: 1px solid #f1f5f9; padding-top: 6px; }
.row:first-child { border-top: none; padding-top: 0; }
.row--head { color: #64748b; font-weight: 600; border-bottom: 1px solid #f1f5f9; padding-bottom: 6px; }
.json-pre { margin: 0; white-space: pre-wrap; word-break: break-word; font-size: 11px; line-height: 1.45; font-family: Menlo, Monaco, Consolas, "Courier New", monospace; }
.empty { font-size: 12px; color: #94a3b8; }
</style>

