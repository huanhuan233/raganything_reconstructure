# State-driven Nodes Report

## 已完成 Runtime 化的节点

- `document.parse` (`workflow_nodes/parsing/document_parse_node.py`)
  - 主输出写入 `context.content_pool` 的 `parsed_document`。
  - 写入时自动发 `content_written` 事件（写入 `context.trace_events`）。
- `chunk.split` (`workflow_nodes/parsing/chunk_split_node.py`)
  - 主输入从 `parsed_document` 读取（优先 `ContentAccess.get_parsed_document`）。
  - 主输出写入 `chunks`。
- `embedding.index` (`workflow_nodes/storage/embedding_index_node.py`)
  - 主输入从 `chunks` 读取。
  - 主输出写入 `embeddings`。
  - 支持读取 `context.variable_pool`：`embedding_provider`、`vector_backend`。
- `graph.retrieve` (`workflow_nodes/retrieval/graph_retrieve_node.py`)
  - 主输入从 `context.variable_pool` 读取：`query`、`top_k`。
  - 主输出写入 `retrieval_results`。
- `retrieval.merge` (`workflow_nodes/retrieval/retrieval_merge_node.py`)
  - 读取 `retrieval_results`、`rerank_results`（图检索结果兼容 legacy 输入 `graph_results`）。
  - 输出 `merged_results`，并回写 `retrieval_results`。

## 已移除的 Legacy 依赖（主路径）

- `WorkflowRunner` 不再将 parent `result.data` 直接传给 `node.run`，改为调度 `node.execute(context)`。
- 第一批节点主读写路径不再依赖 `input_data` 作为唯一数据源，改为优先读取 `context.content_pool` / `context.variable_pool`。
- 节点内容读写统一走 `ContentAccess`，避免散落硬编码 bucket 名称。

## 当前仍存在 Legacy 依赖的节点

以下节点仍显式使用 `input_data`（通过 `*_node.py` 扫描）：

- `vector_retrieve_node.py`
- `storage_persist_node.py`
- `rag_query_node.py`
- `workflow_start_node.py`
- `workflow_end_node.py`
- `context_build_node.py`
- `rag_delete_node.py`
- `raganything_insert_node.py`
- `lightrag_insert_node.py`
- `doc_status_update_node.py`
- `rerank_node.py`
- `knowledge_select_node.py`
- `keyword_extract_node.py`
- `content_normalize_node.py`
- `content_filter_node.py`
- `visual_recover_node.py`
- `multimodal_process_node.py`
- `content_route_node.py`
- `llm_generate_node.py`
- `industrial/*_node.py`
- `graph/*_node.py`

说明：

- 本阶段通过 `runtime_kernel/runtime_state/legacy_bridge.py` 保留兼容层，避免一次性改造全部节点导致运行中断。

## Content 生命周期图

- `parsed_document`
  -> `chunks`
  -> `embeddings`
  -> `retrieval_results`
  -> `merged_results`
  -> `generated_content`（后续节点）

`content_lifecycle` 注册表：`runtime_kernel/runtime_state/content_lifecycle.py`

## 下一阶段建议

- 继续把 `vector.retrieve / rerank / context.build / llm.generate` 迁移为纯 state-driven。
- 在 `ContentAccess` 中增加 typed reference（content id）与版本号，支持 checkpoint/replay。
- 将 runtime trace 事件从内存列表扩展为可查询存储模型。
- 在不引入 scheduler 的前提下先补齐 barrier 元数据与分支 join 语义。
