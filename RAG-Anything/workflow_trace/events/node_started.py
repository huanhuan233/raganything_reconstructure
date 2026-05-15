"""node_started 事件。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class NodeStartedEvent:
    run_id: str
    workflow_id: str
    node_id: str
    node_type: str
    input_preview: Any = None
