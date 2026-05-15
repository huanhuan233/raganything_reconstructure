# RAGAnything Adapter 架构说明

本文描述 `adapters/raganything` 分包的设计动机、与 `adapters/lightrag` 的分工及推荐调用方式。**不改变**原始 `raganything` 包、**不修改** `adapters/lightrag`。

---

## 1. 为什么 RAG-Anything 也需要 Adapter

- **边界清晰**：上层平台只需依赖 `ParsedDocument`、`DocumentProcessRequest` 等与解析器演进解耦的 DTO，而不是直接散布对 `process_document_complete`、`insert_content_list` 等方法签名的耦合。
- **生命周期统一**：Neo4j / Milvus / 异步循环导致的 `finalize`、`close` 顺序可由 `RAGAnythingLifecycleAdapter` 集中编排（参见 `lifecycle_adapter.py`）。
- **节点化预备**：DAG 中「解析 → 规范化 → 入库 → 查询」可映射为独立节点，DTO 在各节点边界传递。
- **国产化与替换**：Parser / 多模态策略可在适配层替换，而不 fork `raganything` 源码树。

---

## 2. 与 `adapters/lightrag` 的关系

| 层级 | 包 | 职责 |
|------|-----|------|
| 多模态解析与规范化 | `adapters/raganything` | 组合 `RAGAnything`：文件、`content_list`、查询 mixin |
| 纯 LightRAG 引擎 | `adapters/lightrag` | 组合 `LightRAG`：`insert`、`query`、`delete`，无 MinerU 管线 |

二者可共享同一个 **`LightRAG` 实例**（在应用工厂中创建 `LightRAG` 并注入 `RAGAnything(lightrag=...)`，`RAGAnythingAdapterConfig.lightrag_adapter_enabled` 为后续勾选此模式预留）。

---

## 2a. 为什么 Adapter 生命周期不应强依赖 Parser 安装

在原始 `RAGAnything` 中，`_ensure_lightrag_initialized()` 将 **LightRAG 存储初始化** 与 **文档解析器（如 MinerU）安装检查**绑在同一段逻辑首部。对工业化 Adapter 而言，这是三层不同运行时的耦合：

| 运行时 | 职责 | 何时需要 ready |
|--------|------|----------------|
| **Engine 生命周期** | 创建工作目录、`LightRAG` 实例、`initialize_storages`、KV/向量/文档状态、`parse_cache`（结构就绪）、收尾 `finalize_storages` | 平台进程启动或租户会话开始时 |
| **Parser Runtime** | MinerU / Docling / OCR 的可执行环境与依赖 | **仅当**需要从磁盘字节流解析版面时 |
| **Workflow Runtime** | DAG / 异步任务编排、幂等键、重试 | 可能长期持有 Engine，但按需调度解析 |

将「Engine 已成功 `initialize()`」等同于「MinerU 已 pip install」会导致：

- CI 无法做导入与存储自检；
- 仅测 `ParsedDocument → insert_content_list` 的多模态平台被迫装解析侧重磅依赖；
- 与微服务拆分（向量服务 / 解析服务）的自然边界冲突。

因此 **Adapter 默认**启用 `lazy_parser_validation=True`：在单个 `RAGAnything` **实例上**绑定 `_ensure_lightrag_initialized` 的包装方法（实例级 `types.MethodType`，**非全局猴子补丁**），使「仅引擎 / DTO / 查询烟测路径」可走 **不包含 `doc_parser.check_installation`** 的桥接初始化（代码见 `adapters/raganything/lazy_lightrag_bridge.py`）。

一旦进入 **`process_document(DocumentProcessRequest)` 且带有 `source_path`**，或由编排显式调用 `ensure_parser_ready_for_document_parsing()`，则将内部标志 `_adapter_parser_required=True`，随后的 `_ensure_lightrag_initialized` **回落到原版**，从而触发与上游完全一致的 Parser 校验与错误信息。**未关闭校验逻辑**，仅延迟执行。

### 风险说明（lazy bridge 与版本漂移）

| 风险项 | 说明 |
|--------|------|
| **复制型实现** | `lazy_lightrag_bridge.duplicate_ensure_without_parser_check` **复制**了 `RAGAnything._ensure_lightrag_initialized` **去掉 parser 段之后**的内部逻辑（含 LightRAG 构造参数拼装、`initialize_pipeline_status`、parse_cache、`modal_processors` 等）。**非**上游公开 API；上游一旦调整初始化顺序或新增必选步骤，本桥可能与官方行为分叉。 |
| **升级必对照** | 每次升级 **`raganything` / `lightrag-hku`** 后，必须从 `raganything.py` **重新比对** `_ensure_lightrag_initialized` 全文，并同步修改 `duplicate_ensure_without_parser_check`。**推荐流程**见 `docs/adapter_upgrade_checklist.md`。 |
| **上游演进方向** | 长期应避免双份逻辑：建议向官方仓库推动 **构造函数或 `_ensure_*` 的显式开关**（如 `skip_parser_check` / `lazy_parser_validation`），使「无磁盘解析场景的引擎就绪」为一等公民；届时可删除适配层复制代码。 |
| **定位** | 当前惰性方案**仅为 Adapter 兼容补丁**，不替代上游维护；运行时可用 `check_lazy_bridge_health(rag)` 做一次**唯读**字段自检（见 `lazy_binding.py`）。 |

---

## 3. 推荐调用路径

**含解析与多模态的完整链路：**

```
文件或 ParsedDocument
  → RAGAnythingEngineAdapter.initialize()
  → process_document(DocumentProcessRequest) 或 insert_content_list(ParsedDocument)
       → raganything.RAGAnything.process_document_complete / insert_content_list
       → LightRAG（分块、向量、图谱……）
  → query(RAGAnythingQueryRequest)
  → RAGAnythingEngineAdapter.finalize()
```

**仅文本、`content_list` 已由外部准备好的快速路径：** 仍可走 `insert_content_list`（同上）。

---

## 3a. ``from_config`` 工厂方法与惰性 Parser（默认）

- ``RAGAnythingEngineAdapter.from_config(adapter_config, ...)``：若 ``adapter_config.lazy_parser_validation=True``（**默认**），在返回前对 **该** ``RAGAnything`` 实例安装惰性 `_ensure_lightrag_initialized` 绑定。
- 若需恢复「与原版完全一致、首次初始化即校验 Parser」，在配置中设 ``lazy_parser_validation=False``（不在此处安装绑定）。

参见 ``examples/adapter_raganything_lifecycle_only.py``：仅 ``initialize/finalize``，用于 CI/架构冒烟（仍需 LLM/embed 占位或真实密钥以初始化 LightRAG）。

---

## 3b. ``from_config`` 代码示例

以下展示与必选模型函数拼装引擎的常规写法（默认已含惰性 Parser 绑定，见 3a）：

可在不手写 ``RAGAnything(...)`` 的情况下，通过 ``RAGAnythingAdapterConfig`` 与必选模型函数拼装引擎：

```python
from adapters.raganything import (
    RAGAnythingEngineAdapter,
    RAGAnythingAdapterConfig,
)

engine = RAGAnythingEngineAdapter.from_config(
    RAGAnythingAdapterConfig(working_dir="./rag_storage"),
    llm_model_func=your_llm,
    embedding_func=your_embedding,
    vision_model_func=None,          # 可选
    lightrag=None,                     # 可选：传入已构造的 LightRAG
    lightrag_kwargs={...},             # 仅当需要透传给 RAGAnything 时，例如自定义 LightRAG 参数字典
)
```

- ``raganything_kwargs`` 仅能包含 **`RAGAnything` dataclass 已声明字段**（源码见 `raganything/raganything.py`），常用为 ``lightrag_kwargs``。
- 仍采用 **组合** 而非继承。

---

## 3c. 最小导入自检（不入库）

项目根目录执行：

```bash
python examples/adapter_import_check.py
```

仅依次 `import adapters.lightrag`、`import adapters.raganything` 并打印主要类符号，用于 CI/环境问题快速排查。**需要环境已安装 `lightrag`**（与 `raganything.config` 的依赖一致）。

---

## 4. 什么情况下直接用 LightRAGAdapter

- 无 MinerU / 无图版式解析诉求，仅 **`ainsert` 文本** 与 **`aquery`**。
- 多模态由其他系统预处理为纯文本后一次性写入。

此时使用 `adapters/lightrag.LightRAGEngineAdapter` 即可。

---

## 5. 什么情况下用 RAGAnythingAdapter

- PDF/Office/图片需 **MinerU / Docling / OCR** 转成 `content_list`。
- 需 **图像 / 表格 / 公式** 的上下文感知描述与图谱写入（`modalprocessors` 路径）。
- 查询需要 **`aquery_vlm_enhanced`** / **`aquery_with_multimodal`** 语义。

---

## 6. 后续如何变成工作流节点

建议节点划分：

| 节点 | 适配类/方法 |
|------|-------------|
| 解析（可选独立） | `ParserAdapter` 实现类 → 产出 `ParsedDocument` |
| 规范化 | `DocumentAdapter.from_content_list` / `to_content_list` |
| 入库 | `RAGAnythingEngineAdapter.process_document` / `insert_content_list` |
| 多模态细粒度（可选） | `MultimodalAdapter`（待实现委托） |
| 查询 | `RAGAnythingQueryAdapter` |
| 收尾 | `RAGAnythingLifecycleAdapter.finalize_storages` |

引擎级 `initialize`/`finalize` 对应 DAG 首尾或 pre/post hook。

---

## 7. 已实现包装（当前骨架）

| 能力 | 实现位置 |
|------|----------|
| 组合 `RAGAnything` | `RAGAnythingEngineAdapter` |
| 转调 `process_document_complete` / `insert_content_list` | `engine_adapter.py` |
| 查询三路分发 | `RAGAnythingQueryAdapter.dispatch` |
| 生命周期 `_ensure_lightrag_initialized` / `finalize_storages` | `lifecycle_adapter.py` |
| DTO（含 MinerU 友好字段） | `types.py` |
| ParsedDocument ↔ content_list（简约） | `document_adapter.py` |
| `RAGAnythingAdapterConfig → RAGAnythingConfig` | `config.py::to_raganything_config` |
| 工厂拼装 `RAGAnything` | `RAGAnythingEngineAdapter.from_config` |
| 惰性 Parser + LightRAG 初始化桥接 | `lazy_binding.py`、`lazy_lightrag_bridge.py`、`RAGAnythingAdapterConfig.lazy_parser_validation` |
| Parser 延后校验入口 | ``process_document``（``source_path``）、``ensure_parser_ready_for_document_parsing()`` |

**doc_id 返回约定（不写死猜测逻辑）：**

- 若调用方传入 ``request.doc_id``，响应中返回该值。
- ``insert_content_list`` / ``parsed_document`` 路径若无 ``request.doc_id``，则回退 ``parsed_document.doc_id``。
- **文件路径** ``process_document_complete`` 且未传 ``doc_id`` 时：**不**从 parse_cache / doc_status 反查；在 ``metadata.doc_id_resolution`` 标注 ``TODO: generated by RAGAnything content hash`，由业务层后续自行对齐。

另有最小冒烟示例：`examples/adapter_raganything_minimal_example.py`（占位模型可能导致入库失败，需自行替换）。

---

## 8. 仅占位 / 扩展点

| 项目 | 说明 |
|------|------|
| `ParserAdapter` 具体解析 | **仍未实现**：`NotImplementedError`；未接 MinerU/Docling；解析前应 `ensure_parser_ready_for_document_parsing` 或 `process_document(source_path=...)` |
| `MultimodalAdapter` | **仍未实现**：**未**转调 ``ImageModalProcessor`` 等，`modalprocessors` 仍仅在原始 ``RAGAnything`` 入库路径内部使用 |
| 内容哈希生成的 ``doc_id`` | 仅在 metadata 中用 TODO 标明；Adapter 不负责从缓存反查 |
| YAML/env 一统加载 | `RAGAnythingAdapterConfig` TODO |
| 与 Temporal/Celery 集成 | `RAGAnythingEngineAdapter` TODO |

---

## 9. Import 路径

在项目根 **`RAG-Anything`** 下将包路径加入 `PYTHONPATH`（或安装为可编辑包）后：

```python
from adapters.raganything import (
    RAGAnythingEngineAdapter,
    RAGAnythingAdapterConfig,
    ParsedDocument,
    ParsedChunk,
    DocumentProcessRequest,
    DocumentProcessResponse,
    RAGAnythingQueryRequest,
    RAGAnythingQueryResponse,
    check_lazy_bridge_health,
)
```

---

*与 `docs/raganything_source_analysis.md` 对照阅读；升级依赖时请执行 `docs/adapter_upgrade_checklist.md`。*
