"""DAG 运行图状态。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GraphState:
    """为调度器保留的图状态结构。"""

    ready_queue: list[str] = field(default_factory=list)
    dependency_state: dict[str, list[str]] = field(default_factory=dict)
    unresolved_dependencies: dict[str, int] = field(default_factory=dict)
    barrier_state: dict[str, Any] = field(default_factory=dict)
    parallel_branch_state: dict[str, Any] = field(default_factory=dict)

    def init_dependencies(self, nodes: list[str], edges: list[tuple[str, str]]) -> None:
        self.ready_queue = []
        self.dependency_state = {nid: [] for nid in nodes}
        self.unresolved_dependencies = {nid: 0 for nid in nodes}
        for src, dst in edges:
            self.dependency_state.setdefault(dst, []).append(src)
            self.unresolved_dependencies[dst] = int(self.unresolved_dependencies.get(dst, 0)) + 1
        self.ready_queue = [nid for nid in nodes if int(self.unresolved_dependencies.get(nid, 0)) == 0]

