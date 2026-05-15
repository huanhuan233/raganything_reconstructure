"""多模态语义增强：处理 image/table/equation/sheet/seal 等块。"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.entities.content_types import (
    CONTENT_TYPE_GROUPS,
    get_content_group,
    is_formula_type,
    is_table_type,
    is_vision_type,
)
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult


class MultimodalProcessNode(BaseNode):
    """对非 text 内容做多模态理解，产出可检索描述文本。"""

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="",
            display_name="多模态处理",
            category="multimodal",
            description="多模态内容理解与可检索文本增强。",
            implementation_status="partial",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(
                    name="use_vlm",
                    label="使用 VLM",
                    type="boolean",
                    required=False,
                    default=False,
                ),
                NodeConfigField(
                    name="vlm_model",
                    label="VLM 模型",
                    type="select",
                    required=False,
                    options=[],
                    description="默认读取 .env 中的 VISION_MODEL；候选项由 /api/nodes 动态注入。",
                ),
                NodeConfigField(
                    name="vlm_prompt",
                    label="VLM 提示词",
                    type="string",
                    required=False,
                    default="请描述该图片、表格或视觉区域中的关键信息，用于后续RAG检索。",
                ),
                NodeConfigField(
                    name="max_visual_items",
                    label="最多处理条数",
                    type="number",
                    required=False,
                    default=32,
                ),
                NodeConfigField(
                    name="process_types",
                    label="处理类型",
                    type="json",
                    required=False,
                    default=sorted(
                        CONTENT_TYPE_GROUPS["VISION_TYPES"]
                        | CONTENT_TYPE_GROUPS["TABLE_TYPES"]
                        | CONTENT_TYPE_GROUPS["FORMULA_TYPES"]
                        | {"footer", "page_number"}
                    ),
                ),
                NodeConfigField(
                    name="resume_from_cache",
                    label="启用断点缓存恢复",
                    type="boolean",
                    required=False,
                    default=True,
                ),
                NodeConfigField(
                    name="resume_cache_key",
                    label="断点缓存键",
                    type="string",
                    required=False,
                    default="",
                    description="可选；为空时按 workflow/source_path/config 自动生成。",
                ),
            ],
            input_schema={"type": "object"},
            output_schema={
                "type": "object",
                "description": "content_list, multimodal_items, multimodal_descriptions, process_summary",
            },
        )

    @staticmethod
    def _as_type_set(v: Any) -> set[str]:
        if v is None:
            return set()
        if isinstance(v, list):
            return {str(x).strip().lower() for x in v if str(x).strip()}
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return set()
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return {str(x).strip().lower() for x in parsed if str(x).strip()}
            except Exception:  # noqa: BLE001
                return {s.lower()}
        return set()

    async def _maybe_call_vlm(
        self,
        context: ExecutionContext,
        *,
        prompt: str,
        image_path: str | None = None,
        vlm_provider: str = "",
        vlm_model: str = "",
    ) -> str | None:
        async def _await_if_needed(x: Any) -> Any:
            if hasattr(x, "__await__"):
                return await x
            return x

        fn: Any = None
        # 1) 显式 provider 名称
        if vlm_provider and vlm_provider in context.adapters:
            provider = context.adapters.get(vlm_provider)
            if callable(provider):
                fn = provider
            elif hasattr(provider, "vision_model_func"):
                fn = getattr(provider, "vision_model_func")
            elif hasattr(provider, "generate"):
                fn = getattr(provider, "generate")
        # 2) raganything engine 注入
        if fn is None:
            rag = context.adapters.get("raganything")
            if rag is not None:
                if hasattr(rag, "raganything") and hasattr(rag.raganything, "vision_model_func"):
                    fn = getattr(rag.raganything, "vision_model_func")
                elif hasattr(rag, "vision_model_func"):
                    fn = getattr(rag, "vision_model_func")
        # 3) 通用 callable 注入
        if fn is None:
            for key in ("vision_model_func", "vlm_provider", "vision"):
                c = context.adapters.get(key)
                if callable(c):
                    fn = c
                    break
        if fn is None:
            # 无注入 provider 时，回退到 OpenAI-compatible（由环境变量驱动）
            return await self._call_openai_compatible_vlm(
                prompt=prompt,
                image_path=image_path,
                vlm_model=vlm_model,
            )

        image_b64: str | None = None
        if image_path:
            p = Path(image_path)
            if p.is_file():
                try:
                    image_b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
                except Exception:  # noqa: BLE001
                    image_b64 = None
        kwargs = {"prompt": prompt}
        if vlm_model:
            kwargs["model"] = vlm_model
        if image_b64:
            kwargs["image_data"] = image_b64
        # 兼容常见签名：prompt / system_prompt / image_data / messages
        try:
            ret = await _await_if_needed(fn(**kwargs))
        except TypeError:
            ret = await _await_if_needed(fn(prompt))
        if ret is None:
            return None
        if isinstance(ret, str):
            return ret.strip()
        return str(ret).strip()

    async def _call_openai_compatible_vlm(
        self,
        *,
        prompt: str,
        image_path: str | None,
        vlm_model: str,
    ) -> str | None:
        base_url = (
            os.getenv("VLM_BINDING_HOST")
            or os.getenv("LLM_BINDING_HOST")
            or os.getenv("OPENAI_BASE_URL")
            or ""
        ).strip()
        api_key = (
            os.getenv("VLM_BINDING_API_KEY")
            or os.getenv("LLM_BINDING_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or ""
        ).strip()
        model = (vlm_model or os.getenv("VISION_MODEL") or "").strip()
        if not (base_url and api_key and model):
            return None
        try:
            from openai import OpenAI
        except Exception:  # noqa: BLE001
            return None

        image_b64: str | None = None
        if image_path:
            p = Path(image_path)
            if p.is_file():
                try:
                    image_b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
                except Exception:  # noqa: BLE001
                    image_b64 = None

        def _invoke() -> str | None:
            client = OpenAI(base_url=base_url, api_key=api_key)
            if image_b64:
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                        ],
                    }
                ]
            else:
                messages = [{"role": "user", "content": prompt}]
            resp = client.chat.completions.create(model=model, messages=messages)
            try:
                return (resp.choices[0].message.content or "").strip()
            except Exception:  # noqa: BLE001
                return str(resp).strip()

        try:
            import asyncio

            return await asyncio.to_thread(_invoke)
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _vlm_trace_path(run_id: str) -> Path:
        root = Path(__file__).resolve().parents[2]
        out_dir = root / "backend_api" / "storage" / "runs"
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir / f"{run_id}_vlm.jsonl"

    @classmethod
    def _append_vlm_trace(cls, run_id: str, record: dict[str, Any]) -> None:
        try:
            path = cls._vlm_trace_path(run_id)
            payload = json.dumps(record, ensure_ascii=False)
            with path.open("a", encoding="utf-8") as f:
                f.write(payload + "\n")
        except Exception:  # noqa: BLE001
            # 跟踪日志写入失败不影响主流程。
            pass

    @staticmethod
    def _checkpoint_path(cache_key: str) -> Path:
        root = Path(__file__).resolve().parents[2]
        out_dir = root / "backend_api" / "storage" / "runs"
        out_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha1(cache_key.encode("utf-8")).hexdigest()[:16]
        return out_dir / f"multimodal_{digest}_checkpoint.jsonl"

    @classmethod
    def _load_checkpoint(cls, cache_key: str) -> dict[int, dict[str, Any]]:
        path = cls._checkpoint_path(cache_key)
        if not path.is_file():
            return {}
        out: dict[int, dict[str, Any]] = {}
        try:
            with path.open(encoding="utf-8") as f:
                for line in f:
                    s = line.strip()
                    if not s:
                        continue
                    try:
                        one = json.loads(s)
                    except Exception:  # noqa: BLE001
                        continue
                    idx = one.get("idx")
                    if isinstance(idx, int) and idx > 0 and isinstance(one, dict):
                        out[idx] = one
        except Exception:  # noqa: BLE001
            return {}
        return out

    @classmethod
    def _append_checkpoint(cls, cache_key: str, record: dict[str, Any]) -> None:
        try:
            path = cls._checkpoint_path(cache_key)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:  # noqa: BLE001
            pass

    @staticmethod
    def _item_fingerprint(*, t: str, page_idx: Any, image_path: str, table_text: str, eq_text: str) -> str:
        src = json.dumps(
            {
                "type": t,
                "page_idx": page_idx,
                "image_path": image_path,
                "table_text": table_text[:500],
                "equation_text": eq_text[:500],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha1(src.encode("utf-8")).hexdigest()[:20]

    @staticmethod
    def _resolve_cache_key(
        *,
        explicit_key: str,
        context: ExecutionContext,
        source_path: str,
        use_vlm: bool,
        vlm_model: str,
        max_visual_items: int,
        process_types: set[str],
    ) -> str:
        if explicit_key:
            return explicit_key
        basis = {
            "workflow_id": context.workflow_id,
            "node_id": "multimodal.process",
            "source_path": source_path or "",
            "use_vlm": use_vlm,
            "vlm_model": vlm_model or "",
            "max_visual_items": max_visual_items,
            "process_types": sorted(process_types),
        }
        return json.dumps(basis, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _normalize_source_path(path: str) -> str:
        s = str(path or "").strip()
        if not s:
            return ""
        return s.replace("\\", "/").lower()

    @staticmethod
    def _cache_key_hash(cache_key: str) -> str:
        return hashlib.sha1(cache_key.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _rule_description(item: dict[str, Any], t: str) -> str:
        page = item.get("page_idx", "?")
        if t in {"image", "seal"}:
            return f"Image block detected on page {page}."
        if is_table_type(t):
            table_text = str(item.get("table_body", "")).strip()
            if table_text:
                return f"Table-like block detected on page {page}: {table_text[:200]}"
            return f"Table-like block detected on page {page}."
        if is_formula_type(t):
            return "Mathematical equation detected."
        if t == "footer":
            return f"Footer block detected on page {page}."
        if t == "page_number":
            return f"Page number marker detected on page {page}."
        return f"{t} block detected on page {page}."

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        started = time.perf_counter()
        if not isinstance(input_data, dict):
            return NodeResult(success=False, error="multimodal.process 期望输入为 dict")
        content_list = input_data.get("content_list")
        if not isinstance(content_list, list):
            return NodeResult(success=False, error="multimodal.process 缺少 content_list(list)")

        use_vlm = bool(self.config.get("use_vlm", False))
        vlm_model = str(self.config.get("vlm_model", "") or "").strip()
        vlm_prompt = str(
            self.config.get("vlm_prompt", "请描述该图片、表格或视觉区域中的关键信息，用于后续RAG检索。")
            or "请描述该图片、表格或视觉区域中的关键信息，用于后续RAG检索。"
        ).strip()
        max_visual_items = int(self.config.get("max_visual_items", 32) or 32)
        if max_visual_items <= 0:
            max_visual_items = 32
        process_types = self._as_type_set(self.config.get("process_types"))
        if not process_types:
            process_types = (
                set(CONTENT_TYPE_GROUPS["VISION_TYPES"])
                | set(CONTENT_TYPE_GROUPS["TABLE_TYPES"])
                | set(CONTENT_TYPE_GROUPS["FORMULA_TYPES"])
                | {"footer", "page_number"}
            )
        context.log(
            "[MultimodalProcessNode] start "
            f"before_count={len(content_list)} use_vlm={use_vlm} "
            f"max_visual_items={max_visual_items} process_types={sorted(process_types)}"
        )

        source_path_raw = str(
            input_data.get("source_path")
            or (input_data.get("parsed_document") or {}).get("source_file")
            or ""
        )
        source_path = self._normalize_source_path(source_path_raw)
        resume_from_cache = bool(self.config.get("resume_from_cache", True))
        explicit_cache_key = str(
            self.config.get("resume_cache_key")
            or (input_data.get("resume_cache_key") if isinstance(input_data, dict) else "")
            or ""
        ).strip()
        cache_key_norm = self._resolve_cache_key(
            explicit_key=explicit_cache_key,
            context=context,
            source_path=source_path,
            use_vlm=use_vlm,
            vlm_model=vlm_model,
            max_visual_items=max_visual_items,
            process_types=process_types,
        )
        # 兼容旧缓存键（未归一化 source_path），避免升级后缓存失效。
        cache_keys = [cache_key_norm]
        if not explicit_cache_key:
            cache_key_legacy = self._resolve_cache_key(
                explicit_key="",
                context=context,
                source_path=source_path_raw,
                use_vlm=use_vlm,
                vlm_model=vlm_model,
                max_visual_items=max_visual_items,
                process_types=process_types,
            )
            if cache_key_legacy not in cache_keys:
                cache_keys.append(cache_key_legacy)
        checkpoint_by_idx: dict[int, dict[str, Any]] = {}
        loaded_hashes: list[str] = []
        if resume_from_cache:
            for one_key in cache_keys:
                one_ckpt = self._load_checkpoint(one_key)
                if one_ckpt:
                    loaded_hashes.append(self._cache_key_hash(one_key))
                    for k, v in one_ckpt.items():
                        checkpoint_by_idx.setdefault(k, v)
        if checkpoint_by_idx:
            context.log(
                "[MultimodalProcessNode] resume cache enabled "
                f"cache_hits={len(checkpoint_by_idx)} loaded_hashes={loaded_hashes} "
                f"write_hash={self._cache_key_hash(cache_key_norm)}"
            )
        elif resume_from_cache:
            context.log(
                "[MultimodalProcessNode] resume cache miss "
                f"try_hashes={[self._cache_key_hash(x) for x in cache_keys]}"
            )
        multimodal_items: list[dict[str, Any]] = []
        candidate_counter: Counter[str] = Counter()
        for raw in content_list:
            if not isinstance(raw, dict):
                continue
            t = str(raw.get("type", "")).strip().lower()
            if t and t in process_types:
                multimodal_items.append(dict(raw))
                candidate_counter[t] += 1
            if len(multimodal_items) >= max_visual_items:
                break
        context.log(
            "[MultimodalProcessNode] candidate_selected "
            f"candidate_count={len(multimodal_items)} type_distribution={dict(candidate_counter)}"
        )

        descriptions: list[dict[str, Any]] = []
        type_counter: Counter[str] = Counter()
        vlm_used_count = 0
        fallback_count = 0

        for idx, item in enumerate(multimodal_items, start=1):
            t = str(item.get("type", "unknown")).strip().lower()
            page_idx = item.get("page_idx")
            image_path = str(item.get("img_path", "")).strip() if is_vision_type(t) else ""
            table_text = str(item.get("table_body", "")).strip() if is_table_type(t) else ""
            eq_text = str(item.get("latex") or item.get("text") or "").strip() if is_formula_type(t) else ""
            fingerprint = self._item_fingerprint(
                t=t,
                page_idx=page_idx,
                image_path=image_path,
                table_text=table_text,
                eq_text=eq_text,
            )

            prompt = vlm_prompt
            if is_table_type(t) and table_text:
                prompt = f"{vlm_prompt}\n\n表格内容:\n{table_text[:3000]}"
            elif is_formula_type(t) and eq_text:
                prompt = f"{vlm_prompt}\n\n公式内容:\n{eq_text[:1200]}"

            text_description: str | None = None
            vlm_response: str | None = None
            use_vlm_for_item = use_vlm and get_content_group(t) in {"vision", "table", "formula"}
            cache_hit = False
            context.log(
                "[MultimodalProcessNode] item_processing "
                f"idx={idx}/{len(multimodal_items)} type={t} page_idx={page_idx} "
                f"use_vlm_for_item={use_vlm_for_item}"
            )
            cached = checkpoint_by_idx.get(idx)
            if isinstance(cached, dict) and cached.get("fingerprint") == fingerprint:
                cache_hit = True
                vlm_response = cached.get("vlm_response") if isinstance(cached.get("vlm_response"), str) else None
                td = cached.get("text_description")
                text_description = str(td).strip() if td is not None else None
            else:
                if use_vlm_for_item:
                    vlm_response = await self._maybe_call_vlm(
                        context,
                        prompt=prompt,
                        image_path=image_path or None,
                        vlm_model=vlm_model,
                    )
                    text_description = vlm_response
            if text_description:
                vlm_used_count += 1
            else:
                fallback_count += 1
                text_description = self._rule_description(item, t)

            desc = {
                "item_id": f"{self.node_id}:{idx}",
                "type": t,
                "page_idx": page_idx,
                "source_path": source_path or None,
                "image_path": image_path or None,
                "table_text": table_text or None,
                "equation_text": eq_text or None,
                "text_description": text_description,
                "vlm_response": vlm_response,
                "raw_item": item,
            }
            descriptions.append(desc)
            type_counter[t] += 1
            if resume_from_cache and not cache_hit:
                self._append_checkpoint(
                    cache_key_norm,
                    {
                        "idx": idx,
                        "fingerprint": fingerprint,
                        "type": t,
                        "page_idx": page_idx,
                        "use_vlm_for_item": use_vlm_for_item,
                        "vlm_response": vlm_response,
                        "text_description": text_description,
                    },
                )
            self._append_vlm_trace(
                context.run_id,
                {
                    "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "workflow_id": context.workflow_id,
                    "run_id": context.run_id,
                    "node_id": self.node_id,
                    "item_id": desc["item_id"],
                    "idx": idx,
                    "total": len(multimodal_items),
                    "type": t,
                    "page_idx": page_idx,
                    "use_vlm_for_item": use_vlm_for_item,
                    "cache_hit": cache_hit,
                    "fallback_used": not bool(vlm_response),
                    "vlm_model": vlm_model or None,
                    "prompt": prompt,
                    "vlm_response": vlm_response,
                    "text_description": text_description,
                    "image_path": image_path or None,
                },
            )

        process_summary = {
            "before_count": len(content_list),
            "candidate_count": len(multimodal_items),
            "processed_count": len(descriptions),
            "type_distribution": dict(type_counter),
            "use_vlm": use_vlm,
            "vlm_model": vlm_model or None,
            "vlm_used_count": vlm_used_count,
            "fallback_count": fallback_count,
            "process_types": sorted(process_types),
        }
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        context.log(
            "[MultimodalProcessNode] done "
            f"processed={process_summary['processed_count']} "
            f"vlm_used={vlm_used_count} fallback={fallback_count} "
            f"elapsed_ms={elapsed_ms}"
        )
        return NodeResult(
            success=True,
            data={
                "content_list": content_list,
                "multimodal_items": multimodal_items,
                "multimodal_descriptions": descriptions,
                "process_summary": process_summary,
            },
            metadata={"node": "multimodal.process"},
        )
