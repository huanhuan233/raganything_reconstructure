"""内置可编排节点：注册到默认 NodeRegistry。"""

from __future__ import annotations

from runtime_kernel.node_runtime.node_registry import get_default_registry
from .parsing.chunk_split_node import ChunkSplitNode
from .parsing.content_filter_node import ContentFilterNode
from .parsing.content_normalize_node import ContentNormalizeNode
from .parsing.document_parse_node import DocumentParseNode
from .storage.doc_status_update_node import DocStatusUpdateNode
from .storage.embedding_index_node import EmbeddingIndexNode
from .storage.lightrag_insert_node import LightRAGInsertNode
from .storage.rag_delete_node import RAGDeleteNode
from .storage.raganything_insert_node import RAGAnythingInsertNode
from .storage.storage_persist_node import StoragePersistNode
from .multimodal.content_route_node import ContentRouteNode
from .multimodal.multimodal_process_node import MultimodalProcessNode
from .multimodal.visual_recover_node import VisualRecoverNode
from .retrieval.graph_retrieve_node import GraphRetrieveNode
from .retrieval.keyword_extract_node import KeywordExtractNode
from .retrieval.knowledge_select_node import KnowledgeSelectNode
from .retrieval.rag_query_node import RAGQueryNode
from .retrieval.rerank_node import RerankNode
from .retrieval.retrieval_merge_node import RetrievalMergeNode
from .retrieval.vector_retrieve_node import VectorRetrieveNode
from .graph.entity_merge_node import EntityMergeNode
from .graph.entity_relation_extract_node import EntityRelationExtractNode
from .graph.graph_merge_node import GraphMergeNode
from .graph.graph_persist_node import GraphPersistNode
from .graph.constraint_relation_persist_node import ConstraintRelationPersistNode
from .graph.ontology_graph_persist_node import OntologyGraphPersistNode
from .graph.relation_merge_node import RelationMergeNode
from .graph.semantic_relation_persist_node import SemanticRelationPersistNode
from .workflow.context_build_node import ContextBuildNode
from .workflow.workflow_end_node import WorkflowEndNode
from .workflow.workflow_start_node import WorkflowStartNode
from .llm.llm_generate_node import LLMGenerateNode
from .industrial.industrial_registry import register_industrial_nodes


def register_builtin_nodes() -> None:
    """将本包内建节点类型注册到 ``get_default_registry()``。"""
    reg = get_default_registry()
    reg.register("workflow.start", WorkflowStartNode)
    reg.register("workflow.end", WorkflowEndNode)
    reg.register("document.parse", DocumentParseNode)
    reg.register("doc.status.update", DocStatusUpdateNode)
    reg.register("content.normalize", ContentNormalizeNode)
    reg.register("content.filter", ContentFilterNode)
    reg.register("content.route", ContentRouteNode)
    reg.register("chunk.split", ChunkSplitNode)
    reg.register("entity_relation.extract", EntityRelationExtractNode)
    reg.register("embedding.index", EmbeddingIndexNode)
    reg.register("storage.persist", StoragePersistNode)
    reg.register("lightrag.insert", LightRAGInsertNode)
    reg.register("raganything.insert", RAGAnythingInsertNode)
    reg.register("multimodal.process", MultimodalProcessNode)
    reg.register("visual.recover", VisualRecoverNode)
    reg.register("rag.query", RAGQueryNode)
    reg.register("keyword.extract", KeywordExtractNode)
    reg.register("knowledge.select", KnowledgeSelectNode)
    reg.register("vector.retrieve", VectorRetrieveNode)
    reg.register("graph.retrieve", GraphRetrieveNode)
    reg.register("rerank", RerankNode)
    reg.register("rag.delete", RAGDeleteNode)
    reg.register("entity.merge", EntityMergeNode)
    reg.register("relation.merge", RelationMergeNode)
    reg.register("graph.merge", GraphMergeNode)
    reg.register("graph.persist", GraphPersistNode)
    reg.register("ontology.graph.persist", OntologyGraphPersistNode)
    reg.register("semantic.relation.persist", SemanticRelationPersistNode)
    reg.register("constraint.relation.persist", ConstraintRelationPersistNode)
    reg.register("retrieval.merge", RetrievalMergeNode)
    reg.register("context.build", ContextBuildNode)
    reg.register("llm.generate", LLMGenerateNode)
    register_industrial_nodes(reg)


register_builtin_nodes()

__all__ = [
    "register_builtin_nodes",
    "WorkflowStartNode",
    "WorkflowEndNode",
    "ChunkSplitNode",
    "DocumentParseNode",
    "DocStatusUpdateNode",
    "ContentFilterNode",
    "ContentRouteNode",
    "ContentNormalizeNode",
    "EmbeddingIndexNode",
    "EntityRelationExtractNode",
    "LightRAGInsertNode",
    "RAGAnythingInsertNode",
    "MultimodalProcessNode",
    "VisualRecoverNode",
    "RAGQueryNode",
    "KeywordExtractNode",
    "KnowledgeSelectNode",
    "VectorRetrieveNode",
    "GraphRetrieveNode",
    "RerankNode",
    "RAGDeleteNode",
    "EntityMergeNode",
    "RelationMergeNode",
    "GraphMergeNode",
    "GraphPersistNode",
    "OntologyGraphPersistNode",
    "SemanticRelationPersistNode",
    "ConstraintRelationPersistNode",
    "RetrievalMergeNode",
    "ContextBuildNode",
    "LLMGenerateNode",
    "StoragePersistNode",
]
