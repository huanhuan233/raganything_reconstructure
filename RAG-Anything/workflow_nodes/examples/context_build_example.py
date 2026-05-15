"""
context.build 节点示例（minimal runtime）。

workflow.start -> retrieval.merge -> context.build -> workflow.end

运行::

    conda activate raga
    cd RAG-Anything
    python backend_runtime/examples/context_build_example.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.graph_engine.workflow_runner import WorkflowRunner
from runtime_kernel.graph.workflow_schema import WorkflowSchema  # noqa: E402


async def main() -> None:
    ctx = ExecutionContext(
        workflow_id="context_build_example",
        run_id="example-1",
        workspace=str((_ROOT / "output" / "context_build_example").resolve()),
        adapters={},
        shared_data={},
        logs=[],
    )
    schema = WorkflowSchema(
        workflow_id="context_build_example",
        nodes=[
            {"id": "start", "type": "workflow.start", "config": {}},
            {
                "id": "merge",
                "type": "retrieval.merge",
                "config": {
                    "fusion_strategy": "max_score",
                    "top_k": 10,
                    "enable_dedup": True,
                    "vector_weight": 1.0,
                    "graph_weight": 1.2,
                    "keyword_weight": 0.8,
                    "vision_weight": 1.0,
                    "min_score": 0,
                },
            },
            {
                "id": "ctx",
                "type": "context.build",
                "config": {
                    "max_context_chars": 3000,
                    "max_results": 10,
                    "include_metadata": True,
                    "include_scores": True,
                    "context_format": "markdown",
                    "deduplicate_text": True,
                },
            },
            {"id": "end", "type": "workflow.end", "config": {}},
        ],
        edges=[("start", "merge"), ("merge", "ctx"), ("ctx", "end")],
        entry_node_ids=["start"],
    )

    initial = {
        "vector_results": [
            {"record_id": "v_1", "score": 0.88, "text": "该文档讨论了气动外形优化及其工程约束。", "metadata": {"pipeline": "text"}},
            {"record_id": "v_2", "score": 0.77, "text": "报告给出材料疲劳寿命评估方法与样本数据。", "metadata": {"pipeline": "text"}},
            {"record_id": "dup_1", "score": 0.66, "text": "同一段文本用于测试去重。", "metadata": {"pipeline": "text"}},
        ],
        "graph_results": [
            {"record_id": "g_1", "score": 0.71, "text": "图谱路径提示结构节点与设计约束关联。", "metadata": {"hop": 2}},
            {"record_id": "dup_1", "score": 0.62, "text": "同一段文本用于测试去重。", "metadata": {"hop": 1}},
        ],
    }

    result = await WorkflowRunner().run(schema, ctx, initial_input=initial)
    if not result.get("success"):
        print("运行失败:", result.get("error"), file=sys.stderr)
        raise SystemExit(1)

    ctx_res = (result.get("node_results") or {}).get("ctx")
    data = ctx_res.data if ctx_res and isinstance(ctx_res.data, dict) else {}
    summary = data.get("context_summary") if isinstance(data, dict) else {}
    blocks = data.get("context_blocks") if isinstance(data, dict) else []
    cstr = data.get("context_str") if isinstance(data, dict) else ""
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(blocks, list):
        blocks = []
    if not isinstance(cstr, str):
        cstr = ""

    print("context_summary:", summary)
    print("context_blocks:", len(blocks))
    print("context_str chars:", len(cstr))
    print("context_str preview:")
    print(cstr[:600] + ("..." if len(cstr) > 600 else ""))


if __name__ == "__main__":
    asyncio.run(main())
