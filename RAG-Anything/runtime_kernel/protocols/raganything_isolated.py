"""
在不执行 ``adapters/raganything/__init__.py`` 的前提下加载 types / document_adapter。

``adapters.raganything`` 包级 ``__init__`` 会急切导入 ``RAGAnythingEngineAdapter`` 进而依赖
``lightrag``；本模块通过 ``sys.modules`` 注入桩包后按文件路径加载子模块，供节点在精简环境中运行。
"""

from __future__ import annotations

import importlib.util
import sys
import types as std_types
from pathlib import Path
from types import ModuleType
from typing import Any, Type

_rag_anything_root_cache: Path | None = None
_types_mod: ModuleType | None = None
_document_adapter_cls: Any | None = None
_mineru_parser_adapter_cls: Any | None = None
_generic_parser_adapter_cls: Any | None = None


def _rag_anything_repo_root() -> Path:
    """``backend_runtime/core`` → 上两级为 ``RAG-Anything`` 根目录。"""
    global _rag_anything_root_cache
    if _rag_anything_root_cache is None:
        _rag_anything_root_cache = Path(__file__).resolve().parents[2]
    return _rag_anything_root_cache


def _ensure_stub_packages() -> Path:
    root = _rag_anything_repo_root()
    ra_pkg_dir = root / "adapters" / "raganything"
    if "adapters" not in sys.modules:
        sys.modules["adapters"] = std_types.ModuleType("adapters")
    if "adapters.raganything" not in sys.modules:
        pkg = std_types.ModuleType("adapters.raganything")
        pkg.__path__ = [str(ra_pkg_dir)]
        sys.modules["adapters.raganything"] = pkg
    return root


def load_raganything_types() -> ModuleType:
    """加载 ``adapters/raganything/types.py`` 为 ``adapters.raganything.types``。"""
    global _types_mod
    if _types_mod is not None:
        return _types_mod
    root = _ensure_stub_packages()
    path = root / "adapters" / "raganything" / "types.py"
    spec = importlib.util.spec_from_file_location(
        "adapters.raganything.types",
        path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载类型模块: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["adapters.raganything.types"] = mod
    spec.loader.exec_module(mod)
    _types_mod = mod
    return mod


def load_document_adapter_class() -> Type[Any]:
    """加载 ``DocumentAdapter`` 类（不执行包级 ``__init__``）。"""
    global _document_adapter_cls
    if _document_adapter_cls is not None:
        return _document_adapter_cls
    load_raganything_types()
    root = _rag_anything_repo_root()
    path = root / "adapters" / "raganything" / "document_adapter.py"
    spec = importlib.util.spec_from_file_location(
        "adapters.raganything.document_adapter",
        path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载 DocumentAdapter: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["adapters.raganything.document_adapter"] = mod
    spec.loader.exec_module(mod)
    _document_adapter_cls = mod.DocumentAdapter
    return _document_adapter_cls


def load_parser_adapter_classes() -> tuple[Type[Any], Type[Any]]:
    """加载 ``MinerUParserAdapter`` 与 ``GenericParserAdapter``（不执行包级 ``__init__``）。"""
    global _mineru_parser_adapter_cls, _generic_parser_adapter_cls
    if _mineru_parser_adapter_cls is not None and _generic_parser_adapter_cls is not None:
        return _mineru_parser_adapter_cls, _generic_parser_adapter_cls

    load_raganything_types()
    load_document_adapter_class()
    root = _rag_anything_repo_root()
    path = root / "adapters" / "raganything" / "parser_adapter.py"
    spec = importlib.util.spec_from_file_location(
        "adapters.raganything.parser_adapter",
        path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载 ParserAdapter: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["adapters.raganything.parser_adapter"] = mod
    spec.loader.exec_module(mod)
    _mineru_parser_adapter_cls = mod.MinerUParserAdapter
    _generic_parser_adapter_cls = mod.GenericParserAdapter
    return _mineru_parser_adapter_cls, _generic_parser_adapter_cls
