<script setup lang="ts">
import MarkdownIt from 'markdown-it';
import { computed, ref } from 'vue';
import { parseMechanicalAnalysisResult } from '@/utils/multimodalResultParser';

type NodeResultLike = {
  success?: boolean;
  data?: unknown;
  error?: string | null;
  metadata?: unknown;
};

const props = defineProps<{
  result: NodeResultLike;
}>();

const viewMode = ref<'markdown' | 'engineering'>('markdown');
const debugOpen = ref<string[]>([]);

function asRecord(v: unknown): Record<string, unknown> {
  return v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
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

function tagType(kind: 'dimension' | 'tolerance' | 'material' | 'process' | 'roughness' | 'datum'): string {
  if (kind === 'dimension') return 'primary';
  if (kind === 'tolerance') return 'warning';
  if (kind === 'material') return 'success';
  if (kind === 'process') return 'info';
  if (kind === 'roughness') return 'info';
  return 'danger';
}

const data = computed(() => asRecord(props.result.data));
const answer = computed(() => String(data.value.answer ?? '').trim());
const generationSummary = computed(() => asRecord(data.value.generation_summary));
const prompt = computed(() => String(data.value.prompt ?? '').trim());
const engineering = computed(() => parseMechanicalAnalysisResult(answer.value));

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: true
});

const markdownHtml = computed(() => md.render(answer.value || ''));
</script>

<template>
  <div class="rag-wf-llm-panel">
    <div class="rag-wf-llm-toolbar">
      <ElRadioGroup v-model="viewMode" size="small">
        <ElRadioButton label="markdown">Markdown视图</ElRadioButton>
        <ElRadioButton label="engineering">工程分析视图</ElRadioButton>
      </ElRadioGroup>
    </div>

    <ElCard shadow="never" class="rag-wf-llm-card">
      <div class="rag-wf-llm-cap">generation_summary</div>
      <div class="summary-grid">
        <div>used_llm: {{ String(generationSummary.used_llm ?? '-') }}</div>
        <div>model: {{ String(generationSummary.model ?? '-') }}</div>
        <div>prompt_chars: {{ Number(generationSummary.prompt_chars ?? 0) }}</div>
        <div>answer_chars: {{ Number(generationSummary.answer_chars ?? 0) }}</div>
      </div>
    </ElCard>

    <template v-if="viewMode === 'markdown'">
      <ElCard shadow="never" class="rag-wf-llm-card">
        <div class="rag-wf-llm-cap">answer_markdown</div>
        <ElScrollbar max-height="560px">
          <div class="llm-markdown" v-html="markdownHtml" />
        </ElScrollbar>
      </ElCard>
    </template>

    <template v-else>
      <div class="llm-engineering">
        <div class="left">
          <ElCard shadow="never" class="rag-wf-llm-card">
            <div class="rag-wf-llm-cap">工程语义摘要</div>
            <ElDescriptions :column="1" border size="small">
              <ElDescriptionsItem label="零件类型">{{ engineering.partType || '-' }}</ElDescriptionsItem>
              <ElDescriptionsItem label="材料">{{ engineering.material || '-' }}</ElDescriptionsItem>
              <ElDescriptionsItem label="热处理">{{ engineering.heatTreatment || '-' }}</ElDescriptionsItem>
            </ElDescriptions>
          </ElCard>

          <ElTabs type="border-card" class="rag-wf-llm-card">
            <ElTabPane label="关键参数">
              <div class="tag-group">
                <ElTag v-for="x in asList(engineering.keyDimensions)" :key="`d-${x}`" :type="tagType('dimension')" effect="light">{{ x }}</ElTag>
                <ElTag v-for="x in asList(engineering.tolerances)" :key="`t-${x}`" :type="tagType('tolerance')" effect="light">{{ x }}</ElTag>
                <ElTag v-for="x in asList(engineering.datums)" :key="`da-${x}`" :type="tagType('datum')" effect="light">{{ x }}</ElTag>
                <ElTag v-for="x in asList(engineering.roughness)" :key="`r-${x}`" :type="tagType('roughness')" effect="light">{{ x }}</ElTag>
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
          <ElCard shadow="never" class="rag-wf-llm-card">
            <div class="rag-wf-llm-cap">answer_markdown</div>
            <ElScrollbar max-height="560px">
              <div class="llm-markdown" v-html="markdownHtml" />
            </ElScrollbar>
          </ElCard>
        </div>
      </div>
    </template>

    <ElCollapse v-model="debugOpen" class="debug-collapse">
      <ElCollapseItem name="prompt" title="Prompt / Debug">
        <div class="rag-wf-llm-card prompt-card">
          <div class="rag-wf-llm-cap">prompt</div>
          <ElScrollbar max-height="200px">
            <pre class="debug-json">{{ prompt || '（空）' }}</pre>
          </ElScrollbar>
        </div>
        <div class="rag-wf-llm-card">
          <div class="rag-wf-llm-cap">engineering_json</div>
          <ElScrollbar max-height="200px">
            <pre class="debug-json">{{ formatJson(engineering) }}</pre>
          </ElScrollbar>
        </div>
      </ElCollapseItem>
    </ElCollapse>
  </div>
</template>

<style scoped lang="scss">
.rag-wf-llm-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.rag-wf-llm-toolbar {
  display: flex;
  justify-content: flex-start;
}
.rag-wf-llm-card {
  border: 1px solid #e5e7eb;
}
.rag-wf-llm-cap {
  font-size: 11px;
  font-weight: 700;
  color: #9ca3af;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  margin-bottom: 8px;
}
.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  font-size: 12px;
  color: #334155;
}
.llm-engineering {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 10px;
}
.left {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}
.right {
  min-width: 0;
}
.tag-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.process-text {
  color: #334155;
  font-size: 12px;
  line-height: 1.5;
}
.empty {
  color: #94a3b8;
  font-size: 12px;
}
.debug-collapse {
  border: none;
}
.prompt-card {
  margin-bottom: 8px;
}
.debug-json {
  margin: 0;
  font-size: 11px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: Menlo, Monaco, Consolas, 'Courier New', monospace;
}

.llm-markdown {
  color: var(--el-text-color-primary);
  line-height: 1.7;
  font-size: 13px;
  :deep(h1), :deep(h2), :deep(h3), :deep(h4) {
    margin: 10px 0 6px;
    line-height: 1.4;
  }
  :deep(code) {
    font-family: ui-monospace, Menlo, Monaco, Consolas, 'Courier New', monospace;
    font-variant-numeric: tabular-nums;
  }
  :deep(pre) {
    padding: 10px;
    border-radius: 8px;
    background: var(--el-fill-color-light);
    overflow-x: auto;
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
  .llm-engineering {
    grid-template-columns: 1fr;
  }
}
</style>
