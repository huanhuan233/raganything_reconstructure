"""文档解析节点（当前支持通过 ``ParserAdapter`` 调用 MinerU）。"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult


class DocumentParseNode(BaseNode):
    """
    将源文件或字节流转为 ``ParsedDocument`` / ``content_list``。

    当提供 ``source_path`` 时调用 ``ParserAdapter``（目前仅支持 MinerU）；
    未提供 ``source_path`` 时保留 mock 行为，便于无文件场景联调。
    """

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="",
            display_name="文档解析",
            category="document",
            description="将源文件解析为 ParsedDocument / content_list（当前支持 MinerU parse_file）。",
            implementation_status="partial",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(
                    name="source_path",
                    label="源文件路径",
                    type="path",
                    required=False,
                    placeholder="如 Inputs/sample.pdf",
                    description="优先使用 config.source_path；也可由上游 input_data.source_path 传入。",
                ),
                NodeConfigField(
                    name="parser",
                    label="解析器",
                    type="select",
                    required=False,
                    default="mineru",
                    options=["mineru", "docling", "paddleocr", "deepseek_ocr2"],
                ),
                NodeConfigField(
                    name="parse_method",
                    label="解析方式 (MinerU -m)",
                    type="select",
                    required=False,
                    default="auto",
                    options=["auto", "ocr", "txt"],
                ),
                NodeConfigField(
                    name="pages_per_split",
                    label="每几页一分割",
                    type="number",
                    required=False,
                    default=2,
                    description="对可分页文档生效（PDF/Office/Text）；按 N 页分批解析后合并回单一完整 parse_result（默认 2）。",
                ),
                NodeConfigField(
                    name="doc_id",
                    label="文档 ID",
                    type="string",
                    required=False,
                    description="可选，写入模拟 ParsedDocument。",
                ),
                NodeConfigField(
                    name="mock_text",
                    label="模拟正文",
                    type="string",
                    required=False,
                    default="模拟解析得到的正文片段。",
                    description="占位阶段注入 chunks 的文本。",
                ),
            ],
            input_schema={"type": "object"},
            output_schema={"type": "object", "description": "source_path, content_list, parsed_document, parse_status"},
        )

    def _resolve_source_path(self, input_data: Any) -> str | None:
        p = self.config.get("source_path") or self.config.get("file_path")
        if p:
            return str(p)
        if isinstance(input_data, dict):
            p = input_data.get("source_path") or input_data.get("file_path")
            if p:
                return str(p)
        return None

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        from runtime_kernel.protocols.raganything_isolated import (
            load_document_adapter_class,
            load_parser_adapter_classes,
            load_raganything_types,
        )

        m = load_raganything_types()
        ParsedChunk = m.ParsedChunk
        ParsedDocument = m.ParsedDocument

        source = self._resolve_source_path(input_data)

        if source:
            parser_name = str(self.config.get("parser", "mineru")).strip().lower() or "mineru"
            parse_method = str(self.config.get("parse_method", "auto")).strip() or "auto"
            raw_pages_per_split = self.config.get("pages_per_split", 2)
            try:
                pages_per_split = int(raw_pages_per_split)
                if pages_per_split <= 0:
                    pages_per_split = 2
            except Exception:  # noqa: BLE001
                pages_per_split = 2
            MinerUParserAdapter, _GenericParserAdapter = load_parser_adapter_classes()
            DocumentAdapter = load_document_adapter_class()
            if parser_name != "mineru":
                return NodeResult(
                    success=False,
                    error=f"document.parse 当前仅接入 mineru，收到 parser={parser_name}",
                )
            adapter = MinerUParserAdapter()
            context.log(
                f"[DocumentParseNode] real parse node_id={self.node_id} "
                f"parser={parser_name} method={parse_method} pages_per_split={pages_per_split}"
            )
            try:
                parsed_doc = await adapter.parse_file(
                    source,
                    output_dir=self.config.get("output_dir"),
                    method=parse_method,
                    doc_id=self.config.get("doc_id"),
                    pages_per_split=pages_per_split,
                )
                content_list = DocumentAdapter.to_content_list(parsed_doc)
            except Exception as exc:  # noqa: BLE001
                return NodeResult(
                    success=False,
                    error=f"document.parse 解析失败: {exc}",
                    data={"source_path": source, "parse_status": "failed"},
                )
            return NodeResult(
                success=True,
                data={
                    "source_path": source,
                    "content_list": content_list,
                    "parsed_document": asdict(parsed_doc),
                    "parse_status": "success",
                },
                metadata={
                    "parser": parser_name,
                    "parse_method": parse_method,
                    "pages_per_split": pages_per_split,
                    "paginated_parse": bool(parsed_doc.metadata.get("paginated_parse", False)),
                    "page_batches": int(parsed_doc.metadata.get("page_batches", 0) or 0),
                    "merged_back": bool(parsed_doc.metadata.get("merged_back", True)),
                },
            )

        context.log(f"[DocumentParseNode] mock parse node_id={self.node_id} (no source_path)")
        mock_doc = ParsedDocument(
            source_file=source or "mock://placeholder.pdf",
            doc_id=self.config.get("doc_id"),
            raw_content_list=[
                {
                    "type": "text",
                    "text": self.config.get("mock_text", "模拟解析得到的正文片段。"),
                    "page_idx": 0,
                    "text_level": 0,
                }
            ],
            chunks=[
                ParsedChunk(
                    text=self.config.get("mock_text", "模拟解析得到的正文片段。"),
                    page_idx=0,
                    text_level=0,
                )
            ],
        )
        return NodeResult(
            success=True,
            data={
                "source_path": source,
                "content_list": mock_doc.raw_content_list,
                "parsed_document": asdict(mock_doc),
                "parse_status": "mock_skipped",
            },
            metadata={"phase": "mock"},
        )
