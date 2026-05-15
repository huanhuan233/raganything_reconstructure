"""运行期状态注册表。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuntimeRegistry:
    """统一登记运行时状态对象，便于后续扩展 scheduler/event-stream。"""

    _items: dict[str, Any] = field(default_factory=dict)

    def register(self, key: str, value: Any) -> None:
        self._items[str(key)] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._items.get(key, default)

    def as_dict(self) -> dict[str, Any]:
        return dict(self._items)
