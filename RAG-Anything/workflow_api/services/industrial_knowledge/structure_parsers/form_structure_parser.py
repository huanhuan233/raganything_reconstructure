"""工艺卡片/表单结构识别。"""

from __future__ import annotations

import re
from typing import Any

from .base_parser import BaseStructureParser


class FormStructureParser(BaseStructureParser):
    parser_name = "form_structure"
    supported_document_types = ["process_card", "form", "general"]

    def detect(self, blocks: list[dict[str, Any]]) -> bool:
        for one in blocks:
            text = str(one.get("text") or "")
            if ":" in text or "：" in text:
                return True
        return False

    def build_structure(self, blocks: list[dict[str, Any]]) -> dict[str, Any]:
        fields: list[dict[str, Any]] = []
        for one in blocks:
            text = str(one.get("text") or "").strip()
            if not text:
                continue
            m = re.match(r"^\s*([^:：]{1,40})[:：]\s*(.+)$", text)
            if not m:
                continue
            fields.append(
                {
                    "name": str(m.group(1)).strip(),
                    "value": str(m.group(2)).strip(),
                    "block_id": str(one.get("block_id") or ""),
                    "page": int(one.get("page") or 0),
                }
            )
        return {"fields": fields}
