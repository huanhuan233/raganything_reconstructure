"""材料抽取。"""

from __future__ import annotations

import re
from typing import Any


class MaterialExtractor:
    MATERIAL_RE = re.compile(r"(铝合金|钛合金|不锈钢|钢|45钢|TC4|Al\d+|Ti[-\s]?\d+|Q\d+)", re.I)

    def extract(self, blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for one in blocks:
            text = str(one.get("text") or "")
            if not text:
                continue
            for m in self.MATERIAL_RE.finditer(text):
                out.append(
                    {
                        "material": m.group(1),
                        "source_block_id": str(one.get("block_id") or ""),
                        "page": int(one.get("page") or 0),
                    }
                )
        return out
