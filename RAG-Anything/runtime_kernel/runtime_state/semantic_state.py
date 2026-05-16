"""Industrial Runtime：语义执行计划挂载与阶段标记。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SemanticRuntimeState:
    """与 ``SemanticExecutionPlan`` 对应；plan 本体存 ``ExecutionContext.semantic_plan``。"""

    phase: str = "idle"
    plan_id: str | None = None
    dependency_edges: list[tuple[str, str, str]] = field(default_factory=list)
    legality_issues: list[str] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)
