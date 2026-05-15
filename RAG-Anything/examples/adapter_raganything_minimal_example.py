"""
【Adapter 骨架调用示例 — 不构成生产默认可运行保证】

演示：
  1. ``RAGAnythingEngineAdapter.from_config`` 组装 ``RAGAnything``；
  2. ``ParsedDocument``（单 ``ParsedChunk``）经 ``insert_content_list`` 入库；
  3. ``query`` 发起一次检索问答。

本示例 **不调用 MinerU / 不进行磁盘文档解析**：仅 ``ParsedDocument`` → ``insert_content_list``，
依赖 ``RAGAnythingAdapterConfig.lazy_parser_validation=True``（默认）使 ``initialize()`` 跳过 Parser 安装校验。

⚠️ 必须自行替换可用的 ``llm_model_func`` / ``embedding_func``；占位 LLM **不符合**实体抽取所需 JSON，
**极易**在入库或查询阶段失败，属预期之内。

运行（在项目根 RAG-Anything 下）:
  python examples/adapter_raganything_minimal_example.py

依赖：已安装本项目 ``raganything``、``lightrag-hku``。
示例内 ``lightrag_kwargs`` 使用本地 Nano 向量 + NetworkX 图 + 独立 ``workspace``，避免误连宿主 .env 中的 Milvus 维度。
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
    ParsedChunk,
    ParsedDocument,
    RAGAnythingAdapterConfig,
    RAGAnythingEngineAdapter,
    RAGAnythingQueryRequest,
)

# ---------------------------------------------------------------------------
# 下面两段请替换为你的真实异步 LLM / 嵌入封装（可参考 examples/raganything_example.py）。
# ---------------------------------------------------------------------------


async def placeholder_llm_model_func(prompt: str, **kwargs: Any) -> str:
    """占位：返回固定字符串；无法满足真实 extract_entities JSON 时请替换。"""
    return '{"entities":[],"relationships":[]}'


async def placeholder_embedding_texts(texts: list[str]) -> list[list[float]]:
    """占位：确定性伪向量（4096 维），仅用于冒烟；生产请替换为真实 embedding API。"""
    dim = 4096
    out: list[list[float]] = []
    for i, _ in enumerate(texts):
        out.append([(i + k) % 13 * 0.01 for k in range(dim)])
    return out


def build_placeholder_embedding_func() -> Any:
    """包装为 LightRAG 可用的 ``EmbeddingFunc``。"""
    from lightrag.utils import EmbeddingFunc

    return EmbeddingFunc(
        embedding_dim=4096,
        func=placeholder_embedding_texts,
        max_token_size=8192,
        model_name="adapter-minimal-placeholder",
    )


async def main() -> None:
    working = ROOT / "output" / "adapter_minimal_demo"
    working.mkdir(parents=True, exist_ok=True)

    adapter_config = RAGAnythingAdapterConfig(
        working_dir=str(working),
        lazy_parser_validation=True,
        enable_image_processing=False,
        enable_table_processing=False,
        enable_equation_processing=False,
    )

    llm_model_func = placeholder_llm_model_func
    embedding_func = build_placeholder_embedding_func()

    print("⚠ Adapter 骨架示例：占位模型可能导致入库失败，请按需替换。\n")

    engine = RAGAnythingEngineAdapter.from_config(
        adapter_config,
        llm_model_func=llm_model_func,
        embedding_func=embedding_func,
        lightrag_kwargs={
            "workspace": "adapter_minimal_isolated",
            "vector_storage": "NanoVectorDBStorage",
            "graph_storage": "NetworkXStorage",
        },
    )

    await engine.initialize()

    # 单个文本块 → ParsedDocument → content_list → insert_content_list
    doc_id = "doc-adapter-demo-001"
    document = ParsedDocument(
        source_file="adapter_demo.txt",
        doc_id=doc_id,
        chunks=[
            ParsedChunk(
                text=(
                    "RAG-Anything Adapter 演示文档：这是一条用于最小入库链路测试的简短中文文本。"
                ),
                page_idx=0,
                text_level=0,
            ),
        ],
    )

    ins = await engine.insert_content_list(document, doc_id=doc_id)
    print("insert_content_list:", ins)

    q = RAGAnythingQueryRequest(
        query="演示文档里提到了什么？",
        mode="naive",
        enable_vlm=False,
        multimodal_content=[],
        extra_query_kwargs={},
    )
    q_resp = await engine.query(q)
    print("query:", q_resp)

    await engine.finalize()
    print("finalize 已完成。")


if __name__ == "__main__":
    asyncio.run(main())
