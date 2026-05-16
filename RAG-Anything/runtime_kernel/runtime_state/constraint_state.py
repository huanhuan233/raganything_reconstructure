"""Industrial Runtime：约束状态与可追溯拒绝记录。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConstraintState:
    """活跃约束快照 + filter 运行时产生的 rejection / explanation 摘要。"""

    active_constraints: list[dict[str, Any]] = field(default_factory=list)
    rejection_log: list[dict[str, Any]] = field(default_factory=list)
    last_filter_node_id: str | None = None

    def register_active(self, items: list[dict[str, Any]]) -> None:
        self.active_constraints.extend(items)

    def log_rejection(self, entry: dict[str, Any]) -> None:
        self.rejection_log.append(dict(entry))
