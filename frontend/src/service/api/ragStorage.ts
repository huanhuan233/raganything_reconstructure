/** 存储资源 API（backend_api /api/storage） */

import { ragWorkflowRequest } from '../request';

export type MilvusCollectionRow = { name: string; description?: string; num_entities?: number };
export type Neo4jDatabaseRow = { name: string; currentStatus?: string };

export type StorageApiEnvelope<T> = { success: boolean; data?: T; error?: string | null };
export type KnowledgeDiscoverVectorBackend = {
  backend: string;
  collections: string[];
  warnings: string[];
};
export type KnowledgeDiscoverGraphBackend = {
  backend: string;
  workspaces: string[];
  labels?: string[];
  warnings: string[];
};
export type KnowledgeDiscoverResponse = {
  vector_backends: KnowledgeDiscoverVectorBackend[];
  graph_backends: KnowledgeDiscoverGraphBackend[];
};

export function fetchMilvusCollections() {
  return ragWorkflowRequest<StorageApiEnvelope<MilvusCollectionRow[]>>({
    url: '/api/storage/milvus/collections/',
    method: 'get',
    timeout: 30000
  });
}

export function fetchMilvusCollectionCreate(body: {
  name: string;
  dimension: number;
  metric_type?: string;
  index_type?: string;
  auto_create_index?: boolean;
}) {
  return ragWorkflowRequest<StorageApiEnvelope<{ name: string }>>({
    url: '/api/storage/milvus/collections/',
    method: 'post',
    data: body,
    timeout: 60000
  });
}

export function fetchNeo4jDatabases() {
  return ragWorkflowRequest<StorageApiEnvelope<Neo4jDatabaseRow[]>>({
    url: '/api/storage/neo4j/databases/',
    method: 'get'
  });
}

/** 多库环境：CREATE DATABASE（需 Neo4j 支持；编排 UI 默认不用） */
export function fetchNeo4jDatabaseCreate(body: { name: string; auto_create_constraints?: boolean }) {
  return ragWorkflowRequest<StorageApiEnvelope<{ name: string }>>({
    url: '/api/storage/neo4j/databases/',
    method: 'post',
    data: body
  });
}

/** 单库内图分区：校验 database + 可选索引/约束（不创建 database） */
export function fetchNeo4jGraphPartitionEnsure(body: {
  database?: string;
  partition: string;
  auto_create_constraints?: boolean;
}) {
  return ragWorkflowRequest<StorageApiEnvelope<{ database: string; partition: string }>>({
    url: '/api/storage/neo4j/graph-partitions/',
    method: 'post',
    data: body
  });
}

export function fetchEmbeddingDimHint() {
  return ragWorkflowRequest<StorageApiEnvelope<{ dimension: number }>>({
    url: '/api/storage/embedding-dim/',
    method: 'get'
  });
}

export function fetchKnowledgeDiscover() {
  return ragWorkflowRequest<KnowledgeDiscoverResponse>({
    url: '/api/knowledge/discover',
    method: 'get'
  });
}
