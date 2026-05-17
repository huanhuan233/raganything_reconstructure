"""基于统一内容类型体系的 Runtime 内容路由。"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.entities.content_types import DEFAULT_IGNORE_TYPES, DEFAULT_ROUTE_MAPPING, is_discard_type
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult


class ContentRouteNode(BaseNode):
    """将 content_list 分发到不同 pipeline 路由桶。"""

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="",
            display_name="内容路由",
            category="content",
            description="基于文档 layout/type 将内容分发到不同 Runtime pipeline。",
            implementation_status="real",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(
                    name="route_mapping",
                    label="路由映射",
                    type="json",
                    required=False,
                    default=DEFAULT_ROUTE_MAPPING,
                    description="route_name -> type 列表。",
                ),
                NodeConfigField(
                    name="ignore_types",
                    label="忽略类型",
                    type="json",
                    required=False,
                    default=sorted(DEFAULT_IGNORE_TYPES),
                ),
                NodeConfigField(
                    name="keep_unrouted",
                    label="保留未命中类型",
                    type="boolean",
                    required=False,
                    default=True,
                ),
                NodeConfigField(
                    name="drop_discard_types",
                    label="丢弃 discard 类型",
                    type="boolean",
                    required=False,
                    default=True,
                ),
            ],
            input_schema={"type": "object"},
            output_schema={"type": "object", "description": "routes, route_summary"},
        )

    @staticmethod
    def _json_list(v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x).strip().lower() for x in v if str(x).strip()]
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [str(x).strip().lower() for x in parsed if str(x).strip()]
            except Exception:  # noqa: BLE001
                return [s.lower()]
        return []

    @staticmethod
    def _route_mapping(v: Any) -> dict[str, list[str]]:
        if v is None:
            return {k: list(vs) for k, vs in DEFAULT_ROUTE_MAPPING.items()}
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return {k: list(vs) for k, vs in DEFAULT_ROUTE_MAPPING.items()}
            try:
                v = json.loads(s)
            except Exception:  # noqa: BLE001
                return {k: list(vs) for k, vs in DEFAULT_ROUTE_MAPPING.items()}
        if not isinstance(v, dict):
            return {k: list(vs) for k, vs in DEFAULT_ROUTE_MAPPING.items()}
        out: dict[str, list[str]] = {}
        for route, types in v.items():
            if not isinstance(route, str) or not route.strip():
                continue
            out[route.strip()] = ContentRouteNode._json_list(types)
        return out or {k: list(vs) for k, vs in DEFAULT_ROUTE_MAPPING.items()}

    @staticmethod
    def _build_desc_index(multimodal_descriptions: list[dict[str, Any]]) -> dict[tuple[str, Any], dict[str, Any]]:
        idx: dict[tuple[str, Any], dict[str, Any]] = {}
        for d in multimodal_descriptions:
            if not isinstance(d, dict):
                continue
            t = str(d.get("type", "")).strip().lower()
            p = d.get("page_idx")
            if t:
                idx.setdefault((t, p), d)
        return idx

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        if not isinstance(input_data, dict):
            return NodeResult(success=False, error="content.route 期望输入为 dict")
        content_list = input_data.get("content_list")
        if not isinstance(content_list, list):
            return NodeResult(success=False, error="content.route 缺少 content_list(list)")

        route_mapping = self._route_mapping(self.config.get("route_mapping"))
        ignore_types = set(self._json_list(self.config.get("ignore_types")) or sorted(DEFAULT_IGNORE_TYPES))
        keep_unrouted = bool(self.config.get("keep_unrouted", True))
        drop_discard_types = bool(self.config.get("drop_discard_types", True))

        multimodal_descriptions = input_data.get("multimodal_descriptions")
        if not isinstance(multimodal_descriptions, list):
            multimodal_descriptions = []
        desc_index = self._build_desc_index(
            [d for d in multimodal_descriptions if isinstance(d, dict)]
        )

        routes: dict[str, list[dict[str, Any]]] = {k: [] for k in route_mapping.keys()}
        if keep_unrouted:
            routes["unrouted"] = []
        type_distribution: Counter[str] = Counter()
        group_distribution: Counter[str] = Counter()
        routed_items = 0
        unrouted_items = 0
        ignored_items = 0
        discarded_items = 0

        for idx, raw in enumerate(content_list, start=1):
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            canonical_block_id = str(
                raw.get("block_id") or raw.get("id") or raw.get("item_id") or f"mineru_block_{idx}"
            ).strip()
            if canonical_block_id:
                raw.setdefault("block_id", canonical_block_id)
                item.setdefault("block_id", canonical_block_id)
            t = str(item.get("type", "")).strip().lower() or "unknown"
            type_distribution[t] += 1

            if t in ignore_types:
                ignored_items += 1
                continue
            if drop_discard_types and is_discard_type(t):
                discarded_items += 1
                continue

            key = (t, item.get("page_idx"))
            desc = desc_index.get(key)
            if desc:
                item["multimodal_description"] = desc.get("text_description")

            hit_route: str | None = None
            for route_name, types in route_mapping.items():
                if t in types:
                    hit_route = route_name
                    break
            if hit_route is None:
                if keep_unrouted:
                    routes["unrouted"].append(item)
                    group_distribution["unrouted"] += 1
                unrouted_items += 1
                continue
            routes[hit_route].append(item)
            group_distribution[hit_route] += 1
            routed_items += 1

        summary = {
            "total_items": len(content_list),
            "routed_items": routed_items,
            "unrouted_items": unrouted_items,
            "ignored_items": ignored_items,
            "discarded_items": discarded_items,
            "group_distribution": dict(group_distribution),
            "type_distribution": dict(type_distribution),
            "route_mapping": route_mapping,
            "ignore_types": sorted(ignore_types),
            "keep_unrouted": keep_unrouted,
            "drop_discard_types": drop_discard_types,
        }
        context.log(
            f"[ContentRouteNode] total={summary['total_items']} routed={routed_items} unrouted={unrouted_items}"
        )
        return NodeResult(success=True, data={"routes": routes, "route_summary": summary})

