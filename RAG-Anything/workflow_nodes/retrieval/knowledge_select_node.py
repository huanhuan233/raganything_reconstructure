"""选择已有知识库/索引上下文节点。"""

from __future__ import annotations

from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult


def _as_dict(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _clean_str(v: Any) -> str:
    return str(v or "").strip()


def _clean_map_str(v: Any) -> dict[str, str]:
    if not isinstance(v, dict):
        return {}
    out: dict[str, str] = {}
    for k, one in v.items():
        kk = _clean_str(k)
        vv = _clean_str(one)
        if kk and vv:
            out[kk] = vv
    return out


def _build_display_id(
    *,
    knowledge_id: str,
    vector_backend: str,
    graph_backend: str,
    collection_mode: str,
    collection: str,
    pipeline_collections: dict[str, str],
    workspace: str,
) -> str:
    if knowledge_id:
        return knowledge_id
    if collection_mode == "unified" and collection:
        return f"{vector_backend}:{collection}"
    if pipeline_collections:
        c = next((x for x in pipeline_collections.values() if x), "")
        if c:
            if graph_backend != "none" and workspace:
                return f"{vector_backend}:{c}|{graph_backend}:{workspace}"
            return f"{vector_backend}:{c}"
    if workspace and graph_backend != "none":
        return f"{graph_backend}:{workspace}"
    return f"{vector_backend}:{graph_backend}"


class KnowledgeSelectNode(BaseNode):
    """
    仅输出检索配置上下文，不执行解析/embedding/存储/查询。

    约定输出 ``selected_knowledge``，供后续 ``vector.retrieve`` 等节点优先使用。
    """

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="",
            display_name="选择知识库",
            category="knowledge",
            description="选择已有知识库、向量库 collection、图谱 workspace 与本地索引路径，供后续检索节点使用。",
            implementation_status="real",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(
                    name="knowledge_id",
                    label="知识库标识（可选）",
                    type="string",
                    required=False,
                    placeholder="可选，例如 kb_project_a；为空时自动根据 collection/workspace 生成",
                ),
                NodeConfigField(
                    name="collection_mode",
                    label="Collection模式",
                    type="select",
                    required=False,
                    default="unified",
                    options=["unified", "by_pipeline"],
                ),
                NodeConfigField(
                    name="vector_backend",
                    label="向量后端",
                    type="select",
                    required=False,
                    default="local_jsonl",
                    options=["local_jsonl", "milvus", "qdrant", "pgvector"],
                ),
                NodeConfigField(
                    name="graph_backend",
                    label="图后端",
                    type="select",
                    required=False,
                    default="none",
                    options=["none", "neo4j", "networkx"],
                ),
                NodeConfigField(
                    name="workspace",
                    label="图谱 workspace",
                    type="string",
                    required=False,
                    placeholder="例如 workflow_runtime",
                ),
                NodeConfigField(
                    name="collection",
                    label="统一 collection",
                    type="string",
                    required=False,
                ),
                NodeConfigField(
                    name="pipeline_collections",
                    label="按 pipeline 的 collection 映射",
                    type="json",
                    required=False,
                    default={},
                ),
                NodeConfigField(
                    name="local_jsonl_paths",
                    label="本地 JSONL 路径映射",
                    type="json",
                    required=False,
                    default={},
                    placeholder='{"text_pipeline":"./runtime_storage/text.jsonl"}',
                ),
                NodeConfigField(
                    name="embedding_model",
                    label="Embedding 模型",
                    type="string",
                    required=False,
                ),
            ],
            input_schema={"type": "object", "description": "query + optional knowledge_config"},
            output_schema={"type": "object", "description": "附加 selected_knowledge"},
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        payload = dict(input_data) if isinstance(input_data, dict) else {}
        cfg = dict(self.config or {})
        in_kcfg = _as_dict(payload.get("knowledge_config"))

        def pick(name: str, default: Any = "") -> Any:
            if name in in_kcfg and in_kcfg.get(name) not in (None, ""):
                return in_kcfg.get(name)
            return cfg.get(name, default)

        knowledge_id = str(pick("knowledge_id", "") or "").strip()
        collection_mode = _clean_str(pick("collection_mode", "unified")).lower() or "unified"
        if collection_mode not in ("unified", "by_pipeline"):
            collection_mode = "unified"
        vector_backend = str(pick("vector_backend", "local_jsonl") or "local_jsonl").strip().lower()
        graph_backend = str(pick("graph_backend", "none") or "none").strip().lower()
        workspace = str(pick("workspace", "") or "").strip()
        collection = _clean_str(pick("collection", ""))
        pipeline_collections = _clean_map_str(pick("pipeline_collections", {}))
        text_collection = str(pick("text_collection", "") or "").strip()
        table_collection = str(pick("table_collection", "") or "").strip()
        vision_collection = str(pick("vision_collection", "") or "").strip()
        embedding_model = str(pick("embedding_model", "") or "").strip()
        local_jsonl_paths = _as_dict(pick("local_jsonl_paths", {}))
        metadata = _as_dict(pick("metadata", {}))

        # 兼容旧配置：若 by_pipeline 未传新字段，则回填 legacy 三字段。
        if collection_mode == "by_pipeline" and not pipeline_collections:
            if text_collection:
                pipeline_collections["text_pipeline"] = text_collection
            if table_collection:
                pipeline_collections["table_pipeline"] = table_collection
            if vision_collection:
                pipeline_collections["vision_pipeline"] = vision_collection
        # 兼容旧配置：若 unified 未传 collection，尝试使用 legacy text_collection。
        if collection_mode == "unified" and not collection:
            collection = text_collection or table_collection or vision_collection

        display_id = _build_display_id(
            knowledge_id=knowledge_id,
            vector_backend=vector_backend or "local_jsonl",
            graph_backend=graph_backend or "none",
            collection_mode=collection_mode,
            collection=collection,
            pipeline_collections=pipeline_collections,
            workspace=workspace,
        )
        selected_knowledge: dict[str, Any] = {
            "knowledge_id": knowledge_id,
            "display_id": display_id,
            "name": str(pick("name", display_id) or display_id),
            "vector_backend": vector_backend or "local_jsonl",
            "collection_mode": collection_mode,
            "collection": collection,
            "pipeline_collections": pipeline_collections,
            "vector_collections": {
                "text_pipeline": text_collection,
                "table_pipeline": table_collection,
                "vision_pipeline": vision_collection,
            },
            "graph_backend": graph_backend or "none",
            "graph_workspace": workspace,
            "local_jsonl_paths": local_jsonl_paths,
            "embedding_model": embedding_model,
            "metadata": metadata,
        }

        out = dict(payload)
        out["selected_knowledge"] = selected_knowledge
        context.log(
            f"[KnowledgeSelectNode] knowledge_id={knowledge_id!r} display_id={display_id!r} "
            f"vector_backend={selected_knowledge['vector_backend']!r} collection_mode={collection_mode!r}"
        )
        return NodeResult(
            success=True,
            data=out,
            metadata={"node": "knowledge.select"},
        )
