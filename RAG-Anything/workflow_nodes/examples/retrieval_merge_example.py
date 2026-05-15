"""
retrieval.merge 节点示例（minimal runtime）:

示例1：仅 vector_results
示例2：vector_results + graph_results（含重复 record_id）

运行::

    conda activate raga
    cd RAG-Anything
    python backend_runtime/examples/retrieval_merge_example.py
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


async def _run_case(case_name: str, initial_input: dict, cfg: dict) -> None:
    ctx = ExecutionContext(
        workflow_id=f"retrieval_merge_example_{case_name}",
        run_id="example-1",
        workspace=str((_ROOT / "output" / "retrieval_merge_example").resolve()),
        adapters={},
        shared_data={},
        logs=[],
    )
    schema = WorkflowSchema(
        workflow_id=f"retrieval_merge_example_{case_name}",
        nodes=[
            {"id": "start", "type": "workflow.start", "config": {}},
            {"id": "merge", "type": "retrieval.merge", "config": cfg},
            {"id": "end", "type": "workflow.end", "config": {}},
        ],
        edges=[("start", "merge"), ("merge", "end")],
        entry_node_ids=["start"],
    )
    result = await WorkflowRunner().run(schema, ctx, initial_input=initial_input)
    if not result.get("success"):
        print(f"[{case_name}] 运行失败: {result.get('error')}", file=sys.stderr)
        raise SystemExit(1)
    merge_res = (result.get("node_results") or {}).get("merge")
    data = merge_res.data if merge_res and isinstance(merge_res.data, dict) else {}
    summary = data.get("merge_summary") if isinstance(data, dict) else {}
    rows = data.get("unified_results") if isinstance(data, dict) else []
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(rows, list):
        rows = []
    print(f"\n=== {case_name} ===")
    print("total_input:", summary.get("total_input"))
    print("total_output:", summary.get("total_output"))
    print("deduplicated:", summary.get("deduplicated"))
    print("source_distribution:", summary.get("source_distribution"))
    print("top3 unified_results:")
    for i, one in enumerate(rows[:3], start=1):
        if not isinstance(one, dict):
            continue
        print(
            f"  [{i}] result_id={one.get('result_id')} sources={one.get('sources')} "
            f"score={one.get('score')} text={str(one.get('text') or '')[:60]}"
        )


async def main() -> None:
    # 示例 1：只有 vector_results
    case1_input = {
        "vector_results": [
            {"record_id": "v1", "score": 0.81, "text": "飞机结构设计基础知识"},
            {"record_id": "v2", "score": 0.74, "text": "飞控系统与传感器融合方法"},
            {"record_id": "v3", "score": 0.69, "text": "发动机热管理与可靠性"},
        ]
    }
    case1_cfg = {
        "fusion_strategy": "max_score",
        "top_k": 10,
        "enable_dedup": True,
        "vector_weight": 1.0,
        "graph_weight": 1.2,
        "keyword_weight": 0.8,
        "vision_weight": 1.0,
        "min_score": 0,
    }
    await _run_case("case1_vector_only", case1_input, case1_cfg)

    # 示例 2：vector + graph（包含重复 record_id）
    case2_input = {
        "vector_results": [
            {"record_id": "r_1001", "score": 0.82, "text": "机翼气动外形优化"},
            {"record_id": "r_1002", "score": 0.77, "text": "材料疲劳寿命评估"},
            {"record_id": "r_1003", "score": 0.61, "text": "航电总线通信机制"},
        ],
        "graph_results": [
            {"record_id": "r_1001", "score": 0.66, "text": "机翼气动外形优化", "metadata": {"hop": 1}},
            {"record_id": "r_2001", "score": 0.71, "text": "结构节点拓扑约束", "metadata": {"hop": 2}},
        ],
    }
    case2_cfg = {
        "fusion_strategy": "weighted_sum",
        "top_k": 10,
        "enable_dedup": True,
        "vector_weight": 1.0,
        "graph_weight": 1.2,
        "keyword_weight": 0.8,
        "vision_weight": 1.0,
        "min_score": 0,
    }
    await _run_case("case2_vector_graph_dedup", case2_input, case2_cfg)


if __name__ == "__main__":
    asyncio.run(main())
