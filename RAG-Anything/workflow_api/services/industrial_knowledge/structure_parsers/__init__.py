"""结构识别解析器插件系统。"""

from .base_parser import BaseStructureParser
from .custom_schema_parser import CustomSchemaParser
from .form_structure_parser import FormStructureParser
from .parser_registry import StructureParserRegistry, build_default_registry
from .process_flow_parser import ProcessFlowParser
from .table_structure_parser import TableStructureParser
from .title_hierarchy_parser import TitleHierarchyParser

__all__ = [
    "BaseStructureParser",
    "StructureParserRegistry",
    "build_default_registry",
    "TitleHierarchyParser",
    "ProcessFlowParser",
    "TableStructureParser",
    "FormStructureParser",
    "CustomSchemaParser",
]
