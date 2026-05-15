# Adapter 工业化架构说明

本文描述 `RAG-Anything/adapters` 分包的设计动机、与 LightRAG 的边界，以及后续多模态、国产化与工作流落地的扩展方式。**不替代**已有 `raganything` 业务包，亦不修改 `site-packages/lightrag`。

---

## 1. 为什么使用 Adapter

- **稳定边界**：上层平台（网关、租户、配额、审计、工作流 DSL）需要的是稳定接口与数据结构，而非直接耦合 `LightRAG` 的巨型 dataclass 与内部存储生命周期。
- **可替换性**：MinerU、向量库、图数据库、国产模型网关可在外层替换，而不必 fork LightRAG。
- **可测试性**：Adapter 层可 Mock `LightRAG` 或注入测试用双写存储，避免在业务代码中散落 `import lightrag`。
- **合规与演进**：删除、缓存、多租户 `workspace` 策略可在 Adapter 中统一打补丁，而保持上游 LightRAG 版本可升级。

---

## 2. Adapter 与 LightRAG 的关系

| 维度 | 说明 |
|------|------|
| **组合** | `LightRAGEngineAdapter` 内部持有 `self.rag: LightRAG`，所有能力通过转发完成。 |
| **不继承** | 不子类化 `LightRAG`，避免升级时破坏父类初始化与存储内部状态。 |
| **不修改源码** | 不改 `site-packages/lightrag`；扩展通过注入 `embedding_func`、`llm_model_func`、`vector_storage` 等构造参数或环境变量完成。 |
| **职责切分** | LightRAG 负责算法与存储协作；Adapter 负责「入口形状、配置聚合、未来节点化时的 I/O 契约」。 |

---

## 3. 后续如何接入

### 3.1 MinerU

- 在 `parsers/mineru_adapter.py` 中实现 `content_list -> types.ParsedDocument`。
- 在 `indexing_adapter.py` 中实现 `insert_content_list` / `insert_parsed_document`，将 `ParsedDocument` 映射为 `insert_text`、`insert_custom_chunks` 或未来的多向量写入。
- **不**在 Adapter 内启动 MinerU 进程；由部署层（Docker Compose / K8s）保证服务可用，Adapter 只持 API 客户端或本地库句柄。

### 3.2 多模态处理

- 图像、表格在 `types.ParsedImage`、`ParsedTable` 中携带 URI/结构化字段。
- **TODO 路径**：视觉嵌入、跨模态检索、与 `chunks_vdb` 并列的新向量命名空间——应在平台层设计，必要时通过 LightRAG 扩展字段或外挂存储，而非硬改包内逻辑。

### 3.3 国产化存储

- 使用 `storages/vector_storage_adapter.py` 与 `graph_storage_adapter.py` 承载连接参数与「类名 / 环境变量」映射表。
- 实际驱动仍由 LightRAG `kg/*_impl` 或官方/社区插件提供；Adapter 只在应用启动时统一 `os.environ` 或构造 `LightRAG(vector_storage=..., graph_storage=...)`。

### 3.4 工作流节点

- 将 **同步薄封装**（如 `LightRAGEngineAdapter.insert_document`）与 **异步原语**（`QueryAdapter.answer_query` → `aquery_llm`）分别暴露给编排引擎（Temporal、自建 DAG、LlamaIndex Workflow 等）。
- 节点的输入输出优先使用 `types.QueryRequest`、`QueryResponse`、`ParsedDocument`、`RetrievalResult`，减少与 LightRAG 内部 dict 键名强耦合。

---

## 4. 哪些类未来会变成工作流节点（建议映射）

以下为推荐节点粒度，可与 DAG 中 Stage 一一对应：

| 概念节点 | 对应 Adapter / 类型 |
|-----------|---------------------|
| 解析节点 | `MineruAdapter`、`GenericParserAdapter` → 输出 `ParsedDocument` |
| 入库Enqueue | `IndexingAdapter.insert_*` → 内含 `LightRAG` enqueue/process |
| 查询检索 | `QueryAdapter.retrieve_only` |
| 查询生成 | `QueryAdapter.answer_query` / `hybrid_query` |
| 删除治理 | `DeletionAdapter.delete_by_doc_id` |
| 模型提供者 | `EmbeddingProvider`、`LLMProvider` → 产出注入函数 |
| 存储选址 | `VectorStorageAdapter`、`GraphStorageAdapter` → 启动前配置 |

`LightRAGEngineAdapter` 自身可作为「持有 RAG 引擎上下文」的 **会话级单例节点依赖**，一般不单独当一个业务 Step。

---

## 5. 目录索引（快照）

```
adapters/
  lightrag/
    engine_adapter.py    # LightRAG 最小门面
    indexing_adapter.py # 入库多形态骨架
    query_adapter.py    # aquery_llm / aquery_data / hybrid
    deletion_adapter.py # adelete_by_doc_id
    types.py            # Parsed* / Query* / Retrieval*
    config.py           # 构造参数收口
    providers/          # Embedding / LLM 抽象 + OpenAI 兼容占位
    storages/           # 向量/图配置结构（非驱动实现）
    parsers/            # MinerU / 通用解析占位
```

---

## 6. 使用前置

- Python 路径需包含 `RAG-Anything` 项目根以便 `import adapters`（或将 `adapters` 安装为同名 namespace 包）。
- 运行前仍需按 LightRAG 要求配置 `embedding_func` 与 `llm_model_func`，并完成目标向量/图后端的环境变量（若使用 Milvus、Neo4j 等）。

---

*当前阶段 intentional：仅骨架与中文注释/TODO，无复杂业务算法。*
