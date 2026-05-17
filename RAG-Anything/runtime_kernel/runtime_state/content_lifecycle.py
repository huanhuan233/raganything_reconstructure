"""内容生命周期注册表。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContentLifecycleItem:
    content_name: str
    producer_node: str
    consumer_nodes: list[str]
    lifecycle_stage: str


CONTENT_LIFECYCLE_REGISTRY: list[ContentLifecycleItem] = [
    ContentLifecycleItem(
        content_name="parsed_document",
        producer_node="document.parse",
        consumer_nodes=["chunk.split"],
        lifecycle_stage="document_parsed",
    ),
    ContentLifecycleItem(
        content_name="semantic_blocks",
        producer_node="semantic.block.merge",
        consumer_nodes=["chunk.split"],
        lifecycle_stage="semantic_merged",
    ),
    ContentLifecycleItem(
        content_name="chunks",
        producer_node="chunk.split",
        consumer_nodes=["embedding.index", "entity_relation.extract"],
        lifecycle_stage="chunked",
    ),
    ContentLifecycleItem(
        content_name="embeddings",
        producer_node="embedding.index",
        consumer_nodes=["vector.retrieve", "retrieval.merge"],
        lifecycle_stage="vectorized",
    ),
    ContentLifecycleItem(
        content_name="entities",
        producer_node="entity_relation.extract",
        consumer_nodes=["graph.merge", "graph.persist"],
        lifecycle_stage="graph_entity_extracted",
    ),
    ContentLifecycleItem(
        content_name="relations",
        producer_node="entity_relation.extract",
        consumer_nodes=["graph.merge", "graph.persist"],
        lifecycle_stage="graph_relation_extracted",
    ),
    ContentLifecycleItem(
        content_name="graph_objects",
        producer_node="graph.merge",
        consumer_nodes=["graph.retrieve", "graph.persist"],
        lifecycle_stage="graph_built",
    ),
    ContentLifecycleItem(
        content_name="retrieval_results",
        producer_node="graph.retrieve|vector.retrieve|retrieval.merge",
        consumer_nodes=["rerank", "context.build"],
        lifecycle_stage="retrieved",
    ),
    ContentLifecycleItem(
        content_name="rerank_results",
        producer_node="rerank",
        consumer_nodes=["retrieval.merge", "context.build"],
        lifecycle_stage="reranked",
    ),
    ContentLifecycleItem(
        content_name="generated_content",
        producer_node="llm.generate",
        consumer_nodes=["workflow.end"],
        lifecycle_stage="generated",
    ),
    ContentLifecycleItem(
        content_name="ontology_objects",
        producer_node="ontology.object.define",
        consumer_nodes=[
            "constraint.extract",
            "constraint.runtime.filter",
            "semantic.runtime.plan",
            "ontology.graph.persist",
        ],
        lifecycle_stage="industrial_objects_defined",
    ),
    ContentLifecycleItem(
        content_name="constraints",
        producer_node="constraint.extract",
        consumer_nodes=[
            "constraint.runtime.filter",
            "semantic.runtime.plan",
            "constraint.relation.persist",
        ],
        lifecycle_stage="industrial_constraints_materialized",
    ),
    ContentLifecycleItem(
        content_name="industrial_filtered",
        producer_node="constraint.runtime.filter",
        consumer_nodes=["semantic.runtime.plan", "workflow.end"],
        lifecycle_stage="industrial_runtime_filtered",
    ),
]
