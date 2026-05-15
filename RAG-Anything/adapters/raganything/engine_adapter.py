"""
RAGAnything 引擎适配：组合注入 `raganything.RAGAnything`，不承担解析算法实现。
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from third_party.raganything.raganything import RAGAnything

from .config import RAGAnythingAdapterConfig
from .document_adapter import DocumentAdapter
from .lazy_binding import install_lazy_parser_ensure_on_instance, mark_parser_required
from .lifecycle_adapter import RAGAnythingLifecycleAdapter
from .query_adapter import RAGAnythingQueryAdapter
from .types import (
    DocumentProcessRequest,
    DocumentProcessResponse,
    ParsedDocument,
    RAGAnythingQueryRequest,
    RAGAnythingQueryResponse,
)


class RAGAnythingEngineAdapter:
    """
    工业化统一入口：`initialize` → 处理文档 / 入库 / 查询 → `finalize`。

    惰性 parser：当 ``RAGAnythingAdapterConfig.lazy_parser_validation=True``（默认）且在
    ``from_config`` / 构造函数中启用绑定后，生命周期初始化**不检查** Parser 安装；
    处理 ``source_path`` 的文档时会自动切换为正版校验路径。

    TODO: 接入任务队列（Celery/Arq）、DAG Runtime（Temporal）、幂等与重试策略。
    """

    def __init__(
        self,
        raganything: Any,
        *,
        adapter_config: Optional[RAGAnythingAdapterConfig] = None,
        lazy_parser_validation: Optional[bool] = None,
        lifecycle: Optional[RAGAnythingLifecycleAdapter] = None,
        query: Optional[RAGAnythingQueryAdapter] = None,
    ) -> None:
        self.raganything = raganything
        self._adapter_config = adapter_config

        # 惰性绑定：优先显式 ``lazy_parser_validation=True``；为 None 时读 ``adapter_config``。
        # ``False`` 显式关闭时不安装（但若 ``from_config`` 已预先安装则会保持幂等跳过）。
        _apply_lazy = False
        if lazy_parser_validation is True:
            _apply_lazy = True
        elif lazy_parser_validation is False:
            _apply_lazy = False
        elif adapter_config is not None and adapter_config.lazy_parser_validation:
            _apply_lazy = True

        if _apply_lazy:
            install_lazy_parser_ensure_on_instance(raganything)

        self._lifecycle = lifecycle or RAGAnythingLifecycleAdapter(raganything)
        self._query = query or RAGAnythingQueryAdapter(raganything)


    @classmethod
    def from_config(
        cls,
        adapter_config: RAGAnythingAdapterConfig,
        *,
        llm_model_func: Callable[..., Any],
        embedding_func: Callable[..., Any],
        vision_model_func: Optional[Callable[..., Any]] = None,
        lightrag: Any = None,
        **raganything_kwargs: Any,
    ) -> RAGAnythingEngineAdapter:
        """
        根据适配层配置与模型函数构造 `RAGAnything` 并封装为 Adapter。

        `raganything_kwargs` 仅透传 **`RAGAnything` dataclass 合法字段**，例如：
        `lightrag_kwargs`（参见 `raganything.py` 中 ``lightrag_kwargs: Dict[str, Any]`` 文档说明）。

        禁止传入源码中不存在的构造函数参数。
        """
        rag_inst = RAGAnything(
            lightrag=lightrag,
            llm_model_func=llm_model_func,
            vision_model_func=vision_model_func,
            embedding_func=embedding_func,
            config=adapter_config.to_raganything_config(),
            **raganything_kwargs,
        )
        if adapter_config.lazy_parser_validation:
            install_lazy_parser_ensure_on_instance(rag_inst)
        return cls(
            rag_inst,
            adapter_config=adapter_config,
            lazy_parser_validation=False,
        )

    async def initialize(self) -> None:
        """初始化 LightRAG、parse_cache、多模态处理器等（惰性模式下不校验 Parser）。"""
        await self._lifecycle.initialize_storages()

    async def ensure_parser_ready_for_document_parsing(self) -> None:
        """
        在调用 ``parse_document`` / ``process_document_complete``（文件路径）**之前**，由编排层主动触发。

        行为：标记需走正版 ``_ensure_lightrag_initialized``，并调用 ``verify_parser_installation_once()``。
        未安装配置的 Parser 时将抛出 ``RuntimeError``（与原版一致）。
        """
        mark_parser_required(self.raganything)
        self.raganything.verify_parser_installation_once()

    async def process_document(self, request: DocumentProcessRequest) -> DocumentProcessResponse:
        """整文件流水线：等价于 `RAGAnything.process_document_complete`。

        parsed_document：走 `insert_content_list`。

        ``source_path``：在调用原版前标记需要 Parser 可用性校验（正版路径）。

        doc_id 返回规则：优先 ``request.doc_id``，其次 ``parsed_document.doc_id``；
        文件路径入库且未显式传 doc_id 时，不在此猜测 RAGAnything 内部生成的哈希 id。
        """
        try:
            if request.source_path:
                mark_parser_required(self.raganything)
                await self.raganything.process_document_complete(
                    request.source_path,
                    output_dir=request.output_dir,
                    parse_method=request.parse_method,
                    display_stats=request.display_stats,
                    split_by_character=request.split_by_character,
                    split_by_character_only=request.split_by_character_only,
                    doc_id=request.doc_id,
                    file_name=request.file_name,
                    **request.extra,
                )
                meta: dict[str, Any] = {"source_path": request.source_path}
                resolved_doc_id: Optional[str] = request.doc_id
                if resolved_doc_id is None:
                    meta["doc_id_resolution"] = (
                        "TODO: generated by RAGAnything content hash"
                    )
                return DocumentProcessResponse(
                    success=True,
                    doc_id=resolved_doc_id,
                    message="process_document_complete 已执行",
                    metadata=meta,
                )
            if request.parsed_document is not None:
                sub_id = (
                    request.doc_id
                    if request.doc_id is not None
                    else request.parsed_document.doc_id
                )
                return await self.insert_content_list(
                    request.parsed_document,
                    doc_id=sub_id,
                )
            return DocumentProcessResponse(
                success=False,
                error_message="DocumentProcessRequest 缺少 source_path 与 parsed_document",
            )
        except Exception as exc:  # noqa: BLE001 — 骨架阶段兜底
            err_doc_id = request.doc_id
            if err_doc_id is None and request.parsed_document is not None:
                err_doc_id = request.parsed_document.doc_id
            return DocumentProcessResponse(
                success=False,
                doc_id=err_doc_id,
                error_message=str(exc),
                message="process_document 失败",
            )

    async def insert_content_list(
        self, document: ParsedDocument, *, doc_id: Optional[str] = None
    ) -> DocumentProcessResponse:
        """将 ParsedDocument 转为 content_list 后调用 `RAGAnything.insert_content_list`。

        ``doc_id`` 若调用方与本对象均未提供，则由 LightRAG 内部生成；
        Adapter **不读取 parse_cache/doc_status** 回填该字段。
        """
        try:
            cl = DocumentAdapter.to_content_list(document)
            fp = document.source_file or "unknown_document"
            did = doc_id if doc_id is not None else document.doc_id
            await self.raganything.insert_content_list(cl, file_path=fp, doc_id=did)
            meta: dict[str, Any] = {"blocks": len(cl)}
            if did is None:
                meta["doc_id_resolution"] = (
                    "TODO: generated by RAGAnything content hash"
                )
            return DocumentProcessResponse(
                success=True,
                doc_id=did,
                message="insert_content_list 已执行",
                metadata=meta,
            )
        except Exception as exc:  # noqa: BLE001
            fallback_id = doc_id if doc_id is not None else document.doc_id
            return DocumentProcessResponse(
                success=False,
                doc_id=fallback_id,
                error_message=str(exc),
            )

    async def query(self, request: RAGAnythingQueryRequest) -> RAGAnythingQueryResponse:
        """查询：内部转调 QueryAdapter.dispatch。"""
        try:
            return await self._query.dispatch(request)
        except Exception as exc:  # noqa: BLE001
            return RAGAnythingQueryResponse(
                answer_text="",
                mode=request.mode,
                used_vlm=request.enable_vlm,
                used_multimodal=bool(request.multimodal_content),
                metadata={"error": str(exc)},
            )

    async def finalize(self) -> None:
        """异步持久化与关闭存储。"""
        await self._lifecycle.finalize_storages()
