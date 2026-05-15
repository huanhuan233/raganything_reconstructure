"""
entity_relation.extract 节点示例：
workflow.start -> document.parse -> content.filter -> multimodal.process -> content.route -> chunk.split -> entity_relation.extract -> workflow.end
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
    parser = argparse.ArgumentParser(description="entity_relation.extract node example")
    parser.add_argument("--source", type=str, default=None, help="本地 PDF 路径（默认 Inputs/3.pdf）")
    args = parser.parse_args()

    source_path = _resolve_source_path(args.source)
    if not Path(source_path).is_file():
        print(f"文件不存在: {source_path}", file=sys.stderr)
        raise SystemExit(2)

    schema = WorkflowSchema(
        workflow_id="entity_relation_extract_example",
        nodes=[
            {"id": "start", "type": "workflow.start", "config": {}},
            {
                "id": "parse",
                "type": "document.parse",
                "config": {"source_path": source_path, "parser": "mineru", "parse_method": "auto"},
            },
            {"id": "filter", "type": "content.filter", "config": {"drop_empty": True, "keep_page_numbers": True}},
            {"id": "mm", "type": "multimodal.process", "config": {"use_vlm": False}},
            {"id": "route", "type": "content.route", "config": {"keep_unrouted": True, "drop_discard_types": True}},
            {
                "id": "chunk",
                "type": "chunk.split",
                "config": {"chunk_token_size": 1200, "chunk_overlap_token_size": 100},
            },
            {
                "id": "er",
                "type": "entity_relation.extract",
                "config": {
                    "model": "default",
                    "entity_extract_max_gleaning": 1,
                    "language": "auto",
                    "include_multimodal_chunks": True,
                    "max_chunks": 50,
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
            ("chunk", "er"),
            ("er", "end"),
        ],
        entry_node_ids=["start"],
    )

    adapters = await build_adapters_for_request(_request_for_adapters(schema, source_path))
    ctx = ExecutionContext(
        workflow_id="entity_relation_extract_example",
        run_id="example-1",
        workspace=str((_ROOT / "output" / "entity_relation_extract_example").resolve()),
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

    er_node = (result.get("node_results") or {}).get("er")
    data = er_node.data if er_node and isinstance(er_node.data, dict) else {}
    summary = data.get("entity_relation_summary") if isinstance(data, dict) else {}
    entities = data.get("entities") if isinstance(data, dict) else []
    relations = data.get("relations") if isinstance(data, dict) else []
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(entities, list):
        entities = []
    if not isinstance(relations, list):
        relations = []

    print("entity_count:", summary.get("entity_count", len(entities)))
    print("relation_count:", summary.get("relation_count", len(relations)))
    print("entities top5:")
    for one in entities[:5]:
        if not isinstance(one, dict):
            continue
        print("-", one.get("entity_name"), "|", one.get("entity_type"))
    print("relations top5:")
    for one in relations[:5]:
        if not isinstance(one, dict):
            continue
        print("-", one.get("source_entity"), "->", one.get("target_entity"), "|", one.get("relation_type"))


if __name__ == "__main__":
    asyncio.run(main())

