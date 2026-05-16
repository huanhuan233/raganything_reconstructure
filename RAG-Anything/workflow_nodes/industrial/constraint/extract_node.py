"""constraint.extract — 从 Chunk/表格/文本启发式抽取工业 ConstraintObject（可无 LLM）。"""

from __future__ import annotations

import re
import uuid
from typing import Any

from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult

from ..models.constraint_object import (
    AppliesTo,
    ConstraintKind,
    ConstraintObject,
    PredicatePayload,
)
from ..utils import merge_named_bucket_models


def _norm_text(blob: Any) -> str:
    if blob is None:
        return ""
    if isinstance(blob, str):
        return blob
    try:
        return str(blob)
    except Exception:  # noqa: BLE001
        return ""


def _gather_corpus(payload: dict[str, Any], context: ExecutionContext) -> str:
    parts: list[str] = []

    chunks = payload.get("chunks") or context.content_pool.get("chunks") or []
    if isinstance(chunks, list):
        for c in chunks:
            if isinstance(c, dict):
                parts.append(_norm_text(c.get("content") or c.get("text") or c))

    blocks = payload.get("multimodal_blocks") or context.content_pool.get("multimodal_blocks") or []
    if isinstance(blocks, list):
        for b in blocks:
            if isinstance(b, dict):
                parts.append(_norm_text(b.get("content") or b.get("markdown") or b))

    corpus = payload.get("corpus")
    if isinstance(corpus, str) and corpus.strip():
        parts.append(corpus.strip())

    return "\n".join([p for p in parts if p])


def heuristic_extract_constraints(text: str, *, snippet_max: int = 120) -> list[ConstraintObject]:
    found: list[ConstraintObject] = []
    lines = text.splitlines()
    for line in lines:
        s = line.strip()
        if not s:
            continue
        cid = uuid.uuid4().hex
        snip = (s[:snippet_max] + "…") if len(s) > snippet_max else s

        if "禁止" in s and ("材料" in s or "工艺" in s):
            m = re.search(
                r"材料\s*[：: ]\s*(?P<mat>[\w\d\-]+).*工艺\s*[：: ]\s*(?P<proc>[\w\d\-]+)|"
                r"工艺\s*[：: ]\s*(?P<proc2>[\w\d\-]+).*材料\s*[：: ]\s*(?P<mat2>[\w\d\-]+)",
                s,
            )
            mat = ""
            proc = ""
            if m:
                gd = {k: v for k, v in m.groupdict().items() if v}
                mat = gd.get("mat") or gd.get("mat2") or ""
                proc = gd.get("proc") or gd.get("proc2") or ""
            found.append(
                ConstraintObject(
                    constraint_id=cid,
                    kind=ConstraintKind.FORBID_PAIR,
                    predicates=PredicatePayload(material_a=mat or "__unspecified__", process_b=proc or "__unspecified__", text=snip),
                    nl_source=snip,
                    confidence=0.55 if mat or proc else 0.35,
                    applies_to=AppliesTo(ontology_type="Process"),
                )
            )

        m_ord = re.search(
            r"(?P<b>[^\s,\.;，]{2,})\s*(?:之前|先于|须在.*之前)\s*(?P<a>[^\s,\.;，]{2,})",
            s,
        )
        if m_ord:
            bef = str(m_ord.group("b")).strip()
            af = str(m_ord.group("a")).strip()
            found.append(
                ConstraintObject(
                    constraint_id=str(uuid.uuid4().hex),
                    kind=ConstraintKind.DEPENDS_ON,
                    predicates=PredicatePayload(requires_ordering_before=bef, text=f"{bef} BEFORE {af}"),
                    nl_source=snip,
                    confidence=0.5,
                    applies_to=AppliesTo(ontology_type="Operation"),
                )
            )

        m_th = re.search(r"(厚度).{0,8}(?P<op>[><≤≥])\s*(?P<v>\d+(\.\d+)?)", s.replace("≤", "<").replace("≥", ">"))
        if m_th:
            raw_op = m_th.group("op")
            v = float(m_th.group("v"))
            op = {"<": "lt", ">": "gt"}.get(raw_op, "gt")
            found.append(
                ConstraintObject(
                    constraint_id=str(uuid.uuid4().hex),
                    kind=ConstraintKind.THICKNESS_LIMIT,
                    predicates=PredicatePayload(text=snip, prop_key="thickness_mm", op=op, value=v),
                    nl_source=snip,
                    confidence=0.6,
                    applies_to=AppliesTo(ontology_type="Part"),
                )
            )

        m_te = re.search(r"(温度|淬火|回火).{0,14}(≤|<)\s*(?P<v>\d+(\.\d+)?)", s)
        if m_te:
            vmax = float(m_te.group("v"))
            found.append(
                ConstraintObject(
                    constraint_id=str(uuid.uuid4().hex),
                    kind=ConstraintKind.TEMPERATURE_LIMIT,
                    predicates=PredicatePayload(text=snip, prop_key="temperature_c", op="lte", temperature_c_max=vmax, value=vmax),
                    nl_source=snip,
                    confidence=0.45,
                    applies_to=AppliesTo(ontology_type="Process"),
                )
            )

    return found


class IndustrialConstraintSemanticExtractNode(BaseNode):
    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="constraint.extract",
            display_name="工业约束语义抽取（Runtime IR）",
            category="industrial_semantic_runtime",
            description="从 Chunk / multimodal_blocks 聚合文本抽取 ConstraintObject（禁止/依赖/阈值）。",
            implementation_status="partial",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(name="append_mode", label="Append Mode", type="boolean", required=False, default=True)
            ],
            semantic_inputs=["chunks", "multimodal_blocks"],
            semantic_outputs=["constraints", "constraint_state"],
            ontology_types=["Constraint"],
            constraint_dependencies=["constraint.runtime.filter"],
            runtime_state_dependencies=["constraint_state"],
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        payload = dict(input_data) if isinstance(input_data, dict) else {}
        corpus = _gather_corpus(payload, context)
        if not corpus.strip():
            return NodeResult(
                success=False,
                error="constraint.extract requires non-empty corpus",
                data=payload,
            )

        new_objs = heuristic_extract_constraints(corpus)
        as_dicts = [o.model_dump(mode="python") for o in new_objs]
        merged = merge_named_bucket_models(context, "constraints", as_dicts, id_key="constraint_id")
        context.constraint_state.register_active(as_dicts)

        payload["constraints"] = merged
        payload["constraint_extract_preview"] = corpus[:512]
        return NodeResult(success=True, data=payload, metadata={"count": len(merged)})

    def build_node_output(self, result: NodeResult, context: ExecutionContext):
        out = super().build_node_output(result, context)
        cnt = dict(result.metadata or {}).get("count")
        out.trace_events.append({"event_type": "constraint_materialized", "count": cnt, "node_id": self.node_id})
        return out
