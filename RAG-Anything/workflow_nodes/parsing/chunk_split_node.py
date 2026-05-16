"""Chunk 切片节点：routes/content_list -> chunks。"""

from __future__ import annotations

import json
from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.entities.content_types import is_formula_type, is_table_type, is_text_type, is_vision_type
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult
from runtime_kernel.runtime_state.content_access import ContentAccess


class ChunkSplitNode(BaseNode):
    """通过 adapters/lightrag 调用 LightRAG 切片能力。"""

    ROUTE_PRIORITY = ["text_pipeline", "table_pipeline", "vision_pipeline", "equation_pipeline"]

    @staticmethod
    def _as_dict(v: Any) -> dict[str, Any]:
        return v if isinstance(v, dict) else {}

    @staticmethod
    def _as_list(v: Any) -> list[Any]:
        return v if isinstance(v, list) else []

    @staticmethod
    def _json_to_list(v: Any) -> list[str]:
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            try:
                p = json.loads(s)
                if isinstance(p, list):
                    return [str(x).strip() for x in p if str(x).strip()]
            except Exception:  # noqa: BLE001
                return [x.strip() for x in s.split(",") if x.strip()]
        return []

    @staticmethod
    def _normalize_path(v: Any) -> str:
        s = str(v or "").strip()
        return s.replace("\\", "/").lower() if s else ""

    @classmethod
    def _build_desc_index(cls, multimodal_descriptions: list[dict[str, Any]]) -> dict[tuple[str, Any, str], str]:
        idx: dict[tuple[str, Any, str], str] = {}
        for one in multimodal_descriptions:
            if not isinstance(one, dict):
                continue
            desc = str(one.get("text_description", "")).strip()
            if not desc:
                continue
            t = str(one.get("type", "")).strip().lower()
            p = one.get("page_idx")
            img = cls._normalize_path(one.get("image_path"))
            idx.setdefault((t, p, img), desc)
            idx.setdefault((t, p, ""), desc)
        return idx

    @classmethod
    def _resolve_desc(cls, item: dict[str, Any], desc_idx: dict[tuple[str, Any, str], str]) -> str:
        local = str(item.get("multimodal_description") or item.get("text_description") or "").strip()
        if local:
            return local
        t = str(item.get("type", "")).strip().lower()
        p = item.get("page_idx")
        img = cls._normalize_path(item.get("img_path") or item.get("image_path"))
        return desc_idx.get((t, p, img), "") or desc_idx.get((t, p, ""), "")

    @classmethod
    def _extract_chunk_text(
        cls,
        *,
        item: dict[str, Any],
        pipeline: str,
        include_multimodal_descriptions: bool,
        desc_idx: dict[tuple[str, Any, str], str],
    ) -> str:
        t = str(item.get("type", "unknown")).strip().lower() or "unknown"

        def pick(*keys: str) -> str:
            for k in keys:
                v = item.get(k)
                if v is None:
                    continue
                s = str(v).strip()
                if s:
                    return s
            return ""

        if is_text_type(t):
            return pick("text", "content")

        if is_table_type(t):
            base = pick("table_text", "markdown", "text", "table_body", "html", "content")
            if base:
                return base
            if include_multimodal_descriptions:
                return cls._resolve_desc(item, desc_idx)
            return ""

        if is_vision_type(t):
            if include_multimodal_descriptions:
                return cls._resolve_desc(item, desc_idx)
            return ""

        if is_formula_type(t):
            base = pick("latex", "equation_text", "text", "content")
            if base:
                return base
            if include_multimodal_descriptions:
                return cls._resolve_desc(item, desc_idx)
            return ""

        # 兜底：允许来自 text_pipeline 的未知类型按文本字段切片
        if pipeline == "text_pipeline":
            return pick("text", "content", "markdown")
        return ""

    @classmethod
    def _type_to_default_pipeline(cls, t: str) -> str:
        if is_table_type(t):
            return "table_pipeline"
        if is_vision_type(t):
            return "vision_pipeline"
        if is_formula_type(t):
            return "equation_pipeline"
        return "text_pipeline"

    @classmethod
    def _collect_chunk_items(
        cls,
        *,
        payload: dict[str, Any],
        include_multimodal_descriptions: bool,
        skip_pipelines: set[str],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        routes = cls._as_dict(payload.get("routes"))
        content_list = cls._as_list(payload.get("content_list"))
        multimodal_descriptions = [
            x for x in cls._as_list(payload.get("multimodal_descriptions")) if isinstance(x, dict)
        ]
        desc_idx = cls._build_desc_index(multimodal_descriptions)
        warnings: list[str] = []
        out: list[dict[str, Any]] = []

        def push_item(pipeline: str, raw_item: dict[str, Any], idx: int) -> None:
            if pipeline in skip_pipelines:
                return
            t = str(raw_item.get("type", "unknown")).strip().lower() or "unknown"
            text = cls._extract_chunk_text(
                item=raw_item,
                pipeline=pipeline,
                include_multimodal_descriptions=include_multimodal_descriptions,
                desc_idx=desc_idx,
            ).strip()
            if not text:
                return
            sid = str(raw_item.get("item_id") or raw_item.get("id") or f"{pipeline}:{idx}")
            out.append(
                {
                    "pipeline": pipeline,
                    "content_type": t,
                    "text": text,
                    "source_item_id": sid,
                    "metadata": {
                        "page_idx": raw_item.get("page_idx"),
                        "source_path": raw_item.get("source_path") or raw_item.get("source_file"),
                        "image_path": raw_item.get("img_path") or raw_item.get("image_path"),
                        "bbox": raw_item.get("bbox"),
                        "route_pipeline": pipeline,
                    },
                    "raw_item": dict(raw_item),
                }
            )

        if routes:
            ordered = []
            for p in cls.ROUTE_PRIORITY:
                if p in routes:
                    ordered.append(p)
            for p in routes.keys():
                if p not in ordered:
                    ordered.append(p)
            for p in ordered:
                if p == "discard_pipeline":
                    continue
                items = routes.get(p)
                if not isinstance(items, list):
                    continue
                for i, one in enumerate(items):
                    if not isinstance(one, dict):
                        continue
                    push_item(str(p), dict(one), i)
        else:
            if not content_list:
                return [], ["chunk.split 缺少 routes/content_list，无法切片"]
            for i, one in enumerate(content_list):
                if not isinstance(one, dict):
                    continue
                t = str(one.get("type", "unknown")).strip().lower() or "unknown"
                pipeline = cls._type_to_default_pipeline(t)
                if pipeline in skip_pipelines:
                    continue
                push_item(pipeline, dict(one), i)
            warnings.append("chunk.split hint: routes 缺失，已从 content_list 推断 pipeline")

        return out, warnings

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="",
            display_name="文本切片",
            category="chunk",
            description="将路由后的内容切成可索引 chunks。",
            implementation_status="partial",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(
                    name="chunk_token_size",
                    label="Chunk token size",
                    type="number",
                    required=False,
                    default=1200,
                ),
                NodeConfigField(
                    name="chunk_overlap_token_size",
                    label="Overlap token size",
                    type="number",
                    required=False,
                    default=100,
                ),
                NodeConfigField(
                    name="split_by_character",
                    label="按字符切分",
                    type="string",
                    required=False,
                    default="",
                ),
                NodeConfigField(
                    name="split_by_character_only",
                    label="仅按字符切分",
                    type="boolean",
                    required=False,
                    default=False,
                ),
                NodeConfigField(
                    name="include_multimodal_descriptions",
                    label="包含多模态描述",
                    type="boolean",
                    required=False,
                    default=True,
                ),
                NodeConfigField(
                    name="skip_pipelines",
                    label="跳过 pipeline",
                    type="json",
                    required=False,
                    default=["discard_pipeline"],
                ),
            ],
            input_schema={"type": "object", "description": "routes/content_list/multimodal_descriptions"},
            output_schema={"type": "object", "description": "chunks/chunk_summary"},
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        payload = dict(input_data) if isinstance(input_data, dict) else {}
        parsed_document = ContentAccess.get_parsed_document(context, self.node_id)
        if isinstance(parsed_document, dict):
            payload.setdefault("parsed_document", parsed_document)
            if "content_list" not in payload:
                raw_list = parsed_document.get("raw_content_list")
                payload["content_list"] = raw_list if isinstance(raw_list, list) else []

        chunk_token_size = max(1, int(self.config.get("chunk_token_size") or 1200))
        chunk_overlap = max(0, int(self.config.get("chunk_overlap_token_size") or 100))
        split_by_character = str(self.config.get("split_by_character") or "").strip() or None
        split_by_character_only = bool(self.config.get("split_by_character_only", False))
        include_mm_desc = bool(self.config.get("include_multimodal_descriptions", True))
        skip_pipelines = {x.strip() for x in self._json_to_list(self.config.get("skip_pipelines")) if x.strip()}

        items, collect_warnings = self._collect_chunk_items(
            payload=payload,
            include_multimodal_descriptions=include_mm_desc,
            skip_pipelines=skip_pipelines,
        )
        if not items:
            out_empty = dict(payload)
            out_empty["chunks"] = []
            out_empty["chunk_summary"] = {
                "input_items": 0,
                "total_chunks": 0,
                "pipeline_distribution": {},
                "type_distribution": {},
                "source_algorithm": "lightrag.operate.chunking_by_token_size",
                "used_original_algorithm": True,
                "warnings": collect_warnings,
            }
            ContentAccess.set_chunks(context, self.node_id, [])
            return NodeResult(success=True, data=out_empty, metadata={"node": "chunk.split"})

        adapter = context.adapters.get("lightrag_chunk")
        if adapter is None:
            return NodeResult(success=False, error="chunk.split requires lightrag_chunk adapter", data=payload)
        try:
            ret = await adapter.split_chunks(
                items,
                chunk_token_size=chunk_token_size,
                chunk_overlap_token_size=chunk_overlap,
                split_by_character=split_by_character,
                split_by_character_only=split_by_character_only,
            )
        except Exception as exc:  # noqa: BLE001
            return NodeResult(success=False, error=f"chunk.split failed: {exc}", data=payload)

        chunks = ret.get("chunks") if isinstance(ret, dict) else []
        summary = ret.get("chunk_summary") if isinstance(ret, dict) else {}
        warnings = list(collect_warnings)
        if isinstance(summary, dict) and isinstance(summary.get("warnings"), list):
            warnings.extend([str(x) for x in summary.get("warnings") if str(x).strip()])
        summary = self._as_dict(summary)
        summary["input_items"] = int(summary.get("input_items") or len(items))
        summary["total_chunks"] = int(summary.get("total_chunks") or (len(chunks) if isinstance(chunks, list) else 0))
        summary["pipeline_distribution"] = self._as_dict(summary.get("pipeline_distribution"))
        summary["type_distribution"] = self._as_dict(summary.get("type_distribution"))
        summary["source_algorithm"] = str(
            summary.get("source_algorithm") or "lightrag.operate.chunking_by_token_size"
        )
        summary["used_original_algorithm"] = bool(summary.get("used_original_algorithm", True))
        summary["warnings"] = warnings

        out = dict(payload)
        out["chunks"] = chunks if isinstance(chunks, list) else []
        out["chunk_summary"] = summary
        ContentAccess.set_chunks(context, self.node_id, out["chunks"])
        context.log(
            f"[ChunkSplitNode] input_items={summary['input_items']} total_chunks={summary['total_chunks']} "
            f"skip={sorted(skip_pipelines)}"
        )
        return NodeResult(
            success=True,
            data=out,
            metadata={"node": "chunk.split"},
        )
