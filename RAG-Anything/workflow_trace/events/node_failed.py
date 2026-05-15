"""node_failed 事件。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class NodeFailedEvent:
    run_id: str
    workflow_id: str
    node_id: str
    node_type: str
    error: str
