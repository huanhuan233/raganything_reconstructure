"""默认工作流模板。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


_DEFAULT_SEMANTIC_BLOCK_MERGE_CFG: Dict[str, Any] = {
    "semantic_merge_token_limit": 2048,
    "require_same_page": True,
    "protect_multimodal_boundaries": True,
    "protect_industrial_boundaries": True,
}


def _semantic_block_merge_step() -> Tuple[str, str, str, Dict[str, Any]]:
    return ("semantic_block_merge", "semantic.block.merge", "语义块合并", dict(_DEFAULT_SEMANTIC_BLOCK_MERGE_CFG))


def _chunk_split_cfg(extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "chunk_token_size": 1200,
        "chunk_overlap_token_size": 100,
        "include_multimodal_descriptions": True,
        "skip_pipelines": ["discard_pipeline"],
        "prefer_semantic_blocks": True,
    }
    if extra:
        base.update(extra)
    return base


def _mk_node(node_id: str, node_type: str, x: float, y: float, label: str, config: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return {
        "id": node_id,
        "type": node_type,
        "config": dict(config or {}),
        "position": {"x": x, "y": y},
        "label": label,
    }


def _build_doc(
    workflow_id: str,
    name: str,
    description: str,
    nodes: List[Dict[str, Any]],
    edges: List[Tuple[str, str]],
    entry_node_ids: List[str],
    input_data: Any = None,
) -> Dict[str, Any]:
    ts = _utc_iso()
    return {
        "workflow_id": workflow_id,
        "name": name,
        "description": description,
        "nodes": nodes,
        "edges": [[s, t] for s, t in edges],
        "entry_node_ids": entry_node_ids,
        "input_data": input_data,
        "created_at": ts,
        "updated_at": ts,
    }


def build_default_runnable_raganything_workflow() -> Dict[str, Any]:
    """默认可运行多模态 RAG 工作流。"""
    nodes = [
        _mk_node("start", "workflow.start", 80, 120, "开始"),
        _mk_node(
            "insert",
            "raganything.insert",
            360,
            120,
            "RAG-Anything 入库",
            {"parser": "mineru", "parse_method": "auto"},
        ),
        _mk_node(
            "query",
            "rag.query",
            640,
            120,
            "RAG 查询",
            {"engine": "raganything", "mode": "hybrid", "query": "简述文档主要内容。"},
        ),
        _mk_node("end", "workflow.end", 920, 120, "结束"),
    ]
    edges = [("start", "insert"), ("insert", "query"), ("query", "end")]
    return _build_doc(
        workflow_id="default-raganything-runnable",
        name="默认可运行多模态RAG工作流",
        description="文件解析入库并进行问答的默认流程。",
        nodes=nodes,
        edges=edges,
        entry_node_ids=["start"],
        input_data=None,
    )


def build_default_full_pipeline_workflow() -> Dict[str, Any]:
    """默认完整源码阶段展示工作流（细粒度映射链）。"""
    chain = [
        ("start", "workflow.start", "开始", {}),
        ("document_parse", "document.parse", "文档解析", {}),
        ("content_normalize", "content.normalize", "内容规范化", {}),
        ("chunk_split", "chunk.split", "文本切片", {}),
        ("entity_relation_extract", "entity_relation.extract", "实体关系抽取", {}),
        ("entity_merge", "entity.merge", "实体归并", {}),
        ("relation_merge", "relation.merge", "关系归并", {}),
        ("graph_merge", "graph.merge", "图级归并", {}),
        ("embedding_index", "embedding.index", "向量索引", {}),
        ("storage_persist", "storage.persist", "存储落盘", {}),
        ("doc_status_update", "doc.status.update", "文档状态更新", {}),
        ("multimodal_process", "multimodal.process", "多模态预处理", {}),
        ("keyword_extract", "keyword.extract", "关键词抽取", {}),
        ("graph_retrieve", "graph.retrieve", "图谱检索", {}),
        ("vector_retrieve", "vector.retrieve", "向量检索", {}),
        ("retrieval_merge", "retrieval.merge", "检索合并", {}),
        ("rerank", "rerank", "结果重排", {}),
        ("context_build", "context.build", "上下文构建", {}),
        ("visual_recover", "visual.recover", "视觉内容回收", {}),
        ("llm_generate", "llm.generate", "LLM 生成", {}),
        ("end", "workflow.end", "结束", {}),
    ]
    start_x = 80
    start_y = 280
    step_x = 250
    nodes: List[Dict[str, Any]] = []
    for idx, (nid, ntype, label, cfg) in enumerate(chain):
        nodes.append(_mk_node(nid, ntype, start_x + idx * step_x, start_y, label, cfg))
    # 粗粒度真实节点仅做展示参考，不放入主链 edges。
    detached = [
        ("raganything_insert_ref", "raganything.insert", "RAG-Anything 入库（粗粒度参考）", {"parser": "mineru", "parse_method": "auto"}),
        ("rag_query_ref", "rag.query", "RAG 查询（粗粒度参考）", {"engine": "raganything", "mode": "hybrid"}),
        ("lightrag_insert_ref", "lightrag.insert", "LightRAG 入库（参考）", {}),
        ("rag_delete_ref", "rag.delete", "RAG 删除文档（参考）", {}),
    ]
    detach_y = start_y + 210
    for idx, (nid, ntype, label, cfg) in enumerate(detached):
        nodes.append(_mk_node(nid, ntype, start_x + idx * step_x, detach_y, label, cfg))

    edges: List[Tuple[str, str]] = []
    for i in range(len(chain) - 1):
        edges.append((chain[i][0], chain[i + 1][0]))
    return _build_doc(
        workflow_id="default-raganything-full-pipeline",
        name="完整源码阶段展示工作流",
        description="展示 RAGAnything / LightRAG 当前源码阶段与未来可拆解节点形态。",
        nodes=nodes,
        edges=edges,
        entry_node_ids=["start"],
        input_data=None,
    )


def build_default_knowledge_build_workflow() -> Dict[str, Any]:
    """建库模板：解析 -> 过滤 -> 预处理 -> 路由 -> embedding -> storage.persist。"""
    chain = [
        ("document_parse", "document.parse", "文档解析", {}),
        ("content_filter", "content.filter", "内容过滤", {"drop_empty": True, "keep_page_numbers": True}),
        (
            "multimodal_process",
            "multimodal.process",
            "多模态预处理",
            {"use_vlm": False},
        ),
        ("content_route", "content.route", "内容路由", {"keep_unrouted": True, "drop_discard_types": True}),
        (
            "embedding_index",
            "embedding.index",
            "向量索引",
            {"include_raw_item": True, "allow_without_vector": True, "batch_size": 16},
        ),
        ("storage_persist", "storage.persist", "存储落盘", {}),
    ]
    start_x = 120
    start_y = 180
    step_x = 250
    nodes: List[Dict[str, Any]] = []
    for idx, (nid, ntype, label, cfg) in enumerate(chain):
        nodes.append(_mk_node(nid, ntype, start_x + idx * step_x, start_y, label, cfg))
    edges: List[Tuple[str, str]] = []
    for i in range(len(chain) - 1):
        edges.append((chain[i][0], chain[i + 1][0]))
    return _build_doc(
        workflow_id="default-knowledge-build",
        name="建库模板（解析到落盘）",
        description="document.parse -> content.filter -> multimodal.process -> content.route -> embedding.index -> storage.persist",
        nodes=nodes,
        edges=edges,
        entry_node_ids=[chain[0][0]],
        input_data=None,
    )


def build_default_knowledge_query_workflow() -> Dict[str, Any]:
    """查询已有库模板：knowledge.select -> vector.retrieve -> retrieval.merge -> rerank -> context.build -> llm.generate。"""
    chain = [
        (
            "knowledge_select",
            "knowledge.select",
            "选择知识库",
            {
                "knowledge_id": "",
                "collection_mode": "unified",
                "vector_backend": "local_jsonl",
                "graph_backend": "none",
                "workspace": "",
                "collection": "",
                "pipeline_collections": {},
                "text_collection": "",
                "table_collection": "",
                "vision_collection": "",
                "local_jsonl_paths": {},
                "embedding_model": "",
            },
        ),
        ("vector_retrieve", "vector.retrieve", "向量检索", {"top_k": 10}),
        ("retrieval_merge", "retrieval.merge", "检索合并", {}),
        ("rerank", "rerank", "结果重排", {"rerank_engine": "runtime", "rerank_model": "none", "top_k": 8}),
        ("context_build", "context.build", "上下文构建", {}),
        ("llm_generate", "llm.generate", "LLM 生成", {}),
    ]
    start_x = 120
    start_y = 420
    step_x = 260
    nodes: List[Dict[str, Any]] = []
    for idx, (nid, ntype, label, cfg) in enumerate(chain):
        nodes.append(_mk_node(nid, ntype, start_x + idx * step_x, start_y, label, cfg))
    edges: List[Tuple[str, str]] = []
    for i in range(len(chain) - 1):
        edges.append((chain[i][0], chain[i + 1][0]))
    return _build_doc(
        workflow_id="default-knowledge-query",
        name="查询已有库模板",
        description="knowledge.select -> vector.retrieve -> retrieval.merge -> rerank -> context.build -> llm.generate",
        nodes=nodes,
        edges=edges,
        entry_node_ids=[chain[0][0]],
        input_data={"query": "请概述知识库中的重点内容"},
    )


def build_default_knowledge_qa_full_workflow() -> Dict[str, Any]:
    """问答模板（含 start/end）：start -> knowledge.select -> keyword.extract -> vector.retrieve -> retrieval.merge -> rerank -> context.build -> llm.generate -> end。"""
    chain = [
        ("start", "workflow.start", "开始", {}),
        (
            "knowledge_select",
            "knowledge.select",
            "选择知识库",
            {
                "knowledge_id": "",
                "collection_mode": "unified",
                "vector_backend": "local_jsonl",
                "graph_backend": "none",
                "workspace": "",
                "collection": "",
                "pipeline_collections": {},
                "text_collection": "",
                "table_collection": "",
                "vision_collection": "",
                "local_jsonl_paths": {},
                "embedding_model": "",
            },
        ),
        (
            "keyword_extract",
            "keyword.extract",
            "关键词抽取",
            {"keyword_mode": "lightrag", "max_keywords": 12, "language": "auto", "fallback_to_rule": False},
        ),
        ("vector_retrieve", "vector.retrieve", "向量检索", {"top_k": 10}),
        ("retrieval_merge", "retrieval.merge", "检索合并", {}),
        ("rerank", "rerank", "结果重排", {"rerank_engine": "runtime", "rerank_model": "none", "top_k": 8}),
        ("context_build", "context.build", "上下文构建", {}),
        ("llm_generate", "llm.generate", "LLM 生成", {}),
        ("end", "workflow.end", "结束", {}),
    ]
    start_x = 120
    start_y = 520
    step_x = 240
    nodes: List[Dict[str, Any]] = []
    for idx, (nid, ntype, label, cfg) in enumerate(chain):
        nodes.append(_mk_node(nid, ntype, start_x + idx * step_x, start_y, label, cfg))
    edges: List[Tuple[str, str]] = []
    for i in range(len(chain) - 1):
        edges.append((chain[i][0], chain[i + 1][0]))
    return _build_doc(
        workflow_id="default-knowledge-qa-full",
        name="问答模板（全链路）",
        description="workflow.start -> knowledge.select -> keyword.extract -> vector.retrieve -> retrieval.merge -> rerank -> context.build -> llm.generate -> workflow.end",
        nodes=nodes,
        edges=edges,
        entry_node_ids=["start"],
        input_data={"query": "请根据知识库回答这个问题"},
    )


def build_default_entity_relation_extract_validation_workflow() -> Dict[str, Any]:
    """实体关系抽取验证模板（含 start/end）。"""
    chain = [
        ("start", "workflow.start", "开始", {}),
        (
            "document_parse",
            "document.parse",
            "文档解析",
            {"source_path": "Inputs/3.pdf", "parser": "mineru", "parse_method": "auto"},
        ),
        ("content_filter", "content.filter", "内容过滤", {"drop_empty": True, "keep_page_numbers": True}),
        ("multimodal_process", "multimodal.process", "多模态预处理", {"use_vlm": False}),
        ("content_route", "content.route", "内容路由", {"keep_unrouted": True, "drop_discard_types": True}),
        _semantic_block_merge_step(),
        (
            "chunk_split",
            "chunk.split",
            "文本切片",
            _chunk_split_cfg(),
        ),
        (
            "entity_relation_extract",
            "entity_relation.extract",
            "实体关系抽取",
            {
                "model": "default",
                "entity_extract_max_gleaning": 1,
                "language": "auto",
                "include_multimodal_chunks": True,
                "max_chunks": 0,
                "use_llm_cache": False,
            },
        ),
        ("end", "workflow.end", "结束", {}),
    ]
    start_x = 100
    start_y = 680
    step_x = 220
    nodes: List[Dict[str, Any]] = []
    for idx, (nid, ntype, label, cfg) in enumerate(chain):
        nodes.append(_mk_node(nid, ntype, start_x + idx * step_x, start_y, label, cfg))
    edges: List[Tuple[str, str]] = []
    for i in range(len(chain) - 1):
        edges.append((chain[i][0], chain[i + 1][0]))
    return _build_doc(
        workflow_id="default-entity-relation-extract-validation",
        name="实体关系抽取验证模板",
        description="workflow.start -> document.parse -> content.filter -> multimodal.process -> content.route -> semantic.block.merge -> chunk.split -> entity_relation.extract -> workflow.end",
        nodes=nodes,
        edges=edges,
        entry_node_ids=["start"],
        input_data={"source_path": "Inputs/3.pdf"},
    )


def build_default_entity_relation_extract_validation_with_industrial_workflow() -> Dict[str, Any]:
    """实体关系抽取 + 工业知识增强模板（按指定顺序编排，无 industrial.validation）。"""
    chain = [
        ("start", "workflow.start", "开始", {}),
        (
            "document_parse",
            "document.parse",
            "文档解析",
            {"source_path": "Inputs/3.pdf", "parser": "mineru", "parse_method": "auto"},
        ),
        ("content_filter", "content.filter", "内容过滤", {"drop_empty": True, "keep_page_numbers": True}),
        ("multimodal_process", "multimodal.process", "多模态预处理", {"use_vlm": False}),
        ("content_route", "content.route", "内容路由", {"keep_unrouted": True, "drop_discard_types": True}),
        _semantic_block_merge_step(),
        (
            "industrial_structure",
            "industrial.structure_recognition",
            "工业结构识别",
            {
                "enabled_parsers": ["title_hierarchy", "process_flow", "table_structure"],
                "enable_validation": True,
                "enable_semantic_completion": False,
            },
        ),
        ("industrial_table", "industrial.table_parse", "工业表结构解析", {}),
        ("industrial_constraint", "industrial.constraint_extract", "工业约束抽取", {"enable_validation": True}),
        ("industrial_process", "industrial.process_extract", "工业流程抽取", {}),
        (
            "chunk_split",
            "chunk.split",
            "文本切片",
            _chunk_split_cfg(),
        ),
        (
            "embedding_index",
            "embedding.index",
            "向量索引",
            {"include_raw_item": True, "allow_without_vector": True, "batch_size": 16},
        ),
        (
            "entity_relation_extract",
            "entity_relation.extract",
            "实体关系抽取",
            {
                "model": "default",
                "entity_extract_max_gleaning": 1,
                "language": "auto",
                "include_multimodal_chunks": True,
                "max_chunks": 0,
                "use_llm_cache": False,
            },
        ),
        (
            "relation_merge",
            "relation.merge",
            "关系归并",
            {
                "merge_engine": "lightrag",
                "merge_strategy": "canonical",
                "similarity_threshold": 0.9,
                "use_llm_summary_on_merge": False,
            },
        ),
        ("industrial_graph", "industrial.graph_build", "工业图谱构建", {}),
        (
            "industrial_graph_persist",
            "industrial.graph.persist",
            "工业图谱持久化",
            {
                "graph_backend": "neo4j",
                "namespace": "industrial_default",
                "enable_native_labels": True,
                "enable_typed_relationships": True,
                "validation": True,
                "batch_size": 100,
                "dry_run": False,
            },
        ),
        ("storage_persist", "storage.persist", "存储落盘", {}),
        ("end", "workflow.end", "结束", {}),
    ]
    start_x = 100
    start_y = 700
    step_x = 230
    nodes: List[Dict[str, Any]] = []
    for idx, (nid, ntype, label, cfg) in enumerate(chain):
        nodes.append(_mk_node(nid, ntype, start_x + idx * step_x, start_y, label, cfg))

    edges: List[Tuple[str, str]] = []
    for i in range(len(chain) - 1):
        edges.append((chain[i][0], chain[i + 1][0]))
    return _build_doc(
        workflow_id="default-entity-relation-extract-validation-industrial",
        name="实体关系抽取验证模板（工业增强）",
        description=(
            "workflow.start -> document.parse -> content.filter -> multimodal.process -> content.route -> "
            "semantic.block.merge -> industrial.structure_recognition -> industrial.table_parse -> "
            "industrial.constraint_extract -> industrial.process_extract -> chunk.split -> embedding.index -> "
            "entity_relation.extract -> "
            "relation.merge -> industrial.graph_build -> industrial.graph.persist -> storage.persist -> workflow.end"
        ),
        nodes=nodes,
        edges=edges,
        entry_node_ids=["start"],
        input_data={"source_path": "Inputs/3.pdf"},
    )


def build_default_industrial_ontology_object_library_workflow() -> Dict[str, Any]:
    """
    本体对象建库默认工作流：在 industrial 图谱构建之后串联 ISR 链路（ontology / semantic plan / constraint filter / persist），
    再接工业图谱 Neo4j 与向量存储；与 ``default-entity-relation-extract-validation-industrial`` 并行模板，不改变后者。
    """
    chain_before_isr = [
        ("start", "workflow.start", "开始", {}),
        (
            "document_parse",
            "document.parse",
            "文档解析",
            {"source_path": "Inputs/3.pdf", "parser": "mineru", "parse_method": "auto"},
        ),
        ("content_filter", "content.filter", "内容过滤", {"drop_empty": True, "keep_page_numbers": True}),
        ("multimodal_process", "multimodal.process", "多模态预处理", {"use_vlm": False}),
        ("content_route", "content.route", "内容路由", {"keep_unrouted": True, "drop_discard_types": True}),
        _semantic_block_merge_step(),
        (
            "industrial_structure",
            "industrial.structure_recognition",
            "工业结构识别",
            {
                "enabled_parsers": ["title_hierarchy", "process_flow", "table_structure"],
                "enable_validation": True,
                "enable_semantic_completion": False,
            },
        ),
        ("industrial_table", "industrial.table_parse", "工业表结构解析", {}),
        ("industrial_constraint", "industrial.constraint_extract", "工业约束抽取", {"enable_validation": True}),
        ("industrial_process", "industrial.process_extract", "工业流程抽取", {}),
        (
            "chunk_split",
            "chunk.split",
            "文本切片",
            _chunk_split_cfg(),
        ),
        (
            "embedding_index",
            "embedding.index",
            "向量索引",
            {"include_raw_item": True, "allow_without_vector": True, "batch_size": 16},
        ),
        (
            "entity_relation_extract",
            "entity_relation.extract",
            "实体关系抽取",
            {
                "model": "default",
                "entity_extract_max_gleaning": 1,
                "language": "auto",
                "include_multimodal_chunks": True,
                "max_chunks": 0,
                "use_llm_cache": False,
            },
        ),
        (
            "relation_merge",
            "relation.merge",
            "关系归并",
            {
                "merge_engine": "lightrag",
                "merge_strategy": "canonical",
                "similarity_threshold": 0.9,
                "use_llm_summary_on_merge": False,
            },
        ),
        ("industrial_graph", "industrial.graph_build", "工业图谱构建", {}),
    ]
    chain_isr_tail = [
        (
            "ontology_object_define",
            "ontology.object.define",
            "工业本体对象定义",
            {
                "ontology_type": "Part",
                "object_id": "",
                "label": "默认占位零件",
                "attributes": {},
                "source_refs": [],
            },
        ),
        ("isr_constraint_extract", "constraint.extract", "语义约束抽取（ISR）", {}),
        (
            "isr_semantic_plan",
            "semantic.runtime.plan",
            "语义运行时执行计划 IR",
            {"use_dag_topo": False},
        ),
        (
            "isr_constraint_filter",
            "constraint.runtime.filter",
            "工业运行时约束过滤",
            {"explain_all": False},
        ),
        ("ontology_graph_persist", "ontology.graph.persist", "本体对象图持久化", {"dry_run": True}),
        ("semantic_relation_persist", "semantic.relation.persist", "语义关系持久化", {"dry_run": True}),
        ("constraint_relation_persist", "constraint.relation.persist", "约束关系持久化", {"dry_run": True}),
        (
            "industrial_graph_persist",
            "industrial.graph.persist",
            "工业图谱持久化",
            {
                "graph_backend": "neo4j",
                "namespace": "industrial_default",
                "enable_native_labels": True,
                "enable_typed_relationships": True,
                "validation": True,
                "batch_size": 100,
                "dry_run": False,
            },
        ),
        ("storage_persist", "storage.persist", "存储落盘", {}),
        ("end", "workflow.end", "结束", {}),
    ]
    full_chain = chain_before_isr + chain_isr_tail

    start_x = 80
    start_y = 720
    step_x = 200
    nodes: List[Dict[str, Any]] = []
    for idx, (nid, ntype, label, cfg) in enumerate(full_chain):
        nodes.append(_mk_node(nid, ntype, start_x + idx * step_x, start_y, label, cfg))

    edges: List[Tuple[str, str]] = []
    for i in range(len(full_chain) - 1):
        edges.append((full_chain[i][0], full_chain[i + 1][0]))

    desc = (
        "与实体关系抽取验证（工业增强）相同的解析与图谱前置；在 industrial.graph_build 之后串联 "
        "ontology.object.define → constraint.extract → semantic.runtime.plan → constraint.runtime.filter → "
        "ontology.graph.persist / semantic.relation.persist / constraint.relation.persist（persist 默认为 dry_run，需适配器时关闭）→ "
        "industrial.graph.persist → storage.persist"
    )
    return _build_doc(
        workflow_id="default-industrial-ontology-object-library",
        name="本体对象建库默认工作流",
        description=desc,
        nodes=nodes,
        edges=edges,
        entry_node_ids=["start"],
        input_data={"source_path": "Inputs/3.pdf"},
    )


def build_default_industrial_ontology_from_chunk_split_workflow() -> Dict[str, Any]:
    """
    与 ``default-industrial-ontology-object-library`` 后半段一致，但从 ``chunk.split`` 起执行。

    ``input_data`` 须替换为：**某次完整跑完后** ``industrial.process_extract`` 节点的 ``result.data``
    （或与之等价的字典：至少含可供 chunk.split 使用的 ``routes``/``content_list`` 及下游工业图所需的结构字段）。
    """
    chunk_onward: List[Tuple[str, str, str, Dict[str, Any]]] = [
        _semantic_block_merge_step(),
        (
            "chunk_split",
            "chunk.split",
            "文本切片",
            _chunk_split_cfg(),
        ),
        (
            "embedding_index",
            "embedding.index",
            "向量索引",
            {"include_raw_item": True, "allow_without_vector": True, "batch_size": 16},
        ),
        (
            "entity_relation_extract",
            "entity_relation.extract",
            "实体关系抽取",
            {
                "model": "default",
                "entity_extract_max_gleaning": 1,
                "language": "auto",
                "include_multimodal_chunks": True,
                "max_chunks": 0,
                "use_llm_cache": False,
            },
        ),
        (
            "relation_merge",
            "relation.merge",
            "关系归并",
            {
                "merge_engine": "lightrag",
                "merge_strategy": "canonical",
                "similarity_threshold": 0.9,
                "use_llm_summary_on_merge": False,
            },
        ),
        ("industrial_graph", "industrial.graph_build", "工业图谱构建", {}),
        (
            "ontology_object_define",
            "ontology.object.define",
            "工业本体对象定义",
            {
                "ontology_type": "Part",
                "object_id": "",
                "label": "默认占位零件",
                "attributes": {},
                "source_refs": [],
            },
        ),
        ("isr_constraint_extract", "constraint.extract", "语义约束抽取（ISR）", {}),
        (
            "isr_semantic_plan",
            "semantic.runtime.plan",
            "语义运行时执行计划 IR",
            {"use_dag_topo": False},
        ),
        (
            "isr_constraint_filter",
            "constraint.runtime.filter",
            "工业运行时约束过滤",
            {"explain_all": False},
        ),
        ("ontology_graph_persist", "ontology.graph.persist", "本体对象图持久化", {"dry_run": True}),
        ("semantic_relation_persist", "semantic.relation.persist", "语义关系持久化", {"dry_run": True}),
        ("constraint_relation_persist", "constraint.relation.persist", "约束关系持久化", {"dry_run": True}),
        (
            "industrial_graph_persist",
            "industrial.graph.persist",
            "工业图谱持久化",
            {
                "graph_backend": "neo4j",
                "namespace": "industrial_default",
                "enable_native_labels": True,
                "enable_typed_relationships": True,
                "validation": True,
                "batch_size": 100,
                "dry_run": False,
            },
        ),
        ("storage_persist", "storage.persist", "存储落盘", {}),
        ("end", "workflow.end", "结束", {}),
    ]
    full_chain: List[Tuple[str, str, str, Dict[str, Any]]] = [
        ("start", "workflow.start", "开始", {}),
        *chunk_onward,
    ]

    start_x = 80
    start_y = 720
    step_x = 200
    nodes: List[Dict[str, Any]] = []
    for idx, (nid, ntype, label, cfg) in enumerate(full_chain):
        nodes.append(_mk_node(nid, ntype, start_x + idx * step_x, start_y, label, cfg))

    edges: List[Tuple[str, str]] = []
    for i in range(len(full_chain) - 1):
        edges.append((full_chain[i][0], full_chain[i + 1][0]))

    desc = (
        "从文本切片(chunk.split)起的本体建库+ISR尾巴；跳过 document.parse〜industrial.process_extract。"
        "运行前请将 input_data 整段替换为某次完整跑完后 industrial.process_extract 节点 result.data "
        "(含 routes/content_list/composite_structure 等)。"
        "默认落盘/接口里 node_results 会缩略 routes；若需从 runs/*.json 直接拷贝，请在服务端 .env 设置 "
        "WORKFLOW_RUN_STRIP_VISUAL_HEAVY=0 后再跑全链，或使用未经过缩略导出的快照。"
    )
    return _build_doc(
        workflow_id="default-industrial-ontology-from-chunk-split",
        name="本体建库（自 chunk.split 接入）",
        description=desc,
        nodes=nodes,
        edges=edges,
        entry_node_ids=["start"],
        input_data={},
    )


def list_default_workflow_templates() -> List[Dict[str, str]]:
    return [
        {
            "template_id": "default-raganything-runnable",
            "name": "默认可运行工作流",
            "description": "start -> raganything.insert -> rag.query -> end",
        },
        {
            "template_id": "default-raganything-full-pipeline",
            "name": "完整源码阶段工作流",
            "description": "细粒度源码阶段展示链（含 start/end 包裹）",
        },
        {
            "template_id": "default-knowledge-build",
            "name": "建库模板（解析到落盘）",
            "description": "document.parse -> ... -> storage.persist",
        },
        {
            "template_id": "default-knowledge-query",
            "name": "查询已有库模板",
            "description": "knowledge.select -> vector.retrieve -> retrieval.merge -> rerank -> context.build -> llm.generate",
        },
        {
            "template_id": "default-knowledge-qa-full",
            "name": "问答模板（全链路）",
            "description": "workflow.start -> knowledge.select -> keyword.extract -> vector.retrieve -> retrieval.merge -> rerank -> context.build -> llm.generate -> workflow.end",
        },
        {
            "template_id": "default-entity-relation-extract-validation",
            "name": "实体关系抽取验证模板",
            "description": "workflow.start -> document.parse -> content.filter -> multimodal.process -> content.route -> chunk.split -> entity_relation.extract -> workflow.end",
        },
        {
            "template_id": "default-entity-relation-extract-validation-industrial",
            "name": "实体关系抽取验证模板（工业增强）",
            "description": "基于实体关系抽取验证模板，新增 6 个工业/重排节点",
        },
        {
            "template_id": "default-industrial-ontology-object-library",
            "name": "本体对象建库默认工作流",
            "description": "工业图谱构建后串联 ontology / ISR 语义计划 / 约束过滤与三类 ontology 图谱持久化，再接 Neo4j 与存储",
        },
        {
            "template_id": "default-industrial-ontology-from-chunk-split",
            "name": "本体建库（自 chunk.split 接入）",
            "description": "从 chunk.split 起跳；input_data 需粘贴 industrial.process_extract 的 data；默认 run 会缩略 routes，需断点请设 WORKFLOW_RUN_STRIP_VISUAL_HEAVY=0",
        },
    ]


def get_default_workflow_template(template_id: str) -> Dict[str, Any]:
    if template_id == "default-raganything-runnable":
        return build_default_runnable_raganything_workflow()
    if template_id == "default-raganything-full-pipeline":
        return build_default_full_pipeline_workflow()
    if template_id == "default-knowledge-build":
        return build_default_knowledge_build_workflow()
    if template_id == "default-knowledge-query":
        return build_default_knowledge_query_workflow()
    if template_id == "default-knowledge-qa-full":
        return build_default_knowledge_qa_full_workflow()
    if template_id == "default-entity-relation-extract-validation":
        return build_default_entity_relation_extract_validation_workflow()
    if template_id == "default-entity-relation-extract-validation-industrial":
        return build_default_entity_relation_extract_validation_with_industrial_workflow()
    if template_id == "default-industrial-ontology-object-library":
        return build_default_industrial_ontology_object_library_workflow()
    if template_id == "default-industrial-ontology-from-chunk-split":
        return build_default_industrial_ontology_from_chunk_split_workflow()
    raise KeyError(template_id)
