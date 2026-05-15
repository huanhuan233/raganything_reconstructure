"""
嵌入模型 Provider 抽象。

后续可在此包外实现：DashScope Qwen Embedding、国产专用网关、本地 onnx 等，
仅要求能产出 ``lightrag.utils.EmbeddingFunc`` 或等价可调用接口供 ``LightRAG`` 注入。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List, Sequence

try:
    from lightrag.utils import EmbeddingFunc
except ImportError:  # 类型占位，便于无依赖静态检查
    EmbeddingFunc = Any  # type: ignore[misc, assignment]


class EmbeddingProvider(ABC):
    """
    嵌入能力抽象。

    LightRAG 侧消费的是带有 ``func`` / ``embedding_dim`` 等属性的 ``EmbeddingFunc``；
    本抽象负责把「底座配置」收口为可供引擎注入的单一工厂方法。
    """

    @abstractmethod
    def build_embedding_func(self) -> Any:
        """
        构建并返回 ``EmbeddingFunc`` 实例。

        Raises:
            NotImplementedError: 子类未实现。

        TODO: 增加 batch_token_limit、熔断、国产化签名鉴权适配器。
        """
        raise NotImplementedError


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    """
    OpenAI 兼容 HTTP 网关的占位实现（如 vLLM、OneAPI、部分国产聚合网关）。

    不在此文件内发起真实 HTTP 调用，仅为后续接入保留构造参数形状。
    """

    def __init__(
        self,
        *,
        base_url: str = "https://api.openai.com/v1",
        api_key: str = "",
        model: str = "text-embedding-3-small",
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model

    def build_embedding_func(self) -> Any:
        """
        TODO:
            - 使用 ``lightrag.llm.openai.openai_embed`` 或等价工厂组装 ``EmbeddingFunc``；
            - 支持 dimensions / encoding_format 等与 Milvus schema 对齐；
            - Qwen Embedding / 国产化替换时继承 ``EmbeddingProvider`` 另建新类。
        """
        raise NotImplementedError(
            "TODO: 调用 lightrag.llm.openai.openai_embed 或项目内统一工厂生成 EmbeddingFunc。"
        )

    def embed_text_stub(self, texts: Sequence[str]) -> List[List[float]]:
        """仅占位签名，演示「非 LightRAG 路径」如何用同一 Provider。"""
        raise NotImplementedError("TODO: 直连网关时的最小 embed 封装（不走 LightRAG）。")
