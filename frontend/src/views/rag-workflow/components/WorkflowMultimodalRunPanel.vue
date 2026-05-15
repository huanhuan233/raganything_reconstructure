<script setup lang="ts">
import MarkdownIt from 'markdown-it';
import { computed, ref } from 'vue';
import { mergeMultimodalMarkdownFromData, parseMechanicalAnalysisResult } from '@/utils/multimodalResultParser';

type NodeResultLike = {
  success?: boolean;
  data?: unknown;
  error?: string | null;
  metadata?: unknown;
};

const props = defineProps<{ result: NodeResultLike }>();
const viewMode = ref<'markdown' | 'engineering'>('engineering');
const debugOpen = ref<string[]>([]);

function asRecord(v: unknown): Record<string, unknown> {
  return v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
}

const dataObj = computed(() => asRecord(props.result.data));
const processSummary = computed(() => asRecord(dataObj.value.process_summary));
const markdownText = computed(() => mergeMultimodalMarkdownFromData(dataObj.value));
const engineering = computed(() => parseMechanicalAnalysisResult(markdownText.value));

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: true
});

const oldTextRender = md.renderer.rules.text;
md.renderer.rules.text = (tokens, idx, options, env, self) => {
  const content = tokens[idx]?.content ?? '';
  const esc = md.utils.escapeHtml(content);
  const rendered = esc.replace(
    /(\b\d+(?:\.\d+)?(?:\s*(?:mm|cm|m|μm|um|°|HBW|HRC|N·m|rpm|kW|%)?)\b|[ØΦ]\s*\d+(?:\.\d+)?)/gi,
    '<span class="mm-num">$1</span>'
  );
  if (oldTextRender) {
    return oldTextRender(tokens, idx, options, env, self).replace(md.utils.escapeHtml(content), rendered);
  }
  return rendered;
};

const markdownHtml = computed(() => md.render(markdownText.value || ''));

function tagType(kind: 'dimension' | 'tolerance' | 'material' | 'process' | 'roughness' | 'datum'): string {
  if (kind === 'dimension') return 'primary';
  if (kind === 'tolerance') return 'warning';
  if (kind === 'material') return 'success';
  if (kind === 'process') return 'info';
  if (kind === 'roughness') return 'info';
  return 'danger';
}

function asList(v: unknown): string[] {
  return Array.isArray(v) ? v.map(x => String(x || '').trim()).filter(Boolean) : [];
}

function formatJson(v: unknown): string {
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}
</script>

<template>
  <div class="mm-panel">
    <div class="mm-toolbar">
      <ElRadioGroup v-model="viewMode" size="small">
        <ElRadioButton label="markdown">Markdown视图</ElRadioButton>
        <ElRadioButton label="engineering">工程分析视图</ElRadioButton>
      </ElRadioGroup>
    </div>

    <div class="mm-summary">
      <ElCard shadow="never">
        <div class="cap">处理概览</div>
        <div class="summary-grid">
          <div>候选数: {{ Number(processSummary.candidate_count ?? 0) }}</div>
          <div>处理数: {{ Number(processSummary.processed_count ?? 0) }}</div>
          <div>VLM使用: {{ Number(processSummary.vlm_used_count ?? 0) }}</div>
          <div>fallback: {{ Number(processSummary.fallback_count ?? 0) }}</div>
        </div>
      </ElCard>
    </div>

    <template v-if="viewMode === 'markdown'">
      <ElCard class="mm-markdown-card" shadow="never">
        <ElScrollbar max-height="560px">
          <div class="mm-markdown" v-html="markdownHtml" />
        </ElScrollbar>
      </ElCard>
    </template>

    <template v-else>
      <div class="mm-engineering">
        <div class="left">
          <ElCard shadow="never" class="left-card">
            <div class="cap">机械工程语义面板</div>
            <ElDescriptions :column="1" border size="small">
              <ElDescriptionsItem label="零件类型">{{ engineering.partType || '-' }}</ElDescriptionsItem>
              <ElDescriptionsItem label="材料">{{ engineering.material || '-' }}</ElDescriptionsItem>
              <ElDescriptionsItem label="热处理">{{ engineering.heatTreatment || '-' }}</ElDescriptionsItem>
            </ElDescriptions>
          </ElCard>

          <ElTabs type="border-card" class="left-card">
            <ElTabPane label="关键参数">
              <div class="tag-group">
                <ElTag v-for="x in asList(engineering.keyDimensions)" :key="`d-${x}`" :type="tagType('dimension')" effect="light">{{ x }}</ElTag>
                <ElTag v-for="x in asList(engineering.tolerances)" :key="`t-${x}`" :type="tagType('tolerance')" effect="light">{{ x }}</ElTag>
                <ElTag v-for="x in asList(engineering.datums)" :key="`da-${x}`" :type="tagType('datum')" effect="light">{{ x }}</ElTag>
                <ElTag v-for="x in asList(engineering.roughness)" :key="`r-${x}`" :type="tagType('roughness')" effect="light">{{ x }}</ElTag>
              </div>
            </ElTabPane>
            <ElTabPane label="结构特征">
              <div class="tag-group">
                <ElTag v-for="x in asList(engineering.features)" :key="`f-${x}`" :type="tagType('material')" effect="light">{{ x }}</ElTag>
                <ElTag v-for="x in asList(engineering.threads)" :key="`th-${x}`" :type="tagType('material')" effect="light">{{ x }}</ElTag>
                <ElTag v-for="x in asList(engineering.sections)" :key="`s-${x}`" :type="tagType('material')" effect="light">{{ x }}</ElTag>
              </div>
            </ElTabPane>
            <ElTabPane label="工艺路线">
              <ElTimeline v-if="asList(engineering.processes).length">
                <ElTimelineItem v-for="(p, idx) in asList(engineering.processes)" :key="`p-${idx}`" :timestamp="`Step ${idx + 1}`">
                  <span class="process-text">{{ p }}</span>
                </ElTimelineItem>
              </ElTimeline>
              <div v-else class="empty">无工艺路线信息</div>
            </ElTabPane>
          </ElTabs>
        </div>

        <div class="right">
          <ElCard shadow="never" class="right-card">
            <div class="cap">原始Markdown渲染</div>
            <ElScrollbar max-height="560px">
              <div class="mm-markdown" v-html="markdownHtml" />
            </ElScrollbar>
          </ElCard>
        </div>
      </div>
    </template>

    <ElCollapse v-model="debugOpen" class="debug-collapse">
      <ElCollapseItem name="debug" title="JSON调试数据">
        <ElScrollbar max-height="220px">
          <pre class="debug-json">{{ formatJson(engineering) }}</pre>
        </ElScrollbar>
      </ElCollapseItem>
    </ElCollapse>
  </div>
</template>

<style scoped lang="scss">
.mm-panel { display: flex; flex-direction: column; gap: 10px; }
.mm-toolbar { display: flex; align-items: center; justify-content: flex-start; }
.mm-summary .el-card,
.mm-markdown-card,
.left-card,
.right-card { border: 1px solid #e5e7eb; }
.cap {
  margin-bottom: 8px;
  font-size: 11px;
  font-weight: 700;
  color: #94a3b8;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}
.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  font-size: 12px;
  color: #334155;
}
.mm-engineering { display: grid; grid-template-columns: 1.2fr 1fr; gap: 10px; }
.left { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.right { min-width: 0; }
.tag-group { display: flex; flex-wrap: wrap; gap: 8px; }
.process-text { color: #334155; font-size: 12px; line-height: 1.5; }
.empty { color: #94a3b8; font-size: 12px; }
.debug-collapse { border: none; }
.debug-json {
  margin: 0;
  font-size: 11px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: Menlo, Monaco, Consolas, 'Courier New', monospace;
}

.mm-markdown {
  color: var(--el-text-color-primary);
  line-height: 1.7;
  font-size: 13px;

  :deep(h1), :deep(h2), :deep(h3), :deep(h4) {
    margin: 10px 0 6px;
    line-height: 1.4;
    color: var(--el-text-color-primary);
  }
  :deep(code), :deep(.mm-num) {
    font-family: ui-monospace, Menlo, Monaco, Consolas, 'Courier New', monospace;
    font-variant-numeric: tabular-nums;
  }
  :deep(pre) {
    padding: 10px;
    border-radius: 8px;
    background: var(--el-fill-color-light);
    overflow-x: auto;
  }
  :deep(blockquote) {
    margin: 8px 0;
    padding: 6px 10px;
    border-left: 3px solid var(--el-color-primary-light-5);
    background: var(--el-fill-color-lighter);
  }
  :deep(table) {
    display: block;
    width: max-content;
    min-width: 100%;
    overflow-x: auto;
    border-collapse: collapse;
    margin: 8px 0;
  }
  :deep(th), :deep(td) {
    border: 1px solid var(--el-border-color-light);
    padding: 6px 8px;
    white-space: nowrap;
  }
}

@media (max-width: 1200px) {
  .mm-engineering { grid-template-columns: 1fr; }
}
</style>
