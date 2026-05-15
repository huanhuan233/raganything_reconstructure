# Runtime Kernel 架构迁移报告

## 1. 原目录问题

- Runtime、Node、Adapter、API 分层耦合：`backend_runtime` 同时承载执行内核、节点实现、存储管理。
- Node 与 third-party 耦合：节点层存在直接 `import lightrag` 的路径，边界不清晰。
- API 与运行时路径耦合：`backend_api` 直接依赖 `backend_runtime.*`，且存储目录绑定在 API 包内。
- Third-party boundary 不清晰：`raganything` 作为源码目录与平台代码同层，运行时边界不明显。

## 2. 新目录结构

已按目标结构收敛为以下主干（`frontend/` 保持原位）：

- `runtime_kernel/`
  - `graph_engine/`, `runtime_state/`, `scheduler/`, `variable_pool/`, `event_stream/`
  - `execution_context/`, `node_runtime/`, `graph/`, `entities/`, `protocols/`
- `workflow_nodes/`
  - `parsing/`, `retrieval/`, `graph/`, `storage/`, `llm/`, `multimodal/`, `industrial/`, `workflow/`
- `adapters/`
  - 原 `lightrag/`、`raganything/` 保留
  - 新增并迁入 `milvus/`、`neo4j/`、`runtime/`、`mineru/`（预留）
- `workflow_api/`
  - `routers/`, `services/`, `runtime_trace/`, `storage/`
- `workflow_storage/`
  - `runs/`, `workflows/`
- `workflow_trace/`（预留）
- `third_party/`
  - `raganything/`（源码迁入）
  - `graphon/`（源码迁入）
  - `lightrag/`（边界目录预留）

## 3. 文件迁移记录

核心迁移（节选）：

- `backend_runtime/core/execution_context.py`
  -> `runtime_kernel/execution_context/execution_context.py`
- `backend_runtime/core/workflow_runner.py`
  -> `runtime_kernel/graph_engine/workflow_runner.py`
- `backend_runtime/core/node_registry.py`
  -> `runtime_kernel/node_runtime/node_registry.py`
- `backend_runtime/core/base_node.py`
  -> `runtime_kernel/node_runtime/base_node.py`
- `backend_runtime/core/node_result.py`
  -> `runtime_kernel/entities/node_result.py`
- `backend_runtime/core/workflow_schema.py`
  -> `runtime_kernel/graph/workflow_schema.py`
- `backend_runtime/core/node_metadata.py`
  -> `runtime_kernel/entities/node_metadata.py`
- `backend_runtime/core/raganything_isolated.py`
  -> `runtime_kernel/protocols/raganything_isolated.py`

节点迁移（节选）：

- `backend_runtime/nodes/document_parse_node.py`
  -> `workflow_nodes/parsing/document_parse_node.py`
- `backend_runtime/nodes/chunk_split_node.py`
  -> `workflow_nodes/parsing/chunk_split_node.py`
- `backend_runtime/nodes/rag_query_node.py`
  -> `workflow_nodes/retrieval/rag_query_node.py`
- `backend_runtime/nodes/retrieval_merge_node.py`
  -> `workflow_nodes/retrieval/retrieval_merge_node.py`
- `backend_runtime/nodes/rerank_node.py`
  -> `workflow_nodes/retrieval/rerank_node.py`
- `backend_runtime/nodes/entity_relation_extract_node.py`
  -> `workflow_nodes/graph/entity_relation_extract_node.py`
- `backend_runtime/nodes/entity_merge_node.py`
  -> `workflow_nodes/graph/entity_merge_node.py`
- `backend_runtime/nodes/relation_merge_node.py`
  -> `workflow_nodes/graph/relation_merge_node.py`
- `backend_runtime/nodes/graph_merge_node.py`
  -> `workflow_nodes/graph/graph_merge_node.py`
- `backend_runtime/nodes/graph_persist_node.py`
  -> `workflow_nodes/graph/graph_persist_node.py`
- `backend_runtime/nodes/storage_persist_node.py`
  -> `workflow_nodes/storage/storage_persist_node.py`
- `backend_runtime/nodes/embedding_index_node.py`
  -> `workflow_nodes/storage/embedding_index_node.py`
- `backend_runtime/nodes/multimodal_process_node.py`
  -> `workflow_nodes/multimodal/multimodal_process_node.py`
- `backend_runtime/nodes/content_route_node.py`
  -> `workflow_nodes/multimodal/content_route_node.py`
- `backend_runtime/nodes/workflow_start_node.py`
  -> `workflow_nodes/workflow/workflow_start_node.py`
- `backend_runtime/nodes/workflow_end_node.py`
  -> `workflow_nodes/workflow/workflow_end_node.py`
- `backend_runtime/nodes/context_build_node.py`
  -> `workflow_nodes/workflow/context_build_node.py`

存储/适配器迁移（节选）：

- `backend_runtime/storage/milvus_admin.py`
  -> `adapters/milvus/milvus_admin.py`
- `backend_runtime/storage/neo4j_admin.py`
  -> `adapters/neo4j/neo4j_admin.py`
- `backend_runtime/storage/env_resolution.py`
  -> `adapters/runtime/env_resolution.py`
- `backend_runtime/storage/persist.py`
  -> `adapters/runtime/persist.py`
- `backend_runtime/nodes/industrial/industrial_graph_persist_adapter.py`
  -> `adapters/runtime/industrial_graph_persist_adapter.py`

API 与存储迁移（节选）：

- `backend_api/main.py`
  -> `workflow_api/main.py`
- `backend_api/runtime_service.py`
  -> `workflow_api/runtime_service.py`
- `backend_api/raganything_runtime.py`
  -> `workflow_api/raganything_runtime.py`
- `backend_api/routers/*`
  -> `workflow_api/routers/*`
- `backend_api/run_store.py`
  -> `workflow_api/run_store.py`
- `backend_api/workflow_store.py`
  -> `workflow_api/workflow_store.py`
- `backend_runtime/templates/default_workflows.py`
  -> `workflow_storage/workflows/default_workflows.py`

Third-party 迁移：

- `raganything/`
  -> `third_party/raganything/`
- `<repo-root>/graphon/`
  -> `RAG-Anything/third_party/graphon/`

同时已移除旧目录：`backend_runtime/`、`backend_api/`。

## 4. 高危 import 检查

检查范围：`runtime_kernel/`、`workflow_nodes/`。

- 直接 `import lightrag`：未发现
- 直接 `import raganything`：未发现
- 直接 `import third_party.*`：未发现

结论：Runtime Kernel / Workflow Nodes 已满足边界约束：

`Runtime Kernel -> Workflow Nodes -> Adapters -> Third-party`

补充：`workflow_api/` 与 `adapters/` 中仍存在对第三方依赖的直接导入，这是当前边界设计允许的位置。

## 5. TODO（后续阶段）

- `runtime_kernel/runtime_state/`：实现运行态快照与恢复机制。
- `runtime_kernel/scheduler/`：实现可插拔调度器（串行/并行/优先级）。
- `runtime_kernel/event_stream/`：实现统一事件总线与订阅协议。
- `runtime_kernel/graph_engine/dispatcher`：补齐 dispatcher 与 graph_execution 分层。
- `workflow_trace/`：接入实时 trace 持久化与查询模型。
- `third_party/lightrag/`：确认本地源码托管策略（子模块/镜像/外部依赖）。

