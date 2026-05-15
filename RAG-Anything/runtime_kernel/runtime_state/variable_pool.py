"""运行期变量池。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class VariablePool:
    """统一承载 query/top_k/runtime_flags 等变量。"""

    _data: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[str(key)] = value

    def update(self, values: dict[str, Any] | None) -> None:
        if not values:
            return
        for k, v in values.items():
            self._data[str(k)] = v

    def as_dict(self) -> dict[str, Any]:
        return dict(self._data)
