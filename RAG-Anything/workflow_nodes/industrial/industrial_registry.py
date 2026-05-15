"""工业节点注册表（独立于原生节点实现）。"""

from __future__ import annotations

from runtime_kernel.node_runtime.node_registry import NodeRegistry
from .industrial_graph_persist_node import IndustrialGraphPersistNode
from .industrial_constraint_extract_node import IndustrialConstraintExtractNode
from .industrial_graph_build_node import IndustrialGraphBuildNode
from .industrial_process_extract_node import IndustrialProcessExtractNode
from .industrial_structure_recognition_node import IndustrialStructureRecognitionNode
from .industrial_table_parse_node import IndustrialTableParseNode


def register_industrial_nodes(reg: NodeRegistry) -> None:
    reg.register("industrial.structure_recognition", IndustrialStructureRecognitionNode)
    reg.register("industrial.constraint_extract", IndustrialConstraintExtractNode)
    reg.register("industrial.process_extract", IndustrialProcessExtractNode)
    reg.register("industrial.table_parse", IndustrialTableParseNode)
    reg.register("industrial.graph_build", IndustrialGraphBuildNode)
    reg.register("industrial.graph.persist", IndustrialGraphPersistNode)
