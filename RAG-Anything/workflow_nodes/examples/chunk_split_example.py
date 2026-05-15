"""
chunk.split 节点示例：
workflow.start -> document.parse -> content.filter -> multimodal.process -> content.route -> chunk.split -> workflow.end
"""

from __future__ import annotations

import argparse
import asyncio
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


def _resolve_source_path(raw: str | None) -> str:
    if raw:
        p = Path(raw)
        if not p.is_absolute():
            p = (_ROOT / p).resolve()
        return str(p)
    return str((_ROOT / "Inputs" / "3.pdf").resolve())


def _request_for_adapters(schema: WorkflowSchema, source_path: str) -> WorkflowRunRequest:
    nodes = [
        WorkflowNodeSpec(
            id=str(n.get("id") or ""),
            type=str(n.get("type") or ""),
            config=dict(n.get("config") or {}),
        )
        for n in schema.nodes
    ]
    return WorkflowRunRequest(
        workflow_id=schema.workflow_id,
        nodes=nodes,
        edges=[[a, b] for a, b in schema.edges],
        entry_node_ids=list(schema.entry_node_ids),
        input_data={"source_path": source_path},
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description="chunk.split node example")
    parser.add_argument("--source", type=str, default=None, help="本地 PDF 路径（默认 Inputs/3.pdf）")
    args = parser.parse_args()

    source_path = _resolve_source_path(args.source)
    if not Path(source_path).is_file():
        print(f"文件不存在: {source_path}", file=sys.stderr)
        raise SystemExit(2)

    schema = WorkflowSchema(
        workflow_id="chunk_split_example",
        nodes=[
            {"id": "start", "type": "workflow.start", "config": {}},
            {
                "id": "parse",
                "type": "document.parse",
                "config": {"source_path": source_path, "parser": "mineru", "parse_method": "auto"},
            },
            {
                "id": "filter",
                "type": "content.filter",
                "config": {"drop_empty": True, "keep_page_numbers": True},
            },
            {
                "id": "mm",
                "type": "multimodal.process",
                "config": {"use_vlm": False},
            },
            {
                "id": "route",
                "type": "content.route",
                "config": {"keep_unrouted": True, "drop_discard_types": True},
            },
            {
                "id": "chunk",
                "type": "chunk.split",
                "config": {
                    "chunk_token_size": 1200,
                    "chunk_overlap_token_size": 100,
                    "include_multimodal_descriptions": True,
                    "skip_pipelines": ["discard_pipeline"],
                },
            },
            {"id": "end", "type": "workflow.end", "config": {}},
        ],
        edges=[
            ("start", "parse"),
            ("parse", "filter"),
            ("filter", "mm"),
            ("mm", "route"),
            ("route", "chunk"),
            ("chunk", "end"),
        ],
        entry_node_ids=["start"],
    )

    adapters = await build_adapters_for_request(_request_for_adapters(schema, source_path))
    ctx = ExecutionContext(
        workflow_id="chunk_split_example",
        run_id="example-1",
        workspace=str((_ROOT / "output" / "chunk_split_example").resolve()),
        adapters=adapters,
        shared_data={},
        logs=[],
    )
    result = await WorkflowRunner().run(schema, ctx, initial_input={"source_path": source_path})
    if not result.get("success"):
        print("运行失败:", result.get("error"), file=sys.stderr)
        for nid, node_res in (result.get("node_results") or {}).items():
            if not node_res.success:
                print(f"失败节点 {nid}: {node_res.error}", file=sys.stderr)
        raise SystemExit(1)

    chunk_node = (result.get("node_results") or {}).get("chunk")
    data = chunk_node.data if chunk_node and isinstance(chunk_node.data, dict) else {}
    summary = data.get("chunk_summary") if isinstance(data, dict) else {}
    chunks = data.get("chunks") if isinstance(data, dict) else []
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(chunks, list):
        chunks = []

    print("total_chunks:", summary.get("total_chunks", 0))
    print("pipeline_distribution:", summary.get("pipeline_distribution", {}))
    print("preview_chunks:")
    for one in chunks[:3]:
        if not isinstance(one, dict):
            continue
        txt = str(one.get("text") or "").replace("\n", " ").strip()
        if len(txt) > 120:
            txt = f"{txt[:120]}..."
        print("-", txt)


if __name__ == "__main__":
    asyncio.run(main())

