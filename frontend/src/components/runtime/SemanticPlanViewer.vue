<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  plan: Record<string, unknown> | null;
}>();

const planId = computed(() => String(props.plan?.plan_id ?? props.plan?.id ?? '').trim());

const ordering = computed(() => {
  const p = props.plan;
  if (!p) return [] as unknown[];
  const keys = ['execution_order', 'ordering', 'topo_order', 'ordered_nodes', 'steps'];
  for (const k of keys) {
    const v = p[k];
    if (Array.isArray(v)) return v;
  }
  return [];
});

type EdgeLike = Record<string, unknown>;

const semanticEdges = computed<EdgeLike[]>(() => {
  const p = props.plan;
  if (!p) return [];
  const v = p.semantic_edges ?? p.semanticRelations ?? p.semantic_relations ?? p.edges;
  if (!Array.isArray(v)) return [];
  return v.filter(e => !!e && typeof e === 'object') as EdgeLike[];
});

const depEdges = computed<EdgeLike[]>(() => {
  const p = props.plan;
  if (!p) return [];
  const v = p.dependency_edges ?? p.dependencies ?? p.data_edges ?? p.dag_edges;
  if (!Array.isArray(v)) return [];
  return v.filter(e => !!e && typeof e === 'object') as EdgeLike[];
});

const constraintChains = computed<unknown[]>(() => {
  const p = props.plan;
  if (!p) return [];
  const v = p.constraint_chains ?? p.constraintChain ?? p.constraint_chain;
  return Array.isArray(v) ? v : [];
});

const forbidden = computed(() => {
  const p = props.plan;
  if (!p) return [] as unknown[];
  const v = p.forbidden_transitions ?? p.forbidden ?? p.blocked_transitions;
  return Array.isArray(v) ? v : [];
});

function summarizeEdge(e: EdgeLike): string {
  const s =
    String(e.source ?? e.from ?? e.src ?? e.subject ?? e.head ?? '').trim();
  const t = String(e.target ?? e.to ?? e.dst ?? e.object ?? e.tail ?? '').trim();
  const rel = String(e.rel ?? e.role ?? e.predicate ?? e.type ?? 'rel').trim();
  if (!s && !t) return rel || JSON.stringify(e).slice(0, 80);
  return `${s} ·${rel}→ ${t}`;
}
</script>

<template>
  <div class="semantic-plan-viewer">
    <div class="semantic-plan-viewer__flow">
      <div class="semantic-plan-viewer__stage semantic-plan-viewer__stage--dag">
        <div class="semantic-plan-viewer__stage-tag">DAG</div>
        <span class="semantic-plan-viewer__hint">工作流画布拓扑 →</span>
      </div>
      <div class="semantic-plan-viewer__arrow">↓</div>
      <div class="semantic-plan-viewer__stage semantic-plan-viewer__stage--ir">
        <div class="semantic-plan-viewer__stage-tag">Semantic IR</div>
        <p v-if="planId" class="semantic-plan-viewer__plan-id">{{ planId }}</p>
        <ElEmpty v-else description="未解析到语义计划结构" />
      </div>
      <div class="semantic-plan-viewer__arrow">↓</div>
      <div class="semantic-plan-viewer__stage semantic-plan-viewer__stage--ord">
        <div class="semantic-plan-viewer__stage-tag">执行序</div>
        <ol v-if="ordering.length" class="semantic-plan-viewer__ordering">
          <li v-for="(x, i) in ordering.slice(0, 24)" :key="`${i}-${String(x)}`">{{ x }}</li>
          <li v-if="ordering.length > 24" class="muted">… 共 {{ ordering.length }} 项</li>
        </ol>
        <p v-else class="muted">（无顺序字段时由 Planner 隐含推导）</p>
      </div>
    </div>

    <ElCollapse accordion class="semantic-plan-viewer__collapse">
      <ElCollapseItem title="依赖边 dependency edge" name="dep">
        <template v-if="depEdges.length">
          <div v-for="(e, i) in depEdges.slice(0, 40)" :key="i" class="semantic-plan-viewer__edge">
            {{ summarizeEdge(e) }}
          </div>
        </template>
        <ElEmpty v-else description="本运行未带出 dependency_edges 字段" :image-size="48" />
      </ElCollapseItem>
      <ElCollapseItem title="语义边 semantic edge" name="sem">
        <template v-if="semanticEdges.length">
          <div v-for="(e, i) in semanticEdges.slice(0, 40)" :key="i" class="semantic-plan-viewer__edge semantic">
            {{ summarizeEdge(e) }}
          </div>
        </template>
        <ElEmpty v-else description="本运行未带出 semantic_edges 字段" :image-size="48" />
      </ElCollapseItem>
      <ElCollapseItem title="约束链 constraint chain" name="chain">
        <template v-if="constraintChains.length">
          <pre class="semantic-plan-viewer__pre">{{ JSON.stringify(constraintChains, null, 2).slice(0, 2800) }}</pre>
        </template>
        <ElEmpty v-else description="无 constraint_chains 数据" :image-size="48" />
      </ElCollapseItem>
      <ElCollapseItem title="禁止迁移 forbidden transition" name="fb">
        <template v-if="forbidden.length">
          <pre class="semantic-plan-viewer__pre">{{ JSON.stringify(forbidden, null, 2).slice(0, 2000) }}</pre>
        </template>
        <ElEmpty v-else description="未声明 forbid 迁移" :image-size="48" />
      </ElCollapseItem>
    </ElCollapse>
  </div>
</template>

<style scoped lang="scss">
.semantic-plan-viewer {
  font-size: 12px;
  color: #334155;
}

.semantic-plan-viewer__flow {
  padding: 8px;
  margin-bottom: 10px;
  border-radius: 12px;
  background: linear-gradient(180deg, #f8fafc, #fff);
  border: 1px solid #e2e8f0;
}

.semantic-plan-viewer__stage {
  border-radius: 10px;
  padding: 8px 10px;
  border: 1px dashed #cbd5e1;

  .semantic-plan-viewer__stage-tag {
    display: inline-block;
    font-weight: 700;
    font-size: 11px;
    color: #0f172a;
    letter-spacing: 0.06em;
  }
}

.semantic-plan-viewer__stage--dag {
  border-style: solid;
}

.semantic-plan-viewer__stage--ir {
  border-color: rgb(139 92 246 / 45%);
}

.semantic-plan-viewer__stage--ord {
  border-color: rgb(14 165 233 / 45%);
}

.semantic-plan-viewer__hint {
  font-size: 11px;
  color: #64748b;
  margin-left: 8px;
}

.semantic-plan-viewer__arrow {
  text-align: center;
  color: #94a3b8;
  padding: 2px;
}

.semantic-plan-viewer__plan-id {
  margin: 4px 0 0;
  font-family: ui-monospace, monospace;
  word-break: break-all;
}

.semantic-plan-viewer__ordering {
  margin: 8px 0 0;
  padding-left: 18px;
  line-height: 1.5;
}

.muted {
  color: #94a3b8;
  margin: 0;
}

.semantic-plan-viewer__collapse {
  border-radius: 8px;

  --el-collapse-header-text-color: #334155;
  --el-collapse-header-height: 40px;
}

.semantic-plan-viewer__edge {
  padding: 6px 8px;
  border-radius: 8px;
  background: #f8fafc;
  margin-bottom: 6px;
  font-variant-numeric: tabular-nums;

  &.semantic {
    border-left: 3px solid #8b5cf6;
  }
}

.semantic-plan-viewer__pre {
  margin: 0;
  font-size: 11px;
  line-height: 1.4;
  max-height: 200px;
  overflow: auto;
  background: #0f172a;
  color: #e2e8f0;
  padding: 10px;
  border-radius: 8px;
}
</style>
