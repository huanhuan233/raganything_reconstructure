"""内容生命周期池。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .state_types import CONTENT_BUCKETS


@dataclass
class ContentPool:
    """统一存放节点产生的内容对象。"""

    _buckets: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in CONTENT_BUCKETS:
            self._buckets.setdefault(name, None)

    def put(self, bucket: str, value: Any) -> None:
        self._buckets[str(bucket)] = value

    def get(self, bucket: str, default: Any = None) -> Any:
        return self._buckets.get(bucket, default)

    def append(self, bucket: str, value: Any) -> None:
        bucket = str(bucket)
        current = self._buckets.get(bucket)
        if not isinstance(current, list):
            current = [] if current is None else [current]
        current.append(value)
        self._buckets[bucket] = current

    def as_dict(self) -> dict[str, Any]:
        return dict(self._buckets)
