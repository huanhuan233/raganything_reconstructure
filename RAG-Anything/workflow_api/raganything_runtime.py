"""
为 ``POST /api/workflows/run`` 惰性注入 ``RAGAnythingEngineAdapter``。

优先读取 ``RAG-Anything/.env``（与 ``raganything`` 包一致），使用其中的 LLM / Embedding /
存储等变量；未配置密钥时回退占位实现并打日志。

**Embedding 维度**：若 ``EMBEDDING_DIM`` 未设置或为 ``auto``，则对 ``EMBEDDING_MODEL``
发起一次 **原始 OpenAI 兼容 embeddings 调用**（不经 LightRAG 内置 ``openai_embed`` 装饰器），
按返回向量长度配置 ``EmbeddingFunc``。LightRAG 自带的 ``openai_embed`` 被写死
``embedding_dim=1536`` 校验，会导致 Qwen 4096 等在探测阶段就失败。
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from .schemas import WorkflowRunRequest

logger = logging.getLogger(__name__)

_lock = asyncio.Lock()
_engine: Optional[Any] = None
_shared_embedding_func: Optional[Any] = None
_shared_llm_model_func: Optional[Any] = None
_shared_lightrag_keyword_adapter: Optional[Any] = None
_shared_lightrag_graph_retrieve_adapter: Optional[Any] = None
_shared_lightrag_chunk_adapter: Optional[Any] = None
_shared_lightrag_entity_adapter: Optional[Any] = None
_shared_lightrag_entity_merge_adapter: Optional[Any] = None
_shared_lightrag_relation_merge_adapter: Optional[Any] = None
_shared_lightrag_graph_merge_adapter: Optional[Any] = None
_shared_lightrag_graph_persist_adapter: Optional[Any] = None
_shared_runtime_rerank_adapter: Optional[Any] = None
_shared_industrial_knowledge_adapter: Optional[Any] = None
_shared_industrial_graph_persist_adapter: Optional[Any] = None
_dotenv_loaded = False


def _project_root() -> Path:
    """``backend_api`` 的上一级为 RAG-Anything 仓库根目录。"""
    return Path(__file__).resolve().parents[1]


def _ensure_project_root_importable() -> None:
    """确保仓库根目录位于 ``sys.path`` 前列，避免同名第三方模块覆盖本地 adapters 包。"""
    root = str(_project_root())
    if root in sys.path:
        # 将项目根路径前置，优先解析本地包
        sys.path.remove(root)
    sys.path.insert(0, root)


def _load_lightrag_module() -> Any:
    """
    稳健加载 ``adapters.lightrag``：
    - 先确保项目根路径可导入
    - 若已缓存同名非包模块 ``adapters``（无 ``__path__``），先移除再导入
    """
    _ensure_project_root_importable()
    cached = sys.modules.get("adapters")
    if cached is not None and not hasattr(cached, "__path__"):
        logger.warning("检测到冲突模块 adapters（非包），已移除并重试导入本地 adapters 包")
        sys.modules.pop("adapters", None)
    return importlib.import_module("adapters.lightrag")


def _import_lightrag_symbols(*names: str) -> tuple[Any, ...]:
    mod = _load_lightrag_module()
    return tuple(getattr(mod, n) for n in names)


def _ensure_dotenv_loaded() -> None:
    """
    加载根目录 ``.env``。

    使用 ``override=True``，使仓库内 ``EMBEDDING_DIM`` / ``EMBEDDING_MODEL`` 等与 SiliconFlow
    配置一致；避免系统或 Conda 里残留的 ``EMBEDDING_DIM=1536`` 覆盖 ``.env`` 中的 4096，
    导致 ``Embedding dimension mismatch``。
    """
    global _dotenv_loaded
    if _dotenv_loaded:
        return
    _dotenv_loaded = True
    env_path = _project_root() / ".env"
    if not env_path.is_file():
        logger.warning("未找到 %s，将仅使用进程环境变量", env_path)
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(dotenv_path=str(env_path), override=True)
        logger.info("已加载环境配置（覆盖同名进程变量）: %s", env_path)
    except ImportError:
        logger.warning("未安装 python-dotenv，跳过 .env 加载")


def _truthy_env(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


async def _placeholder_llm_model_func(prompt: str, **kwargs: Any) -> str:
    return '{"entities":[],"relationships":[]}'


async def _placeholder_embedding_texts(texts: list[str]) -> list[list[float]]:
    dim = 4096
    return [[(i + k) % 13 * 0.01 for k in range(dim)] for i, _ in enumerate(texts)]


def _build_placeholder_embedding_func() -> Any:
    from lightrag.utils import EmbeddingFunc

    return EmbeddingFunc(
        embedding_dim=4096,
        func=_placeholder_embedding_texts,
        max_token_size=8192,
        model_name="backend-api-raganything-emb-placeholder",
    )


def _normalize_openai_base_url(base_url: str) -> str:
    u = base_url.rstrip("/")
    if not u.endswith("/v1"):
        u = f"{u}/v1"
    return u


async def _raw_openai_compatible_embeddings(
    texts: list[str],
    *,
    model: str,
    base_url: str,
    api_key: str,
) -> list[list[float]]:
    """
    直接调用 OpenAI 兼容 ``POST .../embeddings``，返回二维 float 列表。

    不使用 ``lightrag.llm.openai.openai_embed``：该函数被
    ``@wrap_embedding_func_with_attrs(embedding_dim=1536)`` 包装，会在返回 4096 维
    （如 Qwen3-Embedding）时在校验阶段抛错，导致无法探测真实维度，也无法正常入库。
    """
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        base_url=_normalize_openai_base_url(base_url),
        api_key=api_key,
    )
    resp = await client.embeddings.create(model=model, input=texts)
    return [list(item.embedding) for item in resp.data]


async def _probe_or_read_embedding_dim() -> int:
    """
    决定 ``EmbeddingFunc.embedding_dim``。

    - ``EMBEDDING_DIM`` 为纯数字：直接使用（须与模型/Milvus 集合一致）。
    - 未设置、空、或 ``auto``：调用当前 embedding API 探测向量长度（如 Qwen3 → 4096）。
    - 探测失败：**不再**静默回退 1536（易与 Qwen 等 4096 维 API 冲突），改为抛错。
    """
    _ensure_dotenv_loaded()
    raw = (os.getenv("EMBEDDING_DIM") or "").strip().lower()
    emb_model = os.getenv("EMBEDDING_MODEL") or "text-embedding-3-small"

    if raw and raw != "auto" and raw.isdigit():
        d = int(raw)
        logger.info("EMBEDDING_DIM 使用 .env 显式值: %s", d)
        em = emb_model.lower()
        if d == 1536 and "qwen" in em and "embed" in em:
            logger.warning(
                "当前 EMBEDDING_DIM=1536，但模型名含 Qwen Embedding，常见输出为 4096 维；"
                "若仍报 dimension mismatch，请改为 EMBEDDING_DIM=4096 或删除该项以使用 auto 探测"
            )
        return d

    emb_key = (os.getenv("EMBEDDING_BINDING_API_KEY") or "").strip() or (
        os.getenv("LLM_BINDING_API_KEY") or ""
    ).strip()
    if not emb_key:
        logger.info("无 Embedding API 密钥，维度使用占位 4096")
        return 4096

    llm_host = (os.getenv("LLM_BINDING_HOST") or "https://api.openai.com/v1").rstrip("/")
    emb_host = (os.getenv("EMBEDDING_BINDING_HOST") or llm_host).rstrip("/")

    try:
        vecs = await _raw_openai_compatible_embeddings(
            ["__embedding_dim_probe__"],
            model=emb_model,
            base_url=emb_host,
            api_key=emb_key.strip(),
        )
        d = len(vecs[0])
        logger.info(
            "EMBEDDING_DIM 已由 API 自动探测: %s（模型 %s）",
            d,
            emb_model,
        )
        return d
    except Exception as exc:  # noqa: BLE001
        msg = (
            f"无法探测 Embedding 维度（{exc}）。请在 .env 设置与模型一致的 EMBEDDING_DIM "
            f"（如 Qwen3-Embedding-8B 常为 4096），或检查网络与 EMBEDDING_* 密钥。"
        )
        logger.error(msg)
        raise RuntimeError(msg) from exc


def _build_llm_embedding_from_env(*, embedding_dim: int) -> tuple[Any, Any] | None:
    """若 LLM / Embedding 环境变量齐全则返回 (llm_model_func, embedding_func)，否则 None。"""
    _ensure_dotenv_loaded()
    llm_key = (os.getenv("LLM_BINDING_API_KEY") or "").strip()
    emb_key = (os.getenv("EMBEDDING_BINDING_API_KEY") or "").strip() or llm_key
    if not llm_key:
        return None

    from lightrag.llm.openai import openai_complete_if_cache
    from lightrag.utils import EmbeddingFunc

    llm_host = (os.getenv("LLM_BINDING_HOST") or "https://api.openai.com/v1").rstrip("/")
    llm_model = os.getenv("LLM_MODEL") or "gpt-4o-mini"

    emb_host = (os.getenv("EMBEDDING_BINDING_HOST") or llm_host).rstrip("/")
    emb_model = os.getenv("EMBEDDING_MODEL") or "text-embedding-3-small"
    emb_max_tokens = int(os.getenv("EMBEDDING_MAX_TOKEN_SIZE") or "8192")
    logger.info(
        "Embedding 配置: model=%s embedding_dim=%s",
        emb_model,
        embedding_dim,
    )

    async def llm_model_func(
        prompt: str,
        system_prompt: Optional[str] = None,
        history_messages: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> str:
        req_model = kwargs.pop("model", None)
        model_name = str(req_model).strip() if req_model is not None else ""
        if not model_name:
            model_name = llm_model
        return await openai_complete_if_cache(
            model=model_name,
            prompt=prompt,
            system_prompt=system_prompt,
            history_messages=history_messages or [],
            base_url=llm_host,
            api_key=llm_key,
            **kwargs,
        )

    async def embedding_texts(texts: list[str]) -> np.ndarray:
        rows = await _raw_openai_compatible_embeddings(
            texts,
            model=emb_model,
            base_url=emb_host,
            api_key=emb_key,
        )
        return np.asarray(rows, dtype=np.float32)

    embedding_func = EmbeddingFunc(
        embedding_dim=embedding_dim,
        func=embedding_texts,
        max_token_size=emb_max_tokens,
        model_name=emb_model,
    )
    return llm_model_func, embedding_func


def _build_llm_model_func_from_env() -> Any | None:
    """仅构建 llm_model_func（用于 llm.generate 等不依赖 embedding 的节点）。"""
    _ensure_dotenv_loaded()
    llm_key = (os.getenv("LLM_BINDING_API_KEY") or "").strip()
    if not llm_key:
        return None

    from lightrag.llm.openai import openai_complete_if_cache

    llm_host = (os.getenv("LLM_BINDING_HOST") or "https://api.openai.com/v1").rstrip("/")
    llm_model = os.getenv("LLM_MODEL") or "gpt-4o-mini"

    async def llm_model_func(
        prompt: str,
        system_prompt: Optional[str] = None,
        history_messages: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> str:
        req_model = kwargs.pop("model", None)
        model_name = str(req_model).strip() if req_model is not None else ""
        if not model_name:
            model_name = llm_model
        return await openai_complete_if_cache(
            model=model_name,
            prompt=prompt,
            system_prompt=system_prompt,
            history_messages=history_messages or [],
            base_url=llm_host,
            api_key=llm_key,
            **kwargs,
        )

    return llm_model_func


def _raganything_working_dir() -> str:
    _ensure_dotenv_loaded()
    for key in ("RAGANYTHING_WORKING_DIR", "OUTPUT_DIR"):
        v = os.getenv(key, "").strip()
        if v:
            return os.path.expanduser(v)
    return str(Path.cwd() / "rag_storage")


def _lightrag_kwargs_from_env() -> Dict[str, Any]:
    """
    仅透传 ``workspace``（若存在），不强制 vector/graph 后端。

    ``RAGAnything`` 初始化时会从未在 ``lightrag_kwargs`` 中出现的键位读取
    ``VECTOR_STORAGE`` / ``GRAPH_STORAGE`` 等环境变量。
    """
    _ensure_dotenv_loaded()
    kw: Dict[str, Any] = {}
    ws = (
        os.getenv("RAGANYTHING_LIGHTRAG_WORKSPACE")
        or os.getenv("WORKSPACE")
        or ""
    ).strip()
    if ws:
        kw["workspace"] = ws
    return kw


def _create_raganything_engine(*, embedding_dim: int) -> Any:
    from adapters.raganything import RAGAnythingAdapterConfig, RAGAnythingEngineAdapter

    _ensure_dotenv_loaded()

    working = _raganything_working_dir()
    Path(working).mkdir(parents=True, exist_ok=True)

    cfg = RAGAnythingAdapterConfig(
        working_dir=working,
        parser=os.getenv("RAGANYTHING_PARSER") or os.getenv("PARSER", "mineru"),
        parse_method=os.getenv("RAGANYTHING_PARSE_METHOD")
        or os.getenv("PARSE_METHOD", "auto"),
        lazy_parser_validation=True,
        enable_image_processing=_truthy_env("ENABLE_IMAGE_PROCESSING", "true"),
        enable_table_processing=_truthy_env("ENABLE_TABLE_PROCESSING", "true"),
        enable_equation_processing=_truthy_env("ENABLE_EQUATION_PROCESSING", "true"),
    )

    pair = _build_llm_embedding_from_env(embedding_dim=embedding_dim)
    if pair is not None:
        llm_model_func, embedding_func = pair
        logger.info(
            "使用 .env / 环境中的 LLM 与 Embedding（模型: %s / %s）",
            os.getenv("LLM_MODEL", ""),
            os.getenv("EMBEDDING_MODEL", ""),
        )
    else:
        llm_model_func = _placeholder_llm_model_func
        embedding_func = _build_placeholder_embedding_func()
        logger.warning(
            "未检测到 LLM_BINDING_API_KEY，RAGAnything 使用占位 LLM/Embedding，"
            "真实 PDF 入库与查询可能失败；请在 .env 中配置 SiliconFlow/OpenAI 等密钥。"
        )

    return RAGAnythingEngineAdapter.from_config(
        cfg,
        llm_model_func=llm_model_func,
        embedding_func=embedding_func,
        lightrag_kwargs=_lightrag_kwargs_from_env(),
    )


def workflow_needs_raganything(request: WorkflowRunRequest) -> bool:
    """判断当前请求是否可能调用 ``RAGAnythingEngineAdapter``。"""
    for n in request.nodes:
        if n.type == "raganything.insert":
            cfg = dict(n.config or {})
            if cfg.get("source_path") or cfg.get("file_path"):
                return True
        if n.type == "rag.query":
            cfg = dict(n.config or {})
            if str(cfg.get("engine", "")).lower() == "raganything":
                return True
    return False


def workflow_needs_embedding_index(request: WorkflowRunRequest) -> bool:
    """判断当前 DAG 是否包含 embedding.index。"""
    for n in request.nodes:
        if n.type == "embedding.index":
            return True
    return False


def workflow_needs_vector_retrieve(request: WorkflowRunRequest) -> bool:
    """判断当前 DAG 是否包含 vector.retrieve（用于按 query 自动向量化）。"""
    for n in request.nodes:
        if n.type == "vector.retrieve":
            return True
    return False


def workflow_needs_llm_generate(request: WorkflowRunRequest) -> bool:
    """判断当前 DAG 是否包含 llm.generate。"""
    for n in request.nodes:
        if n.type == "llm.generate":
            return True
    return False


def workflow_needs_keyword_extract(request: WorkflowRunRequest) -> bool:
    """判断当前 DAG 是否包含 keyword.extract。"""
    for n in request.nodes:
        if n.type == "keyword.extract":
            return True
    return False


def workflow_needs_graph_retrieve(request: WorkflowRunRequest) -> bool:
    """判断当前 DAG 是否包含 graph.retrieve。"""
    for n in request.nodes:
        if n.type == "graph.retrieve":
            return True
    return False


def workflow_needs_chunk_split(request: WorkflowRunRequest) -> bool:
    """判断当前 DAG 是否包含 chunk.split。"""
    for n in request.nodes:
        if n.type == "chunk.split":
            return True
    return False


def workflow_needs_entity_relation_extract(request: WorkflowRunRequest) -> bool:
    """判断当前 DAG 是否包含 entity_relation.extract。"""
    for n in request.nodes:
        if n.type == "entity_relation.extract":
            return True
    return False


def workflow_needs_entity_merge(request: WorkflowRunRequest) -> bool:
    """判断当前 DAG 是否包含 entity.merge。"""
    for n in request.nodes:
        if n.type == "entity.merge":
            return True
    return False


def workflow_needs_relation_merge(request: WorkflowRunRequest) -> bool:
    """判断当前 DAG 是否包含 relation.merge。"""
    for n in request.nodes:
        if n.type == "relation.merge":
            return True
    return False


def workflow_needs_graph_merge(request: WorkflowRunRequest) -> bool:
    """判断当前 DAG 是否包含 graph.merge。"""
    for n in request.nodes:
        if n.type == "graph.merge":
            return True
    return False


def workflow_needs_graph_persist(request: WorkflowRunRequest) -> bool:
    """判断当前 DAG 是否包含 graph.persist。"""
    for n in request.nodes:
        if n.type == "graph.persist":
            return True
    return False


def workflow_needs_industrial_graph_persist(request: WorkflowRunRequest) -> bool:
    """判断当前 DAG 是否包含 industrial.graph.persist。"""
    for n in request.nodes:
        if n.type == "industrial.graph.persist":
            return True
    return False


def workflow_needs_rerank(request: WorkflowRunRequest) -> bool:
    """判断当前 DAG 是否包含 rerank。"""
    for n in request.nodes:
        if n.type == "rerank":
            return True
    return False


def workflow_needs_industrial(request: WorkflowRunRequest) -> bool:
    """判断当前 DAG 是否包含工业知识节点。"""
    for n in request.nodes:
        if str(n.type).startswith("industrial."):
            return True
    return False


async def get_shared_raganything_engine() -> Optional[Any]:
    """单例：首次成功 ``initialize`` 后复用。"""
    global _engine
    async with _lock:
        if _engine is not None:
            return _engine
        try:
            _ensure_dotenv_loaded()
            has_llm = bool((os.getenv("LLM_BINDING_API_KEY") or "").strip())
            emb_dim = await _probe_or_read_embedding_dim() if has_llm else 384
            eng = _create_raganything_engine(embedding_dim=emb_dim)
            await eng.initialize()
            _engine = eng
            logger.info(
                "RAGAnythingEngineAdapter 已就绪，working_dir=%s workspace=%s",
                _raganything_working_dir(),
                os.getenv("WORKSPACE", ""),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "RAGAnythingEngineAdapter 初始化失败（真实 PDF/查询将不可用）：%s",
                exc,
            )
            return None
        return _engine


async def get_shared_embedding_func() -> Optional[Any]:
    """
    为 Runtime 节点（如 embedding.index）提供可复用 embedding_func。

    不依赖 raganything.insert/rag.query，独立按 .env 构建。
    """
    global _shared_embedding_func
    async with _lock:
        if _shared_embedding_func is not None:
            return _shared_embedding_func
        _ensure_dotenv_loaded()
        try:
            has_llm = bool((os.getenv("LLM_BINDING_API_KEY") or "").strip())
            has_emb = bool(
                (os.getenv("EMBEDDING_BINDING_API_KEY") or "").strip()
                or (os.getenv("LLM_BINDING_API_KEY") or "").strip()
            )
            if not (has_llm or has_emb):
                logger.info("未检测到 embedding 相关 API 密钥，跳过 embedding_func 注入")
                return None
            emb_dim = await _probe_or_read_embedding_dim()
            pair = _build_llm_embedding_from_env(embedding_dim=emb_dim)
            if pair is None:
                logger.info("无法从环境构建 embedding_func，跳过注入")
                return None
            _llm_model_func, embedding_func = pair
            _shared_embedding_func = embedding_func
            logger.info(
                "已构建共享 embedding_func（model=%s dim=%s）",
                os.getenv("EMBEDDING_MODEL", ""),
                emb_dim,
            )
            return _shared_embedding_func
        except Exception as exc:  # noqa: BLE001
            logger.warning("构建共享 embedding_func 失败：%s", exc)
            return None


async def get_shared_llm_model_func() -> Optional[Any]:
    """为 llm.generate 注入可复用 llm_model_func。"""
    global _shared_llm_model_func
    async with _lock:
        if _shared_llm_model_func is not None:
            return _shared_llm_model_func
        _ensure_dotenv_loaded()
        try:
            fn = _build_llm_model_func_from_env()
            if fn is None:
                logger.info("未检测到 LLM_BINDING_API_KEY，跳过 llm_model_func 注入")
                return None
            _shared_llm_model_func = fn
            logger.info("已构建共享 llm_model_func（model=%s）", os.getenv("LLM_MODEL", ""))
            return _shared_llm_model_func
        except Exception as exc:  # noqa: BLE001
            logger.warning("构建共享 llm_model_func 失败：%s", exc)
            return None


async def get_shared_lightrag_keyword_adapter() -> Optional[Any]:
    """为 keyword.extract(lightrag) 注入适配器。"""
    global _shared_lightrag_keyword_adapter
    async with _lock:
        if _shared_lightrag_keyword_adapter is not None:
            return _shared_lightrag_keyword_adapter
        _ensure_dotenv_loaded()
        try:
            llm_fn = _build_llm_model_func_from_env()
            if llm_fn is None:
                logger.info("未检测到 LLM_BINDING_API_KEY，跳过 lightrag keyword adapter 注入")
                return None
            KeywordAdapter, LightRAGAdapterConfig, LightRAGEngineAdapter = _import_lightrag_symbols(
                "KeywordAdapter",
                "LightRAGAdapterConfig",
                "LightRAGEngineAdapter",
            )

            cfg = LightRAGAdapterConfig(
                working_dir=os.path.join(_raganything_working_dir(), "lightrag_keyword"),
                workspace=(os.getenv("WORKSPACE") or "").strip(),
                embedding_func=_build_placeholder_embedding_func(),
                llm_model_func=llm_fn,
            )
            engine = LightRAGEngineAdapter(config=cfg)
            _shared_lightrag_keyword_adapter = KeywordAdapter(engine)
            logger.info("已构建共享 lightrag keyword adapter")
            return _shared_lightrag_keyword_adapter
        except Exception as exc:  # noqa: BLE001
            logger.warning("构建共享 lightrag keyword adapter 失败：%s", exc)
            return None


async def get_shared_lightrag_graph_retrieve_adapter() -> Optional[Any]:
    """为 graph.retrieve 注入适配器。"""
    global _shared_lightrag_graph_retrieve_adapter
    async with _lock:
        if _shared_lightrag_graph_retrieve_adapter is not None:
            return _shared_lightrag_graph_retrieve_adapter
        _ensure_dotenv_loaded()
        try:
            GraphRetrieveAdapter, LightRAGAdapterConfig, LightRAGEngineAdapter = _import_lightrag_symbols(
                "GraphRetrieveAdapter",
                "LightRAGAdapterConfig",
                "LightRAGEngineAdapter",
            )

            llm_fn = _build_llm_model_func_from_env() or _placeholder_llm_model_func
            cfg = LightRAGAdapterConfig(
                working_dir=os.path.join(_raganything_working_dir(), "lightrag_graph_retrieve"),
                workspace=(os.getenv("WORKSPACE") or "").strip(),
                embedding_func=_build_placeholder_embedding_func(),
                llm_model_func=llm_fn,
            )
            engine = LightRAGEngineAdapter(config=cfg)
            _shared_lightrag_graph_retrieve_adapter = GraphRetrieveAdapter(engine)
            logger.info("已构建共享 lightrag graph retrieve adapter")
            return _shared_lightrag_graph_retrieve_adapter
        except Exception as exc:  # noqa: BLE001
            logger.warning("构建共享 lightrag graph retrieve adapter 失败：%s", exc)
            return None


async def get_shared_lightrag_chunk_adapter() -> Optional[Any]:
    """为 chunk.split 注入适配器。"""
    global _shared_lightrag_chunk_adapter
    async with _lock:
        if _shared_lightrag_chunk_adapter is not None:
            return _shared_lightrag_chunk_adapter
        _ensure_dotenv_loaded()
        try:
            ChunkAdapter, LightRAGAdapterConfig, LightRAGEngineAdapter = _import_lightrag_symbols(
                "ChunkAdapter",
                "LightRAGAdapterConfig",
                "LightRAGEngineAdapter",
            )

            llm_fn = _build_llm_model_func_from_env() or _placeholder_llm_model_func
            cfg = LightRAGAdapterConfig(
                working_dir=os.path.join(_raganything_working_dir(), "lightrag_chunk"),
                workspace=(os.getenv("WORKSPACE") or "").strip(),
                embedding_func=_build_placeholder_embedding_func(),
                llm_model_func=llm_fn,
            )
            engine = LightRAGEngineAdapter(config=cfg)
            _shared_lightrag_chunk_adapter = ChunkAdapter(engine)
            logger.info("已构建共享 lightrag chunk adapter")
            return _shared_lightrag_chunk_adapter
        except Exception as exc:  # noqa: BLE001
            logger.warning("构建共享 lightrag chunk adapter 失败：%s", exc)
            return None


async def get_shared_lightrag_entity_adapter() -> Optional[Any]:
    """为 entity_relation.extract 注入适配器。"""
    global _shared_lightrag_entity_adapter
    async with _lock:
        if _shared_lightrag_entity_adapter is not None:
            return _shared_lightrag_entity_adapter
        _ensure_dotenv_loaded()
        try:
            EntityAdapter, LightRAGAdapterConfig, LightRAGEngineAdapter = _import_lightrag_symbols(
                "EntityAdapter",
                "LightRAGAdapterConfig",
                "LightRAGEngineAdapter",
            )

            llm_fn = _build_llm_model_func_from_env()
            if llm_fn is None:
                logger.info("未检测到 LLM_BINDING_API_KEY，跳过 lightrag entity adapter 注入")
                return None
            cfg = LightRAGAdapterConfig(
                working_dir=os.path.join(_raganything_working_dir(), "lightrag_entity"),
                workspace=(os.getenv("WORKSPACE") or "").strip(),
                embedding_func=_build_placeholder_embedding_func(),
                llm_model_func=llm_fn,
            )
            engine = LightRAGEngineAdapter(config=cfg)
            _shared_lightrag_entity_adapter = EntityAdapter(engine)
            logger.info("已构建共享 lightrag entity adapter")
            return _shared_lightrag_entity_adapter
        except Exception as exc:  # noqa: BLE001
            logger.warning("构建共享 lightrag entity adapter 失败：%s", exc)
            return None


async def get_shared_lightrag_entity_merge_adapter() -> Optional[Any]:
    """为 entity.merge 注入适配器。"""
    global _shared_lightrag_entity_merge_adapter
    async with _lock:
        if _shared_lightrag_entity_merge_adapter is not None:
            return _shared_lightrag_entity_merge_adapter
        _ensure_dotenv_loaded()
        try:
            EntityMergeAdapter, LightRAGAdapterConfig, LightRAGEngineAdapter = _import_lightrag_symbols(
                "EntityMergeAdapter",
                "LightRAGAdapterConfig",
                "LightRAGEngineAdapter",
            )

            llm_fn = _build_llm_model_func_from_env() or _placeholder_llm_model_func
            cfg = LightRAGAdapterConfig(
                working_dir=os.path.join(_raganything_working_dir(), "lightrag_entity_merge"),
                workspace=(os.getenv("WORKSPACE") or "").strip(),
                embedding_func=_build_placeholder_embedding_func(),
                llm_model_func=llm_fn,
            )
            engine = LightRAGEngineAdapter(config=cfg)
            _shared_lightrag_entity_merge_adapter = EntityMergeAdapter(engine)
            logger.info("已构建共享 lightrag entity merge adapter")
            return _shared_lightrag_entity_merge_adapter
        except Exception as exc:  # noqa: BLE001
            logger.warning("构建共享 lightrag entity merge adapter 失败：%s", exc)
            return None


async def get_shared_lightrag_relation_merge_adapter() -> Optional[Any]:
    """为 relation.merge 注入适配器。"""
    global _shared_lightrag_relation_merge_adapter
    async with _lock:
        if _shared_lightrag_relation_merge_adapter is not None:
            return _shared_lightrag_relation_merge_adapter
        _ensure_dotenv_loaded()
        try:
            LightRAGAdapterConfig, LightRAGEngineAdapter, RelationMergeAdapter = _import_lightrag_symbols(
                "LightRAGAdapterConfig",
                "LightRAGEngineAdapter",
                "RelationMergeAdapter",
            )

            llm_fn = _build_llm_model_func_from_env() or _placeholder_llm_model_func
            cfg = LightRAGAdapterConfig(
                working_dir=os.path.join(_raganything_working_dir(), "lightrag_relation_merge"),
                workspace=(os.getenv("WORKSPACE") or "").strip(),
                embedding_func=_build_placeholder_embedding_func(),
                llm_model_func=llm_fn,
            )
            engine = LightRAGEngineAdapter(config=cfg)
            _shared_lightrag_relation_merge_adapter = RelationMergeAdapter(engine)
            logger.info("已构建共享 lightrag relation merge adapter")
            return _shared_lightrag_relation_merge_adapter
        except Exception as exc:  # noqa: BLE001
            logger.warning("构建共享 lightrag relation merge adapter 失败：%s", exc)
            return None


async def get_shared_lightrag_graph_merge_adapter() -> Optional[Any]:
    """为 graph.merge 注入适配器。"""
    global _shared_lightrag_graph_merge_adapter
    async with _lock:
        if _shared_lightrag_graph_merge_adapter is not None:
            return _shared_lightrag_graph_merge_adapter
        _ensure_dotenv_loaded()
        try:
            GraphMergeAdapter, LightRAGAdapterConfig, LightRAGEngineAdapter = _import_lightrag_symbols(
                "GraphMergeAdapter",
                "LightRAGAdapterConfig",
                "LightRAGEngineAdapter",
            )

            llm_fn = _build_llm_model_func_from_env() or _placeholder_llm_model_func
            cfg = LightRAGAdapterConfig(
                working_dir=os.path.join(_raganything_working_dir(), "lightrag_graph_merge"),
                workspace=(os.getenv("WORKSPACE") or "").strip(),
                embedding_func=_build_placeholder_embedding_func(),
                llm_model_func=llm_fn,
            )
            engine = LightRAGEngineAdapter(config=cfg)
            _shared_lightrag_graph_merge_adapter = GraphMergeAdapter(engine)
            logger.info("已构建共享 lightrag graph merge adapter")
            return _shared_lightrag_graph_merge_adapter
        except Exception as exc:  # noqa: BLE001
            logger.warning("构建共享 lightrag graph merge adapter 失败：%s", exc)
            return None


async def get_shared_lightrag_graph_persist_adapter() -> Optional[Any]:
    """为 graph.persist 注入适配器。"""
    global _shared_lightrag_graph_persist_adapter
    async with _lock:
        if _shared_lightrag_graph_persist_adapter is not None:
            return _shared_lightrag_graph_persist_adapter
        _ensure_dotenv_loaded()
        try:
            (GraphPersistAdapter,) = _import_lightrag_symbols("GraphPersistAdapter")

            _shared_lightrag_graph_persist_adapter = GraphPersistAdapter()
            logger.info("已构建共享 lightrag graph persist adapter")
            return _shared_lightrag_graph_persist_adapter
        except Exception as exc:  # noqa: BLE001
            logger.warning("构建共享 lightrag graph persist adapter 失败：%s", exc)
            return None


async def get_shared_runtime_rerank_adapter() -> Optional[Any]:
    """为 rerank(runtime) 注入适配器。"""
    global _shared_runtime_rerank_adapter
    async with _lock:
        if _shared_runtime_rerank_adapter is not None:
            return _shared_runtime_rerank_adapter
        try:
            from adapters.runtime.runtime_rerank_adapter import RuntimeRerankAdapter

            _shared_runtime_rerank_adapter = RuntimeRerankAdapter()
            logger.info("已构建共享 runtime rerank adapter")
            return _shared_runtime_rerank_adapter
        except Exception as exc:  # noqa: BLE001
            logger.warning("构建共享 runtime rerank adapter 失败：%s", exc)
            return None


async def get_shared_industrial_knowledge_adapter() -> Optional[Any]:
    """为 industrial.* 节点注入工业知识适配器。"""
    global _shared_industrial_knowledge_adapter
    async with _lock:
        if _shared_industrial_knowledge_adapter is not None:
            return _shared_industrial_knowledge_adapter
        try:
            from adapters.industrial_knowledge import IndustrialKnowledgeAdapter

            _shared_industrial_knowledge_adapter = IndustrialKnowledgeAdapter()
            logger.info("已构建共享 industrial knowledge adapter")
            return _shared_industrial_knowledge_adapter
        except Exception as exc:  # noqa: BLE001
            logger.warning("构建共享 industrial knowledge adapter 失败：%s", exc)
            return None


async def get_shared_industrial_graph_persist_adapter() -> Optional[Any]:
    """为 industrial.graph.persist 注入适配器。"""
    global _shared_industrial_graph_persist_adapter
    async with _lock:
        if _shared_industrial_graph_persist_adapter is not None:
            return _shared_industrial_graph_persist_adapter
        try:
            from adapters.runtime.industrial_graph_persist_adapter import (
                IndustrialGraphPersistAdapter,
            )

            _shared_industrial_graph_persist_adapter = IndustrialGraphPersistAdapter()
            logger.info("已构建共享 industrial graph persist adapter")
            return _shared_industrial_graph_persist_adapter
        except Exception as exc:  # noqa: BLE001
            logger.warning("构建共享 industrial graph persist adapter 失败：%s", exc)
            return None


async def build_adapters_for_request(request: WorkflowRunRequest) -> Dict[str, Any]:
    """返回注入到 ``ExecutionContext.adapters`` 的映射。"""
    out: Dict[str, Any] = {}
    if not workflow_needs_raganything(request):
        # 即使不需要 raganything，也可为 embedding.index / vector.retrieve 注入 embedding_func
        if workflow_needs_embedding_index(request) or workflow_needs_vector_retrieve(request):
            emb = await get_shared_embedding_func()
            if emb is not None:
                out["embedding_func"] = emb
        if workflow_needs_llm_generate(request):
            llm = await get_shared_llm_model_func()
            if llm is not None:
                out["llm_model_func"] = llm
        if workflow_needs_keyword_extract(request):
            llm = await get_shared_llm_model_func()
            if llm is not None:
                out["llm_model_func"] = llm
            kw = await get_shared_lightrag_keyword_adapter()
            if kw is not None:
                out["lightrag_keyword"] = kw
        if workflow_needs_graph_retrieve(request):
            gr = await get_shared_lightrag_graph_retrieve_adapter()
            if gr is not None:
                out["lightrag_graph_retrieve"] = gr
        if workflow_needs_chunk_split(request):
            ch = await get_shared_lightrag_chunk_adapter()
            if ch is not None:
                out["lightrag_chunk"] = ch
        if workflow_needs_entity_relation_extract(request):
            llm = await get_shared_llm_model_func()
            if llm is not None:
                out["llm_model_func"] = llm
            er = await get_shared_lightrag_entity_adapter()
            if er is not None:
                out["lightrag_entity"] = er
        if workflow_needs_entity_merge(request):
            em = await get_shared_lightrag_entity_merge_adapter()
            if em is not None:
                out["lightrag_entity_merge"] = em
        if workflow_needs_relation_merge(request):
            rm = await get_shared_lightrag_relation_merge_adapter()
            if rm is not None:
                out["lightrag_relation_merge"] = rm
        if workflow_needs_graph_merge(request):
            gm = await get_shared_lightrag_graph_merge_adapter()
            if gm is not None:
                out["lightrag_graph_merge"] = gm
        if workflow_needs_graph_persist(request):
            gp = await get_shared_lightrag_graph_persist_adapter()
            if gp is not None:
                out["lightrag_graph_persist"] = gp
        if workflow_needs_rerank(request):
            rr = await get_shared_runtime_rerank_adapter()
            if rr is not None:
                out["runtime_rerank"] = rr
        if workflow_needs_industrial(request):
            ik = await get_shared_industrial_knowledge_adapter()
            if ik is not None:
                out["industrial_knowledge"] = ik
        if workflow_needs_industrial_graph_persist(request):
            igp = await get_shared_industrial_graph_persist_adapter()
            if igp is not None:
                out["industrial_graph_persist"] = igp
        return out
    ra = await get_shared_raganything_engine()
    if ra is not None:
        out["raganything"] = ra
        # raganything engine 可直接提供 embedding_func，供 embedding.index 复用
        if hasattr(ra, "embedding_func") and callable(getattr(ra, "embedding_func")):
            out["embedding_func"] = getattr(ra, "embedding_func")
        if hasattr(ra, "llm_model_func") and callable(getattr(ra, "llm_model_func")):
            out["llm_model_func"] = getattr(ra, "llm_model_func")
        # 若 raganything 已持有 lightrag 实例，优先复用其关键词抽取能力
        try:
            (
                ChunkAdapter,
                EntityAdapter,
                EntityMergeAdapter,
                GraphMergeAdapter,
                GraphPersistAdapter,
                GraphRetrieveAdapter,
                KeywordAdapter,
                LightRAGEngineAdapter,
                RelationMergeAdapter,
            ) = _import_lightrag_symbols(
                "ChunkAdapter",
                "EntityAdapter",
                "EntityMergeAdapter",
                "GraphMergeAdapter",
                "GraphPersistAdapter",
                "GraphRetrieveAdapter",
                "KeywordAdapter",
                "LightRAGEngineAdapter",
                "RelationMergeAdapter",
            )

            inner_rag = getattr(ra, "raganything", None)
            lightrag_inst = getattr(inner_rag, "lightrag", None) if inner_rag is not None else None
            if lightrag_inst is not None:
                shared_engine = LightRAGEngineAdapter(rag=lightrag_inst)
                out["lightrag_keyword"] = KeywordAdapter(shared_engine)
                out["lightrag_graph_retrieve"] = GraphRetrieveAdapter(shared_engine)
                out["lightrag_chunk"] = ChunkAdapter(shared_engine)
                out["lightrag_entity"] = EntityAdapter(shared_engine)
                out["lightrag_entity_merge"] = EntityMergeAdapter(shared_engine)
                out["lightrag_relation_merge"] = RelationMergeAdapter(shared_engine)
                out["lightrag_graph_merge"] = GraphMergeAdapter(shared_engine)
                out["lightrag_graph_persist"] = GraphPersistAdapter()
        except Exception:  # noqa: BLE001
            pass
    elif workflow_needs_embedding_index(request) or workflow_needs_vector_retrieve(request):
        # raganything 初始化失败时，仍尝试单独注入 embedding_func（供 embedding.index/vector.retrieve）
        emb = await get_shared_embedding_func()
        if emb is not None:
            out["embedding_func"] = emb
    if workflow_needs_llm_generate(request) and "llm_model_func" not in out:
        llm = await get_shared_llm_model_func()
        if llm is not None:
            out["llm_model_func"] = llm
    if workflow_needs_keyword_extract(request):
        if "llm_model_func" not in out:
            llm = await get_shared_llm_model_func()
            if llm is not None:
                out["llm_model_func"] = llm
        if "lightrag_keyword" not in out:
            kw = await get_shared_lightrag_keyword_adapter()
            if kw is not None:
                out["lightrag_keyword"] = kw
    if workflow_needs_graph_retrieve(request) and "lightrag_graph_retrieve" not in out:
        gr = await get_shared_lightrag_graph_retrieve_adapter()
        if gr is not None:
            out["lightrag_graph_retrieve"] = gr
    if workflow_needs_chunk_split(request) and "lightrag_chunk" not in out:
        ch = await get_shared_lightrag_chunk_adapter()
        if ch is not None:
            out["lightrag_chunk"] = ch
    if workflow_needs_entity_relation_extract(request):
        if "llm_model_func" not in out:
            llm = await get_shared_llm_model_func()
            if llm is not None:
                out["llm_model_func"] = llm
        if "lightrag_entity" not in out:
            er = await get_shared_lightrag_entity_adapter()
            if er is not None:
                out["lightrag_entity"] = er
    if workflow_needs_entity_merge(request) and "lightrag_entity_merge" not in out:
        em = await get_shared_lightrag_entity_merge_adapter()
        if em is not None:
            out["lightrag_entity_merge"] = em
    if workflow_needs_relation_merge(request) and "lightrag_relation_merge" not in out:
        rm = await get_shared_lightrag_relation_merge_adapter()
        if rm is not None:
            out["lightrag_relation_merge"] = rm
    if workflow_needs_graph_merge(request) and "lightrag_graph_merge" not in out:
        gm = await get_shared_lightrag_graph_merge_adapter()
        if gm is not None:
            out["lightrag_graph_merge"] = gm
    if workflow_needs_graph_persist(request) and "lightrag_graph_persist" not in out:
        gp = await get_shared_lightrag_graph_persist_adapter()
        if gp is not None:
            out["lightrag_graph_persist"] = gp
    if workflow_needs_rerank(request) and "runtime_rerank" not in out:
        rr = await get_shared_runtime_rerank_adapter()
        if rr is not None:
            out["runtime_rerank"] = rr
    if workflow_needs_industrial(request) and "industrial_knowledge" not in out:
        ik = await get_shared_industrial_knowledge_adapter()
        if ik is not None:
            out["industrial_knowledge"] = ik
    if workflow_needs_industrial_graph_persist(request) and "industrial_graph_persist" not in out:
        igp = await get_shared_industrial_graph_persist_adapter()
        if igp is not None:
            out["industrial_graph_persist"] = igp
    return out
