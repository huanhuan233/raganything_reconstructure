"""查询上下文字符串构建节点（Runtime 第一阶段 minimal 实现）。"""

from __future__ import annotations

import json
from hashlib import sha1
from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult


def _as_dict(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _as_list_of_dict(v: Any) -> list[dict[str, Any]]:
    if not isinstance(v, list):
        return []
    return [x for x in v if isinstance(x, dict)]


def _safe_int(v: Any, default: int) -> int:
    try:
        return int(v)
    except Exception:  # noqa: BLE001
        return default


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:  # noqa: BLE001
        return default


def _source_of(row: dict[str, Any]) -> str:
    src = row.get("source")
    if isinstance(src, str) and src.strip():
        return src.strip()
    srcs = row.get("sources")
    if isinstance(srcs, list) and srcs:
        return str(srcs[0])
    backend = row.get("backend")
    if isinstance(backend, str) and backend.strip():
        return backend.strip()
    return "unknown"


def _metadata_pretty_line(metadata: dict[str, Any]) -> str:
    if not metadata:
        return ""
    pairs: list[str] = []
    for k, v in metadata.items():
        key = str(k).strip()
        if not key:
            continue
        val = str(v).strip().replace("\n", " ")
        if len(val) > 80:
            val = val[:77] + "..."
        pairs.append(f"{key}={val}")
    if not pairs:
        return ""
    return "metadata: " + "; ".join(pairs[:8])


def _block_text(block: dict[str, Any], *, include_metadata: bool, include_scores: bool, fmt: str, idx: int) -> str:
    rid = str(block.get("result_id") or "")
    source = str(block.get("source") or "unknown")
    score = _safe_float(block.get("score"), 0.0)
    text = str(block.get("text") or "").strip()
    metadata = _as_dict(block.get("metadata"))

    if fmt == "json":
        one: dict[str, Any] = {
            "index": idx,
            "result_id": rid,
            "source": source,
            "text": text,
        }
        if include_scores:
            one["score"] = round(score, 6)
        if include_metadata:
            one["metadata"] = metadata
        return json.dumps(one, ensure_ascii=False)

    score_part = f" score={score:.4f}" if include_scores else ""
    head = f"[{idx}] source={source}{score_part}"
    if rid:
        head += f" result_id={rid}"
    body = f"内容：{text}"
    parts = [head, body]
    if include_metadata and metadata:
        meta_line = _metadata_pretty_line(metadata)
        if meta_line:
            parts.append(meta_line)
    sep = "\n" if fmt == "plain" else "\n"
    return sep.join(parts)


class ContextBuildNode(BaseNode):
    """将 unified_results 构造成 context_str/context_blocks（不调用 LLM）。"""

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="",
            display_name="上下文构建",
            category="context",
            description="将检索融合结果格式化为 prompt context（minimal runtime 版本）。",
            implementation_status="partial",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(
                    name="max_context_chars",
                    label="最大上下文字符数",
                    type="number",
                    required=False,
                    default=8000,
                ),
                NodeConfigField(
                    name="max_results",
                    label="最大结果数",
                    type="number",
                    required=False,
                    default=10,
                ),
                NodeConfigField(
                    name="include_metadata",
                    label="包含元数据",
                    type="boolean",
                    required=False,
                    default=True,
                ),
                NodeConfigField(
                    name="include_scores",
                    label="包含分数",
                    type="boolean",
                    required=False,
                    default=True,
                ),
                NodeConfigField(
                    name="context_format",
                    label="上下文格式",
                    type="select",
                    required=False,
                    default="markdown",
                    options=["markdown", "plain", "json"],
                ),
                NodeConfigField(
                    name="deduplicate_text",
                    label="文本去重",
                    type="boolean",
                    required=False,
                    default=True,
                ),
            ],
            input_schema={"type": "object", "description": "unified_results"},
            output_schema={"type": "object", "description": "context_str/context_blocks/context_summary"},
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        payload = dict(input_data) if isinstance(input_data, dict) else {}
        rows = _as_list_of_dict(payload.get("unified_results"))
        if not rows:
            rows = _as_list_of_dict(payload.get("reranked_results"))
        rows_sorted = sorted(rows, key=lambda x: _safe_float(x.get("score"), 0.0), reverse=True)

        max_context_chars = max(256, _safe_int(self.config.get("max_context_chars", 8000), 8000))
        max_results = max(1, _safe_int(self.config.get("max_results", 10), 10))
        include_metadata = bool(self.config.get("include_metadata", True))
        include_scores = bool(self.config.get("include_scores", True))
        context_format = str(self.config.get("context_format", "markdown") or "markdown").strip().lower()
        if context_format not in ("markdown", "plain", "json"):
            context_format = "markdown"
        deduplicate_text = bool(self.config.get("deduplicate_text", True))

        blocks: list[dict[str, Any]] = []
        seen_text: set[str] = set()
        for row in rows_sorted:
            if len(blocks) >= max_results:
                break
            text = str(row.get("text") or row.get("content") or "").strip()
            if deduplicate_text and text:
                key = sha1(text.encode("utf-8")).hexdigest()  # noqa: S324 - only dedup key
                if key in seen_text:
                    continue
                seen_text.add(key)
            block = {
                "result_id": str(row.get("result_id") or row.get("record_id") or row.get("id") or ""),
                "source": _source_of(row),
                "score": _safe_float(row.get("score"), 0.0),
                "text": text,
                "metadata": _as_dict(row.get("metadata")),
            }
            blocks.append(block)

        parts: list[str] = []
        used_results = 0
        for idx, block in enumerate(blocks, start=1):
            one = _block_text(
                block,
                include_metadata=include_metadata,
                include_scores=include_scores,
                fmt=context_format,
                idx=idx,
            )
            if context_format == "markdown":
                one = one
            sep = "\n\n" if context_format != "json" else "\n"
            cand = (sep.join(parts + [one])) if parts else one
            if len(cand) > max_context_chars:
                break
            parts.append(one)
            used_results += 1

        context_str = ("\n\n".join(parts) if context_format != "json" else "\n".join(parts)).strip()
        context_summary = {
            "input_results": len(rows),
            "used_results": used_results,
            "max_context_chars": max_context_chars,
            "context_chars": len(context_str),
        }
        out = dict(payload)
        out["context_str"] = context_str
        out["context_blocks"] = blocks[:used_results]
        out["context_summary"] = context_summary
        context.log(
            f"[ContextBuildNode] input={len(rows)} used={used_results} chars={len(context_str)} format={context_format}"
        )
        return NodeResult(
            success=True,
            data=out,
            metadata={"node": "context.build"},
        )
