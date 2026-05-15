"""存储后端配置适配：与 LightRAG 环境变量命名并存，不作为运行时唯一真源。"""

from .graph_storage_adapter import GraphBackendConfig, GraphStorageAdapter
from .vector_storage_adapter import VectorBackendConfig, VectorStorageAdapter

__all__ = [
    "VectorBackendConfig",
    "VectorStorageAdapter",
    "GraphBackendConfig",
    "GraphStorageAdapter",
]
