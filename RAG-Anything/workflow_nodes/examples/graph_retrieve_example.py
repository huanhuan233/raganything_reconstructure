"""
graph.retrieve 节点最小示例：

workflow.start -> knowledge.select -> keyword.extract -> graph.retrieve -> workflow.end
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from workflow_api.raganything_runtime import build_adapters_for_request  # noqa: E402
from workflow_api.schemas import WorkflowNodeSpec, WorkflowRunRequest  # noqa: E402
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.graph_engine.workflow_runner import WorkflowRunner
from runtime_kernel.graph.workflow_schema import WorkflowSchema  # noqa: E402


def _schema(top_k: int, mode: str) -> WorkflowSchema:
    return WorkflowSchema(
        workflow_id="graph_retrieve_example",
        nodes=[
            {"id": "start", "type": "workflow.start", "config": {}},
            {
                "id": "ks",
                "type": "knowledge.select",
                "config": {
                    "vector_backend": "milvus",
                    "graph_backend": "neo4j",
                    "workspace": "",
                },
            },
            {
                "id": "kw",
                "type": "keyword.extract",
                "config": {"keyword_mode": "rule", "max_keywords": 12},
            },
            {
                "id": "gr",
                "type": "graph.retrieve",
                "config": {
                    "implementation_mode": mode,
                    "top_k": max(1, int(top_k)),
                    "graph_backend": "auto",
                    "workspace": "",
                },
            },
            {"id": "end", "type": "workflow.end", "config": {}},
        ],
        edges=[("start", "ks"), ("ks", "kw"), ("kw", "gr"), ("gr", "end")],
        entry_node_ids=["start"],
    )


def _request_for_adapters(schema: WorkflowSchema, query: str) -> WorkflowRunRequest:
    nodes = [
        WorkflowNodeSpec(id=str(n.get("id") or ""), type=str(n.get("type") or ""), config=dict(n.get("config") or {}))
        for n in schema.nodes
    ]
    return WorkflowRunRequest(
        workflow_id=schema.workflow_id,
        nodes=nodes,
        edges=[[a, b] for a, b in schema.edges],
        entry_node_ids=list(schema.entry_node_ids),
        input_data={"query": query},
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description="graph.retrieve minimal example")
    parser.add_argument("--query", type=str, default="这报价单里制造院的对接人是谁")
    parser.add_argument("--workspace", type=str, default="test013")
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--mode", type=str, default="minimal", choices=["minimal", "lightrag_context"])
    args = parser.parse_args()

    schema = _schema(top_k=args.top_k, mode=args.mode)
    req = _request_for_adapters(schema, args.query)
    adapters = await build_adapters_for_request(req)

    ctx = ExecutionContext(
        workflow_id=schema.workflow_id,
        run_id="example-1",
        workspace=str((_ROOT / "output" / "graph_retrieve_example").resolve()),
        adapters=adapters,
        shared_data={"query": args.query},
        logs=[],
    )

    initial = {
        "query": args.query,
        "selected_knowledge": {
            "graph_backend": "neo4j",
            "graph_workspace": args.workspace,
            "workspace": args.workspace,
        },
    }
    result = await WorkflowRunner().run(schema, ctx, initial_input=initial)
    if not result.get("success"):
        print("运行失败:", result.get("error"), file=sys.stderr)
        raise SystemExit(1)

    gr = (result.get("node_results") or {}).get("gr")
    data = gr.data if gr and isinstance(gr.data, dict) else {}
    summary = data.get("graph_summary") if isinstance(data, dict) else {}
    rows = data.get("graph_results") if isinstance(data, dict) else []
    print("graph_summary:", json.dumps(summary, ensure_ascii=False, indent=2))
    print("graph_results_count:", len(rows) if isinstance(rows, list) else 0)
    if isinstance(summary, dict):
        ws = summary.get("warnings")
        if isinstance(ws, list) and ws:
            print("warnings:")
            for w in ws:
                print("-", w)


if __name__ == "__main__":
    # 避免示例在未配置 .env 时直接崩；如需真实 Neo4j，请配置 NEO4J_* 与 LLM key。
    os.environ.setdefault("PYTHONUTF8", "1")
    asyncio.run(main())

