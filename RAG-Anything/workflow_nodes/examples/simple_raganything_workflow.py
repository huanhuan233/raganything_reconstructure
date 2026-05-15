"""
RAG-Anything 多模态入库 + 查询示例：解析 → 归一化 → 入库 → 查询。

通过 ``raganything_isolated`` 加载类型与 ``DocumentAdapter``，**无需**安装 lightrag 即可跑通骨架。
Mock 引擎仅需 ``insert_content_list`` / ``query`` 方法。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional

_RAG_ROOT = Path(__file__).resolve().parents[2]
if str(_RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(_RAG_ROOT))

from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.graph_engine.workflow_runner import WorkflowRunner
from runtime_kernel.graph.workflow_schema import WorkflowSchema  # noqa: E402
from runtime_kernel.protocols.raganything_isolated import load_raganything_types  # noqa: E402


class MockRAGAnythingBackend:
    """占位引擎：返回带 ``success`` / ``doc_id`` / ``answer_text`` 属性的简单对象。"""

    async def process_document(self, request: Any) -> Any:
        path = getattr(request, "source_path", None)
        did = getattr(request, "doc_id", None) or "mock-doc"
        return SimpleNamespace(
            success=True,
            doc_id=did,
            message="mock process_document",
            metadata={"mock": True, "source_path": path},
        )

    async def insert_content_list(self, document: Any, *, doc_id: Optional[str] = None) -> Any:
        did = doc_id or getattr(document, "doc_id", None) or "mock-doc"
        return SimpleNamespace(
            success=True,
            doc_id=did,
            message="mock insert_content_list",
            metadata={"mock": True},
        )

    async def query(self, request: Any) -> Any:
        q = getattr(request, "query", "")
        mode = getattr(request, "mode", "mix")
        return SimpleNamespace(
            answer_text=f"[mock-raganything] 已收到问题：{q!r}",
            mode=mode,
            metadata={"mock": True},
            used_vlm=False,
        )


async def main() -> None:
    # 确认隔离类型可加载（与节点内部一致）
    load_raganything_types()

    mock_eng = MockRAGAnythingBackend()
    ctx = ExecutionContext(
        workflow_id="simple_raganything",
        run_id="run-1",
        workspace="/tmp/mock_ra_workspace",
        adapters={"raganything": mock_eng},
    )

    schema = WorkflowSchema(
        workflow_id="simple_raganything",
        nodes=[
            {"id": "parse", "type": "document.parse", "config": {"mock_text": "章节一 简介"}},
            {"id": "norm", "type": "content.normalize", "config": {}},
            {
                "id": "ins",
                "type": "raganything.insert",
                "config": {"source_path": "mock://demo.pdf"},
            },
            {
                "id": "ask",
                "type": "rag.query",
                "config": {"engine": "raganything", "query": "请概括文档"},
            },
        ],
        edges=[("parse", "norm"), ("norm", "ins"), ("ins", "ask")],
        entry_node_ids=["parse"],
    )

    runner = WorkflowRunner()
    result = await runner.run(schema, ctx)
    print("success:", result.get("success"))
    for line in ctx.logs:
        print("log:", line)
    if result.get("success"):
        ask = result["node_results"].get("ask")
        if ask:
            print("查询结果:", ask.data)


if __name__ == "__main__":
    asyncio.run(main())
