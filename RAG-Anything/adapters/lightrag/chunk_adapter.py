"""
Chunk 适配器：通过 LightRAG 的局部切片能力执行分块。
"""

from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any

from .engine_adapter import LightRAGEngineAdapter


class ChunkAdapter:
    """封装 LightRAG ``chunking_func`` 调用。"""

    def __init__(self, engine: LightRAGEngineAdapter) -> None:
        self._engine = engine

    @property
    def rag(self):
        return self._engine.rag

    @staticmethod
    def _stable_chunk_id(*, pipeline: str, source_item_id: str, chunk_index: int, text: str) -> str:
        seed = f"{pipeline}|{source_item_id}|{chunk_index}|{hashlib.sha1(text.encode('utf-8')).hexdigest()[:16]}"
        return f"chunk_{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:24]}"

    async def split_chunks(
        self,
        items: list[dict],
        *,
        chunk_token_size: int = 1200,
        chunk_overlap_token_size: int = 100,
        split_by_character: str | None = None,
        split_by_character_only: bool = False,
    ) -> dict[str, Any]:
        out_chunks: list[dict[str, Any]] = []
        pipe_counter: Counter[str] = Counter()
        type_counter: Counter[str] = Counter()

        tokenizer = getattr(self.rag, "tokenizer", None)
        chunking_func = getattr(self.rag, "chunking_func", None)
        if tokenizer is None or not callable(chunking_func):
            return {
                "chunks": [],
                "chunk_summary": {
                    "input_items": len(items),
                    "total_chunks": 0,
                    "pipeline_distribution": {},
                    "type_distribution": {},
                    "source_algorithm": "lightrag.operate.chunking_by_token_size",
                    "used_original_algorithm": False,
                    "warnings": ["LightRAG chunking_func/tokenizer is unavailable"],
                },
                "source_algorithm": "lightrag.operate.chunking_by_token_size",
                "adapter_path": "adapters.lightrag.chunk_adapter.ChunkAdapter",
                "used_original_algorithm": False,
            }

        for idx, one in enumerate(items):
            if not isinstance(one, dict):
                continue
            text = str(one.get("text") or "").strip()
            if not text:
                continue
            pipeline = str(one.get("pipeline") or "text_pipeline").strip() or "text_pipeline"
            content_type = str(one.get("content_type") or "text").strip().lower() or "text"
            source_item_id = str(one.get("source_item_id") or f"item-{idx}").strip() or f"item-{idx}"
            metadata = one.get("metadata") if isinstance(one.get("metadata"), dict) else {}
            raw_item = one.get("raw_item") if isinstance(one.get("raw_item"), dict) else {}

            chunk_rows = chunking_func(
                tokenizer,
                text,
                split_by_character=split_by_character,
                split_by_character_only=split_by_character_only,
                chunk_overlap_token_size=max(0, int(chunk_overlap_token_size)),
                chunk_token_size=max(1, int(chunk_token_size)),
            )
            if not isinstance(chunk_rows, (list, tuple)):
                continue
            for cidx, row in enumerate(chunk_rows):
                if not isinstance(row, dict):
                    continue
                chunk_text = str(row.get("content") or "").strip()
                if not chunk_text:
                    continue
                tokens = row.get("tokens")
                tval = int(tokens) if isinstance(tokens, (int, float)) else 0
                out_chunks.append(
                    {
                        "chunk_id": self._stable_chunk_id(
                            pipeline=pipeline,
                            source_item_id=source_item_id,
                            chunk_index=cidx,
                            text=chunk_text,
                        ),
                        "pipeline": pipeline,
                        "content_type": content_type,
                        "text": chunk_text,
                        "tokens": tval,
                        "source_item_id": source_item_id,
                        "metadata": dict(metadata),
                        "raw_item": dict(raw_item) if raw_item else {},
                    }
                )
                pipe_counter[pipeline] += 1
                type_counter[content_type] += 1

        return {
            "chunks": out_chunks,
            "chunk_summary": {
                "input_items": len(items),
                "total_chunks": len(out_chunks),
                "pipeline_distribution": dict(pipe_counter),
                "type_distribution": dict(type_counter),
                "source_algorithm": "lightrag.operate.chunking_by_token_size",
                "used_original_algorithm": True,
            },
            "source_algorithm": "lightrag.operate.chunking_by_token_size",
            "adapter_path": "adapters.lightrag.chunk_adapter.ChunkAdapter",
            "used_original_algorithm": True,
        }

