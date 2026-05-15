"""答案生成节点（Runtime 第一阶段 minimal 实现）。"""

from __future__ import annotations

import inspect
from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult


def _as_dict(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _answer_from_result(v: Any) -> str:
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, dict):
        obj = _as_dict(v)
        for k in ("answer", "text", "content", "output"):
            if isinstance(obj.get(k), str) and str(obj.get(k)).strip():
                return str(obj.get(k)).strip()
        return str(v)
    if isinstance(v, list):
        return "\n".join(str(x) for x in v if x is not None).strip()
    if v is None:
        return ""
    return str(v).strip()


def _make_fallback_answer(query: str, context_str: str, answer_style: str, include_references: bool) -> str:
    clean_q = query.strip() or "（未提供问题）"
    lines = [x.strip() for x in context_str.splitlines() if x.strip()]
    top = lines[:5]
    if answer_style == "简洁":
        base = f"基于当前上下文，对问题“{clean_q}”的回答：已检索到相关信息，请参考下方上下文片段。"
    elif answer_style == "详细":
        body = "\n".join(f"- {x}" for x in top) if top else "- （上下文为空）"
        base = f"问题：{clean_q}\n基于上下文的整理如下：\n{body}"
    else:  # 要点式
        body = "\n".join(f"- {x}" for x in top) if top else "- （上下文为空）"
        base = f"问题：{clean_q}\n要点：\n{body}"
    if include_references:
        refs = [x for x in lines if x.startswith("[")]
        if refs:
            base += "\n\n参考片段：" + " ".join(refs[:6])
    return base.strip()


def _build_prompt(
    *,
    query: str,
    context_str: str,
    system_prompt: str,
    answer_style: str,
    include_references: bool,
) -> str:
    refs_hint = "请在回答中标注可对应到片段编号。" if include_references else "无需在回答中标注片段编号。"
    return (
        f"{system_prompt.strip()}\n\n"
        f"回答风格：{answer_style}\n"
        f"{refs_hint}\n\n"
        f"用户问题：{query.strip()}\n\n"
        f"可用上下文：\n{context_str.strip()}\n"
    ).strip()


def _resolve_llm_callable(payload: dict[str, Any], context: ExecutionContext) -> Any | None:
    # 1) shared_data 直接注入
    fn = context.shared_data.get("llm_model_func")
    if callable(fn):
        return fn
    # 2) payload 里临时注入（通常不会走 API，但保留兼容）
    fn = payload.get("llm_model_func")
    if callable(fn):
        return fn
    # 3) adapters 直接注入
    fn = context.adapters.get("llm_model_func")
    if callable(fn):
        return fn
    # 4) raganything adapter / engine 上挂载
    rag = context.adapters.get("raganything")
    if rag is not None:
        for attr in ("llm_model_func",):
            f = getattr(rag, attr, None)
            if callable(f):
                return f
        inner = getattr(rag, "raganything", None)
        if inner is not None:
            f = getattr(inner, "llm_model_func", None)
            if callable(f):
                return f
    return None


class LLMGenerateNode(BaseNode):
    """接收 context_str + query，生成 answer（支持真实 llm_model_func 或 fallback）。"""

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="llm.generate",
            display_name="答案生成",
            category="llm",
            description="结合 query 与 context_str 生成答案；无 llm_model_func 时使用模板 fallback。",
            implementation_status="partial",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(
                    name="query",
                    label="用户问题",
                    type="string",
                    required=False,
                ),
                NodeConfigField(
                    name="model",
                    label="模型名称",
                    type="string",
                    required=False,
                ),
                NodeConfigField(
                    name="system_prompt",
                    label="系统提示词",
                    type="string",
                    required=False,
                    default="你是一个严谨的知识库问答助手，请仅根据给定上下文回答问题。",
                ),
                NodeConfigField(
                    name="answer_style",
                    label="回答风格",
                    type="select",
                    required=False,
                    default="要点式",
                    options=["简洁", "详细", "要点式"],
                ),
                NodeConfigField(
                    name="include_references",
                    label="是否包含引用",
                    type="boolean",
                    required=False,
                    default=True,
                ),
                NodeConfigField(
                    name="temperature",
                    label="temperature",
                    type="number",
                    required=False,
                    default=0.2,
                ),
                NodeConfigField(
                    name="max_tokens",
                    label="max_tokens",
                    type="number",
                    required=False,
                    default=2048,
                ),
            ],
            input_schema={"type": "object", "description": "query + context_str"},
            output_schema={"type": "object", "description": "answer + generation_summary + prompt"},
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        payload = dict(input_data) if isinstance(input_data, dict) else {}
        query = str(
            self.config.get("query")
            or payload.get("query")
            or payload.get("query_text")
            or context.shared_data.get("query")
            or ""
        ).strip()
        context_str = str(payload.get("context_str") or "").strip()
        model = str(self.config.get("model") or "").strip()
        system_prompt = str(
            self.config.get("system_prompt")
            or "你是一个严谨的知识库问答助手，请仅根据给定上下文回答问题。"
        )
        answer_style = str(self.config.get("answer_style") or "要点式").strip() or "要点式"
        include_references = bool(self.config.get("include_references", True))
        temperature = float(self.config.get("temperature", 0.2) or 0.2)
        max_tokens = int(self.config.get("max_tokens", 2048) or 2048)

        prompt = _build_prompt(
            query=query,
            context_str=context_str,
            system_prompt=system_prompt,
            answer_style=answer_style,
            include_references=include_references,
        )
        llm_fn = _resolve_llm_callable(payload, context)
        used_llm = False
        answer = ""
        if callable(llm_fn):
            try:
                # 只透传通用 LLM 参数，避免 OpenAI 兼容端收到 query/context 等非标准字段报错
                call_kwargs: dict[str, Any] = {
                    "system_prompt": system_prompt,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if model:
                    call_kwargs["model"] = model
                ret = llm_fn(
                    prompt,
                    **call_kwargs,
                )
                if inspect.isawaitable(ret):
                    ret = await ret  # type: ignore[assignment]
                answer = _answer_from_result(ret)
                used_llm = True
            except Exception as exc:  # noqa: BLE001
                context.log(f"[LLMGenerateNode] llm_model_func 调用失败，改用 fallback: {exc}")
                answer = _make_fallback_answer(query, context_str, answer_style, include_references)
                used_llm = False
        else:
            answer = _make_fallback_answer(query, context_str, answer_style, include_references)
            used_llm = False

        generation_summary = {
            "used_llm": used_llm,
            "model": model,
            "prompt_chars": len(prompt),
            "context_chars": len(context_str),
            "answer_chars": len(answer),
        }
        out = dict(payload)
        out["answer"] = answer
        out["generation_summary"] = generation_summary
        out["prompt"] = prompt
        context.log(
            f"[LLMGenerateNode] used_llm={used_llm} model={model!r} prompt_chars={len(prompt)} answer_chars={len(answer)}"
        )
        return NodeResult(
            success=True,
            data=out,
            metadata={"node": "llm.generate", "used_llm": used_llm},
        )
