import type { AxiosError } from 'axios';
import { ref } from 'vue';
import { fetchRagWorkflowRun, fetchRagWorkflowRunDetail } from '@/service/api';
import type { RagRunHistoryDetail, RagWorkflowRunPayload, RagWorkflowRunResult } from '@/types/ragWorkflow';
import { formatFastApiDetail } from '../utils/apiError';
import { stringifyPretty } from '../utils/jsonHelper';
import { safeParseJson5 } from '../utils/jsonHelper';

export type RunStatus = 'idle' | 'running' | 'success' | 'error';

export function useWorkflowRun(options: {
  refreshRunHistory: () => Promise<void>;
}) {
  const { refreshRunHistory } = options;

  const runLoading = ref(false);
  const lastRunRaw = ref('');
  const runErrorMsg = ref('');
  const runStatus = ref<RunStatus>('idle');

  function formatRun(res: RagWorkflowRunResult): string {
    return stringifyPretty(res);
  }

  /** 以服务端落盘记录为准刷新「上次运行」展示（修正 HTTP 断连/响应截断导致的 UI 偏差）。 */
  async function syncRunStateFromServer(runId: string): Promise<RagRunHistoryDetail | null> {
    const rid = runId.trim();
    if (!rid) return null;
    try {
      const detail = await fetchRagWorkflowRunDetail(rid);
      lastRunRaw.value = stringifyPretty(detail);
      runStatus.value = detail.success ? 'success' : detail.running ? 'running' : 'error';
      runErrorMsg.value = detail.error || '';
      return detail;
    } catch {
      return null;
    }
  }

  async function runWorkflow(
    payload: RagWorkflowRunPayload,
    inputJsonText: string,
    reconcileRunId?: string
  ): Promise<RagWorkflowRunResult | null> {
    runErrorMsg.value = '';
    const rawIn = inputJsonText.trim();
    if (rawIn && safeParseJson5(inputJsonText) === null) {
      runErrorMsg.value = '入口 input_data JSON 解析失败';
      runStatus.value = 'error';
      window.$message?.error(runErrorMsg.value);
      return null;
    }

    runLoading.value = true;
    lastRunRaw.value = '';
    runStatus.value = 'running';

    const fallbackId = (reconcileRunId || payload.run_id || '').trim();

    try {
      const res = await fetchRagWorkflowRun(payload);
      lastRunRaw.value = formatRun(res);
      runStatus.value = res.success ? 'success' : 'error';
      return res;
    } catch (e) {
      const ax = e as AxiosError<{ detail?: unknown }>;
      runErrorMsg.value = formatFastApiDetail(ax.response?.data?.detail) || ax.message || String(e);
      runStatus.value = 'error';
      if (fallbackId) {
        const recovered = await syncRunStateFromServer(fallbackId);
        if (recovered) {
          window.$message?.warning('运行请求已中断，已从服务端运行记录恢复展示（与 run_id 同步）');
          return null;
        }
      }
      window.$message?.error(runErrorMsg.value);
      lastRunRaw.value = '';
      return null;
    } finally {
      runLoading.value = false;
      await refreshRunHistory();
    }
  }

  function isWorkflowEndLike(nodeId: string, data: Record<string, unknown> | undefined): boolean {
    const nid = nodeId.trim().toLowerCase();
    const d = data ?? {};
    // workflow.end 的典型输出：{"final_output": ..., "summary": {"keys": [...]}}
    if ('final_output' in d) return true;
    if (nid === 'end' || nid.endsWith('.end') || nid.includes('workflow.end')) return true;
    return false;
  }

  function summarizeOneNode(nodeId: string, data: Record<string, unknown> | undefined): string {
    if (!data || typeof data !== 'object') return `${nodeId} | 无数据`;

    const answer = data.answer;
    if (typeof answer === 'string' && answer.trim()) {
      return answer.trim().slice(0, 480);
    }

    if ('route_summary' in data) {
      const rs = (data.route_summary ?? {}) as Record<string, unknown>;
      const routes = (data.routes ?? {}) as Record<string, unknown>;
      const groupDist = (rs.group_distribution ?? {}) as Record<string, unknown>;
      const groups = Object.entries(groupDist)
        .map(([k, n]) => `${k}:${n}`)
        .slice(0, 6)
        .join(', ');
      const routeCounts = Object.entries(routes)
        .map(([k, v]) => `${k}:${Array.isArray(v) ? v.length : 0}`)
        .slice(0, 6)
        .join(', ');
      return [
        'content.route',
        `total=${String(rs.total_items ?? '-')}`,
        `routed=${String(rs.routed_items ?? '-')}`,
        `unrouted=${String(rs.unrouted_items ?? '-')}`,
        groups ? `groups=[${groups}]` : '',
        routeCounts ? `routes=[${routeCounts}]` : ''
      ]
        .filter(Boolean)
        .join(' | ')
        .slice(0, 480);
    }

    if ('embedding_summary' in data) {
      const es = (data.embedding_summary ?? {}) as Record<string, unknown>;
      const pd = (es.pipeline_distribution ?? {}) as Record<string, unknown>;
      const pp = (es.provider_distribution ?? {}) as Record<string, unknown>;
      const pds = Object.entries(pd)
        .map(([k, n]) => `${k}:${n}`)
        .slice(0, 6)
        .join(', ');
      const pps = Object.entries(pp)
        .map(([k, n]) => `${k}:${n}`)
        .slice(0, 6)
        .join(', ');
      return [
        'embedding.index',
        `total=${String(es.total_records ?? '-')}`,
        `with_vector=${String(es.with_vector ?? '-')}`,
        `without_vector=${String(es.without_vector ?? '-')}`,
        pds ? `pipeline=[${pds}]` : '',
        pps ? `provider=[${pps}]` : ''
      ]
        .filter(Boolean)
        .join(' | ')
        .slice(0, 480);
    }

    if ('merge_summary' in data || Array.isArray(data.unified_results)) {
      const ms = (data.merge_summary ?? {}) as Record<string, unknown>;
      const sd = (ms.source_distribution ?? {}) as Record<string, unknown>;
      const dist = Object.keys(sd).join('/');
      const unified = Array.isArray(data.unified_results) ? data.unified_results.length : 0;
      return [
        'retrieval.merge',
        `in=${String(ms.total_input ?? '-')}`,
        `out=${String(ms.total_output ?? unified)}`,
        `dedup=${String(ms.deduplicated ?? 0)}`,
        dist ? `src=${dist}` : ''
      ]
        .filter(Boolean)
        .join(' | ')
        .slice(0, 480);
    }

    if ('context_summary' in data || typeof data.context_str === 'string' || Array.isArray(data.context_blocks)) {
      const cs = (data.context_summary ?? {}) as Record<string, unknown>;
      return [
        'context.build',
        `input=${String(cs.input_results ?? '-')}`,
        `used=${String(cs.used_results ?? '-')}`,
        `chars=${String(cs.context_chars ?? (typeof data.context_str === 'string' ? data.context_str.length : 0))}`
      ]
        .join(' | ')
        .slice(0, 480);
    }

    if ('retrieve_summary' in data || Array.isArray(data.vector_results)) {
      const rs = (data.retrieve_summary ?? {}) as Record<string, unknown>;
      const vd = (rs.backend_distribution ?? {}) as Record<string, unknown>;
      const backendDist = Object.entries(vd)
        .map(([k, n]) => `${k}:${n}`)
        .slice(0, 6)
        .join(', ');
      const warns = Array.isArray(rs.warnings) ? rs.warnings.length : 0;
      const rows = Array.isArray(data.vector_results) ? data.vector_results.length : 0;
      return [
        'vector.retrieve',
        `total=${String(rs.total ?? rows)}`,
        backendDist ? `backend=[${backendDist}]` : '',
        warns > 0 ? `warnings=${warns}` : ''
      ]
        .filter(Boolean)
        .join(' | ')
        .slice(0, 480);
    }

    if ('process_summary' in data) {
      const ps = (data.process_summary ?? {}) as Record<string, unknown>;
      return [
        'multimodal.process',
        `candidate=${String(ps.candidate_count ?? '-')}`,
        `processed=${String(ps.processed_count ?? '-')}`,
        `vlm=${String(ps.vlm_used_count ?? 0)}`,
        `fallback=${String(ps.fallback_count ?? 0)}`
      ]
        .join(' | ')
        .slice(0, 480);
    }

    if ('filter_summary' in data) {
      const fs = (data.filter_summary ?? {}) as Record<string, unknown>;
      const kept = (fs.kept_types ?? {}) as Record<string, unknown>;
      const keptPairs = Object.entries(kept)
        .map(([k, n]) => `${k}:${n}`)
        .slice(0, 6)
        .join(', ');
      return [
        'content.filter',
        `before=${String(fs.before_count ?? '-')}`,
        `after=${String(fs.after_count ?? '-')}`,
        keptPairs ? `kept=[${keptPairs}]` : ''
      ]
        .filter(Boolean)
        .join(' | ')
        .slice(0, 480);
    }

    if ('parse_status' in data || Array.isArray(data.content_list)) {
      const contentList = Array.isArray(data.content_list) ? data.content_list : [];
      return [
        `document.parse: ${String(data.parse_status ?? 'unknown')}`,
        `content_list=${contentList.length}`,
        typeof data.source_path === 'string' && data.source_path ? `source=${data.source_path}` : ''
      ]
        .filter(Boolean)
        .join(' | ')
        .slice(0, 480);
    }

    const keys = Object.keys(data).slice(0, 8);
    return `${nodeId} | keys=[${keys.join(', ')}]`.slice(0, 480);
  }

  /** 全局摘要：取最后一个非 workflow.end 节点结果（动态） */
  function runAnswerSnippet(rawJson: string): string {
    if (!rawJson.trim()) return '';
    try {
      const o = JSON.parse(rawJson) as Record<string, unknown>;
      const nr = o.node_results as Record<string, { data?: Record<string, unknown> }> | undefined;
      if (!nr) return '';
      const entries = Object.entries(nr);
      if (!entries.length) return '';

      // node_results 在后端按执行顺序写入；这里从后往前找最后一个非 end 节点
      for (let i = entries.length - 1; i >= 0; i -= 1) {
        const [nodeId, one] = entries[i];
        const data = one?.data;
        if (isWorkflowEndLike(nodeId, data)) continue;
        return summarizeOneNode(nodeId, data);
      }

      // 全是 end-like 时退化用最后一个
      const [lastId, lastOne] = entries[entries.length - 1];
      return summarizeOneNode(lastId, lastOne?.data);
    } catch {
      return '';
    }
  }

  return {
    runLoading,
    lastRunRaw,
    runErrorMsg,
    runStatus,
    runWorkflow,
    formatRun,
    syncRunStateFromServer,
    runAnswerSnippet
  };
}
