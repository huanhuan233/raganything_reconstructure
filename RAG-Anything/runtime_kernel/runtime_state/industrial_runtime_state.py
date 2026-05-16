"""Industrial Runtime：聚合工业语义运行时元信息与版本。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IndustrialRuntimeState:
    """
    不替代 ``ExecutionContext`` / ``OntologyState`` 等；

    仅承载跨子域的版本号与诊断块，便于 trace / 快照。
    """

    schema_revision: str = "industrial-semantic-runtime-v1"
    diagnostics: dict[str, Any] = field(default_factory=dict)
