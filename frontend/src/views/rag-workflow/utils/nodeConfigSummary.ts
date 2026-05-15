import type { RagFlowNodeData } from '@/types/ragWorkflow';

function basenamePath(p: string): string {
  const s = p.replace(/\\/g, '/');
  const i = s.lastIndexOf('/');
  return i >= 0 ? s.slice(i + 1) : s;
}

function parseStorageStrategy(v: unknown): Record<string, unknown> {
  if (v && typeof v === 'object' && !Array.isArray(v)) return v as Record<string, unknown>;
  if (typeof v === 'string') {
    const s = v.trim();
    if (!s) return {};
    try {
      const obj = JSON.parse(s);
      return obj && typeof obj === 'object' && !Array.isArray(obj) ? (obj as Record<string, unknown>) : {};
    } catch {
      return {};
    }
  }
  return {};
}

function summarizeVectorRetrieveBackends(cfg: Record<string, unknown>): string {
  const strategy = parseStorageStrategy(cfg.storage_strategy);
  const backends = new Set<string>();
  for (const steps of Object.values(strategy)) {
    if (!Array.isArray(steps)) continue;
    for (const one of steps) {
      if (!one || typeof one !== 'object' || Array.isArray(one)) continue;
      const b = String((one as Record<string, unknown>).backend || '').trim().toLowerCase();
      if (b) backends.add(b);
    }
  }
  if (!backends.size) backends.add('local_jsonl');
  return [...backends].slice(0, 3).join('+');
}

function hasJsonObjectValue(v: unknown): boolean {
  return !!(v && typeof v === 'object' && !Array.isArray(v) && Object.keys(v as Record<string, unknown>).length);
}

function queryScopeSummary(cfg: Record<string, unknown>): string {
  const q = String(cfg.query || '').trim();
  return q ? '覆盖问题' : '使用全局问题';
}

/**
 * 画布节点卡片 config 摘要（仅展示，不改 data 结构）
 */
export function summarizeNodeConfig(data: RagFlowNodeData): string {
  const cfg = (data.config ?? {}) as Record<string, unknown>;
  const nt = data.nodeType || '';
  if (nt === 'workflow.start') {
    return '';
  }
  if (nt === 'content.route') {
    const parseList = (v: unknown): string[] => {
      if (Array.isArray(v)) return v.map(x => String(x).trim()).filter(Boolean);
      if (typeof v === 'string') {
        const s = v.trim();
        if (!s) return [];
        try {
          const parsed = JSON.parse(s);
          if (Array.isArray(parsed)) return parsed.map(x => String(x).trim()).filter(Boolean);
        } catch {
          return [s];
        }
      }
      return [];
    };
    const mapping = cfg.route_mapping;
    const ignore = parseList(cfg.ignore_types);
    const runtimeDist = (data.runtimeGroupDistribution ?? {}) as Record<string, unknown>;
    const mapKeys =
      mapping && typeof mapping === 'object'
        ? Object.keys(mapping as Record<string, unknown>)
        : [];
    const segs: string[] = [];
    if (mapKeys.length) segs.push(`路由:${mapKeys.join(',')}`);
    if (ignore.length) segs.push(`忽略:${ignore.join(',')}`);
    const runtimePairs = Object.entries(runtimeDist)
      .map(([k, n]) => `${k}:${n}`)
      .slice(0, 5);
    if (runtimePairs.length) segs.push(`分布:${runtimePairs.join(',')}`);
    if (segs.length) return segs.join(' | ').slice(0, 64);
  }
  if (nt === 'storage.persist') {
    const vs = (cfg.vector_storage ?? {}) as Record<string, unknown>;
    const parts: string[] = [];
    const backends: string[] = [];
    if (vs.backend === 'milvus' && String(vs.collection || '').trim()) {
      backends.push('milvus');
      parts.push(`Milvus:${String(vs.collection).trim()}`);
    }
    backends.push('local_jsonl');
    const segs: string[] = [];
    if (parts.length) segs.push(parts.join(' · '));
    if (backends.length) segs.push(`存储:${[...new Set(backends)].join(',')}`);
    const rt = (data.runtimeStorageSummary ?? {}) as Record<string, unknown>;
    const st = typeof rt.stored === 'number' ? rt.stored : undefined;
    const sk = typeof rt.skipped === 'number' ? rt.skipped : undefined;
    const fa = typeof rt.failed === 'number' ? rt.failed : undefined;
    if (st !== undefined || sk !== undefined || fa !== undefined) {
      segs.push(`已存 ${st ?? 0} · 跳过 ${sk ?? 0} · 失败 ${fa ?? 0}`);
    }
    if (segs.length) return segs.join(' | ').slice(0, 88);
  }

  if (nt === 'embedding.index') {
    const parseList = (v: unknown): string[] => {
      if (Array.isArray(v)) return v.map(x => String(x).trim()).filter(Boolean);
      if (typeof v === 'string') {
        const s = v.trim();
        if (!s) return [];
        try {
          const parsed = JSON.parse(s);
          if (Array.isArray(parsed)) return parsed.map(x => String(x).trim()).filter(Boolean);
        } catch {
          return [s];
        }
      }
      return [];
    };
    const strategy = (cfg.embedding_strategy ?? {}) as Record<string, unknown>;
    const enabledPipelines = Object.entries(strategy)
      .filter(([, one]) => {
        if (!one || typeof one !== 'object') return false;
        return Boolean((one as Record<string, unknown>).enabled ?? true);
      })
      .map(([k]) => k);
    const runtime = (data.runtimeEmbeddingSummary ?? {}) as Record<string, unknown>;
    const segs: string[] = [];
    if (enabledPipelines.length) segs.push(`启用:${enabledPipelines.join(',')}`);
    if (typeof runtime.total_records === 'number') segs.push(`记录:${runtime.total_records}`);
    const wv = runtime.with_vector;
    const nv = runtime.without_vector;
    if (typeof wv === 'number' || typeof nv === 'number') segs.push(`向量:${wv ?? 0}/${nv ?? 0}`);
    const skipped = parseList(cfg.skip_pipelines);
    if (skipped.length) segs.push(`跳过:${skipped.join(',')}`);
    if (segs.length) return segs.join(' | ').slice(0, 72);
  }
  if (nt === 'knowledge.select') {
    const cap = (s: string): string => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);
    const vback = String(cfg.vector_backend || '').trim().toLowerCase();
    const gback = String(cfg.graph_backend || '').trim().toLowerCase();
    const mode = String(cfg.collection_mode || 'unified').trim().toLowerCase();
    const unified = String(cfg.collection || '').trim();
    const pipeCols =
      cfg.pipeline_collections && typeof cfg.pipeline_collections === 'object' && !Array.isArray(cfg.pipeline_collections)
        ? Object.values(cfg.pipeline_collections as Record<string, unknown>).map(x => String(x || '').trim()).filter(Boolean)
        : [];
    const text = String(cfg.text_collection || '').trim();
    const table = String(cfg.table_collection || '').trim();
    const vision = String(cfg.vision_collection || '').trim();
    const workspace = String(cfg.workspace || '').trim();
    const segs: string[] = [];
    if (vback) {
      if (mode === 'by_pipeline') segs.push(`${cap(vback)} · ${pipeCols.length || 0} pipelines`);
      else segs.push(`${cap(vback)}${(unified || text) ? ` · ${unified || text}` : ''}`);
    }
    if (gback && gback !== 'none') segs.push(`${cap(gback)}${workspace ? ` · ${workspace}` : ''}`);
    if (!unified && !text && (table || vision)) segs.push([table, vision].filter(Boolean).join(' / '));
    if (!segs.length && hasJsonObjectValue(cfg.local_jsonl_paths)) segs.push('local_jsonl');
    if (segs.length) return segs.join(' · ').slice(0, 64);
  }
  if (nt === 'vector.retrieve') {
    const qScope = queryScopeSummary(cfg);
    const rt = (data.runtimeRetrieveSummary ?? {}) as Record<string, unknown>;
    const total = typeof rt.total === 'number' ? rt.total : undefined;
    const rows = typeof rt.rows_count === 'number' ? rt.rows_count : undefined;
    const warns = typeof rt.warnings_count === 'number' ? rt.warnings_count : 0;
    const dist = (rt.backend_distribution ?? {}) as Record<string, unknown>;
    const distLabel = Object.entries(dist)
      .map(([k, n]) => `${k} ${n}`)
      .slice(0, 2)
      .join(' · ');
    if (
      total !== undefined ||
      rows !== undefined ||
      (dist && typeof dist === 'object' && Object.keys(dist).length > 0) ||
      warns > 0
    ) {
      const segs: string[] = [];
      segs.push(qScope);
      segs.push(`检索 ${total ?? rows ?? 0}`);
      if (distLabel) segs.push(distLabel);
      if (warns > 0) segs.push(`警告 ${warns}`);
      return segs.join(' · ').slice(0, 56);
    }
    const upstream = (data.upstreamKnowledgeHint ?? {}) as Record<string, unknown>;
    const upKid = String(upstream.knowledge_id || '').trim();
    const upVb = String(upstream.vector_backend || '').trim().toLowerCase();
    if (upKid || upVb) {
      const segs: string[] = [qScope, '检索:'];
      if (upKid) segs.push(`KB ${upKid}`);
      if (upVb) segs.push(upVb);
      return segs.join(' ').slice(0, 56);
    }
    const q = String(cfg.query || '').trim();
    const topK = Number(cfg.top_k);
    const back = summarizeVectorRetrieveBackends(cfg);
    const useUp = cfg.use_upstream_storage_refs !== false;
    const segs: string[] = [qScope];
    if (q) {
      const qt = q.length > 20 ? `${q.slice(0, 20)}…` : q;
      segs.push(qt);
    }
    if (Number.isFinite(topK) && topK > 0) segs.push(`TopK ${Math.floor(topK)}`);
    if (back) segs.push(back);
    if (useUp) segs.push('自动使用上游存储结果');
    return segs.join(' · ').slice(0, 56);
  }
  if (nt === 'retrieval.merge') {
    const rt = (data.runtimeMergeSummary ?? {}) as Record<string, unknown>;
    const tin = typeof rt.total_input === 'number' ? rt.total_input : undefined;
    const tout = typeof rt.total_output === 'number' ? rt.total_output : undefined;
    const ded = typeof rt.deduplicated === 'number' ? rt.deduplicated : undefined;
    const dist = (rt.source_distribution ?? {}) as Record<string, unknown>;
    if (tin !== undefined || tout !== undefined || ded !== undefined || Object.keys(dist).length) {
      const segs: string[] = [];
      if (tin !== undefined || tout !== undefined) segs.push(`融合 ${tin ?? 0}→${tout ?? 0}`);
      if (ded !== undefined) segs.push(`去重 ${ded}`);
      const srcKeys = Object.keys(dist).slice(0, 3);
      if (srcKeys.length) segs.push(`来源 ${srcKeys.join('/')}`);
      return segs.join(' · ').slice(0, 56);
    }
    const strategy = String(cfg.fusion_strategy || 'max_score').trim();
    const topK = Number(cfg.top_k);
    return `策略: ${strategy || 'max_score'} · TopK: ${Number.isFinite(topK) && topK > 0 ? Math.floor(topK) : 10}`.slice(0, 56);
  }
  if (nt === 'rerank') {
    const rt = (data.runtimeRerankSummary ?? {}) as Record<string, unknown>;
    const input = typeof rt.input_count === 'number' ? rt.input_count : undefined;
    const output = typeof rt.output_count === 'number' ? rt.output_count : undefined;
    const engineRt = String(rt.rerank_engine || '').trim().toLowerCase();
    const modelRt = String(rt.rerank_model || '').trim();
    if (input !== undefined || output !== undefined || engineRt || modelRt) {
      const segs: string[] = [];
      if (input !== undefined || output !== undefined) segs.push(`重排 ${input ?? 0}→${output ?? 0}`);
      if (engineRt) segs.push(engineRt === 'lightrag' ? 'LightRAG' : 'Runtime');
      if (modelRt && modelRt.toLowerCase() !== 'none') segs.push(modelRt);
      return segs.join(' · ').slice(0, 72);
    }
    const engine = String(cfg.rerank_engine || 'runtime').trim().toLowerCase();
    if (engine === 'lightrag') return '结果重排 · LightRAG';
    const model = String(cfg.rerank_model || 'none').trim() || 'none';
    return `结果重排 · Runtime · ${model}`.slice(0, 72);
  }
  if (nt === 'context.build') {
    const rt = (data.runtimeContextSummary ?? {}) as Record<string, unknown>;
    const input = typeof rt.input_results === 'number' ? rt.input_results : undefined;
    const used = typeof rt.used_results === 'number' ? rt.used_results : undefined;
    const chars = typeof rt.context_chars === 'number' ? rt.context_chars : undefined;
    if (input !== undefined || used !== undefined || chars !== undefined) {
      const segs: string[] = [];
      segs.push(`使用 ${used ?? 0}/${input ?? 0}`);
      segs.push(`${chars ?? 0}字`);
      return segs.join(' · ').slice(0, 56);
    }
    const maxResults = Number(cfg.max_results);
    const maxChars = Number(cfg.max_context_chars);
    return `上下文: Top${Number.isFinite(maxResults) && maxResults > 0 ? Math.floor(maxResults) : 10} · ${Number.isFinite(maxChars) && maxChars > 0 ? Math.floor(maxChars) : 8000}字`.slice(0, 56);
  }
  if (nt === 'llm.generate') {
    const qScope = queryScopeSummary(cfg);
    const rt = (data.runtimeGenerationSummary ?? {}) as Record<string, unknown>;
    const answerChars = typeof rt.answer_chars === 'number' ? rt.answer_chars : undefined;
    const promptChars = typeof rt.prompt_chars === 'number' ? rt.prompt_chars : undefined;
    if (answerChars !== undefined || promptChars !== undefined) {
      return `${qScope} · 答案 ${answerChars ?? 0}字 · prompt ${promptChars ?? 0}字`.slice(0, 56);
    }
    const model = String(cfg.model || '').trim() || 'auto';
    const style = String(cfg.answer_style || '要点式').trim() || '要点式';
    return `${qScope} · 模型: ${model} · 风格: ${style}`.slice(0, 56);
  }
  if (nt === 'keyword.extract') {
    const qScope = queryScopeSummary(cfg);
    const rt = (data.runtimeKeywordSummary ?? {}) as Record<string, unknown>;
    const total = typeof rt.total === 'number' ? rt.total : undefined;
    const high = typeof rt.high_level_count === 'number' ? rt.high_level_count : undefined;
    const low = typeof rt.low_level_count === 'number' ? rt.low_level_count : undefined;
    if (total !== undefined || high !== undefined || low !== undefined) {
      return `${qScope} · 关键词 ${total ?? 0} 个 · high/low ${high ?? 0}/${low ?? 0}`.slice(0, 56);
    }
    const mode = String(cfg.keyword_mode || 'lightrag').trim().toLowerCase();
    if (mode === 'llm') return `${qScope} · LLM关键词`;
    if (mode === 'rule') return `${qScope} · 规则关键词`;
    return `${qScope} · LightRAG关键词`;
  }
  if (nt === 'multimodal.process') {
    const toList = (v: unknown): string[] => {
      if (Array.isArray(v)) return v.map(x => String(x).trim()).filter(Boolean);
      if (typeof v === 'string') {
        const s = v.trim();
        if (!s) return [];
        try {
          const parsed = JSON.parse(s);
          if (Array.isArray(parsed)) return parsed.map(x => String(x).trim()).filter(Boolean);
        } catch {
          return [s];
        }
      }
      return [];
    };
    const useVlm = Boolean(cfg.use_vlm);
    const types = toList(cfg.process_types);
    const processedCount = data.runtimeProcessedCount;
    const segs: string[] = [`VLM:${useVlm ? 'on' : 'off'}`];
    if (types.length) segs.push(`类型:${types.join(',')}`);
    if (typeof processedCount === 'number') segs.push(`已处理:${processedCount}`);
    return segs.join(' | ').slice(0, 56);
  }
  if (nt === 'content.filter') {
    const toList = (v: unknown): string[] => {
      if (Array.isArray(v)) return v.map(x => String(x).trim()).filter(Boolean);
      if (typeof v === 'string') {
        const s = v.trim();
        if (!s) return [];
        try {
          const parsed = JSON.parse(s);
          if (Array.isArray(parsed)) return parsed.map(x => String(x).trim()).filter(Boolean);
        } catch {
          return [s];
        }
      }
      return [];
    };
    const keep = toList(cfg.keep_types);
    const drop = toList(cfg.drop_types);
    const segs: string[] = [];
    if (keep.length) segs.push(`保留: ${keep.join(',')}`);
    if (drop.length) segs.push(`删除: ${drop.join(',')}`);
    if (segs.length) return segs.join(' | ').slice(0, 40);
  }

  if (nt === 'raganything.insert' || nt.includes('insert')) {
    const sp = cfg.source_path;
    if (typeof sp === 'string' && sp.trim()) {
      const b = basenamePath(sp.trim());
      return b.length > 36 ? `${b.slice(0, 33)}…` : b;
    }
  }

  if (nt === 'rag.query' || nt.includes('rag.query') || nt.endsWith('.query')) {
    const qScope = queryScopeSummary(cfg);
    const q = String(cfg.query || '').trim();
    if (!q) return qScope;
    const t = q.length > 16 ? `${q.slice(0, 16)}…` : q;
    return `${qScope} · ${t}`.slice(0, 56);
  }

  if (nt === 'graph.retrieve') {
    const rtSummary = (data.runtimeGraphSummary ?? {}) as Record<string, unknown>;
    const entityCount = typeof rtSummary.entity_count === 'number' ? Number(rtSummary.entity_count) : undefined;
    const relationCount = typeof rtSummary.relation_count === 'number' ? Number(rtSummary.relation_count) : undefined;
    const total = typeof rtSummary.total === 'number' ? Number(rtSummary.total) : undefined;
    if (entityCount !== undefined || relationCount !== undefined || total !== undefined) {
      if (entityCount !== undefined || relationCount !== undefined) {
        return `实体 ${entityCount ?? 0} · 关系 ${relationCount ?? 0}`;
      }
      return `图结果 ${total ?? 0}`;
    }
    const topK = Number(cfg.top_k);
    const backend = String(cfg.graph_backend || 'auto').trim().toLowerCase();
    const ws = String(cfg.workspace || '').trim();
    const segs: string[] = [`图检索 · TopK ${Number.isFinite(topK) && topK > 0 ? Math.floor(topK) : 20}`];
    if (ws) segs.push(`${backend === 'auto' ? 'Neo4j' : backend} · ${ws}`);
    else segs.push('使用知识库图空间');
    return segs.join(' · ').slice(0, 72);
  }

  if (nt === 'chunk.split') {
    const rt = (data.runtimeChunkSummary ?? {}) as Record<string, unknown>;
    const total = typeof rt.total_chunks === 'number' ? Number(rt.total_chunks) : undefined;
    const typeDist = (rt.type_distribution ?? {}) as Record<string, unknown>;
    if (total !== undefined) {
      const types = Object.keys(typeDist).slice(0, 3);
      return `chunks ${total} · ${types.length ? types.join('/') : 'text'}`.slice(0, 72);
    }
    const size = Number(cfg.chunk_token_size);
    const overlap = Number(cfg.chunk_overlap_token_size);
    return `Chunk ${Number.isFinite(size) && size > 0 ? Math.floor(size) : 1200} · overlap ${
      Number.isFinite(overlap) && overlap >= 0 ? Math.floor(overlap) : 100
    }`;
  }

  if (nt === 'entity_relation.extract') {
    const rt = (data.runtimeEntityRelationSummary ?? {}) as Record<string, unknown>;
    const ec = typeof rt.entity_count === 'number' ? Number(rt.entity_count) : undefined;
    const rc = typeof rt.relation_count === 'number' ? Number(rt.relation_count) : undefined;
    if (ec !== undefined || rc !== undefined) {
      return `实体 ${ec ?? 0} 个 · 关系 ${rc ?? 0} 条`;
    }
    const maxChunks = Number(cfg.max_chunks);
    return `实体关系抽取 · max ${Number.isFinite(maxChunks) && maxChunks > 0 ? Math.floor(maxChunks) : 50} chunks`;
  }

  if (nt === 'entity.merge') {
    const rt = (data.runtimeEntityMergeSummary ?? {}) as Record<string, unknown>;
    const input = typeof rt.input_entities === 'number' ? Number(rt.input_entities) : undefined;
    const merged = typeof rt.merged_entities === 'number' ? Number(rt.merged_entities) : undefined;
    const engineRt = String(rt.merge_engine || '').trim().toLowerCase();
    if (input !== undefined || merged !== undefined) {
      const tag = engineRt === 'lightrag' ? 'LightRAG' : 'runtime';
      return `${input ?? 0} → ${merged ?? 0} entities · ${tag}`;
    }
    const engine = String(cfg.merge_engine || 'runtime').trim().toLowerCase();
    if (engine === 'lightrag') return '实体归并 · LightRAG';
    const strategy = String(cfg.merge_strategy || 'normalize').trim().toLowerCase() || 'normalize';
    return `实体归并 · runtime`;
  }

  if (nt === 'relation.merge') {
    const rt = (data.runtimeRelationMergeSummary ?? {}) as Record<string, unknown>;
    const inRel = typeof rt.input_relations === 'number' ? Number(rt.input_relations) : undefined;
    const outRel = typeof rt.merged_relations === 'number' ? Number(rt.merged_relations) : undefined;
    const engineRt = String(rt.merge_engine || '').trim().toLowerCase();
    if (inRel !== undefined || outRel !== undefined) {
      const tag = engineRt === 'lightrag' ? 'LightRAG' : 'runtime';
      return `${inRel ?? 0} → ${outRel ?? 0} relations · ${tag}`;
    }
    const engine = String(cfg.merge_engine || 'runtime').trim().toLowerCase();
    if (engine === 'lightrag') return '关系归并 · LightRAG';
    return `关系归并 · runtime`;
  }

  if (nt === 'graph.merge') {
    const rt = (data.runtimeGraphMergeSummary ?? {}) as Record<string, unknown>;
    const e = typeof rt.entity_count === 'number' ? Number(rt.entity_count) : undefined;
    const r = typeof rt.relation_count === 'number' ? Number(rt.relation_count) : undefined;
    const c = typeof rt.component_count === 'number' ? Number(rt.component_count) : undefined;
    const engineRt = String(rt.merge_engine || '').trim().toLowerCase();
    if (e !== undefined || r !== undefined || c !== undefined) {
      const tag = engineRt === 'lightrag' ? 'LightRAG' : 'runtime';
      return `${e ?? 0} entities · ${r ?? 0} relations · ${c ?? 0} components · ${tag}`;
    }
    const engine = String(cfg.merge_engine || 'runtime').trim().toLowerCase();
    if (engine === 'lightrag') return '图级归并 · LightRAG Consistency';
    return `图级归并 · connected_components`;
  }

  if (nt === 'graph.persist') {
    const rt = (data.runtimeGraphPersistSummary ?? {}) as Record<string, unknown>;
    const ep = typeof rt.entity_persisted === 'number' ? Number(rt.entity_persisted) : undefined;
    const rp = typeof rt.relation_persisted === 'number' ? Number(rt.relation_persisted) : undefined;
    if (ep !== undefined || rp !== undefined) {
      return `${ep ?? 0} entities · ${rp ?? 0} relations stored`;
    }
    const backend = String(cfg.graph_backend || 'neo4j').trim().toLowerCase();
    const backendLabel = backend === 'local_jsonl' ? 'Local JSONL' : backend === 'networkx' ? 'NetworkX' : 'Neo4j';
    return `图谱持久化 · ${backendLabel}`;
  }

  for (const v of Object.values(cfg)) {
    if (typeof v === 'string' && v.trim().length > 0) {
      const t = v.trim();
      if (t.length > 28) return `${t.slice(0, 25)}…`;
      return t;
    }
  }

  return '';
}
