"""
最小 FastAPI 应用入口。

启动（建议 ``RAG-Anything`` 根目录；若从其它目录启动，下面会自动把仓库根加入 ``sys.path``）::

    uvicorn backend_api.main:app --host 0.0.0.0 --port 18080 --reload
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

# 从任意 cwd 启动时仍能 ``import adapters`` / ``backend_runtime``（否则 RAGAnything 适配器无法注入）
_RAG_ANYTHING_ROOT = Path(__file__).resolve().parents[1]
_root_str = str(_RAG_ANYTHING_ROOT)
if _root_str not in sys.path:
    sys.path.insert(0, _root_str)

from fastapi import FastAPI

import workflow_nodes  # noqa: F401  # 导入触发内置节点注册

from .raganything_runtime import _ensure_dotenv_loaded
from .routers import health, knowledge, nodes, runtime_trace, storage, workflows


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """启动时加载仓库根 ``.env``，使 ``/api/storage/*`` 等路由能读到 MILVUS_URI / NEO4J_URI。"""
    _ensure_dotenv_loaded()
    yield


app = FastAPI(
    title="RAG Backend API",
    description="将 backend_runtime 工作流以 HTTP 暴露的最小服务",
    version="0.1.0",
    lifespan=_lifespan,
)

app.include_router(health.router, prefix="/api")
app.include_router(nodes.router, prefix="/api")
app.include_router(knowledge.router, prefix="/api")
app.include_router(storage.router, prefix="/api")
app.include_router(workflows.router, prefix="/api")
app.include_router(runtime_trace.router, prefix="/api")
