"""content_written 事件。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ContentWrittenEvent:
    run_id: str
    workflow_id: str
    node_id: str
    bucket: str
    content_ref: str | None = None
