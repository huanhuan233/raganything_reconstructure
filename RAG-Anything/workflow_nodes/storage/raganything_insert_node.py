"""RAG-Anything 多模态入库节点。"""

from __future__ import annotations

from typing import Any, Optional

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult


class RAGAnythingInsertNode(BaseNode):
    """
    - 当 ``config`` 或 ``input_data``（dict）中提供 ``source_path``（或 ``file_path``）时：
      调用 ``RAGAnythingEngineAdapter.process_document``，返回 ``doc_id`` / ``metadata`` / ``process_status``。
    - 否则：保持占位行为（不访问适配器，标记 mock_skipped）。

    **MinerU 的 ``-m / --method``** 只接受 ``auto`` / ``txt`` / ``ocr``，对应节点里的 ``parse_method``。
    ``parser``（如 ``mineru``）表示「用哪种解析器」，由引擎 ``RAGAnythingConfig`` / ``.env`` 的 ``PARSER`` 决定，
    **不要**把 ``parser: \"mineru\"`` 写进本字段传给 CLI（否则会报 ``'mineru' is not one of ...``）。
    """

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="",
            display_name="RAG-Anything 入库",
            category="raganything",
            description="多模态文档入库：调用 RAGAnythingEngineAdapter.process_document。",
            implementation_status="real",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(
                    name="source_path",
                    label="源文件路径",
                    type="path",
                    required=True,
                    placeholder="如 Inputs/sample.pdf",
                    description="待处理文件路径；也可由上游 input_data.source_path 提供。",
                ),
                NodeConfigField(
                    name="parser",
                    label="解析器",
                    type="select",
                    required=False,
                    default="mineru",
                    options=["mineru", "docling", "paddleocr", "deepseek_ocr2"],
                    description="解析后端选型（与引擎 PARSER / .env 对齐；勿与 parse_method 混淆）。",
                ),
                NodeConfigField(
                    name="parse_method",
                    label="解析方式 (MinerU -m)",
                    type="select",
                    required=False,
                    default="auto",
                    options=["auto", "ocr", "txt"],
                    description="MinerU 的 method，仅 auto / ocr / txt。",
                ),
                NodeConfigField(
                    name="output_dir",
                    label="工作目录 / 输出目录",
                    type="path",
                    required=False,
                    placeholder="可选，写入 DocumentProcessRequest.output_dir",
                    description="处理输出目录，对应 config.output_dir。",
                ),
            ],
            input_schema={"type": "object", "description": "可含 source_path / file_path"},
            output_schema={"type": "object", "description": "doc_id, metadata, process_status"},
        )

    def _resolve_parse_method(self) -> Optional[str]:
        """仅合法 MinerU method；忽略误用的 ``parser: mineru``。"""
        pm = self.config.get("parse_method")
        if pm is not None and str(pm).strip():
            return str(pm).strip()
        legacy = self.config.get("parser")
        if legacy is None:
            return None
        s = str(legacy).strip().lower()
        if s in ("auto", "txt", "ocr"):
            return s
        return None

    def _resolve_source_path(self, input_data: Any) -> Optional[str]:
        p = self.config.get("source_path") or self.config.get("file_path")
        if p:
            return str(p)
        if isinstance(input_data, dict):
            p = input_data.get("source_path") or input_data.get("file_path")
            if p:
                return str(p)
        return None

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        path = self._resolve_source_path(input_data)
        if not path:
            return NodeResult(
                success=True,
                data={
                    "doc_id": None,
                    "metadata": {
                        "skipped": True,
                        "reason": "未提供 source_path（可在 config 或 input_data 中设置）",
                    },
                    "process_status": "mock_skipped",
                },
                metadata={"mock": True},
            )

        key = str(self.config.get("adapter_key", "raganything"))
        adapter = context.adapters.get(key)
        if adapter is None or not hasattr(adapter, "process_document"):
            return NodeResult(
                success=False,
                error=f"context.adapters[{key!r}] 未注入或不支持 process_document",
                data=None,
            )

        from runtime_kernel.protocols.raganything_isolated import load_raganything_types

        DocumentProcessRequest = load_raganything_types().DocumentProcessRequest

        parse_method: Optional[str] = self._resolve_parse_method()
        extra: dict[str, Any] = dict(self.config.get("extra") or {})
        if isinstance(input_data, dict):
            in_extra = input_data.get("extra")
            if isinstance(in_extra, dict):
                for k, v in in_extra.items():
                    extra.setdefault(k, v)

        doc_id_cfg = self.config.get("doc_id")
        if doc_id_cfg is None and isinstance(input_data, dict):
            doc_id_cfg = input_data.get("doc_id")

        req = DocumentProcessRequest(
            source_path=path,
            doc_id=doc_id_cfg,
            output_dir=self.config.get("output_dir"),
            parse_method=parse_method,
            display_stats=self.config.get("display_stats"),
            split_by_character=self.config.get("split_by_character"),
            split_by_character_only=bool(self.config.get("split_by_character_only", False)),
            file_name=self.config.get("file_name"),
            extra=extra,
        )

        resp = await adapter.process_document(req)
        ok = bool(getattr(resp, "success", False))
        meta = dict(getattr(resp, "metadata", None) or {})
        did = getattr(resp, "doc_id", None)

        if not ok:
            return NodeResult(
                success=False,
                error=getattr(resp, "error_message", None) or "process_document 失败",
                data={
                    "doc_id": did,
                    "metadata": meta,
                    "process_status": "failed",
                },
            )

        return NodeResult(
            success=True,
            data={
                "doc_id": did,
                "metadata": meta,
                "process_status": "success",
            },
        )
