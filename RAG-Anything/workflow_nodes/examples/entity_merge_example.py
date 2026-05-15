"""
entity.merge 节点示例：
workflow.start -> entity_relation.extract -> entity.merge -> workflow.end
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
                "entity_id": "raw_1",
                "entity_name": "Qwen3",
                "entity_type": "model",
                "description": "Qwen3 model",
                "source_chunk_id": "chunk_demo_1",
                "pipeline": "text_pipeline",
                "metadata": {"aliases": ["Qwen-3", "QWEN3"]},
                "raw_entity": {},
            },
            {
                "entity_id": "raw_2",
                "entity_name": "Qwen-3",
                "entity_type": "model",
                "description": "Qwen-3 variant",
                "source_chunk_id": "chunk_demo_1",
                "pipeline": "text_pipeline",
                "metadata": {"aliases": ["QWEN 3"]},
                "raw_entity": {},
            },
            {
                "entity_id": "raw_3",
                "entity_name": "QWEN 3",
                "entity_type": "model",
                "description": "QWEN 3 uppercase",
                "source_chunk_id": "chunk_demo_2",
                "pipeline": "text_pipeline",
                "metadata": {},
                "raw_entity": {},
            },
        ]
        return {
            "entities": entities,
            "relations": [],
            "raw_extraction": {},
            "entity_relation_summary": {
                "input_chunks": 1,
                "entity_count": len(entities),
                "relation_count": 0,
                "entity_type_distribution": {"model": 3},
                "relation_type_distribution": {},
                "source_algorithm": "fake.entity.extract",
                "used_original_algorithm": False,
            },
            "source_algorithm": "fake.entity.extract",
            "adapter_path": "examples.entity_merge_example._FakeEntityExtractAdapter",
            "used_original_algorithm": False,
        }


async def _dummy_llm(_prompt: str, **_kwargs: Any) -> str:
    return "{}"


async def main() -> None:
    schema = WorkflowSchema(
        workflow_id="entity_merge_example",
        nodes=[
            {"id": "start", "type": "workflow.start", "config": {}},
            {
                "id": "er",
                "type": "entity_relation.extract",
                "config": {"max_chunks": 5, "include_multimodal_chunks": True},
            },
            {
                "id": "em",
                "type": "entity.merge",
                "config": {
                    "merge_strategy": "normalize",
                    "similarity_threshold": 0.9,
                    "enable_alias_merge": True,
                    "enable_fuzzy_merge": True,
                    "enable_embedding_merge": False,
                },
            },
            {"id": "end", "type": "workflow.end", "config": {}},
        ],
        edges=[("start", "er"), ("er", "em"), ("em", "end")],
        entry_node_ids=["start"],
    )

    from workflow_api.raganything_runtime import get_shared_lightrag_entity_merge_adapter  # noqa: E402

    entity_merge_adapter = await get_shared_lightrag_entity_merge_adapter()
    if entity_merge_adapter is None:
        print("无法构建 entity merge adapter", file=sys.stderr)
        raise SystemExit(1)

    ctx = ExecutionContext(
        workflow_id="entity_merge_example",
        run_id="example-1",
        workspace=str((_ROOT / "output" / "entity_merge_example").resolve()),
        adapters={
            "lightrag_entity": _FakeEntityExtractAdapter(),
            "lightrag_entity_merge": entity_merge_adapter,
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
                "text": "Qwen3 Qwen-3 QWEN 3 are the same model name variants.",
                "tokens": 16,
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
    em = (result.get("node_results") or {}).get("em")
    data = em.data if em and isinstance(em.data, dict) else {}
    summary = data.get("entity_merge_summary") if isinstance(data, dict) else {}
    merged = data.get("merged_entities") if isinstance(data, dict) else []
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(merged, list):
        merged = []
    print("input_entities:", summary.get("input_entities"))
    print("merged_entities:", summary.get("merged_entities"))
    for one in merged:
        if not isinstance(one, dict):
            continue
        print("-", one.get("canonical_name"), "merged_from=", len(one.get("merged_from") or []))


if __name__ == "__main__":
    asyncio.run(main())

