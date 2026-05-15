"""节点单次执行结果载体。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class NodeResult:
    """
    节点 ``run`` 返回值，与具体业务负载解耦。

    ``data`` 通常为 dict，供下游节点作为 ``input_data`` 合并使用。
    """

    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
