"""retrieval_completed 事件。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RetrievalCompletedEvent:
    run_id: str
    workflow_id: str
    node_id: str
    backend: str
    result_count: int
