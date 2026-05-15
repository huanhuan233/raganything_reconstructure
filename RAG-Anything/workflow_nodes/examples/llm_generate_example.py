"""
llm.generate 节点示例（minimal runtime）:

workflow.start -> context.build -> llm.generate -> workflow.end

运行::

    conda activate raga
    cd RAG-Anything
    python backend_runtime/examples/llm_generate_example.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.graph_engine.workflow_runner import WorkflowRunner
from runtime_kernel.graph.workflow_schema import WorkflowSchema  # noqa: E402


def build_schema() -> WorkflowSchema:
    return WorkflowSchema(
        workflow_id="llm_generate_example",
        nodes=[
            {"id": "start", "type": "workflow.start", "config": {}},
            {
                "id": "ctx",
                "type": "context.build",
                "config": {
                    "max_context_chars": 2500,
                    "max_results": 6,
                    "include_metadata": True,
                    "include_scores": True,
                    "context_format": "markdown",
                    "deduplicate_text": True,
                },
            },
            {
                "id": "llm",
                "type": "llm.generate",
                "config": {
                    "query": "",
                    "model": "demo-model",
                    "system_prompt": "你是一个严谨的知识库问答助手，请仅根据给定上下文回答问题。",
                    "answer_style": "要点式",
                    "include_references": True,
                    "temperature": 0.2,
                    "max_tokens": 1024,
                },
            },
            {"id": "end", "type": "workflow.end", "config": {}},
        ],
        edges=[("start", "ctx"), ("ctx", "llm"), ("llm", "end")],
        entry_node_ids=["start"],
    )


def build_input() -> dict[str, Any]:
    return {
        "query": "这份资料主要讲了什么？",
        "unified_results": [
            {
                "result_id": "r1",
                "source": "vector",
                "score": 0.91,
                "text": "文档重点介绍了多模态知识库构建流程，包括解析、切分、向量化与检索。",
                "metadata": {"pipeline": "text"},
            },
            {
                "result_id": "r2",
                "source": "vector",
                "score": 0.83,
                "text": "查询链路采用 vector.retrieve + retrieval.merge + context.build 的分层设计。",
                "metadata": {"pipeline": "text"},
            },
            {
                "result_id": "r3",
                "source": "graph",
                "score": 0.74,
                "text": "图谱部分强调实体关系融合与图分区隔离能力。",
                "metadata": {"pipeline": "graph"},
            },
        ],
    }


async def _demo_llm_func(prompt: str, **kwargs: Any) -> str:
    query = str(kwargs.get("query") or "").strip() or "（未知问题）"
    model = str(kwargs.get("model") or "mock-model").strip()
    return f"[mock llm:{model}] 已根据上下文回答：{query}\n(prompt_chars={len(prompt)})"


async def run_case(case_name: str, *, with_llm: bool) -> None:
    shared_data: dict[str, Any] = {}
    if with_llm:
        shared_data["llm_model_func"] = _demo_llm_func
    ctx = ExecutionContext(
        workflow_id=f"llm_generate_example_{case_name}",
        run_id="example-1",
        workspace=str((_ROOT / "output" / "llm_generate_example").resolve()),
        adapters={},
        shared_data=shared_data,
        logs=[],
    )
    result = await WorkflowRunner().run(build_schema(), ctx, initial_input=build_input())
    if not result.get("success"):
        print(f"[{case_name}] 运行失败: {result.get('error')}", file=sys.stderr)
        raise SystemExit(1)
    llm_res = (result.get("node_results") or {}).get("llm")
    data = llm_res.data if llm_res and isinstance(llm_res.data, dict) else {}
    answer = str(data.get("answer") or "")
    summary = data.get("generation_summary") if isinstance(data, dict) else {}
    if not isinstance(summary, dict):
        summary = {}
    print(f"\n=== {case_name} ===")
    print("used_llm:", summary.get("used_llm"))
    print("model:", summary.get("model"))
    print("prompt_chars:", summary.get("prompt_chars"))
    print("context_chars:", summary.get("context_chars"))
    print("answer_chars:", summary.get("answer_chars"))
    print("answer preview:")
    print(answer[:300] + ("..." if len(answer) > 300 else ""))


async def main() -> None:
    await run_case("fallback_without_llm_func", with_llm=False)
    await run_case("real_call_with_llm_func", with_llm=True)


if __name__ == "__main__":
    asyncio.run(main())
