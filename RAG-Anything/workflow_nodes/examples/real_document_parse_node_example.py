"""
真实 document.parse 节点示例：
workflow.start -> document.parse -> workflow.end

运行：
    python backend_runtime/examples/real_document_parse_node_example.py --source Inputs/3.pdf
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
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
    parser = argparse.ArgumentParser(description="real document.parse node example")
    parser.add_argument("--source", type=str, default=None, help="本地 PDF 路径（默认 Inputs/3.pdf）")
    parser.add_argument("--parser", type=str, default="mineru", help="解析器（当前仅支持 mineru）")
    parser.add_argument("--parse-method", type=str, default="auto", choices=["auto", "ocr", "txt"])
    args = parser.parse_args()

    source_path = _resolve_source_path(args.source)
    if not Path(source_path).is_file():
        print(f"文件不存在: {source_path}", file=sys.stderr)
        raise SystemExit(2)

    ctx = ExecutionContext(
        workflow_id="real_document_parse",
        run_id="example-1",
        workspace=str((_ROOT / "output" / "real_document_parse").resolve()),
        adapters={},
        shared_data={},
        logs=[],
    )

    schema = WorkflowSchema(
        workflow_id="real_document_parse",
        nodes=[
            {"id": "start", "type": "workflow.start", "config": {}},
            {
                "id": "parse",
                "type": "document.parse",
                "config": {
                    "source_path": source_path,
                    "parser": args.parser,
                    "parse_method": args.parse_method,
                },
            },
            {"id": "end", "type": "workflow.end", "config": {}},
        ],
        edges=[("start", "parse"), ("parse", "end")],
        entry_node_ids=["start"],
    )

    runner = WorkflowRunner()
    result = await runner.run(schema, ctx, initial_input={"source_path": source_path})
    if not result.get("success"):
        print("运行失败:", result.get("error"), file=sys.stderr)
        for nid, node_res in (result.get("node_results") or {}).items():
            if not node_res.success:
                print(f"失败节点 {nid}: {node_res.error}", file=sys.stderr)
        raise SystemExit(1)

    parse_node = (result.get("node_results") or {}).get("parse")
    data = parse_node.data if parse_node and parse_node.data else {}
    content_list = data.get("content_list") if isinstance(data, dict) else []
    if not isinstance(content_list, list):
        content_list = []
    counter = Counter(str(item.get("type", "unknown")) for item in content_list if isinstance(item, dict))

    print("source_path:", data.get("source_path"))
    print("content_list_count:", len(content_list))
    print("block_type_stats:", dict(counter))


if __name__ == "__main__":
    asyncio.run(main())
