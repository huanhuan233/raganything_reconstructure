"""
LightRAG 引擎的最小封装：组合持有 ``LightRAG`` 实例，不继承。
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional, Union

from lightrag import LightRAG
from lightrag.base import DeletionResult, QueryParam
from lightrag.utils import always_get_an_event_loop

from .config import LightRAGAdapterConfig


class LightRAGEngineAdapter:
    """
    工业化场景下的单一入口包装类。

    - 职责：转发 insert / query / 纯检索 / 删除 四类最常用能力。
    - 禁止：在此处实现分块、抽取、图谱合并等业务算法（应留在 LightRAG 或由上游节点完成）。
    """

    def __init__(
        self,
        rag: Optional[LightRAG] = None,
        *,
        config: Optional[LightRAGAdapterConfig] = None,
        **lightrag_kwargs: Any,
    ) -> None:
        """
        Args:
            rag: 外部已初始化好的 ``LightRAG``（推荐在与应用共享生命周期的工厂中创建）。
            config: 与 ``extra_lightrag_kwargs`` 合并后构造 ``LightRAG``。
            **lightrag_kwargs: 直接透传给 ``LightRAG`` 构造函数。

        Raises:
            ValueError: 未提供 ``rag`` 且无法从 ``config``/``kwargs`` 构造时。
        """
        if rag is not None:
            self.rag: LightRAG = rag
        else:
            kw: Dict[str, Any] = {}
            if config is not None:
                kw.update(
                    {
                        "working_dir": config.working_dir,
                        "workspace": config.workspace,
                        "kv_storage": config.kv_storage,
                        "vector_storage": config.vector_storage,
                        "graph_storage": config.graph_storage,
                        "doc_status_storage": config.doc_status_storage,
                        "embedding_func": config.embedding_func,
                        "llm_model_func": config.llm_model_func,
                    }
                )
                kw.update(config.extra_lightrag_kwargs)
            kw.update(lightrag_kwargs)
            self.rag = LightRAG(**kw)

    # --- 写入（同步薄封装，内部仍为 LightRAG 的异步流水线） ---

    def insert_document(
        self,
        input: Union[str, List[str]],
        *,
        split_by_character: Optional[str] = None,
        split_by_character_only: bool = False,
        ids: Union[str, List[str], None] = None,
        file_paths: Union[str, List[str], None] = None,
        track_id: Optional[str] = None,
    ) -> str:
        """插入原始文本（整篇），返回 track_id。"""
        return self.rag.insert(
            input,
            split_by_character=split_by_character,
            split_by_character_only=split_by_character_only,
            ids=ids,
            file_paths=file_paths,
            track_id=track_id,
        )

    # --- 查询（生成答案） ---

    def query(
        self,
        query: str,
        param: QueryParam = QueryParam(),
        system_prompt: Optional[str] = None,
    ) -> Union[str, Iterator[str]]:
        """同步 RAG 问答，语义等同于 ``LightRAG.query``。"""
        return self.rag.query(query, param=param, system_prompt=system_prompt)

    # --- 仅检索 ---

    def retrieve(
        self,
        query: str,
        param: QueryParam = QueryParam(),
    ) -> Dict[str, Any]:
        """仅取结构化检索结果，不调用最终生成（``query_data``）。"""
        return self.rag.query_data(query, param=param)

    # --- 删除 ---

    def delete_document(
        self, doc_id: str, *, delete_llm_cache: bool = False
    ) -> DeletionResult:
        """按文档 ID 删除全链路派生数据。"""
        loop = always_get_an_event_loop()
        return loop.run_until_complete(
            self.rag.adelete_by_doc_id(doc_id, delete_llm_cache=delete_llm_cache)
        )
