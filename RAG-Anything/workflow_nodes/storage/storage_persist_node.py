"""多后端存储持久化：embedding_records -> local_jsonl / Milvus / MinIO。"""

from __future__ import annotations

from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult
from adapters.runtime.persist import persist_embedding_records
from adapters.runtime.ui_strategy import ensure_storage_resources, resolve_strategy_from_node_config

_DEFAULT_VECTOR_STORAGE: dict[str, Any] = {
    "backend": "milvus",
    "mode": "existing",
    "collection": "",
    "dimension": 0,
    "metric_type": "COSINE",
    "index_type": "IVF_FLAT",
    "auto_create_index": True,
    "create_if_missing": False,
}

class StoragePersistNode(BaseNode):
    """按 vector_storage（或 legacy storage_strategy）落盘。"""

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="",
            display_name="存储落盘",
            category="storage",
            description="Milvus 连接由服务端 .env 管理；各 pipeline 共享同一向量库，local_jsonl 自动兜底。",
            implementation_status="partial",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(
                    name="vector_storage",
                    label="向量库（结构化）",
                    type="json",
                    required=False,
                    default=_DEFAULT_VECTOR_STORAGE,
                    description="由编排前端写入：milvus collection / 新建参数等",
                ),
            ],
            input_schema={"type": "object", "description": "含 embedding_records / embedding_summary"},
            output_schema={
                "type": "object",
                "description": "透传输入并附加 storage_refs / storage_summary",
            },
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        if not isinstance(input_data, dict):
            return NodeResult(success=False, error="storage.persist 期望输入为 dict（通常来自 embedding.index）")

        records = input_data.get("embedding_records")
        if records is None:
            records = []
        if not isinstance(records, list):
            return NodeResult(success=False, error="embedding_records 必须为 list")

        cfg = dict(self.config or {})
        try:
            ensure_storage_resources(cfg, log=context.log)
            strategy, create_if_missing = resolve_strategy_from_node_config(cfg)
        except Exception as exc:  # noqa: BLE001
            return NodeResult(success=False, error=f"storage.persist 准备存储资源失败: {exc}")

        out = dict(input_data)
        try:
            persisted = persist_embedding_records(
                [r for r in records if isinstance(r, dict)],
                storage_strategy=strategy,
                create_if_missing=create_if_missing,
                workspace=context.workspace or "",
                log=context.log,
            )
        except Exception as exc:  # noqa: BLE001
            return NodeResult(success=False, error=f"storage.persist 执行异常: {exc}")

        out["storage_refs"] = persisted.get("storage_refs", [])
        out["storage_summary"] = persisted.get("storage_summary", {})
        context.log(
            f"[StoragePersistNode] refs={out['storage_summary'].get('refs_total', 0)} "
            f"by_status={out['storage_summary'].get('by_status')}"
        )
        return NodeResult(
            success=True,
            data=out,
            metadata={"node": "storage.persist"},
        )
