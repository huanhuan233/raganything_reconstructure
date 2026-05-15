"""MinerU 数据桥。"""

from __future__ import annotations

from typing import Any

from workflow_api.services.industrial_knowledge.normalized_blocks import normalize_mineru_layout_blocks


class IndustrialMinerUBridge:
    def normalize(self, content_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return normalize_mineru_layout_blocks(content_list)
