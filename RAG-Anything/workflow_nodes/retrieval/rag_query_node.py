"""统一 RAG 查询节点：按引擎键分派到 LightRAG 或 RAG-Anything 适配器。"""

from __future__ import annotations

from typing import Any, Optional

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult


class RAGQueryNode(BaseNode):
    """
    ``config.engine``：``lightrag`` | ``raganything``。

    查询文本优先顺序：``input_data["query"]`` → ``config["query"]``。
    适配器实例键：    ``config.lightrag_adapter_key`` / ``config.raganything_adapter_key``（各有默认值）。
    """

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="",
            display_name="RAG 查询",
            category="rag",
            description="按 engine 调用 LightRAG 或 RAG-Anything 适配器查询。",
            implementation_status="real",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(
                    name="query",
                    label="查询文本",
                    type="string",
                    required=True,
                    placeholder="问题或检索式",
                    description="可与入口 input_data.query 叠加；二者至少其一。",
                ),
                NodeConfigField(
                    name="engine",
                    label="引擎",
                    type="select",
                    required=False,
                    default="raganything",
                    options=["raganything", "lightrag"],
                ),
                NodeConfigField(
                    name="mode",
                    label="查询模式",
                    type="select",
                    required=False,
                    default="hybrid",
                    options=["local", "global", "hybrid", "mix", "naive", "bypass"],
                    description="RAG-Anything 查询模式；LightRAG 侧可能映射为 QueryParam。",
                ),
            ],
            input_schema={"type": "object", "description": "可含 query / question"},
            output_schema={"type": "object", "description": "answer, engine, metadata 等"},
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        engine = str(self.config.get("engine", "lightrag")).lower()
        q_text: Optional[str] = None
        if isinstance(input_data, dict):
            q_text = input_data.get("query") or input_data.get("question")
        if not q_text:
            q_text = self.config.get("query")
        if not q_text:
            return NodeResult(success=False, error="未提供查询文本 query", data=input_data)

        if engine == "lightrag":
            lk = self.config.get("lightrag_adapter_key", "lightrag")
            adapter = context.adapters.get(lk)
            if adapter is None or not hasattr(adapter, "query"):
                return NodeResult(
                    success=False,
                    error=f"context.adapters[{lk!r}] 缺失或没有 query 方法",
                )
            try:
                param = self.config.get("query_param")
                if param is None:
                    # Runtime/Node 层不直接依赖 third-party；若适配器暴露构造器则使用它。
                    if hasattr(adapter, "build_default_query_param"):
                        try:
                            param = adapter.build_default_query_param()
                        except Exception:  # noqa: BLE001
                            param = None
                    else:
                        param = None
                system_prompt = self.config.get("system_prompt")
                out = adapter.query(
                    q_text,
                    param=param,
                    system_prompt=system_prompt,
                )
            except Exception as exc:  # noqa: BLE001
                return NodeResult(success=False, error=str(exc), data=None)
            # 流式 Iterator 时取首段或字符串化（骨架阶段）
            answer: Any = out
            if hasattr(out, "__iter__") and not isinstance(out, (str, bytes, dict)):
                try:
                    answer = "".join(str(x) for x in out)  # type: ignore[operator]
                except TypeError:
                    answer = str(out)
            return NodeResult(
                success=True,
                data={"query": q_text, "answer": answer, "engine": "lightrag"},
                metadata={},
            )

        if engine == "raganything":
            from runtime_kernel.protocols.raganything_isolated import load_raganything_types

            RAGAnythingQueryRequest = load_raganything_types().RAGAnythingQueryRequest
            rk = self.config.get("raganything_adapter_key", "raganything")
            adapter = context.adapters.get(rk)
            if adapter is None or not hasattr(adapter, "query"):
                return NodeResult(
                    success=False,
                    error=f"context.adapters[{rk!r}] 缺失或没有 query 方法",
                )
            req = RAGAnythingQueryRequest(
                query=q_text,
                mode=str(self.config.get("mode", "hybrid")),
                system_prompt=self.config.get("system_prompt"),
                enable_vlm=bool(self.config.get("enable_vlm", False)),
                multimodal_content=list(self.config.get("multimodal_content") or []),
                extra_query_kwargs=dict(self.config.get("extra_query_kwargs") or {}),
            )
            try:
                resp = await adapter.query(req)
            except Exception as exc:  # noqa: BLE001
                return NodeResult(success=False, error=str(exc))
            meta = dict(resp.metadata or {})
            meta.setdefault("used_vlm", resp.used_vlm)
            meta.setdefault("used_multimodal", resp.used_multimodal)
            return NodeResult(
                success=True,
                data={
                    "answer": resp.answer_text,
                    "query_mode": resp.mode,
                    "metadata": meta,
                    # 兼容旧消费方
                    "query": q_text,
                    "engine": "raganything",
                    "response_metadata": resp.metadata,
                },
                metadata={"mode": resp.mode, "used_vlm": resp.used_vlm},
            )

        return NodeResult(
            success=False,
            error=f"未知 engine: {engine}（支持 lightrag / raganything）",
        )
