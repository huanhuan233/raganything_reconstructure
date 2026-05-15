"""
Adapter 生命周期烟测：**仅** ``initialize()`` / ``finalize()``，不涉及文档解析。

设计目的：
  - CI / 架构回归：验证 ``adapters.raganything`` + ``lightrag`` 可连通；
  - 验证 ``lazy_parser_validation`` 下无需安装 MinerU 即可完成引擎初始化。

不执行 ``insert_content_list``、不触碰业务向量写入（仍会初始化 LightRAG 存储）。

为减少与宿主环境（如全局 Milvus/Neo4j）冲突，脚本通过 ``lightrag_kwargs`` 强制
**NanoVectorDBStorage + NetworkXStorage** 与独立 ``workspace``，仅作架构烟测目录。

运行（项目根 RAG-Anything）:
  python examples/adapter_raganything_lifecycle_only.py

需提供可用的 ``llm_model_func`` 与 ``embedding_func``。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.raganything import (
    RAGAnythingAdapterConfig,
    RAGAnythingEngineAdapter,
    check_lazy_bridge_health,
)


async def trivial_llm(prompt: str, **kwargs: Any) -> str:
    return ""


async def trivial_embed(texts: list[str]) -> list[list[float]]:
    dim = 4096
    return [[0.0] * dim for _ in texts]


def build_embed() -> Any:
    from lightrag.utils import EmbeddingFunc

    return EmbeddingFunc(
        embedding_dim=4096,
        func=trivial_embed,
        max_token_size=8192,
        model_name="lifecycle-smoke",
    )


async def main() -> None:
    work = ROOT / "output" / "adapter_lifecycle_smoke"
    work.mkdir(parents=True, exist_ok=True)

    cfg = RAGAnythingAdapterConfig(
        working_dir=str(work),
        lazy_parser_validation=True,
        enable_image_processing=False,
        enable_table_processing=False,
        enable_equation_processing=False,
    )

    engine = RAGAnythingEngineAdapter.from_config(
        cfg,
        llm_model_func=trivial_llm,
        embedding_func=build_embed(),
        lightrag_kwargs={
            # 隔离于常见 .env 中的 Milvus/Neo4j；烟测不向远程向量库写入
            "workspace": "adapter_lifecycle_isolated",
            "vector_storage": "NanoVectorDBStorage",
            "graph_storage": "NetworkXStorage",
        },
    )

    print("check_lazy_bridge_health (initialize 之前):", check_lazy_bridge_health(engine.raganything))

    print("lifecycle_only: initializing (expect success without MinerU)...")
    await engine.initialize()
    print("initialize: OK")
    print("check_lazy_bridge_health (initialize 之后):", check_lazy_bridge_health(engine.raganything))

    await engine.finalize()
    print("finalize: OK")
    print("lifecycle_only smoke test finished.")


if __name__ == "__main__":
    asyncio.run(main())
