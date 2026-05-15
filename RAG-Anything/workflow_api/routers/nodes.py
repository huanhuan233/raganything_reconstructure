"""节点类型注册表视图。"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter

from ..runtime_service import get_available_nodes
from ..schemas import NodeInfoResponse, NodeMetadataModel

router = APIRouter(tags=["nodes"])
_dotenv_loaded = False


def _ensure_project_dotenv_loaded() -> None:
    global _dotenv_loaded
    if _dotenv_loaded:
        return
    _dotenv_loaded = True
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.is_file():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(dotenv_path=str(env_path), override=False)
    except Exception:
        return


def _parse_model_list(raw: str) -> list[str]:
    if not raw.strip():
        return []
    items: list[str] = []
    for chunk in raw.replace("\n", ",").replace(";", ",").split(","):
        one = chunk.strip()
        if one:
            items.append(one)
    return items


def _llm_model_candidates_from_env() -> list[str]:
    _ensure_project_dotenv_loaded()
    candidates: list[str] = []
    # 支持显式配置多个候选模型
    for key in ("LLM_MODEL_OPTIONS", "LLM_MODELS", "LLM_MODEL_LIST"):
        candidates.extend(_parse_model_list(os.getenv(key, "")))
    # 至少包含当前默认模型
    one = os.getenv("LLM_MODEL", "").strip()
    if one:
        candidates.append(one)
    # 去重并保持顺序
    out: list[str] = []
    seen: set[str] = set()
    for m in candidates:
        if m in seen:
            continue
        seen.add(m)
        out.append(m)
    return out


def _rerank_model_candidates_from_env() -> list[str]:
    _ensure_project_dotenv_loaded()
    defaults = [
        "none",
        "BAAI/bge-reranker-v2-m3",
        "Qwen/Qwen3-Reranker-4B",
        "Qwen/Qwen3-VL-Reranker-8B",
    ]
    candidates: list[str] = []
    for key in ("RERANK_MODEL_OPTIONS", "RERANK_MODELS", "RERANK_MODEL_LIST"):
        candidates.extend(_parse_model_list(os.getenv(key, "")))
    one = os.getenv("RERANK_MODEL", "").strip()
    if one:
        candidates.append(one)
    mm = os.getenv("MULTIMODAL_RERANK_MODEL", "").strip()
    if mm:
        candidates.append(mm)
    out: list[str] = []
    seen: set[str] = set()
    for m in [*defaults, *candidates]:
        if not m or m in seen:
            continue
        seen.add(m)
        out.append(m)
    return out


def _vision_model_candidates_from_env() -> list[str]:
    _ensure_project_dotenv_loaded()
    candidates: list[str] = []
    for key in ("VISION_MODEL_OPTIONS", "VISION_MODELS", "VISION_MODEL_LIST"):
        candidates.extend(_parse_model_list(os.getenv(key, "")))
    one = os.getenv("VISION_MODEL", "").strip()
    if one:
        candidates.append(one)
    out: list[str] = []
    seen: set[str] = set()
    for m in candidates:
        if not m or m in seen:
            continue
        seen.add(m)
        out.append(m)
    return out


def _patch_llm_generate_model_field(nodes: list[NodeMetadataModel]) -> None:
    models = _llm_model_candidates_from_env()
    if not models:
        return
    for n in nodes:
        if n.node_type != "llm.generate":
            continue
        for f in n.config_fields:
            if f.name != "model":
                continue
            f.type = "select"
            f.options = models
            if not f.default:
                f.default = models[0]
            if not f.placeholder:
                f.placeholder = "选择模型"
            desc = (f.description or "").strip()
            hint = "候选项来自 .env（LLM_MODEL_OPTIONS/LLM_MODELS/LLM_MODEL_LIST，回退 LLM_MODEL）"
            f.description = f"{desc}；{hint}" if desc else hint
            break


def _patch_keyword_extract_model_field(nodes: list[NodeMetadataModel]) -> None:
    models = _llm_model_candidates_from_env()
    options = ["default", *models] if models else ["default"]
    for n in nodes:
        if n.node_type != "keyword.extract":
            continue
        for f in n.config_fields:
            if f.name != "model":
                continue
            f.type = "select"
            f.options = options
            if not f.default:
                f.default = "default"
            if not f.placeholder:
                f.placeholder = "选择模型"
            desc = (f.description or "").strip()
            hint = "候选项来自 .env（LLM_MODEL_OPTIONS/LLM_MODELS/LLM_MODEL_LIST，回退 LLM_MODEL）"
            f.description = f"{desc}；{hint}" if desc else hint
            break


def _patch_entity_relation_extract_model_field(nodes: list[NodeMetadataModel]) -> None:
    models = _llm_model_candidates_from_env()
    options = ["default", *models] if models else ["default"]
    for n in nodes:
        if n.node_type != "entity_relation.extract":
            continue
        for f in n.config_fields:
            if f.name != "model":
                continue
            f.type = "select"
            f.options = options
            if not f.default:
                f.default = "default"
            if not f.placeholder:
                f.placeholder = "选择模型"
            desc = (f.description or "").strip()
            hint = "候选项来自 .env（LLM_MODEL_OPTIONS/LLM_MODELS/LLM_MODEL_LIST，回退 LLM_MODEL）"
            f.description = f"{desc}；{hint}" if desc else hint
            break


def _patch_merge_model_fields(nodes: list[NodeMetadataModel]) -> None:
    models = _llm_model_candidates_from_env()
    options = ["default", *models] if models else ["default"]
    for n in nodes:
        if n.node_type not in {"entity.merge", "relation.merge"}:
            continue
        for f in n.config_fields:
            if f.name != "model":
                continue
            f.type = "select"
            f.options = options
            if not f.default:
                f.default = "default"
            if not f.placeholder:
                f.placeholder = "选择模型"
            desc = (f.description or "").strip()
            hint = "候选项来自 .env（LLM_MODEL_OPTIONS/LLM_MODELS/LLM_MODEL_LIST，回退 LLM_MODEL）"
            f.description = f"{desc}；{hint}" if desc else hint
            break


def _patch_rerank_fields(nodes: list[NodeMetadataModel]) -> None:
    options = _rerank_model_candidates_from_env()
    for n in nodes:
        if n.node_type != "rerank":
            continue
        for f in n.config_fields:
            if f.name == "rerank_engine":
                f.type = "select"
                f.options = ["runtime", "lightrag"]
                if not f.default:
                    f.default = "runtime"
                f.description = "runtime=独立重排；lightrag=复用 LightRAG retrieval ordering。"
            elif f.name == "rerank_model":
                f.type = "select"
                f.options = options
                if not f.default:
                    f.default = "none"
                if not f.placeholder:
                    f.placeholder = "选择重排模型"
                desc = (f.description or "").strip()
                hint = (
                    "候选项来自 .env（RERANK_MODEL_OPTIONS/RERANK_MODELS/RERANK_MODEL_LIST，"
                    "回退 RERANK_MODEL + MULTIMODAL_RERANK_MODEL）"
                )
                f.description = f"{desc}；{hint}" if desc else hint
        break


def _patch_multimodal_vlm_model_field(nodes: list[NodeMetadataModel]) -> None:
    models = _vision_model_candidates_from_env()
    for n in nodes:
        if n.node_type != "multimodal.process":
            continue
        for f in n.config_fields:
            if f.name == "vlm_provider":
                # provider 改为环境自动决策，不再对外配置。
                f.advanced = True
            if f.name != "vlm_model":
                continue
            f.type = "select"
            f.options = models
            if not f.default and models:
                f.default = models[0]
            if not f.placeholder:
                f.placeholder = "选择 VLM 模型"
            desc = (f.description or "").strip()
            hint = "候选项来自 .env（VISION_MODEL_OPTIONS/VISION_MODELS/VISION_MODEL_LIST，回退 VISION_MODEL）"
            f.description = f"{desc}；{hint}" if desc else hint
            break
        break


def _patch_knowledge_select_fields(nodes: list[NodeMetadataModel]) -> None:
    vector_backends = ["local_jsonl", "milvus"]
    graph_backends = ["none", "neo4j", "networkx"]
    for n in nodes:
        if n.node_type != "knowledge.select":
            continue
        for f in n.config_fields:
            if f.name == "vector_backend":
                f.type = "select"
                f.options = vector_backends
            elif f.name == "graph_backend":
                f.type = "select"
                f.options = graph_backends
            elif f.name in ("collection", "text_collection", "table_collection", "vision_collection"):
                f.type = "string"
                if not f.placeholder:
                    f.placeholder = "手工填写（需要时可在面板点击资源刷新）"
            elif f.name == "workspace":
                f.type = "string"
                if not f.placeholder:
                    f.placeholder = "手工填写（Neo4j workspace/partition）"


def _patch_graph_persist_workspace_field(nodes: list[NodeMetadataModel]) -> None:
    """graph.persist.workspace 保持轻量返回，避免 /api/nodes 被 discover 扫描阻塞。"""
    for n in nodes:
        if n.node_type != "graph.persist":
            continue
        for f in n.config_fields:
            if f.name != "workspace":
                continue
            f.type = "string"
            if not f.placeholder:
                f.placeholder = "手工填写 graph partition/workspace"
            desc = (f.description or "").strip()
            hint = "如需自动发现，请在对应配置面板手动点击“刷新图分区”"
            f.description = f"{desc}；{hint}" if desc else hint
            break


@router.get("/nodes", response_model=NodeInfoResponse)
def list_node_types() -> NodeInfoResponse:
    """列出 ``backend_runtime`` 默认 ``NodeRegistry`` 中的节点元数据（含表单 schema）。"""
    raw = get_available_nodes()
    nodes = [NodeMetadataModel.model_validate(x) for x in raw]
    _patch_llm_generate_model_field(nodes)
    _patch_keyword_extract_model_field(nodes)
    _patch_entity_relation_extract_model_field(nodes)
    _patch_merge_model_fields(nodes)
    _patch_rerank_fields(nodes)
    _patch_multimodal_vlm_model_field(nodes)
    _patch_knowledge_select_fields(nodes)
    _patch_graph_persist_workspace_field(nodes)
    return NodeInfoResponse(
        nodes=nodes,
        node_types=[n.node_type for n in nodes],
    )
