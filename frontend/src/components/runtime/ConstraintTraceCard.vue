<script setup lang="ts">
import type { ObservatoryConstraintRow } from './useSemanticObservatory';

defineProps<{ row: ObservatoryConstraintRow }>();

function verdictLabel(v: ObservatoryConstraintRow['verdict']) {
  const m: Record<ObservatoryConstraintRow['verdict'], string> = {
    valid: '已过约束',
    rejected: '拒绝',
    warning: '提示',
    dependency_missing: '依赖缺失'
  };
  return m[v];
}

function verdictClass(v: ObservatoryConstraintRow['verdict']) {
  return `constraint-trace-card--${v}`;
}
</script>

<template>
  <div class="constraint-trace-card" :class="verdictClass(row.verdict)">
    <header class="constraint-trace-card__head">
      <span class="constraint-trace-card__verdict">{{ verdictLabel(row.verdict) }}</span>
      <span v-if="row.constraint_id" class="constraint-trace-card__cid" :title="row.constraint_id">{{
        row.constraint_id
      }}</span>
    </header>
    <dl class="constraint-trace-card__body">
      <div v-if="row.target_id" class="constraint-trace-card__kv">
        <dt>被拒对象</dt>
        <dd>{{ row.target_id }}</dd>
      </div>
      <div v-if="row.predicate" class="constraint-trace-card__kv">
        <dt>规则 / 谓词</dt>
        <dd>{{ row.predicate }}</dd>
      </div>
      <div v-if="row.reason_zh" class="constraint-trace-card__kv constraint-trace-card__why">
        <dt>可解释原因</dt>
        <dd>{{ row.reason_zh }}</dd>
      </div>
      <div
        v-if="row.operands && Object.keys(row.operands).length"
        class="constraint-trace-card__kv constraint-trace-card__operands"
      >
        <dt>依赖 / operands</dt>
        <dd>
          <ElTag v-for="(vv, kk) in row.operands" :key="String(kk)" size="small" class="operand-tag">
            {{ kk }}: {{ vv }}
          </ElTag>
        </dd>
      </div>
    </dl>
  </div>
</template>

<style scoped lang="scss">
.constraint-trace-card {
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  padding: 10px 12px;
  font-size: 12px;
  background: #fff;
}

.constraint-trace-card--valid {
  border-color: rgb(74 222 128 / 45%);
  background: linear-gradient(160deg, #f0fdf4, #fff);
}

.constraint-trace-card--rejected {
  border-color: rgb(248 113 113 / 55%);
  background: linear-gradient(160deg, #fef2f2, #fff);
}

.constraint-trace-card--warning {
  border-color: rgb(251 191 36 / 45%);
  background: linear-gradient(160deg, #fffbeb, #fff);
}

.constraint-trace-card--dependency_missing {
  border-color: rgb(167 139 250 / 45%);
  background: linear-gradient(160deg, #f5f3ff, #fff);
}

.constraint-trace-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.constraint-trace-card__verdict {
  font-weight: 700;
  font-size: 11px;
  color: #0f172a;
}

.constraint-trace-card__cid {
  font-family: ui-monospace, monospace;
  font-size: 10px;
  color: #64748b;
  max-width: 55%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.constraint-trace-card__body {
  margin: 0;
}

.constraint-trace-card__kv {
  margin: 0 0 6px;

  &:last-child {
    margin-bottom: 0;
  }

  dt {
    font-size: 10px;
    color: #94a3b8;
    margin-bottom: 2px;
  }

  dd {
    margin: 0;
    color: #334155;
    line-height: 1.45;
    word-break: break-word;
  }
}

.constraint-trace-card__operands dd {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.operand-tag {
  font-variant-numeric: tabular-nums;
}
</style>
