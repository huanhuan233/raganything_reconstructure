import type { Node } from '@vue-flow/core';
import type { RagFlowNodeData } from '@/types/ragWorkflow';
import { fetchMilvusCollectionCreate } from '@/service/api/ragStorage';

/**
 * 保存 / 运行前：对 storage.persist 节点在「新建」模式下调用后端创建接口。
 */
export async function ensureStoragePersistRemoteResources(nodes: Node[]): Promise<void> {
  for (const n of nodes) {
    const d = (n.data ?? {}) as RagFlowNodeData;
    if (String(d.nodeType || '') !== 'storage.persist') continue;
    const cfg = (d.config ?? {}) as Record<string, unknown>;
    const vs = (cfg.vector_storage ?? {}) as Record<string, unknown>;
    if (vs.backend === 'milvus' && vs.mode === 'create') {
      const name = String(vs.collection || '').trim();
      const dim = Number(vs.dimension) || 0;
      if (!name || dim <= 0) {
        throw new Error(`节点「${d.label || n.id}」：向量库新建需填写 collection 名称与有效维度`);
      }
      const res = await fetchMilvusCollectionCreate({
        name,
        dimension: dim,
        metric_type: String(vs.metric_type || 'COSINE'),
        index_type: String(vs.index_type || 'IVF_FLAT'),
        auto_create_index: vs.auto_create_index !== false
      });
      if (!res?.success) {
        throw new Error(res?.error || `Milvus 创建 collection 失败：${name}`);
      }
    }
  }
}
