"""节点状态模型。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .state_types import NodePhase


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class NodeState:
    node_id: str
    node_type: str
    phase: NodePhase = NodePhase.PENDING
    start_time: str | None = None
    end_time: str | None = None
    error: str | None = None
    retry_count: int = 0
    duration_ms: int | None = None

    def mark_running(self) -> None:
        self.phase = NodePhase.RUNNING
        self.start_time = _utc_now_iso()
        self.end_time = None
        self.error = None
        self.duration_ms = None

    def mark_success(self) -> None:
        self.phase = NodePhase.SUCCESS
        self.end_time = _utc_now_iso()
        self.duration_ms = _duration_ms(self.start_time, self.end_time)

    def mark_failed(self, error: str) -> None:
        self.phase = NodePhase.FAILED
        self.error = str(error)
        self.end_time = _utc_now_iso()
        self.duration_ms = _duration_ms(self.start_time, self.end_time)

    def mark_skipped(self) -> None:
        self.phase = NodePhase.SKIPPED
        self.end_time = _utc_now_iso()
        self.duration_ms = _duration_ms(self.start_time, self.end_time)


def _duration_ms(start: str | None, end: str | None) -> int | None:
    if not start or not end:
        return None
    try:
        s = datetime.fromisoformat(start.replace("Z", "+00:00"))
        e = datetime.fromisoformat(end.replace("Z", "+00:00"))
        return max(0, int((e - s).total_seconds() * 1000))
    except Exception:  # noqa: BLE001
        return None
