"""
vector.retrieve 最小示例：
workflow.start -> vector.retrieve -> workflow.end

默认写入本地 runtime_storage/text.jsonl 并走 local_jsonl 兜底检索。

运行::

    conda activate raga
    cd RAG-Anything
    python backend_runtime/examples/vector_retrieve_example.py
"""

from __future__ import annotations

import argparse
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


def _prepare_local_jsonl(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    samples = [
        {
            "record_id": "demo_001",
            "pipeline": "text_pipeline",
            "content_type": "text",
            "text": "RAG-Anything 支持多模态解析与向量化存储。",
            "metadata": {"source_path": "demo-a.pdf"},
        },
        {
            "record_id": "demo_002",
            "pipeline": "text_pipeline",
            "content_type": "text",
            "text": "Neo4j 图分区可以用于同库多租户隔离。",
            "metadata": {"source_path": "demo-b.pdf"},
        },
        {
            "record_id": "demo_003",
            "pipeline": "text_pipeline",
            "content_type": "text",
            "text": "Milvus 常用于语义向量检索。",
            "metadata": {"source_path": "demo-c.pdf"},
        },
    ]
    with path.open("w", encoding="utf-8") as f:
        for one in samples:
            f.write(json.dumps(one, ensure_ascii=False) + "\n")


async def main() -> None:
    parser = argparse.ArgumentParser(description="vector.retrieve minimal example")
    parser.add_argument(
        "--out-dir",
        type=str,
        default=None,
        help="workspace 根目录（默认 output/vector_retrieve_example）",
    )
    parser.add_argument("--query", type=str, default="图分区", help="检索文本")
    parser.add_argument("--top-k", type=int, default=5, help="返回上限")
    args = parser.parse_args()

    workspace = args.out_dir or str((_ROOT / "output" / "vector_retrieve_example").resolve())
    local_path = Path(workspace) / "runtime_storage" / "text.jsonl"
    _prepare_local_jsonl(local_path)

    ctx = ExecutionContext(
        workflow_id="vector_retrieve_example",
        run_id="example-1",
        workspace=workspace,
        adapters={},
        shared_data={},
        logs=[],
    )

    schema = WorkflowSchema(
        workflow_id="vector_retrieve_example",
        nodes=[
            {"id": "start", "type": "workflow.start", "config": {}},
            {"id": "vr", "type": "vector.retrieve", "config": {"top_k": max(1, int(args.top_k))}},
            {"id": "end", "type": "workflow.end", "config": {}},
        ],
        edges=[("start", "vr"), ("vr", "end")],
        entry_node_ids=["start"],
    )

    initial = {
        "query": args.query,
        "query_vector": None,
        "storage_strategy": {
            "text_pipeline": [{"backend": "local_jsonl", "path": str(local_path)}],
        },
    }
    result = await WorkflowRunner().run(schema, ctx, initial_input=initial)
    if not result.get("success"):
        print("运行失败:", result.get("error"), file=sys.stderr)
        raise SystemExit(1)

    vr_res = (result.get("node_results") or {}).get("vr")
    data = vr_res.data if vr_res and isinstance(vr_res.data, dict) else {}
    summary = data.get("retrieve_summary") or {}
    rows = data.get("vector_results") or []
    print("retrieve_summary:", summary)
    print("vector_results top3:")
    if isinstance(rows, list):
        for i, one in enumerate(rows[:3], start=1):
            if not isinstance(one, dict):
                continue
            txt = str(one.get("text") or "").replace("\n", " ").strip()
            if len(txt) > 96:
                txt = txt[:96] + "..."
            print(f"  [{i}] backend={one.get('backend')} score={one.get('score')} text={txt}")


if __name__ == "__main__":
    asyncio.run(main())
