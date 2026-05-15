"""
Adapter 层「无 Parser 校验」LightRAG 初始化桥接（兼容补丁，非业务逻辑）。

【重要】本模块中的 ``duplicate_ensure_without_parser_check`` **手工复制**了上游
``raganything.raganything.RAGAnything._ensure_lightrag_initialized`` 在 **parser 校验之后**
的那一段初始化流程（预置 LightRAG / 新建 LightRAG 两条分支）。这样做是为了在**不修改**
``raganything`` 源码的前提下实现惰性 Parser 校验；其代价是：

- **上游 RAG-Anything 或 LightRAG 升级后，该复制段可能失效或行为不一致**；
- 每次升级依赖后必须在 ``docs/adapter_upgrade_checklist.md`` 指导下**人工逐行对照**原版方法并同步修改本文件；
- **长期建议**：推动上游在 ``_ensure_lightrag_initialized`` 增加官方参数（如
  ``skip_parser_check`` / ``lazy_parser_validation``），以便删除本桥接、消除漂移风险。

在 drift 消除之前，当前实现**仅作为 Adapter 层兼容手段**，不具备与上游自动同步的保证。

---

语义概要：与上游方法中非 parser 段落保持一致，不包含 ``doc_parser.check_installation()``；
不改动 ``raganything`` 源码目录。仅限已安装实例级绑定（见 ``lazy_binding.py``）后由包装方法调用。
"""

from __future__ import annotations

import os
from typing import Any


async def duplicate_ensure_without_parser_check(rag: Any) -> dict:
    """
    镜像 ``raganything.py`` 中 `_ensure_lightrag_initialized` 在 parser 校验之后的分支。

    注意：不写 ``self._parser_installation_checked``，以便后续文档解析路径上
    `RAGAnything` 仍可执行正版校验逻辑。
    """
    try:
        from lightrag import LightRAG
        from lightrag.kg.shared_storage import initialize_pipeline_status

        if rag.lightrag is not None:
            if rag.llm_model_func is None and hasattr(rag.lightrag, "llm_model_func"):
                rag.llm_model_func = rag.lightrag.llm_model_func
                rag.logger.debug("Inherited llm_model_func from LightRAG instance")

            if rag.embedding_func is None and hasattr(rag.lightrag, "embedding_func"):
                rag.embedding_func = rag.lightrag.embedding_func
                rag.logger.debug("Inherited embedding_func from LightRAG instance")

            try:
                if (
                    not hasattr(rag.lightrag, "_storages_status")
                    or rag.lightrag._storages_status.name != "INITIALIZED"
                ):
                    rag.logger.info(
                        "Initializing storages for pre-provided LightRAG instance"
                    )
                    await rag.lightrag.initialize_storages()
                    await initialize_pipeline_status()

                if rag.parse_cache is None:
                    rag.logger.info(
                        "Initializing parse cache for pre-provided LightRAG instance"
                    )
                    rag.parse_cache = rag.lightrag.key_string_value_json_storage_cls(
                        namespace="parse_cache",
                        workspace=rag.lightrag.workspace,
                        global_config=rag.lightrag.__dict__,
                        embedding_func=rag.embedding_func,
                    )
                    await rag.parse_cache.initialize()

                if not rag.modal_processors:
                    rag._initialize_processors()

                return {"success": True}

            except Exception as e:
                error_msg = f"Failed to initialize pre-provided LightRAG instance: {str(e)}"
                rag.logger.error(error_msg, exc_info=True)
                return {"success": False, "error": error_msg}

        if rag.llm_model_func is None:
            error_msg = (
                "llm_model_func must be provided when LightRAG is not pre-initialized"
            )
            rag.logger.error(error_msg)
            return {"success": False, "error": error_msg}

        if rag.embedding_func is None:
            error_msg = (
                "embedding_func must be provided when LightRAG is not pre-initialized"
            )
            rag.logger.error(error_msg)
            return {"success": False, "error": error_msg}

        lightrag_params = {
            "working_dir": rag.working_dir,
            "llm_model_func": rag.llm_model_func,
            "embedding_func": rag.embedding_func,
        }

        env_storage_mapping = {
            "kv_storage": os.getenv("KV_STORAGE") or os.getenv("LIGHTRAG_KV_STORAGE"),
            "vector_storage": os.getenv("VECTOR_STORAGE")
            or os.getenv("LIGHTRAG_VECTOR_STORAGE"),
            "graph_storage": os.getenv("GRAPH_STORAGE") or os.getenv("LIGHTRAG_GRAPH_STORAGE"),
            "doc_status_storage": os.getenv("DOC_STATUS_STORAGE")
            or os.getenv("LIGHTRAG_DOC_STATUS_STORAGE"),
        }
        for key, value in env_storage_mapping.items():
            if value and key not in rag.lightrag_kwargs:
                lightrag_params[key] = value

        lightrag_params.update(rag.lightrag_kwargs)

        log_params = {
            k: v
            for k, v in lightrag_params.items()
            if not callable(v)
            and k not in ["llm_model_kwargs", "vector_db_storage_cls_kwargs"]
        }
        rag.logger.info(f"Initializing LightRAG with parameters: {log_params}")

        try:
            rag.lightrag = LightRAG(**lightrag_params)
            await rag.lightrag.initialize_storages()
            await initialize_pipeline_status()

            rag.parse_cache = rag.lightrag.key_string_value_json_storage_cls(
                namespace="parse_cache",
                workspace=rag.lightrag.workspace,
                global_config=rag.lightrag.__dict__,
                embedding_func=rag.embedding_func,
            )
            await rag.parse_cache.initialize()

            rag._initialize_processors()

            rag.logger.info(
                "LightRAG, parse cache, and multimodal processors initialized [adapter lazy-init path]"
            )
            return {"success": True}

        except Exception as e:
            error_msg = f"Failed to initialize LightRAG instance: {str(e)}"
            rag.logger.error(error_msg, exc_info=True)
            return {"success": False, "error": error_msg}

    except Exception as e:
        error_msg = f"Unexpected error during LightRAG initialization: {str(e)}"
        rag.logger.error(error_msg, exc_info=True)
        return {"success": False, "error": error_msg}
