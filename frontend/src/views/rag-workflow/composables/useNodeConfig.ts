import type { Node } from '@vue-flow/core';
import { computed, nextTick, ref, watch, type Ref } from 'vue';
import { useDebounceFn } from '@vueuse/core';
import Json5 from 'json5';
import type { RagFlowNodeData, RagNodeConfigField, RagNodeMetadata } from '@/types/ragWorkflow';

export function useNodeConfig(options: {
  flowNodes: Ref<Node[]>;
  selectedNodeId: Ref<string | null>;
  paletteCatalog: Ref<RagNodeMetadata[]>;
  onStructureChange: () => void;
}) {
  const { flowNodes, selectedNodeId, paletteCatalog, onStructureChange } = options;

  const labelDraft = ref('');
  const configDraft = ref('{}');
  const configDraftProgrammatic = ref(false);
  const labelDraftProgrammatic = ref(false);
  const localSchemaProgrammatic = ref(false);
  const localSchemaConfig = ref<Record<string, unknown>>({});

  const selectedNode = computed((): Node | null => {
    const id = selectedNodeId.value;
    if (!id) return null;
    const found = flowNodes.value.find(n => String(n.id) === id);
    return found ? (found as Node) : null;
  });

  const selectedNodeMeta = computed((): RagNodeMetadata | null => {
    const id = selectedNodeId.value;
    if (!id) return null;
    const n = flowNodes.value.find(x => String(x.id) === id);
    const nt = (n?.data as RagFlowNodeData | undefined)?.nodeType;
    if (!nt) return null;
    return paletteCatalog.value.find(m => m.node_type === nt) ?? null;
  });

  const hasConfigSchema = computed(() => (selectedNodeMeta.value?.config_fields?.length ?? 0) > 0);

  function rebuildLocalSchemaConfig() {
    const id = selectedNodeId.value;
    if (!id) {
      localSchemaConfig.value = {};
      return;
    }
    const n = flowNodes.value.find(x => String(x.id) === id);
    const d = (n?.data ?? {}) as RagFlowNodeData;
    const meta = paletteCatalog.value.find(m => m.node_type === d.nodeType);
    const cfg: Record<string, unknown> = { ...(d.config ?? {}) };
    for (const f of meta?.config_fields ?? []) {
      if (cfg[f.name] === undefined && f.default !== undefined) {
        cfg[f.name] = f.default;
      }
    }
    localSchemaConfig.value = cfg;
  }

  function patchSchemaField(name: string, value: unknown) {
    const next = { ...localSchemaConfig.value };
    if (value === '' || value === undefined) {
      delete next[name];
    } else {
      next[name] = value;
    }
    localSchemaConfig.value = next;
  }

  function schemaStrValue(f: RagNodeConfigField): string {
    const v = localSchemaConfig.value[f.name];
    if (v === undefined || v === null) return '';
    return String(v);
  }

  function schemaOptions(f: RagNodeConfigField): string[] {
    return (f.options ?? []).map(o => String(o));
  }

  function syncLabelDraftToFlow() {
    if (!selectedNodeId.value) return;
    const sid = selectedNodeId.value;
    const idx = flowNodes.value.findIndex(n => String(n.id) === sid);
    if (idx < 0) return;
    const cur = flowNodes.value[idx];
    const d = (cur.data ?? {}) as RagFlowNodeData;
    const nextLabel = labelDraft.value.trim() || d.nodeType;
    if (nextLabel === d.label && String(cur.label) === nextLabel) return;
    const nextData: RagFlowNodeData = { ...d, label: nextLabel };
    const nextNodes = [...flowNodes.value];
    nextNodes[idx] = { ...cur, label: nextLabel, data: nextData };
    flowNodes.value = nextNodes;
    onStructureChange();
  }

  const debouncedLabelSync = useDebounceFn(syncLabelDraftToFlow, 300);

  watch(labelDraft, () => {
    if (labelDraftProgrammatic.value) return;
    void debouncedLabelSync();
  });

  function syncConfigDraftToFlow() {
    if (!selectedNodeId.value) return;
    let parsed: Record<string, unknown>;
    try {
      parsed = Json5.parse(configDraft.value || '{}') as Record<string, unknown>;
    } catch {
      if (configDraft.value.trim()) {
        window.$message?.warning('config JSON 无法解析，已保留节点原配置');
      }
      return;
    }
    const sid = selectedNodeId.value;
    const idx = flowNodes.value.findIndex(n => String(n.id) === sid);
    if (idx < 0) return;

    const cur = flowNodes.value[idx];
    const d = (cur.data ?? {}) as RagFlowNodeData;
    if (JSON.stringify(d.config ?? {}) === JSON.stringify(parsed)) return;

    const nextData: RagFlowNodeData = {
      ...d,
      config: parsed
    };
    const nextNodes = [...flowNodes.value];
    nextNodes[idx] = {
      ...cur,
      label: nextData.label,
      data: nextData
    };
    flowNodes.value = nextNodes;
    onStructureChange();
  }

  const debouncedSyncConfigToFlow = useDebounceFn(syncConfigDraftToFlow, 350);

  watch(configDraft, () => {
    if (configDraftProgrammatic.value) return;
    if (hasConfigSchema.value) return;
    void debouncedSyncConfigToFlow();
  });

  function pushLocalSchemaToFlow() {
    const id = selectedNodeId.value;
    if (!id) return;
    const idx = flowNodes.value.findIndex(n => String(n.id) === id);
    if (idx < 0) return;
    const cur = flowNodes.value[idx];
    const d = (cur.data ?? {}) as RagFlowNodeData;
    const next = { ...localSchemaConfig.value };
    if (JSON.stringify(d.config ?? {}) === JSON.stringify(next)) return;
    const nextData: RagFlowNodeData = { ...d, config: next };
    const nextNodes = [...flowNodes.value];
    nextNodes[idx] = { ...cur, data: nextData };
    flowNodes.value = nextNodes;
    onStructureChange();
    configDraftProgrammatic.value = true;
    configDraft.value = JSON.stringify(next, null, 2);
    nextTick(() => {
      configDraftProgrammatic.value = false;
    });
  }

  const debouncedPushLocalSchema = useDebounceFn(pushLocalSchemaToFlow, 320);

  watch(
    localSchemaConfig,
    () => {
      if (localSchemaProgrammatic.value || !selectedNodeId.value) return;
      if (!hasConfigSchema.value) return;
      void debouncedPushLocalSchema();
    },
    { deep: true }
  );

  function onNodeSelected(n: Node) {
    selectedNodeId.value = String(n.id);
    const d = (n.data ?? {}) as RagFlowNodeData;
    configDraftProgrammatic.value = true;
    labelDraftProgrammatic.value = true;
    localSchemaProgrammatic.value = true;
    configDraft.value = JSON.stringify(d.config ?? {}, null, 2);
    labelDraft.value = d.label ?? d.nodeType;
    rebuildLocalSchemaConfig();
    nextTick(() => {
      configDraftProgrammatic.value = false;
      labelDraftProgrammatic.value = false;
      localSchemaProgrammatic.value = false;
    });
  }

  function clearSelectionDrafts() {
    localSchemaConfig.value = {};
  }

  function resetDraftsAfterClearCanvas() {
    configDraftProgrammatic.value = true;
    labelDraftProgrammatic.value = true;
    configDraft.value = '{}';
    labelDraft.value = '';
    nextTick(() => {
      configDraftProgrammatic.value = false;
      labelDraftProgrammatic.value = false;
    });
  }

  function applyConfigDraftNow() {
    if (!selectedNodeId.value) {
      window.$message?.warning('请先在画布中点击选择一个节点');
      return;
    }
    let parsed: Record<string, unknown>;
    try {
      parsed = Json5.parse(configDraft.value || '{}') as Record<string, unknown>;
    } catch {
      window.$message?.error('JSON 解析失败');
      return;
    }
    if (hasConfigSchema.value) {
      localSchemaProgrammatic.value = true;
      localSchemaConfig.value = { ...parsed };
      nextTick(() => {
        localSchemaProgrammatic.value = false;
        pushLocalSchemaToFlow();
      });
    } else {
      syncConfigDraftToFlow();
    }
    window.$message?.success('config 已同步');
  }

  return {
    labelDraft,
    configDraft,
    configDraftProgrammatic,
    labelDraftProgrammatic,
    localSchemaProgrammatic,
    localSchemaConfig,
    selectedNode,
    selectedNodeMeta,
    hasConfigSchema,
    patchSchemaField,
    schemaStrValue,
    schemaOptions,
    rebuildLocalSchemaConfig,
    onNodeSelected,
    clearSelectionDrafts,
    resetDraftsAfterClearCanvas,
    applyConfigDraftNow
  };
}
