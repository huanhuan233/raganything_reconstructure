/**
 * 从单次运行快照（纯前端推导）拼装 Industrial Semantic Observatory 视图模型。
 * 数据源：run 详情的 ``node_results``、``trace_timeline``、``logs``。
 */

import type { RagRunHistoryDetail, RagSerializedNodeResult } from '@/types/ragWorkflow';

export type ObservatoryConstraintRow = {
  constraint_id?: string;
  target_id?: string;
  predicate?: string;
  reason_zh?: string;
  satisfied?: boolean;
  operands?: Record<string, unknown>;
  verdict: 'valid' | 'rejected' | 'warning' | 'dependency_missing';
};

export type ObservatoryTimelineEvent = {
  id: string;
  ts: string;
  kind: string;
  label: string;
  detail?: Record<string, unknown>;
};

export type SemanticObservatorySnapshot = {
  ontologyObjects: Record<string, unknown>[];
  constraints: Record<string, unknown>[];
  semanticPlan: Record<string, unknown> | null;
  industrialFiltered: { valid_objects?: unknown[]; rejected_objects?: unknown[] } | null;
  runtimeFiltersEcho: Record<string, unknown>[];
  constraintExplanations: ObservatoryConstraintRow[];
  transitionLog: Record<string, unknown>[];
  lastTransition?: { allowed?: boolean; from?: string; to?: string; reason?: string };
  timeline: ObservatoryTimelineEvent[];
  sourceNodeIds: Record<string, string>;
};

function asObjArray(v: unknown): Record<string, unknown>[] {
  if (!Array.isArray(v)) return [];
  return v.filter(x => !!x && typeof x === 'object') as Record<string, unknown>[];
}

function uniqOntology(rows: Record<string, unknown>[]): Record<string, unknown>[] {
  const m = new Map<string, Record<string, unknown>>();
  for (const r of rows) {
    const id = String(r.object_id ?? r.uri ?? JSON.stringify(r).slice(0, 140));
    m.set(id, r);
  }
  return [...m.values()];
}

function uniqConstraints(rows: Record<string, unknown>[]): Record<string, unknown>[] {
  const m = new Map<string, Record<string, unknown>>();
  for (const r of rows) {
    const id = String(r.constraint_id ?? r.expression ?? JSON.stringify(r).slice(0, 140));
    m.set(id, r);
  }
  return [...m.values()];
}

function normalizeExplanation(one: Record<string, unknown>): ObservatoryConstraintRow {
  const sat = one.satisfied;
  let verdict: ObservatoryConstraintRow['verdict'] = 'warning';
  if (sat === true) verdict = 'valid';
  else if (sat === false) verdict = 'rejected';
  const pred = String(one.predicate || '');
  const rz = String(one.reason_zh || '');
  if (pred.includes('dependency') || rz.includes('依赖') || rz.includes('轨迹')) {
    verdict = 'dependency_missing';
  }
  return {
    constraint_id: String(one.constraint_id || ''),
    target_id: String(one.target_id || ''),
    predicate: pred,
    reason_zh: rz,
    satisfied: typeof sat === 'boolean' ? sat : undefined,
    operands: typeof one.operands === 'object' && one.operands !== null ? (one.operands as Record<string, unknown>) : {},
    verdict
  };
}

function ingestNodeData(
  acc: {
    ontologyObjects: Record<string, unknown>[];
    constraints: Record<string, unknown>[];
    semanticPlan: Record<string, unknown> | null;
    industrialFiltered: SemanticObservatorySnapshot['industrialFiltered'];
    runtimeFiltersEcho: Record<string, unknown>[];
    explanations: ObservatoryConstraintRow[];
    transitionLog: Record<string, unknown>[];
    lastTransition: SemanticObservatorySnapshot['lastTransition'];
    sourceNodeIds: Record<string, string>;
  },
  nodeId: string,
  data: unknown
): void {
  if (!data || typeof data !== 'object') return;
  const d = data as Record<string, unknown>;
  acc.sourceNodeIds[nodeId] = nodeId;

  asObjArray(d.ontology_objects).forEach(x => acc.ontologyObjects.push(x));
  asObjArray(d.constraints).forEach(x => acc.constraints.push(x));

  if (d.semantic_plan && typeof d.semantic_plan === 'object') {
    acc.semanticPlan = d.semantic_plan as Record<string, unknown>;
  }

  const filt = d.industrial_filtered ?? d.runtime_filters ?? d.filtered;
  if (!acc.industrialFiltered && filt && typeof filt === 'object' && filt !== null) {
    acc.industrialFiltered = filt as SemanticObservatorySnapshot['industrialFiltered'];
  }
  const filtEcho = d.runtime_filters_echo;
  if (Array.isArray(filtEcho)) {
    filtEcho.forEach(x => {
      if (x && typeof x === 'object' && !Array.isArray(x)) acc.runtimeFiltersEcho.push(x as Record<string, unknown>);
    });
  } else if (filtEcho && typeof filtEcho === 'object' && !Array.isArray(filtEcho)) {
    acc.runtimeFiltersEcho.push(filtEcho as Record<string, unknown>);
  }

  const ce = asObjArray(d.constraint_explanations);
  ce.forEach(c => acc.explanations.push(normalizeExplanation(c)));

  const digest = String(d.explanation_digest_zh || '');
  if (digest && !ce.length) {
    acc.explanations.push({ verdict: 'warning', predicate: 'digest', reason_zh: digest.slice(0, 400) });
  }

  const transitionAllowed = typeof d.transition_allowed === 'boolean' ? d.transition_allowed : undefined;
  if (transitionAllowed !== undefined || d.transition_verdict_zh) {
    acc.lastTransition = {
      allowed: transitionAllowed,
      from: String(d.from_state || d.from || ''),
      to: String(d.to_state || d.to || ''),
      reason: String(d.transition_verdict_zh || '')
    };
    acc.transitionLog.push({
      node_id: nodeId,
      ...acc.lastTransition
    });
  }
}

/** 服务端 trace timeline + logs 转成统一事件列表 */
export function observatoryTimelineFromRunRecord(run: Record<string, unknown>): ObservatoryTimelineEvent[] {
  const out: ObservatoryTimelineEvent[] = [];
  const tl = Array.isArray(run.trace_timeline) ? run.trace_timeline : [];
  tl.forEach((raw, idx) => {
    if (!raw || typeof raw !== 'object') return;
    const t = raw as Record<string, unknown>;
    const ev = String(t.event_type || t.type || '');
    const ts = String(t.ts ?? t.timestamp ?? '');
    out.push({
      id: `${ev || 'evt'}-${idx}`,
      ts,
      kind: ev || 'event',
      label: ev || '(event)',
      detail: typeof t.payload === 'object' && t.payload !== null ? (t.payload as Record<string, unknown>) : t
    });
  });

  const logs = Array.isArray(run.logs) ? run.logs : [];
  logs.forEach((line, idx) => {
    const txt = typeof line === 'string' ? line : String(line);
    if (!/\b(chunk|ontology|constraint|semantic|transition|persist|filtered|plan)\b/i.test(txt))
      return;
    out.push({
      id: `log-${idx}`,
      ts: '',
      kind: 'log.semantic_hint',
      label: txt.slice(0, 160),
      detail: {}
    });
  });

  return out.slice(-120);
}

function mergeTimelineInto(
  base: ObservatoryTimelineEvent[],
  extra: Array<Record<string, unknown>>
): ObservatoryTimelineEvent[] {
  const seen = new Set(base.map(x => `${x.kind}|${x.label}|${x.ts}`));
  const add: ObservatoryTimelineEvent[] = [];
  extra.forEach((t, idx) => {
    if (!t || typeof t !== 'object') return;
    const ev = String((t as { event_type?: string }).event_type ?? (t as { type?: string }).type ?? '');
    const ts = String((t as { ts?: string }).ts ?? '');
    const key = `${ev}|${idx}|${ts}`;
    if (seen.has(key)) return;
    seen.add(key);
    add.push({
      id: `live-${ev}-${idx}`,
      ts,
      kind: ev || 'trace',
      label: ev || '(trace)',
      detail: typeof (t as { payload?: unknown }).payload === 'object' ? ((t.payload as Record<string, unknown>) ?? {}) : (t as Record<string, unknown>)
    });
  });
  return [...base, ...add].slice(-150);
}

export function mergeSemanticObservatoryFromRun(
  detail: RagRunHistoryDetail | Record<string, unknown> | null,
  opts?: { liveTraceTimeline?: Array<Record<string, unknown>> | null }
): SemanticObservatorySnapshot | null {
  if (!detail || typeof detail !== 'object') return null;
  const rec = detail as Record<string, unknown>;
  const nodeResults = (rec.node_results || {}) as Record<string, RagSerializedNodeResult | Record<string, unknown>>;

  let timeline = observatoryTimelineFromRunRecord(rec);
  if (opts?.liveTraceTimeline?.length) {
    timeline = mergeTimelineInto(timeline, opts.liveTraceTimeline);
  }

  const bucket = {
    ontologyObjects: [] as Record<string, unknown>[],
    constraints: [] as Record<string, unknown>[],
    semanticPlan: null as Record<string, unknown> | null,
    industrialFiltered: null as SemanticObservatorySnapshot['industrialFiltered'],
    runtimeFiltersEcho: [] as Record<string, unknown>[],
    explanations: [] as ObservatoryConstraintRow[],
    transitionLog: [] as Record<string, unknown>[],
    lastTransition: undefined as SemanticObservatorySnapshot['lastTransition'],
    sourceNodeIds: {} as Record<string, string>
  };

  for (const [nid, nr] of Object.entries(nodeResults)) {
    const typed = nr as RagSerializedNodeResult & { data?: unknown };
    const data = typed?.data ?? (nr as Record<string, unknown>)?.data;
    ingestNodeData(bucket, nid, data);
  }

  bucket.ontologyObjects = uniqOntology(bucket.ontologyObjects);
  bucket.constraints = uniqConstraints(bucket.constraints);

  if (
    bucket.lastTransition?.allowed !== undefined ||
    bucket.lastTransition?.reason
  ) {
    timeline.push({
      id: `syn-transition-${timeline.length}`,
      ts: '',
      kind: 'state.transition.validated',
      label:
        bucket.lastTransition?.allowed === false ? 'transition rejected' : 'transition validated',
      detail: { ...(bucket.lastTransition ?? {}) }
    });
  }
  if (bucket.semanticPlan && typeof bucket.semanticPlan.plan_id === 'string') {
    timeline.unshift({
      id: 'syn-plan',
      ts: '',
      kind: 'semantic.plan.generated',
      label: `plan ${bucket.semanticPlan.plan_id}`
    });
  }

  const hasPayload =
    bucket.ontologyObjects.length > 0 ||
    bucket.constraints.length > 0 ||
    !!bucket.semanticPlan ||
    bucket.runtimeFiltersEcho.length > 0 ||
    bucket.explanations.length > 0 ||
    !!bucket.industrialFiltered;

  if (!hasPayload && timeline.length === 0) return null;

  const snap: SemanticObservatorySnapshot = {
    ontologyObjects: bucket.ontologyObjects,
    constraints: bucket.constraints,
    semanticPlan: bucket.semanticPlan,
    industrialFiltered: bucket.industrialFiltered,
    runtimeFiltersEcho: bucket.runtimeFiltersEcho,
    constraintExplanations: bucket.explanations,
    transitionLog: bucket.transitionLog,
    lastTransition: bucket.lastTransition,
    timeline,
    sourceNodeIds: bucket.sourceNodeIds
  };

  return snap;
}
