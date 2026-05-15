"""图谱桥接层。"""

from __future__ import annotations

from typing import Any

from workflow_api.services.industrial_knowledge.graph import ProcessKnowledgeGraphBuilder


class IndustrialGraphBridge:
    def __init__(self) -> None:
        self._builder = ProcessKnowledgeGraphBuilder()

    def build_graph(self, **kwargs: Any) -> dict[str, Any]:
        return self._builder.build(**kwargs)
