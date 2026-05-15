<script setup lang="ts">
import { computed, ref } from 'vue';
import { BaseEdge, EdgeLabelRenderer, getBezierPath } from '@vue-flow/core';
import type { Position } from '@vue-flow/core';
import { requestWorkflowPalette } from '../workflowPaletteBus';

defineOptions({
  // 该边组件为多根节点（路径 + Teleport 标签），禁止自动 attribute 继承可避免 Vue 警告噪音。
  inheritAttrs: false
});

const props = withDefaults(
  defineProps<{
    id: string;
    source: string;
    target: string;
    sourceX: number;
    sourceY: number;
    targetX: number;
    targetY: number;
    sourcePosition: Position;
    targetPosition: Position;
    markerEnd?: string;
    selected?: boolean;
  }>(),
  { selected: false, markerEnd: undefined }
);

const hitPath = ref(false);
const hitPlus = ref(false);
const hovered = computed(() => hitPath.value || hitPlus.value);

const bezier = computed(() =>
  getBezierPath({
    sourceX: props.sourceX,
    sourceY: props.sourceY,
    sourcePosition: props.sourcePosition,
    targetX: props.targetX,
    targetY: props.targetY,
    targetPosition: props.targetPosition
  })
);

const pathD = computed(() => bezier.value[0]);
const labelX = computed(() => bezier.value[1]);
const labelY = computed(() => bezier.value[2]);

const edgeStroke = computed(() => {
  if (props.selected) {
    return { stroke: 'var(--el-color-primary)', strokeOpacity: 1 };
  }
  if (hovered.value) {
    return { stroke: 'var(--el-color-primary)', strokeOpacity: 0.85 };
  }
  return { stroke: 'var(--el-color-primary)', strokeOpacity: 0.42 };
});

function onPlusClick(e: MouseEvent) {
  e.preventDefault();
  e.stopPropagation();
  const btn = e.currentTarget as HTMLElement;
  const r = btn.getBoundingClientRect();
  requestWorkflowPalette({
    paletteSource: 'edge',
    edgeId: props.id,
    source: props.source,
    target: props.target,
    flowMidX: labelX.value,
    flowMidY: labelY.value,
    anchorClientX: r.left + r.width / 2,
    anchorClientY: r.top + r.height / 2
  });
}
</script>

<template>
  <g class="rag-wf-insert-edge-path" @mouseenter="hitPath = true" @mouseleave="hitPath = false">
    <BaseEdge
      :id="id"
      :path="pathD"
      :marker-end="markerEnd"
      :interaction-width="28"
      :style="{
        strokeWidth: selected ? 2.5 : 2,
        transition: 'stroke 0.16s ease, stroke-opacity 0.16s ease, stroke-width 0.16s ease',
        ...edgeStroke
      }"
    />
  </g>
  <EdgeLabelRenderer>
    <div
      :style="{
        pointerEvents: 'all',
        position: 'absolute',
        transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`
      }"
      class="rag-wf-edge-plus-host nopan nodrag"
      @mousedown.stop
      @dblclick.stop
    >
      <ElTooltip placement="top" effect="light" :show-after="180" :hide-after="0">
        <template #content>
          <div class="rag-wf-edge-tip-pop">
            <p class="rag-wf-edge-tip-line">点击添加节点</p>
            <p class="rag-wf-edge-tip-sub">拖拽连接节点</p>
          </div>
        </template>
        <button
          type="button"
          class="rag-wf-edge-plus"
          :class="{ 'is-hot': hovered }"
          aria-label="点击添加节点"
          @click="onPlusClick"
        >
          +
        </button>
      </ElTooltip>
    </div>
  </EdgeLabelRenderer>
</template>

<style scoped lang="scss">
.rag-wf-edge-tip-pop {
  padding: 2px 0;
  max-width: 180px;

  .rag-wf-edge-tip-line {
    margin: 0 0 2px;
    font-size: 13px;
    font-weight: 600;
    line-height: 1.35;
    color: var(--el-text-color-primary, #303133);
  }

  .rag-wf-edge-tip-sub {
    margin: 0;
    font-size: 12px;
    line-height: 1.4;
    color: var(--el-text-color-secondary, #909399);
  }
}

.rag-wf-edge-plus-host {
  width: 0;
  height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.rag-wf-edge-plus-host :deep(.el-tooltip__trigger) {
  outline: none;
}

/* Dify：主色实心圆钮，连线亦用同色淡化，悬停更明显 */
.rag-wf-edge-plus {
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 50%;
  padding: 0;
  margin: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 700;
  line-height: 1;
  cursor: pointer;
  color: var(--el-color-white, #fff);
  background: var(--el-color-primary);
  box-shadow:
    0 1px 2px rgb(0 0 0 / 8%),
    0 3px 12px rgb(15 23 42 / 12%);
  opacity: 0.9;
  transform: scale(1);
  transition:
    opacity 0.16s ease,
    transform 0.16s ease,
    background-color 0.16s ease,
    box-shadow 0.16s ease;

  &.is-hot {
    opacity: 1;
    box-shadow:
      0 2px 8px rgb(0 0 0 / 10%),
      0 6px 16px rgb(15 23 42 / 14%);
  }

  &:hover {
    opacity: 1 !important;
    transform: scale(1.08);
    background: var(--el-color-primary-dark-2, var(--el-color-primary));
    box-shadow:
      0 3px 10px rgb(0 0 0 / 12%),
      0 8px 22px rgb(15 23 42 / 16%);
  }
}
</style>
