<script setup lang="ts">
import { computed } from 'vue';

type NodeResultLike = { data?: unknown; error?: string | null };
const props = defineProps<{ result: NodeResultLike }>();

function asRecord(v: unknown): Record<string, unknown> {
  return v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
}

const dataObj = computed(() => asRecord(props.result.data));
const summary = computed(() => asRecord(dataObj.value.relation_merge_summary));
const mergedRelations = computed(() => {
  const rows = dataObj.value.merged_relations;
  return Array.isArray(rows) ? (rows.filter(x => x && typeof x === 'object') as Record<string, unknown>[]).slice(0, 20) : [];
});
const mergeMap = computed(() => asRecord(dataObj.value.relation_merge_map));
</script>

<template>
  <div class="relation-merge-panel">
    <div class="card">
      <div class="title">RELATION_MERGE_SUMMARY</div>
      <div class="kv-grid">
        <div><span>input_relations</span><b>{{ Number(summary.input_relations ?? 0) }}</b></div>
        <div><span>merged_relations</span><b>{{ Number(summary.merged_relations ?? mergedRelations.length) }}</b></div>
        <div><span>merged_groups</span><b>{{ Number(summary.merged_groups ?? 0) }}</b></div>
        <div><span>merge_strategy</span><b>{{ String(summary.merge_strategy ?? '-') }}</b></div>
        <div><span>merge_engine</span><b>{{ String(summary.merge_engine ?? 'runtime') }}</b></div>
        <div><span>use_llm_summary_on_merge</span><b>{{ String(Boolean(summary.use_llm_summary_on_merge ?? false)) }}</b></div>
        <div><span>used_original_algorithm</span><b>{{ String(Boolean(summary.used_original_algorithm ?? false)) }}</b></div>
      </div>
    </div>

    <div class="card">
      <div class="title">MERGED_RELATIONS（前 20 条）</div>
      <div v-if="!mergedRelations.length" class="empty">无 merged_relations</div>
      <div v-else class="rows">
        <div class="row row--head">
          <div>source_entity</div>
          <div>target_entity</div>
          <div>relation_type</div>
          <div>merged_from count</div>
        </div>
        <div v-for="(r, idx) in mergedRelations" :key="`${idx}-${String(r.canonical_relation_id ?? '')}`" class="row">
          <div>{{ String(r.source_entity ?? '-') }}</div>
          <div>{{ String(r.target_entity ?? '-') }}</div>
          <div>{{ String(r.relation_type ?? '-') }}</div>
          <div>{{ Array.isArray(r.merged_from) ? r.merged_from.length : 0 }}</div>
        </div>
      </div>
    </div>

    <ElCollapse class="card card-collapse">
      <ElCollapseItem name="map" title="RELATION_MERGE_MAP（折叠预览）">
        <pre class="json-pre">{{ JSON.stringify(mergeMap, null, 2) }}</pre>
      </ElCollapseItem>
    </ElCollapse>
  </div>
</template>

<style scoped lang="scss">
.relation-merge-panel { display: flex; flex-direction: column; gap: 10px; }
.card { border: 1px solid #e5e7eb; border-radius: 12px; background: #fff; padding: 10px; }
.card-collapse :deep(.el-collapse-item__header) { font-size: 11px; color: #9ca3af; }
.title { font-size: 11px; font-weight: 700; color: #9ca3af; margin-bottom: 8px; letter-spacing: .03em; }
.kv-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 8px; font-size: 12px; }
.kv-grid span { color: #94a3b8; display: block; }
.kv-grid b { color: #111827; font-weight: 600; word-break: break-all; }
.rows { display: flex; flex-direction: column; gap: 6px; }
.row { display: grid; grid-template-columns: 1fr 1fr .9fr .8fr; gap: 8px; font-size: 12px; border-top: 1px solid #f1f5f9; padding-top: 6px; }
.row:first-child { border-top: none; padding-top: 0; }
.row--head { color: #64748b; font-weight: 600; border-bottom: 1px solid #f1f5f9; padding-bottom: 6px; }
.json-pre { margin: 0; white-space: pre-wrap; word-break: break-word; font-size: 11px; line-height: 1.45; font-family: Menlo, Monaco, Consolas, "Courier New", monospace; }
.empty { font-size: 12px; color: #94a3b8; }
</style>

