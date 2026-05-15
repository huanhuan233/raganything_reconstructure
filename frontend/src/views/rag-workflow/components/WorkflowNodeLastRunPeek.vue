<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  lastRunRaw: string;
  /** 当前画布节点 id */
  nodeId: string;
}>();

const nodeSlice = computed(() => {
  const HEAVY_ARRAY_KEYS = new Set(['embedding_records', 'storage_refs', 'vector_results', 'unified_results', 'reranked_results', 'context_blocks']);

  function truncateString(s: string): string {
    if (s.length <= 360) return s;
    const keepHead = 180;
    const keepTail = 120;
    const omitted = s.length - keepHead - keepTail;
    return `${s.slice(0, keepHead)}...(omitted ${omitted} chars)...${s.slice(-keepTail)}`;
  }

  function shrinkArray(a: unknown[], parentKey: string): unknown[] {
    const key = parentKey.toLowerCase();
    const isNumeric = a.every(one => typeof one === 'number');
    if (isNumeric && key.includes('vector') && a.length > 6) {
      return [...a.slice(0, 3), `...(${a.length - 6} omitted)...`, ...a.slice(-3)];
    }
    if (HEAVY_ARRAY_KEYS.has(parentKey) && a.length > 3) {
      return [...a.slice(0, 2), `...(${a.length - 3} omitted items)...`, a[a.length - 1]];
    }
    if (a.length > 20 && key !== 'bbox') {
      return [...a.slice(0, 5), `...(${a.length - 7} omitted items)...`, ...a.slice(-2)];
    }
    return a.map(one => shrink(one, parentKey));
  }

  function shrinkObject(obj: Record<string, unknown>, parentKey: string): Record<string, unknown> {
    if (parentKey === 'raw_result') {
      return {
        _omitted: 'raw_result hidden',
        keys: Object.keys(obj).slice(0, 20)
      };
    }
    const out: Record<string, unknown> = {};
    for (const [k, v2] of Object.entries(obj)) {
      out[k] = shrink(v2, k);
    }
    return out;
  }

  function shrink(x: unknown, parentKey = ''): unknown {
    if (typeof x === 'string') return truncateString(x);
    if (Array.isArray(x)) return shrinkArray(x, parentKey);
    if (x && typeof x === 'object') return shrinkObject(x as Record<string, unknown>, parentKey);
    return x;
  }

  if (!props.lastRunRaw.trim()) return '';
  try {
    const o = JSON.parse(props.lastRunRaw) as Record<string, unknown>;
    const nr = o.node_results as Record<string, unknown> | undefined;
    if (!nr || typeof nr !== 'object') return '';
    const id = props.nodeId;
    if (!(id in nr)) return '';
    return JSON.stringify(shrink(nr[id]), null, 2);
  } catch {
    return '';
  }
});
</script>

<template>
  <div class="rag-wf-last-run-peek">
    <p v-if="!lastRunRaw.trim() || !nodeSlice" class="rag-wf-last-run-empty">暂无节点运行记录</p>
    <ElScrollbar v-else class="rag-wf-last-run-scroll">
      <pre class="rag-wf-last-run-pre">{{ nodeSlice }}</pre>
    </ElScrollbar>
  </div>
</template>

<style scoped lang="scss">
.rag-wf-last-run-peek {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.rag-wf-last-run-empty {
  margin: 0;
  padding: 12px 0 4px;
  font-size: 12px;
  line-height: 1.55;
  color: #94a3b8;
  text-align: center;
}

.rag-wf-last-run-scroll {
  flex: 1;
  min-height: 0;
}

.rag-wf-last-run-pre {
  margin: 0;
  font-size: 11px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: Menlo, Monaco, Consolas, 'Courier New', monospace;
}
</style>
