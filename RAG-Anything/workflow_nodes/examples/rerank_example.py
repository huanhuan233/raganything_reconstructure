"""
rerank 节点示例：

vector.retrieve + graph.retrieve（模拟输入）
-> retrieval.merge -> rerank -> context.build -> workflow.end
"""

from __future__ import annotations

import asyncio
import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.graph_engine.workflow_runner import WorkflowRunner
from runtime_kernel.graph.workflow_schema import WorkflowSchema  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser(description="rerank node example")
    parser.add_argument("--engine", type=str, default="runtime", choices=["runtime", "lightrag"], help="rerank engine")
    args = parser.parse_args()
    ctx = ExecutionContext(
        workflow_id="rerank_example",
        run_id="example-1",
        workspace=str((_ROOT / "output" / "rerank_example").resolve()),
        adapters={},
        shared_data={},
        logs=[],
    )
    schema = WorkflowSchema(
        workflow_id="rerank_example",
        nodes=[
            {"id": "start", "type": "workflow.start", "config": {}},
            {"id": "merge", "type": "retrieval.merge", "config": {"fusion_strategy": "weighted_sum", "top_k": 20}},
            {
                "id": "rerank",
                "type": "rerank",
                "config": {
                    "rerank_engine": args.engine,
                    "rerank_model": "none",
                    "top_k": 8,
                    "score_threshold": 0.0,
                    "graph_boost": 0.15,
                    "keyword_boost": 0.12,
                    "diversity_boost": 0.06,
                },
            },
            {"id": "ctx", "type": "context.build", "config": {"max_results": 6, "include_scores": True}},
            {"id": "end", "type": "workflow.end", "config": {}},
        ],
        edges=[("start", "merge"), ("merge", "rerank"), ("rerank", "ctx"), ("ctx", "end")],
        entry_node_ids=["start"],
    )
    initial = {
        "query": "飞机装配工艺里普通铆接的质量要求是什么？",
        "vector_results": [
            {"record_id": "v1", "score": 0.86, "text": "普通铆接应满足孔位同轴度和铆钉成形高度要求。"},
            {"record_id": "v2", "score": 0.78, "text": "铆接前需完成毛刺去除并进行表面清洁。"},
            {"record_id": "v3", "score": 0.67, "text": "扭矩校准主要针对螺栓连接，不适用于普通铆接。"},
        ],
        "graph_results": [
            {"record_id": "g1", "score": 0.73, "text": "质量验收包含铆钉头形状、裂纹、间隙等检查项。"},
            {"record_id": "g2", "score": 0.64, "text": "返修流程强调先判定孔壁损伤等级后再补铆。"},
        ],
    }
    result = await WorkflowRunner().run(schema, ctx, initial_input=initial)
    if not result.get("success"):
        print("运行失败:", result.get("error"), file=sys.stderr)
        raise SystemExit(1)
    rr = (result.get("node_results") or {}).get("rerank")
    data = rr.data if rr and isinstance(rr.data, dict) else {}
    summary = data.get("rerank_summary") if isinstance(data, dict) else {}
    rows = data.get("reranked_results") if isinstance(data, dict) else []
    print("rerank_summary:", summary)
    print("top reranked:")
    for idx, one in enumerate(rows[:5] if isinstance(rows, list) else [], start=1):
        if not isinstance(one, dict):
            continue
        print(
            f"  [{idx}] score={one.get('score')} -> rerank={one.get('rerank_score')} "
            f"source={one.get('source_type')} text={str(one.get('content') or '')[:60]}"
        )


if __name__ == "__main__":
    asyncio.run(main())
