<script setup lang="ts">
import { computed } from 'vue';

type NodeResultLike = { data?: unknown; error?: string | null };

const props = defineProps<{ result: NodeResultLike }>();

function asRecord(v: unknown): Record<string, unknown> {
  return v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
}

const dataObj = computed(() => asRecord(props.result.data));
const summary = computed(() => asRecord(dataObj.value.chunk_summary));
const chunks = computed(() => {
  const rows = dataObj.value.chunks;
  return Array.isArray(rows) ? (rows.filter(x => x && typeof x === 'object') as Record<string, unknown>[]).slice(0, 20) : [];
});

function shortText(v: unknown, n = 120): string {
  const s = String(v ?? '').replace(/\s+/g, ' ').trim();
  if (!s) return '-';
  return s.length > n ? `${s.slice(0, n)}...` : s;
}

function distLine(v: unknown): string {
  const d = asRecord(v);
  const pairs = Object.entries(d);
  if (!pairs.length) return '无';
  return pairs.map(([k, n]) => `${k}:${n}`).join(', ');
}
</script>

<template>
  <div class="chunk-split-panel">
    <div class="card">
      <div class="title">CHUNK_SUMMARY</div>
      <div class="kv-grid">
        <div><span>total_chunks</span><b>{{ Number(summary.total_chunks ?? chunks.length) }}</b></div>
        <div><span>input_items</span><b>{{ Number(summary.input_items ?? 0) }}</b></div>
        <div><span>pipeline_distribution</span><b>{{ distLine(summary.pipeline_distribution) }}</b></div>
        <div><span>type_distribution</span><b>{{ distLine(summary.type_distribution) }}</b></div>
        <div><span>source_algorithm</span><b>{{ String(summary.source_algorithm ?? '-') }}</b></div>
      </div>
    </div>

    <div class="card">
      <div class="title">CHUNKS（前 20 条）</div>
      <div v-if="!chunks.length" class="empty">无 chunks</div>
      <div v-else class="rows">
        <div class="row row--head">
          <div>序号</div>
          <div>类型</div>
          <div>内容</div>
        </div>
        <div v-for="(r, idx) in chunks" :key="`${idx}-${String(r.chunk_id ?? '')}`" class="row">
          <div class="mono">
            <ElTooltip
              effect="dark"
              :content="String(r.chunk_id ?? '-')"
              placement="top"
              :show-after="150"
            >
              <span class="idx-chip">{{ idx + 1 }}</span>
            </ElTooltip>
          </div>
          <div>{{ `${String(r.pipeline ?? '-')}/${String(r.content_type ?? '-')}` }}</div>
          <div>{{ shortText(r.text, 180) }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.chunk-split-panel { display: flex; flex-direction: column; gap: 10px; }
.card { border: 1px solid #e5e7eb; border-radius: 12px; background: #fff; padding: 10px; }
.title { font-size: 11px; font-weight: 700; color: #9ca3af; margin-bottom: 8px; letter-spacing: .03em; }
.kv-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 8px; font-size: 12px; }
.kv-grid span { color: #94a3b8; display: block; }
.kv-grid b { color: #111827; font-weight: 600; word-break: break-all; }
.rows { display: flex; flex-direction: column; gap: 6px; }
.row { display: grid; grid-template-columns: 72px 150px minmax(0,1fr); gap: 8px; font-size: 12px; border-top: 1px solid #f1f5f9; padding-top: 6px; align-items: start; }
.row:first-child { border-top: none; padding-top: 0; }
.row--head {
  color: #64748b;
  font-weight: 600;
  border-top: none;
  border-bottom: 1px solid #f1f5f9;
  padding-bottom: 6px;
}
.idx-chip {
  display: inline-flex;
  min-width: 24px;
  height: 20px;
  padding: 0 6px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  cursor: help;
}
.mono { font-family: ui-monospace, Menlo, Monaco, Consolas, "Courier New", monospace; }
.empty { font-size: 12px; color: #94a3b8; }
</style>

