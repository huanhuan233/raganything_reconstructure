"""
在单个 ``RAGAnything`` 实例上绑定 ``_ensure_lightrag_initialized`` 的包装函数。

此为**实例替换**（``types.MethodType``），不属于对全局函数的 monkey patch，
也不修改 ``raganything`` 源码或 ``site-packages``。
"""

from __future__ import annotations

import types
from typing import Any, Dict

from third_party.raganything.raganything import RAGAnything

from .lazy_lightrag_bridge import duplicate_ensure_without_parser_check


def install_lazy_parser_ensure_on_instance(rag: Any) -> None:
    """
    为给定 ``rag`` 安装惰性 parser 语义：

    - ``_adapter_parser_required=False``（默认）：走 ``duplicate_ensure_without_parser_check``，
      不调用 ``doc_parser.check_installation``；
    - ``_adapter_parser_required=True``（由 Adapter 在处理「需磁盘解析」的入口前设置）：
      委托原版 ``RAGAnything._ensure_lightrag_initialized``（含正版 parser 检查）。

    幂等：同一实例重复安装会跳过替换。
    """
    if getattr(rag, "_adapter_lazy_ensure_installed", False):
        return

    setattr(rag, "_adapter_lazy_ensure_installed", True)
    setattr(rag, "_adapter_lazy_parser_validation", True)
    setattr(rag, "_adapter_parser_required", False)

    _cls_original = RAGAnything.__dict__["_ensure_lightrag_initialized"]

    async def _wrapped_ensure(inst: Any) -> dict:
        if getattr(inst, "_adapter_lazy_parser_validation", False):
            if getattr(inst, "_adapter_parser_required", False):
                return await _cls_original(inst)
            return await duplicate_ensure_without_parser_check(inst)
        return await _cls_original(inst)

    rag._ensure_lightrag_initialized = types.MethodType(_wrapped_ensure, rag)


def mark_parser_required(rag: Any) -> None:
    """
    标记「下一次 _ensure_lightrag_initialized 必须经过正版路径（含 parser 可用性）」。
    Adapter 在处理 ``source_path`` 的 ``process_document`` 等入口处调用。
    """
    setattr(rag, "_adapter_parser_required", True)


def check_lazy_bridge_health(rag: Any) -> Dict[str, Any]:
    """
    惰性桥接状态自检（**只读** ``RAGAnything`` / ``LightRAG`` 实例属性）。

    不连接远程数据库、不触发 ``initialize_storages``、不做任何写操作。
    用于 CI / 排障时确认绑定标志与 LightRAG 存储状态的大致一致性。

    Returns:
        dict: ``lazy_binding_installed``, ``parser_required``, ``lightrag_initialized``, ``warning``（多段提示以 `` | `` 拼接；无则空字符串）。
    """
    lazy_binding_installed = bool(getattr(rag, "_adapter_lazy_ensure_installed", False))
    parser_required = bool(getattr(rag, "_adapter_parser_required", False))

    lr = getattr(rag, "lightrag", None)
    lightrag_initialized = False
    if lr is not None:
        st = getattr(lr, "_storages_status", None)
        if st is not None:
            nm = getattr(st, "name", None)
            if isinstance(nm, str):
                lightrag_initialized = nm == "INITIALIZED"
            else:
                # Enum / 其他：尽量宽松匹配
                tail = str(nm).split(".")[-1]
                lightrag_initialized = tail == "INITIALIZED"

    warnings: list[str] = []
    if lazy_binding_installed:
        warnings.append(
            "兼容提示：lazy_lightrag_bridge 与上游 _ensure_lightrag_initialized 存在复制关系，"
            "升级 RAG-Anything 后请按 docs/adapter_upgrade_checklist.md 复核。"
        )
    if lazy_binding_installed and lr is None:
        warnings.append("LightRAG 尚未挂载（可能尚未执行 initialize）。")
    if lazy_binding_installed and lr is not None and not lightrag_initialized:
        warnings.append(
            "LightRAG._storages_status 未呈现 INITIALIZED（初始化未完成、失败或字段名变更）。"
        )

    return {
        "lazy_binding_installed": lazy_binding_installed,
        "parser_required": parser_required,
        "lightrag_initialized": lightrag_initialized,
        "warning": " | ".join(warnings) if warnings else "",
    }


def unregister_lazy_binding_if_installed(rag: Any) -> None:
    """
    测试/降级用：一般不调用。无法完全还原类默认方法引用，仅占位以备未来扩展。

    TODO: 若需提供「运行时卸载」，需备份 ``__func__`` 原始绑定。
    """
    _ = rag  # pragma: no cover
