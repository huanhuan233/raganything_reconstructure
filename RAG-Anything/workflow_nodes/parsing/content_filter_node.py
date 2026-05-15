"""content_list 过滤与路由前预处理。"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from runtime_kernel.entities.content_types import is_formula_type, is_table_type, is_text_type, is_vision_type
from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult


class ContentFilterNode(BaseNode):
    """按类型、长度与空值规则过滤 content_list。"""

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="",
            display_name="内容过滤",
            category="content",
            description="对 content_list 做类型过滤与预处理。",
            implementation_status="real",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(
                    name="keep_types",
                    label="保留类型",
                    type="json",
                    required=False,
                    default=[],
                    placeholder='如 ["image","table"]',
                    description="仅保留指定 type（优先于 drop_types）。",
                ),
                NodeConfigField(
                    name="drop_types",
                    label="删除类型",
                    type="json",
                    required=False,
                    default=[],
                    placeholder='如 ["footer"]',
                    description="删除指定 type。",
                ),
                NodeConfigField(
                    name="min_text_length",
                    label="文本最小长度",
                    type="number",
                    required=False,
                    default=0,
                    description="仅对 text 类型生效。",
                ),
                NodeConfigField(
                    name="drop_empty",
                    label="删除空内容",
                    type="boolean",
                    required=False,
                    default=True,
                ),
                NodeConfigField(
                    name="keep_page_numbers",
                    label="保留页码块",
                    type="boolean",
                    required=False,
                    default=True,
                ),
            ],
            input_schema={"type": "object"},
            output_schema={"type": "object", "description": "content_list, filter_summary"},
        )

    @staticmethod
    def _as_type_set(v: Any) -> set[str]:
        if v is None:
            return set()
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return set()
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return {str(x).strip() for x in parsed if str(x).strip()}
                return {s}
            except Exception:  # noqa: BLE001
                return {s}
        if isinstance(v, list):
            return {str(x).strip() for x in v if str(x).strip()}
        return set()

    @staticmethod
    def _is_empty_item(item: dict[str, Any]) -> bool:
        t = str(item.get("type", "")).strip().lower()
        if is_text_type(t):
            return not str(item.get("text", "")).strip()
        if is_table_type(t):
            return not str(item.get("table_body", "")).strip()
        if is_vision_type(t):
            return not str(item.get("img_path", "")).strip()
        if is_formula_type(t):
            return not str(item.get("latex", "")).strip() and not str(item.get("text", "")).strip()
        # 通用空值判定：常见主字段都为空时视为空
        keys = ("text", "table_body", "img_path", "latex")
        return all(not str(item.get(k, "")).strip() for k in keys)

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        if not isinstance(input_data, dict):
            return NodeResult(success=False, error="content.filter 期望输入为 dict。")

        raw_items = input_data.get("content_list")
        if not isinstance(raw_items, list):
            return NodeResult(success=False, error="content.filter 缺少 content_list（list）。")

        keep_types = self._as_type_set(self.config.get("keep_types"))
        drop_types = self._as_type_set(self.config.get("drop_types"))
        min_text_length = int(self.config.get("min_text_length", 0) or 0)
        drop_empty = bool(self.config.get("drop_empty", True))
        keep_page_numbers = bool(self.config.get("keep_page_numbers", True))

        out: list[dict[str, Any]] = []
        before_counter: Counter[str] = Counter()
        kept_counter: Counter[str] = Counter()
        dropped_counter: Counter[str] = Counter()

        for raw in raw_items:
            if not isinstance(raw, dict):
                dropped_counter["__invalid__"] += 1
                continue
            item = dict(raw)
            t = str(item.get("type", "")).strip().lower() or "unknown"
            before_counter[t] += 1

            # 1) keep_types 优先
            if keep_types and t not in keep_types:
                dropped_counter[t] += 1
                continue
            # keep_page_numbers 额外开关
            if not keep_page_numbers and t == "page_number":
                dropped_counter[t] += 1
                continue
            # 2) drop_types 次之
            if t in drop_types:
                dropped_counter[t] += 1
                continue
            # 3) text 最小长度
            if is_text_type(t) and min_text_length > 0:
                txt = str(item.get("text", "")).strip()
                if len(txt) < min_text_length:
                    dropped_counter[t] += 1
                    continue
            # 4) 空内容
            if drop_empty and self._is_empty_item(item):
                dropped_counter[t] += 1
                continue

            out.append(item)
            kept_counter[t] += 1

        summary = {
            "before_count": len(raw_items),
            "after_count": len(out),
            "kept_types": dict(kept_counter),
            "dropped_types": dict(dropped_counter),
            "before_types": dict(before_counter),
            "config_applied": {
                "keep_types": sorted(keep_types),
                "drop_types": sorted(drop_types),
                "min_text_length": min_text_length,
                "drop_empty": drop_empty,
                "keep_page_numbers": keep_page_numbers,
            },
        }
        context.log(
            f"[ContentFilterNode] before={summary['before_count']} after={summary['after_count']}"
        )
        return NodeResult(success=True, data={"content_list": out, "filter_summary": summary})

