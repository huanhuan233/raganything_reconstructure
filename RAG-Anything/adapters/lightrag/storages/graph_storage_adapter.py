"""
图数据库侧配置结构：Neo4j / Memgraph / 国产图库的连接参数载体。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional


GraphDialect = Literal[
    "networkx",
    "neo4j",
    "memgraph",
]


@dataclass
class GraphBackendConfig:
    """
    图存储连接占位。

    TODO: 与国密 TLS、Kerberos、bulk import 离线灌库任务协调。
    """

    dialect: GraphDialect = "networkx"
    uri: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


class GraphStorageAdapter:
    """
    ``GraphBackendConfig`` -> LightRAG ``graph_storage`` 类名与环境变量 hints。
    """

    def __init__(self, config: GraphBackendConfig) -> None:
        self._config = config

    def resolve_lightrag_graph_storage_class_name(self) -> str:
        """
        TODO:
            - neo4j -> ``Neo4JStorage``
            - memgraph -> 以 lightrag kg 注册名为准
            - 国产图 -> 外挂存储插件 + lazy import
        """
        raise NotImplementedError(
            "TODO: dialect -> LIGHTRAG_GRAPH_STORAGE / graph_storage 构造参数。"
        )

    def runtime_env_hints(self) -> Dict[str, str]:
        """Neo4j BOLT_URI、AUTH 等写入建议（由宿主进程统一应用）。"""
        raise NotImplementedError(
            "TODO: 对齐 lightrag Neo4j 实现所读取的环境变量集合。"
        )
