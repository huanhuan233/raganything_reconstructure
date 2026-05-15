"""
relation.merge 节点示例：
workflow.start -> entity_relation.extract -> entity.merge -> relation.merge -> workflow.end
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
                "source_chunk_id": "chunk_demo_1",
                "pipeline": "text_pipeline",
                "metadata": {"aliases": ["QWEN-3"]},
                "raw_entity": {},
            },
            {
                "entity_id": "raw_qwen_3",
                "entity_name": "QWEN-3",
                "entity_type": "model",
                "description": "QWEN-3 variant",
                "source_chunk_id": "chunk_demo_1",
                "pipeline": "text_pipeline",
                "metadata": {},
                "raw_entity": {},
            },
            {
                "entity_id": "raw_alibaba",
                "entity_name": "Alibaba",
                "entity_type": "organization",
                "description": "Alibaba Group",
                "source_chunk_id": "chunk_demo_2",
                "pipeline": "text_pipeline",
                "metadata": {},
                "raw_entity": {},
            },
        ]
        relations = [
            {
                "relation_id": "r1",
                "source_entity": "raw_qwen3",
                "target_entity": "raw_alibaba",
                "relation_type": "developed_by",
                "description": "Qwen3 is developed by Alibaba",
                "weight": 0.92,
                "source_chunk_id": "chunk_demo_1",
                "pipeline": "text_pipeline",
                "metadata": {},
                "raw_relation": {},
            },
            {
                "relation_id": "r2",
                "source_entity": "raw_qwen_3",
                "target_entity": "raw_alibaba",
                "relation_type": "created_by",
                "description": "QWEN-3 was created by Alibaba",
                "weight": 0.89,
                "source_chunk_id": "chunk_demo_2",
                "pipeline": "text_pipeline",
                "metadata": {},
                "raw_relation": {},
            },
        ]
        return {
            "entities": entities,
            "relations": relations,
            "raw_extraction": {},
            "entity_relation_summary": {
                "input_chunks": 1,
                "entity_count": len(entities),
                "relation_count": len(relations),
                "entity_type_distribution": {"model": 2, "organization": 1},
                "relation_type_distribution": {"developed_by": 1, "created_by": 1},
                "source_algorithm": "fake.entity.extract",
                "used_original_algorithm": False,
            },
            "source_algorithm": "fake.entity.extract",
            "adapter_path": "examples.relation_merge_example._FakeEntityExtractAdapter",
            "used_original_algorithm": False,
        }


async def _dummy_llm(_prompt: str, **_kwargs: Any) -> str:
    return "{}"


async def main() -> None:
    schema = WorkflowSchema(
        workflow_id="relation_merge_example",
        nodes=[
            {"id": "start", "type": "workflow.start", "config": {}},
            {"id": "er", "type": "entity_relation.extract", "config": {"max_chunks": 5}},
            {"id": "em", "type": "entity.merge", "config": {"merge_strategy": "normalize"}},
            {
                "id": "rm",
                "type": "relation.merge",
                "config": {
                    "merge_strategy": "canonical",
                    "similarity_threshold": 0.9,
                    "enable_relation_type_merge": True,
                    "enable_description_merge": True,
                },
            },
            {"id": "end", "type": "workflow.end", "config": {}},
        ],
        edges=[("start", "er"), ("er", "em"), ("em", "rm"), ("rm", "end")],
        entry_node_ids=["start"],
    )

    from workflow_api.raganything_runtime import (  # noqa: E402
        get_shared_lightrag_entity_merge_adapter,
        get_shared_lightrag_relation_merge_adapter,
    )

    entity_merge_adapter = await get_shared_lightrag_entity_merge_adapter()
    relation_merge_adapter = await get_shared_lightrag_relation_merge_adapter()
    if entity_merge_adapter is None or relation_merge_adapter is None:
        print("无法构建 entity/relation merge adapter", file=sys.stderr)
        raise SystemExit(1)

    ctx = ExecutionContext(
        workflow_id="relation_merge_example",
        run_id="example-1",
        workspace=str((_ROOT / "output" / "relation_merge_example").resolve()),
        adapters={
            "lightrag_entity": _FakeEntityExtractAdapter(),
            "lightrag_entity_merge": entity_merge_adapter,
            "lightrag_relation_merge": relation_merge_adapter,
            "llm_model_func": _dummy_llm,
        },
        shared_data={"llm_model_func": _dummy_llm},
        logs=[],
    )

    initial = {
        "chunks": [
            {
                "chunk_id": "chunk_demo_1",
                "pipeline": "text_pipeline",
                "content_type": "text",
                "text": "Qwen3 / QWEN-3 are model aliases; both linked to Alibaba.",
                "tokens": 18,
                "source_item_id": "demo",
                "metadata": {},
                "raw_item": {},
            }
        ]
    }
    result = await WorkflowRunner().run(schema, ctx, initial_input=initial)
    if not result.get("success"):
        print("运行失败:", result.get("error"), file=sys.stderr)
        raise SystemExit(1)
    rm = (result.get("node_results") or {}).get("rm")
    data = rm.data if rm and isinstance(rm.data, dict) else {}
    summary = data.get("relation_merge_summary") if isinstance(data, dict) else {}
    merged = data.get("merged_relations") if isinstance(data, dict) else []
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(merged, list):
        merged = []
    print("input_relations:", summary.get("input_relations"))
    print("merged_relations:", summary.get("merged_relations"))
    for one in merged:
        if not isinstance(one, dict):
            continue
        print(
            "-",
            one.get("source_entity"),
            "->",
            one.get("relation_type"),
            "->",
            one.get("target_entity"),
            "merged_from=",
            len(one.get("merged_from") or []),
        )


if __name__ == "__main__":
    asyncio.run(main())

