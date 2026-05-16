<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import ConstraintTraceCard from './ConstraintTraceCard.vue';
import OntologyObjectInspector from './OntologyObjectInspector.vue';
import SemanticPlanViewer from './SemanticPlanViewer.vue';
import RuntimeTimeline from './RuntimeTimeline.vue';
import type { SemanticObservatorySnapshot } from './useSemanticObservatory';

const props = defineProps<{
  snapshot: SemanticObservatorySnapshot | null;
}>();

const pickedObj = ref<Record<string, unknown> | null>(null);

const ontologyList = computed(() => props.snapshot?.ontologyObjects ?? []);
const constraintsFlat = computed(() => props.snapshot?.constraints ?? []);
const explanations = computed(() => props.snapshot?.constraintExplanations ?? []);
const filterEcho = computed(() => props.snapshot?.runtimeFiltersEcho ?? []);
const transitions = computed(() => props.snapshot?.transitionLog ?? []);
const timeline = computed(() => props.snapshot?.timeline ?? []);

const rejCount = computed(() => explanations.value.filter(e => e.verdict === 'rejected').length);

watch(
  () => ontologyList.value,
  rows => {
    if (!rows.length) {
      pickedObj.value = null;
      return;
    }
    if (!pickedObj.value || !rows.includes(pickedObj.value)) {
      pickedObj.value = rows[0];
    }
  },
  { immediate: true }
);

function ontologyTitle(o: Record<string, unknown>): string {
  const oid = '@id' in o ? String((o as { '@id'?: string })['@id'] ?? '').trim() : '';
  const idLike = String(o.object_id ?? o.uri ?? o.id ?? '').trim() || oid;
  const tp = String(o.ontology_type ?? o.type_bucket ?? '').trim();
  return idLike || tp || '(object)';
}

function constraintTitle(c: Record<string, unknown>): string {
  return String(c.constraint_id ?? c.expression ?? 'constraint').slice(0, 80);
}

function onPickRow(row: Record<string, unknown>) {
  pickedObj.value = row;
}

const inspectorSubject = computed(() => pickedObj.value);
</script>

<template>
  <div class="semantic-runtime-panel">
    <template v-if="snapshot">
      <div class="srp-metrics">
        <div class="srp-chip srp-chip--ontology">本体对象 × {{ ontologyList.length }}</div>
        <div class="srp-chip srp-chip--constraint">
          约束 × {{ constraintsFlat.length }} · Trace {{ explanations.length }}
        </div>
        <div class="srp-chip srp-chip--warn">拒绝条目 {{ rejCount }}</div>
        <div v-if="snapshot.lastTransition?.allowed !== undefined" class="srp-chip srp-chip--state">
          最近一次迁移 {{ snapshot.lastTransition.allowed === false ? '拒绝' : '通过' }}
        </div>
      </div>

      <RuntimeTimeline :events="timeline" />

      <ElCollapse accordion class="srp-collapse">
        <ElCollapseItem title="本体对象 · Ontology Inspector" name="ontology">
          <div class="srp-split">
            <ul class="srp-mini-list">
              <li v-for="(o, i) in ontologyList.slice(0, 40)" :key="i">
                <button type="button" class="srp-mini-btn" @click="onPickRow(o)">
                  {{ ontologyTitle(o) }}
                </button>
              </li>
            </ul>
            <OntologyObjectInspector class="srp-inspect" :obj="inspectorSubject" />
          </div>
          <template v-if="!ontologyList.length">
            <ElEmpty description="未发现 ontology_objects" :image-size="48" />
          </template>
        </ElCollapseItem>

        <ElCollapseItem title="约束溯源 Constraint trace" name="constraints">
          <div class="srp-cards">
            <ConstraintTraceCard v-for="(row, idx) in explanations.slice(0, 24)" :key="idx" :row="row" />
          </div>
          <template v-if="snapshot.industrialFiltered">
            <div class="srp-subhead">Industrial filter（valid / rejected）</div>
            <p class="srp-plain">
              valid:
              {{ (snapshot.industrialFiltered.valid_objects as unknown[] | undefined)?.length ?? 0 }}
              rejected:
              {{
                (snapshot.industrialFiltered.rejected_objects as unknown[] | undefined)?.length ?? 0
              }}
            </p>
          </template>
          <template v-if="filterEcho.length">
            <div class="srp-subhead">runtime_filters_echo</div>
            <pre class="srp-pre">{{ JSON.stringify(filterEcho.slice(0, 3), null, 2) }}</pre>
          </template>
        </ElCollapseItem>

        <ElCollapseItem title="语义执行计划" name="plan">
          <SemanticPlanViewer :plan="snapshot.semanticPlan" />
        </ElCollapseItem>

        <ElCollapseItem title="状态迁移日志" name="transition">
          <template v-if="transitions.length">
            <pre class="srp-pre">{{ JSON.stringify(transitions.slice(0, 8), null, 2) }}</pre>
          </template>
          <ElEmpty v-else description="未发现 transition_validate 载荷" :image-size="48" />
        </ElCollapseItem>

        <ElCollapseItem title="约束平面 constraints[]" name="constraint_plane">
          <ul class="srp-plain-list">
            <li v-for="(c, i) in constraintsFlat.slice(0, 28)" :key="i">{{ constraintTitle(c) }}</li>
          </ul>
          <template v-if="!constraintsFlat.length">
            <ElEmpty description="无 constraints[]" :image-size="48" />
          </template>
        </ElCollapseItem>
      </ElCollapse>
    </template>
    <template v-else>
      <div class="srp-placeholder">
        <div class="srp-ph-title">Runtime Semantic Observatory</div>
        <p class="srp-ph-text">
          当运行结果包含 ontology_objects、constraints、semantic_plan 或约束解释等 ISR 载荷时，将在此处聚合回放；请先执行工业语义工作流并打开本条运行。
        </p>
      </div>
    </template>
  </div>
</template>

<style scoped lang="scss">
.semantic-runtime-panel {
  font-size: 12px;
}

.srp-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.srp-chip {
  font-size: 11px;
  font-weight: 600;
  border-radius: 999px;
  padding: 3px 10px;
}

.srp-chip--ontology {
  background: rgb(30 64 175 / 10%);
  color: #1e3a8a;
}

.srp-chip--constraint {
  background: rgb(220 38 38 / 12%);
  color: #991b1b;
}

.srp-chip--warn {
  background: rgb(234 88 12 / 12%);
  color: #9a3412;
}

.srp-chip--state {
  background: rgb(14 116 144 / 12%);
  color: #155e75;
}

.srp-collapse {
  border-radius: 10px;

  --el-collapse-header-font-size: 12px;
  --el-collapse-header-height: 40px;
}

.srp-cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.srp-split {
  display: grid;
  gap: 10px;

  @media (min-width: 420px) {
    grid-template-columns: minmax(0, 120px) 1fr;
  }
}

.srp-mini-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.srp-mini-btn {
  width: 100%;
  margin-bottom: 4px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 4px 8px;
  font-size: 10px;
  text-align: left;
  cursor: pointer;
  background: #fff;
}

.srp-mini-btn:hover {
  border-color: #93c5fd;
  background: #eff6ff;
}

.srp-plain {
  margin: 0;
  font-size: 11px;
  color: #64748b;
}

.srp-subhead {
  font-weight: 600;
  margin: 10px 0 6px;
  color: #0f172a;
}

.srp-plain-list {
  margin: 0;
  padding-left: 14px;

  li {
    margin-bottom: 4px;
    color: #475569;
  }
}

.srp-pre {
  margin: 0;
  font-size: 10px;
  line-height: 1.35;
  max-height: 180px;
  overflow: auto;
  padding: 8px;
  border-radius: 8px;
  background: #0f172a;
  color: #e2e8f0;
}

.srp-placeholder {
  padding: 16px;
  border-radius: 12px;
  border: 1px dashed #cbd5e1;
  background: #f8fafc;
}

.srp-ph-title {
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 8px;
}

.srp-ph-text {
  margin: 0;
  font-size: 12px;
  color: #64748b;
  line-height: 1.55;
}
</style>
