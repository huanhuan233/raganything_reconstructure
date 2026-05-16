<script setup lang="ts">
import { Icon } from '@iconify/vue';
import { computed } from 'vue';
import { Handle, Position } from '@vue-flow/core';
import type { RagFlowNodeData, RagNodeImplementationStatus } from '@/types/ragWorkflow';
import { resolveIsrVisualDomain } from '@/components/runtime/isrPalette';
import { requestDeleteWorkflowNode } from '../workflowNodeDeleteBus';
import { requestWorkflowPalette } from '../workflowPaletteBus';
import { summarizeNodeConfig } from '../utils/nodeConfigSummary';

const props = defineProps<{
  id: string;
  data: RagFlowNodeData;
}>();

const summaryLine = computed(() => summarizeNodeConfig(props.data));
const isrDomain = computed(() => resolveIsrVisualDomain(String(props.data.nodeType || '')));

const isrCardClasses = computed(() =>
  isrDomain.value ? ['rag-wf-node-card--isr', `rag-wf-node-card--isr-${isrDomain.value}`] : []
);

const semanticMetaBlocks = computed(() => {
  const d = props.data;
  const blocks: Array<{ label: string; items: string[] }> = [];
  const si = Array.isArray(d.semanticInputs) ? d.semanticInputs : [];
  const so = Array.isArray(d.semanticOutputs) ? d.semanticOutputs : [];
  const cd = Array.isArray(d.constraintDependencies) ? d.constraintDependencies : [];
  const rd = Array.isArray(d.runtimeStateDependencies) ? d.runtimeStateDependencies : [];
  const ot = Array.isArray(d.ontologyTypes) ? d.ontologyTypes : [];
  if (si.length) blocks.push({ label: '语义入', items: si });
  if (so.length) blocks.push({ label: '语义出', items: so });
  if (cd.length) blocks.push({ label: '约束依赖', items: cd });
  if (rd.length) blocks.push({ label: '状态依赖', items: rd });
  if (ot.length) blocks.push({ label: '本体类型', items: ot });
  return blocks;
});

const implStatus = computed<RagNodeImplementationStatus>(() => {
  return props.data.implementationStatus ?? (props.data.isPlaceholder ? 'placeholder' : 'real');
});
const isWorkflowStart = computed(() => String(props.data.nodeType || '') === 'workflow.start');
const isWorkflowEnd = computed(() => String(props.data.nodeType || '') === 'workflow.end');

function openPaletteAnchored(el: HTMLElement) {
  const r = el.getBoundingClientRect();
  requestWorkflowPalette({
    paletteSource: 'handle',
    sourceNodeId: props.id,
    anchorClientX: r.left + r.width / 2,
    anchorClientY: r.top + r.height / 2
  });
}

/** 必须挂在 Handle 的子节点上：Vue Flow 的 Handle 根节点不写 mergeAttrs，外层 @click 不会生效 */
function onHandlePlusClick(e: MouseEvent) {
  openPaletteAnchored(e.currentTarget as HTMLElement);
}

function onHandlePlusClickFromKeyboard(e: KeyboardEvent) {
  openPaletteAnchored(e.currentTarget as HTMLElement);
}

function onDeleteClick(e: MouseEvent) {
  e.preventDefault();
  e.stopPropagation();
  requestDeleteWorkflowNode(props.id);
}
</script>

<template>
  <div
    class="rag-wf-node-card"
    :class="[
      {
        'is-workflow-start': isWorkflowStart,
        'is-workflow-end': isWorkflowEnd
      },
      ...isrCardClasses
    ]"
  >
    <Handle id="rag-in" class="rag-wf-node-handle rag-wf-node-handle-target" type="target" :position="Position.Left" />
    <button
      type="button"
      class="rag-wf-node-del nodrag nopan"
      aria-label="删除节点"
      title="删除节点"
      @click="onDeleteClick"
    >
      <Icon icon="mdi:close" class="rag-wf-node-del-ico" aria-hidden="true" />
    </button>
    <div class="rag-wf-node-main">
      <div class="rag-wf-node-title">{{ data.label || data.nodeType }}</div>
      <div class="rag-wf-node-type" :title="data.nodeType">{{ data.nodeType }}</div>
      <div v-if="summaryLine" class="rag-wf-node-sum" :title="summaryLine">{{ summaryLine }}</div>
      <div v-if="semanticMetaBlocks.length" class="rag-wf-node-sem">
        <template v-for="block in semanticMetaBlocks" :key="block.label">
          <div class="rag-wf-node-sem-head">{{ block.label }}</div>
          <div class="rag-wf-node-sem-tags">
            <span v-for="(tag, ix) in block.items.slice(0, 8)" :key="`${block.label}-${ix}`" class="rag-wf-node-sem-tag">{{
              tag
            }}</span>
            <span v-if="block.items.length > 8" class="rag-wf-node-sem-more">+{{ block.items.length - 8 }}</span>
          </div>
        </template>
      </div>
      <div class="rag-wf-node-footer">
        <span v-if="implStatus === 'placeholder'" class="rag-wf-node-badge rag-wf-node-badge--placeholder">占位</span>
        <span v-else-if="implStatus === 'partial'" class="rag-wf-node-badge rag-wf-node-badge--partial">半实现</span>
        <span v-else class="rag-wf-node-badge rag-wf-node-badge--runnable">可运行</span>
      </div>
    </div>
    <!-- 出口仅需一个圆形「+」：兼 Vue Flow 连接桩；点击打开节点库，拖拽仍可连线 -->
    <Handle
      id="rag-out"
      class="rag-wf-node-handle rag-wf-node-handle-source rag-wf-node-source-plus nodrag nopan"
      type="source"
      :position="Position.Right"
      aria-label="添加或连接下游节点"
      title="点击添加节点 · 拖拽连接到下一节点"
    >
      <!-- mousedown/touchstart 仍可冒泡到 Handle 外层以拖拽连线；click 止于内层打开节点库 -->
      <span
        class="rag-wf-source-plus-face nodrag nopan"
        role="button"
        tabindex="0"
        @click.stop="onHandlePlusClick"
        @keydown.enter.prevent="onHandlePlusClickFromKeyboard"
        @keydown.space.prevent="onHandlePlusClickFromKeyboard"
      >
        +
      </span>
    </Handle>
  </div>
</template>

<style scoped lang="scss">
.rag-wf-node-card {
  width: 210px;
  min-height: 88px;
  box-sizing: border-box;
  position: relative;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  background: #fff;
  box-shadow:
    0 1px 3px rgb(15 23 42 / 3%),
    0 1px 2px rgb(15 23 42 / 2%);
  transition:
    border-color 0.14s ease,
    box-shadow 0.14s ease;
}

.rag-wf-node-card:hover {
  box-shadow:
    0 3px 8px rgb(15 23 42 / 5%),
    0 1px 2px rgb(15 23 42 / 4%);
}

.rag-wf-node-card.is-workflow-start {
  border-color: #34d399;
  border-radius: 16px;
  background: #f0fdf4;
}

.rag-wf-node-card.is-workflow-end {
  border-color: #475569;
  border-radius: 16px;
  background: #f8fafc;
}

.rag-wf-node-del {
  position: absolute;
  top: 6px;
  right: 6px;
  z-index: 3;
  width: 22px;
  height: 22px;
  padding: 0;
  margin: 0;
  border: none;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #94a3b8;
  background: rgb(255 255 255 / 92%);
  box-shadow: 0 0 0 1px rgb(226 232 240 / 90%);
  transition:
    color 0.14s ease,
    background 0.14s ease,
    box-shadow 0.14s ease;

  &:hover {
    color: #dc2626;
    background: #fef2f2;
    box-shadow: 0 0 0 1px #fecaca;
  }
}

.rag-wf-node-del-ico {
  width: 14px;
  height: 14px;
}

.rag-wf-node-main {
  padding: 10px 32px 12px 26px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 88px;
  box-sizing: border-box;
}

.rag-wf-node-title {
  font-weight: 600;
  font-size: 13px;
  color: #0f172a;
  line-height: 1.35;
  word-break: break-word;
}

.rag-wf-node-type {
  margin-top: 4px;
  font-size: 11px;
  color: #94a3b8;
  font-family: ui-monospace, Menlo, Monaco, Consolas, monospace;
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rag-wf-node-sum {
  margin-top: 6px;
  font-size: 11px;
  color: #64748b;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  line-clamp: 2;
  -webkit-line-clamp: 2;
  overflow: hidden;
  word-break: break-word;
  flex: 1;
}

.rag-wf-node-sem {
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px dashed #e2e8f0;
  font-size: 10px;
}

.rag-wf-node-sem-head {
  margin: 6px 0 2px;
  font-weight: 700;
  color: #475569;
  letter-spacing: 0.03em;

  &:first-child {
    margin-top: 0;
  }
}

.rag-wf-node-sem-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.rag-wf-node-sem-tag {
  padding: 1px 5px;
  border-radius: 4px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #334155;
  font-variant-numeric: tabular-nums;
}

.rag-wf-node-sem-more {
  color: #94a3b8;
  align-self: center;
}

.rag-wf-node-card--isr {
  border-width: 1.5px;
}

.rag-wf-node-card--isr-ontology {
  border-color: #1e3a8a;
  background: linear-gradient(165deg, rgb(30 58 138 / 5%), #fff);
}

.rag-wf-node-card--isr-constraint {
  border-color: #b91c1c;
  background: linear-gradient(165deg, rgb(185 28 28 / 5%), #fff);
}

.rag-wf-node-card--isr-semantic {
  border-color: #7c3aed;
  background: linear-gradient(165deg, rgb(124 58 237 / 5%), #fff);
}

.rag-wf-node-card--isr-state {
  border-color: #ea580c;
  background: linear-gradient(165deg, rgb(234 88 12 / 5%), #fff);
}

.rag-wf-node-card--isr-graph {
  border-color: #0e7490;
  background: linear-gradient(165deg, rgb(14 116 144 / 5%), #fff);
}

.rag-wf-node-card--isr-runtime {
  border-color: #334155;
  background: linear-gradient(165deg, rgb(51 65 85 / 6%), #fff);
}

.rag-wf-node-footer {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid #f1f5f9;
}

.rag-wf-node-badge {
  display: inline-block;
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 6px;
  line-height: 1.25;
}

.rag-wf-node-badge--placeholder {
  color: #c2410c;
  background: #fffbeb;
  border: 1px solid #fcd34d;
}

.rag-wf-node-badge--runnable {
  color: #15803d;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
}

.rag-wf-node-badge--partial {
  color: #1d4ed8;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
}

/* 左侧入口：小方桩 */
.rag-wf-node-handle:not(.rag-wf-node-source-plus) {
  width: 10px !important;
  height: 10px !important;
  border: 2px solid #94a3b8 !important;
  background: #fff !important;
}

.rag-wf-node-handle-target {
  left: -6px !important;
}

/* 右侧出口：仅此一颗正圆「+」（与 vue-flow「右桩」同源 transform: translate(50%, -50%)） */
.rag-wf-node-source-plus {
  width: 24px !important;
  height: 24px !important;
  min-width: 24px !important;
  min-height: 24px !important;
  aspect-ratio: 1 / 1 !important;
  box-sizing: border-box !important;
  padding: 0 !important;
  border: none !important;
  border-radius: 50% !important;
  background: var(--el-color-primary) !important;
  /* 在半宽外再接 half 半径，视觉上圆心落在卡片右边缘 */
  right: -12px !important;
  transform: translate(50%, -50%) !important;
  box-shadow:
    0 1px 2px rgb(0 0 0 / 8%),
    0 3px 12px rgb(15 23 42 / 12%);
  cursor: crosshair;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  transition:
    transform 0.16s ease,
    background-color 0.16s ease,
    box-shadow 0.16s ease;

  &:hover {
    transform: translate(50%, -50%) scale(1.06) !important;
    background: var(--el-color-primary-dark-2, var(--el-color-primary)) !important;
    box-shadow:
      0 3px 10px rgb(0 0 0 / 12%),
      0 8px 22px rgb(15 23 42 / 16%);
  }
}

.rag-wf-source-plus-face {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  min-width: 100%;
  min-height: 100%;
  margin: 0;
  padding: 0;
  color: var(--el-color-white, #fff);
  font-size: 17px;
  font-weight: 700;
  line-height: 1;
  outline: none;
  user-select: none;
}
</style>
