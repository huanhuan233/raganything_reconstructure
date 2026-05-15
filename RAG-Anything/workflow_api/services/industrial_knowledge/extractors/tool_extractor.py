"""工具抽取。"""

from __future__ import annotations

import re
from typing import Any


class ToolExtractor:
    TOOL_RE = re.compile(r"(钻头|铣刀|扳手|夹具|胎具|工装|torque\s*wrench|reamer)", re.I)

    def extract(self, blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for one in blocks:
            text = str(one.get("text") or "")
            if not text:
                continue
            for m in self.TOOL_RE.finditer(text):
                out.append(
                    {
                        "tool_name": m.group(1),
                        "source_block_id": str(one.get("block_id") or ""),
                        "page": int(one.get("page") or 0),
                    }
                )
        return out
