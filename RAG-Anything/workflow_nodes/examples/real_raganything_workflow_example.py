"""
第一条真实 RAGAnything 工作流：本地 PDF → ``raganything.insert`` → ``rag.query``。

使用 ``RAGAnythingEngineAdapter.process_document``（引擎配置 ``parser=mineru``，节点 ``parse_method=auto``）与 ``query``，
**不使用** Mock 适配器。

运行（在 ``RAG-Anything`` 仓库根目录，需已安装 ``raganything``、``lightrag``、解析器等依赖）::

    python workflow_nodes/examples/real_raganything_workflow_example.py path/to/file.pdf

可选环境变量：

- ``RAGANYTHING_WORKING_DIR``：工作目录（默认 ``<repo>/output/real_raganything_wf``）

⚠ 示例内 LLM / Embedding 仍为占位实现；真实 PDF 入库与 ``hybrid`` 查询需替换为
可用的异步 ``llm_model_func`` 与 ``embedding_func``（可参考 ``examples/adapter_raganything_minimal_example.py``）。
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from adapters.raganything import (  # noqa: E402
    RAGAnythingAdapterConfig,
    RAGAnythingEngineAdapter,
)
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.graph_engine.workflow_runner import WorkflowRunner
from runtime_kernel.graph.workflow_schema import WorkflowSchema  # noqa: E402


async def placeholder_llm_model_func(prompt: str, **kwargs: Any) -> str:
    """请替换为真实 LLM；占位仅满足部分图抽取 JSON 形态。"""
    return '{"entities":[],"relationships":[]}'


async def placeholder_embedding_texts(texts: list[str]) -> list[list[float]]:
    dim = 4096
    return [[(i + k) % 13 * 0.01 for k in range(dim)] for i, _ in enumerate(texts)]


def build_placeholder_embedding_func() -> Any:
    from adapters.lightrag.providers.embedding_provider import EmbeddingFunc

    return EmbeddingFunc(
        embedding_dim=4096,
        func=placeholder_embedding_texts,
        max_token_size=8192,
        model_name="real-raganything-workflow-example",
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description="真实 RAGAnything：insert → query")
    parser.add_argument("pdf", type=str, help="本地 PDF 路径")
    parser.add_argument(
        "--query",
        type=str,
        default="请用中文简要概括文档主要内容。",
        help="查询问题",
    )
    args = parser.parse_args()
    pdf_path = str(Path(args.pdf).resolve())
    if not Path(pdf_path).is_file():
        print(f"文件不存在: {pdf_path}", file=sys.stderr)
        raise SystemExit(2)

    working = os.environ.get(
        "RAGANYTHING_WORKING_DIR",
        str(_ROOT / "output" / "real_raganything_wf"),
    )
    Path(working).mkdir(parents=True, exist_ok=True)

    adapter_config = RAGAnythingAdapterConfig(
        working_dir=working,
        parser="mineru",
        parse_method="auto",
        lazy_parser_validation=True,
    )

    engine = RAGAnythingEngineAdapter.from_config(
        adapter_config,
        llm_model_func=placeholder_llm_model_func,
        embedding_func=build_placeholder_embedding_func(),
        lightrag_kwargs={
            "workspace": "real_raganything_example",
            "vector_storage": "NanoVectorDBStorage",
            "graph_storage": "NetworkXStorage",
        },
    )

    await engine.initialize()

    ctx = ExecutionContext(
        workflow_id="real_raganything",
        run_id="example-1",
        workspace=working,
        adapters={"raganything": engine},
        shared_data={},
        logs=[],
    )

    nodes = [
        {
            "id": "ins",
            "type": "raganything.insert",
            "config": {
                "source_path": pdf_path,
                "parse_method": "auto",
            },
        },
        {
            "id": "q",
            "type": "rag.query",
            "config": {
                "engine": "raganything",
                "query": args.query,
                "mode": "hybrid",
            },
        },
    ]
    schema = WorkflowSchema(
        workflow_id="real_raganything",
        nodes=nodes,
        edges=[("ins", "q")],
        entry_node_ids=["ins"],
    )

    runner = WorkflowRunner()
    result = await runner.run(schema, ctx, initial_input=None)
    print("success:", result.get("success"))
    for line in ctx.logs:
        print("log:", line)
    if not result.get("success"):
        print("error:", result.get("error"))
        for nid, r in (result.get("node_results") or {}).items():
            if not r.success:
                print(f"节点失败 {nid}: {r.error}")
        await engine.finalize()
        raise SystemExit(1)

    ask = result["node_results"].get("q")
    if ask and ask.data:
        print("answer:", ask.data.get("answer"))
        print("query_mode:", ask.data.get("query_mode"))
        print("metadata:", ask.data.get("metadata"))

    await engine.finalize()


if __name__ == "__main__":
    asyncio.run(main())
