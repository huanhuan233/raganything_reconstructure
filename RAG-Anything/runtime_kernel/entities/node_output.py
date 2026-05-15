"""标准化节点输出对象。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NodeOutput:
    """节点写入 context 的标准化载体。"""

    content_refs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    state_changes: dict[str, Any] = field(default_factory=dict)
    trace_events: list[dict[str, Any]] = field(default_factory=list)
