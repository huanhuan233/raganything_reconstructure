"""工作流执行期共享上下文。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

_logger = logging.getLogger("backend_runtime.execution")


@dataclass
class ExecutionContext:
    """
    在一次工作流运行（run）内在线程/协程间传递的只读偏可写容器。

    - ``adapters``：由应用工厂注入 ``lightrag`` / ``raganything`` 等键，对应 ``*EngineAdapter`` 实例；
    - ``shared_data``：节点间可约定的跨步缓存（如幂等键、租户 id）；
    - ``logs``：简易字符串日志，便于前端或排障聚合。
    """

    workflow_id: str
    run_id: str
    workspace: str = ""
    adapters: Dict[str, Any] = field(default_factory=dict)
    shared_data: Dict[str, Any] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)

    def log(self, message: str) -> None:
        """追加一条日志。"""
        self.logs.append(message)
        # 同步输出到后端日志，便于在 uvicorn 控制台实时观察节点执行过程。
        try:
            _logger.info(
                "[workflow_id=%s run_id=%s] %s",
                self.workflow_id,
                self.run_id,
                message,
            )
        except Exception:  # noqa: BLE001
            pass
