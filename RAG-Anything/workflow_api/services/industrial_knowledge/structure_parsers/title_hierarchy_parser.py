"""标题层级识别（regex + layout）。"""

from __future__ import annotations

import re
from typing import Any

from ..rules.section_patterns import SECTION_TITLE_PATTERNS
from .base_parser import BaseStructureParser


class TitleHierarchyParser(BaseStructureParser):
    parser_name = "title_hierarchy"
    supported_document_types = ["standard", "process_spec", "mbse", "sysml", "general"]

    def detect(self, blocks: list[dict[str, Any]]) -> bool:
        for one in blocks:
            text = str(one.get("text") or "").strip()
            if not text:
                continue
            for p in SECTION_TITLE_PATTERNS:
                if re.match(p, text):
                    return True
        return False

    def build_structure(self, blocks: list[dict[str, Any]]) -> dict[str, Any]:
        sections: list[dict[str, Any]] = []
        for one in blocks:
            text = str(one.get("text") or "").strip()
            if not text:
                continue
            for p in SECTION_TITLE_PATTERNS:
                m = re.match(p, text)
                if not m:
                    continue
                sid = str(m.group(1)).strip()
                title = str(m.group(2)).strip() if m.lastindex and m.lastindex >= 2 else text
                level = sid.count(".") + 1 if "." in sid else 1
                sections.append(
                    {
                        "section_id": sid,
                        "title": title,
                        "level": level,
                        "page": int(one.get("page") or 0),
                        "block_id": str(one.get("block_id") or ""),
                    }
                )
                break
        return {"sections": sections}

    def validate(self, structure: dict[str, Any]) -> list[str]:
        sections = structure.get("sections") if isinstance(structure.get("sections"), list) else []
        warnings: list[str] = []
        seen: set[str] = set()
        for one in sections:
            sid = str((one or {}).get("section_id") or "")
            if not sid:
                continue
            if sid in seen:
                warnings.append(f"duplicate_section:{sid}")
            seen.add(sid)
        return warnings
