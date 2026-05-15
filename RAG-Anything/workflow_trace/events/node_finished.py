"""node_finished 事件。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NodeFinishedEvent:
    run_id: str
    workflow_id: str
    node_id: str
    node_type: str
    success: bool
    summary: dict[str, Any] = field(default_factory=dict)
