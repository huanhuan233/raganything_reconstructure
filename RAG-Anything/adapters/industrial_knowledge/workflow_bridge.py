"""工作流桥接层。"""

from __future__ import annotations

from typing import Any

from workflow_api.services.industrial_knowledge.schemas import (
    IndustrialKnowledgeConfig,
    StructureRecognitionConfig,
)
from workflow_api.services.industrial_knowledge.service import IndustrialKnowledgePipeline


class IndustrialWorkflowBridge:
    def __init__(self) -> None:
        self._pipeline = IndustrialKnowledgePipeline()

    @staticmethod
    def _coerce_config(config: dict[str, Any] | None) -> IndustrialKnowledgeConfig:
        raw = dict(config or {})
        structure_raw = raw.get("structure")
        if isinstance(structure_raw, dict):
            enabled = structure_raw.get("enabled_parsers")
            raw["structure"] = StructureRecognitionConfig(
                enabled_parsers=list(enabled) if isinstance(enabled, list) else StructureRecognitionConfig().enabled_parsers
            )
        elif not isinstance(structure_raw, StructureRecognitionConfig):
            raw["structure"] = StructureRecognitionConfig()
        return IndustrialKnowledgeConfig(**raw)

    async def run_pipeline(
        self,
        *,
        mineru_content_list: list[dict[str, Any]],
        config: dict[str, Any] | None = None,
        document_id: str = "document:industrial",
    ) -> dict[str, Any]:
        cfg = self._coerce_config(config)
        result = await self._pipeline.run(
            mineru_content_list=mineru_content_list,
            config=cfg,
            document_id=document_id,
        )
        return {
            "normalized_blocks": result.normalized_blocks,
            "composite_structure": result.composite_structure.__dict__,
            "constraints": result.constraints,
            "process_steps": result.process_steps,
            "structured_tables": result.structured_tables,
            "semantic": result.semantic,
            "graph": result.graph,
            "validation": result.validation.__dict__,
        }
