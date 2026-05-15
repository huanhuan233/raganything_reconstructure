"""content_list / ParsedDocument 规范化（纯适配层变换）。"""

from __future__ import annotations

from typing import Any, Dict, List

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult


class ContentNormalizeNode(BaseNode):
    """
    使用 ``DocumentAdapter`` 在 ``content_list`` 与 ``ParsedDocument`` 间归一化。

    输入支持：
    - ``raw_content_list`` / ``content_list``：list of dict
    - ``parsed_document``：已是 ``ParsedDocument`` 时可选再走 ``to_content_list``     再 ``from_content_list`` 做无损往返校验（由 config 控制）。
    """

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="",
            display_name="内容规范化",
            category="content",
            description="content_list 与 ParsedDocument 间归一化（真实逻辑已接 DocumentAdapter）。",
            implementation_status="partial",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(
                    name="roundtrip_validate",
                    label="往返校验",
                    type="boolean",
                    required=False,
                    default=False,
                    description="若为 true，对已解析的 ParsedDocument 做 to_content_list 再 from_content_list。",
                ),
                NodeConfigField(
                    name="source_file",
                    label="源文件标识",
                    type="string",
                    required=False,
                    description="构建文档时的 source_file，可覆盖上游。",
                ),
                NodeConfigField(
                    name="doc_id",
                    label="文档 ID",
                    type="string",
                    required=False,
                ),
            ],
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        from runtime_kernel.protocols.raganything_isolated import (
            load_document_adapter_class,
            load_raganything_types,
        )

        DocumentAdapter = load_document_adapter_class()
        ParsedDocument = load_raganything_types().ParsedDocument

        if not isinstance(input_data, dict):
            return NodeResult(
                success=False,
                error="ContentNormalizeNode 期望上游输出为 dict",
                data=None,
            )
        roundtrip = bool(self.config.get("roundtrip_validate", False))
        source_file = self.config.get("source_file") or input_data.get("source_path")
        doc_id = self.config.get("doc_id") or input_data.get("doc_id")

        parsed_in = input_data.get("parsed_document")
        if isinstance(parsed_in, ParsedDocument) and not roundtrip:
            # 已规范化则原样透传
            return NodeResult(
                success=True,
                data={
                    "parsed_document": parsed_in,
                    "content_list": DocumentAdapter.to_content_list(parsed_in),
                },
                metadata={"path": "passthrough"},
            )

        items: List[Dict[str, Any]] = []
        if isinstance(parsed_in, ParsedDocument) and roundtrip:
            items = DocumentAdapter.to_content_list(parsed_in)
        else:
            raw = input_data.get("raw_content_list") or input_data.get("content_list")
            if not isinstance(raw, list):
                return NodeResult(
                    success=False,
                    error="缺少 raw_content_list / content_list",
                    data=input_data,
                )
            items = raw  # type: ignore[assignment]

        doc = DocumentAdapter.from_content_list(
            items,
            source_file=source_file,
            doc_id=doc_id,
        )
        return NodeResult(
            success=True,
            data={
                "parsed_document": doc,
                "content_list": DocumentAdapter.to_content_list(doc),
            },
            metadata={"adapter": "DocumentAdapter"},
        )
