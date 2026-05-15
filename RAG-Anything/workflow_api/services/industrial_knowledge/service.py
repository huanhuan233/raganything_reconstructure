"""工业知识主编排服务。"""

from __future__ import annotations

from typing import Any

from .extractors import (
    ConstraintExtractor,
    InspectionExtractor,
    MaterialExtractor,
    ProcessStepExtractor,
    ToolExtractor,
)
from .graph import ProcessKnowledgeGraphBuilder
from .normalized_blocks import normalize_mineru_layout_blocks
from .schemas import (
    CompositeStructureResult,
    IndustrialKnowledgeConfig,
    IndustrialKnowledgeResult,
    ValidationResult,
)
from .semantic import SemanticCompletion
from .structure_parsers import build_default_registry
from .validators import (
    ConstraintValidator,
    HierarchyValidator,
    ProcessValidator,
    TableValidator,
)


class IndustrialKnowledgePipeline:
    def __init__(self) -> None:
        self.registry = build_default_registry()
        self.constraint_extractor = ConstraintExtractor()
        self.process_extractor = ProcessStepExtractor()
        self.tool_extractor = ToolExtractor()
        self.material_extractor = MaterialExtractor()
        self.inspection_extractor = InspectionExtractor()
        self.graph_builder = ProcessKnowledgeGraphBuilder()
        self.semantic_completion = SemanticCompletion()
        self.hierarchy_validator = HierarchyValidator()
        self.constraint_validator = ConstraintValidator()
        self.process_validator = ProcessValidator()
        self.table_validator = TableValidator()

    async def run(
        self,
        *,
        mineru_content_list: list[dict[str, Any]],
        config: IndustrialKnowledgeConfig | None = None,
        document_id: str = "document:industrial",
        llm_adapter: Any = None,
    ) -> IndustrialKnowledgeResult:
        cfg = config or IndustrialKnowledgeConfig()
        blocks = normalize_mineru_layout_blocks(mineru_content_list)
        parser_result, parser_trace = self.registry.run_enabled(
            blocks=blocks,
            enabled_parsers=list(cfg.structure.enabled_parsers),
            custom_patterns=list(cfg.custom_schema_patterns),
        )
        composite = CompositeStructureResult(
            title_hierarchy=dict(parser_result.get("title_hierarchy") or {}),
            process_flow=dict(parser_result.get("process_flow") or {}),
            table_relations=dict(parser_result.get("table_structure") or {}),
            form_structure=dict(parser_result.get("form_structure") or {}),
            custom_schema=dict(parser_result.get("custom_schema") or {}),
            parser_trace=parser_trace,
        )
        constraints = self.constraint_extractor.extract(blocks) if cfg.enable_constraint_extract else []
        process_steps = self.process_extractor.extract(blocks) if cfg.enable_process_extract else []
        structured_tables = (
            (composite.table_relations.get("tables") if isinstance(composite.table_relations, dict) else []) or []
            if cfg.enable_table_parse
            else []
        )
        tools = self.tool_extractor.extract(blocks)
        materials = self.material_extractor.extract(blocks)
        inspections = self.inspection_extractor.extract(blocks)

        semantic = await self.semantic_completion.complete(
            enabled=cfg.enable_semantic_completion,
            composite_structure=composite.__dict__,
            constraints=constraints,
            process_steps=process_steps,
            llm_adapter=llm_adapter,
        )
        graph = (
            self.graph_builder.build(
                document_id=document_id,
                title_hierarchy=composite.title_hierarchy,
                process_steps=process_steps,
                constraints=constraints,
                tools=tools,
                materials=materials,
                inspections=inspections,
                tables=structured_tables,
            )
            if cfg.enable_graph_build
            else {}
        )
        errors: list[str] = []
        warnings: list[str] = []
        if cfg.enable_validation:
            for validator, target in [
                (self.hierarchy_validator, composite.title_hierarchy),
                (self.constraint_validator, constraints),
                (self.process_validator, process_steps),
                (self.table_validator, structured_tables),
            ]:
                e, w = validator.validate(target)
                errors.extend(e)
                warnings.extend(w)

        return IndustrialKnowledgeResult(
            normalized_blocks=blocks,
            composite_structure=composite,
            constraints=constraints,
            process_steps=process_steps,
            structured_tables=structured_tables,
            semantic=semantic,
            graph=graph,
            validation=ValidationResult(errors=errors, warnings=warnings),
        )
