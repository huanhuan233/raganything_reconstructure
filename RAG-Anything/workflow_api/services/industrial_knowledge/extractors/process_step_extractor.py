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
                    steps.append(
                        {
                            "step_id": f"step_{len(steps) + 1}",
                            "name": kw,
                            "description": text,
                            "page": int(one.get("page") or 0),
                            "block_id": str(one.get("block_id") or ""),
                        }
                    )
                    break
        for i, step in enumerate(steps):
            step["before"] = steps[i - 1]["step_id"] if i > 0 else ""
            step["next_step"] = steps[i + 1]["step_id"] if i < len(steps) - 1 else ""
        return steps
