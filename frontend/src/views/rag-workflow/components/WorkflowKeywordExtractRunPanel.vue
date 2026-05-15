<script setup lang="ts">
import { computed } from 'vue';

type NodeResultLike = {
  success?: boolean;
  data?: unknown;
};

const props = defineProps<{ result: NodeResultLike }>();

function asRecord(v: unknown): Record<string, unknown> {
  return v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
}

const view = computed(() => {
  const data = asRecord(props.result.data);
  const summary = asRecord(data.keyword_summary);
  const keywords = Array.isArray(data.keywords) ? data.keywords : [];
  const high = Array.isArray(data.high_level_keywords) ? data.high_level_keywords : [];
  const low = Array.isArray(data.low_level_keywords) ? data.low_level_keywords : [];
  const mode = String(data.keyword_mode || summary.mode || 'lightrag').trim() || 'lightrag';
  const source = String(summary.source_algorithm || '').trim();
  return {
    mode,
    source,
    total: Number(summary.total ?? keywords.length ?? 0),
    highCount: Number(summary.high_level_count ?? high.length ?? 0),
    lowCount: Number(summary.low_level_count ?? low.length ?? 0),
    keywords: keywords.map(one => String(one)).filter(Boolean).slice(0, 24)
  };
});
</script>

<template>
  <div class="wf-kw-panel">
    <div class="wf-kw-top">
      <div class="wf-kw-item">模式：{{ view.mode }}</div>
      <div class="wf-kw-item">关键词：{{ view.total }}</div>
      <div class="wf-kw-item">high/low：{{ view.highCount }}/{{ view.lowCount }}</div>
    </div>
    <div v-if="view.source" class="wf-kw-source">算法：{{ view.source }}</div>
    <div class="wf-kw-tags">
      <ElTag v-for="(k, idx) in view.keywords" :key="`${k}-${idx}`" size="small" effect="plain">{{ k }}</ElTag>
      <span v-if="!view.keywords.length" class="wf-kw-empty">无关键词</span>
    </div>
  </div>
</template>

<style scoped lang="scss">
.wf-kw-panel {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 10px;
  background: #fff;
}

.wf-kw-top {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.wf-kw-item {
  font-size: 12px;
  color: #334155;
}

.wf-kw-source {
  font-size: 11px;
  color: #64748b;
  margin-bottom: 8px;
}

.wf-kw-tags {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.wf-kw-empty {
  font-size: 12px;
  color: #94a3b8;
}
</style>

