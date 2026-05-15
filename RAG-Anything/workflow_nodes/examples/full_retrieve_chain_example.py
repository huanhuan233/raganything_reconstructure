"""
完整链路示例：
workflow.start -> document.parse -> content.filter -> multimodal.process -> content.route
-> embedding.index -> storage.persist -> vector.retrieve -> workflow.end
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
    parser = argparse.ArgumentParser(description="full chain with storage.persist + vector.retrieve")
    parser.add_argument("--source", type=str, default=None, help="本地 PDF 路径（默认 Inputs/3.pdf）")
    parser.add_argument("--query", type=str, default="这份文档讲了什么", help="检索问题")
    parser.add_argument(
        "--out-dir",
        type=str,
        default=None,
        help="workspace 根目录（默认 output/full_retrieve_chain_example）",
    )
    parser.add_argument("--top-k", type=int, default=10, help="vector.retrieve top_k")
    args = parser.parse_args()

    source_path = _resolve_source_path(args.source)
    if not Path(source_path).is_file():
        print(f"文件不存在: {source_path}", file=sys.stderr)
        raise SystemExit(2)

    workspace = args.out_dir or str((_ROOT / "output" / "full_retrieve_chain_example").resolve())
    ctx = ExecutionContext(
        workflow_id="full_retrieve_chain_example",
        run_id="example-1",
        workspace=workspace,
        adapters={},
        shared_data={},
        logs=[],
    )

    schema = WorkflowSchema(
        workflow_id="full_retrieve_chain_example",
        nodes=[
            {"id": "start", "type": "workflow.start", "config": {}},
            {
                "id": "parse",
                "type": "document.parse",
                "config": {"source_path": source_path, "parser": "mineru", "parse_method": "auto"},
            },
            {"id": "filter", "type": "content.filter", "config": {"drop_empty": True, "keep_page_numbers": True}},
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
            {
                "id": "persist",
                "type": "storage.persist",
                "config": {
                    "vector_storage": {
                        "backend": "milvus",
                        "mode": "existing",
                        "collection": "",
                        "dimension": 0,
                        "metric_type": "COSINE",
                        "index_type": "IVF_FLAT",
                        "auto_create_index": True,
                        "create_if_missing": False,
                    },
                    "graph_storage": {
                        "backend": "neo4j",
                        "mode": "existing",
                        "database": "neo4j",
                        "graph_partition": "",
                        "create_if_missing": False,
                        "auto_create_constraints": True,
                    },
                },
            },
            {"id": "vr", "type": "vector.retrieve", "config": {"top_k": max(1, int(args.top_k))}},
            {"id": "end", "type": "workflow.end", "config": {}},
        ],
        edges=[
            ("start", "parse"),
            ("parse", "filter"),
            ("filter", "mm"),
            ("mm", "route"),
            ("route", "emb"),
            ("emb", "persist"),
            ("persist", "vr"),
            ("vr", "end"),
        ],
        entry_node_ids=["start"],
    )

    initial = {"source_path": source_path, "query": args.query}
    result = await WorkflowRunner().run(schema, ctx, initial_input=initial)
    if not result.get("success"):
        print("运行失败:", result.get("error"), file=sys.stderr)
        for nid, node_res in (result.get("node_results") or {}).items():
            if not node_res.success:
                print(f"失败节点 {nid}: {node_res.error}", file=sys.stderr)
        raise SystemExit(1)

    vr_res = (result.get("node_results") or {}).get("vr")
    data = vr_res.data if vr_res and isinstance(vr_res.data, dict) else {}
    print("retrieve_summary:", data.get("retrieve_summary"))
    print("vector_results size:", len(data.get("vector_results") or []))


if __name__ == "__main__":
    asyncio.run(main())
