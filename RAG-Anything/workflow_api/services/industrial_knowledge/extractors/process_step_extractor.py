"""工艺步骤抽取。"""

from __future__ import annotations

from typing import Any

from ..rules.process_patterns import PROCESS_STEP_KEYWORDS


class ProcessStepExtractor:
    def extract(self, blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        steps: list[dict[str, Any]] = []
        for one in blocks:
            text = str(one.get("text") or "").strip()
            if not text:
                continue
            for kw in PROCESS_STEP_KEYWORDS:
                if kw in text:
                    bid = str(one.get("block_id") or "").strip()
                    iid = str(one.get("item_id") or "").strip()
                    oid = str(one.get("id") or "").strip()
                    primary_layout = bid or oid or iid

                    raw_meta = one.get("metadata") if isinstance(one.get("metadata"), dict) else {}
                    mi = str(raw_meta.get("item_id") or "").strip()
                    mdi = str(raw_meta.get("id") or "").strip()
                    mb = str(raw_meta.get("block_id") or "").strip()

                    chi_sid = iid or oid or mi or mdi
                    primary_layout = primary_layout or mb or mdi or mi

                    row: dict[str, Any] = {
                        "step_id": f"step_{len(steps) + 1}",
                        "name": kw,
                        "description": text,
                        "page": int(one.get("page") or 0),
                        "block_id": primary_layout,
                    }
                    if iid:
                        row["item_id"] = iid
                    elif mi:
                        row["item_id"] = mi
                    elif oid:
                        row["item_id"] = oid
                    elif mdi:
                        row["item_id"] = mdi
                    elif primary_layout:
                        row["item_id"] = primary_layout
                    else:
                        row["item_id"] = ""
                    row["source_block_id"] = primary_layout if primary_layout else ""
                    if chi_sid:
                        row["source_item_id"] = chi_sid

                    steps.append(row)
                    break
        for i, step in enumerate(steps):
            step["before"] = steps[i - 1]["step_id"] if i > 0 else ""
            step["next_step"] = steps[i + 1]["step_id"] if i < len(steps) - 1 else ""
        return steps
