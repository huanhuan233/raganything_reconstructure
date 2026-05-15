"""content_read 事件。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ContentReadEvent:
    run_id: str
    workflow_id: str
    node_id: str
    bucket: str
    hit: bool
