<script setup lang="ts">
import { computed, ref } from 'vue';
import type { RagNodeImplementationStatus, RagNodeMetadata } from '@/types/ragWorkflow';
import { resolveIsrVisualDomain } from '@/components/runtime/isrPalette';
import { buildPaletteGroups } from '../utils/nodeCategory';

const props = defineProps<{
  visible: boolean;
  position: { x: number; y: number };
  loading: boolean;
  catalog: RagNodeMetadata[];
}>();

const emit = defineEmits<{
  close: [];
  'add-node': [meta: RagNodeMetadata];
}>();

const nodePickerSearch = ref('');

const filteredPickerGroups = computed(() => buildPaletteGroups(props.catalog, nodePickerSearch.value.trim()));

function isrAccentClass(meta: RagNodeMetadata): string {
  const d = resolveIsrVisualDomain(meta.node_type);
  return d ? `rag-wf-np-item--isr rag-wf-np-item--isr-${d}` : '';
}

function statusOf(meta: RagNodeMetadata): RagNodeImplementationStatus {
  return meta.implementation_status ?? (meta.is_placeholder ? 'placeholder' : 'real');
}
</script>

<template>
  <div
    v-show="visible"
    class="rag-wf-node-picker"
    :style="{ left: `${position.x}px`, top: `${position.y}px` }"
    @click.stop
  >
    <div class="rag-wf-np-head">
      <span class="rag-wf-np-title">节点库</span>
      <button type="button" class="rag-wf-np-close" title="关闭" @click="emit('close')">×</button>
    </div>
    <div class="rag-wf-np-search">
      <ElInput v-model="nodePickerSearch" size="default" placeholder="搜索节点" clearable />
    </div>
    <div class="rag-wf-np-scroll">
      <ElSkeleton v-if="loading && !catalog.length" :rows="5" animated />
      <template v-else>
        <template v-for="g in filteredPickerGroups" :key="g.key">
          <div class="rag-wf-np-group-title">{{ g.title }}</div>
          <button
            v-for="meta in g.items"
            :key="meta.node_type"
            type="button"
            class="rag-wf-np-item"
            :class="isrAccentClass(meta)"
            @click="emit('add-node', meta)"
          >
            <div class="rag-wf-np-icon">
              <span class="rag-wf-np-ico-text">{{ (meta.display_name || meta.node_type).slice(0, 1).toUpperCase() }}</span>
            </div>
            <div class="rag-wf-np-text">
              <div class="rag-wf-np-name-row">
                <span class="rag-wf-np-name">{{ meta.display_name }}</span>
                <span v-if="statusOf(meta) === 'placeholder'" class="rag-wf-np-badge rag-wf-np-badge--ph">占位</span>
                <span v-else-if="statusOf(meta) === 'partial'" class="rag-wf-np-badge rag-wf-np-badge--partial">
                  半实现
                </span>
                <span v-else class="rag-wf-np-badge rag-wf-np-badge--ok">可运行</span>
              </div>
              <div class="rag-wf-np-sub">{{ meta.node_type }}</div>
            </div>
          </button>
        </template>
        <ElEmpty v-if="!filteredPickerGroups.length" description="无匹配节点" :image-size="72" />
      </template>
    </div>
  </div>
</template>

<style scoped lang="scss">
.rag-wf-node-picker {
  position: absolute;
  width: 320px;
  max-height: min(520px, calc(100vh - 120px));
  height: min(520px, calc(100% - 24px));
  box-sizing: border-box;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  box-shadow: 0 12px 40px rgb(15 23 42 / 10%);
  z-index: 30;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.rag-wf-np-head {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  padding: 10px 14px;
  border-bottom: 1px solid #eef2f7;
}

.rag-wf-np-title {
  font-weight: 600;
  font-size: 14px;
  color: #0f172a;
}

.rag-wf-np-close {
  margin-left: auto;
  border: none;
  background: transparent;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  cursor: pointer;
  color: #9ca3af;
  font-size: 18px;
  line-height: 1;
}

.rag-wf-np-close:hover {
  background: #f1f5f9;
  color: #334155;
}

.rag-wf-np-search {
  flex-shrink: 0;
  padding: 10px 14px;
  border-bottom: 1px solid #f1f5f9;
}

.rag-wf-np-scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 8px 10px 12px;
}

.rag-wf-np-group-title {
  margin: 10px 4px 6px;
  font-size: 11px;
  color: #94a3b8;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.rag-wf-np-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  width: 100%;
  padding: 10px 10px;
  margin-bottom: 4px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  text-align: left;
  transition:
    background 0.12s,
    border-color 0.12s,
    box-shadow 0.12s;
}

.rag-wf-np-item:hover {
  background: #f8fafc;
  border-color: #e2e8f0;
  box-shadow: 0 2px 8px rgb(15 23 42 / 4%);
}

.rag-wf-np-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(145deg, #eef4ff, #f8fafc);
  border: 1px solid #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.rag-wf-np-ico-text {
  font-size: 14px;
  font-weight: 700;
  color: #2563eb;
}

.rag-wf-np-text {
  min-width: 0;
  flex: 1;
}

.rag-wf-np-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.rag-wf-np-name {
  font-size: 13px;
  color: #0f172a;
  font-weight: 600;
  line-height: 1.35;
  word-break: break-word;
}

.rag-wf-np-sub {
  font-size: 11px;
  color: #94a3b8;
  font-family: ui-monospace, Menlo, Monaco, Consolas, monospace;
  word-break: break-all;
  margin-top: 4px;
  line-height: 1.35;
}

.rag-wf-np-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 999px;
  flex-shrink: 0;
}

.rag-wf-np-badge--ph {
  color: #b45309;
  background: #fffbeb;
  border: 1px solid rgb(251 191 36 / 35%);
}

.rag-wf-np-badge--ok {
  color: #166534;
  background: #f0fdf4;
  border: 1px solid rgb(74 222 128 / 35%);
}

.rag-wf-np-badge--partial {
  color: #1d4ed8;
  background: #eff6ff;
  border: 1px solid rgb(96 165 250 / 38%);
}

.rag-wf-np-item--isr {
  border-left: 4px solid #64748b;
}

.rag-wf-np-item--isr-ontology {
  border-left-color: #1e3a8a;
  background: linear-gradient(90deg, rgb(30 58 138 / 6%), #fff);
}

.rag-wf-np-item--isr-constraint {
  border-left-color: #b91c1c;
  background: linear-gradient(90deg, rgb(185 28 28 / 6%), #fff);
}

.rag-wf-np-item--isr-semantic {
  border-left-color: #7c3aed;
  background: linear-gradient(90deg, rgb(124 58 237 / 7%), #fff);
}

.rag-wf-np-item--isr-state {
  border-left-color: #ea580c;
  background: linear-gradient(90deg, rgb(234 88 12 / 7%), #fff);
}

.rag-wf-np-item--isr-graph {
  border-left-color: #0e7490;
  background: linear-gradient(90deg, rgb(14 116 144 / 7%), #fff);
}

.rag-wf-np-item--isr-runtime {
  border-left-color: #334155;
  background: linear-gradient(90deg, rgb(51 65 85 / 8%), #fff);
}
</style>
