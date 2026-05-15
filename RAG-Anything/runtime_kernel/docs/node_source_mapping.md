# backend_runtime 节点源码映射（26 节点）

本文描述当前 `backend_runtime` 可编排节点与 RAGAnything / LightRAG 源码阶段的对应关系。

## 说明

- `raganything.insert` 是当前**粗粒度真实节点**：内部已经覆盖 parse / chunk / extract / merge / index / multimodal process 等能力。
- `rag.query` 是当前**粗粒度真实查询节点**：内部包含 retrieve / context / generate 主流程。
- 本次新增细粒度节点属于“源码阶段映射”：用于 DAG 拆分设计与可观测，不代表已经接入真实函数调用。
- 后续建议逐步将粗粒度节点内部能力剥离到细粒度节点，并用工作流显式编排连接。

## 节点清单

| node_type | implementation_status | 对应源码文件 | 对应源码函数/阶段 | 当前是否真实执行 | 后续真实化建议 |
|---|---|---|---|---|---|
| `workflow.start` | real | `backend_runtime/nodes/workflow_start_node.py` | 编排入口 | 是 | 可补充 trace/span 注入与 run 级别上下文初始化 |
| `workflow.end` | real | `backend_runtime/nodes/workflow_end_node.py` | 编排出口 | 是 | 可补充标准化 final_output 聚合协议 |
| `document.parse` | placeholder | `backend_runtime/nodes/document_parse_node.py` | 未来映射解析器管线 | 否（mock） | 接入 ParserAdapter / MinerU 实际解析 |
| `doc.status.update` | placeholder | `backend_runtime/nodes/doc_status_update_node.py` | 文档状态流转 | 否（透传） | 接入 doc_status 状态机与失败回写 |
| `content.normalize` | partial | `backend_runtime/nodes/content_normalize_node.py` | DocumentAdapter 归一化 | 部分真实 | 增补端到端校验与异常兜底策略 |
| `chunk.split` | placeholder | `backend_runtime/nodes/chunk_split_node.py` | `lightrag/operate.py::chunking_by_token_size` | 否（透传） | 接入 token 切分实现与 chunk 元数据输出 |
| `entity.extract` | placeholder | `backend_runtime/nodes/entity_extract_node.py` | `lightrag/operate.py::extract_entities`（实体子阶段） | 否（透传） | 接入实体抽取模型与结构化产物 |
| `relation.extract` | placeholder | `backend_runtime/nodes/relation_extract_node.py` | `lightrag/operate.py::extract_entities`（关系子阶段） | 否（透传） | 将关系抽取从实体流程中拆出独立可观测步骤 |
| `entity.merge` | placeholder | `backend_runtime/nodes/entity_merge_node.py` | merge_nodes_and_edges（实体归并语义） | 否（透传） | 接入实体去重/同义归并规则 |
| `relation.merge` | placeholder | `backend_runtime/nodes/relation_merge_node.py` | merge_nodes_and_edges（关系归并语义） | 否（透传） | 接入关系冲突消解与权重融合 |
| `graph.merge` | placeholder | `backend_runtime/nodes/graph_merge_node.py` | merge_nodes_and_edges（图级聚合语义） | 否（透传） | 接入整图一致化与图存储写回 |
| `embedding.index` | placeholder | `backend_runtime/nodes/embedding_index_node.py` | chunks/entities/relationships vdb upsert | 否（透传） | 接入 embedding 计算与三类向量库写入 |
| `storage.persist` | placeholder | `backend_runtime/nodes/storage_persist_node.py` | `index_done_callback` / `finalize_storages` | 否（透传） | 接入持久化收尾、回调与一致性确认 |
| `lightrag.insert` | real | `backend_runtime/nodes/lightrag_insert_node.py` | `insert_document` | 是 | 增补批量与失败重试策略 |
| `raganything.insert` | real | `backend_runtime/nodes/raganything_insert_node.py` | `process_document` | 是 | 后续拆分粗粒度内含阶段到细粒度节点 |
| `multimodal.process` | placeholder | `backend_runtime/nodes/multimodal_process_node.py` | 多模态预处理阶段 | 否（透传） | 接入 VLM/OCR 后处理与跨模态对齐 |
| `visual.recover` | placeholder | `backend_runtime/nodes/visual_recover_node.py` | VLM enhanced query 视觉资源回收 | 否（透传） | 接入 image path dereference / base64 处理 |
| `keyword.extract` | placeholder | `backend_runtime/nodes/keyword_extract_node.py` | `get_keywords_from_query` | 否（透传） | 接入 query 关键词抽取与标准化 |
| `vector.retrieve` | placeholder | `backend_runtime/nodes/vector_retrieve_node.py` | naive/kg 查询向量召回阶段 | 否（透传） | 接入语义召回与召回分数结构化输出 |
| `graph.retrieve` | placeholder | `backend_runtime/nodes/graph_retrieve_node.py` | `kg_query` / `_build_query_context` 图检索阶段 | 否（透传） | 接入图扩展召回与路径证据返回 |
| `retrieval.merge` | placeholder | `backend_runtime/nodes/retrieval_merge_node.py` | `_build_query_context` 前多路融合语义 | 否（透传） | 接入多路召回去重与融合打分 |
| `rerank` | partial | `backend_runtime/nodes/rerank_node.py` | Hybrid Retrieval 重排阶段（runtime/lightrag） | 是（双模式） | 继续增强真实多模态模型打分与批量推理性能 |
| `context.build` | placeholder | `backend_runtime/nodes/context_build_node.py` | `_build_context_str` | 否（mock） | 接入真实上下文拼接模板与 token 控制 |
| `llm.generate` | placeholder | `backend_runtime/nodes/llm_generate_node.py` | 查询尾部 LLM 生成阶段 | 否（mock） | 接入真实 LLM 调用与可追踪输出 |
| `rag.query` | real | `backend_runtime/nodes/rag_query_node.py` | `lightrag` / `raganything` query dispatch | 是 | 拆分为 keyword/retrieve/rerank/context/generate 子节点 |
| `rag.delete` | real | `backend_runtime/nodes/rag_delete_node.py` | `delete_document` | 是 | 增补删除后索引一致性与审计日志 |

## 迁移建议（从粗粒度到细粒度）

1. 保留 `raganything.insert` 与 `rag.query` 作为稳定兜底路径。
2. 逐步在新 workflow 中引入细粒度占位节点，先打通观测与日志。
3. 按链路拆解优先级接入真实实现：`chunk.split -> entity/relation.extract -> embedding.index -> vector/graph.retrieve -> rerank -> context.build -> llm.generate`。
4. 在每个节点真实化后，将 `implementation_status` 从 `placeholder` 更新为 `partial` 或 `real`。
