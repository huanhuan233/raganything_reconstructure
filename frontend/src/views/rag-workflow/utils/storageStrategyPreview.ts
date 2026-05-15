/** 与 backend_runtime/storage/ui_strategy 对齐：预览将写入 persist 的 storage_strategy（只读展示） */

const PIPELINES = ['text_pipeline', 'table_pipeline', 'vision_pipeline', 'equation_pipeline'] as const;

function asRecord(v: unknown): Record<string, unknown> {
  return v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
}

export function buildStorageStrategyPreview(vectorStorage: unknown): Record<string, unknown[]> {
  const vs = asRecord(vectorStorage);
  const coll = vs.backend === 'milvus' ? String(vs.collection || '').trim() : '';
  const useMilvus = vs.backend === 'milvus' && Boolean(coll);

  const out: Record<string, unknown[]> = {};
  for (const p of PIPELINES) {
    const steps: unknown[] = [];
    if (useMilvus) steps.push({ backend: 'milvus', collection: coll });
    out[p] = steps;
  }
  return out;
}
