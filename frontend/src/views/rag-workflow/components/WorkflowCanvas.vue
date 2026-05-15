<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue';
import type {
  Connection,
  DefaultEdgeOptions,
  Edge,
  EdgeTypesObject,
  Node,
  NodeTypesObject,
  ViewportTransform,
  VueFlowStore
} from '@vue-flow/core';
import { VueFlow } from '@vue-flow/core';
import '@vue-flow/core/dist/style.css';
import { setWorkflowNodeDeleteHandler } from '../workflowNodeDeleteBus';
import { setWorkflowPaletteHandler, type WorkflowPaletteOpenRequest } from '../workflowPaletteBus';
import RagWfFlowNode from './RagWfFlowNode.vue';
import RagWfInsertBezierEdge from './RagWfInsertBezierEdge.vue';

const props = withDefaults(defineProps<{ interactionMode?: 'pan' | 'select' }>(), {
  interactionMode: 'pan'
});

const nodes = defineModel<Node[]>('nodes', { required: true });
const edges = defineModel<Edge[]>('edges', { required: true });

const emit = defineEmits<{
  init: [store: VueFlowStore];
  viewportChange: [vp: ViewportTransform];
  nodeClick: [node: Node];
  paneClick: [];
  connect: [c: Connection];
  structureChange: [];
  workflowPaletteRequest: [payload: WorkflowPaletteOpenRequest];
  nodeDeleteRequest: [nodeId: string];
}>();

onMounted(() => {
  setWorkflowPaletteHandler(p => emit('workflowPaletteRequest', p));
  setWorkflowNodeDeleteHandler(id => emit('nodeDeleteRequest', id));
});

onBeforeUnmount(() => {
  setWorkflowPaletteHandler(null);
  setWorkflowNodeDeleteHandler(null);
});

const nodeTypes = Object.freeze({
  ragWf: RagWfFlowNode
}) as unknown as NodeTypesObject;

const edgeTypes = Object.freeze({
  ragWfInsert: RagWfInsertBezierEdge
}) as unknown as EdgeTypesObject;

const defaultEdgeOptions: DefaultEdgeOptions = {
  type: 'ragWfInsert',
  class: 'rag-wf-insert-bezier',
  selectable: true,
  deletable: true
};

/** 拖拽：画布平移；选择：拖拽框选 */
const panOnDrag = computed(() => props.interactionMode === 'pan');
const selectionOnDrag = computed(() => props.interactionMode === 'select');

function onInit(store: VueFlowStore) {
  emit('init', store);
}

function onViewportChange(vp: ViewportTransform) {
  emit('viewportChange', vp);
}
</script>

<template>
  <div class="rag-wf-flow-outer">
    <VueFlow
      v-model:nodes="nodes"
      v-model:edges="edges"
      class="rag-wf-vue-flow"
      :node-types="nodeTypes"
      :edge-types="edgeTypes"
      :default-edge-options="defaultEdgeOptions"
      :default-zoom="1"
      :min-zoom="0.35"
      :max-zoom="1.95"
      :nodes-draggable="true"
      :nodes-connectable="true"
      :elements-selectable="true"
      :delete-key-code="true"
      :pan-on-drag="panOnDrag"
      :selection-on-drag="selectionOnDrag"
      snap-to-grid
      :snap-grid="[14, 14]"
      :default-viewport="{ x: 32, y: 40, zoom: 1 }"
      @init="onInit"
      @viewport-change="onViewportChange"
      @node-click="(e: any) => emit('nodeClick', e.node as Node)"
      @pane-click="emit('paneClick')"
      @connect="c => emit('connect', c)"
      @nodes-change="emit('structureChange')"
      @edges-change="emit('structureChange')"
    >
    </VueFlow>
    <div v-if="!nodes.length" class="rag-wf-empty-hint">
      从左栏添加节点 · 连线中点「+」插入节点 · 节点出口旁「+」追加 · 拖拽端口连线 · Esc 清空选择
    </div>
  </div>
</template>

<style scoped lang="scss">
.rag-wf-flow-outer {
  position: absolute;
  inset: 0;
  box-sizing: border-box;
  background-color: #f7f9fc;
  background-image: radial-gradient(#d8dee9 1px, transparent 1px);
  background-size: 18px 18px;
}

.rag-wf-vue-flow {
  width: 100%;
  height: 100%;
  background: transparent;
}

.rag-wf-empty-hint {
  position: absolute;
  left: 50%;
  top: 44%;
  transform: translate(-50%, -50%);
  font-size: 13px;
  color: #94a3b8;
  pointer-events: none;
  z-index: 2;
  text-align: center;
  max-width: 360px;
  line-height: 1.55;
  letter-spacing: 0.01em;
}

.rag-wf-flow-outer :deep(.vue-flow) {
  width: 100%;
  height: 100%;
}

.rag-wf-flow-outer :deep(.vue-flow__node.selected .rag-wf-node-card) {
  border-color: #4f46e5;
  box-shadow:
    0 1px 2px rgb(79 70 229 / 6%),
    0 6px 20px rgb(79 70 229 / 12%);
}

.rag-wf-flow-outer :deep(.vue-flow__connectionline path) {
  stroke: var(--el-color-primary, #6366f1);
  stroke-width: 2px;
}

/* 自定义边由内联 stroke 控制；默认边沿用灰/主色选中 */
.rag-wf-flow-outer :deep(.vue-flow__edge:not(.rag-wf-insert-bezier) .vue-flow__edge-path) {
  stroke: #94a3b8;
}

.rag-wf-flow-outer :deep(.vue-flow__edge:not(.rag-wf-insert-bezier).selected .vue-flow__edge-path) {
  stroke: var(--el-color-primary, #4f46e5);
}
</style>
