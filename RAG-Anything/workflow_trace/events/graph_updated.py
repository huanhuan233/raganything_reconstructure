"""graph_updated 事件。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GraphUpdatedEvent:
    run_id: str
    workflow_id: str
    node_id: str
    changes: dict[str, Any] = field(default_factory=dict)
