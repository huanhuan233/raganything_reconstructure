"""
embedding.index 节点示例：
workflow.start -> document.parse -> content.filter -> multimodal.process -> content.route -> embedding.index -> workflow.end
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

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


async def main() -> None:
    parser = argparse.ArgumentParser(description="embedding.index node example")
    parser.add_argument("--source", type=str, default=None, help="本地 PDF 路径（默认 Inputs/3.pdf）")
    args = parser.parse_args()

    source_path = _resolve_source_path(args.source)
    if not Path(source_path).is_file():
        print(f"文件不存在: {source_path}", file=sys.stderr)
        raise SystemExit(2)

    ctx = ExecutionContext(
        workflow_id="embedding_index_example",
        run_id="example-1",
        workspace=str((_ROOT / "output" / "embedding_index_example").resolve()),
        adapters={},
        shared_data={},
        logs=[],
    )

    schema = WorkflowSchema(
        workflow_id="embedding_index_example",
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
                "config": {
                    "use_vlm": False,
                    "process_types": ["table", "seal", "image", "equation", "sheet", "footer", "page_number"],
                },
            },
            {"id": "route", "type": "content.route", "config": {"keep_unrouted": True, "drop_discard_types": True}},
            {
                "id": "emb",
                "type": "embedding.index",
                "config": {
                    "include_raw_item": True,
                    "allow_without_vector": True,
                    "batch_size": 16,
                },
            },
            {"id": "end", "type": "workflow.end", "config": {}},
        ],
        edges=[
            ("start", "parse"),
            ("parse", "filter"),
            ("filter", "mm"),
            ("mm", "route"),
            ("route", "emb"),
            ("emb", "end"),
        ],
        entry_node_ids=["start"],
    )

    result = await WorkflowRunner().run(schema, ctx, initial_input={"source_path": source_path})
    if not result.get("success"):
        print("运行失败:", result.get("error"), file=sys.stderr)
        for nid, node_res in (result.get("node_results") or {}).items():
            if not node_res.success:
                print(f"失败节点 {nid}: {node_res.error}", file=sys.stderr)
        raise SystemExit(1)

    emb_node = (result.get("node_results") or {}).get("emb")
    data = emb_node.data if emb_node and emb_node.data else {}
    summary = data.get("embedding_summary") if isinstance(data, dict) else {}
    records = data.get("embedding_records") if isinstance(data, dict) else []

    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(records, list):
        records = []

    print("total_records:", summary.get("total_records"))
    print("pipeline_distribution:", summary.get("pipeline_distribution"))
    print("with_vector:", summary.get("with_vector"))
    print("without_vector:", summary.get("without_vector"))
    print("top3_text_preview:")
    for i, one in enumerate(records[:3], start=1):
        if not isinstance(one, dict):
            continue
        txt = str(one.get("text", "")).strip().replace("\n", " ")
        if len(txt) > 120:
            txt = txt[:120] + "..."
        print(f"  [{i}] {txt}")


if __name__ == "__main__":
    asyncio.run(main())
