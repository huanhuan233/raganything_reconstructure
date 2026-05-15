"""
storage.persist 节点示例：使用结构化 vector_storage / graph_storage（由前端编排写入）。

无 Milvus/Neo4j 时：collection / database 留空则仅 local_jsonl；若填写 collection 且无服务则 Milvus 步骤为 skipped。

运行::

    conda activate raga
    cd RAG-Anything
    python backend_runtime/examples/storage_persist_example.py
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


async def main() -> None:
    parser = argparse.ArgumentParser(description="storage.persist example (structured config)")
    parser.add_argument(
        "--out-dir",
        type=str,
        default=None,
        help="workspace 根目录（默认 output/storage_persist_example）",
    )
    args = parser.parse_args()

    workspace = args.out_dir or str((_ROOT / "output" / "storage_persist_example").resolve())

    embedding_records = [
        {
            "record_id": "emb_demo_no_vec",
            "pipeline": "text_pipeline",
            "content_type": "text",
            "text": "无向量样例，仅应写入 local_jsonl。",
            "vector": None,
            "vector_dim": None,
            "embedding_provider": "none",
            "embedding_model": "none",
            "metadata": {"source_path": "demo.pdf", "page_idx": 0},
            "raw_item": {"type": "text", "text": "raw"},
        },
        {
            "record_id": "emb_demo_with_vec",
            "pipeline": "text_pipeline",
            "content_type": "text",
            "text": "有向量样例。",
            "vector": [0.01, 0.02, 0.03, 0.04],
            "vector_dim": 4,
            "embedding_provider": "mock",
            "embedding_model": "mock-4d",
            "metadata": {"source_path": "demo.pdf", "page_idx": 1},
            "raw_item": None,
        },
    ]
    embedding_summary = {"total_records": len(embedding_records), "with_vector": 1, "without_vector": 1}

    # 与编排面板保存结构一致；collection 非空时会尝试 Milvus（无 URI 则 skipped）
    vector_storage = {
        "backend": "milvus",
        "mode": "existing",
        "collection": "rag_text_chunks_demo",
        "dimension": 0,
        "metric_type": "COSINE",
        "index_type": "IVF_FLAT",
        "auto_create_index": True,
        "create_if_missing": False,
    }
    graph_storage = {
        "backend": "neo4j",
        "mode": "existing",
        "database": "neo4j",
        "graph_partition": "",
        "create_if_missing": False,
        "auto_create_constraints": True,
    }

    ctx = ExecutionContext(
        workflow_id="storage_persist_example",
        run_id="example-1",
        workspace=workspace,
        adapters={},
        shared_data={},
        logs=[],
    )

    schema = WorkflowSchema(
        workflow_id="storage_persist_example",
        nodes=[
            {"id": "start", "type": "workflow.start", "config": {}},
            {
                "id": "store",
                "type": "storage.persist",
                "config": {
                    "vector_storage": vector_storage,
                    "graph_storage": graph_storage,
                },
            },
            {"id": "end", "type": "workflow.end", "config": {}},
        ],
        edges=[("start", "store"), ("store", "end")],
        entry_node_ids=["start"],
    )

    initial = {"embedding_records": embedding_records, "embedding_summary": embedding_summary}
    result = await WorkflowRunner().run(schema, ctx, initial_input=initial)
    if not result.get("success"):
        print("运行失败:", result.get("error"), file=sys.stderr)
        for nid, node_res in (result.get("node_results") or {}).items():
            if not node_res.success:
                print(f"失败节点 {nid}: {node_res.error}", file=sys.stderr)
        raise SystemExit(1)

    store_res = (result.get("node_results") or {}).get("store")
    data = store_res.data if store_res and isinstance(store_res.data, dict) else {}
    refs = data.get("storage_refs") or []
    summary = data.get("storage_summary") or {}

    print("storage_summary:", summary)
    print("storage_refs (逐条):")
    for r in refs:
        if not isinstance(r, dict):
            continue
        print(
            f"  - {r.get('backend')} target={r.get('target')!r} status={r.get('status')} "
            f"warning={r.get('warning')!r} error={r.get('error')!r}"
        )

    jsonl_path = Path(workspace) / "runtime_storage" / "text.jsonl"
    if jsonl_path.is_file():
        print(f"已写入本地文件: {jsonl_path.resolve()}")
    else:
        print(f"未找到预期 jsonl: {jsonl_path}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    asyncio.run(main())
