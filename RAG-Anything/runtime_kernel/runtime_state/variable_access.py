"""VariablePool 标准访问层。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from runtime_kernel.execution_context.execution_context import ExecutionContext


class VariableAccess:
    @staticmethod
    def get_query(context: "ExecutionContext", default: str = "") -> str:
        return str(context.variable_pool.get("query", default) or default).strip()

    @staticmethod
    def set_query(context: "ExecutionContext", query: str) -> None:
        context.variable_pool.set("query", str(query or "").strip())

    @staticmethod
    def get_top_k(context: "ExecutionContext", default: int = 20) -> int:
        try:
            return max(1, int(context.variable_pool.get("top_k", default) or default))
        except Exception:  # noqa: BLE001
            return max(1, int(default))

    @staticmethod
    def set_top_k(context: "ExecutionContext", top_k: int) -> None:
        try:
            context.variable_pool.set("top_k", max(1, int(top_k)))
        except Exception:  # noqa: BLE001
            pass

    @staticmethod
    def get_runtime_flag(context: "ExecutionContext", name: str, default: bool = False) -> bool:
        flags = context.variable_pool.get("runtime_flags", {})
        if not isinstance(flags, dict):
            return bool(default)
        val = flags.get(str(name), default)
        return bool(val)

    @staticmethod
    def get_storage_strategy(context: "ExecutionContext", default: str = "auto") -> str:
        return str(context.variable_pool.get("storage_strategy", default) or default).strip()

    @staticmethod
    def get_embedding_provider(context: "ExecutionContext", default: str = "default") -> str:
        return str(context.variable_pool.get("embedding_provider", default) or default).strip()

    @staticmethod
    def get_vector_backend(context: "ExecutionContext", default: str = "auto") -> str:
        return str(context.variable_pool.get("vector_backend", default) or default).strip()
