"""Industrial Runtime：本体对象快照（不写 Neo4j，仅运行时注册表）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OntologyState:
    """
    挂载由 ``ontology.object.define`` 节点写入的对象 ``model_dump()``。

    ``registry``：object_id → 结构化 dict（通常为 ``OntologyObject.model_dump()``）。
    """

    registry: dict[str, dict[str, Any]] = field(default_factory=dict)
    ordered_ids: list[str] = field(default_factory=list)
    last_emit_node_id: str | None = None

    def upsert_object(self, object_id: str, payload: dict[str, Any], *, node_id: str | None = None) -> None:
        self.registry[str(object_id)] = dict(payload)
        if str(object_id) not in self.ordered_ids:
            self.ordered_ids.append(str(object_id))
        if node_id:
            self.last_emit_node_id = node_id

    def as_list(self) -> list[dict[str, Any]]:
        return [dict(self.registry[i]) for i in self.ordered_ids if i in self.registry]

