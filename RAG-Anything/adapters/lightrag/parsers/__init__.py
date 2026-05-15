"""解析器适配：MinerU / 通用 Office-OCR / 未来将接 Docling 等。"""

from .generic_parser_adapter import GenericParserAdapter
from .mineru_adapter import MineruAdapter

__all__ = ["MineruAdapter", "GenericParserAdapter"]
