"""工作流静态描述（可序列化为 JSON 供前端保存）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

# 边：``(from_node_id, to_node_id)``
Edge = Tuple[str, str]


@dataclass
class WorkflowSchema:
    """
    工作流图结构。

    ``nodes`` 每项至少包含: ``id``, ``type``, ``config``（可为空 dict）。
    """

    workflow_id: str
    nodes: List[Dict[str, Any]]
    edges: List[Edge] = field(default_factory=list)
    entry_node_ids: List[str] = field(default_factory=list)

    def node_ids(self) -> List[str]:
        ids: List[str] = []
        for n in self.nodes:
            if "id" not in n:
                raise ValueError("每个节点必须包含 id 字段")
            ids.append(str(n["id"]))
        return ids
