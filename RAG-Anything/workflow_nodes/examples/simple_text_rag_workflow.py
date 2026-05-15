"""
纯文本 LightRAG 链路示例：文本入口 → 入库 → 查询。

运行::

    cd RAG-Anything
    set PYTHONPATH=.
    python workflow_nodes/examples/simple_text_rag_workflow.py

使用 **Mock 适配器**（仅需实现 ``insert_document`` / ``query``），无需安装 lightrag。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, List, Union

_RAG_ROOT = Path(__file__).resolve().parents[2]
if str(_RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(_RAG_ROOT))

from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.graph_engine.workflow_runner import WorkflowRunner
from runtime_kernel.graph.workflow_schema import WorkflowSchema
from runtime_kernel.node_runtime.node_registry import get_default_registry
from runtime_kernel.node_runtime.base_node import BaseNode  # noqa: E402
from runtime_kernel.entities.node_result import NodeResult  # noqa: E402


class TextInputMockNode(BaseNode):
    """演示用文本源头节点，将配置中的静态文本写入下游。"""

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        text = str(self.config.get("text", "默认演示文本：骨架可编排。"))
        return NodeResult(
            success=True,
            data={"text": text, "mock_source": True},
            metadata={"kind": "text_input_mock"},
        )


class MockLightRAGBackend:
    """不依赖 ``LightRAGEngineAdapter`` 类，供入库/查询烟测。"""

    def insert_document(
        self,
        input: Union[str, List[str]],
        *,
        split_by_character=None,
        split_by_character_only: bool = False,
        ids=None,
        file_paths=None,
        track_id=None,
    ) -> str:
        return "mock-track-id"

    def query(self, query: str, param: Any = None, system_prompt: Any = None) -> str:
        return f"[mock-lightrag] 关于「{query[:20]}...」的占位回答"

    def delete_document(self, doc_id: str, *, delete_llm_cache: bool = False) -> Any:
        from types import SimpleNamespace

        return SimpleNamespace(doc_id=doc_id, deleted=True, mock=True)


async def main() -> None:
    reg = get_default_registry()
    reg.register("demo.text_input", TextInputMockNode)

    mock_engine = MockLightRAGBackend()
    ctx = ExecutionContext(
        workflow_id="simple_text_rag",
        run_id="run-1",
        workspace="/tmp/mock_workspace",
        adapters={"lightrag": mock_engine},
    )

    schema = WorkflowSchema(
        workflow_id="simple_text_rag",
        nodes=[
            {
                "id": "src",
                "type": "demo.text_input",
                "config": {"text": "RAG Anything 工作流骨架"},
            },
            {"id": "insert", "type": "lightrag.insert", "config": {}},
            {
                "id": "ask",
                "type": "rag.query",
                "config": {
                    "engine": "lightrag",
                    "query": "这段内容在说什么？",
                },
            },
        ],
        edges=[("src", "insert"), ("insert", "ask")],
        entry_node_ids=["src"],
    )

    runner = WorkflowRunner(registry=reg)
    result = await runner.run(schema, ctx, initial_input=None)
    print("success:", result.get("success"))
    for line in ctx.logs:
        print("log:", line)
    if result.get("success"):
        last = result["node_results"].get("ask")
        if last:
            print("最终查询输出 data:", last.data)


if __name__ == "__main__":
    asyncio.run(main())
