"""工作流执行状态。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .node_state import NodeState
from .state_types import ExecutionPhase


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class ExecutionState:
    workflow_id: str
    run_id: str
    phase: ExecutionPhase = ExecutionPhase.PENDING
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    scheduler_state: dict[str, Any] = field(default_factory=dict)
    execution_metadata: dict[str, Any] = field(default_factory=dict)
    node_states: dict[str, NodeState] = field(default_factory=dict)

    def mark_running(self) -> None:
        self.phase = ExecutionPhase.RUNNING
        self.started_at = self.started_at or _utc_now_iso()
        self.finished_at = None
        self.error = None

    def mark_success(self) -> None:
        self.phase = ExecutionPhase.SUCCESS
        self.finished_at = _utc_now_iso()

    def mark_failed(self, error: str) -> None:
        self.phase = ExecutionPhase.FAILED
        self.error = str(error)
        self.finished_at = _utc_now_iso()
