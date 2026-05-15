"""模型侧 Provider：Embedding / LLM 抽象与 OpenAI 兼容占位实现。"""

from .embedding_provider import EmbeddingProvider, OpenAICompatibleEmbeddingProvider
from .llm_provider import LLMProvider, OpenAICompatibleLLMProvider

__all__ = [
    "EmbeddingProvider",
    "OpenAICompatibleEmbeddingProvider",
    "LLMProvider",
    "OpenAICompatibleLLMProvider",
]
