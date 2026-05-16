import type { RagFlowNodeData, RagNodeMetadata } from '@/types/ragWorkflow';

/** ISR 画布 / 调色板可视化域（与后端 node_type 前缀约定对齐） */
export type IsrVisualDomain = 'ontology' | 'constraint' | 'semantic' | 'state' | 'graph' | 'runtime';

export function resolveIsrVisualDomain(nodeType: string): IsrVisualDomain | null {
  const t = String(nodeType || '');
  if (!t) return null;
  if (
    /^ontology\.graph\./i.test(t) ||
    /^semantic\.relation/i.test(t) ||
    /^constraint\.relation/i.test(t) ||
    /^graph\./i.test(t)
  ) {
    return 'graph';
  }
  if (/^ontology\./i.test(t)) return 'ontology';
  if (/^constraint\./i.test(t)) return 'constraint';
  if (/^semantic\./i.test(t)) return 'semantic';
  if (/^state\./i.test(t)) return 'state';
  if (/^runtime\./i.test(t)) return 'runtime';
  return null;
}

function asStrList(v: unknown): string[] | undefined {
  if (!Array.isArray(v)) return undefined;
  const xs = v.map(x => String(x)).filter(Boolean);
  return xs.length ? xs : [];
}

/** 将 API nodes 中的 ISR 语义元数据塞进画布 RagFlowNodeData（提交 run/save 时仍只扁平化 id/type/config） */
export function isrSemanticFieldsFromMeta(meta: RagNodeMetadata | undefined): Partial<RagFlowNodeData> {
  if (!meta) return {};
  const m = meta as RagNodeMetadata & Record<string, unknown>;
  const si = asStrList(m.semantic_inputs);
  const so = asStrList(m.semantic_outputs);
  const cd = asStrList(m.constraint_dependencies);
  const rd = asStrList(m.runtime_state_dependencies);
  const ot = asStrList(m.ontology_types);
  const out: Partial<RagFlowNodeData> = {};
  if (si) out.semanticInputs = si;
  if (so) out.semanticOutputs = so;
  if (cd) out.constraintDependencies = cd;
  if (rd) out.runtimeStateDependencies = rd;
  if (ot) out.ontologyTypes = ot;
  return out;
}
