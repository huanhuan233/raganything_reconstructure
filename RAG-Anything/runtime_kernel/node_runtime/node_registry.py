"""节点类型注册表：字符串 ``node_type`` → 实现类。"""

from __future__ import annotations

from typing import Any, Dict, List, Type

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.entities.node_metadata import metadata_as_dict, with_node_type

_default_registry: "NodeRegistry | None" = None


class NodeRegistry:
    """线程内单例式注册表（进程级）；便于测试替换。"""

    def __init__(self) -> None:
        self._types: Dict[str, Type[BaseNode]] = {}

    def register(self, node_type: str, node_class: Type[BaseNode]) -> None:
        """注册节点类型；重复注册则覆盖。"""
        self._types[node_type] = node_class

    def create_node(
        self, node_type: str, node_id: str, config: Dict[str, Any]
    ) -> BaseNode:
        """根据类型实例化节点；未知类型抛 ``KeyError``。"""
        cls = self._types[node_type]
        return cls(node_id=node_id, node_type=node_type, config=config)

    def list_nodes(self) -> List[Dict[str, Any]]:
        """返回已注册节点的元数据列表（按 ``node_type`` 排序）；每项含 ``node_type`` 等字段。"""
        out: List[Dict[str, Any]] = []
        for ntype in sorted(self._types.keys()):
            cls = self._types[ntype]
            meta = with_node_type(cls.metadata(), ntype)
            out.append(metadata_as_dict(meta))
        return out

    def list_node_types(self) -> List[str]:
        """仅 ``node_type`` 字符串列表（排序稳定），兼容旧调用。"""
        return sorted(self._types.keys())

    def has_type(self, node_type: str) -> bool:
        return node_type in self._types


def get_default_registry() -> NodeRegistry:
    """懒加载全局默认注册表。"""
    global _default_registry
    if _default_registry is None:
        _default_registry = NodeRegistry()
    return _default_registry
