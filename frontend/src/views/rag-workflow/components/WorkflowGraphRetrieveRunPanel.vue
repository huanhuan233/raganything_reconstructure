<script setup lang="ts">
import { computed } from 'vue';

type NodeResultLike = {
  data?: unknown;
  error?: string | null;
};

const props = defineProps<{ result: NodeResultLike }>();

function asRecord(v: unknown): Record<string, unknown> {
  return v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
}

const dataObj = computed(() => asRecord(props.result.data));
const summary = computed(() => asRecord(dataObj.value.graph_summary));
const graphResults = computed(() => {
  const rows = dataObj.value.graph_results;
  return Array.isArray(rows) ? rows.filter(x => x && typeof x === 'object').slice(0, 20) as Record<string, unknown>[] : [];
});
const warnings = computed<string[]>(() => {
  const ws = summary.value.warnings;
  if (!Array.isArray(ws)) return [];
  return ws.map(x => String(x || '').trim()).filter(Boolean);
});

function shortText(v: unknown, n = 120): string {
  const s = String(v ?? '').replace(/\s+/g, ' ').trim();
  if (!s) return '-';
  return s.length > n ? `${s.slice(0, n)}...` : s;
}
</script>

<template>
  <div class="graph-retrieve-panel">
    <div class="card">
      <div class="title">GRAPH_SUMMARY</div>
      <div class="kv-grid">
        <div><span>total</span><b>{{ Number(summary.total ?? graphResults.length) }}</b></div>
        <div><span>entity_count</span><b>{{ Number(summary.entity_count ?? 0) }}</b></div>
        <div><span>relation_count</span><b>{{ Number(summary.relation_count ?? 0) }}</b></div>
        <div><span>backend</span><b>{{ String(summary.backend ?? '-') }}</b></div>
        <div><span>workspace</span><b>{{ String(summary.workspace ?? '-') }}</b></div>
        <div><span>source_algorithm</span><b>{{ String(summary.source_algorithm ?? '-') }}</b></div>
      </div>
      <div v-if="warnings.length" class="warnings">
        <div v-for="(w, i) in warnings" :key="i">{{ w }}</div>
      </div>
    </div>

    <div class="card">
      <div class="title">GRAPH_RESULTS（前 20 条）</div>
      <div v-if="!graphResults.length" class="empty">无 graph_results</div>
      <div v-else class="rows">
        <div v-for="(r, idx) in graphResults" :key="`${idx}-${String(r.result_id ?? '')}`" class="row">
          <div class="mono">{{ String(r.result_id ?? '-') }}</div>
          <div>{{ String(r.result_type ?? '-') }}</div>
          <div>{{ Number(r.score ?? 0).toFixed(4) }}</div>
          <div>{{ shortText(r.text) }}</div>
          <div class="mono">{{ String(r.entity_id ?? '-') }}</div>
          <div class="mono">{{ String(r.relation_id ?? '-') }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.graph-retrieve-panel { display: flex; flex-direction: column; gap: 10px; }
.card { border: 1px solid #e5e7eb; border-radius: 12px; background: #fff; padding: 10px; }
.title { font-size: 11px; font-weight: 700; color: #9ca3af; margin-bottom: 8px; letter-spacing: .03em; }
.kv-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 8px; font-size: 12px; }
.kv-grid span { color: #94a3b8; display: block; }
.kv-grid b { color: #111827; font-weight: 600; word-break: break-all; }
.warnings { margin-top: 8px; padding: 8px; border: 1px dashed #fca5a5; border-radius: 8px; color: #b91c1c; font-size: 12px; }
.rows { display: flex; flex-direction: column; gap: 6px; }
.row { display: grid; grid-template-columns: 1.4fr .7fr .6fr 2fr 1fr 1fr; gap: 8px; font-size: 12px; border-top: 1px solid #f1f5f9; padding-top: 6px; }
.row:first-child { border-top: none; padding-top: 0; }
.mono { font-family: ui-monospace, Menlo, Monaco, Consolas, "Courier New", monospace; }
.empty { font-size: 12px; color: #94a3b8; }
</style>

