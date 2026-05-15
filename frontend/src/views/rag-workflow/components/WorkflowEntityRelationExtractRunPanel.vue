<script setup lang="ts">
import { computed } from 'vue';

type NodeResultLike = { data?: unknown; error?: string | null };
const props = defineProps<{ result: NodeResultLike }>();

function asRecord(v: unknown): Record<string, unknown> {
  return v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
}

const dataObj = computed(() => asRecord(props.result.data));
const summary = computed(() => asRecord(dataObj.value.entity_relation_summary));
const entities = computed(() => {
  const rows = dataObj.value.entities;
  return Array.isArray(rows) ? (rows.filter(x => x && typeof x === 'object') as Record<string, unknown>[]).slice(0, 20) : [];
});
const relations = computed(() => {
  const rows = dataObj.value.relations;
  return Array.isArray(rows) ? (rows.filter(x => x && typeof x === 'object') as Record<string, unknown>[]).slice(0, 20) : [];
});

function distLine(v: unknown): string {
  const d = asRecord(v);
  const pairs = Object.entries(d);
  if (!pairs.length) return '无';
  return pairs.map(([k, n]) => `${k}:${n}`).join(', ');
}
function shortText(v: unknown, n = 120): string {
  const s = String(v ?? '').replace(/\s+/g, ' ').trim();
  if (!s) return '-';
  return s.length > n ? `${s.slice(0, n)}...` : s;
}
</script>

<template>
  <div class="entity-relation-panel">
    <div class="card">
      <div class="title">ENTITY_RELATION_SUMMARY</div>
      <div class="kv-grid">
        <div><span>entity_count</span><b>{{ Number(summary.entity_count ?? entities.length) }}</b></div>
        <div><span>relation_count</span><b>{{ Number(summary.relation_count ?? relations.length) }}</b></div>
        <div><span>entity_type_distribution</span><b>{{ distLine(summary.entity_type_distribution) }}</b></div>
        <div><span>relation_type_distribution</span><b>{{ distLine(summary.relation_type_distribution) }}</b></div>
        <div><span>source_algorithm</span><b>{{ String(summary.source_algorithm ?? '-') }}</b></div>
      </div>
    </div>

    <div class="card">
      <div class="title">ENTITIES（前 20 条）</div>
      <div v-if="!entities.length" class="empty">无 entities</div>
      <div v-else class="rows">
        <div class="row row--head">
          <div>entity_name</div>
          <div>entity_type</div>
          <div>description</div>
        </div>
        <div v-for="(r, idx) in entities" :key="`${idx}-${String(r.entity_id ?? '')}`" class="row">
          <div>{{ String(r.entity_name ?? '-') }}</div>
          <div>{{ String(r.entity_type ?? '-') }}</div>
          <div>{{ shortText(r.description) }}</div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="title">RELATIONS（前 20 条）</div>
      <div v-if="!relations.length" class="empty">无 relations</div>
      <div v-else class="rows">
        <div class="row row--head">
          <div>source_entity</div>
          <div>target_entity</div>
          <div>relation_type / description</div>
        </div>
        <div v-for="(r, idx) in relations" :key="`${idx}-${String(r.relation_id ?? '')}`" class="row">
          <div>{{ String(r.source_entity ?? '-') }}</div>
          <div>{{ String(r.target_entity ?? '-') }}</div>
          <div>{{ `${String(r.relation_type ?? '-')} · ${shortText(r.description)}` }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.entity-relation-panel { display: flex; flex-direction: column; gap: 10px; }
.card { border: 1px solid #e5e7eb; border-radius: 12px; background: #fff; padding: 10px; }
.title { font-size: 11px; font-weight: 700; color: #9ca3af; margin-bottom: 8px; letter-spacing: .03em; }
.kv-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 8px; font-size: 12px; }
.kv-grid span { color: #94a3b8; display: block; }
.kv-grid b { color: #111827; font-weight: 600; word-break: break-all; }
.rows { display: flex; flex-direction: column; gap: 6px; }
.row { display: grid; grid-template-columns: 1fr .8fr 2fr; gap: 8px; font-size: 12px; border-top: 1px solid #f1f5f9; padding-top: 6px; }
.row:first-child { border-top: none; padding-top: 0; }
.row--head { color: #64748b; font-weight: 600; border-bottom: 1px solid #f1f5f9; padding-bottom: 6px; }
.empty { font-size: 12px; color: #94a3b8; }
</style>

