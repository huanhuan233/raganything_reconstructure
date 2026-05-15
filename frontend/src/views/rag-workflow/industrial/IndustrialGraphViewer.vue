<script setup lang="ts">
import { computed } from 'vue';

type GraphNode = {
  id?: unknown;
  label?: unknown;
  labels?: unknown;
  properties?: unknown;
};
type GraphEdge = {
  source?: unknown;
  target?: unknown;
  from?: unknown;
  to?: unknown;
  type?: unknown;
};

const props = defineProps<{
  graph: Record<string, unknown>;
}>();

const nodes = computed<GraphNode[]>(() => {
  const raw = props.graph.nodes;
  return Array.isArray(raw) ? (raw as GraphNode[]) : [];
});

const edges = computed<GraphEdge[]>(() => {
  const raw = props.graph.edges;
  return Array.isArray(raw) ? (raw as GraphEdge[]) : [];
});

const labelColor: Record<string, string> = {
  Document: '#1d4ed8',
  Section: '#0f766e',
  ProcessStep: '#7c3aed',
  Constraint: '#b91c1c'
};

function nodeLabel(n: GraphNode): string {
  const direct = String(n.label ?? '').trim();
  if (direct) return direct;
  const labels = n.labels;
  if (Array.isArray(labels) && labels.length) return String(labels[0] ?? '').trim() || 'Unknown';
  return 'Unknown';
}

function nodeId(n: GraphNode): string {
  return String(n.id ?? '').trim();
}

function nodeColor(n: GraphNode): string {
  const label = nodeLabel(n);
  return labelColor[label] ?? '#475569';
}

function edgeText(e: GraphEdge): string {
  const source = String(e.source ?? e.from ?? '').trim();
  const target = String(e.target ?? e.to ?? '').trim();
  const type = String(e.type ?? '').trim() || 'RELATED_TO';
  return `${source} -[${type}]-> ${target}`;
}
</script>

<template>
  <div class="igv-wrap">
    <div class="igv-meta">Nodes: {{ nodes.length }} · Edges: {{ edges.length }}</div>
    <div v-if="!nodes.length" class="igv-empty">暂无工业图谱节点</div>
    <div v-else class="igv-nodes">
      <div v-for="n in nodes" :key="nodeId(n)" class="igv-node">
        <span class="igv-dot" :style="{ backgroundColor: nodeColor(n) }"></span>
        <span class="igv-id">{{ nodeId(n) }}</span>
        <span class="igv-label">{{ nodeLabel(n) }}</span>
      </div>
    </div>
    <div v-if="edges.length" class="igv-edges">
      <div class="igv-subtitle">Relationships</div>
      <div v-for="(e, idx) in edges" :key="idx" class="igv-edge">{{ edgeText(e) }}</div>
    </div>
  </div>
</template>

<style scoped>
.igv-wrap {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 10px;
}

.igv-meta {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 8px;
}

.igv-empty {
  font-size: 12px;
  color: #94a3b8;
}

.igv-nodes {
  display: grid;
  gap: 6px;
}

.igv-node {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border: 1px solid #f1f5f9;
  border-radius: 8px;
  font-size: 12px;
}

.igv-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.igv-id {
  font-family: ui-monospace, Menlo, Monaco, Consolas, 'Courier New', monospace;
  color: #334155;
}

.igv-label {
  color: #64748b;
}

.igv-edges {
  margin-top: 10px;
  border-top: 1px dashed #e2e8f0;
  padding-top: 8px;
}

.igv-subtitle {
  font-size: 12px;
  color: #475569;
  font-weight: 600;
  margin-bottom: 6px;
}

.igv-edge {
  font-size: 12px;
  color: #334155;
  line-height: 1.4;
}
</style>

