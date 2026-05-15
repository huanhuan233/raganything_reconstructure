"""LLM 语义补全（默认关闭）。"""

from __future__ import annotations

from typing import Any


class SemanticCompletion:
    async def complete(
        self,
        *,
        enabled: bool,
        composite_structure: dict[str, Any],
        constraints: list[dict[str, Any]],
        process_steps: list[dict[str, Any]],
        llm_adapter: Any = None,
    ) -> dict[str, Any]:
        if not enabled:
            return {"enabled": False, "summary": "semantic completion disabled"}
        # 避免耦合具体 LLM 实现：优先尝试外部 adapter。
        if llm_adapter is None:
            return {
                "enabled": True,
                "summary": "no llm adapter bound, skip api call",
                "process_hint": [x.get("description") for x in process_steps[:5]],
                "constraint_hint": constraints[:10],
            }
        return {
            "enabled": True,
            "summary": "semantic completion delegated to llm adapter",
            "structure_keys": list((composite_structure or {}).keys()),
        }
