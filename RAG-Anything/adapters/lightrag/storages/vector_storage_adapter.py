"""
向量库侧配置结构：用于平台级统一配置，再映射到 LightRAG ``vector_storage`` 名称与 env。

不实现具体驱动；连接仍由 ``lightrag.kg.*_impl`` 与 ``LIGHTRAG_VECTOR_STORAGE`` 等环境变量负责。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional


VectorDialect = Literal[
    "nano",
    "milvus",
    "qdrant",
    "faiss",
    "chroma",
]


@dataclass
class VectorBackendConfig:
    """
    向量库连接与集合级元数据占位。

    TODO: 与国产业务线与等保租户隔离对齐；collection 后缀与 ``workspace`` 联动策略。
    """

    dialect: VectorDialect = "nano"
    endpoint: Optional[str] = None
    api_key: Optional[str] = None
    database: Optional[str] = None
    collection: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


class VectorStorageAdapter:
    """
    将 ``VectorBackendConfig`` 译为 LightRAG 可用的 ``vector_storage`` 逻辑名与环境变量补丁。

    当前不修改 ``os.environ``，仅预留方法签名供上层服务启动阶段调用。
    """

    def __init__(self, config: VectorBackendConfig) -> None:
        self._config = config

    def resolve_lightrag_vector_storage_class_name(self) -> str:
        """
        返回 LightRAG ``STORAGES`` 注册使用的类名字符串。

        TODO:
            - MILVUS -> ``MilvusVectorDBStorage``
            - QDRANT -> 对应 kg 模块名（以实际 lightrag-hku 版本为准）
            - 国产向量库 -> 外挂独立包注册动态 import
        """
        raise NotImplementedError(
            "TODO: dialect -> LIGHTRAG_VECTOR_STORAGE / LightRAG 构造函数 vector_storage 字段映射。"
        )

    def runtime_env_hints(self) -> Dict[str, str]:
        """返回建议写入进程的 env 键值（由调用方决定是否 ``os.environ.update``）。"""
        raise NotImplementedError(
            "TODO: 汇总 MILVUS_URI、QDRANT_URL、国产化网关 AK/SK 等键名。"
        )
