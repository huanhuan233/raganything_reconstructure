"""
LightRAG 引擎与外围后端的配置载体。

仅承载数据与默认值，不在此模块内读写环境变量或连接远程服务（保持骨架纯净）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from .storages.graph_storage_adapter import GraphBackendConfig
from .storages.vector_storage_adapter import VectorBackendConfig


@dataclass
class LightRAGAdapterConfig:
    """
    构造 LightRAGEngineAdapter / LightRAG 实例时的常用参数合集。

    说明：LightRAG 本体为巨型 dataclass，此处只收录工业化场景最常注入的字段；
    未尽参数请通过 ``extra_lightrag_kwargs`` 透传。
    """

    working_dir: str = "./rag_storage"
    workspace: str = ""
    kv_storage: str = "JsonKVStorage"
    vector_storage: str = "NanoVectorDBStorage"
    graph_storage: str = "NetworkXStorage"
    doc_status_storage: str = "JsonDocStatusStorage"

    embedding_func: Optional[Any] = None
    llm_model_func: Optional[Callable[..., Any]] = None

    vector_backend: Optional[VectorBackendConfig] = None
    graph_backend: Optional[GraphBackendConfig] = None

    extra_lightrag_kwargs: Dict[str, Any] = field(default_factory=dict)
    # TODO: 从 pydantic-settings / 配置中心加载；与多租户 workspace 映射策略
