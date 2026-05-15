"""LightRAG 文本入库节点。"""

from __future__ import annotations

from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult


class LightRAGInsertNode(BaseNode):
    """
    调用 ``LightRAGEngineAdapter.insert_document`` 写入纯文本。

    ``config.adapter_key`` 默认为 ``"lightrag``，从 ``context.adapters[adapter_key]`` 取引擎实例。
    文本取自 ``input_data["text"]`` 或 ``input_data["content"]``     或 ``str(input_data)``。
    """

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="",
            display_name="LightRAG 入库",
            category="lightrag",
            description="调用 LightRAGEngineAdapter.insert_document 写入纯文本。",
            implementation_status="real",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(
                    name="adapter_key",
                    label="适配器键",
                    type="string",
                    required=False,
                    default="lightrag",
                    description="context.adapters 中的键名。",
                ),
                NodeConfigField(
                    name="split_by_character",
                    label="按字符切分",
                    type="string",
                    required=False,
                    description="可选，传给 insert_document。",
                ),
                NodeConfigField(
                    name="split_by_character_only",
                    label="仅按字符切分",
                    type="boolean",
                    required=False,
                    default=False,
                ),
                NodeConfigField(
                    name="track_id",
                    label="跟踪 ID",
                    type="string",
                    required=False,
                ),
            ],
            input_schema={"type": "object", "description": "text / content / body"},
            output_schema={"type": "object", "description": "text, track_id"},
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        key = self.config.get("adapter_key", "lightrag")
        adapter = context.adapters.get(key)
        # 采用鸭子类型，便于示例中注入 Mock，无需继承适配器类
        if adapter is None or not hasattr(adapter, "insert_document"):
            return NodeResult(
                success=False,
                error=f"context.adapters[{key!r}] 缺失或没有 insert_document 方法",
                data=None,
            )
        text: str
        if isinstance(input_data, dict):
            text = str(
                input_data.get("text")
                or input_data.get("content")
                or input_data.get("body")
                or ""
            )
        elif input_data is None:
            text = ""
        else:
            text = str(input_data)
        if not text.strip():
            return NodeResult(
                success=False,
                error="入库文本为空",
                data=input_data,
            )
        try:
            track_id = adapter.insert_document(
                text,
                split_by_character=self.config.get("split_by_character"),
                split_by_character_only=bool(
                    self.config.get("split_by_character_only", False)
                ),
                ids=self.config.get("ids"),
                file_paths=self.config.get("file_paths"),
                track_id=self.config.get("track_id"),
            )
        except Exception as exc:  # noqa: BLE001
            return NodeResult(
                success=False,
                error=str(exc),
                data=None,
            )
        context.log(f"[LightRAGInsertNode] track_id={track_id}")
        return NodeResult(
            success=True,
            data={"text": text, "track_id": track_id},
            metadata={"adapter_key": key},
        )
