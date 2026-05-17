"""下游节点载荷白名单拷贝：剥离 OCR / routes / 原始 content_list 等巨型字段，保留建库与本体验链."""

from __future__ import annotations

from typing import Any, FrozenSet

# 语义运行 / 图谱落盘链路需要沿 DAG 接力传递的核心键。
SEMANTIC_CARRY_KEEP: FrozenSet[str] = frozenset(
    {
        # 向量落盘尾部
        "embedding_records",
        "embedding_summary",
        "semantic_blocks",
        "semantic_merge_summary",
        "chunks",
        "chunk_summary",
        # 实体关系与关系归并
        "entities",
        "relations",
        "merged_entities",
        "merged_relations",
        "entity_merge_map",
        "relation_merge_map",
        "relation_merge_summary",
        "relation_merge",
        "entity_relation_summary",
        "entity_relation_extract_summary",
        "graph_summary",
        "graph_merge",
        # 工业结构与图谱主产物
        "process_summary",
        "composite_structure",
        "constraints",
        "structured_tables",
        "process_graph",
        "process_steps",
        "industrial_graph",
        "graph",
        # 运行时本体 / ISR
        "ontology_objects",
        "ontology_object",
        "semantic_plan",
        "semantic_runtime_state",
        "industrial_filtered",
        "valid_objects",
        "rejected_objects",
        "constraint_explanations",
        "explanation_digest_zh",
        "constraint_extract_preview",
        # 持久化回执与跳过原因
        "ontology_graph_persist_summary",
        "ontology_graph_persist_skipped",
        "ontology_graph_persist_reason",
        "semantic_relation_persist_summary",
        "semantic_relation_persist_skipped",
        "semantic_relation_persist_reason",
        "semantic_relations_preview",
        "semantic_relation_preview",
        "constraint_relation_persist_summary",
        "constraint_relation_persist_skipped",
        "constraint_relation_snapshot",
        "industrial_graph_persist_summary",
        "industrial_graph_persist_errors",
        "storage_refs",
        "storage_summary",
        # 文档溯源（短字段）
        "doc_id",
        "document_id",
        "document_id_normalized",
        "track_id",
        "source_path",
        # 轻量化解析占位（可由 chunk.split 等处写入）
        "parsed_document",
        "warnings",
        "candidate_retrieval_results",
        "candidate_retrieval_results_filtered",
        "candidate_plan",
        "candidate_process_plan",
        "semantic_dependencies",
        "semantic_relations",
    }
)


def slim_semantic_carry_payload(inp: dict[str, Any] | None) -> dict[str, Any]:
    """
    从上游 payload 拷贝白名单字段，丢弃 routes / multimodal_blocks 等与当前节点无关的大数据。
    若某键缺失，调用方仍可随后从 ExecutionContext.content_pool 读取同名桶。
    """
    if not isinstance(inp, dict) or not inp:
        return {}
    return {k: inp[k] for k in SEMANTIC_CARRY_KEEP if k in inp}
