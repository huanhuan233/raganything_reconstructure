# LightRAG 源码架构与调用链分析

> **分析范围**：当前项目虚拟环境内 `lightrag` 包（`RAG-Anything/.venv/lib/python3.12/site-packages/lightrag/`）。  
> **说明**：本文仅为阅读笔记与调用链梳理，**不包含对 LightRAG 源码的修改建议落地代码**。

---

## 1. 项目整体分层

| 层级 | 职责 | 主要位置 |
|------|------|----------|
| **总调度层** | 文档入队/流水线、查询入口、删除编排、存储类解析与 `LightRAG` 实例生命周期 | `lightrag.py` |
| **算法执行层** | 分块、实体关系抽取、图谱合并、检索上下文构建、朴素向量检索 | `operate.py`、`utils_graph.py`（图删除等辅助） |
| **存储抽象层** | `BaseKVStorage`、`BaseVectorStorage`、`BaseGraphStorage`、`DocStatusStorage` 等接口与 `QueryParam` | `base.py` |
| **存储实现层** | KV/向量/图/文档状态的具体后端 | `kg/*.py`（如 `nano_vector_db_impl.py`、`milvus_impl.py`、`neo4j_impl.py`、`json_kv_impl.py` 等） |
| **模型适配层** | 各厂商 LLM/Embedding 的异步调用、重试、可选 Langfuse | `llm/*.py`（核心为 `openai.py`，另有 `ollama.py`、`azure_openai.py` 等） |
| **Prompt 层** | 抽取、摘要、查询、关键词等模板字符串字典 `PROMPTS` | `prompt.py` |
| **API 服务层** | HTTP 服务、路由、鉴权、与 `LightRAG` 实例绑定 | `api/lightrag_server.py`、`api/routers/*.py` |

**存储注册表**：`kg/__init__.py` 中 `STORAGE_IMPLEMENTATIONS`、`STORAGES` 将逻辑名（如 `MilvusVectorDBStorage`）映射到 `kg` 子模块，供 `lightrag.py` 中 `_get_storage_class` 动态加载。

---

## 2. Insert 入库调用链

### 2.1 标准入口（文本整篇写入 + 流水线）

```
insert(...)
  → asyncio: ainsert(...)
ainsert(...)
  → apipeline_enqueue_documents(...)
  → apipeline_process_enqueue_documents(...)
       →（内部）process_document(...) 对每个待处理 doc_id
```

**`ainsert`**（`lightrag.py`）  
- `apipeline_enqueue_documents`：校验/生成 `doc_id`、去重、`doc_status` 初始为 `PENDING`，**`full_docs.upsert`** 写入正文，**`doc_status.upsert`**。  
- `apipeline_process_enqueue_documents`：从 `doc_status` 拉取待处理文档集合，并发受 `max_parallel_insert` 限制，对每个文档调用内嵌 **`process_document`**。

**`process_document` 主干**（`lightrag.py`，逻辑顺序）  

1. 从 **`full_docs.get_by_id(doc_id)`** 取正文。  
2. **`chunking_func(...)`**（默认 **`chunking_by_token_size`**，来自 `operate.py`，在 `LightRAG` 字段 `default_factory` 中挂载）→ 得到 chunk 字典（key 为 `chunk-` 前缀的 hash）。  
3. **`doc_status.upsert`** → `PROCESSING`，记录 `chunks_list` 等。  
4. **阶段一（并行）**  
   - `chunks_vdb.upsert(chunks)`  
   - `text_chunks.upsert(chunks)`  
5. **阶段二**  
   - `_process_extract_entities(chunks)`  
     → **`extract_entities(...)`**（`operate.py`）：逐 chunk LLM 抽取，内部 **`_process_extraction_result`** 解析为元数据。  
6. **`merge_nodes_and_edges(...)`**（`operate.py`）：写入图存储、实体/关系向量库、`full_entities`/`full_relations`、`entity_chunks`/`relation_chunks` 等索引。  
7. **`doc_status.upsert`** → `PROCESSED`。  
8. **`_insert_done()`**：对各存储 **`index_done_callback()`**（持久化/刷新）。

**`ainsert_custom_chunks`**（仍可用的自定义切片路径）：直接向 `chunks_vdb`、`text_chunks`、`full_docs` 等 `upsert` 并 **`_process_extract_entities`**（与流水线版阶段二对齐）。

```
ainsert_custom_chunks
  → full_docs / text_chunks / chunks_vdb 等 upsert（与标准路径略有差异，见源码）
  → _process_extract_entities → merge_nodes_and_edges（在旧路径中或通过 gather 并行）
```

---

## 3. Query 查询调用链

### 3.1 对外 API 关系

```
query(...)
  → aquery(...)
aquery(...)
  → aquery_llm(...)
  → 仅返回 llm_response 中的文本或流迭代器

query_data(...) / aquery_data(...)
  → 构造 only_need_context=True 的 QueryParam
  → 与 below 相同的 kg_query / naive_query / bypass 分支
  → 不调用生成阶段（或跳过最终 LLM），返回结构化 `raw_data`

aquery_llm(...)
  → 分支见下
  → _query_done()
```

### 3.2 模式 → 实现映射（`lightrag.py` + `base.py::QueryParam`）

| `QueryParam.mode` | 检索实现 | 说明 |
|-------------------|----------|------|
| `local` | `kg_query` | 依赖低阶关键词 → 偏重实体邻近上下文 |
| `global` | `kg_query` | 依赖高阶关键词 → 偏重关系与公司级信息 |
| `hybrid` | `kg_query` | local + global 路线在 `operate.py` 内合并 |
| `mix` | `kg_query` | 图谱检索 + **`chunks_vdb`** 向量块补充 |
| `naive` | `naive_query` | **仅** `chunks_vdb` 向量检索，实体/关系列表为空 |
| `bypass` | 无检索 | **直接**调用 `llm_model_func`，`data` 为空 |

### 3.3 `kg_query` 内部主路径（`operate.py`）

```
kg_query(...)
  → get_keywords_from_query(...)   # LLM + 可选 cache
  → _build_query_context(...)       # 图遍历 + VDB + chunk 拼装
  → _build_context_str(...)        # Token 预算与文本拼接（及 rerank 等）
  →（若非 only_need_*）拼装 PROMPTS["rag_response"] 等 → LLM 生成
```

### 3.4 `naive_query`（`operate.py`）

- 仅以查询文本做 embedding，`chunks_vdb.query` 取块，再走上下文构建与（可选）LLM。

**官方文档注释摘要**（`aquery_data` docstring，`lightrag.py`）：  
- **local**：低阶关键词主导的实体及相关 chunk  
- **global**：高阶关键词主导的关系及关联实体  
- **hybrid**：local 与 global 结果轮询式合并  
- **mix**：图谱数据 + 向量检索 chunk  
- **naive**：仅向量 chunk，entities/relationships 为空  
- **bypass**：不检索，直接 LLM  

---

## 4. Delete 删除调用链（`adelete_by_doc_id`）

**入口**：`LightRAG.adelete_by_doc_id(doc_id, delete_llm_cache=False)`（`lightrag.py`）

**流水线互斥**：通过 `pipeline_status`（`kg/shared_storage` 命名空间）判断当前任务是否为删除作业，避免与普通 insert 流水线冲突。

**主要步骤（按源码顺序概括为链）**

```
adelete_by_doc_id
  → doc_status.get_by_id(doc_id)  # 无则 not_found
  → 从 doc_status 取 chunks_list
  →（可选）delete_llm_cache：从 text_chunks 收集 llm_cache_list → doc_llm_cache_ids
  → full_entities / full_relations + 图批量读 → 分析 affected nodes/edges
  → entity_chunks / relation_chunks 更新或标记待删
  → chunks_vdb.delete(chunk_ids)
  → text_chunks.delete(chunk_ids)
  → relationships_vdb.delete + graph.remove_edges（完全删除的关系）
  → entities_vdb.delete + graph.remove_nodes + entity_chunks.delete（完全删除的实体）
  → _insert_done()  # 重建前持久化
  →（若有）rebuild_knowledge_from_chunks(...)  # 对部分实体/关系用剩余 chunk + LLM 缓存重建
  → full_entities.delete([doc_id]); full_relations.delete([doc_id])
  → full_docs.delete([doc_id]); doc_status.delete([doc_id])
  →（可选）llm_response_cache.delete(doc_llm_cache_ids)
  → finally: _insert_done()；释放 pipeline busy
```

**要点**：删除不是简单「按 doc_id 删一行」，而是**按 chunk 来源**消解实体/边，必要时 **`rebuild_knowledge_from_chunks`** 保持图与 VDB 一致。

---

## 5. `operate.py` 核心算子（职责速览）

| 符号 | 行号（约） | 职责 |
|------|------------|------|
| `chunking_by_token_size` | ~99 | 按 tokenizer 与 `chunk_token_size`/`overlap` 切段，返回 `{content, tokens, chunk_order_index}` 列表 |
| `extract_entities` | ~2813 | 并发处理各 chunk：`PROMPTS` + `use_llm_func_with_cache`，调用 `_process_extraction_result`，支持 gleaning |
| `_process_extraction_result` | ~930 | 将 LLM 原始输出解析为 `maybe_nodes` / `maybe_edges` 结构化字典 |
| `merge_nodes_and_edges` | ~2443 | 合并多 chunk 抽取结果 → 写入图、`entities_vdb`、`relationships_vdb`、全文实体关系索引、`entity_chunks`/`relation_chunks` 等 |
| `kg_query` | ~3084 | 关键词 → `_build_query_context` → 上下文字符串 → LLM |
| `naive_query` | ~4804+ | 多块重载版本名相同；语义为仅向量检索路径 |
| `_build_query_context` | ~4118 | 按 mode 组装的统一检索上下文（实体/关系/chunk/raw_data） |
| `_build_context_str` | ~3935 | Token 裁剪、格式化供 prompt 使用的最终上下文字符串 |

---

## 6. 适合后续拆成「可编排节点」的边界（概念映射）

以下为**逻辑拆分点**，不改变 LightRAG 行为前提下可供外部 DAG/工作流引用：

| 概念节点 | 对应源码锚点 |
|----------|----------------|
| **DocumentEnqueueNode** | `apipeline_enqueue_documents`：`full_docs`/`doc_status` 写入 |
| **ChunkNode** | `chunking_func` → 默认 `chunking_by_token_size` |
| **EmbeddingNode** | `chunks_vdb.upsert` / 各 VDB upsert 内嵌的 `embedding_func` |
| **EntityExtractNode** | `extract_entities` + `_process_extraction_result` |
| **GraphMergeNode** | `merge_nodes_and_edges` |
| **DocStatusUpdateNode** | `doc_status.upsert`（PROCESSING/PROCESSED/FAILED） |
| **PersistNode** | `_insert_done` → 各存储 `index_done_callback` |
| **KeywordExtractNode** | `get_keywords_from_query` |
| **KGQueryNode** | `kg_query` 中 `_build_query_context` 段 |
| **VectorQueryNode** | `naive_query` 或 `kg_query` 中 mix 模式的 `chunks_vdb` 部分 |
| **PromptBuildNode** | `_build_context_str` + `PROMPTS["rag_response"]` 拼装 |
| **LLMGenerateNode** | `aquery_llm`/`kg_query` 尾部 `use_model_func` |
| **DeleteOrchestrationNode** | `adelete_by_doc_id` 整段（含 rebuild） |

---

## 7. Adapter 化重构建议（外挂层，**不修改** LightRAG 源码）

### 7.1 原则

- **组合优于继承**：在外部模块持有 `LightRAG` 实例，封装 `insert` / `ainsert`、`query` / `aquery` / `aquery_data`、`adelete_by_doc_id`。  
- **依赖注入**：通过构造函数传入 `embedding_func`、`llm_model_func`、或 Monkey-patch 不推荐；优先使用 **`LightRAG(..., embedding_func=..., llm_model_func=..., vector_storage=..., graph_storage=...)`**（具体参数见 `lightrag.py` dataclass）。

### 7.2 建议 Adapter 接口（概念）

- **`IndexingAdapter`**  
  - `enqueue_documents(texts, ids?, file_paths?, track_id?)` → `ainsert` 或分拆调用 `apipeline_enqueue_documents` + 手动触发 process（一般不暴露）。  
  - `insert_custom_chunks(...)`：对接 **MinerU / 其他解析器** 的输出，不落库 LightRAG 前由 Adapter 转成 `(full_text, chunk_list)`。
- **`QueryAdapter`**  
  - `query_answer(prompt, QueryParam \| dict)` → `aquery_llm`，统一错误与超时策略。  
  - `retrieve_only(...)` → `aquery_data`。
- **`DeletionAdapter`**  
  - `delete_document(doc_id, delete_llm_cache=...)` → `adelete_by_doc_id`。  
  - 可增加「软删除/归档」语义：在 Adapter 层写审计表，再调 LightRAG。

### 7.3 替换扩展点（不碰包内代码）

| 能力 | 扩展方式 |
|------|----------|
| **MinerU** | 在 Adapter 前先跑解析；输出走 `insert` / `ainsert_custom_chunks` / 自定义写入 `full_docs + chunks`。 |
| **Embedding** | 构造 `EmbeddingFunc`（见 `utils.py`）传给 `LightRAG`；或对 OpenAI 兼容服务用 `llm/openai.openai_embed`。 |
| **VectorDB** | 环境变量 **`LIGHTRAG_VECTOR_STORAGE`** + 后端连接串（见 `kg/__init__.py` 的 env 要求）。 |
| **GraphDB** | **`LIGHTRAG_GRAPH_STORAGE`** + Neo4j/Memgraph 等 env。 |
| **LLM** | `llm_model_func` / `QueryParam.model_func` 注入；`prompt.py` 可在外部复制常量后通过 `addon_params` 或自定义 wrapper  prepend。 |

### 7.4 版本与缓存注意

- 升级 **`lightrag-hku`** 后应回归测试 Adapter 调的 **公有方法**：`ainsert`、`aquery`、`aquery_data`、`aquery_llm`、`adelete_by_doc_id`。  
- **工作空间 `workspace`** 与多套存储前缀一致时再切换后端，避免 Milvus collection / Neo4j 标签错乱。

---

## 附录：关键文件一览（本仓库 venv）

- `lightrag.py` — 总线  
- `operate.py` — 图谱与检索算法主体  
- `base.py` — 抽象与 `QueryParam`  
- `prompt.py` — `PROMPTS`  
- `utils.py` — `EmbeddingFunc`、`priority_limit_async_func_call`、`compute_mdhash_id` 等  
- `kg/*_impl.py` — 存储实现  
- `llm/*.py` — 模型适配  
- `api/*` — 服务层  

---

*文档生成方式：静态阅读源码与 grep 抽样，未运行时插桩。*
