"""Structure parser base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseStructureParser(ABC):
    parser_name: str = "base"
    supported_document_types: list[str] = ["general"]

    @abstractmethod
    def detect(self, blocks: list[dict[str, Any]]) -> bool:
        raise NotImplementedError

    @abstractmethod
    def build_structure(self, blocks: list[dict[str, Any]]) -> dict[str, Any]:
        raise NotImplementedError

    def validate(self, structure: dict[str, Any]) -> list[str]:
        _ = structure
        return []

    def metadata(self) -> dict[str, Any]:
        return {
            "parser_name": self.parser_name,
            "supported_document_types": list(self.supported_document_types),
        }
