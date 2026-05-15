# Adapter 升级自检清单（RAG-Anything / LightRAG）

在升级 **`raganything`**、**`lightrag-hku`** 或调整了 `.env` 存储相关变量后执行。  
本清单不写业务代码变更，只做**核对与冒烟**步骤。

---

## 1. 必查文件（Adapter 层）

| 文件 | 关注点 |
|------|--------|
| `adapters/raganything/lazy_lightrag_bridge.py` | **`duplicate_ensure_without_parser_check` 必须与上游 `_ensure_lightrag_initialized` parser 之后的逻辑逐项一致** |
| `adapters/raganything/lazy_binding.py` | 包装函数是否仍能通过 `RAGAnything.__dict__["_ensure_lightrag_initialized"]` 取得原版 |
| `adapters/raganything/engine_adapter.py` | `mark_parser_required`、`ensure_parser_ready_for_document_parsing`、`process_document` 中 `source_path` 分支 |
| `adapters/raganything/lifecycle_adapter.py` | `initialize_storages` 调用链是否与上游 Async 语义冲突 |
| `adapters/raganything/config.py` | `lazy_parser_validation` / `to_raganything_config` 字段是否与 `RAGAnythingConfig` 仍对齐 |

---

## 2. 与上游逐项对比（最关键）

1. 打开 **`raganything/raganything.py`**，定位 **`_ensure_lightrag_initialized`**。
2. 划出 **-parser 校验块之前**的行（通常为 `doc_parser.check_installation` 与 `_parser_installation_checked` 相关）。
3. 将其余 **`if self.lightrag is not None:`** 分支与 **`LightRAG(**lightrag_params)`** 分支，与 **`lazy_lightrag_bridge.duplicate_ensure_without_parser_check`** **逐 diff**：
   - 环境变量拼装（`KV_STORAGE`、`VECTOR_STORAGE` 等）；
   - `lightrag_params` / `initialize_pipeline_status` 调用次序；
   - `parse_cache` 命名空间与 `global_config` 来源；
   - **`_initialize_processors()`** 调用条件。
4. 若上游新增了 **必选初始化步骤**，必须在桥接函数中补上，否则会静默行为不一致。

---

## 3. 自动化冒烟（项目根 `RAG-Anything`）

在目标虚拟环境（如 `conda activate raga`）下：

```bash
python examples/adapter_import_check.py
python examples/adapter_raganything_lifecycle_only.py
python examples/adapter_raganything_minimal_example.py
```

含义：

| 脚本 | 目的 |
|------|------|
| `adapter_import_check.py` | ``adapters.lightrag`` / ``adapters.raganything`` **import** |
| `adapter_raganything_lifecycle_only.py` | 惰性初始化 + **`check_lazy_bridge_health`** 字段检查 |
| `adapter_raganything_minimal_example.py` | ParsedDocument → `insert_content_list` → `query` **闭环**（依赖真实/占位模型质量） |

说明：lifecycle / minimal 示例内通过 `lightrag_kwargs` 指向 **Nano + NetworkX + 隔离 workspace**；若在您的环境中改为 Milvus，见下文维度检查。

---

## 4. LightRAG storage 初始化参数

- 核对 **`working_dir`、`workspace`、`vector_storage`、`graph_storage`**、`lightrag_kwargs` 是否与生产一致。
- `.env` 中 **`LIGHTRAG_*_STORAGE`**、`WORKSPACE` 是否在升级后被 LightRAG 新版本改义。
- **`initialize_pipeline_status`**：`lightrag.kg.shared_storage` API 是否仍兼容（升级后偶有 import 路径变化）。

---

## 5. Parser 校验路径

- **`lazy_parser_validation=True`**：`initialize()` 不应要求 Mineru 安装；**若失败**，多半是桥接漂移或存储层问题而非 Parser。
- **`source_path`** 的 `process_document_complete`：**必须**走正版 `_ensure_lightrag_initialized`（含 Parser 检查）；需在**已安装 Parser** 的环境或用例中验证。
- **`ensure_parser_ready_for_document_parsing()`**：是否与 `verify_parser_installation_once` 行为一致（同步抛错语义）。

---

## 6. doc_id 返回逻辑（Adapter）

- **`DocumentProcessResponse`**：`source_path` 且无调用方 `doc_id` 时，`metadata.doc_id_resolution` 是否有 TODO 占位。
- **`insert_content_list`**：未传入 `doc_id` 时不应强行从 KV 推断（仍由上层或 LightRAG 内容哈希生成）。
- 回归阅读 **`adapters/raganything/engine_adapter.py`** 中与 doc_id 相关的分支。

---

## 7. Milvus 与 Embedding 维度一致

若使用 **`MilvusVectorDBStorage`**（非示例中的 Nano）：

- 现有 collection 的 **向量维度** 必须与当前 **`embedding_func.embedding_dim`** 一致；
- 升级嵌入模型维度后常见于 **报错「Vector dimension mismatch」**；处理方式：建新 `workspace`/collection，或清空兼容集合（生产需迁移策略）。
- 烟测脚本默认 **隔离 Nano**，避免因宿主 Milvus 历史 collection 误判 Adapter 失效。

---

## 8. 唯读自检 API

在无业务负载时，可对已构造的 `RAGAnything` 实例调用：

```python
from adapters.raganything import check_lazy_bridge_health

print(check_lazy_bridge_health(rag_instance))
```

返回字段：`lazy_binding_installed`、`parser_required`、`lightrag_initialized`、`warning`。**不触发**重初始化。

---

*升级后若桥接对齐成本过高，请优先在社区 issue / PR 中推动上游官方「跳过 parser 校验的初始化路径」。*
