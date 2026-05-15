"""
RAGAnything Adapter 配置收口（不读取复杂 YAML）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from third_party.raganything.config import RAGAnythingConfig


@dataclass
class RAGAnythingAdapterConfig:
    """
    适配层配置，用于构造 `raganything.config.RAGAnythingConfig` 或与工厂方法联动。

    TODO: 支持从 pydantic-settings / 统一 YAML / 配置中心加载并与多租户 workspace 绑定。
    """

    working_dir: str = "./rag_storage"
    parser: str = "mineru"
    parse_method: str = "auto"

    enable_image_processing: bool = True
    enable_table_processing: bool = True
    enable_equation_processing: bool = True

    use_full_path: bool = False
    context_window: int = 1
    context_mode: str = "page"
    content_format: str = "minerU"

    #: 为 True 时，未来可与 `adapters.lightrag.LightRAGEngineAdapter` 共用同一 LightRAG 实例（当前仅占位）。
    lightrag_adapter_enabled: bool = False

    #: 为 True（默认）：``initialize()`` 可走 Adapter 安装的惰性路径，不强制 MinerU/Docling 等已安装；
    #: 需在解析磁盘文件时再显式校验（见 ``RAGAnythingEngineAdapter.ensure_parser_ready_for_document_parsing``）。
    lazy_parser_validation: bool = True

    extra_options: Dict[str, Any] = field(default_factory=dict)

    def to_raganything_config(self) -> RAGAnythingConfig:
        """转换为官方 `RAGAnythingConfig`（供构造 RAGAnything 时使用）。"""
        from third_party.raganything.config import RAGAnythingConfig

        return RAGAnythingConfig(
            working_dir=self.working_dir,
            parser=self.parser,
            parse_method=self.parse_method,
            enable_image_processing=self.enable_image_processing,
            enable_table_processing=self.enable_table_processing,
            enable_equation_processing=self.enable_equation_processing,
            use_full_path=self.use_full_path,
            context_window=self.context_window,
            context_mode=self.context_mode,
            content_format=self.content_format,
        )
