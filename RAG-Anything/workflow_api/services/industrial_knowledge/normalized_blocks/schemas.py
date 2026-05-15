"""Normalized layout block schema."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class NormalizedLayoutBlock:
    block_id: str
    type: str
    text: str
    bbox: list[float]
    page: int
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
