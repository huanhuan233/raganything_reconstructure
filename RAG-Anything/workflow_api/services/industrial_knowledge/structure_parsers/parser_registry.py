"""Parser registry for industrial structure parsing."""

from __future__ import annotations

from typing import Any

from .base_parser import BaseStructureParser
from .custom_schema_parser import CustomSchemaParser
from .form_structure_parser import FormStructureParser
from .process_flow_parser import ProcessFlowParser
from .table_structure_parser import TableStructureParser
from .title_hierarchy_parser import TitleHierarchyParser


class StructureParserRegistry:
    def __init__(self) -> None:
        self._parsers: dict[str, BaseStructureParser] = {}

    def register(self, parser: BaseStructureParser) -> None:
        self._parsers[parser.parser_name] = parser

    def get_parser(self, parser_name: str) -> BaseStructureParser:
        return self._parsers[parser_name]

    def list_parsers(self) -> list[dict[str, Any]]:
        return [p.metadata() for p in self._parsers.values()]

    def run_enabled(
        self,
        *,
        blocks: list[dict[str, Any]],
        enabled_parsers: list[str],
        custom_patterns: list[str] | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        out: dict[str, Any] = {}
        trace: list[dict[str, Any]] = []
        for name in enabled_parsers:
            p = self._parsers.get(name)
            if p is None:
                trace.append({"parser": name, "detected": False, "warning": "parser_not_found"})
                continue
            detected = bool(p.detect(blocks))
            if not detected:
                trace.append({"parser": name, "detected": False})
                continue
            if isinstance(p, CustomSchemaParser):
                structure = p.build_structure(blocks, patterns=custom_patterns or [])
            else:
                structure = p.build_structure(blocks)
            warnings = p.validate(structure)
            out[name] = structure
            trace.append({"parser": name, "detected": True, "warnings": warnings})
        return out, trace


def build_default_registry() -> StructureParserRegistry:
    reg = StructureParserRegistry()
    reg.register(TitleHierarchyParser())
    reg.register(ProcessFlowParser())
    reg.register(TableStructureParser())
    reg.register(FormStructureParser())
    reg.register(CustomSchemaParser())
    return reg
