"""
仅验证 Adapter 子包可被 import，不连接模型、向量库或图数据库。

运行：在 RAG-Anything 项目根目录执行
  python examples/adapter_import_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def main() -> None:
    # raganything.config 依赖 lightrag；未安装时请 ``pip install lightrag-hku`` 或使用项目 .venv。
    import adapters.lightrag as al
    import adapters.raganything as ar
    print("adapters.lightrag 导出（部分）:")
    for name in (
        "LightRAGEngineAdapter",
        "IndexingAdapter",
        "QueryAdapter",
        "DeletionAdapter",
    ):
        print(f"  - {name}: {getattr(al, name)}")

    print("adapters.raganything 导出（部分）:")
    for name in (
        "RAGAnythingEngineAdapter",
        "RAGAnythingAdapterConfig",
        "ParsedDocument",
        "ParsedChunk",
        "DocumentProcessRequest",
        "RAGAnythingQueryRequest",
        "RAGAnythingQueryResponse",
        "DocumentAdapter",
    ):
        print(f"  - {name}: {getattr(ar, name)}")

    print("adapter_import_check: 完成。")


if __name__ == "__main__":
    try:
        main()
    except ModuleNotFoundError as e:
        if "lightrag" in str(e).lower():
            print("缺少 lightrag 模块，请先安装依赖（例如: pip install lightrag-hku）。")
            print("详情:", e)
            sys.exit(1)
        raise
