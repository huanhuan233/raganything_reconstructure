"""Runtime state 基础类型定义。"""

from __future__ import annotations

from enum import Enum


class NodePhase(str, Enum):
    """节点生命周期状态。"""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ExecutionPhase(str, Enum):
    """工作流运行状态。"""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


CONTENT_BUCKETS: tuple[str, ...] = (
    "parsed_document",
    "chunks",
    "multimodal_blocks",
    "embeddings",
    "entities",
    "relations",
    "graph_objects",
    "retrieval_results",
    "rerank_results",
    "generated_content",
)
