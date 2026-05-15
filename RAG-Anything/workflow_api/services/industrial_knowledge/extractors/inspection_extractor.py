"""检验要求抽取。"""

from __future__ import annotations

import re
from typing import Any


class InspectionExtractor:
    INSPECT_RE = re.compile(r"(检验|检测|复核|无损检测|目视检查|尺寸检查|验收)", re.I)

    def extract(self, blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for one in blocks:
            text = str(one.get("text") or "")
            if not text:
                continue
            if self.INSPECT_RE.search(text):
                out.append(
                    {
                        "inspection_text": text.strip(),
                        "source_block_id": str(one.get("block_id") or ""),
                        "page": int(one.get("page") or 0),
                    }
                )
        return out
