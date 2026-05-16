<script setup lang="ts">
import type { ObservatoryTimelineEvent } from './useSemanticObservatory';

withDefaults(defineProps<{ events: ObservatoryTimelineEvent[]; compact?: boolean }>(), {
  compact: false
});

const phasePalette: Record<
  string,
  { hue: string; label: string }
> = {
  'chunk.created': { hue: 'trace-line--muted', label: '块' },
  'constraint.extracted': { hue: 'trace-line--constraint', label: '约束' },
  'semantic.plan.generated': { hue: 'trace-line--semantic', label: '计划' },
  'constraint.filtered': { hue: 'trace-line--constraint', label: '过滤' },
  'graph.persisted': { hue: 'trace-line--graph', label: '图持久' },
  'state.transition.validated': { hue: 'trace-line--state', label: '状态' },
  'ontology.persist': { hue: 'trace-line--ontology', label: '本体' },
  'log.semantic_hint': { hue: 'trace-line--log', label: '日志' }
};

function resolvePalette(kind: string) {
  if (phasePalette[kind]) return phasePalette[kind];
  const k = kind.toLowerCase();
  if (k.includes('constraint')) return phasePalette['constraint.extracted'];
  if (k.includes('semantic') || k.includes('plan')) return phasePalette['semantic.plan.generated'];
  if (k.includes('state') || k.includes('transition')) return phasePalette['state.transition.validated'];
  if (k.includes('graph') || k.includes('persist')) return phasePalette['graph.persisted'];
  if (k.includes('chunk')) return phasePalette['chunk.created'];
  if (k.startsWith('log.')) return phasePalette['log.semantic_hint'];
  return { hue: 'trace-line--runtime', label: 'RT' };
}
</script>

<template>
  <div class="runtime-timeline-root" :class="{ compact }">
    <template v-if="events.length">
      <div class="runtime-timeline-title">Runtime 生命周期（语义）</div>
      <ol class="runtime-timeline">
        <li v-for="ev in events" :key="ev.id" class="runtime-timeline__row">
          <div class="trace-line-bar" :class="resolvePalette(ev.kind).hue" />
          <div class="runtime-timeline__main">
            <div class="runtime-timeline__head">
              <span class="kind-pill">{{ ev.kind }}</span>
              <span v-if="ev.ts" class="ts">{{ ev.ts }}</span>
            </div>
            <div class="runtime-timeline__lbl">{{ ev.label }}</div>
          </div>
        </li>
      </ol>
    </template>
    <div v-else class="muted">暂无时间线条目</div>
  </div>
</template>

<style scoped lang="scss">
.runtime-timeline-root {
  font-size: 12px;
}

.runtime-timeline-root.compact .runtime-timeline__lbl {
  display: none;
}

.runtime-timeline-title {
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 8px;
  font-size: 11px;
  letter-spacing: 0.04em;
}

.muted {
  color: #94a3b8;
  font-size: 12px;
}

.runtime-timeline {
  list-style: none;
  margin: 0;
  padding: 0;
}

.runtime-timeline__row {
  display: grid;
  grid-template-columns: 10px 1fr;
  gap: 10px;
  align-items: start;
  margin-bottom: 10px;

  &:last-child {
    margin-bottom: 0;
  }
}

.trace-line-bar {
  width: 6px;
  min-height: 28px;
  border-radius: 999px;

  &.trace-line--ontology {
    background: #1e40af;
  }

  &.trace-line--constraint {
    background: #dc2626;
  }

  &.trace-line--semantic {
    background: #9333ea;
  }

  &.trace-line--state {
    background: #ea580c;
  }

  &.trace-line--graph {
    background: #0891b2;
  }

  &.trace-line--runtime {
    background: #334155;
  }

  &.trace-line--muted {
    background: #94a3b8;
  }

  &.trace-line--log {
    background: #64748b;
  }
}

.runtime-timeline__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.kind-pill {
  font-family: ui-monospace, monospace;
  font-size: 10px;
  color: #2563eb;
  background: #eff6ff;
  border-radius: 6px;
  padding: 1px 6px;
}

.ts {
  font-size: 10px;
  color: #94a3b8;
  white-space: nowrap;
}

.runtime-timeline__lbl {
  margin-top: 4px;
  color: #475569;
  line-height: 1.35;
  word-break: break-word;
}
</style>
