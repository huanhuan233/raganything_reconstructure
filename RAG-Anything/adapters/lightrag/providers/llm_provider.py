"""
大语言模型 Provider 抽象。

与 ``LightRAG.llm_model_func`` 对齐：可为 async 调用、带回退优先级、CoT/stream 等。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable


class LLMProvider(ABC):
    """
    LLM 调用抽象。

    ``build_llm_model_func`` 的产物需满足 LightRAG 对 ``llm_model_func`` 的调用约定（含可选 keyword）。
    """

    @abstractmethod
    def build_llm_model_func(self) -> Callable[..., Awaitable[Any] | Any]:
        """
        返回可被 ``LightRAG(llm_model_func=...)`` 直接注入的可调用对象。

        TODO: 结构化输出路由、thinking 模式、国产内容安全策略注入点。
        """
        raise NotImplementedError


class OpenAICompatibleLLMProvider(LLMProvider):
    """
    OpenAI Chat Completions 兼容网关占位（DeepSeek / OneAPI / vLLM 等）。

    本类不实现网络 I/O，仅保留配置槽位。
    """

    def __init__(
        self,
        *,
        base_url: str = "https://api.openai.com/v1",
        api_key: str = "",
        model: str = "gpt-4o-mini",
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model

    def build_llm_model_func(self) -> Callable[..., Awaitable[Any] | Any]:
        """
        TODO:
            - 使用 ``lightrag.llm.openai.gpt_4o_mini_complete`` 或 ``openai_complete_if_cache`` 系列；
            - 从环境变量与安全存储加载 api_key；
            - 国产化模型网关：新建 ``XXXLLMProvider`` 继承 ``LLMProvider``。
        """
        raise NotImplementedError(
            "TODO: 使用 lightrag.llm.openai 中现成封装或自建 async 方法与 priority 适配。"
        )
