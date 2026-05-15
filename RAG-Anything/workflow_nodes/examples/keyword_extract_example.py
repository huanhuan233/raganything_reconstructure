"""
keyword.extract 节点示例：

- case1_rule: 规则抽取（无模型可运行）
- case2_llm: 通过 shared_data 注入 llm_model_func 的 LLM 抽取

运行::

    conda activate raga
    cd RAG-Anything
    python backend_runtime/examples/keyword_extract_example.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.graph_engine.workflow_runner import WorkflowRunner
from runtime_kernel.graph.workflow_schema import WorkflowSchema  # noqa: E402


async def _run_case(case_name: str, cfg: dict, initial_input: dict, shared_data: dict | None = None) -> None:
    ctx = ExecutionContext(
        workflow_id=f"keyword_extract_{case_name}",
        run_id="example-1",
        workspace=str((_ROOT / "output" / "keyword_extract_example").resolve()),
        adapters={},
        shared_data=shared_data or {},
        logs=[],
    )
    schema = WorkflowSchema(
        workflow_id=f"keyword_extract_{case_name}",
        nodes=[
            {"id": "start", "type": "workflow.start", "config": {}},
            {"id": "kw", "type": "keyword.extract", "config": cfg},
            {"id": "end", "type": "workflow.end", "config": {}},
        ],
        edges=[("start", "kw"), ("kw", "end")],
        entry_node_ids=["start"],
    )
    res = await WorkflowRunner().run(schema, ctx, initial_input=initial_input)
    if not res.get("success"):
        raise RuntimeError(f"{case_name} failed: {res.get('error')}")
    kw_res = (res.get("node_results") or {}).get("kw")
    data = kw_res.data if kw_res and isinstance(kw_res.data, dict) else {}
    summary = data.get("keyword_summary") if isinstance(data, dict) else {}
    print(f"\n=== {case_name} ===")
    print("mode:", (summary or {}).get("mode"))
    print("source_algorithm:", (summary or {}).get("source_algorithm"))
    print("total:", (summary or {}).get("total"))
    print("high_level_keywords:", (data or {}).get("high_level_keywords"))
    print("low_level_keywords:", (data or {}).get("low_level_keywords"))


async def _demo_llm_func(prompt: str, **_: object) -> str:
    # 仅用于示例：模拟模型返回。
    _ = prompt
    return json.dumps(
        {
            "high_level_keywords": ["RAG pipeline", "keyword extraction"],
            "low_level_keywords": ["query parsing", "json output"],
        },
        ensure_ascii=False,
    )


async def main() -> None:
    await _run_case(
        "case1_rule",
        cfg={
            "keyword_mode": "rule",
            "max_keywords": 8,
            "language": "zh",
            "fallback_to_rule": False,
        },
        initial_input={"query": "多模态RAG系统里，如何提高关键词召回的稳定性和可解释性？"},
    )

    await _run_case(
        "case2_llm",
        cfg={
            "keyword_mode": "llm",
            "max_keywords": 8,
            "language": "auto",
            "fallback_to_rule": False,
        },
        initial_input={"query": "How to improve keyword extraction quality in a RAG pipeline?"},
        shared_data={"llm_model_func": _demo_llm_func},
    )


if __name__ == "__main__":
    asyncio.run(main())

