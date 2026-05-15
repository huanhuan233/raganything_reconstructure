"""工业知识统一适配器。"""

from __future__ import annotations

from typing import Any

from .graph_bridge import IndustrialGraphBridge
from .mineru_bridge import IndustrialMinerUBridge
from .workflow_bridge import IndustrialWorkflowBridge


class IndustrialKnowledgeAdapter:
    def __init__(self) -> None:
        self.mineru_bridge = IndustrialMinerUBridge()
        self.workflow_bridge = IndustrialWorkflowBridge()
        self.graph_bridge = IndustrialGraphBridge()

    async def structure_recognition(
        self,
        *,
        mineru_content_list: list[dict[str, Any]],
        config: dict[str, Any] | None = None,
        document_id: str = "document:industrial",
    ) -> dict[str, Any]:
        data = await self.workflow_bridge.run_pipeline(
            mineru_content_list=mineru_content_list,
            config=config,
            document_id=document_id,
        )
        return {
            "normalized_blocks": data.get("normalized_blocks", []),
            "composite_structure": data.get("composite_structure", {}),
            "validation": data.get("validation", {}),
            "summary": {
                "parser_count": len((data.get("composite_structure", {}) or {}).get("parser_trace", [])),
                "block_count": len(data.get("normalized_blocks", [])),
            },
        }

    async def constraint_extract(self, *, mineru_content_list: list[dict[str, Any]], config: dict[str, Any] | None = None) -> dict[str, Any]:
        data = await self.workflow_bridge.run_pipeline(
            mineru_content_list=mineru_content_list,
            config=config,
        )
        return {"constraints": data.get("constraints", []), "validation": data.get("validation", {})}

    async def process_extract(self, *, mineru_content_list: list[dict[str, Any]], config: dict[str, Any] | None = None) -> dict[str, Any]:
        data = await self.workflow_bridge.run_pipeline(
            mineru_content_list=mineru_content_list,
            config=config,
        )
        return {"process_graph": data.get("process_steps", []), "validation": data.get("validation", {})}

    async def table_parse(self, *, mineru_content_list: list[dict[str, Any]], config: dict[str, Any] | None = None) -> dict[str, Any]:
        data = await self.workflow_bridge.run_pipeline(
            mineru_content_list=mineru_content_list,
            config=config,
        )
        return {"structured_tables": data.get("structured_tables", []), "validation": data.get("validation", {})}

    async def graph_build(
        self,
        *,
        document_id: str,
        title_hierarchy: dict[str, Any],
        process_steps: list[dict[str, Any]],
        constraints: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        materials: list[dict[str, Any]] | None = None,
        inspections: list[dict[str, Any]] | None = None,
        tables: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return self.graph_bridge.build_graph(
            document_id=document_id,
            title_hierarchy=title_hierarchy,
            process_steps=process_steps,
            constraints=constraints,
            tools=tools,
            materials=materials,
            inspections=inspections,
            tables=tables,
        )
