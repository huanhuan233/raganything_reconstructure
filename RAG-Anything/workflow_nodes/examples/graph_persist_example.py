"""
graph.persist 节点示例：
workflow.start -> entity_relation.extract -> entity.merge -> relation.merge -> graph.merge -> graph.persist -> workflow.end
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.graph_engine.workflow_runner import WorkflowRunner
from runtime_kernel.graph.workflow_schema import WorkflowSchema  # noqa: E402


class _FakeEntityExtractAdapter:
    async def extract_entities_and_relations(self, _chunks: list[dict], **_kwargs: Any) -> dict[str, Any]:
        entities = [
            {
                "entity_id": "raw_qwen3",
                "entity_name": "Qwen3",
                "entity_type": "model",
                "description": "Qwen3 model",
                "source_chunk_id": "chunk_1",
                "metadata": {"aliases": ["QWEN-3"]},
            },
            {
                "entity_id": "raw_qwen_3",
                "entity_name": "QWEN-3",
                "entity_type": "model",
                "description": "QWEN-3 variant",
                "source_chunk_id": "chunk_8",
                "metadata": {},
            },
            {
                "entity_id": "raw_alibaba",
                "entity_name": "Alibaba",
                "entity_type": "organization",
                "description": "Alibaba Group",
                "source_chunk_id": "chunk_20",
                "metadata": {},
            },
        ]
        relations = [
            {
                "relation_id": "r1",
                "source_entity": "raw_qwen3",
                "target_entity": "raw_alibaba",
                "relation_type": "developed_by",
                "description": "Qwen3 developed by Alibaba",
                "weight": 0.93,
                "source_chunk_id": "chunk_1",
                "metadata": {},
            },
            {
                "relation_id": "r2",
                "source_entity": "raw_qwen_3",
                "target_entity": "raw_alibaba",
                "relation_type": "created_by",
                "description": "QWEN-3 created by Alibaba",
                "weight": 0.89,
                "source_chunk_id": "chunk_20",
                "metadata": {},
            },
        ]
        return {
            "entities": entities,
            "relations": relations,
            "entity_relation_summary": {
                "input_chunks": 1,
                "entity_count": len(entities),
                "relation_count": len(relations),
            },
        }


async def _dummy_llm(_prompt: str, **_kwargs: Any) -> str:
    return "{}"


async def main() -> None:
    schema = WorkflowSchema(
        workflow_id="graph_persist_example",
        nodes=[
            {"id": "start", "type": "workflow.start", "config": {}},
            {"id": "er", "type": "entity_relation.extract", "config": {"max_chunks": 5}},
            {"id": "em", "type": "entity.merge", "config": {"merge_engine": "runtime"}},
            {"id": "rm", "type": "relation.merge", "config": {"merge_engine": "runtime"}},
            {"id": "gm", "type": "graph.merge", "config": {"merge_engine": "runtime"}},
            {
                "id": "gp",
                "type": "graph.persist",
                "config": {
                    "graph_backend": "local_jsonl",
                    "workspace": "test0512",
                    "create_if_missing": True,
                    "persist_components": True,
                },
            },
            {"id": "end", "type": "workflow.end", "config": {}},
        ],
        edges=[("start", "er"), ("er", "em"), ("em", "rm"), ("rm", "gm"), ("gm", "gp"), ("gp", "end")],
        entry_node_ids=["start"],
    )

    from workflow_api.raganything_runtime import (  # noqa: E402
        get_shared_lightrag_entity_merge_adapter,
        get_shared_lightrag_graph_merge_adapter,
        get_shared_lightrag_graph_persist_adapter,
        get_shared_lightrag_relation_merge_adapter,
    )

    entity_merge_adapter = await get_shared_lightrag_entity_merge_adapter()
    relation_merge_adapter = await get_shared_lightrag_relation_merge_adapter()
    graph_merge_adapter = await get_shared_lightrag_graph_merge_adapter()
    graph_persist_adapter = await get_shared_lightrag_graph_persist_adapter()
    if (
        entity_merge_adapter is None
        or relation_merge_adapter is None
        or graph_merge_adapter is None
        or graph_persist_adapter is None
    ):
        print("无法构建 graph.persist 相关 adapter", file=sys.stderr)
        raise SystemExit(1)

    ctx = ExecutionContext(
        workflow_id="graph_persist_example",
        run_id="example-1",
        workspace=str((_ROOT / "output" / "graph_persist_example").resolve()),
        adapters={
            "lightrag_entity": _FakeEntityExtractAdapter(),
            "lightrag_entity_merge": entity_merge_adapter,
            "lightrag_relation_merge": relation_merge_adapter,
            "lightrag_graph_merge": graph_merge_adapter,
            "lightrag_graph_persist": graph_persist_adapter,
            "llm_model_func": _dummy_llm,
        },
        shared_data={"llm_model_func": _dummy_llm},
        logs=[],
    )
    initial = {"chunks": [{"chunk_id": "chunk_demo", "text": "Qwen3 and Alibaba relation."}]}
    result = await WorkflowRunner().run(schema, ctx, initial_input=initial)
    if not result.get("success"):
        print("运行失败:", result.get("error"), file=sys.stderr)
        raise SystemExit(1)
    gp = (result.get("node_results") or {}).get("gp")
    data = gp.data if gp and isinstance(gp.data, dict) else {}
    summary = data.get("graph_persist_summary") if isinstance(data, dict) else {}
    if not isinstance(summary, dict):
        summary = {}
    print("graph_backend:", summary.get("graph_backend"))
    print("workspace:", summary.get("workspace"))
    print("entity_persisted:", summary.get("entity_persisted"))
    print("relation_persisted:", summary.get("relation_persisted"))
    print("component_persisted:", summary.get("component_persisted"))
    refs = data.get("storage_refs") if isinstance(data, dict) else []
    if isinstance(refs, list):
        print("storage_refs:", len(refs))


if __name__ == "__main__":
    asyncio.run(main())
