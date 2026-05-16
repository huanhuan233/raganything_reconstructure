"""Runtime Constraint / Rule Engine 雏形（可解释过滤 + 变迁校验）。

不依赖 RDF/OWL；对上由 ``ConstraintObject`` / Pydantic dict 驱动。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence


@dataclass
class ExplainEntry:
    target_id: str
    constraint_id: str
    predicate: str
    reason_zh: str
    satisfied: bool
    operands: dict[str, Any] = field(default_factory=dict)


@dataclass
class TransitionVerdict:
    allowed: bool
    from_state: str
    to_state: str
    reason_zh: str
    violated_rule_ids: list[str] = field(default_factory=list)


def _normalize_state(s: str) -> str:
    return str(s or "").strip().lower()


class RuntimeConstraintEngine:
    """对候选对象字典执行过滤并生成解释条目。"""

    def evaluate(
        self,
        *,
        constraint: dict[str, Any],
        candidate: dict[str, Any],
    ) -> tuple[bool, ExplainEntry | None]:
        """单条约束对单候选求值。"""
        cid = str(constraint.get("constraint_id") or constraint.get("id") or "")
        ctype = str(constraint.get("kind") or "").lower()
        preds = constraint.get("predicates") or {}
        tgt = constraint.get("applies_to") or {}
        target_type = str(tgt.get("ontology_type") or "")
        ot = candidate.get("ontology_type")
        if hasattr(ot, "value"):
            ctype_cand = str(getattr(ot, "value", "") or "").lower()
        else:
            ctype_cand = str(ot or "").lower()

        explain_base = ExplainEntry(
            target_id=cid_target,
            constraint_id=cid or "__anon__",
            predicate=ctype,
            reason_zh="",
            satisfied=True,
            operands=dict(preds) if isinstance(preds, dict) else {},
        )

        if target_type and ctype_cand and target_type.lower() != ctype_cand:
            e = ExplainEntry(
                target_id=cid_target,
                constraint_id=cid or "__anon__",
                predicate=ctype,
                reason_zh=f"候选类型 `{ctype_cand}` 不匹配约束适用范围 `{target_type}`，跳过。",
                satisfied=True,
                operands=explain_base.operands,
            )
            return True, e

        if ctype == "forbid_pair":
            # （材料 × 工艺）类二元禁止：仅在 attributes 中同时命中时判定违反
            mat = preds.get("material_a")
            proc = preds.get("process_b")
            attrs = candidate.get("attributes") if isinstance(candidate.get("attributes"), dict) else {}
            if mat and proc and attrs.get("material") == mat and attrs.get("process") == proc:
                e = ExplainEntry(
                    target_id=cid_target,
                    constraint_id=cid,
                    predicate=ctype,
                    reason_zh=f"二元禁止：`材料={mat}` 不得与 `工艺={proc}` 共存。",
                    satisfied=False,
                    operands={"material": mat, "process": proc},
                )
                return False, e
            return True, None

        if ctype == "forbid_relation":
            rel = preds.get("relation")
            forb = preds.get("forbidden_target_kind") or preds.get("value")
            attrs = candidate.get("attributes") if isinstance(candidate.get("attributes"), dict) else {}
            if rel and forb and str(attrs.get("relation_kind") or "") == str(rel) and str(attrs.get("endpoint_kind") or "") == str(
                forb,
            ):
                e = ExplainEntry(
                    target_id=cid_target,
                    constraint_id=cid,
                    predicate=ctype,
                    reason_zh=f"违反禁止关系类型 `{rel}` → `{forb}`。",
                    satisfied=False,
                    operands={"relation": rel, "forbidden": forb},
                )
                return False, e
            return True, None

        if ctype in ("requires_before", "depends_on"):
            ordering = preds.get("requires_ordering_before")
            ordering = preds.get("before") if ordering is None else ordering
            if ordering:
                e = ExplainEntry(
                    target_id=cid_target,
                    constraint_id=cid,
                    predicate=ctype,
                    reason_zh=(
                        "序依赖需在状态/计划层校验（本节点仅存根条件）；"
                        f"要求在 `{ordering}` 之前。"
                    ),
                    satisfied=True,
                    operands={"before": ordering},
                )
                return True, e
            return True, None

        if ctype in ("must_not_rule", "must_rule"):
            phrase = str(preds.get("text") or "").strip()
            hay = "".join(
                [
                    str(candidate.get("label") or ""),
                    str(candidate.get("object_id") or ""),
                    str(candidate.get("attributes") or {}),
                ]
            ).lower()
            needle = phrase.lower()
            if ctype == "must_not_rule":
                if needle and needle in hay:
                    return False, ExplainEntry(
                        target_id=cid_target,
                        constraint_id=cid,
                        predicate=ctype,
                        reason_zh=f"命中「不得/禁止」类文本：`{phrase}`，与候选内容重叠。",
                        satisfied=False,
                        operands={"needle": needle},
                    )
                return True, None


            prop = preds.get("prop_key") or preds.get("property") or "thickness_mm"
            op = str(preds.get("op") or "gt")
            val = preds.get("value")
            cand_val = candidate.get(prop) or candidate.get("attributes", {}).get(prop)
            try:
                v = float(cand_val) if cand_val not in (None, "") else None
                thresh = float(val)
            except (TypeError, ValueError):
                e = ExplainEntry(
                    target_id=cid_target,
                    constraint_id=cid,
                    predicate=ctype,
                    reason_zh=f"无法将属性 `{prop}` 或阈值解析为数值。",
                    satisfied=False,
                    operands={"property": prop, "raw": cand_val},
                )
                return False, e

            if v is None:
                e = ExplainEntry(
                    target_id=cid_target,
                    constraint_id=cid,
                    predicate=ctype,
                    reason_zh=f"缺失数值属性 `{prop}`，阈值规则无法断言。",
                    satisfied=False,
                    operands={"property": prop},
                )
                return False, e

            ok = False
            if op == "gt":
                ok = v > thresh
            elif op == "gte":
                ok = v >= thresh
            elif op == "lt":
                ok = v < thresh
            elif op == "lte":
                ok = v <= thresh
            else:
                ok = False

            e = ExplainEntry(
                target_id=cid_target,
                constraint_id=cid,
                predicate=ctype,
                reason_zh=(
                    f"数值规则 `{prop} {op} {thresh}`：实际 `{v}`，"
                    f"{'满足' if ok else '不满足'}。"
                ),
                satisfied=ok,
                operands={"property": prop, "value": v, "op": op, "threshold": thresh},
            )
            return ok, e

        # 默认文本 must / forbid 短语：简单关键词
        txt = ""
        nl = preds.get("text") or preds.get("nl") or ""
        if nl:
            txt = str(nl).lower()
        if "禁止" in txt and str(candidate.get("label", "")).lower() in txt:
            return False, ExplainEntry(
                target_id=cid_target,
                constraint_id=cid,
                predicate="keyword_forbid",
                reason_zh=f"关键字禁止命中：候选 `{candidate.get('label')}`。",
                satisfied=False,
                operands={"snippet": nl},
            )
        return True, None

    def filter(
        self,
        *,
        constraints: Sequence[dict[str, Any]],
        candidates: Iterable[dict[str, Any]],
        explain_all: bool = False,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Returns:
            valid_objects, rejected_objects, explanations (dict 序列，便于序列化)
        """
        valid: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        explanations: list[dict[str, Any]] = []

        for cand in candidates:
            cdict = dict(cand) if isinstance(cand, dict) else {}
            ok_all = True
            for constraint in constraints:
                sat, explain = self.evaluate(constraint=dict(constraint), candidate=cdict)
                if explain is not None and (explain_all or not explain.satisfied):
                    explanations.append(self._explain_to_dict(explain))
                if not sat:
                    ok_all = False
            if ok_all:
                valid.append(cdict)
            else:
                explanations.append(
                    {
                        "target_id": str(cdict.get("object_id") or ""),
                        "constraint_id": "__aggregate__",
                        "predicate": "batch",
                        "reason_zh": "至少一条运行时约束不满足，条目被拒绝。",
                        "satisfied": False,
                        "operands": {},
                    }
                )
                rejected.append(cdict)

        return valid, rejected, explanations

    def explain(self, explanations: Sequence[dict[str, Any]]) -> str:
        lines = []
        for e in explanations:
            lines.append(
                f"[{e.get('constraint_id','?')}] {e.get('target_id','?')}: "
                f"{e.get('reason_zh','')}"
            )
        return "\n".join(lines) if lines else "(无)"

    def validate_transition(
        self,
        *,
        from_state: str,
        to_state: str,
        forbidden_edges: Iterable[tuple[str, str]],
        required_order: Sequence[tuple[str, str]] | None,
        emitted_sequence: Sequence[str],
    ) -> TransitionVerdict:
        """极简变迁校验：黑名单边 + （可选）已执行序中的先后关系。"""
        fs = _normalize_state(from_state)
        ts = _normalize_state(to_state)
        violated: list[str] = []
        for a, b in forbidden_edges:
            if _normalize_state(a) == fs and _normalize_state(b) == ts:
                violated.append(f"FORBIDDEN:{a}->{b}")
                return TransitionVerdict(
                    allowed=False,
                    from_state=from_state,
                    to_state=to_state,
                    reason_zh=f"命中禁止变迁 `{from_state}` → `{to_state}`。",
                    violated_rule_ids=violated,
                )

        emitted = [_normalize_state(x) for x in emitted_sequence]

        def _depends_ok(before_label: str, after_label: str) -> tuple[bool, str]:
            bef = _normalize_state(before_label)
            aft = _normalize_state(after_label)
            # 若在 emitted 中出现，要求 before 的索引小于 after
            if bef not in emitted or aft not in emitted:
                return True, "序约束未在执行轨迹中完备出现，暂不判失败。"
            if emitted.index(bef) > emitted.index(aft):
                return False, (
                    f"违反所需顺序：`{before_label}` 须在 `{after_label}` 之前；"
                    f"当前轨迹 {list(emitted_sequence)}。"
                )
            return True, ""

        if required_order:
            for b, a in required_order:
                ok, msg = _depends_ok(b, a)
                if not ok:
                    violated.append(f"ORDER:{b}before{a}")
                    return TransitionVerdict(
                        allowed=False,
                        from_state=from_state,
                        to_state=to_state,
                        reason_zh=msg,
                        violated_rule_ids=violated,
                    )

        return TransitionVerdict(
            allowed=True,
            from_state=from_state,
            to_state=to_state,
            reason_zh="变迁在禁止集与必需序（若给定）下通过。",
            violated_rule_ids=[],
        )

    @staticmethod
    def _explain_to_dict(e: ExplainEntry) -> dict[str, Any]:
        return {
            "target_id": e.target_id,
            "constraint_id": e.constraint_id,
            "predicate": e.predicate,
            "reason_zh": e.reason_zh,
            "satisfied": e.satisfied,
            "operands": dict(e.operands),
        }


# 惰性单例可选
_default_engine = RuntimeConstraintEngine()


def eval_constraint(**kwargs: Any) -> tuple[bool, ExplainEntry | None]:
    return _default_engine.evaluate(**kwargs)

