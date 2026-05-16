<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{ obj: Record<string, unknown> | null }>();

function pick(...keys: string[]): string | undefined {
  const o = props.obj;
  if (!o) return undefined;
  for (const k of keys) {
    const v = o[k];
    if (v === undefined || v === null || v === '') continue;
    return typeof v === 'object' ? JSON.stringify(v).slice(0, 280) : String(v);
  }
  return undefined;
}

function legalityBadge(): string {
  const o = props.obj;
  if (!o) return '—';
  const raw = (
    pick('runtime_legal', 'is_legal', 'legal', 'legality') ??
    ''
  ).toLowerCase();
  if (raw.includes('false') || raw.includes('illegal') || raw.includes('reject')) return 'illegal';
  if (raw.includes('true') || raw.includes('legal') || raw.includes('ok')) return 'legal';
  if (pick('lifecycle_stage')) return 'lifecycle';
  return 'unknown';
}

const rows = computed(() => {
  const o = props.obj;
  const out = [
    { k: '类型', v: pick('ontology_type', 'type_bucket', 'type', '@type') },
    { k: '实例', v: pick('uri', 'object_id', 'id', '@id') },
    { k: '当前状态', v: pick('state', 'current_state', 'status') },
    { k: '生命周期', v: pick('lifecycle_stage', 'stage', 'phase') },
    {
      k: '约束附着',
      v: pick(
        'constraint_ids',
        'constraints_attached',
        'constraint_refs',
        'linked_constraints'
      )
    },
    {
      k: '语义关联',
      v: pick('semantic_roles', 'semantic_relations', 'relations_summary', 'graph_links')
    },
    {
      k: '运行时合法性',
      v: `${legalityBadge()} · ${pick('rejection_reason', 'illegal_reason_zh', 'validation_note') ?? '—'}`
    }
  ];
  return out.filter(r => !!r.v && r.v.trim() !== '—');
});

const supplemental = computed(() => {
  const o = props.obj;
  if (!o) return [] as Array<{ label: string; value: string }>;
  /** 不落 JSON dump：只展示少量可读余量字段 */
  const skip = new Set([
    '@context',
    'raw_blob',
    'embedding'
  ]);
  const out: Array<{ label: string; value: string }> = [];
  for (const [k, v] of Object.entries(o)) {
    if (skip.has(k)) continue;
    if (rows.value.some(r => r.v?.includes?.(String(v).slice(0, 80)))) continue;
    if (typeof v === 'object' && v !== null && !Array.isArray(v)) continue;
    if (typeof v !== 'string' && typeof v !== 'number' && typeof v !== 'boolean' && !Array.isArray(v)) continue;
    let s =
      typeof v === 'object' ? JSON.stringify(v).slice(0, 240) : String(v);
    s = s.slice(0, 240);
    if (s.length < 3) continue;
    if (rows.value.some(x => String(x.k) === k || String(x.v) === s)) continue;
    if (out.length >= 12) break;
    out.push({ label: k, value: s });
  }
  return out;
});
</script>

<template>
  <div class="ontology-inspector">
    <template v-if="props.obj">
      <ElDescriptions :column="1" size="small" border class="ontology-inspector__desc">
        <ElDescriptionsItem v-for="row in rows" :key="row.k" :label="row.k">
          {{ row.v }}
        </ElDescriptionsItem>
      </ElDescriptions>
      <div v-if="supplemental.length" class="ontology-inspector__more">
        <div class="ontology-inspector__more-title">上下文字段</div>
        <dl>
          <div v-for="s in supplemental" :key="s.label" class="ontology-inspector__kv">
            <dt>{{ s.label }}</dt>
            <dd>{{ s.value }}</dd>
          </div>
        </dl>
      </div>
    </template>
    <ElEmpty v-else description="未选择本体对象" :image-size="56" />
  </div>
</template>

<style scoped lang="scss">
.ontology-inspector {
  font-size: 12px;
}

.ontology-inspector__desc {
  margin-bottom: 8px;

  --el-descriptions-table-border-color: #e5e7eb;
}

.ontology-inspector__more-title {
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 6px;
}

.ontology-inspector__kv {
  margin: 0 0 6px;

  dt {
    font-size: 10px;
    color: #94a3b8;
  }

  dd {
    margin: 2px 0 0;
    color: #334155;
    word-break: break-word;
    line-height: 1.4;
  }
}
</style>
