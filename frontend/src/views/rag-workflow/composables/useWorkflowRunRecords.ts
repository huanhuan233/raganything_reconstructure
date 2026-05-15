import { ref, type Ref } from 'vue';
import {
  fetchRagWorkflowRunDelete,
  fetchRagWorkflowRunDetail,
  fetchRagWorkflowRuns
} from '@/service/api';
import type { RagRunHistoryDetail, RagRunHistorySummary } from '@/types/ragWorkflow';
import { messageFromAxios } from '../utils/apiError';
import { stringifyPretty } from '../utils/jsonHelper';

export function useWorkflowRunRecords(options: { workflowId: Ref<string>; filterByCurrentWorkflow: Ref<boolean> }) {
  const { workflowId, filterByCurrentWorkflow } = options;

  const runHistoryList = ref<RagRunHistorySummary[]>([]);
  const runHistoryLoading = ref(false);
  const runDetailVisible = ref(false);
  const runDetailLoading = ref(false);
  const runDetailFull = ref<RagRunHistoryDetail | null>(null);

  function prettyJson(val: unknown): string {
    return stringifyPretty(val);
  }

  async function refreshRunHistory() {
    runHistoryLoading.value = true;
    try {
      const wid = workflowId.value.trim();
      const res = await fetchRagWorkflowRuns(
        filterByCurrentWorkflow.value && wid ? wid : undefined
      );
      runHistoryList.value = [...res.runs];
    } catch (e) {
      window.$message?.error(messageFromAxios(e));
    } finally {
      runHistoryLoading.value = false;
    }
  }

  async function openRunDetail(row: RagRunHistorySummary) {
    runDetailLoading.value = true;
    runDetailFull.value = null;
    runDetailVisible.value = true;
    try {
      runDetailFull.value = await fetchRagWorkflowRunDetail(row.run_id);
    } catch (e) {
      window.$message?.error(messageFromAxios(e));
      runDetailVisible.value = false;
    } finally {
      runDetailLoading.value = false;
    }
  }

  async function deleteRunRecord(runId: string) {
    try {
      await window.$messageBox?.confirm(`确定删除运行记录 ${runId}？`, '删除运行记录', {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      });
    } catch {
      return;
    }
    try {
      await fetchRagWorkflowRunDelete(runId);
      window.$message?.success('已删除');
      if (runDetailVisible.value && runDetailFull.value?.run_id === runId) {
        runDetailVisible.value = false;
        runDetailFull.value = null;
      }
      await refreshRunHistory();
    } catch (e) {
      window.$message?.error(messageFromAxios(e));
    }
  }

  return {
    runHistoryList,
    runHistoryLoading,
    runDetailVisible,
    runDetailLoading,
    runDetailFull,
    prettyJson,
    refreshRunHistory,
    openRunDetail,
    deleteRunRecord
  };
}
