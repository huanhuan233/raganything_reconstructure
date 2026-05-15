"""表结构识别，不扁平化。"""

from __future__ import annotations

from typing import Any

from .base_parser import BaseStructureParser


class TableStructureParser(BaseStructureParser):
    parser_name = "table_structure"
    supported_document_types = ["process_card", "standard", "general"]

    def detect(self, blocks: list[dict[str, Any]]) -> bool:
        return any(str(x.get("type") or "") in {"table", "sheet"} for x in blocks)

    def build_structure(self, blocks: list[dict[str, Any]]) -> dict[str, Any]:
        tables: list[dict[str, Any]] = []
        for one in blocks:
            btype = str(one.get("type") or "")
            if btype not in {"table", "sheet"}:
                continue
            raw = str(one.get("text") or "").strip()
            rows = [r.strip() for r in raw.split("\n") if r.strip()]
            header: list[str] = []
            data_rows: list[list[str]] = []
            if rows:
                header = [x.strip() for x in rows[0].split("|") if x.strip()]
            for r in rows[1:]:
                data_rows.append([x.strip() for x in r.split("|") if x.strip()])
            units = [h for h in header if any(k in h.lower() for k in ("mm", "μm", "um", "hbw", "hrc", "n·m"))]
            tables.append(
                {
                    "table_id": f"table_{len(tables) + 1}",
                    "block_id": str(one.get("block_id") or ""),
                    "page": int(one.get("page") or 0),
                    "row_headers": header,
                    "column_headers": header,
                    "rows": data_rows,
                    "merged_cells": [],
                    "units": units,
                    "constraints": [],
                }
            )
        return {"tables": tables}

    def validate(self, structure: dict[str, Any]) -> list[str]:
        warnings: list[str] = []
        tables = structure.get("tables") if isinstance(structure.get("tables"), list) else []
        for t in tables:
            h = (t or {}).get("column_headers")
            if not isinstance(h, list) or not h:
                warnings.append(f"table_header_missing:{(t or {}).get('table_id')}")
        return warnings
