<script setup lang="ts">
import { Icon } from '@iconify/vue';
import { computed, ref, watch } from 'vue';
import type { RunStatus } from '../composables/useWorkflowRun';
import WorkflowChunkSplitRunPanel from './WorkflowChunkSplitRunPanel.vue';
import WorkflowContextBuildRunPanel from './WorkflowContextBuildRunPanel.vue';
import WorkflowEntityMergeRunPanel from './WorkflowEntityMergeRunPanel.vue';
import WorkflowEntityRelationExtractRunPanel from './WorkflowEntityRelationExtractRunPanel.vue';
import WorkflowGraphMergeRunPanel from './WorkflowGraphMergeRunPanel.vue';
import WorkflowGraphPersistRunPanel from './WorkflowGraphPersistRunPanel.vue';
import WorkflowGraphRetrieveRunPanel from './WorkflowGraphRetrieveRunPanel.vue';
import WorkflowKeywordExtractRunPanel from './WorkflowKeywordExtractRunPanel.vue';
import WorkflowLlmGenerateRunPanel from './WorkflowLlmGenerateRunPanel.vue';
import WorkflowMultimodalRunPanel from './WorkflowMultimodalRunPanel.vue';
import WorkflowIndustrialRunPanel from './WorkflowIndustrialRunPanel.vue';
import WorkflowRelationMergeRunPanel from './WorkflowRelationMergeRunPanel.vue';
import WorkflowRerankRunPanel from './WorkflowRerankRunPanel.vue';
import WorkflowRetrievalMergeRunPanel from './WorkflowRetrievalMergeRunPanel.vue';
import WorkflowStoragePersistRunPanel from './WorkflowStoragePersistRunPanel.vue';

const props = withDefaults(
  defineProps<{
    lastRunRaw: string;
    runErrorMsg: string;
    runStatus: RunStatus;
    answerSnippet: string;
    preferredNodeId?: string | null;
    nodeTitleMap?: Record<string, string>;
    /** ``dock``：辅助抽屉内；``collapse``：外层包一层 ElCollapseItem（旧布局） */
    mode?: 'dock' | 'collapse';
  }>(),
  { mode: 'collapse', preferredNodeId: null, nodeTitleMap: () => ({}) }
);

const rawJsonOpen = ref<string[]>([]);
const nodeOpen = ref<string[]>([]);
const nodeRawView = ref<Record<string, boolean>>({});
const compactJsonView = ref(true);

const statusTone = computed(() => {
  if (props.runStatus === 'running') return 'running';
  if (props.runStatus === 'error') return 'error';
  if (props.runStatus === 'success') return 'success';
  return 'idle';
});

const statusLabel = computed(() => {
  switch (props.runStatus) {
    case 'running':
      return '运行中…';
    case 'success':
      return '上次运行：成功';
    case 'error':
      return '上次运行：失败';
    default:
      return '尚未运行';
  }
});

type NodeResultLike = {
  success?: boolean;
  data?: unknown;
  error?: string | null;
  metadata?: unknown;
};

const nodeResults = computed<Record<string, NodeResultLike>>(() => {
  if (!props.lastRunRaw.trim()) return {};
  try {
    const o = JSON.parse(props.lastRunRaw) as Record<string, unknown>;
    const nr = o.node_results;
    if (!nr || typeof nr !== 'object') return {};
    return nr as Record<string, NodeResultLike>;
  } catch {
    return {};
  }
});

const nodeResultList = computed(() =>
  Object.entries(nodeResults.value).map(([id, result]) => ({
    id,
    result
  }))
);

function formatJson(v: unknown, compact = true): string {
  if (!compact) {
    try {
      return JSON.stringify(v, null, 2);
    } catch {
      return String(v);
    }
  }
  const HEAVY_ARRAY_KEYS = new Set([
    'embedding_records',
    'storage_refs',
    'vector_results',
    'reranked_results',
    'unified_results',
    'context_blocks',
    'chunks',
    'entities',
    'relations',
    'merged_entities',
    'merged_relations'
  ]);

  function truncateString(s: string): string {
    if (s.length <= 360) return s;
    const keepHead = 180;
    const keepTail = 120;
    const omitted = s.length - keepHead - keepTail;
    return `${s.slice(0, keepHead)}...(omitted ${omitted} chars)...${s.slice(-keepTail)}`;
  }

  function shrinkArray(a: unknown[], parentKey: string): unknown[] {
    const key = parentKey.toLowerCase();
    const isNumeric = a.every(one => typeof one === 'number');
    if (isNumeric && key.includes('vector') && a.length > 6) {
      return [...a.slice(0, 3), `...(${a.length - 6} omitted)...`, ...a.slice(-3)];
    }
    if (HEAVY_ARRAY_KEYS.has(parentKey) && a.length > 3) {
      return [...a.slice(0, 2), `...(${a.length - 3} omitted items)...`, a[a.length - 1]];
    }
    if (a.length > 20 && key !== 'bbox') {
      return [...a.slice(0, 5), `...(${a.length - 7} omitted items)...`, ...a.slice(-2)];
    }
    return a.map(one => shrink(one, parentKey));
  }

  function shrinkObject(obj: Record<string, unknown>, parentKey: string): Record<string, unknown> {
    if (parentKey === 'raw_result') {
      return {
        _omitted: 'raw_result hidden',
        keys: Object.keys(obj).slice(0, 20)
      };
    }
    const out: Record<string, unknown> = {};
    for (const [k, v2] of Object.entries(obj)) {
      out[k] = shrink(v2, k);
    }
    return out;
  }

  function shrink(x: unknown, parentKey = ''): unknown {
    if (typeof x === 'string') return truncateString(x);
    if (Array.isArray(x)) return shrinkArray(x, parentKey);
    if (x && typeof x === 'object') return shrinkObject(x as Record<string, unknown>, parentKey);
    return x;
  }

  try {
    return JSON.stringify(shrink(v), null, 2);
  } catch {
    return String(v);
  }
}

const activeNodeRawJson = computed(() => {
  const nr = nodeResults.value;
  if (!Object.keys(nr).length) return '';
  const preferred = props.preferredNodeId;
  const openId = nodeOpen.value[0];
  const nodeId = preferred && nr[preferred] ? preferred : openId && nr[openId] ? openId : Object.keys(nr)[0];
  const one = nr[nodeId];
  if (!one) return '';
  return formatJson(one, compactJsonView.value);
});

function nodeTitle(id: string): string {
  return props.nodeTitleMap?.[id] || id;
}

function nodeDisplayTitle(id: string): string {
  const raw = nodeTitle(id);
  // 对“中文名（英文.node_type）”中的英文类型做截断，避免挤成多行。
  const zhParen = raw.match(/（([^）]+)）/);
  if (zhParen?.[1]) {
    const inner = zhParen[1];
    if (inner.length > 28) {
      return raw.replace(/（[^）]+）/, `（${inner.slice(0, 28)}...）`);
    }
    return raw;
  }
  const enParen = raw.match(/\(([^)]+)\)/);
  if (enParen?.[1]) {
    const inner = enParen[1];
    if (inner.length > 28) {
      return raw.replace(/\([^)]+\)/, `(${inner.slice(0, 28)}...)`);
    }
  }
  return raw;
}

function isNodeRaw(id: string): boolean {
  return Boolean(nodeRawView.value[id]);
}

function toggleNodeRaw(id: string): void {
  nodeRawView.value = {
    ...nodeRawView.value,
    [id]: !nodeRawView.value[id]
  };
}

function nodeViewIcon(id: string): string {
  return isNodeRaw(id) ? 'mdi:text-box-outline' : 'mdi:code-json';
}

type Dict = Record<string, unknown>;
type PrettyBlock = { title: string; lines: string[]; scrollable?: boolean };

function asRecord(v: unknown): Dict {
  return v && typeof v === 'object' && !Array.isArray(v) ? (v as Dict) : {};
}

function inferNodeType(id: string, result: NodeResultLike): string {
  const meta = asRecord(result.metadata);
  const mNode = meta.node;
  if (typeof mNode === 'string' && mNode.trim()) return mNode.trim();
  const t = nodeTitle(id);
  const mm = t.match(/\(([\w.]+)\)\s*$/);
  if (mm?.[1]) return mm[1];
  return '';
}

function toDistributionLine(v: unknown, maxItems = 8): string {
  const d = asRecord(v);
  const pairs = Object.entries(d).slice(0, maxItems);
  if (!pairs.length) return '无';
  return pairs.map(([k, n]) => `${k}:${n}`).join(', ');
}

function isScrollablePrettyBlock(blk: PrettyBlock): boolean {
  return Boolean(blk.scrollable);
}

function isStoragePersistPanel(result: NodeResultLike): boolean {
  const d = asRecord(result.data);
  if (Array.isArray(d.storage_refs)) return true;
  if (d.storage_summary && typeof d.storage_summary === 'object') return true;
  return false;
}

function isRetrievalMergePanel(result: NodeResultLike): boolean {
  const d = asRecord(result.data);
  if (Array.isArray(d.unified_results)) return true;
  if (d.merge_summary && typeof d.merge_summary === 'object') return true;
  return false;
}

function isRerankPanel(result: NodeResultLike): boolean {
  const d = asRecord(result.data);
  if (Array.isArray(d.reranked_results)) return true;
  if (d.rerank_summary && typeof d.rerank_summary === 'object') return true;
  return false;
}

function isContextBuildPanel(result: NodeResultLike): boolean {
  const d = asRecord(result.data);
  if (typeof d.context_str === 'string') return true;
  if (d.context_summary && typeof d.context_summary === 'object') return true;
  if (Array.isArray(d.context_blocks)) return true;
  return false;
}

function isLlmGeneratePanel(result: NodeResultLike): boolean {
  const d = asRecord(result.data);
  if (d.generation_summary && typeof d.generation_summary === 'object') return true;
  if (typeof d.answer === 'string' && typeof d.prompt === 'string') return true;
  return false;
}

function isKeywordExtractPanel(result: NodeResultLike): boolean {
  const d = asRecord(result.data);
  if (Array.isArray(d.keywords)) return true;
  if (d.keyword_summary && typeof d.keyword_summary === 'object') return true;
  return false;
}

function isGraphRetrievePanel(result: NodeResultLike): boolean {
  const d = asRecord(result.data);
  if (d.graph && typeof d.graph === 'object') return false;
  if (Array.isArray(d.graph_results)) return true;
  const gs = asRecord(d.graph_summary);
  if (typeof gs.backend === 'string' || typeof gs.workspace === 'string' || typeof gs.total === 'number') return true;
  return false;
}

function isGraphMergePanel(result: NodeResultLike): boolean {
  const d = asRecord(result.data);
  if (d.graph && typeof d.graph === 'object') return true;
  const gs = asRecord(d.graph_summary);
  if (typeof gs.component_count === 'number' || typeof gs.isolated_entity_count === 'number') return true;
  return false;
}

function isGraphPersistPanel(result: NodeResultLike): boolean {
  const d = asRecord(result.data);
  if (d.graph_persist_summary && typeof d.graph_persist_summary === 'object') return true;
  return false;
}

function isChunkSplitPanel(result: NodeResultLike): boolean {
  const d = asRecord(result.data);
  if (Array.isArray(d.chunks)) return true;
  if (d.chunk_summary && typeof d.chunk_summary === 'object') return true;
  return false;
}

function isMultimodalProcessPanel(result: NodeResultLike): boolean {
  const d = asRecord(result.data);
  if (d.process_summary && typeof d.process_summary === 'object') return true;
  if (Array.isArray(d.multimodal_descriptions)) return true;
  return false;
}

function isEntityRelationExtractPanel(result: NodeResultLike): boolean {
  const d = asRecord(result.data);
  if (Array.isArray(d.entities)) return true;
  if (Array.isArray(d.relations)) return true;
  if (d.entity_relation_summary && typeof d.entity_relation_summary === 'object') return true;
  return false;
}

function isEntityMergePanel(result: NodeResultLike): boolean {
  const d = asRecord(result.data);
  if (Array.isArray(d.merged_entities)) return true;
  if (d.entity_merge_summary && typeof d.entity_merge_summary === 'object') return true;
  return false;
}

function isRelationMergePanel(result: NodeResultLike): boolean {
  const d = asRecord(result.data);
  if (Array.isArray(d.merged_relations)) return true;
  if (d.relation_merge_summary && typeof d.relation_merge_summary === 'object') return true;
  return false;
}

function isIndustrialPanel(id: string, result: NodeResultLike): boolean {
  const nodeType = inferNodeType(id, result);
  if (nodeType.startsWith('industrial.')) return true;
  const d = asRecord(result.data);
  if (d.composite_structure && typeof d.composite_structure === 'object') return true;
  if (d.industrial_graph && typeof d.industrial_graph === 'object') return true;
  return false;
}

function panelTypeForNode(
  id: string,
  result: NodeResultLike
): 'context_build' | 'llm_generate' | 'keyword_extract' | 'graph_retrieve' | 'graph_merge' | 'graph_persist' | 'multimodal_process' | 'chunk_split' | 'entity_relation_extract' | 'entity_merge' | 'relation_merge' | 'retrieval_merge' | 'rerank' | 'storage_persist' | 'industrial' | 'generic' {
  const nodeType = inferNodeType(id, result);
  if (nodeType === 'context.build') return 'context_build';
  if (nodeType === 'llm.generate') return 'llm_generate';
  if (nodeType === 'keyword.extract') return 'keyword_extract';
  if (nodeType === 'graph.retrieve') return 'graph_retrieve';
  if (nodeType === 'graph.merge') return 'graph_merge';
  if (nodeType === 'graph.persist') return 'graph_persist';
  if (nodeType === 'multimodal.process') return 'multimodal_process';
  if (nodeType === 'chunk.split') return 'chunk_split';
  if (nodeType === 'entity_relation.extract') return 'entity_relation_extract';
  if (nodeType === 'entity.merge') return 'entity_merge';
  if (nodeType === 'relation.merge') return 'relation_merge';
  if (nodeType === 'retrieval.merge') return 'retrieval_merge';
  if (nodeType === 'rerank') return 'rerank';
  if (nodeType === 'storage.persist') return 'storage_persist';
  if (nodeType.startsWith('industrial.')) return 'industrial';
  if (isContextBuildPanel(result)) return 'context_build';
  if (isLlmGeneratePanel(result)) return 'llm_generate';
  if (isKeywordExtractPanel(result)) return 'keyword_extract';
  if (isGraphRetrievePanel(result)) return 'graph_retrieve';
  if (isGraphMergePanel(result)) return 'graph_merge';
  if (isGraphPersistPanel(result)) return 'graph_persist';
  if (isMultimodalProcessPanel(result)) return 'multimodal_process';
  if (isChunkSplitPanel(result)) return 'chunk_split';
  if (isEntityRelationExtractPanel(result)) return 'entity_relation_extract';
  if (isEntityMergePanel(result)) return 'entity_merge';
  if (isRelationMergePanel(result)) return 'relation_merge';
  if (isRetrievalMergePanel(result)) return 'retrieval_merge';
  if (isRerankPanel(result)) return 'rerank';
  if (isStoragePersistPanel(result)) return 'storage_persist';
  if (isIndustrialPanel(id, result)) return 'industrial';
  return 'generic';
}

function prettyNodeBlocks(id: string, result: NodeResultLike): PrettyBlock[] {
  const data = asRecord(result.data);
  const nodeType = inferNodeType(id, result);

  // 优先按数据结构识别，避免 node_type 推断失败时退化成通用摘要
  if (nodeType === 'multimodal.process' || 'process_summary' in data || 'multimodal_descriptions' in data) {
    const ps = asRecord(data.process_summary);
    const descs = Array.isArray(data.multimodal_descriptions) ? data.multimodal_descriptions : [];
    const allDesc = descs
      .map(one => asRecord(one))
      .map((one, idx) => {
        const t = String(one.original_type ?? one.type ?? '').trim();
        const raw = String(one.text_description ?? '').replace(/\s+/g, ' ').trim();
        if (!raw) return '';
        return t ? `[${idx + 1}] (${t}) ${raw}` : `[${idx + 1}] ${raw}`;
      })
      .filter(Boolean);
    return [
      {
        title: '处理概览',
        lines: [
          `候选数: ${String(ps.candidate_count ?? '-')}`,
          `处理数: ${String(ps.processed_count ?? '-')}`,
          `VLM使用: ${String(ps.vlm_used_count ?? 0)} / fallback: ${String(ps.fallback_count ?? 0)}`,
          `类型分布: ${toDistributionLine(ps.type_distribution)}`
        ]
      },
      ...(allDesc.length
        ? [
            {
              title: `多模态描述（${allDesc.length} 条）`,
              lines: allDesc,
              scrollable: true
            }
          ]
        : [])
    ];
  }

  if (nodeType === 'document.parse' || 'parse_status' in data) {
    const list = Array.isArray(data.content_list) ? data.content_list : [];
    const typeCounter: Record<string, number> = {};
    for (const one of list) {
      const obj = asRecord(one);
      const t = String(obj.type ?? 'unknown').trim().toLowerCase() || 'unknown';
      typeCounter[t] = (typeCounter[t] ?? 0) + 1;
    }
    return [
      {
        title: '解析概览',
        lines: [
          `状态: ${String(data.parse_status ?? 'unknown')}`,
          `源文件: ${String(data.source_path ?? '-')}`,
          `内容块数量: ${list.length}`,
          `类型分布: ${toDistributionLine(typeCounter)}`
        ]
      }
    ];
  }

  if (nodeType === 'content.filter' || 'filter_summary' in data) {
    const fs = asRecord(data.filter_summary);
    return [
      {
        title: '过滤概览',
        lines: [
          `过滤前: ${String(fs.before_count ?? '-')}`,
          `过滤后: ${String(fs.after_count ?? '-')}`,
          `保留类型: ${toDistributionLine(fs.kept_types)}`,
          `删除类型: ${toDistributionLine(fs.dropped_types)}`
        ]
      }
    ];
  }

  if (nodeType === 'content.route' || 'route_summary' in data || 'routes' in data) {
    const rs = asRecord(data.route_summary);
    const routes = asRecord(data.routes);
    const routeLines = Object.entries(routes).map(([k, v]) => {
      const n = Array.isArray(v) ? v.length : 0;
      return `${k}: ${n}`;
    });
    return [
      {
        title: '路由概览',
        lines: [
          `总条目: ${String(rs.total_items ?? '-')}`,
          `已路由: ${String(rs.routed_items ?? '-')}`,
          `未路由: ${String(rs.unrouted_items ?? '-')}`,
          `分组分布: ${toDistributionLine(rs.group_distribution)}`
        ]
      },
      {
        title: '各路由数量',
        lines: routeLines.length ? routeLines : ['无']
      }
    ];
  }

  if (nodeType === 'embedding.index' || 'embedding_summary' in data || 'embedding_records' in data) {
    const es = asRecord(data.embedding_summary);
    const records = Array.isArray(data.embedding_records) ? data.embedding_records : [];
    return [
      {
        title: '向量化概览',
        lines: [
          `总记录: ${String(es.total_records ?? records.length)}`,
          `有向量: ${String(es.with_vector ?? '-')}`,
          `无向量: ${String(es.without_vector ?? '-')}`,
          `pipeline分布: ${toDistributionLine(es.pipeline_distribution)}`,
          `provider分布: ${toDistributionLine(es.provider_distribution)}`
        ]
      }
    ];
  }

  if (nodeType === 'knowledge.select' || 'selected_knowledge' in data) {
    const sk = asRecord(data.selected_knowledge);
    const vc = asRecord(sk.vector_collections);
    const pm = asRecord(sk.pipeline_collections);
    const mode = String(sk.collection_mode ?? 'unified');
    const pipeCount = Object.keys(pm).filter(k => String(pm[k] ?? '').trim()).length;
    const lines = [
      `display id: ${String(sk.display_id ?? sk.knowledge_id ?? '-')}`,
      `vector backend: ${String(sk.vector_backend ?? '-')}`,
      `graph backend: ${String(sk.graph_backend ?? '-')}`,
      `workspace: ${String(sk.graph_workspace ?? '-')}`,
      `collection mode: ${mode}`,
      mode === 'by_pipeline'
        ? `pipeline collections: ${pipeCount}`
        : `collection: ${String(sk.collection ?? vc.text_pipeline ?? '-')}`
    ];
    return [{ title: '已选择知识库', lines }];
  }

  if (
    nodeType === 'storage.persist' ||
    (typeof data.storage_summary === 'object' && data.storage_summary !== null) ||
    Array.isArray(data.storage_refs)
  ) {
    return [];
  }

  if (nodeType === 'relation.merge' || 'relation_merge_summary' in data || 'merged_relations' in data) {
    const rs = asRecord(data.relation_merge_summary ?? data.relation_merge);
    return [
      {
        title: '关系归并概览',
        lines: [
          `输入关系: ${String(rs.input_relations ?? '-')}`,
          `输出关系: ${String(rs.merged_relations ?? '-')}`,
          `归并组数: ${String(rs.merged_groups ?? 0)}`,
          `策略: ${String(rs.merge_strategy ?? '-')}`
        ]
      }
    ];
  }

  if (nodeType === 'graph.merge' || 'graph' in data || ('graph_summary' in data && !('graph_results' in data))) {
    const gs = asRecord(data.graph_summary);
    return [
      {
        title: '图级归并概览',
        lines: [
          `实体: ${String(gs.entity_count ?? '-')}`,
          `关系: ${String(gs.relation_count ?? '-')}`,
          `连通分量: ${String(gs.component_count ?? '-')}`,
          `孤立实体: ${String(gs.isolated_entity_count ?? '-')}`
        ]
      }
    ];
  }

  const keys = Object.keys(data);
  const lines = [
    `success: ${String(result.success ?? '-')}`,
    `data字段: ${keys.length ? keys.join(', ') : '无'}`
  ];
  return [{ title: '运行概览', lines }];
}

function nodeStateIcon(success: boolean | undefined): string {
  if (success === true) return 'mdi:check-circle';
  if (success === false) return 'mdi:close-circle';
  return 'mdi:help-circle-outline';
}

function nodeStateClass(success: boolean | undefined): string {
  if (success === true) return 'ok';
  if (success === false) return 'bad';
  return 'idle';
}

watch(
  [nodeResultList, () => props.preferredNodeId],
  () => {
    const list = nodeResultList.value;
    if (!list.length) {
      nodeOpen.value = [];
      return;
    }
    const preferred = props.preferredNodeId;
    const target = preferred && list.some(i => i.id === preferred) ? preferred : list[0].id;
    nodeOpen.value = [target];
  },
  { immediate: true }
);

watch(
  nodeResultList,
  list => {
    const keep = new Set(list.map(i => i.id));
    const next: Record<string, boolean> = {};
    for (const [k, v] of Object.entries(nodeRawView.value)) {
      if (keep.has(k)) next[k] = v;
    }
    nodeRawView.value = next;
  },
  { immediate: true }
);
</script>

<template>
  <ElCollapseItem v-if="mode === 'collapse'" title="运行结果" name="run">
    <div class="rag-wf-run-dock rag-wf-run-dock--nested">
      <div class="rag-wf-run-status-row">
        <span class="rag-wf-run-chip" :class="[`is-${statusTone}`]">{{ statusLabel }}</span>
      </div>
      <div v-if="runStatus === 'error' && runErrorMsg" class="rag-wf-run-error-card">
        {{ runErrorMsg }}
      </div>
      <div v-if="answerSnippet && lastRunRaw" class="rag-wf-run-answer-card">
        <div class="rag-wf-run-answer-cap">全局摘要</div>
        <div class="rag-wf-run-answer-body">{{ answerSnippet }}</div>
      </div>
      <ElCollapse v-if="nodeResultList.length" v-model="nodeOpen" class="rag-wf-run-node-collapse">
        <ElCollapseItem v-for="it in nodeResultList" :key="it.id" :name="it.id">
          <template #title>
            <div class="rag-wf-node-item-head">
              <span class="rag-wf-node-item-id" :title="nodeTitle(it.id)">{{ nodeDisplayTitle(it.id) }}</span>
              <span class="rag-wf-node-item-head-actions">
                <ElButton text class="rag-wf-node-toggle-btn" @click.stop="toggleNodeRaw(it.id)">
                  <Icon :icon="nodeViewIcon(it.id)" />
                </ElButton>
                <span class="rag-wf-node-item-state" :class="nodeStateClass(it.result.success)">
                  <Icon :icon="nodeStateIcon(it.result.success)" />
                </span>
              </span>
            </div>
          </template>
          <div class="rag-wf-node-item-body">
            <div v-if="it.result.error" class="rag-wf-run-error-card">{{ it.result.error }}</div>
            <template v-if="isNodeRaw(it.id)">
              <div class="rag-wf-node-item-block">
                <div class="rag-wf-run-answer-cap">data</div>
                <pre class="rag-wf-json-pre-mon">{{ formatJson(it.result.data) }}</pre>
              </div>
              <div class="rag-wf-node-item-block">
                <div class="rag-wf-run-answer-cap">metadata</div>
                <pre class="rag-wf-json-pre-mon">{{ formatJson(it.result.metadata) }}</pre>
              </div>
            </template>
            <template v-else>
              <WorkflowContextBuildRunPanel
                v-if="panelTypeForNode(it.id, it.result) === 'context_build'"
                :result="it.result"
              />
              <WorkflowRetrievalMergeRunPanel
                v-else-if="panelTypeForNode(it.id, it.result) === 'retrieval_merge'"
                :result="it.result"
              />
              <WorkflowLlmGenerateRunPanel
                v-else-if="panelTypeForNode(it.id, it.result) === 'llm_generate'"
                :result="it.result"
              />
              <WorkflowRerankRunPanel
                v-else-if="panelTypeForNode(it.id, it.result) === 'rerank'"
                :result="it.result"
              />
              <WorkflowKeywordExtractRunPanel
                v-else-if="panelTypeForNode(it.id, it.result) === 'keyword_extract'"
                :result="it.result"
              />
              <WorkflowGraphRetrieveRunPanel
                v-else-if="panelTypeForNode(it.id, it.result) === 'graph_retrieve'"
                :result="it.result"
              />
              <WorkflowGraphMergeRunPanel
                v-else-if="panelTypeForNode(it.id, it.result) === 'graph_merge'"
                :result="it.result"
              />
              <WorkflowGraphPersistRunPanel
                v-else-if="panelTypeForNode(it.id, it.result) === 'graph_persist'"
                :result="it.result"
              />
              <WorkflowMultimodalRunPanel
                v-else-if="panelTypeForNode(it.id, it.result) === 'multimodal_process'"
                :result="it.result"
              />
              <WorkflowChunkSplitRunPanel
                v-else-if="panelTypeForNode(it.id, it.result) === 'chunk_split'"
                :result="it.result"
              />
              <WorkflowEntityRelationExtractRunPanel
                v-else-if="panelTypeForNode(it.id, it.result) === 'entity_relation_extract'"
                :result="it.result"
              />
              <WorkflowEntityMergeRunPanel
                v-else-if="panelTypeForNode(it.id, it.result) === 'entity_merge'"
                :result="it.result"
              />
              <WorkflowRelationMergeRunPanel
                v-else-if="panelTypeForNode(it.id, it.result) === 'relation_merge'"
                :result="it.result"
              />
              <WorkflowStoragePersistRunPanel
                v-else-if="panelTypeForNode(it.id, it.result) === 'storage_persist'"
                :result="it.result"
              />
              <WorkflowIndustrialRunPanel
                v-else-if="panelTypeForNode(it.id, it.result) === 'industrial'"
                :result="it.result"
              />
              <template v-else>
                <div v-for="blk in prettyNodeBlocks(it.id, it.result)" :key="`${it.id}-${blk.title}`" class="rag-wf-node-item-block">
                  <div class="rag-wf-run-answer-cap">{{ blk.title }}</div>
                  <div class="rag-wf-node-pretty-lines" :class="{ 'is-scrollable': isScrollablePrettyBlock(blk) }">
                    <div v-for="(line, idx) in blk.lines" :key="idx" class="rag-wf-node-pretty-line">{{ line }}</div>
                  </div>
                </div>
              </template>
            </template>
          </div>
        </ElCollapseItem>
      </ElCollapse>
      <ElCollapse v-if="activeNodeRawJson" v-model="rawJsonOpen" class="rag-wf-run-json-collapse">
        <ElCollapseItem name="full">
          <template #title>
            <div class="rag-wf-json-head">
              <span>当前节点 JSON</span>
              <ElSwitch
                v-model="compactJsonView"
                active-text="简洁"
                inactive-text="完整"
                inline-prompt
                size="small"
                @click.stop
              />
            </div>
          </template>
          <ElScrollbar max-height="200px">
            <pre class="rag-wf-json-pre-mon">{{ activeNodeRawJson }}</pre>
          </ElScrollbar>
        </ElCollapseItem>
      </ElCollapse>
      <ElEmpty v-if="!lastRunRaw && runStatus !== 'error'" description="尚未运行" :image-size="56" />
    </div>
  </ElCollapseItem>

  <div v-else class="rag-wf-run-dock">
    <div class="rag-wf-run-status-row">
      <span class="rag-wf-run-chip" :class="[`is-${statusTone}`]">{{ statusLabel }}</span>
    </div>

    <div v-if="runStatus === 'error' && runErrorMsg" class="rag-wf-run-error-card">
      {{ runErrorMsg }}
    </div>

    <div v-if="answerSnippet && lastRunRaw" class="rag-wf-run-answer-card">
      <div class="rag-wf-run-answer-cap">全局摘要</div>
      <div class="rag-wf-run-answer-body">{{ answerSnippet }}</div>
    </div>

    <ElCollapse v-if="nodeResultList.length" v-model="nodeOpen" class="rag-wf-run-node-collapse">
      <ElCollapseItem v-for="it in nodeResultList" :key="it.id" :name="it.id">
        <template #title>
          <div class="rag-wf-node-item-head">
            <span class="rag-wf-node-item-id" :title="nodeTitle(it.id)">{{ nodeDisplayTitle(it.id) }}</span>
            <span class="rag-wf-node-item-head-actions">
              <ElButton text class="rag-wf-node-toggle-btn" @click.stop="toggleNodeRaw(it.id)">
                <Icon :icon="nodeViewIcon(it.id)" />
              </ElButton>
              <span class="rag-wf-node-item-state" :class="nodeStateClass(it.result.success)">
                <Icon :icon="nodeStateIcon(it.result.success)" />
              </span>
            </span>
          </div>
        </template>
        <div class="rag-wf-node-item-body">
          <div v-if="it.result.error" class="rag-wf-run-error-card">{{ it.result.error }}</div>
          <template v-if="isNodeRaw(it.id)">
            <div class="rag-wf-node-item-block">
              <div class="rag-wf-run-answer-cap">data</div>
              <pre class="rag-wf-json-pre-mon">{{ formatJson(it.result.data) }}</pre>
            </div>
            <div class="rag-wf-node-item-block">
              <div class="rag-wf-run-answer-cap">metadata</div>
              <pre class="rag-wf-json-pre-mon">{{ formatJson(it.result.metadata) }}</pre>
            </div>
          </template>
          <template v-else>
            <WorkflowContextBuildRunPanel
              v-if="panelTypeForNode(it.id, it.result) === 'context_build'"
              :result="it.result"
            />
            <WorkflowRetrievalMergeRunPanel
              v-else-if="panelTypeForNode(it.id, it.result) === 'retrieval_merge'"
              :result="it.result"
            />
            <WorkflowLlmGenerateRunPanel
              v-else-if="panelTypeForNode(it.id, it.result) === 'llm_generate'"
              :result="it.result"
            />
            <WorkflowRerankRunPanel
              v-else-if="panelTypeForNode(it.id, it.result) === 'rerank'"
              :result="it.result"
            />
            <WorkflowKeywordExtractRunPanel
              v-else-if="panelTypeForNode(it.id, it.result) === 'keyword_extract'"
              :result="it.result"
            />
            <WorkflowGraphRetrieveRunPanel
              v-else-if="panelTypeForNode(it.id, it.result) === 'graph_retrieve'"
              :result="it.result"
            />
            <WorkflowGraphMergeRunPanel
              v-else-if="panelTypeForNode(it.id, it.result) === 'graph_merge'"
              :result="it.result"
            />
            <WorkflowGraphPersistRunPanel
              v-else-if="panelTypeForNode(it.id, it.result) === 'graph_persist'"
              :result="it.result"
            />
            <WorkflowMultimodalRunPanel
              v-else-if="panelTypeForNode(it.id, it.result) === 'multimodal_process'"
              :result="it.result"
            />
            <WorkflowChunkSplitRunPanel
              v-else-if="panelTypeForNode(it.id, it.result) === 'chunk_split'"
              :result="it.result"
            />
            <WorkflowEntityRelationExtractRunPanel
              v-else-if="panelTypeForNode(it.id, it.result) === 'entity_relation_extract'"
              :result="it.result"
            />
            <WorkflowEntityMergeRunPanel
              v-else-if="panelTypeForNode(it.id, it.result) === 'entity_merge'"
              :result="it.result"
            />
            <WorkflowRelationMergeRunPanel
              v-else-if="panelTypeForNode(it.id, it.result) === 'relation_merge'"
              :result="it.result"
            />
            <WorkflowStoragePersistRunPanel
              v-else-if="panelTypeForNode(it.id, it.result) === 'storage_persist'"
              :result="it.result"
            />
            <WorkflowIndustrialRunPanel
              v-else-if="panelTypeForNode(it.id, it.result) === 'industrial'"
              :result="it.result"
            />
            <template v-else>
              <div v-for="blk in prettyNodeBlocks(it.id, it.result)" :key="`${it.id}-${blk.title}`" class="rag-wf-node-item-block">
                <div class="rag-wf-run-answer-cap">{{ blk.title }}</div>
                <div class="rag-wf-node-pretty-lines" :class="{ 'is-scrollable': isScrollablePrettyBlock(blk) }">
                  <div v-for="(line, idx) in blk.lines" :key="idx" class="rag-wf-node-pretty-line">{{ line }}</div>
                </div>
              </div>
            </template>
          </template>
        </div>
      </ElCollapseItem>
    </ElCollapse>

    <ElCollapse v-if="activeNodeRawJson" v-model="rawJsonOpen" class="rag-wf-run-json-collapse">
      <ElCollapseItem name="full">
        <template #title>
          <div class="rag-wf-json-head">
            <span>当前节点 JSON</span>
            <ElSwitch
              v-model="compactJsonView"
              active-text="简洁"
              inactive-text="完整"
              inline-prompt
              size="small"
              @click.stop
            />
          </div>
        </template>
        <ElScrollbar max-height="220px">
          <pre class="rag-wf-json-pre-mon">{{ activeNodeRawJson }}</pre>
        </ElScrollbar>
      </ElCollapseItem>
    </ElCollapse>
    <ElEmpty v-if="!lastRunRaw && runStatus !== 'error'" description="运行后将在此展示摘要与详情" :image-size="72" />
  </div>
</template>

<style scoped lang="scss">
.rag-wf-run-status-row {
  margin-bottom: 14px;
}

.rag-wf-run-chip {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}

.rag-wf-run-chip.is-idle {
  color: #6b7280;
  background: #f3f4f6;
  border: 1px solid #e5e7eb;
}

.rag-wf-run-chip.is-running {
  color: #1d4ed8;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
}

.rag-wf-run-chip.is-success {
  color: #15803d;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
}

.rag-wf-run-chip.is-error {
  color: #b91c1c;
  background: #fef2f2;
  border: 1px solid #fecaca;
}

.rag-wf-run-error-card {
  margin-bottom: 14px;
  padding: 10px 12px;
  font-size: 12px;
  line-height: 1.45;
  color: #b91c1c;
  background: #fff5f5;
  border: 1px solid #fecaca;
  border-radius: 10px;
  word-break: break-word;
}

.rag-wf-run-answer-card {
  margin-bottom: 14px;
  padding: 12px;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  background: linear-gradient(to bottom right, #fff, #fafbfc);
  box-shadow: 0 1px 8px rgb(15 23 42 / 4%);
}

.rag-wf-run-answer-cap {
  font-size: 11px;
  font-weight: 600;
  color: #9ca3af;
  letter-spacing: 0.03em;
  margin-bottom: 8px;
  text-transform: uppercase;
}

.rag-wf-run-answer-body {
  font-size: 13px;
  line-height: 1.55;
  color: #374151;
  white-space: pre-wrap;
  word-break: break-word;
}

.rag-wf-json-pre-mon {
  margin: 0;
  font-size: 11px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: Menlo, Monaco, Consolas, 'Courier New', monospace;
}

.rag-wf-run-json-collapse {
  margin-top: 4px;
  border: none;
}

.rag-wf-json-head {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding-right: 6px;
}

.rag-wf-run-node-collapse {
  margin-bottom: 12px;
}

.rag-wf-node-item-head {
  width: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  column-gap: 8px;
  padding-right: 6px;
}

.rag-wf-node-item-id {
  display: block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.35;
  font-size: 12px;
  font-weight: 600;
  color: #334155;
  font-family: ui-monospace, Menlo, Monaco, Consolas, monospace;
}

.rag-wf-node-item-state {
  width: 18px;
  height: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: #94a3b8;
  background: transparent;
  font-size: 17px;
}

.rag-wf-node-item-head-actions {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  justify-self: end;
  flex-shrink: 0;
}

.rag-wf-node-toggle-btn {
  color: var(--el-color-primary);
  padding: 2px 4px;
  min-height: 22px;
}

.rag-wf-node-toggle-btn :deep(svg) {
  font-size: 16px;
}

.rag-wf-node-item-state.ok {
  color: #15803d;
}

.rag-wf-node-item-state.bad {
  color: #b91c1c;
}

.rag-wf-node-item-state.idle {
  color: #94a3b8;
}

.rag-wf-node-item-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.rag-wf-run-node-collapse :deep(.el-collapse-item__header) {
  min-height: 44px;
  height: auto;
  align-items: center;
}

.rag-wf-node-item-block {
  padding: 10px;
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  background: #fff;
}

.rag-wf-node-pretty-lines {
  display: flex;
  flex-direction: column;
  gap: 4px;

  &.is-scrollable {
    max-height: 320px;
    overflow-y: auto;
    padding-right: 4px;
  }
}

.rag-wf-node-pretty-line {
  font-size: 12px;
  line-height: 1.5;
  color: #334155;
  white-space: pre-wrap;
  word-break: break-word;
}

.rag-wf-run-json-collapse :deep(.el-collapse-item__header) {
  height: auto;
  min-height: 40px;
  font-size: 13px;
  padding: 0 4px;
  background: transparent;
}

.rag-wf-run-json-collapse :deep(.el-collapse-item__wrap) {
  border: none;
}

.rag-wf-run-json-collapse :deep(.el-collapse-item__content) {
  padding: 8px 0 0;
}

.rag-wf-run-dock--nested .rag-wf-run-status-row {
  margin-bottom: 10px;
}
</style>
