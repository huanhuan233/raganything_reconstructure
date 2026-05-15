"""规则优先的约束抽取。"""

from __future__ import annotations

import re
from typing import Any

from ..rules.constraint_patterns import CONSTRAINT_PATTERNS


class ConstraintExtractor:
    def extract(self, blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for one in blocks:
            text = str(one.get("text") or "")
            if not text:
                continue
            for rule in CONSTRAINT_PATTERNS:
                pat = str(rule.get("pattern") or "")
                if not pat:
                    continue
                for m in re.finditer(pat, text):
                    gd = m.groupdict()
                    op = str(gd.get("operator") or "").strip()
                    op = {
                        "不大于": "<=",
                        "不小于": ">=",
                        "大于等于": ">=",
                        "小于等于": "<=",
                    }.get(op, op)
                    out.append(
                        {
                            "parameter": str(gd.get("parameter") or "").strip(),
                            "operator": op,
                            "value": float(gd.get("value")) if gd.get("value") else None,
                            "unit": str(gd.get("unit") or "").strip(),
                            "source_block_id": str(one.get("block_id") or ""),
                            "page": int(one.get("page") or 0),
                        }
                    )
        return out
