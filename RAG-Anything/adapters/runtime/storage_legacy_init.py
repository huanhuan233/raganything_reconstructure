"""多后端存储持久化（独立于 LightRAG / raganything 核心库）。"""

from __future__ import annotations

from .persist import persist_embedding_records

__all__ = ["persist_embedding_records"]
