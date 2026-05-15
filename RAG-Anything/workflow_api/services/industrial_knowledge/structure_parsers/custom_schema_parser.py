"""自定义 schema 解析器。"""

from __future__ import annotations

import re
from typing import Any

from .base_parser import BaseStructureParser


class CustomSchemaParser(BaseStructureParser):
    parser_name = "custom_schema"
    supported_document_types = ["general", "custom"]

    def detect(self, blocks: list[dict[str, Any]]) -> bool:
        return bool(blocks)

    def build_structure(self, blocks: list[dict[str, Any]], *, patterns: list[str] | None = None) -> dict[str, Any]:
        pats = [p for p in (patterns or []) if str(p).strip()]
        if not pats:
            return {"matches": []}
        out: list[dict[str, Any]] = []
        for one in blocks:
            text = str(one.get("text") or "").strip()
            if not text:
                continue
            for p in pats:
                if re.search(p, text):
                    out.append(
                        {
                            "pattern": p,
                            "text": text,
                            "block_id": str(one.get("block_id") or ""),
                            "page": int(one.get("page") or 0),
                        }
                    )
        return {"matches": out}
