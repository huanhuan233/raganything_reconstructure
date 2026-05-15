"""工艺流程识别。"""

from __future__ import annotations

from typing import Any

from ..rules.process_patterns import PROCESS_STEP_KEYWORDS
from .base_parser import BaseStructureParser


class ProcessFlowParser(BaseStructureParser):
    parser_name = "process_flow"
    supported_document_types = ["process_card", "process_spec", "assembly", "general"]

    def detect(self, blocks: list[dict[str, Any]]) -> bool:
        text_all = " ".join(str(x.get("text") or "") for x in blocks)
        return any(k in text_all for k in PROCESS_STEP_KEYWORDS)

    def build_structure(self, blocks: list[dict[str, Any]]) -> dict[str, Any]:
        steps: list[dict[str, Any]] = []
        for one in blocks:
            text = str(one.get("text") or "").strip()
            if not text:
                continue
            hit = [k for k in PROCESS_STEP_KEYWORDS if k in text]
            if not hit:
                continue
            steps.append(
                {
                    "step_id": f"step_{len(steps) + 1}",
                    "name": hit[0],
                    "raw_text": text,
                    "page": int(one.get("page") or 0),
                    "block_id": str(one.get("block_id") or ""),
                }
            )
        edges: list[dict[str, str]] = []
        for i in range(len(steps) - 1):
            edges.append(
                {
                    "before": str(steps[i]["step_id"]),
                    "next_step": str(steps[i + 1]["step_id"]),
                }
            )
        return {"steps": steps, "flow_edges": edges}

    def validate(self, structure: dict[str, Any]) -> list[str]:
        steps = structure.get("steps") if isinstance(structure.get("steps"), list) else []
        if not steps:
            return ["no_process_steps_detected"]
        return []
