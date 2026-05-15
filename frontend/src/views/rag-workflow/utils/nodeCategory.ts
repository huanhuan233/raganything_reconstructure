import type { RagNodeMetadata } from '@/types/ragWorkflow';
import type { PaletteGroup } from '../types';

export const CATEGORY_ORDER = [
  'document',
  'content',
  'lightrag',
  'raganything',
  'graph',
  'retrieval',
  'industrial_parsing',
  'process_knowledge',
  'industrial_graph',
  'constraint_extraction',
  'context',
  'llm',
  'rag',
  'multimodal',
  'other'
] as const;

export const CATEGORY_LABELS: Record<string, string> = {
  document: '文档',
  content: '内容',
  lightrag: 'LightRAG',
  raganything: 'RAG-Anything',
  graph: '知识图谱',
  retrieval: '检索',
  industrial_parsing: 'Industrial Parsing',
  process_knowledge: 'Process Knowledge',
  industrial_graph: 'Industrial Graph',
  constraint_extraction: 'Constraint Extraction',
  context: '上下文',
  llm: 'LLM',
  rag: 'RAG',
  multimodal: '多模态',
  other: '其他'
};

const categoryOrderSet = new Set<string>(CATEGORY_ORDER);

export function buildPaletteGroups(catalog: RagNodeMetadata[], searchTrimmed: string): PaletteGroup[] {
  const q = searchTrimmed.toLowerCase();
  const buckets = new Map<string, RagNodeMetadata[]>();
  for (const k of CATEGORY_ORDER) {
    buckets.set(k, []);
  }
  for (const meta of catalog) {
    if (q) {
      const hay = `${meta.node_type} ${meta.display_name} ${meta.description}`.toLowerCase();
      if (!hay.includes(q)) continue;
    }
    let cat = meta.category;
    if (!categoryOrderSet.has(cat)) cat = 'other';
    buckets.get(cat)!.push(meta);
  }
  return CATEGORY_ORDER.map(key => ({
    key,
    title: CATEGORY_LABELS[key] ?? key,
    items: buckets.get(key) ?? []
  })).filter(g => g.items.length > 0);
}
