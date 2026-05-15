"""
MinerU（及兼容 API）解析适配骨架。

不负责启动 MinerU 服务进程；仅从「已解析结果」或「远端 API JSON」映射为 ``ParsedDocument``。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..types import ParsedDocument


class MineruAdapter:
    """
    MinerU 流水线入口占位。

    TODO:
        - PDF/Office -> MinerU 本地或 HTTP API；
        - content_list -> ``ParsedDocument``（含 ParsedImage / ParsedTable）；
        - DeepSeek-OCR2 结构化结果字段对齐；
        - 与本项目 raganything.processor 共存：Adapter 只做契约，不调业务实现。
    """

    def parse_file(self, path: Union[str, Path], **_: Any) -> ParsedDocument:
        """从磁盘路径触发解析。"""
        raise NotImplementedError(
            "TODO: 调用 MinerU pipeline 或远端 API；错误重试与版本锁定。"
        )

    def parse_content_list(
        self, content_list: List[Dict[str, Any]], *, file_path: Optional[str] = None
    ) -> ParsedDocument:
        """直接消费 MinerU 风格 content_list JSON。"""
        raise NotImplementedError(
            "TODO: 遍历 type（text/table/image/code）映射到 ParsedChunk/ParsedTable/ParsedImage。"
        )
