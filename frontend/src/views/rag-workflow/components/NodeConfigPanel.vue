<script setup lang="ts">
import { computed, ref, toRefs } from 'vue';
import type { Node } from '@vue-flow/core';
import type { RagNodeConfigField, RagNodeImplementationStatus, RagNodeMetadata } from '@/types/ragWorkflow';
import { uploadRagWorkflowSource } from '@/service/api/ragWorkflow';
import { messageFromAxios } from '../utils/apiError';
import KnowledgeSelectConfigPanel from './KnowledgeSelectConfigPanel.vue';
import StoragePersistConfigPanel from './StoragePersistConfigPanel.vue';
import IndustrialConfigPanel from '../industrial/IndustrialConfigPanel.vue';

const props = withDefaults(
  defineProps<{
    selectedNode: Node | null;
    selectedNodeMeta: RagNodeMetadata | null;
    hasConfigSchema: boolean;
    localSchemaConfig: Record<string, unknown>;
    knowledgePipelineCandidates?: string[];
    suppressInternalHead?: boolean;
  }>(),
  { suppressInternalHead: false, knowledgePipelineCandidates: () => [] }
);
const { selectedNode, selectedNodeMeta, hasConfigSchema, localSchemaConfig, suppressInternalHead, knowledgePipelineCandidates } = toRefs(props);
const globalQuery = defineModel<string>('globalQuery', { default: '' });

const isStoragePersistSelected = computed(
  () => String(selectedNode.value?.data?.nodeType ?? '') === 'storage.persist'
);
const isKnowledgeSelectSelected = computed(
  () => String(selectedNode.value?.data?.nodeType ?? '') === 'knowledge.select'
);
const isGraphRetrieveSelected = computed(
  () => String(selectedNode.value?.data?.nodeType ?? '') === 'graph.retrieve'
);
const isRerankSelected = computed(
  () => String(selectedNode.value?.data?.nodeType ?? '') === 'rerank'
);
const isWorkflowStartSelected = computed(
  () => String(selectedNode.value?.data?.nodeType ?? '') === 'workflow.start'
);
const isIndustrialSelected = computed(() => String(selectedNode.value?.data?.nodeType ?? '').startsWith('industrial.'));

const QUERY_OVERRIDE_NODE_TYPES = new Set(['keyword.extract', 'vector.retrieve', 'graph.retrieve', 'rag.query', 'llm.generate']);
const isQueryOverrideNode = computed(() => QUERY_OVERRIDE_NODE_TYPES.has(String(selectedNode.value?.data?.nodeType ?? '')));
const MERGE_NODE_TYPES = new Set(['entity.merge', 'relation.merge', 'graph.merge']);

const visibleConfigFields = computed(() => {
  const meta = props.selectedNodeMeta;
  if (!meta?.config_fields) return [];
  const nodeType = String(selectedNode.value?.data?.nodeType ?? '');
  const mergeEngine = String(localSchemaConfig.value.merge_engine ?? 'runtime').trim().toLowerCase();
  const useLlmSummary = Boolean(localSchemaConfig.value.use_llm_summary_on_merge);
  if (isStoragePersistSelected.value) {
    return meta.config_fields.filter(x => x.name !== 'vector_storage' && x.name !== 'graph_storage');
  }
  if (isKnowledgeSelectSelected.value) {
    return [];
  }
  if (isIndustrialSelected.value) {
    return [];
  }
  if (isKeywordExtractSelected.value) {
    const mode = String(localSchemaConfig.value.keyword_mode ?? 'lightrag').trim().toLowerCase();
    if (mode === 'rule') {
      return meta.config_fields.filter(x => x.name !== 'model' && x.name !== 'query');
    }
  }
  if (isQueryOverrideNode.value) {
    const hidden = new Set(['query']);
    if (isGraphRetrieveSelected.value) {
      hidden.add('high_level_keywords');
      hidden.add('low_level_keywords');
    }
    return meta.config_fields.filter(x => !hidden.has(x.name));
  }
  if (MERGE_NODE_TYPES.has(nodeType)) {
    return meta.config_fields.filter(f => {
      if (mergeEngine === 'lightrag' && f.name === 'merge_strategy') return false;
      if ((nodeType === 'entity.merge' || nodeType === 'relation.merge') && f.name === 'model') {
        return mergeEngine === 'lightrag' && useLlmSummary;
      }
      return true;
    });
  }
  if (isRerankSelected.value) {
    const engine = String(localSchemaConfig.value.rerank_engine ?? 'runtime').trim().toLowerCase();
    if (engine === 'lightrag') {
      const runtimeOnly = new Set([
        'rerank_model',
        'graph_boost',
        'keyword_boost',
        'diversity_boost',
        'vector_weight',
        'graph_weight',
        'keyword_weight',
        'vision_weight'
      ]);
      return meta.config_fields.filter(f => !runtimeOnly.has(f.name));
    }
  }
  return meta.config_fields;
});

const isKeywordExtractSelected = computed(
  () => String(selectedNode.value?.data?.nodeType ?? '') === 'keyword.extract'
);

const keywordModeHelp = computed(() => {
  if (!isKeywordExtractSelected.value) return '';
  const mode = String(localSchemaConfig.value.keyword_mode ?? 'lightrag').trim().toLowerCase();
  if (mode === 'llm') {
    return '使用 Runtime 自定义 Prompt 调用 .env 配置的模型抽取关键词。';
  }
  if (mode === 'rule') {
    return '使用规则抽取，仅用于调试或无模型环境。';
  }
  return '调用 LightRAG 原生关键词抽取逻辑，最接近原始 RAG 查询流程。';
});

const rerankModeHelp = computed(() => {
  if (!isRerankSelected.value) return '';
  const engine = String(localSchemaConfig.value.rerank_engine ?? 'runtime').trim().toLowerCase();
  if (engine === 'lightrag') {
    return '使用 LightRAG Retrieval Ordering（复用原检索分数行为，不启用独立 CrossEncoder Rerank）。';
  }
  return 'Runtime 模式将执行 score fusion + weighted ranking，并可选二阶段模型 rerank。';
});

const labelDraft = defineModel<string>('labelDraft', { required: true });
const configDraft = defineModel<string>('configDraft', { required: true });

const emit = defineEmits<{
  'patch-field': [name: string, value: unknown];
  'apply-json-config': [];
}>();

/** 默认折叠「高级 JSON」 */
const advancedJsonActive = ref<string[]>([]);
/** query 覆盖项默认折叠 */
const advancedQueryActive = ref<string[]>([]);
const advancedGraphKwActive = ref<string[]>([]);
const pathFileInputRef = ref<HTMLInputElement | null>(null);
const pendingPathFieldName = ref<string>('');
const pathUploading = ref(false);

const nodeImplementationStatus = computed<RagNodeImplementationStatus | null>(() => {
  const meta = props.selectedNodeMeta;
  if (!meta) return null;
  return meta.implementation_status ?? (meta.is_placeholder ? 'placeholder' : 'real');
});

const statusTipText = computed(() => {
  if (nodeImplementationStatus.value === 'placeholder') {
    return '占位节点：当前仅用于编排映射，未接真实源码函数。';
  }
  if (nodeImplementationStatus.value === 'partial') {
    return '半实现节点：已接入部分逻辑，仍有阶段待补齐。';
  }
  return '';
});

function schemaStrValue(f: RagNodeConfigField, local: Record<string, unknown>): string {
  const v = local[f.name];
  if (v === undefined || v === null) return '';
  if (f.type === 'json' && typeof v !== 'string') {
    try {
      return JSON.stringify(v, null, 2);
    } catch {
      return String(v);
    }
  }
  return String(v);
}

function schemaOptions(f: RagNodeConfigField): string[] {
  return (f.options ?? []).map(o => String(o));
}

function isCreatableSelectField(f: RagNodeConfigField): boolean {
  if (f.type !== 'select') return false;
  const nodeType = String(selectedNode.value?.data?.nodeType ?? '');
  // graph.persist / knowledge.select 的 workspace 既要支持自动发现，也要支持手工新增输入。
  if (f.name === 'workspace' && (nodeType === 'graph.persist' || nodeType === 'knowledge.select')) {
    return true;
  }
  return false;
}

const MINERU_CONTENT_TYPES = [
  'title',
  'subtitle',
  'text',
  'list',
  'reference',
  'caption',
  'code',
  'algorithm',
  'image',
  'figure',
  'chart',
  'seal',
  'image_caption',
  'table',
  'table_caption',
  'table_footnote',
  'sheet',
  'equation',
  'inline_formula',
  'formula',
  'formula_caption',
  'formula_label',
  'header',
  'footer',
  'page_number',
  'footnote',
  'margin_note',
  'discarded',
  'layout_region',
  'multi_column_region'
];

const DEFAULT_ROUTE_PIPELINES = [
  'text_pipeline',
  'table_pipeline',
  'vision_pipeline',
  'equation_pipeline',
  'discard_pipeline'
];

function isTypeMultiSelectField(f: RagNodeConfigField): boolean {
  if (f.type !== 'json') return false;
  return ['keep_types', 'drop_types', 'process_types', 'ignore_types'].includes(f.name);
}

function isRouteMappingField(f: RagNodeConfigField): boolean {
  return f.type === 'json' && f.name === 'route_mapping';
}

function asTypeList(v: unknown): string[] {
  if (Array.isArray(v)) return v.map(x => String(x).trim()).filter(Boolean);
  if (typeof v === 'string') {
    const s = v.trim();
    if (!s) return [];
    try {
      const parsed = JSON.parse(s);
      if (Array.isArray(parsed)) return parsed.map(x => String(x).trim()).filter(Boolean);
    } catch {
      return s
        .split(',')
        .map(x => x.trim())
        .filter(Boolean);
    }
  }
  return [];
}

function asRouteMapping(v: unknown): Record<string, string[]> {
  let raw: unknown = v;
  if (typeof raw === 'string') {
    const s = raw.trim();
    if (!s) return {};
    try {
      raw = JSON.parse(s);
    } catch {
      return {};
    }
  }
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {};
  const obj = raw as Record<string, unknown>;
  const out: Record<string, string[]> = {};
  for (const [k, vv] of Object.entries(obj)) {
    const key = String(k).trim();
    if (!key) continue;
    out[key] = asTypeList(vv);
  }
  return out;
}

function routeTypesFor(local: Record<string, unknown>, fieldName: string, routeName: string): string[] {
  const mapping = asRouteMapping(local[fieldName]);
  return mapping[routeName] ?? [];
}

function patchRouteMapping(fieldName: string, routeName: string, values: string[]) {
  const mapping = asRouteMapping(localSchemaConfig.value[fieldName]);
  mapping[routeName] = values;
  emit('patch-field', fieldName, mapping);
}

function queryOverrideValue(local: Record<string, unknown>): string {
  const q = local.query;
  return typeof q === 'string' ? q : '';
}

function keywordCsvValue(local: Record<string, unknown>, key: 'high_level_keywords' | 'low_level_keywords'): string {
  const raw = local[key];
  if (Array.isArray(raw)) {
    return raw.map(x => String(x || '').trim()).filter(Boolean).join(', ');
  }
  if (typeof raw === 'string') return raw;
  return '';
}

function patchKeywordCsv(
  key: 'high_level_keywords' | 'low_level_keywords',
  value: string
) {
  const out = String(value || '')
    .split(',')
    .map(x => x.trim())
    .filter(Boolean);
  emit('patch-field', key, out);
}

function triggerPickPathFile(fieldName: string) {
  pendingPathFieldName.value = fieldName;
  pathFileInputRef.value?.click();
}

async function onPickedPathFile(e: Event) {
  const input = e.target as HTMLInputElement | null;
  const fieldName = pendingPathFieldName.value;
  const file = input?.files?.[0];
  if (!fieldName || !file) {
    if (input) input.value = '';
    return;
  }
  pathUploading.value = true;
  try {
    const resp = await uploadRagWorkflowSource(file);
    const sourcePath = String(resp?.source_path || '').trim();
    if (!sourcePath) {
      throw new Error('上传成功但未返回 source_path');
    }
    emit('patch-field', fieldName, sourcePath);
    window.$message?.success('文件已上传并填充 source_path');
  } catch (err) {
    window.$message?.error(messageFromAxios(err));
  } finally {
    pathUploading.value = false;
    pendingPathFieldName.value = '';
    if (input) input.value = '';
  }
}
</script>

<template>
  <div class="rag-wf-config rag-wf-config-drawer-root is-dify-density" :class="{ 'is-compact-drawer': suppressInternalHead }">
    <div v-if="!suppressInternalHead" class="rag-wf-config-head">
      <span class="rag-wf-config-title">{{ selectedNode ? selectedNode.data?.label || '节点' : '节点' }}</span>
    </div>
    <div class="rag-wf-config-body">
      <template v-if="selectedNode">
        <!-- 节点实现状态提示 -->
        <div v-if="statusTipText" class="rag-wf-ph-tip" role="status">
          <span class="rag-wf-ph-tip-ico" aria-hidden="true">!</span>
          <span class="rag-wf-ph-tip-text">{{ statusTipText }}</span>
        </div>

        <!-- 基础信息 -->
        <div class="rag-wf-pane rag-wf-pane--base">
          <div class="rag-wf-pane-title">基础信息</div>
          <div class="rag-wf-base-rows">
            <div class="rag-wf-base-field">
              <span class="rag-wf-pane-label">节点 ID</span>
              <ElInput :model-value="String(selectedNode.id)" size="default" readonly class="rag-wf-inp-nodeid" />
            </div>
            <div class="rag-wf-base-field">
              <span class="rag-wf-pane-label">显示名称</span>
              <ElInput v-model="labelDraft" size="default" placeholder="显示名称" />
            </div>
          </div>
        </div>

        <div v-if="isWorkflowStartSelected" class="rag-wf-pane rag-wf-pane--params">
          <div class="rag-wf-pane-title">工作流输入</div>
          <div class="rag-wf-param-row">
            <div class="rag-wf-param-label-line">
              <span class="rag-wf-pane-label">用户问题 query</span>
            </div>
            <div class="rag-wf-param-desc">写入 workflow.input_data.query，作为默认问题入口。</div>
            <ElInput
              v-model="globalQuery"
              type="textarea"
              :autosize="{ minRows: 2, maxRows: 6 }"
              placeholder="请输入用户问题"
            />
          </div>
        </div>

        <template v-if="hasConfigSchema && selectedNodeMeta">
          <!-- 节点参数 -->
          <div class="rag-wf-pane rag-wf-pane--params">
            <div class="rag-wf-pane-title">节点参数</div>
            <StoragePersistConfigPanel
              v-if="isStoragePersistSelected"
              :vector-storage="(localSchemaConfig.vector_storage as Record<string, unknown>) || {}"
              @patch-field="(name: string, val: unknown) => emit('patch-field', name, val)"
            />
            <KnowledgeSelectConfigPanel
              v-else-if="isKnowledgeSelectSelected"
              :config="localSchemaConfig"
              :pipeline-candidates="knowledgePipelineCandidates"
              @patch-field="(name: string, val: unknown) => emit('patch-field', name, val)"
            />
            <IndustrialConfigPanel
              v-else-if="isIndustrialSelected"
              :node-type="String(selectedNode?.data?.nodeType ?? '')"
              :config="localSchemaConfig"
              @patch-field="(name: string, val: unknown) => emit('patch-field', name, val)"
            />
            <div v-if="visibleConfigFields.length" class="rag-wf-param-list">
              <div v-for="f in visibleConfigFields" :key="f.name" class="rag-wf-param-row">
                <div class="rag-wf-param-label-line">
                  <span class="rag-wf-pane-label"
                    >{{ f.label }}<template v-if="f.required">&nbsp;<span class="rag-wf-required">*</span></template></span
                  >
                </div>
                <div v-if="f.description" class="rag-wf-param-desc">{{ f.description }}</div>
                <div v-if="f.type === 'path'" class="rag-wf-path-input-wrap">
                  <ElInput
                    size="default"
                    class="rag-wf-path-input"
                    :placeholder="f.placeholder ?? undefined"
                    :model-value="schemaStrValue(f, localSchemaConfig)"
                    @update:model-value="v => emit('patch-field', f.name, v)"
                  />
                  <ElButton
                    size="small"
                    class="rag-wf-path-pick"
                    :loading="pathUploading"
                    @click="triggerPickPathFile(f.name)"
                  >
                    选择并上传
                  </ElButton>
                </div>
                <ElInput
                  v-else-if="f.type === 'string'"
                  size="default"
                  :placeholder="f.placeholder ?? undefined"
                  :model-value="schemaStrValue(f, localSchemaConfig)"
                  @update:model-value="v => emit('patch-field', f.name, v)"
                />
                <ElInput
                  v-else-if="f.type === 'number'"
                  size="default"
                  :placeholder="f.placeholder ?? undefined"
                  :model-value="schemaStrValue(f, localSchemaConfig)"
                  @update:model-value="
                    v => emit('patch-field', f.name, v === '' || v === undefined ? undefined : Number(v))
                  "
                />
                <ElSwitch
                  v-else-if="f.type === 'boolean'"
                  :model-value="Boolean(localSchemaConfig[f.name])"
                  @update:model-value="v => emit('patch-field', f.name, v)"
                />
                <ElSelect
                  v-else-if="f.type === 'select'"
                  size="default"
                  class="rag-wf-select-full"
                  :placeholder="f.placeholder ?? '选择'"
                  :model-value="localSchemaConfig[f.name] as string | undefined"
                  :filterable="isCreatableSelectField(f)"
                  :allow-create="isCreatableSelectField(f)"
                  :default-first-option="isCreatableSelectField(f)"
                  clearable
                  @update:model-value="v => emit('patch-field', f.name, v ?? undefined)"
                >
                  <ElOption v-for="opt in schemaOptions(f)" :key="opt" :label="opt" :value="opt" />
                </ElSelect>
                <ElInput
                  v-else-if="f.type === 'json' && !isTypeMultiSelectField(f) && !isRouteMappingField(f)"
                  type="textarea"
                  :autosize="{ minRows: 3, maxRows: 8 }"
                  class="rag-wf-inp-json mono"
                  spellcheck="false"
                  :placeholder="f.placeholder ?? '{}'"
                  :model-value="schemaStrValue(f, localSchemaConfig)"
                  @update:model-value="v => emit('patch-field', f.name, v)"
                />
                <div v-else-if="isRouteMappingField(f)" class="rag-wf-route-mapping-editor">
                  <div v-for="route in DEFAULT_ROUTE_PIPELINES" :key="route" class="rag-wf-route-mapping-row">
                    <div class="rag-wf-route-name">{{ route }}</div>
                    <ElSelect
                      size="default"
                      class="rag-wf-select-full rag-wf-type-multi-select"
                      :model-value="routeTypesFor(localSchemaConfig, f.name, route)"
                      multiple
                      clearable
                      filterable
                      collapse-tags
                      collapse-tags-tooltip
                      placeholder="选择类型"
                      @update:model-value="v => patchRouteMapping(f.name, route, (v ?? []) as string[])"
                    >
                      <ElOption v-for="opt in MINERU_CONTENT_TYPES" :key="opt" :label="opt" :value="opt" />
                    </ElSelect>
                  </div>
                </div>
                <ElSelect
                  v-else-if="isTypeMultiSelectField(f)"
                  size="default"
                  class="rag-wf-select-full rag-wf-type-multi-select"
                  :model-value="asTypeList(localSchemaConfig[f.name])"
                  multiple
                  clearable
                  collapse-tags
                  collapse-tags-tooltip
                  :placeholder="f.placeholder ?? '请选择内容类型'"
                  @update:model-value="v => emit('patch-field', f.name, v)"
                >
                  <ElOption v-for="opt in MINERU_CONTENT_TYPES" :key="opt" :label="opt" :value="opt" />
                </ElSelect>
                <ElInput
                  v-else
                  size="default"
                  :placeholder="f.placeholder ?? undefined"
                  :model-value="schemaStrValue(f, localSchemaConfig)"
                  @update:model-value="v => emit('patch-field', f.name, v)"
                />
              </div>
            </div>
            <div v-if="isQueryOverrideNode" class="rag-wf-pane rag-wf-pane--adv rag-wf-pane--query-override">
              <ElCollapse v-model="advancedQueryActive" class="rag-wf-adv-collapse">
                <ElCollapseItem name="adv-query">
                  <template #title>
                    <span class="rag-wf-adv-collapse-title">高级：覆盖用户问题</span>
                  </template>
                  <div class="rag-wf-param-desc">留空时自动使用 workflow.input_data.query。</div>
                  <ElInput
                    :model-value="queryOverrideValue(localSchemaConfig)"
                    type="textarea"
                    :autosize="{ minRows: 2, maxRows: 6 }"
                    placeholder="覆盖用户问题（可选）"
                    @update:model-value="v => emit('patch-field', 'query', v)"
                  />
                </ElCollapseItem>
              </ElCollapse>
            </div>
            <div v-if="isGraphRetrieveSelected" class="rag-wf-pane rag-wf-pane--adv rag-wf-pane--query-override">
              <ElCollapse v-model="advancedGraphKwActive" class="rag-wf-adv-collapse">
                <ElCollapseItem name="adv-graph-kws">
                  <template #title>
                    <span class="rag-wf-adv-collapse-title">高级：覆盖图检索关键词</span>
                  </template>
                  <div class="rag-wf-param-row">
                    <div class="rag-wf-param-label-line">
                      <span class="rag-wf-pane-label">覆盖高层关键词</span>
                    </div>
                    <ElInput
                      :model-value="keywordCsvValue(localSchemaConfig, 'high_level_keywords')"
                      type="textarea"
                      :autosize="{ minRows: 2, maxRows: 4 }"
                      placeholder="可选，逗号分隔，例如：报价单, 对接人"
                      @update:model-value="v => patchKeywordCsv('high_level_keywords', String(v || ''))"
                    />
                  </div>
                  <div class="rag-wf-param-row" style="margin-top: 8px">
                    <div class="rag-wf-param-label-line">
                      <span class="rag-wf-pane-label">覆盖低层关键词</span>
                    </div>
                    <ElInput
                      :model-value="keywordCsvValue(localSchemaConfig, 'low_level_keywords')"
                      type="textarea"
                      :autosize="{ minRows: 2, maxRows: 4 }"
                      placeholder="可选，逗号分隔，例如：联系人, 负责人"
                      @update:model-value="v => patchKeywordCsv('low_level_keywords', String(v || ''))"
                    />
                  </div>
                </ElCollapseItem>
              </ElCollapse>
            </div>
            <div v-if="keywordModeHelp" class="rag-wf-param-desc rag-wf-param-desc--mode-tip">{{ keywordModeHelp }}</div>
            <div v-if="rerankModeHelp" class="rag-wf-param-desc rag-wf-param-desc--mode-tip">{{ rerankModeHelp }}</div>
          </div>

          <!-- 高级 JSON -->
          <div class="rag-wf-pane rag-wf-pane--adv">
            <ElCollapse v-model="advancedJsonActive" class="rag-wf-adv-collapse">
              <ElCollapseItem name="adv-json">
                <template #title>
                  <span class="rag-wf-adv-collapse-title">高级：原始 config JSON</span>
                </template>
                <ElInput
                  v-model="configDraft"
                  type="textarea"
                  :autosize="{ minRows: 4, maxRows: 12 }"
                  class="rag-wf-json-textarea mono"
                  spellcheck="false"
                />
                <div class="rag-wf-json-actions">
                  <ElButton size="small" type="primary" plain @click="emit('apply-json-config')">同步 JSON</ElButton>
                </div>
              </ElCollapseItem>
            </ElCollapse>
          </div>
        </template>
        <template v-else>
          <div class="rag-wf-pane rag-wf-pane--adv">
            <ElCollapse v-model="advancedJsonActive" class="rag-wf-adv-collapse">
              <ElCollapseItem name="adv-json">
                <template #title>
                  <span class="rag-wf-adv-collapse-title">高级：原始 config JSON</span>
                </template>
                <ElInput
                  v-model="configDraft"
                  type="textarea"
                  :autosize="{ minRows: 4, maxRows: 12 }"
                  class="rag-wf-json-textarea mono"
                  spellcheck="false"
                />
                <div class="rag-wf-json-actions">
                  <ElButton size="small" type="primary" plain @click="emit('apply-json-config')">同步 JSON</ElButton>
                </div>
              </ElCollapseItem>
            </ElCollapse>
          </div>
        </template>
      </template>
    </div>
    <input ref="pathFileInputRef" type="file" style="display: none" @change="onPickedPathFile" />
  </div>
</template>

<style scoped lang="scss">
.mono {
  font-family: ui-monospace, Menlo, Monaco, Consolas, 'Courier New', monospace;
}

/* 占位提示卡 */
.rag-wf-ph-tip {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  margin-bottom: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid #fed7aa;
  background: #fff7ed;
  color: #9a3412;
  box-sizing: border-box;
}

.rag-wf-ph-tip-ico {
  flex-shrink: 0;
  width: 18px;
  height: 18px;
  border-radius: 999px;
  background: rgb(251 146 60 / 25%);
  color: #9a3412;
  font-size: 11px;
  font-weight: 800;
  line-height: 18px;
  text-align: center;
}

.rag-wf-ph-tip-text {
  font-size: 12px;
  line-height: 1.5;
}

/* 分区白卡片 */
.rag-wf-pane {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 14px;
  margin-bottom: 12px;
  box-shadow: none;
  box-sizing: border-box;
}

.rag-wf-pane-title {
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 12px;
  letter-spacing: 0.02em;
}

.rag-wf-pane-label {
  font-size: 12px;
  font-weight: 500;
  color: #475569;
  line-height: 1.35;
}

.rag-wf-required {
  color: #dc2626;
  font-weight: 600;
}

.rag-wf-base-rows {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.rag-wf-base-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.rag-wf-inp-nodeid :deep(.el-input__wrapper) {
  font-size: 12px;
  min-height: 32px !important;
  font-family: ui-monospace, Menlo, Monaco, Consolas, 'Courier New', monospace !important;
  color: #64748b;
}

.rag-wf-config-body :deep(.el-input__wrapper) {
  min-height: 32px !important;
}

.rag-wf-param-list {
  display: flex;
  flex-direction: column;
}

.rag-wf-param-row {
  margin-bottom: 14px;

  &:last-child {
    margin-bottom: 0;
  }
}

.rag-wf-param-label-line {
  margin-bottom: 4px;
}

.rag-wf-param-desc {
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.45;
  margin-bottom: 6px;
}

.rag-wf-param-desc--mode-tip {
  margin-top: 8px;
  margin-bottom: 0;
  padding: 8px 10px;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  color: #475569;
  background: #f8fafc;
}

.rag-wf-path-input-wrap {
  display: flex;
  gap: 8px;
  align-items: stretch;
}

.rag-wf-path-input {
  flex: 1;
  min-width: 0;
}

.rag-wf-path-pick {
  flex-shrink: 0;
  padding: 0 10px !important;
  min-height: 32px !important;
}

.rag-wf-select-full {
  width: 100%;
}

.rag-wf-type-multi-select :deep(.el-select__tags) {
  max-width: calc(100% - 40px);
}

.rag-wf-route-mapping-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.rag-wf-route-mapping-row {
  padding: 8px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
}

.rag-wf-route-name {
  margin-bottom: 6px;
  font-size: 12px;
  color: #64748b;
  font-family: ui-monospace, Menlo, Monaco, Consolas, 'Courier New', monospace;
}

.rag-wf-inp-json :deep(.el-textarea__inner) {
  font-family: ui-monospace, Menlo, Monaco, Consolas, 'Courier New', monospace;
  font-size: 12px;
}

/* 高级 JSON 折叠 */
.rag-wf-pane--adv {
  padding: 0;
  overflow: hidden;
}

.rag-wf-adv-collapse {
  border: none;
  --el-collapse-border-color: transparent;
}

.rag-wf-adv-collapse :deep(.el-collapse-item__header) {
  height: 40px;
  min-height: 40px;
  line-height: 40px;
  padding: 0 14px;
  font-size: 13px;
  font-weight: 500;
  color: #475569;
  background: #fff;
  border-radius: 12px;
}

.rag-wf-adv-collapse :deep(.el-collapse-item.is-active > .el-collapse-item__header) {
  border-bottom-left-radius: 0;
  border-bottom-right-radius: 0;
  border-bottom: 1px solid #f1f5f9;
}

.rag-wf-adv-collapse-title {
  user-select: none;
}

.rag-wf-adv-collapse :deep(.el-collapse-item__wrap) {
  border: none;
  background: #fff;
}

.rag-wf-adv-collapse :deep(.el-collapse-item__arrow) {
  font-size: 13px;
}

.rag-wf-adv-collapse :deep(.el-collapse-item__content) {
  padding: 10px 14px 12px;
  border-bottom-left-radius: 12px;
  border-bottom-right-radius: 12px;
}

.rag-wf-json-textarea :deep(.el-textarea__inner) {
  max-height: 180px;
  overflow-y: auto !important;
  font-family: ui-monospace, Menlo, Monaco, Consolas, 'Courier New', monospace;
  font-size: 11px;
  line-height: 1.45;
  resize: none;
}

.rag-wf-json-actions {
  margin-top: 10px;
  display: flex;
  justify-content: flex-start;
}

</style>
