import { ref } from 'vue';
import {
  fetchRagWorkflowDelete,
  fetchRagWorkflowGet,
  fetchRagWorkflowList,
  fetchRagWorkflowSave
} from '@/service/api';
import type {
  RagWorkflowStoredDocument,
  RagWorkflowSummary
} from '@/types/ragWorkflow';
import { messageFromAxios } from '../utils/apiError';
import { flowToSavePayload } from '../utils/workflowTransform';
import type { Edge, Node } from '@vue-flow/core';
import type { Ref } from 'vue';

export function useWorkflowStore(options: {
  flowNodes: Ref<Node[]>;
  flowEdges: Ref<Edge[]>;
  workflowId: Ref<string>;
  workflowDisplayName: Ref<string>;
  workflowDescription: Ref<string>;
  workflowInputJson: Ref<string>;
  applyLoadedDocument: (doc: RagWorkflowStoredDocument) => void;
}) {
  const {
    flowNodes,
    flowEdges,
    workflowId,
    workflowDisplayName,
    workflowDescription,
    workflowInputJson,
    applyLoadedDocument
  } = options;

  const saveLoading = ref(false);
  const loadDialogVisible = ref(false);
  const loadListLoading = ref(false);
  const savedWorkflowList = ref<RagWorkflowSummary[]>([]);

  async function saveWorkflow() {
    const wid = workflowId.value.trim();
    if (!wid) {
      window.$message?.warning('请填写 workflow_id');
      return;
    }
    saveLoading.value = true;
    try {
      const payload = flowToSavePayload(
        flowNodes.value,
        flowEdges.value,
        workflowId.value.trim(),
        workflowDisplayName.value.trim(),
        workflowDescription.value.trim(),
        workflowInputJson.value
      );
      await fetchRagWorkflowSave(payload);
      window.$message?.success('工作流已保存');
    } catch (e) {
      window.$message?.error(messageFromAxios(e));
    } finally {
      saveLoading.value = false;
    }
  }

  async function listSavedWorkflows() {
    loadListLoading.value = true;
    try {
      const res = await fetchRagWorkflowList();
      savedWorkflowList.value = [...res.workflows];
    } catch (e) {
      window.$message?.error(messageFromAxios(e));
    } finally {
      loadListLoading.value = false;
    }
  }

  async function openLoadDialog() {
    loadDialogVisible.value = true;
    await listSavedWorkflows();
  }

  async function loadWorkflowByIdent(workflowIdent: string) {
    loadListLoading.value = true;
    try {
      const doc = await fetchRagWorkflowGet(workflowIdent);
      applyLoadedDocument(doc);
      loadDialogVisible.value = false;
      window.$message?.success(`已加载：${doc.workflow_id}`);
    } catch (e) {
      window.$message?.error(messageFromAxios(e));
    } finally {
      loadListLoading.value = false;
    }
  }

  async function deleteSavedWorkflowCurrent() {
    const wid = workflowId.value.trim();
    if (!wid) {
      window.$message?.warning('请填写要删除的 workflow_id');
      return;
    }
    try {
      await window.$messageBox?.confirm(`确定删除已保存的工作流 "${wid}" 吗？`, '删除工作流', {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      });
    } catch {
      return;
    }
    try {
      await fetchRagWorkflowDelete(wid);
      window.$message?.success('已删除');
    } catch (e) {
      window.$message?.error(messageFromAxios(e));
    }
  }

  return {
    saveLoading,
    loadDialogVisible,
    loadListLoading,
    savedWorkflowList,
    saveWorkflow,
    listSavedWorkflows,
    openLoadDialog,
    loadWorkflowByIdent,
    deleteSavedWorkflowCurrent
  };
}
