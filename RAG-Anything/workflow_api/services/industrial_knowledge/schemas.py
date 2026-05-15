"""工业知识服务层通用 schema。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

INDUSTRIAL_NODE_TYPES = [
    "Document",
    "Section",
    "ProcessStep",
    "Constraint",
    "Parameter",
    "Tool",
    "Material",
    "Inspection",
    "Figure",
    "Table",
]

INDUSTRIAL_RELATION_TYPES = [
    "contains",
    "before",
    "next_step",
    "requires",
    "uses",
    "references",
    "constraint_of",
]


@dataclass
class StructureRecognitionConfig:
    enabled_parsers: list[str] = field(
        default_factory=lambda: ["title_hierarchy", "process_flow", "table_structure"]
    )


@dataclass
class IndustrialKnowledgeConfig:
    structure: StructureRecognitionConfig = field(default_factory=StructureRecognitionConfig)
    enable_constraint_extract: bool = True
    enable_process_extract: bool = True
    enable_table_parse: bool = True
    enable_semantic_completion: bool = False
    enable_validation: bool = True
    enable_graph_build: bool = True
    custom_schema_patterns: list[str] = field(default_factory=list)


@dataclass
class CompositeStructureResult:
    title_hierarchy: dict[str, Any] = field(default_factory=dict)
    process_flow: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    table_relations: dict[str, Any] = field(default_factory=dict)
    form_structure: dict[str, Any] = field(default_factory=dict)
    custom_schema: dict[str, Any] = field(default_factory=dict)
    parser_trace: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class IndustrialKnowledgeResult:
    normalized_blocks: list[dict[str, Any]] = field(default_factory=list)
    composite_structure: CompositeStructureResult = field(default_factory=CompositeStructureResult)
    constraints: list[dict[str, Any]] = field(default_factory=list)
    process_steps: list[dict[str, Any]] = field(default_factory=list)
    structured_tables: list[dict[str, Any]] = field(default_factory=list)
    semantic: dict[str, Any] = field(default_factory=dict)
    graph: dict[str, Any] = field(default_factory=dict)
    validation: ValidationResult = field(default_factory=ValidationResult)
